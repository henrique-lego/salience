# OAuth 2.0 PKCE flow for X API user context authentication
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPES = ["tweet.read", "users.read", "bookmark.read", "offline.access"]
DEFAULT_TOKEN_PATH = Path("tokens.json")


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def authorize(client_id: str, token_path: Path = DEFAULT_TOKEN_PATH) -> dict[str, str]:
    """Run the full OAuth 2.0 PKCE flow.

    Opens a browser for user authorization, catches the callback,
    exchanges the code for tokens, and saves them.
    """
    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    # Start local server to catch callback
    callback_result: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)

            callback_result["code"] = qs.get("code", [""])[0]
            callback_result["state"] = qs.get("state", [""])[0]
            callback_result["error"] = qs.get("error", [""])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Salience authorized.</h2>"
                b"<p>You can close this tab.</p></body></html>"
            )

        def log_message(self, format: str, *args: object) -> None:
            pass  # Suppress HTTP server logs

    server = HTTPServer(("localhost", 8765), CallbackHandler)
    server_thread = Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Open browser
    logger.info("Opening browser for X authorization...")
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join(timeout=120)
    server.server_close()

    if callback_result.get("error"):
        raise RuntimeError(f"Authorization failed: {callback_result['error']}")

    if callback_result.get("state") != state:
        raise RuntimeError("State mismatch – possible CSRF attack")

    code = callback_result.get("code", "")
    if not code:
        raise RuntimeError("No authorization code received")

    # Exchange code for tokens
    tokens = _exchange_code(code, verifier, client_id)
    save_tokens(tokens, token_path)

    logger.info("Authorization successful. Tokens saved to %s", token_path)
    return tokens


def _exchange_code(
    code: str, verifier: str, client_id: str
) -> dict[str, str]:
    """Exchange authorization code for access and refresh tokens."""
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(
    refresh_token: str, client_id: str
) -> dict[str, str]:
    """Refresh an expired access token."""
    response = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()


def load_tokens(token_path: Path = DEFAULT_TOKEN_PATH) -> dict[str, str] | None:
    """Load saved tokens from disk."""
    if not token_path.exists():
        return None
    with open(token_path) as f:
        return json.load(f)


def save_tokens(tokens: dict[str, str], token_path: Path = DEFAULT_TOKEN_PATH) -> None:
    """Save tokens to disk."""
    with open(token_path, "w") as f:
        json.dump(tokens, f, indent=2)


def get_valid_access_token(
    client_id: str, token_path: Path = DEFAULT_TOKEN_PATH
) -> str:
    """Get a valid access token, refreshing if needed.

    Returns the access token string. Raises if no tokens exist
    (user needs to run `salience auth` first).
    """
    tokens = load_tokens(token_path)
    if not tokens:
        logger.info("No tokens found. Launching authorization flow.")
        tokens = authorize(client_id, token_path)
        return tokens["access_token"]

    # Always try to refresh if we have a refresh token,
    # since access tokens are short-lived (~2h).
    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        try:
            new_tokens = refresh_access_token(refresh_token, client_id)
            # Preserve refresh token if not returned in response
            if "refresh_token" not in new_tokens and refresh_token:
                new_tokens["refresh_token"] = refresh_token
            save_tokens(new_tokens, token_path)
            return new_tokens["access_token"]
        except httpx.HTTPStatusError:
            logger.warning("Token refresh failed. Re-authorizing.")
            tokens = authorize(client_id, token_path)
            return tokens["access_token"]

    return tokens["access_token"]
