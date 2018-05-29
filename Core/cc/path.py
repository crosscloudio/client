"""
Utiliy module for path
"""
import unicodedata

__author__ = "Johannes Innerbichler"


def normalize_path_element(elem):
    """
    Normalizes a path element to the internal representations
    :param elem: string
    :return: the normalized string
    """
    return unicodedata.normalize('NFKD', elem.casefold())


def rename_file(original_name, new_name):
    """
    This is a string operation to rename a file with extension, it takes care if a file
    has an extension.

    With an extension it looks like this:

    >>> rename_file('hello.txt', 'test')
    'test.txt'

    It also works without extension:

    >>> rename_file('hello', 'test')
    'test'

    >>> rename_file('hello.bla.txt', 'test')
    'test.txt'

    :param original_name: the filename to be renamed
    :param new_name: the new name
    :return: str
    """
    if '.' in original_name:
        _, extension = original_name.rsplit('.', 1)
        return '{}.{}'.format(new_name, extension)
    else:
        return new_name
