import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../services/api_service.dart';

class PremiumGate {
  static bool isPremiumPlan(String? plan) {
    final p = (plan ?? '').trim().toLowerCase();
    if (p.isEmpty) return false;
    if (p.contains('free')) return false;
    return true;
  }

  static bool isPremium(BuildContext context) {
    try {
      final plan = context.read<AuthProvider>().plan;
      return isPremiumPlan(plan);
    } catch (_) {
      return false;
    }
  }

  static Future<bool> ensureCanCreateTrigger(BuildContext context, {int freeMaxTriggers = 10}) async {
    if (isPremium(context)) return true;

    final api = context.read<ApiService>();
    final triggers = await api.listTriggers();
    if (triggers.length >= freeMaxTriggers) {
      return false;
    }
    return true;
  }
}
