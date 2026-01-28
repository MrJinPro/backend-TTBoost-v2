import 'dart:async';

import 'package:flutter/foundation.dart';

import '../services/api_service.dart';

class NotificationsProvider extends ChangeNotifier {
  ApiService _api;
  String? _activeToken;

  int _unreadCount = 0;
  bool _loadingList = false;
  List<Map<String, dynamic>> _items = const [];

  Timer? _pollTimer;

  int get unreadCount => _unreadCount;
  bool get loadingList => _loadingList;
  List<Map<String, dynamic>> get items => List.unmodifiable(_items);

  NotificationsProvider({required ApiService apiService}) : _api = apiService;

  void updateAuth({required ApiService apiService, required String? jwtToken}) {
    _api = apiService;
    if (jwtToken == _activeToken) return;
    _activeToken = jwtToken;

    _pollTimer?.cancel();
    _pollTimer = null;

    if (jwtToken == null || jwtToken.trim().isEmpty) {
      _unreadCount = 0;
      _items = const [];
      _loadingList = false;
      notifyListeners();
      return;
    }

    // One immediate refresh + periodic polling.
    refreshUnreadCount();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      refreshUnreadCount();
    });
  }

  Future<void> refreshUnreadCount() async {
    if (_activeToken == null || _activeToken!.trim().isEmpty) return;
    final c = await _api.getUnreadNotificationsCount();
    if (c != _unreadCount) {
      _unreadCount = c;
      notifyListeners();
    }
  }

  Future<void> loadNotifications({int limit = 50, int offset = 0}) async {
    if (_activeToken == null || _activeToken!.trim().isEmpty) return;
    if (_loadingList) return;
    _loadingList = true;
    notifyListeners();
    try {
      final list = await _api.listNotifications(limit: limit, offset: offset);
      _items = list;
    } finally {
      _loadingList = false;
      notifyListeners();
      // Keep badge accurate.
      await refreshUnreadCount();
    }
  }

  Future<void> markRead(String notificationId) async {
    if (_activeToken == null || _activeToken!.trim().isEmpty) return;
    final ok = await _api.markNotificationRead(id: notificationId);
    if (!ok) return;

    // Update local list optimistically.
    final updated = _items.map((e) {
      if ((e['id']?.toString() ?? '') == notificationId) {
        return {
          ...e,
          'is_read': true,
        };
      }
      return e;
    }).toList(growable: false);

    _items = updated;
    notifyListeners();
    await refreshUnreadCount();
  }

  Future<void> markAllRead() async {
    if (_activeToken == null || _activeToken!.trim().isEmpty) return;
    final ok = await _api.markAllNotificationsRead();
    if (!ok) return;

    _items = _items
        .map((e) => {
              ...e,
              'is_read': true,
            })
        .toList(growable: false);
    _unreadCount = 0;
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _pollTimer = null;
    super.dispose();
  }
}
