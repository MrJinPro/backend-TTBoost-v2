# 🎮 Запуск NovaBoost Mobile

## Быстрый старт

### 1. Установите Flutter (если ещё не установлен)
```powershell
# Скачайте Flutter SDK: https://flutter.dev/docs/get-started/install/windows
# Распакуйте и добавьте в PATH
flutter doctor
```

### 2. Установите зависимости
```powershell
cd mobile
flutter pub get
```

### 3. Запустите приложение
```powershell
# Автоматический запуск с выбором платформы
.\run.ps1

# ИЛИ вручную:
flutter run -d windows      # Windows Desktop
flutter run -d chrome        # Web Browser
flutter run -d android       # Android (требует эмулятор или устройство)
```

### Spotify (Android)
1. В Spotify Dashboard добавьте redirect URI `novaboost://spotify-auth`.
2. На сервере заполните `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` и `SPOTIFY_REDIRECT_URI=novaboost://spotify-auth`.
3. При необходимости в папке `mobile` создайте `.env.local` на основе `.env.local.example` и укажите `SPOTIFY_CLIENT_ID` и `SPOTIFY_REDIRECT_URI` как локальный override.
4. `SPOTIFY_CLIENT_SECRET` в мобильное приложение не добавляется.
5. Подключайте Spotify из профиля в Android-сборке. В Web/Chrome этот сценарий не поддерживается.

## Тестирование v2 API

### Данные для входа
Используйте тестовые данные из продакшн API:

**Вариант 1: Регистрация нового аккаунта**
- Имя пользователя: (выберите своё)
- Пароль: (задайте свой)

**Вариант 2: Вход в существующий аккаунт**
- Имя пользователя: `streamer123`
- Пароль: `Test123!`

### Функции для тестирования

1. **Авторизация**
   - ✅ Активация лицензии (redeem-license)
   - ✅ Вход в аккаунт (login)
   - ✅ Авто-логин при повторном запуске

2. **Профиль**
   - ✅ Получение данных пользователя
   - ✅ Настройка TikTok username
   - ✅ Выбор голоса TTS
   - ✅ Настройка громкости

3. **Звуки**
   - ✅ Загрузка звукового файла (≤100KB, ≤5s)
   - ✅ Список загруженных звуков
   - ✅ Воспроизведение звуков

4. **Триггеры**
   - ✅ Создание триггера для подарка
   - ✅ Создание триггера для чата
   - ✅ Список триггеров
   - ✅ Удаление триггера

5. **WebSocket**
   - ✅ Подключение к стриму
   - ✅ Получение событий (chat, gift, like, viewer_join)
   - ✅ Автоматическое воспроизведение TTS и звуков

## Структура проекта

```
mobile/
├── lib/
│   ├── main.dart                 # Точка входа
│   ├── utils/
│   │   └── constants.dart        # API URLs (v2)
│   ├── services/
│   │   ├── api_service.dart      # V2 REST API
│   │   └── ws_service.dart       # V2 WebSocket
│   ├── providers/
│   │   └── auth_provider.dart    # JWT + secure storage
│   ├── screens/
│   │   ├── login_screen.dart     # Redeem + Login
│   │   ├── home_screen.dart      # WebSocket + события
│   │   ├── settings_screen.dart  # Настройки
│   │   └── triggers_screen.dart  # Триггеры
│   └── models/
│       ├── chat_event.dart
│       └── gift_event.dart
└── pubspec.yaml                  # Зависимости

```

## Известные проблемы

- **Windows**: Flutter Secure Storage может требовать дополнительных настроек
- **Web**: File picker ограничен из-за CORS политики браузеров
- **Android**: Требуются разрешения для хранилища и интернета

## Отладка

### Просмотр логов
```powershell
# В отдельной консоли
flutter logs
```

### Очистка кеша
```powershell
flutter clean
flutter pub get
```

### Проверка подключения к API
```powershell
# Тест health endpoint
curl https://api.ttboost.pro/
```

## Полезные команды

```powershell
# Билд для Windows
flutter build windows --release

# Билд для Web
flutter build web --release --web-renderer html

# Билд для Android
flutter build apk --release
```
