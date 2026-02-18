import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from passbolt.add_custom_field import app
from passbolt.helper import ResourceInfo

runner = CliRunner()


@pytest.fixture
def mock_client():
    with patch("passbolt.add_custom_field.PassboltClient") as mock_cls:
        mock = MagicMock()
        mock_cls.return_value = mock
        yield mock


class TestCLIValidation:
    def test_no_target_exits_with_error(self, mock_client):
        result = runner.invoke(app, ["--field-name", "key", "--field-value", "val"])
        assert result.exit_code == 1

    def test_conflicting_new_and_existing(self, mock_client):
        result = runner.invoke(
            app,
            [
                "--field-name",
                "key",
                "--field-value",
                "val",
                "--name",
                "New",
                "--resource-id",
                "r1",
            ],
        )
        assert result.exit_code == 1

    def test_new_resource_missing_password(self, mock_client):
        result = runner.invoke(
            app,
            [
                "--field-name",
                "key",
                "--field-value",
                "val",
                "--name",
                "New",
            ],
        )
        assert result.exit_code == 1


class TestCLICreateNew:
    def test_create_new_resource(self, mock_client):
        mock_client.create_resource_with_custom_field.return_value = "new-uuid"

        result = runner.invoke(
            app,
            [
                "--field-name",
                "api_key",
                "--field-value",
                "tok-123",
                "--name",
                "MyApp",
                "--password",
                "pw123",
                "--username",
                "admin",
                "--uri",
                "https://app.test",
                "--description",
                "desc",
            ],
        )

        assert result.exit_code == 0
        mock_client.create_resource_with_custom_field.assert_called_once()
        call_kwargs = mock_client.create_resource_with_custom_field.call_args[1]
        assert call_kwargs["name"] == "MyApp"
        assert call_kwargs["password"] == "pw123"
        assert call_kwargs["field"].key == "api_key"
        assert call_kwargs["field"].value == "tok-123"


class TestCLIUpdateExisting:
    def test_update_by_resource_id(self, mock_client):
        result = runner.invoke(
            app,
            [
                "--field-name",
                "env",
                "--field-value",
                "prod",
                "--resource-id",
                "r1",
            ],
        )

        assert result.exit_code == 0
        mock_client.add_custom_field_to_existing.assert_called_once()
        call_kwargs = mock_client.add_custom_field_to_existing.call_args[1]
        assert call_kwargs["resource_id"] == "r1"
        assert call_kwargs["field"].key == "env"

    def test_update_by_resource_name(self, mock_client):
        mock_client.find_resource_by_name.return_value = ResourceInfo(
            id="r1", name="MyApp", resource_type_id="rt-1"
        )

        result = runner.invoke(
            app,
            [
                "--field-name",
                "env",
                "--field-value",
                "staging",
                "--resource-name",
                "MyApp",
            ],
        )

        assert result.exit_code == 0
        mock_client.find_resource_by_name.assert_called_once_with("MyApp")
        mock_client.add_custom_field_to_existing.assert_called_once()

    def test_update_by_name_not_found(self, mock_client):
        mock_client.find_resource_by_name.return_value = None

        result = runner.invoke(
            app,
            [
                "--field-name",
                "env",
                "--field-value",
                "dev",
                "--resource-name",
                "Missing",
            ],
        )

        assert result.exit_code == 1


class TestCLIAuthFailure:
    def test_auth_failure_exits(self):
        with patch(
            "passbolt.add_custom_field.PassboltClient",
            side_effect=Exception("GPG auth failed"),
        ):
            result = runner.invoke(
                app,
                [
                    "--field-name",
                    "k",
                    "--field-value",
                    "v",
                    "--resource-id",
                    "r1",
                ],
            )
            assert result.exit_code == 1
