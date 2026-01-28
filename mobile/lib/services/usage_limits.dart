import 'package:shared_preferences/shared_preferences.dart';

class UsageLimits {
  static const String _kChatTtsDate = 'usage_chat_tts_date';
  static const String _kChatTtsCount = 'usage_chat_tts_count';

  static String _todayKey() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  static Future<int> getChatTtsCountToday() async {
    final prefs = await SharedPreferences.getInstance();
    final today = _todayKey();
    final date = prefs.getString(_kChatTtsDate);
    if (date != today) return 0;
    return prefs.getInt(_kChatTtsCount) ?? 0;
  }

  static Future<bool> tryConsumeChatTts({int limit = 150}) async {
    final prefs = await SharedPreferences.getInstance();
    final today = _todayKey();
    final date = prefs.getString(_kChatTtsDate);

    if (date != today) {
      await prefs.setString(_kChatTtsDate, today);
      await prefs.setInt(_kChatTtsCount, 0);
    }

    final count = prefs.getInt(_kChatTtsCount) ?? 0;
    if (count >= limit) return false;

    await prefs.setInt(_kChatTtsCount, count + 1);
    return true;
  }
}
