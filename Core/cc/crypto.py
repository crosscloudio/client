"""
The part of CrossCloud dealing with cryptographic operations and encryption
"""
import base64
import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding, keywrap
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# getting logger to output warnings in case of usage with dangerous parameters
LOGGER = logging.getLogger(__name__)

# constants
AES_BLOCK_SIZE_BYTES = 16
AES_BLOCK_SIZE_BITS = 128
AES_KEY_LENGTH_BITS = 256
AES_KEY_LENGTH_BYTES = 32


def derive_key_pbkdf2sha512(password, salt=None, iterations=77000, length=32):
    """ Derives a AES key of desired length using the given parameters

    Uses PBKDF2-HMAC-SHA512 (RFC2898) to derive a key from a given password and salt.
    Parameters for the derivation (number of iterations and length of the desired key)
    can be provided if necessary. Default values for these parameters are present. It is
    recommended to stick to the default values as the provide the desired security level.
    Please note that the default iteration count makes the execution of this function
    fairly slow. Please consider this when using the function in production OR test cases
    (CI execution time etc.) Please refer to https://www.ietf.org/rfc/rfc2898.txt for more
    details.

    :param password: the password used to derive the key
    :param salt: the salt used for the derivation process in a seed-style manner. A good
        default value for the length
        of this parameter is 32 bytes (CC standard)! If nothing is passed, a
        random value of 32 byte length is generated and used
    :param iterations: the numbers of iterations (of the round function) used in the
        process of the password derivation.
        Important: This value directly affects the execution duration of the function.The
        default value is 77k iterations.This value is relatively high (=long execution
        time) but provides very good security
        properties.
    :param length: the length of the desired derived key in bytes. As CrossCloud uses a
        default key length of 256bits,
        it's default value is 32bytes (256bits).
    :return: a tuple of the used salt and the resulting key for the derivation
    """

    # if no salt is provided, a random value is generated
    if not salt:
        salt = os.urandom(32)

    # deriving key with standard parameters
    kdf = PBKDF2HMAC(algorithm=hashes.SHA512(), length=length, salt=salt,
                     iterations=iterations,
                     backend=default_backend())

    if isinstance(password, str):
        key = kdf.derive(password.encode('ASCII'))
    else:
        key = kdf.derive(password)

    return salt, key


def encrypt_aes256(plaintext, key=None, init_vector=None, enable_padding=True):
    """ encrypts the provided plaintext using AES-CBC with arbitrary key length

    Encrypt the provided plaintext using the AES block cipher in CBC mode
    (https://tools.ietf.org/html/rfc3602) with
    arbitrary key length in {128, 192, 256}.
    The strongly recommended key size (and default for CrossCloud) is 256bit keys.

    :param enable_padding: determines if PKCS7 padding shall be activated for the
        encryption process (https://www.ietf.org/rfc/rfc2315.txt) shall be applied. If
        disabled, the input data to this operation must have a multiple length of the
        cipher block length (128bits). Otherwise the operation will fail.
    :param init_vector: the initialisation vector for the encryption. This value must
    provide
        sufficient entropy but is NO confidential information (=does not have to be
        kept secret)
    :param key: the key used for the encryption. NOTE: this is confidential and must be
        kept secret
    :param plaintext: the input to the encryption operation

    :return: A tuple in the form of (ciphertext, key, IV). The ciphertext as the result
        of the encryption described above. The other parameters are the used key and
        initialisation vector.If IV and key were specified, these values are returned

    """

    # creating key if none specified
    if not key:
        key = os.urandom(32)

    # creating iv if none specified
    if not init_vector:
        init_vector = os.urandom(16)

    # setting default backend
    backend = default_backend()

    # assigning plaintext to padded data
    to_encrypt = plaintext

    # adding PKCS7 padding
    if enable_padding:
        padder = padding.PKCS7(AES_BLOCK_SIZE_BITS).padder()
        to_encrypt = padder.update(plaintext) + padder.finalize()

    # doing encryption update
    cipher = Cipher(algorithms.AES(key), modes.CBC(init_vector), backend)
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(to_encrypt) + encryptor.finalize()

    return ciphertext, key, init_vector


def decrypt_aes256(ciphertext, key, init_vector, enable_unpadding=True):
    """ decrypts the provided ciphertext using AES-CBC with arbitrary key length

    Decrypts the provided ciphertext using the AES block cipher in CBC mode
    (https://tools.ietf.org/html/rfc3602) with
    arbitrary key length in {128, 192, 256}.
    The strongly recommended key size (and default for CrossCloud) is 256bit keys.

    :param enable_unpadding: determines if PKCS7 padding shall be activated for the
        decryption process
        (https://www.ietf.org/rfc/rfc2315.txt) shall be applied. If disabled, the
        input data to this operation must have a multiple length of the cipher block
        length (128bits). Otherwise the operation will fail.
    :param init_vector: the initialisation vector for the decryption. Must be identical to
    the one
        used to encrypt the data.
    :param key: the key used for the encryption. Must be identical to the one used to
        encrypt the data.
    :param ciphertext: the input to the decryption operation

    :return: The decrypted message (plaintext) using the key and IV.

    """
    backend = default_backend()

    # decrypting data
    cipher = Cipher(algorithms.AES(key), modes.CBC(init_vector), backend)
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # removing padding
    if enable_unpadding:
        unpadder = padding.PKCS7(AES_BLOCK_SIZE_BITS).unpadder()
        return unpadder.update(plaintext) + unpadder.finalize()
    else:
        return plaintext


def wrap_key_aes(key_to_wrap, wrapping_key=None):
    """ Wraps a key using the AES key wrapping mode of operation as specified in
    https://www.ietf.org/rfc/rfc3394.txt

    :param key_to_wrap: the key to be wrapped in the process.
    :param wrapping_key: the key to be used to wrap the key  = KEK, If non is provided,
        it is generated randomly
    :return: the wrapped key as well as the used key as (wrapped_result, wrapping_key)
    """
    # checking if key needs to be generated
    if wrapping_key is None:
        wrapping_key = os.urandom(len(key_to_wrap))

    return keywrap.aes_key_wrap(wrapping_key, key_to_wrap,
                                default_backend()), wrapping_key


def unwrap_key_aes(key_to_unwrap, wrapping_key):
    """ Unwraps a key using the AES key wrapping mode of operation as specified in
    https://www.ietf.org/rfc/rfc3394.txt

    :param key_to_unwrap: the wrapped result of a previous wrap operation. I.e. the key
        to be unwrapped
    :param wrapping_key: the key used to unwrap = KEK. This must be the same key used
        to wrap
    :return: the unwrapped key
    """
    return keywrap.aes_key_unwrap(wrapping_key, key_to_unwrap, default_backend())


def calculate_sha256(data_to_hash):
    """
    Calculates the SHA256 hash of the given input data as defined in
    https://tools.ietf.org/html/rfc4634
    :param data_to_hash: the data to be hashed (as bytes)
    :return the sha256 hash of the input data
    """
    # creating hash object
    digest = hashes.Hash(algorithm=hashes.SHA256(), backend=default_backend())

    # hashing content
    digest.update(data=data_to_hash)

    # getting result
    return base64.b64encode(digest.finalize())
