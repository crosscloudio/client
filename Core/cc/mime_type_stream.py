"""Module containing helpers to operate with file objects."""
import io
import typing

import magic


class MimeTypeDetectingFileObject(io.RawIOBase):
    """File like class which tries to detect the mimetime as soon as enough data is availabe."""

    def __init__(self, orig_obj: io.RawIOBase,
                 detection_callback: typing.Callable[[str], None], max_buffer_size: int=1024):
        """Init.

        :param orig_obj: the file object to wrap
        :param detection_callback: a function pointer taking a string as argument, called if either
               the max_buffer_size has been read or the file has ended before.
        :param max_buffer_size: maximum data collected to pass to magic
        """
        super().__init__()
        self._orig_obj = orig_obj
        self.read_count = 0

        self.max_buffer_size = max_buffer_size

        # this buffer stores the bytes
        self.buffer = b''

        self.detection_callback = detection_callback
        self.called_back = False

    def read(self, count=None):
        """Pass the read to the orig_obj and tries to find out the mime-type."""
        buffer = self._orig_obj.read(count)

        if len(self.buffer) < self.max_buffer_size and not self.called_back:
            # lets add the buffer
            self.buffer += buffer

        if (len(self.buffer) >= self.max_buffer_size or len(
                buffer) != count) and not self.called_back:
            self.detection_callback(magic.from_buffer(self.buffer, mime=True))
            self.called_back = True
            self.buffer = b''
        return buffer
