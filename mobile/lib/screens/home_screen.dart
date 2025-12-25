import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/notifications_provider.dart';
import '../providers/ws_provider.dart';
import '../services/overlay_bridge.dart';
import '../theme/app_theme.dart';
import 'alerts_screen.dart';
import 'dashboard_screen.dart';
import 'notifications_screen.dart';
import 'profile_screen.dart';
import 'stats_screen.dart';
import 'voice_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  int _currentIndex = 0;

  final _pages = const [
    DashboardScreen(),
    StatsScreen(),
    AlertsScreen(),
    VoiceScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final ws = context.read<WsProvider>();
    if (state == AppLifecycleState.paused) {
      // Показываем оверлей только когда реально подключены к LIVE.
      if (ws.tiktokConnected) {
        OverlayBridge.show();
      }
    }
    if (state == AppLifecycleState.resumed) {
      OverlayBridge.hide();
      context.read<NotificationsProvider>().refreshUnreadCount();
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final ws = context.watch<WsProvider>();
    final notifications = context.watch<NotificationsProvider>();
    final live = ws.tiktokConnected;

    return Scaffold(
      appBar: AppBar(
        title: const Text('NovaBoost Mobile', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: live ? AppColors.accentGreen.withOpacity(0.2) : AppColors.cardBackground,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: live ? AppColors.accentGreen : AppColors.cardBorder),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: live ? AppColors.accentGreen : AppColors.secondaryText,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      live ? 'LIVE' : 'OFFLINE',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (notifications.unreadCount > 0)
            IconButton(
              tooltip: 'Уведомления',
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                );
              },
              icon: Stack(
                clipBehavior: Clip.none,
                children: [
                  const Icon(Icons.notifications),
                  Positioned(
                    right: -6,
                    top: -6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.accentRed,
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: AppColors.background, width: 1.5),
                      ),
                      child: Text(
                        notifications.unreadCount > 99 ? '99+' : notifications.unreadCount.toString(),
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          IconButton(icon: const Icon(Icons.logout), onPressed: () => auth.logout()),
        ],
      ),
      body: IndexedStack(index: _currentIndex, children: _pages),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        backgroundColor: AppColors.cardBackground,
        selectedItemColor: AppColors.accentPurple,
        unselectedItemColor: AppColors.secondaryText,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Панель'),
          BottomNavigationBarItem(icon: Icon(Icons.analytics), label: 'Статистика'),
          BottomNavigationBarItem(icon: Icon(Icons.notifications_active), label: 'Алёрты'),
          BottomNavigationBarItem(icon: Icon(Icons.record_voice_over), label: 'TTS'),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: 'Профиль'),
        ],
      ),
    );
  }
}