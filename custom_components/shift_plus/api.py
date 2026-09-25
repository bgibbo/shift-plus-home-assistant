"""Narrow authenticated transport endpoints for pairing and delta sync."""

from __future__ import annotations

import base64
import json
import logging
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PROTOCOL_VERSION
from .coordinator import make_qr
from .security import (
    EntitlementError,
    entitlement_is_active,
    sign_endpoint_challenge,
    validate_renewal,
    verify_request,
)
from .sync import ReplicatedRecord

_LOGGER = logging.getLogger(__name__)


class PairingStartView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/pairing/start"
    name = "api:shift_plus:pairing:start"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        if runtime.pairing is None:
            return self.json_message(
                "Premium entitlement public key is not configured", 409
            )
        data = await request.json()
        base_url = str(data.get("base_url") or request.url.origin())
        payload = runtime.pairing.begin(base_url)
        runtime.pairing_payload = payload
        runtime.pairing_qr = make_qr(payload)
        runtime.pairing_qr_generated_at = datetime.now(UTC)
        runtime.pairing_qr_expires_at = datetime.fromisoformat(
            str(payload["expires_at"])
        )
        runtime.pairing_qr_expired = False
        runtime.coordinator.async_update_listeners()
        return self.json(payload)


class PairingCompleteView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/pairing/complete"
    name = "api:shift_plus:pairing:complete"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        if runtime.pairing is None:
            return self.json_message("Pairing is unavailable", 409)
        try:
            data = await request.json()
            claim, credential = runtime.pairing.complete(
                session_id=data["session_id"],
                one_time_secret=data["one_time_secret"],
                app_public_key=data["app_public_key"],
                entitlement=data["entitlement"],
                device_id=data["device_id"],
            )
        except (KeyError, ValueError) as error:
            runtime.clear_pairing_qr(expired=True)
            runtime.coordinator.async_update_listeners()
            return self.json_message(str(error), 403)
        runtime.store.paired_devices[data["device_id"]] = {
            "credential": base64.b64encode(credential).decode(),
            "claim_id": claim.get("grant_id"),
            "entitlement_id": claim["entitlement_id"],
            "entitlement_issued_at": claim["iat"],
            "entitlement_jti": claim["jti"],
            "installation_id": claim["installation_id"],
            "app_public_key": data["app_public_key"],
            "entitlement_expires_at": claim["expires_at"],
            "revoked": False,
            "used_nonces": [],
        }
        runtime.clear_pairing_qr()
        await runtime.store.async_save()
        runtime.coordinator.async_update_listeners()
        return self.json(
            {
                "paired": True,
                "protocol": PROTOCOL_VERSION,
                "replica_id": runtime.store.sync.replica_id,
                "server_cursor": runtime.store.sync.cursor,
                "entitlement_expires_at": claim["expires_at"],
            }
        )


class SyncView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/sync"
    name = "api:shift_plus:sync"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        async with runtime.store.transport_lock:
            return await self._post(request, entry_id)

    async def _post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        device_id = request.headers.get("X-Shift-Plus-Device", "")
        nonce = request.headers.get("X-Shift-Plus-Nonce", "")
        signature = request.headers.get("X-Shift-Plus-Signature", "")
        device = runtime.store.paired_devices.get(device_id)
        if not device or device.get("revoked"):
            return self.json_message("Unknown or revoked device", 401)
        if not entitlement_is_active(device):
            return self.json_message("Premium entitlement expired", 403)
        used_nonces: list[str] = device.setdefault("used_nonces", [])
        if not nonce or nonce in used_nonces:
            return self.json_message("Replayed request", 409)
        body = await request.read()
        credential = base64.b64decode(device["credential"])
        if not verify_request(credential, nonce, body, signature):
            return self.json_message("Invalid request signature", 401)
        try:
            data = json.loads(body)
            if int(data["protocol"]) != PROTOCOL_VERSION:
                return self.json_message("Unsupported protocol", 426)
            replica_id = str(data["replica_id"])
            phone_cursor = int(data.get("cursor", 0))
            records = [
                ReplicatedRecord.from_dict(item) for item in data.get("operations", [])
            ]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return self.json_message(f"Invalid sync request: {error}", 400)
        used_nonces.append(nonce)
        del used_nonces[:-500]
        store = runtime.store
        previous_success = store.last_successful_sync
        requested_at = store.sync_requested_at
        try:
            store.sync_status = "processing"
            cursor_before = store.sync.cursor
            outcomes = await store.async_merge(records, replica_id, phone_cursor)
            changes = store.sync.changes_after(phone_cursor)
            store.sync_details = {
                "received_operations": len(records),
                "applied_operations": store.sync.cursor - cursor_before,
                "conflicts": len(store.sync.conflicts),
            }
            # Force a completed calculation, not a debounced refresh request.
            await runtime.coordinator.async_refresh()
            if not runtime.coordinator.last_update_success:
                raise RuntimeError("Coordinator refresh failed")
            store.last_successful_sync = datetime.now(UTC).isoformat()
            store.sync_requested_at = None
            store.sync_status = "completed"
            await store.async_save()
            runtime.coordinator.async_update_listeners()
        except Exception:
            store.last_successful_sync = previous_success
            store.sync_requested_at = requested_at
            store.sync_status = "processing_or_refresh_failed"
            try:
                await store.async_save()
            except OSError:
                _LOGGER.exception("Unable to persist failed sync status")
            _LOGGER.warning("Shift + sync did not complete storage and state refresh")
            return self.json_message("Sync processing or state refresh failed", 503)
        return self.json(
            {
                "protocol": PROTOCOL_VERSION,
                "replica_id": runtime.store.sync.replica_id,
                "server_cursor": runtime.store.sync.cursor,
                "outcomes": outcomes,
                "changes": changes,
                "conflicts": list(runtime.store.sync.conflicts),
                "manual_sync_requested_at": requested_at,
            }
        )


class EndpointVerificationView(HomeAssistantView):
    """Prove this route reaches the same already-paired integration instance."""

    url = "/api/shift_plus/{entry_id}/endpoint-verification"
    name = "api:shift_plus:endpoint-verification"
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        try:
            data = await request.json()
            device_id = str(data["device_id"])
            challenge = str(data["challenge"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self.json_message("Invalid verification challenge", 400)
        if len(challenge) < 32 or len(challenge) > 200:
            return self.json_message("Invalid verification challenge", 400)
        device = runtime.store.paired_devices.get(device_id)
        if not device or device.get("revoked"):
            return self.json_message("Unknown or revoked device", 401)
        credential = base64.b64decode(device["credential"])
        return self.json(
            {
                "protocol": PROTOCOL_VERSION,
                "entry_id": entry_id,
                "device_id": device_id,
                "challenge": challenge,
                "proof": sign_endpoint_challenge(
                    credential,
                    entry_id=entry_id,
                    device_id=device_id,
                    challenge=challenge,
                ),
            }
        )


class UnpairView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/devices/{device_id}"
    name = "api:shift_plus:devices:revoke"
    requires_auth = True

    async def delete(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        device = runtime.store.paired_devices.get(device_id)
        if device is None:
            raise web.HTTPNotFound()
        device["revoked"] = True
        device["credential"] = ""
        runtime.store.sync.replica_acks.pop(device_id, None)
        await runtime.store.async_save()
        return self.json({"revoked": True})


class EntitlementRefreshView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/devices/{device_id}/entitlement"
    name = "api:shift_plus:devices:entitlement"
    requires_auth = False

    async def post(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        async with runtime.store.transport_lock:
            return await self._post(request, entry_id, device_id)

    async def _post(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        device = runtime.store.paired_devices.get(device_id)
        if not device or device.get("revoked"):
            return self.json_message("Unknown or revoked device", 401)
        nonce = request.headers.get("X-Shift-Plus-Nonce", "")
        signature = request.headers.get("X-Shift-Plus-Signature", "")
        used_nonces: list[str] = device.setdefault("used_nonces", [])
        if not nonce or nonce in used_nonces:
            return self.json_message("Replayed request", 409)
        body = await request.read()
        credential = base64.b64decode(device["credential"])
        if not verify_request(credential, nonce, body, signature):
            return self.json_message("Invalid request signature", 401)
        try:
            data = json.loads(body)
            claim = runtime.pairing.verifier.verify(
                data["entitlement"],
                ha_instance_id=entry_id,
                pairing_session_id=f"renew:{device_id}",
                device_id=device_id,
                app_public_key=device["app_public_key"],
            )
            validate_renewal(device, claim)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            reason = (
                str(error)
                if isinstance(error, EntitlementError)
                else "Malformed entitlement"
            )
            _LOGGER.warning("Shift + entitlement renewal rejected: %s", reason)
            runtime.store.sync_status = "entitlement_rejected"
            await runtime.store.async_save()
            runtime.coordinator.async_update_listeners()
            return self.json_message(reason, 403)
        previous_device = deepcopy(device)
        previous_status = runtime.store.sync_status
        used_nonces.append(nonce)
        del used_nonces[:-500]
        device["entitlement_id"] = claim["entitlement_id"]
        device["installation_id"] = claim["installation_id"]
        device["entitlement_issued_at"] = claim["iat"]
        device["entitlement_jti"] = claim["jti"]
        runtime.store.sync_status = "entitlement_valid"
        device["claim_id"] = claim.get("grant_id")
        device["entitlement_expires_at"] = claim["expires_at"]
        try:
            await runtime.store.async_save()
        except OSError:
            device.clear()
            device.update(previous_device)
            runtime.store.sync_status = previous_status
            _LOGGER.exception("Unable to persist entitlement renewal")
            return self.json_message("Entitlement renewal could not be stored", 503)
        runtime.coordinator.async_update_listeners()
        return self.json({"entitlement_expires_at": claim["expires_at"]})


class SelfRevokeView(HomeAssistantView):
    url = "/api/shift_plus/{entry_id}/devices/{device_id}/self-revoke"
    name = "api:shift_plus:devices:self-revoke"
    requires_auth = False

    async def post(
        self, request: web.Request, entry_id: str, device_id: str
    ) -> web.Response:
        runtime = _runtime(request.app["hass"], entry_id)
        device = runtime.store.paired_devices.get(device_id)
        if not device or device.get("revoked"):
            return self.json_message("Unknown or revoked device", 401)
        nonce = request.headers.get("X-Shift-Plus-Nonce", "")
        signature = request.headers.get("X-Shift-Plus-Signature", "")
        body = await request.read()
        credential = base64.b64decode(device["credential"])
        if not nonce or not verify_request(credential, nonce, body, signature):
            return self.json_message("Invalid request signature", 401)
        device["revoked"] = True
        device["credential"] = ""
        runtime.store.sync.replica_acks.pop(device_id, None)
        await runtime.store.async_save()
        return self.json({"revoked": True})


def _runtime(hass: HomeAssistant, entry_id: str) -> Any:
    try:
        return hass.data[DOMAIN][entry_id]
    except KeyError as error:
        raise web.HTTPNotFound() from error


def register_views(hass: HomeAssistant) -> None:
    hass.http.register_view(PairingStartView())
    hass.http.register_view(PairingCompleteView())
    hass.http.register_view(SyncView())
    hass.http.register_view(EndpointVerificationView())
    hass.http.register_view(UnpairView())
    hass.http.register_view(SelfRevokeView())
    hass.http.register_view(EntitlementRefreshView())
