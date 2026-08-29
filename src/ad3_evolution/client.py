from __future__ import annotations

import json
import mimetypes
import re
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .profiles import API_OPERATIONS, IDEMPOTENT, ROUTES
from .security import safe_error, validate_instance


class EvolutionError(RuntimeError):
    pass


_PATH_PARAMETER = re.compile(r"{([A-Za-z][A-Za-z0-9_]*)}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class EvolutionClient:
    """HTTP client whose outbound capabilities are pinned to Evolution 2.3.7."""

    profile = "evolution-2.3.7"

    def __init__(self, base_url: str, api_key: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        operation: str,
        instance: str = "",
        payload: dict | None = None,
        query: dict | None = None,
        params: dict | None = None,
        file_path: str | Path | None = None,
        file_field: str = "file",
    ) -> dict:
        method, path, read_only = self._route(operation, instance, params)
        if query:
            if not isinstance(query, dict):
                raise EvolutionError("query is invalid")
            path += "?" + urlencode({key: value for key, value in query.items() if value is not None}, doseq=True)
        url = self.base_url + path
        body, content_type = self._body(method, payload, file_path, file_field)
        headers = {"Content-Type": content_type}
        if self.api_key:
            headers["apikey"] = self.api_key
        attempts = 3 if read_only else 1
        for attempt in range(attempts):
            try:
                request = Request(url, data=body, method=method, headers=headers)
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except (URLError, HTTPError, TimeoutError) as exc:
                if attempt + 1 == attempts:
                    raise EvolutionError(f"Evolution request failed: {safe_error(exc)}") from None
                time.sleep(0.15 * (attempt + 1))
        raise AssertionError("unreachable")

    def _route(self, operation: str, instance: str, params: dict | None) -> tuple[str, str, bool]:
        legacy = ROUTES.get(operation)
        legacy_operation = legacy is not None
        if legacy is not None:
            method, path = legacy
            read_only = operation in IDEMPOTENT
        else:
            catalogued = API_OPERATIONS.get(operation)
            if catalogued is None:
                raise EvolutionError("operation is not in the explicit capability matrix")
            method, path, read_only = catalogued.method, catalogued.path, catalogued.read_only

        if params is not None and not isinstance(params, dict):
            raise EvolutionError("route parameters are invalid")
        values = dict(params or {})
        required = set(_PATH_PARAMETER.findall(path))
        allowed = required - {"instance"}
        if set(values) - allowed:
            raise EvolutionError("unexpected route parameter")
        if "instance" in required:
            try:
                values["instance"] = validate_instance(instance)
            except ValueError as exc:
                raise EvolutionError(str(exc)) from None
        elif instance and not legacy_operation:
            raise EvolutionError("operation does not accept an instance")

        missing = required - set(values)
        if missing:
            raise EvolutionError("missing route parameter")
        for name in required:
            value = values[name]
            if name != "instance":
                value = self._path_parameter(value)
            path = path.replace("{" + name + "}", quote(value, safe=""))
        return method, path, read_only

    @staticmethod
    def _path_parameter(value: object) -> str:
        if not isinstance(value, str) or not value or _CONTROL.search(value) or any(char in value for char in "/\\?#"):
            raise EvolutionError("route parameter is invalid")
        return value

    def _body(
        self,
        method: str,
        payload: dict | None,
        file_path: str | Path | None,
        file_field: str,
    ) -> tuple[bytes | None, str]:
        if payload is not None and not isinstance(payload, dict):
            raise EvolutionError("payload is invalid")
        if file_path is not None:
            if method == "GET":
                raise EvolutionError("GET operations cannot upload a file")
            return self._multipart(payload or {}, Path(file_path), file_field)
        if method == "GET":
            if payload:
                raise EvolutionError("GET operations accept query parameters, not a JSON payload")
            return None, "application/json"
        if payload is None:
            return None, "application/json"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json"

    @staticmethod
    def _multipart(payload: dict, file_path: Path, field: str) -> tuple[bytes, str]:
        if not file_path.is_file():
            raise EvolutionError("upload file cannot be read")
        if not isinstance(field, str) or not field or _CONTROL.search(field) or any(char in field for char in '"\\\r\n'):
            raise EvolutionError("upload field is invalid")

        boundary = "----AD3Evolution" + secrets.token_hex(16)
        chunks: list[bytes] = []
        for name, value in payload.items():
            if not isinstance(name, str) or not name or _CONTROL.search(name) or any(char in name for char in '"\\\r\n'):
                raise EvolutionError("multipart payload field is invalid")
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            chunks.extend(
                (
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    rendered.encode("utf-8"),
                    b"\r\n",
                )
            )

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{field}"; filename="{file_path.name}"\r\n'.encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                file_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            )
        )
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
