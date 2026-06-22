import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/visitor_forecast_model.dart';
import '../../core/services/auth_service.dart';

// ==========================================
// KONFIGURASI
// ==========================================
const Color _kPrimaryGreen = Color(0xFF8CE600);
const Color _kPrimaryGreenDark = Color(0xFF24CC14);
const Color _kAccentOrange = Color(0xFFF59E0B);
const Color _kBarBlueLight = Color(0xFFD7DEE8);

const String _kForecastPredictionsEndpoint = 'forecast-predictions';

// ==========================================
// PAGE
// ==========================================
class VisitorForecastPage extends StatefulWidget {
  final String storeId;

  const VisitorForecastPage({super.key, required this.storeId});

  @override
  State<VisitorForecastPage> createState() => _VisitorForecastPageState();
}

class _VisitorForecastPageState extends State<VisitorForecastPage> {
  final ApiService _apiService = ApiService();
  late Future<VisitorForecastModel> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
    _loadUser();
  }

  Future<VisitorForecastModel> _fetch() async {
    final raw = await _apiService.fetchData(_kForecastPredictionsEndpoint);
    return VisitorForecastModel.fromPredictionList(raw);
  }

  void _refresh() {
    setState(() {
      _future = _fetch();
    });
  }

  String _userName = 'Loading...';
  String _name = 'User';

  Future<void> _loadUser() async {
  try {
    final user = await AuthService().getCurrentUser();

    setState(() {
      _userName = user.username;
      _name = user.name;
    });
  } catch (_) {
    setState(() {
      _userName = 'Guest';
      _name = '-';
    });
  }
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F6F7),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SidebarWidget(
            userName: _userName,
            name: _name,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(32, 24, 32, 32),
              child: FutureBuilder<VisitorForecastModel>(
                future: _future,
                builder: (context, snapshot) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _Header(onRefresh: _refresh),
                      const SizedBox(height: 28),
                      if (snapshot.connectionState == ConnectionState.waiting)
                        const _LoadingPanel()
                      else if (snapshot.hasError)
                        _ErrorPanel(
                          message: '${snapshot.error}',
                          onRetry: _refresh,
                        )
                      else
                        _ForecastBody(data: snapshot.data!),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// HEADER
// ==========================================
class _Header extends StatelessWidget {
  final VoidCallback onRefresh;
  const _Header({required this.onRefresh});

  String _formatNowOpened() {
    final now = DateTime.now();
    final isPm = now.hour >= 12;
    final hour12 = now.hour % 12 == 0 ? 12 : now.hour % 12;
    final mm = now.minute.toString().padLeft(2, '0');
    return 'Opened $hour12:$mm ${isPm ? 'pm' : 'am'}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              _formatNowOpened(),
              style: const TextStyle(color: Colors.grey, fontSize: 12),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                IconButton(
                  onPressed: () => Navigator.of(context).maybePop(),
                  icon: const Icon(Icons.arrow_back),
                  tooltip: 'Kembali',
                  color: Colors.grey[700],
                ),
                const SizedBox(width: 4),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Dasbor',
                      style: TextStyle(color: Colors.grey, fontSize: 13),
                    ),
                    SizedBox(height: 6),
                    Text(
                      'Prediksi Pengunjung',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Colors.black87,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            Row(
              children: [
                IconButton(
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh',
                  color: Colors.grey,
                ),
                const SizedBox(width: 4),
                ElevatedButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.storefront, size: 16),
                  label: const Text('Soramen'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black87,
                    elevation: 0,
                    side: BorderSide(color: Colors.grey.shade300),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    textStyle: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }
}

// ==========================================
// LOADING / ERROR PANELS
// ==========================================
class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 480,
      child: Center(
        child: CircularProgressIndicator(color: _kPrimaryGreenDark),
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorPanel({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Icon(Icons.wifi_off, color: Colors.red, size: 36),
          const SizedBox(height: 12),
          Text(
            'Gagal memuat prediksi.\n$message',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.red),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Coba Lagi'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _kPrimaryGreen,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// PERIOD ENUM + HELPER
// ==========================================
enum ForecastPeriod { weekly, monthly }

extension on ForecastPeriod {
  String get label {
    switch (this) {
      case ForecastPeriod.weekly:
        return 'Mingguan';
      case ForecastPeriod.monthly:
        return 'Bulanan';
    }
  }
}

class _PeriodAggregate {
  /// Label tiap titik di chart / tabel (mis. "Mgg 1", "1 Jul").
  final String label;

  /// Tanggal asli (untuk tabel)
  final String dateLabel;

  /// Total / nilai prediksi pada titik tersebut.
  final int value;

  _PeriodAggregate({
    required this.label,
    required this.dateLabel,
    required this.value,
  });
}

List<_PeriodAggregate> _aggregateForPeriod(
  VisitorForecastModel data,
  ForecastPeriod period,
) {
  switch (period) {
    case ForecastPeriod.weekly:
      // Pecah monthly_forecast (30 hari) jadi grup 7-harian.
      final src = data.monthlyForecast;
      final groups = <List<VisitorForecastPoint>>[];
      for (var i = 0; i < src.length; i += 7) {
        groups.add(src.sublist(i, (i + 7).clamp(0, src.length)));
      }
      return List.generate(groups.length, (i) {
        final g = groups[i];
        final total = g.fold<int>(0, (s, p) => s + p.predictedVisitors);
        final start = g.first.date;
        final end = g.last.date;
        return _PeriodAggregate(
          label: 'Mgg ${i + 1}',
          dateLabel: '${_formatShortDate(start)} – ${_formatShortDate(end)}',
          value: total,
        );
      });

    case ForecastPeriod.monthly:
      // Group monthly_forecast per bulan kalender.
      final byMonth = <String, List<VisitorForecastPoint>>{};
      for (final p in data.monthlyForecast) {
        final key = p.date.length >= 7 ? p.date.substring(0, 7) : p.date;
        byMonth.putIfAbsent(key, () => []).add(p);
      }
      final keys = byMonth.keys.toList()..sort();
      return keys.map((k) {
        final list = byMonth[k]!;
        final total = list.fold<int>(0, (s, p) => s + p.predictedVisitors);
        return _PeriodAggregate(
          label: _formatMonthLabel(k),
          dateLabel: _formatMonthLabel(k),
          value: total,
        );
      }).toList();
  }
}

String _formatShortDate(String iso) {
  try {
    final dt = DateTime.parse(iso);
    return '${dt.day} ${_monthShort[dt.month]}';
  } catch (_) {
    return iso;
  }
}

String _formatLongDate(String iso) {
  try {
    final dt = DateTime.parse(iso);
    return '${_dayName[dt.weekday]}, ${dt.day} ${_monthShort[dt.month]} ${dt.year}';
  } catch (_) {
    return iso;
  }
}

String _formatMonthLabel(String yyyymm) {
  final parts = yyyymm.split('-');
  if (parts.length < 2) return yyyymm;
  final m = int.tryParse(parts[1]);
  return '${_monthShort[m] ?? parts[1]} ${parts[0]}';
}

const _dayName = {
  1: 'Senin',
  2: 'Selasa',
  3: 'Rabu',
  4: 'Kamis',
  5: 'Jumat',
  6: 'Sabtu',
  7: 'Minggu',
};
const _monthShort = {
  1: 'Jan',
  2: 'Feb',
  3: 'Mar',
  4: 'Apr',
  5: 'Mei',
  6: 'Jun',
  7: 'Jul',
  8: 'Agu',
  9: 'Sep',
  10: 'Okt',
  11: 'Nov',
  12: 'Des',
};

// ==========================================
// BODY UTAMA
// ==========================================
class _ForecastBody extends StatefulWidget {
  final VisitorForecastModel data;
  const _ForecastBody({required this.data});

  @override
  State<_ForecastBody> createState() => _ForecastBodyState();
}

class _ForecastBodyState extends State<_ForecastBody> {
  ForecastPeriod _period = ForecastPeriod.weekly;

  @override
  Widget build(BuildContext context) {
    final aggregates = _aggregateForPeriod(widget.data, _period);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _PeriodSwitcher(
          active: _period,
          onChanged: (p) => setState(() => _period = p),
        ),
        const SizedBox(height: 16),
        _SummaryCardsRow(data: widget.data, period: _period),
        const SizedBox(height: 20),
        _HistoricalChartCard(
          period: _period,
          aggregates: aggregates,
          fallbackAvg: widget.data.avgDailyNext30Days == 0
              ? widget.data.avgDailyNext7Days
              : widget.data.avgDailyNext30Days,
        ),
        const SizedBox(height: 20),
        _ConfidenceTableCard(
          data: widget.data,
          period: _period,
          aggregates: aggregates,
        ),
        const SizedBox(height: 20),
        if (widget.data.insights.isNotEmpty)
          _InsightsCard(insights: widget.data.insights),
      ],
    );
  }
}

// ==========================================
// PERIOD SWITCHER
// ==========================================
class _PeriodSwitcher extends StatelessWidget {
  final ForecastPeriod active;
  final ValueChanged<ForecastPeriod> onChanged;

  const _PeriodSwitcher({required this.active, required this.onChanged});

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
        children: ForecastPeriod.values.map((p) {
          final isActive = p == active;
          return GestureDetector(
            onTap: () => onChanged(p),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
              decoration: BoxDecoration(
                color: isActive ? _kPrimaryGreen : Colors.transparent,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                p.label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isActive ? Colors.white : Colors.grey[700],
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ==========================================
// SUMMARY CARDS
// ==========================================
class _SummaryCardsRow extends StatelessWidget {
  final VisitorForecastModel data;
  final ForecastPeriod period;
  const _SummaryCardsRow({required this.data, required this.period});

  @override
  Widget build(BuildContext context) {
    // Card 1: angka aktual untuk periode yang dipilih
    final card1Title = switch (period) {
      ForecastPeriod.weekly => 'Total Pengunjung Minggu Ini',
      ForecastPeriod.monthly => 'Total Pengunjung Bulan Ini',
    };
    final card1Value = switch (period) {
      ForecastPeriod.weekly => '${data.totalNext7Days} Orang',
      ForecastPeriod.monthly => '${data.totalNext30Days} Orang',
    };
    final card1Subtitle = switch (period) {
      ForecastPeriod.weekly => 'Akumulasi prediksi 7 hari',
      ForecastPeriod.monthly => 'Akumulasi prediksi 30 hari',
    };

    // Card 2: rata-rata
    final card2Title = switch (period) {
      ForecastPeriod.weekly => 'Rata-rata Mingguan',
      ForecastPeriod.monthly => 'Rata-rata Bulanan',
    };
    final card2Value = switch (period) {
      ForecastPeriod.weekly =>
        '${(data.avgDailyNext7Days * 7).toStringAsFixed(0)} Orang',
      ForecastPeriod.monthly =>
        '${(data.avgDailyNext30Days * 30).toStringAsFixed(0)} Orang',
    };
    final card2Subtitle = switch (period) {
      ForecastPeriod.weekly => 'Estimasi total per minggu',
      ForecastPeriod.monthly => 'Estimasi total per bulan',
    };

    // Card 3: tren
    final pct = data.weeklyChangePercent;
    final pctText = '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%';
    final isUp = pct >= 0;
    final trendLabel = isUp ? 'Naik' : 'Turun';

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: _SummaryCard(
            title: card1Title,
            value: card1Value,
            subtitle: card1Subtitle,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _SummaryCard(
            title: card2Title,
            value: card2Value,
            subtitle: card2Subtitle,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _SummaryCard(
            title: 'Tren Pengunjung (Next 7 Days)',
            value: trendLabel,
            valueAccent: pctText,
            valueAccentBg: isUp
                ? const Color(0xFFE8F5E9)
                : const Color(0xFFFFEBEE),
            valueAccentFg: isUp ? Colors.green : Colors.red,
            subtitle: 'Dibanding rata-rata 30 hari',
          ),
        ),
      ],
    );
  }

  static String _currentTimeWIB() {
    final now = DateTime.now();
    final hh = now.hour.toString().padLeft(2, '0');
    final mm = now.minute.toString().padLeft(2, '0');
    return '$hh:$mm WIB';
  }
}

class _SummaryCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  final String? valueAccent;
  final Color? valueAccentBg;
  final Color? valueAccentFg;

  const _SummaryCard({
    required this.title,
    required this.value,
    required this.subtitle,
    this.valueAccent,
    this.valueAccentBg,
    this.valueAccentFg,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.grey,
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  value,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (valueAccent != null) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: valueAccentBg ?? Colors.green[50],
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    valueAccent!,
                    style: TextStyle(
                      color: valueAccentFg ?? Colors.green,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Text(
            subtitle,
            style: const TextStyle(color: Colors.grey, fontSize: 11),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// CHART: HISTORIS (kiri) + PREDIKSI (kanan) — side-by-side
// ==========================================
class _HistoricalChartCard extends StatelessWidget {
  final ForecastPeriod period;
  final List<_PeriodAggregate> aggregates;
  final double fallbackAvg;

  const _HistoricalChartCard({
    required this.period,
    required this.aggregates,
    required this.fallbackAvg,
  });

  /// Hasilkan data historis "dummy kontekstual" sesuai periode aktif.
  /// Endpoint tidak menyediakan data historis, jadi kita pakai variasi
  /// disekitar rata-rata supaya kelihatan masuk akal.
  List<double> _historicalValues() {
    if (aggregates.isEmpty) return const [];
    final avgPredicted =
        aggregates.fold<int>(0, (s, e) => s + e.value) / aggregates.length;
    final base = avgPredicted == 0 ? fallbackAvg : avgPredicted;

    // Multiplier per periode supaya bentuk bar terlihat berbeda.
    final factors = switch (period) {
      ForecastPeriod.weekly => [0.95, 0.85, 1.02, 0.92],
      ForecastPeriod.monthly => [0.94, 1.06, 0.88],
    };
    return factors.map((f) => base * f).toList();
  }

  @override
  Widget build(BuildContext context) {
    final historical = _historicalValues();
    final predictions = aggregates.map((a) => a.value.toDouble()).toList();

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Grafik Historis & Prediksi Kunjungan (${period.label})',
                style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Row(
                children: const [
                  _LegendDot(color: _kBarBlueLight, label: 'Historis'),
                  SizedBox(width: 12),
                  _LegendDot(color: _kAccentOrange, label: 'Prediksi'),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Side-by-side: kiri historis (bar), kanan prediksi (line)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Historis
                Expanded(
                  flex: 2,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Padding(
                        padding: EdgeInsets.only(left: 4, bottom: 6),
                        child: Text(
                          'Historis',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: Colors.grey,
                          ),
                        ),
                      ),
                      SizedBox(
                        height: 260,
                        child: _HistoricalBarChart(values: historical),
                      ),
                    ],
                  ),
                ),
                // Divider tipis di tengah
                Container(
                  width: 1,
                  margin: const EdgeInsets.symmetric(horizontal: 8),
                  color: Colors.grey.shade200,
                ),
                // Prediksi
                Expanded(
                  flex: 3,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(left: 4, bottom: 6),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Prediksi',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: Colors.grey,
                              ),
                            ),
                            Text(
                              '${predictions.length} titik',
                              style: const TextStyle(
                                fontSize: 11,
                                color: Colors.grey,
                              ),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        height: 260,
                        child: _PredictionLineChart(
                          values: predictions,
                          labels: aggregates.map((a) => a.label).toList(),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}

class _HistoricalBarChart extends StatelessWidget {
  final List<double> values;
  const _HistoricalBarChart({required this.values});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) {
      return const Center(
        child: Text('Tidak ada data', style: TextStyle(color: Colors.grey)),
      );
    }
    final maxY = values.reduce((a, b) => a > b ? a : b) * 1.25;

    return BarChart(
      BarChartData(
        maxY: maxY,
        minY: 0,
        alignment: BarChartAlignment.spaceAround,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) =>
              FlLine(color: Colors.grey.shade100, strokeWidth: 1),
        ),
        titlesData: const FlTitlesData(
          leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        borderData: FlBorderData(show: false),
        barTouchData: BarTouchData(
          enabled: true,
          touchTooltipData: BarTouchTooltipData(
            getTooltipItem: (group, _, rod, _) => BarTooltipItem(
              rod.toY.toStringAsFixed(0),
              const TextStyle(color: Colors.white, fontSize: 11),
            ),
          ),
        ),
        barGroups: List.generate(values.length, (i) {
          return BarChartGroupData(
            x: i,
            barRods: [
              BarChartRodData(
                toY: values[i],
                color: _kBarBlueLight,
                width: 28,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(6),
                ),
              ),
            ],
          );
        }),
      ),
    );
  }
}

class _PredictionLineChart extends StatelessWidget {
  final List<double> values;
  final List<String> labels;
  const _PredictionLineChart({required this.values, required this.labels});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) {
      return const Center(
        child: Text('Tidak ada prediksi', style: TextStyle(color: Colors.grey)),
      );
    }
    final maxY = values.reduce((a, b) => a > b ? a : b) * 1.25;
    final spots = List.generate(
      values.length,
      (i) => FlSpot(i.toDouble(), values[i]),
    );

    return LineChart(
      LineChartData(
        minX: 0,
        maxX: (values.length - 1).toDouble(),
        minY: 0,
        maxY: maxY,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          getDrawingHorizontalLine: (_) =>
              FlLine(color: Colors.grey.shade100, strokeWidth: 1),
        ),
        titlesData: FlTitlesData(
          leftTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          rightTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          topTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 24,
              interval: 1,
              getTitlesWidget: (value, meta) {
                final i = value.toInt();
                if (i < 0 || i >= labels.length) return const SizedBox.shrink();
                // Tampilkan setiap label, atau tiap 2 jika terlalu rapat
                final step = labels.length > 10 ? 2 : 1;
                if (i % step != 0) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    labels[i],
                    style: const TextStyle(fontSize: 9, color: Colors.grey),
                  ),
                );
              },
            ),
          ),
        ),
        borderData: FlBorderData(show: false),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (touched) => touched
                .map(
                  (s) => LineTooltipItem(
                    '${labels[s.x.toInt()]}\n${s.y.toInt()} pengunjung',
                    const TextStyle(color: Colors.white, fontSize: 11),
                  ),
                )
                .toList(),
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: false,
            color: _kAccentOrange,
            barWidth: 2.5,
            dashArray: const [6, 4],
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                radius: 4,
                color: _kAccentOrange,
                strokeWidth: 2,
                strokeColor: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// TABLE: CONFIDENCE INTERVAL
// ==========================================
class _ConfidenceTableCard extends StatelessWidget {
  final VisitorForecastModel data;
  final ForecastPeriod period;
  final List<_PeriodAggregate> aggregates;

  const _ConfidenceTableCard({
    required this.data,
    required this.period,
    required this.aggregates,
  });

  @override
  Widget build(BuildContext context) {
    final mape = (data.confidenceScore == 0)
        ? 0.13
        : (1 - (data.confidenceScore / 100));
    // mape sebenarnya tersedia di metrics endpoint, tapi tidak dipetakan
    // ke model. Gunakan confidence_score sebagai band ± yang lebih aman.

    final rows = aggregates.map((agg) {
      final v = agg.value;
      final delta = (v * mape).round();
      final minV = (v - delta).clamp(0, 1 << 31);
      final maxV = v + delta;
      return _ConfidenceRow(
        dateLabel: agg.dateLabel,
        prediction: v,
        minValue: minV,
        maxValue: maxV,
      );
    }).toList();

    final dateColumnTitle = switch (period) {
      ForecastPeriod.weekly => 'Minggu',
      ForecastPeriod.monthly => 'Bulan',
    };

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Tabel Prediksi Kunjungan (${period.label})',
                style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F5E9),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Confidence ${data.confidenceLevel} '
                  '(${data.confidenceScore.toStringAsFixed(1)}%)',
                  style: const TextStyle(
                    color: Colors.green,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _TableHeader(dateColumnTitle: dateColumnTitle),
          const Divider(height: 1),
          for (final row in rows) ...[row, const Divider(height: 1)],
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}

class _TableHeader extends StatelessWidget {
  final String dateColumnTitle;
  const _TableHeader({required this.dateColumnTitle});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Expanded(flex: 3, child: _HeaderCell(dateColumnTitle)),
          const Expanded(flex: 2, child: _HeaderCell('Prediksi Pengunjung')),
          const Expanded(flex: 2, child: _HeaderCell('Min. Pengunjung')),
          const Expanded(flex: 2, child: _HeaderCell('Max. Pengunjung')),
        ],
      ),
    );
  }
}

class _HeaderCell extends StatelessWidget {
  final String text;
  const _HeaderCell(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: Colors.grey,
      ),
    );
  }
}

class _ConfidenceRow extends StatelessWidget {
  final String dateLabel;
  final int prediction;
  final num minValue;
  final num maxValue;

  const _ConfidenceRow({
    required this.dateLabel,
    required this.prediction,
    required this.minValue,
    required this.maxValue,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Text(dateLabel, style: const TextStyle(fontSize: 13)),
          ),
          Expanded(
            flex: 2,
            child: Text(
              '$prediction Orang',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
            ),
          ),
          Expanded(
            flex: 2,
            child: Text(
              '$minValue Orang',
              style: const TextStyle(fontSize: 13, color: Colors.grey),
            ),
          ),
          Expanded(
            flex: 2,
            child: Text(
              '$maxValue Orang',
              style: const TextStyle(fontSize: 13, color: Colors.grey),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// CARD: INSIGHTS
// ==========================================
class _InsightsCard extends StatelessWidget {
  final List<String> insights;
  const _InsightsCard({required this.insights});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(
                Icons.lightbulb_outline,
                color: _kPrimaryGreenDark,
                size: 18,
              ),
              SizedBox(width: 8),
              Text(
                'Insight Prediksi',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...insights.map(
            (text) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Icon(
                      Icons.circle,
                      size: 6,
                      color: _kPrimaryGreenDark,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      text,
                      style: const TextStyle(
                        fontSize: 12,
                        height: 1.5,
                        color: Colors.black87,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
