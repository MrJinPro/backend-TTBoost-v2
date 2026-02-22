import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';
import '../services/api_service.dart';
import '../utils/constants.dart';

class AuthProvider extends ChangeNotifier {
  final ApiService apiService;
  final storage = const FlutterSecureStorage();

  static const String _kJwtKey = 'jwt_token';
  static const String _kJwtKeyFallback = 'jwt_token_fallback';

  StreamSubscription<dynamic>? _supabaseAuthSub;
  
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

  @override
  void dispose() {
    try {
      _supabaseAuthSub?.cancel();
    } catch (_) {}
    _supabaseAuthSub = null;
    super.dispose();
  }

  Future<void> _writeJwtToken(String token) async {
    final t = token.trim();
    if (t.isEmpty) return;
    try {
      await storage.write(key: _kJwtKey, value: t);
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_kJwtKeyFallback, t);
      } catch (_) {}
      return;
    } catch (_) {
      // Fallback for devices/environments where secure storage is unavailable.
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kJwtKeyFallback, t);
    } catch (_) {}
  }

  Future<String?> _readJwtToken() async {
    try {
      final t = await storage.read(key: _kJwtKey);
      if (t != null && t.trim().isNotEmpty) return t.trim();
    } catch (_) {
      // ignore
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      final t = prefs.getString(_kJwtKeyFallback);
      if (t != null && t.trim().isNotEmpty) return t.trim();
    } catch (_) {
      // ignore
    }
    return null;
  }

  Future<void> _deleteJwtToken() async {
    try {
      await storage.delete(key: _kJwtKey);
    } catch (_) {}
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kJwtKeyFallback);
    } catch (_) {}
  }

  void _ensureSupabaseAuthListener() {
    if (!supabaseEnabled) return;
    if (_supabaseAuthSub != null) return;
    final sb = _sb;
    if (sb == null) return;

    // Keep backend JWT in sync with Supabase session.
    _supabaseAuthSub = sb.auth.onAuthStateChange.listen((data) async {
      try {
        final session = (data as dynamic).session as Session?;
        final event = (data as dynamic).event;

        if (event == AuthChangeEvent.signedOut) {
          await _deleteJwtToken();
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
          return;
        }

        final accessToken = session?.accessToken;
        if (accessToken != null && accessToken.isNotEmpty) {
          final jwt = await apiService.exchangeSupabaseToken(supabaseAccessToken: accessToken);
          if (jwt != null && jwt.isNotEmpty) {
            await _writeJwtToken(jwt);
            await _loadProfile();
            notifyListeners();
          }
        }
      } catch (_) {
        // Listener should never crash app.
      }
    });
  }
  
  Future<void> initialize() async {
    _ensureSupabaseAuthListener();

    // Prefer Supabase session if configured.
    if (supabaseEnabled) {
      try {
        // Best-effort: refresh session to avoid expired access tokens.
        try {
          await _sb?.auth.refreshSession();
        } catch (_) {}

        final session = _sb?.auth.currentSession;
        final accessToken = session?.accessToken;
        if (accessToken != null && accessToken.isNotEmpty) {
          final jwt = await apiService.exchangeSupabaseToken(supabaseAccessToken: accessToken);
          if (jwt != null && jwt.isNotEmpty) {
            await _writeJwtToken(jwt);
            await _loadProfile();
            notifyListeners();
            return;
          }
        }
      } catch (_) {
        // ignore supabase restore issues
      }
    }

    // Fallback to legacy backend JWT.
    final token = await _readJwtToken();
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
        await _writeJwtToken(jwt);
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
    await _writeJwtToken(result.token);
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
    await _deleteJwtToken();
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
