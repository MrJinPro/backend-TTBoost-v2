import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/spotify_service.dart';
import '../services/overlay_bridge.dart';

class SpotifyProvider extends ChangeNotifier {
  final SpotifyService _spotify = SpotifyService();

  bool _connected = false;
  bool _playing = false;
  String? _track;
  String? _artist;
  int? _volume;
  String? _error;

  Timer? _pollTimer;
  Timer? _overlayCmdTimer;

  bool get configured => _spotify.isConfigured;
  bool get connected => _connected;
  bool get playing => _playing;
  String? get track => _track;
  String? get artist => _artist;
  int? get volume => _volume;
  String? get error => _error;

  SpotifyProvider() {
    _init();
  }

  Future<void> _init() async {
    if (kIsWeb) return;

    try {
      final hasRt = await _spotify.hasRefreshToken();
      _connected = hasRt;
      await OverlayBridge.setSpotifyStatus(
        connected: _connected,
        isPlaying: false,
        track: null,
        artist: null,
        volumePercent: null,
      );

      if (_connected) {
        _startPolling();
        _startOverlayCommandListener();
      }
    } catch (_) {
      // ignore
    }
    notifyListeners();
  }

  Future<void> connect() async {
    _error = null;
    notifyListeners();

    if (!configured) {
      _error = 'Нужно задать SPOTIFY_CLIENT_ID (через --dart-define=SPOTIFY_CLIENT_ID=...)';
      notifyListeners();
      return;
    }

    if (kIsWeb) {
      _error = 'Подключение Spotify не поддерживается в Chrome/Web. Проверьте на Android.';
      notifyListeners();
      return;
    }

    try {
      await _spotify.connect();
      _connected = true;
      await OverlayBridge.setSpotifyStatus(
        connected: true,
        isPlaying: _playing,
        track: _track,
        artist: _artist,
        volumePercent: _volume,
      );

      _startPolling();
      _startOverlayCommandListener();
      await refreshNow();
    } catch (e) {
      _error = e.toString();
      _connected = false;
      await OverlayBridge.setSpotifyStatus(
        connected: false,
        isPlaying: false,
        track: null,
        artist: null,
        volumePercent: null,
      );
    }

    notifyListeners();
  }

  Future<void> disconnect() async {
    _error = null;
    try {
      await _spotify.disconnect();
    } catch (_) {}

    _connected = false;
    _playing = false;
    _track = null;
    _artist = null;
    _volume = null;

    _pollTimer?.cancel();
    _pollTimer = null;
    _overlayCmdTimer?.cancel();
    _overlayCmdTimer = null;

    await OverlayBridge.setSpotifyStatus(
      connected: false,
      isPlaying: false,
      track: null,
      artist: null,
      volumePercent: null,
    );

    notifyListeners();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      refreshNow();
    });
  }

  Future<void> refreshNow() async {
    if (!_connected) return;

    try {
      final playback = await _spotify.getCurrentPlayback();
      if (playback == null) {
        _playing = false;
        _track = null;
        _artist = null;
        _volume = null;
      } else {
        _playing = playback['is_playing'] == true;

        final item = playback['item'];
        if (item is Map) {
          _track = item['name']?.toString();
          final artists = item['artists'];
          if (artists is List && artists.isNotEmpty) {
            final a0 = artists.first;
            if (a0 is Map) {
              _artist = a0['name']?.toString();
            }
          }
        }

        final device = playback['device'];
        if (device is Map) {
          final v = device['volume_percent'];
          if (v is num) {
            _volume = v.toInt().clamp(0, 100);
          }
        }
      }

      await OverlayBridge.setSpotifyStatus(
        connected: _connected,
        isPlaying: _playing,
        track: _track,
        artist: _artist,
        volumePercent: _volume,
      );
      _error = null;
    } catch (e) {
      _error = e.toString();
    }

    notifyListeners();
  }

  Future<void> togglePlayPause() async {
    if (!_connected) return;
    _error = null;

    try {
      if (_playing) {
        await _spotify.pause();
      } else {
        await _spotify.play();
      }
      await refreshNow();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> next() async {
    if (!_connected) return;
    _error = null;
    try {
      await _spotify.next();
      await refreshNow();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> previous() async {
    if (!_connected) return;
    _error = null;
    try {
      await _spotify.previous();
      await refreshNow();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> setSpotifyVolume(int percent) async {
    if (!_connected) return;
    _error = null;
    try {
      await _spotify.setVolumePercent(percent);
      _volume = percent.clamp(0, 100);
      await OverlayBridge.setSpotifyStatus(
        connected: _connected,
        isPlaying: _playing,
        track: _track,
        artist: _artist,
        volumePercent: _volume,
      );
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  void _startOverlayCommandListener() {
    _overlayCmdTimer?.cancel();

    _overlayCmdTimer = Timer.periodic(const Duration(milliseconds: 300), (_) async {
      if (kIsWeb) return;
      if (!_connected) return;

      final prefs = await SharedPreferences.getInstance();
      try {
        await prefs.reload();
      } catch (_) {}

      final playPause = prefs.getBool(kPrefSpotifyCmdPlayPause) ?? false;
      final next = prefs.getBool(kPrefSpotifyCmdNext) ?? false;
      final prev = prefs.getBool(kPrefSpotifyCmdPrev) ?? false;
      final setVol = prefs.getBool(kPrefSpotifyCmdSetVolume) ?? false;

      if (playPause) {
        await prefs.setBool(kPrefSpotifyCmdPlayPause, false);
        await togglePlayPause();
      }

      if (next) {
        await prefs.setBool(kPrefSpotifyCmdNext, false);
        await this.next();
      }

      if (prev) {
        await prefs.setBool(kPrefSpotifyCmdPrev, false);
        await previous();
      }

      if (setVol) {
        final raw = prefs.getDouble(kPrefSpotifyCmdVolume) ??
            double.tryParse(prefs.getString(kPrefSpotifyCmdVolume) ?? '');
        await prefs.setBool(kPrefSpotifyCmdSetVolume, false);
        if (raw != null) {
          await setSpotifyVolume(raw.toInt());
        }
      }
    });
  }
}
