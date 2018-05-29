"""Contains classes and functions that handle synchronization related tasks.

This subpackage compartmentalizes functionality to keep local or remote storages `in-sync`.

It allows crosscloud to:
- Persist and load sync state from disk
- Issue changes in form of :class:`cc.synctask.SyncTasks` to
restore the `in-sync` state
- Spawn/manage a worker pool holding a set of worker threads that are responsible for executing
  tasks issued by the :class:`cc.synchronization.syncengine.SyncEngine`.
- Combine one local and one remote Filesystem into a single manageable entity called the
  :class:`.models.SynchronizationLink`.
- Persist and keep the SyncState between to SynchronizationLink endpoints
- Combine a set of configured SynchronizationLinks into a single manageable entity called the
  SynchronizationGraph.

>>> graph = SynchronizationGraph.using(cc.config)

This method will return a ready-to-use graph containing all the links that could be configured from
the given cc.configuration. After calling startup configured the graph should start "syncing" away.

>>> graph.startup()
>>> ...
>>> # Get aggregated state of all links in the graph.
>>> graph.aggregate_state()
>>> # Everything should be running now.

In case the configuration of a link changes for now we have to:

1. Shutdown all the links in the graph (call .shutdown on the graph)
2. Call the SynchronizationGraph.using with the updated configuration
3. Call startup again (call .startup on the graph)

for the changes to be picked up.

>>> graph.shutdown()
>>> graph = SynchronizationGraph.using(new_configuration)
>>> graph.startup()

IMPORTANT: Calling restart on the graph will not re-read the configuration!
"""
# pylint: disable=wrong-import-order
# pylint: disable=ungrouped-imports
import io
import logging
import os
import queue
import threading
import time
from functools import partial

import blinker
import jars.dropbox
import jars.fs.filesystem
import jars.googledrive
import jars.microsoft
import jars.owncloud
import jars.webdav
from jars import StorageMetrics
from jars.utils import config_to_tree
from jars.utils import FilterEventSinkWrapper

import cc.ipc_gui
import cc.synctask

from cc.configuration.helpers import (get_credentials_from_config,
                                      store_credentials_in_config,
                                      get_public_key_pem_by_subject,
                                      get_private_key_pem_by_subject,
                                      update_filter_in_config)

from cc.configuration.helpers import get_storage_cache_dir
from cc.encryption.storage_wrapper import EncryptingFileSystem
from cc.periodic_scheduler import PeriodicScheduler
from cc.synchronization.bademeister import Bademeister
from cc.synchronization.exceptions import (PolicyError,
                                           SyncTaskCancelledException)
from cc.synchronization.state import State
from cc.synchronization.syncengine import SyncEngine, SyncEngineState

# pylint: disable=wrong-import-order
# pylint: disable=ungrouped-imports
if os.name == 'nt':
    import jars.fs.cifs

logger = logging.getLogger(__name__)


class ControlFileWrapper(io.RawIOBase):
    """A class which can be wrapped around a file object to cancel read operations."""

    def __init__(self, orig_obj, task, data_rate_callback=None):
        super().__init__()
        self._orig_obj = orig_obj
        self.task = task
        self.data_rate_callback = data_rate_callback
        self.read_count = 0

    def read(self, count=None):
        """Makes a transfer cancellable."""
        # check if it should be cancelled
        if self.task.cancelled:
            raise SyncTaskCancelledException('Cancelled while read')

        start_read_time = time.time()
        data = self._orig_obj.read(count)

        # submits the current datarate to the data_rate_callback
        if self.data_rate_callback:
            self.data_rate_callback(len(data) /
                                    time.time() - start_read_time)
        self.read_count += len(data)
        return data

    def tell(self):
        return self.read_count

    def seekable(self):
        return False

    def writable(self):
        return False


class PolicyWrapper:
    """ A class which can be wrapped around a file object to cancel read operations
    and measure the speed """

    def __init__(self, orig_obj, task, policies):
        self._orig_obj = orig_obj
        self.task = task
        self.policies = policies
        self.blocked_ext = []

        self.get_blocked_extensions()
        self.check_policies()

    def get_blocked_extensions(self):
        """Extract the blocked extensions from the policies dict."""
        for policy in self.policies:
            if policy.get('type') == 'fileextension' and policy.get('is_enabled'):
                self.blocked_ext.append(policy.get('criteria'))

    def check_policies(self):
        """Check if any policies have been violated.

        :raises PolicyError if any of the given policies have been violated.
        :return:
        """
        path = self.task.source_path
        # check file extension
        file_name = path[-1]
        file_ext = file_name.split('.')[-1]

        if file_ext in self.blocked_ext:
            self.task.state = cc.synctask.SyncTask.BLOCKED
            raise PolicyError(path)

    def __getattr__(self, item):
        """Return the attribute of the wrapped object.

        :param item: the wrapped attribute's name
        :return: the original attribute given by item
        """
        return getattr(self._orig_obj, item)


class SynchronizationLink(object):
    """Connects a filesystem and storage provider with each other.

    Connects a local and remote filesystem with each other and contains all the necessary
    classes to keep track of connection state, metrics and contents.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, local, remote, actor, engine, state, task_queue, metrics, config_dir):
        """Initialize the link with all pre-configured objects necessary to operate.

        This will almost always be called via SynchronizationLink.using.

        :param local: the local filesystem (currently :class`EncryptedFilesystem`)
        :type local: :class:`jars.EncryptedFilesystem`
        :param remote: the remote filesystem (e.g. one of the SPs from jars).
        :type remote: a subclass of `jars.storage`
        :param actor: the sync actor
        :param engine: the sync engine
        :param state: the sync engine state
        :param task_queue: the global task_queue where new synctasks should be put on.
        :param metrics: the remote's storage metrics
        :type metrics: a subclass of `jars.storage.StorageMetrics`
        :param config_dir: path to the configuration directory
        """
        # pylint: disable=too-many-arguments
        self.local = local
        self.remote = remote
        self.actor = actor
        self.engine = engine
        self.state = state
        self.queue = task_queue
        self.metrics = metrics
        self.config_dir = config_dir

        # Link with engine.
        self.engine.task_sink = self.task_sink

    @property
    def storages(self):
        """Return storage/filesystem associated with this link.

        This exists because certain callers still rely on this functionality. However this should
        be deprecated and removed if possible.

        :returns dictionary containing the 'local' and 'storage_id' keys resolving to the local
                 and remote storage associated with the link.
        """
        # TODO FIXME: This attr will be deprecated once other parts have been refactored.
        logger.info("(DEPRECATED) SynchronizationLink.storages is deprecated and "
                    "should not be used any longer.")
        return {
            self.local.storage_id: self.local,
            self.remote.storage_id: self.remote
        }

    @property
    def client_config(self):
        """Return the client config attatched to the client."""
        return self.local.client_config

    def task_sink(self, task):
        """Add ack_callback to the sync engine of the link, and then put the task on the queue.

        - Sets the ack_callback of the task to the ack_task of the syncengine
        - Attaches this link to the task for future reference.

        :param task: a synctask that should be put on the global task queue.
        :return: None
        """
        task.set_ack_callback(self.engine.ack_task)
        task.link = self
        self.queue.put_task(task)

    @property
    def link_id(self):
        """Return this link's `link_id` which is a concatenation of each ends 'storage_id'.

        :return: unique textual identifier if the current link.
        """
        return "{}::{}".format(self.local.storage_id, self.remote.storage_id)

    # pylint: disable=too-many-locals,too-many-arguments
    @classmethod
    def using(cls, client_config, storage_config, task_queue):
        """Build a SynchronizationLink from the given configuration and global task queue.

        :param configuration: configuration dictionary for the SP that should be setup with
                              this link. See :class`cc.configuration.Config`.
        :type configuration: cc.configuration.Config
        :param task_queue: the task queue that is kept by the bademeister.
        :type task_queue: cc.synchronization.models.TaskQueue
        :param local_sync_root: path to the sync base directory
        :param config_dir: path to the configuration directory
        :return: a ready-to-use synchronization link
        """
        # Load SyncEngine state from disk if present.
        # We most likely want one sync state per pair. Thus we append the storage unique id to
        # get a unique location for the state.
        sync_state_filename = "sync_state_{}".format(storage_config['id'])

        sync_state_file = os.path.join(client_config.config_dir, sync_state_filename)
        sync_state = State.fromfile(sync_state_file)

        # Prepare Metrics
        metrics = StorageMetrics(storage_id=storage_config['id'],
                                 free_space=0,
                                 display_name=storage_config['display_name'])

        # Setup Sync Engine
        sync_actor = SyncEngine.start(storage_metrics=metrics,
                                      task_sink=task_queue.put_task,
                                      model=sync_state)
        sync_engine = sync_actor.proxy()

        # getting csps where storage name matches
        csps = [c for c in jars.registered_storages if c.storage_name == storage_config['type']]

        storage_cls = csps[0]

        remote = instantiate_storage(
            storage_cls,
            storage_id=storage_config.get('id'),
            config=client_config,
            # TODO FIXME: Properly build the selected_sync_dirs (children, path).
            selected_sync_dirs=storage_config.get('selected_sync_directories'),
            sync_engine=sync_engine)

        local_sync_root = os.path.join(client_config.sync_root, storage_config['display_name'])
        logger.info("Local Root for '%s' is '%s'.", storage_config['id'], local_sync_root)
        if not os.path.exists(local_sync_root):
            logger.error("'%s' does not exist!", local_sync_root)

        # FOOBAR
        local = prepare_local_filesystem(
            local_sync_root=local_sync_root,
            sync_engine=sync_engine,
            public_key_getter=partial(get_public_key_pem_by_subject, client_config),
            private_key_getter=partial(get_private_key_pem_by_subject, client_config))

        # TODO Hack Hack Hack! This is needed by the EncryptionWrapper around the local storage.
        # This needs more refactoring is an improvement over the previous global config.
        local.client_config = client_config

        link = SynchronizationLink(local=local,
                                   remote=remote,
                                   actor=sync_actor,
                                   engine=sync_engine,
                                   state=sync_state,
                                   metrics=metrics,
                                   task_queue=task_queue,
                                   config_dir=client_config.config_dir)
        logger.info("Instantiated Link '%s'", link.link_id)
        return link

    def is_properly_configured(self):
        """Check if all necessary objects of the link have been setup.

        :return: True if the link has been configured correctly. False otherwise.
        """
        return all([self.local,
                    self.remote,
                    self.queue,
                    self.actor,
                    self.engine,
                    self.metrics])

    def startup(self):
        """Start link/syncengine operations.

        :return:
        """
        assert self.is_properly_configured()
        logger.info("Starting up '%s'...", self.link_id)
        self.engine.init()

    def pause(self):
        """Pause link/syncengine operations.

        Called when the user requests the link or graph to pause operations via the UI

        :return:
        """
        logger.info("Pausing '%s'...", self.link_id)
        # TODO FIXME: Set State
        self.engine.pause()
        logger.info("Paused link '%s'!", self.link_id)

    def resume(self):
        """Resume link/syncengine operations.

        Called when the user requests the link or graph to resume operations via the UI

        :return:
        """
        logger.info("Resuming '%s'...", self.link_id)
        # TODO FIXME: Set State
        self.engine.resume()
        logger.info("Resumed link '%s'!", self.link_id)

    def shutdown(self):
        """Shutdown the link and its associated actors.

        :return:
        """
        logger.info("Shutting down '%s'.", self.link_id)

        # TODO XXX: Stop periodic writer for sync state model

        if self.remote:
            logger.info("Shutting down remote storage.")
            try:
                self.remote.stop_events(join=True)
                if self.remote.supports_serialization:
                    logger.info('Serializing model of %r.', self.remote)
                    self.remote.serialize()
            except BaseException:
                logger.exception('Error while shutting down remote storage')

        if self.local:
            logger.info("Shutting down local storage.")
            try:
                self.local.stop_events(join=True)
                if self.local.supports_serialization:
                    logger.info('Serializing model of %r.', self.local)
            except BaseException:
                logger.exception('Error while shutting down local storage')

        # Stop the sync engine and persist the current sync state model to disc.
        if self.engine:
            self.save_state()

            logger.info("Stopping sync engine.")
            self.actor.stop(block=True)

        logger.info("Shutdown complete.")

    def save_state(self):
        """Save state to state file. (might take longer)
        """
        logger.info("Storing engine state on disk.")
        sync_state_filename = "sync_state_{}".format(self.remote.storage_id)
        sync_state_file = os.path.join(self.config_dir, sync_state_filename)
        State.to_pickle(self.engine, sync_state_file)

    def __str__(self):
        """Return human-readable representation of the link."""
        return "Link '{}' <-> '{}'".format(self.local.storage_id, self.remote.storage_id)


class SynchronizationGraph(object):
    """Container that handles a set of pre-configured SynchronizationLinks.

    Once all links have been added to an instance of this class, several methods (e.g.
    start, stop) can be used to issue commands on all contained links.
    """

    def __init__(self, sync_root, bademeister, periodic_state_saver):
        """Initialize a SynchronizationGraph.

        This will usually only be called from within `.using`.

        :param sync_root: the local sync_root for this graph
        :type sync_root: str
        :param bademeister: the worker pool containing the set of workers
        :type bademeister: cc.synchronization.bademeister.Bademeister
        :param periodic_state_saver: PeriodicScheduler used to save the state of the links.
        """
        self.sync_root = sync_root
        self.state = 'STOPPED'
        self.links = {}
        self.bademeister = bademeister
        self.periodic_state_saver = periodic_state_saver

    def add(self, link):
        """Add a new SynchronizationLink to the graph.

        :param link: The link to add
        :type link: SynchronizationLink
        :returns: True
        """
        assert isinstance(link, SynchronizationLink)
        self.links[link.link_id] = link
        logger.info("Added link '%s' to graph", link.link_id)
        return True

    def remove(self, link):
        """Remove a link from the graph.

        :param link: The link to remove
        :type link: SynchronizationLink
        :returns: True if link can be removed, false if removal fails.
        """
        assert isinstance(link, SynchronizationLink)
        item = self.links.pop(link.link_id, None)

        if item:
            logger.info("Shutting down link.")
            assert link.shutdown()
            return True

        logger.error("Link not found!")
        return False

    @classmethod
    def using(cls, configuration):
        """Construct a new SynchronizationGraph from a given client configuration.

        :param configuration: the current client configuration that should be used
                              to setup the new graph.
        :type configuration: cc.configuration.Config
        :return: a new, setup and ready-to-use SynchronizationGraph.
        """
        # Create a new global task queue and worker pool.
        task_queue = cc.synchronization.models.TaskQueue()
        task_queue.task_acked.connect(cc.ipc_gui.on_task_acked)
        task_queue.task_acked.connect(partial(cc.settings_sync.log_task_to_backend, configuration),
                                      weak=False)

        # Periodic scheduler needed
        periodic_state_saver = PeriodicScheduler(interval=90)

        # Instantiate a fresh graph and pass it the worker pool.
        bademeister = Bademeister(task_queue)
        graph = SynchronizationGraph(configuration.sync_root, bademeister, periodic_state_saver)
        periodic_state_saver.target = graph.save_state

        # For every configured SP in the current clients configuration, configure
        # a new link by calling ".using" with the relevant part of the SP configuration
        # and a reference to the task_queue.
        for storage_config in configuration.csps:
            logger.info("Preparing Link for '%s'.", storage_config['id'])
            link = SynchronizationLink.using(client_config=configuration,
                                             storage_config=storage_config,
                                             task_queue=task_queue)
            logger.debug(link)
            logger.debug("Successfully prepared synchronization link!")
            graph.add(link)
            logger.debug("Added '%s' to synchronization graph.", storage_config['id'])

        logger.info("Successfully configured new graph with %d links", len(graph.links.keys()))
        return graph

    def save_state(self):
        """Save state for all links."""
        for link in self.links.values():
            link.save_state()

    def pause(self):
        """Pause all links currently configured in the graph."""
        for link in self.links.values():
            link.pause()

    def resume(self):
        """Resume all links currently configured in the graph."""
        for link in self.links.values():
            link.resume()

    def restart(self):
        """Restart synchronization graph."""
        logger.info("Performing restart...")
        self.shutdown()
        self.startup()

    def startup(self):
        """Startup the whole system.

        1. Try to create the sync directory
        2. Start all configured Synchronization Links
        3. Start the WorkerPool and its associated workers.
        """
        logger.info('Try to create the sync root directory')
        os.makedirs(self.sync_root, exist_ok=True)

        for link in self.links.values():
            logger.info('Starting link "%s"...', link.link_id)
            link.startup()

        logger.info("Booting the Bademeister!")
        self.bademeister.start()

        logger.info("Booting the periodic state writer")
        self.periodic_state_saver.start()

        self.state = 'RUNNING'
        logger.info("Graph startup complete!")

    def aggregate_state(self):
        """Get the aggregated (worst-case) state of the graph.

        Worst-case means that e.g. the agg. state will be not RUNNING if _any_ of the links
        have a state other than RUNNING.

        :return: the (worst-case) state of all sync engines contained in the graph.
        """
        link_states = [link.engine.state.get() for link in self.links.values()]

        if all([SyncEngineState.RUNNING == state for state in link_states]):
            return SyncEngineState.RUNNING
        elif any([SyncEngineState.STATE_SYNC == state for state in link_states]):
            return SyncEngineState.STATE_SYNC
        elif any([SyncEngineState.STOPPED == state for state in link_states]):
            return SyncEngineState.STOPPED

        return SyncEngineState.STATE_SYNC

    def shutdown(self):
        """Shutdown all contained synchronization links.

        :return:
        """
        logger.debug('Shutting down periodic state saver')
        if self.periodic_state_saver:
            self.periodic_state_saver.stop()

        logger.debug('Shutting down all links.')
        for link in self.links.values():
            logger.debug("Shutting down '%s'...", link.link_id)
            link.shutdown()

        logger.info("Shutting down Bademeister...")
        self.bademeister.stop()

        logger.debug('Shutdown complete!')

    def get_synclink_by_displayname(self, display_name):
        """Return a specific syncLink based on the path."""
        link_id = 'local::' + display_name
        return self.links.get(link_id, None)


def instantiate_storage(storage_factory, storage_id, config=None,
                        selected_sync_dirs=None, sync_engine=None):
    """Build a new storage instance using the provided `storage_factory` and configuration.

    :param configuration: the base configuration to use.
    :param storage_factory: A subclass of jars.storage
    :param storage_id: id to use for the created storage.
    :type storage_id: str
    :param selected_sync_dirs: directories selected in the selective sync.
    :type selected_sync_dirs: list
    """
    logger.debug('Instantiate storage with id %s', storage_id)

    if selected_sync_dirs is None:
        logger.info("Selective Synchronization is not configured.")
        selected_sync_dirs = []

    # creating reader and writer so storage can update authentication data
    storage_cred_reader = partial(get_credentials_from_config, config, storage_id)
    storage_cred_writer = partial(store_credentials_in_config, config, storage_id)

    # defining cache dir for storage
    storage_cache_dir = get_storage_cache_dir(config, storage_id)

    filter_tree = config_to_tree(selected_sync_dirs)
    # register the auto updating filter config signals
    update_func = partial(update_filter_in_config, config, csp_id=storage_id)
    filter_tree.on_update.connect(update_func, weak=False)
    filter_tree.on_delete.connect(update_func, weak=False)
    filter_tree.on_create.connect(update_func, weak=False)

    event_sink = FilterEventSinkWrapper(sync_engine, filter_tree)

    # wrap the syncengine for filtering
    storage_instance = storage_factory(event_sink=event_sink,
                                       storage_id=storage_id,
                                       storage_cache_dir=storage_cache_dir,
                                       storage_cred_reader=storage_cred_reader,
                                       storage_cred_writer=storage_cred_writer)

    storage_instance.filter_tree = filter_tree

    logger.info("Storage Provider '%s' setup!", storage_id)
    return storage_instance


def prepare_local_filesystem(local_sync_root, sync_engine, public_key_getter, private_key_getter):
    """Create an instance of the local filesystem storage.

    :param local_sync_root: the local "mountpoint" of the filesystem
    :param sync_engine: the event sink (sync engine)
    :param public_key_getter: function to be used for public key retrieval
    :param private_key_getter: function to be used for private key retrieval
    :return: the setup 'local' encrypted filesystem
    """
    return EncryptingFileSystem(root=local_sync_root,
                                event_sink=sync_engine,
                                storage_id='local',
                                syncengine=sync_engine,
                                public_key_getter=public_key_getter,
                                private_key_getter=private_key_getter)


class HashPathQueue(queue.Queue):
    """Queue which improves perfomance of determining tasks operate on same link path combination.

    It uses an internal hashmap to store tasks which operate on the same link path combination.
    """

    def _init(self, maxsize=0):
        super()._init(maxsize)
        self.path_queue = dict()

    def _put(self, task):
        super(HashPathQueue, self)._put(task)

        # Return early if we encounter a STOP_TOKEN.
        if task == cc.synctask.STOP_TOKEN:
            logger.info("Put 'STOP_TOKEN' on task queue.")
            return

        # Otherwise handle the task as we would normally.
        path = task.operates_on()
        self.path_queue.setdefault(path, [])
        self.path_queue[path].append(task)
        logger.debug("Queued Task '%s'", task)

    def _get(self):
        """Retrieve item from queue and remove empty path_queue entry if necessary."""
        task = super(HashPathQueue, self)._get()

        # Return early if we encounter a STOP_TOKEN.
        if task == cc.synctask.STOP_TOKEN:
            logger.info("Got 'STOP_TOKEN'.")
            return task

        # Otherwise handle the task as we would normally.
        path = task.operates_on()
        self.path_queue[path].remove(task)
        logger.info("Got task '%s' from path_queue '%s'", task, path)

        if len(self.path_queue[path]) == 0:
            del self.path_queue[path]
            logger.debug("Deleting empty path_queue entry for '%s'.", path)

        return task

    def tasks_for(self, operates_on_hash):
        """Return task queue for the given path_hash.

        :param operates_on_hash: the path_hash the queue should be obtained for (see `path_hash`).
        :return: the underlying path_queue for the given path_hash or an empty list
                 (if non-existent).
        """
        return self.path_queue.get(operates_on_hash, [])


class TaskQueue:
    """Contains multiple data structures to maintain tasks in certain states."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.pending = HashPathQueue()

        self.running = set()
        self.running_lock = threading.Lock()

        self.cancel = dict()
        self.cancel_lock = threading.Lock()

        self.task_acked = blinker.Signal()
        self.task_putted = blinker.Signal()

    @property
    def statistics(self):
        """Return statistics."""
        return {'sync_task_count': self.pending.qsize() + len(self.running)}

    def _handle_cancel_sync_task(self, sync_task):
        cancelled_something = False

        # add it to the cancel list
        with self.cancel_lock:
            self.cancel[sync_task.operates_on()] = sync_task
            logger.info("Added task to cancel list '%s'.", sync_task)

        # Cancel action
        # 1) cancel all running tasks
        with self.running_lock:
            for running_task in self.running:
                if running_task.operates_on() == sync_task.operates_on():
                    running_task.cancel()
                    logger.info("Cancelled running task: '%s'.", running_task)
                    cancelled_something = True

        # 2) cancel all tasks currently in the queue
        # they'll not passed to the executor meanwhile, since we're holding the queue lock
        with self.pending.mutex:
            pending_tasks = self.pending.tasks_for(sync_task.operates_on())
            logger.debug("Found %d pending tasks.", len(pending_tasks))
            for pending_task in pending_tasks:
                pending_task.cancel()
                logger.info("Cancelled pending task prior to execution '%s'", pending_task)
                cancelled_something = True

        # 3) check if any tasks are in progress or queued
        if not cancelled_something:
            with self.cancel_lock:
                del self.cancel[sync_task.operates_on()]
                sync_task.state = cc.synctask.SyncTask.SUCCESSFUL
            sync_task.ack_callback(sync_task)

    def put_task(self, sync_task):
        """Put a task onto the queue, if not a CancelSyncTask.

        If it is a CancelSyncTask it will cancel all running and queued SyncTasks.
        As another side effect it will put CancelSyncTask on a separate set
        """
        logger.info('[put_task] %s', sync_task)
        if isinstance(sync_task, cc.synctask.CancelSyncTask):
            self._handle_cancel_sync_task(sync_task)
            return

        self.pending.put(sync_task)

        # syncing callbacks
        self.task_putted.send(sync_task)

    def get_task(self, block=True, timeout=None):
        """Return next task to be executed.

        Puts the task on the running list
        Should only be called by a worker who intends to process a taks.
        """
        task = self.pending.get(block, timeout)
        # decrease internal semaphore for correct task count
        self.pending.task_done()
        with self.running_lock:
            if isinstance(task, cc.synctask.SyncTask):
                self.running.add(task)
        return task

    def ack_task(self, task):
        """Acknowledge that the given task was completed.

        Called by a worker
        Removes the task from the running list and checks if there is a cancel task left
        """
        # pylint: disable=too-many-branches

        # remove from running list
        with self.running_lock:
            logger.info('[ack_task] %s', task)
            try:
                self.running.remove(task)
            except KeyError:
                logger.exception("Failed removing task")

        if task.state == cc.synctask.SyncTask.BLOCKED:
            # stop syncing blocked files
            task.state = cc.synctask.SyncTask.INVALID_OPERATION

        task.ack_callback(task)
        self.task_acked.send(task)

        # check if there are any cancel tasks, and if, if there are any related left
        with self.cancel_lock:
            path_hash = task.operates_on()
            cancel_task = self.cancel.get(path_hash)
            if cancel_task is not None:
                are_tasks_running = False
                # check the in queue
                with self.pending.mutex:
                    if len(self.pending.path_queue.get(path_hash, [])) != 0:
                        are_tasks_running = True
                with self.running_lock:
                    for running_task in self.running:
                        if running_task.path == cancel_task.path:
                            are_tasks_running = True
                            break
                    if not are_tasks_running:
                        # ack the cancel task and remove it from the list if
                        # there are not queued or running tasks left
                        del self.cancel[path_hash]
                        cancel_task.state = cc.synctask.SyncTask.SUCCESSFUL
                        cancel_task.ack_callback(cancel_task)

    def path_has_tasks(self, path_hash, is_dir):
        """Check if a path is in the queue or in the actual execution.

        :param is_dir: if set to True it will lookup if any of the subdirectories are
                       in a sync operation.
        """
        # TODO XXX: Make sure the given path_hash is actually a path_hash.
        result = False

        if not is_dir:
            with self.running_lock:
                # its only as much elements as workers, so iterations should be fine
                for task in self.running:
                    if path_hash == task.operates_on():
                        result = True
                        break
            with self.pending.mutex:
                result = result or path_hash in self.pending.path_queue
        else:
            # this is a fucked up operation -> improve?
            with self.running_lock:
                for task in self.running:
                    for my_hash, other_hash in zip(path_hash, task.operates_on()):
                        if my_hash != other_hash:
                            break
                    else:
                        result = True
            with self.pending.mutex:
                for task in self.pending.queue:
                    for my_hash, other_hash in zip(path_hash, task.operates_on()):
                        if my_hash != other_hash:
                            break
                    else:
                        result = True

        return result
