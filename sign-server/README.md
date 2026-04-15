# TTBoost Sign Server

Легкий Node.js сервис, который умеет:
- подписывать TikTok Webcast запросы через HTTP (`POST /sign`)
- держать многопользовательский TikTok LIVE bridge для backend через WebSocket (`/bridge`)

## Структура
- `index.js` — HTTP + WebSocket сервер
- `live-bridge.js` — multi-user session manager для TikTok LIVE
- `tiktok_signer.js` — реализация подписи (можете заменить на свою)
- `package.json` — зависимости и запуск

## Установка и запуск
```powershell
cd sign-server
npm install
npm start
```
Сервер поднимется на `http://localhost:3000`.

Доступные интерфейсы:
- `POST /sign`
- `GET /health`
- `WS /bridge`

## Формат запроса
```json
{
  "url": "https://webcast.tiktok.com/webcast/im/fetch/...",
  "userAgent": "Mozilla/5.0 ..."
}
```

## Формат ответа
```json
{
  "signed_url": "https://webcast...&X-Bogus=...",
  "xBogus": "...",
  "userAgent": "Mozilla/5.0 ..."
}
```

## Настройка бэкенда TTBoost
В файле `backend/.env` задайте:
```
TIKTOK_CONNECTOR_BACKEND=js
```
Этого уже достаточно для локального bridge на том же сервере.

Дополнительно, только если нужно изменить дефолты:
```
TIKTOK_BRIDGE_WS_URL=ws://127.0.0.1:3000/bridge
TIKTOK_BRIDGE_TOKEN=change_me
```

Важно:
- `TIKTOK_BRIDGE_WS_URL` необязателен, по умолчанию backend сам использует `ws://127.0.0.1:3000/bridge`
- `TIKTOK_BRIDGE_TOKEN` необязателен, если bridge крутится локально и наружу не открыт
- `SIGN_SERVER_URL` для JS LIVE bridge не нужен; он нужен только если вы отдельно используете HTTP endpoint `POST /sign`

Перезапустите backend после изменения env.

## Multi-user bridge

Bridge рассчитан на многопользовательский режим: backend держит один служебный WebSocket к Node.js сервису, а сам bridge управляет множеством TikTok LIVE сессий одновременно.

Полезные env для bridge:
```
PORT=3000
# Необязательно. Если не указывать, bridge принимает локальные подключения без токена.
# TIKTOK_BRIDGE_TOKEN=change_me
TIKTOK_BRIDGE_MAX_SESSIONS=1000
TIKTOK_BRIDGE_RECONNECT_BASE_SEC=2
TIKTOK_BRIDGE_RECONNECT_MAX_SEC=30
TIKTOK_BRIDGE_RECONNECT_ATTEMPTS=8
```

## Минимальный запуск на сервере

1. В `backend/.env` включите:
```dotenv
TIKTOK_CONNECTOR_BACKEND=js
```

2. В папке `sign-server` выполните:
```bash
npm install
node index.js
```

3. Перезапустите backend.

4. Проверьте:
```bash
curl http://127.0.0.1:3000/health
```

Если видите `"ok":true`, bridge поднят и backend может к нему подключаться по умолчанию.

## Важно
- Пример алгоритма в `tiktok_signer.js` — упрощенный и предназначен как заглушка/демонстрация интерфейса.
- Для продакшена замените логику на свою актуальную реализацию.
- Не злоупотребляйте частыми переподключениями — TikTok применяет rate limit.
