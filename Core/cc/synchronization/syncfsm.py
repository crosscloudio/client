"""CrossCloud Sync Finite State Machine
"""
import logging
import os
import threading

from copy import deepcopy

import yaml

import cc.ipc_gui
from cc import path
from cc.synctask import (CancelSyncTask, CompareSyncTask, CreateDirSyncTask,
                         DeleteSyncTask, DownloadSyncTask, MoveSyncTask,
                         PathWithStorageAndVersion, UploadSyncTask)

__author__ = 'crosscloud GmbH'
logger = logging.getLogger(__name__)

# FSM states
S_DELETING = 'S_ST_DELETING'
S_SELF_CHECK = 'S_SELF_CHECK'
S_SYNCED = 'S_SYNCED'
S_DOWNLOADING = 'S_DOWNLOADING'
S_UPLOADING = 'S_UPLOADING'
S_CANCELLING = 'S_CANCELLING'
S_UNKNOWN = 'S_UNKNOWN'

S_RESOLVING = 'S_RESOLVING'
S_COMPARING = 'S_COMPARING'

FILESYSTEM_ID = 'local'

# dict keys
SE_FSM = 'se_fsm'
SYNC_TASK_STATE = 'sync_task_state'
STORAGE_FEEDBACK = 'storage_feedback'
MODIFIED_DATE = 'modified_date'
STORAGE_ID = 'storage_id'
STORAGE = 'storage'
IS_DIR = 'is_dir'
SIZE = 'size'
SHARE_ID = 'share_id'
PUBLIC_SHARE = 'public_share'
DISPLAY_NAME = 'display_name'
EVENT_PROPS = 'event_props'
DOWNLOADED = 'DOWNLOADED'
UPLOADED = 'UPLOADED'
TRIGGER = 'trigger'
STATE = 'state'
DELETING = 'DELETING'
DELETED = 'DELETED'
DOWNLOADING = 'DOWNLOADING'
UPLOADING = 'UPLOADING'
MOVING = 'MOVING'
MOVED = 'MOVED'

SYNC_TASK_RUNNING = 'sync_task_running'
SYNC_TASK_FAILED = 'sync_task_failed'
EVENT_RECEIVED = 'event_received'
STORAGE_PRESELECT = 'storage_preselect'


# *************************************************************
# ***************************** FSM ***************************
# *************************************************************

def on_deleting(event):
    '''
    checks if all sync tasks are acked and the item is DELETED on all storages
    '''
    logger.debug('Checking if node is done with deleting %s %s',
                 event.node.path,
                 event.node.props)

    new_equivalents = event.node.props['equivalents'].get('new', {})

    if not new_equivalents and \
            all((st.get('deleted', False) for st in event.node.props[STORAGE].values())):
        # delete the whole node
        logger.debug('Done with deleting. Destroying node for path %s', event.node.path)
        event.node.delete()
        event.fsm.e_node_deleted(node=event.node,
                                 csps=event.csps,
                                 task_sink=event.task_sink)
        return

    storages = event.node.props[STORAGE]

    tasks = \
        {st for st in storages.keys()
         if 'sync_task_running' in storages[st]}
    success_tasks = \
        {st for st in storages.keys()
         if storages[st].get('deleted', False) and 'sync_task_running' in storages[st]}
    running_tasks = \
        {st for st in storages.keys()
         if storages[st].get('sync_task_running', False)}
    failed_tasks = \
        {st for st in storages.keys()
         if not storages[st].get('sync_task_running', False) and
         storages[st].get('sync_task_failed', False)}

    current_state_running = {(st, storages[st].get('version_id')) for st in running_tasks
                             if storages[st].get('version_id') is not None}

    if tasks == success_tasks.union(failed_tasks) and not running_tasks:
        event.fsm.e_all_done(node=event.node,
                             csps=event.csps,
                             task_sink=event.task_sink)

    elif new_equivalents and not current_state_running.issubset(new_equivalents.items()):
        event.fsm.e_cancel_all(node=event.node,
                               csps=event.csps,
                               task_sink=event.task_sink)


def while_issue_upload(event):
    """ Issue Upload Handler
    Issues upload tasks and prepares the node's storage props with status information
    :param event: the event with event.target_storage_ids as a list of storages
        to issue a upload
    :return: None
    """
    logger.debug('%s to %s', event.node.path,
                 event.target_storage_ids)

    for storage_id in event.target_storage_ids:
        event.node.props[STORAGE].setdefault(storage_id, {})[SYNC_TASK_RUNNING] = True
        event.node.props[STORAGE].setdefault(storage_id, {})['sync_task_source'] = \
            FILESYSTEM_ID
        event.node.props[STORAGE].setdefault(storage_id, {})[
            'sync_task_source_version'] = \
            event.node.props[STORAGE].get(FILESYSTEM_ID, {}).get('version_id')
        if event.node.props[STORAGE][FILESYSTEM_ID][IS_DIR]:
            event.task_sink(
                CreateDirSyncTask(
                    path=event.node.path,
                    target_storage_id=storage_id,
                    source_storage_id=FILESYSTEM_ID,
                    target_path=get_storage_path(event.node,
                                                 storage_id,
                                                 FILESYSTEM_ID),
                    source_path=get_storage_path(event.node,
                                                 FILESYSTEM_ID),
                    source_version_id=event.node.props[STORAGE][FILESYSTEM_ID].get(
                        'version_id')
                ))
        else:
            event.task_sink(UploadSyncTask(
                path=event.node.path,
                target_storage_id=storage_id,
                target_path=get_storage_path(event.node, storage_id, FILESYSTEM_ID),
                source_version_id=event.node.props[STORAGE][FILESYSTEM_ID]['version_id'],
                source_path=get_storage_path(event.node, FILESYSTEM_ID),
                original_version_id=event.node.props[STORAGE].get(storage_id, {}).get(
                    'version_id')))


def while_issue_download(event):
    """ Issue Download Handler
    Issues download tasks and prepares the node's storage props with status information
    :param event: the event with event.sourcce_storage_ids as the storages
        to issue a download
    :return: None
    """

    # 1) get CSPs where to sync via the equivalent list
    logger.debug('%s from %s', event.node.path,
                 event.source_storage_id)

    event.node.props[STORAGE].setdefault(FILESYSTEM_ID, {})[SYNC_TASK_RUNNING] = True
    event.node.props[STORAGE][FILESYSTEM_ID]['sync_task_source'] = event.source_storage_id
    event.node.props[STORAGE][FILESYSTEM_ID]['sync_task_source_version'] = \
        event.node.props[STORAGE].get(event.source_storage_id, {}).get('version_id')
    if not event.node.props[STORAGE][event.source_storage_id][IS_DIR]:
        event.task_sink(DownloadSyncTask(
            path=event.node.path,
            source_storage_id=event.source_storage_id,
            source_version_id=event.node.props[STORAGE][event.source_storage_id][
                'version_id'],
            source_path=get_storage_path(event.node, event.source_storage_id),
            target_path=get_storage_path(event.node, FILESYSTEM_ID,
                                         event.source_storage_id),
            original_version_id=event.node.props[STORAGE].get(
                FILESYSTEM_ID, {}).get('version_id')))
    else:
        event.task_sink(
            CreateDirSyncTask(path=event.node.path,
                              target_storage_id=FILESYSTEM_ID,
                              target_path=get_storage_path(event.node,
                                                           FILESYSTEM_ID,
                                                           event.source_storage_id),
                              source_storage_id=event.source_storage_id,
                              source_path=get_storage_path(event.node,
                                                           event.source_storage_id)))


def while_issue_delete(event):
    """ Issue Delete Handler
    Issues delete tasks and prepares the node's storage props with status information
    :param event: the event with event.target_storage_ids as a list of storages
        to issue a delete
    :return: None
    """
    logger.debug('%s from %s', event.node.path,
                 event.target_storage_ids)
    for storage_id in event.target_storage_ids:
        event.node.props[STORAGE].setdefault(storage_id, {})[SYNC_TASK_RUNNING] = True
        event.task_sink(DeleteSyncTask(
            path=event.node.path,
            target_storage_id=storage_id,
            target_path=get_storage_path(event.node, storage_id),
            original_version_id=event.node.props[STORAGE][storage_id]['version_id']
        ))


def on_downloading(event):
    """ Downloading State Handler
    Checks if all downloads are successfull or detects conflicts
    :param event:
    :return:
    """
    source = event.node.props[STORAGE][FILESYSTEM_ID]['sync_task_source']
    return on_up_download_check(event, source)


def on_uploading(event):
    """ Uploading State Handler
    Checks if all downloads are successfull or detects conflicts
    :param event:
    :return:
    """
    return on_up_download_check(event, FILESYSTEM_ID)


def on_up_download_check(event, source_storage_id):
    """
    Checks running up and downloads for finished operations or failures.
    :param event:
    :param source_storage_id: the source storage id
    :return:
    """
    # TODO: assert SYNC_TASK_RUNNING and SYNC_TASK_FAILED
    logger.debug('path: %s', event.node.path)
    logger.debug('equivalent list %s', event.node.props.get('equivalents'))
    logger.debug('storage list %s', event.node.props.get(STORAGE))
    logger.debug('desired_storages list %s', event.node.props.get('desired_storages'))

    storages = event.node.props.setdefault(STORAGE, {})
    desired_storages = event.node.props['desired_storages']
    new_equivalents = event.node.props.get('equivalents', {}).get('new', {})
    old_equivalents = event.node.props.get('equivalents', {}).get('old', {})

    # get the actual state from all storages in the desired_storages list
    current_state_finished_suc = \
        {st: storages[st].get('version_id') for st in desired_storages
         if st in storages and  # and not storages[st].get('sync_task_failed') and
         not storages[st].get('sync_task_running', False) and
         'version_id' in storages[st] and
         storages[st]['version_id'] != old_equivalents.get(st) and
         st != source_storage_id}

    current_state = {st: storages[st].get('version_id') for st in desired_storages
                     if st in storages and not storages[st].get('sync_task_failed')}

    # check all storage if anything changed
    for store in storages:
        source_storage = storages[store].get('sync_task_source')
        if source_storage is not None:
            version_id = storages[source_storage].get('version_id')
            source_version_id = storages[store].get('sync_task_source_version',
                                                    version_id)
            if version_id != source_version_id:
                logger.debug('Cancel all, because something has changed')
                event.fsm.e_cancel_all(node=event.node, csps=event.csps,
                                       task_sink=event.task_sink)
                return

    if current_state_finished_suc and new_equivalents and \
            not set(current_state_finished_suc.items()).issubset(new_equivalents.items()):
        logger.debug('Cancel all')
        event.fsm.e_cancel_all(node=event.node, csps=event.csps,
                               task_sink=event.task_sink)
        return

    if any((storages[st].get(SYNC_TASK_RUNNING, False)
            for st in event.node.props['desired_storages'] if st in storages)):
        logger.debug('There are still running tasks. Waiting all to be done.')
        return

    # either the current state is as supposed or there was no sync task completed,therfore
    # no new equivalents
    if set(new_equivalents.items()).issubset(current_state.items()) or \
            not new_equivalents:
        logger.debug('Up/Download done.')
        event.fsm.e_all_done(node=event.node, csps=event.csps, task_sink=event.task_sink)

    logger.debug('I did nothing')


# pylint: disable=too-many-statements, too-many-branches, too-many-return-statements,
# pylint: disable=too-many-locals
def on_synced(event):
    """ State Handler for Synced State
    Checks the current state and triggers transitions if necessary
    :param event:
    :return:
    """
    logger.debug('path: %s', event.node.path)

    if event.node.props.get('invalid_op'):
        del event.node.props['invalid_op']
        logger.info("Invalid Operation")
        return

    _cleanup_node(event.node, event.csps)

    new_equivalents = event.node.props.setdefault('equivalents', {}).setdefault('new', {})
    old_equivalents = event.node.props.setdefault('equivalents', {}).setdefault('old', {})
    storages = event.node.props.setdefault(STORAGE, {})

    current_state = \
        {storage_id: storages[storage_id].get('version_id') for storage_id in
         storages.keys()}

    current_storages = set(storages.keys())

    if current_storages == set():
        logger.info("No storages -> delete node")
        # no storages -> delete this node from the tree
        event.node.delete()
        return

    # determine desired state
    # check if there are syncrules and clean them from invalid values

    desired_storages = event.node.props.setdefault('desired_storages', set())
    desired_storages.add(FILESYSTEM_ID)
    desired_storages.add(event.csps[0].storage_id)

    if logger.level <= logging.DEBUG:
        # here we log out the input of the function in a yaml format the test_on_synced can test
        props_copy = deepcopy(dict(event.node.props))
        props_copy.pop('se_fsm', None)
        test_case = {'node': props_copy}
        logger.debug('on_synced testcase:\n%s', yaml.dump(test_case))

    # nothing to do?
    if set(new_equivalents.items()) == \
            set(current_state.items()) and new_equivalents.keys() == desired_storages:
        logger.debug('in desired state')
        event.node.props['equivalents']['old'] = {}
        return

    if not new_equivalents:
        logger.debug('fresh sync, no equivalents')
        if len(current_storages) > 1:
            logger.debug('conflict, versions without version info (path: %s)',
                         event.node.path)
            # we have no version info, but more then one existences of a file
            event.fsm.e_conflicted(node=event.node,
                                   task_sink=event.task_sink)
            return
        else:
            # we have one version of the file somewhere, distribute it!
            if FILESYSTEM_ID not in current_storages:
                event.fsm.e_issue_download(node=event.node,
                                           task_sink=event.task_sink,
                                           source_storage_id=list(current_storages)[0])
                return
            else:
                event.fsm.e_issue_upload(node=event.node,
                                         task_sink=event.task_sink,
                                         target_storage_ids=desired_storages - {
                                             FILESYSTEM_ID})
                return
    else:
        if desired_storages == current_storages:
            # storage lists are equal -> check if versions are equal
            unsynced = set(current_state.items()) - set(new_equivalents.items())
            if len(unsynced) > 1:
                # conflict, because more then one storage changed
                event.fsm.e_conflicted(node=event.node,
                                       task_sink=event.task_sink)
                return
            elif len(unsynced) == 0:
                # do nothing
                logger.debug('Node is in desired state but equivalents changed')
                new_equivalents = current_state
                logger.debug('new equivalents: %s', new_equivalents)
                return
            else:
                storage_id, version_id = list(unsynced)[0]
                if not old_equivalents:
                    # we are coming from a clean sync state
                    if storage_id == FILESYSTEM_ID:
                        event.fsm.e_issue_upload(
                            target_storage_ids=desired_storages - {FILESYSTEM_ID},
                            node=event.node,
                            task_sink=event.task_sink)
                        return
                    else:
                        event.fsm.e_issue_download(
                            source_storage_id=storage_id,
                            node=event.node,
                            task_sink=event.task_sink)
                        return
                else:
                    # either a loop for syncrules -> first down- and then upload OR
                    # a change on a storage while a down- or upload operation
                    if (storage_id, version_id) in set(old_equivalents.items()):

                        # we are in the down- upload loop for the syncrules
                        event.fsm.e_issue_upload(
                            target_storage_ids={storage_id},
                            node=event.node,
                            task_sink=event.task_sink)
                        return
                    else:
                        # conflict, because a csp changed while the previous download
                        event.fsm.e_conflicted(node=event.node,
                                               task_sink=event.task_sink)
                        return

        else:
            # desired and current storages are different
            missing_on = desired_storages - current_storages
            unwanted_on = current_storages - desired_storages
            if unwanted_on:
                for unwanty in unwanted_on:
                    if unwanty not in new_equivalents:
                        # never heared about that -> conflict (external conflict)
                        event.fsm.e_conflicted(node=event.node,
                                               task_sink=event.task_sink)
                    else:
                        # syncrule update
                        event.fsm.e_issue_delete(target_storage_ids=unwanted_on,
                                                 node=event.node,
                                                 task_sink=event.task_sink)
                return
            elif missing_on:
                current_equivalents = \
                    set(current_state.items()).intersection(new_equivalents.items())
                storages_in_sync = set((x for x, _ in current_equivalents))
                if any(((missing in new_equivalents) for missing in missing_on)) \
                        and storages_in_sync:
                    # the file was delete from a storage where it was in sync before
                    event.fsm.e_issue_delete(target_storage_ids=storages_in_sync,
                                             node=event.node,
                                             task_sink=event.task_sink)
                    return
                else:
                    if FILESYSTEM_ID in missing_on:
                        event.fsm.e_issue_download(
                            node=event.node,
                            task_sink=event.task_sink,
                            source_storage_id=list(current_storages)[0])
                    else:
                        event.fsm.e_issue_upload(target_storage_ids=missing_on,
                                                 node=event.node,
                                                 task_sink=event.task_sink)
                    return
    logger.fatal('Not able to determine action for this node',
                 extra={'path': event.node.path, 'props': event.node.props})
    assert True


def _cleanup_node(node, csps):
    """
    Cleans the node from unused elements
    :param node: the node
    :param csps: current csps
    """

    storages = node.props.get(STORAGE, {})
    available_csps = [storage.storage_id for storage in csps]
    available_csps.append(FILESYSTEM_ID)
    # cleanup nodes if they have storages flagged as deleted
    for storage_id, storage in list(storages.items()):
        if SYNC_TASK_RUNNING in storage:
            del storage[SYNC_TASK_RUNNING]
        if SYNC_TASK_FAILED in storage:
            del storage[SYNC_TASK_FAILED]
        if EVENT_RECEIVED in storage:
            del storage[EVENT_RECEIVED]
        if 'sync_task_source' in storage:
            del storage['sync_task_source']
        if 'sync_task_source_version' in storage:
            del storage['sync_task_source_version']
        if storage.get('deleted') or not storage:
            del storages[storage_id]
        if storage_id not in available_csps:
            del storages[storage_id]

    # cleanup equivalent list
    new_equivalents = node.props.setdefault('equivalents', {}).setdefault('new', {})
    old_equivalents = node.props.setdefault('equivalents', {}).setdefault('old', {})
    for storage_id in list(new_equivalents.keys()):
        if storage_id not in available_csps:
            del new_equivalents[storage_id]
    if len(new_equivalents) < 2:
        new_equivalents.clear()

    if 'tasks_cancelled' in node.props:
        del node.props['tasks_cancelled']
    if 'comp_task_received' in node.props:
        del node.props['comp_task_received']

    # remove all unused elemts from old_equivalents
    for storage_id in new_equivalents:
        old_equivalents.pop(storage_id, None)

    # remove storage preselection
    if new_equivalents and STORAGE_PRESELECT in node.props:
        # preselection can be removed if the node has equivalents
        del node.props[STORAGE_PRESELECT]


def on_resolving(event):
    """
    Handler for (re) entering resolving state. Will wait until all move actions have been
    acked. Normally it has to wait for the successful storage events as well, here it will
     only wait until all storages sent a delete to the node
    :return:
    """
    logger.debug('path: %s', event.node.path)
    storages = event.node.props[STORAGE]

    moving = [storage_id for storage_id, st in storages.items() if
              st.get(SYNC_TASK_STATE) == MOVING]

    if not moving:
        # if there is nothing to move anymore
        moved = [storage_id for storage_id, st in storages.items()
                 if st.get(SYNC_TASK_STATE) == MOVED]

        logger.debug('waiting for storage move events')

        # check if all moved items are deleted
        if all(storages[storage_id].get('deleted') for storage_id in moved):
            logger.debug('resolving done')
            event.fsm.e_all_done(node=event.node,
                                 csps=event.csps,
                                 task_sink=event.task_sink)
    else:
        logger.debug('still moving files on %s', moving)


def while_conflicted(event):
    """Handle to issue Compare Tasks"""
    logger.debug('Conflict resolving')
    storage_id_paths = []
    storage = event.node.props[STORAGE].keys()

    # keep sorted to be deterministic, can be removed with py36
    for csp in sorted(storage):
        storage_path = get_storage_path(event.node, csp)
        storage_id_paths.append(
            PathWithStorageAndVersion(storage_id=csp,
                                      path=storage_path,
                                      expected_version_id=None,
                                      is_dir=event.node.props[STORAGE][csp][IS_DIR]))

    task = CompareSyncTask(event.node.path, storage_id_paths)
    event.task_sink(task)


def on_comparing(event):
    """
    Handler for comparing conflicting files
    """
    new_equivalents = event.node.props.setdefault('equivalents', {}).setdefault('new', {})
    storages = event.node.props.setdefault(STORAGE, {})

    # check if any other event was received
    if any((event.node.props[STORAGE][sid].get(EVENT_RECEIVED) for sid in storages)):
        # Cancel this compare operation
        event.fsm.e_cancel_all(node=event.node, task_sink=event.task_sink,
                               csps=event.csps)
        return

    current_state = \
        {storage_id: storages[storage_id].get('version_id') for storage_id in
         storages.keys()}
    if event.node.props.get('comp_task_received'):
        if new_equivalents == current_state:
            event.fsm.e_equal(node=event.node, task_sink=event.task_sink, csps=event.csps)
        else:
            event.fsm.e_resolve_different(node=event.node, task_sink=event.task_sink,
                                          csps=event.csps,
                                          equivalents=event.task.equivalents)


def while_resolve_different(event):
    """
    Handler to resolve conflicts
    :param event: event.resolve_on as a list of storages where to resolve the conflict
    :return:
    """
    logger.debug('resolving conflict for %s', event.equivalents)
    storages = event.node.props[STORAGE]

    # rearrange nodes in tree
    for storage_ids in event.equivalents:
        if FILESYSTEM_ID in storage_ids:
            # we are not renaming local conflicts, but the others
            continue

        # there is only one storage id
        storage_id, = storage_ids

        display_path = os.path.sep.join(get_storage_path(event.node, storage_id))

        # displaying notification to let user know what conflicted
        # TODO: handling in a seperate thread is a temporary soltion, we want slots here!
        threading.Thread(target=cc.ipc_gui.displayNotification,
                         args=('Conflict Detected', 'The file "{}" has conflicts '
                                                    ' Check the sync '
                                                    'log to review.'.format(display_path)),
                         daemon=True).start()

        for storage_id in storage_ids:
            display_name = storages[storage_id][DISPLAY_NAME]
            new_filename = \
                path.rename_file(display_name,
                                 '{} (Conflicting copy)'.format(display_name))
            new_path = get_storage_path(event.node.parent, storage_id) + [new_filename]
            old_path = get_storage_path(event.node, storage_id)
            assert not event.node.parent.has_child(new_filename)

            # the new node will be created by the storage events
            # it is just important to remove them from the desired list, since they are
            # not desired any longer. There might be no entry, so we use discard
            event.node.props['desired_storages'].discard(storage_id)

            event.task_sink(MoveSyncTask(
                path=event.node.path,
                source_path=old_path,
                source_version_id=storages[storage_id][
                    'version_id'],
                source_storage_id=storage_id,
                target_path=new_path))

            storages[storage_id][SYNC_TASK_STATE] = MOVING


def while_e_cancel_all(event):
    """
    Cancel all events
    :param event:
    :return:
    """
    logger.debug('issue cancel task for %s while in state %s', event.node.path,
                 event.fsm.current)
    event.node.props['tasks_cancelled'] = False
    event.task_sink(CancelSyncTask(path=event.node.path))


def on_cancelling(event):
    """
    Handler for on cancelling
    """
    storages = event.node.props.setdefault(STORAGE, {})

    # storages which tasks are acknowledged with success
    ack_succ_tasks = {storage_id for storage_id in storages
                      if SYNC_TASK_RUNNING in storages[storage_id] and
                      not storages[storage_id][SYNC_TASK_RUNNING] and
                      not storages[storage_id][SYNC_TASK_FAILED]}

    # storages which received an event
    finished = {storage_id for storage_id in storages
                if SYNC_TASK_RUNNING in storages[storage_id] and
                storages[storage_id].get(EVENT_RECEIVED, False)}

    if event.node.props['tasks_cancelled']:
        if not ack_succ_tasks or (ack_succ_tasks and ack_succ_tasks == finished):
            # all successful synctask resulted in a storage event -> done
            logger.debug('everything cancelled for node %s - storages: %s',
                         event.node.path, storages)
            event.fsm.e_all_cancelled(node=event.node,
                                      csps=event.csps,
                                      task_sink=event.task_sink)
            return

    logger.debug('waiting for additional events for path %s - storages: %s',
                 event.node.path, storages)


FSM_NODE_CONFIG = {'initial': S_UNKNOWN,
                   'events': [
                       # Synced state
                       {'name': 'e_created', 'src': S_UNKNOWN,
                        'dst': S_SYNCED},
                       {'name': 'e_modified', 'src': S_UNKNOWN,
                        'dst': S_SYNCED},

                       {'name': 'e_created', 'src': S_SYNCED,
                        'dst': '='},

                       # Uploading
                       {'name': 'e_st_ack', 'src': S_UPLOADING,
                        'dst': '='},
                       {'name': 'e_created', 'src': S_UPLOADING,
                        'dst': '='},
                       {'name': 'e_modified', 'src': S_UPLOADING,
                        'dst': '='},
                       {'name': 'e_all_done', 'src': S_UPLOADING,
                        'dst': S_SYNCED},
                       {'name': 'e_issue_upload', 'src': S_SYNCED,
                        'dst': S_UPLOADING},
                       {'name': 'e_deleted', 'src': S_UPLOADING,
                        'dst': '='},
                       {'name': 'e_cancel_all', 'src': S_UPLOADING,
                        'dst': S_CANCELLING},

                       # DOWNLOADING
                       {'name': 'e_st_ack', 'src': S_DOWNLOADING,
                        'dst': '='},
                       {'name': 'e_created', 'src': S_DOWNLOADING,
                        'dst': '='},
                       {'name': 'e_modified', 'src': S_DOWNLOADING,
                        'dst': '='},
                       {'name': 'e_deleted', 'src': S_DOWNLOADING,
                        'dst': '='},
                       {'name': 'e_all_done', 'src': S_DOWNLOADING,
                        'dst': S_SYNCED},
                       {'name': 'e_issue_download', 'src': S_SYNCED,
                        'dst': S_DOWNLOADING},
                       {'name': 'e_cancel_all', 'src': S_DOWNLOADING,
                        'dst': S_CANCELLING},

                       # Local Modify
                       {'name': 'e_modified', 'src': S_SYNCED,
                        'dst': '='},

                       # Delete (local and remote)
                       {'name': 'e_deleted', 'src': S_SYNCED,
                        'dst': '='},
                       {'name': 'e_issue_delete', 'src': S_SYNCED,
                        'dst': S_DELETING},
                       {'name': 'e_st_ack', 'src': S_DELETING,
                        'dst': '='},
                       {'name': 'e_deleted', 'src': S_DELETING,
                        'dst': '='},
                       {'name': 'e_modified', 'src': S_DELETING,
                        'dst': '='},
                       {'name': 'e_created', 'src': S_DELETING,
                        'dst': '='},
                       {'name': 'e_cancel_all', 'src': S_DELETING,
                        'dst': S_CANCELLING},
                       {'name': 'e_node_deleted', 'src': S_DELETING,
                        'dst': S_UNKNOWN},
                       {'name': 'e_all_done', 'src': S_DELETING,
                        'dst': S_SYNCED},

                       # Resolving
                       {'name': 'e_conflicted', 'src': S_SYNCED,
                        'dst': S_COMPARING},
                       {'name': 'e_resolve_different', 'src': S_COMPARING,
                        'dst': S_RESOLVING},
                       {'name': 'e_created', 'src': S_COMPARING,
                        'dst': S_COMPARING},
                       {'name': 'e_deleted', 'src': S_COMPARING,
                        'dst': S_COMPARING},
                       {'name': 'e_cancel_all', 'src': S_COMPARING,
                        'dst': S_CANCELLING},
                       {'name': 'e_modified', 'src': S_COMPARING,
                        'dst': S_COMPARING},
                       {'name': 'e_equal', 'src': S_COMPARING,
                        'dst': S_SYNCED},
                       {'name': 'e_comp_ack', 'src': S_COMPARING,
                        'dst': '='},
                       {'name': 'e_st_move_success', 'src': S_RESOLVING,
                        'dst': '='},
                       {'name': 'e_st_move_failed', 'src': S_RESOLVING,
                        'dst': '='},
                       {'name': 'e_created', 'src': S_RESOLVING,
                        'dst': '='},
                       {'name': 'e_deleted', 'src': S_RESOLVING,
                        'dst': '='},
                       {'name': 'e_all_done', 'src': S_RESOLVING,
                        'dst': S_SYNCED},

                       # to trigger a check
                       {'name': 'e_check', 'src': S_SYNCED,
                        'dst': '='},

                       # S_CANCELLING
                       {'name': 'e_deleted', 'src': S_CANCELLING,
                        'dst': '='},
                       {'name': 'e_modified', 'src': S_CANCELLING,
                        'dst': '='},
                       {'name': 'e_st_ack', 'src': S_CANCELLING,
                        'dst': '='},
                       {'name': 'e_created', 'src': S_CANCELLING,
                        'dst': '='},
                       {'name': 'e_all_cancelled', 'src': S_CANCELLING,
                        'dst': S_SYNCED}

                   ],
                   'callbacks': {
                       # event callbacks
                       'onbeforee_issue_upload': while_issue_upload,
                       'onbeforee_issue_delete': while_issue_delete,
                       'onenterS_UPLOADING': on_uploading,
                       'onreenterS_UPLOADING': on_uploading,
                       'onenterS_DOWNLOADING': on_downloading,
                       'onreenterS_DOWNLOADING': on_downloading,
                       'onbeforee_issue_download': while_issue_download,
                       'onbeforee_resolve_different': while_resolve_different,
                       'onbeforee_conflicted': while_conflicted,
                       'onenterS_SYNCED': on_synced,
                       'onreenterS_SYNCED': on_synced,
                       'onenterS_ST_DELETING': on_deleting,
                       'onreenterS_ST_DELETING': on_deleting,
                       'onenter' + S_RESOLVING: on_resolving,
                       'onreenter' + S_RESOLVING: on_resolving,
                       'onbeforee_cancel_all': while_e_cancel_all,
                       'onenterS_CANCELLING': on_cancelling,
                       'onreenterS_CANCELLING': on_cancelling,
                       'onenterS_COMPARING': on_comparing,
                       'onreenterS_COMPARING': on_comparing
                   }}


def get_storage_path(node, target_storage_id, source_storage_id=None):
    """
    Determines the case sensitive path for a storage
    :return: the display path
    """
    new_path = []
    for elem in node.iter_up:
        if elem.parent is None:
            continue
        if DISPLAY_NAME in elem.props.get(STORAGE, {}).get(target_storage_id, {}):
            new_path.append(elem.props[STORAGE][target_storage_id][DISPLAY_NAME])
        elif DISPLAY_NAME in elem.props.get(STORAGE, {}).get(source_storage_id, {}):
            new_path.append(elem.props[STORAGE][source_storage_id][DISPLAY_NAME])
        else:
            new_path.append(elem.name)
    return list(reversed(new_path))


class NoStorageForFileException(Exception):
    """
    Exception for the case that there is no csp with enough free space
    for a file
    """
