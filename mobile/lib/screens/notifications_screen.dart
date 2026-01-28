import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/notifications_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationsProvider>().loadNotifications();
    });
  }

  Future<void> _openNotification(Map<String, dynamic> n) async {
    final id = (n['id']?.toString() ?? '').trim();
    if (id.isNotEmpty) {
      await context.read<NotificationsProvider>().markRead(id);
    }

    if (!mounted) return;

    final title = (n['title']?.toString() ?? '').trim();
    final body = (n['body']?.toString() ?? '').trim();
    final link = (n['link']?.toString() ?? '').trim();
    final type = (n['type']?.toString() ?? '').trim().toLowerCase();

    await showDialog<void>(
      context: context,
      builder: (_) {
        return AlertDialog(
          backgroundColor: AppColors.cardBackground,
          title: Text(title.isEmpty ? 'Уведомление' : title, style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText)),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (type.isNotEmpty) ...[
                  Text(
                    type,
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                  ),
                  const SizedBox(height: 8),
                ],
                Text(body, style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText)),
                if (link.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text('Ссылка:', style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText)),
                  const SizedBox(height: 6),
                  SelectableText(link, style: AppTextStyles.bodySmall.copyWith(color: AppColors.accentCyan)),
                ]
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Закрыть'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<NotificationsProvider>(
      builder: (context, p, _) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('Уведомления'),
            actions: [
              const HelpIcon(
                title: 'Уведомления',
                message:
                    'Здесь показываются системные уведомления приложения (например, важные статусы, сообщения от сервера).\n\nНажмите на уведомление, чтобы открыть подробности.',
              ),
              if (p.unreadCount > 0)
                TextButton(
                  onPressed: () async {
                    await p.markAllRead();
                  },
                  child: const Text('Прочитать все'),
                ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: () async {
              await p.loadNotifications();
            },
            child: p.loadingList
                ? const Center(child: CircularProgressIndicator())
                : (p.items.isEmpty
                    ? ListView(
                        children: [
                          const SizedBox(height: 24),
                          Center(
                            child: Text(
                              'Пока уведомлений нет',
                              style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
                            ),
                          ),
                        ],
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(12),
                        itemCount: p.items.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final n = p.items[index];
                          final title = (n['title']?.toString() ?? '').trim();
                          final body = (n['body']?.toString() ?? '').trim();
                          final isRead = n['is_read'] == true;
                          final type = (n['type']?.toString() ?? '').trim().toLowerCase();

                          return InkWell(
                            onTap: () => _openNotification(n),
                            borderRadius: BorderRadius.circular(14),
                            child: Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: AppColors.cardBackground,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(color: AppColors.cardBorder),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    width: 10,
                                    height: 10,
                                    margin: const EdgeInsets.only(top: 4),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: isRead ? AppColors.cardBorder : AppColors.accentPurple,
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          title.isEmpty ? 'Уведомление' : title,
                                          style: AppTextStyles.bodyMedium.copyWith(
                                            color: AppColors.primaryText,
                                            fontWeight: isRead ? FontWeight.w500 : FontWeight.w700,
                                          ),
                                        ),
                                        if (type.isNotEmpty) ...[
                                          const SizedBox(height: 4),
                                          Text(
                                            type,
                                            style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                                          ),
                                        ],
                                        const SizedBox(height: 6),
                                        Text(
                                          body,
                                          maxLines: 3,
                                          overflow: TextOverflow.ellipsis,
                                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      )),
          ),
        );
      },
    );
  }
}
