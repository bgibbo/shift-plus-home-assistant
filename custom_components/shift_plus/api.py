"""HTTP API implementing the Shift Plus mobile protocol."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import qrcode
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import CONF_ENTITLEMENT_PUBLIC_KEY, DOMAIN, ENTITLEMENT_MAX_SECONDS
from .crypto import (
    EntitlementError,
    b64decode,
    endpoint_proof,
    verify_entitlement,
    verify_request_signature,
)
from .store import ShiftPlusStore


def _runtime(request: web.Request, entry_id: str) -> dict[str, Any]:
    hass: HomeAssistant = request.app["hass"]
    runtime = hass.data[DOMAIN].get(entry_id)
    if runtime is None:
        raise web.HTTPNotFound()
    return runtime


async def _json(request: web.Request) -> tuple[bytes, dict[str, Any]]:
    body = await request.read()
    if len(body) > 2_000_000:
        raise web.HTTPRequestEntityTooLarge(max_size=2_000_000, actual_size=len(body))
    try:
        value = json.loads(body or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise web.HTTPBadRequest(text="Invalid JSON") from err
    if not isinstance(value, dict):
        raise web.HTTPBadRequest(text="Expected a JSON object")
    return body, value


def _verification_key(runtime: dict[str, Any]) -> str:
    entry = runtime["entry"]
    return entry.options.get(
        CONF_ENTITLEMENT_PUBLIC_KEY,
        entry.data.get(CONF_ENTITLEMENT_PUBLIC_KEY, ""),
    ).strip()


def _expires_at(claims: dict[str, Any]) -> datetime:
    maximum = datetime.now(UTC) + timedelta(seconds=ENTITLEMENT_MAX_SECONDS)
    claimed = datetime.fromtimestamp(float(claims["exp"]), UTC)
    return min(claimed, maximum)


def _authenticate(
    request: web.Request,
    store: ShiftPlusStore,
    device_id: str,
    body: bytes,
) -> dict[str, Any]:
    device = store.device(device_id)
    nonce = request.headers.get("X-Shift-Plus-Nonce", "")
    signature = request.headers.get("X-Shift-Plus-Signature", "")
    if (
        device is None
        or not nonce
        or not signature
        or not store.accept_nonce(device_id, nonce)
        or not verify_request_signature(
            b64decode(device["credential"]), nonce, body, signature
        )
    ):
        raise web.HTTPUnauthorized(text="Invalid device authentication")
    if datetime.fromisoformat(device["entitlement_expires_at"]) <= datetime.now(UTC):
        raise web.HTTPForbidden(text="Premium entitlement expired")
    return device


class PairingPageView(HomeAssistantView):
    """Authenticated page that displays a short-lived pairing QR."""

    url = "/api/shift_plus/{entry_id}/pairing"
    name = "api:shift_plus:pairing_page"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request, entry_id)
        hass: HomeAssistant = request.app["hass"]
        payload = runtime["store"].new_pairing(get_url(hass, prefer_external=False))
        raw = json.dumps(payload, separators=(",", ":"))
        image = qrcode.make(raw)
        output = BytesIO()
        image.save(output, format="PNG")
        import base64

        data_uri = (
            "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
        )
        html = (
            "<!doctype html><html><head>"
            '<meta name="viewport" content="width=device-width">'
            "<title>Pair Shift Plus</title><style>"
            "body{font-family:sans-serif;text-align:center;margin:2rem}"
            "img{width:min(80vw,420px);image-rendering:pixelated}"
            "</style></head><body><h1>Pair Shift Plus</h1>"
            "<p>In Shift Plus, open Home Assistant and scan this code.</p>"
            f'<img alt="Shift Plus pairing QR" src="{data_uri}">'
            "<p>This code expires in five minutes.</p></body></html>"
        )
        return web.Response(text=html, content_type="text/html")


class PairingCompleteView(HomeAssistantView):
    """Complete X25519 pairing from the mobile app."""

    url = "/api/shift_plus/{entry_id}/pairing/complete"
    name = "api:shift_plus:pairing_complete"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request, entry_id)
        store: ShiftPlusStore = runtime["store"]
        _, data = await _json(request)
        try:
            session_id = str(data["session_id"])
            secret = str(data["one_time_secret"])
            device_id = str(data["device_id"])
            app_public_key = str(data["app_public_key"])
            claims = verify_entitlement(
                str(data["entitlement"]),
                _verification_key(runtime),
                entry_id=entry_id,
                session_id=session_id,
                device_id=device_id,
                app_public_key=app_public_key,
            )
            store.consume_pairing(session_id, secret)
            expires_at = _expires_at(claims)
            await store.add_device(
                device_id=device_id,
                app_public_key=app_public_key,
                one_time_secret=secret,
                entitlement_expires_at=expires_at,
            )
        except EntitlementError as err:
            raise web.HTTPForbidden(text=str(err)) from err
        except (KeyError, TypeError, ValueError) as err:
            raise web.HTTPBadRequest(text="Invalid or expired pairing request") from err
        return self.json(
            {
                "replica_id": store.data["replica_id"],
                "server_cursor": store.data["cursor"],
                "entitlement_expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            }
        )


class SyncView(HomeAssistantView):
    """Bidirectional operation-log synchronization."""

    url = "/api/shift_plus/{entry_id}/sync"
    name = "api:shift_plus:sync"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request, entry_id)
        store: ShiftPlusStore = runtime["store"]
        body, data = await _json(request)
        device_id = request.headers.get("X-Shift-Plus-Device", "")
        _authenticate(request, store, device_id, body)
        if data.get("protocol") != 1:
            raise web.HTTPBadRequest(text="Unsupported protocol")
        operations = data.get("operations", [])
        cursor = data.get("cursor", 0)
        if (
            not isinstance(operations, list)
            or not isinstance(cursor, int)
            or cursor < 0
        ):
            raise web.HTTPBadRequest(text="Invalid sync envelope")
        try:
            result = await store.sync(operations, cursor)
        except ValueError as err:
            raise web.HTTPBadRequest(text=str(err)) from err
        return self.json(result)


class EntitlementView(HomeAssistantView):
    """Refresh a device's Premium entitlement."""

    url = "/api/shift_plus/{entry_id}/devices/{device_id}/entitlement"
    name = "api:shift_plus:entitlement"
    requires_auth = False

    async def post(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        runtime = _runtime(request, entry_id)
        store: ShiftPlusStore = runtime["store"]
        body, data = await _json(request)
        device = _authenticate(request, store, device_id, body)
        try:
            claims = verify_entitlement(
                str(data["entitlement"]),
                _verification_key(runtime),
                entry_id=entry_id,
                session_id=f"renew:{device_id}",
                device_id=device_id,
                app_public_key=device["app_public_key"],
            )
            expires_at = _expires_at(claims)
            await store.update_entitlement(device_id, expires_at)
        except EntitlementError as err:
            raise web.HTTPForbidden(text=str(err)) from err
        except (KeyError, TypeError, ValueError) as err:
            raise web.HTTPBadRequest(text="Invalid entitlement") from err
        return self.json(
            {"entitlement_expires_at": expires_at.isoformat().replace("+00:00", "Z")}
        )


class RevokeView(HomeAssistantView):
    """Allow a device to revoke itself."""

    url = "/api/shift_plus/{entry_id}/devices/{device_id}/self-revoke"
    name = "api:shift_plus:self_revoke"
    requires_auth = False

    async def post(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        store: ShiftPlusStore = _runtime(request, entry_id)["store"]
        body, _ = await _json(request)
        _authenticate(request, store, device_id, body)
        await store.revoke(device_id)
        return self.json({"revoked": True})


class EndpointVerificationView(HomeAssistantView):
    """Prove identity before the app stores an alternative URL."""

    url = "/api/shift_plus/{entry_id}/endpoint-verification"
    name = "api:shift_plus:endpoint_verification"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        store: ShiftPlusStore = _runtime(request, entry_id)["store"]
        _, data = await _json(request)
        device_id = str(data.get("device_id", ""))
        challenge = str(data.get("challenge", ""))
        device = store.device(device_id)
        if device is None or not challenge:
            raise web.HTTPUnauthorized()
        return self.json(
            {
                "protocol": 1,
                "entry_id": entry_id,
                "device_id": device_id,
                "challenge": challenge,
                "proof": endpoint_proof(
                    b64decode(device["credential"]), entry_id, device_id, challenge
                ),
            }
        )


VIEWS = (
    PairingPageView,
    PairingCompleteView,
    SyncView,
    EntitlementView,
    RevokeView,
    EndpointVerificationView,
)
