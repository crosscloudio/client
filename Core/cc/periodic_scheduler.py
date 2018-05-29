"""
This module exposes a thread class which enables to execute a task in a periodic manner
"""

import threading
import logging

logger = logging.getLogger(__name__)


class PeriodicScheduler(threading.Thread):
    """ Helper class for pollers, which helps to be cancelable"""

    # pylint: disable=too-many-arguments
    def __init__(self, interval, target=None, target_args=(), target_kwargs=None):
        """
        Scheduled method execution
        :param interval: sleep between two executions
        :param target: target function pointer
        :param target_args: target arguments
        :param target_kwargs: target keyword argument
        :param offline_callback: triggered with parameter true if call was successful
                                 and false if it failed
        """
        super().__init__(daemon=True)
        if target_kwargs is None:
            target_kwargs = {}
        self.target = target
        self.target_args = target_args
        self.target_kwargs = target_kwargs
        self.stop_event = threading.Event()
        self.interval = interval

    def stop(self, join=False, timeout=None):
        """ sets the stop flag  """
        self.stop_event.set()
        if join:
            self.join(timeout)

    def start(self):
        """ resets the stop flag """
        if not self.is_alive():
            self.stop_event.clear()
            return super().start()

    def run(self):
        """ checks every interval """
        while True:
            try:
                self.target(*self.target_args, **self.target_kwargs)
            except BaseException:
                logger.error('Error while running periodic scheduler function', exc_info=True)

            self.stop_event.wait(self.interval)

            if self.stop_event.is_set():
                logger.debug("Stopped poller")
                break
