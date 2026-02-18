import json

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pydantic import ValidationError

from passbolt.helper import (
    CustomField,
    PassboltClient,
    PassboltConfig,
    ResourceInfo,
    load_config_from_env,
)


class TestCustomField:
    def test_create_text_field(self):
        field = CustomField(key="api_key", value="abc123")
        assert field.key == "api_key"
        assert field.value == "abc123"
        assert field.field_type == "text"

    def test_create_secret_field(self):
        field = CustomField(key="token", value="secret", field_type="secret")
        assert field.field_type == "secret"

    def test_empty_key_rejected(self):
        with pytest.raises(ValidationError):
            CustomField(key="", value="val")

    def test_empty_value_allowed(self):
        field = CustomField(key="notes", value="")
        assert field.value == ""

    def test_frozen(self):
        field = CustomField(key="k", value="v")
        with pytest.raises(ValidationError):
            field.key = "other"


class TestResourceInfo:
    def test_create_minimal(self):
        r = ResourceInfo(id="uuid-1", name="test", resource_type_id="rt-1")
        assert r.id == "uuid-1"
        assert r.username is None
        assert r.uri is None

    def test_create_full(self):
        r = ResourceInfo(
            id="uuid-1",
            name="test",
            username="admin",
            uri="https://example.com",
            resource_type_id="rt-1",
        )
        assert r.username == "admin"
        assert r.uri == "https://example.com"


class TestPassboltConfig:
    def test_create(self):
        c = PassboltConfig(
            base_url="https://pb.test",
            private_key="---KEY---",
            passphrase="pass",
        )
        assert c.base_url == "https://pb.test"


class TestLoadConfigFromEnv:
    def test_missing_env_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="PASSBOLT_BASE_URL"):
                load_config_from_env()

    def test_partial_env_raises(self):
        env = {"PASSBOLT_BASE_URL": "https://pb.test"}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ValueError):
                load_config_from_env()

    def test_valid_env(self):
        env = {
            "PASSBOLT_BASE_URL": "https://pb.test",
            "PASSBOLT_GPG_KEY_FILE": "/tmp/key.asc",
            "PASSBOLT_GPG_PASSPHRASE": "secret",
        }
        key_content = "fake-armored-private-key-block-for-testing"
        with patch.dict("os.environ", env, clear=True):
            with patch("builtins.open", mock_open(read_data=key_content)):
                config = load_config_from_env()

        assert config["base_url"] == "https://pb.test"
        assert config["private_key"] == "fake-armored-private-key-block-for-testing"
        assert config["passphrase"] == "secret"


def _make_mock_auth() -> MagicMock:
    mock_auth = MagicMock()
    mock_auth.user_id = "user-uuid-1"
    mock_auth.base_url = "https://pb.test"
    return mock_auth


@pytest.fixture
def mock_gpg_auth():
    with patch("passbolt.helper.PassboltGPGAuth") as mock_cls:
        mock_auth = _make_mock_auth()
        mock_cls.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def client(mock_gpg_auth):
    config = {
        "base_url": "https://pb.test",
        "private_key": "---KEY---",
        "passphrase": "pass",
    }
    c = PassboltClient(config=config)
    c._resource_type_ids = {
        "password-string": "rt-pw-string",
        "password-and-description": "rt-pw-desc",
    }
    return c


class TestPassboltClient:
    def test_find_resource_by_name_found(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": [
                {
                    "id": "r1",
                    "name": "MySecret",
                    "username": "admin",
                    "uri": "https://example.com",
                    "resource_type_id": "rt-1",
                },
                {
                    "id": "r2",
                    "name": "Other",
                    "username": None,
                    "uri": None,
                    "resource_type_id": "rt-2",
                },
            ]
        }

        result = client.find_resource_by_name("MySecret")

        assert result is not None
        assert result.id == "r1"
        assert result.name == "MySecret"

    def test_find_resource_by_name_not_found(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": [{"id": "r1", "name": "Other", "resource_type_id": "rt-1"}]
        }

        result = client.find_resource_by_name("Missing")
        assert result is None

    def test_get_resource(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": {
                "id": "r1",
                "name": "Secret",
                "username": "user",
                "uri": "https://test.com",
                "resource_type_id": "rt-1",
            }
        }

        result = client.get_resource("r1")
        assert result.id == "r1"
        assert result.name == "Secret"
        mock_gpg_auth.get.assert_called_with("/resources/r1.json")

    def test_get_decrypted_secret_json(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {"body": {"data": "encrypted-armored"}}
        mock_gpg_auth._decrypt.return_value = json.dumps(
            {"password": "pass123", "description": "desc"}
        )

        result = client.get_decrypted_secret("r1")

        assert isinstance(result, dict)
        assert result["password"] == "pass123"

    def test_get_decrypted_secret_bytes(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {"body": {"data": "encrypted"}}
        mock_gpg_auth._decrypt.return_value = json.dumps({"password": "p"}).encode()

        result = client.get_decrypted_secret("r1")
        assert isinstance(result, dict)
        assert result["password"] == "p"

    def test_get_decrypted_secret_plain_string(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {"body": {"data": "encrypted"}}
        mock_gpg_auth._decrypt.return_value = "just-a-password"

        result = client.get_decrypted_secret("r1")
        assert result == "just-a-password"

    def test_create_resource_with_custom_field(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": {"gpgkey": {"armored_key": "---PUB---"}}
        }
        mock_gpg_auth._encrypt.return_value = "-----BEGIN PGP MESSAGE-----"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"body": {"id": "new-r1"}}
        mock_gpg_auth.post.return_value = mock_response

        field = CustomField(key="api_token", value="tok-123")
        resource_id = client.create_resource_with_custom_field(
            name="NewSecret",
            password="pass",
            field=field,
            username="admin",
            uri="https://app.test",
            description="my desc",
        )

        assert resource_id == "new-r1"
        mock_gpg_auth.post.assert_called_once()

        call_payload = mock_gpg_auth.post.call_args[0][1]
        assert call_payload["name"] == "NewSecret"
        assert call_payload["username"] == "admin"
        assert call_payload["uri"] == "https://app.test"
        assert call_payload["resource_type_id"] == "rt-pw-desc"

        encrypt_plaintext = mock_gpg_auth._encrypt.call_args[0][0]
        parsed = json.loads(encrypt_plaintext)
        assert parsed["password"] == "pass"
        assert parsed["description"] == "my desc"
        assert parsed["api_token"] == "tok-123"

    def test_create_resource_minimal(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": {"gpgkey": {"armored_key": "---PUB---"}}
        }
        mock_gpg_auth._encrypt.return_value = "encrypted"

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"body": {"id": "r2"}}
        mock_gpg_auth.post.return_value = mock_response

        field = CustomField(key="env", value="prod")
        resource_id = client.create_resource_with_custom_field(
            name="Minimal",
            password="pw",
            field=field,
        )

        assert resource_id == "r2"
        call_payload = mock_gpg_auth.post.call_args[0][1]
        assert "username" not in call_payload
        assert "uri" not in call_payload

    def test_create_resource_failure(self, client, mock_gpg_auth):
        mock_gpg_auth.get.return_value = {
            "body": {"gpgkey": {"armored_key": "---PUB---"}}
        }
        mock_gpg_auth._encrypt.return_value = "encrypted"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"header": {"message": "Validation failed"}}
        mock_response.text = "Validation failed"
        mock_gpg_auth.post.return_value = mock_response

        field = CustomField(key="k", value="v")
        with pytest.raises(RuntimeError, match="Failed to create resource"):
            client.create_resource_with_custom_field(
                name="Bad", password="pw", field=field
            )

    def test_add_custom_field_to_existing_dict_secret(self, client, mock_gpg_auth):
        def get_side_effect(path):
            if "/secrets/" in path:
                return {"body": {"data": "encrypted"}}
            if "/resources/" in path:
                return {
                    "body": {
                        "id": "r1",
                        "name": "Existing",
                        "username": "user",
                        "uri": None,
                        "resource_type_id": "rt-1",
                    }
                }
            if "/users/" in path:
                return {"body": {"gpgkey": {"armored_key": "---PUB---"}}}
            return {}

        mock_gpg_auth.get.side_effect = get_side_effect
        mock_gpg_auth._decrypt.return_value = json.dumps(
            {"password": "old-pass", "description": "existing desc"}
        )
        mock_gpg_auth._encrypt.return_value = "re-encrypted"

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_gpg_auth.put.return_value = mock_put_response

        field = CustomField(key="ssh_key", value="ssh-rsa AAAA...")
        client.add_custom_field_to_existing("r1", field)

        mock_gpg_auth.put.assert_called_once()
        put_path = mock_gpg_auth.put.call_args[0][0]
        assert put_path == "/resources/r1.json"

        put_payload = mock_gpg_auth.put.call_args[0][1]
        assert put_payload["name"] == "Existing"
        assert put_payload["resource_type_id"] == "rt-1"
        assert len(put_payload["secrets"]) == 1
        assert put_payload["secrets"][0]["user_id"] == "user-uuid-1"

        encrypt_plaintext = mock_gpg_auth._encrypt.call_args[0][0]
        parsed = json.loads(encrypt_plaintext)
        assert parsed["password"] == "old-pass"
        assert parsed["description"] == "existing desc"
        assert parsed["ssh_key"] == "ssh-rsa AAAA..."

    def test_add_custom_field_to_existing_string_secret(self, client, mock_gpg_auth):
        def get_side_effect(path):
            if "/secrets/" in path:
                return {"body": {"data": "encrypted"}}
            if "/resources/" in path:
                return {
                    "body": {
                        "id": "r2",
                        "name": "Simple",
                        "resource_type_id": "rt-2",
                    }
                }
            if "/users/" in path:
                return {"body": {"gpgkey": {"armored_key": "---PUB---"}}}
            return {}

        mock_gpg_auth.get.side_effect = get_side_effect
        mock_gpg_auth._decrypt.return_value = "plain-password"
        mock_gpg_auth._encrypt.return_value = "re-encrypted"

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_gpg_auth.put.return_value = mock_put_response

        field = CustomField(key="env", value="staging")
        client.add_custom_field_to_existing("r2", field)

        encrypt_plaintext = mock_gpg_auth._encrypt.call_args[0][0]
        parsed = json.loads(encrypt_plaintext)
        assert parsed["password"] == "plain-password"
        assert parsed["env"] == "staging"

    def test_add_custom_field_update_failure(self, client, mock_gpg_auth):
        def get_side_effect(path):
            if "/secrets/" in path:
                return {"body": {"data": "encrypted"}}
            if "/resources/" in path:
                return {
                    "body": {
                        "id": "r1",
                        "name": "Fail",
                        "resource_type_id": "rt-1",
                    }
                }
            if "/users/" in path:
                return {"body": {"gpgkey": {"armored_key": "---PUB---"}}}
            return {}

        mock_gpg_auth.get.side_effect = get_side_effect
        mock_gpg_auth._decrypt.return_value = json.dumps({"password": "p"})
        mock_gpg_auth._encrypt.return_value = "encrypted"

        mock_put_response = MagicMock()
        mock_put_response.status_code = 403
        mock_put_response.json.return_value = {"header": {"message": "Forbidden"}}
        mock_put_response.text = "Forbidden"
        mock_gpg_auth.put.return_value = mock_put_response

        field = CustomField(key="k", value="v")
        with pytest.raises(RuntimeError, match="Failed to update resource"):
            client.add_custom_field_to_existing("r1", field)

    def test_overwrite_existing_custom_field(self, client, mock_gpg_auth):
        def get_side_effect(path):
            if "/secrets/" in path:
                return {"body": {"data": "encrypted"}}
            if "/resources/" in path:
                return {
                    "body": {
                        "id": "r1",
                        "name": "HasField",
                        "resource_type_id": "rt-1",
                    }
                }
            if "/users/" in path:
                return {"body": {"gpgkey": {"armored_key": "---PUB---"}}}
            return {}

        mock_gpg_auth.get.side_effect = get_side_effect
        mock_gpg_auth._decrypt.return_value = json.dumps(
            {"password": "pw", "api_key": "old-value"}
        )
        mock_gpg_auth._encrypt.return_value = "re-encrypted"

        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_gpg_auth.put.return_value = mock_put_response

        field = CustomField(key="api_key", value="new-value")
        client.add_custom_field_to_existing("r1", field)

        encrypt_plaintext = mock_gpg_auth._encrypt.call_args[0][0]
        parsed = json.loads(encrypt_plaintext)
        assert parsed["api_key"] == "new-value"
        assert parsed["password"] == "pw"

    def test_resource_type_ids_lazy_load(self, client, mock_gpg_auth):
        client._resource_type_ids = None
        mock_gpg_auth.get.return_value = {
            "body": [
                {"slug": "password-string", "id": "rt-1"},
                {"slug": "password-and-description", "id": "rt-2"},
            ]
        }

        result = client.resource_type_ids

        assert result == {"password-string": "rt-1", "password-and-description": "rt-2"}
        mock_gpg_auth.get.assert_called_with("/resource-types.json")
