import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../utils/log.dart';

/// Android Foreground Service wrapper.
///
/// Keeps the process alive in background (best-effort) and shows an ongoing
/// notification with quick actions (Stop TTS / Stop Gifts).
class ForegroundService {
  static const MethodChannel _channel = MethodChannel('ttboost/foreground_service');

  static bool get _isAndroid => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  static Future<void> start({String? tiktokUsername}) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod('start', <String, dynamic>{
        if (tiktokUsername != null) 'tiktokUsername': tiktokUsername,
      });
    } catch (e) {
      logDebug('ForegroundService.start error: $e');
    }
  }

  static Future<void> stop() async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod('stop');
    } catch (e) {
      logDebug('ForegroundService.stop error: $e');
    }
  }
}
