import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class TutorialScreen extends StatefulWidget {
  const TutorialScreen({super.key, required this.onFinished});

  final Future<void> Function() onFinished;

  @override
  State<TutorialScreen> createState() => _TutorialScreenState();
}

class _TutorialScreenState extends State<TutorialScreen> {
  final _controller = PageController();
  int _index = 0;
  bool _finishing = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _finish() async {
    if (_finishing) return;
    setState(() => _finishing = true);
    await widget.onFinished();
  }

  Widget _page({required IconData icon, required String title, required String text}) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  color: AppColors.accentPurple.withOpacity(0.18),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppColors.cardBorder),
                ),
                child: Icon(icon, size: 44, color: AppColors.accentPurple),
              ),
              const SizedBox(height: 20),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              Text(
                text,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.secondaryText, fontSize: 14, height: 1.4),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final last = _index == 3;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Короткий туториал'),
        actions: [
          TextButton(
            onPressed: _finishing ? null : _finish,
            child: const Text('Пропустить'),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: PageView(
              controller: _controller,
              onPageChanged: (i) => setState(() => _index = i),
              children: [
                _page(
                  icon: Icons.person,
                  title: '1) Профиль',
                  text: 'Открой «Профиль» и укажи TikTok-ник. Это нужно, чтобы подключаться к LIVE и получать события.',
                ),
                _page(
                  icon: Icons.dashboard,
                  title: '2) Панель (LIVE)',
                  text: 'На вкладке «Панель» подключись к своему LIVE. Вверху загорится индикатор LIVE — значит всё работает.',
                ),
                _page(
                  icon: Icons.record_voice_over,
                  title: '3) Озвучка (TTS)',
                  text: 'Во вкладке «TTS» выбери голос и настрой фильтр озвучки чата: все, только с префиксом, или только донаторы.',
                ),
                _page(
                  icon: Icons.volume_off,
                  title: '4) Режим «Тишина» (Premium)',
                  text: 'Если включён Premium, на «Панели» можно включить «Тишину» — бот будет поддерживать активность, когда чат молчит.',
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: Row(
              children: [
                IconButton(
                  tooltip: 'Назад',
                  onPressed: _index == 0
                      ? null
                      : () {
                          _controller.previousPage(
                            duration: const Duration(milliseconds: 220),
                            curve: Curves.easeOut,
                          );
                        },
                  icon: const Icon(Icons.arrow_back),
                ),
                Expanded(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(4, (i) {
                      final active = i == _index;
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: active ? 18 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: active ? AppColors.accentPurple : AppColors.cardBorder,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      );
                    }),
                  ),
                ),
                ElevatedButton(
                  onPressed: _finishing
                      ? null
                      : () {
                          if (last) {
                            _finish();
                            return;
                          }
                          _controller.nextPage(
                            duration: const Duration(milliseconds: 220),
                            curve: Curves.easeOut,
                          );
                        },
                  child: Text(last ? 'Начать' : 'Далее'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
