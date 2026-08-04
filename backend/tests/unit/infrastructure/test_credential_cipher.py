import pytest
from cryptography.fernet import Fernet

from app.infrastructure.security.credential_cipher import (
    CredentialCipher,
    InvalidEncryptionKeyError,
)


def test_round_trips_plaintext() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode())

    ciphertext = cipher.encrypt("hunter2")

    assert ciphertext != "hunter2"
    assert cipher.decrypt(ciphertext) == "hunter2"


def test_rejects_invalid_key() -> None:
    with pytest.raises(InvalidEncryptionKeyError):
        CredentialCipher("not-a-valid-fernet-key")


def test_decrypt_with_wrong_key_raises_clear_error() -> None:
    encrypted = CredentialCipher(Fernet.generate_key().decode()).encrypt("hunter2")
    other_cipher = CredentialCipher(Fernet.generate_key().decode())

    with pytest.raises(InvalidEncryptionKeyError):
        other_cipher.decrypt(encrypted)
