import 'package:flutter/material.dart';

@immutable
class NovaTokens extends ThemeExtension<NovaTokens> {
  final Color bg0;
  final Color bg1;
  final Color surface;
  final Color surfaceGlass;
  final Color border;
  final Color textPrimary;
  final Color textSecondary;
  final Color purple;
  final Color cyan;
  final Color red;
  final Color green;
  final Color pink;

  const NovaTokens({
    required this.bg0,
    required this.bg1,
    required this.surface,
    required this.surfaceGlass,
    required this.border,
    required this.textPrimary,
    required this.textSecondary,
    required this.purple,
    required this.cyan,
    required this.red,
    required this.green,
    required this.pink,
  });

  @override
  NovaTokens copyWith({
    Color? bg0,
    Color? bg1,
    Color? surface,
    Color? surfaceGlass,
    Color? border,
    Color? textPrimary,
    Color? textSecondary,
    Color? purple,
    Color? cyan,
    Color? red,
    Color? green,
    Color? pink,
  }) {
    return NovaTokens(
      bg0: bg0 ?? this.bg0,
      bg1: bg1 ?? this.bg1,
      surface: surface ?? this.surface,
      surfaceGlass: surfaceGlass ?? this.surfaceGlass,
      border: border ?? this.border,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      purple: purple ?? this.purple,
      cyan: cyan ?? this.cyan,
      red: red ?? this.red,
      green: green ?? this.green,
      pink: pink ?? this.pink,
    );
  }

  @override
  NovaTokens lerp(ThemeExtension<NovaTokens>? other, double t) {
    if (other is! NovaTokens) return this;
    return NovaTokens(
      bg0: Color.lerp(bg0, other.bg0, t)!,
      bg1: Color.lerp(bg1, other.bg1, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceGlass: Color.lerp(surfaceGlass, other.surfaceGlass, t)!,
      border: Color.lerp(border, other.border, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      purple: Color.lerp(purple, other.purple, t)!,
      cyan: Color.lerp(cyan, other.cyan, t)!,
      red: Color.lerp(red, other.red, t)!,
      green: Color.lerp(green, other.green, t)!,
      pink: Color.lerp(pink, other.pink, t)!,
    );
  }
}

extension NovaTokensX on BuildContext {
  NovaTokens get nova => Theme.of(this).extension<NovaTokens>()!;
}
