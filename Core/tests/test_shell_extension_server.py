"""Test the server for the shell extension."""
import os

import mock
import pytest
from pykka import ThreadingFuture
from jars import BasicStorage, StorageMetrics

from cc.shell_extension_server import (create_displaying_menu_items,
                                       create_sharing_menu_items,
                                       ShellExtensionInterface)
# from cc.synchronization.step import StepManager
from cc.synchronization.syncengine import SyncEngine
from cc.synchronization.models import SynchronizationGraph, SynchronizationLink
from cc.synctask import SyncTask

# pylint: disable=redefined-outer-name

# pytestmark = pytest.mark.skip('This will be fixed with #795')
LINK_ID = 'local::csp0'
LINK_ID2 = 'local::csp1'


@pytest.fixture
def sei_no_storage(config):
    """Return a ShellExtensionInterface without any remote storage."""
    sync_graph = SynchronizationGraph(sync_root=None,
                                      bademeister=None,
                                      periodic_state_saver=None)
    sync_graph.links = {}
    with mock.patch('cc.shell_extension_server.ShellExtensionInterface.initialize_callbacks'):
        return ShellExtensionInterface(sync_graph, config)


@pytest.fixture
def sei_one_storage(sei_no_storage):
    """Return a ShellExtensionInterface with one csp called 'csp0'."""
    sei_no_storage.sync_graph.links[LINK_ID] = generate_sync_link(LINK_ID, 'CSP 0')
    return sei_no_storage


@pytest.fixture
def sei_two_storages(sei_one_storage):
    """Return a ShellExtensionInterface with one csp called 'csp1'."""
    sei_one_storage.sync_graph.links[LINK_ID2] = generate_sync_link(LINK_ID2, 'CSP 1')
    return sei_one_storage


def generate_sync_link(display_name, storage_id, capacity=1000):
    """Return a dummy sync link."""
    sync_link = mock.Mock(SynchronizationLink)
    sync_link.local = mock.Mock(BasicStorage)
    sync_link.remote = mock.Mock(BasicStorage)
    sync_link.remote.storage_id = storage_id
    metrics = ThreadingFuture()
    metrics.set(StorageMetrics(storage_id, capacity, display_name=display_name))
    sync_link.metrics = metrics
    sync_engine = mock.MagicMock(SyncEngine)
    sync_engine.query().get.return_value = {}
    sync_link.sync_engine = sync_engine
    return sync_link


@pytest.fixture
def test_path(config):
    """Return a testpath relative to the sync path."""
    return os.path.join(config.sync_root, 'csp0', 'hello')


def test_action_browser_open(sei_two_storages, test_path):
    """Test if the browser was opened by a link created with csp's create_web_link."""
    with mock.patch('webbrowser.open') as browser_open_mock:
        sei_two_storages.perform_action('browser_open_csp1', [test_path])
        sei_two_storages.sync_graph.links[LINK_ID].remote. \
            create_open_in_web_link.assert_called_once()
    browser_open_mock.assert_called_with(sei_two_storages.sync_graph.links[LINK_ID].remote.
                                         create_open_in_web_link.return_value)


def test_action_share(sei_two_storages, test_path):
    """Test if the browser was opened by a link created with csp's create_web_link."""
    with mock.patch('pyperclip.copy') as pyperclip_mock:
        sei_two_storages.perform_action('create_link_csp1', [test_path])
        sei_two_storages.sync_graph.links[LINK_ID].remote. \
            create_public_sharing_link.assert_called_once()

    pyperclip_mock.assert_called_with(sei_two_storages.sync_graph.links[LINK_ID].remote.
                                      create_public_sharing_link.return_value)


def test_get_context_menu_sharing_no_csp(sei_no_storage, test_path):
    """Test if nothing will be returned if there is no csp to share with."""
    ctx_menu = sei_no_storage.get_context_menu([test_path])
    assert ctx_menu == []


def test_get_context_menu_sharing_one_csp(sei_one_storage, test_path, mocker):
    """Simple case: one csp, one file."""
    create_sharing_menu_mock = mock.MagicMock()
    create_display_menu_mock = mock.MagicMock()
    mocker.patch('cc.shell_extension_server.create_sharing_menu_items',
                 create_sharing_menu_mock)
    mocker.patch('cc.shell_extension_server.create_displaying_menu_items',
                 create_display_menu_mock)

    # this indicates it has been synced to csp0
    sei_one_storage.sync_graph.\
        links[LINK_ID].sync_engine.query().get.return_value = {'storage': {'csp0': {}}}

    sei_one_storage.get_context_menu([test_path])

    # the sharing item will be created by create_sharing_menu_mock, so this must
    # have been called
    create_sharing_menu_mock.assert_called()


def test_get_context_menu_sharing_one_csp_multiple_files(sei_one_storage, test_path, mocker):
    """Simple case: one csp, multiple files: no sharing menu should be displayed."""
    create_sharing_menu_mock = mock.Mock()
    create_displaying_menu_mock = mock.Mock()
    mocker.patch('cc.shell_extension_server.create_sharing_menu_items',
                 create_sharing_menu_mock)
    mocker.patch('cc.shell_extension_server.create_displaying_menu_items',
                 create_displaying_menu_mock)

    ctx_menu = sei_one_storage.get_context_menu([test_path, test_path])

    # if there is at least one csp there has to be a menu item called 'Sharing', grab it
    assert not [itm for itm in ctx_menu if itm ==
                create_sharing_menu_mock.return_value]


@pytest.fixture
def metrics():
    """Return a couple of metrics."""
    result = []
    for num in range(5):
        result.append(StorageMetrics(
            storage_id='csp{}'.format(num),
            free_space=num * 5,
            display_name='Csp {}'.format(num)))
    return result


@pytest.fixture
def csp_mocks():
    """Return a couple of csp mocks."""
    result = []
    for num in range(5):
        mocked_csp = mock.Mock(spec=BasicStorage)
        mocked_csp.storage_id = 'csp{}'.format(num)
        result.append(mocked_csp)
    return result


def test_create_sharing_sub_menu_mock(csp_mocks):
    """Test if the submenu for sharing is created right."""
    menu = create_sharing_menu_items(storage=csp_mocks[0], storage_id='csp0')
    assert len(menu) == 1
    assert menu[0] == {'name': 'Create public link',
                       'enabled': True,
                       'children': [],
                       'actionId': 'create_link_csp0'}

    menu = create_displaying_menu_items(storage=csp_mocks[0], storage_id='csp0')
    assert len(menu) == 1
    assert menu[0] == {'name': 'Show in browser',
                       'enabled': True,
                       'children': [],
                       'actionId': 'browser_open_csp0'}


def test_create_sharing_sub_menu_no_weblink(csp_mocks):
    """Test if the submenu for weblinks is created right."""
    csp_mocks[0].storage_name = 'CSP'
    csp_mocks[0].supports_sharing_link = False
    menu = create_sharing_menu_items(storage_id='csp0', storage=csp_mocks[0])

    # the second one is expected to be creating a weblink
    assert len(menu) == 1
    assert menu[0] == {'name': 'Public link not supported by storage',
                       'enabled': False,
                       'children': [],
                       'actionId': ''}


def test_create_sharing_sub_menu_no_browser(csp_mocks):
    """Test if not supported sharing is also displayed."""
    csp_mocks[0].storage_name = 'CSP'
    csp_mocks[0].supports_open_in_web_link = False
    menu = create_displaying_menu_items(storage_id='csp0', storage=csp_mocks[0])

    # the second one is expected to be creating a weblink
    assert len(menu) == 1
    assert menu[0] == {'name': 'Show in browser not supported by storage',
                       'enabled': False,
                       'children': [],
                       'actionId': ''}


@pytest.mark.parametrize('path', [[LINK_ID, 'a'],
                                  [LINK_ID, 'B'],
                                  [LINK_ID, 'aB'],
                                  [LINK_ID, 'a', 'B'],
                                  [LINK_ID, 'A', 'b']])
def test_get_absolute_task_path(sei_one_storage, path):
    """Ensure the return is a properly constructed path."""
    task = mock.Mock(SyncTask)
    task.path = path
    task.link = sei_one_storage.sync_graph.links[LINK_ID]
    expected_return = ['fake'] + path
    with mock.patch('cc.configuration.helpers.get_storage', return_value={'display_name': 'fake'}):
        path = sei_one_storage.get_absolute_task_path(task)
        assert path == expected_return


def test_get_path_status_not_normalized(sei_one_storage, config):
    """Ensure get_storage_by_displayname is called with a non normalized path."""
    with mock.patch('cc.configuration.helpers.get_storage_by_displayname') as mocked_get_storage:
        sei_one_storage.get_path_status(config.sync_root + '/fake/path/csp0')
    mocked_get_storage.assert_called_with(mock.ANY, 'fake')
