"""Module for syncing settings and accounts."""
# pylint: disable=too-many-statements
import datetime
import json
import logging
import os
import sys

import requests
from requests import HTTPError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from marshmallow import Schema, fields, post_dump

import jars
import cc.crypto
import cc.crypto2
import cc.ipc_gui
import cc.synctask
from cc.configuration import helpers
from cc.requests_utils import FingerprintAdapter
from cc.synchronization.syncfsm import FILESYSTEM_ID
from cc.utils import current_storage_props

#: share:<key-iteration>:<storage_type>+<share_id>
EXEPECETD_API_VERSION = '0.1.0'
KEY_SUBJECT_SHARE = 'share:{}:{}+{}'
#: share:<key-iteration>:<user-id>@<organization-id>
KEY_SUBJECT_USER = 'user:{}:{}@{}'
#: master:<key-iteration>:<org-uuid>
KEY_SUBJECT_MASTER = 'master:{}:{}'

# pylint: disable=invalid-name
logger = logging.getLogger(__name__)

# TODO XXX: Everything build configuration related is a work-around and should be refactored!
# !!!!!! NEVER EVER HARD-CODE A VALUE HERE, PLEASE USE THE ENV-VARIABLE !!!!
FALLBACK_ADMIN_CONSOLE_URL = os.environ.get('CC_ADMIN_CONSOLE_URL',
                                            'https://cc-testing.crosscloud.me')
FALLBACK_CERTFINGERPRINT = '51581E6EA9EE5B9C292793924A348E37FD491C4465FA8BBDBC16CE00B9A9DC58'

if hasattr(sys, 'frozen'):
    logger.info("Checking for build configuration.")
    build_configuration_profile = os.path.join(os.path.dirname(sys.executable), 'profile.json')

    if os.path.exists(build_configuration_profile):
        logger.debug("Found build configuration in '%s'.", build_configuration_profile)
        with open(build_configuration_profile) as pfh:
            build_config = json.load(pfh).get('admin_console', {})
            logger.debug("Loaded build configuration '%s'.", build_config)

        # Set Admin Console to build configuration, env. variable or default.
        HOST = build_config.get('url', FALLBACK_ADMIN_CONSOLE_URL)
        # Set Fingerprint to build configuration or default.
        CERT_FINGERPRINT = build_config.get('fingerprint', FALLBACK_CERTFINGERPRINT)
    else:
        logger.warning("No build configuration found in '%s'.", build_configuration_profile)
        HOST = FALLBACK_ADMIN_CONSOLE_URL
        CERT_FINGERPRINT = FALLBACK_CERTFINGERPRINT
else:
    logger.info("Not frozen. Not checking for build configuration.")
    HOST = FALLBACK_ADMIN_CONSOLE_URL
    CERT_FINGERPRINT = FALLBACK_CERTFINGERPRINT

GRAPHQL_URL = '{}/graphql'.format(HOST)
TOKEN_URL = '{}/auth/local'.format(HOST)
KEYCHAIN_KEY = 'CrossCloud-Portal'

logger.info("Setting console to '%s'.", HOST)
logger.debug("GraphQL URL '%s'", GRAPHQL_URL)
logger.debug("Token URL '%s'", TOKEN_URL)
logger.info('Fingerprint checking enabled against "%s".', CERT_FINGERPRINT)

# the server configuration fetched from the admin console
server_config = None
# last known encryption enablign status
prev_encryption_state = None


class GraphQLError(Exception):
    """Raise when graphql response contains a 'error' entry."""
    pass


def raise_for_graphql_error(response):
    """Raise GraphQLError if response contains errors and raise for status.

    The raise for status is included to remove clutter from the rest of the code.
    Simply use `raise_for_graphql_error(response)` instead of `respons`.raise_for_status()`
    """
    response.raise_for_status()

    try:
        if 'errors' in response.json():
            raise GraphQLError(response.json()['errors'])
    except json.JSONDecodeError:
        # There is no json here to decode
        pass


def rfc_now():
    """Current time in iso format."""
    return datetime.datetime.utcnow().isoformat()


class SyncTaskLogEntry(Schema):
    """JSON Schema for sync task on api side."""

    type = fields.Str(default='SyncTask')
    timestamp = fields.DateTime(default=rfc_now)
    path = fields.List(fields.Str)
    mime_type = fields.Str()
    encrypted = fields.Boolean(default=False)
    bytes_transferred = fields.Integer()

    @post_dump(pass_original=True)
    def parse_type(self, item, original):
        """Add the type and the storage."""
        # pylint: disable=no-self-use
        item['type'] = type(original).__name__
        item['status'] = original.state
        relevant_storage_id = ''
        if isinstance(original, cc.synctask.UploadSyncTask):
            relevant_storage_id = original.target_storage_id
        elif isinstance(original, cc.synctask.DownloadSyncTask):
            relevant_storage_id = original.source_storage_id
        elif isinstance(original, cc.synctask.DeleteSyncTask):
            relevant_storage_id = original.target_storage_id
        elif isinstance(original, cc.synctask.CreateDirSyncTask):
            relevant_storage_id = original.target_storage_id

        item['storage_id'] = relevant_storage_id


def fetch_admin_console_configuration(config):
    """Fetch admin console configuration."""
    # pylint: disable=global-statement
    global server_config

    # getting authentication token
    auth_token = get_token(config=config)

    # if token present, initialising server configuration
    if auth_token:
        try:
            server_config = fetch_user_settings(config=config)
        except HTTPError as err:
            if err.response.status_code == 401:
                raise cc.UnauthenticatedUserError()
            else:
                raise err
    else:
        raise cc.UnauthenticatedUserError()


def fetch_and_apply_configuration(config):
    """Fetch and applies the configuration from the server"""
    logger.debug('fetch and apply configuration')
    fetch_admin_console_configuration(config=config)
    apply_configuration(config=config)


def check_encryption_change(restart_client):
    """Compare current and previous encryption status and trigger restart."""
    # pylint: disable=global-statement
    global prev_encryption_state

    cur_encryption_state = server_config['organization']['encryption']
    if prev_encryption_state is not None and prev_encryption_state != cur_encryption_state:
        # restart client if encryption status has changed
        logger.info('client restart triggered, new encryption status: %s', cur_encryption_state)
        restart_client()
    prev_encryption_state = cur_encryption_state


def authenticate_user(username, password, config):
    """Authenticate / log in the user with the CrossCloud backend
    :return the client auto updating the value
    """
    logger.debug('Authenticating user against admin console on %s', HOST)

    # pylint: disable=global-statement
    try:
        session = get_fingerprint_checking_session()
        res = session.post(TOKEN_URL,
                           json={'email': username, 'password': password})
        raise_for_graphql_error(res)
        token_saver(res.json(), config=config)

        return get_session(config=config)
    except HTTPError as err:
        if err.response.status_code == 401:
            raise cc.UnauthenticatedUserError()
        else:
            raise err


def logout(config):
    """Logout the user by deleting the authentication token from the configuration file."""
    config.auth_token = None
    config.write_config()
    config.read_config()
    assert config.auth_token is None


def apply_configuration(config):
    """ sends the current config to the endpoints """
    # pylint: disable=redefined-outer-name

    logger.debug('apply configuration')

    # making sure token and server config are present
    if config.auth_token and server_config:
        # updating crypto
        update_crypto(config=config)

        # updating csps
        update_storages(config=config)

        # updating policies
        update_policies(config=config)

        # updating enabled storages
        update_enabled_storages(config=config)

        # getting device key approval requests if there are any
        update_device_approval_request()

        # writing configuration for admin console storages
        config.admin_console_csps = [csp['csp_id'] for csp in
                                     fetch_user_settings(config=config)['csps']]

        config.public_keys, \
            config.storage_unique_id_mapping, config.share_key_pairs = get_share_info(config)

        config.write_config()

        # storing user and organisation info
        config.user_id = server_config['id']
        config.organization_id = server_config['organization']['id']
        config.user_email = server_config['email']
    else:
        logger.warning('Unable to apply configuration.')


def update_enabled_storages(config):
    """Store the currently enabled storages in the config."""
    if not config.enabled_storage_types == server_config['enabled_storage_types']:
        config.enabled_storage_types = server_config['enabled_storage_types']
        storage_props = current_storage_props(config=config,
                                              registered_storages=jars.registered_storages)
        logger.info('Updating GUI account types.')
        cc.ipc_gui.updateAccountTypes(storage_props)


def update_share_keys(config):
    """Checks if there are any shares present which have users without a share key and
    if this is the case provides the necessary key material and sends it to the
    admin console"""
    logger.info("Updating share keys.")

    for csp in server_config['csps']:
        logger.debug("Processing storage '%s'.", csp['csp_id'])

        for share in csp['shares']:
            logger.debug("Updating share keys for %s share '%s'.",
                         share['storage_type'],
                         share['unique_id'])
            key_subject = KEY_SUBJECT_SHARE.format(0, share['storage_type'], share['unique_id'])
            logger.debug("Key subject is '%s'", key_subject)

            if key_subject not in config.share_key_pairs:
                logger.info("No key present for subject '%s'. Skipping.", key_subject)
                continue

            key_pair = config.share_key_pairs[key_subject]
            logger.debug("Got key pair for subject '%s'.", key_subject)

            logger.debug("Handling users without share key.")
            for user in share['users_without_share_key']:
                logger.debug('Encryption key for user: %s', user)
                public_key_object = cc.crypto2.load_pem_public_key(
                    user['public_key'].encode('ascii'))
                encrypted_share_key = json.dumps(cc.crypto2.wrap_private_key(
                    private_key_pem=key_pair.private_pem,
                    public_key_object=public_key_object))

                # try to upload the wrapped keys
                variables = {"storage_type": share['storage_type'],
                             "share_unique_id": share['unique_id'],
                             "user_id": user['id'],
                             "encrypted_share_key": encrypted_share_key}

                mutation = '''
                          mutation AddShareKey(
                              $storage_type: String!,
                              $share_unique_id: String!,
                              $user_id: String!,
                              $encrypted_share_key: String!) {
                                   addShareKey(storage_type: $storage_type,
                                   share_unique_id: $share_unique_id,
                                   user_id: $user_id,
                                   encrypted_share_key: $encrypted_share_key)
                                   {encrypted_share_key}
                           }
                       '''

                logger.debug("Submitting wrapped share key to backend.")
                response = get_session(config).post(
                    GRAPHQL_URL,
                    json={
                        'query': mutation,
                        'variables': variables
                    })

                raise_for_graphql_error(response)
                logger.debug("Submitting wrapped share key for '%s' to backend.", user)
        logger.debug("Finished processing storage '%s'.", csp['csp_id'])
    logger.info("Updated share keys.")


def update_share_information(storages, config):
    """Update the information about shares in the administrator console.

    :param storages: the locally configured storages after the server config has
    been applied
    :param config: The current client configuration.
    """

    # pylint: disable=too-many-locals,too-many-branches

    # early return if auth token or server config not present
    if not config.auth_token or not server_config:
        logger.warning("No authentication token or server configuration found. Returning.")
        return

    logger.debug("Updating share information.")
    # 1) getting admin console shares
    # structure of ac share data structure {csp_id: {unique_id: ({user_unique_ids}, name)
    shares_admin_console_all = {}

    # data structure for external users -> will be saved in config
    shares_with_external_users = set()

    # going through the shares per storage
    for storage_provider in server_config['csps']:
        logger.debug("Updating sharing information for storage '%s' for %d shares.",
                     storage_provider.get('csp_id', 'Unknown'),
                     len(storage_provider.get('shared', [])))

        id_to_info = {}

        # going through all the shares of the storage
        for share in storage_provider['shares']:
            logger.debug("Updating share '%s' with %s",
                         share['name'],
                         set(share['storage_unique_ids']))
            id_to_info[share['unique_id']] = (set(share['storage_unique_ids']),
                                              share['name'])

            # adding to external shares if appropriate
            if share['has_external_users']:
                logger.debug("Share has external users.")
                shares_with_external_users.add(
                    (storage_provider['type'], share['unique_id']))

        # setting external shares in config
        logger.info("Update shares with external users.")
        helpers.set_shares_with_external_users(config, shares_with_external_users)

        logger.debug("Storing updated sharing information for '%s'.",
                     storage_provider.get('csp_id'))
        shares_admin_console_all[storage_provider['csp_id']] = id_to_info

    # 2) getting shares from the storages (same data structure as in 1))
    for storage in storages:
        logger.debug("Processing shares for storage '%s'.", storage.storage_id)
        if storage.storage_id == FILESYSTEM_ID:
            logger.debug("Storage is local filesystem. Skipping.")
            continue

        try:
            # getting storage shares (same data structure as for ac)
            shares_storages = {share.share_id: (set(share.sp_user_ids), '/'.join(share.path))
                               for share in storage.get_shared_folders()}
            logger.debug("Storage '%s' has %d shares.",
                         storage.storage_id,
                         len(shares_storages))
        except BaseException:
            # if we cannot get the shares for this storage -> skip it
            logger.warning("Could not get share information for storage '%s'. Skipping.",
                           storage.storage_id,
                           exc_info=True)
            continue

        # getting shares admin console for this csp
        logger.debug("Fetching shares for '%s' from admin console.", storage.storage_id)
        shares_admin_console = shares_admin_console_all.get(storage.storage_id, None)

        # comparing the two in three cases 1) a not b 2) b not a 2) a and b + check
        if shares_admin_console is not None:
            logger.debug("Comparing gathered sharing information.")

            # getting sets from keys of dict
            local_set = set(shares_storages.keys())
            logger.debug("Local set has %d items (%s).", len(local_set), local_set)

            ac_set = set(shares_admin_console.keys())
            logger.debug("Remote set has %d items (%s).", len(ac_set), ac_set)

            # getting storage type
            current_csp = get_csp_from_list(storage.storage_id, config.csps)
            storage_type = current_csp['type']

            # 1) shares locally but not remotely -> add to ac
            # adding shares to admin console

            logger.debug("Submitting shares that are not yet stored with the backend.")
            for share_id in local_set - ac_set:
                logger.info("Adding local share to remote.")
                key_pair = add_share_remote(share_id=share_id,
                                            users=list(shares_storages[share_id][0]),
                                            storage_type=storage_type,
                                            share_name=shares_storages[share_id][1],
                                            config=config)
                logger.debug("Added local share '%s' to remote.", share_id)
                config.share_key_pairs[
                    KEY_SUBJECT_SHARE.format(0, storage_type, share_id)] = key_pair

            # 2) shares added remotely but not locally -> remove remotely
            # removing shares from admin console
            logger.debug("Removing shares no longer present in the backend.")
            for share_id in ac_set - local_set:
                logger.info("Removing share from remote.")
                # removing self from admin console share
                remove_user_from_share_remote(share_id=share_id,
                                              storage_type=storage_type,
                                              storage_id=current_csp['unique_id'],
                                              config=config)
                logger.debug("Removed share '%s' from remote.", share_id)

            # 3) shares present on locally and on ac -> check user ids of shares
            # checking mails on shares and updating if required
            logger.debug("Updating user information for existing shares.")
            for share_id in local_set & ac_set:
                logger.debug("Checking share '%s'.", share_id)
                # checking if the content is the same -> else update
                if (shares_storages[share_id][0] != shares_admin_console[share_id][0]) \
                        or (shares_storages[share_id][1] != shares_admin_console[
                            share_id][1]):
                    logger.debug('Users on share have been changed: "%s", %s!=%s',
                                 shares_storages[share_id][1],
                                 shares_storages[share_id][0],
                                 shares_admin_console[share_id][0])
                    adapt_users_of_share_remote(storage_type=storage_type,
                                                share_id=share_id,
                                                users=list(shares_storages[share_id][0]),
                                                share_name=shares_storages[share_id][1],
                                                config=config)
                    logger.debug("Adapted users of remote share.")
                else:
                    logger.debug("Users on share '%s' have not changed", share_id)

            update_share_keys(config)
            logger.debug("Successfully updated share information!")
        else:
            # if the csp_id is not present from the admin console, the account is
            # added locally but not remotely -> this should not happen
            logger.error('Account is added locally but not remotely, this should '
                         'not happen')


def update_policies(config):
    """
    Stores the fetched policies in the local persistent storage
    :return:
    """
    # pylint: disable=redefined-outer-name

    # config.policies = server_config['organization']['policies']
    config.blocked_extensions = set()
    config.blocked_mime_types = set()

    for policy in server_config['organization']['policies']:
        if not policy['is_enabled']:
            continue

        if policy['type'] == 'mimetype':
            for criteria in policy['criteria'].split(','):
                config.blocked_mime_types.add(criteria)
        elif policy['type'] == 'fileextension':
            config.blocked_extensions.add(policy['criteria'])
        else:
            logger.error('Unknown policy type')


def update_crypto(config):
    """
    Updates all crypto related parts
    """
    # pylint: disable=redefined-outer-name

    logger.debug('updating crypto')

    # extracting encryption settings
    encryption = server_config['organization']['encryption']

    # parsing crypto values
    encryption_enabled = encryption['enabled']
    csp_settings = encryption['csps_settings']
    encrypt_external_shares = encryption['encrypt_external_shares']
    encrypt_public_shares = encryption['encrypt_public_shares']

    if encryption_enabled:
        # only fetch master key if encryption is enabled, without that we don't
        config.master_key_pem = encryption['master_key'].encode('ascii')
    config.master_key_subject = \
        KEY_SUBJECT_MASTER.format(0, server_config['organization']['id'])

    # getting public key of current user
    user_public_key = server_config['public_key']

    # checking if the user keys have been initialized by another device.
    # if not -> setting everything up
    if not user_public_key:
        perform_initial_key_setup(config)

    # if it is -> checking if either we are good or need to request approval
    elif not config.user_public_key or user_public_key != config.user_public_key.decode('ascii'):
        # checking if the device was already approved
        device_approvals = [approved_key for approved_key in
                            server_config['encrypted_user_keys']
                            if approved_key['device_id'] == config.device_id and
                            approved_key['public_device_key'] ==
                            config.device_public_key.decode('ascii')]

        # if approved request is there -> unwrap and save private key
        if device_approvals:
            # getting wrapped user key
            wrapped_user_private_key = device_approvals[0]['encrypted_user_key']

            # unwrapping user private key
            config.user_private_key = cc.crypto2.unwrap_private_key(
                wrapped_object=json.loads(wrapped_user_private_key),
                private_key_object=cc.crypto2.load_pem_private_key(
                    config.device_private_key))

            # saving user public key
            config.user_public_key = user_public_key.encode('ascii')

            # writing config to ensure this gets into the config
            helpers.write_config(config=config)

            cc.ipc_gui.displayNotification('Device Approved', 'This device has been '
                                                              'approved')
        # we need to request approval
        else:
            # ensuring that device keys are setup
            if not config.device_public_key or not config.device_private_key:
                # creating new device key pair
                (config.device_private_key, config.device_public_key) = \
                    cc.crypto2.generate_keypair()

                # writing config to ensure this gets into the config
                helpers.write_config(config=config)

            # we need to request approval from another device
            request_device_approval(device_id=config.device_id,
                                    public_device_key=config.device_public_key,
                                    config=config)

            # raising error
            raise cc.DeviceApprovalRequiredError('Approval from another device required.')

    # setting new value for config
    config.encryption_enabled = encryption_enabled
    config.encrypt_external_shares = encrypt_external_shares
    config.encrypt_public_shares = encrypt_public_shares

    # setting the csp encryption settings
    config.encryption_csp_settings = {csp_setting['type']: csp_setting['enabled']
                                      for csp_setting in csp_settings}

    helpers.write_config(config=config)


def perform_initial_key_setup(config):
    """ sets up the initial keys on the administrator console"""
    # pylint: disable=redefined-outer-name
    # pylint: disable=no-member
    logger.debug('performing initial key setup')

    # setting up device keys
    device_private_key, device_public_key = cc.crypto2.generate_keypair()

    # setting up user key
    user_private_key, user_public_key = cc.crypto2.generate_keypair()

    # wrapping user private key with device public key
    wrapped_private_user_key = cc.crypto2.wrap_private_key(
        private_key_pem=user_private_key,
        public_key_object=cc.crypto2.load_pem_public_key(device_public_key))

    try:
        # initialising user keys on admin console
        init_admin_console_user_keys(device_id=config.device_id,
                                     public_user_key=user_public_key,
                                     encrypted_private_user_key=wrapped_private_user_key,
                                     public_device_key=device_public_key,
                                     config=config)
    except GraphQLError:
        logger.debug("Unable to init user keys. This operation is only possible once.")
        return

    # After sucessfull `init_admin_console_user_key` we save the keys to the config
    config.device_private_key = device_private_key
    config.device_public_key = device_public_key

    config.user_private_key = user_private_key
    config.user_public_key = user_public_key


def update_storages(config):
    """
    The actual settings sync. Triggers the add and remove actions based on the
    local state
    """

    # pylint: disable=redefined-outer-name

    current_remote_csps = {csp['csp_id'] for csp in server_config['csps']}
    current_local_csps = {csp['id'] for csp in config.csps}
    # last_remote_csps = set(config.admin_console_csps)

    # CC-560: Do not sync accounts DOWN from the admin console, but just UP to the admin console.
    #         An new user story will be created that reflects the final behaviour.

    # remote_added_csps = current_remote_csps - last_remote_csps - current_local_csps
    # remote_removed_csps = last_remote_csps - current_remote_csps
    local_added_csps = current_local_csps - current_remote_csps  # - remote_removed_csps
    local_removed_csps = current_remote_csps - current_local_csps  # - remote_added_csps

    # for csp_id in remote_added_csps:
    #     csp = get_csp_from_list(csp_id, server_config['csps'], 'csp_id')
    #     if csp is not None:
    #         add_csp_local(csp)

    # for csp_id in remote_removed_csps:
    #     csp = get_csp_from_list(csp_id, config.csps)
    #     if csp is not None:
    #         remove_csp_local(csp)

    for csp_id in local_added_csps:
        csp = get_csp_from_list(csp_id, config.csps)
        if csp is not None:
            try:
                add_csp_remote(csp, config=config)
            except GraphQLError as error:
                logger.info('Unabale to add storage %s to admin console: %s',
                            csp['display_name'], error)

    for csp_id in local_removed_csps:
        csp = get_csp_from_list(csp_id, server_config['csps'], 'csp_id')
        if csp is not None:
            remove_csp_remote(csp, config=config)


def token_saver(token, config=None):
    """Store authentication token inside global and persist it to disk."""
    # pylint: disable=redefined-outer-name
    config.auth_token = json.dumps(token)
    helpers.write_config(config)


def get_token(config=None):
    """Get authentication token from configuration file."""
    try:
        # logger.info(config.auth_token)
        auth_token = json.loads(config.auth_token)
    except (json.JSONDecodeError, TypeError):
        logger.info('Failed to load token.')
        auth_token = None
    return auth_token


def get_fingerprint_checking_session():
    """Return requests.session with enforced certificate fingerprint verification."""
    session = requests.Session()
    if getattr(sys, 'frozen', False):
        logger.info("Using console at '%s'", HOST)
        logger.info('Fingerprint checking enabled against "%s"', CERT_FINGERPRINT)
        session.mount(HOST, FingerprintAdapter(CERT_FINGERPRINT))
    else:
        logger.warning('Fingerprint checking not enabled')
    session.headers['X-Api-Version-Expected'] = EXEPECETD_API_VERSION
    return session


def get_session(config):
    """returns the session for accessing settings sync resources"""
    # building token
    token = get_token(config=config)
    session = get_fingerprint_checking_session()
    session.headers = {'Authorization': 'Bearer {}'.format(token['token'])}
    return session


def is_encrypted_upload_or_download_task(task):
    """Determine whether the a given tasks handled encrypted data or not.

    Helper function to determine whether the given task was handling encrypted data.
    This is currently only relevant for Upload/Download Tasks and logging to the Admin Console.

    :param task: The current task.
    :return: True if the task handled encrypted data, False otherwise.
    """
    from cc.encryption.storage_wrapper import EncryptedVersionTag

    # Only Upload/Download Tasks should be marked/handled.
    if not isinstance(task, cc.synctask.CopySyncTask):
        return False

    # Encrypted Upload
    if isinstance(task.source_version_id, EncryptedVersionTag) \
            and task.source_version_id.key_subjects:
        return True

    # Encrypted Download
    if isinstance(task.target_version_id, EncryptedVersionTag) \
            and task.target_version_id.key_subjects:
        return True

    return False


def log_task_to_backend(config, task):
    """Log a task to the backend if logged in.

    For task to be logged its type must either be a CopySyncTask or DeleteSyncTask.
    """
    logger.debug("logging to backend %s %s", task.path, type(task))
    if get_token(config=config):
        if isinstance(task, cc.synctask.CopySyncTask) or \
                isinstance(task, cc.synctask.DeleteSyncTask):
            schema = SyncTaskLogEntry()
            if is_encrypted_upload_or_download_task(task):
                logger.debug("'%s' handled upload/download of encrypted data.", task)
                task.encrypted = True
            dump = schema.dump(task)
            try:
                mutation = '''mutation AddActivityLogMutation($input: ActivityLogInput!) {
                                  addActivityLog(input: $input) {
                                    id
                                  }
                                }'''

                get_session(config).post(
                    GRAPHQL_URL,
                    json={
                        'query': mutation,
                        'variables': {
                            'input': dump.data
                        }
                    })

                # TODO: find a mutation without arguments
                # with a user role you can't access any field, so it raises an error even the
                # insert was sucessfully
                # raise_for_graphql_error(response)

            except HTTPError:
                logger.debug('Error while connecting to admin console', exc_info=True)


def fetch_user_settings(config):
    """
    Fetches the current user's settings from the admin console
    this contains al necessary data
    :return: the currents user settings
    """
    # pylint: disable=global-statement
    global server_config

    logger.debug('fetch user settings')
    query = '''{
  currentUser {
    id
    email
    roles
    enabled_storage_types
    public_key
    encrypted_user_keys {
      public_device_key
      device_id
      encrypted_user_key
    }
    approval_requests {
      public_device_key
      device_id
    }
    organization {
      id
      display_name
      encryption {
        master_key
        enabled
        encrypt_external_shares
        encrypt_public_shares
        csps_settings {
          type
          enabled
        }
      }
      policies {
        name
        type
        criteria
        is_enabled
      }
    }
    csps {
      id
      display_name
      csp_id
      unique_id
      type
      authentication_data
      shares {
        id
        name
        storage_type
        unique_id
        has_external_users
        storage_unique_ids
        users_without_share_key {
            id
            public_key
        }

        csps {
          unique_id
          user {
            email
            public_key
          }
        }
        public_share_key
        share_key_for_current_user {
          encrypted_share_key
        }
      }
    }
  }
}
'''
    resp = get_session(config).post(
        GRAPHQL_URL,
        json={'query': query}
    )

    raise_for_graphql_error(resp)
    server_config = resp.json()['data']['currentUser']
    return server_config


def get_csp_from_list(csp_id, csp_list, field='id'):
    """
    Extracts a csp dict from a given list
    """
    for csp in csp_list:
        if csp[field] == csp_id:
            return csp


def add_csp_local(csp, config):
    """
    Adds a CSP to the local list of mounted csps and also adds the credentials
    to the keychain

    @:param csp: remote object from admin console
    """
    # pylint: disable=redefined-outer-name

    cloud_account = {'id': csp['csp_id'],
                     'type': csp['type'],
                     'unique_id': csp['unique_id'],
                     'display_name': csp['display_name'],
                     'credentials': csp['authentication_data']}
    config.csps.append(cloud_account)
    config.write_config()
    logger.info("Added remote storage provider %s to configuration.", csp['unique_id'])


# The only call to this is currently commented out.
# TODO: Is it still needed?
# def remove_csp_local(csp_remote, field='id', config):
#     """Remove a storage provider from the global list of configured storage providers."""
#     # pylint: disable=redefined-outer-name

#     config.remove_csp(csp_remote[field])


def add_csp_remote(csp_local, config):
    """ Adds a csp to the csps list of the current user in the admin console
    @:param csp: the local csp dict is used
    """
    mutation = 'mutation AddCspMutation($input: CloudStorageProviderInput!) {' \
               'addCloudStorageProvider(input: $input) {unique_id}}'

    inp = {"unique_id": csp_local['unique_id'],
           "display_name": csp_local['display_name'],
           "type": csp_local['type'],
           "authentication_data": csp_local['credentials'],
           "csp_id": csp_local['id']}

    response = get_session(config=config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': {
                'input': inp
            }
        })

    raise_for_graphql_error(response)


def remove_csp_remote(csp, config):
    """ Removes a csp from the csps list of the current user in the admin console
    @:param csp: the remote csp dict is used
    """
    mutation = 'mutation DeleteCspMutation($csp_id: String!) { ' \
               'deleteCloudStorageProvider(csp_id: $csp_id) { id }}'

    variables = {'csp_id': csp['csp_id']}

    response = get_session(config=config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def add_share_remote(share_name, share_id, users, storage_type, config):
    """ adds a share to the administrator console and generates a keypair
    :param share_id: id of the share to add
    :param users: users having access to the share
    :param storage_type: type of the storage"""
    logger.info("Adding remote share #'%s' named '%s'.", share_id, share_name)
    logger.info("Users with access are '%s'.", users)

    # OneDrive and Owncloud return 1 user if they are not the owners of the share.
    # To prevent problems with they sharekeys we are allowing only the owner to update
    # with a new share.
    # TODO: investigate ways to fix/improve this patch (hack)
    excluded_storages = ['onedrive', 'owncloud']
    if storage_type in excluded_storages and len(users) == 1:
        logger.debug("%s couldn't add share because it's not the owner.", storage_type)
        return

    mutation = '''mutation AddShare($share: ShareInput!) {
     addShare(input: $share) { id users {  id   public_key }}}'''

    variables = {"share": {"storage_type": storage_type,
                           "unique_id": share_id,
                           "storage_unique_ids": users,
                           "name": share_name}}

    response = get_session(config=config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    try:
        raise_for_graphql_error(response)
    except GraphQLError as error:
        # this happens, if the share is in the db but already initalized because the account was
        # removed meanwhile
        logger.error("Error while adding share remote: %s", error)
        return

    keypair = cc.crypto2.generate_keypair()

    encrypted_private_keys = []
    for user in response.json()['data']['addShare']['users']:
        if not user['public_key']:
            logger.warning("User '%s' has no public key attached. Skipping.", user.get('id'))
            continue

        public_key_object = cc.crypto2.load_pem_public_key(
            user['public_key'].encode('ascii'))
        encrypted_private_keys.append(
            {'user_id': user['id'],
             'encrypted_share_key': json.dumps(cc.crypto2.wrap_private_key(
                 private_key_pem=keypair.private_pem,
                 public_key_object=public_key_object))})

    # try to upload the wrapped keys
    variables = {"storage_type": storage_type,
                 "share_unique_id": share_id,
                 "public_share_key": keypair.public_pem.decode('ascii'),
                 "encrypted_share_keys": encrypted_private_keys}

    mutation = '''
       mutation InitShareKeys(
           $storage_type: String!,
           $share_unique_id: String!,
           $public_share_key: String!,
           $encrypted_share_keys: [EncryptedShareKeyInput!]!) {
                initShareKeys(storage_type: $storage_type,
                share_unique_id: $share_unique_id,
                public_share_key: $public_share_key,
                 encrypted_share_keys: $encrypted_share_keys) {
            id
          }
        }
    '''

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)
    return keypair


def remove_user_from_share_remote(share_id, storage_type, storage_id, config):
    """ removes the current user from the specified share in the admin console
    :param share_id: id of the share to remove the user from
    :param storage_type: the type of the storage the share is on
    :param storage_id: the id of the storage the share is on"""
    mutation = '''mutation RemoveFromShare($storage_type: String!,
    $storage_unique_id: String!, $share_unique_id: String!)
    { removeUserFromShare(storage_type: $storage_type, storage_unique_id:
    $storage_unique_id, share_unique_id:$share_unique_id)}'''

    if storage_type == 'onedrive':
        logger.info('## user not removed from share because onedrive')
        return

    variables = {"storage_type": storage_type,
                 "storage_unique_id": storage_id,
                 "share_unique_id": share_id}

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def adapt_users_of_share_remote(storage_type, share_id, users, share_name, config):
    """ modifies a specific share on the administrator console
     :param storage_type: the type of the storage
     :param share_id: the id of the share to be modified
     :param users: the value for the users having access to the share
     :param share_name the name of the share (updated or not)"""
    mutation = '''mutation UpdateShares($storage_type: String!, $unique_id: String!,
    $storage_unique_ids: [String!], $name: String) {
    updateShare(storage_type: $storage_type, unique_id: $unique_id,
    storage_unique_ids: $storage_unique_ids, name: $name)
    {id users_without_share_key {  id   public_key }}
    }'''

    # XXX: This is a hack
    # For oneDrive and owncloud the len of users is 1 when the user does not own
    # the share. In this case, the adaptation may not take place.
    # Otherwise it will remove the other users from the share.
    excluded_types = ['onedrive', 'owncloud']
    if storage_type in excluded_types and len(users) == 1:
        logger.debug('%s failed to modify share because it does not own the share.',
                     storage_type)
        return

    variables = {
        "storage_type": storage_type,
        "unique_id": share_id,
        "storage_unique_ids": users,
        "name": share_name
    }

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    assert 'error' not in response.json()
    raise_for_graphql_error(response)


def get_share_info(config):
    """
    Returns a tuple of two dicts based on the current entries in the server config
    the first dict is a mapping of admin console user id (email) to the public key
    the second dict is a mapping of (storage_type, unique_id) to the admin console
    user's email
    """
    # pylint: disable=redefined-outer-name

    public_keys = {}
    unique_id_mapping = {}
    share_key_pairs = {}

    for csp in server_config.get('csps', {}):
        for share in csp.get('shares', {}):
            for connected_csp in share.get('csps', {}):
                user_email = connected_csp['user']['email']
                user_public_key = connected_csp['user']['public_key']
                if user_public_key is not None:
                    public_keys[user_email] = user_public_key.encode()
                    unique_id_mapping[(csp['type'], connected_csp['unique_id'])] = user_email
            if share.get('share_key_for_current_user'):
                try:
                    enc_share_key = share.get('share_key_for_current_user',
                                              {}).get('encrypted_share_key')
                    if enc_share_key:
                        user_private_key = serialization.load_pem_private_key(
                            config.user_private_key, None, backend=default_backend())
                        share_private_key = cc.crypto2.unwrap_private_key(
                            wrapped_object=json.loads(enc_share_key),
                            private_key_object=user_private_key)
                        share_public_key = share['public_share_key'].encode('ascii')
                        subject_id = KEY_SUBJECT_SHARE.format(0, csp['type'], share['unique_id'])
                        keypair = cc.crypto2.KeyPair(private_pem=share_private_key,
                                                     public_pem=share_public_key)
                        share_key_pairs[subject_id] = keypair
                except cc.crypto2.KeyWrappingError:
                    logger.warning('Unable to unwrap key. '
                                   'Removing share with id "%s" from SP "%s".',
                                   share.get('id'), csp.get('unique_id'))
                    # trigger mutation remove user from share
                    remove_user_from_share_remote(share_id=share.get('id'),
                                                  storage_type=csp.get('type'),
                                                  storage_id=csp.get('unique_id'),
                                                  config=config)
    return public_keys, unique_id_mapping, share_key_pairs


def dump_config(config):
    """Dump the local config to a json object.

    This is used for testing purposes
    """
    # pylint: disable=redefined-outer-name

    return json.dumps({'machine_id': config.device_id,
                       'csps': config.csps.copy()})


def update_device_approval_request():
    """
    Updates device key approval requests from other devices. If another device is added
    by the user, it needs to be approved on another device in order to exchange keys
    and activate proper encryption. Only processing one request at a time
    """
    for approval_request in server_config['approval_requests']:
        device_id_to_approve = approval_request['device_id']
        public_key_to_approve = approval_request['public_device_key']

        # calculating fingerprint of public key
        fingerprint = cc.crypto.calculate_sha256(public_key_to_approve.encode(
            'ascii')).decode('ascii')

        # calling the gui so the user can approve the device
        cc.ipc_gui.showApproveDeviceDialog(device_id=device_id_to_approve,
                                           fingerprint=fingerprint)
        # for now only processing one at a time
        return


def confirm_device_approval(device_id, public_key_fingerprint, config):
    """Trigger the confirmation of the another device key by the gui.

    :param device_id: the id of the device to approve
    :param public_key_fingerprint: the SHA-256 fingerprint of the device to approve
    """
    # pylint: disable=redefined-outer-name

    # finding right approval request
    approval_request = find_approval_request(device_id, public_key_fingerprint)
    if approval_request is None:
        return

    # getting public key of the device id
    public_device_key_pem = approval_request['public_device_key'].encode('ascii')
    device_id = approval_request['device_id']

    # wrapping user private key with public device key to approve. this makes the
    # private user key accessible for the other device
    device_to_approve_public_key = cc.crypto2.load_pem_public_key(public_device_key_pem)

    wrapped_user_private_key = cc.crypto2.wrap_private_key(
        private_key_pem=config.user_private_key,
        public_key_object=device_to_approve_public_key)

    # calling AC to perform actual operation
    approve_device(device_id=device_id, public_device_key=public_device_key_pem,
                   encrypted_user_key=wrapped_user_private_key, config=config)

    # displaying notification that has been approved
    cc.ipc_gui.displayNotification('Device Approved', 'Your other device has been approved')


def confirm_device_declination(device_id, public_key_fingerprint, config):
    """Trigger the declination of another device

    :param device_id: the id of the device to approve
    :param public_key_fingerprint: the SHA-256 fingerprint of the device to decline
    """
    # finding right approval request
    approval_request = find_approval_request(device_id, public_key_fingerprint)
    if approval_request is None:
        return

    # getting public key of the device id
    public_device_key_pem = approval_request['public_device_key'].encode('ascii')
    device_id = approval_request['device_id']

    # calling AC mutation
    decline_device(device_id=device_id, public_device_key=public_device_key_pem, config=config)


def find_approval_request(device_id, public_key_fingerprint):
    """Find the approval request matching the given criteria.

    :param device_id: the device idea of the approval request
    :param public_key_fingerprint: the fingerprint of the public key of the approval
    request to find
    :return: one approval request matching the parameter or None if not found
    """
    for approval_request in server_config['approval_requests']:
        if approval_request['device_id'] == device_id:
            public_key_request = approval_request['public_device_key'].encode('ascii')
            public_key_request_hash = cc.crypto.calculate_sha256(
                public_key_request).decode('ascii')
            if public_key_request_hash == public_key_fingerprint:
                return approval_request
    return None


def approve_device(device_id, public_device_key, encrypted_user_key, config):
    """
    Approves another device by providing the user private key to the other device by
    encrypting it with the other device's device key
    :param device_id: the id of the device to approve
    :param public_device_key: the public key of the device to approve as submitted in
    the approval request
    :param encrypted_user_key: the user private key protected with the approved devices
    public key received in the approval request and as passed in this call
    """
    mutation = '''mutation ApproveDevice($device_id: String!, $public_device_key:
               String!, $encrypted_user_key: String!) {
               approveDevice(device_id: $device_id,
               public_device_key: $public_device_key,
               encrypted_user_key: $encrypted_user_key){device_id}}'''

    variables = {'device_id': device_id,
                 'public_device_key': public_device_key.decode('ascii'),
                 'encrypted_user_key': json.dumps(encrypted_user_key)}

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def decline_device(device_id, public_device_key, config):
    """
    Declines a device approval request
    :param device_id: the id of the device to approve
    :param public_device_key: the public key of the device to approve as submitted in
    the approval request
    """
    mutation = '''mutation DeclineDevice($device_id: String!, $public_device_key:
    String!) {declineDevice(device_id: $device_id, public_device_key:
    $public_device_key)}'''

    variables = {'device_id': device_id,
                 'public_device_key': public_device_key.decode('ascii')}

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def request_device_approval(device_id, public_device_key, config):
    """Request the approval of this device (the device running on) from another device.

    Requests the approval of this device (the device running on) from another device in order to
    receive the proper encryption keys

    :param device_id: the device ID of this device
    :param public_device_key: the public key of this device
    """
    logger.debug('request device approval for : %s', public_device_key)

    mutation = '''mutation requestDeviceApproval($public_device_key: String!,
    $device_id: String!)
    {
    requestDeviceApproval(public_device_key: $public_device_key, device_id: $device_id)
    { device_id }}'''

    variables = {'public_device_key': public_device_key.decode('ascii'),
                 'device_id': device_id}

    response = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def check_for_device_approval(device_id, config):
    """Check if the device approval requested by this device has already been approved.

    :param device_id: the id of this deviec
    :return: true if the request has been approved, false else
    """
    query = '''{
                 currentUser {
                  encrypted_user_keys {
                    device_id
                  }
                 }
               }
               '''

    resp = get_session(config).post(
        GRAPHQL_URL,
        json={'query': query}
    )

    raise_for_graphql_error(resp)

    # if any key entry matching device id is there -> approved
    for key_entry in resp['encrypted_user_keys']:
        if key_entry['device_id'] == device_id:
            return True

    return False


def init_admin_console_user_keys(device_id, public_user_key, encrypted_private_user_key,
                                 public_device_key, config):
    """Initialize the user keys if necessary and encryption is enabled on the admin console.

    Initializes the user keys if encryption is enabled on the admin console and no keys
    have been set for the user yet. This can only be executed one time for each user
    account and sets the user key pair as well as device keys for this device
    :param device_id: the device id of this device
    :param public_user_key: the public key of the freshly and carefully created user key
    pair - the corresponding private key needs to be stored on the client!!
    :param encrypted_private_user_key: the private key of the user key pair encrypted with
    the device public key.
    :param public_device_key: the public device key freshly and carefully created - the
    private key needs to be stored on this device

    If you are confused about any of this - call Christoph!! I am here to help and please
    don't assume and mess things up - thanks :-)
    """
    mutation = '''mutation initUserKey($public_user_key: String!, $encrypted_user_key:
                    String!, $public_device_key: String!, $device_id: String!) {
                    initUserKey(public_user_key: $public_user_key, public_device_key:
                    $public_device_key,device_id: $device_id, encrypted_user_key:
                    $encrypted_user_key) {public_device_key }}'''

    variables = {'public_user_key': public_user_key.decode('ascii'),
                 'encrypted_user_key': json.dumps(encrypted_private_user_key),
                 'public_device_key': public_device_key.decode('ascii'),
                 'device_id': device_id}

    response = get_session(config=config).post(
        GRAPHQL_URL,
        json={
            'query': mutation,
            'variables': variables
        })

    raise_for_graphql_error(response)


def get_public_key(email, config):
    """Fetch the public key for a given user email address.

    :returns the public key of the user if it was found in the admin console or None if
    this was an unknown user
    """
    query = 'query($email: String!) { publicKeyForUser(email: $email) }'
    resp = get_session(config).post(
        GRAPHQL_URL,
        json={
            'query': query,
            'variables': {
                'email': email
            }
        }
    )
    raise_for_graphql_error(resp)
    return resp.json()['data']['publicKeyForUser']


def check_login(config):
    """Check if the current users login is valid.

    This is done by checking if the auth token is present and can be used to communicate with the
    configured admin console
    :return: true if the user login is valid and working with the configured admin console, false
    else
    """
    logger.debug('Checking user login against admin console.')

    # checking if token is there
    if get_token(config=config) is None:
        return False

    # query only fetching user id
    query = '''{
                 currentUser {
                   id
                 }
                }'''

    try:
        resp = get_session(config).post(
            GRAPHQL_URL,
            json={'query': query}
        )

        raise_for_graphql_error(resp)

        # if we get a valid id back -> the user must be logged in
        response = resp.json()['data']
        if response['currentUser']['id'] is not None:
            return True

        # default to false
        return False
    # catching all exceptions related to request or decoding the result (e.g valid host and
    # strange response)
    except requests.HTTPError as http_exc:
        # Check if the AC responds that the user is not logged in
        logger.debug("Got HTTP error.")
        error_code = http_exc.response.status_code
        if error_code == 401:
            logger.debug("Logging the user out.")
            return False
        else:
            logger.debug("Got error code: %s. But we are allowing it.", error_code)
            return True
    except (requests.RequestException, json.JSONDecodeError) as login_error:
        # otherwise we allow the user to stay logged in
        logger.debug("Couldn't check login authentication. %s", login_error)
        return True
