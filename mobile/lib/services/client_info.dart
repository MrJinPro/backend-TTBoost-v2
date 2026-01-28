import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';

class ClientInfo {
  static String platform = 'mobile';
  static String os = 'unknown';
  static String device = 'unknown';

  static bool _initialized = false;

  static String _osFromTargetPlatform() {
    if (kIsWeb) return 'web';
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return 'android';
      case TargetPlatform.iOS:
        return 'ios';
      case TargetPlatform.windows:
        return 'windows';
      case TargetPlatform.macOS:
        return 'macos';
      case TargetPlatform.linux:
        return 'linux';
      case TargetPlatform.fuchsia:
        return 'fuchsia';
    }
  }

  static String _clamp255(String value) {
    final v = value.trim();
    if (v.isEmpty) return 'unknown';
    if (v.length <= 255) return v;
    return v.substring(0, 255);
  }

  static Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    os = _osFromTargetPlatform();

    try {
      final plugin = DeviceInfoPlugin();
      if (kIsWeb) {
        final info = await plugin.webBrowserInfo;
        device = _clamp255(info.browserName.name);
        return;
      }

      switch (defaultTargetPlatform) {
        case TargetPlatform.android:
          final info = await plugin.androidInfo;
          final brand = (info.brand).trim();
          final model = (info.model).trim();
          final release = (info.version.release).trim();
          device = _clamp255([brand, model, if (release.isNotEmpty) 'Android $release']
              .where((x) => x.trim().isNotEmpty)
              .join(' '));
          return;
        case TargetPlatform.iOS:
          final info = await plugin.iosInfo;
          final model = (info.utsname.machine).trim();
          final system = (info.systemVersion).trim();
          device = _clamp255([if (model.isNotEmpty) model, if (system.isNotEmpty) 'iOS $system']
              .where((x) => x.trim().isNotEmpty)
              .join(' '));
          return;
        case TargetPlatform.windows:
          final info = await plugin.windowsInfo;
          device = _clamp255('Windows ${info.displayVersion}');
          return;
        case TargetPlatform.macOS:
          final info = await plugin.macOsInfo;
          device = _clamp255('macOS ${info.osRelease}');
          return;
        case TargetPlatform.linux:
          final info = await plugin.linuxInfo;
          device = _clamp255('Linux ${info.prettyName}');
          return;
        case TargetPlatform.fuchsia:
          device = 'fuchsia';
          return;
      }
    } catch (_) {
      // best-effort only
      device = 'unknown';
    }
  }

  static Map<String, String> baseHeaders({bool json = true}) {
    final headers = <String, String>{
      // backend uses this for tariff restrictions (mobile|desktop)
      'X-Client-Platform': platform,
      'X-Client-OS': os,
      'X-Client-Device': device,
    };
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }
}
