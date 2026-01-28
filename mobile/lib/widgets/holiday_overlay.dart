import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Lightweight seasonal UI overlay (no assets required).
///
/// Toggle via [enabled]. Intended to be wrapped around the whole app.
class HolidayOverlay extends StatefulWidget {
  final Widget child;
  final bool enabled;
  final bool garlandEnabled;
  final bool snowDriftsEnabled;

  const HolidayOverlay({
    super.key,
    required this.child,
    required this.enabled,
    this.garlandEnabled = true,
    this.snowDriftsEnabled = true,
  });

  @override
  State<HolidayOverlay> createState() => _HolidayOverlayState();
}

class _HolidayOverlayState extends State<HolidayOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  final List<_Snowflake> _flakes = <_Snowflake>[];
  double _spawnCarry = 0.0;
  double _timeSeconds = 0.0;
  late final Stopwatch _stopwatch;
  double _lastTickSeconds = 0.0;
  final math.Random _rng = math.Random();

  @override
  void initState() {
    super.initState();
    _stopwatch = Stopwatch()..start();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 12),
    );
    if (widget.enabled) {
      _controller.repeat();
    }
  }

  @override
  void didUpdateWidget(covariant HolidayOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.enabled == widget.enabled) return;

    if (widget.enabled) {
      _controller.repeat();
    } else {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) return widget.child;

    return Stack(
      fit: StackFit.expand,
      children: [
        widget.child,
        IgnorePointer(
          ignoring: true,
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, _) {
              _tick();
              return CustomPaint(
                painter: _SnowPainter(
                  t: _controller.value,
                  timeSeconds: _timeSeconds,
                  drawGarland: widget.garlandEnabled,
                  drawSnowDrifts: widget.snowDriftsEnabled,
                  flakes: _flakes,
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  void _tick() {
    final now = _stopwatch.elapsedMicroseconds / 1e6;
    var dt = now - _lastTickSeconds;
    _lastTickSeconds = now;

    // Guard against long pauses/background.
    if (dt.isNaN || dt.isInfinite) dt = 0.016;
    dt = dt.clamp(0.0, 0.05);

    _timeSeconds += dt;

    // Spawn like the HTML sample: about one flake per ~200ms.
    const double spawnPerSecond = 5.0;
    final jitter = 0.7 + _rng.nextDouble() * 0.9;
    _spawnCarry += spawnPerSecond * dt * jitter;
    final toSpawn = _spawnCarry.floor();
    _spawnCarry -= toSpawn;

    for (int i = 0; i < toSpawn; i++) {
      _flakes.add(_Snowflake.spawnRandom(_timeSeconds, _rng));
    }

    // Cleanup old flakes.
    _flakes.removeWhere((f) => (_timeSeconds - f.startTime) > f.duration);
  }
}

class _SnowPainter extends CustomPainter {
  final double t;
  final bool drawGarland;
  final bool drawSnowDrifts;
  final List<_Snowflake> flakes;
  final double timeSeconds;

  _SnowPainter({
    required this.t,
    required this.timeSeconds,
    required this.drawGarland,
    required this.drawSnowDrifts,
    required this.flakes,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (drawGarland) {
      _paintGarland(canvas, size);
    }

    _paintSnowflakes(canvas, size);

    // Subtle top vignette (like frosty haze) to make it feel festive.
    final rect = Rect.fromLTWH(0, 0, size.width, size.height);
    final gradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        const Color(0xFFFFFFFF).withOpacity(0.05),
        const Color(0xFFFFFFFF).withOpacity(0.00),
      ],
      stops: const [0.0, 0.35],
    );
    canvas.drawRect(rect, Paint()..shader = gradient.createShader(rect));

    if (drawSnowDrifts) {
      _paintSnowDrifts(canvas, size);
    }
  }

  @override
  bool shouldRepaint(covariant _SnowPainter oldDelegate) {
    return oldDelegate.t != t ||
        oldDelegate.timeSeconds != timeSeconds ||
        oldDelegate.drawGarland != drawGarland ||
        oldDelegate.drawSnowDrifts != drawSnowDrifts ||
        oldDelegate.flakes.length != flakes.length;
  }

  void _paintSnowflakes(Canvas canvas, Size size) {
    // Draw snowflakes as text glyphs (❄), similar to the HTML example.
    for (final f in flakes) {
      final p = ((timeSeconds - f.startTime) / f.duration).clamp(0.0, 1.0);
      final y = -50.0 + p * (size.height + 100.0);
      final x = (f.x * size.width) + math.sin((p * 6.0) + f.phase) * f.drift;

      final opacity = (1.0 - p) * f.opacity;
      final textPainter = TextPainter(
        text: TextSpan(
          text: '❄',
          style: TextStyle(
            fontSize: f.size,
            color: const Color(0xFFFFFFFF).withOpacity(opacity.clamp(0.0, 1.0)),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();

      textPainter.paint(
        canvas,
        Offset(
          x - textPainter.width / 2,
          y - textPainter.height / 2,
        ),
      );
    }
  }

  void _paintGarland(Canvas canvas, Size size) {
    // Garland is drawn near the top edge. Keep it subtle and light.
    final yBase = math.max(10.0, size.height * 0.02);
    final amplitude = math.min(14.0, size.height * 0.018);
    final left = 10.0;
    final right = size.width - 10.0;

    final wirePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFFFFFFFF).withOpacity(0.14);

    final path = Path();
    const int segments = 8;
    for (int i = 0; i <= segments; i++) {
      final x = left + (right - left) * (i / segments);
      final w = math.sin((i / segments) * math.pi) * amplitude;
      final y = yBase + w;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, wirePaint);

    // Lights along the wire
    const int bulbs = 14;
    for (int i = 0; i < bulbs; i++) {
      final p = (i + 0.5) / bulbs;
      final x = left + (right - left) * p;
      final y = yBase + math.sin(p * math.pi) * amplitude;

      // Twinkle: deterministic per index + time.
      final phase = _rand01(i * 911 + 7) * math.pi * 2;
      final tw = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * math.pi * 2 * 1.7 + phase));

      final c = _bulbColor(i).withOpacity(0.30 * tw);
      final glow = Paint()..color = c;
      final core = Paint()..color = _bulbColor(i).withOpacity(0.55 * tw);

      final rGlow = 6.5;
      final rCore = 2.4;
      canvas.drawCircle(Offset(x, y + 3), rGlow, glow);
      canvas.drawCircle(Offset(x, y + 3), rCore, core);
    }
  }

  void _paintSnowDrifts(Canvas canvas, Size size) {
    // Accumulation increases over time but stays subtle.
    // t loops [0..1], so make a pseudo "progress" that ramps each loop.
    final progress = (t * 1.15).clamp(0.0, 1.0);

    final h = math.min(52.0, size.height * 0.08) * progress;
    final w = math.min(120.0, size.width * 0.28) * progress;

    final driftPaint = Paint()..color = const Color(0xFFFFFFFF).withOpacity(0.08);
    final edgePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = const Color(0xFFFFFFFF).withOpacity(0.10);

    // Bottom-left
    final bl = Path()
      ..moveTo(0, size.height)
      ..quadraticBezierTo(w * 0.25, size.height - h * 0.35, w * 0.55, size.height - h)
      ..quadraticBezierTo(w * 0.75, size.height - h * 1.10, w, size.height - h * 0.65)
      ..lineTo(w, size.height)
      ..close();
    canvas.drawPath(bl, driftPaint);
    canvas.drawPath(bl, edgePaint);

    // Bottom-right
    final br = Path()
      ..moveTo(size.width, size.height)
      ..quadraticBezierTo(size.width - w * 0.25, size.height - h * 0.35, size.width - w * 0.55, size.height - h)
      ..quadraticBezierTo(size.width - w * 0.75, size.height - h * 1.10, size.width - w, size.height - h * 0.65)
      ..lineTo(size.width - w, size.height)
      ..close();
    canvas.drawPath(br, driftPaint);
    canvas.drawPath(br, edgePaint);
  }

  static Color _bulbColor(int i) {
    switch (i % 5) {
      case 0:
        return const Color(0xFFFFD54F); // warm yellow
      case 1:
        return const Color(0xFF81C784); // green
      case 2:
        return const Color(0xFF64B5F6); // blue
      case 3:
        return const Color(0xFFE57373); // red
      default:
        return const Color(0xFFBA68C8); // purple
    }
  }

  static double _rand01(int seed) {
    // Simple hash -> [0,1)
    var x = seed;
    x = (x ^ 0x6C8E9CF5) * 0x45D9F3B;
    x = (x ^ (x >> 16)) * 0x45D9F3B;
    x = x ^ (x >> 16);
    final u = (x & 0x7fffffff) / 0x80000000;
    return u.clamp(0.0, 0.999999);
  }
}

class _Snowflake {
  final double startTime;
  final double duration;
  final double x; // 0..1
  final double size;
  final double opacity;
  final double drift;
  final double phase;

  _Snowflake({
    required this.startTime,
    required this.duration,
    required this.x,
    required this.size,
    required this.opacity,
    required this.drift,
    required this.phase,
  });

  factory _Snowflake.spawnRandom(double now, math.Random rng) {
    // Match the HTML feel: random X, random size, random opacity,
    // fallDuration ~ 5..10 seconds.
    final rX = rng.nextDouble();
    final rS = rng.nextDouble();
    final rO = rng.nextDouble();
    final rD = rng.nextDouble();
    final rP = rng.nextDouble();

    return _Snowflake(
      startTime: now,
      duration: 5.0 + rS * 5.0,
      x: rX,
      size: 10.0 + rS * 20.0,
      opacity: 0.25 + rO * 0.75,
      drift: (rD - 0.5) * 60.0,
      phase: rP * math.pi * 2,
    );
  }
}
