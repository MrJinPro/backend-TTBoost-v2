import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';

class PermissionsScreen extends StatelessWidget {
  final bool notificationsGranted;
  final bool overlaySupported;
  final bool overlayGranted;
  final bool overlayRequired;

  final Future<void> Function() onRequestOverlay;
  final Future<void> Function() onOpenNotificationSettings;
  final Future<void> Function() onRecheck;
  final Future<void> Function()? onContinueWithoutOverlay;

  const PermissionsScreen({
    super.key,
    required this.notificationsGranted,
    required this.overlaySupported,
    required this.overlayGranted,
    required this.overlayRequired,
    required this.onRequestOverlay,
    required this.onOpenNotificationSettings,
    required this.onRecheck,
    required this.onContinueWithoutOverlay,
  });

  @override
  Widget build(BuildContext context) {
    final items = <_PermItem>[
      _PermItem(
        title: 'Уведомления',
        subtitle: 'Нужны для управления в шторке и работы в фоне.',
        ok: notificationsGranted,
        helpTitle: 'Разрешение: уведомления',
        helpMessage:
            'Нужно, чтобы приложение могло показывать управление/статус в уведомлении и корректно работать в фоне.\n\nЕсли отключено — некоторые функции в фоне могут работать хуже.',
        primaryText: notificationsGranted ? null : 'Открыть настройки уведомлений',
        onPrimary: notificationsGranted ? null : onOpenNotificationSettings,
      ),
      if (overlaySupported)
        _PermItem(
          title: 'Оверлей (поверх других приложений)',
          subtitle: 'Рекомендуется: ползунки громкости и быстрые кнопки поверх TikTok.',
          ok: overlayGranted || !overlayRequired,
          helpTitle: 'Разрешение: оверлей',
          helpMessage:
              'Оверлей позволяет показывать быстрые кнопки/ползунки поверх TikTok, когда приложение свёрнуто.\n\nЕсли не включать — приложением можно пользоваться, но управление поверх TikTok будет недоступно.',
          primaryText: (overlayGranted || !overlayRequired) ? null : 'Включить оверлей',
          onPrimary: (overlayGranted || !overlayRequired) ? null : onRequestOverlay,
          secondaryText: (overlayGranted || !overlayRequired || onContinueWithoutOverlay == null)
              ? null
              : 'Продолжить без оверлея',
          onSecondary: (overlayGranted || !overlayRequired) ? null : onContinueWithoutOverlay,
        ),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Разрешения')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Чтобы всё работало корректно, включите нужные разрешения.',
              style: TextStyle(color: AppColors.secondaryText),
            ),
            const SizedBox(height: 8),
            const Align(
              alignment: Alignment.centerLeft,
              child: HelpIcon(
                title: 'Зачем нужны разрешения?',
                message:
                    'Некоторые функции (работа в фоне, управление через оверлей) требуют системных разрешений Android/iOS.\n\nНажимайте на «?» рядом с пунктом, чтобы увидеть подробности.',
              ),
            ),
            const SizedBox(height: 16),
            ...items.map((i) => _PermCard(item: i)),
            const Spacer(),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: () => onRecheck(),
                    child: const Text('Проверить снова'),
                  ),
                ),
                const SizedBox(width: 8),
                const HelpIcon(
                  title: 'Проверить снова',
                  message:
                      'После выдачи разрешений в системных настройках нажмите сюда, чтобы приложение повторно проверило статусы и продолжило.',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PermItem {
  final String title;
  final String subtitle;
  final bool ok;
  final String helpTitle;
  final String helpMessage;
  final String? primaryText;
  final Future<void> Function()? onPrimary;
  final String? secondaryText;
  final Future<void> Function()? onSecondary;

  _PermItem({
    required this.title,
    required this.subtitle,
    required this.ok,
    required this.helpTitle,
    required this.helpMessage,
    this.primaryText,
    this.onPrimary,
    this.secondaryText,
    this.onSecondary,
  });
}

class _PermCard extends StatelessWidget {
  final _PermItem item;

  const _PermCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                item.ok ? Icons.check_circle : Icons.warning_amber_rounded,
                color: item.ok ? AppColors.accentGreen : AppColors.accentRed,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  item.title,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ),
              HelpIcon(title: item.helpTitle, message: item.helpMessage),
            ],
          ),
          const SizedBox(height: 8),
          Text(item.subtitle, style: const TextStyle(color: AppColors.secondaryText)),
          if (item.primaryText != null) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: item.onPrimary == null ? null : () => item.onPrimary!(),
                child: Text(item.primaryText!),
              ),
            ),
          ],
          if (item.secondaryText != null) ...[
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: item.onSecondary == null ? null : () => item.onSecondary!(),
                child: Text(item.secondaryText!),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
