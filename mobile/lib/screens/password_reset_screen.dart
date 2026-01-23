import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';

class PasswordResetScreen extends StatefulWidget {
  const PasswordResetScreen({super.key, this.prefillLoginOrEmail});

  final String? prefillLoginOrEmail;

  @override
  State<PasswordResetScreen> createState() => _PasswordResetScreenState();
}

class _PasswordResetScreenState extends State<PasswordResetScreen> {
  final _loginOrEmailCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _newPassCtrl = TextEditingController();
  final _newPass2Ctrl = TextEditingController();

  bool _loading = false;
  bool _codeSent = false;
  String? _error;
  String? _info;

  bool _obscure1 = true;
  bool _obscure2 = true;

  @override
  void initState() {
    super.initState();
    _loginOrEmailCtrl.text = widget.prefillLoginOrEmail?.trim() ?? '';
  }

  @override
  void dispose() {
    _loginOrEmailCtrl.dispose();
    _codeCtrl.dispose();
    _newPassCtrl.dispose();
    _newPass2Ctrl.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    setState(() {
      _loading = true;
      _error = null;
      _info = null;
    });

    final auth = context.read<AuthProvider>();
    final ok = await auth.apiService.requestPasswordReset(
      loginOrEmail: _loginOrEmailCtrl.text.trim(),
    );

    if (!mounted) return;
    setState(() {
      _loading = false;
      if (ok) {
        _codeSent = true;
        _info = 'Если email привязан к аккаунту — код отправлен. Проверьте «Входящие» и «Спам».';
      } else {
        _error = auth.apiService.lastError ?? 'Не удалось отправить код';
      }
    });
  }

  Future<void> _confirm() async {
    final p1 = _newPassCtrl.text;
    final p2 = _newPass2Ctrl.text;
    if (p1 != p2) {
      setState(() {
        _error = 'Пароли не совпадают';
        _info = null;
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _info = null;
    });

    final auth = context.read<AuthProvider>();
    final ok = await auth.apiService.confirmPasswordReset(
      loginOrEmail: _loginOrEmailCtrl.text.trim(),
      code: _codeCtrl.text.trim(),
      newPassword: p1,
    );

    if (!mounted) return;

    setState(() {
      _loading = false;
      if (ok) {
        _info = 'Пароль обновлён. Теперь выполните вход с новым паролем.';
      } else {
        _error = auth.apiService.lastError ?? 'Не удалось сбросить пароль';
      }
    });

    if (ok && mounted) {
      await Future.delayed(const Duration(milliseconds: 400));
      if (mounted) Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Восстановление пароля'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Укажите логин или email. Мы отправим код на привязанный email.',
                      style: TextStyle(color: AppColors.secondaryText),
                    ),
                    const SizedBox(height: 12),
                    if (_error != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: AppColors.accentRed.withOpacity(0.15),
                          border: Border.all(color: AppColors.accentRed),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _error!,
                          style: const TextStyle(color: AppColors.accentRed),
                        ),
                      ),
                    if (_info != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: AppColors.accentGreen.withOpacity(0.15),
                          border: Border.all(color: AppColors.accentGreen),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _info!,
                          style: const TextStyle(color: AppColors.accentGreen),
                        ),
                      ),
                    TextField(
                      controller: _loginOrEmailCtrl,
                      enabled: !_loading,
                      decoration: const InputDecoration(
                        labelText: 'Логин или email',
                        prefixIcon: Icon(Icons.alternate_email),
                      ),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton(
                      onPressed: _loading ? null : _sendCode,
                      child: _loading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : Text(_codeSent ? 'Отправить код ещё раз' : 'Отправить код'),
                    ),
                    if (_codeSent) ...[
                      const SizedBox(height: 16),
                      TextField(
                        controller: _codeCtrl,
                        enabled: !_loading,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Код из письма',
                          prefixIcon: Icon(Icons.pin),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _newPassCtrl,
                        enabled: !_loading,
                        obscureText: _obscure1,
                        decoration: InputDecoration(
                          labelText: 'Новый пароль',
                          prefixIcon: const Icon(Icons.lock),
                          suffixIcon: IconButton(
                            tooltip: _obscure1 ? 'Показать пароль' : 'Скрыть пароль',
                            onPressed: _loading ? null : () => setState(() => _obscure1 = !_obscure1),
                            icon: Icon(_obscure1 ? Icons.visibility : Icons.visibility_off),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _newPass2Ctrl,
                        enabled: !_loading,
                        obscureText: _obscure2,
                        decoration: InputDecoration(
                          labelText: 'Повторите новый пароль',
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            tooltip: _obscure2 ? 'Показать пароль' : 'Скрыть пароль',
                            onPressed: _loading ? null : () => setState(() => _obscure2 = !_obscure2),
                            icon: Icon(_obscure2 ? Icons.visibility : Icons.visibility_off),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _loading ? null : _confirm,
                        child: _loading
                            ? const SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Text('Сбросить пароль'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
