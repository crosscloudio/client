"""A collection of functions which modify on a config object."""
import base64
import binascii
import copy
import json
import logging
import os
import threading

import atomicwrites
import keyring
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

import jars
from cc import configuration, crypto2, synchronization

logger = logging.getLogger(__name__)

# pylint: disable=invalid-name
config_file_lock = threading.RLock()


# pylint: enable=invalid-name


class DuplicatedAccountError(Exception):
    """
    Thrown if same account was added a second time.
    """

    def __init__(self, unique_id, acc_type):
        super().__init__()
        self.unique_id = unique_id
        self.acc_type = acc_type


class ConfigurationError(Exception):
    """Thrown if there is something wrong with the configuration file."""


class ConfigurationStorageNotFound(ConfigurationError):
    """Thrown if something should be written to a non-existing storage."""


class ConfigurationIntegrityError(ConfigurationError):
    """Thrown if the integrity of the stored configuration in combination with the authenticity.

    tag in the keychain could not be verified.
    """


def get_configuration_tag(config):
    """
    :returns the current configuration tag in its original binary form.
    """
    b64tag = keyring.get_password(config.APP_NAME,
                                  config.KEYCHAIN_CONFIGURATION_TAG_NAME)
    if b64tag:
        return base64.b64decode(b64tag)
    return None


def read_encrypted_configuration(config, file, key, tag):
    """Try to decrypt the given file using the given key and return a CrossCloud configuration.

    https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.modes.GCM

    :param file: the location of the file containing the CrossCloud cryptographic container.
    :param key: the configuration key that was used to encrypt the configuration.
    :param tag: the authenticity tag used as part of GCM to ensure integrity.
    :raise `ConfigurationError`
    :raise `ConfigurationIntegrityError`
    :return:
    """
    try:
        # Verify that the encrypted configuration has a proper header.
        with open(file, 'rb') as f_in:
            header = crypto2.read_header(f_in)
            header_length = len(json.dumps(header))
            f_in.seek(0)
            raw_header = f_in.read(header_length + len(crypto2.MAGIC_NUMBER) + 4)
            logger.debug("Found configuration header.")
            cipher_text = f_in.read()

        # Setup `cryptography` using the stored IV.
        logger.debug("Using stored IV '%s' from Header.", header['iv'])
        initialization_vector = base64.b64decode(header['iv'])
        cipher = Cipher(algorithms.AES(key),
                        modes.GCM(initialization_vector=initialization_vector,
                                  tag=tag,
                                  min_tag_length=config.KEYCHAIN_CONFIGURATION_TAG_SIZE),
                        backend=default_backend())

        # Decrypt configuration, re-add the header for proper validation & finalize.
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(raw_header)
        plaintext = decryptor.update(cipher_text)

        try:
            decryptor.finalize()
            logger.info("Integrity of configuration file has been established!")
        except InvalidTag as err:
            from cc.ipc_gui import displayNotification
            displayNotification("Configuration Integrity Warning",
                                " ".join(["The authenticity of the configuration file",
                                          "could not be verified!"]))
            logger.warning("Integrity of configuration file could not be verified! %s", err)

        # If the configuration is invalid json this will throw a ValueError
        config = json.loads(plaintext.decode('utf-8'))
        assert 'metadata' in config.keys() and 'general' in config.keys()
        return config

    except crypto2.HeaderError:
        raise ConfigurationError("The configuration header appears to be corrupted!")
    except crypto2.EncryptionException:
        raise ConfigurationError("Unable to decrypted the stored configuration file!")
    except ValueError:
        raise ConfigurationError("The configuration file appears to be corrupted!")
    except AssertionError:
        raise ConfigurationError("The configuration file does not contain all required items!")


def write_encrypted_configuration(config, configuration_dict, key):
    """Encrypt a given JSON-style configuration object using the given key.

    :param config: the actual config object
    :param configuration_dict: the JSON-style object to be encrypted
    :param key: the key to be used (see `KEYCHAIN_CONFIGURATION_KEY_SIZE`).
    :raise `ConfigurationError` if the given configuration is invalid.
    :return: a tuple consisting of the used key, encrypted buffer and the authenticity tag.
    """

    try:
        # Setup `cryptography` and create a new IV to be used for encryption.
        initialization_vector = os.urandom(config.KEYCHAIN_CONFIGURATION_KEY_IV_SIZE)
        buffer = crypto2.create_header(initialization_vector, {},
                                       algorithm="AES256-GCM",
                                       version="0.1")
        cipher = Cipher(algorithms.AES(key),
                        modes.GCM(initialization_vector=initialization_vector,
                                  tag=None,
                                  min_tag_length=config.KEYCHAIN_CONFIGURATION_TAG_SIZE),
                        backend=default_backend())
        encryptor = cipher.encryptor()

        # We attach the header created by `crypto2.create_header` as additional data that
        # will be also verified in the decryption stage.
        encryptor.authenticate_additional_data(b''.join(buffer))

        # Serialize the given JSON object and pass it to the `encryptor`.
        payload = json.dumps(configuration_dict).encode('utf-8')
        buffer.append(encryptor.update(payload))
        buffer.append(encryptor.finalize())
        return key, buffer, encryptor.tag
    except ValueError:
        raise ConfigurationError("Unable to write encrypted configuration to storage!")


def set_configuration_tag(config, tag):
    """Helper function to set store a new configuration tag inside the keychain."""

    if len(tag) < config.KEYCHAIN_CONFIGURATION_TAG_SIZE:
        raise ConfigurationIntegrityError("The provided TAG's size is too small!")

    b64tag = base64.b64encode(tag).decode('ascii')
    keyring.set_password(config.APP_NAME,
                         config.KEYCHAIN_CONFIGURATION_TAG_NAME, b64tag)
    return b64tag


def get_configuration_key(config, auto_create=False):
    """Helper function to retrieve and/or create the current configuration key. The key is stored
    in BASE64 format but always should be returned in its original binary form.

    :param auto_create: whether to create and store a new configuration key if not found
                        (default False).
    :raises keyring.errors.PasswordSetError if the new key could not be set.
    :return: the original binary form of the key or None if no key was found
    """
    logger.info("Looking for '%s' in '%s' keychain.",
                config.KEYCHAIN_CONFIGURATION_KEY_NAME, config.APP_NAME)

    key = keyring.get_password(config.APP_NAME,
                               config.KEYCHAIN_CONFIGURATION_KEY_NAME)

    # We were not able to find the key but want to create one (happens e.g. during initial setup.)
    if key is None and auto_create:
        logger.info("'%s' not found!", config.KEYCHAIN_CONFIGURATION_KEY_NAME)
        logger.info("Attempting to create a new configuration key!")
        created_key = set_configuration_key(config)
        logger.info("Successfully created new configuration key!")
        return created_key
    # We found a key, everything is fine. Decode it and return it.
    elif key:
        logger.info("Using key from '%s' keychain item.",
                    config.KEYCHAIN_CONFIGURATION_KEY_NAME)
        return base64.b64decode(key)
    else:
        logger.warning("The configuration key was not found in the keychain!")
        return None


def set_configuration_key(config):
    """Helper function to create and store configuration key."""
    new_key = os.urandom(config.KEYCHAIN_CONFIGURATION_KEY_SIZE)
    logger.info("Created a new %3d-bit key.", config.KEYCHAIN_CONFIGURATION_KEY_SIZE * 8)

    new_key_b64 = base64.b64encode(new_key).decode('ascii')
    keyring.set_password(config.APP_NAME,
                         config.KEYCHAIN_CONFIGURATION_KEY_NAME, new_key_b64)

    logger.info("Set new '%s' in '%s'!", config.KEYCHAIN_CONFIGURATION_KEY_NAME, config.APP_NAME)
    return new_key


def write_config(config, file=None, auto_create_configuration_key=True):
    """Write the config to the file path. takes the sync_root and csp values from this
     module

    TODO: rewrite to use to_json of the config.
    """

    if file is None:
        file = config.config_file

    with config_file_lock:
        logger.debug("Acquiring configuration file lock.")

        config_dict = dict({})

        # Set metadata information, will be checked
        config_dict['metadata'] = {'version': config.CONFIGURATION_SCHEMA_VERSION}

        # writing general configuration
        config_dict['general'] = {'sync_root_directory': config.sync_root,
                                  'device_id': config.device_id,
                                  'last_login': config.last_login,
                                  'auth_token': config.auth_token}
        config_dict['admin_console_state'] = \
            {'policies': config.policies,
             'storage_providers': config.admin_console_csps,
             # convert to a list, since sets cannot be stored in json
             'shares_with_external_users': list(config.shares_with_external_users)}

        # writing encryption config retrieved from server
        config_dict['encryption'] = {
            'encryption_enabled': config.encryption_enabled,
            'encrypt_external_shares': config.encrypt_external_shares,
            'encrypt_public_shares': config.encrypt_public_shares,
            'encrypt_storage_provider_types': config.encryption_csp_settings,
            'user_private_key': config.user_private_key.decode('ascii'),
            'user_public_key': config.user_public_key.decode('ascii'),
            'device_public_key': config.device_public_key.decode('ascii'),
            'device_private_key': config.device_private_key.decode('ascii')}

        for csp in config.csps:
            csp.setdefault('selected_sync_directories', [{'path': [], 'children': True}])
            csp = copy.deepcopy(csp)
            csp['selected_sync_directories'] = csp['selected_sync_directories']
            config_dict[csp['id']] = csp

        logger.debug("Trying to write configuration to %s", file)

        with atomicwrites.atomic_write(file, mode='wb', overwrite=True) as f_out:
            key = get_configuration_key(config, auto_create=auto_create_configuration_key)
            if key:
                _, encrypted_config, tag = write_encrypted_configuration(config, config_dict, key)
                f_out.write(b''.join(encrypted_config))
                assert set_configuration_tag(config, tag)
                logger.debug("Successfully wrote encrypted configuration to %s", file)
            else:
                raise crypto2.NoKeyError("No configuration key found in the keychain!")


def read_config(config, file=None):
    """ reads the config from the file path. writes the sync_root and csp values to this
     module
     :param file: the file containing the configuration to be read. Defaults to default
     configuration file
    """
    # pylint: disable=too-many-statements,too-many-branches
    # to prevent cyclic imports

    def ensure_configuration_key_setup(encrypted_configuration_file):
        """ Helper function that creates the or loads existing key and tag material to be able
            to handle encrypted configuration files.
            :param encrypted_configuration_file the full path to the encrypted CC configuration.
            :returns tuple containing whether the setup appears to be new and the key/tag material

            >>> ensure_configuration_key_setup("does.not.exist")
            (True, None, None)

            >>> ensure_configuration_key_setup("~/.config/crosscloud/config.json")
            (False, b'configuration_key', b'current_configuration_tag')
        """

        # If no configuration file is found and no key and no tag are present in the keychain
        # 1. create a configuration key and store it in the keychain.
        # 2. proceed with a bare minimum/default configuration.
        if not os.path.exists(encrypted_configuration_file):
            logger.info("No configuration file found under '%s'.", encrypted_configuration_file)
            # Previous tags will be overwritten and are not handled.

            # If the configuration file encryption key is not found create it.
            if not get_configuration_key(config):
                logger.info("'%s' not found in keychain. Creating it!",
                            config.KEYCHAIN_CONFIGURATION_KEY_NAME)
                assert get_configuration_key(config, auto_create=True)

            # This is a new setup, return no key or tag information.
            return True, None, None
        else:
            logger.info("Using configuration file '%s'.", encrypted_configuration_file)
            config_key = get_configuration_key(config, auto_create=False)
            current_tag = get_configuration_tag(config)

            # We should have a key by know, if we don't throw an error.
            if not config_key:
                raise crypto2.NoKeyError("No configuration key found in the keychain!")

            if not current_tag:
                raise ConfigurationError(
                    "No configuration tag found for current configuration file!")

            # This is not a new setup, return key and current tag
            return False, config_key, current_tag

    # If no file was specified we assume we want to write to the default configuration file.
    if file is None:
        file = config.config_file

    with config_file_lock:
        # TODO: XXX: Collect all stored public keys from the `key_dir`.
        # public_keys = _get_cached_public_keys_from(key_dir)

        # We start with an empty configuration. If no configuration file is found this will be
        # populate with a set of default values (see below). Otherwise we will pre-populate it with
        # the values stored in the encrypted configuration file.
        config_dict = {}

        # If this is a new_setup key and tag will contain the previous auth tag and encryption key.
        new_setup, key, tag = ensure_configuration_key_setup(config.config_file)
        if not new_setup:
            config_dict = read_encrypted_configuration(config, file, key, tag)
            logger.info("Loaded existing configuration from '%s'.", file)

            # Ensure that the configuration schema matches the expected one.
            format_version = config_dict['metadata'].get('version', None)
            if format_version != config.CONFIGURATION_SCHEMA_VERSION:
                logger.warning("Configuration file schema '%s' differs from expected version '%s'",
                               format_version, config.CONFIGURATION_SCHEMA_VERSION)
        else:
            logger.info("This appears to be a new setup. Starting with a fresh configuration!")

        # At this point we have a pre-filled configuration file. Everything below should only
        # set default values if necessary and set the globals accordingly.
        if 'general' in config_dict:
            config.sync_root = config_dict['general'].get('sync_root_directory', config.sync_root)
            config.device_id = config_dict['general'].get('device_id', config.device_id)
            config.last_login = config_dict['general'].get('last_login', None)
            config.auth_token = config_dict['general'].get('auth_token', None)

        if 'admin_console_state' in config_dict:
            policies = config_dict['admin_console_state'].get('policies', [])
            config.admin_console_csps = \
                config_dict['admin_console_state'].get('storage_providers', [])
            if 'shares_with_external_users' in config_dict['admin_console_state']:
                config.shares_with_external_users = \
                    {(storage_type, share_id)
                     for storage_type, share_id in
                     config_dict['admin_console_state']['shares_with_external_users']}
            config.policies = policies

        if 'encryption' in config_dict:
            config.encryption_enabled = \
                config_dict['encryption'].get('encryption_enabled', False)

            config.encrypt_external_shares = \
                config_dict['encryption'].get('encrypt_external_shares', False)

            config.encrypt_public_shares = \
                config_dict['encryption'].get('encrypt_public_shares', False)

            config.encryption_csp_settings = \
                config_dict['encryption'].get('encrypt_storage_provider_types', {})

            config.user_private_key = \
                config_dict['encryption'].get('user_private_key', b'""').encode('ascii')

            config.user_public_key = \
                config_dict['encryption'].get('user_public_key', b'""').encode('ascii')

            config.device_public_key = \
                config_dict['encryption'].get('device_public_key', b'""').encode('ascii')

            config.device_private_key = \
                config_dict['encryption'].get('device_private_key', b'""').encode('ascii')

        for section in config_dict.keys():
            if section in ['metadata', 'general', 'admin_console_state', 'encryption']:
                continue
            csp = config_dict[section]
            csp['id'] = section
            if 'selected_sync_directories' in csp:
                csp['selected_sync_directories'] = csp['selected_sync_directories']
            else:
                # if there is not selective sync dir define root as it
                csp['selected_sync_directories'] = [{'path': [], 'children': True}]
            config.csps.append(csp)
        return config


def determine_csp_display_name(config, sp_type, display_name):
    """Determine the default display name for a csp with the given id.

    It will count all accounts with the same type and add one to that.
    """
    name_list = [sp['display_name'] for sp in config.csps if sp['type'] == sp_type]
    # First storage should not have a number, after that start from 2
    count = 1
    name = display_name
    found = False
    while not found:
        if count > 1:
            new_name = "{} {}".format(name, count)
        else:
            new_name = name
        file_exists = os.path.isdir(os.path.join(config.sync_root, new_name))
        if new_name in name_list or file_exists:
            count = count + 1
        else:
            found = True
    return new_name


def get_storage(config, storage_id):
    """gets the storage corresponding to the storage_id"""
    # searching for csp
    item = None
    for storage in config.csps:
        if storage['id'] == storage_id:
            item = storage

    # returning result
    return item


def raise_for_duplicate(config, acc_type, unique_id):
    """
    :raises: :class: DuplicateAccount if account already exists.
    """
    for csp in config.csps:
        if csp['type'] == acc_type and csp['unique_id'] == unique_id:
            raise DuplicatedAccountError(unique_id=unique_id, acc_type=acc_type)


# pylint: disable=too-many-arguments
def add_csp(config, auth_data):
    """Initialize csp, add it to the list and writes the config"""
    os.makedirs(auth_data['sp_dir'], exist_ok=True)
    local_unique_id = os.stat(auth_data['sp_dir']).st_ino

    storage = {'id': auth_data['new_storage_id'], 'type': auth_data['storage'].storage_name,
               'unique_id': auth_data['identifier'], 'selected_sync_directories': {},
               'local_unique_id': local_unique_id, 'storage_user_name': '-',
               'display_name': auth_data['display_name']}

    raise_for_duplicate(config, auth_data['storage'].storage_name, auth_data['identifier'])

    # appending sp info to module variable
    config.csps.append(storage)

    config.store_credentials_in_config(auth_data['new_storage_id'], auth_data['credentials'],
                                       False)

    storage_inst = synchronization.models.instantiate_storage(
        auth_data['storage'], storage_id=auth_data['new_storage_id'], config=config)

    storage['storage_user_name'] = storage_inst.storage_user_name

    # writing config
    write_config(config)
    logger.info("Added storage provider '%s' to configuration.", auth_data['new_storage_id'])


def delete_credentials_from_config(config, name):
    """ deletes an item from the config file
    :param name: the name of the item to be deleted
    """
    with config_file_lock:
        storage = get_storage(config, name)
        if storage and storage.get('credentials', False):
            del storage['credentials']
            write_config(config)

    if not storage:
        raise ConfigurationStorageNotFound("Storage {} not found in configuration!".format(name))


def get_credentials_from_config(config, name, binary=False):
    """Retrieves a stored cryptographic item from the system keychain

    this retrieves a previously stored cryptographic key from the system keychain

    :param binary: true if the read data is binary, false else
    :param name: the name under which the key has been stored
    :raises `ConfigurationError` if the given storage does not exist.
    :return: the item ore None if not found
    """
    read_item = None

    with config_file_lock:
        storage = get_storage(config, name)
        if storage and storage.get('credentials', False):
            read_item = get_storage(config, name)['credentials']

    if not storage:
        raise ConfigurationStorageNotFound(
            "Storage configuration for '{}' not found!".format(name))

    if read_item and binary:
        try:
            return base64.b64decode(read_item)
        except binascii.Error:
            logger.debug("could not decode keychain content")
            return None
    elif read_item:
        return read_item
    else:
        return None


def store_credentials_in_config(config, name, item, binary=False):
    """ stores a cryptographic item in the config file base64 encoded

    :param name: the name to store the key under
    :param item: the item to be stored
    :param binary: true if the data is binary, false else
    """

    with config_file_lock:
        if binary:
            value_to_store = base64.b64encode(item).decode('ASCII')
        else:
            value_to_store = item

        storage = get_storage(config, name)
        if storage:
            storage['credentials'] = value_to_store
            write_config(config)

    if not storage:
        raise ConfigurationStorageNotFound(
            "Storage configuration for '{}' not found!".format(name))


def init_config_dirs(config):
    """Create required directories."""
    for dir_name in ['config_dir', 'cache_dir', 'log_dir']:
        dir_path = config.item(dir_name)
        logger.info('creating %s at %s', dir_name, dir_path)
        os.makedirs(dir_path.value, exist_ok=True)


def set_constants(config):
    """Append constants to the base config."""
    for name in dir(configuration.constants):
        if name.upper() == name:
            value = getattr(configuration.constants, name)
            setattr(config, name, value)
    return config


def set_methods(config):
    """Append methods to the base config."""
    for name in dir(configuration.helpers):
        value = getattr(configuration.helpers, name)
        setattr(config, name, value)
    return config


def set_csp_selected_sync_dirs(config, csp_id, filter_config):
    """Modify the config to contain the selected_sync_directories"""
    for csp in config.csps:
        if csp_id == csp['id']:
            csp['selected_sync_directories'] = filter_config
            break
    write_config(config)


def update_filter_in_config(config, *args, **kwargs):
    """Update filter in the configuration for a specific storage_id
    The configuration is also written to the config file
    """
    filter_tree = args[0]
    # find root node
    root_node = None
    for root_node in filter_tree.iter_up:
        pass
    csp_id = kwargs['csp_id']
    filter_config = list(jars.utils.tree_to_config(root_node))
    set_csp_selected_sync_dirs(config, csp_id, filter_config)


def rename_csp(config, storage_id, new_name):
    """Renaming item in csps and write the config"""
    # searching for csp
    item = get_storage(config, storage_id)

    # removing item from csps
    try:
        assert item is not None
        item['display_name'] = new_name
    except AssertionError:
        logger.exception('SP account not found in config.')

    # writing config
    write_config(config)
    logger.info("Renamed storage provider '%s' to '%s'.", storage_id, new_name)


def set_shares_with_external_users(config, shares_with_external_users_arg):
    """Write the shares_with_external_users variable if changed."""
    config.shares_with_external_users = shares_with_external_users_arg
    write_config(config)


def get_private_key_pem_by_subject(config, subject):
    """ Returns the :class: cc.crypto2.KeyPair for a given subject
    :raises: :class:KeyError if the element is not found"""
    category, _, _ = subject.split(':')
    if category == 'share':
        return config.share_key_pairs[subject].private_pem
    elif category == 'user':
        # TODO: check if the subject id is the correct one
        return config.user_private_key
    else:
        raise KeyError('Unknown category')


def get_public_key_pem_by_subject(config, subject):
    """Return a public key pem by a subject."""
    category, _, _ = subject.split(':')
    if category == 'share':
        return config.share_key_pairs[subject].public_pem
    elif category == 'user':
        # TODO: check if the subject id is the correct one
        return config.user_public_key
    elif category == 'master':
        if subject == config.master_key_subject:
            return config.master_key_pem
        else:
            raise KeyError('Wrong master key requested')
    else:
        raise KeyError('Unknown category')


def get_storage_cache_dir(config, storage_id):
    """Create the path to the storage cache file"""
    storage_cache_dir = os.path.join(config.cache_dir, storage_id)
    return storage_cache_dir


def build_config(module):
    """Construct a new config object from a module of defintions."""
    config = configuration.models.Config()
    for entry_name in dir(module):
        # exclude dunder methods and models which needs to be imported.
        if entry_name.startswith('__') or entry_name is 'models':
            continue

        # instatiate the class and set it up on the new config object.
        klass = getattr(module, entry_name)
        try:
            if issubclass(klass, configuration.models.ConfigItem):
                setattr(config, klass.key,
                        klass(name=klass.key, value=copy.deepcopy(klass.default)))
        except TypeError:
            logger.info('unable to add entry %s to config', entry_name)
    return config


def get_storage_by_displayname(config, display_name):
    """Return a storage based on its dispaynam."""
    item = None
    for storage in config.csps:
        if storage['display_name'] == display_name:
            item = storage
    # returning result
    return item


def get_storage_class(storage_name):
    """Return the jar class which matches the storage_name.

    TODO: This function should be moved to jars
    TODO: registered_storages should be a dict with storage_name as key
    """
    storages = [c for c in jars.registered_storages
                if c.storage_name == storage_name]

    if not storages:
        storage = None
    else:
        storage = storages[0]

    return storage


def update_inodes(config):
    """Point all storages local_unique_ids to the new sync_dirs."""
    path = config.sync_root
    for storage in config.csps:
        sp_dir = os.path.join(path, storage['display_name'])
        storage['local_unique_id'] = os.stat(sp_dir).st_ino
