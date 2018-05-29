"""A module to keep various small pieces of reusable code.

Please ensure that all functions in this module have at least doctests in order to enable
reuseability.
"""

import logging
logger = logging.getLogger(__name__)


def humanize_byte(nbytes):
    """Format a filesize to human readable format.

    Example
    -------
    >>> humanize_byte(0)
    '0 B'
    >>> humanize_byte(10)
    '10 B'
    >>> humanize_byte(1E4)
    '9.77 kB'
    >>> humanize_byte(1E9)
    '953.67 MB'
    >>> humanize_byte(1E12)
    '931.32 GB'
    """
    suffixes = ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    if nbytes == 0:
        return '0 B'

    suffix_index = 0
    while nbytes >= 1024 and suffix_index < len(suffixes) - 1:
        nbytes /= 1024.
        suffix_index += 1
    str_rep = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (str_rep, suffixes[suffix_index])


def current_storage_props(config, registered_storages):
    """Return the dict of the currently enabled storages and their auth.

    Currently this only adds the enabled flag to the registered_storages.

    TODO: This should live in jars and be combined with registered_storages, which then returns a
    dict with the required elements for various calls.
    """
    storage_list = []
    enabled = None
    for storage in registered_storages:
        logger.debug('Filtering enabled storages.')
        # decide if the storage should be enabled or disabled
        if storage.storage_name in config.enabled_storage_types:
            enabled = True
        else:
            enabled = False
            logger.debug('Storage %s disabled', storage.storage_name)
        storage_list.append({'name': storage.storage_name,
                             'display_name': storage.storage_display_name,
                             'auth': storage.auth,
                             'enabled': enabled})

    return sorted(storage_list, key=lambda storage: storage['display_name'])
