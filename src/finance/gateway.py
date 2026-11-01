"""Authenticated Supabase HTTPS gateway.

The secret key lives in Muse's Secure Vault under the registered
connection `custom.supabase`. This module never sees the key: it places
an `hsurr:` surrogate via the credential broker, and Muse's egress
proxy substitutes the real credential only for the registered host.

Transport is urllib on purpose: it is the combination verified
end-to-end on 1 Nov 2026 (probe_auth_users.py). The broker's httpx
branch mis-detects the venv's httpx Request type, and httpx's env
parser rejects this environment's NO_PROXY — urllib handles both.
"""
from __future__ import annotations

import json as _json
import sys
import urllib.error
import urllib.parse
import urllib.request

from .errors import OutcomeUnknown, TemporarilyUnavailable

_BROKER_DIR = "/opt/muse/skills/custom-connector-setup/bin"
if _BROKER_DIR not in sys.path:
    sys.path.insert(0, _BROKER_DIR)

PROVIDER_ID = "custom.supabase"
TIMEOUT_SECONDS = 30


class SupabaseGateway:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.host = self.base_url.replace("https://", "")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        headers: dict | None = None,
        write: bool = False,
    ) -> tuple[int, object]:
        from dynamic_credentials import add_surrogate_to_request

        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = None
        req_headers = dict(headers or {})
        if json_body is not None:
            data = _json.dumps(json_body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=data, method=method, headers=req_headers
        )
        add_surrogate_to_request(req, PROVIDER_ID, allowed_hosts=[self.host])
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            if write:
                raise OutcomeUnknown(
                    f"transport error during write: {exc.reason}"
                ) from exc
            raise TemporarilyUnavailable(
                f"transport error: {exc.reason}"
            ) from exc
        try:
            parsed: object = _json.loads(raw) if raw else None
        except ValueError:
            parsed = raw
        return status, parsed
