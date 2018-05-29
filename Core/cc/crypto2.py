"""This module provides the functionality for asymmetric/symmetric encryption."""
import base64
import io
import json
import os
import struct
import logging
import typing
from collections import namedtuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import cc.crypto

# setting logger object
logger = logging.getLogger(__name__)

WRAP_METHOD_STRING_RSA_AES = 'rsa_aes256cbckey_privatekeypem'
WRAP_VERSION = '1'

ENCODING = 'utf-8'

# mamgic number in header of crypto files to instantly
# detect if ciphertext or not
MAGIC_NUMBER = b'CROSSCLOUDCIPHERTEXT'
VERSION = '0.1'

# 128 bits = block size AES
AES_IV_LENGTH = 16

# 256 bits = key size AES
AES_KEY_LENGTH = 32

RSA_KEY_LENGTH = 512

# Named tuple for keypairs
# pylint: disable=invalid-name
KeyPair = namedtuple('KeyPair', field_names=['private_pem', 'public_pem'])
""" A KeyPair consisting of public and private key

:var private_pem: The private key in pem format
:var public_pem: The public key in pem format
"""


class EncryptionException(Exception):
    """General Encryption exception."""


class HeaderError(EncryptionException):
    """Thrown if something with the header went wrong."""

    def __init__(self, *args, read_data=b'', **kwargs):
        super().__init__(*args, **kwargs)

        # : data which has been read, this is to recover to non encrypted
        self.read_data = read_data


class KeyWrappingError(EncryptionException):
    """Thrown if wrapping or unwrapping a private key asymmetrically failed."""


class NoKeyError(EncryptionException):
    """If the header does not contain a key to decrypt the content."""


def generate_keypair():
    """ Generates a private/public keypair encoded as pem returned as a tuple of bytes"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=RSA_KEY_LENGTH * 8,
        backend=default_backend()
    )

    return \
        KeyPair(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()),
            private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                                  format=serialization.PublicFormat.PKCS1))


def load_pem_public_key(pem_public_key_bytes):
    """
    De-serializes a pem public key from bytes
    :param pem_public_key_bytes: the public key to get in PEM format
    :return: the key object
    """
    return serialization.load_pem_public_key(data=pem_public_key_bytes,
                                             backend=default_backend())


def load_pem_private_key(pem_private_key_bytes, password=None):
    """
    De-serializes a pem private key from bytes
    :param pem_private_key_bytes: the public key to get in PEM format
    :param password: the password used to protect the private key in pem format
    :return: the key object
    """
    return serialization.load_pem_private_key(data=pem_private_key_bytes,
                                              password=password,
                                              backend=default_backend())


def encrypt_with_public_key(public_key, plaintext):
    """
    Encrypts a given plaintext using the given public key and OAEP padding (with
    MGF1 and SHA256
    :param public_key: the public key to be used for encryption (key object not bytes)
    :param plaintext: the plaintext to be encrypted (bytes)
    :return: the ciphertext resulting from the encryption operation of the plaintext
    """
    return public_key.encrypt(plaintext, padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    ))


def wrap_private_key(private_key_pem, public_key_object):
    """
    Wraps an asymmetric private key with an asymmetric public key the following way: 1) the
    private key (in pem format) is encrypted using a random symmetric AES256 key adn
    IV. 2) the AES256 key is encrypted using the given public key. This function
    returns a key wrapping json object with the appropriate fields set
    :param private_key_pem: the private key in pem format to be wrapped (bytes object)
    :param public_key_object: the public key (object) used to wrap the private key
    :return: a key wrapping json object with base64 (ascii) fields
    """
    try:
        # encrypting pem key
        (ciphertext, key, init_vector) = cc.crypto.encrypt_aes256(plaintext=private_key_pem)

        # wrapping key with public key specified
        wrapped_key = encrypt_with_public_key(public_key=public_key_object, plaintext=key)

        # base64 encoding the values + decoding to ascii
        # creating key wrapping object
        return {
            'public_wrapped_aes_key': base64.b64encode(wrapped_key).decode('ascii'),
            'wrapping_iv': base64.b64encode(init_vector).decode('ascii'),
            'wrapped_private_key': base64.b64encode(ciphertext).decode('ascii'),
            'wrapping_method':
                {
                    'method': WRAP_METHOD_STRING_RSA_AES,
                    'version': WRAP_VERSION
                }
        }
    except BaseException:
        raise KeyWrappingError('Could not wrap key with the given parameters. Public '
                               'key seems to be malformed')


def unwrap_private_key(wrapped_object, private_key_object):
    """
    Unwraps an asymmetric private key with the correspinding asymmetric private key as
    follows: 1) unwrapps an AES256 key using the private key. 2) decrypts the private
    key material wrapped by decrypting it with the AES256 key
    :param wrapped_object: the wrapped object to unwrap
    :param private_key_object: the private key to unwrap
    :return: the unwrapped private key in pem format
    """
    # checking version of the wrapped key object
    wrapped_version_info = wrapped_object['wrapping_method']
    if wrapped_version_info['version'] != WRAP_VERSION \
            or wrapped_version_info['method'] != WRAP_METHOD_STRING_RSA_AES:
        logger.warning('Found not matching wrapped object version or method when '
                       'unwrapping key. Proceeding now, but this should not happen and '
                       'might lead to errors when unwrapping')

    try:
        # unwrapping aes key
        aes_key = decrypt_with_private_key(private_key=private_key_object,
                                           ciphertext=base64.b64decode(
                                               wrapped_object['public_wrapped_aes_key']))

        # decrypting private pem key
        return cc.crypto.decrypt_aes256(base64.b64decode(
            wrapped_object['wrapped_private_key']),
            key=aes_key,
            init_vector=base64.b64decode(
                wrapped_object['wrapping_iv']))
    except BaseException:
        raise KeyWrappingError('Could not unwrap key.')


def decrypt_with_private_key(private_key, ciphertext):
    """
    Decrypts a given ciphertext using the given private key and assumes OAEP padding
    (with MGF1 and SHA256)
    :param private_key: the private key to use for decryption (key object not bytes)
    :param ciphertext: the ciphertext to decrypt (bytes)
    :return: the plaintext of the decrypted ciphertext
    """
    return private_key.decrypt(ciphertext, padding=padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None))


def create_header(initialization_vector: bytes,
                  keys, algorithm='AES256-CFB', version=VERSION) -> [bytes]:
    """ Creates the header for an encrypted file, returns artifacts as list of bytes
    ready to be joined"""
    header = [MAGIC_NUMBER]

    metadata = {'iv': base64.b64encode(initialization_vector).decode('ascii'),
                'keys': {key_sub: base64.b64encode(key).decode('ascii')
                         for key_sub, key in keys.items()},
                'algorithm': algorithm,
                'version': version}

    json_str = json.dumps(metadata).encode(ENCODING)

    header.append(struct.pack('<I', len(json_str)))
    header.append(json_str)

    return header


def read_header(f_in: io.RawIOBase) -> dict:
    """ reads the header of a file stream with CrossCloud encryption

    :param f_in: readable file-object
    :return: the header dict
    """
    magic_number = f_in.read(len(MAGIC_NUMBER))

    if magic_number != MAGIC_NUMBER:
        raise HeaderError('magic number is {}'.format(magic_number),
                          read_data=magic_number)

    header_length, = struct.unpack('<I', f_in.read(4))

    header_str = f_in.read(header_length).decode(ENCODING)
    return json.loads(header_str)


class EncryptionFileWrapper(io.RawIOBase):
    """ Wraps over an existing file object and encrypted the stream"""

    def __init__(self, f_original, public_keys, file_key=None):
        """
        initializer

        :param f_original: the original FLO to wrap and get plaintext from
        :param public_keys: list of tuples representing public key information
        in the format of (subject, public key), where subject is the email_address
        of the recipient and public key is a string containing the RSA public key
        in PEM format
        :param file_key: the symmetric key used for encryption (AES256). If not
        passed, it will be generated randomly
        (os.urandom)
        """
        super().__init__()

        # we never encrypt a file without public keys ;)
        assert len(public_keys)

        # setting symmetric key used for file encryption
        if not file_key:
            # creating random file key if not passed
            self._file_key = os.urandom(AES_KEY_LENGTH)
        else:
            # setting file key if passed (assuming right size)
            self._file_key = file_key

        # creating random IV
        initialization_vector = os.urandom(AES_IV_LENGTH)

        # creating cipher to perform encryption using given IV
        self._cypher = Cipher(algorithms.AES(self._file_key),
                              modes.CFB(initialization_vector=initialization_vector),
                              backend=default_backend())
        self._encryptor = self._cypher.encryptor()
        self._f_original = f_original

        # wrapping encryption key (symmetric) with all public keys of intended recipients
        keys = {}
        for subject, public_key_str in public_keys.items():
            public_key = serialization.load_pem_public_key(public_key_str,
                                                           default_backend())
            # wrapping symmetric key with public key of user
            encrypted_file_key = encrypt_with_public_key(public_key=public_key,
                                                         plaintext=self._file_key)

            # storing wrapped file key
            keys[subject] = encrypted_file_key

        # creating header information and adding to output buffer
        self._buffer = \
            b''.join(create_header(
                initialization_vector=initialization_vector, keys=keys))

        # determining header size
        self.header_size = len(self._buffer)

    def read(self, count=None):
        """
        reads data through the wrapper and encrypts the data
        :param count: the bytes to read or -1
        :return: the ciphertext = encrypted plaintext from wrapped FLO
        """
        result = b''

        # if buffer is filled (e.g. header), reading first part of result from buffer
        if self._buffer:
            if count:
                result = self._buffer[:count]
                self._buffer = self._buffer[count:]
                # suggestion: if self._buffer == b'': self._buffer = None
            else:
                result = self._buffer
                self._buffer = b''
                # suggestion: self._buffer = None

        # reading remaining part
        if count is not None:
            # if size to read defined, reading remaining part not yet read from buffer
            plain_text = self._f_original.read(count - len(result))
        else:
            # if no size defined -> reading whole original
            plain_text = self._f_original.read()
        if plain_text:
            # encrypting and appending to result
            result += self._encryptor.update(plain_text)

        # returning ciphertext
        return result

    def readable(self):
        """
        determines if the FLO is readable
        :return: true if readable, false else
        """
        return True

    def writable(self):
        """
        determines if the FLO is writable
        :return: true if writeable, false else
        """
        return False

    def seekable(self):
        """
        determines if the FLO is seekable
        :return: true if seekable, false else
        """
        return False


class DecryptionFileWrapper(io.RawIOBase):
    """Wraps over an existing file object and decrypts the stream."""

    def __init__(self, f_original: io.RawIOBase, get_key_pair: typing.Callable[[str], KeyPair]):
        """
        initializer, NOTE: this starts reading the stream of f_original
        to extract header information if present!!
        :param f_original: the wrapped FLO
        :param get_key_pair: a function, called for each key_subject from the header until one does
         not throw a KeyError.
        """
        super().__init__()

        # setting wrapped stream to read from
        self._f_original = f_original

        # reading json header contained in encrypted file
        json_header = read_header(self._f_original)

        # reading iv from header
        initialization_vector = base64.b64decode(json_header['iv'])

        # try to get a key for one of the subject in the file-header
        for private_key_subject in json_header['keys'].keys():
            try:
                private_pem = get_key_pair(private_key_subject)
                # reading (wrapped) key information and extracting relevant one
                encrypted_file_key_string = json_header['keys'].get(private_key_subject)
                break
            except KeyError:
                # This is part of the process finding a key, get_key_private will be called for all
                # key subjects read from the header until it returns a valid KeyPair
                pass
        else:
            # (else is executed if break was not hit in loop)
            # if own subject not in key info -> error as we cannot decrypt
            raise NoKeyError('No decryption key present')

        # store the set of available subject ids from the header
        self.subject_ids = set(json_header['keys'].keys())

        # decoding wrapped file key (symmetric)
        encrypted_file_key = base64.b64decode(encrypted_file_key_string)

        # getting private key (PEM)
        private_key = serialization.load_pem_private_key(
            private_pem, None, backend=default_backend())

        # initializing file key (AES) by unwrapping wrapped key info with private key
        self._file_key = decrypt_with_private_key(private_key=private_key,
                                                  ciphertext=encrypted_file_key)

        # initializing cipher to decrypt using file key
        self._cypher = Cipher(algorithms.AES(self._file_key),
                              modes.CFB(initialization_vector=initialization_vector),
                              backend=default_backend())
        self._decryptor = self._cypher.decryptor()

    def read(self, count):
        """
        reads data through the wrapper and decrypts the data
        :param count: the bytes to read or -1
        :return: the plaintext = decrypted ciphertext from wrapped FLO
        """
        # reading ciphertext from wrapped FLO
        cipher_text = self._f_original.read(count)

        # decrypting
        plain_text = self._decryptor.update(cipher_text)

        # returning plaintext
        return plain_text

    def readable(self):
        """
        determines if the FLO is readable
        :return: true if readable, false else
        """
        return True

    def writable(self):
        """
        determines if the FLO is writable
        :return: true if writeable, false else
        """
        return False

    def seekable(self):
        """
        determines if the FLO is seekable
        :return: true if seekable, false else
        """
        return False


def calc_header_size(subjects) -> int:
    """Calculates the size of the header based on subjects

    it uses the create_header with fake key and iv date function in the background, to
    ensure this returns the correct size
    """
    return \
        len(b''.join(create_header(b'\0' * AES_IV_LENGTH,
                                   {sub: b'\0' * 512 for sub in subjects})))
