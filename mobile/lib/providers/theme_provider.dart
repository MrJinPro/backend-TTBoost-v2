import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeProvider extends ChangeNotifier {
  static const _key = 'ui_premium_enabled';

  bool _initialized = false;
  bool _premiumEnabled = true;

  bool get initialized => _initialized;

  /// Premium UI is supported only on Android.
  bool get premiumSupported => defaultTargetPlatform == TargetPlatform.android && !kIsWeb;

  bool get premiumEnabled => premiumSupported && _premiumEnabled;

  Future<void> initialize() async {
    if (_initialized) return;
    final prefs = await SharedPreferences.getInstance();
    _premiumEnabled = prefs.getBool(_key) ?? true;
    _initialized = true;
    notifyListeners();
  }

  Future<void> setPremiumEnabled(bool value) async {
    _premiumEnabled = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, value);
    notifyListeners();
  }
}
