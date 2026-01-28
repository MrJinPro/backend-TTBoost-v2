import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../utils/premium_gate.dart';

class ViewerJoinTriggerFormDialog extends StatefulWidget {
  const ViewerJoinTriggerFormDialog({super.key});

  @override
  State<ViewerJoinTriggerFormDialog> createState() => _ViewerJoinTriggerFormDialogState();
}

class _ViewerJoinTriggerFormDialogState extends State<ViewerJoinTriggerFormDialog> {
  final _nameController = TextEditingController();
  final _usernameController = TextEditingController();
  String? _soundFilename;
  bool _uploading = false;
  bool _creating = false;
  bool _anyViewer = false;
  bool _oncePerStream = true;
  bool _autoplaySound = true;
  final _cooldownController = TextEditingController(text: '0');

  @override
  void dispose() {
    _nameController.dispose();
    _usernameController.dispose();
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

      if (!mounted) return;

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;
      if (file.bytes == null) {
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
        _soundFilename = uploaded?.filename;
      });

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

  Future<void> _createTrigger() async {
    final username = _usernameController.text.trim();

    if (!_anyViewer && username.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Введите никнейм зрителя или включите "Для всех"')),
      );
      return;
    }

    if (_soundFilename == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Загрузите звуковой файл')),
      );
      return;
    }

    final canCreate = await PremiumGate.ensureCanCreateTrigger(context, freeMaxTriggers: 10);
    if (!canCreate) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Free: максимум 10 триггеров. Оформите Premium.')),
      );
      return;
    }

    setState(() => _creating = true);

    try {
      final api = context.read<ApiService>();
      final messenger = ScaffoldMessenger.of(context);
      final navigator = Navigator.of(context);

      final cooldown = int.tryParse(_cooldownController.text.trim()) ?? 0;
      
      final success = await api.setTrigger(
        eventType: 'viewer_join',
        conditionKey: _anyViewer ? 'always' : 'username',
        conditionValue: _anyViewer ? '*' : username,
        action: 'play_sound',
        actionParams: {
          'sound_file': _soundFilename,
          'once_per_stream': _oncePerStream,
          'autoplay_sound': _autoplaySound,
          if (cooldown > 0) 'cooldown_seconds': cooldown,
        },
        enabled: true,
        triggerName: _nameController.text.trim().isEmpty ? null : _nameController.text.trim(),
      );

      if (!mounted) return;

      setState(() => _creating = false);

      if (success) {
        navigator.pop(true);
        messenger.showSnackBar(
          const SnackBar(content: Text('Триггер создан')),
        );
      } else {
        messenger.showSnackBar(
          SnackBar(content: Text(api.lastError ?? 'Ошибка создания триггера')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _creating = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка: $e')),
      );
    }
  }

  String _getDefaultTriggerName() {
    final username = _usernameController.text.trim();
    if (_anyViewer) return 'Вход: все зрители';
    return username.isEmpty ? 'Вход зрителя' : 'Вход: $username';
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Container(
        width: 500,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Заголовок
            Row(
              children: [
                const Icon(Icons.person_add, color: Colors.blue),
                const SizedBox(width: 8),
                const Text(
                  'Триггер на вход зрителя',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Название триггера (опционально)
            TextField(
              controller: _nameController,
              decoration: InputDecoration(
                labelText: 'Название триггера (опционально)',
                hintText: _getDefaultTriggerName(),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.label_outline),
              ),
            ),
            const SizedBox(height: 16),

            // Username
            Row(
              children: [
                Expanded(
                  child: SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: _anyViewer,
                    title: const Text('Для всех зрителей'),
                    subtitle: Text(
                      _oncePerStream
                          ? 'Сработает на первое появление зрителя в текущей сессии'
                          : 'Сработает на каждый вход зрителя (рекомендуется поставить кулдаун)',
                    ),
                    onChanged: (v) {
                      setState(() {
                        _anyViewer = v;
                        if (_anyViewer) _usernameController.clear();
                      });
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _usernameController,
              enabled: !_anyViewer,
              decoration: InputDecoration(
                labelText: 'Никнейм зрителя (логин TikTok)',
                hintText: 'username',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.alternate_email),
                helperText: _anyViewer ? 'Выключено, потому что выбран режим "Для всех"' : 'Без @, только логин пользователя',
              ),
              onChanged: (_) => setState(() {}), // Обновляем hint для названия
            ),
            const SizedBox(height: 16),

            // Поведение
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _oncePerStream,
              title: const Text('Только 1 раз за стрим'),
              subtitle: const Text('Если выключить — будет срабатывать на каждый вход зрителя'),
              onChanged: (v) => setState(() => _oncePerStream = v),
            ),
            const SizedBox(height: 8),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: _autoplaySound,
              title: const Text('Проигрывать звук сразу'),
              subtitle: const Text('Если выключить — звук не будет авто‑проигрываться'),
              onChanged: (v) => setState(() => _autoplaySound = v),
            ),
            const SizedBox(height: 16),

            // Cooldown
            TextField(
              controller: _cooldownController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: 'Кулдаун (сек)',
                hintText: '0',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.timer_outlined),
                helperText: '0 = без ограничения (иначе сработает не чаще указанного интервала)',
              ),
            ),
            const SizedBox(height: 16),

            // Загрузка звука
            ElevatedButton.icon(
              onPressed: _uploading ? null : _uploadSound,
              icon: _uploading
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.upload_file),
              label: Text(_soundFilename == null ? 'Загрузить звук' : 'Звук: $_soundFilename'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 48),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 24),

            // Кнопки действий
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _creating ? null : () => Navigator.of(context).pop(),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(0, 48),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('Отмена'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: _creating ? null : _createTrigger,
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(0, 48),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _creating
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Создать'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
