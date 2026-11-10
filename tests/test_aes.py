"""AES-128 HLS decryption tests (spec 6.3)."""

from __future__ import annotations

import pytest

from pydownloader.download.aes import (
    decrypt,
    key_bytes,
    parse_iv,
    segment_iv,
)


def encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Reference PKCS#7 + AES-CBC encrypt, the same cipher as the parser tests."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    pad = PKCS7(128).padder()
    padded = pad.update(data) + pad.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


KEY = bytes(range(16))
IV = bytes(range(16, 32))


def test_iv_parsing():
    assert parse_iv("0x001234abcd") == 0x001234ABCD
    assert parse_iv("0X34567890abcdef1234567890abcdef12") == 0x34567890ABCDEF1234567890ABCDEF12
    assert parse_iv('"0x01"') == 1
    assert parse_iv("not-a-number") is None
    assert parse_iv("123") is None


def test_iv_defaults_to_the_sequence_number():
    assert segment_iv(None, 1) == (1).to_bytes(16, "big")
    assert segment_iv(None, 300) == (300).to_bytes(16, "big")
    assert segment_iv(0x34567890, 300) == (0x34567890).to_bytes(16, "big")


def test_key_must_be_16_bytes():
    assert key_bytes(KEY) == KEY
    for body in (b"", b"short", KEY + b"x"):
        with pytest.raises(ValueError):
            key_bytes(body)


def test_roundtrip():
    data = b"#EXTINF:10,\nsegment payload"
    assert decrypt(encrypt(data, KEY, IV), KEY, IV) == data


def test_roundtrip_block_aligned():
    data = b"a" * 16
    assert decrypt(encrypt(data, KEY, IV), KEY, IV) == data


def test_bad_padding_is_reported():
    with pytest.raises(ValueError, match="PKCS#7"):
        decrypt(b"0" * 16, KEY, IV)


def test_wrong_sizes_are_reported():
    with pytest.raises(ValueError, match="16 байт"):
        decrypt(b"x" * 16, KEY[:8], IV)
    with pytest.raises(ValueError, match="16 байт"):
        decrypt(b"x" * 16, KEY, b"short")
    with pytest.raises(ValueError, match="кратны"):
        decrypt(b"x" * 10, KEY, IV)
