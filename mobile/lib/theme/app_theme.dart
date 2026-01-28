import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'nova_tokens.dart';

class AppColors {
  static const Color background = Color(0xFF0D0D12);
  static const Color cardBackground = Color(0xFF1A1A2E);
  static const Color cardBorder = Color(0xFF2D2D44);
  static const Color surfaceColor = Color(0xFF1A1A2E);
  
  static const Color white = Color(0xFFFFFFFF);
  static const Color primaryText = Color(0xFFFFFFFF);
  static const Color secondaryText = Color(0xFFBFBFBF);
  
  static const Color accentPurple = Color(0xFF8A2BE2);
  static const Color accentCyan = Color(0xFF00E5FF);
  static const Color accentGreen = Color(0xFF00FF88);
  static const Color accentRed = Color(0xFFFF4757);
}

class AppTextStyles {
  static const TextStyle headline = TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.bold,
    color: AppColors.primaryText,
  );

  static const TextStyle subtitle = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.primaryText,
  );

  static const TextStyle bodyLarge = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.normal,
    color: AppColors.primaryText,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.normal,
    color: AppColors.primaryText,
  );

  static const TextStyle bodySmall = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.normal,
    color: AppColors.secondaryText,
  );
}

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.background,
      extensions: const <ThemeExtension<dynamic>>[
        NovaTokens(
          bg0: AppColors.background,
          bg1: AppColors.background,
          surface: AppColors.cardBackground,
          surfaceGlass: AppColors.cardBackground,
          border: AppColors.cardBorder,
          textPrimary: AppColors.primaryText,
          textSecondary: AppColors.secondaryText,
          purple: AppColors.accentPurple,
          cyan: AppColors.accentCyan,
          red: AppColors.accentRed,
          green: AppColors.accentGreen,
          pink: AppColors.accentPurple,
        ),
      ],
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme),
      cardTheme: const CardTheme(
        color: AppColors.cardBackground,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
          side: BorderSide(color: AppColors.cardBorder, width: 1),
        ),
      ),

      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.cardBackground,
        elevation: 0,
        centerTitle: false,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.accentPurple,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: AppColors.cardBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          borderSide: BorderSide(color: AppColors.cardBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          borderSide: BorderSide(color: AppColors.cardBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          borderSide: BorderSide(color: AppColors.accentPurple, width: 2),
        ),
      ),
    );
  }

  static ThemeData get premiumDarkTheme {
    const tokens = NovaTokens(
      bg0: Color(0xFF0E1020),
      bg1: Color(0xFF14162B),
      surface: Color(0xFF14162B),
      // glass surface is semi-transparent; actual blur is implemented at widget level
      surfaceGlass: Color(0x3314162B),
      border: Color(0x3322D3EE),
      textPrimary: Color(0xFFEDEEFF),
      textSecondary: Color(0xFFA9AEC9),
      purple: Color(0xFF8B5CF6),
      cyan: Color(0xFF22D3EE),
      red: Color(0xFFEF4444),
      green: Color(0xFF34D399),
      pink: Color(0xFFEC4899),
    );

    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: tokens.bg0,
      colorScheme: ColorScheme.fromSeed(
        seedColor: tokens.purple,
        brightness: Brightness.dark,
        primary: tokens.purple,
        secondary: tokens.cyan,
        error: tokens.red,
        surface: tokens.surface,
      ),
      extensions: const <ThemeExtension<dynamic>>[tokens],
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme).apply(
        bodyColor: tokens.textPrimary,
        displayColor: tokens.textPrimary,
      ),
    );

    return base.copyWith(
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        foregroundColor: tokens.textPrimary,
        titleTextStyle: base.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      ),
      cardTheme: CardTheme(
        color: tokens.surfaceGlass,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: const BorderRadius.all(Radius.circular(18)),
          side: BorderSide(color: tokens.border, width: 1),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: tokens.surfaceGlass,
        hintStyle: TextStyle(color: tokens.textSecondary),
        labelStyle: TextStyle(color: tokens.textSecondary),
        border: OutlineInputBorder(
          borderRadius: const BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: tokens.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: const BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: tokens.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: const BorderRadius.all(Radius.circular(14)),
          borderSide: BorderSide(color: tokens.purple, width: 2),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: tokens.surface,
        contentTextStyle: TextStyle(color: tokens.textPrimary),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return tokens.purple;
          return tokens.textSecondary;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return tokens.purple.withOpacity(0.35);
          return tokens.border;
        }),
      ),
      dividerColor: tokens.border,
    );
  }
}
