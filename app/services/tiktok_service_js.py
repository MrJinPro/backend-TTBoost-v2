import asyncio
import json
import logging
import os
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class JsTikTokService:
    def __init__(self):
        self._callbacks: dict[str, dict[str, Any]] = {}
        self._desired_usernames: dict[str, str] = {}
        self._connected_user_ids: set[str] = set()
        self._status_states: dict[str, str] = {}
        self._pending_starts: dict[str, asyncio.Future] = {}
        self._last_errors: dict[str, str] = {}
        self._callback_tasks: set[asyncio.Task] = set()

        self._bridge_ws = None
        self._bridge_ready = asyncio.Event()
        self._bridge_lock = asyncio.Lock()
        self._bridge_task: asyncio.Task | None = None
        self._closing = False
        self._request_seq = 0

    def _bridge_url(self) -> str:
        raw = (os.getenv("TIKTOK_BRIDGE_WS_URL") or "ws://127.0.0.1:3000/bridge").strip()
        token = (os.getenv("TIKTOK_BRIDGE_TOKEN") or "").strip()
        if not token:
            return raw
        joiner = '&' if '?' in raw else '?'
        return f"{raw}{joiner}token={token}"

    def _next_request_id(self) -> str:
        self._request_seq += 1
        return f"req-{self._request_seq}"

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)

    async def _send(self, payload: dict[str, Any]) -> None:
        ws = self._bridge_ws
        if ws is None:
            raise RuntimeError("TikTok JS bridge is not connected")
        await ws.send(json.dumps(payload, ensure_ascii=False))

    async def _ensure_bridge(self) -> None:
        if self._bridge_task is None or self._bridge_task.done():
            async with self._bridge_lock:
                if self._bridge_task is None or self._bridge_task.done():
                    self._bridge_task = asyncio.create_task(self._bridge_loop())
        await asyncio.wait_for(self._bridge_ready.wait(), timeout=10)

    async def _bridge_loop(self) -> None:
        backoff = 2
        while not self._closing:
            try:
                async with websockets.connect(self._bridge_url(), ping_interval=20, ping_timeout=20) as ws:
                    self._bridge_ws = ws
                    self._bridge_ready.set()
                    logger.info("Connected to TikTok JS bridge: %s", self._bridge_url())
                    await self._resubscribe_all()
                    backoff = 2

                    async for raw in ws:
                        await self._handle_bridge_message(raw)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("TikTok JS bridge disconnected: %s", exc)
            finally:
                self._bridge_ws = None
                self._bridge_ready.clear()
                self._mark_bridge_lost()

            if self._closing:
                break

            await asyncio.sleep(backoff)
            backoff = min(15, backoff * 2)

    def _mark_bridge_lost(self) -> None:
        previously_connected = list(self._connected_user_ids)
        self._connected_user_ids.clear()
        for user_id in previously_connected:
            callbacks = self._callbacks.get(user_id) or {}
            username = self._desired_usernames.get(user_id, user_id)
            disconnect_cb = callbacks.get("disconnect")
            if disconnect_cb is not None:
                self._spawn(disconnect_cb(username))

    async def _resubscribe_all(self) -> None:
        for user_id, username in list(self._desired_usernames.items()):
            try:
                await self._send({
                    "op": "subscribe",
                    "requestId": self._next_request_id(),
                    "userId": user_id,
                    "username": username,
                })
            except Exception as exc:
                logger.warning("Failed to resubscribe %s: %s", user_id, exc)

    async def _handle_bridge_message(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except Exception:
            logger.warning("TikTok JS bridge sent invalid JSON")
            return

        op = str(message.get("op") or "").strip().lower()
        if op == "ready" or op == "ack" or op == "pong" or op == "stats":
            return
        if op == "status":
            await self._handle_status(message)
            return
        if op == "error":
            await self._handle_error(message)
            return
        if op == "event":
            await self._handle_event(message)
            return

    async def _handle_status(self, message: dict[str, Any]) -> None:
        user_id = str(message.get("userId") or "").strip()
        if not user_id:
            return
        state = str(message.get("state") or "").strip().lower()
        username = str(message.get("username") or self._desired_usernames.get(user_id) or "").strip()
        was_connected = user_id in self._connected_user_ids

        self._status_states[user_id] = state

        if state == "connected" or message.get("connected") is True:
            self._connected_user_ids.add(user_id)
            waiter = self._pending_starts.pop(user_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_result(True)
            if not was_connected:
                connect_cb = (self._callbacks.get(user_id) or {}).get("connect")
                if connect_cb is not None:
                    self._spawn(connect_cb(username))
            return

        self._connected_user_ids.discard(user_id)

        if state in {"reconnecting", "disconnected"} and was_connected:
            disconnect_cb = (self._callbacks.get(user_id) or {}).get("disconnect")
            if disconnect_cb is not None:
                self._spawn(disconnect_cb(username))

    async def _handle_error(self, message: dict[str, Any]) -> None:
        user_id = str(message.get("userId") or "").strip()
        error_message = str(message.get("message") or "TikTok JS bridge error").strip()
        if user_id:
            self._last_errors[user_id] = error_message
            waiter = self._pending_starts.pop(user_id, None)
            if waiter is not None and not waiter.done():
                waiter.set_exception(RuntimeError(error_message))
        logger.warning("TikTok JS bridge error%s: %s", f" for {user_id}" if user_id else "", error_message)

    async def _handle_event(self, message: dict[str, Any]) -> None:
        user_id = str(message.get("userId") or "").strip()
        if not user_id:
            return

        event_name = str(message.get("event") or "").strip().lower()
        payload = message.get("payload") or {}
        callbacks = self._callbacks.get(user_id) or {}

        if event_name == "chat":
            cb = callbacks.get("comment")
            if cb is not None:
                self._spawn(cb(str(payload.get("user") or ""), str(payload.get("message") or "")))
            return

        if event_name == "gift":
            cb = callbacks.get("gift")
            if cb is not None:
                self._spawn(cb(
                    str(payload.get("user") or ""),
                    str(payload.get("giftId") or ""),
                    str(payload.get("giftName") or "Gift"),
                    int(payload.get("count") or 1),
                    int(payload.get("diamonds") or 0),
                ))
            return

        if event_name == "like":
            cb = callbacks.get("like")
            if cb is not None:
                self._spawn(cb(str(payload.get("user") or ""), int(payload.get("count") or 1)))
            return

        if event_name == "viewer_join":
            cb = callbacks.get("join")
            if cb is not None:
                self._spawn(cb({
                    "username": payload.get("username"),
                    "nickname": payload.get("nickname"),
                }))
            return

        if event_name == "follow":
            cb = callbacks.get("follow")
            if cb is not None:
                self._spawn(cb(str(payload.get("user") or "")))
            return

        if event_name == "subscribe":
            cb = callbacks.get("subscribe")
            if cb is not None:
                self._spawn(cb(str(payload.get("user") or "")))
            return

        if event_name == "share":
            cb = callbacks.get("share")
            if cb is not None:
                self._spawn(cb(str(payload.get("user") or "")))
            return

        if event_name == "viewer":
            cb = callbacks.get("viewer")
            if cb is not None:
                self._spawn(cb(int(payload.get("current") or 0), int(payload.get("total") or 0)))

    async def start_client(
        self,
        user_id: str,
        tiktok_username: str,
        on_comment_callback=None,
        on_gift_callback=None,
        on_like_callback=None,
        on_join_callback=None,
        on_follow_callback=None,
        on_subscribe_callback=None,
        on_share_callback=None,
        on_viewer_callback=None,
        on_connect_callback=None,
        on_disconnect_callback=None,
    ):
        uid = str(user_id)
        username = str(tiktok_username or "").strip().lstrip("@").lower()
        if not username:
            raise RuntimeError("TikTok username is required")

        self._callbacks[uid] = {
            "comment": on_comment_callback,
            "gift": on_gift_callback,
            "like": on_like_callback,
            "join": on_join_callback,
            "follow": on_follow_callback,
            "subscribe": on_subscribe_callback,
            "share": on_share_callback,
            "viewer": on_viewer_callback,
            "connect": on_connect_callback,
            "disconnect": on_disconnect_callback,
        }
        self._desired_usernames[uid] = username
        self._last_errors.pop(uid, None)

        await self._ensure_bridge()

        waiter = asyncio.get_running_loop().create_future()
        old_waiter = self._pending_starts.get(uid)
        if old_waiter is not None and not old_waiter.done():
            old_waiter.cancel()
        self._pending_starts[uid] = waiter

        await self._send({
            "op": "subscribe",
            "requestId": self._next_request_id(),
            "userId": uid,
            "username": username,
        })

        try:
            await asyncio.wait_for(waiter, timeout=float(os.getenv("TT_CONNECT_TIMEOUT_SEC", "25")))
        except Exception:
            self._pending_starts.pop(uid, None)
            raise

    async def stop_client(self, user_id: str):
        uid = str(user_id)
        self._desired_usernames.pop(uid, None)
        self._connected_user_ids.discard(uid)
        self._status_states.pop(uid, None)
        self._last_errors.pop(uid, None)
        waiter = self._pending_starts.pop(uid, None)
        if waiter is not None and not waiter.done():
            waiter.cancel()
        self._callbacks.pop(uid, None)

        if self._bridge_ws is not None and self._bridge_ready.is_set():
            try:
                await self._send({
                    "op": "unsubscribe",
                    "requestId": self._next_request_id(),
                    "userId": uid,
                })
            except Exception as exc:
                logger.warning("Failed to unsubscribe %s from TikTok JS bridge: %s", uid, exc)

    def is_running(self, user_id: str) -> bool:
        return str(user_id) in self._connected_user_ids


tiktok_service = JsTikTokService()