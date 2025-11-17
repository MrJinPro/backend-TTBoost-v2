import asyncio, json, os, sys
import argparse
import websockets
import httpx

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default=os.environ.get('BASE', 'http://127.0.0.1:8000'))
    p.add_argument('--key', default=os.environ.get('KEY', 'TTBOOST-PRO-2024'))
    p.add_argument('--username', default=os.environ.get('USERNAME'))
    return p.parse_args()

async def probe():
    args = parse_args()
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(f"{args.base}/auth/login", json={"license_key": args.key})
        r.raise_for_status()
        data = r.json()
        token = data.get('ws_token')
        ws_url = f"ws://{httpx.URL(args.base).host}:{httpx.URL(args.base).port or 80}/ws/{token}"
        print('Health:', (await client.get(f"{args.base}/")).json())
        if args.username:
            # Устанавливаем TikTok username для этого токена
            rr = await client.post(f"{args.base}/auth/set-tiktok", json={"ws_token": token, "tiktok_username": args.username})
            print('Set username status:', rr.status_code)
    print('Connecting WS:', ws_url)
    try:
        async with websockets.connect(ws_url) as ws:
            print('WS connected, waiting for a server message (3s)...')
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                print('WS recv:', msg[:200])
            except asyncio.TimeoutError:
                print('WS connected but no message in 3s (ok if stream offline).')
    except Exception as e:
        print('WS error:', e)

if __name__ == '__main__':
    asyncio.run(probe())
