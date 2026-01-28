import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/audio_output_prefs.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';
import '../utils/premium_gate.dart';

class AudioOutputScreen extends StatefulWidget {
  const AudioOutputScreen({super.key});

  @override
  State<AudioOutputScreen> createState() => _AudioOutputScreenState();
}

class _AudioOutputScreenState extends State<AudioOutputScreen> {
  bool _loading = true;
  AudioOutputTarget _chat = AudioOutputTarget.system;
  AudioOutputTarget _gifts = AudioOutputTarget.system;
  bool _priorityWhenLive = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final chat = await AudioOutputPrefs.getChatOutput();
      final gifts = await AudioOutputPrefs.getGiftsOutput();
      final prio = await AudioOutputPrefs.getPrioritySpeakerWhenLive();
      if (!mounted) return;
      setState(() {
        _chat = chat;
        _gifts = gifts;
        _priorityWhenLive = prio;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  Future<void> _setChat(AudioOutputTarget v) async {
    setState(() => _chat = v);
    await AudioOutputPrefs.setChatOutput(v);
  }

  Future<void> _setGifts(AudioOutputTarget v) async {
    setState(() => _gifts = v);
    await AudioOutputPrefs.setGiftsOutput(v);
  }

  Future<void> _setPriority(bool v) async {
    setState(() => _priorityWhenLive = v);
    await AudioOutputPrefs.setPrioritySpeakerWhenLive(v);
  }

  void _showPremiumSnack() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Доступно в Premium')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isPremium = PremiumGate.isPremiumPlan(context.watch<AuthProvider>().plan);
    final effectiveChat = isPremium ? _chat : AudioOutputTarget.system;
    final effectiveGifts = isPremium ? _gifts : AudioOutputTarget.system;
    final effectivePriority = isPremium ? _priorityWhenLive : false;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Аудио вывод', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: const [
          HelpIcon(
            title: 'Аудио вывод',
            message:
                'Эти настройки позволяют (best-effort) выбирать, куда выводить звук (чат/подарки) и как вести себя во время LIVE.\n\nНа Android разделение маршрутов не всегда гарантируется — это зависит от устройства и прошивки.',
          ),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (!isPremium) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.cardBackground,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.cardBorder),
                      ),
                      child: Text(
                        'Смена источника звука и режим "Дублировать" доступны только в Premium.',
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  _sectionTitle(
                    'Озвучка чата',
                    helpTitle: 'Озвучка чата: куда выводить звук',
                    helpMessage:
                        'Выберите маршрут вывода звука для озвучки чата.\n\n«Системный» — как решит Android. «Динамик/Дублировать» — best-effort и доступны в Premium.',
                  ),
                  _radioCard(
                    groupValue: effectiveChat,
                    onChanged: (v) async {
                      if (!isPremium && v != AudioOutputTarget.system) {
                        _showPremiumSnack();
                        return;
                      }
                      await _setChat(v);
                    },
                    enabled: isPremium,
                  ),
                  const SizedBox(height: 16),
                  _sectionTitle(
                    'Озвучка подарков',
                    helpTitle: 'Озвучка подарков: куда выводить звук',
                    helpMessage:
                        'Выберите маршрут вывода звука для подарков.\n\nЕсли подарки отключены на «Панели», то звук всё равно не будет проигрываться.',
                  ),
                  _radioCard(
                    groupValue: effectiveGifts,
                    onChanged: (v) async {
                      if (!isPremium && v != AudioOutputTarget.system) {
                        _showPremiumSnack();
                        return;
                      }
                      await _setGifts(v);
                    },
                    enabled: isPremium,
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.cardBackground,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.cardBorder),
                    ),
                    child: SwitchListTile.adaptive(
                      contentPadding: EdgeInsets.zero,
                      value: effectivePriority,
                      secondary: const HelpIcon(
                        title: 'Приоритет динамика при LIVE',
                        message:
                            'Если включено, приложение будет пытаться выводить звук в динамик во время LIVE.\n\nЭто best-effort: некоторые Bluetooth-наушники/прошивки могут игнорировать настройку.',
                      ),
                      onChanged: isPremium
                          ? _setPriority
                          : (v) {
                              _showPremiumSnack();
                            },
                      title: Text(
                        'Приоритет динамика при LIVE',
                        style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
                      ),
                      subtitle: Text(
                        'Если включено, приложение будет пытаться вывести звук в динамик во время LIVE.\n'
                        'Не гарантируется на всех Bluetooth-наушниках и прошивках.',
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Важно: Android не всегда позволяет жёстко разделить маршруты (наушники/динамик) между приложениями. Режимы "Динамик" и "Дублировать" — best-effort.',
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _sectionTitle(String text, {required String helpTitle, required String helpMessage}) {
    return Row(
      children: [
        Text(text, style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
        const SizedBox(width: 8),
        HelpIcon(title: helpTitle, message: helpMessage),
      ],
    );
  }

  Widget _radioCard({
    required AudioOutputTarget groupValue,
    required Future<void> Function(AudioOutputTarget v) onChanged,
    required bool enabled,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        children: [
          RadioListTile<AudioOutputTarget>(
            value: AudioOutputTarget.system,
            groupValue: groupValue,
            onChanged: (v) => v == null ? null : onChanged(v),
            title: Text('Системный (по умолчанию)', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            subtitle: Text('Android сам решает, куда выводить звук', style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText)),
          ),
          const Divider(height: 1, color: AppColors.cardBorder),
          RadioListTile<AudioOutputTarget>(
            value: AudioOutputTarget.speaker,
            groupValue: groupValue,
            onChanged: enabled ? (v) => v == null ? null : onChanged(v) : null,
            title: Text('Динамик (best-effort)', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            subtitle: Text('Пытаемся принудительно вывести в динамик', style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText)),
          ),
          const Divider(height: 1, color: AppColors.cardBorder),
          RadioListTile<AudioOutputTarget>(
            value: AudioOutputTarget.headphones,
            groupValue: groupValue,
            onChanged: enabled ? (v) => v == null ? null : onChanged(v) : null,
            title: Text('Наушники', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            subtitle: Text('По сути = системный маршрут (если наушники подключены)', style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText)),
          ),
          const Divider(height: 1, color: AppColors.cardBorder),
          RadioListTile<AudioOutputTarget>(
            value: AudioOutputTarget.duplicateIfPossible,
            groupValue: groupValue,
            onChanged: enabled ? (v) => v == null ? null : onChanged(v) : null,
            title: Text('Дублировать (если возможно)', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            subtitle: Text('Экспериментально: пытаемся продублировать звук в динамик', style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText)),
          ),
        ],
      ),
    );
  }
}
