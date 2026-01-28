import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../services/api_service.dart';
import '../utils/premium_gate.dart';
import 'gift_picker_dialog.dart';

class GiftTriggerFormDialog extends StatefulWidget {
  const GiftTriggerFormDialog({super.key});

  @override
  State<GiftTriggerFormDialog> createState() => _GiftTriggerFormDialogState();
}

class _GiftTriggerFormDialogState extends State<GiftTriggerFormDialog> {
  final _nameController = TextEditingController();
  Map<String, dynamic>? _selectedGift;
  double _comboCount = 0;
  String? _soundFilename;
  bool _uploading = false;
  bool _creating = false;
  final _cooldownController = TextEditingController(text: '0');

  @override
  void dispose() {
    _nameController.dispose();
    _cooldownController.dispose();
    super.dispose();
  }

  Future<void> _pickGift() async {
    final gift = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => const GiftPickerDialog(),
    );
    if (gift != null) {
      setState(() => _selectedGift = gift);
    }
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
    if (_selectedGift == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Выберите подарок')),
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
      final giftId = _selectedGift!['gift_id'].toString();

      final cooldown = int.tryParse(_cooldownController.text.trim()) ?? 0;
      
      final success = await api.setTrigger(
        eventType: 'gift',
        conditionKey: 'gift_id',
        conditionValue: giftId,
        action: 'play_sound',
        actionParams: {
          'sound_file': _soundFilename,
          if (cooldown > 0) 'cooldown_seconds': cooldown,
        },
        enabled: true,
        triggerName: _nameController.text.trim().isEmpty ? null : _nameController.text.trim(),
        comboCount: _comboCount.toInt(),
      );

      if (!mounted) return;

      setState(() => _creating = false);

      if (success) {
        navigator.pop(true); // Возвращаем true для обновления списка
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
    if (_selectedGift == null) return 'Новый триггер';
    final nameRu = _selectedGift!['name_ru'] as String? ?? '';
    final nameEn = _selectedGift!['name_en'] as String? ?? '';
    return nameRu.isNotEmpty ? nameRu : nameEn;
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
                const Icon(Icons.card_giftcard, color: Colors.purple),
                const SizedBox(width: 8),
                const Text(
                  'Триггер на подарок',
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

            // Выбор подарка
            InkWell(
              onTap: _pickGift,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade300),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    if (_selectedGift != null && (_selectedGift!['image'] as String? ?? '').isNotEmpty)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: SizedBox(
                          width: 40,
                          height: 40,
                          child: CachedNetworkImage(
                            imageUrl: _selectedGift!['image'] as String,
                            fit: BoxFit.cover,
                            placeholder: (context, url) => const Center(
                              child: SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              ),
                            ),
                            errorWidget: (context, url, error) =>
                                const Icon(Icons.card_giftcard, color: Colors.purple),
                          ),
                        ),
                      )
                    else
                      const Icon(Icons.card_giftcard, color: Colors.purple),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _selectedGift == null
                          ? const Text(
                              'Выберите подарок',
                              style: TextStyle(color: Colors.grey),
                            )
                          : Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  (_selectedGift!['name_ru'] as String? ?? '').isNotEmpty
                                      ? _selectedGift!['name_ru'] as String
                                      : _selectedGift!['name_en'] as String,
                                  style: const TextStyle(fontWeight: FontWeight.bold),
                                ),
                                Text(
                                  '💎 ${_selectedGift!['diamond_count']} алмазов',
                                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                                ),
                              ],
                            ),
                    ),
                    const Icon(Icons.arrow_forward_ios, size: 16),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Combo count
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('Минимальное комбо', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(width: 8),
                    Tooltip(
                      message: 'Минимальное количество подарков для срабатывания триггера.\n'
                          '0 = срабатывает на любое количество\n'
                          '10 = срабатывает только если отправлено 10+ подарков',
                      child: Icon(Icons.help_outline, size: 18, color: Colors.grey[600]),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: Slider(
                        value: _comboCount,
                        min: 0,
                        max: 200,
                        divisions: 40,
                        label: _comboCount == 0 ? 'Любое' : '${_comboCount.toInt()}+',
                        onChanged: (value) => setState(() => _comboCount = value),
                      ),
                    ),
                    SizedBox(
                      width: 60,
                      child: Text(
                        _comboCount == 0 ? 'Любое' : '${_comboCount.toInt()}+',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ],
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
