"""CrossCloud Test Package"""
import socket

import gc

import mock

__author__ = 'CrossCloud GmbH'


def assert_args(call_args, *args, **kwargs):
    """Checks if args contain elements in args and kwargs"""
    c_args, c_kwargs = call_args

    # check positional args
    for arg in args:
        assert arg in c_args

    # check keyword args
    for name, value in kwargs.items():
        assert c_kwargs[name] == value


def any_args(call_arg_list, *args, **expected_args):
    """
    Checks if arg list contains elements in args and kwargs
    """
    for call_args in call_arg_list:
        c_args, c_kwargs = call_args

        # check positional args
        c_args_match = all((arg in c_args for arg in args))

        # check keyword args
        c_kargs_match = all(
            (c_kwargs[karg] == value for karg, value in expected_args.items()))

        if c_args_match and c_kargs_match:
            return True
    return False


class GoOffline:
    """
    With Block for set system to offline
    This disables pythons DNS resolution
    and kills all tcp connections
    """

    # pylint: disable=no-member, redefined-builtin
    def __init__(self):
        self.patcher1 = None
        self.patcher2 = None

    def __enter__(self):
        # patching socket name resolution
        # to RFC TEST-NET-1
        # https://tools.ietf.org/html/rfc5737
        new_return_1 = mock.MagicMock(return_value='192.0.2.1')
        new_return_2 = mock.MagicMock(return_value=[(socket.AddressFamily.AF_INET,
                                                     socket.SocketKind.SOCK_STREAM,
                                                     6,
                                                     '',
                                                     ('192.0.2.1', 80))])
        self.patcher1 = mock.patch('socket.gethostbyname', new=new_return_1)
        self.patcher2 = mock.patch('socket.getaddrinfo', new=new_return_2)
        self.patcher1.start()
        self.patcher2.start()

        # kill all connections
        # for sock in gc.get_objects():
        #     if isinstance(sock, socket.socket):
        #         sock.shutdown(socket.SHUT_WR)
        #         sock.close()

    def __exit__(self, type, value, traceback):
        self.patcher1.stop()
        self.patcher2.stop()


def print_model(model):
    """
    Prints model
    """

    for node in model:
        print(node.path, node.props)


class WeakComparingDict:
    """ Weak compare for dicts
    Can be used to compare a dict with another one where it is not forced to be completely
    equal. Example:
    WeakComparingDict({'a': 'b'}) == {'a': 'b', 'c': 'd'} returns True
    WeakComparingDict({'a': 'b'}) == {'c': 'd'} returns False
    So this enforces that all elements of the WeakComparingDict are also in the other dict
    but not vice versa.
    """

    def __init__(self, the_dict):
        self._the_dict = the_dict

    def __getattr__(self, item):
        """regular getattr"""
        return getattr(self._the_dict, item)

    def __eq__(self, other):
        if not isinstance(other, dict):
            return False
        for key in self._the_dict.keys():
            if key not in other:
                return False
            if other[key] != self._the_dict[key]:
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return repr(self._the_dict)


def test_weak_comparing_dict():
    """Basic test of WeakComparingDict"""
    assert WeakComparingDict({'a': 'b'}) == {'a': 'b', 'c': 'd'}
    assert WeakComparingDict({'a': 'b'}) != {'c': 'd'}
