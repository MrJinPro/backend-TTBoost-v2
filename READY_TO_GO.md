# ✅ Финальный чеклист установки и запуска

## Сейчас выполняется:
⏳ Загрузка Flutter SDK (~300 МБ)
⏳ Это займёт 5-10 минут в зависимости от интернета

---

## После завершения установки:

### 1. Перезапустите PowerShell ⚠️
**ОБЯЗАТЕЛЬНО!** Новый PATH не подхватится без перезапуска

### 2. Проверьте Flutter
```powershell
flutter --version
# Должно показать: Flutter 3.24.5

flutter doctor
# Покажет что ещё нужно (Chrome, Visual Studio, etc)
```

### 3. Установите зависимости проекта
```powershell
cd D:\Projects\ttboost-mobile\mobile
flutter pub get
```

### 4. Запустите приложение
```powershell
# Вариант 1: Chrome (рекомендуется для быстрого старта)
flutter run -d chrome --web-renderer html

# Вариант 2: Windows Desktop
flutter run -d windows

# Вариант 3: Посмотреть доступные устройства
flutter devices
```

---

## Тестирование приложения

### Шаг 1: Активация лицензии
При первом запуске выберите "Активация лицензии":
- **Лицензионный ключ**: `TTB-9E2E-5DE1-A3FC`
- **Username**: придумайте (например: `myuser123`)
- **Password**: придумайте (минимум 8 символов)

ИЛИ войдите в существующий аккаунт:
- **Username**: `streamer123`
- **Password**: `Test123!`

### Шаг 2: Настройте профиль
Нажмите ⚙️ (настройки):
1. **TikTok Username**: `ваш_тикток` ⚠️ ОБЯЗАТЕЛЬНО!
2. **Voice**: `ru-RU-SvetlanaNeural` (женский) или `ru-RU-DmitryNeural` (мужской)
3. **Громкость**: 80-100 для обоих

### Шаг 3: Загрузите звук (опционально)
Используйте тестовый файл:
```
D:\Projects\ttboost-mobile\test_sound.mp3 (4.69 KB)
```

### Шаг 4: Создайте триггер (опционально)
Пример: Триггер для подарка Rose
- Event Type: `gift`
- Condition: `gift_name = Rose`
- Action: `tts`
- Text: `Спасибо за розу, {user}!`

### Шаг 5: Подключитесь к стриму
1. Нажмите кнопку **"Connect"**
2. Дождитесь статуса **"Connected"** (зелёный)
3. WebSocket подключится к: `wss://api.ttboost.pro/v2/ws`

### Шаг 6: Проверьте события
Во время TikTok Live стрима:
- ✅ Комментарии озвучиваются
- ✅ Подарки воспроизводят звуки
- ✅ События логируются на экране
- ✅ Триггеры срабатывают

---

## Если что-то не работает

### "flutter: command not found"
```powershell
# Перезапустите PowerShell!
# Или добавьте вручную:
$env:Path += ";C:\flutter\bin"
```

### Ошибки при pub get
```powershell
flutter clean
flutter pub get
```

### WebSocket не подключается
- Проверьте TikTok username в настройках
- Убедитесь что стрим активен
- Перелогиньтесь (JWT может истечь)

### Chrome не запускается
```powershell
# Установите Chrome или используйте Windows Desktop:
flutter run -d windows
```

---

## Полезные команды

```powershell
# Логи в реальном времени
flutter logs

# Пересборка проекта
flutter clean
flutter pub get

# Релизная сборка
flutter build web --release
flutter build windows --release

# Обновление Flutter
flutter upgrade

# Помощь
flutter help
```

---

## Текущий статус

✅ Backend API v2: https://api.ttboost.pro
✅ Код приложения обновлён для v2
✅ Тестовые файлы готовы
✅ Документация создана
⏳ Flutter SDK устанавливается...

## Следующие шаги после запуска

1. Протестировать все функции (чеклист выше)
2. Создать релизную сборку
3. Развернуть на продакшн (опционально)
4. Собрать feedback от пользователей

---

**Примерное время до запуска: ~10-15 минут**
(загрузка Flutter + pub get + первый запуск)
