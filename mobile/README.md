# NovaBoost Mobile (Flutter)

Flutter-клиент для NovaBoost (MVP).

Реализовано:
- Экран Login: вход/регистрация, запрос к backend, сохранение токена
- Экран Home: переключатели TTS/Gifts, индикаторы статуса, мини-лог, подключение к WebSocket (по ws_url из /auth/login)
- Экран Settings: управление громкостью TTS/подарков и переключатели
- Audioplayers: параллельное воспроизведение звуков по URL

## Быстрый старт

1) Установите Flutter SDK 3.x

2) Создайте платформенные папки (если их нет):

```powershell
cd mobile
flutter create .
flutter pub get
```

3) Запуск:

```powershell
# PROD (по умолчанию)
flutter run -d windows

# DEV (локальное тестирование, Android эмулятор/Chrome)
flutter run -d emulator-5554
```

Конфигурацию адресов можно задавать через `--dart-define`:
- `API_BASE_URL` (по умолчанию `https://api.ttboost.pro`)
- `WS_URL` (по умолчанию `wss://api.ttboost.pro/v2/ws`)

Для DEV `API_BASE_URL=http://10.0.2.2:8000` (эмулятор Android), для PROD `API_BASE_URL=https://api.ttboost.pro`.

### DEMO режим (без backend)

Для быстрого просмотра интерфейса можно запустить web/desktop сборку и использовать моковые данные (доработка по необходимости).

## Фоновый режим (Android/iOS)

Для полной работы в фоне потребуется настроить платформенные проекты:

- Android:
  - Разрешения в `android/app/src/main/AndroidManifest.xml`:
    - `<uses-permission android:name="android.permission.WAKE_LOCK" />`
    - `<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />` (Android 13+)
  - Foreground service: используется `flutter_background_service` с уведомлением «NovaBoost работает в фоне» (канал `ttboost_bg`).
  - Медиа в фоне: конфигурация аудиосессии выполняется в `main.dart` через пакет `audio_session`.
  - Проверьте настройки `flutter_local_notifications` (каналы/инициализация) согласно документации плагина.

- iOS:
  - В Xcode включите Capabilities: Background Modes → Audio.
  - В `Info.plist` добавьте описание использования фонового аудио (если требуется для публикации).
  - `audio_session` настраивается в `main.dart` и включает AVAudioSession (режим Music/Playback).

В текущем MVP код содержит заготовки и архитектуру; платформенные изменения нужно внести после генерации android/ios папок. Подробную интеграцию можно доработать на следующем шаге.