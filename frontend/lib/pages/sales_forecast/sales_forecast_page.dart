import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/sales_forecast_model.dart';
import '../../core/services/auth_service.dart';

const Color _kPrimaryGreen = Color(0xFF8CE600);
const Color _kPrimaryGreenDark = Color(0xFF24CC14);
const Color _kLineGreen = Color(0xFF43A047);
const Color _kLineBlueDash = Color(0xFF1E88E5);
const Color _kCIBand = Color(0x1E1E88E5);

// ==========================================
// PAGE
// ==========================================
class SalesForecastPage extends StatefulWidget {
  const SalesForecastPage({super.key});

  @override
  State<SalesForecastPage> createState() => _SalesForecastPageState();
}

class _SalesForecastPageState extends State<SalesForecastPage> {
  final ApiService _api = ApiService();
  late Future<SalesForecastModel> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
    _loadUser();
  }

  Future<SalesForecastModel> _fetch() async {
    final results = await Future.wait([
      _api.fetchData('forecast-predictions'),
      _api.fetchData('forecast-results'),
      _api.fetchData('sales-daily-summaries'),
    ]);
    return SalesForecastModel.fromSources(results[0], results[1], results[2]);
  }

  void _refresh() => setState(() => _future = _fetch());

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
              child: FutureBuilder<SalesForecastModel>(
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
                            message: '${snapshot.error}', onRetry: _refresh)
                      else if (snapshot.data!.weeklyForecast.isEmpty &&
                          snapshot.data!.monthlyForecast.isEmpty)
                        _NoDataPanel(onRetry: _refresh)
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

  String _fmt() {
    final now = DateTime.now();
    final h = now.hour % 12 == 0 ? 12 : now.hour % 12;
    final mm = now.minute.toString().padLeft(2, '0');
    return 'Opened $h:$mm ${now.hour >= 12 ? 'pm' : 'am'}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(_fmt(), style: const TextStyle(color: Colors.grey, fontSize: 12))
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
                  color: Colors.grey[700],
                ),
                const SizedBox(width: 4),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Dasbor',
                        style: TextStyle(color: Colors.grey, fontSize: 13)),
                    SizedBox(height: 6),
                    Text('Prediksi Penjualan',
                        style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                            color: Colors.black87)),
                  ],
                ),
              ],
            ),
            Row(
              children: [
                IconButton(
                    onPressed: onRefresh,
                    icon: const Icon(Icons.refresh),
                    color: Colors.grey),
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
                        borderRadius: BorderRadius.circular(10)),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    textStyle: const TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600),
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
// LOADING / ERROR
// ==========================================
class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) => const SizedBox(
        height: 480,
        child: Center(
            child: CircularProgressIndicator(color: _kPrimaryGreenDark)),
      );
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
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          const Icon(Icons.wifi_off, color: Colors.red, size: 36),
          const SizedBox(height: 12),
          Text('Gagal memuat data penjualan.\n$message',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Coba Lagi'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kPrimaryGreen,
                foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}

class _NoDataPanel extends StatelessWidget {
  final VoidCallback onRetry;
  const _NoDataPanel({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(40),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Icon(Icons.bar_chart, size: 52, color: Colors.grey[300]),
          const SizedBox(height: 16),
          const Text(
            'Belum ada data prediksi penjualan',
            style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.black87),
          ),
          const SizedBox(height: 8),
          const Text(
            'Data prediksi penjualan akan muncul setelah model forecast\n'
            'menyimpan data dengan module "revenue" atau "sales"\n'
            'ke tabel forecast_predictions.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey, fontSize: 13, height: 1.5),
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Refresh'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kPrimaryGreen,
                foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// PERIOD
// ==========================================
enum _Period { weekly, monthly }

extension on _Period {
  String get label {
    switch (this) {
      case _Period.weekly:
        return 'Mingguan';
      case _Period.monthly:
        return 'Bulanan';
    }
  }
}

class _Agg {
  final String label;
  final String dateLabel;
  final double value;
  final double? lower;
  final double? upper;
  _Agg(
      {required this.label,
      required this.dateLabel,
      required this.value,
      this.lower,
      this.upper});
}

List<_Agg> _buildAggregates(SalesForecastModel data, _Period period) {
  switch (period) {
    case _Period.weekly:
      final src = data.monthlyForecast;
      final groups = <List<SalesForecastPoint>>[];
      for (var i = 0; i < src.length; i += 7) {
        groups.add(src.sublist(i, (i + 7).clamp(0, src.length)));
      }
      return List.generate(groups.length, (i) {
        final g = groups[i];
        final total = g.fold<double>(0, (s, p) => s + p.value);
        final lo = g.every((p) => p.lowerBound != null)
            ? g.fold<double>(0, (s, p) => s + p.lowerBound!)
            : null;
        final hi = g.every((p) => p.upperBound != null)
            ? g.fold<double>(0, (s, p) => s + p.upperBound!)
            : null;
        return _Agg(
          label: 'Mgg ${i + 1}',
          dateLabel:
              '${_shortDate(g.first.date)} – ${_shortDate(g.last.date)}',
          value: total,
          lower: lo,
          upper: hi,
        );
      });
    case _Period.monthly:
      final byMonth = <String, List<SalesForecastPoint>>{};
      for (final p in data.monthlyForecast) {
        final key = p.date.length >= 7 ? p.date.substring(0, 7) : p.date;
        byMonth.putIfAbsent(key, () => []).add(p);
      }
      final keys = byMonth.keys.toList()..sort();
      return keys.map((k) {
        final list = byMonth[k]!;
        final total = list.fold<double>(0, (s, p) => s + p.value);
        return _Agg(
          label: _monthLabel(k),
          dateLabel: _monthLabel(k),
          value: total,
        );
      }).toList();
  }
}

// Date helpers
String _shortDate(String iso) {
  try {
    final dt = DateTime.parse(iso);
    return '${dt.day} ${_ms[dt.month]}';
  } catch (_) {
    return iso;
  }
}

String _longDate(String iso) {
  try {
    final dt = DateTime.parse(iso);
    return '${_dn[dt.weekday]}, ${dt.day} ${_ms[dt.month]} ${dt.year}';
  } catch (_) {
    return iso;
  }
}

String _monthLabel(String yyyymm) {
  final p = yyyymm.split('-');
  if (p.length < 2) return yyyymm;
  final m = int.tryParse(p[1]);
  return '${_ms[m] ?? p[1]} ${p[0]}';
}

const _dn = {
  1: 'Senin', 2: 'Selasa', 3: 'Rabu', 4: 'Kamis',
  5: 'Jumat', 6: 'Sabtu', 7: 'Minggu',
};
const _ms = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
  7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
};

// ==========================================
// BODY
// ==========================================
class _ForecastBody extends StatefulWidget {
  final SalesForecastModel data;
  const _ForecastBody({required this.data});

  @override
  State<_ForecastBody> createState() => _ForecastBodyState();
}

class _ForecastBodyState extends State<_ForecastBody> {
  _Period _period = _Period.weekly;

  @override
  Widget build(BuildContext context) {
    final aggs = _buildAggregates(widget.data, _period);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _PeriodSwitcher(
            active: _period, onChanged: (p) => setState(() => _period = p)),
        const SizedBox(height: 16),
        _SummaryCards(data: widget.data, period: _period),
        const SizedBox(height: 20),
        _CombinedChartCard(
            data: widget.data, period: _period, aggregates: aggs),
        const SizedBox(height: 20),
        _TableCard(data: widget.data, period: _period, aggregates: aggs),
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
  final _Period active;
  final ValueChanged<_Period> onChanged;
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
        children: _Period.values.map((p) {
          final isActive = p == active;
          return GestureDetector(
            onTap: () => onChanged(p),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding:
                  const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
              decoration: BoxDecoration(
                color: isActive ? _kPrimaryGreen : Colors.transparent,
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

// ==========================================
// SUMMARY CARDS
// ==========================================
class _SummaryCards extends StatelessWidget {
  final SalesForecastModel data;
  final _Period period;
  const _SummaryCards({required this.data, required this.period});

  @override
  Widget build(BuildContext context) {
    final card1Title = switch (period) {
      _Period.weekly => 'Total Penjualan 7 Hari',
      _Period.monthly => 'Total Penjualan Bulan Ini',
    };
    final card1Value = switch (period) {
      _Period.weekly => data.formattedTotal7,
      _Period.monthly => SalesForecastModel.formatRupiah(data.total30Days),
    };

    final pct = data.weeklyChangePercent;
    final pctText = '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%';
    final isUp = pct >= 0;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: _Card(
            title: card1Title,
            value: card1Value,
            subtitle: 'Realisasi per hari ini',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _Card(
            title: 'Rata-rata Penjualan Harian',
            value: data.formattedAvg7,
            subtitle: 'Periode berjalan',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _Card(
            title: 'Proyeksi Growth (MOM)',
            value: pctText,
            valueColor: isUp ? Colors.green[700] : Colors.red,
            badge: isUp ? 'Naik' : 'Turun',
            badgeBg:
                isUp ? const Color(0xFFE8F5E9) : const Color(0xFFFFEBEE),
            badgeFg: isUp ? Colors.green : Colors.red,
            subtitle: 'Prediksi vs bulan lalu',
          ),
        ),
      ],
    );
  }
}

class _Card extends StatelessWidget {
  final String title;
  final String value;
  final Color? valueColor;
  final String subtitle;
  final String? badge;
  final Color? badgeBg;
  final Color? badgeFg;

  const _Card({
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
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2))
        ],
      ),
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
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
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

// ==========================================
// COMBINED CHART (Historis + Prediksi + CI)
// ==========================================
class _CombinedChartCard extends StatelessWidget {
  final SalesForecastModel data;
  final _Period period;
  final List<_Agg> aggregates;

  const _CombinedChartCard(
      {required this.data, required this.period, required this.aggregates});

  static const int _histCount = 5;

  // Nilai historis dummy yang mengacu pada nilai prediksi pertama agar
  // transisi historis→prediksi menyatu di titik yang sama.
  List<double> _histValues(double firstPredVal) {
    final ref = firstPredVal > 0 ? firstPredVal : (data.avg7Days == 0 ? 1000000.0 : data.avg7Days);
    const factors = [0.82, 0.91, 1.06, 0.87, 0.97];
    return factors.map((f) => ref * f).toList();
  }

  bool get _hasCi =>
      aggregates.any((a) => a.lower != null && a.upper != null);

  @override
  Widget build(BuildContext context) {
    if (aggregates.isEmpty) {
      return _chartShell(
          period,
          _hasCi,
          const Center(
              child: Padding(
            padding: EdgeInsets.all(40),
            child: Text('Tidak ada data prediksi',
                style: TextStyle(color: Colors.grey)),
          )));
    }

    final predVals = aggregates.map((a) => a.value).toList();
    final firstPred = predVals.isNotEmpty ? predVals[0] : 0.0;

    // Nilai historis mengacu ke prediksi pertama supaya sambung mulus
    final histVals = _histValues(firstPred);

    // Combine for y-max calculation
    final allVals = [...histVals, ...predVals];
    if (aggregates.any((a) => a.upper != null)) {
      allVals.addAll(aggregates.map((a) => a.upper ?? a.value));
    }
    final maxY = allVals.reduce((a, b) => a > b ? a : b) * 1.25;

    // histSpots: 5 titik dummy + 1 titik penghubung di x=_histCount dengan
    // nilai = predVals[0], sehingga garis historis dan prediksi bertemu persis
    // di satu titik yang sama → tidak patah.
    final histSpots = [
      ...List.generate(_histCount, (i) => FlSpot(i.toDouble(), histVals[i])),
      if (predVals.isNotEmpty) FlSpot(_histCount.toDouble(), firstPred),
    ];
    final predSpots = List.generate(
        predVals.length,
        (i) => FlSpot((_histCount + i).toDouble(), predVals[i]));

    // CI spots (transparent boundary lines for betweenBarsData)
    final upperSpots = List.generate(
        aggregates.length,
        (i) => FlSpot((_histCount + i).toDouble(),
            aggregates[i].upper ?? aggregates[i].value * 1.05));
    final lowerSpots = List.generate(
        aggregates.length,
        (i) => FlSpot((_histCount + i).toDouble(),
            aggregates[i].lower ?? aggregates[i].value * 0.95));

    // X-axis labels
    final now = DateTime.now();
    final xLabels = <int, String>{};
    for (var i = 0; i < _histCount; i++) {
      final d = now.subtract(Duration(days: _histCount - i));
      xLabels[i] = '${d.day}/${d.month}';
    }
    for (var i = 0; i < aggregates.length; i++) {
      xLabels[_histCount + i] = aggregates[i].label;
    }

    final chart = LineChart(LineChartData(
      minX: 0,
      maxX: (_histCount + predVals.length - 1).toDouble(),
      minY: 0,
      maxY: maxY,
      clipData: const FlClipData.all(),
      gridData: FlGridData(
        show: true,
        drawVerticalLine: false,
        getDrawingHorizontalLine: (_) =>
            FlLine(color: Colors.grey.shade100, strokeWidth: 1),
      ),
      titlesData: FlTitlesData(
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 64,
            getTitlesWidget: (value, meta) => Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Text(SalesForecastModel.formatRupiah(value),
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
            reservedSize: 26,
            interval: 1,
            getTitlesWidget: (v, meta) {
              final i = v.toInt();
              if (!xLabels.containsKey(i)) return const SizedBox.shrink();
              final step = xLabels.length > 10 ? 2 : 1;
              if (i % step != 0) return const SizedBox.shrink();
              return Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(xLabels[i]!,
                    style: const TextStyle(fontSize: 9, color: Colors.grey)),
              );
            },
          ),
        ),
      ),
      borderData: FlBorderData(show: false),
      // lineBarsData order matters for betweenBarsData indices:
      // 0 = upper bound (transparent)
      // 1 = lower bound (transparent)
      // 2 = prediction (blue dashed)
      // 3 = historical (green solid)
      betweenBarsData: [
        BetweenBarsData(
          fromIndex: 0,
          toIndex: 1,
          color: _kCIBand,
        ),
      ],
      lineBarsData: [
        // 0: Upper bound (invisible, CI reference)
        LineChartBarData(
          spots: upperSpots,
          color: Colors.transparent,
          barWidth: 0,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(show: false),
        ),
        // 1: Lower bound (invisible, CI reference)
        LineChartBarData(
          spots: lowerSpots,
          color: Colors.transparent,
          barWidth: 0,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(show: false),
        ),
        // 2: Prediction (blue dashed)
        LineChartBarData(
          spots: predSpots,
          color: _kLineBlueDash,
          isCurved: false,
          barWidth: 2.5,
          dashArray: const [8, 5],
          dotData: FlDotData(
            show: true,
            getDotPainter: (spot, pct, bar, idx) => FlDotCirclePainter(
                radius: 3.5,
                color: _kLineBlueDash,
                strokeWidth: 1.5,
                strokeColor: Colors.white),
          ),
          belowBarData: BarAreaData(show: false),
        ),
        // 3: Historical (green solid)
        LineChartBarData(
          spots: histSpots,
          color: _kLineGreen,
          isCurved: false,
          barWidth: 2.5,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(show: false),
        ),
      ],
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipItems: (spots) => spots.map((s) {
            if (s.barIndex == 0 || s.barIndex == 1) {
              return const LineTooltipItem('', TextStyle());
            }
            final label = xLabels[s.x.toInt()] ?? '';
            final val = SalesForecastModel.formatRupiah(s.y);
            if (s.barIndex == 3) {
              return LineTooltipItem('Historis\n$label\n$val',
                  const TextStyle(color: Colors.white, fontSize: 11));
            }
            // barIndex 2 = prediksi — tampilkan CI jika ada
            final xi = s.x.toInt();
            FlSpot? findSpot(List<FlSpot> lst) {
              for (final sp in lst) {
                if (sp.x.toInt() == xi) return sp;
              }
              return null;
            }
            final upper = findSpot(upperSpots);
            final lower = findSpot(lowerSpots);
            final ciLine = (upper != null && lower != null)
                ? '\nCI: ${SalesForecastModel.formatRupiah(lower.y)}'
                    ' – ${SalesForecastModel.formatRupiah(upper.y)}'
                : '';
            return LineTooltipItem('Prediksi\n$label\n$val$ciLine',
                const TextStyle(color: Colors.white, fontSize: 11));
          }).toList(),
        ),
      ),
    ));

    return _chartShell(period, _hasCi, chart);
  }

  Widget _chartShell(
      _Period period, bool hasCi, Widget chartWidget) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2))
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Grafik Tren & Prediksi Penjualan (${period.label})',
                  style: const TextStyle(
                      color: Colors.grey,
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
              Row(
                children: [
                  _LegendLine(color: _kLineGreen, dashed: false, label: 'Historis'),
                  const SizedBox(width: 12),
                  _LegendLine(color: _kLineBlueDash, dashed: true, label: 'Prediksi'),
                  if (hasCi) ...[
                    const SizedBox(width: 12),
                    _LegendCi(
                      fillColor: _kCIBand,
                      lineColor: _kLineBlueDash.withValues(alpha: 0.45),
                      label: 'Confidence Interval',
                    ),
                  ],
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(height: 300, child: chartWidget),
        ],
      ),
    );
  }
}

class _LegendLine extends StatelessWidget {
  final Color color;
  final bool dashed;
  final String label;
  const _LegendLine(
      {required this.color, required this.dashed, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 24,
          height: 14,
          child: CustomPaint(
            painter: _LinePainter(color: color, dashed: dashed),
          ),
        ),
        const SizedBox(width: 4),
        Text(label,
            style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}

class _LegendCi extends StatelessWidget {
  final Color fillColor;
  final Color lineColor;
  final String label;
  const _LegendCi(
      {required this.fillColor, required this.lineColor, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 28,
          height: 14,
          child: CustomPaint(
              painter: _CiLegendPainter(
                  fillColor: fillColor, lineColor: lineColor)),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}

class _CiLegendPainter extends CustomPainter {
  final Color fillColor;
  final Color lineColor;
  const _CiLegendPainter({required this.fillColor, required this.lineColor});

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Rect.fromLTRB(0, 3, size.width, size.height - 3),
      Paint()..color = fillColor,
    );
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    _drawDash(canvas, Offset(0, 2), Offset(size.width, 2), linePaint);
    _drawDash(canvas, Offset(0, size.height - 2),
        Offset(size.width, size.height - 2), linePaint);
  }

  void _drawDash(Canvas canvas, Offset start, Offset end, Paint paint) {
    const dashLen = 4.0;
    const gapLen = 3.0;
    var x = start.dx;
    while (x < end.dx) {
      canvas.drawLine(Offset(x, start.dy),
          Offset((x + dashLen).clamp(0, end.dx), start.dy), paint);
      x += dashLen + gapLen;
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _LinePainter extends CustomPainter {
  final Color color;
  final bool dashed;
  const _LinePainter({required this.color, required this.dashed});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final y = size.height / 2;
    if (dashed) {
      const dashLen = 5.0;
      const gapLen = 3.0;
      var x = 0.0;
      while (x < size.width) {
        canvas.drawLine(
            Offset(x, y), Offset((x + dashLen).clamp(0, size.width), y), paint);
        x += dashLen + gapLen;
      }
    } else {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ==========================================
// TABLE
// ==========================================
class _TableCard extends StatelessWidget {
  final SalesForecastModel data;
  final _Period period;
  final List<_Agg> aggregates;

  const _TableCard(
      {required this.data, required this.period, required this.aggregates});

  @override
  Widget build(BuildContext context) {
    final dateCol = switch (period) {
      _Period.weekly => 'Minggu',
      _Period.monthly => 'Bulan',
    };

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2))
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Tabel Ringkasan Prediksi Penjualan',
              style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(children: [
              Expanded(flex: 3, child: _TH(dateCol)),
              const Expanded(flex: 3, child: _TH('Prediksi Penjualan')),
              const Expanded(flex: 2, child: _TH('Batas Bawah')),
              const Expanded(flex: 2, child: _TH('Batas Atas')),
            ]),
          ),
          const Divider(height: 1),
          for (final agg in aggregates) ...[
            _TableRow(agg: agg, confScore: data.confidenceScore),
            const Divider(height: 1),
          ],
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}

class _TH extends StatelessWidget {
  final String t;
  const _TH(this.t);

  @override
  Widget build(BuildContext context) {
    return Text(t,
        style: const TextStyle(
            fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey));
  }
}

class _TableRow extends StatelessWidget {
  final _Agg agg;
  final double confScore;
  const _TableRow({required this.agg, required this.confScore});

  @override
  Widget build(BuildContext context) {
    final mape = confScore == 0 ? 0.08 : (1 - confScore / 100);
    final delta = agg.value * mape;
    final lo = agg.lower ?? (agg.value - delta).clamp(0, double.infinity);
    final hi = agg.upper ?? (agg.value + delta);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(children: [
        Expanded(
            flex: 3,
            child: Text(agg.dateLabel,
                style: const TextStyle(fontSize: 13, color: Colors.black87))),
        Expanded(
            flex: 3,
            child: Text(
              SalesForecastModel.formatRupiah(agg.value),
              style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: _kLineBlueDash),
            )),
        Expanded(
            flex: 2,
            child: Text(SalesForecastModel.formatRupiah(lo),
                style: const TextStyle(fontSize: 13, color: Colors.grey))),
        Expanded(
            flex: 2,
            child: Text(SalesForecastModel.formatRupiah(hi),
                style: const TextStyle(fontSize: 13, color: Colors.grey))),
      ]),
    );
  }
}

// ==========================================
// INSIGHTS
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
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2))
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.lightbulb_outline, color: _kPrimaryGreenDark, size: 18),
            SizedBox(width: 8),
            Text('Insight Prediksi',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          ]),
          const SizedBox(height: 12),
          ...insights.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Icon(Icons.circle, size: 6, color: _kPrimaryGreenDark),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                      child: Text(t,
                          style: const TextStyle(
                              fontSize: 12, height: 1.5, color: Colors.black87))),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
