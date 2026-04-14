import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/constants.dart';

class SpotifyService {
  static const _storage = FlutterSecureStorage();
  static const _appAuth = FlutterAppAuth();

  static const _kAccessTokenKey = 'spotify_access_token';
  static const _kRefreshTokenKey = 'spotify_refresh_token';
  static const _kExpiryKey = 'spotify_access_token_expiry';
  static const _kJwtKey = 'jwt_token';
  static const _kJwtKeyFallback = 'jwt_token_fallback';

  static const _authEndpoint = 'https://accounts.spotify.com/authorize';
  static const _tokenEndpoint = 'https://accounts.spotify.com/api/token';
  static const _apiBase = 'https://api.spotify.com/v1';

  static const List<String> _scopes = <String>[
    'user-read-playback-state',
    'user-read-currently-playing',
    'user-modify-playback-state',
  ];

  String _clientId = kSpotifyClientId.trim();
  String _redirectUri = kSpotifyRedirectUri.trim();

  bool get isConfigured => _clientId.isNotEmpty && _redirectUri.isNotEmpty;

  Uri _backendUri(String path) {
    final normalizedBase = kApiBaseUrl.endsWith('/')
        ? kApiBaseUrl.substring(0, kApiBaseUrl.length - 1)
        : kApiBaseUrl;
    return Uri.parse('$normalizedBase$path');
  }

  Future<String?> _readJwtToken() async {
    try {
      final token = await _storage.read(key: _kJwtKey);
      if (token != null && token.trim().isNotEmpty) {
        return token.trim();
      }
    } catch (_) {}

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString(_kJwtKeyFallback);
      if (token != null && token.trim().isNotEmpty) {
        return token.trim();
      }
    } catch (_) {}

    return null;
  }

  Future<Map<String, String>> _backendHeaders() async {
    final jwt = await _readJwtToken();
    if (jwt == null || jwt.isEmpty) {
      throw StateError('Нужна авторизация в приложении перед подключением Spotify.');
    }

    return <String, String>{
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $jwt',
      'X-Client-Platform': 'mobile',
    };
  }

  Future<void> loadConfig() async {
    if (_clientId.isNotEmpty && _redirectUri.isNotEmpty) {
      return;
    }

    final resp = await http.get(
      _backendUri('/v2/spotify/config'),
      headers: await _backendHeaders(),
    );

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Не удалось загрузить Spotify config: ${resp.statusCode} ${resp.body}');
    }

    final decoded = jsonDecode(resp.body);
    if (decoded is! Map<String, dynamic>) {
      throw StateError('Некорректный ответ Spotify config от сервера.');
    }

    final enabled = decoded['enabled'] == true;
    if (!enabled) {
      _clientId = '';
      _redirectUri = '';
      return;
    }

    _clientId = (decoded['client_id']?.toString() ?? '').trim();
    _redirectUri = (decoded['redirect_uri']?.toString() ?? '').trim();
  }

  DateTime? _expiryFromNowSeconds(dynamic rawSeconds) {
    if (rawSeconds is int) {
      return DateTime.now().toUtc().add(Duration(seconds: rawSeconds));
    }
    if (rawSeconds is num) {
      return DateTime.now().toUtc().add(Duration(seconds: rawSeconds.toInt()));
    }
    return null;
  }

  Future<String> _exchangeCodeWithBackend({
    required String code,
    required String redirectUri,
    String? codeVerifier,
  }) async {
    final resp = await http.post(
      _backendUri('/v2/spotify/exchange'),
      headers: await _backendHeaders(),
      body: jsonEncode(<String, dynamic>{
        'code': code,
        'redirect_uri': redirectUri,
        if (codeVerifier != null && codeVerifier.trim().isNotEmpty)
          'code_verifier': codeVerifier.trim(),
      }),
    );

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify exchange failed: ${resp.statusCode} ${resp.body}');
    }

    final decoded = jsonDecode(resp.body);
    if (decoded is! Map<String, dynamic>) {
      throw StateError('Некорректный ответ Spotify exchange от сервера.');
    }

    final accessToken = (decoded['access_token']?.toString() ?? '').trim();
    if (accessToken.isEmpty) {
      throw StateError('Сервер не вернул Spotify access token.');
    }

    await _storage.write(key: _kAccessTokenKey, value: accessToken);

    final refreshToken = (decoded['refresh_token']?.toString() ?? '').trim();
    if (refreshToken.isNotEmpty) {
      await _storage.write(key: _kRefreshTokenKey, value: refreshToken);
    }

    final expiry = _expiryFromNowSeconds(decoded['expires_in']);
    if (expiry != null) {
      await _storage.write(key: _kExpiryKey, value: expiry.toIso8601String());
    }

    return accessToken;
  }

  Future<bool> hasRefreshToken() async {
    final rt = await _storage.read(key: _kRefreshTokenKey);
    return rt != null && rt.trim().isNotEmpty;
  }

  Future<void> disconnect() async {
    await _storage.delete(key: _kAccessTokenKey);
    await _storage.delete(key: _kRefreshTokenKey);
    await _storage.delete(key: _kExpiryKey);
  }

  Future<void> connect() async {
    if (kIsWeb) {
      throw StateError('Spotify auth is not supported on Web in this app.');
    }
    await loadConfig();
    if (!isConfigured) {
      throw StateError('Spotify не настроен на сервере. Укажите SPOTIFY_CLIENT_ID и SPOTIFY_CLIENT_SECRET в backend .env.');
    }

    final req = AuthorizationRequest(
      _clientId,
      _redirectUri,
      serviceConfiguration: const AuthorizationServiceConfiguration(
        authorizationEndpoint: _authEndpoint,
        tokenEndpoint: _tokenEndpoint,
      ),
      scopes: _scopes,
      preferEphemeralSession: true,
    );

    final res = await _appAuth.authorize(req);
    final code = (res?.authorizationCode ?? '').trim();
    if (res == null || code.isEmpty) {
      throw StateError('Spotify auth canceled or failed.');
    }

    await _exchangeCodeWithBackend(
      code: code,
      redirectUri: _redirectUri,
      codeVerifier: res.codeVerifier,
    );
  }

  Future<String> _getValidAccessToken() async {
    final token = await _storage.read(key: _kAccessTokenKey);
    final expiryRaw = await _storage.read(key: _kExpiryKey);

    if (token != null && token.trim().isNotEmpty && expiryRaw != null) {
      final expiry = DateTime.tryParse(expiryRaw);
      if (expiry != null) {
        final now = DateTime.now().toUtc();
        if (expiry.isAfter(now.add(const Duration(seconds: 30)))) {
          return token;
        }
      }
    }

    return await _refreshAccessToken();
  }

  Future<String> _refreshAccessToken() async {
    final rt = await _storage.read(key: _kRefreshTokenKey);
    if (rt == null || rt.trim().isEmpty) {
      throw StateError('Нет refresh token Spotify. Подключите Spotify заново.');
    }

    final resp = await http.post(
      _backendUri('/v2/spotify/refresh'),
      headers: await _backendHeaders(),
      body: jsonEncode(<String, dynamic>{
        'refresh_token': rt,
      }),
    );

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify token refresh failed: ${resp.statusCode} ${resp.body}');
    }

    final decoded = jsonDecode(resp.body);
    if (decoded is! Map<String, dynamic>) {
      throw StateError('Некорректный ответ Spotify refresh от сервера.');
    }

    final accessToken = (decoded['access_token']?.toString() ?? '').trim();
    if (accessToken.isEmpty) {
      throw StateError('Сервер не вернул новый Spotify access token.');
    }
    await _storage.write(key: _kAccessTokenKey, value: accessToken);

    final refreshToken = (decoded['refresh_token']?.toString() ?? '').trim();
    if (refreshToken.isNotEmpty) {
      await _storage.write(key: _kRefreshTokenKey, value: refreshToken);
    }

    final expiry = _expiryFromNowSeconds(decoded['expires_in']);
    if (expiry != null) {
      await _storage.write(key: _kExpiryKey, value: expiry.toIso8601String());
    }

    return accessToken;
  }

  Future<http.Response> _authedRequest(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  }) async {
    final accessToken = await _getValidAccessToken();
    final mergedHeaders = <String, String>{
      'Authorization': 'Bearer $accessToken',
      if (headers != null) ...headers,
    };

    http.Response resp;
    switch (method.toUpperCase()) {
      case 'GET':
        resp = await http.get(uri, headers: mergedHeaders);
        break;
      case 'PUT':
        resp = await http.put(uri, headers: mergedHeaders, body: body);
        break;
      case 'POST':
        resp = await http.post(uri, headers: mergedHeaders, body: body);
        break;
      default:
        throw ArgumentError('Unsupported method: $method');
    }

    // One retry on 401.
    if (resp.statusCode == 401) {
      await _refreshAccessToken();
      final retryHeaders = <String, String>{
        'Authorization': 'Bearer ${await _storage.read(key: _kAccessTokenKey)}',
        if (headers != null) ...headers,
      };
      switch (method.toUpperCase()) {
        case 'GET':
          resp = await http.get(uri, headers: retryHeaders);
          break;
        case 'PUT':
          resp = await http.put(uri, headers: retryHeaders, body: body);
          break;
        case 'POST':
          resp = await http.post(uri, headers: retryHeaders, body: body);
          break;
      }
    }

    return resp;
  }

  Future<Map<String, dynamic>?> getCurrentPlayback() async {
    final uri = Uri.parse('$_apiBase/me/player');
    final resp = await _authedRequest('GET', uri);

    if (resp.statusCode == 204) return null;

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify playback error: ${resp.statusCode} ${resp.body}');
    }

    final decoded = jsonDecode(resp.body);
    if (decoded is Map<String, dynamic>) return decoded;
    return null;
  }

  Future<List<Map<String, dynamic>>> getDevices() async {
    final uri = Uri.parse('$_apiBase/me/player/devices');
    final resp = await _authedRequest('GET', uri);

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify devices error: ${resp.statusCode} ${resp.body}');
    }

    final decoded = jsonDecode(resp.body);
    if (decoded is! Map<String, dynamic>) return const [];
    final devices = decoded['devices'];
    if (devices is! List) return const [];
    return devices.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Never _throwPlayerCommandError(String actionLabel, http.Response resp) {
    String? reason;
    String? message;
    try {
      final decoded = jsonDecode(resp.body);
      if (decoded is Map<String, dynamic>) {
        final err = decoded['error'];
        if (err is Map<String, dynamic>) {
          reason = err['reason']?.toString();
          message = err['message']?.toString();
        }
      }
    } catch (_) {}

    final normalizedReason = (reason ?? '').trim().toUpperCase();
    final normalizedMessage = (message ?? '').trim().toLowerCase();

    if (normalizedReason == 'NO_ACTIVE_DEVICE' ||
        normalizedMessage.contains('no active device') ||
        resp.statusCode == 404) {
      throw StateError(
        'Spotify не видит активное устройство. Откройте Spotify на телефоне, начните воспроизведение любого трека и вернитесь в TTBoost.',
      );
    }

    if (resp.statusCode == 403 &&
        (normalizedMessage.contains('premium') || normalizedReason.contains('PREMIUM'))) {
      throw StateError('Управление воспроизведением Spotify доступно только для Premium-аккаунта.');
    }

    throw StateError('Spotify $actionLabel failed: ${resp.statusCode} ${resp.body}');
  }

  Future<void> play() async {
    final uri = Uri.parse('$_apiBase/me/player/play');
    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      _throwPlayerCommandError('play', resp);
    }
  }

  Future<void> pause() async {
    final uri = Uri.parse('$_apiBase/me/player/pause');
    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      _throwPlayerCommandError('pause', resp);
    }
  }

  Future<void> next() async {
    final uri = Uri.parse('$_apiBase/me/player/next');
    final resp = await _authedRequest('POST', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      _throwPlayerCommandError('next', resp);
    }
  }

  Future<void> previous() async {
    final uri = Uri.parse('$_apiBase/me/player/previous');
    final resp = await _authedRequest('POST', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      _throwPlayerCommandError('previous', resp);
    }
  }

  Future<void> setVolumePercent(int percent) async {
    final p = percent.clamp(0, 100);
    final uri = Uri.parse('$_apiBase/me/player/volume').replace(queryParameters: {
      'volume_percent': p.toString(),
    });

    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      _throwPlayerCommandError('volume', resp);
    }
  }
}
