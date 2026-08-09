"""Shared GET-JSON helper for the TMDB and Watchmode clients.

Some networks (corporate/AV TLS inspection) reset httpx's raw OpenSSL
handshake to certain hosts while the system `curl` (Schannel on Windows,
OpenSSL trusted-store on Linux) goes through fine. We try httpx first and
transparently fall back to shelling out to `curl` on a transport error, so
the app is resilient regardless of the network it runs on.
"""

import json
import subprocess
import time

import httpx

# Once httpx has proven unusable on this network (see module docstring), stop
# paying for a doomed httpx attempt on every subsequent call and go straight to
# curl. A benign race across threads (a couple of extra httpx attempts before
# this flips) is harmless, so no lock is needed here.
_httpx_broken = False


class HttpError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body[:300]}")


def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 20.0,
    retries: int = 5,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return _get_once(url, params, headers, timeout)
        except (httpx.TransportError, HttpError) as exc:
            last_error = exc
            if isinstance(exc, HttpError) and 400 <= exc.status_code < 500:
                raise  # client errors (bad key, 404, ...) won't be fixed by retrying
            if attempt < retries - 1:
                time.sleep(0.6 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _get_once(url: str, params: dict | None, headers: dict | None, timeout: float) -> dict:
    global _httpx_broken
    if not _httpx_broken:
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=timeout)
        except httpx.TransportError:
            _httpx_broken = True
            return _curl_get_json(url, params, headers, timeout)

        if response.status_code >= 400:
            raise HttpError(response.status_code, response.text)
        return response.json()

    return _curl_get_json(url, params, headers, timeout)


def _curl_get_json(url: str, params: dict | None, headers: dict | None, timeout: float) -> dict:
    full_url = str(httpx.URL(url, params=params or {}))
    marker = "__HTTP_STATUS__:"
    cmd = ["curl", "-sS", "-m", str(int(timeout)), "-w", f"\n{marker}%{{http_code}}", full_url]
    for key, value in (headers or {}).items():
        cmd += ["-H", f"{key}: {value}"]

    # TMDB/OMDb responses are UTF-8 and often contain non-ASCII text (accented
    # names, em dashes, non-English titles); without an explicit encoding,
    # Windows decodes subprocess output with the system codepage (cp1252) and
    # crashes with a UnicodeDecodeError on anything outside that range.
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise HttpError(0, result.stderr or "curl fallback failed")

    body, _, status_part = result.stdout.rpartition(marker)
    status_code = int(status_part.strip() or 0)
    body = body.strip()

    if status_code >= 400 or status_code == 0:
        raise HttpError(status_code, body)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise HttpError(status_code, body) from exc
