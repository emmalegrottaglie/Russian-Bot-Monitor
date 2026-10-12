"""Posting to X (Twitter) with OAuth 1.0a user context.

X bills per post under the pay-per-use plan, and a post containing a URL costs
far more than a plain one, so alerts leave the link out by default.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote

import httpx

POST_URL = "https://api.x.com/2/tweets"


def _enc(value: str) -> str:
    return quote(str(value), safe="~-._")


def oauth1_header(method: str, url: str, consumer_key: str, consumer_secret: str, token: str,
                  token_secret: str, params: dict | None = None, nonce: str | None = None,
                  timestamp: int | None = None) -> str:
    """RFC 5849 HMAC-SHA1 Authorization header. `params` are query/form parameters;
    a JSON body is not part of the signature."""
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    pairs = sorted((_enc(k), _enc(v)) for k, v in {**(params or {}), **oauth}.items())
    param_str = "&".join(f"{k}={v}" for k, v in pairs)
    base = "&".join((method.upper(), _enc(url), _enc(param_str)))
    key = f"{_enc(consumer_secret)}&{_enc(token_secret)}"
    oauth["oauth_signature"] = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    ).decode()
    return "OAuth " + ", ".join(f'{_enc(k)}="{_enc(v)}"' for k, v in sorted(oauth.items()))


async def post(settings, text: str) -> str:
    """Post `text`; returns the new post id. Raises httpx.HTTPError on failure."""
    header = oauth1_header("POST", POST_URL, settings.x_api_key, settings.x_api_secret,
                           settings.x_access_token, settings.x_access_secret)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(POST_URL, json={"text": text}, headers={"Authorization": header})
        r.raise_for_status()
        return r.json()["data"]["id"]
