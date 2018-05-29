"""CrossCloud SyncEngine."""
# pylint: disable=too-many-instance-attributes,wrong-import-order
import copy
import logging
import time
from collections import namedtuple
from datetime import datetime
from pprint import pformat

import fysom
from blinker import Signal
from bushn import DELETE, Node
from pykka.proxy import priority
from pykka.threading import ThreadingActorPriorityMailbox

import cc.ipc_gui
from cc.path import normalize_path_element
from cc.synchronization.syncfsm import (DISPLAY_NAME, EVENT_RECEIVED,
                                        FILESYSTEM_ID, FSM_NODE_CONFIG, IS_DIR,
                                        MOVED, PUBLIC_SHARE, S_SYNCED, SE_FSM,
                                        SHARE_ID, SIZE, STORAGE,
                                        SYNC_TASK_FAILED, SYNC_TASK_RUNNING,
                                        SYNC_TASK_STATE, get_storage_path)
from cc.synctask import (CancelSyncTask, CompareSyncTask, CreateDirSyncTask,
                         DeleteSyncTask, DownloadSyncTask, FetchFileTreeTask,
                         MoveSyncTask, SyncTask, UploadSyncTask)
from enum import Enum
from jars import SHARED

__author__ = 'crosscloud GmbH'
logger = logging.getLogger(__name__)

# pylint: disable=invalid-name
SharedState = namedtuple('SharedState', field_names=['storage_id',
                                                     'share_id',
                                                     'public_shared'])


class SyncEngineState(Enum):
    """Possible states of the SyncEngine.

    :members:
    """

    #: Sync engine has stopped, value 0
    STOPPED = 0
    #: Sync engine is initializing, value 1
    STATE_SYNC = 1
    #: Sync engine is running, value 2
    RUNNING = 2
    # Offline state means that the  storage is not reachable
    #: SYnc engine has stopped due to storage being unreachable, value 3
    OFFLINE = 3


class ItemHasNoStorageException(Exception):
    """Raise if an operation on a path is not able to determine the according storage."""


class SyncEngine(ThreadingActorPriorityMailbox):
    """Responsible to keep two StorageProviders in Sync.

    All functions started with 'storage_' are called by the storages, that is from the jars module.
    """

    # pylint: disable=too-many-arguments, too-many-public-methods
    def __init__(self, storage_metrics, task_sink, model=None):
        super().__init__(self)
        if model is not None:
            self.root_node = model
        else:
            self.root_node = Node(name=None)

        self.state = SyncEngineState.STOPPED

        self.task_sink = task_sink
        #: a iterable of StorageMetrics
        self.storage_metrics = storage_metrics

        # this is used for the local state transition between STATE_SYNC->RUNNING
        self.local_tree_fetched = False
        self.remote_tree_fetched = False

        #: :class:`blinker.Signal` is called if the props of the node change
        #: IMPORTANT: the signal handlers run in the same context as the
        #: sync_engine. Be aware of blocking calls etc.
        self.on_node_props_change = Signal()

    def _handle_failure(self, exception_type, exception_value, traceback):
        logger.error("In the syncengine. NOT shutting down",
                     exc_info=(exception_type, exception_value, traceback))

    def _handle_receive(self, message):
        """Measure time, when executing something via the pykka actor"""
        start_time = time.time()
        return_val = super()._handle_receive(message)
        took = time.time() - start_time
        if took > 0.08:
            logger.info('execution of %s took %.4f, that might be problematic',
                        message['attr_path'], took)
        return return_val

    @priority(100)
    def get_model_copy(self):
        """Returns a copy of the model"""
        return copy.deepcopy(self.root_node)

    @priority(1)
    def init(self):
        """Initialize sync engine by executing state sync"""
        if self.state == SyncEngineState.STOPPED or self.state == SyncEngineState.OFFLINE:
            self.issue_sync_task(FetchFileTreeTask(self.storage_metrics.storage_id))
            self.state = SyncEngineState.STATE_SYNC
        else:
            raise ValueError('Wrong state')

    @priority(10)
    def query(self, path):
        """Query an element

        :param path: the elements path
        :return: a deepcopy of the properties
        """
        path = normalize_path(path)
        node = self.root_node.get_node(path)
        return copy.deepcopy(node.props)

    @priority(10)
    def query_storage_path(self, path):
        """Get the real path on the storages

        :param path: the path
        :return: a dict of normalized paths with the storage id as key and the normalized
        path on the storage as value
        """
        path = normalize_path(path)
        node = self.root_node.get_node(path)

        storage_paths = {}
        for csp_id in node.props[STORAGE]:
            if csp_id != FILESYSTEM_ID:
                storage_paths[csp_id] = get_storage_path(node, csp_id)
        return storage_paths

    @priority(9)
    def query_shared_state(self, path):
        """ Queries the key subjects for the item in path

        :param path: a not necessarily normalized path to an item
        :return a tuple with storage_id, public_shared, shared_id


        This method does a lookup if any of the parents of the item might have information about
        the shared state.
        """
        path = normalize_path(path)

        storage_id = self.storage_metrics.storage_id

        logger.debug('Querying sync state for path %s and storage_id %s', path, storage_id)

        share_id = None
        public_shared = False

        for node in self.root_node.iter_up_existing(path):
            if node.props.get(STORAGE, {}).get(storage_id, {}).get(PUBLIC_SHARE, False):
                public_shared = True
                break

        for node in self.root_node.iter_up_existing(path):
            share_id = node.props.get(STORAGE, {}).get(storage_id, {}).get(SHARE_ID)
            if share_id:
                break
        logger.debug('Found share_id:%s in path %s', share_id, node.path)

        return SharedState(
            storage_id=storage_id, share_id=share_id, public_shared=public_shared)

    def get_default_fsm(self, path):
        """Get node fsm for node, if not exists it will create the default fsm

        :param path: the path
        :return: the fsm
        :raise: ValueError for the root node []
        """
        if path == []:
            raise ValueError('There should be no state machine for the root')
        node = self.root_node.get_node_safe(path=path)
        return node.props.setdefault(SE_FSM, fysom.Fysom(FSM_NODE_CONFIG))

    def storage_delete(self, storage_id, path):
        """
        Handler for a Delete Event on a storage
        :param storage_id: the storage
        :param path: the path for the event
        :return:
        """
        normalized_path = normalize_path(path)
        logger.debug("Deletion for %s(%s) from %s", path, normalized_path, storage_id)

        # Check if the node exists
        try:
            del_node = self.root_node.get_node(normalized_path)
        except KeyError:
            logger.info("Node does not exist -> nothing to delete")
            return

        logger.debug("Triggering a delete event on %s and all it's children", normalized_path)
        for node in del_node:
            logger.debug("triggering e_deleted for %s", node.path)
            fsm = self.get_default_fsm(path=node.path)
            update_storage_delete(storage_id, node)
            if self.state == SyncEngineState.RUNNING:
                try:
                    node.props[STORAGE][storage_id][EVENT_RECEIVED] = True
                    fsm.e_deleted(node=node, storage_id=storage_id,
                                  task_sink=self.issue_sync_task,
                                  event_props={},
                                  csps=[self.storage_metrics])

                except KeyError:
                    # This is ok since it could be that the node was already deleted
                    # or at least manipulated
                    # If we don't catch exceptions here, the remaining children and the parent
                    # won't be deleted properly (see client#933 for more information).
                    logger.debug(
                            "Tried to delete %s from %s which might have already been deleted.",
                            path, storage_id)

    def storage_create(self, storage_id, path, event_props):
        """
        Handler for a Create Event on a storage
        :param event_props: dictionary for the properties of an event with the
         keys [modified_date, is_dir]
        :param storage_id: the storage
        :param path: the path
        :return
        """
        name = path[-1]
        normed_path = normalize_path(path)
        logger.debug("Got create message for %s(%s)", path, normed_path)

        # Ensure full path structure has entries for the current storage
        # tree nodes need normed path, display name gets unnormalized version.
        curr_path = []
        for elem in path[:-1]:
            curr_path.append(normalize_path_element(elem))
            node = self.root_node.get_node_safe(curr_path)
            storage = node.props.setdefault(STORAGE, {}).setdefault(storage_id, {})
            storage[DISPLAY_NAME] = elem

        event_props[DISPLAY_NAME] = name

        fsm = self.get_default_fsm(path=normed_path)

        node = self.root_node.get_node_safe(normed_path)

        # update storage props and send blinker signal
        old_props = copy.deepcopy(node.props)
        update_storage_props(storage_id, node, event_props)
        if old_props != node.props:
            # props changed -> send signal
            self.on_node_props_change.send(self,
                                           storage_id=storage_id,
                                           old_props=old_props,
                                           node=node)
        if self.state == SyncEngineState.RUNNING:
            node.props[STORAGE][storage_id][EVENT_RECEIVED] = True
            fsm.e_created(csps=[self.storage_metrics],
                          node=node,
                          task_sink=self.issue_sync_task,
                          event_props=event_props,
                          storage_id=storage_id)

    def storage_move(self, storage_id, source_path, target_path, event_props):
        """Handler for a Move Event on a storage.

        Currently this is just doing a delete on the old node and a create on the new node
        :param storage_id: the storage
        :param source_path: the old path
        :param target_path: the new path
        :param event_props event properties of the move
        :return:
        """
        self.storage_create(storage_id, target_path, event_props)
        for node in self.root_node.get_node(normalize_path(source_path)).children:
            child_target_path = copy.deepcopy(target_path)
            node_path = node.path[-1]
            child_target_path.append(node_path)
            self.storage_move(storage_id=storage_id, source_path=node.path,
                              target_path=child_target_path,
                              event_props=node.props[STORAGE][storage_id])
        self.storage_delete(storage_id, source_path)

    def storage_modify(self, storage_id, path, event_props):
        """
        Handler for a Modify Event on a storage
        :param storage_id: the storage
        :param path: the path
        :param event_props event properties of the modify
        """
        name = path[-1]
        normed_path = normalize_path(path)
        logger.debug("Got modify message for %s(%s)", path, normed_path)

        event_props[DISPLAY_NAME] = name

        fsm = self.get_default_fsm(path=normed_path)
        node = self.root_node.get_node(normed_path)

        # update storage props and send blinker signal
        old_props = copy.deepcopy(node.props)
        update_storage_props(storage_id, node, event_props)
        if old_props != node.props:
            # props changed -> send signal
            self.on_node_props_change.send(self,
                                           storage_id=storage_id,
                                           old_props=old_props,
                                           node=node)

        if self.state == SyncEngineState.RUNNING:
            if SE_FSM in node.props:
                logging.debug('Triggering e_modified(current state: %s)',
                              node.props[SE_FSM].current)
            node.props[STORAGE][storage_id][EVENT_RECEIVED] = True
            fsm.e_modified(node=node,
                           csps=[self.storage_metrics],
                           task_sink=self.issue_sync_task,
                           event_props=event_props,
                           storage_id=storage_id)
            if SE_FSM in node.props:
                logging.debug('now in state: %s', node.props[SE_FSM].current)

    def ack_task(self, task):
        """
        Acknowledge a task
        :param task: the task
        :return: None
        """
        logger.debug('acknowledging %s', task)

        if isinstance(task, FetchFileTreeTask):
            self._ack_fetch_file_tree_task(task)
        else:
            path = task.path

            fsm = self.get_default_fsm(path=path)

            # TODO: this creates a node for delete events as well, good idea?
            node = self.root_node.get_node(path)

            if task.state == SyncTask.INVALID_OPERATION:
                # Fatal error -> mark node
                node.props['invalid_op'] = True

            if isinstance(task, UploadSyncTask) or isinstance(task, DownloadSyncTask):
                self._ack_updownload_task(fsm, node, task)

            elif isinstance(task, DeleteSyncTask):
                self._ack_delete_task(fsm, node, task)

            elif isinstance(task, CreateDirSyncTask):
                self._ack_updownload_task(fsm, node, task)

            elif isinstance(task, MoveSyncTask):
                self._ack_move_task(fsm, node, task)

            elif isinstance(task, CancelSyncTask):
                self._ack_cancel_task(fsm, node, task)

            elif isinstance(task, CompareSyncTask):
                self._ack_compare_task(fsm, node, task)

            else:
                logger.critical("Ack of task %s not handled", task)

    def _ack_compare_task(self, fsm, node, task):
        if task.state == SyncTask.SUCCESSFUL:
            result = task.equivalents
            if len(result) == 1:
                # all elements are equal -> add it to the equivalents list
                equivalents = node.props.setdefault('equivalents', {})
                new_equivalents = equivalents.setdefault('new', {})

                for storage in node.props.setdefault(STORAGE, {}):
                    new_equivalents[storage] = node.props[STORAGE][storage]['version_id']
            else:
                logger.debug("Not implemented")

            node.props['comp_task_received'] = True
            if self.state == SyncEngineState.RUNNING:
                fsm.e_comp_ack(task=task,
                               node=node,
                               task_sink=self.issue_sync_task,
                               csps=[self.storage_metrics])

    def _ack_delete_task(self, fsm, node, task):
        """
        Acknowledge a delete task
        :param fsm: the state machine for this node
        :param node: the node
        :param task: the task
        """
        if STORAGE not in node.props:
            logger.info('No storage entries in this node!')
            return
        if task.target_storage_id not in node.props[STORAGE]:
            logger.info('No storage entry for %s in this node!', task.target_storage_id)
            return

        if task.state == SyncTask.INVALID_AUTHENTICATION:
            self._handle_invalid_authentication(task.target_storage_id)
            return

        node.props[STORAGE][task.target_storage_id][SYNC_TASK_RUNNING] = False
        node.props[STORAGE][task.target_storage_id][SYNC_TASK_FAILED] = \
            not task.state == SyncTask.SUCCESSFUL
        if task.state == SyncTask.SUCCESSFUL:
            # update metrics
            file_size = node.props[STORAGE][task.target_storage_id][SIZE]
            self._update_storage_metrics(task.target_storage_id, file_size)

            # update node props
            node.props.setdefault('equivalents', {}).setdefault('new', {}).pop(
                task.target_storage_id, None)
            if len(node.props['equivalents']['new']) == 1:
                node.props['equivalents']['new'] = {}
        else:
            logger.info("Synctask failed %s", task)

        if self.state == SyncEngineState.RUNNING:
            fsm.e_st_ack(task=task,
                         node=node,
                         task_sink=self.issue_sync_task,
                         csps=[self.storage_metrics])

    def _ack_updownload_task(self, fsm, node, task):
        logger.debug('task:%s path:%s', task, node.path)

        # checking if account is invalid
        if task.state == SyncTask.INVALID_AUTHENTICATION:
            self._handle_invalid_authentication(task.target_storage_id)

        node.props[STORAGE][task.target_storage_id][SYNC_TASK_RUNNING] = False
        node.props[STORAGE][task.target_storage_id][SYNC_TASK_FAILED] = \
            not task.state == SyncTask.SUCCESSFUL

        if task.state == SyncTask.SUCCESSFUL:
            equivalents = node.props.setdefault('equivalents', {})
            new_equivalents = equivalents.setdefault('new', {})

            source = (task.source_storage_id, task.source_version_id)
            target = (task.target_storage_id, task.target_version_id)

            if source in new_equivalents.items() or target in new_equivalents.items():
                new_equivalents[task.source_storage_id] = task.source_version_id
                new_equivalents[task.target_storage_id] = task.target_version_id
            else:
                equivalents['old'] = new_equivalents
                equivalents['new'] = {
                    task.source_storage_id: task.source_version_id,
                    task.target_storage_id: task.target_version_id}
        else:
            # if upload -> revert metrics updates
            if task.target_storage_id != FILESYSTEM_ID:
                file_size = node.props[STORAGE][FILESYSTEM_ID][SIZE]
                self._update_storage_metrics(task.target_storage_id, file_size)

            # Remove this storage id from desired storages -> new value will be determined
            # in on sync
            # logger.debug('removing storage %s from desired storages', task.target_storage_id)
            # if task.target_storage_id in node.props.get('desired_storages', []):
            #     node.props['desired_storages'].remove(task.target_storage_id)

        if self.state == SyncEngineState.RUNNING:
            if SE_FSM in node.props:
                logger.debug('_ack_updownload_task finished for node %s, state:%s', node.path,
                             node.props[SE_FSM].current)
            fsm.e_st_ack(task=task,
                         node=node,
                         task_sink=self.issue_sync_task,
                         csps=[self.storage_metrics])
            if SE_FSM in node.props:
                logger.debug('state:%s afterwards', node.props[SE_FSM].current)

    def _handle_invalid_authentication(self, storage_id):
        # pylint: disable=no-self-use
        logger.info('detected invalid account with id %s', storage_id)
        # storage is not authenticated anymore
        # for storage in self.csps:
        #     if storage.storage_id == storage_id and storage.valid_auth:
        #         storage.valid_auth = False
        #         logger.info('trigger handling of invalid account with id %s', storage_id)
        #         message = 'handling invalid account with id {}'.format(storage_id)
        #         thread = Thread(target=self.restart_client_callback, args=(message,))
        #         thread.start()

    def _ack_move_task(self, fsm, node, task):
        """Acknowledge a move task."""
        if task.state == SyncTask.SUCCESSFUL:
            node.props['storage'].setdefault(
                task.source_storage_id, {})[SYNC_TASK_STATE] = MOVED
            if self.state == SyncEngineState.RUNNING:
                fsm.e_st_move_success(task=task,
                                      node=node,
                                      csps=[self.storage_metrics],
                                      task_sink=self.issue_sync_task)
        else:
            if self.state == SyncEngineState.RUNNING:
                fsm.e_st_move_failed(task=task,
                                     node=node,
                                     task_sink=self.issue_sync_task,
                                     csps=[self.storage_metrics])

    def _ack_fetch_file_tree_task(self, task):
        """
        Adds the fetched tree model to the local model
        :param task:
        """
        if task.state == SyncTask.SUCCESSFUL:
            self.merge_storage_to_sync_model(
                storage_model=task.file_tree, storage_id=task.storage_id)

            # wait until both trees have been returned
            # pylint: disable=simplifiable-if-statement
            if task.storage_id == FILESYSTEM_ID:
                self.local_tree_fetched = True
            else:
                self.remote_tree_fetched = True
                self.storage_metrics = task.file_tree.props['metrics']
                self.issue_sync_task(FetchFileTreeTask(FILESYSTEM_ID))

            if self.remote_tree_fetched and self.local_tree_fetched:
                self._sync_state()
                self.state = SyncEngineState.RUNNING

                # TODO: yuk! (we need to use more signals)
                cc.ipc_gui.accountDeleted('')

                self.local_tree_fetched = False
                self.remote_tree_fetched = False

        else:
            # in case of failure
            self.state = SyncEngineState.STOPPED  # pylint: disable=redefined-variable-type

    def _ack_cancel_task(self, fsm, node, task):
        node.props['tasks_cancelled'] = True
        if self.state == SyncEngineState.RUNNING:
            fsm.e_st_ack(node=node, task=task, task_sink=self.issue_sync_task,
                         csps=[self.storage_metrics])

    def storage_offline(self, **kwargs):
        """Turn the syncengine for this storage off.

        Note: kwargs are required to stay compatible with older versions which pass storage_id.
        """
        # pylint: disable=unused-argument
        storage_id = self.root_node.props.get(STORAGE, {})
        logger.info("Storage %s went offline.", storage_id)
        self.state = SyncEngineState.OFFLINE

    def storage_online(self, **kwargs):
        """Turn the syncengine for this storage on.

        Note: kwargs are required to stay compatible with older versions which pass storage_id.
        """
        # pylint: disable=unused-argument
        storage_id = self.root_node.props.get(STORAGE, {})
        logger.info("Storage %s is back online.", storage_id)

        # if we have not been initialized before, we were probably totally offline
        cur_state = self.state
        if cur_state is SyncEngineState.OFFLINE:
            self.init()

    def pause(self):
        """ Pause sync engine.

        That means, it cancel all running actions an stops executing things within the stop
        """
        if self.state == SyncEngineState.RUNNING:
            # Cancel all tasks
            self.cancel_all_tasks()
            self.state = SyncEngineState.STOPPED

    def resume(self):
        """
        Reenables that events are passed to the FSM and triggers state sync
        """
        if self.state == SyncEngineState.STOPPED:
            self._sync_state()
            self.state = SyncEngineState.RUNNING

    ##################
    # Helper Methods #
    ##################

    def print_state(self):
        """
        prints all data stored in tree
        """
        all_items = copy.deepcopy(self.root_node)
        print_sync_model(all_items)

    def _update_storage_metrics(self, storage_id, usage_diff):
        """ Metrics Update
        Updates the metrics of a specified csps
        :param storage_id: the csp_id
        :param usage_diff: positive or negative change
        :return: None
        """
        if self.storage_metrics.storage_id == storage_id:
            self.storage_metrics.free_space += usage_diff

            logger.debug('updating metrics of %s - free space %2.2fMB (diff %2.2fMB)',
                         storage_id,
                         self.storage_metrics.free_space / (1024 * 1024),
                         usage_diff / (1024 * 1024))

            return

    def issue_sync_task(self, task):
        """
        Issues a sync tasks and calculates new metrics
        :param task: the synctask
        """
        if isinstance(task, UploadSyncTask):
            # the metrics only change if an upload is issued
            logger.debug("Upload Task issued. Updating Metrics.")
            node = self.root_node.get_node(task.path)
            file_size = node.props[STORAGE][FILESYSTEM_ID][SIZE]
            self._update_storage_metrics(task.target_storage_id,
                                         (file_size * (-1)))

        logger.debug("Issuing task '%s' on '%s' sink.", task, self.task_sink)
        self.task_sink(task)

    def merge_storage_to_sync_model(self, storage_model, storage_id):
        """
        Merges storage model into existing sync model with necessary attributes.
        """
        # create and add every node to sync model
        for storage_node in storage_model:
            sync_node = self.root_node.get_node_safe(normalize_path(storage_node.path))
            sync_node.props.setdefault(STORAGE, {})[storage_id] = {}

            if storage_node.parent is None:
                # the rest from here on is not needed for the root, but the other values are
                # used to mark if the tree has been retrieved
                continue

            if DISPLAY_NAME not in storage_node.props:
                storage_node.props[DISPLAY_NAME] = storage_node.name

            update_storage_props(storage_id=storage_id, node=sync_node,
                                 props=storage_node.props)

            if storage_node.parent is not None:
                # normalize storage model, to normalize the model, so the deletion operation below
                # is working
                storage_node.name = normalize_path_element(storage_node.name)

        for node in set(self.root_node) - set(storage_model):
            storages = node.props.get(STORAGE, {})
            if storage_id in storages:
                del storages[storage_id]

    def _sync_state(self):
        """Force an (re-)evaluation of all nodes in the model by triggering the e_check method."""
        logger.debug('Starting state sync')
        for node in self.root_node:
            if node.parent is None:
                # ignore the root
                continue

            fsm = self.get_default_fsm(node.path)
            fsm.current = S_SYNCED
            try:
                fsm.e_check(csps=[self.storage_metrics],
                            task_sink=self.task_sink, node=node)
            except BaseException:
                logger.exception('State Sync for node %s failed', node.path,
                                 extra={'path': node.path,
                                        'node props': node.props})
        logger.debug('Done with state sync')

    def cancel_all_tasks(self):
        """Try to cancel all SyncTasks for each Node"""
        for node in self.root_node:
            if node.parent is None:
                continue
            fsm = node.props.get(SE_FSM)
            if fsm is not None:
                try:
                    fsm.e_cancel_all(csps=[self.storage_metrics],
                                     task_sink=self.task_sink,
                                     node=node)
                except fysom.FysomError:
                    logger.info('did not cancel task since in state "%s"', fsm.current)
                    logger.debug(node.props)


def update_storage_props(storage_id, node, props):
    """
    Callback for a local created event
    """

    # check if this storage is already present in the storage_props
    storages = node.props.setdefault(STORAGE, {})
    present = storage_id in storages

    storage_props = storages.setdefault(storage_id, {})

    try:
        # make sure the mandatory values are not DELETE:
        if props.get('version_id') == DELETE or props.get('modified_date') == DELETE \
                or props.get('size') == DELETE or props.get('is_dir') == DELETE:
            raise KeyError("Mandatory values are not allowed to be set to DELETE")

        # assign values
        storage_props['version_id'] = props['version_id']
        storage_props['modified_date'] = props.get('modified_date', datetime(1, 1, 1))
        storage_props['size'] = props.get('size', 0)
        storage_props['is_dir'] = props['is_dir']
        storage_props[DISPLAY_NAME] = props.get(DISPLAY_NAME, node.name)

        # setting shared property for node, if not in there -> False
        storage_props[SHARED] = props.get(SHARED, False)
        storage_props['share_id'] = props.get('share_id', DELETE)
        storage_props['public_share'] = props.get('public_share', False)

        storage_props.pop('deleted', None)

        if logger.level <= logging.DEBUG:
            logger.debug('Updated storage props of storage %s::%s to \n%s',
                         storage_id, node.path, pformat(node.props[STORAGE][storage_id]))
    except KeyError:
        logger.info("Error while updating storage props", exc_info=True)
        # if the storage was not present before -> remove it again
        if not present:
            del storages[storage_id]

        raise

    for elem in list(storage_props.keys()):
        if storage_props[elem] == DELETE:
            del storage_props[elem]


def update_storage_delete(storage_id, node):
    """
    Callback for deletion transition
    """
    logger.debug('for %s from %s',
                 node.path, storage_id)

    if storage_id in node.props[STORAGE]:
        node.props[STORAGE][storage_id].pop('version_id', None)
        node.props[STORAGE][storage_id]['deleted'] = True


def print_sync_model(model):
    """
    Prints all data stored in sync model.
    """
    all_items = copy.deepcopy(model)

    for node in all_items:
        node_props = dict(node.props)
        output = 'path: ' + '/'.join(node.path)
        output += '\n\tis_dir: ' + str(node_props.pop(IS_DIR, 'not specified'))
        output += '\n\tsize: ' + str(node_props.pop(SIZE, 'not specified'))
        if SE_FSM in node_props:
            output += '\n\tstate: ' + node_props.pop(SE_FSM).current
        for s_id, storage_props in node_props.pop(STORAGE, {}).items():
            output += '\n\t' + s_id + ': ' + str(storage_props)
        output += '\n\tother: ' + str(node_props)


def normalize_path(path):
    """
    Normalizes the given path with unicode NFC and lower case
    :param path: the path
     :return: the normalized path
    """
    new_path = []
    for elem in path:
        new_path.append(normalize_path_element(elem))
    return new_path
