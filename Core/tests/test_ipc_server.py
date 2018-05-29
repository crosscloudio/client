"""
Test of shell extension server implementation in core
"""
# import os
# from collections import namedtuple
#
# import pytest
# import mock
# from mock import MagicMock
#
# from cc import ipc_server
# from cc.config import sync_root
# from cc.ipc_server import Dispatcher, cc_thrift, MenuItem, MenuType,
# ACTION_REMOVE_ALL, \
#     ACTION_ADD_TO_ALL, ACTION_ADD_TO_PREFIX, ACTION_REMOVE_FROM_PREFIX
# from cc.syncfsm import SYNC_RULES, STORAGE, FILESYSTEM_ID
#
# # pylint: disable=redefined-outer-name
#
# if os.name == 'nt':
#     P_SEP = os.altsep
# else:
#     P_SEP = os.sep
#
#
# def test_get_sync_root():
#     """
#     Tests sync dir getter
#     """
#
#     dispatcher = Dispatcher(None, None)
#     assert dispatcher.getSyncDirectory() == sync_root
#
#
# def test_no_accounts_menu():
#     """
#     Test ipc server with no accounts added.
#     """
#     dispatcher = Dispatcher(step=MagicMock(), sync_engine=MagicMock(spec=[],
#                                                                     csps=[]))
#     ctx_menu = dispatcher.getContextMenu([])
#     assert ctx_menu == [cc_thrift.MenuItem(name='No Accounts added',
#                                            enabled=True,
#                                            type=cc_thrift.MenuType.ACTION,
#                                            children=[],
#                                            actionId='')]
#
#
# def test_one_account_menu():
#     """
#     Test ipc server with no accounts added.
#     """
#     csps = {'st_id': MagicMock(spec=[], storage_id='st_id', storage_name='Dropbox')}
#     dispatcher = Dispatcher(step=MagicMock(spec=[], storages=csps),
#                             sync_engine=MagicMock(spec=[]))
#
#     # test with empty paths
#     assert [create_default_sharing_element()] == dispatcher.getContextMenu([])
#
#     # test with single path
#     expected_menu = [create_default_sharing_element(add_weblink=True)]
#
#     test_paths = [os.path.join(sync_root, "crosscloud")]
#     assert expected_menu == dispatcher.getContextMenu(test_paths)
#
#
# def test_menu_with_empy_sync_rules():
#     """
#     Test ipc server with no accounts added.
#     """
#     csps = {'st_id_1': MagicMock(spec=[], storage_id='st_id_1', display_name='st_id_1',
#                                  storage_name='Dropbox'),
#             'st_id_2': MagicMock(spec=[], storage_id='st_id_2', display_name='st_id_2',
#                                  storage_name='GDrive')}
#     query_method = wrap_method_get({SYNC_RULES: []})
#     csps_getter = wrap_method_get([csps['st_id_1'], csps['st_id_2']])
#     sync_engine = MagicMock(spec=[], query_sync_rules=query_method,
#                             get_metrics=csps_getter)
#     step = MagicMock(spec=[], storages=csps)
#
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#
#     sr_menu = MenuItem(name='Sync To',
#                        enabled=True,
#                        type=MenuType.POPUP,
#                        children=[],
#                        actionId='')
#     sr_menu.children = [MenuItem(name='Sync to st_id_1',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='addTo_st_id_1',
#                                  children=[]),
#                         MenuItem(name='Sync to st_id_2',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='addTo_st_id_2',
#                                  children=[]),
#                         MenuItem(name='Sync to all',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='addToAll',
#                                  children=[]),
#                         MenuItem(name='Sync to any',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='RemoveAll',
#                                  children=[])]
#     expected_menu = [sr_menu, create_default_sharing_element(add_weblink=True)]
#
#     test_paths = [os.path.join(sync_root, "crosscloud")]
#     ctx_menu = dispatcher.getContextMenu(test_paths)
#     assert expected_menu == ctx_menu
#
#
# def test_menu_with_sync_to_all_sync_rules():
#     """
#     Test ipc server with no accounts added.
#     """
#     csps = {'st_id_1': MagicMock(spec=[], storage_id='st_id_1', display_name='st_id_1',
#                                  storage_name='Dropbox'),
#             'st_id_2': MagicMock(spec=[], storage_id='st_id_2', display_name='st_id_2',
#                                  storage_name='GDrive')}
#     query_method = wrap_method_get({'st_id_1': ['crosscloud'], 'st_id_2':
# ['crosscloud']})
#     csps_getter = wrap_method_get([csps['st_id_1'], csps['st_id_2']])
#     sync_engine = MagicMock(spec=[], query_sync_rules=query_method,
#                             get_metrics=csps_getter)
#     step = MagicMock(spec=[], storages=csps)
#
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#
#     sr_menu = MenuItem(name='Sync To', enabled=True, type=MenuType.POPUP, children=[],
#                        actionId='')
#     sr_menu.children = [MenuItem(name='Remove from st_id_1',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='removeFrom_st_id_1',
#                                  children=[]),
#                         MenuItem(name='Remove from st_id_2',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='removeFrom_st_id_2',
#                                  children=[]),
#                         MenuItem(name='Sync to all',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='addToAll',
#                                  children=[]),
#                         MenuItem(name='Sync to any',
#                                  type=MenuType.ACTION,
#                                  enabled=True,
#                                  actionId='RemoveAll',
#                                  children=[])]
#     expected_menu = [sr_menu, create_default_sharing_element(add_weblink=True)]
#
#     replacer = os.altsep or os.sep
#     assert dispatcher.getContextMenu([sync_root.replace('\\', replacer)]) == []
#
#     test_paths = [(sync_root.replace('\\', replacer) + "crosscloud")]
#     ctx_menu = dispatcher.getContextMenu(test_paths)
#     assert expected_menu == ctx_menu
#
#
# def test_convert_empty_array():
#     """tests that an empty array is transformed corrently into an empty string array"""
#     string_array = ipc_server.convert_path_strings([])
#     assert len(string_array) == 0
#
#     replacer = os.altsep or os.sep
#     string_array = ipc_server.convert_path_strings([sync_root.replace('\\', replacer)])
#     assert len(string_array) == 1
#     assert string_array[0] == ['']
#
#
# def test_context_menu_sync_root():
#     """tests that the ipc server does not return a menu for the root entry"""
#     csps = {'st_id_1': MagicMock(spec=[], storage_id='st_id_1', storage_name='Dropbox'),
#             'st_id_2': MagicMock(spec=[], storage_id='st_id_2', storage_name='GDrive')}
#     query_method = wrap_method_get({'st_id_1': ['crosscloud'], 'st_id_2':
# ['crosscloud']})
#     csps_getter = wrap_property_get([csps['st_id_1'], csps['st_id_2']])
#     sync_engine = MagicMock(spec=[], query_sync_rules=query_method, csps=csps_getter)
#     step = MagicMock(spec=[], storages=csps)
#
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#
#     replacer = os.altsep or os.sep
#     assert dispatcher.getContextMenu([sync_root.replace('\\', replacer)]) == []
#
#
# def test_sharing_link_action():
#     """
#     Test creation of sharing link.
#     """
#
#     sync_engine = MagicMock()
#     step = MagicMock()
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#     action_id = 'GenerateSharingLink'
#
#     # # test with empty paths
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id, selected_paths=[])
#     #
#     # # test with too many paths
#     # with pytest.raises(ValueError):
#     #     dispatcher.performAction(action_id=action_id,
#     #                              selected_paths=['a' + P_SEP + 'b',
#     #                                              'a' + P_SEP +
#     #                                              'e'])
#     #
#     # # test with no cps found
#     # sync_engine.query = MagicMock(return_value=MagicMock(props={STORAGE: {}}))
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id,
#     #                              selected_paths=['a' + P_SEP + 'b'])
#     #
#     # # test with no cps found with sharing link support
#     # csp = MagicMock(supports_sharing_link=False)
#     # step.get_storage = MagicMock(return_value=csp)
#     # sync_engine.query = MagicMock(return_value=MagicMock(props={STORAGE: {'a': csp}}))
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id, selected_paths=['a' + P_SEP +
#     #                                                                   'b'])
#
#     # test with SUCCUESS
#     csp = MagicMock(supports_sharing_link=True,
#                     create_public_sharing_link=MagicMock(return_value='sharing link'))
#     step.get_storage = MagicMock(return_value=csp)
#     sync_engine.query = wrap_method_get({STORAGE: {'a': csp}})
#
#     # copy mock
#     paste_mock = MagicMock()
#     with mock.patch("pyperclip.copy", new=paste_mock):
#         dispatcher.performAction(action_id=action_id, selected_paths=['a' + P_SEP +
#                                                                       'b'])
#
#     csp.create_public_sharing_link.assert_called_once_with(path=['a', 'b'])
#     paste_mock.assert_called_once_with('sharing link')
#
#
# def test_web_link_action():
#     """
#     Test creation of sharing link.
#     """
#
#     sync_engine = MagicMock()
#     step = MagicMock()
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#     action_id = 'ShowInWebAction'
#
#     # # test with empty paths
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id, selected_paths=[])
#     #
#     # # test with too many paths
#     # with pytest.raises(ValueError):
#     #     dispatcher.performAction(action_id=action_id,
#     #                              selected_paths=['a' + P_SEP + 'b',
#     #                                              'a' + P_SEP + 'e'])
#     #
#     # # test with no cps found
#     # sync_engine.query = wrap_method_get({STORAGE: {}})
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id,
#     #                              selected_paths=['a' + P_SEP + 'b'])
#     #
#     # # test with no cps found with web link support
#     # csp = MagicMock(supports_web_link=False)
#     # step.get_storage = MagicMock(return_value=csp)
#     # sync_engine.query = wrap_method_get({STORAGE: {'a': csp}})
#     # with pytest.raises(IndexError):
#     #     dispatcher.performAction(action_id=action_id,
#     #                              selected_paths=['a' + P_SEP + 'b'])
#
#     # test with SUCCUESS
#     csp = MagicMock(supports_web_link=True,
#                     create_web_link=MagicMock(return_value='web link'))
#     step.get_storage = MagicMock(return_value=csp)
#     sync_engine.query = wrap_method_get({STORAGE: {'a': csp}})
#
#     # browser mock
#     browser_mock = MagicMock()
#     with mock.patch("webbrowser.open", new=browser_mock):
#         dispatcher.performAction(action_id=action_id,
#                                  selected_paths=['a' + P_SEP + 'b'])
#
#     csp.create_web_link.assert_called_once_with(path=['a', 'b'])
#     browser_mock.assert_called_once_with('web link')
#
#
# @pytest.fixture()
# def init_sync_rule_action_test():
#     """
#     Initialises sync engine and step with csps and sync rules.
#     """
#     csps = {'st_id_1': MagicMock(spec=[], storage_id='st_id_1', storage_name='Dropbox'),
#             'st_id_2': MagicMock(spec=[], storage_id='st_id_2', storage_name='GDrive')}
#     all_storages = dict(csps)
#     all_storages[FILESYSTEM_ID] = MagicMock(spec=[],
#                                             storage_id=FILESYSTEM_ID,
#                                             storage_name='FS')
#
#     csps_getter = wrap_property_get([csps['st_id_1'], csps['st_id_2']])
#     query_method = wrap_method_get({SYNC_RULES: ['st_id_1', 'st_id_2']})
#     sync_engine = MagicMock(spec=['set_sync_rule'], query=query_method,
# csps=csps_getter)
#     step = MagicMock(spec=[], storages=all_storages)
#
#     dispatcher = Dispatcher(step=step, sync_engine=sync_engine)
#
#     return_type = namedtuple('InitSRTest', 'dispatcher sync_engine step csps')
#     return return_type(dispatcher=dispatcher,
#                        sync_engine=sync_engine,
#                        step=step,
#                        csps=csps)
#
#
# def test_remove_all_sync_rules(init_sync_rule_action_test):
#     """
#     Tests removal of all sync rules.
#     """
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b').replace(os.sep, P_SEP),
#                       os.path.join(sync_root, 'b', 'c').replace(os.sep, P_SEP)]
#
#     dispatcher.performAction(action_id=ACTION_REMOVE_ALL, selected_paths=selected_paths)
#
#     # check calls
#     sync_engine.set_sync_rule.assert_any_call(path=['a', 'b'], csps=[])
#     sync_engine.set_sync_rule.assert_any_call(path=['b', 'c'], csps=[])
#
#
# def test_add_to_all_sync_rules(init_sync_rule_action_test):
#     """
#     Tests add all sync rules.
#     """
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b'),
#                       os.path.join(sync_root, 'b', 'c')]
#
#     dispatcher.performAction(action_id=ACTION_ADD_TO_ALL, selected_paths=selected_paths)
#
#     # check calls
#     sync_engine.set_sync_rule.call_count = 2
#
#
# def test_add_sync_rule(init_sync_rule_action_test):
#     """
#     Test adding of sync rules.
#     """
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#     sync_engine.query = wrap_method_get({SYNC_RULES: ['st_id_1']})
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b').replace(os.sep, P_SEP),
#                       os.path.join(sync_root, 'b', 'c').replace(os.sep, P_SEP)]
#
#     action_id = ACTION_ADD_TO_PREFIX + 'st_id_2'
#     dispatcher.performAction(action_id=action_id, selected_paths=selected_paths)
#
#     expected_rules = ['st_id_1', 'st_id_2']
#     sync_engine.set_sync_rule.assert_any_call(path=['a', 'b'], csps=expected_rules)
#     sync_engine.set_sync_rule.assert_any_call(path=['b', 'c'], csps=expected_rules)
#
#
# def test_adding_existing_rule(init_sync_rule_action_test):
#     """
#     Test adding of existing rule.
#     """
#
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b'),
#                       os.path.join(sync_root, 'b', 'c')]
#
#     # call with existing id
#     action_id = ACTION_ADD_TO_PREFIX + 'st_id_2'
#     dispatcher.performAction(action_id=action_id, selected_paths=selected_paths)
#
#     assert sync_engine.set_sync_rule.call_count == 0
#
#
# def test_remove_sync_rule(init_sync_rule_action_test):
#     """
#     Test removing of sync rules.
#     """
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b').replace(os.sep, P_SEP),
#                       os.path.join(sync_root, 'b', 'c').replace(os.sep, P_SEP)]
#
#     # test invalid csp
#     # with(pytest.raises(ValueError)):
#     #     action_id = ACTION_REMOVE_FROM_PREFIX + 'wrong_id'
#     #     dispatcher.performAction(action_id=action_id, selected_paths=selected_paths)
#
#     action_id = ACTION_REMOVE_FROM_PREFIX + 'st_id_2'
#     dispatcher.performAction(action_id=action_id, selected_paths=selected_paths)
#
#     expected_rules = ['st_id_1']
#     sync_engine.set_sync_rule.assert_any_call(path=['a', 'b'], csps=expected_rules)
#     sync_engine.set_sync_rule.assert_any_call(path=['b', 'c'], csps=expected_rules)
#
#
# def test_remove_non_existing_rule(init_sync_rule_action_test):
#     """
#     Test removal of non existing rule.
#     """
#
#     sync_engine = init_sync_rule_action_test.sync_engine
#     dispatcher = init_sync_rule_action_test.dispatcher
#     query_method = MagicMock(return_value=MagicMock(props={SYNC_RULES: ['st_id_1']}))
#     sync_engine.query = query_method
#
#     selected_paths = [os.path.join(sync_root, 'a', 'b'),
#                       os.path.join(sync_root, 'b', 'c')]
#
#     # call with existing id
#     action_id = ACTION_REMOVE_FROM_PREFIX + 'st_id_2'
#     dispatcher.performAction(action_id=action_id, selected_paths=selected_paths)
#
#     assert sync_engine.set_sync_rule.call_count == 0
#
#
# def test_current_syncing_paths():
#     """
#     Test getter of current syncing paths.
#     """
#
#     active_paths = [['a', 'b'], ['a', 'c'], ['c']]
#     active_tasks = [MagicMock(spec=[], path=path) for path in active_paths]
#     step = MagicMock(spec=[], get_active_tasks=MagicMock(return_value=active_tasks))
#
#     dispatcher = Dispatcher(step=step, sync_engine=MagicMock(spec=[]))
#
#     # get active paths of a
#     full_path_a = os.path.join(sync_root, 'a').replace(os.sep, P_SEP)
#     active_paths_ret = dispatcher.getCurrentlySyncingPathsForDirectories([full_path_a])
#
#     assert os.path.join(sync_root, 'a', 'b') in active_paths_ret
#     assert os.path.join(sync_root, 'a', 'c') in active_paths_ret
#
#     # get active paths of c
#     full_path_a = os.path.join(sync_root, 'c').replace(os.sep, P_SEP)
#     active_paths_ret = dispatcher.getCurrentlySyncingPathsForDirectories([full_path_a])
#
#     assert os.path.join(sync_root, 'c') in active_paths_ret
#
#     # get active paths of d should be empty
#     full_path_a = os.path.join(sync_root, 'd').replace(os.sep, P_SEP)
#     active_paths_ret = dispatcher.getCurrentlySyncingPathsForDirectories([full_path_a])
#
#     assert not active_paths_ret
#
#     # test root with appended separator
#     root_path = os.path.join(sync_root).replace(os.sep, P_SEP) + P_SEP
#     active_paths_ret = dispatcher.getCurrentlySyncingPathsForDirectories([root_path])
#     assert os.path.join(sync_root, 'a', 'b') in active_paths_ret
#     assert os.path.join(sync_root, 'a', 'c') in active_paths_ret
#     assert os.path.join(sync_root, 'c') in active_paths_ret
#
#     # test root without appended separator
#     root_path = os.path.join(sync_root).replace(os.sep, P_SEP)
#     active_paths_ret = dispatcher.getCurrentlySyncingPathsForDirectories([root_path])
#     assert os.path.join(sync_root, 'a', 'b') in active_paths_ret
#     assert os.path.join(sync_root, 'a', 'c') in active_paths_ret
#     assert os.path.join(sync_root, 'c') in active_paths_ret
#
#
# def test_invalid_action_id():
#     """
#     Tests invalid action id.
#     """
#     dispatcher = Dispatcher(step=MagicMock(spec=[]), sync_engine=MagicMock(spec=[]))
#     dispatcher.performAction(action_id='invalid', selected_paths=[])
#
#
# # --------------------------------
# # ---------- helper --------------
# # --------------------------------
#
#
# def create_default_sharing_element(add_weblink=False):
#     """
#     creates element for default sharing
#     """
#     sharing_element = MenuItem(name='Sharing',
#                                type=MenuType.POPUP,
#                                enabled=True,
#                                children=[],
#                                actionId='')
#     sharing_element.children = [MenuItem(name='Generate Public Sharing Link',
#                                          enabled=True,
#                                          type=MenuType.ACTION,
#                                          actionId='GenerateSharingLink',
#                                          children=[])]
#     if add_weblink:
#         sharing_element.children.append(MenuItem(name='Display in Browser',
#                                                  type=MenuType.ACTION,
#                                                  enabled=True,
#                                                  actionId='ShowInWebAction',
#                                                  children=[]))
#     return sharing_element
#
#
# def wrap_method_get(to_wrap):
#     """
#     wraps function in get
#     """
#     return MagicMock(return_value=MagicMock(get=MagicMock(return_value=to_wrap)))
#
#
# def wrap_property_get(to_wrap):
#     """
#     wraps property in get
#     """
#     return MagicMock(spec=[], get=MagicMock(return_value=to_wrap))
