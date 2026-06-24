import 'package:flutter/material.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/sales_forecast_model.dart';
import '../../core/services/auth_service.dart';
import '../../widgets/forecast_chart.dart';

const Color _kPrimaryGreen = Color(0xFF8CE600);
const Color _kPrimaryGreenDark = Color(0xFF24CC14);
const Color _kLineGreen = Color(0xFF43A047);

// ==========================================
// PAGE
// ==========================================
class SalesForecastPage extends StatefulWidget {
  const SalesForecastPage({super.key});

  @override
  State<SalesForecastPage> createState() => _SalesForecastPageState();
}

/// Forecast (dari forecast_results) + data historis nyata (sales_daily_summaries).
class _SalesBundle {
  final SalesForecastModel model;
  final List<dynamic> summaries;
  const _SalesBundle(this.model, this.summaries);
}

class _SalesForecastPageState extends State<SalesForecastPage> {
  final ApiService _api = ApiService();
  late Future<_SalesBundle> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
    _loadUser();
  }

  Future<_SalesBundle> _fetch() async {
    final r = await Future.wait([
      _api.fetchData('forecast-results'),
      _api.fetchData('sales-daily-summaries'),
    ]);
    return _SalesBundle(SalesForecastModel.fromResults(r[0]), r[1]);
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
          SidebarWidget(userName: _userName, name: _name),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(32, 24, 32, 32),
              child: FutureBuilder<_SalesBundle>(
                future: _future,
                builder: (context, snapshot) {
                  final model = snapshot.data?.model;
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
                      else if (model!.dailyForecast.isEmpty &&
                          model.weeklyForecast.isEmpty &&
                          model.monthlyForecast.isEmpty)
                        _NoDataPanel(onRetry: _refresh)
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
            Text(_fmt(),
                style: const TextStyle(color: Colors.grey, fontSize: 12))
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
// LOADING / ERROR / NO DATA
// ==========================================
class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) => const SizedBox(
        height: 480,
        child:
            Center(child: CircularProgressIndicator(color: _kPrimaryGreenDark)),
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
                backgroundColor: _kPrimaryGreen, foregroundColor: Colors.white),
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
      width: double.infinity,
      padding: const EdgeInsets.all(40),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Icon(Icons.bar_chart, size: 52, color: Colors.grey[300]),
          const SizedBox(height: 16),
          const Text('Belum ada data prediksi penjualan',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.black87)),
          const SizedBox(height: 8),
          const Text(
            'Data prediksi penjualan akan muncul setelah model forecast\n'
            'menyimpan hasil bertipe "sales"\n'
            'ke tabel forecast_results.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey, fontSize: 13, height: 1.5),
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Refresh'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kPrimaryGreen, foregroundColor: Colors.white),
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
  return '${d.day} ${_monthShort[d.month]} ${d.year}';
}

String _dayShort(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${d.day}/${d.month}';
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

// ==========================================
// BODY
// ==========================================
class _ForecastBody extends StatefulWidget {
  final _SalesBundle bundle;
  const _ForecastBody({required this.bundle});

  @override
  State<_ForecastBody> createState() => _ForecastBodyState();
}

class _ForecastBodyState extends State<_ForecastBody> {
  ForecastPeriodKind _period = ForecastPeriodKind.daily;

  List<ForecastBar> _history() => buildHistoryBars(
        summaries: widget.bundle.summaries,
        valueOf: (r) => (r['total_omzet'] as num?)?.toDouble() ?? 0.0,
        period: _period,
      );

  /// Seri terkaya (harian) untuk tren yang konsisten antar tab.
  List<double> _trendSeries() {
    final m = widget.bundle.model;
    final src = m.dailyForecast.isNotEmpty ? m.dailyForecast : m.weeklyForecast;
    return src.map((p) => p.value).toList();
  }

  List<ForecastBar> _bars() {
    final d = widget.bundle.model;
    switch (_period) {
      case ForecastPeriodKind.daily:
        return d.dailyForecast
            .map((p) => ForecastBar(
                  label: _dayShort(p.date),
                  fullLabel: _formatLongDate(p.date),
                  value: p.value,
                  lower: p.lowerBound,
                  upper: p.upperBound,
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
            value: p.value,
            lower: p.lowerBound,
            upper: p.upperBound,
          );
        });
      case ForecastPeriodKind.monthly:
        return d.monthlyForecast.map((p) {
          final key = p.date.length >= 7 ? p.date.substring(0, 7) : p.date;
          return ForecastBar(
            label: _formatMonthLabel(key),
            fullLabel: _formatMonthLabel(key),
            value: p.value,
            lower: p.lowerBound,
            upper: p.upperBound,
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
    String fmt(double v) => SalesForecastModel.formatRupiah(v);

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
          const _PeriodEmpty()
        else ...[
          ForecastSummaryCards(
              bars: bars,
              fmt: fmt,
              period: _period,
              trendPct: forecastTrendPct(_trendSeries())),
          const SizedBox(height: 20),
          ForecastTrendChart(
            title: 'Penjualan: Data Real → Prediksi (${_period.label})',
            history: history,
            forecast: bars,
            fmtFull: fmt,
            fmtAxis: fmt,
            lineColor: _kLineGreen,
            bandColor: _kLineGreen.withValues(alpha: 0.13),
          ),
          const SizedBox(height: 20),
          ForecastMetricsPanel(
            bars: bars,
            fmt: fmt,
            confidenceScore: widget.bundle.model.confidenceScore,
            confidenceLevel: widget.bundle.model.confidenceLevel,
            accent: _kPrimaryGreenDark,
          ),
          const SizedBox(height: 20),
          ForecastDetailTable(
            title: 'Tabel Detail Prediksi Penjualan — ${_period.label}',
            periodColumn: periodColumn,
            bars: bars,
            fmt: fmt,
            accent: _kLineGreen,
          ),
          const SizedBox(height: 20),
          if (widget.bundle.model.insights.isNotEmpty)
            _InsightsCard(insights: widget.bundle.model.insights),
        ],
      ],
    );
  }
}

/// Ditampilkan saat granularitas tertentu (mis. bulanan) belum tersedia
/// padahal granularitas lain ada.
class _PeriodEmpty extends StatelessWidget {
  const _PeriodEmpty();

  @override
  Widget build(BuildContext context) {
    return ForecastCardShell(
      padding: const EdgeInsets.all(32),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.timeline, size: 36, color: Colors.grey[300]),
            const SizedBox(height: 10),
            const Text('Belum ada data untuk periode ini',
                style: TextStyle(color: Colors.grey, fontSize: 13)),
          ],
        ),
      ),
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
                    child:
                        Icon(Icons.circle, size: 6, color: _kPrimaryGreenDark),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                      child: Text(t,
                          style: const TextStyle(
                              fontSize: 12,
                              height: 1.5,
                              color: Colors.black87))),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
