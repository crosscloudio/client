"""Mainly helper functions for the tests inside this package."""
from unittest import mock


def dummy_link_with_id(link_id):
    """Create a dummy link with a given link_id."""
    from cc.synchronization.models import SynchronizationLink
    link_mock = mock.Mock(spec=SynchronizationLink)
    link_mock.link_id = link_id
    return link_mock
