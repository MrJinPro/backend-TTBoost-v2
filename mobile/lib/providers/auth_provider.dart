import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/api_service.dart';
import '../utils/constants.dart';

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

  bool get supabaseEnabled => kSupabaseUrl.isNotEmpty && kSupabaseAnonKey.isNotEmpty;

  SupabaseClient? get _sb => supabaseEnabled ? Supabase.instance.client : null;
  
  Future<void> initialize() async {
    // Prefer Supabase session if configured.
    if (supabaseEnabled) {
      final session = _sb?.auth.currentSession;
      final accessToken = session?.accessToken;
      if (accessToken != null && accessToken.isNotEmpty) {
        final jwt = await apiService.exchangeSupabaseToken(supabaseAccessToken: accessToken);
        if (jwt != null && jwt.isNotEmpty) {
          await storage.write(key: 'jwt_token', value: jwt);
          await _loadProfile();
          notifyListeners();
          return;
        }
      }
    }

    // Fallback to legacy backend JWT.
    final token = await storage.read(key: 'jwt_token');
    if (token != null && token.isNotEmpty) {
      apiService.setToken(token);
      await _loadProfile();
      notifyListeners();
    }
  }
  
  Future<String?> login({
    required String username,
    required String password,
  }) async {
    final ident = username.trim();

    // If user enters email and Supabase is enabled, authenticate via Supabase.
    if (supabaseEnabled && ident.contains('@')) {
      try {
        final res = await _sb!.auth.signInWithPassword(email: ident, password: password);
        final session = res.session;
        final user = res.user;
        if (session == null || session.accessToken.isEmpty) {
          return 'Не удалось выполнить вход. Подтвердите email и попробуйте ещё раз.';
        }

        // Best-effort: enforce email confirmation client-side.
        final confirmedAt = user?.emailConfirmedAt;
        if (confirmedAt == null || confirmedAt.trim().isEmpty) {
          await _sb!.auth.signOut();
          return 'Email не подтверждён. Откройте письмо от Supabase и подтвердите адрес.';
        }

        final jwt = await apiService.exchangeSupabaseToken(supabaseAccessToken: session.accessToken);
        if (jwt == null) return apiService.lastError ?? 'Не удалось войти через Supabase';
        await storage.write(key: 'jwt_token', value: jwt);
        await _loadProfile();
        notifyListeners();
        return null;
      } on AuthException catch (e) {
        return e.message;
      } catch (e) {
        return 'Ошибка входа через Supabase';
      }
    }

    // Legacy login (username OR email via backend).
    final result = await apiService.login(
      username: ident,
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
    final email = username.trim();
    if (!email.contains('@')) {
      return 'Для регистрации нужен email';
    }
    if (!supabaseEnabled) {
      return 'Supabase не настроен в приложении';
    }
    try {
      await _sb!.auth.signUp(email: email, password: password);
      // Обычно с включённым Confirm Email сессии нет до подтверждения.
      return null;
    } on AuthException catch (e) {
      return e.message;
    } catch (e) {
      return 'Ошибка регистрации через Supabase';
    }
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
    if (supabaseEnabled) {
      try {
        await _sb?.auth.signOut();
      } catch (_) {
        // ignore
      }
    }
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
