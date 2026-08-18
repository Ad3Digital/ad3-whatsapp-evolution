from __future__ import annotations
import json, time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from .profiles import ROUTES, IDEMPOTENT, EVOLUTION_2_3_7
from .security import safe_error
from .security import validate_instance

class EvolutionError(RuntimeError): pass

class EvolutionClient:
    """HTTP client whose known capabilities are pinned to Evolution 2.3.7."""
    profile = EVOLUTION_2_3_7
    def __init__(self, base_url: str, api_key: str, timeout: float = 10): self.base_url, self.api_key, self.timeout = base_url.rstrip("/"), api_key, timeout
    def request(self, operation: str, instance: str = "", payload: dict | None = None, query: dict | None = None) -> dict:
        if operation not in ROUTES: raise EvolutionError("operation is not in explicit capability matrix")
        method, path = ROUTES[operation]
        if "{instance}" in path:
            try:
                instance = validate_instance(instance)
            except ValueError as exc:
                raise EvolutionError(str(exc)) from None
            url = self.base_url + path.format(instance=quote(instance, safe=""))
        else:
            url = self.base_url + path
        if query: url += "?" + urlencode({k:v for k,v in query.items() if v is not None}, doseq=True)
        body = None if method == "GET" or payload is None else json.dumps(payload).encode()
        headers = {"Content-Type":"application/json"}
        if self.api_key: headers["apikey"] = self.api_key
        attempts = 3 if operation in IDEMPOTENT else 1
        for attempt in range(attempts):
            try:
                with urlopen(Request(url, data=body, method=method, headers=headers), timeout=self.timeout) as r:
                    raw = r.read().decode(); return json.loads(raw) if raw else {}
            except (URLError, HTTPError, TimeoutError) as e:
                if attempt + 1 == attempts: raise EvolutionError(f"Evolution request failed: {safe_error(e)}") from None
                time.sleep(0.15 * (attempt + 1))
        raise AssertionError("unreachable")
