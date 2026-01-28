import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ws_provider.dart';
import '../providers/auth_provider.dart';
import '../services/overlay_bridge.dart';
import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _connecting = false;
  final Map<String, String?> _tiktokAvatarCache = {};
  final Map<String, Future<String?>> _tiktokAvatarInFlight = {};

  Future<String?> _getTikTokAvatarUrl(String username) {
    final u = username.trim().replaceAll('@', '');
    if (u.isEmpty) return Future.value(null);

    if (_tiktokAvatarCache.containsKey(u)) {
      return Future.value(_tiktokAvatarCache[u]);
    }

    return _tiktokAvatarInFlight.putIfAbsent(u, () async {
      try {
        final auth = context.read<AuthProvider>();
        final m = await auth.apiService.getTikTokProfile(username: u);
        final url = m?['avatar_url']?.toString().trim();
        final normalized = (url != null && url.isNotEmpty) ? url : null;
        _tiktokAvatarCache[u] = normalized;
        return normalized;
      } catch (_) {
        _tiktokAvatarCache[u] = null;
        return null;
      } finally {
        _tiktokAvatarInFlight.remove(u);
      }
    });
  }

  @override
  void dispose() {
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<WsProvider>(
      builder: (context, ws, _) {
        final auth = context.watch<AuthProvider>();
        final live = ws.tiktokConnected;
        final current = ws.currentTikTokUsername;
        final events = ws.events;
        final isDemoAccount = (auth.username ?? '').trim().toLowerCase() == 'demogoogle';
        final profileTikTok = (auth.tiktokUsername ?? '').trim();
        final effectiveUsername = (current?.trim().isNotEmpty == true ? current!.trim() : profileTikTok).replaceAll('@', '').trim();

        return Scaffold(
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildLiveStatusCard(live: live, currentUsername: effectiveUsername.isNotEmpty ? effectiveUsername : null, ws: ws),
                  const SizedBox(height: 16),
                  if (isDemoAccount) ...[
                    _buildDemoControls(ws, auth.username ?? ''),
                    const SizedBox(height: 16),
                  ],
                  _buildQuickToggles(ws),
                  const SizedBox(height: 16),
                  _buildEmergencyControls(ws),
                  const SizedBox(height: 16),
                  _buildRecentEvents(events, ws),
                ],
              ),
            ),
          ),
        );
      },
    );

  }

  Widget _buildDemoControls(WsProvider ws, String accountUsername) {
    final enabled = ws.demoMode;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Demo режим (для ревью)', style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
          const SizedBox(height: 8),
          Text(
            enabled ? 'Включен: генерируются тестовые события' : 'Выключен: можно включить тестовые события без LIVE',
            style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () async {
                if (enabled) {
                  await ws.stopDemoMode();
                  return;
                }
                final ok = await ws.startDemoMode(accountUsername: accountUsername);
                if (!ok && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Demo режим доступен только для DemoGoogle')),
                  );
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: enabled ? AppColors.accentRed : AppColors.accentGreen,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: Text(enabled ? 'Выключить DEMO' : 'Включить DEMO'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLiveStatusCard({
    required bool live,
    required String? currentUsername,
    required WsProvider ws,
  }) {
    final connecting = _connecting || ws.liveConnecting;
    final status = ws.liveErrorText?.trim().isNotEmpty == true
        ? ws.liveErrorText!
        : (ws.liveStatusText?.trim().isNotEmpty == true ? ws.liveStatusText! : null);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: live ? AppColors.accentGreen.withOpacity(0.15) : AppColors.accentRed.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: live ? AppColors.accentGreen : AppColors.accentRed),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: live ? AppColors.accentGreen : AppColors.accentRed,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      live ? 'LIVE' : 'OFFLINE',
                      style: AppTextStyles.bodySmall.copyWith(
                        color: AppColors.primaryText,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              if (currentUsername != null && currentUsername.isNotEmpty)
                Row(
                  children: [
                    FutureBuilder<String?>(
                      future: _getTikTokAvatarUrl(currentUsername),
                      builder: (context, snapshot) {
                        final url = snapshot.data;
                        final hasUrl = url != null && url.isNotEmpty;
                        return CircleAvatar(
                          radius: 16,
                          backgroundColor: AppColors.accentPurple,
                          backgroundImage: hasUrl ? NetworkImage(url) : null,
                          child: hasUrl
                              ? null
                              : Text(
                                  currentUsername.substring(0, 1).toUpperCase(),
                                  style: AppTextStyles.bodySmall.copyWith(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                        );
                      },
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '@$currentUsername',
                      style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                    ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 12),

          Row(
            children: [
              Expanded(
                child: ElevatedButton(
              onPressed: _connecting
                  ? null
                  : () async {
                      setState(() => _connecting = true);
                      try {
                        if (live) {
                          await OverlayBridge.hide();
                          await ws.disconnectFromTikTok();
                        } else {
                          final u = (currentUsername ?? '').trim().replaceAll('@', '');
                          if (u.isEmpty) {
                            if (mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Укажите TikTok аккаунт в Профиле')), 
                              );
                            }
                            return;
                          }

                          // UX: показываем оверлей сразу после нажатия "Подключиться"
                          // (если разрешение не выдано — откроется системный экран).
                          await OverlayBridge.show();
                          await ws.connectToTikTok(u);
                        }
                      } finally {
                        if (mounted) setState(() => _connecting = false);
                      }
                    },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: live ? AppColors.accentRed : AppColors.accentPurple,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _connecting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : Text(live ? 'Отключиться от LIVE' : 'Подключиться к LIVE'),
                ),
              ),
              const SizedBox(width: 8),
              const HelpIcon(
                title: 'Подключение к LIVE',
                tooltip: 'Что делает кнопка подключения?',
                message:
                    'Подключает приложение к вашему LIVE в TikTok, чтобы получать события (чат, подарки, входы зрителей) и запускать озвучку/алёрты.\n\nПеред подключением укажите TikTok-ник в «Профиле» (без @).',
              ),
            ],
          ),

          if (connecting) ...[
            const SizedBox(height: 10),
            const LinearProgressIndicator(minHeight: 3),
          ],
          if (status != null) ...[
            const SizedBox(height: 10),
            Text(
              status,
              style: AppTextStyles.bodySmall.copyWith(
                color: ws.liveErrorText?.trim().isNotEmpty == true ? AppColors.accentRed : AppColors.secondaryText,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildQuickToggles(WsProvider ws) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('Быстрые переключатели', style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
              const Spacer(),
              const HelpIcon(
                title: 'Быстрые переключатели',
                message:
                    'Здесь собраны основные переключатели, которые чаще всего нужны во время стрима. Нажмите на «?» рядом с конкретным пунктом, чтобы узнать детали.',
              ),
            ],
          ),
          const SizedBox(height: 12),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Автоподключение к LIVE', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            value: ws.autoConnectLive,
            onChanged: (v) => ws.setAutoConnectLive(v),
            activeColor: AppColors.accentGreen,
            secondary: const HelpIcon(
              title: 'Автоподключение к LIVE',
              message:
                  'Если включено — приложение будет пытаться автоматически подключаться к LIVE (к вашему TikTok нику) при старте и/или при восстановлении соединения.\n\nПолезно, чтобы не забывать нажать «Подключиться».',
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('TTS ON / OFF', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            value: ws.ttsEnabled,
            onChanged: ws.updateTtsEnabled,
            activeColor: AppColors.accentGreen,
            secondary: const HelpIcon(
              title: 'TTS ON / OFF',
              message:
                  'Глобальный выключатель озвучки.\n\nЕсли выключено — приложение не будет генерировать и проигрывать TTS (включая озвучку чата/триггеров), даже если LIVE подключён.',
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Озвучка подарков ON / OFF', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            value: ws.giftSoundsEnabled,
            onChanged: ws.updateGiftSoundsEnabled,
            activeColor: AppColors.accentGreen,
            secondary: const HelpIcon(
              title: 'Озвучка подарков',
              message:
                  'Включает/выключает звуки/озвучку, которые срабатывают на подарки.\n\nЕсли выключено — подарки продолжат приходить как события, но звук/озвучка для них не проиграется.',
            ),
          ),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Режим «Тишина» (Premium)', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
            value: ws.silenceEnabled,
            onChanged: (v) async {
              final messenger = ScaffoldMessenger.of(context);
              final isPremium = ws.premiumEnabled;
              if (!isPremium && v) {
                messenger.showSnackBar(
                  const SnackBar(content: Text('Доступно только на Premium тарифе')),
                );
                return;
              }

              final ok = await ws.updateSilenceEnabled(v);
              if (!ok && mounted) {
                messenger.showSnackBar(
                  const SnackBar(content: Text('Не удалось сохранить настройку')),
                );
              }
            },
            activeColor: AppColors.accentGreen,
            secondary: const HelpIcon(
              title: 'Режим «Тишина» (Premium)',
              message:
              'Когда чат молчит, приложение может периодически отправлять «реплики» от бота (и озвучивать их), чтобы поддерживать активность на стриме.\n\nДоступно только на Premium тарифе.',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmergencyControls(WsProvider ws) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('Экстренное управление', style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
              const Spacer(),
              const HelpIcon(
                title: 'Экстренное управление',
                message:
                    'Кнопки для быстрого отключения озвучки и звуков, если что-то пошло не так во время стрима. Это не отключает LIVE, только звук/озвучку.',
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => ws.stopTts(),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.accentRed,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('STOP TTS'),
                      ),
                    ),
                    const SizedBox(width: 6),
                    const HelpIcon(
                      title: 'STOP TTS',
                      message:
                          'Мгновенно останавливает текущую/очередь озвучки (TTS). Используйте, если озвучка зациклилась или звучит не то.',
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => ws.stopGifts(),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.accentCyan,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('STOP GIFTS SOUND'),
                      ),
                    ),
                    const SizedBox(width: 6),
                    const HelpIcon(
                      title: 'STOP GIFTS SOUND',
                      message:
                          'Мгновенно отключает проигрывание звуков/озвучки подарков. Полезно, если подарки «спамят» звуком.',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRecentEvents(List<Map<String, dynamic>> events, WsProvider ws) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('Последние события', style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
              const SizedBox(width: 8),
              const HelpIcon(
                title: 'Последние события',
                message:
                    'Это журнал событий, которые пришли из LIVE: чат, подарки, лайки, входы зрителей и т.д.\n\nЕсли здесь пусто — проверьте подключение к LIVE и TikTok-ник в «Профиле».',
              ),
              const Spacer(),
              TextButton(onPressed: ws.clearEvents, child: const Text('Очистить')),
            ],
          ),
          const SizedBox(height: 8),
          if (events.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text('Событий пока нет', style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText)),
            )
          else
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: events.length > 20 ? 20 : events.length,
              itemBuilder: (context, index) {
                final e = events[index];
                final type = e['type']?.toString() ?? 'unknown';
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _eventIcon(type),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          e['text']?.toString() ?? '',
                          style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _eventIcon(String type) {
    IconData icon;
    Color color;
    switch (type) {
      case 'gift':
        icon = Icons.card_giftcard;
        color = AppColors.accentPurple;
        break;
      case 'follow':
        icon = Icons.person_add;
        color = AppColors.accentGreen;
        break;
      case 'viewer_join':
        icon = Icons.person;
        color = AppColors.accentCyan;
        break;
      case 'join':
        icon = Icons.person;
        color = AppColors.accentCyan;
        break;
      case 'like':
        icon = Icons.favorite;
        color = AppColors.accentRed;
        break;
      default:
        icon = Icons.notifications;
        color = AppColors.secondaryText;
    }
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
      child: Icon(icon, size: 18, color: color),
    );
  }
}