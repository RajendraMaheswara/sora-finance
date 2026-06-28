import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

// ============================================================================
// WIDGET PREDIKSI YANG DIPAKAI BERSAMA (penjualan & pengunjung)
// ----------------------------------------------------------------------------
// - Period switcher 3 tab: Harian / Mingguan / Bulanan
// - Kartu ringkasan konsisten (Total, Rata-rata, Tren) yang dihitung dari titik
//   periode yang sama dengan chart.
// - Chart: DATA REAL (garis solid) lalu PREDIKSI (garis putus-putus + pita
//   confidence interval). Sumbu-Y di-skala dari batas bawah ke batas atas.
// - Panel metrik model + tabel detail.
// ============================================================================

/// Satu titik teragregasi untuk satu periode pada chart/tabel.
class ForecastBar {
  final String label; // label sumbu-x ringkas (mis. "24/6", "Mgg 1", "Jun")
  final String fullLabel; // label panjang untuk tooltip & tabel
  final double value;
  final double? lower;
  final double? upper;
  final int? confidence;

  const ForecastBar({
    required this.label,
    required this.fullLabel,
    required this.value,
    this.lower,
    this.upper,
    this.confidence,
  });

  double get lo => lower ?? value;
  double get hi => upper ?? value;
  bool get hasCi => lower != null && upper != null;
}

enum ForecastPeriodKind { daily, weekly, monthly }

extension ForecastPeriodKindX on ForecastPeriodKind {
  String get label => switch (this) {
        ForecastPeriodKind.daily => 'Harian',
        ForecastPeriodKind.weekly => 'Mingguan',
        ForecastPeriodKind.monthly => 'Bulanan',
      };
  String get unitNoun => switch (this) {
        ForecastPeriodKind.daily => 'hari',
        ForecastPeriodKind.weekly => 'minggu',
        ForecastPeriodKind.monthly => 'bulan',
      };
}

String _capitalize(String s) =>
    s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';

const _legendMonth = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
  7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
};
const _dayShortName = {
  1: 'Sen', 2: 'Sel', 3: 'Rab', 4: 'Kam', 5: 'Jum', 6: 'Sab', 7: 'Min',
};
const _dayFullName = {
  1: 'Senin', 2: 'Selasa', 3: 'Rabu', 4: 'Kamis',
  5: 'Jumat', 6: 'Sabtu', 7: 'Minggu',
};

DateTime? _parseDay(String s) {
  final t = s.length >= 10 ? s.substring(0, 10) : s;
  return DateTime.tryParse(t);
}

// ============================================================================
// HISTORY HELPER — bangun titik DATA REAL dari sales_daily_summaries
// ============================================================================
/// [valueOf] mengambil nilai real dari tiap baris (mis. total_omzet untuk
/// penjualan, total_transaction untuk pengunjung). Diagregasi ke granularitas
/// [period] dan dibatasi pada beberapa periode terakhir.
List<ForecastBar> buildHistoryBars({
  required List<dynamic>? summaries,
  required double Function(Map<String, dynamic>) valueOf,
  required ForecastPeriodKind period,
}) {
  if (summaries == null) return const [];
  final rows = summaries
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .where((e) => ((e['date'] as String?) ?? '').isNotEmpty)
      .toList()
    ..sort(
        (a, b) => (a['date'] as String).compareTo(b['date'] as String));
  if (rows.isEmpty) return const [];

  switch (period) {
    case ForecastPeriodKind.daily:
      // Kelompokkan per tanggal (jumlahkan) supaya tidak ada tanggal ganda bila
      // endpoint mengembalikan >1 baris per hari.
      final byDay = <String, double>{};
      for (final r in rows) {
        final ds = r['date'] as String;
        final key = ds.length >= 10 ? ds.substring(0, 10) : ds;
        byDay[key] = (byDay[key] ?? 0) + valueOf(r);
      }
      final keys = byDay.keys.toList()..sort();
      final last = keys.length > 14 ? keys.sublist(keys.length - 14) : keys;
      return last.map((k) {
        final d = _parseDay(k);
        return ForecastBar(
          label: d == null ? k : '${_dayShortName[d.weekday]} ${d.day}/${d.month}',
          fullLabel: d == null
              ? k
              : '${_dayFullName[d.weekday]}, ${d.day} ${_legendMonth[d.month]} '
                  '${d.year}',
          value: byDay[k]!,
        );
      }).toList();

    case ForecastPeriodKind.weekly:
      final byWeek = <String, List<Map<String, dynamic>>>{};
      for (final r in rows) {
        final d = _parseDay(r['date'] as String);
        if (d == null) continue;
        final ws = d.subtract(Duration(days: d.weekday - 1)); // Senin
        final key = '${ws.year}-${ws.month.toString().padLeft(2, '0')}-'
            '${ws.day.toString().padLeft(2, '0')}';
        byWeek.putIfAbsent(key, () => []).add(r);
      }
      final keys = byWeek.keys.toList()..sort();
      final last = keys.length > 8 ? keys.sublist(keys.length - 8) : keys;
      return last.map((k) {
        final sum = byWeek[k]!.fold<double>(0, (s, r) => s + valueOf(r));
        final ws = DateTime.parse(k);
        final we = ws.add(const Duration(days: 6));
        return ForecastBar(
          label: '${ws.day}/${ws.month}',
          fullLabel: '${ws.day} ${_legendMonth[ws.month]} – '
              '${we.day} ${_legendMonth[we.month]}',
          value: sum,
        );
      }).toList();

    case ForecastPeriodKind.monthly:
      final byMonth = <String, List<Map<String, dynamic>>>{};
      for (final r in rows) {
        final d = _parseDay(r['date'] as String);
        if (d == null) continue;
        final key = '${d.year}-${d.month.toString().padLeft(2, '0')}';
        byMonth.putIfAbsent(key, () => []).add(r);
      }
      final keys = byMonth.keys.toList()..sort();
      final last = keys.length > 6 ? keys.sublist(keys.length - 6) : keys;
      return last.map((k) {
        final sum = byMonth[k]!.fold<double>(0, (s, r) => s + valueOf(r));
        final p = k.split('-');
        final mi = int.tryParse(p[1]);
        return ForecastBar(
          label: '${_legendMonth[mi] ?? p[1]} ${p[0].substring(2)}',
          fullLabel: '${_legendMonth[mi] ?? p[1]} ${p[0]}',
          value: sum,
        );
      }).toList();
  }
}

// ============================================================================
// CARD SHELL
// ============================================================================
class ForecastCardShell extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  const ForecastCardShell({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2)),
        ],
      ),
      child: child,
    );
  }
}

// ============================================================================
// PERIOD SWITCHER (Harian / Mingguan / Bulanan)
// ============================================================================
class ForecastPeriodSwitcher extends StatelessWidget {
  final ForecastPeriodKind active;
  final ValueChanged<ForecastPeriodKind> onChanged;
  final Color activeColor;

  const ForecastPeriodSwitcher({
    super.key,
    required this.active,
    required this.onChanged,
    required this.activeColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: ForecastPeriodKind.values.map((p) {
          final isActive = p == active;
          return GestureDetector(
            onTap: () => onChanged(p),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
              decoration: BoxDecoration(
                color: isActive ? activeColor : Colors.transparent,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(p.label,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: isActive ? Colors.white : Colors.grey[700])),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ============================================================================
// KARTU RINGKASAN (Total / Rata-rata / Tren) — tentang PREDIKSI
// ============================================================================
class ForecastSummaryCards extends StatelessWidget {
  final List<ForecastBar> bars;
  final String Function(double) fmt;
  final ForecastPeriodKind period;

  /// Tren dihitung dari seri TERKAYA (harian) lalu dipakai SAMA di semua tab,
  /// supaya mingguan & bulanan tidak saling bertentangan (mis. mingguan "Naik"
  /// tapi bulanan "Stabil" hanya karena run bulanan cuma 1 titik).
  final double trendPct;

  const ForecastSummaryCards({
    super.key,
    required this.bars,
    required this.fmt,
    required this.period,
    required this.trendPct,
  });

  @override
  Widget build(BuildContext context) {
    final total = bars.fold<double>(0, (s, b) => s + b.value);
    final avg = bars.isEmpty ? 0.0 : total / bars.length;

    final up = trendPct > 0.5;
    final down = trendPct < -0.5;
    final trendLabel = up ? 'Naik' : down ? 'Turun' : 'Stabil';
    final trendColor = up
        ? Colors.green
        : down
            ? Colors.red
            : Colors.blueGrey;
    final pctText = '${trendPct >= 0 ? '+' : ''}${trendPct.toStringAsFixed(1)}%';

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: _StatCard(
            title:
                'Total ${bars.length} ${_capitalize(period.unitNoun)} ke Depan',
            value: fmt(total),
            subtitle: 'Akumulasi seluruh prediksi periode',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _StatCard(
            title: 'Rata-rata per ${_capitalize(period.unitNoun)}',
            value: fmt(avg),
            subtitle: 'Estimasi tiap ${period.unitNoun}',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _StatCard(
            title: 'Tren Prediksi',
            value: trendLabel,
            valueColor: trendColor,
            badge: pctText,
            badgeBg: trendColor.withValues(alpha: 0.12),
            badgeFg: trendColor,
            subtitle: 'Arah keseluruhan (per hari)',
          ),
        ),
      ],
    );
  }
}

/// Tren % dari seri nilai: rata-rata paruh akhir vs paruh awal.
double forecastTrendPct(List<double> series) {
  if (series.length < 2) return 0;
  final mid = series.length ~/ 2;
  final first = series.take(mid).toList();
  final second = series.skip(mid).toList();
  if (first.isEmpty || second.isEmpty) return 0;
  final fa = first.reduce((a, b) => a + b) / first.length;
  final sa = second.reduce((a, b) => a + b) / second.length;
  if (fa == 0) return 0;
  return (sa - fa) / fa * 100;
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  final Color? valueColor;
  final String? badge;
  final Color? badgeBg;
  final Color? badgeFg;

  const _StatCard({
    required this.title,
    required this.value,
    required this.subtitle,
    this.valueColor,
    this.badge,
    this.badgeBg,
    this.badgeFg,
  });

  @override
  Widget build(BuildContext context) {
    return ForecastCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Flexible(
                child: Text(value,
                    style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: valueColor ?? Colors.black87),
                    overflow: TextOverflow.ellipsis),
              ),
              if (badge != null) ...[
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                      color: badgeBg ?? Colors.grey[100],
                      borderRadius: BorderRadius.circular(6)),
                  child: Text(badge!,
                      style: TextStyle(
                          color: badgeFg ?? Colors.grey,
                          fontSize: 12,
                          fontWeight: FontWeight.bold)),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Text(subtitle,
              style: const TextStyle(color: Colors.grey, fontSize: 11)),
        ],
      ),
    );
  }
}

// ============================================================================
// CHART: DATA REAL (solid) → PREDIKSI (dashed) + CONFIDENCE INTERVAL
// ============================================================================
class ForecastTrendChart extends StatelessWidget {
  final String title;
  final List<ForecastBar> history; // data real (garis solid)
  final List<ForecastBar> forecast; // prediksi (garis putus-putus + pita CI)
  final String Function(double) fmtFull;
  final String Function(double) fmtAxis;
  final Color lineColor;
  final Color bandColor;

  const ForecastTrendChart({
    super.key,
    required this.title,
    required this.forecast,
    this.history = const [],
    required this.fmtFull,
    required this.fmtAxis,
    required this.lineColor,
    required this.bandColor,
  });

  static const Color _histColor = Color(0xFF334155); // slate gelap = data real

  @override
  Widget build(BuildContext context) {
    final hasCi = forecast.any((b) => b.hasCi);
    return ForecastCardShell(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(title,
                    style: const TextStyle(
                        color: Colors.grey,
                        fontSize: 13,
                        fontWeight: FontWeight.w600)),
              ),
              Wrap(
                spacing: 12,
                runSpacing: 4,
                children: [
                  if (history.isNotEmpty)
                    _LegendLine(color: _histColor, label: 'Data real'),
                  _LegendLine(color: lineColor, label: 'Prediksi', dashed: true),
                  if (hasCi) _LegendBand(color: bandColor, label: 'Interval'),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(height: 300, child: _buildChart()),
        ],
      ),
    );
  }

  Widget _buildChart() {
    if (history.isEmpty && forecast.isEmpty) {
      return const Center(
        child:
            Text('Tidak ada data', style: TextStyle(color: Colors.grey)),
      );
    }

    final all = [...history, ...forecast];
    final n = all.length;
    final histN = history.length;
    final hasCi = forecast.any((b) => b.hasCi);

    // Rentang sumbu-Y dari batas bawah ke batas atas (bukan dari 0).
    var minLo = double.infinity;
    var maxHi = -double.infinity;
    for (final b in all) {
      final lo = b.hasCi ? b.lo : b.value;
      final hi = b.hasCi ? b.hi : b.value;
      minLo = [minLo, lo, b.value].reduce((a, c) => a < c ? a : c);
      maxHi = [maxHi, hi, b.value].reduce((a, c) => a > c ? a : c);
    }
    final span = (maxHi - minLo).abs();
    final pad = span == 0 ? (maxHi.abs() * 0.1 + 1) : span * 0.18;
    var minY = minLo - pad;
    final maxY = maxHi + pad;
    if (minLo >= 0 && minY < 0) minY = 0;

    final histSpots =
        List.generate(histN, (i) => FlSpot(i.toDouble(), history[i].value));

    // Garis prediksi dimulai dari titik real terakhir agar menyambung.
    final fcSpots = <FlSpot>[];
    final upperSpots = <FlSpot>[];
    final lowerSpots = <FlSpot>[];
    if (histN > 0) {
      final c = FlSpot((histN - 1).toDouble(), history.last.value);
      fcSpots.add(c);
      upperSpots.add(c);
      lowerSpots.add(c);
    }
    for (var j = 0; j < forecast.length; j++) {
      final x = (histN + j).toDouble();
      final b = forecast[j];
      fcSpots.add(FlSpot(x, b.value));
      upperSpots.add(FlSpot(x, b.hasCi ? b.hi : b.value));
      lowerSpots.add(FlSpot(x, b.hasCi ? b.lo : b.value));
    }

    final fcBar = LineChartBarData(
      spots: fcSpots,
      color: lineColor,
      isCurved: false,
      barWidth: 2.6,
      dashArray: const [7, 5],
      dotData: FlDotData(
        show: forecast.length <= 16,
        getDotPainter: (s, p, b, i) => FlDotCirclePainter(
            radius: 3.2,
            color: lineColor,
            strokeWidth: 1.5,
            strokeColor: Colors.white),
      ),
      belowBarData: BarAreaData(show: false),
    );
    final histBar = LineChartBarData(
      spots: histSpots,
      color: _histColor,
      isCurved: false,
      barWidth: 2.4,
      dotData: FlDotData(
        show: histN <= 16,
        getDotPainter: (s, p, b, i) => FlDotCirclePainter(
            radius: 2.6,
            color: _histColor,
            strokeWidth: 1,
            strokeColor: Colors.white),
      ),
      belowBarData: BarAreaData(show: false),
    );
    LineChartBarData invisible(List<FlSpot> spots) => LineChartBarData(
          spots: spots,
          color: Colors.transparent,
          barWidth: 0,
          dotData: const FlDotData(show: false),
        );

    final yInterval = ((maxY - minY) / 4).abs();
    final labelStep = n > 12 ? (n / 8).ceil() : 1;
    final showLabels = forecast.isNotEmpty && forecast.length <= 6;

    return LineChart(LineChartData(
      minX: 0,
      maxX: n > 1 ? (n - 1).toDouble() : 1.0,
      minY: minY,
      maxY: maxY,
      clipData: const FlClipData.all(),
      gridData: FlGridData(
        show: true,
        drawVerticalLine: false,
        horizontalInterval: yInterval <= 0 ? null : yInterval,
        getDrawingHorizontalLine: (_) =>
            FlLine(color: Colors.grey.shade100, strokeWidth: 1),
      ),
      extraLinesData: (histN > 0 && forecast.isNotEmpty)
          ? ExtraLinesData(verticalLines: [
              VerticalLine(
                x: (histN - 1).toDouble(),
                color: Colors.grey.shade300,
                strokeWidth: 1,
                dashArray: const [5, 4],
                label: VerticalLineLabel(
                  show: true,
                  alignment: Alignment.topRight,
                  padding: const EdgeInsets.only(right: 4, bottom: 2),
                  style: const TextStyle(
                      fontSize: 9,
                      color: Colors.grey,
                      fontWeight: FontWeight.w600),
                  labelResolver: (_) => 'Prediksi →',
                ),
              ),
            ])
          : ExtraLinesData(),
      titlesData: FlTitlesData(
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 52,
            interval: yInterval <= 0 ? null : yInterval,
            getTitlesWidget: (v, meta) => Padding(
              padding: const EdgeInsets.only(right: 6),
              child: Text(fmtAxis(v),
                  style: const TextStyle(fontSize: 9, color: Colors.grey)),
            ),
          ),
        ),
        rightTitles:
            const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        topTitles:
            const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 28,
            interval: 1,
            getTitlesWidget: (v, meta) {
              final i = v.toInt();
              if (i < 0 || i >= n) return const SizedBox.shrink();
              if (i % labelStep != 0 && i != n - 1) {
                return const SizedBox.shrink();
              }
              return Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(all[i].label,
                    style: const TextStyle(fontSize: 9, color: Colors.grey)),
              );
            },
          ),
        ),
      ),
      borderData: FlBorderData(show: false),
      betweenBarsData: hasCi
          ? [BetweenBarsData(fromIndex: 0, toIndex: 1, color: bandColor)]
          : const [],
      lineBarsData: [
        invisible(upperSpots),
        invisible(lowerSpots),
        fcBar,
        histBar,
      ],
      showingTooltipIndicators: showLabels
          ? List.generate(forecast.length, (j) {
              final idx = histN > 0 ? j + 1 : j;
              return ShowingTooltipIndicators(
                  [LineBarSpot(fcBar, 2, fcSpots[idx])]);
            })
          : const [],
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (_) => Colors.black.withValues(alpha: 0.82),
          fitInsideHorizontally: true,
          fitInsideVertically: true,
          getTooltipItems: (spots) => spots.map((s) {
            if (s.barIndex == 0 || s.barIndex == 1) return null;
            final xi = s.x.toInt();
            if (s.barIndex == 3) {
              if (xi < 0 || xi >= histN) return null;
              final b = history[xi];
              return LineTooltipItem(
                '${b.label}\n',
                const TextStyle(color: Colors.white70, fontSize: 10),
                children: [
                  TextSpan(
                    text: 'Real: ${fmtFull(b.value)}',
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              );
            }
            final j = xi - histN;
            if (j < 0 || j >= forecast.length) return null;
            final b = forecast[j];
            final ci = b.hasCi ? '\n${fmtAxis(b.lo)} – ${fmtAxis(b.hi)}' : '';
            return LineTooltipItem(
              '${b.label}\n',
              const TextStyle(
                  color: Colors.white70,
                  fontSize: 10,
                  fontWeight: FontWeight.w500),
              children: [
                TextSpan(
                  text: fmtFull(b.value),
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold),
                ),
                TextSpan(
                  text: ci,
                  style:
                      const TextStyle(color: Colors.white60, fontSize: 9.5),
                ),
              ],
            );
          }).toList(),
        ),
      ),
    ));
  }
}

class _LegendLine extends StatelessWidget {
  final Color color;
  final String label;
  final bool dashed;
  const _LegendLine(
      {required this.color, required this.label, this.dashed = false});

  @override
  Widget build(BuildContext context) {
    final swatch = dashed
        ? Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(
                3,
                (i) => Container(
                      width: 5,
                      height: 3,
                      margin: const EdgeInsets.only(right: 2),
                      color: color,
                    )),
          )
        : Container(width: 18, height: 3, color: color);
    return Row(children: [
      swatch,
      const SizedBox(width: 5),
      Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
    ]);
  }
}

class _LegendBand extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendBand({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Container(
        width: 18,
        height: 11,
        decoration:
            BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
      ),
      const SizedBox(width: 5),
      Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
    ]);
  }
}

// ============================================================================
// PANEL METRIK MODEL (akurasi, puncak, terendah, interval)
// ============================================================================
class ForecastMetricsPanel extends StatelessWidget {
  final List<ForecastBar> bars;
  final String Function(double) fmt;

  /// Dipakai sebagai cadangan saja bila titik periode tidak punya
  /// confidence_level.
  final double confidenceScore;
  final Color accent;

  const ForecastMetricsPanel({
    super.key,
    required this.bars,
    required this.fmt,
    required this.confidenceScore,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    if (bars.isEmpty) return const SizedBox.shrink();

    ForecastBar peak = bars.first, low = bars.first;
    for (final b in bars) {
      if (b.value > peak.value) peak = b;
      if (b.value < low.value) low = b;
    }
    final ciBars = bars.where((b) => b.hasCi).toList();
    final avgCiHalf = ciBars.isEmpty
        ? null
        : ciBars.fold<double>(0, (s, b) => s + (b.hi - b.lo) / 2) /
            ciBars.length;

    // Tingkat keyakinan diambil dari confidence_level baris periode AKTIF
    // (per granularitas, sesuai DB) — jadi nilainya berubah saat ganti
    // harian/mingguan/bulanan. Cadangan: confidenceScore dari model.
    final barConfs = bars
        .where((b) => b.confidence != null)
        .map((b) => b.confidence!.toDouble())
        .toList();
    final score = barConfs.isEmpty
        ? confidenceScore
        : barConfs.reduce((a, b) => a + b) / barConfs.length;
    final confLevel =
        score >= 85 ? 'Tinggi' : score >= 70 ? 'Sedang' : 'Rendah';

    final confColor = score >= 85
        ? Colors.green
        : score >= 70
            ? Colors.orange
            : Colors.red;

    return ForecastCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.insights_outlined, size: 18, color: accent),
            const SizedBox(width: 8),
            const Text('Ringkasan Metrik Model',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          ]),
          const SizedBox(height: 4),
          const Text(
            'Seberapa yakin model terhadap prediksi periode ini.',
            style: TextStyle(color: Colors.grey, fontSize: 11),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [
              _MetricTile(
                icon: Icons.verified_outlined,
                iconColor: confColor,
                label: 'Tingkat Keyakinan',
                value: '${score.toStringAsFixed(0)}%',
                sub: confLevel,
              ),
              _MetricTile(
                icon: Icons.trending_up,
                iconColor: Colors.green,
                label: 'Prediksi Tertinggi',
                value: fmt(peak.value),
                sub: peak.fullLabel,
              ),
              _MetricTile(
                icon: Icons.trending_down,
                iconColor: Colors.redAccent,
                label: 'Prediksi Terendah',
                value: fmt(low.value),
                sub: low.fullLabel,
              ),
              _MetricTile(
                icon: Icons.unfold_more,
                iconColor: accent,
                label: 'Rentang Keyakinan',
                value: avgCiHalf == null ? '—' : '± ${fmt(avgCiHalf)}',
                sub: avgCiHalf == null
                    ? 'interval tidak tersedia'
                    : 'rata-rata interval',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;
  final String sub;

  const _MetricTile({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
    required this.sub,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 200,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFB),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade100),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8)),
            child: Icon(icon, size: 16, color: iconColor),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
                const SizedBox(height: 3),
                Text(value,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.bold),
                    overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text(sub,
                    style: const TextStyle(fontSize: 10, color: Colors.grey),
                    overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// TABEL DETAIL (tanggal, prediksi, batas bawah/atas)
// ============================================================================
class ForecastDetailTable extends StatelessWidget {
  final String title;
  final String periodColumn; // "Hari" / "Minggu" / "Bulan"
  final List<ForecastBar> bars;
  final String Function(double) fmt;
  final Color accent;

  const ForecastDetailTable({
    super.key,
    required this.title,
    required this.periodColumn,
    required this.bars,
    required this.fmt,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    return ForecastCardShell(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(children: [
              Expanded(flex: 3, child: _th(periodColumn)),
              Expanded(flex: 3, child: _th('Prediksi')),
              Expanded(flex: 2, child: _th('Batas Bawah')),
              Expanded(flex: 2, child: _th('Batas Atas')),
            ]),
          ),
          const Divider(height: 1),
          for (final b in bars) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 13),
              child: Row(children: [
                Expanded(
                    flex: 3,
                    child: Text(b.fullLabel,
                        style: const TextStyle(
                            fontSize: 13, color: Colors.black87))),
                Expanded(
                    flex: 3,
                    child: Text(fmt(b.value),
                        style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: accent))),
                Expanded(
                    flex: 2,
                    child: Text(b.hasCi ? fmt(b.lo) : '—',
                        style: const TextStyle(
                            fontSize: 13, color: Colors.grey))),
                Expanded(
                    flex: 2,
                    child: Text(b.hasCi ? fmt(b.hi) : '—',
                        style: const TextStyle(
                            fontSize: 13, color: Colors.grey))),
              ]),
            ),
            const Divider(height: 1),
          ],
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _th(String t) => Text(t,
      style: const TextStyle(
          fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey));
}
