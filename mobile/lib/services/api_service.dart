import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/constants.dart';

class ApiService {
  final String baseUrl;
  String? _jwtToken;

  ApiService({this.baseUrl = kApiBaseUrl});

  void setToken(String token) {
    _jwtToken = token;
  }

  String? get token => _jwtToken;

  Map<String, String> _authHeaders() {
    final headers = {'Content-Type': 'application/json'};
    if (_jwtToken != null) {
      headers['Authorization'] = 'Bearer $_jwtToken';
    }
    return headers;
  }

  Future<({String token, String userId, String username})?> redeemLicense({
    required String licenseKey,
    required String username,
    required String password,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/auth/redeem-license');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'license_key': licenseKey,
          'username': username,
          'password': password,
        }),
      );

      if (resp.statusCode == 200) {
        final m = jsonDecode(resp.body) as Map<String, dynamic>;
        final t = m['access_token'] as String? ?? '';
        _jwtToken = t;
        final profile = await getProfile();
        if (profile != null) {
          return (token: t, userId: profile['id'].toString(), username: profile['username'] as String);
        }
      }
      return null;
    } catch (e) {
      print('redeemLicense error: $e');
      return null;
    }
  }

  Future<({String token, String userId, String username})?> login({
    required String username,
    required String password,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/auth/login');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'password': password,
        }),
      );

      if (resp.statusCode == 200) {
        final m = jsonDecode(resp.body) as Map<String, dynamic>;
        final t = m['access_token'] as String? ?? '';
        _jwtToken = t;
        final profile = await getProfile();
        if (profile != null) {
          return (token: t, userId: profile['id'].toString(), username: profile['username'] as String);
        }
      }
      return null;
    } catch (e) {
      print('login error: $e');
      return null;
    }
  }

  Future<Map<String, dynamic>?> getProfile() async {
    try {
      final uri = Uri.parse('$baseUrl/auth/me');
      final resp = await http.get(uri, headers: _authHeaders());

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return null;
    } catch (e) {
      print('getProfile error: $e');
      return null;
    }
  }

  Future<bool> updateSettings({
    String? tiktokUsername,
    String? voiceId,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/settings/update');
      final body = <String, dynamic>{};

      if (tiktokUsername != null) body['tiktok_username'] = tiktokUsername;
      if (voiceId != null) body['voice_id'] = voiceId;

      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );

      return resp.statusCode == 200;
    } catch (e) {
      print('updateSettings error: $e');
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> listTriggers() async {
    try {
      final uri = Uri.parse('$baseUrl/triggers/list');
      final resp = await http.get(uri, headers: _authHeaders());

      if (resp.statusCode == 200) {
        final map = jsonDecode(resp.body) as Map<String, dynamic>;
        final triggers = map['triggers'] as List<dynamic>? ?? [];
        return triggers.cast<Map<String, dynamic>>();
      }
      return [];
    } catch (e) {
      print('listTriggers error: $e');
      return [];
    }
  }

  Future<bool> setTrigger({
    required String eventType,
    String? conditionKey,
    String? conditionValue,
    required String action,
    required Map<String, dynamic> actionParams,
    bool enabled = true,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/triggers/set');
      final body = <String, dynamic>{
        'event_type': eventType,
        'action': action,
        'action_params': actionParams,
        'enabled': enabled,
      };

      if (conditionKey != null) body['condition_key'] = conditionKey;
      if (conditionValue != null) body['condition_value'] = conditionValue;

      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );

      return resp.statusCode == 200;
    } catch (e) {
      print('setTrigger error: $e');
      return false;
    }
  }

  Future<bool> deleteTrigger({
    required String eventType,
    String? conditionKey,
    String? conditionValue,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/triggers/delete');
      final body = <String, dynamic>{
        'event_type': eventType,
      };

      if (conditionKey != null) body['condition_key'] = conditionKey;
      if (conditionValue != null) body['condition_value'] = conditionValue;

      final resp = await http.post(
        uri,
        headers: _authHeaders(),
        body: jsonEncode(body),
      );

      return resp.statusCode == 200;
    } catch (e) {
      print('deleteTrigger error: $e');
      return false;
    }
  }
}
