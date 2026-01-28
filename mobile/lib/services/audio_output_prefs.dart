import 'package:shared_preferences/shared_preferences.dart';

enum AudioOutputTarget {
  system,
  speaker,
  headphones,
  duplicateIfPossible,
}

class AudioOutputPrefs {
  static const String kPrefChatOutput = 'audio_output_chat';
  static const String kPrefGiftsOutput = 'audio_output_gifts';
  static const String kPrefPrioritySpeakerWhenLive = 'audio_output_priority_speaker_when_live';

  static AudioOutputTarget parseTarget(String? v) {
    switch ((v ?? '').trim()) {
      case 'speaker':
        return AudioOutputTarget.speaker;
      case 'headphones':
        return AudioOutputTarget.headphones;
      case 'duplicate':
        return AudioOutputTarget.duplicateIfPossible;
      case 'system':
      default:
        return AudioOutputTarget.system;
    }
  }

  static String serializeTarget(AudioOutputTarget t) {
    switch (t) {
      case AudioOutputTarget.speaker:
        return 'speaker';
      case AudioOutputTarget.headphones:
        return 'headphones';
      case AudioOutputTarget.duplicateIfPossible:
        return 'duplicate';
      case AudioOutputTarget.system:
      default:
        return 'system';
    }
  }

  static Future<AudioOutputTarget> getChatOutput() async {
    final prefs = await SharedPreferences.getInstance();
    return parseTarget(prefs.getString(kPrefChatOutput));
  }

  static Future<AudioOutputTarget> getGiftsOutput() async {
    final prefs = await SharedPreferences.getInstance();
    return parseTarget(prefs.getString(kPrefGiftsOutput));
  }

  static Future<bool> getPrioritySpeakerWhenLive() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(kPrefPrioritySpeakerWhenLive) ?? false;
  }

  static Future<void> setChatOutput(AudioOutputTarget t) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(kPrefChatOutput, serializeTarget(t));
  }

  static Future<void> setGiftsOutput(AudioOutputTarget t) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(kPrefGiftsOutput, serializeTarget(t));
  }

  static Future<void> setPrioritySpeakerWhenLive(bool v) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(kPrefPrioritySpeakerWhenLive, v);
  }
}
