import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:audio_session/audio_session.dart';
import 'services/api_service.dart';
import 'services/client_info.dart';
import 'providers/auth_provider.dart';
import 'providers/ws_provider.dart';
import 'providers/billing_provider.dart';
import 'providers/theme_provider.dart';
import 'providers/notifications_provider.dart';
import 'providers/spotify_provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/tutorial_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'widgets/permissions_gate.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Best-effort: collect device/os info for admin visibility.
  await ClientInfo.init();

  // Настройка аудиосессии: позволяет корректно играть аудио в фоне (особенно iOS).
  final session = await AudioSession.instance;
  await session.configure(const AudioSessionConfiguration.music());
  await session.setActive(true);

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
        ChangeNotifierProvider<ThemeProvider>(create: (_) => ThemeProvider()),
        ChangeNotifierProvider<SpotifyProvider>(create: (_) => SpotifyProvider()),
        ChangeNotifierProxyProvider<ApiService, AuthProvider>(
          create: (ctx) => AuthProvider(apiService: Provider.of<ApiService>(ctx, listen: false)),
          update: (ctx, api, prev) => prev ?? AuthProvider(apiService: api),
        ),
        ChangeNotifierProxyProvider2<ApiService, AuthProvider, WsProvider>(
          create: (ctx) => WsProvider(apiService: Provider.of<ApiService>(ctx, listen: false)),
          update: (ctx, api, auth, prev) {
            final p = prev ?? WsProvider(apiService: api);
            p.updateAuth(apiService: api, jwtToken: auth.jwtToken, plan: auth.plan);
            return p;
          },
        ),
        ChangeNotifierProxyProvider2<ApiService, AuthProvider, NotificationsProvider>(
          create: (ctx) => NotificationsProvider(apiService: Provider.of<ApiService>(ctx, listen: false)),
          update: (ctx, api, auth, prev) {
            final p = prev ?? NotificationsProvider(apiService: api);
            p.updateAuth(apiService: api, jwtToken: auth.jwtToken);
            return p;
          },
        ),
        ChangeNotifierProxyProvider2<ApiService, AuthProvider, BillingProvider>(
          create: (ctx) => BillingProvider(apiService: Provider.of<ApiService>(ctx, listen: false)),
          update: (ctx, api, auth, prev) {
            final p = prev ?? BillingProvider(apiService: api);
            p.updateAuth(auth);
            return p;
          },
        ),
      ],
      child: Consumer<ThemeProvider>(
        builder: (context, theme, _) {
          final usePremium = theme.premiumEnabled;
          return MaterialApp(
            title: 'NovaBoost Mobile',
            theme: usePremium ? AppTheme.premiumDarkTheme : AppTheme.darkTheme,
            debugShowCheckedModeBanner: false,
            builder: (context, child) {
              return child ?? const SizedBox.shrink();
            },
            home: const AuthWrapper(),
          );
        },
      ),
    );
  }
}

class AuthWrapper extends StatefulWidget {
  const AuthWrapper({super.key});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  bool _initialized = false;
  bool? _tutorialSeen;

  @override
  void initState() {
    super.initState();
    _initAuth();
  }

  Future<void> _initAuth() async {
    await context.read<ThemeProvider>().initialize();
    await context.read<AuthProvider>().initialize();
    final prefs = await SharedPreferences.getInstance();
    final seen = prefs.getBool('tutorial_seen_v1') ?? false;
    if (mounted) {
      setState(() {
        _initialized = true;
        _tutorialSeen = seen;
      });
    }
  }

  Future<void> _markTutorialSeen() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('tutorial_seen_v1', true);
    if (mounted) {
      setState(() {
        _tutorialSeen = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_initialized || _tutorialSeen == null) {
      return const Scaffold(
        backgroundColor: AppColors.background,
        body: Center(
          child: CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(AppColors.accentPurple),
          ),
        ),
      );
    }

    return Consumer<AuthProvider>(
      builder: (ctx, auth, _) {
        if (!auth.isAuthenticated) {
          return const LoginScreen();
        }

        if (_tutorialSeen == false) {
          return TutorialScreen(onFinished: _markTutorialSeen);
        }

        return const PermissionsGate(child: HomeScreen());
      },
    );
  }
}