# Быстрый старт после установки Flutter

## 1. Проверьте установку

**ВАЖНО: Закройте и откройте PowerShell заново!**

```powershell
flutter --version
```

Должно показать версию ~3.24.5

## 2. Установите зависимости

```powershell
cd D:\Projects\ttboost-mobile\mobile
flutter pub get
```

## 3. Запустите приложение

### Вариант A: Chrome (быстрее всего)
```powershell
flutter run -d chrome --web-renderer html
```

### Вариант B: Windows Desktop
```powershell
flutter run -d windows
```

### Вариант C: Список устройств
```powershell
flutter devices
flutter run -d <device_id>
```

## 4. Первый вход

При запуске увидите экран логина:

**Выберите "Активация лицензии"**
- Лицензия: `TTB-9E2E-5DE1-A3FC`
- Username: придумайте (например, `testuser123`)
- Password: придумайте (минимум 8 символов)

Или **"Вход в аккаунт"** (если уже активировали):
- Username: `streamer123`
- Password: `Test123!`

## 5. Настройка

После входа нажмите ⚙️ (настройки):
1. TikTok Username: `ваш_тикток` (обязательно!)
2. Voice: выберите голос
3. Сохраните

## 6. Подключение к стриму

На главном экране:
1. Нажмите "Connect"
2. Дождитесь зелёного статуса "Connected"

## 7. Тестирование

Откройте TikTok Live стрим и:
- Напишите комментарий → должен озвучиться
- Отправьте подарок → должен сработать триггер
- Проверьте лог событий на экране

---

## Если что-то не работает

### Ошибка "flutter: command not found"
```powershell
# Перезапустите PowerShell!
# Или добавьте в PATH вручную:
$env:Path += ";C:\flutter\bin"
```

### Ошибка при pub get
```powershell
flutter clean
flutter pub get
```

### Приложение не запускается
```powershell
flutter doctor
# Исправьте найденные проблемы
```

### WebSocket не подключается
- Проверьте TikTok username в настройках
- Проверьте интернет соединение
- Проверьте JWT токен (перелогиньтесь)

---

## Полезные команды

```powershell
# Логи
flutter logs

# Пересборка
flutter clean
flutter pub get
flutter run -d chrome

# Релизная сборка
flutter build web --release
flutter build windows --release

# Обновление Flutter
flutter upgrade
```

---

Подробный план тестирования: `TESTING_PLAN.md`
