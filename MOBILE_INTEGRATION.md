# TTBoost Mobile — API Integration Guide v2

## 🚀 Production API
**Base URL:** `https://api.ttboost.pro`  
**Media URL:** `https://media.ttboost.pro`  
**WebSocket:** `wss://api.ttboost.pro/v2/ws`

---

## 📱 Быстрый старт для Flutter

### 1. Установка зависимостей

```yaml
# pubspec.yaml
dependencies:
  http: ^1.1.0
  web_socket_channel: ^2.4.0
  shared_preferences: ^2.2.2
  flutter_secure_storage: ^9.0.0
```

### 2. API Service

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class TTBoostApi {
  static const String baseUrl = 'https://api.ttboost.pro';
  static const String mediaUrl = 'https://media.ttboost.pro';
  
  String? _accessToken;
  
  // 1. Redeem License (первый вход)
  Future<Map<String, dynamic>> redeemLicense({
    required String username,
    required String password,
    required String licenseKey,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/v2/auth/redeem-license'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
        'license_key': licenseKey,
      }),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      _accessToken = data['access_token'];
      // Сохранить токен в SecureStorage
      return data;
    } else {
      throw Exception('Redeem failed: ${response.body}');
    }
  }
  
  // 2. Login (повторный вход)
  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/v2/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      _accessToken = data['access_token'];
      return data;
    } else {
      throw Exception('Login failed');
    }
  }
  
  // 3. Get Profile
  Future<Map<String, dynamic>> getProfile() async {
    final response = await http.get(
      Uri.parse('$baseUrl/v2/auth/me'),
      headers: {
        'Authorization': 'Bearer $_accessToken',
      },
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load profile');
    }
  }
  
  // 4. Upload Sound
  Future<Map<String, dynamic>> uploadSound(String filePath) async {
    var request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/v2/sounds/upload'),
    );
    
    request.headers['Authorization'] = 'Bearer $_accessToken';
    request.files.add(await http.MultipartFile.fromPath('file', filePath));
    
    final response = await request.send();
    final responseBody = await response.stream.bytesToString();
    
    if (response.statusCode == 200) {
      return jsonDecode(responseBody);
    } else {
      throw Exception('Upload failed: $responseBody');
    }
  }
  
  // 5. List Sounds
  Future<List<dynamic>> listSounds() async {
    final response = await http.get(
      Uri.parse('$baseUrl/v2/sounds/list'),
      headers: {'Authorization': 'Bearer $_accessToken'},
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['sounds'];
    } else {
      throw Exception('Failed to load sounds');
    }
  }
  
  // 6. Set Trigger
  Future<Map<String, dynamic>> setTrigger({
    required String eventType,
    required String action,
    String? conditionKey,
    String? conditionValue,
    Map<String, dynamic>? actionParams,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/v2/triggers/set'),
      headers: {
        'Authorization': 'Bearer $_accessToken',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'event_type': eventType,
        'action': action,
        if (conditionKey != null) 'condition_key': conditionKey,
        if (conditionValue != null) 'condition_value': conditionValue,
        if (actionParams != null) 'action_params': actionParams,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to set trigger');
    }
  }
  
  // 7. Update Settings
  Future<Map<String, dynamic>> updateSettings({
    int? ttsVolume,
    int? giftsVolume,
    bool? ttsEnabled,
    bool? giftSoundsEnabled,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/v2/settings/update'),
      headers: {
        'Authorization': 'Bearer $_accessToken',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        if (ttsVolume != null) 'tts_volume': ttsVolume,
        if (giftsVolume != null) 'gifts_volume': giftsVolume,
        if (ttsEnabled != null) 'tts_enabled': ttsEnabled,
        if (giftSoundsEnabled != null) 'gift_sounds_enabled': giftSoundsEnabled,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to update settings');
    }
  }
}
```

### 3. WebSocket Service

```dart
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';

class TTBoostWebSocket {
  WebSocketChannel? _channel;
  
  void connect(String accessToken) {
    final wsUrl = 'wss://api.ttboost.pro/v2/ws?token=$accessToken';
    _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
    
    _channel!.stream.listen(
      (message) {
        final event = jsonDecode(message);
        _handleEvent(event);
      },
      onError: (error) {
        print('WebSocket error: $error');
      },
      onDone: () {
        print('WebSocket closed');
      },
    );
  }
  
  void _handleEvent(Map<String, dynamic> event) {
    switch (event['type']) {
      case 'chat':
        print('💬 ${event['user']}: ${event['message']}');
        // Воспроизвести TTS: event['tts_url']
        break;
      
      case 'gift':
        print('🎁 ${event['user']} -> ${event['gift_name']} x${event['count']}');
        // Воспроизвести звук: event['sound_url']
        break;
      
      case 'like':
        print('❤️ ${event['user']} -> ${event['count']} likes');
        break;
      
      case 'viewer_join':
        print('👋 ${event['user']} joined');
        if (event['sound_url'] != null) {
          // Воспроизвести звук приветствия
        }
        break;
      
      default:
        print('Unknown event: ${event['type']}');
    }
  }
  
  void disconnect() {
    _channel?.sink.close();
  }
}
```

---

## 🔐 Поток авторизации

### Первый вход (с лицензионным ключом)

```dart
final api = TTBoostApi();

// 1. Пользователь вводит лицензионный ключ
String licenseKey = "TTB-XXXX-XXXX-XXXX";
String username = "streamer123";  // TikTok username
String password = "SecurePass123!";

// 2. Обмен лицензии на JWT
final result = await api.redeemLicense(
  username: username,
  password: password,
  licenseKey: licenseKey,
);

// 3. Сохранить токен
await secureStorage.write(key: 'access_token', value: result['access_token']);
await secureStorage.write(key: 'username', value: username);
await secureStorage.write(key: 'password', value: password);

// 4. Показать дату окончания лицензии
print('License expires: ${result['license_expires_at']}');
```

### Повторный вход

```dart
// Восстановить сохранённые данные
final username = await secureStorage.read(key: 'username');
final password = await secureStorage.read(key: 'password');

// Войти снова
final result = await api.login(
  username: username!,
  password: password!,
);

await secureStorage.write(key: 'access_token', value: result['access_token']);
```

### Автоматический вход при старте

```dart
Future<bool> autoLogin() async {
  final token = await secureStorage.read(key: 'access_token');
  
  if (token != null) {
    api._accessToken = token;
    
    try {
      // Проверить валидность токена
      await api.getProfile();
      return true;
    } catch (e) {
      // Токен истёк, перелогиниться
      final username = await secureStorage.read(key: 'username');
      final password = await secureStorage.read(key: 'password');
      
      if (username != null && password != null) {
        await api.login(username: username, password: password);
        return true;
      }
    }
  }
  
  return false;
}
```

---

## 📡 Примеры использования

### Создание триггера "Роза"

```dart
await api.setTrigger(
  eventType: 'gift',
  conditionKey: 'gift_name',
  conditionValue: 'Rose',
  action: 'play_sound',
  actionParams: {
    'sound_filename': 'rose_sound.mp3',
  },
);
```

### Создание кастомного TTS триггера

```dart
await api.setTrigger(
  eventType: 'chat',
  conditionKey: 'message_contains',
  conditionValue: 'привет',
  action: 'tts',
  actionParams: {
    'text_template': 'Привет, {user}! Добро пожаловать в стрим!',
  },
);
```

### Настройка громкости

```dart
await api.updateSettings(
  ttsVolume: 80,
  giftsVolume: 90,
  ttsEnabled: true,
  giftSoundsEnabled: true,
);
```

---

## 🎯 UI Screens

### 1. Login Screen

```dart
class LoginScreen extends StatefulWidget {
  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _licenseController = TextEditingController();
  
  Future<void> _handleRedeem() async {
    try {
      final api = TTBoostApi();
      final result = await api.redeemLicense(
        username: _usernameController.text.trim(),
        password: _passwordController.text,
        licenseKey: _licenseController.text.trim(),
      );
      
      // Сохранить и перейти на главный экран
      Navigator.pushReplacement(context, MaterialPageRoute(
        builder: (_) => HomeScreen(),
      ));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('TTBoost Login')),
      body: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _usernameController,
              decoration: InputDecoration(
                labelText: 'TikTok Username (без @)',
                hintText: 'streamer123',
              ),
            ),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: InputDecoration(labelText: 'Пароль'),
            ),
            TextField(
              controller: _licenseController,
              decoration: InputDecoration(
                labelText: 'Лицензионный ключ',
                hintText: 'TTB-XXXX-XXXX-XXXX',
              ),
            ),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: _handleRedeem,
              child: Text('Активировать лицензию'),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## 🔧 Troubleshooting

### Проблема: "invalid token"
**Причина:** Токен истёк (TTL = 24 часа)  
**Решение:** Перелогиниться через `/v2/auth/login`

### Проблема: "license already bound to another user"
**Причина:** Лицензия уже активирована другим пользователем  
**Решение:** Использовать тот же username или выдать новую лицензию

### Проблема: WebSocket disconnect
**Причина:** Токен неверный или TikTok username не задан  
**Решение:** Проверить токен и убедиться что username = TikTok ник

### Проблема: UserNotFoundError в логах
**Причина:** Стрим оффлайн или username неверный  
**Решение:** Дождаться начала стрима или проверить ник

---

## 📊 Rate Limits

| Endpoint | Limit |
|----------|-------|
| /v2/auth/* | 10 req/min |
| /v2/sounds/upload | 5 req/min |
| /v2/triggers/* | 20 req/min |
| WebSocket | 1 connection/user |

---

## 🚀 Next Steps

1. ✅ Обновить `ApiService` в Flutter под v2
2. ✅ Добавить экран ввода лицензионного ключа
3. ✅ Заменить старый WebSocket на `wss://api.ttboost.pro/v2/ws?token=...`
4. ✅ Тестировать на реальном TikTok стриме
5. ✅ Добавить UI для триггеров и настроек

---

**API Version:** v2.0  
**Last Updated:** 18.11.2025  
**Support:** https://github.com/MrJinPro/backend-TTBoost-v2
