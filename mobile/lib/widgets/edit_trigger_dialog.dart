import 'package:cached_network_image/cached_network_image.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';

class EditTriggerDialog extends StatefulWidget {
  final Map<String, dynamic> trigger;

  const EditTriggerDialog({
    super.key,
    required this.trigger,
  });

  @override
  State<EditTriggerDialog> createState() => _EditTriggerDialogState();
}

class _EditTriggerDialogState extends State<EditTriggerDialog> {
  final _nameController = TextEditingController();
  final _ttsTextController = TextEditingController();
  final _comboController = TextEditingController();
  final _cooldownController = TextEditingController();

  bool _saving = false;
  bool _uploading = false;
  String? _soundFilename;

  bool _oncePerStream = true;
  bool _autoplaySound = true;

  late final String? _originalName;
  late final String? _originalText;
  late final int _originalCombo;
  late final int _originalCooldown;
  late final String? _originalSound;
  late final bool _originalOncePerStream;
  late final bool _originalAutoplaySound;

  Map<String, dynamic> get _actionParams {
    final ap = widget.trigger['action_params'];
    if (ap is Map<String, dynamic>) return ap;
    if (ap is Map) return ap.cast<String, dynamic>();
    return <String, dynamic>{};
  }

  @override
  void initState() {
    super.initState();

    _originalName = (widget.trigger['trigger_name'] as String?)?.trim();

    final action = widget.trigger['action']?.toString() ?? '';
    final ap = _actionParams;

    final text = (widget.trigger['text_template'] as String?) ??
        (ap['text_template'] as String?) ??
        (ap['text'] as String?);
    _originalText = text?.trim();

    final sound = (widget.trigger['sound_filename'] as String?) ??
        (ap['sound_file'] as String?) ??
        (ap['sound_filename'] as String?);
    _originalSound = sound?.trim();

    final combo = (widget.trigger['combo_count'] as int?) ?? 0;
    _originalCombo = combo;

    final cooldown = (ap['cooldown_seconds'] as int?) ?? 0;
    _originalCooldown = cooldown;

    _originalOncePerStream = (ap['once_per_stream'] as bool?) ?? true;
    _originalAutoplaySound = (ap['autoplay_sound'] as bool?) ?? true;

    _nameController.text = _originalName ?? '';
    _ttsTextController.text = _originalText ?? '';
    _comboController.text = _originalCombo.toString();
    _cooldownController.text = _originalCooldown.toString();
    _soundFilename = _originalSound;

    _oncePerStream = _originalOncePerStream;
    _autoplaySound = _originalAutoplaySound;

    // For non-gift triggers combo is irrelevant but we keep controller populated.
    if (action != 'tts') {
      // Keep but unused.
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _ttsTextController.dispose();
    _comboController.dispose();
    _cooldownController.dispose();
    super.dispose();
  }

  Future<void> _uploadSound() async {
    final api = context.read<ApiService>();
    final messenger = ScaffoldMessenger.of(context);
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp3'],
        allowMultiple: false,
      );

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;
      if (file.bytes == null) {
        if (!mounted) return;
        messenger.showSnackBar(
          const SnackBar(content: Text('Не удалось прочитать файл')),
        );
        return;
      }

      setState(() => _uploading = true);

      final uploaded = await api.uploadSound(
        filename: file.name,
        bytes: file.bytes!,
      );

      if (!mounted) return;
      setState(() {
        _uploading = false;
        final fn = uploaded?.filename;
        if (fn != null && fn.trim().isNotEmpty) {
          _soundFilename = fn;
        }
      });

      if (!mounted) return;
      if (uploaded != null) {
        messenger.showSnackBar(const SnackBar(content: Text('Звук загружен')));
      } else {
        messenger.showSnackBar(SnackBar(content: Text(api.lastError ?? 'Ошибка загрузки звука')));
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _uploading = false);
      messenger.showSnackBar(
        SnackBar(content: Text('Ошибка загрузки: $e')),
      );
    }
  }

  Future<void> _save() async {
    final api = context.read<ApiService>();
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);

    final id = widget.trigger['id']?.toString();
    if (id == null || id.isEmpty) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Не найден id триггера')),
      );
      return;
    }

    final eventType = widget.trigger['event_type']?.toString() ?? '';
    final action = widget.trigger['action']?.toString() ?? '';

    final name = _nameController.text.trim();
    // Важно: даём возможность очистить имя.
    // Если было имя и пользователь очистил — шлём пустую строку, чтобы backend обновил поле.
    String? triggerName;
    if (name.isEmpty) {
      if ((_originalName ?? '').isNotEmpty) {
        triggerName = '';
      } else {
        triggerName = null;
      }
    } else {
      triggerName = name == _originalName ? null : name;
    }

    final cooldownParsed = int.tryParse(_cooldownController.text.trim()) ?? 0;
    final cooldown = cooldownParsed < 0 ? 0 : cooldownParsed;
    final cooldownSeconds = cooldown == _originalCooldown ? null : cooldown;

    int? comboCount;
    if (eventType == 'gift') {
      final comboParsed = int.tryParse(_comboController.text.trim()) ?? 0;
      final combo = comboParsed < 0 ? 0 : comboParsed;
      comboCount = combo == _originalCombo ? null : combo;
    }

    String? textTemplate;
    if (action == 'tts') {
      final text = _ttsTextController.text.trim();
      final normalized = text.isEmpty ? null : text;
      textTemplate = normalized == _originalText ? null : normalized;
    }

    String? soundFilename;
    if (action == 'play_sound') {
      final current = _soundFilename?.trim();
      soundFilename = (current == _originalSound) ? null : current;
      final originalSound = (_originalSound ?? '').trim();
      if ((current == null || current.isEmpty) && originalSound.isEmpty) {
        soundFilename = null;
      }
      if ((current == null || current.isEmpty) && originalSound.isNotEmpty) {
        // Don't allow clearing sound via empty string.
        soundFilename = null;
      }
    }

    bool? oncePerStream;
    bool? autoplaySound;
    if (eventType == 'viewer_join' && action == 'play_sound') {
      oncePerStream = (_oncePerStream == _originalOncePerStream) ? null : _oncePerStream;
      autoplaySound = (_autoplaySound == _originalAutoplaySound) ? null : _autoplaySound;
    }

    if (triggerName == null && cooldownSeconds == null && comboCount == null && textTemplate == null && soundFilename == null && oncePerStream == null && autoplaySound == null) {
      navigator.pop(false);
      return;
    }

    setState(() => _saving = true);
    try {
      final ok = await api.updateTrigger(
        id: id,
        triggerName: triggerName,
        comboCount: comboCount,
        textTemplate: textTemplate,
        soundFilename: soundFilename,
        cooldownSeconds: cooldownSeconds,
        oncePerStream: oncePerStream,
        autoplaySound: autoplaySound,
      );

      if (!mounted) return;
      setState(() => _saving = false);

      if (ok) {
        navigator.pop(true);
        messenger.showSnackBar(
          const SnackBar(content: Text('Триггер обновлён')),
        );
      } else {
        messenger.showSnackBar(
          SnackBar(content: Text(api.lastError ?? 'Ошибка обновления триггера')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      messenger.showSnackBar(
        SnackBar(content: Text('Ошибка: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final eventType = widget.trigger['event_type']?.toString() ?? '';
    final action = widget.trigger['action']?.toString() ?? '';

    final giftImageUrl = widget.trigger['gift_image_url']?.toString();

    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.edit),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Редактировать триггер',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              if (eventType == 'gift' && giftImageUrl != null && giftImageUrl.isNotEmpty) ...[
                Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: CachedNetworkImage(
                        imageUrl: giftImageUrl,
                        width: 40,
                        height: 40,
                        fit: BoxFit.cover,
                        errorWidget: (context, url, error) => const Icon(Icons.card_giftcard),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        (widget.trigger['trigger_name'] as String?) ?? 'Подарок',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
              ],

              TextField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Название (опционально)',
                ),
              ),
              const SizedBox(height: 12),

              TextField(
                controller: _cooldownController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Кулдаун (сек)',
                ),
              ),
              const SizedBox(height: 12),

              if (eventType == 'viewer_join' && action == 'play_sound') ...[
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _oncePerStream,
                  title: const Text('Только 1 раз за стрим'),
                  onChanged: (v) => setState(() => _oncePerStream = v),
                ),
                SwitchListTile.adaptive(
                  contentPadding: EdgeInsets.zero,
                  value: _autoplaySound,
                  title: const Text('Проигрывать звук сразу'),
                  onChanged: (v) => setState(() => _autoplaySound = v),
                ),
                const SizedBox(height: 12),
              ],

              if (eventType == 'gift') ...[
                TextField(
                  controller: _comboController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Combo (минимум, 0 = любое)',
                  ),
                ),
                const SizedBox(height: 12),
              ],

              if (action == 'tts') ...[
                TextField(
                  controller: _ttsTextController,
                  minLines: 2,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    labelText: 'Текст TTS (шаблон)',
                  ),
                ),
                const SizedBox(height: 12),
              ],

              if (action == 'play_sound') ...[
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _soundFilename == null || _soundFilename!.isEmpty
                            ? 'Звук не выбран'
                            : 'Звук: $_soundFilename',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton(
                      onPressed: _uploading ? null : _uploadSound,
                      child: Text(_uploading ? 'Загрузка...' : 'Загрузить mp3'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
              ],

              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _saving ? null : () => Navigator.of(context).pop(false),
                    child: const Text('Отмена'),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: _saving ? null : _save,
                    child: Text(_saving ? 'Сохранение...' : 'Сохранить'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
