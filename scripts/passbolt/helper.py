import json
import os
import re
from typing import Optional
from urllib.parse import unquote

import httpx
import structlog
from pgpy import PGPKey, PGPMessage
from pydantic import BaseModel, Field

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def configure_log_level(verbose: bool = False):
    level = 10 if verbose else 20
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))


class CustomField(BaseModel):
    model_config = {"frozen": True}

    key: str = Field(..., min_length=1)
    value: str = Field(...)
    field_type: str = Field(default="text")


class ResourceInfo(BaseModel):
    id: str
    name: str
    username: Optional[str] = None
    uri: Optional[str] = None
    resource_type_id: str


class PassboltConfig(BaseModel):
    base_url: str
    private_key: str
    passphrase: str


def load_config_from_env() -> dict:
    base_url = os.environ.get("PASSBOLT_BASE_URL")
    gpg_key_file = os.environ.get("PASSBOLT_GPG_KEY_FILE")
    passphrase = os.environ.get("PASSBOLT_GPG_PASSPHRASE")

    if not all([base_url, gpg_key_file, passphrase]):
        raise ValueError(
            "PASSBOLT_BASE_URL, PASSBOLT_GPG_KEY_FILE, and "
            "PASSBOLT_GPG_PASSPHRASE must be set"
        )

    key_path = os.path.expanduser(gpg_key_file)  # type: ignore[arg-type]
    with open(key_path) as f:
        private_key = f.read()

    return {
        "base_url": base_url,
        "private_key": private_key,
        "passphrase": passphrase,
    }


class PassboltGPGAuth:
    def __init__(self, base_url: str, private_key_armored: str, passphrase: str):
        self.base_url = base_url.rstrip("/")
        self.passphrase = passphrase
        self.key, _ = PGPKey.from_blob(private_key_armored)
        self.fingerprint = str(self.key.fingerprint).replace(" ", "")
        self.session = httpx.Client(timeout=30)
        self.user_id: Optional[str] = None
        self._login()

    def _login(self):
        login_url = f"{self.base_url}/auth/login.json"

        stage1_resp = self.session.post(
            login_url,
            json={"data": {"gpg_auth": {"keyid": self.fingerprint}}},
        )
        stage1_resp.raise_for_status()

        encrypted_token = unquote(
            stage1_resp.headers.get("x-gpgauth-user-auth-token", "")
        ).replace("\\+", " ")

        nonce = self._decrypt(encrypted_token)
        if isinstance(nonce, bytes):
            nonce = nonce.decode()

        stage2_resp = self.session.post(
            login_url,
            json={
                "data": {
                    "gpg_auth": {
                        "keyid": self.fingerprint,
                        "user_token_result": str(nonce),
                    }
                }
            },
        )
        stage2_resp.raise_for_status()

        me_resp = self.session.get(f"{self.base_url}/users/me.json")
        cookie_header = me_resp.headers.get("set-cookie", "")
        csrf_match = re.search(r"csrfToken=([^;]+)", cookie_header)
        if csrf_match:
            self.session.headers["X-CSRF-Token"] = csrf_match.group(1)

        me_body = me_resp.json()
        self.user_id = me_body["body"]["id"]

    def _decrypt(self, armored_message: str) -> str:
        pgp_msg = PGPMessage.from_blob(armored_message)
        with self.key.unlock(self.passphrase):
            return self.key.decrypt(pgp_msg).message  # type: ignore[return-value]

    def _encrypt(self, plaintext: str, recipient_armored_key: str) -> str:
        pubkey, _ = PGPKey.from_blob(recipient_armored_key)
        pgp_msg = PGPMessage.new(plaintext)
        with self.key.unlock(self.passphrase):
            pgp_msg |= self.key.sign(pgp_msg)
        return str(pubkey.encrypt(pgp_msg))

    def get(self, path: str) -> dict:
        resp = self.session.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: dict) -> httpx.Response:
        return self.session.post(f"{self.base_url}{path}", json=payload)

    def put(self, path: str, payload: dict) -> httpx.Response:
        return self.session.put(f"{self.base_url}{path}", json=payload)


class PassboltClient:
    def __init__(self, config: Optional[dict] = None):
        self.log = get_logger().bind(component="passbolt_client")
        cfg = config or load_config_from_env()
        self.auth = PassboltGPGAuth(
            base_url=cfg["base_url"],
            private_key_armored=cfg["private_key"],
            passphrase=cfg["passphrase"],
        )
        self._resource_type_ids: Optional[dict[str, str]] = None
        self.log.debug("authenticated", user_id=self.auth.user_id)

    @property
    def resource_type_ids(self) -> dict[str, str]:
        if self._resource_type_ids is None:
            data = self.auth.get("/resource-types.json")
            self._resource_type_ids = {
                item["slug"]: item["id"] for item in data["body"]
            }
        return self._resource_type_ids

    def find_resource_by_name(self, name: str) -> Optional[ResourceInfo]:
        data = self.auth.get("/resources.json")
        for r in data["body"]:
            if r["name"] == name:
                return ResourceInfo(
                    id=r["id"],
                    name=r["name"],
                    username=r.get("username"),
                    uri=r.get("uri"),
                    resource_type_id=r["resource_type_id"],
                )
        return None

    def get_resource(self, resource_id: str) -> ResourceInfo:
        data = self.auth.get(f"/resources/{resource_id}.json")
        r = data["body"]
        return ResourceInfo(
            id=r["id"],
            name=r["name"],
            username=r.get("username"),
            uri=r.get("uri"),
            resource_type_id=r["resource_type_id"],
        )

    def get_decrypted_secret(self, resource_id: str) -> dict | str:
        data = self.auth.get(f"/secrets/resource/{resource_id}.json")
        encrypted = data["body"]["data"]
        decrypted = self.auth._decrypt(encrypted)
        if isinstance(decrypted, bytes):
            decrypted = decrypted.decode()
        try:
            return json.loads(decrypted)
        except (json.JSONDecodeError, TypeError):
            return str(decrypted)

    def _encrypt_secret(self, secret_data: dict | str) -> str:
        user_data = self.auth.get(f"/users/{self.auth.user_id}.json")
        armored_key = user_data["body"]["gpgkey"]["armored_key"]
        plaintext = (
            json.dumps(secret_data) if isinstance(secret_data, dict) else secret_data
        )
        return self.auth._encrypt(plaintext, armored_key)

    def create_resource_with_custom_field(
        self,
        name: str,
        password: str,
        field: CustomField,
        username: Optional[str] = None,
        uri: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        secret_data: dict = {"password": password}
        if description:
            secret_data["description"] = description
        secret_data[field.key] = field.value

        resource_type_id = self.resource_type_ids.get(
            "password-and-description",
            list(self.resource_type_ids.values())[0],
        )

        payload: dict = {
            "name": name,
            "resource_type_id": resource_type_id,
            "secrets": [{"data": self._encrypt_secret(secret_data)}],
        }
        if username:
            payload["username"] = username
        if uri:
            payload["uri"] = uri

        response = self.auth.post("/resources.json", payload)
        body = response.json()

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create resource: {response.status_code} "
                f"{body.get('header', {}).get('message', response.text)}"
            )

        resource_id = body["body"]["id"]
        self.log.info(
            "created_resource",
            resource_id=resource_id,
            name=name,
            custom_field=field.key,
        )
        return resource_id

    def add_custom_field_to_existing(
        self,
        resource_id: str,
        field: CustomField,
    ) -> None:
        current_secret = self.get_decrypted_secret(resource_id)

        if isinstance(current_secret, str):
            secret_data: dict = {"password": current_secret}
        else:
            secret_data = dict(current_secret)

        secret_data[field.key] = field.value

        resource = self.get_resource(resource_id)

        update_payload: dict = {
            "name": resource.name,
            "resource_type_id": resource.resource_type_id,
            "secrets": [
                {
                    "user_id": self.auth.user_id,
                    "data": self._encrypt_secret(secret_data),
                }
            ],
        }

        response = self.auth.put(f"/resources/{resource_id}.json", update_payload)

        if response.status_code not in (200, 201):
            body = response.json()
            raise RuntimeError(
                f"Failed to update resource: {response.status_code} "
                f"{body.get('header', {}).get('message', response.text)}"
            )

        self.log.info(
            "added_custom_field",
            resource_id=resource_id,
            resource_name=resource.name,
            custom_field=field.key,
        )
