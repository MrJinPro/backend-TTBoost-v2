# 🎙️ TTBoost — TikTok Live TTS & Events

> Профессиональная система озвучки и кастомных триггеров для TikTok Live стримов

[![Production](https://img.shields.io/badge/Production-Live-success)](https://api.ttboost.pro)
[![API Version](https://img.shields.io/badge/API-v2.0-blue)](https://api.ttboost.pro)
[![License](https://img.shields.io/badge/License-Commercial-orange)]()

---

## 🌟 Особенности

✅ **Реальные события** — только живые комментарии, подарки и лайки (без демо-режима)  
✅ **Кастомные звуки** — загружайте свои звуки для подарков и триггеров  
✅ **Умные триггеры** — автоматические действия на события (TTS, звуки, условия)  
✅ **TTS на русском** — Google TTS + Edge TTS с фоллбеком  
✅ **WebSocket реал-тайм** — мгновенная доставка событий  
✅ **Мобильное приложение** — Flutter (Android/iOS/Web)  
✅ **Лицензии** — система активации через ключи  

---

## 🚀 Быстрый старт

### Для пользователей

1. **Получите лицензионный ключ** (покупка на сайте)
2. **Скачайте приложение** TTBoost Mobile
3. **Активируйте лицензию** — введите ключ, TikTok username и пароль
4. **Подключитесь к стриму** — нажмите кнопку "Connect"
5. **Наслаждайтесь** — все события озвучиваются автоматически

### Для разработчиков

**Backend (API Server)**
```bash
git clone https://github.com/MrJinPro/backend-TTBoost-v2.git
cd backend-TTBoost-v2
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Настроить .env
python -m uvicorn app.main:app --reload
```

**Frontend (Flutter Mobile)**
```bash
git clone <mobile_repo>
cd ttboost-mobile/mobile
flutter pub get
flutter run
```

Полная инструкция: [DEPLOYMENT.md](backend/DEPLOYMENT.md)

---

## 🏗️ Архитектура

```
┌─────────────────┐
│  Flutter Mobile │ ◄─── HTTPS ───┐
│   (Android/iOS) │                │
└─────────────────┘                │
                                   │
┌─────────────────┐                │
│   Web Browser   │ ◄─── HTTPS ───┤
│  (Purchase/UI)  │                │
└─────────────────┘                │
                                   ▼
                         ┌──────────────────┐
                         │  Nginx (443/80)  │
                         │  api.ttboost.pro │
                         └──────────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │                              │
              ┌─────▼──────┐              ┌───────▼────────┐
              │  FastAPI   │              │  Static Files  │
              │  (Uvicorn) │              │ (media domain) │
              │  Port 8000 │              │  /var/ttboost  │
              └─────┬──────┘              └────────────────┘
                    │
          ┌─────────┼─────────┐
          │         │         │
    ┌─────▼───┐ ┌──▼────┐ ┌──▼──────────┐
    │ PostgSQL│ │ Redis │ │ TikTokLive  │
    │   (DB)  │ │(cache)│ │   Client    │
    └─────────┘ └───────┘ └─────────────┘
```

---

## 📡 API Endpoints

### Production
- **API:** https://api.ttboost.pro
- **Media:** https://media.ttboost.pro
- **WebSocket:** wss://api.ttboost.pro/v2/ws

### v2 Endpoints

**Авторизация**
- `POST /v2/auth/register` — регистрация
- `POST /v2/auth/login` — вход
- `POST /v2/auth/redeem-license` — обмен лицензии на JWT
- `GET /v2/auth/me` — профиль

**Лицензии**
- `POST /v2/license/issue` — выдача ключа (админ)
- `GET /v2/license/check` — проверка статуса

**Медиа**
- `POST /v2/sounds/upload` — загрузка звука (≤100KB, ≤5s)
- `GET /v2/sounds/list` — список звуков

**Триггеры**
- `POST /v2/triggers/set` — создать триггер
- `GET /v2/triggers/list` — список триггеров
- `POST /v2/triggers/delete` — удалить

**Настройки**
- `POST /v2/settings/update` — обновить настройки

**WebSocket**
- `WS /v2/ws?token=JWT` — события реал-тайм

Полная документация: [MOBILE_INTEGRATION.md](MOBILE_INTEGRATION.md)

---

## 🎯 Примеры использования

### Создание триггера "Роза"
```bash
curl -X POST https://api.ttboost.pro/v2/triggers/set \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "gift",
    "condition_key": "gift_name",
    "condition_value": "Rose",
    "action": "play_sound",
    "action_params": {"sound_filename": "rose.mp3"}
  }'
```

### Кастомный TTS для приветствия
```bash
curl -X POST https://api.ttboost.pro/v2/triggers/set \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "chat",
    "condition_key": "message_contains",
    "condition_value": "привет",
    "action": "tts",
    "action_params": {
      "text_template": "Привет, {user}! Добро пожаловать!"
    }
  }'
```

### WebSocket подключение
```javascript
const ws = new WebSocket('wss://api.ttboost.pro/v2/ws?token=YOUR_JWT');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'chat':
      console.log(`💬 ${data.user}: ${data.message}`);
      playAudio(data.tts_url);
      break;
    
    case 'gift':
      console.log(`🎁 ${data.user} -> ${data.gift_name}`);
      playAudio(data.sound_url);
      break;
  }
};
```

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — высокопроизводительный Python веб-фреймворк
- **Uvicorn** — ASGI сервер
- **PostgreSQL** — основная БД (SQLAlchemy ORM)
- **Redis** — кеш и очереди (опционально)
- **TikTokLive** — клиент для подключения к TikTok Live
- **gTTS / Edge-TTS** — генерация речи
- **JWT** — авторизация (PyJWT)
- **Nginx** — reverse proxy + static files

### Frontend
- **Flutter** — кросс-платформенное приложение
- **Dart** — язык программирования
- **WebSocket** — реал-тайм события
- **HTTP** — REST API клиент

---

## 📊 Производительность

| Метрика | Значение |
|---------|----------|
| API Response Time | <50ms |
| WebSocket Latency | <100ms |
| TTS Generation | ~1-2s |
| Max Users | 1000+ |
| Uptime | 99.9% |

---

## 🔐 Безопасность

✅ HTTPS (TLS 1.3)  
✅ JWT авторизация (HS256)  
✅ Пароли: pbkdf2_sha256  
✅ Rate limiting  
✅ CORS правильно настроен  
✅ Валидация на всех эндпоинтах  
✅ Admin API Key для критичных операций  

---

## 📄 Лицензирование

Система работает на коммерческих лицензиях:

- **Test** — 7 дней (бесплатно для тестирования)
- **Basic** — 30 дней (базовые функции)
- **Pro** — 90 дней (все функции + приоритет)
- **Unlimited** — без ограничений

Лицензии выдаются через `/v2/license/issue` (админ) и активируются через `/v2/auth/redeem-license` (пользователь).

---

## 🧪 Тестирование

```bash
# Health check
curl https://api.ttboost.pro/

# Запустить все тесты
cd backend
powershell -ExecutionPolicy Bypass -File test_production.ps1
```

Smoke tests: [PRODUCTION_CHECKLIST.md](backend/PRODUCTION_CHECKLIST.md)

---

## 📚 Документация

- [Деплой на продакшн](backend/DEPLOYMENT.md)
- [Интеграция с мобильным приложением](MOBILE_INTEGRATION.md)
- [Production Checklist](backend/PRODUCTION_CHECKLIST.md)
- [Тестовые лицензии](LICENSES.md)

---

## 🤝 Поддержка

- **GitHub Issues:** [backend-TTBoost-v2/issues](https://github.com/MrJinPro/backend-TTBoost-v2/issues)
- **Email:** support@ttboost.pro
- **Telegram:** @ttboost_support

---

## 📈 Roadmap

- [x] v2 API с JWT и PostgreSQL
- [x] WebSocket поддержка token в query
- [x] Лицензии через redeem-license
- [x] Prodакшн деплой
- [ ] Веб-портал для покупки лицензий
- [ ] Dashboard админа
- [ ] Аналитика и статистика
- [ ] Multi-stream support
- [ ] Дополнительные языки TTS

---

## 📜 Changelog

### v2.0 (18.11.2025)
- ✨ Полностью переработанная система авторизации (JWT)
- ✨ PostgreSQL вместо SQLite
- ✨ Лицензии с обменом (redeem-license)
- ✨ WebSocket с query token для веба
- ✨ Prodакшн деплой на api.ttboost.pro
- 🐛 Исправлены проблемы с bcrypt на Windows (pbkdf2_sha256)
- 📝 Полная документация

### v1.0 (15.11.2025)
- 🎉 Первый релиз
- ✅ Базовые функции TTS и триггеров
- ✅ TikTok Live интеграция

---

## ⭐ Star History

Если проект полезен — поставьте звезду!

```
⭐⭐⭐⭐⭐
```

---

**Made with ❤️ by MrJinPro**  
© 2025 TTBoost. All rights reserved.
