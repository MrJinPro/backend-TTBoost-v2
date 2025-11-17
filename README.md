# TTBoost Backend (FastAPI)

Backend для TTBoost Mobile (MVP). Реализует:

- POST /auth/login — вход по лицензионному ключу (MVP-проверка, возвращает ws_token и ws_url)
- POST /tts/generate — заглушка TTS, возвращает URL локального MP3
- WS /ws/{ws_token} — сервер шлёт JSON-события `chat` и `gift`

## Стек

- Python 3.11
- FastAPI, Uvicorn
- Pydantic v2, aiofiles

## Установка и запуск

1. Установите зависимости:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r backend/requirements.txt
```

2. Сконфигурируйте окружение:

Скопируйте `.env.example` в `.env` и при необходимости измените значения:

```
ENV=prod
SERVER_HOST=https://api.ttboost.pro
TTS_BASE_URL=https://api.ttboost.pro
```

В продакшене укажите реальный домен.

3. Запуск (Windows):

```powershell
cd backend; ./run.ps1
```

4. Запуск (Linux/macOS):

```bash
cd backend && bash ./run.sh
```

По умолчанию сервис слушает порт 8000 на 0.0.0.0.

## Эндпоинты

- POST /auth/login
  - body: { "license_key": "string" }
  - resp: {
      "status": "ok",
      "user_id": "uuid",
      "ws_token": "uuid",
      "ws_url": "wss://api.ttboost.pro/ws/<token>",
      "server_time": "2025-11-14T12:34:56.789Z",
      "expires_at": "2025-11-15T12:34:56.789Z"
    }

- POST /tts/generate
  - body: { "text": "string" }
  - resp: { "url": "<TTS_BASE_URL>/static/tts/<id>.mp3" }

- WS /ws/{ws_token}
  - Сервер раз в 3–8 сек отправляет `chat` или `gift` событие для теста

## Примечания

- Переменные окружения загружаются из `.env` (python-dotenv):
  - `ENV` — режим (`dev`/`prod`)
  - `SERVER_HOST` — базовый хост сервера (например, `https://api.ttboost.pro`)
  - `TTS_BASE_URL` — базовый хост для ссылок TTS (по умолчанию равен `SERVER_HOST`)
- Формирование WebSocket URL в продакшене: `wss://<домен>/ws/{token}` при `ENV=prod` (TLS обязателен при HTTPS API).
- Хранилище лицензий и токенов — в памяти (для MVP).
- Статические файлы доступны по `/static/...`.