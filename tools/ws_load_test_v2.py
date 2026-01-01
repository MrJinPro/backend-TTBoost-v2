import argparse
import asyncio
import json
import os
import random
import string
import time
from dataclasses import dataclass

import websockets


def _rand_id(n: int = 8) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


@dataclass
class Stats:
    started: int = 0
    connected: int = 0
    failed: int = 0
    messages_sent: int = 0
    messages_recv: int = 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Load-test for TTBoost backend WS v2.\n"
            "Creates many WebSocket connections to your backend only (does NOT connect TikTok Live)."
        )
    )
    p.add_argument("--ws", default=os.environ.get("WS_URL", "ws://127.0.0.1:8000/v2/ws"))
    p.add_argument("--token", default=os.environ.get("TOKEN"))
    p.add_argument("--connections", type=int, default=int(os.environ.get("CONNECTIONS", "50")))
    p.add_argument("--duration", type=int, default=int(os.environ.get("DURATION", "60")))
    p.add_argument("--ramp", type=float, default=float(os.environ.get("RAMP", "5")))
    p.add_argument(
        "--send-interval",
        type=float,
        default=float(os.environ.get("SEND_INTERVAL", "15")),
        help="How often each client sends a small noop message. 0 = never.",
    )
    p.add_argument(
        "--platform",
        default=os.environ.get("PLATFORM", "desktop"),
        help="Sent as query param platform=... (affects tariff allowed_platforms).",
    )
    p.add_argument("--os", default=os.environ.get("CLIENT_OS", "linux"))
    p.add_argument("--device", default=os.environ.get("DEVICE", "loadtest"))
    return p.parse_args()


def _build_ws_url(base_ws: str, token: str, platform: str, os_name: str, device: str, client_id: str) -> str:
    sep = "&" if "?" in base_ws else "?"
    return (
        f"{base_ws}{sep}token={token}"
        f"&platform={platform}"
        f"&os={os_name}"
        f"&device={device}"
        f"&client_id={client_id}"
    )


async def client_task(
    idx: int,
    ws_url: str,
    stats: Stats,
    stop_at: float,
    send_interval: float,
) -> None:
    stats.started += 1
    try:
        async with websockets.connect(ws_url, ping_interval=None, close_timeout=2) as ws:
            stats.connected += 1
            last_send = 0.0
            while time.monotonic() < stop_at:
                # Best-effort receive, but don't block forever.
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if msg is not None:
                        stats.messages_recv += 1
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break

                if send_interval and send_interval > 0:
                    now = time.monotonic()
                    if now - last_send >= send_interval:
                        last_send = now
                        try:
                            await ws.send(json.dumps({"action": "noop", "i": idx, "t": int(now)}))
                            stats.messages_sent += 1
                        except Exception:
                            break
    except Exception:
        stats.failed += 1


async def run() -> int:
    args = parse_args()

    if not args.token:
        raise SystemExit(
            "Missing token. Provide --token or env TOKEN (JWT from /v2/auth/login or from admin localStorage ttb_token)."
        )

    n = max(1, int(args.connections))
    duration = max(1, int(args.duration))
    ramp = max(0.0, float(args.ramp))

    stats = Stats()
    start = time.monotonic()
    stop_at = start + duration

    # Spread connects to avoid spikes.
    ramp_step = ramp / n if ramp > 0 else 0.0

    tasks: list[asyncio.Task] = []
    for i in range(n):
        await asyncio.sleep(ramp_step)
        url = _build_ws_url(
            args.ws,
            args.token,
            args.platform,
            args.os,
            args.device,
            client_id=_rand_id(10),
        )
        tasks.append(asyncio.create_task(client_task(i, url, stats, stop_at, float(args.send_interval))))

    # Periodic status
    while time.monotonic() < stop_at:
        await asyncio.sleep(2.0)
        elapsed = time.monotonic() - start
        print(
            f"t={elapsed:5.1f}s started={stats.started} connected={stats.connected} failed={stats.failed} "
            f"sent={stats.messages_sent} recv={stats.messages_recv}"
        )

    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.monotonic() - start
    print("\nDone")
    print(
        f"elapsed={elapsed:.1f}s connections={n} connected={stats.connected} failed={stats.failed} "
        f"sent={stats.messages_sent} recv={stats.messages_recv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
