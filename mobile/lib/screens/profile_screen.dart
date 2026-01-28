import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:file_picker/file_picker.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../providers/billing_provider.dart';
import '../providers/spotify_provider.dart';
import '../providers/ws_provider.dart';
import '../providers/theme_provider.dart';
import '../services/api_service.dart';
import '../utils/constants.dart';
import '../utils/log.dart';
import '../widgets/help_icon.dart';
import 'legal/privacy_policy_screen.dart';
import 'legal/terms_of_service_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _tiktokUsernameController = TextEditingController();
  final _currentPasswordController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadUserInfo();
  }

  void _loadUserInfo() {
    final auth = context.read<AuthProvider>();
    final userInfo = auth.userInfo;
    _usernameController.text = userInfo['username']?.toString() ?? '';
    _emailController.text = userInfo['email']?.toString() ?? '';
    _tiktokUsernameController.text = (auth.tiktokUsername ?? '').toString();
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _tiktokUsernameController.dispose();
    _currentPasswordController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Профиль'),
        backgroundColor: AppColors.cardBackground,
        actions: const [
          HelpIcon(
            title: 'Профиль',
            message:
                'Здесь настраиваются данные аккаунта NovaBoost и важный параметр — TikTok-ник для подключения к LIVE.\n\nЕсли не приходят события чата/подарков — сначала проверьте TikTok-ник и подключение на «Панели».',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Consumer<AuthProvider>(
          builder: (context, auth, child) {
            final userInfo = auth.userInfo;
            
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Аватар и основная информация
                _buildProfileHeader(userInfo),
                const SizedBox(height: 24),
                
                // Информация о тарифе
                _buildTariffSection(userInfo),
                const SizedBox(height: 24),
                
                // Настройки профиля
                _buildProfileSettings(userInfo),
                const SizedBox(height: 24),

                _buildLegalAndAccountSection(),
                const SizedBox(height: 24),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildLegalAndAccountSection() {
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
              const Icon(Icons.description, color: AppColors.accentPurple, size: 20),
              const SizedBox(width: 8),
              Text(
                'Документы и аккаунт',
                style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const PrivacyPolicyScreen()),
                );
              },
              child: const Text('Политика конфиденциальности'),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const TermsOfServiceScreen()),
                );
              },
              child: const Text('Условия использования'),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _loading ? null : _logout,
              icon: const Icon(Icons.logout),
              label: const Text('Выйти'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.accentCyan,
                side: const BorderSide(color: AppColors.accentCyan),
              ),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _loading ? null : _showDeleteAccountDialog,
              icon: const Icon(Icons.delete_forever),
              label: const Text('Удалить аккаунт'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.accentRed,
                side: const BorderSide(color: AppColors.accentRed),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Удаление необратимо. Потребуется подтверждение.',
            style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    await context.read<AuthProvider>().logout();
  }

  Future<void> _showDeleteAccountDialog() async {
    final first = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Удалить аккаунт?'),
        content: const Text(
          'Это удалит ваш аккаунт и связанные данные (настройки, триггеры, звуки, аватар).\n\nПродолжить?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.accentRed),
            child: const Text('Продолжить'),
          ),
        ],
      ),
    );
    if (first != true || !mounted) return;

    final confirmCtrl = TextEditingController();
    final passCtrl = TextEditingController();
    try {
      final ok = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: const Text('Подтверждение'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Введите DELETE для подтверждения удаления.'),
              const SizedBox(height: 12),
              TextField(
                controller: confirmCtrl,
                decoration: const InputDecoration(labelText: 'Введите DELETE'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: passCtrl,
                obscureText: true,
                decoration: const InputDecoration(
                  labelText: 'Пароль (необязательно)',
                  hintText: 'Если хотите дополнительную защиту',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Отмена')),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              style: FilledButton.styleFrom(backgroundColor: AppColors.accentRed),
              child: const Text('Удалить'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;

      final confirm = confirmCtrl.text.trim();
      if (confirm.toUpperCase() != 'DELETE') {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Нужно ввести DELETE для подтверждения')),
        );
        return;
      }

      setState(() => _loading = true);
      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      final success = await api.deleteAccount(confirm: confirm, password: passCtrl.text);
      if (!success) {
        throw Exception(api.lastError ?? 'Не удалось удалить аккаунт');
      }
      await auth.logout();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Аккаунт удалён'), backgroundColor: AppColors.accentGreen),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Ошибка удаления аккаунта: $e')),
      );
    } finally {
      confirmCtrl.dispose();
      passCtrl.dispose();
      if (mounted) setState(() => _loading = false);
    }
  }

  Widget _buildProfileHeader(Map<String, dynamic> userInfo) {
    final username = userInfo['username']?.toString() ?? 'Не указан';
    final email = userInfo['email']?.toString() ?? '';
    final avatarUrl = userInfo['avatarUrl']?.toString();
    final hasEmail = email.trim().isNotEmpty;
    
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.accentPurple, AppColors.accentCyan],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          // Аватар
          GestureDetector(
            onTap: _selectAvatar,
            child: Stack(
              children: [
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white.withOpacity(0.2),
                    border: Border.all(color: Colors.white, width: 3),
                  ),
                  child: (avatarUrl != null && avatarUrl.isNotEmpty)
                      ? ClipOval(
                          child: CachedNetworkImage(
                            imageUrl: avatarUrl,
                            fit: BoxFit.cover,
                            width: 80,
                            height: 80,
                            placeholder: (_, __) => const Center(
                              child: SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation(Colors.white),
                                ),
                              ),
                            ),
                            errorWidget: (_, __, ___) => const Icon(
                              Icons.person,
                              color: Colors.white,
                              size: 40,
                            ),
                          ),
                        )
                      : const Icon(
                          Icons.person,
                          color: Colors.white,
                          size: 40,
                        ),
                ),
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: Container(
                    width: 24,
                    height: 24,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.edit,
                      color: AppColors.accentPurple,
                      size: 16,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          
          Text(
            '@$username',
            style: AppTextStyles.headline.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            hasEmail ? email : 'Email не указан',
            style: AppTextStyles.bodyMedium.copyWith(
              color: Colors.white70,
            ),
          ),
          if (!hasEmail) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.white.withOpacity(0.25)),
              ),
              child: const Text(
                'Добавьте email ниже — он нужен для входа и восстановления пароля.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTariffSection(Map<String, dynamic> userInfo) {
    final tariffName = userInfo['tariffName']?.toString() ?? 'Free';
    final subscriptionExpiresAt = userInfo['subscriptionExpiresAt']?.toString();
    final maxTikTokAccounts = userInfo['maxTikTokAccounts']?.toString();
    final tariffFeatures = _getTariffFeatures(tariffName);

    final tariffLower = tariffName.trim().toLowerCase();
    final isFreeTariff = tariffLower.isEmpty || tariffLower == 'free';
    final expiresAt = (subscriptionExpiresAt != null && subscriptionExpiresAt.trim().isNotEmpty)
        ? DateTime.tryParse(subscriptionExpiresAt.trim())
        : null;
    final isExpired = expiresAt != null && !expiresAt.isAfter(DateTime.now());
    final showUpgradeButton = isFreeTariff || isExpired;
    
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
                Icons.workspace_premium,
                color: AppColors.accentGreen,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Текущий тариф',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.accentGreen.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.accentGreen),
                ),
                child: Text(
                  tariffName,
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.accentGreen,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          
          // Особенности тарифа
          ...tariffFeatures.map((feature) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              children: [
                Icon(
                  Icons.check_circle,
                  color: AppColors.accentGreen,
                  size: 16,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    feature,
                    style: AppTextStyles.bodyMedium.copyWith(
                      color: AppColors.secondaryText,
                    ),
                  ),
                ),
              ],
            ),
          )),

          if (subscriptionExpiresAt != null && subscriptionExpiresAt.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Подписка активна до: $subscriptionExpiresAt',
              style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
            ),
          ],
          if (maxTikTokAccounts != null && maxTikTokAccounts.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              'Лимит TikTok аккаунтов: $maxTikTokAccounts',
              style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
            ),
          ],
          
          if (showUpgradeButton) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _showTariffUpgrade,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.accentPurple,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: const Text('Улучшить тариф'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildProfileSettings(Map<String, dynamic> userInfo) {
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
                Icons.settings,
                color: AppColors.accentCyan,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Настройки профиля',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          Consumer<ThemeProvider>(
            builder: (context, theme, _) {
              final supported = theme.premiumSupported;
              return Container(
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.03),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.cardBorder),
                ),
                child: SwitchListTile.adaptive(
                  value: theme.premiumEnabled,
                  onChanged: supported ? (v) => theme.setPremiumEnabled(v) : null,
                  activeColor: AppColors.accentPurple,
                  title: Text(
                    'Премиум интерфейс',
                    style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                  ),
                  subtitle: Text(
                    supported ? 'Визуальный стиль (Android)' : 'Доступно только на Android',
                    style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          
          // Поле имени пользователя
          TextField(
            controller: _usernameController,
            decoration: InputDecoration(
              labelText: 'Имя пользователя',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 12),

          Text(
            'Смена пароля (опционально)',
            style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 8),

          TextField(
            controller: _currentPasswordController,
            obscureText: true,
            decoration: InputDecoration(
              labelText: 'Текущий пароль',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 12),

          TextField(
            controller: _newPasswordController,
            obscureText: true,
            decoration: InputDecoration(
              labelText: 'Новый пароль',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 12),

          TextField(
            controller: _confirmPasswordController,
            obscureText: true,
            decoration: InputDecoration(
              labelText: 'Повторите новый пароль',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 16),
          
          // Поле email
          TextField(
            controller: _emailController,
            decoration: InputDecoration(
              labelText: 'Email',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // TikTok аккаунт (для подключения к LIVE)
          TextField(
            controller: _tiktokUsernameController,
            decoration: InputDecoration(
              labelText: 'TikTok аккаунт',
              hintText: 'ник без @',
              prefixIcon: const Icon(Icons.alternate_email),
              suffixIcon: const HelpIcon(
                title: 'TikTok аккаунт',
                message:
                    'Это ваш TikTok-ник (без @). Он нужен, чтобы приложение могло подключаться к вашему LIVE и получать события (чат, подарки и т.д.).\n\nПример: если в TikTok у вас @myname — здесь пишем myname.',
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.cardBorder),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: AppColors.accentPurple),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Spotify integration (playback + separate Spotify volume)
          Consumer<SpotifyProvider>(
            builder: (context, sp, _) {
              final connected = sp.connected;
              final track = (sp.track ?? '').trim();
              final artist = (sp.artist ?? '').trim();
              final vol = sp.volume;
              final err = (sp.error ?? '').trim();

              return Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.03),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.cardBorder),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.music_note, color: AppColors.accentGreen, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'Spotify',
                          style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
                        ),
                        const Spacer(),
                        if (!sp.configured)
                          const HelpIcon(
                            title: 'Spotify',
                            message:
                                'Интеграция Spotify скоро будет доступна. Сейчас подключение временно недоступно.',
                          ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      !sp.configured
                          ? 'Скоро будет доступно'
                          : (connected ? 'Подключено' : 'Не подключено'),
                      style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                    ),
                    if (connected && (track.isNotEmpty || artist.isNotEmpty)) ...[
                      const SizedBox(height: 8),
                      Text(
                        track.isNotEmpty ? track : '—',
                        style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (artist.isNotEmpty)
                        Text(
                          artist,
                          style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      if (vol != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            'Громкость Spotify: $vol%',
                            style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
                          ),
                        ),
                    ],
                    if (err.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        err,
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.accentRed),
                      ),
                    ],
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _loading
                            ? null
                            : () async {
                                if (!sp.configured) return;
                                if (connected) {
                                  await sp.disconnect();
                                } else {
                                  await sp.connect();
                                }
                              },
                        icon: Icon(connected ? Icons.link_off : Icons.link),
                        label: Text(
                          !sp.configured
                              ? 'Скоро'
                              : (connected ? 'Отключить Spotify' : 'Подключить Spotify'),
                        ),
                      ),
                    ),
                    if (connected) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: _loading ? null : () => sp.previous(),
                              child: const Text('Prev'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: _loading ? null : () => sp.togglePlayPause(),
                              child: Text(sp.playing ? 'Pause' : 'Play'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: _loading ? null : () => sp.next(),
                              child: const Text('Next'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 16),
          
          // Кнопка сохранения
          SizedBox(
            width: double.infinity,
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _loading ? null : _saveProfile,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentCyan,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    child: _loading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation(Colors.white),
                            ),
                          )
                        : const Text('Сохранить изменения'),
                  ),
                ),
                const SizedBox(width: 8),
                const HelpIcon(
                  title: 'Сохранить изменения',
                  message:
                      'Сохраняет профиль на сервере.\n\nВажно: после сохранения TikTok-ника можно вернуться на «Панель» и нажать «Подключиться к LIVE».',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }


  List<String> _getTariffFeatures(String tariff) {
    switch (tariff.toLowerCase()) {
      case 'nova free':
        return [
          'Только мобильные платформы',
          'Базовые голоса Google TTS',
          '1 TikTok аккаунт',
          'Базовая поддержка',
        ];
      case 'nova one':
        return [
          'Мобильные + десктопные платформы',
          'Все голоса (Google, Azure, Premium)',
          '3 TikTok аккаунта',
          'Приоритетная поддержка',
        ];
      case 'nova duo':
        return [
          'Мобильные + десктопные платформы',
          'Премиум голоса',
          '5 TikTok аккаунтов',
          'VIP поддержка',
        ];
      default:
        return ['Базовый функционал'];
    }
  }

  void _selectAvatar() {
    _selectAndUploadAvatar();
  }

  Future<void> _selectAndUploadAvatar() async {
    logDebug('Select avatar tapped');
    try {
      final res = await FilePicker.platform.pickFiles(
        type: FileType.image,
        allowMultiple: false,
        // On web, `path` is unavailable; need `bytes`.
        withData: kIsWeb,
      );
      if (res == null || res.files.isEmpty) return;

      final file = res.files.single;
      final String? path = kIsWeb ? null : file.path;
      final bytes = file.bytes;
      if (!kIsWeb) {
        if (path == null || path.isEmpty) {
          throw Exception('Не удалось получить путь к файлу');
        }
      } else {
        if (bytes == null || bytes.isEmpty) {
          throw Exception('Не удалось прочитать файл');
        }
      }

      if (!mounted) return;
      setState(() => _loading = true);

      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      final url = await api.uploadAvatar(
        filePath: path,
        bytes: kIsWeb ? bytes : null,
        filename: file.name,
      );
      if (url == null) {
        throw Exception(api.lastError ?? 'Не удалось загрузить аватар');
      }

      await auth.refreshUserInfo();

      if (!mounted) return;

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Аватар обновлён'),
            backgroundColor: AppColors.accentGreen,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки аватара: $e')),
        );
      }
      logDebug('Error uploading avatar: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showTariffUpgrade() {
    final billing = context.read<BillingProvider>();
    billing.initialize(productIds: _currentPlatformProductIds());

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => _buildTariffUpgradeModal(),
    );
  }

  Widget _buildTariffUpgradeModal() {
    final billing = context.watch<BillingProvider>();
    final products = billing.products;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: const BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Доступные тарифы',
            style: AppTextStyles.headline.copyWith(color: AppColors.primaryText),
          ),
          const SizedBox(height: 20),

          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Premium открывает:',
              style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
            ),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '• Безлимит озвучки чата\n'
              '• Безлимит триггеров/алёртов\n'
              '• Премиум голоса\n'
              '• Фоновая работа и плавающее окно\n'
              '• Расширенные настройки аудио вывода',
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Подпиской можно управлять в Google Play → Платежи и подписки → Подписки.',
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
            ),
          ),
          const SizedBox(height: 16),

          if (billing.error != null) ...[
            Text(
              billing.error!,
              style: AppTextStyles.bodyMedium.copyWith(color: AppColors.accentRed),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
          ],

          if (billing.loading)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(AppColors.accentPurple),
              ),
            ),

          ...products.map(_buildTariffOptionFromProduct),

          if (!billing.loading && products.isEmpty)
            Text(
              'Тарифы не найдены в магазине. Проверь productId и публикацию подписок.',
              style: AppTextStyles.bodyMedium.copyWith(color: AppColors.secondaryText),
              textAlign: TextAlign.center,
            ),

          const SizedBox(height: 20),

          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: billing.available ? () => context.read<BillingProvider>().restore() : null,
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.accentCyan,
                side: const BorderSide(color: AppColors.accentCyan),
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: const Text('Восстановить покупки'),
            ),
          ),
          const SizedBox(height: 8),

          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Закрыть'),
          ),
        ],
      ),
    );
  }

  Widget _buildTariffOptionFromProduct(ProductDetails p) {
    final billing = context.read<BillingProvider>();
    final isYearly = p.id == kAndroidProductYearly || p.id == kIosProductYearly;
    final name = isYearly ? 'Premium (год)' : 'Premium (месяц)';
    final color = isYearly ? AppColors.accentCyan : AppColors.accentPurple;
    final price = p.price;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: InkWell(
        onTap: billing.available ? () => billing.buy(p) : null,
        child: Row(
          children: [
            Expanded(
              child: Text(
                name,
                style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
              ),
            ),
            Text(
              price,
              style: AppTextStyles.subtitle.copyWith(
                color: color,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Set<String> _currentPlatformProductIds() {
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return {kIosProductMonthly, kIosProductYearly};
    }
    return {kAndroidProductMonthly, kAndroidProductYearly};
  }

  void _saveProfile() async {
    setState(() => _loading = true);
    try {
      final api = context.read<ApiService>();
      final auth = context.read<AuthProvider>();
      final ws = context.read<WsProvider>();

      final desiredUsernameRaw = _usernameController.text.trim();
      final desiredUsername = desiredUsernameRaw.replaceAll('@', '').trim().toLowerCase();
      final currentUsername = (auth.username ?? '').trim().toLowerCase();
      final needUsernameChange = desiredUsername.isNotEmpty && desiredUsername != currentUsername;

      final currentPassword = _currentPasswordController.text;
      final newPassword = _newPasswordController.text;
      final confirmPassword = _confirmPasswordController.text;
      final needPasswordChange = newPassword.trim().isNotEmpty;

      if (needPasswordChange && newPassword != confirmPassword) {
        throw Exception('Пароли не совпадают');
      }
      if (needPasswordChange && newPassword.trim().length < 6) {
        throw Exception('Новый пароль должен быть минимум 6 символов');
      }

      // If changing username or password, require current password.
      if ((needUsernameChange || needPasswordChange) && currentPassword.trim().isEmpty) {
        throw Exception('Введите текущий пароль для смены логина/пароля');
      }

      final raw = _tiktokUsernameController.text.trim();
      final normalized = raw.replaceAll('@', '').trim();

      final emailRaw = _emailController.text.trim();
      final email = emailRaw.isEmpty ? null : emailRaw;

      if (needUsernameChange || needPasswordChange) {
        final okCred = await api.updateCredentials(
          currentPassword: currentPassword,
          newUsername: needUsernameChange ? desiredUsername : null,
          newPassword: needPasswordChange ? newPassword : null,
        );
        if (!okCred) {
          throw Exception(api.lastError ?? 'Не удалось обновить логин/пароль');
        }
      }

      final okProfile = await api.updateProfile(email: email);
      if (!okProfile) {
        throw Exception(api.lastError ?? 'Не удалось сохранить email');
      }

      final success = await api.updateSettings(tiktokUsername: normalized);

      if (!success) {
        throw Exception('Не удалось сохранить TikTok аккаунт');
      }

      // Важно: обновить локально сохранённый ник, иначе Dashboard может
      // продолжать показывать старое значение из WsProvider/SharedPreferences.
      await ws.setSavedTikTokUsername(normalized);

      await auth.refreshUserInfo();

      _currentPasswordController.clear();
      _newPasswordController.clear();
      _confirmPasswordController.clear();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Настройки сохранены'),
            backgroundColor: AppColors.accentGreen,
          ),
        );
      }
      logDebug('Profile settings saved');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка сохранения: $e')),
        );
      }
      logDebug('Error saving profile: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

}