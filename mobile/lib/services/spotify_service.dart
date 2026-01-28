import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../utils/constants.dart';

class SpotifyService {
  static const _storage = FlutterSecureStorage();
  static const _appAuth = FlutterAppAuth();

  static const _kAccessTokenKey = 'spotify_access_token';
  static const _kRefreshTokenKey = 'spotify_refresh_token';
  static const _kExpiryKey = 'spotify_access_token_expiry';

  static const _authEndpoint = 'https://accounts.spotify.com/authorize';
  static const _tokenEndpoint = 'https://accounts.spotify.com/api/token';
  static const _apiBase = 'https://api.spotify.com/v1';

  static const List<String> _scopes = <String>[
    'user-read-playback-state',
    'user-read-currently-playing',
    'user-modify-playback-state',
  ];

  bool get isConfigured => kSpotifyClientId.trim().isNotEmpty;

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
    if (!isConfigured) {
      throw StateError('SPOTIFY_CLIENT_ID не задан.');
    }

    final req = AuthorizationTokenRequest(
      kSpotifyClientId,
      kSpotifyRedirectUri,
      serviceConfiguration: const AuthorizationServiceConfiguration(
        authorizationEndpoint: _authEndpoint,
        tokenEndpoint: _tokenEndpoint,
      ),
      scopes: _scopes,
      preferEphemeralSession: true,
    );

    final res = await _appAuth.authorizeAndExchangeCode(req);
    if (res == null || (res.accessToken ?? '').trim().isEmpty) {
      throw StateError('Spotify auth canceled or failed.');
    }

    await _storage.write(key: _kAccessTokenKey, value: res.accessToken);

    if ((res.refreshToken ?? '').trim().isNotEmpty) {
      await _storage.write(key: _kRefreshTokenKey, value: res.refreshToken);
    }

    final expiry = res.accessTokenExpirationDateTime;
    if (expiry != null) {
      await _storage.write(key: _kExpiryKey, value: expiry.toIso8601String());
    }
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

    final res = await _appAuth.token(TokenRequest(
      kSpotifyClientId,
      kSpotifyRedirectUri,
      refreshToken: rt,
      serviceConfiguration: const AuthorizationServiceConfiguration(
        authorizationEndpoint: _authEndpoint,
        tokenEndpoint: _tokenEndpoint,
      ),
      scopes: _scopes,
    ));

    if (res == null || (res.accessToken ?? '').trim().isEmpty) {
      throw StateError('Spotify token refresh failed.');
    }

    await _storage.write(key: _kAccessTokenKey, value: res.accessToken);

    if ((res.refreshToken ?? '').trim().isNotEmpty) {
      await _storage.write(key: _kRefreshTokenKey, value: res.refreshToken);
    }

    final expiry = res.accessTokenExpirationDateTime;
    if (expiry != null) {
      await _storage.write(key: _kExpiryKey, value: expiry.toIso8601String());
    }

    return res.accessToken!;
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

  Future<void> play() async {
    final uri = Uri.parse('$_apiBase/me/player/play');
    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify play failed: ${resp.statusCode} ${resp.body}');
    }
  }

  Future<void> pause() async {
    final uri = Uri.parse('$_apiBase/me/player/pause');
    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify pause failed: ${resp.statusCode} ${resp.body}');
    }
  }

  Future<void> next() async {
    final uri = Uri.parse('$_apiBase/me/player/next');
    final resp = await _authedRequest('POST', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify next failed: ${resp.statusCode} ${resp.body}');
    }
  }

  Future<void> previous() async {
    final uri = Uri.parse('$_apiBase/me/player/previous');
    final resp = await _authedRequest('POST', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify previous failed: ${resp.statusCode} ${resp.body}');
    }
  }

  Future<void> setVolumePercent(int percent) async {
    final p = percent.clamp(0, 100);
    final uri = Uri.parse('$_apiBase/me/player/volume').replace(queryParameters: {
      'volume_percent': p.toString(),
    });

    final resp = await _authedRequest('PUT', uri);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('Spotify volume failed: ${resp.statusCode} ${resp.body}');
    }
  }
}
