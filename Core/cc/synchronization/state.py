"""Module to encapulate the synchronization state between two storages."""
import logging
import pickle

import atomicwrites
from bushn import Node

from cc.periodic_scheduler import PeriodicScheduler

logger = logging.getLogger(__name__)


class LocalEngineStateSync(object):
    """State of the local Sync Engine"""
    SYNC_STATE_FILE = 'sync_state.dat'
    SYNC_STATE_SAVE_PERIOD = 60

    def __init__(self, engine, location):
        self.engine = engine
        self.location = location
        self.__writer = PeriodicScheduler(self.SYNC_STATE_SAVE_PERIOD, self.persist)

    @property
    def writer(self):
        """Return the periodic scheduler which dumps the state to disk regularly."""
        return self.__writer

    def persist(self):
        """Persists the associated engine state to disk."""
        State.to_pickle(self.engine, self.location)


class State(object):
    """Formerly known as the sync_state_model. The sync state between two endpoints """
    KEEPLIST = ['desired_storages', 'equivalents']
    VERSION = 1

    # State.fromfile(os.path.join(cc.config.config_dir, State.FILENAME)
    # model_file_path = os.path.join(cc.config.config_dir, self.SYNC_STATE_FILE)
    @classmethod
    def fromfile(cls, location):
        """Load state from a dump file.

        :param location: path to the dump file.
        :type location: str
        """
        logger.info("Trying to load synchronization state from '%s'...", location)
        try:
            with open(location, 'rb') as state_file:
                state = pickle.load(state_file)
                logger.info("Unpickled model from '%s'!", location)
        except FileNotFoundError:
            logger.warning("Can't find file '%s'! Using empty model instead!", location,
                           exc_info=True)
            state = Node(name=None)
        except BaseException:
            logger.warning("Can't load model from '%s'! Using empty model instead!", location,
                           exc_info=True)
            state = Node(name=None)

        version = state.props.get('model_version', 0)
        logger.debug('Loaded model with version %d.', version)
        return state

    @staticmethod
    def cleanup(model):
        """Remove all unnecessary attributes from the tree."""
        for node in model:
            if node.parent is None:
                continue
            for key in list(node.props.keys()):
                if key not in State.KEEPLIST:
                    del node.props[key]

    @classmethod
    def to_pickle(cls, engine, location):
        """Persists the currently present model in the associated sync_engine to disk."""
        logger.debug('requesting sync model to save')

        sync_model_future = engine.get_model_copy()
        sync_model = sync_model_future.get()

        logger.debug("Cleaning model.")
        cls.cleanup(sync_model)

        logger.debug("Saving persistent model.")
        with atomicwrites.atomic_write(location, mode='wb', overwrite=True) as file_handle:
            pickle.dump(sync_model, file_handle)
            logger.info("Wrote sychnronization state model of '%s' to '%s'", engine, location)
