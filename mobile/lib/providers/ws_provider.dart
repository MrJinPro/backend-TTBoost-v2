import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/ws_service.dart';
import '../services/api_service.dart';
import '../services/audio_playback_service.dart';
import '../services/overlay_bridge.dart';
import '../services/usage_limits.dart';
import '../utils/log.dart';
import '../utils/premium_gate.dart';
import 'dart:async';

const _kPrefLastTikTokUsername = 'last_tiktok_username';
const _kPrefAutoConnectLive = 'auto_connect_live';

// Auto reconnect uses backoff and never spams parallel attempts.

/// Provider для управления WebSocket соединением и состоянием стрима.
/// Предоставляет доступ к WS событиям, статусу подключения и управлению TikTok соединением.
class WsProvider extends ChangeNotifier {
  final WsService _ws = WsService();
  ApiService _api;
  String? _activeToken;
  final AudioPlaybackService _audio = AudioPlaybackService();
  Timer? _overlayStopListener;
  Timer? _wsKeepAliveTimer;

  bool _premiumEnabled = false;

  String? _pendingTikTokUsername;
  bool _retryingPendingConnect = false;

  bool _autoConnectLive = false;
  bool _manualLiveDisconnect = false;
  bool _sessionAutoReconnectLive = false;
  Timer? _autoReconnectTimer;
  int _autoReconnectAttempt = 0;
  bool _autoReconnectInFlight = false;

  Timer? _wsReconnectTimer;
  int _wsReconnectAttempt = 0;
  bool _wsReconnectInFlight = false;
  
  bool _wsConnected = false;
  bool _tiktokConnected = false;
  bool _liveConnecting = false;
  String? _liveStatusText;
  String? _liveErrorText;
  bool _ttsEnabled = true;
  bool _giftSoundsEnabled = true;
  bool _silenceEnabled = false;
  bool _giftTtsAlongside = false;
  double _ttsVolume = 100;
  double _giftsVolume = 100;
  double _ttsSpeed = 1.0;
  String? _voiceId;

  // Demo mode (Google review): enabled only for a specific account.
  static const String _kDemoAccountUsername = 'DemoGoogle';
  bool _demoMode = false;
  Timer? _demoTimer;
  int _demoStep = 0;
  String? _demoSoundUrl;
  
  final List<Map<String, dynamic>> _events = [];
  String? _currentTikTokUsername;
  Map<String, dynamic> _streamStats = {};
  
  // Getters
  bool get wsConnected => _wsConnected;
  bool get tiktokConnected => _tiktokConnected;
  bool get liveConnecting => _liveConnecting;
  String? get liveStatusText => _liveStatusText;
  String? get liveErrorText => _liveErrorText;
  bool get ttsEnabled => _ttsEnabled;
  bool get giftSoundsEnabled => _giftSoundsEnabled;
  bool get giftTtsAlongside => _giftTtsAlongside;
  double get ttsVolume => _ttsVolume;
  double get giftsVolume => _giftsVolume;
  double get ttsSpeed => _ttsSpeed;
  List<Map<String, dynamic>> get events => List.unmodifiable(_events);
  String? get currentTikTokUsername => _currentTikTokUsername;
  Map<String, dynamic> get streamStats => Map.from(_streamStats);

  bool get demoMode => _demoMode;

  bool get premiumEnabled => _premiumEnabled;

  bool get autoConnectLive => _autoConnectLive;
  bool get silenceEnabled => _silenceEnabled;
  
  WsProvider({required ApiService apiService}) : _api = apiService {
    _initializeWs();
    _loadSavedTikTokUsername(); // Load saved TikTok username on initialization

    // Overlay: allow stopping currently playing audio from a small floating window (Android).
    _overlayStopListener = OverlayBridge.startStopListener(
      onStopTts: stopTts,
      onStopGifts: stopGifts,
      onSetTtsVolume: (v) async => updateTtsVolume(v),
      onSetGiftsVolume: (v) async => updateGiftsVolume(v),
      onTestTts: _testTtsFromOverlay,
      onReconnectLive: _reconnectLiveFromOverlay,
    );
  }

  Future<void> _reconnectLiveFromOverlay() async {
    try {
      final u = (_currentTikTokUsername ?? '').trim();
      if (u.isEmpty) return;

      _manualLiveDisconnect = false;
      _cancelAutoReconnect();

      final token = (_activeToken ?? '').trim();
      if (!_wsConnected && token.isNotEmpty) {
        _ws.connect(token);
        await Future<void>.delayed(const Duration(milliseconds: 600));
      }

      await connectToTikTok(u);
    } catch (_) {
      // Overlay command should never crash provider.
    }
  }

  /// ╨Ю╨▒╨╜╨╛╨▓╨╗╤П╨╡╤В ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜╨╜╤Л╨╣ TikTok username ╨╗╨╛╨║╨░╨╗╤М╨╜╨╛ (╨╕ ╨┤╨╗╤П ╨╛╨▓╨╡╤А╨╗╨╡╤П),
  /// ╤З╤В╨╛╨▒╤Л UI ╤Б╤А╨░╨╖╤Г ╨┐╨╛╨║╨░╨╖╤Л╨▓╨░╨╗ ╨╜╨╛╨▓╨╛╨╡ ╨╖╨╜╨░╤З╨╡╨╜╨╕╨╡ ╨┐╨╛╤Б╨╗╨╡ ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨╕╤П ╨▓ ╨┐╤А╨╛╤Д╨╕╨╗╨╡.
  Future<void> setSavedTikTokUsername(String? username) async {
    final normalized = (username ?? '').trim().replaceAll('@', '').trim();
    final prefs = await SharedPreferences.getInstance();

    if (normalized.isEmpty) {
      _currentTikTokUsername = null;
      await prefs.remove(_kPrefLastTikTokUsername);
    } else {
      _currentTikTokUsername = normalized;
      await prefs.setString(_kPrefLastTikTokUsername, normalized);
    }

    _syncOverlayStatus();
    notifyListeners();
  }

  void updateAuth({required ApiService apiService, required String? jwtToken, String? plan}) {
    _api = apiService;

    final premium = PremiumGate.isPremiumPlan(plan);
    if (premium != _premiumEnabled) {
      _premiumEnabled = premium;
      _audio.setPremiumEnabled(premium);
    }

    if (jwtToken == _activeToken) return;
    _activeToken = jwtToken;
    _api.setToken(jwtToken ?? '');

    if (jwtToken != null && jwtToken.isNotEmpty) {
      // Sync local state with server-side settings (flags, volumes, voice_id).
      () async {
        await refreshSettingsFromServer();

        final shouldResumeLive = false;
        if (shouldResumeLive) {
          return;
        }

        try {
          await _ws.disconnectFromTikTok();
        } catch (_) {}
      }();

      // WS ╨┤╨╗╤П ╤Б╨╛╨▒╤Л╤В╨╕╨╣ ╤Б╤В╤А╨╕╨╝╨░
      _ws.connect(jwtToken);
      _pendingTikTokUsername = null;
    } else {
      // Logout / token cleared
      _ws.disconnect();
      _wsConnected = false;
      _tiktokConnected = false;
      _liveConnecting = false;
      _liveStatusText = null;
      _liveErrorText = null;
      _audio.setLiveConnected(false);
      _cancelAutoReconnect();
      _syncOverlayStatus();
      notifyListeners();
    }
  }

  Future<void> refreshSettingsFromServer() async {
    final t = _activeToken;
    if (t == null || t.trim().isEmpty) return;
    try {
      final settings = await _api.getSettings();
      if (settings == null) return;

      final voiceId = settings['voice_id']?.toString().trim();
      final savedTikTokUsername = settings['tiktok_username']?.toString().trim();
      final ttsEnabled = settings['tts_enabled'];
      final giftEnabled = settings['gift_sounds_enabled'];
      final silenceEnabled = settings['silence_enabled'];
      final ttsVol = (settings['tts_volume'] as num?)?.toDouble();
      final giftsVol = (settings['gifts_volume'] as num?)?.toDouble();
      final auto = settings['auto_connect_live'];

      var changed = false;

      if (voiceId != null && voiceId.isNotEmpty && voiceId != _voiceId) {
        _voiceId = voiceId;
        changed = true;
      }

      if (savedTikTokUsername != null && savedTikTokUsername.isNotEmpty) {
        final normalized = savedTikTokUsername.replaceAll('@', '').trim();
        if (normalized.isNotEmpty && ((_currentTikTokUsername ?? '').trim().isEmpty || _currentTikTokUsername != normalized)) {
          _currentTikTokUsername = normalized;
          try {
            final prefs = await SharedPreferences.getInstance();
            await prefs.setString(_kPrefLastTikTokUsername, normalized);
          } catch (_) {}
          changed = true;
        }
      }

      if (ttsEnabled is bool && ttsEnabled != _ttsEnabled) {
        _ttsEnabled = ttsEnabled;
        changed = true;
      }
      if (giftEnabled is bool && giftEnabled != _giftSoundsEnabled) {
        _giftSoundsEnabled = giftEnabled;
        changed = true;
      }
      if (silenceEnabled is bool && silenceEnabled != _silenceEnabled) {
        _silenceEnabled = silenceEnabled;
        changed = true;
      }

      if (ttsVol != null) {
        final v = ttsVol.clamp(0, 100).toDouble();
        if (v != _ttsVolume) {
          _ttsVolume = v;
          OverlayBridge.setVolumes(ttsVolume: _ttsVolume);
          changed = true;
        }
      }

      if (giftsVol != null) {
        final v = giftsVol.clamp(0, 100).toDouble();
        if (v != _giftsVolume) {
          _giftsVolume = v;
          OverlayBridge.setVolumes(giftsVolume: _giftsVolume);
          changed = true;
        }
      }

      if (auto is bool && auto != false) {
        _autoConnectLive = false;
        try {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setBool(_kPrefAutoConnectLive, false);
        } catch (_) {}
        changed = true;
      }

      if (changed) {
        notifyListeners();
      }

    } catch (e) {
      logDebug('Failed to refresh settings: $e');
    }
  }

  void _syncOverlayStatus() {
    OverlayBridge.setStatus(
      wsConnected: _demoMode ? true : _wsConnected,
      liveConnected: _demoMode ? true : _tiktokConnected,
      tiktokUsername: _currentTikTokUsername,
    );
  }

  bool _isDemoAccount(String accountUsername) {
    return accountUsername.trim().toLowerCase() == _kDemoAccountUsername.toLowerCase();
  }

  void _stopDemoInternal() {
    _demoTimer?.cancel();
    _demoTimer = null;
    _demoMode = false;
    _demoStep = 0;
    _demoSoundUrl = null;
  }

  Future<void> stopDemoMode() async {
    if (!_demoMode) return;
    _stopDemoInternal();
    _tiktokConnected = false;
    _liveConnecting = false;
    _liveStatusText = 'Демо-режим выключен';
    _liveErrorText = null;
    _syncOverlayStatus();
    notifyListeners();
  }

  Future<bool> startDemoMode({required String accountUsername}) async {
    if (!_isDemoAccount(accountUsername)) return false;
    if (_demoMode) return true;

    // Ensure real LIVE is stopped.
    try {
      await _ws.disconnectFromTikTok();
    } catch (_) {}

    _demoMode = true;
    _liveConnecting = false;
    _tiktokConnected = true;
    _liveErrorText = null;
    _liveStatusText = 'Демо-режим: тестовые события без LIVE';

    if ((_currentTikTokUsername ?? '').trim().isEmpty) {
      _currentTikTokUsername = 'demo_live';
    }

    // Optional: pick any available sound for demo gifts.
    try {
      final sounds = await _api.listSounds();
      for (final s in sounds) {
        final url = s['url']?.toString().trim();
        if (url != null && url.isNotEmpty) {
          _demoSoundUrl = url;
          break;
        }
      }
    } catch (_) {}

    _resetStreamStats();
    _events.clear();
    _syncOverlayStatus();
    notifyListeners();

    _demoTimer?.cancel();
    _demoTimer = Timer.periodic(const Duration(seconds: 6), (_) {
      // Fire-and-forget.
      _emitDemoEvent();
    });

    // Emit one event immediately.
    _emitDemoEvent();
    return true;
  }

  Future<void> _emitDemoEvent() async {
    if (!_demoMode) return;

    final step = _demoStep++ % 5;
    Map<String, dynamic> event;
    String? ttsText;

    switch (step) {
      case 0:
        event = {
          '__demo': true,
          'type': 'viewer_join',
          'username': 'demo_viewer_${(_demoStep % 99) + 1}',
        };
        ttsText = 'К нам присоединился зритель.';
        break;
      case 1:
        event = {
          '__demo': true,
          'type': 'chat',
          'user': 'DemoUser',
          'message': 'Привет! Это тестовый чат для проверки.',
        };
        ttsText = 'DemoUser: Привет! Это тестовый чат для проверки.';
        break;
      case 2:
        event = {
          '__demo': true,
          'type': 'gift',
          'user': 'DemoFan',
          'gift_name': 'Rose',
          'count': 1,
          'diamonds': 1,
          if (_demoSoundUrl != null) 'sound_url': _demoSoundUrl,
          'volume': 100,
        };
        ttsText = 'DemoFan отправил подарок Rose.';
        break;
      case 3:
        event = {
          '__demo': true,
          'type': 'follow',
          'user': 'NewFollower',
        };
        break;
      default:
        event = {
          '__demo': true,
          'type': 'like',
          'user': 'LikeUser',
          'count': 12,
        };
    }

    if (ttsText != null) {
      try {
        final url = await _api.generateTts(text: ttsText, voiceId: _voiceId);
        if (url != null && url.trim().isNotEmpty) {
          event['tts_url'] = url.trim();
        }
      } catch (_) {}
    }

    _handleWsEvent(event);
  }

  Future<void> _testTtsFromOverlay() async {
    try {
      // Always allow testing, even if TTS is currently disabled.
      await _audio.stopTts();

      const text = 'NovaBoost Mobile сервис для стримеров!';
      final url = await _api.generateTts(text: text, voiceId: _voiceId);
      if (url == null || url.trim().isEmpty) return;

      final vol = ((_ttsVolume / 100).clamp(0, 1)).toDouble();
      await _audio.playTts(url: url, volume: vol, rate: _ttsSpeed);
    } catch (_) {
      // Silent: overlay test should not crash provider.
    }
  }
  
  void _initializeWs() {
    _ws.onStatus = (connected) {
      _wsConnected = connected;
      logDebug('WS Status changed: $connected');

      if (!connected) {
        _liveConnecting = false;
        _tiktokConnected = false;
        _cancelAutoReconnect();
        _stopWsKeepAlive();
        _scheduleWsReconnect();
      }

      if (connected) {
        // Don't reset attempt immediately: WsService may report "connected" before
        // the handshake is actually stable. We only cancel pending timer/inFlight.
        _cancelWsReconnect(resetAttempt: false);
        _startWsKeepAlive();

        // If WS stays up for a bit, consider it stable and reset backoff.
        () async {
          final marker = _wsReconnectAttempt;
          await Future<void>.delayed(const Duration(seconds: 8));
          if (_wsConnected && _wsReconnectAttempt == marker) {
            _wsReconnectAttempt = 0;
          }
        }();
      }

      _syncOverlayStatus();
      notifyListeners();
    };

    _ws.onEvent = _handleWsEvent;

    () async {
      try {
        final prefs = await SharedPreferences.getInstance();
        _currentTikTokUsername = prefs.getString(_kPrefLastTikTokUsername);
        _autoConnectLive = false;
        _sessionAutoReconnectLive = false;
        await prefs.setBool(_kPrefAutoConnectLive, false);
        _syncOverlayStatus();
        notifyListeners();
      } catch (_) {}
    }();
  }

  Future<void> _loadSavedTikTokUsername() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUsername = prefs.getString(_kPrefLastTikTokUsername);
    if (savedUsername != null && savedUsername.trim().isNotEmpty) {
      _currentTikTokUsername = savedUsername.trim();
      notifyListeners();
    }
  }

  void _maybeAutoConnectSavedLive({bool immediate = false}) {
    return;
  }

  bool _looksCorruptedText(String? text) {
    final value = (text ?? '').trim();
    if (value.isEmpty) return false;
    return value.contains('╨') ||
        value.contains('╤') ||
        value.contains('тА') ||
        value.contains('�');
  }

  bool _isBackendReconnectMessage(String? message) {
    final lower = (message ?? '').trim().toLowerCase();
    if (lower.isEmpty) return false;
    return lower.contains('переподключ') ||
        lower.contains('reconnect') ||
        lower.contains('re-connecting') ||
        lower.contains('recovering');
  }

  String _friendlyLiveStatusText(
    String? message, {
    required bool connected,
    required bool isConnectingStatus,
    bool isRecoveringStatus = false,
    String? username,
  }) {
    final account = (username ?? '').replaceAll('@', '').trim();
    final normalized = (message ?? '').trim();
    final lower = normalized.toLowerCase();

    if (isRecoveringStatus) {
      return account.isNotEmpty
          ? 'Связь с @$account потеряна, переподключаемся...'
          : 'Связь с TikTok LIVE потеряна, переподключаемся...';
    }

    if (isConnectingStatus) {
      return account.isNotEmpty
          ? 'Подключаемся к @$account...'
          : 'Подключаемся к TikTok LIVE...';
    }

    if (connected) {
      return account.isNotEmpty ? 'Подключено к @$account' : 'TikTok LIVE подключен';
    }

    if (normalized.isEmpty || _looksCorruptedText(normalized)) {
      return account.isNotEmpty ? 'LIVE для @$account отключен' : 'TikTok LIVE отключен';
    }

    if (lower.contains('disconnect') ||
        lower.contains('offline') ||
        lower.contains('stopped') ||
        lower.contains('closed') ||
        lower.contains('отключ')) {
      return account.isNotEmpty ? 'LIVE для @$account отключен' : 'TikTok LIVE отключен';
    }

    return normalized;
  }

  String _friendlyLiveErrorText(String? message, {String? username}) {
    final account = (username ?? '').replaceAll('@', '').trim();
    final normalized = (message ?? '').trim();
    final lower = normalized.toLowerCase();

    if (lower.contains('not found') ||
        lower.contains('user_not_found') ||
        lower.contains('room_id') ||
        lower.contains('room id') ||
        lower.contains('offline') ||
        lower.contains('not live') ||
        lower.contains('no active live')) {
      return account.isNotEmpty
          ? 'Не удалось найти активный эфир у @$account. Проверьте, что LIVE запущен.'
          : 'Не удалось найти активный эфир. Проверьте, что LIVE запущен.';
    }

    if (lower.contains('timeout') || lower.contains('timed out')) {
      return 'TikTok долго не отвечает. Попробуйте еще раз.';
    }

    if (lower.contains('network') ||
        lower.contains('websocket') ||
        lower.contains('connection') ||
        lower.contains('connect')) {
      return 'Не удалось подключиться к TikTok LIVE. Попробуйте еще раз.';
    }

    if (normalized.isEmpty ||
        _looksCorruptedText(normalized) ||
        lower.contains('traceback') ||
        lower.contains('exception') ||
        lower.contains('sqlalchemy') ||
        lower.contains('session')) {
      return account.isNotEmpty
          ? 'Не удалось подключиться к @$account. Проверьте username и что эфир уже запущен.'
          : 'Не удалось подключиться к TikTok LIVE. Проверьте username и что эфир уже запущен.';
    }

    return normalized;
  }

  void _handleWsEvent(Map<String, dynamic> rawEvent) {
    final event = Map<String, dynamic>.from(rawEvent);

    // Status updates from backend
    if (event['type']?.toString() == 'status') {
      final connected = event['connected'] == true;
      final msg = event['message']?.toString();
      final u = event['tiktok_username']?.toString().trim();
      final pending = _pendingTikTokUsername?.trim().toLowerCase();
      final incomingUser = u?.replaceAll('@', '').toLowerCase();
      final isRecoveringStatus = !connected && _isBackendReconnectMessage(msg);
      final isConnectingStatus = !connected && (
        (msg != null && msg.toLowerCase().contains('подключаем')) ||
        (pending != null && pending.isNotEmpty && incomingUser == pending)
      );
      if (u != null && u.isNotEmpty) {
        _currentTikTokUsername = u.replaceAll('@', '');
      }

      _tiktokConnected = connected;
      _audio.setLiveConnected(connected);
      _liveStatusText = _friendlyLiveStatusText(
        msg,
        connected: connected,
        isConnectingStatus: isConnectingStatus,
        isRecoveringStatus: isRecoveringStatus,
        username: u,
      );
      _liveErrorText = null;
      _liveConnecting = isConnectingStatus || isRecoveringStatus;

      if (connected) {
        _manualLiveDisconnect = false;
        _pendingTikTokUsername = null;
        _retryingPendingConnect = false;
        _cancelAutoReconnect();
        _resetStreamStats();
        _autoReconnectAttempt = 0;
      } else if (isRecoveringStatus) {
        _cancelAutoReconnect(resetAttempt: false, resetInFlight: false);
      }

      _events.insert(0, _mapEvent(event));
      _syncOverlayStatus();
      notifyListeners();
      return;
    }

    // Errors
    if (event['type']?.toString() == 'error') {
      final msg = event['message']?.toString();
      final expected = _pendingTikTokUsername?.trim();
      final incoming = _extractUsernameFromText(msg)?.trim();

      // If switching usernames, ignore stale error and retry once.
      if (expected != null && expected.isNotEmpty && incoming != null && incoming.isNotEmpty) {
        if (incoming.toLowerCase() != expected.toLowerCase()) {
          if (!_retryingPendingConnect) {
            _retryingPendingConnect = true;
            _liveConnecting = true;
            _liveErrorText = null;
            _liveStatusText = 'Переключаем аккаунт на @$expected…';
            notifyListeners();

            () async {
              try {
                await _ws.disconnectFromTikTok();
                await Future<void>.delayed(const Duration(milliseconds: 450));
                await _ws.connectToTikTok(expected);
              } catch (_) {
              } finally {
                _retryingPendingConnect = false;
              }
            }();
          }
          return;
        }
      }

      if (msg != null && msg.isNotEmpty) {
        _liveErrorText = _friendlyLiveErrorText(
          msg,
          username: expected ?? _currentTikTokUsername,
        );
      } else {
        _liveErrorText = _friendlyLiveErrorText(
          null,
          username: expected ?? _currentTikTokUsername,
        );
      }
      _liveConnecting = false;
      _pendingTikTokUsername = null;
      _retryingPendingConnect = false;
    }

    logDebug('WS Event: ${event['type']}');

    _events.insert(0, _mapEvent(event));
    _updateStreamStats(event);
    _syncOverlayStatus();

    // Auto-play sound/TTS if enabled
    _autoPlay(event);
    notifyListeners();
  }

  String _displayNameFromEvent(Map<String, dynamic> event) {
    final username = event['username']?.toString().trim();
    if (username != null && username.isNotEmpty) {
      final u = username.startsWith('@') ? username : '@$username';
      return u;
    }
    final nickname = event['nickname']?.toString().trim();
    if (nickname != null && nickname.isNotEmpty) return nickname;
    final user = event['user']?.toString().trim();
    if (user != null && user.isNotEmpty) return user;
    return 'Аноним';
  }

  Future<void> _autoPlay(Map<String, dynamic> event) async {
    try {
      final type = event['type']?.toString();
      final isJoin = type == 'viewer_join' || type == 'join';

      final ttsUrl = _resolveMediaUrl(event['tts_url']?.toString());
      if (_ttsEnabled && ttsUrl != null && ttsUrl.isNotEmpty) {
        var allowTts = true;
        if (!_premiumEnabled && type == 'chat') {
          allowTts = await UsageLimits.tryConsumeChatTts(limit: 150);
        }
        final vol = ((_ttsVolume / 100).clamp(0, 1)).toDouble();
        if (allowTts) {
          if (isJoin) {
            _audio.playJoinTts(url: ttsUrl, volume: vol, rate: _ttsSpeed);
          } else {
            _audio.playTts(url: ttsUrl, volume: vol, rate: _ttsSpeed);
          }
        }
      }

      final soundUrl = _resolveMediaUrl(event['sound_url']?.toString());
      final autoplaySound = event['autoplay_sound'];
      if (autoplaySound is bool && autoplaySound == false) {
        return;
      }
      if (_giftSoundsEnabled && soundUrl != null && soundUrl.isNotEmpty) {
        final localVol = (event['volume'] as num?)?.toDouble();
        final effective = (_giftsVolume / 100) * ((localVol ?? 100) / 100);
        final vol = (effective.clamp(0, 1)).toDouble();
        if (isJoin) {
          _audio.playJoinSound(url: soundUrl, volume: vol);
        } else {
          _audio.playGift(url: soundUrl, volume: vol);
        }
      }
    } catch (e) {
      logDebug('Auto play error: $e');
    }
  }

  String? _resolveMediaUrl(String? raw) {
    final s = (raw ?? '').trim();
    if (s.isEmpty) return null;

    final base = (_api.baseUrl).trim().replaceAll(RegExp(r'/+$'), '');
    if (s.startsWith('/')) {
      if (base.isEmpty) return s;
      return '$base$s';
    }

    final u = Uri.tryParse(s);
    final b = Uri.tryParse(base);
    if (u == null || b == null) return s;

    final host = u.host.toLowerCase();
    if (host == 'localhost' || host == '127.0.0.1' || host == '0.0.0.0') {
      return u.replace(
        scheme: b.scheme,
        host: b.host,
        port: b.hasPort ? b.port : null,
      ).toString();
    }

    return s;
  }
  
  Map<String, dynamic> _mapEvent(Map<String, dynamic> event) {
    final type = event['type']?.toString() ?? 'unknown';
    final timestamp = DateTime.now();
    
    String category;
    String text;
    
    switch (type) {
      case 'chat':
        category = 'Чат';
        final user = event['user']?.toString() ?? 'Аноним';
        final message = event['message']?.toString() ?? '';
        text = '$user: $message';
        break;
      case 'gift':
        category = 'Подарок';
        final user = event['user']?.toString() ?? 'Аноним';
        final giftName = event['gift_name']?.toString() ?? 'Подарок';
        final count = event['count']?.toString() ?? '1';
        text = '$user отправил $giftName (x$count)';
        break;
      case 'join':
        category = 'Зритель';
        final who = _displayNameFromEvent(event);
        text = '$who зашел в эфир';
        break;
      case 'viewer_join':
        category = 'Зритель';
        final who = _displayNameFromEvent(event);
        text = '$who зашел в эфир';
        break;
      case 'follow':
        category = 'Подписка';
        final user = event['user']?.toString() ?? 'Аноним';
        text = '$user подписался';
        break;
      case 'like':
        category = 'Лайк';
        final user = event['user']?.toString() ?? 'Аноним';
        final count = event['count']?.toString() ?? '1';
        text = '$user поставил $count лайков';
        break;
      case 'error':
        category = 'Ошибка';
        text = _friendlyLiveErrorText(
          event['message']?.toString(),
          username: _pendingTikTokUsername ?? _currentTikTokUsername,
        );
        break;
      case 'status':
        category = 'Статус';
        text = _friendlyLiveStatusText(
          event['message']?.toString(),
          connected: event['connected'] == true,
          isRecoveringStatus: event['connected'] != true &&
            _isBackendReconnectMessage(event['message']?.toString()),
          isConnectingStatus: event['connected'] != true &&
              ((event['message']?.toString().toLowerCase().contains('подключаем')) ?? false),
          username: event['tiktok_username']?.toString(),
        );
        break;
      default:
        category = 'Событие';
        text = event['message']?.toString() ?? type;
    }
    
    return {
      'timestamp': timestamp,
      'type': type,
      'category': category,
      'text': text,
      'raw': event,
      'tts_url': event['tts_url'],
      'sound_url': event['sound_url'],
    };
  }
  
  void _updateStreamStats(Map<String, dynamic> event) {
    final type = event['type']?.toString();
    
    // ╨Ш╨╜╨╕╤Ж╨╕╨░╨╗╨╕╨╖╨╕╤А╤Г╨╡╨╝ ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╤Г ╨╡╤Б╨╗╨╕ ╨╜╨╡ ╤Б╤Г╤Й╨╡╤Б╤В╨▓╤Г╨╡╤В
    _streamStats.putIfAbsent('totalDiamonds', () => 0);
    _streamStats.putIfAbsent('totalGifts', () => 0);
    _streamStats.putIfAbsent('totalViewers', () => 0);
    _streamStats.putIfAbsent('totalChats', () => 0);
    _streamStats.putIfAbsent('streamStart', () => DateTime.now());
    
    switch (type) {
      case 'gift':
        _streamStats['totalGifts'] = (_streamStats['totalGifts'] ?? 0) + 1;
        final diamonds = event['diamonds'] ?? event['diamond_count'] ?? 0;
        _streamStats['totalDiamonds'] = (_streamStats['totalDiamonds'] ?? 0) + diamonds;
        
        // ╨Ю╨▒╨╜╨╛╨▓╨╗╤П╨╡╨╝ ╤В╨╛╨┐ ╨┤╨╛╨╜╨░╤В╨╡╤А╨░
        final user = event['user']?.toString();
        if (user != null) {
          _streamStats['topGifter'] = user;
        }
        
        // ╨Ю╨▒╨╜╨╛╨▓╨╗╤П╨╡╨╝ ╤Б╨░╨╝╤Л╨╣ ╨┤╨╛╤А╨╛╨│╨╛╨╣ ╨┐╨╛╨┤╨░╤А╨╛╨║
        final currentExpensive = _streamStats['mostExpensiveGift'] as Map<String, dynamic>?;
        if (currentExpensive == null || diamonds > (currentExpensive['diamonds'] ?? 0)) {
          _streamStats['mostExpensiveGift'] = {
            'name': event['gift_name']?.toString() ?? '╨Я╨╛╨┤╨░╤А╨╛╨║',
            'diamonds': diamonds,
            'user': user ?? '╨Р╨╜╨╛╨╜╨╕╨╝',
          };
        }
        break;
      case 'chat':
        _streamStats['totalChats'] = (_streamStats['totalChats'] ?? 0) + 1;
        break;
      case 'join':
      case 'viewer_join':
        _streamStats['totalViewers'] = (_streamStats['totalViewers'] ?? 0) + 1;
        break;
    }
    
    // ╨Ю╨▒╨╜╨╛╨▓╨╗╤П╨╡╨╝ ╨┤╨╗╨╕╤В╨╡╨╗╤М╨╜╨╛╤Б╤В╤М ╤Б╤В╤А╨╕╨╝╨░
    final start = _streamStats['streamStart'] as DateTime?;
    if (start != null) {
      final duration = DateTime.now().difference(start);
      final hours = duration.inHours;
      final minutes = duration.inMinutes % 60;
      _streamStats['streamDuration'] = hours > 0 ? '${hours}╤З ${minutes}╨╝' : '${minutes}╨╝';
    }
  }
  
  // ╨Ь╨╡╤В╨╛╨┤╤Л ╤Г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╤П
  Future<bool> connectToTikTok(String username, {bool fromAutoReconnect = false}) async {
    try {
      logDebug('Connecting to TikTok: $username');

      if (_demoMode) {
        await stopDemoMode();
      }

      _manualLiveDisconnect = false;
      _sessionAutoReconnectLive = false;
      _autoConnectLive = false;
      _cancelAutoReconnect();

      // ╨п╨▓╨╜╨╛╨╡ ╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╡ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П: ╤А╨░╨╖╤А╨╡╤И╨░╨╡╨╝ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╨╡ ╤В╨╛╨╗╤М╨║╨╛ ╤Б╨╡╨╣╤З╨░╤Б.
      _pendingTikTokUsername = username;
      _retryingPendingConnect = false;

      // ╤Б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨╗╨╛╨║╨░╨╗╤М╨╜╨╛ (╨╜╨╡ ╨╜╨░ ╤Б╨╡╤А╨▓╨╡╤А╨╡), ╤З╤В╨╛╨▒╤Л ╨╜╨╡ ╨▒╤Л╨╗╨╛ ╨░╨▓╤В╨╛╨┐╨╛╨┐╤Л╤В╨╛╨║ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╤П ╨┐╤А╨╕ ╤Б╤В╨░╤А╤В╨╡
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kPrefLastTikTokUsername, username);

      _liveConnecting = true;
      _liveErrorText = null;
      _liveStatusText = 'Подключаемся к TikTok LIVE...';
      notifyListeners();

      // ╤Б╨╜╨░╤З╨░╨╗╨░ ╨│╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╜╨╛ ╨╛╤В╨║╨╗╤О╤З╨░╨╡╨╝╤Б╤П ╨╛╤В ╨▓╨╛╨╖╨╝╨╛╨╢╨╜╨╛╨│╨╛ ╨┐╤А╨╡╨┤╤Л╨┤╤Г╤Й╨╡╨│╨╛ LIVE
      try {
        await _ws.disconnectFromTikTok();
      } catch (_) {}

      // ╨┤╨░╤С╨╝ ╤Б╨╡╤А╨▓╨╡╤А╤Г ╨▓╤А╨╡╨╝╤П ╨╜╨░ disconnect, ╨╕╨╜╨░╤З╨╡ ╨╝╨╛╨╢╨╡╤В ╨┐╤А╨╕╨╗╨╡╤В╨╡╤В╤М offline ╨┐╨╛ ╤Б╤В╨░╤А╨╛╨╝╤Г ╨╜╨╕╨║╤Г
      await Future<void>.delayed(const Duration(milliseconds: 450));

      // ╨┐╨╛╨┤╨║╨╗╤О╤З╨░╨╡╨╝╤Б╤П ╨║ LIVE ╤З╨╡╤А╨╡╨╖ WS
      final success = await _ws.connectToTikTok(username);
      if (success) {
        _currentTikTokUsername = username;
        // ╨б╨▒╤А╨░╤Б╤Л╨▓╨░╨╡╨╝ ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╤Г ╤Б╤В╤А╨╕╨╝╨░ ╨┤╨╗╤П ╨╜╨╛╨▓╨╛╨│╨╛ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╤П
        _resetStreamStats();
        notifyListeners();
      }
      return success;
    } catch (e) {
      logDebug('Error connecting to TikTok: $e');
      _liveConnecting = false;
      _liveErrorText = _friendlyLiveErrorText(e.toString(), username: username);
      notifyListeners();
      return false;
    }
  }

  String? _extractUsernameFromText(String? text) {
    if (text == null || text.isEmpty) return null;
    final m = RegExp(r'@([A-Za-z0-9._-]+)').firstMatch(text);
    return m?.group(1);
  }
  
  Future<void> disconnectFromTikTok() async {
    try {
      if (_demoMode) {
        await stopDemoMode();
        return;
      }
      _manualLiveDisconnect = true;
      _sessionAutoReconnectLive = false;
      _cancelAutoReconnect();
      _pendingTikTokUsername = null;
      await _ws.disconnectFromTikTok();
      _tiktokConnected = false;
      _liveStatusText = 'Отключено от LIVE';
      notifyListeners();
    } catch (e) {
      logDebug('Error disconnecting from TikTok: $e');
    }
  }

  Future<void> setAutoConnectLive(bool enabled) async {
    _autoConnectLive = false;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kPrefAutoConnectLive, false);
    } catch (_) {}

    try {
      await _api.updateSettings(autoConnectLive: false);
    } catch (_) {}

    _cancelAutoReconnect();

    notifyListeners();
  }

  void _cancelAutoReconnect({bool resetAttempt = true, bool resetInFlight = true}) {
    _autoReconnectTimer?.cancel();
    _autoReconnectTimer = null;
    if (resetAttempt) _autoReconnectAttempt = 0;
    if (resetInFlight) _autoReconnectInFlight = false;
  }

  void _cancelWsReconnect({bool resetAttempt = true, bool resetInFlight = true}) {
    _wsReconnectTimer?.cancel();
    _wsReconnectTimer = null;
    if (resetAttempt) _wsReconnectAttempt = 0;
    if (resetInFlight) _wsReconnectInFlight = false;
  }

  void _startWsKeepAlive() {
    _wsKeepAliveTimer?.cancel();
    _wsKeepAliveTimer = Timer.periodic(const Duration(seconds: 20), (_) {
      if (!_wsConnected) return;
      try {
        _ws.ping();
      } catch (_) {}
    });
  }

  void _stopWsKeepAlive() {
    _wsKeepAliveTimer?.cancel();
    _wsKeepAliveTimer = null;
  }

  void _scheduleWsReconnect({bool immediate = false}) {
    if (_demoMode) return;
    final token = (_activeToken ?? '').trim();
    if (token.isEmpty) return;
    if (_wsConnected) return;
    if (_wsReconnectTimer != null) return;
    if (_wsReconnectInFlight) return;

    _wsReconnectAttempt += 1;
    final delay = immediate ? Duration.zero : _nextReconnectDelay(_wsReconnectAttempt);

    _wsReconnectTimer = Timer(delay, () async {
      _wsReconnectTimer = null;
      if (_wsConnected) return;

      _wsReconnectInFlight = true;
      try {
        _ws.connect(token);
        await Future<void>.delayed(const Duration(seconds: 2));
        if (!_wsConnected) {
          _scheduleWsReconnect();
        }
      } finally {
        _wsReconnectInFlight = false;
      }
    });
  }

  void _scheduleAutoReconnect({bool immediate = false}) {
    return;
  }

  Duration _nextReconnectDelay(int attempt) {
    // 1, 2, 5, 10, 20, 30, 60...
    if (attempt <= 1) return const Duration(seconds: 1);
    if (attempt == 2) return const Duration(seconds: 2);
    if (attempt == 3) return const Duration(seconds: 5);
    if (attempt == 4) return const Duration(seconds: 10);
    if (attempt == 5) return const Duration(seconds: 20);
    if (attempt == 6) return const Duration(seconds: 30);
    return const Duration(seconds: 60);
  }
  
  void updateTtsEnabled(bool enabled) {
    _ttsEnabled = enabled;
    _api.updateSettings(ttsEnabled: enabled);
    notifyListeners();
  }
  
  void updateGiftSoundsEnabled(bool enabled) {
    _giftSoundsEnabled = enabled;
    _api.updateSettings(giftSoundsEnabled: enabled);
    notifyListeners();
  }

  Future<bool> updateSilenceEnabled(bool enabled) async {
    final prev = _silenceEnabled;
    _silenceEnabled = enabled;
    notifyListeners();

    final ok = await _api.updateSettings(silenceEnabled: enabled);
    if (!ok) {
      _silenceEnabled = prev;
      notifyListeners();
    }
    return ok;
  }

  void updateTtsVolume(double value) {
    _ttsVolume = value;
    _api.updateSettings(ttsVolume: value);
    OverlayBridge.setVolumes(ttsVolume: _ttsVolume);
    notifyListeners();
  }

  void updateGiftsVolume(double value) {
    _giftsVolume = value;
    _api.updateSettings(giftVolume: value);
    OverlayBridge.setVolumes(giftsVolume: _giftsVolume);
    notifyListeners();
  }

  void updateTtsSpeed(double value) {
    _ttsSpeed = value;
    notifyListeners();
  }

  Future<void> stopTts() => _audio.stopTts();

  Future<void> stopGifts() => _audio.stopGifts();
  
  void updateGiftTtsAlongside(bool enabled) {
    _giftTtsAlongside = enabled;
    notifyListeners();
  }
  
  void clearEvents() {
    _events.clear();
    notifyListeners();
  }
  
  void _resetStreamStats() {
    _streamStats = {
      'totalDiamonds': 0,
      'totalGifts': 0,
      'totalViewers': 0,
      'totalChats': 0,
      'streamStart': DateTime.now(),
      'streamDuration': '0╨╝',
    };
  }
  
  List<Map<String, dynamic>> getFilteredEvents(String filter) {
    switch (filter) {
      case 'gifts':
        return _events.where((e) => e['type'] == 'gift').toList();
      case 'chat':
        return _events.where((e) => e['type'] == 'chat').toList();
      case 'viewers':
        return _events.where((e) => ['join', 'viewer_join', 'follow'].contains(e['type'])).toList();
      default:
        return _events;
    }
  }
  
  @override
  void dispose() {
    _autoReconnectTimer?.cancel();
    _wsReconnectTimer?.cancel();
    _wsKeepAliveTimer?.cancel();
    _overlayStopListener?.cancel();
    _ws.disconnect();
    super.dispose();
  }
}
