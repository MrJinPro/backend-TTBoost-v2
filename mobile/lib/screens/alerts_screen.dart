import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';
import '../services/audio_playback_service.dart';
import '../utils/log.dart';
import '../utils/premium_gate.dart';
import '../widgets/gift_picker_dialog.dart';
import '../widgets/help_icon.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<Map<String, dynamic>> _triggers = [];
  bool _loading = true;

  final AudioPlaybackService _audio = AudioPlaybackService();
  final Map<String, String> _soundUrlByFilename = <String, String>{};
  bool _loadingSounds = false;

  @override
  void initState() {
    super.initState();
    _loadTriggers();
  }

  Future<void> _loadTriggers() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      final triggers = await api.getTriggers();
      if (mounted) {
        setState(() {
          _triggers = triggers;
          _loading = false;
        });
        logDebug('Loaded ${triggers.length} triggers from API');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки триггеров: $e')),
        );
      }
      logDebug('Error loading triggers: $e');
    }
  }

  String _soundFilenameForTrigger(Map<String, dynamic> trigger) {
    final ap = trigger['action_params'];
    if (ap is Map) {
      final v = ap['sound_filename'];
      if (v != null) return v.toString();
    }
    final direct = trigger['sound_filename'];
    return direct?.toString() ?? '';
  }

  Future<String?> _resolveSoundUrl(String filename) async {
    final f = filename.trim();
    if (f.isEmpty) return null;
    if (f.startsWith('http://') || f.startsWith('https://')) return f;

    final cached = _soundUrlByFilename[f];
    if (cached != null && cached.trim().isNotEmpty) return cached;

    if (_loadingSounds) return null;
    _loadingSounds = true;
    try {
      final api = context.read<ApiService>();
      final sounds = await api.listSounds();
      for (final s in sounds) {
        final fn = s['filename']?.toString();
        final url = s['url']?.toString();
        if (fn != null && fn.trim().isNotEmpty && url != null && url.trim().isNotEmpty) {
          _soundUrlByFilename[fn.trim()] = url.trim();
        }
      }
      final resolved = _soundUrlByFilename[f];
      if (resolved != null && resolved.trim().isNotEmpty) return resolved;

      // fallback: если filename уже выглядит как путь
      if (f.startsWith('/')) {
        return '${api.baseUrl}$f';
      }
      return null;
    } finally {
      _loadingSounds = false;
    }
  }

  Future<void> _playTriggerSound(String filename) async {
    try {
      final url = await _resolveSoundUrl(filename);
      if (url == null || url.trim().isEmpty) {
        throw Exception('Не найден URL для $filename');
      }
      await _audio.playGift(url: url, volume: 1.0);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Не удалось проиграть звук: $e')),
      );
    }
  }

  Future<({String filename, String url})?> _showMyInstantsImportDialog(ApiService api) async {
    final searchCtrl = TextEditingController();
    bool loading = false;
    bool importing = false;
    String? previewingPageUrl;
    List<Map<String, dynamic>> results = [];
    bool initialized = false;

    return showDialog<({String filename, String url})?>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            Future<void> loadCatalog({bool forceRefresh = false}) async {
              setStateDialog(() => loading = true);
              final found = await api.getMyInstantsCatalog(forceRefresh: forceRefresh);
              if (!context.mounted) return;
              setStateDialog(() {
                results = found;
                loading = false;
              });
            }

            Future<void> runSearch() async {
              final q = searchCtrl.text.trim();
              if (q.length < 2) {
                await loadCatalog();
                return;
              }

              setStateDialog(() => loading = true);
              final found = await api.searchMyInstants(q);
              if (!context.mounted) return;
              setStateDialog(() {
                results = found;
                loading = false;
              });
            }

            Future<void> importItem(Map<String, dynamic> item) async {
              final pageUrl = item['page_url']?.toString().trim() ?? '';
              final title = item['title']?.toString().trim();
              if (pageUrl.isEmpty) return;

              setStateDialog(() => importing = true);
              final imported = await api.importMyInstants(pageUrl: pageUrl, title: title);
              if (!context.mounted) return;
              setStateDialog(() => importing = false);
              if (imported == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(api.lastError ?? 'Не удалось импортировать звук')),
                );
                return;
              }
              Navigator.of(context).pop(imported);
            }

            Future<void> previewItem(Map<String, dynamic> item) async {
              final pageUrl = item['page_url']?.toString().trim() ?? '';
              if (pageUrl.isEmpty) return;

              setStateDialog(() => previewingPageUrl = pageUrl);
              try {
                final previewUrl = await api.getMyInstantsPreviewUrl(pageUrl: pageUrl);
                if (previewUrl == null || previewUrl.isEmpty) {
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(api.lastError ?? 'Не удалось загрузить превью')),
                  );
                  return;
                }
                await _audio.playGift(url: previewUrl, volume: 1.0);
              } catch (e) {
                if (!context.mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Не удалось воспроизвести превью: $e')),
                );
              } finally {
                if (context.mounted) {
                  setStateDialog(() => previewingPageUrl = null);
                }
              }
            }

            if (!initialized) {
              initialized = true;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                loadCatalog();
              });
            }

            return AlertDialog(
              backgroundColor: AppColors.cardBackground,
              title: const Text('Импорт из Myinstants'),
              content: SizedBox(
                width: 520,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: searchCtrl,
                      decoration: InputDecoration(
                        hintText: 'Поиск по названию звука',
                        filled: true,
                        fillColor: AppColors.surfaceColor,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        suffixIcon: IconButton(
                          onPressed: (loading || importing) ? null : runSearch,
                          icon: const Icon(Icons.search),
                        ),
                      ),
                      onSubmitted: (_) {
                        if (!loading && !importing) runSearch();
                      },
                    ),
                    const SizedBox(height: 12),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Каталог подгружается сразу. Любой выбранный звук будет импортирован в вашу библиотеку и затем доступен в триггерах как обычный файл.',
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (loading)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        child: LinearProgressIndicator(),
                      )
                    else
                      SizedBox(
                        height: 320,
                        child: results.isEmpty
                            ? Center(
                                child: Text(
                                  'Каталог пуст. Попробуйте обновить или введите запрос.',
                                  style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
                                ),
                              )
                            : ListView.separated(
                                itemCount: results.length,
                                separatorBuilder: (_, __) => const Divider(color: AppColors.cardBorder),
                                itemBuilder: (context, index) {
                                  final item = results[index];
                                  final title = item['title']?.toString() ?? '';
                                  final pageUrl = item['page_url']?.toString() ?? '';
                                  return ListTile(
                                    contentPadding: EdgeInsets.zero,
                                    title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis),
                                    subtitle: Text(pageUrl, maxLines: 1, overflow: TextOverflow.ellipsis),
                                    trailing: Wrap(
                                      spacing: 8,
                                      children: [
                                        IconButton(
                                          tooltip: 'Прослушать',
                                          onPressed: (importing || loading || previewingPageUrl == pageUrl)
                                              ? null
                                              : () => previewItem(item),
                                          icon: previewingPageUrl == pageUrl
                                              ? const SizedBox(
                                                  width: 18,
                                                  height: 18,
                                                  child: CircularProgressIndicator(strokeWidth: 2),
                                                )
                                              : const Icon(Icons.play_arrow),
                                        ),
                                        FilledButton(
                                          onPressed: importing ? null : () => importItem(item),
                                          child: const Text('Импорт'),
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                      ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: importing || loading ? null : () => loadCatalog(forceRefresh: true),
                  child: const Text('Обновить каталог'),
                ),
                TextButton(
                  onPressed: importing ? null : () => Navigator.of(context).pop(),
                  child: const Text('Закрыть'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Заголовок с кнопкой добавления
            _buildHeader(),
            
            // Список алёртов
            Expanded(
              child: _loading 
                ? const Center(child: CircularProgressIndicator())
                : _triggers.isEmpty 
                  ? _buildEmptyState()
                  : _buildTriggersList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: AppColors.cardBorder),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.notifications_active,
            color: AppColors.accentPurple,
            size: 28,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Алёрты и уведомления',
                  style: AppTextStyles.headline.copyWith(
                    color: AppColors.primaryText,
                  ),
                ),
                Text(
                  'Настройте звуки для событий в эфире',
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.secondaryText,
                  ),
                ),
              ],
            ),
          ),

          const HelpIcon(
            title: 'Алёрты и уведомления',
            tooltip: 'Как работают алёрты?',
            message:
                'Здесь настраиваются триггеры (алёрты) — что именно проигрывать при событиях в LIVE (подарки, вход зрителя, чат и т.д.).\n\nВключайте/выключайте триггеры тумблером и настраивайте их через редактирование.',
          ),
          
          // Кнопка добавления
          Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.accentPurple, AppColors.accentCyan],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: _showAddTriggerDialog,
                child: const Padding(
                  padding: EdgeInsets.all(12),
                  child: Icon(
                    Icons.add,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: AppColors.accentPurple.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.notifications_none,
                color: AppColors.accentPurple,
                size: 60,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Нет настроенных алёртов',
              style: AppTextStyles.subtitle.copyWith(
                color: AppColors.primaryText,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Добавьте звуковые уведомления для\nподарков, чата и других событий',
              textAlign: TextAlign.center,
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.secondaryText,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _showAddTriggerDialog,
              icon: const Icon(Icons.add),
              label: const Text('Добавить алёрт'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTriggersList() {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _triggers.length,
      itemBuilder: (context, index) {
        final trigger = _triggers[index];
        return _buildTriggerCard(trigger, index);
      },
    );
  }

  Widget _buildTriggerCard(Map<String, dynamic> trigger, int index) {
    final eventType = trigger['event_type']?.toString() ?? '';
    final enabled = trigger['enabled'] == true;
    final soundFilename = _soundFilenameForTrigger(trigger);
    
    IconData icon;
    Color iconColor;
    String title;
    String subtitle;
    
    switch (eventType) {
      case 'gift':
        icon = Icons.card_giftcard;
        iconColor = AppColors.accentPurple;
        title = 'Алёрт подарка';
        subtitle = trigger['condition_value']?.toString() ?? 'Любой подарок';
        break;
      case 'viewer_join':
        icon = Icons.person_add;
        iconColor = AppColors.accentGreen;
        title = 'Вход зрителя';
        final ck = trigger['condition_key']?.toString();
        final cvRaw = trigger['condition_value']?.toString() ?? '';
        final cv = cvRaw.trim();

        String who;
        if (ck == 'username' && cv.isNotEmpty) {
          final normalized = cv.startsWith('@') ? cv.substring(1) : cv;
          who = '@$normalized';
        } else {
          who = 'Все зрители';
        }

        Map<String, dynamic> ap = <String, dynamic>{};
        final apRaw = trigger['action_params'];
        if (apRaw is Map<String, dynamic>) {
          ap = apRaw;
        } else if (apRaw is Map) {
          ap = apRaw.cast<String, dynamic>();
        }

        final oncePerStream = (ap['once_per_stream'] as bool?) ?? true;
        final autoplay = (ap['autoplay_sound'] as bool?) ?? true;
        final cooldown = switch (ap['cooldown_seconds']) {
          int v => v,
          String v => int.tryParse(v.trim()) ?? 0,
          _ => int.tryParse(ap['cooldown_seconds']?.toString() ?? '') ?? 0,
        };

        final parts = <String>[
          who,
          oncePerStream ? '1 раз' : 'каждый раз',
          autoplay ? 'автоплей' : 'без автоплея',
          if (cooldown > 0) 'кд ${cooldown}s',
        ];

        subtitle = parts.join(' • ');
        break;
      case 'chat':
        icon = Icons.chat_bubble;
        iconColor = AppColors.accentCyan;
        title = 'Сообщение в чате';
        subtitle = trigger['condition_value']?.toString() ?? 'Любое сообщение';
        break;
      default:
        icon = Icons.notifications;
        iconColor = AppColors.secondaryText;
        title = eventType;
        subtitle = 'Кастомное событие';
    }
    
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: enabled ? iconColor.withOpacity(0.3) : AppColors.cardBorder,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => _editTrigger(trigger, index),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // Иконка события
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: iconColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: iconColor, size: 24),
                ),
                const SizedBox(width: 16),
                
                // Информация о триггере
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: AppTextStyles.subtitle.copyWith(
                          color: AppColors.primaryText,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.secondaryText,
                        ),
                      ),
                      if (soundFilename.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.volume_up,
                              color: AppColors.accentGreen,
                              size: 16,
                            ),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Text(
                                soundFilename,
                                style: AppTextStyles.bodySmall.copyWith(
                                  color: AppColors.accentGreen,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
                
                // Переключатель и кнопки
                Column(
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Switch(
                          value: enabled,
                          onChanged: (value) => _toggleTrigger(index, value),
                          activeColor: AppColors.accentGreen,
                        ),
                        const SizedBox(width: 4),
                        const HelpIcon(
                          title: 'Включить/выключить алёрт',
                          message:
                              'Если выключить — этот триггер перестанет срабатывать при событии в LIVE.\n\nМожно отключать отдельные алёрты, не удаляя их настройки.',
                        ),
                      ],
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (soundFilename.isNotEmpty)
                          IconButton(
                            onPressed: () => _playTriggerSound(soundFilename),
                            icon: const Icon(Icons.play_arrow, size: 20),
                            color: AppColors.accentGreen,
                            padding: EdgeInsets.zero,
                            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                            tooltip: 'Прослушать звук',
                          ),
                        IconButton(
                          onPressed: () => _editTrigger(trigger, index),
                          icon: const Icon(Icons.edit, size: 20),
                          color: AppColors.secondaryText,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                          tooltip: 'Редактировать алёрт',
                        ),
                        IconButton(
                          onPressed: () => _deleteTrigger(index),
                          icon: const Icon(Icons.delete, size: 20),
                          color: AppColors.accentRed,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                          tooltip: 'Удалить алёрт',
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showAddTriggerDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => _buildTriggerTypeSelector(),
    );
  }

  Widget _buildTriggerTypeSelector() {
    final triggerTypes = [
      {
        'type': 'gift',
        'title': 'Алёрт подарка',
        'subtitle': 'Звук при получении подарка',
        'icon': Icons.card_giftcard,
        'color': AppColors.accentPurple,
      },
      {
        'type': 'viewer_join',
        'title': 'Вход зрителя',
        'subtitle': 'Звук когда кто-то заходит в эфир',
        'icon': Icons.person_add,
        'color': AppColors.accentGreen,
      },
      {
        'type': 'chat',
        'title': 'Сообщение в чате',
        'subtitle': 'Звук при новом сообщении',
        'icon': Icons.chat_bubble,
        'color': AppColors.accentCyan,
      },
      {
        'type': 'follow',
        'title': 'Новый подписчик',
        'subtitle': 'Звук при подписке',
        'icon': Icons.favorite,
        'color': AppColors.accentRed,
      },
    ];

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Заголовок
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: AppColors.cardBorder)),
            ),
            child: Row(
              children: [
                Text(
                  'Выберите тип алёрта',
                  style: AppTextStyles.subtitle.copyWith(
                    color: AppColors.primaryText,
                  ),
                ),
                const Spacer(),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                  color: AppColors.secondaryText,
                ),
              ],
            ),
          ),
          
          // Список типов
          ...triggerTypes.map((type) => ListTile(
            leading: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: (type['color'] as Color).withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                type['icon'] as IconData,
                color: type['color'] as Color,
                size: 20,
              ),
            ),
            title: Text(
              type['title'] as String,
              style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.primaryText,
              ),
            ),
            subtitle: Text(
              type['subtitle'] as String,
              style: AppTextStyles.bodySmall.copyWith(
                color: AppColors.secondaryText,
              ),
            ),
            onTap: () async {
              Navigator.pop(context);
              await _createTrigger(type['type'] as String);
            },
          )),
          
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Future<void> _createTrigger(String eventType) async {
    logDebug('Creating trigger for event type: $eventType');
    final canCreate = await PremiumGate.ensureCanCreateTrigger(context, freeMaxTriggers: 10);
    if (!canCreate) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('В бесплатном тарифе максимум 10 алёртов. Перейдите на тариф выше, чтобы использовать больше.')),
        );
      }
      return;
    }
    _showTriggerEditor(eventType: eventType);
  }

  void _editTrigger(Map<String, dynamic> trigger, int index) {
    logDebug('Editing trigger at index: $index');
    final eventType = trigger['event_type']?.toString() ?? '';
    _showTriggerEditor(eventType: eventType, existing: trigger);
  }

  Future<void> _toggleTrigger(int index, bool enabled) async {
    logDebug('Toggling trigger $index to $enabled');
    final trigger = _triggers[index];
    final id = trigger['id']?.toString();
    if (id == null || id.isEmpty) return;
    try {
      final api = context.read<ApiService>();
      final ok = await api.updateTriggerEnabled(id: id, enabled: enabled);
      if (!ok) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(api.lastError ?? 'Не удалось обновить триггер')),
          );
        }
        return;
      }
      if (mounted) {
        setState(() {
          _triggers[index] = {...trigger, 'enabled': enabled};
        });
      }
    } catch (e) {
      logDebug('Error toggling trigger: $e');
    }
  }

  Future<void> _deleteTrigger(int index) async {
    logDebug('Deleting trigger at index: $index');
    final trigger = _triggers[index];
    final id = trigger['id']?.toString();
    if (id == null || id.isEmpty) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить алёрт?'),
        content: const Text('Это действие нельзя отменить.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Удалить')),
        ],
      ),
    );
    if (confirmed != true) return;
    if (!mounted) return;

    try {
      final messenger = ScaffoldMessenger.of(context);
      final api = context.read<ApiService>();
      final ok = await api.deleteTrigger(id: id);
      if (!mounted) return;
      if (!ok) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Не удалось удалить триггер')),
        );
        return;
      }
      await _loadTriggers();
    } catch (e) {
      logDebug('Error deleting trigger: $e');
    }
  }

  Future<void> _showTriggerEditor({
    required String eventType,
    Map<String, dynamic>? existing,
  }) async {
    final api = context.read<ApiService>();

    final existingId = existing?['id']?.toString();
    final existingName = existing?['trigger_name']?.toString() ?? '';
    final existingConditionKey = existing?['condition_key']?.toString();
    final existingConditionValue = existing?['condition_value']?.toString();
    final existingSound = existing != null ? _soundFilenameForTrigger(existing) : '';

    Map<String, dynamic> existingActionParams = <String, dynamic>{};
    final apRaw = existing?['action_params'];
    if (apRaw is Map<String, dynamic>) {
      existingActionParams = apRaw;
    } else if (apRaw is Map) {
      existingActionParams = apRaw.cast<String, dynamic>();
    }

    final nameCtrl = TextEditingController(text: existingName);
    final conditionCtrl = TextEditingController(text: existingConditionValue ?? '');
    String conditionMode = 'any';
    if (eventType == 'gift') {
      if (existingConditionKey == 'gift_id') conditionMode = 'gift_id';
      if (existingConditionKey == 'gift_name') conditionMode = 'gift_name';
    }

    // viewer_join settings
    bool viewerJoinAny = true;
    if (eventType == 'viewer_join') {
      viewerJoinAny = existingConditionKey != 'username';
      if (!viewerJoinAny) {
        final v = (existingConditionValue ?? '').trim();
        conditionCtrl.text = v.startsWith('@') ? v.substring(1) : v;
      } else {
        conditionCtrl.text = '';
      }
    }
    bool viewerJoinOncePerStream = (existingActionParams['once_per_stream'] as bool?) ?? true;
    bool viewerJoinAutoplaySound = (existingActionParams['autoplay_sound'] as bool?) ?? true;
    final viewerJoinCooldownCtrl = TextEditingController(
      text: ((existingActionParams['cooldown_seconds'] as int?) ?? 0).toString(),
    );

    Map<String, dynamic>? selectedGift;

    if (eventType == 'gift' && existingConditionKey == 'gift_id' && (existingConditionValue ?? '').trim().isNotEmpty) {
      try {
        final gifts = await api.getGiftsLibrary();
        final existingGiftId = (existingConditionValue ?? '').trim();
        selectedGift = gifts.firstWhere(
          (gift) => (gift['gift_id']?.toString() ?? '').trim() == existingGiftId,
        );
      } catch (_) {}
    }

    bool saving = false;
    bool soundsLoading = true;
    List<Map<String, dynamic>> sounds = [];
    String? selectedSound = existingSound.isNotEmpty ? existingSound : null;

    Future<void> loadSounds(StateSetter setModalState) async {
      setModalState(() => soundsLoading = true);
      final list = await api.listSounds();
      setModalState(() {
        sounds = list;
        soundsLoading = false;
        if (selectedSound != null && selectedSound!.isNotEmpty) return;
        if (sounds.isNotEmpty) selectedSound = sounds.first['filename']?.toString();
      });
    }

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            if (soundsLoading) {
              // fire once
              soundsLoading = false;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                loadSounds(setModalState);
              });
              soundsLoading = true;
            }

            final bottomInset = MediaQuery.of(context).viewInsets.bottom;
            return Padding(
              padding: EdgeInsets.only(bottom: bottomInset),
              child: Container(
                decoration: const BoxDecoration(
                  color: AppColors.cardBackground,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                child: SafeArea(
                  top: false,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              existing == null ? 'Новый алёрт' : 'Редактирование',
                              style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
                            ),
                            const Spacer(),
                            IconButton(
                              onPressed: saving ? null : () => Navigator.pop(context),
                              icon: const Icon(Icons.close),
                              color: AppColors.secondaryText,
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        TextField(
                          controller: nameCtrl,
                          decoration: InputDecoration(
                            labelText: 'Название (необязательно)',
                            filled: true,
                            fillColor: AppColors.surfaceColor,
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                        const SizedBox(height: 12),

                        if (eventType == 'viewer_join') ...[
                          SwitchListTile.adaptive(
                            contentPadding: EdgeInsets.zero,
                            value: viewerJoinAny,
                            title: const Text('Для всех зрителей'),
                            onChanged: saving
                                ? null
                                : (v) {
                                    setModalState(() {
                                      viewerJoinAny = v;
                                      if (viewerJoinAny) conditionCtrl.text = '';
                                    });
                                  },
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            controller: conditionCtrl,
                            enabled: !viewerJoinAny && !saving,
                            decoration: InputDecoration(
                              labelText: 'Никнейм зрителя (TikTok)',
                              hintText: 'username',
                              filled: true,
                              fillColor: AppColors.surfaceColor,
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                              prefixText: '@',
                            ),
                          ),
                          const SizedBox(height: 12),
                          SwitchListTile.adaptive(
                            contentPadding: EdgeInsets.zero,
                            value: viewerJoinOncePerStream,
                            title: const Text('Только 1 раз за стрим'),
                            onChanged: saving ? null : (v) => setModalState(() => viewerJoinOncePerStream = v),
                          ),
                          const SizedBox(height: 8),
                          SwitchListTile.adaptive(
                            contentPadding: EdgeInsets.zero,
                            value: viewerJoinAutoplaySound,
                            title: const Text('Проигрывать звук сразу'),
                            onChanged: saving ? null : (v) => setModalState(() => viewerJoinAutoplaySound = v),
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            controller: viewerJoinCooldownCtrl,
                            enabled: !saving,
                            keyboardType: TextInputType.number,
                            decoration: InputDecoration(
                              labelText: 'Кулдаун (сек)',
                              filled: true,
                              fillColor: AppColors.surfaceColor,
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],

                        if (eventType == 'gift') ...[
                          Row(
                            children: [
                              Expanded(
                                child: DropdownButtonFormField<String>(
                                  value: conditionMode,
                                  decoration: InputDecoration(
                                    labelText: 'Условие подарка',
                                    filled: true,
                                    fillColor: AppColors.surfaceColor,
                                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                  ),
                                  items: const [
                                    DropdownMenuItem(value: 'any', child: Text('Любой подарок')),
                                    DropdownMenuItem(value: 'gift_id', child: Text('Выбрать из списка')),
                                    DropdownMenuItem(value: 'gift_name', child: Text('По названию')),
                                  ],
                                  onChanged: saving
                                      ? null
                                      : (v) {
                                          if (v == null) return;
                                          setModalState(() => conditionMode = v);
                                          if (v == 'any') conditionCtrl.text = '';
                                          if (v != 'gift_id') {
                                            // Сбрасываем выбранный подарок, если уходим с режима gift_id
                                            selectedGift = null;
                                          }
                                        },
                                ),
                              ),
                            ],
                          ),
                          if (conditionMode != 'any') ...[
                            const SizedBox(height: 12),

                            if (conditionMode == 'gift_id') ...[
                              SizedBox(
                                width: double.infinity,
                                child: OutlinedButton.icon(
                                  onPressed: saving
                                      ? null
                                      : () async {
                                          final gift = await showDialog<Map<String, dynamic>>(
                                            context: context,
                                            builder: (_) => const GiftPickerDialog(),
                                          );
                                          if (gift == null) return;
                                          final id = gift['gift_id']?.toString() ?? '';
                                          if (id.isEmpty) return;
                                          setModalState(() {
                                            selectedGift = gift;
                                            conditionMode = 'gift_id';
                                            conditionCtrl.text = id;
                                          });
                                        },
                                  icon: const Icon(Icons.card_giftcard),
                                  label: Text(selectedGift == null ? 'Выбрать подарок из списка' : 'Изменить подарок'),
                                ),
                              ),
                              if (selectedGift != null) ...[
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    if ((selectedGift!['image'] as String? ?? '').isNotEmpty)
                                      ClipRRect(
                                        borderRadius: BorderRadius.circular(8),
                                        child: Image.network(
                                          selectedGift!['image'] as String,
                                          width: 32,
                                          height: 32,
                                          fit: BoxFit.cover,
                                        ),
                                      )
                                    else
                                      const Icon(Icons.card_giftcard, size: 28, color: AppColors.secondaryText),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Text(
                                        ((selectedGift!['name_ru'] as String? ?? '').isNotEmpty
                                                ? selectedGift!['name_ru'] as String
                                                : (selectedGift!['name_en'] as String? ?? ''))
                                            .trim(),
                                        style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                    const SizedBox(width: 10),
                                    Text(
                                      '💎 ${(selectedGift!['diamond_count'] as int? ?? 0)}',
                                      style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                                    ),
                                  ],
                                ),
                              ],
                              const SizedBox(height: 12),
                              Text(
                                selectedGift == null
                                    ? 'Сначала выберите подарок из списка.'
                                    : 'Для триггера будет сохранён выбранный подарок. Ручной ввод gift_id не нужен.',
                                style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                              ),
                            ] else
                              TextField(
                                controller: conditionCtrl,
                                decoration: InputDecoration(
                                  labelText: 'Название подарка',
                                  filled: true,
                                  fillColor: AppColors.surfaceColor,
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                ),
                              ),
                          ],
                          const SizedBox(height: 12),
                        ],

                        Row(
                          children: [
                            Expanded(
                              child: soundsLoading
                                  ? const Padding(
                                      padding: EdgeInsets.symmetric(vertical: 12),
                                      child: LinearProgressIndicator(),
                                    )
                                  : DropdownButtonFormField<String>(
                                      value: selectedSound,
                                      decoration: InputDecoration(
                                        labelText: 'Звук',
                                        filled: true,
                                        fillColor: AppColors.surfaceColor,
                                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                      ),
                                      items: sounds
                                          .map(
                                            (s) => DropdownMenuItem<String>(
                                              value: s['filename']?.toString(),
                                              child: Text(s['filename']?.toString() ?? ''),
                                            ),
                                          )
                                          .toList(),
                                      onChanged: saving ? null : (v) => setModalState(() => selectedSound = v),
                                    ),
                            ),
                            const SizedBox(width: 10),
                            IconButton(
                              tooltip: 'Обновить список',
                              onPressed: saving ? null : () => loadSounds(setModalState),
                              icon: const Icon(Icons.refresh),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: saving
                                ? null
                                : () async {
                                    final result = await FilePicker.platform.pickFiles(withData: true);
                                    final f = result?.files.firstOrNull;
                                    if (f == null) return;
                                    if (f.bytes == null || f.name.isEmpty) {
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('Не удалось прочитать файл')),
                                        );
                                      }
                                      return;
                                    }
                                    setModalState(() => saving = true);
                                    try {
                                      final uploaded = await api.uploadSound(filename: f.name, bytes: f.bytes!);
                                      if (uploaded == null) {
                                        if (context.mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text(api.lastError ?? 'Ошибка загрузки звука')),
                                          );
                                        }
                                      } else {
                                        await loadSounds(setModalState);
                                        setModalState(() => selectedSound = uploaded.filename);
                                      }
                                    } finally {
                                      setModalState(() => saving = false);
                                    }
                                  },
                            icon: const Icon(Icons.upload_file),
                            label: const Text('Загрузить звук (<= 1MB)'),
                          ),
                        ),
                        const SizedBox(height: 12),

                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: saving
                                ? null
                                : () async {
                                    final imported = await _showMyInstantsImportDialog(api);
                                    if (imported == null) return;
                                    await loadSounds(setModalState);
                                    setModalState(() => selectedSound = imported.filename);
                                  },
                            icon: const Icon(Icons.library_music),
                            label: const Text('Выбрать из Myinstants'),
                          ),
                        ),
                        const SizedBox(height: 16),

                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: saving
                                ? null
                                : () async {
                                    final sf = (selectedSound ?? '').trim();
                                    if (sf.isEmpty) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Выберите звук')),
                                      );
                                      return;
                                    }
                                    String? ck;
                                    String? cv;
                                    if (eventType == 'gift' && conditionMode != 'any') {
                                      ck = conditionMode;
                                      cv = conditionCtrl.text.trim();
                                      if (cv.isEmpty) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('Заполните условие')),
                                        );
                                        return;
                                      }
                                    }
                                    if (eventType == 'viewer_join') {
                                      if (viewerJoinAny) {
                                        ck = 'always';
                                        cv = '*';
                                      } else {
                                        ck = 'username';
                                        final raw = conditionCtrl.text.trim();
                                        final normalized = raw.startsWith('@') ? raw.substring(1) : raw;
                                        cv = normalized;
                                        if (cv.isEmpty) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            const SnackBar(content: Text('Введите никнейм зрителя')),
                                          );
                                          return;
                                        }
                                      }
                                    }
                                    setModalState(() => saving = true);
                                    try {
                                      bool ok;
                                      if (existingId != null && existingId.isNotEmpty) {
                                        final cooldown = int.tryParse(viewerJoinCooldownCtrl.text.trim()) ?? 0;
                                        ok = await api.updateTrigger(
                                          id: existingId,
                                          triggerName: nameCtrl.text.trim().isEmpty ? null : nameCtrl.text.trim(),
                                          conditionKey: ck,
                                          conditionValue: cv,
                                          soundFilename: sf,
                                          cooldownSeconds: eventType == 'viewer_join' ? cooldown : null,
                                          oncePerStream: eventType == 'viewer_join' ? viewerJoinOncePerStream : null,
                                          autoplaySound: eventType == 'viewer_join' ? viewerJoinAutoplaySound : null,
                                        );
                                      } else {
                                        final cooldown = int.tryParse(viewerJoinCooldownCtrl.text.trim()) ?? 0;
                                        final actionParams = <String, dynamic>{
                                          'sound_filename': sf,
                                          if (eventType == 'viewer_join') 'once_per_stream': viewerJoinOncePerStream,
                                          if (eventType == 'viewer_join') 'autoplay_sound': viewerJoinAutoplaySound,
                                          if (eventType == 'viewer_join' && cooldown > 0) 'cooldown_seconds': cooldown,
                                        };
                                        ok = await api.setTrigger(
                                          eventType: eventType,
                                          conditionKey: ck,
                                          conditionValue: cv,
                                          action: 'play_sound',
                                          actionParams: actionParams,
                                        );
                                      }
                                      if (!ok) {
                                        if (context.mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text(api.lastError ?? 'Не удалось сохранить алёрт')),
                                          );
                                        }
                                        return;
                                      }
                                      if (context.mounted) Navigator.pop(context);
                                      await _loadTriggers();
                                    } finally {
                                      if (context.mounted) setModalState(() => saving = false);
                                    }
                                  },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.accentPurple,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                            child: Text(existing == null ? 'Создать' : 'Сохранить'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    nameCtrl.dispose();
    conditionCtrl.dispose();
    viewerJoinCooldownCtrl.dispose();
  }
}

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}