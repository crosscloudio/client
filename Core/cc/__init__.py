"""crosscloud main package.

please do not add any functional stuff here.
"""
# Ensure mimetypes does not add local files to the db.
# This way all operating systems should return the same mimetypes for various file extensions.
import mimetypes

from cc.configuration import get_basic_config

try:
    import BUILD_CONSTANTS

    __version__ = BUILD_CONSTANTS.version
except ImportError:
    __version__ = 'development'

mimetypes.init([])

__author__ = 'crosscloud GmbH'


class UnauthenticatedUserError(Exception):
    """Error for user not authenticated with administrator console."""


class DeviceApprovalRequiredError(Exception):
    """Error for the case of that the current device needs the approval of another device."""


config = get_basic_config()  # pylint: disable=invalid-name

# Create a dict with the relation between storage labels and display names so we are able to
# access them without authentication process
STORAGE_LABELS = {'gdrive': 'Google Drive', 'dropbox': 'Dropbox',
                  'onedrive': 'OneDrive', 'cifs': 'Windows Share',
                  'filesystem': 'File System', 'office365groups': 'Office 365 Groups',
                  'onedrivebusiness': 'OneDrive for Business', 'sharepoint': 'SharePoint',
                  'owncloud': 'OwnCloud', 'nextcloud': 'NextCloud',
                  'fairdocs': 'Fairdocs'}
