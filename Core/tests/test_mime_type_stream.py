"""Tests for streaming utils"""

import io
from unittest.mock import Mock

from cc.mime_type_stream import MimeTypeDetectingFileObject

EXAMPLE_HTML = b'''<html>
<head>
<title> Helloees </title>
</head>
</html>
'''


def test_recoginze_html():
    """Test if it can recognize html from the stream. As a whole peace."""
    raw_stream = io.BytesIO(EXAMPLE_HTML)
    callback_mock = Mock()
    mimetype_detector = MimeTypeDetectingFileObject(raw_stream, detection_callback=callback_mock)

    assert mimetype_detector.read() == EXAMPLE_HTML

    callback_mock.assert_called_with('text/html')
    callback_mock.reset_mock()

    # check if it can be called again without calling the callback
    assert mimetype_detector.read() == b''

    assert not callback_mock.called


def test_empty_file_multiple_read():
    """Test if it can recognize html from the stream. Small pieces."""
    raw_stream = io.BytesIO()
    callback_mock = Mock()
    mimetype_detector = MimeTypeDetectingFileObject(raw_stream, detection_callback=callback_mock)

    assert mimetype_detector.read() == b''
    assert mimetype_detector.read() == b''
    assert mimetype_detector.read() == b''

    callback_mock.assert_called_once_with('application/x-empty')


def test_recoginze_bytewise():
    """Test if it can recognize html from the stream, if read bytewise."""
    raw_stream = io.BytesIO(EXAMPLE_HTML)
    callback_mock = Mock()
    mimetype_detector = MimeTypeDetectingFileObject(raw_stream, detection_callback=callback_mock)

    while True:
        if not mimetype_detector.read(1):
            break

    callback_mock.assert_called_once_with('text/html')
    callback_mock.reset_mock()

    # check if it can be called again without calling the callback
    assert mimetype_detector.read() == b''

    assert not callback_mock.called


def test_recoginze_maxx_buffer():
    """Test if max_buffer is kept"""
    raw_stream = io.BytesIO(EXAMPLE_HTML)
    callback_mock = Mock()
    mimetype_detector = MimeTypeDetectingFileObject(raw_stream, detection_callback=callback_mock,
                                                    max_buffer_size=20)

    mimetype_detector.read(10)
    assert not callback_mock.called
    mimetype_detector.read(9)
    assert not callback_mock.called
    mimetype_detector.read(1)

    # check if the buffer is flushed
    assert mimetype_detector.buffer == b''

    callback_mock.assert_called_once_with('text/html')
    callback_mock.reset_mock()

    assert not callback_mock.called
