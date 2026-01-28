import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class HelpIcon extends StatelessWidget {
  const HelpIcon({
    super.key,
    required this.title,
    required this.message,
    this.tooltip,
    this.iconSize = 18,
  });

  final String title;
  final String message;
  final String? tooltip;
  final double iconSize;

  Future<void> _show(BuildContext context) async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(
          child: Text(
            message,
            style: const TextStyle(color: AppColors.secondaryText, height: 1.35),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Ок'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tip = tooltip ?? title;

    return Tooltip(
      message: tip,
      waitDuration: const Duration(milliseconds: 250),
      child: IconButton(
        visualDensity: VisualDensity.compact,
        padding: EdgeInsets.zero,
        constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
        icon: Icon(Icons.help_outline, size: iconSize, color: AppColors.secondaryText),
        onPressed: () => _show(context),
      ),
    );
  }
}
