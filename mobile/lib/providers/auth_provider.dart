import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  final ApiService apiService;
  final storage = const FlutterSecureStorage();
  
  String? _username;
  String? _tiktokUsername;
  String? _email;
  String? _avatarUrl;
  String? _plan;
  String? _tariffName;
  String? _subscriptionExpiresAt;
  int? _maxTikTokAccounts;
  
  bool get isAuthenticated => apiService.token != null;
  String? get jwtToken => apiService.token;
  String? get username => _username;
  String? get tiktokUsername => _tiktokUsername;
  String? get email => _email;
  String? get avatarUrl => _avatarUrl;
  String? get plan => _plan;
  String? get tariffName => _tariffName;
  String? get subscriptionExpiresAt => _subscriptionExpiresAt;
  int? get maxTikTokAccounts => _maxTikTokAccounts;
  
  Map<String, dynamic> get userInfo => {
    'username': _username,
    'tiktokUsername': _tiktokUsername,
    'email': _email,
    'avatarUrl': _avatarUrl,
    'plan': _plan,
    'tariffName': _tariffName,
    'subscriptionExpiresAt': _subscriptionExpiresAt,
    'maxTikTokAccounts': _maxTikTokAccounts,
  };
  
  AuthProvider({required this.apiService});
  
  Future<void> initialize() async {
    final token = await storage.read(key: 'jwt_token');
    if (token != null && token.isNotEmpty) {
      apiService.setToken(token);
      await _loadProfile();
    }
  }
  
  Future<String?> login({
    required String username,
    required String password,
  }) async {
    final result = await apiService.login(
      username: username,
      password: password,
    );
    if (result == null) return apiService.lastError ?? 'Неверные учетные данные';
    await storage.write(key: 'jwt_token', value: result.token);
    _username = result.username;
    await _loadProfile();
    notifyListeners();
    return null;
  }

  Future<String?> register({
    required String username,
    required String password,
  }) async {
    final result = await apiService.register(
      username: username,
      password: password,
    );
    if (result == null) return apiService.lastError ?? 'Ошибка регистрации';
    await storage.write(key: 'jwt_token', value: result.token);
    _username = result.username;
    await _loadProfile();
    notifyListeners();
    return null;
  }
  
  Future<void> _loadProfile() async {
    final profile = await apiService.getProfile();
    if (profile != null) {
      _username = profile['username'] as String?;
      _tiktokUsername = profile['tiktok_username'] as String?;
      _email = profile['email'] as String?;
      _avatarUrl = profile['avatar_url'] as String?;
      _plan = profile['plan'] as String?;
      _tariffName = profile['tariff_name'] as String?;
      _subscriptionExpiresAt = profile['license_expires_at'] as String?;
      _maxTikTokAccounts = profile['max_tiktok_accounts'] as int?;
      notifyListeners();
    }
  }

  // Публичный метод для обновления профиля
  Future<void> refreshUserInfo() async {
    await _loadProfile();
  }
  
  Future<void> logout() async {
    await storage.delete(key: 'jwt_token');
    apiService.setToken('');
    _username = null;
    _tiktokUsername = null;
    _email = null;
    _avatarUrl = null;
    _plan = null;
    _tariffName = null;
    _subscriptionExpiresAt = null;
    _maxTikTokAccounts = null;
    notifyListeners();
  }
}
