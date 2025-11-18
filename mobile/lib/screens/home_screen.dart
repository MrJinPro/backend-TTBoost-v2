import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/ws_service.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  final _ws = WsService();
  final List<String> _events = [];
  bool _connected = false;
  List<Map<String, dynamic>> _triggers = [];
  final _tiktokCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _ws.onEvent = (ev) {
      setState(() {
        final time = DateTime.now();
        _events.insert(0, '[${time.hour}:${time.minute}:${time.second}] ${ev.toString()}');
        if (_events.length > 50) _events.removeLast();
      });
    };
    _ws.onStatus = (conn) {
      setState(() {
        _connected = conn;
        _events.insert(0, '[STATUS] ${conn ? "Подключено ✓" : "Отключено ✗"}');
      });
    };
    _loadTriggers();
  }

  @override
  void dispose() {
    _ws.disconnect();
    _tiktokCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadTriggers() async {
    final api = context.read<ApiService>();
    final triggers = await api.listTriggers();
    setState(() => _triggers = triggers);
  }

  void _toggleConnection() {
    final auth = context.read<AuthProvider>();
    if (_connected) {
      _ws.disconnect();
    } else {
      final token = auth.jwtToken;
      if (token != null && token.isNotEmpty) _ws.connect(token);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('TTBoost', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: _connected ? AppColors.accentGreen.withOpacity(0.2) : AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: _connected ? AppColors.accentGreen : AppColors.cardBorder),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _connected ? AppColors.accentGreen : AppColors.secondaryText,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _connected ? 'LIVE' : 'OFFLINE',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(icon: const Icon(Icons.logout), onPressed: () => auth.logout()),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: [
          _buildDashboard(auth),
          _buildSettings(auth),
          _buildTriggers(),
          _buildEvents(),
        ],
      ),
      floatingActionButton: _currentIndex == 2
          ? FloatingActionButton(
              onPressed: _showAddTriggerDialog,
              backgroundColor: AppColors.accentPurple,
              child: const Icon(Icons.add),
            )
          : null,
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        backgroundColor: AppColors.cardBackground,
        selectedItemColor: AppColors.accentPurple,
        unselectedItemColor: AppColors.secondaryText,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Панель'),
          BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Настройки'),
          BottomNavigationBarItem(icon: Icon(Icons.bolt), label: 'Триггеры'),
          BottomNavigationBarItem(icon: Icon(Icons.event_note), label: 'События'),
        ],
      ),
    );
  }

  Widget _buildDashboard(AuthProvider auth) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: AppColors.accentPurple,
                    child: Text(
                      (auth.username ?? 'U')[0].toUpperCase(),
                      style: const TextStyle(fontSize: 24, color: Colors.white),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          auth.username ?? 'User',
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                        ),
                        if (auth.tiktokUsername != null)
                          Text(
                            '@${auth.tiktokUsername}',
                            style: const TextStyle(color: AppColors.accentCyan),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: InkWell(
              onTap: _toggleConnection,
              borderRadius: BorderRadius.circular(16),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: (_connected ? AppColors.accentGreen : AppColors.accentRed).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _connected ? Icons.link : Icons.link_off,
                        color: _connected ? AppColors.accentGreen : AppColors.accentRed,
                        size: 32,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _connected ? 'Подключено к TikTok Live' : 'Не подключено',
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                          ),
                          Text(
                            _connected ? 'Получение событий в реальном времени' : 'Нажмите чтобы подключиться',
                            style: const TextStyle(color: AppColors.secondaryText, fontSize: 14),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Статистика', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _buildStatCard('События', '${_events.length}', Icons.event, AppColors.accentCyan)),
              const SizedBox(width: 8),
              Expanded(child: _buildStatCard('Триггеры', '${_triggers.length}', Icons.bolt, AppColors.accentPurple)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
            Text(label, style: const TextStyle(color: AppColors.secondaryText)),
          ],
        ),
      ),
    );
  }

  Widget _buildSettings(AuthProvider auth) {
    if (_tiktokCtrl.text.isEmpty && auth.tiktokUsername != null) {
      _tiktokCtrl.text = auth.tiktokUsername!;
    }
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Настройки', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.person, color: AppColors.accentPurple),
            title: const Text('Имя пользователя'),
            subtitle: Text(auth.username ?? 'Не указано'),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: const [
                    Icon(Icons.video_library, color: AppColors.accentCyan),
                    SizedBox(width: 12),
                    Text('TikTok аккаунт', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _tiktokCtrl,
                  decoration: const InputDecoration(
                    labelText: 'TikTok username',
                    prefixText: '@',
                    hintText: 'your_username',
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () async {
                      final username = _tiktokCtrl.text.trim();
                      if (username.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Введите TikTok username')),
                        );
                        return;
                      }
                      
                      final api = context.read<ApiService>();
                      final success = await api.updateSettings(tiktokUsername: username);
                      
                      if (mounted) {
                        if (success) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('✓ TikTok аккаунт обновлен'),
                              backgroundColor: AppColors.accentGreen,
                            ),
                          );
                          // Перезагружаем профиль
                          await context.read<AuthProvider>().initialize();
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Ошибка сохранения'),
                              backgroundColor: AppColors.accentRed,
                            ),
                          );
                        }
                      }
                    },
                    child: const Text('Сохранить'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTriggers() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: const BoxDecoration(
            color: AppColors.cardBackground,
            border: Border(bottom: BorderSide(color: AppColors.cardBorder)),
          ),
          child: Row(
            children: [
              const Expanded(
                child: Text('Триггеры', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: _loadTriggers,
                tooltip: 'Обновить',
              ),
            ],
          ),
        ),
        Expanded(
          child: _triggers.isEmpty
              ? const Center(
                  child: Text('Нет триггеров', style: TextStyle(color: AppColors.secondaryText)),
                )
              : ListView.builder(
                  itemCount: _triggers.length,
                  itemBuilder: (context, index) {
                    final trigger = _triggers[index];
                    final eventType = trigger['event_type'] as String? ?? '';
                    final action = trigger['action'] as String? ?? '';
                    final enabled = trigger['enabled'] as bool? ?? false;
                    final conditionKey = trigger['condition_key'] as String?;
                    final conditionValue = trigger['condition_value'] as String?;
                    
                    return Card(
                      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: ListTile(
                        leading: Icon(
                          Icons.bolt,
                          color: enabled ? AppColors.accentGreen : AppColors.secondaryText,
                        ),
                        title: Text(eventType),
                        subtitle: Text('Действие: $action'),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              enabled ? Icons.check_circle : Icons.cancel,
                              color: enabled ? AppColors.accentGreen : AppColors.accentRed,
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete, color: AppColors.accentRed),
                              onPressed: () async {
                                final api = context.read<ApiService>();
                                final success = await api.deleteTrigger(
                                  eventType: eventType,
                                  conditionKey: conditionKey,
                                  conditionValue: conditionValue,
                                );
                                if (success) {
                                  await _loadTriggers();
                                  if (mounted) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('Триггер удален')),
                                    );
                                  }
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildEvents() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: const BoxDecoration(
            color: AppColors.cardBackground,
            border: Border(bottom: BorderSide(color: AppColors.cardBorder)),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Лог событий (${_events.length})',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
              if (_events.isNotEmpty)
                TextButton(
                  onPressed: () => setState(() => _events.clear()),
                  child: const Text('Очистить'),
                ),
            ],
          ),
        ),
        Expanded(
          child: _events.isEmpty
              ? const Center(
                  child: Text('События не получены', style: TextStyle(color: AppColors.secondaryText)),
                )
              : ListView.builder(
                  itemCount: _events.length,
                  itemBuilder: (context, index) {
                    final event = _events[index];
                    final isStatus = event.contains('[STATUS]');
                    return Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(color: AppColors.cardBorder.withOpacity(0.3)),
                        ),
                      ),
                      child: Text(
                        event,
                        style: TextStyle(
                          fontSize: 12,
                          fontFamily: 'monospace',
                          color: isStatus ? AppColors.accentCyan : Colors.white,
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  void _showAddTriggerDialog() {
    String selectedEvent = 'gift';
    String selectedAction = 'play_sound';
    String soundFile = '';
    
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Добавить триггер'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  value: selectedEvent,
                  decoration: const InputDecoration(labelText: 'Тип события'),
                  items: const [
                    DropdownMenuItem(value: 'gift', child: Text('Подарок (Gift)')),
                    DropdownMenuItem(value: 'comment', child: Text('Комментарий')),
                    DropdownMenuItem(value: 'follow', child: Text('Подписка')),
                    DropdownMenuItem(value: 'share', child: Text('Репост')),
                    DropdownMenuItem(value: 'like', child: Text('Лайк')),
                  ],
                  onChanged: (val) => setDialogState(() => selectedEvent = val!),
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: selectedAction,
                  decoration: const InputDecoration(labelText: 'Действие'),
                  items: const [
                    DropdownMenuItem(value: 'play_sound', child: Text('Воспроизвести звук')),
                    DropdownMenuItem(value: 'tts', child: Text('Текст в речь (TTS)')),
                  ],
                  onChanged: (val) => setDialogState(() => selectedAction = val!),
                ),
                const SizedBox(height: 16),
                if (selectedAction == 'play_sound')
                  TextField(
                    decoration: const InputDecoration(
                      labelText: 'Имя файла звука',
                      hintText: 'sound.mp3',
                    ),
                    onChanged: (val) => soundFile = val,
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена'),
            ),
            ElevatedButton(
              onPressed: () async {
                final api = context.read<ApiService>();
                
                Map<String, dynamic> actionParams = {};
                if (selectedAction == 'play_sound') {
                  if (soundFile.isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Введите имя файла')),
                    );
                    return;
                  }
                  actionParams['sound_file'] = soundFile;
                } else if (selectedAction == 'tts') {
                  actionParams['text'] = '{username} {message}';
                }
                
                final success = await api.setTrigger(
                  eventType: selectedEvent,
                  action: selectedAction,
                  actionParams: actionParams,
                  enabled: true,
                );
                
                if (mounted) {
                  Navigator.pop(context);
                  if (success) {
                    await _loadTriggers();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('✓ Триггер добавлен'),
                        backgroundColor: AppColors.accentGreen,
                      ),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Ошибка добавления триггера'),
                        backgroundColor: AppColors.accentRed,
                      ),
                    );
                  }
                }
              },
              child: const Text('Добавить'),
            ),
          ],
        ),
      ),
    );
  }
}