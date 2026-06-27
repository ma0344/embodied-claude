"""Google OAuth — desktop flow + refresh token storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource

from presence_ui.gapi.scopes import DEFAULT_PREP_SCOPES, calendar_scopes


class GoogleAuthError(RuntimeError):
    """Missing or invalid Google OAuth configuration."""


def default_token_path() -> Path:
    env = os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude" / "google" / "oauth-token.json"


def default_credentials_path() -> Path:
    env = os.environ.get("GOOGLE_OAUTH_CREDENTIALS_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    for candidate in (Path.cwd(), *Path.cwd().parents):
        scripts_cred = candidate / "scripts" / "google-oauth-client.json"
        if scripts_cred.exists():
            return scripts_cred
        root_cred = candidate / "google-oauth-client.json"
        if root_cred.exists():
            return root_cred
    return Path.cwd() / "scripts" / "google-oauth-client.json"


def _client_config_from_env() -> dict[str, Any] | None:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def load_oauth_client_config() -> dict[str, Any]:
    """OAuth 2.0 client JSON (Desktop) or GOOGLE_OAUTH_CLIENT_ID/SECRET env."""
    from_env = _client_config_from_env()
    if from_env is not None:
        return from_env

    cred_path = default_credentials_path()
    if not cred_path.exists():
        raise GoogleAuthError(
            "Google OAuth client not found. Set GOOGLE_OAUTH_CREDENTIALS_PATH to your "
            "OAuth 2.0 Client ID JSON (Desktop app), or GOOGLE_OAUTH_CLIENT_ID + "
            "GOOGLE_OAUTH_CLIENT_SECRET. API keys alone cannot access Calendar."
        )

    data = json.loads(cred_path.read_text(encoding="utf-8"))
    if "installed" in data:
        return data
    if "web" in data:
        raise GoogleAuthError(
            f"{cred_path}: client type is 'web'. Create a Desktop OAuth client in "
            "Google Cloud Console and download that JSON instead."
        )
    raise GoogleAuthError(f"{cred_path}: expected 'installed' OAuth client JSON.")


def load_credentials(
    *,
    scopes: tuple[str, ...] = DEFAULT_PREP_SCOPES,
    token_path: Path | None = None,
) -> Credentials | None:
    path = token_path or default_token_path()
    if not path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(path), scopes=list(scopes))
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds, path=path)
    return creds


def save_credentials(creds: Credentials, *, path: Path | None = None) -> Path:
    target = path or default_token_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(creds.to_json(), encoding="utf-8")
    return target


def run_oauth_consent(
    *,
    scopes: tuple[str, ...] = DEFAULT_PREP_SCOPES,
    token_path: Path | None = None,
) -> Credentials:
    """Open browser for consent; save refresh token."""
    client_config = load_oauth_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, scopes=list(scopes))
    creds = flow.run_local_server(port=0, open_browser=True)
    saved = save_credentials(creds, path=token_path or default_token_path())
    print(f"Saved OAuth token to {saved}")
    return creds


def require_credentials(
    *,
    scopes: tuple[str, ...] = DEFAULT_PREP_SCOPES,
    token_path: Path | None = None,
) -> Credentials:
    creds = load_credentials(scopes=scopes, token_path=token_path)
    if creds and creds.valid:
        return creds
    raise GoogleAuthError(
        "No valid Google OAuth token. Run: cd presence-ui && uv run google-oauth-consent"
    )


def get_calendar_service(
    *,
    scopes: tuple[str, ...] | None = None,
    token_path: Path | None = None,
) -> Resource:
    if scopes is None:
        scopes = calendar_scopes()
    creds = require_credentials(scopes=scopes, token_path=token_path)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
