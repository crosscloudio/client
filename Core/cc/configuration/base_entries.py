"""This module contains defintions of various fields in the config
"""
import uuid
from . import models


class LocalConfig(models.Config):
    """The collection of locally held configurations."""

    csps = models.ConfigList(name='csps')
    """A list of locally mounted storage providers."""

    admin_console_csps = models.ConfigList(name='admin_console_csps')
    """A list of storage providers listed on the admin console."""

    policies = models.ConfigList(name='policies')
    """A list of currently configured policies."""

    encryption_csp_settings = models.ConfigDict(name='encryption_csp_settings')
    """Encryption setting for each storage provider type: {type: enabled}
    Example:
        {"dropbox": false, "cifs": true}
    """

    share_key_pairs = models.ConfigDict(name='share_key_pairs')
    """Share key pairs."""

    encryption_enabled = models.ConfigItem(value=False, name='encryption_enabled')
    """Flag indicating wether encryption is enabled globaly."""

    encrypt_external_shares = models.ConfigItem(value=False, name='encrypt_external_shares')
    """Flag indicating if public shares (public sharing links etc.) should be encrypted.

    TODO: models.ConfigBool
    """

    encrypt_public_shares = models.ConfigItem(value=False, name='encrypt_public_shares')
    """Flag indicating if public shares (public sharing links etc.) should be encrypted.

    TODO: models.ConfigBool
    """

    shares_with_external_users = models.ConfigItem(value=set(), name='shares_with_external_users')
    """Set with the (storage_type, share_id) of shares with external users.

    TODO: models.ConfigSet
    """

    public_keys = models.ConfigItem(name='public_keys')
    """All keys required to encrypt and decrypt."""

    storage_unique_id_mapping = models.ConfigItem(value=set(), name='storage_unique_id_mapping')
    """All known storage_unique_ids mapped to the corresponding admin console user"""

    user_private_key = models.ConfigItem(value=b'', name='user_private_key')
    """User privat key (set if encryption is enabled).

    TODO: models.ConfigByteString
    """

    user_public_key = models.ConfigItem(value=b'', name='user_public_key')
    """User privat key (set if encryption is enabled).

    TODO: models.ConfigByteString
    """

    device_private_key = models.ConfigItem(value=b'', name='device_private_key')
    """Private key of a device. Must always be present."""

    device_public_key = models.ConfigItem(value=b'', name='device_public_key')
    """Public key of the current device. Must always be present"""

    master_key_subject = models.ConfigStr(value=None, name='master_key_subject')
    """Subject of the master key"""

    master_key_pem = models.ConfigStr(value=None, name='master_key_pem')
    """PEM of the master key"""

    user_id = models.ConfigStr(value=None, name='user_id')
    """The uuid of the user."""

    organization_id = models.ConfigStr(value=None, name='organization_id')
    """The uuid of the organisation of which the users is a member"""

    user_email = models.ConfigStr(name='user_email')
    """Email with which the user is logged into the backend."""

    device_id = models.ConfigStr(value=str(uuid.uuid1()), name='device_id')
    """uuid of the current device."""

    last_login = models.ConfigStr(name='last_login')
    """Time of the last login on the Admin Console"""

    auth_token = models.ConfigStr(value=None, name='auth_token')
    """Authentification token required for talking to admin console."""

    enabled_storage_types = models.ConfigList(name='enabled_storage_types')
    """A list of storage types which the admin has enabled on the admin console."""

    blocked_extensions = set()
    """Extensions to be blocked for uploading"""

    blocked_mime_types = set()
    """Mime types blocked for uploading"""
