import 'package:flutter/material.dart';

class TermsOfServiceScreen extends StatelessWidget {
  const TermsOfServiceScreen({super.key});

  static const String lastUpdated = '24.12.2025';

  static const String _text = '''
Условия использования NovaBoost

Дата обновления: $lastUpdated

1. Назначение
NovaBoost предоставляет инструменты для озвучки и алёртов во время LIVE-эфиров.

2. Аккаунт
- Вы отвечаете за сохранность логина/пароля.
- Вы обязуетесь использовать приложение законно и не нарушать правила платформ (включая TikTok).

3. Контент пользователя
- Вы можете загружать звуки и аватар. Вы подтверждаете, что имеете права на эти файлы.
- Запрещено загружать материалы, нарушающие права третьих лиц.

4. Подписки и платежи
- Оплата и управление подпиской выполняются через Google Play / App Store.
- Отмена подписки осуществляется в настройках магазина.

5. Ограничение ответственности
Сервис предоставляется «как есть». Мы стараемся обеспечить стабильность, но не гарантируем непрерывную работу при внешних сбоях (интернет, платформы, сторонние сервисы).

6. Прекращение использования и удаление аккаунта
Вы можете удалить аккаунт в приложении: Профиль → Удалить аккаунт.

7. Контакты
Email: support@novaboost.cloud
''';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Условия использования'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: SelectableText(
            _text,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      ),
    );
  }
}
