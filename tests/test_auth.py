"""Slice E: Authentication — tests for JWT, password hashing, user management."""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class TestPasswordHashing(unittest.TestCase):

    def test_hash_and_verify(self):
        from justai.auth import hash_password, verify_password
        hashed = hash_password("test123")
        assert verify_password("test123", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_different_hashes(self):
        from justai.auth import hash_password
        h1 = hash_password("test")
        h2 = hash_password("test")
        assert h1 != h2  # Different salts

    def test_verify_invalid_format(self):
        from justai.auth import verify_password
        assert verify_password("test", "invalid") is False
        assert verify_password("test", "") is False


class TestJWT(unittest.TestCase):

    def test_create_and_verify(self):
        from justai.auth import create_jwt, verify_jwt
        token = create_jwt({"sub": "admin", "role": "admin"})
        payload = verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    def test_expired_token(self):
        from justai.auth import create_jwt, verify_jwt
        token = create_jwt({"sub": "admin"}, expiry=-1)
        payload = verify_jwt(token)
        assert payload is None

    def test_invalid_signature(self):
        from justai.auth import create_jwt, verify_jwt
        token = create_jwt({"sub": "admin"}, secret="secret1")
        payload = verify_jwt(token, secret="secret2")
        assert payload is None

    def test_malformed_token(self):
        from justai.auth import verify_jwt
        assert verify_jwt("not.a.valid.token") is None
        assert verify_jwt("abc") is None
        assert verify_jwt("") is None


class TestAuthManager(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        from justai.auth import AuthManager
        self.auth = AuthManager(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_register_and_login(self):
        reg = self.auth.register("admin", "password123", role="admin")
        assert reg.success is True

        login = self.auth.login("admin", "password123")
        assert login.success is True
        assert login.token != ""
        assert login.user is not None
        assert login.user.username == "admin"
        assert login.user.role == "admin"

    def test_register_duplicate(self):
        self.auth.register("user1", "password123")
        result = self.auth.register("user1", "password456")
        assert result.success is False
        assert "already exists" in result.error

    def test_register_short_password(self):
        result = self.auth.register("user1", "abc")
        assert result.success is False
        assert "6 characters" in result.error

    def test_register_empty_fields(self):
        result = self.auth.register("", "password")
        assert result.success is False

    def test_register_invalid_role(self):
        result = self.auth.register("user1", "password123", role="superadmin")
        assert result.success is False

    def test_login_wrong_password(self):
        self.auth.register("admin", "password123")
        result = self.auth.login("admin", "wrongpassword")
        assert result.success is False
        assert "Invalid credentials" in result.error

    def test_login_nonexistent_user(self):
        result = self.auth.login("nonexistent", "password")
        assert result.success is False

    def test_verify_token(self):
        self.auth.register("admin", "password123", role="admin")
        login = self.auth.login("admin", "password123")
        user = self.auth.verify(login.token)
        assert user is not None
        assert user.username == "admin"

    def test_verify_invalid_token(self):
        user = self.auth.verify("invalid.token.here")
        assert user is None

    def test_list_users(self):
        self.auth.register("user1", "password123")
        self.auth.register("user2", "password456", role="admin")
        users = self.auth.list_users()
        assert len(users) == 2
        assert users[0].username == "user1"

    def test_delete_user(self):
        self.auth.register("user1", "password123")
        assert self.auth.delete_user("user1") is True
        assert self.auth.delete_user("nonexistent") is False
        assert len(self.auth.list_users()) == 0

    def test_is_enabled(self):
        from justai.auth import AuthManager
        # In test env, AUTH_ENABLED defaults to False
        assert AuthManager.is_enabled() is False


class TestAuthAPI(unittest.TestCase):

    def test_auth_me_no_auth(self):
        """When auth is disabled, /api/auth/me returns local user."""
        from justai.api import APIHandler
        handler = APIHandler.__new__(APIHandler)
        handler.path = "/api/auth/me"
        handler.headers = {"Authorization": ""}

        responses = []
        handler._json = lambda data, status=200: responses.append((data, status))
        handler.do_POST()

        assert len(responses) == 1
        data, status = responses[0]
        assert data.get("username") == "local" or data.get("auth_enabled") is False


if __name__ == "__main__":
    unittest.main()
