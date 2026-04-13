import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

class ApiService {
  final String baseUrl;
  String? _jwtToken;
  String? lastError;
  String? lastTtsEngineUsed;
  String? lastTtsVoiceIdUsed;
  bool lastTtsFallbackUsed = false;

  ApiService({String baseUrl = kApiBaseUrl})
      : baseUrl = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;

  void _setLastError(String? message) {
    lastError = message;
  }

  String _bodyUtf8(http.Response resp) {
    try {
      return utf8.decode(resp.bodyBytes);
    } catch (_) {
      // Fallback: package:http will decode with latin1 by default.
      return resp.body;
    }
  }

  dynamic _jsonDecodeResponse(http.Response resp) {
    return jsonDecode(_bodyUtf8(resp));
  }

  String _extractErrorMessage(http.Response resp) {
    try {
      final decoded = _jsonDecodeResponse(resp);
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String && detail.trim().isNotEmpty) return detail;
        final message = decoded['message'];
        if (message is String && message.trim().isNotEmpty) return message;
        final error = decoded['error'];
        if (error is String && error.trim().isNotEmpty) return error;
      }
    } catch (_) {
      // ignore parse errors
    }
    return 'Ошибка сервера (код ${resp.statusCode})';
  }

  void setToken(String token) {
    final t = token.trim();
    _jwtToken = t.isEmpty ? null : t;
  }

  String? get token => _jwtToken;

  Map<String, String> _authHeaders() {
    final headers = {
      'Content-Type': 'application/json',
      // backend использует это для тарифных ограничений
      'X-Client-Platform': 'mobile',
    };
    final t = _jwtToken;
    if (t != null && t.isNotEmpty) {
      headers['Authorization'] = 'Bearer $t';
    }
    return headers;
  }

  Map<String, String> _authHeadersMultipart() {
    final headers = {
      // backend использует это для тарифных ограничений
      'X-Client-Platform': 'mobile',
    };
    final t = _jwtToken;
    if (t != null && t.isNotEmpty) {
      headers['Authorization'] = 'Bearer $t';
    }
    return headers;
  }

  Future<({String token, String userId, String username})?> login({
    required String username,
    required String password,
  }) async {
    try {
      _setLastError(null);
      // v2 API: логин/пароль
      final uri = Uri.parse('$baseUrl/v2/auth/login');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'password': password,
        }),
      );

      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final t = m['access_token'] as String? ?? '';
        _jwtToken = t;
        final profile = await getProfile();
        if (profile != null) {
          return (token: t, userId: profile['id'].toString(), username: profile['username'] as String);
        }
      } else if (resp.statusCode == 401 || resp.statusCode == 403) {
        _setLastError('Неверные учетные данные');
      } else {
        _setLastError(_extractErrorMessage(resp));
      }
      return null;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('login error: $e');
      return null;
    }
  }

  Future<String?> exchangeSupabaseToken({required String supabaseAccessToken}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/auth/supabase/exchange');
      final resp = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $supabaseAccessToken',
        },
        body: jsonEncode({}),
      );
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final t = (m['access_token'] as String? ?? '').trim();
        if (t.isEmpty) {
          _setLastError('Пустой токен от сервера');
          return null;
        }
        _jwtToken = t;
        return t;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('exchangeSupabaseToken error: $e');
      return null;
    }
  }

  Future<Map<String, dynamic>?> getProfile() async {
    try {
      _setLastError(null);
      // v2 профиль пользователя
      final uriV2 = Uri.parse('$baseUrl/v2/auth/me');
      final respV2 = await http.get(uriV2, headers: _authHeaders());
      if (respV2.statusCode == 200) {
        return _jsonDecodeResponse(respV2) as Map<String, dynamic>;
      }

      // fallback на legacy (на случай старого бэкенда)
      final uriLegacy = Uri.parse('$baseUrl/auth/me');
      final respLegacy = await http.get(uriLegacy, headers: _authHeaders());
      if (respLegacy.statusCode == 200) {
        return _jsonDecodeResponse(respLegacy) as Map<String, dynamic>;
      }

      return null;
    } catch (e) {
      print('getProfile error: $e');
      return null;
    }
  }

  Future<int> getUnreadNotificationsCount() async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/notifications/unread_count');
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final v = m['unread_count'];
        if (v is int) return v;
        if (v is num) return v.toInt();
        return 0;
      }
      _setLastError(_extractErrorMessage(resp));
      return 0;
    } catch (e) {
      _setLastError('Не удалось загрузить уведомления');
      print('getUnreadNotificationsCount error: $e');
      return 0;
    }
  }

  Future<List<Map<String, dynamic>>> listNotifications({int limit = 50, int offset = 0}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/notifications')
          .replace(queryParameters: {'limit': '$limit', 'offset': '$offset'});
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final items = m['items'] as List<dynamic>? ?? [];
        return items.cast<Map<String, dynamic>>();
      }
      _setLastError(_extractErrorMessage(resp));
      return [];
    } catch (e) {
      _setLastError('Не удалось загрузить уведомления');
      print('listNotifications error: $e');
      return [];
    }
  }

  Future<bool> markNotificationRead({required String id}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/notifications/$id/read');
      final resp = await http.post(uri, headers: _authHeaders(), body: jsonEncode({}));
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось отметить уведомление');
      print('markNotificationRead error: $e');
      return false;
    }
  }

  Future<bool> markAllNotificationsRead() async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/notifications/read_all');
      final resp = await http.post(uri, headers: _authHeaders(), body: jsonEncode({}));
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось отметить уведомления');
      print('markAllNotificationsRead error: $e');
      return false;
    }
  }

  Future<bool> updateProfile({String? email}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/profile');
      final resp = await http.patch(
        uri,
        headers: _authHeaders(),
        body: jsonEncode({
          'email': email,
        }),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('updateProfile error: $e');
      return false;
    }
  }

  Future<bool> requestPasswordReset({required String loginOrEmail}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/auth/password/reset/request');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'login_or_email': loginOrEmail}),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('requestPasswordReset error: $e');
      return false;
    }
  }

  Future<bool> confirmPasswordReset({
    required String loginOrEmail,
    required String code,
    required String newPassword,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/auth/password/reset/confirm');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'login_or_email': loginOrEmail,
          'code': code,
          'new_password': newPassword,
        }),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('confirmPasswordReset error: $e');
      return false;
    }
  }

  Future<bool> deleteAccount({required String confirm, String? password}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/profile/delete');
      final body = <String, dynamic>{
        'confirm': confirm,
        if (password != null && password.trim().isNotEmpty) 'password': password,
      };
      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось удалить аккаунт');
      print('deleteAccount error: $e');
      return false;
    }
  }

  Future<String?> uploadAvatar({
    String? filePath,
    Uint8List? bytes,
    required String filename,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/profile/avatar');
      final req = http.MultipartRequest('POST', uri);
      req.headers.addAll(_authHeadersMultipart());

      if (filePath != null && filePath.isNotEmpty) {
        req.files.add(await http.MultipartFile.fromPath('file', filePath, filename: filename));
      } else if (bytes != null) {
        req.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
      } else {
        _setLastError('Файл не выбран');
        return null;
      }

      final streamed = await req.send();
      final resp = await http.Response.fromStream(streamed);

      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final url = m['avatar_url']?.toString();
        return (url != null && url.isNotEmpty) ? url : null;
      }

      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('uploadAvatar error: $e');
      return null;
    }
  }

  Future<Map<String, dynamic>?> getTikTokProfile({String? username}) async {
    try {
      _setLastError(null);
      final base = Uri.parse('$baseUrl/v2/tiktok/profile');
      final u = (username ?? '').trim();
      final uri = u.isNotEmpty ? base.replace(queryParameters: {'username': u}) : base;
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        return _jsonDecodeResponse(resp) as Map<String, dynamic>;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('getTikTokProfile error: $e');
      return null;
    }
  }

  Future<bool> updateCredentials({
    required String currentPassword,
    String? newUsername,
    String? newPassword,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/profile/credentials');
      final body = <String, dynamic>{
        'current_password': currentPassword,
      };
      if (newUsername != null) body['new_username'] = newUsername;
      if (newPassword != null) body['new_password'] = newPassword;

      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('updateCredentials error: $e');
      return false;
    }
  }

  Future<bool> verifySubscription({
    required String platform,
    required String productId,
    required String verificationData,
    String? packageName,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/billing/verify');
      final body = <String, dynamic>{
        'platform': platform,
        'product_id': productId,
        'verification_data': verificationData,
      };
      if (packageName != null && packageName.trim().isNotEmpty) {
        body['package_name'] = packageName.trim();
      }
      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      if (resp.statusCode == 200) return true;
      _setLastError(_extractErrorMessage(resp));
      return false;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('verifySubscription error: $e');
      return false;
    }
  }

  Future<bool> updateSettings({
    String? tiktokUsername,
    String? voiceId,
    // compat с текущими экранами
    String? selectedVoiceId,
    bool? ttsEnabled,
    bool? giftSoundsEnabled,
    bool? silenceEnabled,
    bool? autoConnectLive,
    double? ttsVolume,
    double? giftVolume,
    String? chatTtsMode,
    String? chatTtsPrefixes,
    int? chatTtsMinDiamonds,
  }) async {
    try {
      final body = <String, dynamic>{};

      if (tiktokUsername != null) body['tiktok_username'] = tiktokUsername;
      final effectiveVoiceId = selectedVoiceId ?? voiceId;
      if (effectiveVoiceId != null) body['voice_id'] = effectiveVoiceId;

      if (ttsEnabled != null) body['tts_enabled'] = ttsEnabled;
      if (giftSoundsEnabled != null) body['gift_sounds_enabled'] = giftSoundsEnabled;
      if (silenceEnabled != null) body['silence_enabled'] = silenceEnabled;
      if (autoConnectLive != null) body['auto_connect_live'] = autoConnectLive;
      if (ttsVolume != null) body['tts_volume'] = ttsVolume.round();
      if (giftVolume != null) body['gifts_volume'] = giftVolume.round();

      if (chatTtsMode != null) body['chat_tts_mode'] = chatTtsMode;
      if (chatTtsPrefixes != null) body['chat_tts_prefixes'] = chatTtsPrefixes;
      if (chatTtsMinDiamonds != null) body['chat_tts_min_diamonds'] = chatTtsMinDiamonds;

      // v2 settings
      final uriV2 = Uri.parse('$baseUrl/v2/settings/update');
      final respV2 = await http.post(
        uriV2,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      if (respV2.statusCode == 200) return true;

      // legacy fallback (если вдруг используется старый бэкенд)
      final uriLegacy = Uri.parse('$baseUrl/settings/update');
      final respLegacy = await http.post(
        uriLegacy,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      return respLegacy.statusCode == 200;
    } catch (e) {
      print('updateSettings error: $e');
      return false;
    }
  }

  Future<Map<String, dynamic>?> getSettings() async {
    try {
      final uriV2 = Uri.parse('$baseUrl/v2/settings/get');
      final respV2 = await http.get(uriV2, headers: _authHeaders());
      if (respV2.statusCode == 200) {
        return _jsonDecodeResponse(respV2) as Map<String, dynamic>;
      }
      return null;
    } catch (e) {
      print('getSettings error: $e');
      return null;
    }
  }

  String _normalizeEventType(String raw) {
    final v = raw.trim().toLowerCase();
    if (v == 'comment') return 'chat';
    return v;
  }

  String _normalizeTextTemplate(String raw) {
    // в бэкенде используются {user} и {message}
    return raw.replaceAll('{username}', '{user}');
  }

  Future<List<Map<String, dynamic>>> listTriggers() async {
    try {
      // v2
      final uriV2 = Uri.parse('$baseUrl/v2/triggers/list');
      final respV2 = await http.get(uriV2, headers: _authHeaders());
      if (respV2.statusCode == 200) {
        final map = _jsonDecodeResponse(respV2) as Map<String, dynamic>;
        final triggers = map['triggers'] as List<dynamic>? ?? [];
        return triggers.cast<Map<String, dynamic>>();
      }

      // алиас (некоторые клиенты ожидают /v2/triggers)
      final uriV2Alias = Uri.parse('$baseUrl/v2/triggers');
      final respV2Alias = await http.get(uriV2Alias, headers: _authHeaders());
      if (respV2Alias.statusCode == 200) {
        final map = _jsonDecodeResponse(respV2Alias) as Map<String, dynamic>;
        final triggers = map['triggers'] as List<dynamic>? ?? [];
        return triggers.cast<Map<String, dynamic>>();
      }

      return [];
    } catch (e) {
      print('listTriggers error: $e');
      return [];
    }
  }

  // compat alias для экранов
  Future<List<Map<String, dynamic>>> getTriggers() => listTriggers();

  Future<bool> updateTriggerEnabled({required String id, required bool enabled}) async {
    try {
      final uriV2 = Uri.parse('$baseUrl/v2/triggers/update-enabled');
      final resp = await http.post(
        uriV2,
        headers: _authHeaders(),
        body: jsonEncode({'id': id, 'enabled': enabled}),
      );
      return resp.statusCode == 200;
    } catch (e) {
      print('updateTriggerEnabled error: $e');
      return false;
    }
  }

  Future<bool> updateTrigger({
    required String id,
    String? triggerName,
    String? conditionKey,
    String? conditionValue,
    int? comboCount,
    String? textTemplate,
    String? soundFilename,
    int? cooldownSeconds,
    int? volume,
    bool? oncePerStream,
    bool? autoplaySound,
  }) async {
    try {
      final body = <String, dynamic>{'id': id};
      if (triggerName != null) body['trigger_name'] = triggerName;
      if (conditionKey != null) body['condition_key'] = conditionKey;
      if (conditionValue != null) body['condition_value'] = conditionValue;
      if (comboCount != null) body['combo_count'] = comboCount;
      if (textTemplate != null) body['text_template'] = _normalizeTextTemplate(textTemplate);
      if (soundFilename != null) body['sound_filename'] = soundFilename;
      if (cooldownSeconds != null) body['cooldown_seconds'] = cooldownSeconds;
      if (volume != null) body['volume'] = volume;
      if (oncePerStream != null) body['once_per_stream'] = oncePerStream;
      if (autoplaySound != null) body['autoplay_sound'] = autoplaySound;

      final uriV2 = Uri.parse('$baseUrl/v2/triggers/update');
      final resp = await http.post(
        uriV2,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      return resp.statusCode == 200;
    } catch (e) {
      print('updateTrigger error: $e');
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> getVoices() async {
    try {
      final uri = Uri.parse('$baseUrl/v2/voices');
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final voices = m['voices'] as List<dynamic>? ?? [];
        return voices.cast<Map<String, dynamic>>();
      }
      return [];
    } catch (e) {
      print('getVoices error: $e');
      return [];
    }
  }

  Future<List<Map<String, dynamic>>> listSounds() async {
    try {
      final uri = Uri.parse('$baseUrl/v2/sounds/list');
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final sounds = m['sounds'] as List<dynamic>? ?? [];
        return sounds.cast<Map<String, dynamic>>();
      }
      return [];
    } catch (e) {
      print('listSounds error: $e');
      return [];
    }
  }

  Future<String?> generateTts({required String text, String? voiceId}) async {
    try {
      _setLastError(null);
      lastTtsEngineUsed = null;
      lastTtsVoiceIdUsed = null;
      lastTtsFallbackUsed = false;
      final uri = Uri.parse('$baseUrl/tts/generate');
      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode({
          'text': text,
          if (voiceId != null && voiceId.trim().isNotEmpty) 'voice_id': voiceId.trim(),
        }),
      );
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        lastTtsEngineUsed = m['engine_used']?.toString();
        lastTtsVoiceIdUsed = m['voice_id_used']?.toString();
        lastTtsFallbackUsed = m['fallback_used'] == true;
        final backendError = m['error']?.toString().trim();
        final url = m['url']?.toString();
        if (lastTtsFallbackUsed) {
          final usedVoice = lastTtsVoiceIdUsed ?? 'gtts-ru';
          final usedEngine = lastTtsEngineUsed ?? 'gtts';
          _setLastError(
            (backendError != null && backendError.isNotEmpty)
                ? 'Выбранный голос недоступен: $backendError. Использован резервный голос $usedVoice ($usedEngine).'
                : 'Выбранный голос недоступен. Использован резервный голос $usedVoice ($usedEngine).',
          );
        }
        if (url != null && url.trim().isNotEmpty) return url.trim();
        _setLastError('Пустой URL озвучки');
        return null;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось сгенерировать TTS');
      print('generateTts error: $e');
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> getGiftsLibrary() async {
    try {
      _setLastError(null);
      // Большой payload: на мобильных сетях без gzip и таймаута может "висеть".
      // Просим облегчённый ответ без поля sound (оно не нужно для выбора подарка).
      final uri = Uri.parse('$baseUrl/v2/gifts/library').replace(
        queryParameters: {'include_sound': '0'},
      );
      final resp = await http.get(uri, headers: _authHeaders()).timeout(const Duration(seconds: 20));
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final gifts = m['gifts'] as List<dynamic>? ?? [];
        return gifts.cast<Map<String, dynamic>>();
      }

      _setLastError(_extractErrorMessage(resp));
      return [];
    } catch (e) {
      _setLastError('Не удалось загрузить библиотеку подарков');
      print('getGiftsLibrary error: $e');
      return [];
    }
  }

  Future<({String filename, String url})?> uploadSound({
    required String filename,
    required Uint8List bytes,
  }) async {
    try {
      _setLastError(null);
      if (bytes.length > kMaxSoundUploadBytes) {
        _setLastError('Файл слишком большой (макс. 1MB)');
        return null;
      }

      final uri = Uri.parse('$baseUrl/v2/sounds/upload');
      final req = http.MultipartRequest('POST', uri);
      req.headers.addAll(_authHeadersMultipart());
      req.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
      final streamed = await req.send();
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode == 200) {
        final m = jsonDecode(body) as Map<String, dynamic>;
        final fn = (m['filename'] ?? filename).toString();
        final url = (m['url'] ?? '').toString();
        return (filename: fn, url: url);
      }

      try {
        final decoded = jsonDecode(body);
        if (decoded is Map<String, dynamic>) {
          final detail = decoded['detail'];
          if (detail is String && detail.trim().isNotEmpty) {
            _setLastError(detail);
            return null;
          }
          final message = decoded['message'];
          if (message is String && message.trim().isNotEmpty) {
            _setLastError(message);
            return null;
          }
          final error = decoded['error'];
          if (error is String && error.trim().isNotEmpty) {
            _setLastError(error);
            return null;
          }
        }
      } catch (_) {
        // ignore parse errors
      }
      _setLastError('Ошибка сервера (код ${streamed.statusCode})');
      return null;
    } catch (e) {
      _setLastError('Не удалось загрузить звук');
      print('uploadSound error: $e');
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> searchMyInstants(String query) async {
    try {
      _setLastError(null);
      final q = query.trim();
      if (q.length < 2) return [];

      final uri = Uri.parse('$baseUrl/v2/sounds/external/myinstants/search').replace(
        queryParameters: {'q': q},
      );
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final items = m['items'] as List<dynamic>? ?? [];
        return items.cast<Map<String, dynamic>>();
      }
      _setLastError(_extractErrorMessage(resp));
      return [];
    } catch (e) {
      _setLastError('Не удалось выполнить поиск Myinstants');
      print('searchMyInstants error: $e');
      return [];
    }
  }

  Future<({String filename, String url})?> importMyInstants({
    required String pageUrl,
    String? title,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/sounds/external/myinstants/import');
      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode({
          'page_url': pageUrl.trim(),
          if (title != null && title.trim().isNotEmpty) 'title': title.trim(),
        }),
      );
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final fn = (m['filename'] ?? '').toString().trim();
        final url = (m['url'] ?? '').toString().trim();
        if (fn.isEmpty || url.isEmpty) {
          _setLastError('Сервер вернул неполные данные звука');
          return null;
        }
        return (filename: fn, url: url);
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось импортировать звук из Myinstants');
      print('importMyInstants error: $e');
      return null;
    }
  }

  Future<String?> getMyInstantsPreviewUrl({required String pageUrl}) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/sounds/external/myinstants/preview').replace(
        queryParameters: {'page_url': pageUrl.trim()},
      );
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final previewUrl = (m['preview_url'] ?? '').toString().trim();
        return previewUrl.isEmpty ? null : previewUrl;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось загрузить превью звука');
      print('getMyInstantsPreviewUrl error: $e');
      return null;
    }
  }

  Future<bool> setTrigger({
    required String eventType,
    String? conditionKey,
    String? conditionValue,
    required String action,
    required Map<String, dynamic> actionParams,
    bool enabled = true,
    String? triggerName,
    int? comboCount,
    int? cooldownSeconds,
  }) async {
    try {
      final normalizedEventType = _normalizeEventType(eventType);

      // v2 /triggers/set принимает text_template/sound_filename отдельно
      final bodyV2 = <String, dynamic>{
        'event_type': normalizedEventType,
        'action': action,
        'enabled': enabled,
      };

      if (conditionKey != null) bodyV2['condition_key'] = conditionKey;
      if (conditionValue != null) bodyV2['condition_value'] = conditionValue;
      if (triggerName != null) bodyV2['trigger_name'] = triggerName;
      if (comboCount != null) bodyV2['combo_count'] = comboCount;

      final dynamicCooldown = cooldownSeconds ?? actionParams['cooldown_seconds'];
      final parsedCooldown = switch (dynamicCooldown) {
        int v => v,
        String v => int.tryParse(v.trim()),
        _ => dynamicCooldown == null ? null : int.tryParse(dynamicCooldown.toString()),
      };
      if (parsedCooldown != null) bodyV2['cooldown_seconds'] = parsedCooldown;

      if (action == 'tts') {
        final raw = (actionParams['text_template'] ?? actionParams['text'] ?? '{message}').toString();
        bodyV2['text_template'] = _normalizeTextTemplate(raw);
      } else if (action == 'play_sound') {
        final filename = (actionParams['sound_filename'] ?? actionParams['sound_file'] ?? actionParams['sound']).toString();
        bodyV2['sound_filename'] = filename;

        final oncePerStream = actionParams['once_per_stream'];
        if (oncePerStream is bool) bodyV2['once_per_stream'] = oncePerStream;

        final autoplaySound = actionParams['autoplay_sound'];
        if (autoplaySound is bool) bodyV2['autoplay_sound'] = autoplaySound;
      }

      final uriV2 = Uri.parse('$baseUrl/v2/triggers/set');
      final respV2 = await http.post(
        uriV2,
        headers: _authHeaders(),
        body: jsonEncode(bodyV2),
      );
      return respV2.statusCode == 200;
    } catch (e) {
      print('setTrigger error: $e');
      return false;
    }
  }

  Future<bool> deleteTrigger({
    String? id,
    String? eventType,
    String? conditionKey,
    String? conditionValue,
  }) async {
    try {
      // v2 удаление по id
      if (id != null && id.trim().isNotEmpty) {
        final uriV2 = Uri.parse('$baseUrl/v2/triggers/delete');
        final respV2 = await http.post(
          uriV2,
          headers: _authHeaders(),
          body: jsonEncode({'id': id}),
        );
        return respV2.statusCode == 200;
      }

      // legacy удалить без ws_token невозможно, поэтому возвращаем false
      // (в UI лучше всегда передавать id)
      return false;
    } catch (e) {
      print('deleteTrigger error: $e');
      return false;
    }
  }

  /// Регистрация нового пользователя через v2 API
  Future<({String token, String userId, String username})?> register({
    required String username,
    required String password,
  }) async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/auth/register');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          // New flow: treat input as email, server auto-generates username.
          // Backward-compat: server still accepts username if email omitted.
          'email': username,
          'password': password,
        }),
      );

      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final t = m['access_token'] as String? ?? '';
        if (t.isEmpty) return null;
        _jwtToken = t;
        final profile = await getProfile();
        if (profile != null) {
          return (
            token: t,
            userId: profile['id'].toString(),
            username: profile['username'] as String,
          );
        }
        // если профиль не загрузился, все равно вернём токен и введённый username
        return (
          token: t,
          userId: '',
          username: username,
        );
      } else if (resp.statusCode == 409) {
        _setLastError('Пользователь уже существует');
      } else {
        _setLastError(_extractErrorMessage(resp));
      }
      return null;
    } catch (e) {
      _setLastError('Не удалось подключиться к серверу');
      print('register error: $e');
      return null;
    }
  }

  /// Подключение TikTok через обновление настроек (tiktok_username)
  Future<bool> connectToTikTok(String username) async {
    try {
      final ok = await updateSettings(tiktokUsername: username);
      return ok;
    } catch (e) {
      print('connectToTikTok error: $e');
      return false;
    }
  }

  /// Отключение TikTok — очищаем tiktok_username в настройках
  Future<void> disconnectFromTikTok() async {
    try {
      await updateSettings(tiktokUsername: '');
    } catch (e) {
      print('disconnectFromTikTok error: $e');
    }
  }

  Future<Map<String, dynamic>?> getStatsOverview() async {
    try {
      _setLastError(null);
      final uri = Uri.parse('$baseUrl/v2/stats/overview');
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        return _jsonDecodeResponse(resp) as Map<String, dynamic>;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось загрузить статистику');
      print('getStatsOverview error: $e');
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> getTopDonors({String period = 'today', int limit = 5}) async {
    try {
      _setLastError(null);
      if (limit <= 0) limit = 5;
      final uri = Uri.parse('$baseUrl/v2/stats/top-donors').replace(
        queryParameters: {
          'period': period,
          'limit': '$limit',
        },
      );
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        final m = _jsonDecodeResponse(resp) as Map<String, dynamic>;
        final donors = m['donors'] as List<dynamic>? ?? [];
        return donors.cast<Map<String, dynamic>>();
      }
      _setLastError(_extractErrorMessage(resp));
      return [];
    } catch (e) {
      _setLastError('Не удалось загрузить топ донатеров');
      print('getTopDonors error: $e');
      return [];
    }
  }

  Future<Map<String, dynamic>?> getDonorStats({required String donorUsername}) async {
    try {
      _setLastError(null);
      final u = donorUsername.trim().replaceAll('@', '');
      if (u.isEmpty) {
        _setLastError('donor_username required');
        return null;
      }
      final uri = Uri.parse('$baseUrl/v2/stats/donor/$u');
      final resp = await http.get(uri, headers: _authHeaders());
      if (resp.statusCode == 200) {
        return _jsonDecodeResponse(resp) as Map<String, dynamic>;
      }
      _setLastError(_extractErrorMessage(resp));
      return null;
    } catch (e) {
      _setLastError('Не удалось загрузить статистику донатера');
      print('getDonorStats error: $e');
      return null;
    }
  }
}
