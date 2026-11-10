"""AES-128 decryption of HLS segments (spec 6.3).

HLS uses AES-128 in CBC mode. The IV is taken from ``EXT-X-KEY``
(``IV=0x…``) and when it is absent it is the media sequence number of the
segment, as a 16 byte big-endian integer. The key is 16 bytes.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CIPHER_BLOCK_SIZE = 16
KEY_SIZE = 16


def parse_iv(value: str) -> int | None:
    """``IV=0x3456789…`` as an integer, ``None`` when it is not usable."""
    text = value.strip().strip('"')
    if text.lower().startswith("0x"):
        try:
            return int(text[2:], 16)
        except ValueError:
            return None
    return None


def key_bytes(body: bytes) -> bytes:
    """Validate a downloaded key: exactly 16 bytes.

    Raises :class:`ValueError` when the server returned something else
    (an HTML error page is a common case).
    """
    if len(body) != KEY_SIZE:
        raise ValueError(f"Ключ имеет размер {len(body)} байт, ожидалось 16")
    return body


def segment_iv(iv: int | None, sequence: int) -> bytes:
    """IV of a segment: the explicit ``IV`` attribute, otherwise the sequence number."""
    value = sequence if iv is None else iv
    return value.to_bytes(CIPHER_BLOCK_SIZE, "big")


def decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-128-CBC decrypt with PKCS#7 padding removed.

    Raises :class:`ValueError` when the padding is broken, which means the
    key is not the key of this segment.
    """
    if len(key) != KEY_SIZE:
        raise ValueError("Ключ должен быть 16 байт")
    if len(iv) != CIPHER_BLOCK_SIZE:
        raise ValueError("IV должен быть 16 байт")
    if not data or len(data) % CIPHER_BLOCK_SIZE:
        raise ValueError("Данные сегмента не кратны размеру блока AES")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    plain = decryptor.update(data) + decryptor.finalize()
    pad = plain[-1]
    if not 1 <= pad <= CIPHER_BLOCK_SIZE or plain[-pad:] != bytes([pad]) * pad:
        raise ValueError("Некорректное дополнение PKCS#7")
    return plain[:-pad]
