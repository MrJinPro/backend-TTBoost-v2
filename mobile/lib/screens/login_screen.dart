import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/help_icon.dart';
import 'legal/privacy_policy_screen.dart';
import 'legal/terms_of_service_screen.dart';
import 'password_reset_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  int _mode = 0; // 0=login, 1=register
  bool _loading = false;
  String? _error;
  bool _obscurePassword = true;

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final auth = context.read<AuthProvider>();
    String? error;
    if (_mode == 0) {
      error = await auth.login(
        username: _userCtrl.text.trim(),
        password: _passCtrl.text,
      );
    } else {
      error = await auth.register(
        username: _userCtrl.text.trim(),
        password: _passCtrl.text,
      );
    }
    if (mounted) {
      setState(() {
        _loading = false;
        _error = error;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.accentPurple, AppColors.background],
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 400),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Image.asset('asset/nova_icon.png', height: 96),
                      const SizedBox(height: 16),
                      const Text(
                        'NovaBoost Mobile',
                        style: TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.bold,
                          color: AppColors.accentPurple,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Звёзды начинаются здесь!',
                        style: TextStyle(color: AppColors.secondaryText),
                      ),
                      const SizedBox(height: 24),
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton(
                              onPressed: _loading
                                  ? null
                                  : () => setState(() {
                                        _mode = 0;
                                        _error = null;
                                      }),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: _mode == 0
                                    ? AppColors.accentPurple
                                    : AppColors.cardBorder,
                              ),
                              child: const Text('Вход'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: ElevatedButton(
                              onPressed: _loading
                                  ? null
                                  : () => setState(() {
                                        _mode = 1;
                                        _error = null;
                                      }),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: _mode == 1
                                    ? AppColors.accentPurple
                                    : AppColors.cardBorder,
                              ),
                              child: const Text('Регистрация'),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      if (_error != null)
                        Container(
                          padding: const EdgeInsets.all(12),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: AppColors.accentRed.withOpacity(0.2),
                            border: Border.all(color: AppColors.accentRed),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            _error!,
                            style: const TextStyle(color: AppColors.accentRed),
                          ),
                        ),
                      if (_mode == 0)
                        Container(
                          padding: const EdgeInsets.all(12),
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                            color: AppColors.accentPurple.withOpacity(0.08),
                            border: Border.all(color: AppColors.cardBorder),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text(
                            'Рекомендуем привязать email в «Профиле»: это нужно для восстановления пароля.',
                            style: TextStyle(color: AppColors.secondaryText),
                          ),
                        ),
                      TextField(
                        controller: _userCtrl,
                        decoration: InputDecoration(
                          labelText: _mode == 0 ? 'Email или логин' : 'Email',
                          prefixIcon: Icon(_mode == 0 ? Icons.person : Icons.alternate_email),
                          suffixIcon: const HelpIcon(
                            title: 'Вход / регистрация',
                            message:
                                'Для входа можно использовать email или старый логин.\n\nДля регистрации используйте email (он понадобится для восстановления пароля).\n\nTikTok-ник указывается отдельно в «Профиле» (без @).',
                          ),
                        ),
                        enabled: !_loading,
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        controller: _passCtrl,
                        decoration: InputDecoration(
                          labelText: 'Пароль',
                          prefixIcon: const Icon(Icons.lock),
                          suffixIcon: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                tooltip: _obscurePassword ? 'Показать пароль' : 'Скрыть пароль',
                                visualDensity: VisualDensity.compact,
                                onPressed: _loading
                                    ? null
                                    : () => setState(() => _obscurePassword = !_obscurePassword),
                                icon: Icon(
                                  _obscurePassword ? Icons.visibility : Icons.visibility_off,
                                ),
                              ),
                              const HelpIcon(
                                title: 'Пароль',
                                message:
                                    'Пароль для вашего аккаунта NovaBoost.\n\nЕсли забыли — воспользуйтесь восстановлением по email (если email привязан к аккаунту).',
                              ),
                            ],
                          ),
                        ),
                        obscureText: _obscurePassword,
                        enabled: !_loading,
                      ),
                      const SizedBox(height: 24),
                      SizedBox(
                        width: double.infinity,
                        child: Row(
                          children: [
                            Expanded(
                              child: ElevatedButton(
                                onPressed: _loading ? null : _submit,
                                child: _loading
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : Text(_mode == 0 ? 'Войти' : 'Зарегистрироваться'),
                              ),
                            ),
                            const SizedBox(width: 8),
                            HelpIcon(
                              title: _mode == 0 ? 'Вход' : 'Регистрация',
                              message: _mode == 0
                                  ? 'Выполняет вход в аккаунт NovaBoost. После входа откройте «Профиль» и укажите TikTok-ник, затем на «Панели» подключитесь к LIVE.'
                                  : 'Создаёт новый аккаунт NovaBoost. После регистрации — укажите TikTok-ник в «Профиле» и подключитесь к LIVE на «Панели».',
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (_mode == 0)
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton(
                            onPressed: _loading
                                ? null
                                : () {
                                    Navigator.of(context).push(
                                      MaterialPageRoute(
                                        builder: (_) => PasswordResetScreen(
                                          prefillLoginOrEmail: _userCtrl.text.trim(),
                                        ),
                                      ),
                                    );
                                  },
                            child: const Text('Забыли пароль?'),
                          ),
                        ),
                      Wrap(
                        alignment: WrapAlignment.center,
                        spacing: 12,
                        runSpacing: 6,
                        children: [
                          TextButton(
                            onPressed: () {
                              Navigator.of(context).push(
                                MaterialPageRoute(builder: (_) => const PrivacyPolicyScreen()),
                              );
                            },
                            child: const Text('Политика'),
                          ),
                          TextButton(
                            onPressed: () {
                              Navigator.of(context).push(
                                MaterialPageRoute(builder: (_) => const TermsOfServiceScreen()),
                              );
                            },
                            child: const Text('Условия'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}