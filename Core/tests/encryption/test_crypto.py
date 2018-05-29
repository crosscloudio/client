"""
Unit tests for crypto primitives and functions used in the context of encrypting/
decrypting files
"""

import binascii
import io
import os

from cryptography.hazmat.primitives.keywrap import InvalidUnwrap
import pytest

import cc.crypto
import cc.crypto2


def read_from_stream_until_eof(file, buffer):
    """ Reads a file like object till the end and returns the data

    This functions takes a file like object and reads from it using the defined buffer
    size until EOF is reached

    :param file: The file like object to be read from
    :param buffer: The size of the buffer to be used for reading in bytes. pass -1 or
    None if no buffering shall be used. We strongly advice you not to read files at
    once but to use buffering
    :return: the whole data read from the file like object until eof
    """
    data = b""
    while True:
        temp = file.read(buffer)
        # print("read %d bytes" % len(temp))
        # print("data is %d bytes" % len(data))
        if not temp:
            break
        data += temp

    return data


def test_key_derivation_determinism():
    """ tests if the key derivation is determinant and consistent

    this test uses the default key derivation function (PBKDF2) to derive a
    cryptographic key from a given password and salt multiple times. It checks if the
    derived key does not alter in the derivation processes
    """

    # initializing reference key
    reference_key = None

    # define password and salt
    salt = b"salt"
    password = "myPassword12##*!!--,,"

    # checking that 10 iterations of the same parameters are always the same
    for _ in range(10):
        if not reference_key:
            reference_key = cc.crypto.derive_key_pbkdf2sha512(password, salt)
        else:
            assert reference_key == cc.crypto.derive_key_pbkdf2sha512(password, salt)


def test_wrapping_vectors():
    """ tests the key wrapping functionality using test vectors as specified in the
    according rfc

    this tests takes the test vectors for AES key wrapping as defined in
    https://www.ietf.org/rfc/rfc3394.txt and tests our wrapping and unwrapping
    mechanisms against it.

    """
    # test vector from RFC 3394
    # 128bit key wrapping 128bit key
    kek1 = binascii.unhexlify("000102030405060708090A0B0C0D0E0F")
    cipher1 = binascii.unhexlify("1FA68B0A8112B447AEF34BD8FB5A7B829D3E862371D2CFE5")
    plain1 = binascii.unhexlify("00112233445566778899AABBCCDDEEFF")

    # 192bit key wrapping 128bit key
    kek2 = binascii.unhexlify("000102030405060708090A0B0C0D0E0F1011121314151617")
    cipher2 = binascii.unhexlify("96778B25AE6CA435F92B5B97C050AED2468AB8A17AD84E5D")
    plain2 = binascii.unhexlify("00112233445566778899AABBCCDDEEFF")

    # 256bit key wrapping 128bit key
    kek3 = binascii.unhexlify(
        "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F")
    cipher3 = binascii.unhexlify("64E8C3F9CE0F5BA263E9777905818A2A93C8191E7D6E8AE7")
    plain3 = binascii.unhexlify("00112233445566778899AABBCCDDEEFF")

    # 256bit key wrapping 256bit key
    kek4 = binascii.unhexlify(
        "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F")
    cipher4 = binascii.unhexlify(
        "28C9F404C4B810F4CBCCB35CFB87F8263F5786E2D80ED326CBC7F0E71A"
        "99F43BFB988B9B7A02DD21")
    plain4 = binascii.unhexlify(
        "00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F")

    # executing tests on wrapping and unwrapping
    assert cc.crypto.unwrap_key_aes(cipher1, kek1) == plain1
    assert cc.crypto.wrap_key_aes(plain1, kek1)[0] == cipher1
    assert cc.crypto.unwrap_key_aes(cipher2, kek2) == plain2
    assert cc.crypto.wrap_key_aes(plain2, kek2)[0] == cipher2
    assert cc.crypto.unwrap_key_aes(cipher3, kek3) == plain3
    assert cc.crypto.wrap_key_aes(plain3, kek3)[0] == cipher3
    assert cc.crypto.unwrap_key_aes(cipher4, kek4) == plain4
    assert cc.crypto.wrap_key_aes(plain4, kek4)[0] == cipher4


def test_encryption_decryption_vectors():
    """ tests the encryption and decryption mechanism of CrossCloud against test
    vectors defined in the corresponding RFC

    this test takes the test vectors for AES256-CBC as defined in
    https://tools.ietf.org/html/rfc3602 and tests our encrypting and decrypting
    functionality against it
    """
    # test vectors from http://www.inconteam.com/software-development/41-encryption/
    # 55-aes-test-vectors#aes-cbc
    key = binascii.unhexlify(
        "603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4")

    iv1 = binascii.unhexlify("000102030405060708090A0B0C0D0E0F")
    iv2 = binascii.unhexlify("F58C4C04D6E5F1BA779EABFB5F7BFBD6")
    iv3 = binascii.unhexlify("9CFC4E967EDB808D679F777BC6702C7D")
    iv4 = binascii.unhexlify("39F23369A9D9BACFA530E26304231461")

    plain1 = binascii.unhexlify("6bc1bee22e409f96e93d7e117393172a")
    plain2 = binascii.unhexlify("ae2d8a571e03ac9c9eb76fac45af8e51")
    plain3 = binascii.unhexlify("30c81c46a35ce411e5fbc1191a0a52ef")
    plain4 = binascii.unhexlify("f69f2445df4f9b17ad2b417be66c3710")

    cipher1 = binascii.unhexlify("f58c4c04d6e5f1ba779eabfb5f7bfbd6")
    cipher2 = binascii.unhexlify("9cfc4e967edb808d679f777bc6702c7d")
    cipher3 = binascii.unhexlify("39f23369a9d9bacfa530e26304231461")
    cipher4 = binascii.unhexlify("b2eb05e2c39be9fcda6c19078c6a9d1b")

    # checking encryption
    assert cc.crypto.encrypt_aes256(plain1, key, iv1, False)[0] == cipher1
    assert cc.crypto.encrypt_aes256(plain2, key, iv2, False)[0] == cipher2
    assert cc.crypto.encrypt_aes256(plain3, key, iv3, False)[0] == cipher3
    assert cc.crypto.encrypt_aes256(plain4, key, iv4, False)[0] == cipher4

    # checking decryption
    assert cc.crypto.decrypt_aes256(cipher1, key, iv1, False) == plain1
    assert cc.crypto.decrypt_aes256(cipher2, key, iv2, False) == plain2
    assert cc.crypto.decrypt_aes256(cipher3, key, iv3, False) == plain3
    assert cc.crypto.decrypt_aes256(cipher4, key, iv4, False) == plain4


def test_basic_encryption_decryption():
    """ tests a very simple example of several mechanisms combined

    this test models a typical usage-chain of different mechanisms as defined in this
    module. Therefore, it encrypts a plaintext message, wraps the corresponding key,
    unwraps it again and performs the final decryption using the same parameters (key,
    iv). This checks the consistency of encryption, decryption and wrapping mechanisms

    """
    # password, 256bit wrapping key, 256bit encryption key,128bit IV
    plaintext = b"a secret message asdfasdfasdfasfdasfd"

    # encrypting
    (cipher, key, ivector) = cc.crypto.encrypt_aes256(plaintext)

    # wrapping key
    (wrapped_key, wrapping_key) = cc.crypto.wrap_key_aes(key)

    # and turn aroooouuuund...now

    # unwrapping key
    decryption_key = cc.crypto.unwrap_key_aes(wrapped_key, wrapping_key)
    plain = cc.crypto.decrypt_aes256(cipher, decryption_key, ivector, True)

    # checking that encryption/decryption results in the same thing
    assert plaintext == plain


@pytest.mark.parametrize("size_data_read,read_buffer_size", [
    [1, 1],
    [100, 1],
    [1000, 1],
    [10000, 1],
    [100000, 1],
    [123459, 1],
    [4000, 16],
    [40000, 16],
    [4000, 15],
    [2742, 5],
    [4000, 4000],
    [4000, 10000],
    [40000, 1234],
    [40000, 40 * 1024 * 1024],
    [20000, None],
    [40 * 1024 * 1024, 1024 * 1024 * 4],
    [9487233, 48 * 1024 * 1024],
    [22, 7],
    [234234, -1]
])
def test_regular_file_read(size_data_read, read_buffer_size):
    """ tests the general throughput of reading operations for performance comparison

    this executes not encryption whatsoever but only reads data

    :param size_data_read: the data read in the test
    :param read_buffer_size: the buffer size
    """
    # creating data to read
    plaintext = b"0" * size_data_read
    plain_data_source = io.BytesIO(plaintext)

    # reading all data
    read_from_stream_until_eof(plain_data_source, read_buffer_size)


def test_faulty_key_unwrap():
    """ test that trying to decrypt data with wrongly unwrappped key fails
    """
    # generating keys
    initial_key = os.urandom(32)

    # encrypting with initial key
    initial_plaintext = b"iamtheplaintext"
    initial_ciphertext, _, init_vector = cc.crypto.encrypt_aes256(
        initial_plaintext, initial_key)

    # defining wrapping key
    wrapping_key = os.urandom(32)

    # wrapping key
    wrapped_key, wrapping_key = cc.crypto.wrap_key_aes(initial_key, wrapping_key)

    # generating second wrapping key
    wrong_wrapping_key = os.urandom(32)

    try:
        # trying to unwrap with wrong wrapping key
        unwrapped_wrong_key = cc.crypto.unwrap_key_aes(wrapped_key, wrong_wrapping_key)

        # trying to decrypt cipher with wrong key
        cc.crypto.decrypt_aes256(initial_ciphertext, unwrapped_wrong_key, init_vector)

        assert False
    except InvalidUnwrap:
        return True


def test_faulty_decryption():
    """ tests that trying to decrypt data with wrong key fails
    """
    # setting the scene
    plain = b"I am the plaintext"

    # encrypting plain
    (cipher, _, init_vector) = cc.crypto.encrypt_aes256(plain)

    # generating other key
    faulty_key = b'THISISDEFENTLYNOTAREALKEY1234568'

    with pytest.raises(ValueError):
        # trying to decrypt data with faulty key -> this should fail!
        cc.crypto.decrypt_aes256(cipher, faulty_key, init_vector)


def test_encrypt_with_public_key():
    """ Test the wrappers for encrypting and decrypting data asymmetrically"""
    # creating keys to test
    (private_key, public_key) = cc.crypto2.generate_keypair()

    # getting key objects from pem bytes
    public_key = cc.crypto2.load_pem_public_key(public_key)
    private_key = cc.crypto2.load_pem_private_key(private_key)

    # defining message to encrypt
    test_message = b"encrypted data"

    # encrypting
    ciphertext = cc.crypto2.encrypt_with_public_key(public_key=public_key,
                                                    plaintext=test_message)

    # decrypting
    plaintext = cc.crypto2.decrypt_with_private_key(private_key=private_key,
                                                    ciphertext=ciphertext)

    assert plaintext == test_message


def test_wrapping_unwrapping_private_key():
    """test the key wrapping and unwrapping functionality and checks if wrapping and
    unwrapping results in the original result"""
    # generating two keyp airs, one to wrap, one to be wrapped
    (test_private_key, _) = cc.crypto2.generate_keypair()
    (wrap_private_key, wrap_public_key) = cc.crypto2.generate_keypair()

    # wrapping private key with public key
    wrapped_key = cc.crypto2.wrap_private_key(
        private_key_pem=test_private_key,
        public_key_object=cc.crypto2.load_pem_public_key(wrap_public_key))

    # checking received object
    assert wrapped_key['public_wrapped_aes_key'] is not None
    assert wrapped_key['wrapping_iv'] is not None
    assert wrapped_key['wrapped_private_key'] is not None

    # checking wrapping method information
    wrapping_method = wrapped_key['wrapping_method']
    assert wrapping_method['method'] == cc.crypto2.WRAP_METHOD_STRING_RSA_AES
    assert wrapping_method['version'] == cc.crypto2.WRAP_VERSION

    # unwrapping wrapped key again
    unwrapped_key = cc.crypto2.unwrap_private_key(
        private_key_object=cc.crypto2.load_pem_private_key(wrap_private_key),
        wrapped_object=wrapped_key)

    # checking if original key is there
    assert unwrapped_key == test_private_key


def test_unwrapping_key_fails():
    """tests the case where a key cannot be unwrapped because of malformed wrapped key
    object -> should through a specific exception"""

    # generating random wrapping keypair
    (wrap_private_key, _) = cc.crypto2.generate_keypair()

    malformed_wrapped_object = {
        'public_wrapped_AES_key': 'malformed',
        'iv': 'this_will_not_work',
        'wrapped_private_key': 'and_that_is_ok',
        'wrapping_method':
            {
                'method': cc.crypto2.WRAP_METHOD_STRING_RSA_AES,
                'version': cc.crypto2.WRAP_VERSION
            }
    }
    with pytest.raises(cc.crypto2.KeyWrappingError):
        # trying to unwrap -> this should fail
        cc.crypto2.unwrap_private_key(wrapped_object=malformed_wrapped_object,
                                      private_key_object=cc.crypto2.load_pem_private_key(
                                          wrap_private_key))


def test_wrapping_key_fails():
    """tests the case where a key cannot be wrapped because errors with the given key
    material"""
    malformed_public_key = b'i_am_clearly_not_an_rsa_public_key'

    with pytest.raises(cc.crypto2.KeyWrappingError):
        cc.crypto2.wrap_private_key(private_key_pem=b'pem',
                                    public_key_object=malformed_public_key)


def test_hashes():
    """tests the basic execution of a hash operation without testing input output
    relations"""
    plain = b'test_input_for_hash'
    hash_ours = cc.crypto.calculate_sha256(plain).decode('ascii')

    assert hash_ours
