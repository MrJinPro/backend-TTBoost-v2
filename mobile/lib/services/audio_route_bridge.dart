import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

class AudioRouteBridge {
  static const MethodChannel _channel = MethodChannel('ttboost/foreground_service');

  static bool get _isAndroid => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  /// Best-effort: temporarily force audio route to speaker.
  /// Returns a token that must be passed to [endSpeakerRoute].
  static Future<int?> beginSpeakerRoute() async {
    if (!_isAndroid) return null;
    try {
      final token = await _channel.invokeMethod<dynamic>('audioRouteBegin', {
        'route': 'speaker',
      });
      if (token is int) return token;
      if (token is num) return token.toInt();
      return null;
    } catch (_) {
      return null;
    }
  }

  static Future<void> endSpeakerRoute(int token) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('audioRouteEnd', {
        'token': token,
      });
    } catch (_) {}
  }

  /// Best-effort: play a URL "through speaker" using Android-side player.
  /// This is used only for the experimental "duplicate" mode.
  static Future<void> playOnSpeaker({required String url, required double volume}) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('speakerPlayUrl', {
        'url': url,
        'volume': volume,
      });
    } catch (_) {}
  }

  static Future<void> stopSpeakerPlayback() async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('speakerStop', {});
    } catch (_) {}
  }
}
