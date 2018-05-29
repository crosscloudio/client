"""This module provides the building blocks for the config object.

The following functionality is implemented:

    * Values can be assigned to keys in the config
    * Values can be retrieved from the config
    * Objects can subscribe to changes at a key.

Create a new config
-------------------
Setup a simple config with four entry:

>>> from cc.configuration.models import Config
>>> config = Config()
>>> config.my_int = 12
>>> config.my_str = 'something'
>>> config.my_list = []
>>> config.my_dict = {}

To retrieve the subscribable config item call:

>>> config.item('my_int')
config.my_int: 12

Subscribing to changes
----------------------

>>> from pprint import pprint
>>> def handler(sender, **kwargs):
...     print('handler recieved:')
...     print(sender)
...     pprint(kwargs)

Subscribe to an int
===================
>>> config.sub('my_int', handler)
>>> config.my_int = 13
handler recieved:
config.my_int: 13
{'name': 'my_int', 'value': 13}

Subscribe to a list
===================
>>> config.sub('my_list', handler)
>>> config.my_list.append('new_thing')

handler recieved:
config.my_list: ['new_thing']
{'operation': 'append', 'value': 'new_thing'}

>>> config.my_list.remove('new_thing')

handler recieved:
config.my_list: []
{'operation': 'remove', 'value': 'new_thing'}

Subscribe to a dict
===================
>>> config.sub('my_dict', handler)
>>> config.my_dict['new_key'] = 'new_thing'

handler recieved:
config.my_dict: {'new_key': 'new_thing'}
{'key': 'new_key', 'operation': 'set', 'value': 'new_thing'}

>>> del config.my_dict['new_key']

handler recieved:
config.my_dict: {}
{'key': 'new_key', 'operation': 'del', 'value': 'new_thing'}

"""
import logging
import types
import copy

import blinker

logger = logging.getLogger(__name__)


class ConfigValidationException(Exception):
    """Exception which is raise when a config item is unable set a value due to a validation error.
    """
    pass


class ConfigItemTypeError(Exception):
    """Raises when setting a config item would change its type.
    """
    pass


class ConfigItem:
    """Single key value pair with subscription."""
    default = None

    def __init__(self, name=None, value=None):
        if value is None:
            value = copy.deepcopy(self.default)
        self._signal = blinker.Signal()
        self._name = name
        self._value = value
        self._secure = False

    def __repr__(self):
        if self._secure:
            # prevent accidentaly logging value
            value = '***secure***'
        else:
            value = repr(self._value)
        return 'config.%s: %s' % (self._name, value)

    def __index__(self):
        return self.value

    def __getattr__(self, func_name):
        return self._value.__getattribute__(func_name)

    def __getitem__(self, item):
        return self.value[item]

    @property
    def value(self):
        """return the real property."""
        return self._value

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._value.__eq__(other.value)
        else:
            return self._value.__eq__(other)

    @value.setter
    def value(self, value):
        """Set the value and publish the changes."""
        try:
            # self.type_check(value)
            value = self.validate(value)
        except (ConfigValidationException, ConfigItemTypeError) as error:
            logger.warning('Unable to set %s=%s: (%s)', self, value, error)
            return

        self._value = value
        self._signal.send(self, name=self._name, value=value)

    def type_check(self, value):
        """Ensure that changing value does not change the type."""
        if not isinstance(value, type(self._value)):
            raise ConfigItemTypeError

    # pylint: disable=no-self-use
    def validate(self, value):
        """Return the validated value or raise ConfigValidationException to prevent setting value.

        This method is meant to be provided by a subclass as a hook prior to setting a value.
        It can:
            - modify the value, ie.: parse string to datetime
            - reject value by raising ConfigValidationException
            - return the same value.
        """
        return value
    # pylint: enable=no-self-use

    def sub(self, handler):
        """Subscribe to changes on this item"""
        self._signal.connect(handler)


class ConfigInt(ConfigItem):
    """Integer configuration item."""

    def __sub__(self, other):
        if isinstance(other, self.__class__):
            other = other.value
        return self._value.__sub__(other)

    def __add__(self, value):
        if isinstance(value, self.__class__):
            return self._value.__add__(value.value)
        return self._value.__add__(value)

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self._value.__lt__(other.value)
        else:
            return self._value.__lt__(other)

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self._value.__gt__(other.value)
        else:
            return self._value.__gt__(other)

    def __mul__(self, other):
        if isinstance(other, self.__class__):
            return self._value.__mul__(other.value)
        else:
            return self._value.__mul__(other)


class ConfigStr(ConfigItem):
    """String which is subscripatable."""
    default = ''

    def __str__(self):
        return self.value


class ConfigList(ConfigItem):
    """List of configurations

    Allow subscribing to adding and removal of items from the list
    """
    default = []

    def append(self, value):
        """Append an value and publish to subscribers."""
        self._value.append(value)
        self._signal.send(self, operation='append', value=value)

    def remove(self, value):
        """Remove an value and publish to subscribers."""
        self._value.remove(value)
        self._signal.send(self, operation='remove', value=value)

    def __iter__(self):
        return self._value.__iter__()

    def __len__(self):
        return len(self._value)


class ConfigDict(ConfigItem):
    """Dict of configurations

    Allow subscribing to adding and removing of items from the dict
    """
    default = dict()

    def __setitem__(self, key, value):
        self._value[key] = value
        self._signal.send(self, operation='set', key=key, value=value)

    def __getitem__(self, key):
        item = self._value[key]
        return item.value

    def __contains__(self, key):
        return key in self.value

    def __delitem__(self, key):
        value = self._value[key]
        del self._value[key]
        self._signal.send(self, operation='del', key=key, value=value)

# pylint: disable=too-many-instance-attributes


class Config:
    """Collection of current configurations.

    Example
    -------
    >>> config = Config()
    >>> config.my_key = 12
    >>> config.my_key
    12
    """
    class_mapping = {
        dict: ConfigDict,
        list: ConfigList,
        int: ConfigInt,
        str: ConfigStr
    }

    def __setattr__(self, name, value):
        """Wrap items in the required calls when setting."""
        try:
            item = self.__dict__[name]
            item.value = value
        except KeyError:
            # use class_mapping or default to simple ConfigItem
            value_type = type(value)
            cls = self.class_mapping.get(value_type, ConfigItem)
            if isinstance(value, ConfigItem):
                # Do not double wrap
                item = value
            elif callable(value):
                item = types.MethodType(value, self)
            else:
                item = cls(name, value)

        object.__setattr__(self, name, item)

    def __getattribute__(self, name):

        item = object.__getattribute__(self, name)
        if isinstance(item, ConfigItem):
            return item.value
        else:
            return item

    def __contains__(self, name):
        return name in self.__dict__

    def item(self, name):
        """Return full ConfigItem."""
        return object.__getattribute__(self, name)

    def sub(self, name, handler):
        """Subscribe to a item by name with the provided handler."""
        item = self.item(name)
        item.sub(handler)
