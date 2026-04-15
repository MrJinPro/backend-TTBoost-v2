# TTBoost TikTok JS Bridge

Node.js сервис для многопользовательских TikTok LIVE подключений.

Он нужен, если backend работает с:

TIKTOK_CONNECTOR_BACKEND=js

## Что делает

- держит WebSocket bridge для backend на `/bridge`
- управляет множеством TikTok LIVE сессий одновременно
- сам делает reconnect внутри JS-контура
- опционально умеет отдавать `/sign`, если рядом есть `tiktok_signer.js`

## Установка

```bash
cd sign-server
npm install
```

## Запуск

```bash
node index.js
```

## Проверка

```bash
curl http://127.0.0.1:3000/health
```

Ожидаемый ответ:

```json
{"ok":true,"bridge":{"sessions":0,"connected":0,"backendClients":0},"signerEnabled":false}
```

## Что нужно в backend/.env

Минимально достаточно:

```dotenv
TIKTOK_CONNECTOR_BACKEND=js
```

Необязательно:

```dotenv
TIKTOK_BRIDGE_WS_URL=ws://127.0.0.1:3000/bridge
TIKTOK_BRIDGE_TOKEN=change_me
```

По умолчанию backend и так подключается к `ws://127.0.0.1:3000/bridge`.

`TIKTOK_BRIDGE_TOKEN` нужен только если вы хотите защитить bridge токеном.

## Переменные bridge

```dotenv
PORT=3000
TIKTOK_BRIDGE_MAX_SESSIONS=1000
TIKTOK_BRIDGE_RECONNECT_BASE_SEC=2
TIKTOK_BRIDGE_RECONNECT_MAX_SEC=30
TIKTOK_BRIDGE_RECONNECT_ATTEMPTS=8
```