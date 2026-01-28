import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../utils/premium_gate.dart';

class FollowTriggerFormDialog extends StatefulWidget {
  const FollowTriggerFormDialog({super.key});

  @override
  State<FollowTriggerFormDialog> createState() => _FollowTriggerFormDialogState();
}

class _FollowTriggerFormDialogState extends State<FollowTriggerFormDialog> {
  final _nameController = TextEditingController();
  final _cooldownController = TextEditingController(text: '0');
  String? _soundFilename;
  bool _uploading = false;
  bool _creating = false;

  @override
  void dispose() {
    _nameController.dispose();
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
        eventType: 'follow',
        conditionKey: 'always',
        conditionValue: 'true',
        action: 'play_sound',
        actionParams: {
          'sound_file': _soundFilename,
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
                const Icon(Icons.person_add_alt_1, color: Colors.green),
                const SizedBox(width: 8),
                const Text(
                  'Триггер на подписку',
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
                hintText: 'Подписка',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.label_outline),
              ),
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
