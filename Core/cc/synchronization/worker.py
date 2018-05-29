"""The worker class which runs in its own thread and cosumes sync tasks from a TaskQueue."""
import logging
import random
import threading
import time

import jars

import cc
from cc.synchronization.exceptions import (PolicyError,
                                           SyncTaskCancelledException)
from cc.synctask import STOP_TOKEN

logger = logging.getLogger(__name__)


def calculate_waiting_time(num_retries, max_delay=30, delta=10, base=1.5):
    """Calculate the back-off parameter for retrying operations.

    :param base: The exponential base
    :param delta: maximum random delta added to the result
    :param max_delay: the maximum delay
    :param num_retries: a value in seconds
    """
    value = base ** num_retries
    if value > max_delay:
        value = max_delay

    return random.random() * delta + value


class Worker(threading.Thread):
    """  class started n-times  """

    def __init__(self, ack_sink, task_source, task_sink, wait_delay=0.1,
                 max_retries=10):
        # pylint: disable=too-many-arguments
        super().__init__(daemon=True)
        self.max_retries = max_retries
        self.wait_delay = wait_delay
        self.task_sink = task_sink
        self.task_source = task_source
        self.ack_sink = ack_sink

    def run(self):
        """Starts an endless loop to acquire sync tasks from the queue."""
        while True:
            try:
                task = self.task_source()
                if task == STOP_TOKEN:
                    logger.debug("stopped worker %s", self)
                    break
                else:
                    if task.execute_after != 0 and task.execute_after > time.time():
                        # logger.debug("not dispatching task %s, has to wait", task)
                        # do a secure wait
                        time.sleep(self.wait_delay)
                        self.task_sink(task)
                    else:
                        logger.debug("dispatching task %s", task)
                        self.dispatch(task)
            except BaseException:
                logger.exception('Broad exception caught in worker thread execution')

    def dispatch(self, task):
        """Call the execute method on the given task and handle errors."""
        # pylint: disable=too-many-branches,too-many-statements
        try:
            if task.cancelled:
                raise SyncTaskCancelledException("Task was cancelled upfront")

            # increment the try counter
            task.tries += 1

            logger.info("Calling 'execute' on Task '%s'", task)
            task.execute()
            logger.info("Finished 'execute' on Task '%s'", task)
            task.state = cc.synctask.SyncTask.SUCCESSFUL
        except (jars.CurrentlyNotPossibleError, cc.crypto2.NoKeyError):
            if task.tries >= self.max_retries:
                logger.info("SyncTask could not be executed! -> failed ", exc_info=True)
                task.state = cc.synctask.SyncTask.CURRENTLY_NOT_POSSIBLE
            else:
                relative_waiting_time = calculate_waiting_time(task.tries)
                task.execute_after = relative_waiting_time + time.time()
                logger.info("SyncTask could not be executed! -> back-off(in %s s)",
                            relative_waiting_time,
                            exc_info=True)
                self.task_sink(task)
                return
        except PolicyError as error:
            logger.info("PolicyError", exc_info=True)
            cc.ipc_gui.displayNotification(title='Policy Error', description=error.message)
            task.state = cc.synctask.SyncTask.INVALID_OPERATION
        except (jars.InvalidOperationError, FileNotFoundError):
            logger.info('Failed with invalid operation error, %s', task, exc_info=True)
            task.state = cc.synctask.SyncTask.INVALID_OPERATION
        except jars.VersionIdNotMatchingError:
            logger.info('Version IDs are not matching for %s', task, exc_info=True)
            task.state = cc.synctask.SyncTask.VERSION_ID_MISMATCH
        except (SyncTaskCancelledException, jars.CancelledException):
            logger.debug('Task got cancelled', exc_info=True)
            task.state = cc.synctask.SyncTask.CANCELLED
        except jars.UnavailableError:
            if hasattr(task, 'state'):
                task.state = cc.synctask.SyncTask.INVALID_OPERATION
            logger.info("service is unavailable", exc_info=True)
        except jars.AuthenticationError:
            if hasattr(task, 'state'):
                task.state = cc.synctask.SyncTask.INVALID_AUTHENTICATION
            logger.info("service is not authenticated", exc_info=True)
        except BaseException:
            if hasattr(task, 'state'):
                task.state = cc.synctask.SyncTask.INVALID_OPERATION
            logger.warning('Uncatched exception from task, %s', task, exc_info=True)

        self.ack_sink(task)
