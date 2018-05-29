"""The Bademeister manages the pool of workers."""
import logging

from cc.synctask import STOP_TOKEN
from cc.synchronization.worker import Worker

logger = logging.getLogger(__name__)

# pylint: disable=too-many-instance-attributes


class Bademeister:
    """Keeps the pool funky fresh."""

    def __init__(self, queue, thread_count=5):
        self.thread_count = thread_count
        self.queue = queue

        self.workers = []

        # flag indicating if the step is running (has been started and not stopped)
        self.is_running = False

    def prepare_workers(self):
        """Return workers prepared to get things done."""
        return [Worker(task_source=self.queue.get_task,
                       ack_sink=self.queue.ack_task,
                       task_sink=self.queue.put_task) for _ in range(self.thread_count)]

    def start(self):
        """ starts the whole threadpool """
        self.workers = self.prepare_workers()

        for worker in self.workers:
            logger.debug("started worker %s", worker)
            worker.start()

        # setting flag
        self.is_running = True

    def stop(self):
        """ stops the whole threadpool  """
        for _ in range(len(self.workers)):
            self.queue.put_task(STOP_TOKEN)
        self.workers.clear()

        # setting flag
        self.is_running = False

    # TODO XXX: add and put callbacks are currently only registered outside of the init function
    # in the shell extension. Fix that or fix the shell extension?
    def register_callback(self, state, new_callback):
        """
        Adds an issue callback outside of initializer
        NOTE!! ONLY call this if STEP is not running, otherwise, it will fail
        :param new_callback: the new callback to add (1 arguments: path)
        """
        if self.is_running:
            raise RuntimeWarning("Cannot add callback while is running")

        logger.info("Registering callback for '%s': %s", state, new_callback)

        available = {
            # :param new_callback: the new callback to add (3 arguments: path, storage and
            'acknowledge': self.queue.ack_callbacks.append,
            # :param new_callback: the new callback to add (1 arguments: path)
            'put_task': self.queue.put_task_callbacks.append, }

        funky_ref = available.get(state, False)

        if funky_ref:
            funky_ref(new_callback)
            logger.info("Registering callback for '%s': %s", state, new_callback)
            return True

        logger.error("Tried to register unknown callback for '%s'", state)
        return False
