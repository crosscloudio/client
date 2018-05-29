"""Tests for the encryption wrapper."""
from copy import deepcopy
from unittest import mock

import pytest
import bushn

from cc.encryption.storage_wrapper import EncryptionWrapper, EncryptedVersionTag, \
    get_key_subjects, _has_different_share_id
from cc.synchronization.syncfsm import STORAGE
from tests.synchronization.se.conftest import FILESYSTEM_ID

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture
def encryption_wrapper():
    """Function to mock the encryption wrapper.

    This is a trick to be able to test a mixin method, encryption_wrapper is a fake
    self for EncryptionWrapper methods"""

    def fake_query(path):
        """fake query which for syncenegine.query"""
        query_mock = mock.Mock()
        if path[0] == 'a':
            query_mock.get = mock.Mock(
                return_value={'storage': {FILESYSTEM_ID: {}, 'b': {}}})
        else:
            query_mock.get = mock.Mock(return_value={'storage': {FILESYSTEM_ID: {}}})
        return query_mock

    syncengine = mock.Mock()
    syncengine.query = fake_query
    syncengine.query_shared_state().get = mock.Mock(return_value=('', False, set()))

    wrapper = mock.Mock(EncryptionWrapper)
    wrapper._syncengine = syncengine

    return wrapper


#
# def test_wrap_props_not_in_a_sp_folder(encryption_wrapper, mocker):
#     """ tests if the properties are *not* wrapped in case the path is not part of a sp-folder
#
#     This is not possible since we have no config, if it then should be encrypted or not
#     """
#
#     new_props = EncryptionWrapper.wrap_props(
#         encryption_wrapper,
#         ['b', 'path'], {'size': 1337, 'version_id': 7331})
#
#     # nothing should be touched
#     assert new_props['size'] == 1337
#     assert new_props['version_id'] == 7331
#
#
# def test_wrap_props(encryption_wrapper):
#     """ test if wrap props correctly wraps the version id """
#     with mock.patch('cc.config.encryption_csp_settings', {'a': True}), \
#          mock.patch('cc.config.get_storage', lambda _: {'type': 'a'}), \
#          mock.patch('cc.config.user_id', 'testuser'):
#         props = EncryptionWrapper.wrap_props(
#             encryption_wrapper, ['a', 'path'],
#             {'version_id': 'a_lonely_id', 'size': 123})
#         expected_shared = ('testuser',)
#         # pylint: disable=invalid-sequence-index
#         assert props['version_id'] == EncryptedVersionTag('a_lonely_id', expected_shared)


@pytest.fixture
def test_path():
    """Fixture for a test path"""
    return ['a file']


@pytest.fixture
def encryption_wrapper_mock(config):
    """ it is hard to test mixin classes, that is the reson why we need a fake class here"""

    class MyClass:
        """Dummy storage"""

        # pylint: disable=unused-argument
        def __init__(self, *args, **kwargs):
            self.open_read_ = mock.Mock()

        def open_read(self, *args, **kwargs):
            """Open read for this mock storage"""
            return self.open_read_(*args, **kwargs)

    class EncryptionWrapperMock(EncryptionWrapper, MyClass):
        """Mocked Encryption Wrapper with MyClass as storage"""
        client_config = config

    return EncryptionWrapperMock(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())


def test_open_read_without_id(test_path):
    """tests if the wrapper returns an unwrapped object in case of non-existing version id"""
    with mock.patch('builtins.super') as superclass:
        encryption_wrapper = EncryptionWrapper(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        assert encryption_wrapper.open_read(test_path) == \
            superclass.return_value.open_read.return_value
        superclass.return_value.open_read.assert_called_with(path=test_path,
                                                             expected_version_id=None)


def test_open_read_not_no_encrypted_tag(test_path):
    """tests if the wrapper returns an unwrapped object in case a EncryptedVersionTag instance is
    passed"""
    with mock.patch('builtins.super') as superclass:
        encryption_wrapper = EncryptionWrapper(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        assert encryption_wrapper.open_read(test_path, 123) == \
            superclass.return_value.open_read.return_value
        superclass.return_value.open_read.assert_called_with(path=test_path,
                                                             expected_version_id=123)


def test_open_read_get_keys(test_path, encryption_wrapper_mock, mocker):
    """tests if the wrapper calls the get_key function for each subject in the
    EncryptedVersionTag and returns a correctly parametrized `cc.crypto2.EncryptionFileWrapper`
    """
    subjects = ('one_key', 'two_key')

    version_id = EncryptedVersionTag(version_id=123, key_subjects=subjects)

    enc_file_wrapper_mock = mocker.patch('cc.crypto2.EncryptionFileWrapper')

    assert enc_file_wrapper_mock.return_value == \
        encryption_wrapper_mock.open_read(test_path, version_id)

    encryption_wrapper_mock.open_read_.assert_called_with(path=test_path, expected_version_id=123)
    for subject in subjects:
        encryption_wrapper_mock.public_key_getter.assert_any_call(subject)


def test_on_shared_state_changed_from_fs(encryption_wrapper_mock):
    """on_shared_state_changed should return without doing anything if the event origin is
    the filesystem.
    """
    sender_mock = mock.Mock()
    mynode = mock.Mock()
    mynode.path = ['hello']
    mynode.props = {}
    encryption_wrapper_mock.on_shared_state_changed(sender=sender_mock, old_props={}, node=mynode,
                                                    storage_id=FILESYSTEM_ID)

    assert len(sender_mock.method_calls) == 0


def test_has_differnet_share_id_from_fs():
    """events from filesystem should be ignored"""
    assert _has_different_share_id(storage_id=FILESYSTEM_ID, old_props={}, new_props={}) is False


def test_has_differnet_share_id_different_version():
    """events with different version_ids should be ignored"""
    assert _has_different_share_id(
        storage_id='c',
        old_props={STORAGE: {'c': {'version_id': 123}}},
        new_props={STORAGE: {'c': {'version_id': 321}}}) is False


def test_has_differnet_share_id_no_old():
    """events with different version_ids should be ignored"""
    assert _has_different_share_id(
        storage_id='c',
        old_props={},
        new_props={STORAGE: {'c': {'version_id': 321}}}) is False


def test_has_differnet_share_id_no_old_no_new():
    """events with different version_ids should be ignored"""
    assert _has_different_share_id(
        storage_id='c',
        old_props={},
        new_props={}) is False


def test_has_differnet_share_id_same_id():
    """events with same share_ids should be ignored"""
    assert _has_different_share_id(
        storage_id='c',
        old_props={STORAGE: {'c': {'version_id': 123, 'share_id': 1}}},
        new_props={STORAGE: {'c': {'version_id': 123, 'share_id': 1}}}) is False


def test_has_differnet_share_id():
    """events with different version_ids should not be ignored"""
    assert _has_different_share_id(
        storage_id='c',
        old_props={STORAGE: {'c': {'version_id': 123, 'share_id': 2}}},
        new_props={STORAGE: {'c': {'version_id': 123, 'share_id': 1}}}) is True


def test_on_shared_state_changed(encryption_wrapper_mock, mocker):
    """check for issue CC-409.

    The bug was that it propagated the wrong properties for the children of a node
    """

    mocker.patch('cc.encryption.storage_wrapper.get_key_subjects', return_value=('abc',))

    new_props = {'c': {'version_id': 'is_dir', 'share_id': 1},
                 FILESYSTEM_ID: {'version_id': 'is_dir', 'is_dir': True}}

    new_props_child = {'c': {'version_id': 123, 'share_id': 1}, FILESYSTEM_ID: {'version_id': 123}}

    sender = mock.Mock()
    sender.root_node = bushn.Node(name=None)
    changed_node = sender.root_node.add_child('a', {STORAGE: new_props})

    changed_node.add_child('xyz', {STORAGE: new_props_child})
    sender.query_shared_state = mock.Mock(return_value=('v', 1, None))

    encryption_wrapper_mock.on_shared_state_changed(
        sender,
        old_props={STORAGE: {'c': {'version_id': 'is_dir'}}},
        node=changed_node,
        storage_id='c')

    new_props_with_enc_tag = deepcopy(new_props[FILESYSTEM_ID])
    new_props_with_enc_tag['version_id'] = EncryptedVersionTag(version_id='is_dir',
                                                               key_subjects=('abc',))
    new_props_with_enc_tag_child = deepcopy(new_props_child[FILESYSTEM_ID])
    new_props_with_enc_tag_child['version_id'] = EncryptedVersionTag(version_id=123,
                                                                     key_subjects=('abc',))

    expected = [
        mock.call(
            storage_id=FILESYSTEM_ID,
            path=['a'],
            event_props=new_props_with_enc_tag),

        mock.call(
            storage_id=FILESYSTEM_ID,
            path=['a', 'xyz'],
            event_props=new_props_with_enc_tag_child)]

    encryption_wrapper_mock._syncengine.storage_modify.has_calls(expected, any_order=True)


def test_get_key_subjects_user(mocker, config):
    """ only the user subject should be returned in that case """
    config.encryption_enabled = True
    config.organization_id = 'pad'
    config.user_id = 'derheinzi@crosscloud.me'
    config.encryption_csp_settings = {'bestdrive': True}
    config.master_key_subject = 'master:0:'
    mocker.patch('cc.configuration.helpers.get_storage', return_value={'type': 'bestdrive'})
    subjects = get_key_subjects(storage_id='blabla', share_id=None, config=config)
    assert subjects[1] == 'user:0:derheinzi@crosscloud.me@pad'


def test_get_key_subjects_share_id(mocker, config):
    """ only the share subject should be returned in that case """
    config.encryption_enabled = True

    config.encryption_csp_settings = {'bestdrive': True}
    config.master_key_subject = 'master:0:'
    mocker.patch('cc.configuration.helpers.get_storage', return_value={'type': 'bestdrive'})

    subjects = get_key_subjects(storage_id='blabla', share_id='hehhe', config=config)
    assert subjects[1] == 'share:0:bestdrive+hehhe'


def test_get_key_subjects_share_id_not_encrypted(mocker, config):
    """ nothing should be returned since it is disabled """
    mocker.patch('cc.configuration.helpers.get_storage', return_value={'type': 'bestdrive'})

    config.encryption_csp_settings = {}

    subjects = get_key_subjects(storage_id='blabla', share_id='hehhe', config=config)
    assert subjects == ()


def test_get_key_subjects_user_not_encrypted(mocker, config):
    """Nothing should be returned since it is disabled."""
    mocker.patch('cc.configuration.helpers.get_storage', return_value={'type': 'bestdrive'})
    config.encryption_csp_settings = {}
    subjects = get_key_subjects(storage_id='blabla', share_id=None, config=config)
    assert subjects == ()


def test_get_key_subjects_share_external_users(mocker, config):
    """If a share is shared with externals and encrypt_external_shares is set."""
    config.encryption_enabled = True
    config.encryption_csp_settings = {'gdruve': True}
    config.encrypt_external_shares = True
    config.shares_with_external_users = {('gdruve', 'ne_id')}
    config.master_key_subject = 'master:0:'

    mocker.patch('cc.configuration.helpers.get_storage',
                 return_value={'type': 'gdruve'})

    subjects = get_key_subjects(storage_id='gang', share_id='ne_id', config=config)

    assert subjects[1] == 'share:0:gdruve+ne_id'


def test_get_key_subjects_share_external_users_no_encrypt(mocker, config):
    """If a share is shared with externals and encrypt_external_shares is set."""
    config.encryption_csp_settings = {'gdruve': True}
    config.encrypt_external_shares = False
    config.shares_with_external_users = {('gdruve', 'ne_id')}
    config.master_key_subject = 'master:0:'

    mocker.patch('cc.configuration.helpers.get_storage',
                 return_value={'type': 'gdruve'})
    assert () == get_key_subjects(storage_id='gang',
                                  share_id='ne_id',
                                  config=config)


def test_get_key_subjects_share_no_external_users_no_encrypt(mocker, config):
    """If a share is shared with externals and encrypt_external_shares is set."""
    config.encryption_enabled = True
    config.encryption_csp_settings = {'gdruve': True}
    config.encrypt_external_shares = False
    config.shares_with_external_users = set()

    config.master_key_subject = 'master:0:'
    mocker.patch('cc.configuration.helpers.get_storage',
                 return_value={'type': 'gdruve'})

    subjects = get_key_subjects(storage_id='gang',
                                share_id='ne_id',
                                config=config)
    assert subjects[1] == 'share:0:gdruve+ne_id'


def test_get_key_subjects_sp_enabled_globally_not(mocker, config):
    """Test if global disable return no keys."""
    config.encryption_csp_settings = {'gdruve': True}
    config.encryption_enabled = False
    config.encrypt_external_shares = False
    config.shares_with_external_users = set()
    config.master_key_subject = 'master:0:'

    mocker.patch('cc.configuration.helpers.get_storage',
                 return_value={'type': 'gdruve'})

    subjects = get_key_subjects(storage_id='gang',
                                share_id='ne_id',
                                config=config)
    assert subjects == ()


def test_encryption_version_tag():
    """
    Tests the merging functionality of the encryption version tag
    """
    version_id = (123435687, 22)
    vid_1 = EncryptedVersionTag(version_id, False)
    assert vid_1.version_id == version_id
    assert vid_1.key_subjects is False
    vid_2 = EncryptedVersionTag(version_id, True)
    assert vid_2.version_id == version_id
    assert vid_2.key_subjects is True
    vid_3 = EncryptedVersionTag(vid_1, True)
    assert vid_3.version_id == version_id
    assert vid_3.key_subjects is True
    vid_4 = EncryptedVersionTag(vid_1, False)
    assert vid_4.version_id == version_id
    assert vid_4.key_subjects is False
    vid_5 = EncryptedVersionTag(vid_2, True)
    assert vid_5.version_id == version_id
    assert vid_5.key_subjects is True
    vid_6 = EncryptedVersionTag(vid_2, False)
    assert vid_6.version_id == version_id
    assert vid_6.key_subjects is False
