import 'dart:async';
import 'dart:collection';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';

import 'audio_output_prefs.dart';
import 'audio_route_bridge.dart';

enum AudioChannel {
  tts,
  gifts,
  join,
}

class _AudioItem {
  final String url;
  final double volume;
  final double? rate;
  final bool isTts;

  const _AudioItem({
    required this.url,
    required this.volume,
    required this.isTts,
    this.rate,
  });
}

class AudioPlaybackService {
  // 3 независимых канала, каждый со своей очередью и плеером:
  // - tts: озвучка чата
  // - gifts: звуки подарков
  // - join: алёрты входа зрителей (звук и/или tts)
  // Каналы могут играть параллельно, внутри канала — строгий FIFO.
  final Map<AudioChannel, AudioPlayer> _players = {
    AudioChannel.tts: AudioPlayer(),
    AudioChannel.gifts: AudioPlayer(),
    AudioChannel.join: AudioPlayer(),
  };

  final Map<AudioChannel, Queue<_AudioItem>> _queues = {
    AudioChannel.tts: Queue<_AudioItem>(),
    AudioChannel.gifts: Queue<_AudioItem>(),
    AudioChannel.join: Queue<_AudioItem>(),
  };

  final Map<AudioChannel, bool> _pumping = {
    AudioChannel.tts: false,
    AudioChannel.gifts: false,
    AudioChannel.join: false,
  };

  final Map<AudioChannel, int> _gen = {
    AudioChannel.tts: 0,
    AudioChannel.gifts: 0,
    AudioChannel.join: 0,
  };

  static const Duration _itemSafetyTimeout = Duration(seconds: 120);
  static const int _maxQueueLength = 60;

  AudioOutputTarget _chatOutput = AudioOutputTarget.system;
  AudioOutputTarget _giftsOutput = AudioOutputTarget.system;
  bool _prioritySpeakerWhenLive = false;
  bool _liveConnected = false;
  bool _premiumEnabled = false;
  DateTime? _lastSettingsLoadAt;

  AudioPlaybackService() {
    for (final p in _players.values) {
      p.setReleaseMode(ReleaseMode.stop);
    }
  }

  void setLiveConnected(bool v) {
    _liveConnected = v;
  }

  void setPremiumEnabled(bool v) {
    _premiumEnabled = v;
  }

  Future<void> reloadOutputSettings() async {
    await _ensureSettingsLoaded();
  }

  Future<void> _ensureSettingsLoaded() async {
    final now = DateTime.now();
    final last = _lastSettingsLoadAt;
    if (last != null && now.difference(last) < const Duration(seconds: 1)) {
      return;
    }
    try {
      _chatOutput = await AudioOutputPrefs.getChatOutput();
      _giftsOutput = await AudioOutputPrefs.getGiftsOutput();
      _prioritySpeakerWhenLive = await AudioOutputPrefs.getPrioritySpeakerWhenLive();
    } catch (_) {
      // keep defaults
    }
    _lastSettingsLoadAt = now;
  }

  Future<void> playTts({required String url, required double volume, double rate = 1.0}) async {
    await _enqueue(
      AudioChannel.tts,
      _AudioItem(
        url: url,
        volume: _clamp01(volume),
        isTts: true,
        rate: rate,
      ),
    );
  }

  Future<void> playGift({required String url, required double volume}) async {
    await _enqueue(
      AudioChannel.gifts,
      _AudioItem(
        url: url,
        volume: _clamp01(volume),
        isTts: false,
      ),
    );
  }

  Future<void> playJoinTts({required String url, required double volume, double rate = 1.0}) async {
    await _enqueue(
      AudioChannel.join,
      _AudioItem(
        url: url,
        volume: _clamp01(volume),
        isTts: true,
        rate: rate,
      ),
    );
  }

  Future<void> playJoinSound({required String url, required double volume}) async {
    await _enqueue(
      AudioChannel.join,
      _AudioItem(
        url: url,
        volume: _clamp01(volume),
        isTts: false,
      ),
    );
  }

  Future<void> stopTts() async {
    await _stopChannel(AudioChannel.tts);
    // По смыслу "Stop TTS" — стопаем и join-tts, чтобы не висело долгое приветствие.
    await _stopChannel(AudioChannel.join);
  }

  Future<void> stopGifts() async {
    await _stopChannel(AudioChannel.gifts);
  }

  Future<void> _stopChannel(AudioChannel ch) async {
    final q = _queues[ch];
    q?.clear();
    _gen[ch] = (_gen[ch] ?? 0) + 1;
    try {
      await _players[ch]?.stop();
    } catch (_) {}

    // If we were duplicating via Android-side speaker player, stop it too.
    try {
      await AudioRouteBridge.stopSpeakerPlayback();
    } catch (_) {}
  }

  Future<void> _enqueue(AudioChannel ch, _AudioItem item) async {
    final cleanUrl = item.url.trim();
    if (cleanUrl.isEmpty) return;
    final q = _queues[ch]!;
    q.add(
      _AudioItem(
        url: cleanUrl,
        volume: _clamp01(item.volume),
        isTts: item.isTts,
        rate: item.rate,
      ),
    );
    // ограничиваем рост очереди (на бурстах подарков)
    while (q.length > _maxQueueLength) {
      q.removeFirst();
    }
    _pump(ch);
  }

  void _pump(AudioChannel ch) {
    if (_pumping[ch] == true) return;
    _pumping[ch] = true;
    () async {
      final player = _players[ch]!;
      final q = _queues[ch]!;
      try {
        while (q.isNotEmpty) {
          await _ensureSettingsLoaded();
          final expectedGen = _gen[ch] ?? 0;
          final item = q.removeFirst();

          final target = _effectiveTarget(item.isTts);
          if (target == AudioOutputTarget.duplicateIfPossible) {
            // Experimental: keep normal playback (usually goes to BT/system route)
            // and additionally ask Android to try playing same URL via speaker.
            await AudioRouteBridge.playOnSpeaker(url: item.url, volume: item.volume);
          }

          int? speakerToken;
          try {
            if (target == AudioOutputTarget.speaker) {
              speakerToken = await AudioRouteBridge.beginSpeakerRoute();
            }
            await player.setVolume(item.volume);
            if (item.rate != null) {
              try {
                await player.setPlaybackRate(item.rate!);
              } catch (_) {
                // не все платформы поддерживают rate
              }
            }
            // WebAudio иногда не может определить формат, если сервер отдаёт неверный/пустой Content-Type.
            // Подсказываем браузеру MP3 mimeType на web.
            await player.play(
              kIsWeb
                  ? UrlSource(item.url, mimeType: 'audio/mpeg')
                  : UrlSource(item.url),
            );
            await player.onPlayerComplete.first.timeout(_itemSafetyTimeout, onTimeout: () {});
            if ((_gen[ch] ?? 0) != expectedGen) {
              // channel was stopped/restarted
              break;
            }
          } catch (_) {
            // skip item
            if ((_gen[ch] ?? 0) != expectedGen) {
              break;
            }
          } finally {
            if (speakerToken != null) {
              await AudioRouteBridge.endSpeakerRoute(speakerToken);
            }
          }
        }
      } finally {
        _pumping[ch] = false;
      }
    }();
  }

  AudioOutputTarget _effectiveTarget(bool isTts) {
    if (_premiumEnabled && _prioritySpeakerWhenLive && _liveConnected) {
      return AudioOutputTarget.speaker;
    }
    final t = isTts ? _chatOutput : _giftsOutput;
    // "headphones" is currently treated as "system" (Android decides the route).
    if (t == AudioOutputTarget.headphones) return AudioOutputTarget.system;

    if (!_premiumEnabled) {
      if (t == AudioOutputTarget.speaker || t == AudioOutputTarget.duplicateIfPossible) {
        return AudioOutputTarget.system;
      }
    }
    return t;
  }

  double _clamp01(double v) {
    if (v.isNaN) return 0;
    if (v < 0) return 0;
    if (v > 1) return 1;
    return v;
  }
}
