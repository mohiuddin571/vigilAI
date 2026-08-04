from cryptography.fernet import Fernet, InvalidToken


class InvalidEncryptionKeyError(RuntimeError):
    """The configured camera-credential encryption key is not a valid Fernet key."""


class CredentialCipher:
    """Symmetric encryption for camera credentials at rest (TD-15).

    The only place in the codebase that touches the encryption key or
    ciphertext — callers pass plaintext in and get plaintext back out.
    """

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise InvalidEncryptionKeyError(
                "CAMERA_CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key. "
                "Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise InvalidEncryptionKeyError(
                "Stored camera credential could not be decrypted with the "
                "configured CAMERA_CREDENTIAL_ENCRYPTION_KEY."
            ) from exc
