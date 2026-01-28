import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';
import '../services/api_service.dart';
import '../services/audio_playback_service.dart';
import '../utils/log.dart';
import 'audio_output_screen.dart';

class VoiceScreen extends StatefulWidget {
  const VoiceScreen({super.key});

  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen> {
  final _testTextController = TextEditingController(text: 'Тест озвучки NovaBoost');
  final AudioPlaybackService _audio = AudioPlaybackService();

  String? _selectedVoiceId;
  double _ttsVolume = 100;
  double _giftVolume = 100;

  String _chatTtsMode = 'all';
  final TextEditingController _chatTtsPrefixesController = TextEditingController(text: '.');
  final TextEditingController _chatTtsMinDiamondsController = TextEditingController(text: '5');

  List<Map<String, dynamic>> _voices = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  Future<void> _loadInitial() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();

      final settings = await api.getSettings();
      if (settings != null && mounted) {
        final voiceId = settings['voice_id']?.toString();
        final ttsVol = (settings['tts_volume'] as num?)?.toDouble();
        final giftsVol = (settings['gifts_volume'] as num?)?.toDouble();
        final chatMode = settings['chat_tts_mode']?.toString();
        final chatPrefixes = settings['chat_tts_prefixes']?.toString();
        final chatMin = settings['chat_tts_min_diamonds']?.toString();
        setState(() {
          if (voiceId != null && voiceId.isNotEmpty) _selectedVoiceId = voiceId;
          if (ttsVol != null) _ttsVolume = ttsVol.clamp(0, 100);
          if (giftsVol != null) _giftVolume = giftsVol.clamp(0, 100);

          final m = (chatMode ?? '').trim().toLowerCase();
          if (m == 'all' || m == 'prefix' || m == 'donor') {
            _chatTtsMode = m;
          }
          if (chatPrefixes != null && chatPrefixes.trim().isNotEmpty) {
            _chatTtsPrefixesController.text = chatPrefixes;
          }
          if (chatMin != null && chatMin.trim().isNotEmpty) {
            _chatTtsMinDiamondsController.text = chatMin;
          }
        });
      }

      final voices = await api.getVoices();
      if (mounted) {
        setState(() {
          _voices = voices;
          _loading = false;
          if (_voices.isNotEmpty) {
            final desired = _selectedVoiceId;
            final exists = desired != null && _voices.any((v) => v['id']?.toString() == desired);
            if (!exists) _selectedVoiceId = _voices.first['id']?.toString();
          }
        });
        logDebug('Loaded ${voices.length} voices from API');
      }
    } catch (e) {
      if (mounted) {
        setState(() => _loading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки голосов: $e')),
        );
      }
      logDebug('Error loading voices: $e');
    }
  }

  @override
  void dispose() {
    _testTextController.dispose();
    _chatTtsPrefixesController.dispose();
    _chatTtsMinDiamondsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Заголовок
                  _buildHeader(),
                  const SizedBox(height: 24),
                  
                  // Выбор голоса
                  _buildVoiceSelection(),
                  const SizedBox(height: 24),
                  
                  // Настройки громкости
                  _buildVolumeSettings(),
                  const SizedBox(height: 24),

                  // Озвучка чата: фильтры
                  _buildChatTtsFilterSettings(),
                  const SizedBox(height: 24),

                  // Аудио вывод
                  _buildAudioOutput(),
                  const SizedBox(height: 24),
                  
                  // Тест голоса
                  _buildVoiceTest(),
                ],
              ),
            ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: AppColors.accentCyan.withOpacity(0.2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(
            Icons.record_voice_over,
            color: AppColors.accentCyan,
            size: 24,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Настройки озвучки',
                style: AppTextStyles.headline.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
              Text(
                'Голос и громкость для TTS и звуков',
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.secondaryText,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildVoiceSelection() {
    return Container(
      padding: const EdgeInsets.all(16),
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
                Icons.mic,
                color: AppColors.accentPurple,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Выбор голоса для TTS',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.surfaceColor,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.cardBorder),
            ),
            child: DropdownButton<String>(
              value: _selectedVoiceId,
              isExpanded: true,
              underline: Container(),
              hint: Text(
                'Выберите голос',
                style: AppTextStyles.bodyMedium.copyWith(
                  color: AppColors.secondaryText,
                ),
              ),
              items: _voices.map((voice) {
                return DropdownMenuItem<String>(
                  value: voice['id'],
                  child: Row(
                    children: [
                      _getVoiceEngineIcon(voice['engine']),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              voice['name'],
                              style: AppTextStyles.bodyMedium.copyWith(
                                color: AppColors.primaryText,
                              ),
                            ),
                            Text(
                              voice['engine'].toString().toUpperCase(),
                              style: AppTextStyles.bodySmall.copyWith(
                                color: AppColors.secondaryText,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
              onChanged: (value) {
                setState(() => _selectedVoiceId = value);
                _saveVoiceSettings();
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAudioOutput() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const AudioOutputScreen()),
          );
        },
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.accentCyan.withOpacity(0.2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.volume_up, color: AppColors.accentCyan, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Аудио вывод',
                    style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Куда выводить озвучку и звуки',
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.secondaryText),
          ],
        ),
      ),
    );
  }

  Widget _buildVolumeSettings() {
    return Container(
      padding: const EdgeInsets.all(16),
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
                Icons.volume_up,
                color: AppColors.accentGreen,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Настройки громкости',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          
          // TTS громкость
          _buildVolumeSlider(
            'Громкость озвучки чата',
            _ttsVolume,
            Icons.chat,
            AppColors.accentCyan,
            (value) => setState(() => _ttsVolume = value),
          ),
          
          const SizedBox(height: 20),
          
          // Громкость подарков
          _buildVolumeSlider(
            'Громкость звуков подарков',
            _giftVolume,
            Icons.card_giftcard,
            AppColors.accentPurple,
            (value) => setState(() => _giftVolume = value),
          ),
        ],
      ),
    );
  }

  Widget _buildVolumeSlider(
    String title,
    double value,
    IconData icon,
    Color color,
    ValueChanged<double> onChanged,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                title,
                style: AppTextStyles.bodyMedium.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: color.withOpacity(0.2),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                '${value.round()}%',
                style: AppTextStyles.bodySmall.copyWith(
                  color: color,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        SliderTheme(
          data: SliderTheme.of(context).copyWith(
            activeTrackColor: color,
            thumbColor: color,
            overlayColor: color.withOpacity(0.2),
            inactiveTrackColor: color.withOpacity(0.3),
          ),
          child: Slider(
            value: value,
            min: 0,
            max: 100,
            divisions: 20,
            onChanged: (newValue) {
              onChanged(newValue);
              _saveVolumeSettings();
            },
          ),
        ),
      ],
    );
  }

  Widget _buildVoiceTest() {
    return Container(
      padding: const EdgeInsets.all(16),
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
                Icons.play_circle,
                color: AppColors.accentGreen,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Тест озвучки',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
              const Spacer(),
              const HelpIcon(
                title: 'Тест озвучки',
                message:
                    'Позволяет проверить выбранный голос/движок TTS: приложение запросит генерацию озвучки на сервере и проиграет результат.\n\nЕсли не слышно — проверьте громкость, подключение к серверу и разрешения.',
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Сгенерировать TTS и проиграть',
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.secondaryText,
            ),
          ),
          const SizedBox(height: 16),

          TextField(
            controller: _testTextController,
            minLines: 2,
            maxLines: 4,
            decoration: InputDecoration(
              labelText: 'Текст для озвучки',
              hintText: 'Введите текст',
              suffixIcon: const HelpIcon(
                title: 'Текст для озвучки',
                message:
                    'Этот текст будет отправлен на сервер для генерации TTS и затем проигран в приложении.\n\nПодходит, чтобы быстро проверить голос и качество озвучки.',
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.accentGreen),
              ),
            ),
          ),
          const SizedBox(height: 12),
          
          SizedBox(
            width: double.infinity,
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _testVoice,
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Проиграть'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentGreen,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                const HelpIcon(
                  title: 'Проиграть (тест)',
                  message:
                      'Запускает генерацию тестового TTS и воспроизведение результата. Если сервер недоступен — появится ошибка.',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatTtsFilterSettings() {
    return Container(
      padding: const EdgeInsets.all(16),
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
              Icon(Icons.forum, color: AppColors.accentCyan, size: 20),
              const SizedBox(width: 8),
              Text(
                'Озвучка чата (фильтр)',
                style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
              ),
              const Spacer(),
              const HelpIcon(
                title: 'Озвучка чата (фильтр)',
                message:
                    'Определяет, какие сообщения из чата будут озвучиваться, когда нет сработавшего триггера.\n\nРежимы: все сообщения, только сообщения с префиксом, или только донаторы от заданного порога.',
              ),
            ],
          ),
          const SizedBox(height: 12),

          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.surfaceColor,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.cardBorder),
            ),
            child: DropdownButton<String>(
              value: _chatTtsMode,
              isExpanded: true,
              underline: Container(),
              items: const [
                DropdownMenuItem(value: 'all', child: Text('Озвучивать все комментарии')),
                DropdownMenuItem(value: 'prefix', child: Text('Озвучивать только с префиксом')),
                DropdownMenuItem(value: 'donor', child: Text('Озвучивать только донаторов от N монет')),
              ],
              onChanged: (v) {
                if (v == null) return;
                setState(() => _chatTtsMode = v);
                _saveChatTtsFilterSettings();
              },
            ),
          ),

          const SizedBox(height: 12),

          TextField(
            controller: _chatTtsPrefixesController,
            decoration: InputDecoration(
              labelText: 'Префиксы (например: .* /,)',
              hintText: '.*/,',
              suffixIcon: const HelpIcon(
                title: 'Префиксы',
                message:
                    'Работает в режиме «Озвучивать только с префиксом».\n\nУкажите символы, с которых должно начинаться сообщение (например: . * / ,). Если сообщение начинается с одного из них — оно будет озвучено, а префикс удалится перед озвучкой.',
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.accentCyan),
              ),
            ),
            onSubmitted: (_) => _saveChatTtsFilterSettings(),
          ),

          const SizedBox(height: 12),

          TextField(
            controller: _chatTtsMinDiamondsController,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              labelText: 'Минимум монет (для режима донатов)',
              hintText: '5',
              suffixIcon: const HelpIcon(
                title: 'Минимум монет',
                message:
                    'Работает в режиме «Озвучивать только донаторов».\n\nОзвучиваются только сообщения пользователей, которые за текущую сессию LIVE подарили на сумму не меньше этого порога (в монетах/diamonds).',
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: AppColors.accentCyan),
              ),
            ),
            onSubmitted: (_) => _saveChatTtsFilterSettings(),
          ),

          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _saveChatTtsFilterSettings,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentCyan,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('Сохранить настройки чата'),
                  ),
                ),
                const SizedBox(width: 8),
                const HelpIcon(
                  title: 'Сохранить настройки чата',
                  message:
                      'Сохраняет выбранный режим и параметры на сервере. Эти настройки применяются при подключенном LIVE и влияют на озвучку сообщений чата.',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _getVoiceEngineIcon(String engine) {
    Color color;
    IconData icon;
    
    switch (engine.toLowerCase()) {
      case 'eleven':
        color = AppColors.accentPurple;
        icon = Icons.auto_awesome;
        break;
      case 'azure':
        color = AppColors.accentCyan;
        icon = Icons.cloud;
        break;
      case 'gtts':
        color = AppColors.accentGreen;
        icon = Icons.g_translate;
        break;
      default:
        color = AppColors.secondaryText;
        icon = Icons.mic;
    }
    
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Icon(icon, color: color, size: 16),
    );
  }

  void _saveVoiceSettings() async {
    try {
      final api = context.read<ApiService>();
      final success = await api.updateSettings(
        selectedVoiceId: _selectedVoiceId,
      );
      if (mounted) {
        if (success) {
          logDebug('Voice settings saved: $_selectedVoiceId');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Ошибка сохранения настроек голоса')),
          );
        }
      }
    } catch (e) {
      logDebug('Error saving voice settings: $e');
    }
  }

  void _saveVolumeSettings() async {
    try {
      final api = context.read<ApiService>();
      final success = await api.updateSettings(
        ttsVolume: _ttsVolume,
        giftVolume: _giftVolume,
      );
      if (mounted) {
        if (success) {
          logDebug('Volume settings saved: TTS=$_ttsVolume, Gifts=$_giftVolume');
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Ошибка сохранения громкости')),
          );
        }
      }
    } catch (e) {
      logDebug('Error saving volume settings: $e');
    }
  }

  void _saveChatTtsFilterSettings() async {
    try {
      final api = context.read<ApiService>();

      final prefixes = _chatTtsPrefixesController.text;
      final minDiamonds = int.tryParse(_chatTtsMinDiamondsController.text.trim()) ?? 0;

      final success = await api.updateSettings(
        chatTtsMode: _chatTtsMode,
        chatTtsPrefixes: prefixes,
        chatTtsMinDiamonds: minDiamonds,
      );

      if (!mounted) return;
      if (!success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ошибка сохранения настроек чата')),
        );
      }
    } catch (e) {
      logDebug('Error saving chat tts filter settings: $e');
    }
  }

  Future<void> _testVoice() async {
    final voiceId = _selectedVoiceId;
    if (voiceId == null || voiceId.trim().isEmpty) return;

    final text = _testTextController.text.trim();
    if (text.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Введите текст для озвучки')),
      );
      return;
    }

    try {
      final api = context.read<ApiService>();
      final url = await api.generateTts(text: text, voiceId: voiceId);
      if (url == null || url.trim().isEmpty) {
        throw Exception(api.lastError ?? 'Не удалось сгенерировать TTS');
      }

      final vol = ((_ttsVolume / 100).clamp(0, 1)).toDouble();
      await _audio.playTts(url: url, volume: vol, rate: 1.0);
    } catch (e) {
      logDebug('Error testing voice: $e');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка теста озвучки: $e')),
      );
    }
  }
}