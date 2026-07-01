import 'package:flutter/material.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/visitor_forecast_model.dart';
import '../../core/services/auth_service.dart';
import '../../widgets/forecast_chart.dart';

// ==========================================
// KONFIGURASI
// ==========================================
const Color _kPrimaryGreen = Color(0xFF8CE600);
const Color _kPrimaryGreenDark = Color(0xFF24CC14);
const Color _kAccentOrange = Color(0xFFF59E0B);

const String _kForecastResultsEndpoint = 'forecast-results';

// ==========================================
// PAGE
// ==========================================
class VisitorForecastPage extends StatefulWidget {
  final String storeId;

  const VisitorForecastPage({super.key, required this.storeId});

  @override
  State<VisitorForecastPage> createState() => _VisitorForecastPageState();
}

/// Forecast (forecast_results) + data historis nyata (sales_daily_summaries,
/// pakai total_transaction sebagai proksi jumlah pengunjung).
class _VisitorBundle {
  final VisitorForecastModel model;
  final List<dynamic> summaries;

  /// Metrik evaluasi model (MAE/RMSE/WAPE) per granularitas, dari
  /// /api/forecast/visitors/latest.
  final Map<ForecastPeriodKind, ForecastModelMetrics> metrics;
  const _VisitorBundle(this.model, this.summaries, this.metrics);
}

class _VisitorForecastPageState extends State<VisitorForecastPage> {
  final ApiService _apiService = ApiService();
  late Future<_VisitorBundle> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
    _loadUser();
  }

  Future<_VisitorBundle> _fetch() async {
    final data = await Future.wait([
      _apiService.fetchData(_kForecastResultsEndpoint),
      _apiService.fetchData('sales-daily-summaries'),
    ]);
    final maps = await Future.wait([
      _apiService.fetchMap('forecast/visitors/latest?horizon_label=daily'),
      _apiService.fetchMap('forecast/visitors/latest?horizon_label=weekly'),
      _apiService.fetchMap('forecast/visitors/latest?horizon_label=monthly'),
    ]);
    ForecastModelMetrics parse(Map<String, dynamic>? resp) =>
        ForecastModelMetrics.fromMetricsJson(
            (resp?['run'] as Map?)?['metrics'] as Map?);
    final metrics = {
      ForecastPeriodKind.daily: parse(maps[0]),
      ForecastPeriodKind.weekly: parse(maps[1]),
      ForecastPeriodKind.monthly: parse(maps[2]),
    };
    return _VisitorBundle(
        VisitorForecastModel.fromResults(data[0]), data[1], metrics);
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
          SidebarWidget(userName: _userName, name: _name),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(32, 24, 32, 32),
              child: FutureBuilder<_VisitorBundle>(
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
                      else
                        _ForecastBody(bundle: snapshot.data!),
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
            Text(_formatNowOpened(),
                style: const TextStyle(color: Colors.grey, fontSize: 12)),
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
                    Text('Dasbor',
                        style: TextStyle(color: Colors.grey, fontSize: 13)),
                    SizedBox(height: 6),
                    Text('Prediksi Pengunjung',
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
// LOADING / ERROR / NO DATA
// ==========================================
class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 480,
      child: Center(child: CircularProgressIndicator(color: _kPrimaryGreenDark)),
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
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          const Icon(Icons.wifi_off, color: Colors.red, size: 36),
          const SizedBox(height: 12),
          Text('Gagal memuat prediksi.\n$message',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Coba Lagi'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kPrimaryGreen, foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}

class _NoDataPanel extends StatelessWidget {
  const _NoDataPanel();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(40),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Icon(Icons.people_alt_outlined, size: 48, color: Colors.grey[300]),
          const SizedBox(height: 14),
          const Text('Belum ada data prediksi pengunjung',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.black87)),
          const SizedBox(height: 8),
          const Text(
            'Data akan muncul setelah model forecast menyimpan hasil\n'
            'pengunjung ke tabel forecast_results.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey, fontSize: 13, height: 1.5),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// DATE HELPERS
// ==========================================
String _formatShortDate(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${d.day} ${_monthShort[d.month]}';
}

String _formatLongDate(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${_dayFullName[d.weekday]}, ${d.day} ${_monthShort[d.month]} ${d.year}';
}

String _dayShort(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${_dayShortName[d.weekday]} ${d.day}/${d.month}';
}

String _formatMonthLabel(String yyyymm) {
  final parts = yyyymm.split('-');
  if (parts.length < 2) return yyyymm;
  final m = int.tryParse(parts[1]);
  return '${_monthShort[m] ?? parts[1]} ${parts[0]}';
}

String _addDays(String iso, int days) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  final n = d.add(Duration(days: days));
  return '${n.year}-${n.month.toString().padLeft(2, '0')}-'
      '${n.day.toString().padLeft(2, '0')}';
}

const _monthShort = {
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

// ==========================================
// FORMATTER PENGUNJUNG
// ==========================================
String _thousands(int n) {
  if (n.abs() < 1000) return '$n';
  final s = n.abs().toString();
  final buf = StringBuffer(n < 0 ? '-' : '');
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) buf.write('.');
    buf.write(s[i]);
  }
  return buf.toString();
}

String _visitorsFull(double v) => '${_thousands(v.round())} Orang';

String _visitorsAxis(double v) {
  if (v >= 1000) return '${(v / 1000).toStringAsFixed(v >= 10000 ? 0 : 1)}k';
  return v.toStringAsFixed(0);
}

// ==========================================
// BODY UTAMA
// ==========================================
class _ForecastBody extends StatefulWidget {
  final _VisitorBundle bundle;
  const _ForecastBody({required this.bundle});

  @override
  State<_ForecastBody> createState() => _ForecastBodyState();
}

class _ForecastBodyState extends State<_ForecastBody> {
  ForecastPeriodKind _period = ForecastPeriodKind.daily;

  List<ForecastBar> _history() => buildHistoryBars(
        summaries: widget.bundle.summaries,
        valueOf: (r) => (r['total_transaction'] as num?)?.toDouble() ?? 0.0,
        period: _period,
      );

  /// Seri terkaya (harian) untuk tren yang konsisten antar tab.
  List<double> _trendSeries() {
    final m = widget.bundle.model;
    final src = m.dailyForecast.isNotEmpty ? m.dailyForecast : m.weeklyForecast;
    return src.map((p) => p.predictedVisitors.toDouble()).toList();
  }

  List<ForecastBar> _bars() {
    final d = widget.bundle.model;
    switch (_period) {
      case ForecastPeriodKind.daily:
        return d.dailyForecast
            .map((p) => ForecastBar(
                  label: _dayShort(p.date),
                  fullLabel: _formatLongDate(p.date),
                  value: p.predictedVisitors.toDouble(),
                  lower: p.lower,
                  upper: p.upper,
                  confidence: p.confidence,
                ))
            .toList();
      case ForecastPeriodKind.weekly:
        final list = d.weeklyForecast;
        return List.generate(list.length, (i) {
          final p = list[i];
          final end = _addDays(p.date, 6);
          return ForecastBar(
            label: 'Mgg ${i + 1}',
            fullLabel: '${_formatShortDate(p.date)} – ${_formatShortDate(end)}',
            value: p.predictedVisitors.toDouble(),
            lower: p.lower,
            upper: p.upper,
            confidence: p.confidence,
          );
        });
      case ForecastPeriodKind.monthly:
        return d.monthlyForecast.map((p) {
          final key = p.date.length >= 7 ? p.date.substring(0, 7) : p.date;
          return ForecastBar(
            label: _formatMonthLabel(key),
            fullLabel: _formatMonthLabel(key),
            value: p.predictedVisitors.toDouble(),
            lower: p.lower,
            upper: p.upper,
            confidence: p.confidence,
          );
        }).toList();
    }
  }

  @override
  Widget build(BuildContext context) {
    final bars = _bars();
    final history = _history();
    final periodColumn = switch (_period) {
      ForecastPeriodKind.daily => 'Tanggal',
      ForecastPeriodKind.weekly => 'Minggu',
      ForecastPeriodKind.monthly => 'Bulan',
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ForecastPeriodSwitcher(
          active: _period,
          activeColor: _kPrimaryGreen,
          onChanged: (p) => setState(() => _period = p),
        ),
        const SizedBox(height: 16),
        if (bars.isEmpty)
          const _NoDataPanel()
        else ...[
          ForecastSummaryCards(
              bars: bars,
              fmt: _visitorsFull,
              period: _period,
              trendPct: forecastTrendPct(_trendSeries())),
          const SizedBox(height: 20),
          ForecastTrendChart(
            title: 'Pengunjung: Data Real → Prediksi (${_period.label})',
            history: history,
            forecast: bars,
            fmtFull: _visitorsFull,
            fmtAxis: _visitorsAxis,
            lineColor: _kAccentOrange,
            bandColor: _kAccentOrange.withValues(alpha: 0.13),
          ),
          const SizedBox(height: 20),
          ForecastMetricsPanel(
            bars: bars,
            fmt: _visitorsFull,
            confidenceScore: widget.bundle.model.confidenceScore,
            accent: _kPrimaryGreenDark,
            modelMetrics: widget.bundle.metrics[_period],
          ),
          const SizedBox(height: 20),
          ForecastDetailTable(
            title: 'Tabel Detail Prediksi Pengunjung — ${_period.label}',
            periodColumn: periodColumn,
            bars: bars,
            fmt: _visitorsFull,
            accent: _kAccentOrange,
          ),
          const SizedBox(height: 20),
          if (widget.bundle.model.insights.isNotEmpty)
            _InsightsCard(insights: widget.bundle.model.insights),
        ],
      ],
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
    return ForecastCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.lightbulb_outline,
                  color: _kPrimaryGreenDark, size: 18),
              SizedBox(width: 8),
              Text('Insight Prediksi',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
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
                    child:
                        Icon(Icons.circle, size: 6, color: _kPrimaryGreenDark),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(text,
                        style: const TextStyle(
                            fontSize: 12, height: 1.5, color: Colors.black87)),
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
