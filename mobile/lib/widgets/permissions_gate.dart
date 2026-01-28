import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../screens/permissions_screen.dart';
import '../services/overlay_bridge.dart';

const _kPrefOverlayOptOut = 'overlay_opt_out';

class PermissionsGate extends StatefulWidget {
  final Widget child;

  const PermissionsGate({super.key, required this.child});

  @override
  State<PermissionsGate> createState() => _PermissionsGateState();
}

class _PermissionsGateState extends State<PermissionsGate> {
  bool _loading = true;
  bool _notificationsGranted = true;
  bool _overlaySupported = false;
  bool _overlayGranted = true;
  bool _overlayRequired = true;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check({bool requestNotificationsIfNeeded = true}) async {
    if (kIsWeb || !Platform.isAndroid) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _notificationsGranted = true;
        _overlaySupported = false;
        _overlayGranted = true;
        _overlayRequired = false;
      });
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    final optedOut = prefs.getBool(_kPrefOverlayOptOut) ?? false;

    // Notifications (Android 13+): runtime permission.
    var notif = await Permission.notification.status;
    if (!notif.isGranted && requestNotificationsIfNeeded) {
      notif = await Permission.notification.request();
    }

    final overlaySupported = await OverlayBridge.isSupported();
    final overlayGranted = overlaySupported ? await OverlayBridge.hasPermission() : true;

    if (!mounted) return;
    setState(() {
      _loading = false;
      _notificationsGranted = notif.isGranted;
      _overlaySupported = overlaySupported;
      _overlayGranted = overlayGranted;
      _overlayRequired = overlaySupported && !optedOut;
    });
  }

  Future<void> _requestOverlay() async {
    await OverlayBridge.requestPermission();
    await Future<void>.delayed(const Duration(milliseconds: 350));
    await _check(requestNotificationsIfNeeded: false);
  }

  Future<void> _openNotificationSettings() async {
    await openAppSettings();
    await Future<void>.delayed(const Duration(milliseconds: 350));
    await _check(requestNotificationsIfNeeded: false);
  }

  Future<void> _continueWithoutOverlay() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kPrefOverlayOptOut, true);
    await _check(requestNotificationsIfNeeded: false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final ready = _notificationsGranted && (!_overlayRequired || _overlayGranted);
    if (ready) return widget.child;

    return PermissionsScreen(
      notificationsGranted: _notificationsGranted,
      overlaySupported: _overlaySupported,
      overlayGranted: _overlayGranted,
      overlayRequired: _overlayRequired,
      onRequestOverlay: _requestOverlay,
      onOpenNotificationSettings: _openNotificationSettings,
      onRecheck: () => _check(requestNotificationsIfNeeded: false),
      onContinueWithoutOverlay: _overlaySupported ? _continueWithoutOverlay : null,
    );
  }
}
