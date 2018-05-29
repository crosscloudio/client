"""Test the cc.synchronization.models modules"""
# pylint: disable=redefined-outer-name

from unittest.mock import Mock

import pytest

from cc.synchronization.models import SynchronizationGraph
from cc.synchronization.syncengine import SyncEngineState


def link_engine_mock_with_state(state):
    """Return a fake link with a fake angine with the given state"""
    link = Mock(spec=['engine'])
    link.engine = Mock(spec=['state'])
    link.engine.state.get = Mock(return_value=state)
    return link


@pytest.fixture
def graph_with_link_engine_state():
    """Return a fake graph with fake links and fake engines to test state aggregation"""
    sync_graph = SynchronizationGraph(sync_root=None,
                                      bademeister=None,
                                      periodic_state_saver=None)
    sync_graph.links = {num: link_engine_mock_with_state(SyncEngineState.RUNNING)
                        for num in range(3)}
    return sync_graph


def test_aggregate_state_running(graph_with_link_engine_state):
    """Test if all is RUNNING it returns RUNNING"""
    assert graph_with_link_engine_state.aggregate_state() == SyncEngineState.RUNNING


def test_aggregate_state_paused(graph_with_link_engine_state):
    """Test if one is PAUSED it returns PAUSED"""
    graph_with_link_engine_state.links[4] = link_engine_mock_with_state(SyncEngineState.STOPPED)
    assert graph_with_link_engine_state.aggregate_state() == SyncEngineState.STOPPED


def test_aggregate_state_initalized(graph_with_link_engine_state):
    """Test if one is STATE_SYNC it returns STATE_SYNC"""
    graph_with_link_engine_state.links[4] = link_engine_mock_with_state(
        SyncEngineState.STATE_SYNC)
    assert graph_with_link_engine_state.aggregate_state() == SyncEngineState.STATE_SYNC
