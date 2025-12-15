import asyncio
import sys

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package is not installed in this environment.")
    sys.exit(2)

async def listen(url: str, inactivity_timeout: int = 30):
    """Listen to a WS URL and print all incoming messages.

    Stops if no messages arrive within inactivity_timeout seconds.
    """
    print(f"Connecting: {url}")
    try:
        async with websockets.connect(url) as ws:
            print("Connected. Waiting for messages...")
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=inactivity_timeout)
                    print("RECV:", msg)
                except asyncio.TimeoutError:
                    print("TIMEOUT: no messages within", inactivity_timeout, "seconds")
                    return
                except KeyboardInterrupt:
                    return
                except Exception as e:
                    print("ERROR while receiving:", type(e).__name__, str(e))
                    return
    except Exception as e:
        print("ERROR connecting:", type(e).__name__, str(e))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ws_listen.py <ws_url> [inactivity_timeout_seconds]")
        sys.exit(1)
    url = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    asyncio.run(listen(url, timeout))
