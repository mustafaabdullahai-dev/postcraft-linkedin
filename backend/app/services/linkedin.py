"""LinkedIn integration: OAuth helper + publish (dry-run capable)."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API = "https://api.linkedin.com"


class LinkedInError(Exception):
    pass


class LinkedInPublisher:
    """LinkedIn OAuth + publish. Multi-user: publishing uses the *logged-in
    user's* access token/URN whenever provided, so every person posts as
    themselves. Dry-run mode needs no credentials (the default)."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._dry_run = settings.linkedin_dry_run
        self._client_id = settings.linkedin_client_id
        self._client_secret = settings.linkedin_client_secret

    # ── Configuration ──────────────────────────────────────────
    def mode(self) -> str:
        return "dry_run" if not self.oauth_configured() else "oauth"

    def oauth_configured(self) -> bool:
        return bool(self._client_id and self._client_secret) and not self._dry_run

    def redirect_uri(self) -> str:
        s = self._settings
        if s.linkedin_redirect_uri:
            return s.linkedin_redirect_uri
        return f"{s.frontend_url.rstrip('/')}/api/auth/linkedin/callback"

    # ── Auth ───────────────────────────────────────────────────
    def authorize_url(self, state: str = "", redirect_uri: str = "") -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": self._settings.linkedin_scope,
            "state": state,
        }
        if not params["client_id"]:
            raise LinkedInError("LINKEDIN_CLIENT_ID is not configured.")
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        resp.raise_for_status()
        return resp.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Exchange a LinkedIn refresh_token for a fresh access token.

        LinkedIn rotates refresh tokens, so callers should persist the new
        `refresh_token`/`expires_in` returned here."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self.redirect_uri(),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        resp.raise_for_status()
        return resp.json()

    async def ensure_valid_access_token(self, user, user_store) -> str:
        """Return a usable LinkedIn access token for `user`, transparently
        refreshing (and persisting) when the stored token is expired or has no
        known expiry. Returns "" when the user has no access token."""
        from app.models.user import LinkedInUser  # noqa: F401

        if not user.access_token:
            return ""
        expires = user.token_expires_at
        now = datetime.now(timezone.utc)
        needs_refresh = bool(user.refresh_token) and (
            expires is None or expires <= now + timedelta(minutes=5)
        )
        if not needs_refresh:
            return user.access_token

        tok = await self.refresh_access_token(user.refresh_token)
        if tok.get("access_token"):
            user.access_token = tok["access_token"]
        if tok.get("refresh_token"):  # LinkedIn rotates refresh tokens
            user.refresh_token = tok["refresh_token"]
        expires_in = int(tok.get("expires_in") or 0)
        if expires_in:
            user.token_expires_at = now + timedelta(seconds=expires_in)
        user_store.save(user)
        logger.info("linkedin token refreshed", user_id=user.user_id)
        return user.access_token

    async def userinfo(self, access_token: str) -> Dict[str, Any]:
        """Google-style userinfo for the OIDC 'Sign in with LinkedIn' flow.
        Returns sub/name/given_name/family_name/picture/email/email_verified."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LINKEDIN_API}/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def me(self, access_token: str) -> Dict[str, Any]:
        """Identity for the logged-in user via the OIDC userinfo endpoint."""
        return await self.userinfo(access_token)

    # ── Publish ────────────────────────────────────────────────
    async def publish_text_post(
        self,
        text: str,
        image_url: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        access_token: Optional[str] = None,
        person_urn: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not text.strip():
            raise LinkedInError("Cannot publish an empty post.")

        if self._dry_run or not (access_token and person_urn):
            # No per-user credentials → simulated publish, or the global
            # dry-run fallback when the user hasn't connected LinkedIn.
            post_id = f"dryrun-{uuid.uuid4().hex[:10]}"
            logger.info(
                "linkedin dry-run publish",
                post_id=post_id,
                real=bool(access_token and person_urn),
            )
            return {
                "post_id": post_id,
                "status": "PUBLISHED",
                "ui_urn": None,
                "dry_run": True,
                "error": None,
            }

        return await self._real_publish(text, image_url, access_token, person_urn)

    async def _real_publish(
        self,
        text: str,
        image_url: Optional[str],
        access_token: str,
        person_urn: str,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        person_id = person_urn.split(":")[-1]

        image_urn: Optional[str] = None
        if image_url:
            image_urn = await self._upload_image(image_url, person_id, headers)

        media = (
            [
                {
                    "status": "READY",
                    "description": {"text": "AI generated post visual"},
                    "media": image_urn,
                    "title": {"text": "AI generated post visual"},
                }
            ]
            if image_urn
            else [{"status": "READY", "description": {"text": "post"}}]
        )

        body = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {"shareCommentary": {"text": text}, "shareMediaCategory": "IMAGE" if image_urn else "NONE", "media": media}
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LINKEDIN_API}/v2/ugcPosts", json=body, headers=headers
            )
        if resp.status_code != 201:
            raise LinkedInError(f"LinkedIn API error {resp.status_code}: {resp.text[:500]}")

        urn = resp.json().get("id", "")
        logger.info("linkedin published real", urn=urn)
        return {"post_id": urn, "status": "PUBLISHED", "ui_urn": urn, "dry_run": False, "error": None}

    async def _upload_image(
        self, image_url: str, person_id: str, headers: Dict[str, str]
    ) -> str:
        # 1) Register upload
        register_body = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}],
            }
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{LINKEDIN_API}/v2/assets?action=registerUpload",
                json=register_body,
                headers=headers,
            )
        resp.raise_for_status()
        value = resp.json()["value"]
        upload_urn = value["asset"]
        upload_url = value["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]

        # 2) Download the AI image
        image_bytes = await self._download(image_url)

        # 3) Upload the bytes
        upload_headers = {
            "Authorization": headers.get("Authorization", ""),
            "Content-Type": "application/octet-stream",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            up = await client.put(
                upload_url, content=image_bytes, headers=upload_headers
            )
        if up.status_code not in (200, 201):
            raise LinkedInError(f"Image upload failed: {up.status_code}")

        return upload_urn

    async def _download(self, image_url: str) -> bytes:
        if image_url.startswith("data:"):
            header, _, payload = image_url.partition(",")
            if "base64" in header:
                return base64.b64decode(payload)
            return payload.encode("utf-8")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            return resp.content


__all__ = ["LinkedInPublisher", "LinkedInError"]