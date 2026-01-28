import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

import '../services/api_service.dart';
import '../utils/constants.dart';
import 'auth_provider.dart';

class BillingProvider extends ChangeNotifier {
  final ApiService _api;
  final InAppPurchase _iap = InAppPurchase.instance;
  AuthProvider? _auth;

  bool _initialized = false;
  bool _available = false;
  bool _loading = false;
  String? _error;

  final Map<String, ProductDetails> _products = {};
  StreamSubscription<List<PurchaseDetails>>? _sub;

  BillingProvider({required ApiService apiService}) : _api = apiService;

  void updateAuth(AuthProvider? auth) {
    _auth = auth;
  }

  bool get available => _available;
  bool get loading => _loading;
  String? get error => _error;

  List<ProductDetails> get products => _products.values.toList()
    ..sort((a, b) => a.id.compareTo(b.id));

  bool get isPremium {
    final plan = (_auth?.plan ?? '').trim().toLowerCase();
    if (plan.isEmpty) return false;
    if (plan.contains('free')) return false;
    return true;
  }

  Future<void> initialize({required Set<String> productIds}) async {
    if (_initialized) return;
    _initialized = true;

    if (kIsWeb) {
      _available = false;
      _error = 'Покупки доступны только на телефоне (Android/iOS)';
      notifyListeners();
      return;
    }

    _available = await _iap.isAvailable();
    if (!_available) {
      _error = 'In‑app покупки недоступны на этом устройстве';
      notifyListeners();
      return;
    }

    _sub = _iap.purchaseStream.listen(
      _onPurchaseUpdate,
      onError: (e) {
        _error = 'Ошибка покупок: $e';
        notifyListeners();
      },
    );

    await refreshProducts(productIds: productIds);

    // Best-effort: sync existing purchases with backend.
    try {
      await _iap.restorePurchases();
    } catch (_) {}
  }

  Future<void> refreshProducts({required Set<String> productIds}) async {
    if (!_available) return;
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final resp = await _iap.queryProductDetails(productIds);
      if (resp.error != null) {
        _error = resp.error!.message;
      }

      // Android subscriptions: query may return multiple ProductDetails per productId
      // (base plan + offers). We select a preferred one per productId.
      final byId = <String, List<ProductDetails>>{};
      for (final p in resp.productDetails) {
        byId.putIfAbsent(p.id, () => <ProductDetails>[]).add(p);
      }

      _products.clear();
      for (final id in productIds) {
        final items = byId[id] ?? const <ProductDetails>[];
        if (items.isEmpty) continue;
        _products[id] = _selectPreferredProductDetails(id, items);
      }
    } catch (e) {
      _error = 'Не удалось загрузить продукты: $e';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> buy(ProductDetails product) async {
    if (!_available) return;
    _error = null;
    notifyListeners();

    final param = PurchaseParam(productDetails: product);
    await _iap.buyNonConsumable(purchaseParam: param);
  }

  ProductDetails _selectPreferredProductDetails(String productId, List<ProductDetails> items) {
    if (defaultTargetPlatform != TargetPlatform.android) {
      return items.first;
    }

    final gp = items.whereType<GooglePlayProductDetails>().toList();
    if (gp.isEmpty) return items.first;

    GooglePlayProductDetails? pickBy(String basePlanId, String? offerId) {
      for (final p in gp) {
        final idx = p.subscriptionIndex;
        if (idx == null) continue;
        final offers = p.productDetails.subscriptionOfferDetails;
        if (offers == null || idx < 0 || idx >= offers.length) continue;
        final o = offers[idx];
        if (o.basePlanId != basePlanId) continue;
        final oid = (o.offerId ?? '').trim();
        final want = (offerId ?? '').trim();
        if (want.isEmpty) {
          if (oid.isEmpty) return p; // base plan
        } else {
          if (oid == want) return p; // discounted offer
        }
      }
      return null;
    }

    if (productId == kAndroidProductMonthly) {
      return pickBy(kAndroidMonthlyBasePlanId, kAndroidMonthlyOfferId) ??
          pickBy(kAndroidMonthlyBasePlanId, null) ??
          gp.first;
    }

    if (productId == kAndroidProductYearly) {
      final wantOffer = kAndroidYearlyOfferId.trim();
      if (wantOffer.isNotEmpty) {
        final preferred = pickBy(kAndroidYearlyBasePlanId, wantOffer);
        if (preferred != null) return preferred;
      }
      return pickBy(kAndroidYearlyBasePlanId, null) ?? gp.first;
    }

    return gp.first;
  }

  Future<void> restore() async {
    if (!_available) return;
    _error = null;
    notifyListeners();
    await _iap.restorePurchases();
  }

  Future<void> disposeStream() async {
    await _sub?.cancel();
    _sub = null;
  }

  Future<void> _onPurchaseUpdate(List<PurchaseDetails> purchases) async {
    for (final p in purchases) {
      if (p.status == PurchaseStatus.pending) {
        // просто ждём
        continue;
      }

      if (p.status == PurchaseStatus.error) {
        _error = p.error?.message ?? 'Ошибка покупки';
        notifyListeners();
        continue;
      }

      if (p.status == PurchaseStatus.purchased || p.status == PurchaseStatus.restored) {
        // Important: completePurchase triggers acknowledge on Android.
        if (p.pendingCompletePurchase) {
          try {
            await _iap.completePurchase(p);
          } catch (_) {}
        }

        final ok = await _api.verifySubscription(
          platform: _detectPlatform(),
          productId: p.productID,
          verificationData: p.verificationData.serverVerificationData,
          packageName: _detectPlatform() == 'android' ? kAndroidPackageName : null,
        );

        if (ok) {
          try {
            await _auth?.refreshUserInfo();
          } catch (_) {}
        } else {
          _error = _api.lastError ?? 'Не удалось подтвердить покупку';
          notifyListeners();
        }

      }
    }
  }

  String _detectPlatform() {
    // без dart:io чтобы не ломать web-таргет
    // backend ожидает android|ios
    if (defaultTargetPlatform == TargetPlatform.iOS) return 'ios';
    return 'android';
  }

  @override
  void dispose() {
    disposeStream();
    super.dispose();
  }
}
