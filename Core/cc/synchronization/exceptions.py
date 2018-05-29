"""Contain synchronization related exceptions."""
import jars


class SynchronizationBaseException(Exception):
    """Basic exception for errors that ocur during sync process."""


class SyncTaskCancelledException(Exception):
    """Thrown in case a task is cancelled."""


class CannotConfigureSTEPWhileRunningException(Exception):
    """If the configuration of the step (e.g. adding callbacks) is done while it is running."""


class PolicyError(jars.InvalidOperationError):
    """Exception for Policy Warnings and Errors"""

    def __init__(self, path=None):
        super().__init__(storage_id=None, origin_error=None, path=path)
        self.message = "The synchronisation of the file {} " \
                       "is not allowed!".format('/'.join(path))

    def __str__(self):
        return self.message
