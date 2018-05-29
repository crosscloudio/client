""" Test for the configuration helpers.
"""
import base64
import json
import os
import tempfile
import uuid

import keyring
import mock
import pytest
from bushn import bushn
from mock import call

import cc
import jars
from cc import settings_sync
from cc.configuration import helpers


def test_read_configuration_with_invalid_header(config):
    """Decrypt a file with no/invalid header should fail."""
    _, file_name = tempfile.mkstemp(text="NOMOREMAGIC")
    with pytest.raises(helpers.ConfigurationError):
        helpers.read_encrypted_configuration(config, file_name, None, None)


def test_read_non_existing_file(config):
    """Try to decrypt a non-existing file should throw an exception. """
    with pytest.raises(FileNotFoundError):
        helpers.read_encrypted_configuration(config, "does.not.exist", None, None)


@mock.patch("keyring.get_password", return_value=base64.b64encode(b'stored_tag'))
def test_get_configuration_tag(mock_keyring_get_password, config):
    """Test fetching tags from the keychain. """

    tag = helpers.get_configuration_tag(config)
    assert tag == b'stored_tag'

    mock_keyring_get_password.return_value = None
    tag = helpers.get_configuration_tag(config)
    assert tag is None


@mock.patch("keyring.get_password", return_value=base64.b64encode(b'stored_tag' * 3))
@mock.patch("keyring.set_password", return_value=None)
def test_set_configuration_tag(mock_keyring_set_password, mock_keyring_get_password, config):
    """Test fetching tags from the keychain. """

    # Setting a Tag with less than the minimal requires length should not be possible.
    with pytest.raises(helpers.ConfigurationIntegrityError):
        helpers.set_configuration_tag(config, os.urandom(
            config.KEYCHAIN_CONFIGURATION_TAG_SIZE - 1))
        assert not mock_keyring_set_password.called

    # Ensure that a tag of proper length can be stored and retrieved from the keychain.
    tag = helpers.set_configuration_tag(config, b'stored_tag' * 3)
    assert mock_keyring_set_password.called

    tag_from_keychain = helpers.get_configuration_tag(config)
    assert mock_keyring_get_password.called
    assert base64.b64decode(tag) == tag_from_keychain


@mock.patch("keyring.set_password", return_value=None)
def test_configuration_tag_write_invalid(mock_keyring_set_password, config):
    """ Setting a Tag with less than the minimal requires length should not be possible. """
    with pytest.raises(helpers.ConfigurationIntegrityError):
        helpers.set_configuration_tag(config,
                                      os.urandom(config.KEYCHAIN_CONFIGURATION_TAG_SIZE - 1))
        # It also should not store any items in the keychain.
        assert not mock_keyring_set_password.called


@mock.patch("keyring.get_password", return_value=base64.b64encode(b'stored_key'))
@mock.patch("cc.configuration.helpers.set_configuration_key", return_value=b'new_key')
def test_get_configuration_key(mock_set_configuration_key, mock_keyring_get_password, config):
    """ Test whether calling get_configuration_key gets and sets a configuration key properly. """

    # A previous key is stored within the keychain.
    key = helpers.get_configuration_key(config, auto_create=False)
    assert mock_keyring_get_password.called_with(service=config.APP_NAME,
                                                 name=config.KEYCHAIN_CONFIGURATION_KEY_NAME)
    assert not mock_set_configuration_key.called
    assert key == b'stored_key'

    # No previous key found.
    mock_keyring_get_password.return_value = None
    key = helpers.get_configuration_key(config, auto_create=False)
    assert mock_keyring_get_password.called
    assert not mock_set_configuration_key.called
    assert key is None

    # No previous key found _and_ auto_create=True
    mock_keyring_get_password.return_value = None
    key = helpers.get_configuration_key(config, auto_create=True)
    assert mock_keyring_get_password.called
    assert mock_set_configuration_key.called_with(service=config.APP_NAME,
                                                  name=config.KEYCHAIN_CONFIGURATION_KEY_NAME,
                                                  password=base64.b64encode(key))
    assert key == b'new_key'


@mock.patch("os.urandom", return_value=b'/\x9c6b\xb9')
@mock.patch("keyring.set_password", return_value=b'Mu31aLY=')
def test_set_configuration_key(mock_keyring_set_password, mock_os_urandom, config):
    """ Tests whether a newly created configuration key is """
    key = helpers.set_configuration_key(config)
    assert mock_keyring_set_password.called_with(service=config.APP_NAME,
                                                 name=config.KEYCHAIN_CONFIGURATION_KEY_NAME,
                                                 password=base64.b64encode(key))
    assert mock_os_urandom.called_with(config.KEYCHAIN_CONFIGURATION_TAG_SIZE)
    assert key == b'/\x9c6b\xb9'


@mock.patch("keyring.set_password", return_value=None)
def test_ensure_configuration_key_length(mock_keyring_set_password, config):
    """ Ensure that the generated configuration key has the necessary size. """
    key = helpers.set_configuration_key(config)
    assert len(key) == config.KEYCHAIN_CONFIGURATION_KEY_SIZE
    assert mock_keyring_set_password.called_with(service=config.APP_NAME,
                                                 name=config.KEYCHAIN_CONFIGURATION_KEY_NAME,
                                                 password=base64.b64encode(key))


@pytest.mark.usefixtures("in_memory_keyring")
def test_read_write_policies(config):
    """ Tests the read and write operations for policies in the config file """
    policy = {'criteria': 'cad', 'createdAt': '2016-09-13T11:27:37.534Z', 'enabled': True,
              '_id': '57d7e2a92107cf1e0375f1d0', 'name': 'CAD files', '__v': 0,
              'type': 'fileextension', 'updatedAt': '2016-09-13T11:27:37.534Z'}

    config.policies = []
    config.policies.append(policy)
    helpers.write_config(config)
    config.policies = []
    config = helpers.read_config(config)
    assert config.policies[0] == policy


@pytest.mark.usefixtures("in_memory_keyring")
def test_write_read_csp(config):
    """ tests if the config is read and safed correctly"""
    testcsp = {'id': 'db1',
               'type': 'test',
               'display_name': 'test_1',
               'selected_sync_directories': [['heelo', 'world'], ['foo'], ['bar']]}

    config.csps.append(testcsp.copy())
    helpers.write_config(config)
    config.csps = []
    config = helpers.read_config(config)
    assert config.csps[0] == testcsp


@pytest.mark.usefixtures("in_memory_keyring")
def test_read_write_last_known_ac_csps(config):
    """ Tests the read and write operation for last known csps in the config file """
    csps = ['csp1', 'csp2']
    config.admin_console_csps = []
    config.admin_console_csps.extend(csps)
    helpers.write_config(config)
    config.admin_console_csps = []
    config = helpers.read_config(config)
    assert config.admin_console_csps == csps


def test_determine_csp_display_name(config):
    """ Tests generation of display name  """
    csps = [{'type': 'dropbox',
             'id': 'dropbox_1467009724.541582',
             'unique_id': 'crosscloudci.1@gmail.com',
             'display_name': 'Dropbox'}]

    with mock.patch('os.path.isdir', return_value=False):
        config.csps = []
        csp_disp_name = helpers.determine_csp_display_name(config=config,
                                                           sp_type='dropbox',
                                                           display_name='Dropbox')
        assert csp_disp_name == 'Dropbox'

        config.csps = csps
        csp_disp_name = helpers.determine_csp_display_name(config=config,
                                                           sp_type='dropbox',
                                                           display_name='Dropbox')
        assert csp_disp_name == 'Dropbox 2'

    csps.append({'type': 'dropbox',
                 'id': 'dropbox_1467009724.54158sdf',
                 'unique_id': 'crosscloudci.2@gmail.com',
                 'display_name': 'Dropbox 3'})

    config.csps = csps
    csp_disp_name = helpers.determine_csp_display_name(config=config,
                                                       sp_type='dropbox',
                                                       display_name='Dropbox')
    assert csp_disp_name == 'Dropbox 2'


@pytest.mark.usefixtures("in_memory_keyring")
def test_delete_storage_provider_credentials(config):
    """Test removing storage provider secrets from the configuration file. """

    # Create a dummy storage provider with not credentials attached.
    config.csps = []
    config.store_credentials_in_config = mock.Mock()
    dummy_credentials = json.dumps({'a': 'b', 'c': 'd'})
    storage = mock.Mock(jars.BasicStorage)
    storage.storage_name = 'Dropbox'
    storage.storage_user_name = 'user1'
    sp_dir = tempfile.mkdtemp()
    auth_data = {'storage': storage, 'credentials': dummy_credentials,
                 'identifier': 'db1', 'display_name': 'Dropbox 1', 'new_storage_id': 'db.1234',
                 'sp_dir': sp_dir}
    with mock.patch('cc.synchronization.models.instantiate_storage', return_value=storage):
        helpers.add_csp(config, auth_data)
    helpers.get_storage(config, "db.1234")['credentials'] = dummy_credentials
    assert len(config.csps) == 1
    helpers.write_config(config)

    # Delete the item and ensure that is no longer stored.
    helpers.delete_credentials_from_config(config, "db.1234")
    assert not helpers.get_credentials_from_config(config, "db.1234")

    # Ensure that we throw an exception if we try to access a non-existing storage.
    with pytest.raises(helpers.ConfigurationStorageNotFound):
        helpers.delete_credentials_from_config(config, "does.not.exist")


@mock.patch("cc.configuration.helpers.get_configuration_key", return_value=None)
def test_fail_encryption_without_configuration_key(mock_get_configuration_key, config, tmpdir):
    """Ensure an exception is thrown when we explicitly don't want a key to be created.

    Also do not provide one during the write operation.
    """
    config_file = str(tmpdir.join('tmp.json'))
    with pytest.raises(cc.crypto2.NoKeyError):
        helpers.write_config(config, config_file, auto_create_configuration_key=False)
    assert mock_get_configuration_key.called_with(service=config.APP_NAME,
                                                  name=config.KEYCHAIN_CONFIGURATION_KEY_NAME)


@pytest.mark.usefixtures("in_memory_keyring")
def test_read_write_encryption(config):
    """Ensure basic encrypt/decrypt works and that invalid keys or tags throw exceptions. """
    # Expected location of the configuration file.
    okey = helpers.get_configuration_key(config, auto_create=True)
    # Writing the configuration once should use the existing key and store the current tag.
    helpers.write_config(config)
    old_tag = helpers.get_configuration_tag(config)
    assert old_tag
    assert okey == helpers.get_configuration_key(config, auto_create=False)
    assert okey == helpers.get_configuration_key(config, auto_create=True)
    helpers.write_config(config)
    assert os.path.exists(config.config_file)
    # The tags should be different.
    new_tag = helpers.get_configuration_tag(config)
    assert old_tag != new_tag
    # The keys should stay the same.
    new_key = helpers.get_configuration_key(config, auto_create=True)
    assert new_key == okey
    # Decrypting it with the proper key and tag should work.
    assert helpers.read_encrypted_configuration(config, config.config_file, new_key, new_tag)
    # Decrypting with the old tag should still return the configuration.
    read_config = helpers.read_encrypted_configuration(config,
                                                       config.config_file,
                                                       new_key,
                                                       old_tag)
    assert 'metadata' in read_config
    # Decrypting with an invalid tag should still return the configuration.
    invalid_tag = b'X'*config.KEYCHAIN_CONFIGURATION_TAG_SIZE
    read_config = helpers.read_encrypted_configuration(config,
                                                       config.config_file,
                                                       new_key,
                                                       invalid_tag)
    assert 'metadata' in read_config
    # Decrypting with an invalid key should also fail.
    tag = helpers.get_configuration_tag(config)
    with pytest.raises(helpers.ConfigurationError):
        helpers.read_encrypted_configuration(config, config.config_file,
                                             os.urandom(config.KEYCHAIN_CONFIGURATION_KEY_SIZE),
                                             tag)


@pytest.mark.usefixtures("in_memory_keyring")
def test_store_read_configuration_key(no_configuration_key):
    """Test that storing and retrieving a given key works."""
    config, key = no_configuration_key

    assert key == helpers.get_configuration_key(config, auto_create=False)
    key = os.urandom(config.KEYCHAIN_CONFIGURATION_KEY_SIZE)

    kb64 = base64.b64encode(key).decode('ascii')
    keyring.set_password(config.APP_NAME,
                         config.KEYCHAIN_CONFIGURATION_KEY_NAME, kb64)

    stored_key = keyring.get_password(config.APP_NAME,
                                      config.KEYCHAIN_CONFIGURATION_KEY_NAME)

    assert stored_key == kb64
    assert key == helpers.get_configuration_key(config, auto_create=True)


@pytest.mark.usefixtures("in_memory_keyring")
def test_configuration_tag_read_write(config):
    """Tests if storing and retrieving configuration tags works properly."""

    # Delete prev. tags.
    keyring.delete_password(config.APP_NAME,
                            config.KEYCHAIN_CONFIGURATION_TAG_NAME)

    assert not helpers.get_configuration_tag(config)

    tag_a = os.urandom(config.KEYCHAIN_CONFIGURATION_TAG_SIZE)
    helpers.set_configuration_tag(config, tag_a)
    assert tag_a == helpers.get_configuration_tag(config)

    tag_b = os.urandom(config.KEYCHAIN_CONFIGURATION_TAG_SIZE)
    helpers.set_configuration_tag(config, tag_b)
    assert tag_b == helpers.get_configuration_tag(config)

    keyring.delete_password(config.APP_NAME,
                            config.KEYCHAIN_CONFIGURATION_TAG_NAME)
    assert not helpers.get_configuration_tag(config)


def reset_config(config):
    """ Helper function to reset the configuration of a config. """
    config.csps = []
    config.device_id = str(uuid.uuid1())
    config.sync_root_directory = ''
    config.encryption_enabled = False
    config.encrypt_public_shares = True
    config.encrypt_external_shares = True
    config.encryption_csp_settings = []
    config.device_private_key = b'reset_config_device_private_key'
    config.device_public_key = b'reset_config_device_public_key'
    config.user_private_key = b'reset_config_user_private_key'
    config.user_public_key = b'reset_config_user_public_key'
    return config


@pytest.mark.usefixtures("in_memory_keyring")
def test_read_write_basic_configuration(no_configuration_key):
    """ Tests basic read/write operation using a valid configuration dictionary. """
    config, no_configuration_key = no_configuration_key

    # Ensure that the temporary location is not tainted already.
    assert not os.path.exists(config.config_file)

    # Ensure that there is not configuration key stored in the keychain.
    assert not no_configuration_key

    # Reset the configuration.
    config = reset_config(config)

    # Setup a simple dummy configuration (as stored "in-memory") to check against.
    basic_configuration_with_sp = {
        'general': {'sync_root_directory': "/some/local/folder", 'device_id': '123-456-678-890'},
        'dropbox_randomid': {'display_name': 'Dropbox',
                             'type': 'dropbox',
                             'id': 'dropbox_randomid',
                             'selected_sync_directories': [{'children': True, 'path': ['test']}],
                             'unique_id': 'dbid:2384928349829384'}
    }
    config.csps.append(basic_configuration_with_sp.get('dropbox_randomid').copy())

    # General
    config.sync_root = basic_configuration_with_sp['general']['sync_root_directory']
    config.device_id = basic_configuration_with_sp['general']['device_id']

    # Encryption
    config.encryption_enabled = True
    config.encrypt_external_shares = True
    assert config.encrypt_external_shares
    config.encrypt_public_shares = True
    config.encryption_csp_settings = ['dropbox', 'onedrive']

    # Store / Encrypt Configuration
    helpers.write_config(config)
    assert os.path.exists(config.config_file)

    # Reset Configuration
    config = reset_config(config)

    # Re-read/Decrypt Configuration
    config = helpers.read_config(config)

    test_csp = basic_configuration_with_sp.get('dropbox_randomid')

    assert config.csps[0] == test_csp
    assert config.sync_root == basic_configuration_with_sp['general']['sync_root_directory']
    assert config.device_id == basic_configuration_with_sp['general']['device_id']
    assert config.csps[0]['selected_sync_directories']
    assert config.csps[0]['selected_sync_directories'] == test_csp['selected_sync_directories']

    # Ensure encryption settings have all been set to True
    assert config.encryption_enabled
    assert config.encrypt_public_shares
    assert config.encrypt_external_shares
    assert 'dropbox' in config.encryption_csp_settings
    assert 'cifs' not in config.encryption_csp_settings

    # TODO: XXX: What do active policies look like?
    # TODO: XXX: What do last known admin console csps look like?


@pytest.mark.usefixtures("in_memory_keyring")
def test_encryption_should_work_with_auto_create_while_write(no_configuration_key):
    """ Ensure that a key is auto created per default if not present when calling write
        operation. """
    config, no_configuration_key = no_configuration_key
    config = reset_config(config)
    assert not no_configuration_key
    helpers.write_config(config, config.config_file)

    # Ensure that a key has been written to the keychain.
    assert helpers.get_configuration_key(config, auto_create=False)


@pytest.mark.usefixtures("in_memory_keyring")
def test_add_storage_provider_credentials(config):
    """ Tests creating and adding storage provider secrets in the configuration file. """

    # Create a dummy storage provider with not credentials attached.
    config.csps = []
    config.store_credentials_in_config = mock.Mock()
    dummy_credentials = json.dumps({'a': 'b', 'c': 'd'})
    storage = mock.Mock(jars.BasicStorage)
    storage.storage_name = 'Dropbox'
    storage.storage_user_name = 'user1'
    sp_dir = tempfile.mkdtemp()
    auth_data = {'storage': storage, 'credentials': dummy_credentials,
                 'identifier': 'db1', 'display_name': 'Dropbox 1', 'new_storage_id': 'db.1234',
                 'sp_dir': sp_dir}
    with mock.patch('cc.synchronization.models.instantiate_storage', return_value=storage):
        helpers.add_csp(config, auth_data)
    # helpers.add_csp(config, auth_data)
    assert len(config.csps) == 1

    dummy_credentials = {'a': 'b', 'c': 'd'}
    helpers.store_credentials_in_config(config, "db.1234", dummy_credentials.copy())
    credentials = helpers.get_credentials_from_config(config, "db.1234")
    assert credentials == dummy_credentials

    # Adding credentials to an non-existing storage provider should raise a ConfigurationError
    with pytest.raises(helpers.ConfigurationError):
        helpers.store_credentials_in_config(config, "does.not.exist", dummy_credentials.copy())

    # Adding new credentials to an existing storage provider should replace the old credentials
    new_dummy_credentials = {'d': 'e', 'f': 'g'}
    helpers.store_credentials_in_config(config, "db.1234", new_dummy_credentials.copy())
    credentials = helpers.get_credentials_from_config(config, "db.1234")
    assert credentials == new_dummy_credentials


@pytest.mark.usefixtures("in_memory_keyring")
def test_store_auth_token(config):
    """Ensure that the AC authentication token can be stored and re-read from the config."""

    # We start with an empty auth_token.
    config.auth_token = None
    helpers.write_config(config)

    # Which should also be persisted.
    config = helpers.read_config(config)
    assert config.auth_token is None

    # Let's try it with an actual token.
    config.auth_token = json.dumps({'username': 'Jack', 'password': 'Daniels'})
    helpers.write_config(config)

    # Reset relevant part of the configuration.
    config.auth_token = None

    # We should be able to read the stored auth_token.
    config = helpers.read_config(config)
    assert config.auth_token is not None
    token = json.loads(config.auth_token)

    assert token['username'] == 'Jack'
    assert token['password'] == 'Daniels'


@pytest.mark.usefixtures("in_memory_keyring")
def test_read_write_auth_token_using_settings_sync(config):
    """Ensure that using the methods in settings_sync to read/write the auth_token works."""
    config.auth_token = None
    token = settings_sync.get_token(config)
    assert token is None

    settings_sync.token_saver({'username': 'Jack', 'password': 'Daniels'}, config=config)
    my_token = settings_sync.get_token(config)
    assert my_token['username'] == 'Jack'

    settings_sync.token_saver({'username': 'Cross', 'password': 'Cloudwalker'}, config=config)
    my_token = settings_sync.get_token(config)
    assert my_token['username'] == 'Cross'


@pytest.mark.usefixtures("in_memory_keyring")
def test_set_csp_selected_sync_dirs(config, sample_csps):
    """Ensure sync dirs are set."""
    new_value = 'test'
    config.csps = sample_csps
    csp = config.csps[0]
    expected_value = csp
    expected_value['selected_sync_directories'] = new_value
    helpers.set_csp_selected_sync_dirs(config, csp_id=csp['id'], filter_config=new_value)
    assert expected_value in config.csps


@pytest.mark.usefixtures("in_memory_keyring")
def test_update_filter_in_config(config):
    """Ensure this function calls set_csp_selected_sync_dirs with proper values."""
    fake_tree = bushn.Node(name=None)
    csp_id = 'fake id'
    expected_filter = list(jars.utils.tree_to_config(fake_tree))
    with mock.patch('cc.configuration.helpers.set_csp_selected_sync_dirs') as mock_function:
        helpers.update_filter_in_config(config, fake_tree, csp_id=csp_id)
        mock_function.assert_called_with(config, csp_id, expected_filter)


@pytest.mark.usefixtures("in_memory_keyring")
def test_rename_csp(config, sample_csps):
    """Ensure a given SP is renamed."""
    new_name = 'Renamed SP'
    config.csps = sample_csps
    csp = config.csps[0]
    csp['display_name'] = new_name
    helpers.rename_csp(config, csp['id'], new_name)
    assert csp in config.csps
    assert len(config.csps) == 2

    helpers.rename_csp(config, None, new_name)


def test_raise_for_duplicate(config, sample_csps):
    """Ensure it is not possible to add duplicated accounts."""
    config.csps = sample_csps
    dupe = sample_csps[0]
    config.store_credentials_in_config = mock.Mock()
    dummy_credentials = json.dumps({'a': 'b', 'c': 'd'})
    storage = mock.Mock(jars.BasicStorage)
    storage.storage_name = dupe['type']
    storage.storage_user_name = 'user1'
    sp_dir = tempfile.mkdtemp()
    auth_data = {'storage': storage, 'credentials': dummy_credentials,
                 'identifier': dupe['unique_id'], 'display_name': 'Dropbox 1',
                 'new_storage_id': 'db.1234', 'sp_dir': sp_dir}
    with mock.patch('cc.synchronization.models.instantiate_storage', return_value=storage), \
            pytest.raises(helpers.DuplicatedAccountError):
        helpers.add_csp(config, auth_data)


def test_init_config_dirs(config):
    """Ensure directories are created."""
    calls = [call(config.CONFIG_DIR, exist_ok=True),
             call(config.CACHE_DIR, exist_ok=True),
             call(config.LOG_DIR, exist_ok=True)]

    with mock.patch('os.makedirs') as mocked_mkdir:
        helpers.init_config_dirs(config)
        mocked_mkdir.assert_has_calls(calls)


def test_set_shares_with_external_users(config):
    """Ensure shares with external users are updated."""
    new_shares = set(['test_share', 'test_share2'])
    old_shares = set()
    with mock.patch('cc.configuration.helpers.write_config') as mock_write:
        config.shares_with_external_users = old_shares
        helpers.set_shares_with_external_users(config, new_shares)
        assert config.shares_with_external_users == new_shares
        mock_write.assert_called_once()


@pytest.mark.parametrize('subject', [('share:_:_'),
                                     ('user:_:_')])
def test_get_private_key_pem_by_subject(config, subject):
    """Ensure correct key is returned for a subject."""
    category, _, _ = subject.split(':')
    if category == 'share':
        fake_share_key_pairs = {subject: cc.crypto2.KeyPair(private_pem='private',
                                                            public_pem=None)}
        config.share_key_pairs = fake_share_key_pairs
        expected = 'private'
    elif category == 'user':
        fake_user_key = 'fake_key'
        config.user_private_key = fake_user_key
        expected = 'fake_key'
    value = helpers.get_private_key_pem_by_subject(config, subject)
    assert value == expected

    with pytest.raises(KeyError):
        helpers.get_private_key_pem_by_subject(config, 'false:_:_')
    cc.config.share_key_pairs = {}
    cc.config.user_private_key = b''


@pytest.mark.parametrize('subject', [('share:_:_'),
                                     ('user:_:_'),
                                     ('master:_:_')])
def test_get_public_key_pem_by_subject(subject, config):
    """Ensure correct key is returned for a subject."""
    category, _, _ = subject.split(':')
    config.master_key_subject = None
    if category == 'share':
        fake_share_key_pairs = {subject: cc.crypto2.KeyPair(private_pem='private',
                                                            public_pem='public')}
        config.share_key_pairs = fake_share_key_pairs
        expected = 'public'
    elif category == 'user':
        fake_user_key = 'fake_key'
        config.user_public_key = fake_user_key
        expected = 'fake_key'
    elif category == 'master':
        fake_master_key = 'fake_master'
        # check 'wrong aster key' is raised
        with pytest.raises(KeyError):
            helpers.get_public_key_pem_by_subject(config, subject)
        config.master_key_subject = subject
        config.master_key_pem = fake_master_key
        expected = fake_master_key

    value = helpers.get_public_key_pem_by_subject(config, subject)
    assert value == expected

    with pytest.raises(KeyError):
        helpers.get_public_key_pem_by_subject(config, 'false:_:_')
    config.share_key_pairs = {}
    config.user_public_key = b''
    config.master_key_pem = None
    config.master_key_subject = None


def test_set_constants(config):
    """Esure that by setting constants, the required fields are set."""
    config = helpers.set_constants(config)
    assert 'APP_NAME' in config

    # defining codes for determining between os
    assert 'WINDOWS_PLATFORM_CODE' in config
    assert 'MACOS_PLATFORM_CODE' in config
    assert 'APP_NAME' in config

    assert 'VERSION' in config
    assert 'CONFIG_FILE' in config
    # Specifies the current schema version of configuration file.
    assert 'CONFIGURATION_SCHEMA_VERSION' in config
    assert 'SYNC_ENGINE_STATE' in config
    assert 'LOCK_FILE' in config

    # define the name of the keyring item the key will be stored in.
    assert 'KEYCHAIN_CONFIGURATION_KEY_NAME' in config
    assert 'KEYCHAIN_CONFIGURATION_KEY_IV_SIZE' in config
    assert 'KEYCHAIN_CONFIGURATION_KEY_SIZE' in config

    assert 'KEYCHAIN_CONFIGURATION_TAG_NAME' in config
    assert 'KEYCHAIN_CONFIGURATION_TAG_SIZE' in config

    assert 'HIDDEN_FILE_PREFIX' in config


def test_update_inodes(config, mocker):
    """Assert inodes for each storage are updated to the new directories."""
    sp1 = {'display_name': 'storage 1', 'local_unique_id': 'fake_id_1'}
    config.csps.append(sp1)
    item = mock.Mock()
    item.st_ino = 'new_fake_id_1'
    with mocker.patch('os.stat', return_value=item):
        helpers.update_inodes(config)
    assert config.csps[0]['local_unique_id'] == item.st_ino
