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

// Tikfinity-like behavior: auto-connect should not loop endlessly.
const int _kMaxAutoReconnectAttempts = 1;

/// Provider ╨┤╨╗╤П ╤Г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╤П WebSocket ╤Б╨╛╨╡╨┤╨╕╨╜╨╡╨╜╨╕╨╡╨╝ ╨╕ ╤Б╨╛╤Б╤В╨╛╤П╨╜╨╕╨╡╨╝ ╤Б╤В╤А╨╕╨╝╨░
/// ╨Я╤А╨╡╨┤╨╛╤Б╤В╨░╨▓╨╗╤П╨╡╤В ╨┤╨╛╤Б╤В╤Г╨┐ ╨║ WS ╤Б╨╛╨▒╤Л╤В╨╕╤П╨╝, ╤Б╤В╨░╤В╤Г╤Б╤Г ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╤П ╨╕ ╤Г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╤О TikTok ╤Б╨╛╨╡╨┤╨╕╨╜╨╡╨╜╨╕╨╡╨╝
class WsProvider extends ChangeNotifier {
  final WsService _ws = WsService();
  ApiService _api;
  String? _activeToken;
  final AudioPlaybackService _audio = AudioPlaybackService();
  Timer? _overlayStopListener;

  bool _premiumEnabled = false;

  String? _pendingTikTokUsername;
  bool _retryingPendingConnect = false;

  bool _autoConnectLive = false;
  bool _manualLiveDisconnect = false;
  Timer? _autoReconnectTimer;
  int _autoReconnectAttempt = 0;
  bool _autoReconnectInFlight = false;
  
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
    );
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
      // WS ╨┤╨╗╤П ╤Б╨╛╨▒╤Л╤В╨╕╨╣ ╤Б╤В╤А╨╕╨╝╨░
      _ws.connect(jwtToken);

      // ╨Э╨░ ╤Б╨╡╤А╨▓╨╡╤А╨╡ ╨╝╨╛╨╢╨╡╤В ╨╛╤Б╤В╨░╨▓╨░╤В╤М╤Б╤П ╨░╨║╤В╨╕╨▓╨╜╨░╤П ╤Б╨╡╤Б╤Б╨╕╤П.
      // ╨з╤В╨╛╨▒╤Л ╨┐╤А╨╕╨╗╨╛╨╢╨╡╨╜╨╕╨╡ ╨╜╨╡ ╨▒╤Л╨╗╨╛ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╛ ╨║ LIVE ╨▒╨╡╨╖ ╤П╨▓╨╜╨╛╨╣ ╨║╨╛╨╝╨░╨╜╨┤╤Л ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П,
      // ╨╛╤В╨┐╤А╨░╨▓╨╗╤П╨╡╨╝ disconnect ╤Б╤А╨░╨╖╤Г ╨┐╨╛╤Б╨╗╨╡ ╨┐╨╛╨┤╨╜╤П╤В╨╕╤П WS.
      _pendingTikTokUsername = null;
      () async {
        try {
          await _ws.disconnectFromTikTok();
        } catch (_) {}
      }();
    } else {
      // Logout / token cleared
      _ws.disconnect();
      _wsConnected = false;
      _tiktokConnected = false;
      _liveConnecting = false;
      _liveStatusText = null;
      _liveErrorText = null;
      _cancelAutoReconnect();
      _syncOverlayStatus();
      notifyListeners();
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
    _liveStatusText = 'Demo ╤А╨╡╨╢╨╕╨╝ ╨▓╤Л╨║╨╗╤О╤З╨╡╨╜';
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
    _liveStatusText = 'DEMO MODE: ╤В╨╡╤Б╤В╨╛╨▓╤Л╨╡ ╤Б╨╛╨▒╤Л╤В╨╕╤П ╨▒╨╡╨╖ LIVE';

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
        ttsText = '╨Ъ ╨╜╨░╨╝ ╨┐╤А╨╕╤Б╨╛╨╡╨┤╨╕╨╜╨╕╨╗╤Б╤П ╨╖╤А╨╕╤В╨╡╨╗╤М.';
        break;
      case 1:
        event = {
          '__demo': true,
          'type': 'chat',
          'user': 'DemoUser',
          'message': '╨Я╤А╨╕╨▓╨╡╤В! ╨н╤В╨╛ ╤В╨╡╤Б╤В╨╛╨▓╤Л╨╣ ╤З╨░╤В ╨┤╨╗╤П ╤А╨╡╨▓╤М╤О.',
        };
        ttsText = 'DemoUser: ╨Я╤А╨╕╨▓╨╡╤В! ╨н╤В╨╛ ╤В╨╡╤Б╤В╨╛╨▓╤Л╨╣ ╤З╨░╤В ╨┤╨╗╤П ╤А╨╡╨▓╤М╤О.';
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
        ttsText = 'DemoFan ╨╛╤В╨┐╤А╨░╨▓╨╕╨╗ ╨┐╨╛╨┤╨░╤А╨╛╨║ Rose.';
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

      const text = 'NovaBoost Mobile ╤Б╨╡╤А╨▓╨╕╤Б ╨┤╨╗╤П ╤Б╤В╤А╨╕╨╝╨╡╤А╨╛╨▓!';
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
        _cancelAutoReconnect();
      }

      if (connected) {
        if (!_demoMode && _autoConnectLive && !_manualLiveDisconnect && !_tiktokConnected) {
          final u = (_currentTikTokUsername ?? '').trim();
          if (u.isNotEmpty) {
            _scheduleAutoReconnect(immediate: true);
          }
        }
      }

      _syncOverlayStatus();
      notifyListeners();
    };

    _ws.onEvent = _handleWsEvent;

    () async {
      try {
        final prefs = await SharedPreferences.getInstance();
        _currentTikTokUsername = prefs.getString(_kPrefLastTikTokUsername);
        _autoConnectLive = prefs.getBool(_kPrefAutoConnectLive) ?? false;
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

  void _handleWsEvent(Map<String, dynamic> rawEvent) {
    final event = Map<String, dynamic>.from(rawEvent);

    // Status updates from backend
    if (event['type']?.toString() == 'status') {
      final connected = event['connected'] == true;
      final msg = event['message']?.toString();
      final u = event['tiktok_username']?.toString().trim();
      if (u != null && u.isNotEmpty) {
        _currentTikTokUsername = u.replaceAll('@', '');
      }

      _tiktokConnected = connected;
      _liveStatusText = msg;
      _liveErrorText = null;
      _liveConnecting = false;

      if (connected) {
        _manualLiveDisconnect = false;
        _pendingTikTokUsername = null;
        _retryingPendingConnect = false;
        _cancelAutoReconnect();
        _resetStreamStats();
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
        _liveErrorText = msg;
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
    return '╨Р╨╜╨╛╨╜╨╕╨╝';
  }

  Future<void> _autoPlay(Map<String, dynamic> event) async {
    try {
      final type = event['type']?.toString();
      final isJoin = type == 'viewer_join' || type == 'join';

      final ttsUrl = event['tts_url']?.toString();
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

      final soundUrl = event['sound_url']?.toString();
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
  
  Map<String, dynamic> _mapEvent(Map<String, dynamic> event) {
    final type = event['type']?.toString() ?? 'unknown';
    final timestamp = DateTime.now();
    
    String category;
    String text;
    
    switch (type) {
      case 'chat':
        category = '╨з╨░╤В';
        final user = event['user']?.toString() ?? '╨Р╨╜╨╛╨╜╨╕╨╝';
        final message = event['message']?.toString() ?? '';
        text = '$user: $message';
        break;
      case 'gift':
        category = '╨Я╨╛╨┤╨░╤А╨╛╨║';
        final user = event['user']?.toString() ?? '╨Р╨╜╨╛╨╜╨╕╨╝';
        final giftName = event['gift_name']?.toString() ?? '╨Я╨╛╨┤╨░╤А╨╛╨║';
        final count = event['count']?.toString() ?? '1';
        text = '$user ╨╛╤В╨┐╤А╨░╨▓╨╕╨╗ $giftName (x$count)';
        break;
      case 'join':
        category = '╨Ч╤А╨╕╤В╨╡╨╗╤М';
        final who = _displayNameFromEvent(event);
        text = '$who ╨╖╨░╤И╤С╨╗ ╨▓ ╤Н╤Д╨╕╤А';
        break;
      case 'viewer_join':
        category = '╨Ч╤А╨╕╤В╨╡╨╗╤М';
        final who = _displayNameFromEvent(event);
        text = '$who ╨╖╨░╤И╤С╨╗ ╨▓ ╤Н╤Д╨╕╤А';
        break;
      case 'follow':
        category = '╨Я╨╛╨┤╨┐╨╕╤Б╨║╨░';
        final user = event['user']?.toString() ?? '╨Р╨╜╨╛╨╜╨╕╨╝';
        text = '$user ╨┐╨╛╨┤╨┐╨╕╤Б╨░╨╗╤Б╤П';
        break;
      case 'like':
        category = '╨Ы╨░╨╣╨║';
        final user = event['user']?.toString() ?? '╨Р╨╜╨╛╨╜╨╕╨╝';
        final count = event['count']?.toString() ?? '1';
        text = '$user ╨┐╨╛╤Б╤В╨░╨▓╨╕╨╗ $count ╨╗╨░╨╣╨║╨╛╨▓';
        break;
      case 'error':
        category = '╨Ю╤И╨╕╨▒╨║╨░';
        text = event['message']?.toString() ?? '╨Э╨╡╨╕╨╖╨▓╨╡╤Б╤В╨╜╨░╤П ╨╛╤И╨╕╨▒╨║╨░';
        break;
      case 'status':
        category = '╨б╤В╨░╤В╤Г╤Б';
        text = event['message']?.toString() ?? '╨Ш╨╖╨╝╨╡╨╜╨╡╨╜╨╕╨╡ ╤Б╤В╨░╤В╤Г╤Б╨░';
        break;
      default:
        category = '╨б╨╛╨▒╤Л╤В╨╕╨╡';
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
      _cancelAutoReconnect(
        resetAttempt: !fromAutoReconnect,
        resetInFlight: !fromAutoReconnect,
      );

      // ╨п╨▓╨╜╨╛╨╡ ╨┤╨╡╨╣╤Б╤В╨▓╨╕╨╡ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤П: ╤А╨░╨╖╤А╨╡╤И╨░╨╡╨╝ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╨╡ ╤В╨╛╨╗╤М╨║╨╛ ╤Б╨╡╨╣╤З╨░╤Б.
      _pendingTikTokUsername = username;
      _retryingPendingConnect = false;

      // ╤Б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨╗╨╛╨║╨░╨╗╤М╨╜╨╛ (╨╜╨╡ ╨╜╨░ ╤Б╨╡╤А╨▓╨╡╤А╨╡), ╤З╤В╨╛╨▒╤Л ╨╜╨╡ ╨▒╤Л╨╗╨╛ ╨░╨▓╤В╨╛╨┐╨╛╨┐╤Л╤В╨╛╨║ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╤П ╨┐╤А╨╕ ╤Б╤В╨░╤А╤В╨╡
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kPrefLastTikTokUsername, username);

      _liveConnecting = true;
      _liveErrorText = null;
      _liveStatusText = '╨Я╨╛╨┤╨║╨╗╤О╤З╨░╨╡╨╝╤Б╤П ╨║ TikTok LiveтАж';
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
      _liveErrorText = '╨Ю╤И╨╕╨▒╨║╨░ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╡╨╜╨╕╤П ╨║ LIVE';
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
      _cancelAutoReconnect();
      _pendingTikTokUsername = null;
      await _ws.disconnectFromTikTok();
      _tiktokConnected = false;
      _liveStatusText = '╨Ю╤В╨║╨╗╤О╤З╨╡╨╜╨╛ ╨╛╤В LIVE';
      notifyListeners();
    } catch (e) {
      logDebug('Error disconnecting from TikTok: $e');
    }
  }

  Future<void> setAutoConnectLive(bool enabled) async {
    _autoConnectLive = enabled;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kPrefAutoConnectLive, enabled);
    } catch (_) {}

    // ╤Б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨╜╨░ ╤Б╨╡╤А╨▓╨╡╤А╨╡ (╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨░ ╨┐╤А╨╛╤Д╨╕╨╗╤П)
    try {
      await _api.updateSettings(autoConnectLive: enabled);
    } catch (_) {}

    if (!enabled) {
      _cancelAutoReconnect();
    } else {
      // ╨╡╤Б╨╗╨╕ ╨▓╨║╨╗╤О╤З╨╕╨╗╨╕ тАФ ╨┐╤А╨╛╨▒╤Г╨╡╨╝ ╨┐╨╛╨┤╨║╨╗╤О╤З╨╕╤В╤М╤Б╤П
      _manualLiveDisconnect = false;
      // Reset attempt counter so enabling the toggle always tries once.
      _cancelAutoReconnect();
      final u = (_currentTikTokUsername ?? '').trim();
      if (u.isNotEmpty && !_tiktokConnected) {
        _scheduleAutoReconnect(immediate: true);
      }
    }

    notifyListeners();
  }

  void _cancelAutoReconnect({bool resetAttempt = true, bool resetInFlight = true}) {
    _autoReconnectTimer?.cancel();
    _autoReconnectTimer = null;
    if (resetAttempt) _autoReconnectAttempt = 0;
    if (resetInFlight) _autoReconnectInFlight = false;
  }

  void _scheduleAutoReconnect({bool immediate = false}) {
    if (_demoMode) return;
    if (_autoReconnectTimer != null) return;
    if (_autoReconnectInFlight) return;
    if (!_wsConnected) return;
    if (_tiktokConnected) return;
    if (_manualLiveDisconnect) return;
    if (!_autoConnectLive) return;

    final u = (_currentTikTokUsername ?? '').trim();
    if (u.isEmpty) return;

    // Do not spam: only one auto attempt per failure.
    if (_autoReconnectAttempt >= _kMaxAutoReconnectAttempts) return;
    _autoReconnectAttempt += 1;

    final delay = immediate ? Duration.zero : _nextReconnectDelay(_autoReconnectAttempt);

    _autoReconnectTimer = Timer(delay, () async {
      _autoReconnectTimer = null;
      if (!_autoConnectLive || _manualLiveDisconnect || _tiktokConnected) return;
      if (!_wsConnected) return;

      _autoReconnectInFlight = true;
      try {
        await connectToTikTok(u, fromAutoReconnect: true);
        // ╨Ц╨┤╤С╨╝ ╤Б╤В╨░╤В╤Г╤Б-╤Б╨╛╨▒╤Л╤В╨╕╨╡ ╨╛╤В ╤Б╨╡╤А╨▓╨╡╤А╨░, ╤З╤В╨╛╨▒╤Л ╨╜╨╡ ╨╖╨░╤Ж╨╕╨║╨╗╨╕╤В╤М╤Б╤П ╨╜╨░ "╨╡╤Й╤С ╨╜╨╡ ╤Г╤Б╨┐╨╡╨╗╨╕ ╨┐╤А╨╛╤Б╤В╨░╨▓╨╕╤В╤М _tiktokConnected".
        await Future<void>.delayed(const Duration(seconds: 2));
      } finally {
        _autoReconnectInFlight = false;
      }
    });
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
    _overlayStopListener?.cancel();
    _ws.disconnect();
    super.dispose();
  }
}
