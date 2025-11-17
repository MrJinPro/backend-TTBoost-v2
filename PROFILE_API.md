# Профиль пользователя и кастомные звуки

## 🎵 Обзор функционала

TTBoost Mobile теперь поддерживает **персонализацию звуков**:
- 🎁 **Кастомные звуки для подарков** - загрузите свои звуки для каждого типа подарка
- 👤 **VIP зрители** - специальные звуки при входе определённых зрителей в стрим
- 💾 **Профиль пользователя** - все настройки сохраняются на сервере

---

## 📋 API Endpoints

### Загрузка звуков

#### POST `/sounds/upload`
Загрузить звуковой файл на сервер.

**Form Data:**
- `ws_token` (string) - токен пользователя
- `sound_name` (string) - название звука (для UI)
- `file` (file) - аудио файл (MP3, WAV, OGG, M4A, макс 5MB)

**Response:**
```json
{
  "status": "ok",
  "sound_file": "rose_sound_a1b2c3d4.mp3",
  "sound_url": "/static/sounds/{user_id}/rose_sound_a1b2c3d4.mp3"
}
```

#### GET `/sounds/list/{ws_token}`
Получить список всех загруженных звуков.

**Response:**
```json
{
  "sounds": [
    {
      "filename": "rose_sound_a1b2c3d4.mp3",
      "url": "/static/sounds/{user_id}/rose_sound_a1b2c3d4.mp3"
    }
  ]
}
```

#### DELETE `/sounds/delete/{ws_token}/{filename}`
Удалить звуковой файл.

---

### Управление профилем

#### POST `/profile/get`
Получить профиль пользователя со всеми настройками.

**Request:**
```json
{
  "ws_token": "your_token"
}
```

**Response:**
```json
{
  "status": "ok",
  "profile": {
    "user_id": "demo_12345678",
    "tiktok_username": "your_username",
    "voice_id": "ru-RU-SvetlanaNeural",
    "tts_enabled": true,
    "tts_volume": 1.0,
    "gifts_enabled": true,
    "gifts_volume": 1.0,
    "gift_sounds": {
      "Rose": {
        "gift_name": "Rose",
        "sound_file": "rose_sound.mp3",
        "enabled": true
      }
    },
    "viewer_sounds": {
      "special_viewer": {
        "viewer_username": "special_viewer",
        "sound_file": "vip_enter.mp3",
        "enabled": true
      }
    },
    "created_at": "2025-11-15T10:00:00Z",
    "updated_at": "2025-11-15T10:30:00Z"
  }
}
```

---

### Звуки подарков

#### POST `/profile/gift-sound/set`
Привязать звук к подарку.

**Request:**
```json
{
  "ws_token": "your_token",
  "gift_name": "Rose",
  "sound_file": "rose_sound_a1b2c3d4.mp3",
  "enabled": true
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Sound set for gift 'Rose'"
}
```

#### POST `/profile/gift-sound/delete`
Удалить привязку звука к подарку.

**Request:**
```json
{
  "ws_token": "your_token",
  "gift_name": "Rose"
}
```

---

### VIP зрители

#### POST `/profile/viewer-sound/set`
Привязать звук к зрителю.

**Request:**
```json
{
  "ws_token": "your_token",
  "viewer_username": "special_viewer",
  "sound_file": "vip_enter_a1b2c3d4.mp3",
  "enabled": true
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Sound set for viewer '@special_viewer'"
}
```

#### POST `/profile/viewer-sound/delete`
Удалить привязку звука к зрителю.

**Request:**
```json
{
  "ws_token": "your_token",
  "viewer_username": "special_viewer"
}
```

#### GET `/profile/sounds/list/{ws_token}`
Получить список всех настроенных звуков.

**Response:**
```json
{
  "gift_sounds": [
    {
      "gift_name": "Rose",
      "sound_file": "rose_sound.mp3",
      "enabled": true
    }
  ],
  "viewer_sounds": [
    {
      "viewer_username": "special_viewer",
      "sound_file": "vip_enter.mp3",
      "enabled": true
    }
  ]
}
```

---

## 🎮 Как это работает

### 1. Кастомные звуки подарков

Когда кто-то отправляет подарок в TikTok Live:

1. **С кастомным звуком:**
   - Проверяется профиль пользователя
   - Если для подарка настроен звук → воспроизводится кастомный звук
   - Событие в WebSocket: `{type: "gift", sound_url: "/static/sounds/{user_id}/rose.mp3"}`

2. **Без кастомного звука (fallback):**
   - Генерируется TTS: "Имя отправил подарок Название, количество X"
   - Событие в WebSocket: `{type: "gift", sound_url: "/static/tts/..."}`

### 2. VIP зрители

Когда зритель заходит в стрим:

1. **VIP зритель (с кастомным звуком):**
   - Проверяется профиль пользователя
   - Если для зрителя настроен звук → отправляется событие
   - Событие в WebSocket: `{type: "viewer_join", user: "username", sound_url: "..."}`

2. **Обычный зритель:**
   - Событие не отправляется (не загружает канал)

### 3. Хранение файлов

```
backend/
  static/
    sounds/
      {user_id}/
        rose_sound_a1b2c3d4.mp3
        galaxy_sound_f5e6d7c8.mp3
        vip_enter_g9h0i1j2.mp3
```

---

## 💡 Популярные подарки TikTok

Список популярных подарков для настройки:

- `Rose` 🌹 - Роза (1 алмаз)
- `Heart` ❤️ - Сердце (10 алмазов)
- `Galaxy` 🌌 - Галактика (1000 алмазов)
- `TikTok` - Логотип TikTok (1 алмаз)
- `Sun Cream` ☀️ - Крем от солнца (50 алмазов)
- `Love Bang` 💥 - Взрыв любви (25 алмазов)
- `Fireworks` 🎆 - Фейерверк (1099 алмазов)
- `Drama Queen` 👑 - Драма квин (5000 алмазов)
- `Lion` 🦁 - Лев (29999 алмазов)

*(Названия могут отличаться в зависимости от региона)*

---

## 🔧 Пример использования

### Загрузка звука для розы

```python
import requests

# 1. Загрузить звук
files = {'file': open('rose_sound.mp3', 'rb')}
data = {
    'ws_token': 'your_token',
    'sound_name': 'rose_sound'
}
response = requests.post('http://localhost:8000/sounds/upload', files=files, data=data)
sound_file = response.json()['sound_file']

# 2. Привязать к подарку
requests.post('http://localhost:8000/profile/gift-sound/set', json={
    'ws_token': 'your_token',
    'gift_name': 'Rose',
    'sound_file': sound_file,
    'enabled': True
})
```

### Добавить VIP зрителя

```python
# 1. Загрузить звук входа
files = {'file': open('vip_enter.mp3', 'rb')}
data = {
    'ws_token': 'your_token',
    'sound_name': 'vip_enter'
}
response = requests.post('http://localhost:8000/sounds/upload', files=files, data=data)
sound_file = response.json()['sound_file']

# 2. Привязать к зрителю
requests.post('http://localhost:8000/profile/viewer-sound/set', json={
    'ws_token': 'your_token',
    'viewer_username': 'special_viewer',
    'sound_file': sound_file,
    'enabled': True
})
```

---

## 📱 Мобильное приложение (TODO)

Планируемый UI:

```
Профиль
├── Голос TTS
│   └── [Выбрать голос] → VoiceSelectionScreen
│
├── Звуки подарков
│   ├── Rose 🌹 [🔊 rose_sound.mp3] [🗑️]
│   ├── Heart ❤️ [+ Добавить звук]
│   └── Galaxy 🌌 [+ Добавить звук]
│
└── VIP зрители
    ├── @special_viewer [🔊 vip.mp3] [🗑️]
    └── [+ Добавить VIP]
```

---

**Версия:** 2.0  
**Дата:** 15 ноября 2025 г.
