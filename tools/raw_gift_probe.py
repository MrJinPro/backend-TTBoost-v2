import os
import asyncio
import logging
from datetime import datetime, timedelta

from TikTokLive import TikTokLiveClient
from TikTokLive.client.web.web_settings import WebDefaults

# Optional proto imports for raw decode
try:
    from TikTokLive.proto import WebcastResponse, WebcastPushFrame
except ImportError:  # pragma: no cover
    WebcastResponse = None
    WebcastPushFrame = None


async def main():
    username = os.getenv("TT_USERNAME") or (os.environ.get("1") if "1" in os.environ else None)
    # Allow passing username via command-line arg as well (when run directly)
    import sys
    if not username and len(sys.argv) > 1:
        username = sys.argv[1]
    if not username:
        print("Usage: python tools/raw_gift_probe.py <tiktok_username>")
        return

    # Configure sign server
    sign_api_key = os.getenv("SIGN_API_KEY")
    sign_api_url = os.getenv("SIGN_API_URL") or os.getenv("SIGN_SERVER_URL")
    if sign_api_key:
        WebDefaults.tiktok_sign_api_key = sign_api_key
        os.environ.setdefault("SIGN_API_KEY", sign_api_key)
        print(f"[probe] SIGN_API_KEY set: {sign_api_key[:15]}...{sign_api_key[-6:]}")
    else:
        print("[probe] WARNING: No SIGN_API_KEY set. You may only receive comments/likes.")
    if sign_api_url:
        WebDefaults.tiktok_sign_url = sign_api_url
        os.environ.setdefault("SIGN_API_URL", sign_api_url)
        print(f"[probe] SIGN_API_URL: {sign_api_url}")
    else:
        print(f"[probe] Using default sign URL: {WebDefaults.tiktok_sign_url}")

    # Create client
    client = TikTokLiveClient(unique_id=f"@{username}")
    logging.basicConfig(level=logging.DEBUG)
    client.logger.setLevel(logging.DEBUG)

    start = datetime.now()
    deadline_sec = int(os.getenv("PROBE_SECONDS", "60"))

    # Counters
    total_frames = 0
    total_gift_msgs = 0

    if WebcastPushFrame is not None:
        @client.on("raw")
        async def on_raw(frame):
            nonlocal total_frames, total_gift_msgs
            total_frames += 1
            try:
                push_bytes = None
                if hasattr(frame, 'SerializeToString'):
                    push_bytes = frame.SerializeToString()
                elif isinstance(frame, (bytes, bytearray)):
                    push_bytes = bytes(frame)
                if not push_bytes:
                    return

                push = WebcastPushFrame()
                push.ParseFromString(push_bytes)
                payload = push.payload if hasattr(push, 'payload') else b''
                if not payload:
                    return
                import zlib
                try:
                    decompressed = zlib.decompress(payload)
                except Exception:
                    decompressed = payload
                resp = WebcastResponse()
                resp.ParseFromString(decompressed)
                type_counts = {}
                gift_messages = 0
                for msg in getattr(resp, 'messages', []):
                    mtype = getattr(msg, 'type', '')
                    type_counts[mtype] = type_counts.get(mtype, 0) + 1
                    if mtype.endswith('GiftMessage') or mtype == 'WebcastGiftMessage' or 'Gift' in mtype:
                        gift_messages += 1
                if type_counts:
                    print(f"[probe] frame types: {type_counts}")
                if gift_messages:
                    total_gift_msgs += gift_messages
                    print(f"[probe] GIFT messages detected in frame: {gift_messages}")
            except Exception as e:
                print(f"[probe] raw decode error: {e}")

    @client.on("disconnect")
    async def on_dc(_):
        print("[probe] disconnected")

    print(f"[probe] Connecting to @{username} for up to {deadline_sec}s...")

    async def stopper():
        while (datetime.now() - start).total_seconds() < deadline_sec:
            await asyncio.sleep(1)
        print(f"[probe] Time limit reached. Frames={total_frames}, GiftMsgs={total_gift_msgs}. Disconnecting...")
        try:
            await client.disconnect()
        except Exception:
            pass

    await asyncio.gather(client.start(), stopper())


if __name__ == "__main__":
    asyncio.run(main())
