"""Test the configuration module.

These testcases use hypothesis to produce a large number of testcases.
Various composite strategies are implemented to create usefull sets of data with which
to test.


The documentation of these strategies contains exaples which are not meant to demonstrate
the output produced. These are not to be understood as doctests, since the actual
output is random.

.. seealso:: http://hypothesis.readthedocs.io/en/latest/index.html
"""
import logging
from unittest import mock

import pytest
from hypothesis import strategies as st
from hypothesis import given, settings, assume

from cc.configuration import models

logger = logging.getLogger(__name__)
INTEGERS = st.integers()
TEXT = st.text()
DICTS = st.dictionaries(keys=st.text(), values=(st.integers()))
LISTS = st.lists(elements=st.integers())

BASE_STRATEGIES = [INTEGERS, TEXT, DICTS, LISTS]


@st.composite
def one_of_a_kind(draw):
    """Select one of the value startegies and draw two values from each.

    Sample Output
    -------------
    >>> one_of_a_kind().example()
    12
    >>> one_of_a_kind().example()
    'some_test'
    >>> one_of_a_kind().example()
    [1,9, 809]
    """
    kind = draw(st.sampled_from(BASE_STRATEGIES))
    value_1 = draw(kind)
    return (value_1, kind)


@st.composite
def two_of_a_kind(draw):
    """Select one of the value startegies and draw two values from each.

    The resulting tuple also contains the strategy used to produce the values.

    Sample Output
    -------------
    >>> two_of_a_kind().example()
    ('some text', 'some other test', TEXT)
    >>> two_of_a_kind().example()
    ({'asd':12}, {'mokey':12}, DICTS)
    """
    kind = draw(st.sampled_from(BASE_STRATEGIES))
    value_1 = draw(kind)
    value_2 = draw(kind)
    return (value_1, value_2, kind)


@st.composite
def two_of_different_kinds(draw):
    """Select two different kinds of strategies.

    Sample Output
    -------------
    >>> two_of_different_kinds.example()
    ('some text', {'asd':12} , TEXT, DICT)
    >>> two_of_different_kinds.example()
    (12, [1,12,9], INTEGERS, LISTS)
    """
    kind_1 = draw(st.sampled_from(BASE_STRATEGIES))
    kind_2 = draw(st.sampled_from(BASE_STRATEGIES).filter(lambda x: x != kind_1))
    value_1 = draw(kind_1)
    value_2 = draw(kind_2)
    return (value_1, value_2, kind_1, kind_2)


@settings(perform_health_check=False)
@given(value=one_of_a_kind())
def test_class_mapping(value, config):
    """Set a value. Check that it is wrapped correctly and value returns correctly.

    This test does not use the config fixture, because various Config types are set to the
    same key, `attr_name`.
    """
    value, kind = value
    config.attr_name = value
    assert isinstance(config.item('attr_name'), models.ConfigItem)
    assert config.attr_name == value

    if kind == DICTS:
        assert isinstance(config.attr_name, dict)

    if kind == LISTS:
        assert isinstance(config.attr_name, list)


# @settings(perform_health_check=False)
# @given(values=two_of_different_kinds())
# def test_raise_for_wrong_type(values):
#     """Once a config item is set, it's type cannot not be changed."""
#     value_1, value_2, _, _ = values
#     config.some_key = value_1
#     with pytest.raises(models.ConfigItemTypeError):
#         config.some_key.type_check(value_2)

#     # this fails
#     config.some_key = value_2
#     assert config.some_key.value == value_1


def only_different_values(values):
    """Return true if first and second value are not the same."""
    return values[0] != values[1]


@settings(perform_health_check=False)
@given(values=two_of_a_kind().filter(only_different_values))
def test_subscribe_handle(subscriber, values, config):
    """Set a value, subscribe to changes, change value and assert that handler was called."""
    pytest.skip('not yet implemented')
    value_1, value_2, _ = values
    # fig = models.Config()
    config.some_key = value_1
    config.some_key.sub(subscriber.handler)
    config.some_key = value_2

    assert config.some_key.value == value_2
    expected_call = {'name': 'some_key',
                     'value': value_2}
    subscriber.mock.assert_called_with(mock.ANY, **expected_call)


@settings(max_examples=1)
@given(list=LISTS)
@given(value=INTEGERS)
def test_subscribe_list_append(subscriber, value, list, config):
    """Subscribe to a list, and an item, assert that the handler is called."""
    pytest.skip('not yet implemented')
    config.some_list = list
    # assert isinstance(config.some_list, models.ConfigList)
    config.some_list.sub(subscriber.handler)
    config.some_list.append(value)
    expected_call = {'value': value,
                     'operation': 'append'}
    subscriber.mock.assert_called_with(mock.ANY, **expected_call)

# @settings(max_examples=1)


@given(list=LISTS, value=INTEGERS)
def test_subscribe_list_remove(subscriber, value, list, config):
    """Subscribe to a list, and an item, assert that the handler is called."""
    pytest.skip('not yet implemented')
    config.some_list = list
    config.some_list.append(value)
    # assert isinstance(config.some_list, models.ConfigList)
    config.some_list.sub(subscriber.handler)
    config.some_list.remove(value)
    expected_call = {'value': value,
                     'operation': 'remove'}
    subscriber.mock.assert_called_with(mock.ANY, **expected_call)

# @settings(max_examples=1)


@given(key=TEXT, value=one_of_a_kind(), dictionary=DICTS)
def test_subscribe_dict_add(subscriber, key, value, dictionary, config):
    """Subscribe to a dict, remove an item, assert that the handler is called."""
    pytest.skip('not yet implemented')
    assume(len(key) > 0)
    value, _ = value
    config.some_dict = dictionary
    assert isinstance(config.some_dict, models.ConfigDict)
    config.some_dict.sub(subscriber.handler)
    config.some_dict[key] = value
    expected_call = {'value': value, 'key': key, 'operation': 'set'}
    subscriber.mock.assert_called_with(mock.ANY, **expected_call)


@settings(max_examples=1)
@given(key=TEXT, value=one_of_a_kind(), dictionary=DICTS)
def test_subscribe_dict_del(subscriber, key, value, dictionary, config):
    """Subscribe to a dict, remove an item, assert that the handler is called."""
    pytest.skip('not yet implemented')
    assume(len(key) > 0)
    value, _ = value
    config.some_dict = dictionary
    assert isinstance(config.some_dict, models.ConfigDict)
    config.some_dict[key] = value
    config.some_dict.sub(subscriber.handler)
    del config.some_dict[key]
    expected_call = {'value': value, 'key': key, 'operation': 'del'}
    subscriber.mock.assert_called_with(mock.ANY, **expected_call)


@given(value_1=INTEGERS, value_2=INTEGERS)
def test_int_add(value_1, value_2, config):
    """Test that ConfigInts can be added as expected."""
    total = value_1 + value_2
    config.value_1 = value_1
    config.value_2 = value_2
    assert config.value_1 + value_2 == total
    assert config.value_2 + config.value_1 == total
    assert value_1 + config.value_2 == total


@given(value_1=INTEGERS, value_2=INTEGERS)
def test_int_sub(value_1, value_2, config):
    """Test that ConfigInts can be subtracted as expected."""
    diff = value_1 - value_2
    config.key_1 = value_1
    config.key_2 = value_2

    assert config.key_1 - value_2 == diff
    assert config.key_1 - config.key_2 == diff
    assert value_1 - config.key_2 == diff
