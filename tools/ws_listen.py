import asyncio
import sys
import json

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package is not installed in this environment.")
    sys.exit(2)

async def listen(url: str, timeout: int = 30):
    print(f"Connecting: {url}")
    try:
        async with websockets.connect(url) as ws:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                print("RECV:", msg)
            except asyncio.TimeoutError:
                print("TIMEOUT: no messages within", timeout, "seconds")
            except Exception as e:
                print("ERROR while receiving:", type(e).__name__, str(e))
    except Exception as e:
        print("ERROR connecting:", type(e).__name__, str(e))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ws_listen.py <ws_url> [timeout_seconds]")
        sys.exit(1)
    url = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    asyncio.run(listen(url, timeout))
