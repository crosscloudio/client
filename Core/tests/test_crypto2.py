""" tests the cc.crypto2 - the asymmentric encryption for cc"""

# pylint:disable=redefined-outer-name
import io
import json
import struct

import pytest

from cc.crypto2 import EncryptionFileWrapper, DecryptionFileWrapper, create_header, \
    MAGIC_NUMBER, read_header, HeaderError, AES_IV_LENGTH, calc_header_size, RSA_KEY_LENGTH

EXAMPLE_KEYPAIR_PUB = b'''-----BEGIN RSA PUBLIC KEY-----
MIICCgKCAgEAvq6bVq54aNBnnJw785jJSaSyUyKaGM8arj+AolSpa9Tjgp79ftoH
YDmLAW4iNf6t29Yh/yhiQ2wtJXAuli/IdJgLjy/W5YO0D2k+PwbLsHMd+dYm/s1W
PcK7DEvb/ToFfrJ9j2Aq/+O1U1RsT1WiGnDpaEDJEzWHxxsI3rSTRqoajZbTUtDi
J0/Y2H+YNuF0bzkJIW0G0g+NEkxKW/0W8rtEuXqFV7CDfXvNIMQZEX3ZqGN/T5hi
12CPgITyEcvPgwnyqCcC2QL07cGCAPAzAxbsp+gWLC44rQN7IorX6O3LeEWMcJJD
CwJpFJOaGDP/K9IWspoyksDxR4WRpqOtFtowi8jCs55+6DuyjwirGY0BXgT4phXf
EpOUj70rNk9sQ9qkJG8YvNlXuaRU7wHCjCwvlfBrI4KQJ25ZjdKNJqJCeJcgaWpX
B74/w+jSd4UG2u0GFuKwRONy2B+qmhfUoDki/0WAR8tkgvzw6LL7dpcokoxK+1Vr
UOMi4Xb5mfCkoxJPy/5bOOOwIxMW6ryDOKHyfyqTqCH8PU8Ps5jc8EEyClxDosYq
aEqSIDamyytSwc4VLflrS2MLdOV2WG2RUwhIIW/EtR10YCbysSdE3q0V8NBm6r8a
QtBJR1kCBBA4H1tZSPIZAPvCzCs3cF9iElJRL1aAL7GP8WICm7q0DUcCAwEAAQ==
-----END RSA PUBLIC KEY-----'''

EXAMPLE_KEYPAIR_PRIVATE = b'''-----BEGIN PRIVATE KEY-----
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
7NQdmXnhSRMXBLiFTu8lhUnD0x0r/mU=
-----END PRIVATE KEY-----'''

FILE_KEY = b'A SECRET PASSWORD IS HERE SERVED'
EXAMPLE_PLAINTEXT = b'hello my friend, this is bob, is there alice?'


@pytest.fixture
def encrypting_file_wrapper():
    """ returns an encrypting file wrapper with EXAMPLE_PLAINTEXT"""
    example = io.BytesIO(EXAMPLE_PLAINTEXT)

    return EncryptionFileWrapper(example, {'bob': EXAMPLE_KEYPAIR_PUB},
                                 file_key=FILE_KEY)


@pytest.mark.parametrize("read_patterns", [range(100), [1, 2, 3, 4, 5, 6, 7, 8, 9], [100],
                                           [None]])
def test_enc_readall(encrypting_file_wrapper, read_patterns):
    """ Tests if readall returns a ciphertext in the same length as the plaintext """
    # skip magic number and version
    encrypting_file_wrapper.read(len(MAGIC_NUMBER))

    # read size of the header
    header_size, = struct.unpack('<I', encrypting_file_wrapper.read(4))

    encrypting_file_wrapper.read(header_size)

    cypher_text_parts = []

    for pattern in read_patterns:
        cypher_text_parts.append(encrypting_file_wrapper.read(pattern))

    cypher_text = b''.join(cypher_text_parts)

    assert len(EXAMPLE_PLAINTEXT) == len(cypher_text)


@pytest.mark.parametrize("read_patterns", [range(100), [1, 2, 3, 4, 5, 6, 7, 8, 9], [100],
                                           [None]])
def test_dec_enc(encrypting_file_wrapper, read_patterns):
    """ Tests if encrypt decrypt is working """
    # skip magic number and version
    enc_file = io.BytesIO(encrypting_file_wrapper.read())

    def get_key(subject_id):
        """dummy to return example key for bob"""
        if subject_id == 'bob':
            return EXAMPLE_KEYPAIR_PRIVATE

    dec_file = DecryptionFileWrapper(enc_file, get_key)

    plaintext_parts = []

    for pattern in read_patterns:
        plaintext_parts.append(dec_file.read(pattern))

    plain_text = b''.join(plaintext_parts)

    assert plain_text == EXAMPLE_PLAINTEXT


def test_enc_write_raises(encrypting_file_wrapper):
    """ Tests if std throw is working """
    with pytest.raises(NotImplementedError):
        encrypting_file_wrapper.write(b'1234')


def test_enc_writelines_raises(encrypting_file_wrapper):
    """ Tests if std throw is working """
    with pytest.raises(NotImplementedError):
        encrypting_file_wrapper.writelines([b'1234'])


def test_enc_seek_raises(encrypting_file_wrapper):
    """ Tests if std throw is working """
    with pytest.raises(io.UnsupportedOperation):
        encrypting_file_wrapper.seek(123)


def test_create_header():
    """ Test if the create header function work properly """
    # pylint: disable=unbalanced-tuple-unpacking
    header = create_header(initialization_vector=b'123', keys={1: b'', 2: b'', 3: b''})

    magic, length, json_str = header

    assert magic.startswith(MAGIC_NUMBER)
    assert struct.unpack('<I', length)[0] == len(json_str)
    assert json.loads(json_str.decode('utf8'))['version'] == '0.1'
    assert json.loads(json_str.decode('utf8'))['iv'] == 'MTIz'
    assert json.loads(json_str.decode('utf8'))['keys'] == {'1': '', '2': '', '3': ''}


def test_read_header():
    """ tests the shortest possible header read, which is an empty dict """
    example_header = b'CROSSCLOUDCIPHERTEXT\x02\x00\x00\x00{}'
    f_in = io.BytesIO(example_header)

    assert read_header(f_in) == {}


def test_read_header_wrong_magic():
    """ tests the if a wrong magic header leads to an exception """
    example_header = b'CROSSCLOUDCIPHERTEX\x00\x00\x00\x01\x00\x00\x02{}'
    f_in = io.BytesIO(example_header)

    with pytest.raises(HeaderError) as error:
        read_header(f_in)

    assert error.value.read_data == example_header[:len(MAGIC_NUMBER)]


@pytest.mark.parametrize('subjects', [[],
                                      ['the funny group'],
                                      ['the funny group', 'the funny guy']])
def test_calc_header_size(subjects):
    """Tests the header size calculation"""
    header = \
        create_header(AES_IV_LENGTH * b'\2', {subject: b'\3' * RSA_KEY_LENGTH
                                              for subject in subjects})

    assert len(b''.join(header)) == calc_header_size(subjects)
