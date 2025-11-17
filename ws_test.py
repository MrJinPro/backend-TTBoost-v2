import asyncio, websockets, json

async def main():
    uri = 'ws://127.0.0.1:8001/ws/a5e22321-ae12-4cc0-a8e7-3ac69a13ca70'
    print('Connecting to', uri)
    try:
        async with websockets.connect(uri) as ws:
            print('Connected! Waiting 8s for any events...')
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=8)
                print('Got message:', msg[:200])
            except asyncio.TimeoutError:
                print('No messages within 8s (stream may be offline).')
    except Exception as e:
        print('WS error:', e)

if __name__ == '__main__':
    asyncio.run(main())
