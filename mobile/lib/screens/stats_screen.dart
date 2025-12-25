import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../providers/ws_provider.dart';

class StatsScreen extends StatefulWidget {
  const StatsScreen({super.key});

  @override
  State<StatsScreen> createState() => _StatsScreenState();
}

class _StatsScreenState extends State<StatsScreen> {
  String _eventFilter = 'all';
  String _donationPeriod = 'today';
  bool _loadingDonations = false;
  String? _donationsError;
  Map<String, dynamic>? _overview;
  List<Map<String, dynamic>> _topDonors = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadDonations();
    });
  }

  Future<void> _loadDonations() async {
    if (_loadingDonations) return;
    setState(() {
      _loadingDonations = true;
      _donationsError = null;
    });
    Map<String, dynamic>? overview;
    List<Map<String, dynamic>> donors = const [];
    String? error;

    try {
      final api = context.read<AuthProvider>().apiService;
      final results = await Future.wait([
        api.getStatsOverview(),
        api.getTopDonors(period: _donationPeriod, limit: 5),
      ]);
      overview = results[0] as Map<String, dynamic>?;
      donors = results[1] as List<Map<String, dynamic>>;
    } catch (_) {
      error = 'Не удалось загрузить статистику';
    }

    if (!mounted) return;
    setState(() {
      _overview = overview;
      _topDonors = donors;
      _donationsError = error;
      _loadingDonations = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<WsProvider>(
      builder: (context, ws, child) {
        return SafeArea(
          child: Column(
            children: [
              // Заголовок с фильтрами
              _buildHeader(),

              // Исторические донаты (из API)
              _buildDonationsSection(),

              // Статистика текущего стрима (live)
              _buildStatsSection(ws),

              // Список событий
              Expanded(child: _buildEventsList(ws)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.cardBorder)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.accentGreen.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.analytics,
                  color: AppColors.accentGreen,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Статистика эфира',
                      style: AppTextStyles.headline.copyWith(
                        color: AppColors.primaryText,
                      ),
                    ),
                    Text(
                      'События и аналитика стрима',
                      style: AppTextStyles.bodySmall.copyWith(
                        color: AppColors.secondaryText,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Обновить',
                onPressed: _loadingDonations ? null : _loadDonations,
                icon: Icon(
                  Icons.refresh,
                  color: _loadingDonations ? AppColors.secondaryText : AppColors.primaryText,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Фильтры событий
          _buildEventFilters(),
        ],
      ),
    );
  }

  Widget _buildDonationsSection() {
    const periods = [
      {'id': 'today', 'title': 'Сегодня (UTC)'},
      {'id': '7d', 'title': '7д'},
      {'id': '30d', 'title': '30д'},
      {'id': 'all', 'title': 'Всё'},
    ];

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 0),
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
              const Icon(Icons.leaderboard, color: AppColors.accentPurple, size: 20),
              const SizedBox(width: 8),
              Text(
                'Донаты',
                style: AppTextStyles.subtitle.copyWith(color: AppColors.primaryText),
              ),
              const Spacer(),
              if (_loadingDonations)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 12),

          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: periods.map((p) {
                final id = p['id'] as String;
                final title = p['title'] as String;
                final isSelected = _donationPeriod == id;
                return Container(
                  margin: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    selected: isSelected,
                    label: Text(
                      title,
                      style: TextStyle(
                        color: isSelected ? Colors.white : AppColors.secondaryText,
                      ),
                    ),
                    onSelected: (selected) {
                      setState(() => _donationPeriod = id);
                      _loadDonations();
                    },
                    backgroundColor: AppColors.cardBackground,
                    selectedColor: AppColors.accentPurple,
                    side: BorderSide(
                      color: isSelected ? AppColors.accentPurple : AppColors.cardBorder,
                    ),
                  ),
                );
              }).toList(),
            ),
          ),

          const SizedBox(height: 12),

          if (_donationsError != null)
            Text(
              _donationsError!,
              style: AppTextStyles.bodySmall.copyWith(color: AppColors.accentRed),
            ),

          _buildOverviewRow(),

          const SizedBox(height: 12),
          Text(
            'Топ-5 дарителей',
            style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
          ),
          const SizedBox(height: 8),
          _buildTopDonorsList(),
        ],
      ),
    );
  }

  Widget _buildOverviewRow() {
    final m = _overview ?? const <String, dynamic>{};
    int toIntValue(dynamic v) {
      if (v is int) return v;
      if (v is num) return v.toInt();
      return int.tryParse(v?.toString() ?? '') ?? 0;
    }

    final total = toIntValue(m['total_coins']);
    final today = toIntValue(m['today_utc']);
    final last7 = toIntValue(m['last_7d']);
    final last30 = toIntValue(m['last_30d']);

    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        SizedBox(
          width: (MediaQuery.of(context).size.width - 16 * 2 - 12) / 2,
          child: _buildStatCard('Всё', '$total', Icons.all_inclusive, AppColors.accentPurple),
        ),
        SizedBox(
          width: (MediaQuery.of(context).size.width - 16 * 2 - 12) / 2,
          child: _buildStatCard('Сегодня', '$today', Icons.today, AppColors.accentGreen),
        ),
        SizedBox(
          width: (MediaQuery.of(context).size.width - 16 * 2 - 12) / 2,
          child: _buildStatCard('7д', '$last7', Icons.calendar_view_week, AppColors.accentCyan),
        ),
        SizedBox(
          width: (MediaQuery.of(context).size.width - 16 * 2 - 12) / 2,
          child: _buildStatCard('30д', '$last30', Icons.calendar_month, AppColors.accentPurple),
        ),
      ],
    );
  }

  Widget _buildTopDonorsList() {
    if (_topDonors.isEmpty) {
      return Text(
        'Нет данных',
        style: AppTextStyles.bodySmall.copyWith(color: AppColors.secondaryText),
      );
    }

    int toIntValue(dynamic v) {
      if (v is int) return v;
      if (v is num) return v.toInt();
      return int.tryParse(v?.toString() ?? '') ?? 0;
    }

    return Column(
      children: List.generate(_topDonors.length, (i) {
        final r = _topDonors[i];
        final username = (r['donor_username'] ?? '').toString();
        final coins = toIntValue(r['coins']);
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppColors.cardBorder),
          ),
          child: Row(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: AppColors.accentPurple.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(
                    '${i + 1}',
                    style: AppTextStyles.bodySmall.copyWith(
                      color: AppColors.accentPurple,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  username.startsWith('@') ? username : '@$username',
                  style: AppTextStyles.bodyMedium.copyWith(color: AppColors.primaryText),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.accentPurple.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  '$coins💎',
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.accentPurple,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        );
      }),
    );
  }

  Widget _buildEventFilters() {
    final filters = [
      {'id': 'all', 'title': 'Все', 'icon': Icons.list},
      {'id': 'gifts', 'title': 'Подарки', 'icon': Icons.card_giftcard},
      {'id': 'chat', 'title': 'Чат', 'icon': Icons.chat},
      {'id': 'viewers', 'title': 'Зрители', 'icon': Icons.people},
    ];

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: filters.map((filter) {
          final isSelected = _eventFilter == filter['id'];
          return Container(
            margin: const EdgeInsets.only(right: 8),
            child: FilterChip(
              selected: isSelected,
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    filter['icon'] as IconData,
                    size: 16,
                    color: isSelected ? Colors.white : AppColors.secondaryText,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    filter['title'] as String,
                    style: TextStyle(
                      color: isSelected ? Colors.white : AppColors.secondaryText,
                    ),
                  ),
                ],
              ),
              onSelected: (selected) {
                setState(() => _eventFilter = filter['id'] as String);
              },
              backgroundColor: AppColors.cardBackground,
              selectedColor: AppColors.accentPurple,
              side: BorderSide(
                color: isSelected ? AppColors.accentPurple : AppColors.cardBorder,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildStatsSection(WsProvider ws) {
    final streamStats = ws.streamStats;
    
    return Container(
      margin: const EdgeInsets.all(16),
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
                Icons.trending_up,
                color: AppColors.accentGreen,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Статистика стрима',
                style: AppTextStyles.subtitle.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.accentGreen.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  streamStats['streamDuration']?.toString() ?? '0м',
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.accentGreen,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Основные метрики
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  'Алмазы',
                  '${streamStats['totalDiamonds'] ?? 0}',
                  Icons.diamond,
                  AppColors.accentPurple,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  'Подарки',
                  '${streamStats['totalGifts'] ?? 0}',
                  Icons.card_giftcard,
                  AppColors.accentCyan,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  'Зрители',
                  '${streamStats['totalViewers'] ?? 0}',
                  Icons.people,
                  AppColors.accentGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Топ донатер и самый дорогой подарок
          _buildTopStats(ws),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 4),
          Text(
            value,
            style: AppTextStyles.subtitle.copyWith(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
          Text(
            title,
            style: AppTextStyles.bodySmall.copyWith(
              color: AppColors.secondaryText,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopStats(WsProvider ws) {
    final streamStats = ws.streamStats;
    final mostExpensive = streamStats['mostExpensiveGift'] as Map<String, dynamic>?;
    final topGifter = streamStats['topGifter'] as String?;

    return Column(
      children: [
        if (topGifter != null) ...[
          _buildTopStatRow(
            'Топ донатер',
            '@$topGifter',
            Icons.star,
            AppColors.accentPurple,
          ),
          const SizedBox(height: 8),
        ],
        if (mostExpensive != null) ...[
          _buildTopStatRow(
            'Самый дорогой подарок',
            '${mostExpensive['name']} (${mostExpensive['diamonds']}💎)',
            Icons.workspace_premium,
            AppColors.accentCyan,
          ),
        ],
      ],
    );
  }

  Widget _buildTopStatRow(String title, String value, IconData icon, Color color) {
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: color.withOpacity(0.2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: color, size: 16),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppTextStyles.bodySmall.copyWith(
                  color: AppColors.secondaryText,
                ),
              ),
              Text(
                value,
                style: AppTextStyles.bodyMedium.copyWith(
                  color: AppColors.primaryText,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEventsList(WsProvider ws) {
    final filteredEvents = _getFilteredEvents(ws);
    
    if (filteredEvents.isEmpty) {
      return _buildEmptyState();
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: filteredEvents.length,
      itemBuilder: (context, index) {
        final event = filteredEvents[index];
        return _buildEventCard(event);
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.inbox_outlined,
            color: AppColors.secondaryText,
            size: 64,
          ),
          const SizedBox(height: 16),
          Text(
            'Нет событий',
            style: AppTextStyles.subtitle.copyWith(
              color: AppColors.primaryText,
            ),
          ),
          Text(
            'События появятся когда стрим будет активен',
            style: AppTextStyles.bodyMedium.copyWith(
              color: AppColors.secondaryText,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(Map<String, dynamic> event) {
    final type = event['type']?.toString() ?? '';
    final category = event['category']?.toString() ?? '';
    final text = event['text']?.toString() ?? '';
    final timestamp = event['timestamp'] as DateTime?;
    final raw = event['raw'] as Map<String, dynamic>? ?? {};
    
    IconData icon;
    Color iconColor;
    String title;
    String subtitle;
    Widget? trailing;
    
    switch (type) {
      case 'gift':
        icon = Icons.card_giftcard;
        iconColor = AppColors.accentPurple;
        title = raw['gift_name']?.toString() ?? 'Подарок';
        final user = raw['user']?.toString() ?? 'Аноним';
        final count = raw['count']?.toString() ?? '1';
        subtitle = '$user • ${count}x';
        final diamonds = raw['diamonds'] ?? raw['diamond_count'] ?? 0;
        trailing = Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: AppColors.accentPurple.withOpacity(0.2),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            '$diamonds💎',
            style: AppTextStyles.bodySmall.copyWith(
              color: AppColors.accentPurple,
              fontWeight: FontWeight.bold,
            ),
          ),
        );
        break;
      case 'chat':
        icon = Icons.chat_bubble;
        iconColor = AppColors.accentCyan;
        title = raw['message']?.toString() ?? 'Сообщение';
        subtitle = raw['user']?.toString() ?? 'Аноним';
        break;
      case 'join':
        icon = Icons.person_add;
        iconColor = AppColors.accentGreen;
        title = 'Зашёл в эфир';
        subtitle = (raw['username']?.toString().trim().isNotEmpty == true)
            ? (raw['username']?.toString().trim().startsWith('@') == true
                ? raw['username']!.toString().trim()
                : '@${raw['username']!.toString().trim()}')
            : (raw['nickname']?.toString().trim().isNotEmpty == true)
                ? raw['nickname']!.toString().trim()
                : (raw['user']?.toString() ?? 'Аноним');
        break;
      case 'viewer_join':
        icon = Icons.person_add;
        iconColor = AppColors.accentGreen;
        title = 'Зашёл в эфир';
        subtitle = (raw['username']?.toString().trim().isNotEmpty == true)
            ? (raw['username']?.toString().trim().startsWith('@') == true
                ? raw['username']!.toString().trim()
                : '@${raw['username']!.toString().trim()}')
            : (raw['nickname']?.toString().trim().isNotEmpty == true)
                ? raw['nickname']!.toString().trim()
                : (raw['user']?.toString() ?? 'Аноним');
        break;
      case 'follow':
        icon = Icons.favorite;
        iconColor = AppColors.accentPurple;
        title = 'Подписался';
        subtitle = raw['user']?.toString() ?? 'Аноним';
        break;
      case 'like':
        icon = Icons.thumb_up;
        iconColor = AppColors.accentCyan;
        title = 'Лайки';
        final user = raw['user']?.toString() ?? 'Аноним';
        final count = raw['count']?.toString() ?? '1';
        subtitle = '$user • $count лайков';
        break;
      default:
        icon = Icons.info;
        iconColor = AppColors.secondaryText;
        title = text;
        subtitle = category;
    }
    
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.cardBorder),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: iconColor.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: iconColor, size: 18),
          ),
          const SizedBox(width: 12),
          
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.bodyMedium.copyWith(
                    color: AppColors.primaryText,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: AppTextStyles.bodySmall.copyWith(
                    color: AppColors.secondaryText,
                  ),
                ),
              ],
            ),
          ),
          
          if (trailing != null) ...[
            const SizedBox(width: 8),
            trailing,
          ],
          
          const SizedBox(width: 8),
          Text(
            _formatTimestamp(timestamp),
            style: AppTextStyles.bodySmall.copyWith(
              color: AppColors.secondaryText,
            ),
          ),
        ],
      ),
    );
  }

  List<Map<String, dynamic>> _getFilteredEvents(WsProvider ws) {
    return ws.getFilteredEvents(_eventFilter);
  }

  String _formatTimestamp(DateTime? timestamp) {
    if (timestamp == null) return '';
    
    final now = DateTime.now();
    final diff = now.difference(timestamp);
    
    if (diff.inMinutes < 1) {
      return 'сейчас';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}м';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}ч';
    } else {
      return '${diff.inDays}д';
    }
  }
}