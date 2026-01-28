import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';

class GiftPickerDialog extends StatefulWidget {
  const GiftPickerDialog({super.key});

  @override
  State<GiftPickerDialog> createState() => _GiftPickerDialogState();
}

class _GiftPickerDialogState extends State<GiftPickerDialog> {
  List<Map<String, dynamic>> _gifts = [];
  List<Map<String, dynamic>> _filteredGifts = [];
  bool _loading = true;
  String _searchQuery = '';
  int? _minDiamonds;
  int? _maxDiamonds;

  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadGifts();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadGifts() async {
    setState(() => _loading = true);
    try {
      // Загрузка библиотеки подарков через API
      final api = context.read<ApiService>();
      final gifts = await api.getGiftsLibrary();
      setState(() {
        _gifts = gifts;
        _filteredGifts = gifts;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки подарков: $e')),
        );
      }
    }
  }

  void _applyFilters() {
    setState(() {
      _filteredGifts = _gifts.where((gift) {
        // Поиск по названию (русскому или английскому)
        final nameRu = (gift['name_ru'] as String? ?? '').toLowerCase();
        final nameEn = (gift['name_en'] as String? ?? '').toLowerCase();
        final query = _searchQuery.toLowerCase();
        final matchesSearch = _searchQuery.isEmpty ||
            nameRu.contains(query) ||
            nameEn.contains(query);

        // Фильтр по стоимости
        final diamonds = gift['diamond_count'] as int? ?? 0;
        final matchesMin = _minDiamonds == null || diamonds >= _minDiamonds!;
        final matchesMax = _maxDiamonds == null || diamonds <= _maxDiamonds!;

        return matchesSearch && matchesMin && matchesMax;
      }).toList();

      // Сортируем по стоимости (от дешевых к дорогим)
      _filteredGifts.sort((a, b) {
        final aDiamonds = a['diamond_count'] as int? ?? 0;
        final bDiamonds = b['diamond_count'] as int? ?? 0;
        return aDiamonds.compareTo(bDiamonds);
      });
    });
  }

  void _resetFilters() {
    setState(() {
      _searchQuery = '';
      _minDiamonds = null;
      _maxDiamonds = null;
      _searchController.clear();
      _applyFilters();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: Container(
        width: MediaQuery.of(context).size.width * 0.9,
        height: MediaQuery.of(context).size.height * 0.85,
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Заголовок
            Row(
              children: [
                const Text(
                  'Выберите подарок',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Поиск
            TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Поиск по названию...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                          _applyFilters();
                        },
                      )
                    : null,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: (value) {
                setState(() => _searchQuery = value);
                _applyFilters();
              },
            ),
            const SizedBox(height: 12),

            // Фильтры по стоимости
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<int?>(
                    value: _minDiamonds,
                    decoration: InputDecoration(
                      labelText: 'Мин. алмазы',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    items: const [
                      DropdownMenuItem(value: null, child: Text('Любая')),
                      DropdownMenuItem(value: 1, child: Text('1+')),
                      DropdownMenuItem(value: 10, child: Text('10+')),
                      DropdownMenuItem(value: 50, child: Text('50+')),
                      DropdownMenuItem(value: 100, child: Text('100+')),
                      DropdownMenuItem(value: 500, child: Text('500+')),
                      DropdownMenuItem(value: 1000, child: Text('1000+')),
                    ],
                    onChanged: (value) {
                      setState(() => _minDiamonds = value);
                      _applyFilters();
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<int?>(
                    value: _maxDiamonds,
                    decoration: InputDecoration(
                      labelText: 'Макс. алмазы',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    items: const [
                      DropdownMenuItem(value: null, child: Text('Любая')),
                      DropdownMenuItem(value: 10, child: Text('10')),
                      DropdownMenuItem(value: 50, child: Text('50')),
                      DropdownMenuItem(value: 100, child: Text('100')),
                      DropdownMenuItem(value: 500, child: Text('500')),
                      DropdownMenuItem(value: 1000, child: Text('1000')),
                      DropdownMenuItem(value: 5000, child: Text('5000')),
                    ],
                    onChanged: (value) {
                      setState(() => _maxDiamonds = value);
                      _applyFilters();
                    },
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Сбросить фильтры',
                  onPressed: _resetFilters,
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Счетчик результатов
            Text(
              'Найдено: ${_filteredGifts.length} из ${_gifts.length}',
              style: TextStyle(color: Colors.grey[600]),
            ),
            const SizedBox(height: 12),

            // Список подарков
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _filteredGifts.isEmpty
                      ? const Center(child: Text('Подарки не найдены'))
                      : ListView.separated(
                          itemCount: _filteredGifts.length,
                          separatorBuilder: (context, index) => const SizedBox(height: 8),
                          itemBuilder: (context, index) {
                            final gift = _filteredGifts[index];
                            final nameRu = gift['name_ru'] as String? ?? '';
                            final nameEn = gift['name_en'] as String? ?? '';
                            final image = gift['image'] as String? ?? '';
                            final diamonds = gift['diamond_count'] as int? ?? 0;
                            final title = (nameRu.isNotEmpty ? nameRu : nameEn).trim();

                            return InkWell(
                              onTap: () => Navigator.of(context).pop(gift),
                              borderRadius: BorderRadius.circular(12),
                              child: Card(
                                elevation: 1,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: ListTile(
                                  leading: ClipRRect(
                                    borderRadius: BorderRadius.circular(10),
                                    child: SizedBox(
                                      width: 40,
                                      height: 40,
                                      child: image.isNotEmpty
                                          ? CachedNetworkImage(
                                              imageUrl: image,
                                              fit: BoxFit.cover,
                                              placeholder: (context, url) => const Center(
                                                child: SizedBox(
                                                  width: 16,
                                                  height: 16,
                                                  child: CircularProgressIndicator(strokeWidth: 2),
                                                ),
                                              ),
                                              errorWidget: (context, url, error) =>
                                                  const Icon(Icons.card_giftcard, size: 22),
                                            )
                                          : const Icon(Icons.card_giftcard, size: 22),
                                    ),
                                  ),
                                  title: Text(
                                    title.isNotEmpty ? title : 'Подарок',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(fontWeight: FontWeight.w600),
                                  ),
                                  trailing: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: Colors.purple.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Text(
                                      '💎 $diamonds',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.purple,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
