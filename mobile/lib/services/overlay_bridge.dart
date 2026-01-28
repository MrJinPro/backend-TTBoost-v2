import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

const kPrefWsConnected = 'overlay_ws_connected';
const kPrefLiveConnected = 'overlay_live_connected';
const kPrefStopTts = 'overlay_stop_tts';
const kPrefStopGifts = 'overlay_stop_gifts';
const kPrefUsername = 'overlay_tiktok_username';

const kPrefTtsVolume = 'overlay_tts_volume';
const kPrefGiftsVolume = 'overlay_gifts_volume';
const kPrefCmdTtsVolume = 'overlay_cmd_tts_volume';
const kPrefCmdGiftsVolume = 'overlay_cmd_gifts_volume';
const kPrefCmdSetTtsVolume = 'overlay_cmd_set_tts_volume';
const kPrefCmdSetGiftsVolume = 'overlay_cmd_set_gifts_volume';

const kPrefTestTts = 'overlay_test_tts';

// Spotify (overlay mini-player)
const kPrefSpotifyConnected = 'overlay_spotify_connected';
const kPrefSpotifyIsPlaying = 'overlay_spotify_is_playing';
const kPrefSpotifyTrack = 'overlay_spotify_track';
const kPrefSpotifyArtist = 'overlay_spotify_artist';
const kPrefSpotifyVolume = 'overlay_spotify_volume';

const kPrefSpotifyCmdPlayPause = 'overlay_spotify_cmd_play_pause';
const kPrefSpotifyCmdNext = 'overlay_spotify_cmd_next';
const kPrefSpotifyCmdPrev = 'overlay_spotify_cmd_prev';
const kPrefSpotifyCmdVolume = 'overlay_spotify_cmd_volume';
const kPrefSpotifyCmdSetVolume = 'overlay_spotify_cmd_set_volume';

class OverlayBridge {
  static bool get _isAndroid => !kIsWeb && Platform.isAndroid;

  static const MethodChannel _fgsChannel = MethodChannel('ttboost/foreground_service');

  static Future<bool> isSupported() async => _isAndroid;

  static Future<bool> hasPermission() async {
    if (!_isAndroid) return false;
    try {
      final status = await Permission.systemAlertWindow.status;
      return status.isGranted;
    } catch (_) {
      return false;
    }
  }

  static Future<bool> requestPermission() async {
    if (!_isAndroid) return false;
    try {
      final status = await Permission.systemAlertWindow.request();
      return status.isGranted;
    } catch (_) {
      return false;
    }
  }

  static Future<void> show() async {
    if (!_isAndroid) return;
    var granted = await hasPermission();
    if (!granted) {
      // SYSTEM_ALERT_WINDOW не является обычным runtime-permission.
      // На Android это открывает системный экран, где пользователь включает разрешение.
      granted = await requestPermission();
    }
    if (!granted) return;
    try {
      await _fgsChannel.invokeMethod('showOverlay');
    } catch (_) {}
  }

  static Future<void> hide() async {
    if (!_isAndroid) return;
    try {
      await _fgsChannel.invokeMethod('hideOverlay');
    } catch (_) {}
  }

  static Future<void> setStatus({
    required bool wsConnected,
    required bool liveConnected,
    String? tiktokUsername,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(kPrefWsConnected, wsConnected);
    await prefs.setBool(kPrefLiveConnected, liveConnected);
    if (tiktokUsername != null) {
      await prefs.setString(kPrefUsername, tiktokUsername);
    }
  }

  static Future<void> setVolumes({
    double? ttsVolume,
    double? giftsVolume,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (ttsVolume != null) {
      await prefs.setDouble(kPrefTtsVolume, ttsVolume.clamp(0, 100));
    }
    if (giftsVolume != null) {
      await prefs.setDouble(kPrefGiftsVolume, giftsVolume.clamp(0, 100));
    }
  }

  static Future<void> setSpotifyStatus({
    required bool connected,
    required bool isPlaying,
    String? track,
    String? artist,
    int? volumePercent,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(kPrefSpotifyConnected, connected);
    await prefs.setBool(kPrefSpotifyIsPlaying, isPlaying);
    await prefs.setString(kPrefSpotifyTrack, (track ?? '').trim());
    await prefs.setString(kPrefSpotifyArtist, (artist ?? '').trim());
    await prefs.setDouble(
      kPrefSpotifyVolume,
      (volumePercent ?? 0).clamp(0, 100).toDouble(),
    );
  }

  static Timer startStopListener({
    required Future<void> Function() onStopTts,
    required Future<void> Function() onStopGifts,
    Future<void> Function(double value)? onSetTtsVolume,
    Future<void> Function(double value)? onSetGiftsVolume,
    Future<void> Function()? onTestTts,
  }) {
    return Timer.periodic(const Duration(milliseconds: 300), (_) async {
      final prefs = await SharedPreferences.getInstance();

      // Android overlay writes into FlutterSharedPreferences directly.
      // SharedPreferences caches values in memory, so we must reload
      // to observe updates coming from the native service.
      if (_isAndroid) {
        try {
          await prefs.reload();
        } catch (_) {}
      }

      final stopTts = prefs.getBool(kPrefStopTts) ?? false;
      final stopGifts = prefs.getBool(kPrefStopGifts) ?? false;
      final setTts = prefs.getBool(kPrefCmdSetTtsVolume) ?? false;
      final setGifts = prefs.getBool(kPrefCmdSetGiftsVolume) ?? false;
      final testTts = prefs.getBool(kPrefTestTts) ?? false;

      if (stopTts) {
        await prefs.setBool(kPrefStopTts, false);
        await onStopTts();
      }

      if (stopGifts) {
        await prefs.setBool(kPrefStopGifts, false);
        await onStopGifts();
      }

      if (testTts && onTestTts != null) {
        await prefs.setBool(kPrefTestTts, false);
        await onTestTts();
      }

      if (setTts && onSetTtsVolume != null) {
        final v = _readDoubleOrString(prefs, kPrefCmdTtsVolume);
        await prefs.setBool(kPrefCmdSetTtsVolume, false);
        if (v != null) {
          await onSetTtsVolume(v);
        }
      }

      if (setGifts && onSetGiftsVolume != null) {
        final v = _readDoubleOrString(prefs, kPrefCmdGiftsVolume);
        await prefs.setBool(kPrefCmdSetGiftsVolume, false);
        if (v != null) {
          await onSetGiftsVolume(v);
        }
      }
    });
  }

  static double? _readDoubleOrString(SharedPreferences prefs, String key) {
    final d = prefs.getDouble(key);
    if (d != null) return d;
    final s = prefs.getString(key);
    if (s == null) return null;
    return double.tryParse(s);
  }
}
