"""Minimal JWT encode/decode test with a test secret (no real tokens)."""
import pytest

try:
    import jwt
except ImportError:
    jwt = None


@pytest.mark.skipif(jwt is None, reason="PyJWT not installed")
def test_jwt_encode_decode_roundtrip():
    """Encode a payload with a test secret and decode; payload should match."""
    secret = "test-secret-do-not-use-in-production"
    payload = {"username": "testuser", "id": "123"}
    token = jwt.encode(payload, secret, algorithm="HS256")
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["username"] == payload["username"]
    assert decoded["id"] == payload["id"]
