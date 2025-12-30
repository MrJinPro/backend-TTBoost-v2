import 'package:flutter/foundation.dart';
import 'dart:io';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/ws_service.dart';
import '../services/api_service.dart';
import '../services/audio_playback_service.dart';
import '../services/foreground_service.dart';
import '../services/overlay_bridge.dart';
import '../services/usage_limits.dart';
import '../utils/log.dart';
import '../utils/premium_gate.dart';
import 'dart:async';

const _kPrefLastTikTokUsername = 'last_tiktok_username';
const _kPrefAutoConnectLive = 'auto_connect_live';

// Tikfinity-like behavior: auto-connect should not loop endlessly.
const int _kMaxAutoReconnectAttempts = 1;

/// Provider для управления WebSocket соединением и состоянием стрима
/// Предоставляет доступ к WS событиям, статусу подключения и управлению TikTok соединением
class WsProvider extends ChangeNotifier {
  final WsService _ws = WsService();
  ApiService _api;
  String? _activeToken;
  final AudioPlaybackService _audio = AudioPlaybackService();
  Timer? _overlayStopListener;

  bool _premiumEnabled = false;

  // TikTok connect control: avoid server-side auto-connect to stale username.
  bool _userInitiatedConnect = false;
  String? _pendingTikTokUsername;
  bool _blockAutoConnect = true;
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

    // Overlay: allow stopping currently playing audio from a small floating window (Android).
    _overlayStopListener = OverlayBridge.startStopListener(
      onStopTts: stopTts,
      onStopGifts: stopGifts,
      onSetTtsVolume: (v) async => updateTtsVolume(v),
      onSetGiftsVolume: (v) async => updateGiftsVolume(v),
      onTestTts: _testTtsFromOverlay,
    );
  }

  /// Обновляет сохранённый TikTok username локально (и для оверлея),
  /// чтобы UI сразу показывал новое значение после сохранения в профиле.
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
      // WS для событий стрима
      _ws.connect(jwtToken);

      // На сервере может оставаться активная сессия.
      // Чтобы приложение не было подключено к LIVE без явной команды пользователя,
      // отправляем disconnect сразу после поднятия WS.
      _blockAutoConnect = true;
      _userInitiatedConnect = false;
      _pendingTikTokUsername = null;
      () async {
        try {
          await _ws.disconnectFromTikTok();
        } catch (_) {}
      }();

      // подтянуть настройки (переключатели/громкости/текущий tiktok)
      _loadSettings();
    } else {
      _stopDemoInternal();
      _ws.disconnect();
      _wsConnected = false;
      _tiktokConnected = false;
      _currentTikTokUsername = null;
      _liveConnecting = false;
      _liveStatusText = null;
      _liveErrorText = null;
      _blockAutoConnect = true;
      _userInitiatedConnect = false;
      _pendingTikTokUsername = null;
      notifyListeners();
    }
  }

  Future<void> _loadSettings() async {
    try {
      final s = await _api.getSettings();
      if (s == null) return;
      _ttsEnabled = s['tts_enabled'] == true;
      _giftSoundsEnabled = s['gift_sounds_enabled'] == true;
      _autoConnectLive = s['auto_connect_live'] == true;
      _silenceEnabled = s['silence_enabled'] == true;
      _ttsVolume = (s['tts_volume'] as num?)?.toDouble() ?? _ttsVolume;
      _giftsVolume = (s['gifts_volume'] as num?)?.toDouble() ?? _giftsVolume;
      _voiceId = s['voice_id']?.toString().trim();

      await OverlayBridge.setVolumes(ttsVolume: _ttsVolume, giftsVolume: _giftsVolume);
      final fromServer = s['tiktok_username']?.toString();
      final prefs = await SharedPreferences.getInstance();

      // local override (если раньше сохраняли локально)
      if (prefs.containsKey(_kPrefAutoConnectLive)) {
        _autoConnectLive = prefs.getBool(_kPrefAutoConnectLive) ?? _autoConnectLive;
      } else {
        await prefs.setBool(_kPrefAutoConnectLive, _autoConnectLive);
      }

      if (fromServer != null && fromServer.trim().isNotEmpty) {
        _currentTikTokUsername = fromServer.trim();
        await prefs.setString(_kPrefLastTikTokUsername, _currentTikTokUsername!);
      } else {
        final local = prefs.getString(_kPrefLastTikTokUsername);
        if (local != null && local.trim().isNotEmpty) {
          _currentTikTokUsername = local.trim();
        }
      }
      _streamStats.putIfAbsent('streamStart', () => DateTime.now());
      notifyListeners();

      // Автоподключение: если включено и есть сохранённый ник — попробуем подключиться.
      if (_autoConnectLive && !_tiktokConnected) {
        final u = (_currentTikTokUsername ?? '').trim();
        if (u.isNotEmpty) {
          _manualLiveDisconnect = false;
          _scheduleAutoReconnect(immediate: true);
        }
      }
    } catch (e) {
      logDebug('Error loading settings: $e');
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
    _liveStatusText = 'Demo режим выключен';
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
      await ForegroundService.stop();
    } catch (_) {}

    _demoMode = true;
    _liveConnecting = false;
    _tiktokConnected = true;
    _liveErrorText = null;
    _liveStatusText = 'DEMO MODE: тестовые события без LIVE';

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
          'message': 'Привет! Это тестовый чат для ревью.',
        };
        ttsText = 'DemoUser: Привет! Это тестовый чат для ревью.';
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
        _cancelAutoReconnect();
      }

      // Если WS переподключился, а автоподключение включено — попробуем снова поднять LIVE.
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
    
    _ws.onEvent = (event) {
      _handleWsEvent(event);
    };
  }

  Future<void> _ensureAndroidNotificationPermission() async {
    if (kIsWeb) return;
    if (!Platform.isAndroid) return;
    try {
      final status = await Permission.notification.status;
      if (!status.isGranted) {
        await Permission.notification.request();
      }
    } catch (_) {
      // ignore
    }
  }

  Future<bool> _ensureAndroidNotificationPermissionGranted() async {
    if (kIsWeb) return true;
    if (!Platform.isAndroid) return true;
    try {
      var status = await Permission.notification.status;
      if (!status.isGranted) {
        status = await Permission.notification.request();
      }
      return status.isGranted;
    } catch (_) {
      return true;
    }
  }
  
  void _handleWsEvent(Map<String, dynamic> event) {
    final isDemoEvent = event['__demo'] == true;
    if (_demoMode && !isDemoEvent) {
      // In demo mode, keep UI deterministic and ignore real WS events.
      return;
    }
    // агрегируем лайки, чтобы лента не заспамливалась
    if (event['type'] == 'like' && _events.isNotEmpty) {
      final prev = _events.first;
      if (prev['type'] == 'like') {
        final prevRaw = prev['raw'] as Map<String, dynamic>?;
        final sameUser = (prevRaw?['user']?.toString() ?? '') == (event['user']?.toString() ?? '');
        if (sameUser) {
          final prevCount = (prevRaw?['count'] as num?)?.toInt() ?? 0;
          final newCount = (event['count'] as num?)?.toInt() ?? 0;
          final merged = Map<String, dynamic>.from(prevRaw ?? {});
          merged['count'] = prevCount + newCount;
          prev['raw'] = merged;
          prev['text'] = '${merged['user'] ?? 'Аноним'} поставил ${merged['count']} лайков';
          notifyListeners();
          return;
        }
      }
    }

    final mappedEvent = _mapEvent(event);
    
    // Добавляем событие в список
    _events.insert(0, mappedEvent);
    if (_events.length > 200) _events.removeLast();
    
    // Обновляем статистику стрима
    _updateStreamStats(event);
    
    // Обрабатываем статусные события
    if (event['type'] == 'status') {
      final wasLive = _tiktokConnected;
      final connected = event['connected'] == true;

      final message = event['message']?.toString();
      if (message != null && message.isNotEmpty) {
        _liveStatusText = message;
      }
      _liveErrorText = null;

      final usernameFromEvent = event['username']?.toString();
      final usernameFromMessage = _extractUsernameFromText(message);
      final incomingUsername = (usernameFromEvent ?? usernameFromMessage)?.trim();

      // Если сейчас идёт ручное подключение — держим ожидаемый ник.
      if (_pendingTikTokUsername != null && _pendingTikTokUsername!.trim().isNotEmpty) {
        _currentTikTokUsername = _pendingTikTokUsername;
      } else if (incomingUsername != null && incomingUsername.isNotEmpty) {
        _currentTikTokUsername = incomingUsername;
      }

      // Если сервер сам подключил к LIVE (старый ник), не принимаем это состояние и отключаемся.
      if (connected && (_blockAutoConnect || !_userInitiatedConnect)) {
        _tiktokConnected = false;
        _liveConnecting = false;
        () async {
          try {
            await _ws.disconnectFromTikTok();
          } catch (_) {}
        }();
      } else {
        _tiktokConnected = connected;
        if (connected) {
          _liveConnecting = false;
        }
      }

      // Audio routing: optional priority to speaker while LIVE.
      _audio.setLiveConnected(_demoMode ? true : _tiktokConnected);

      if (_tiktokConnected) {
        _manualLiveDisconnect = false;
        _cancelAutoReconnect();
      }

      // Автопереподключение: если сорвалось, будем пытаться вернуть LIVE.
      if (wasLive && !connected) {
        if (_autoConnectLive && !_manualLiveDisconnect) {
          _scheduleAutoReconnect();
        }
      }

      // Если пользователь запросил подключение к конкретному нику, а сервер подключил к другому — переподключаемся.
      if (_tiktokConnected && _pendingTikTokUsername != null) {
        final actual = (_currentTikTokUsername ?? incomingUsername ?? '').trim();
        final expected = _pendingTikTokUsername!.trim();
        if (actual.isNotEmpty && expected.isNotEmpty && actual.toLowerCase() != expected.toLowerCase()) {
          _tiktokConnected = false;
          _liveConnecting = true;
          () async {
            try {
              await _ws.disconnectFromTikTok();
              await Future<void>.delayed(const Duration(milliseconds: 450));
              await _ws.connectToTikTok(expected);
            } catch (_) {}
          }();
        } else {
          // успешное подключение к ожидаемому нику — снимаем блок
          _blockAutoConnect = false;
          _userInitiatedConnect = false;
          _pendingTikTokUsername = null;
          _retryingPendingConnect = false;
        }
      }

      // Android overlay permission: запрашиваем при первом успешном подключении к LIVE,
      // иначе оверлей не появится при сворачивании.
      if (!wasLive && _tiktokConnected) {
        () async {
          try {
            final supported = await OverlayBridge.isSupported();
            if (supported) {
              var granted = await OverlayBridge.hasPermission();
              if (!granted) {
                granted = await OverlayBridge.requestPermission();
              }
              if (granted) {
                // Если разрешение есть — показываем оверлей сразу.
                // Дальше HomeScreen будет показывать его при уходе в фон.
                await OverlayBridge.show();
              }
            }
          } catch (_) {}
        }();
      }

      // Android background reliability: foreground service + persistent notification.
      if (!wasLive && _tiktokConnected) {
        () async {
          final granted = await _ensureAndroidNotificationPermissionGranted();
          if (!granted) {
            _liveErrorText = 'Разрешите уведомления для NovaBoost, иначе управление в шторке не появится (Настройки → Уведомления).';
            notifyListeners();
            return;
          }

          // Clear last known FGS error (written by Android side into Flutter prefs).
          try {
            final prefs = await SharedPreferences.getInstance();
            await prefs.setString('fgs_last_error', '');
          } catch (_) {}

          await ForegroundService.start(tiktokUsername: _currentTikTokUsername);

          // If Android service failed early, it will write an error into prefs.
          try {
            final prefs = await SharedPreferences.getInstance();
            final err = prefs.getString('fgs_last_error');
            if (err != null && err.trim().isNotEmpty) {
              _liveErrorText = 'Android уведомление не запустилось: ${err.trim()}';
              notifyListeners();
            }
          } catch (_) {}
        }();
      } else if (wasLive && !_tiktokConnected) {
        () async {
          await ForegroundService.stop();
        }();
      }

      OverlayBridge.setStatus(
        wsConnected: _demoMode ? true : _wsConnected,
        liveConnected: _demoMode ? true : _tiktokConnected,
        tiktokUsername: _currentTikTokUsername,
      );
    }

    // Ошибки приходят отдельным событием.
    if (event['type'] == 'error') {
      final msg = event['message']?.toString();
      final expected = _pendingTikTokUsername?.trim();
      final incoming = _extractUsernameFromText(msg)?.trim();

      // Если ожидаем другой ник, а пришла ошибка по старому (обычно "offline") — игнорируем и ретраим один раз.
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
      _userInitiatedConnect = false;
      _pendingTikTokUsername = null;
      _retryingPendingConnect = false;
    }
    
    logDebug('WS Event: ${event['type']}');

    // Автовоспроизведение звука
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
        text = '$who зашёл в эфир';
        break;
      case 'viewer_join':
        category = 'Зритель';
        final who = _displayNameFromEvent(event);
        text = '$who зашёл в эфир';
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
        text = event['message']?.toString() ?? 'Неизвестная ошибка';
        break;
      case 'status':
        category = 'Статус';
        text = event['message']?.toString() ?? 'Изменение статуса';
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
    
    // Инициализируем статистику если не существует
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
        
        // Обновляем топ донатера
        final user = event['user']?.toString();
        if (user != null) {
          _streamStats['topGifter'] = user;
        }
        
        // Обновляем самый дорогой подарок
        final currentExpensive = _streamStats['mostExpensiveGift'] as Map<String, dynamic>?;
        if (currentExpensive == null || diamonds > (currentExpensive['diamonds'] ?? 0)) {
          _streamStats['mostExpensiveGift'] = {
            'name': event['gift_name']?.toString() ?? 'Подарок',
            'diamonds': diamonds,
            'user': user ?? 'Аноним',
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
    
    // Обновляем длительность стрима
    final start = _streamStats['streamStart'] as DateTime?;
    if (start != null) {
      final duration = DateTime.now().difference(start);
      final hours = duration.inHours;
      final minutes = duration.inMinutes % 60;
      _streamStats['streamDuration'] = hours > 0 ? '${hours}ч ${minutes}м' : '${minutes}м';
    }
  }
  
  // Методы управления
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

      // Явное действие пользователя: разрешаем подключение только сейчас.
      _userInitiatedConnect = true;
      _pendingTikTokUsername = username;
      _blockAutoConnect = false;
      _retryingPendingConnect = false;

      // сохраняем локально (не на сервере), чтобы не было автопопыток подключения при старте
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kPrefLastTikTokUsername, username);

      _liveConnecting = true;
      _liveErrorText = null;
      _liveStatusText = 'Подключаемся к TikTok Live…';
      notifyListeners();

      // сначала гарантированно отключаемся от возможного предыдущего LIVE
      try {
        await _ws.disconnectFromTikTok();
      } catch (_) {}

      // даём серверу время на disconnect, иначе может прилететь offline по старому нику
      await Future<void>.delayed(const Duration(milliseconds: 450));

      // подключаемся к LIVE через WS
      final success = await _ws.connectToTikTok(username);
      if (success) {
        _currentTikTokUsername = username;
        // Сбрасываем статистику стрима для нового подключения
        _resetStreamStats();
        notifyListeners();
      }
      return success;
    } catch (e) {
      logDebug('Error connecting to TikTok: $e');
      _liveConnecting = false;
      _liveErrorText = 'Ошибка подключения к LIVE';
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
      _blockAutoConnect = true;
      _userInitiatedConnect = false;
      _pendingTikTokUsername = null;
      await _ws.disconnectFromTikTok();
      await ForegroundService.stop();
      _tiktokConnected = false;
      _liveStatusText = 'Отключено от LIVE';
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

    // сохраняем на сервере (настройка профиля)
    try {
      await _api.updateSettings(autoConnectLive: enabled);
    } catch (_) {}

    if (!enabled) {
      _cancelAutoReconnect();
    } else {
      // если включили — пробуем подключиться
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
        // Ждём статус-событие от сервера, чтобы не зациклиться на "ещё не успели проставить _tiktokConnected".
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
      'streamDuration': '0м',
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