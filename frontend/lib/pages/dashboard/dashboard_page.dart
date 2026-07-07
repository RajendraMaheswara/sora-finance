import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/visitor_forecast_model.dart';
import '../../models/sales_forecast_model.dart';
import '../../models/forecast_series_model.dart';
import '../visitor_forecast/visitor_forecast_page.dart';
import '../sales_forecast/sales_forecast_page.dart';
import '../stock_forecast/stock_forecast_page.dart';
import '../../core/services/auth_service.dart';

// ==========================================
// KONFIGURASI
// ==========================================
const String _kStoreId = 'b4e2f559-9615-4263-84fe-9ee97780748f';
const Color _kPrimaryGreenDark = Color(0xFF24CC14);
const Color _kLineGreen = Color(0xFF43A047);
const Color _kVisitorBlue = Color(0xFF1E88E5);
const Color _kHistGrey = Color(0xFF94A3B8);

// ==========================================
// HELPER DATA CLASSES
// ==========================================
const int _kNoDepletion = 99999;

class _StockItem {
  final String name;
  final int days; // estimasi hari sampai habis (kecil = paling mendesak)
  final bool depletes; // true bila habis dalam horizon forecast
  _StockItem({required this.name, required this.days, required this.depletes});
}

class _StockCardData {
  final List<_StockItem> items;
  final int monitoredCount;
  _StockCardData({required this.items, required this.monitoredCount});

  List<_StockItem> get nearest =>
      items.where((i) => i.days < _kNoDepletion).take(3).toList();

  _StockItem? get soonest =>
      (items.isNotEmpty && items.first.days < _kNoDepletion)
          ? items.first
          : null;

  int get criticalCount =>
      items.where((i) => i.depletes && i.days <= 3).length;

  factory _StockCardData.from(
    List<dynamic> rawResults,
    List<dynamic> rawHistories,
    List<dynamic> rawIngredients,
  ) {
    final nameMap = <String, String>{};
    for (final r in rawIngredients) {
      if (r is! Map) continue;
      final id = (r['id'] as String?) ?? '';
      if (id.isNotEmpty) nameMap[id] = (r['name'] as String?) ?? id;
    }

    final stockMap = <String, double>{};
    final histByItem = <String, List<Map<String, dynamic>>>{};
    for (final h in rawHistories) {
      if (h is! Map) continue;
      final m = Map<String, dynamic>.from(h);
      final id = (m['m_food_ingredient_id'] as String?) ?? '';
      if (id.isEmpty) continue;
      histByItem.putIfAbsent(id, () => []).add(m);
    }
    for (final entry in histByItem.entries) {
      entry.value.sort((a, b) => ((b['date'] as String?) ?? '')
          .compareTo((a['date'] as String?) ?? ''));
      stockMap[entry.key] =
          (entry.value.first['current_stock'] as num?)?.toDouble() ?? 0.0;
    }

    final rowsByItem = <String, List<Map<String, dynamic>>>{};
    for (final r in rawResults) {
      if (r is! Map) continue;
      final m = Map<String, dynamic>.from(r);
      final id = (m['item_id'] as String?) ?? '';
      if (id.isEmpty) continue;
      rowsByItem.putIfAbsent(id, () => []).add(m);
    }

    final out = <_StockItem>[];
    var monitored = 0;
    for (final entry in rowsByItem.entries) {
      final name = nameMap[entry.key];
      if (name == null) continue;

      final fr = ForecastResults.fromRows(entry.value);
      final series = fr.daily.isNotEmpty
          ? fr.daily
          : (fr.weekly.isNotEmpty ? fr.weekly : fr.monthly);
      if (series.isEmpty) continue;

      monitored++;
      final stock = stockMap[entry.key] ?? 0.0;

      double remaining = stock;
      int? depDay;
      for (var i = 0; i < series.length; i++) {
        remaining -= series[i].value;
        if (remaining <= 0) {
          depDay = i + 1;
          break;
        }
      }

      int days;
      bool depletes;
      if (depDay != null) {
        days = depDay;
        depletes = true;
      } else {
        final avg =
            series.fold<double>(0, (s, p) => s + p.value) / series.length;
        days = avg > 0 ? (stock / avg).ceil() : _kNoDepletion;
        depletes = false;
      }
      out.add(_StockItem(name: name, days: days, depletes: depletes));
    }

    out.sort((a, b) => a.days.compareTo(b.days));
    return _StockCardData(items: out, monitoredCount: monitored);
  }
}

/// Semua data yang dibutuhkan dasbor, dimuat sekali.
class _DashboardData {
  final SalesForecastModel sales;
  final VisitorForecastModel visitor;
  final _StockCardData stock;
  final List<double> salesHistory; // omzet harian terakhir
  final List<double> visitorHistory; // transaksi harian terakhir
  const _DashboardData({
    required this.sales,
    required this.visitor,
    required this.stock,
    required this.salesHistory,
    required this.visitorHistory,
  });
}

/// Nilai harian terakhir dari sales_daily_summaries untuk sparkline.
List<double> _recentDaily(List<dynamic> summaries, String key, int n) {
  final rows = summaries
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .where((e) => ((e['date'] as String?) ?? '').isNotEmpty)
      .toList()
    ..sort((a, b) => (a['date'] as String).compareTo(b['date'] as String));
  final recent = rows.length > n ? rows.sublist(rows.length - n) : rows;
  return recent.map((r) => (r[key] as num?)?.toDouble() ?? 0.0).toList();
}

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

/// % perubahan rata-rata prediksi (7 hari) vs rata-rata historis (7 hari).
double _forecastVsHistory(List<double> history, List<double> forecast) {
  if (history.isEmpty || forecast.isEmpty) return 0;
  final h = history.length >= 7 ? history.sublist(history.length - 7) : history;
  final f = forecast.length >= 7 ? forecast.sublist(0, 7) : forecast;
  final ha = h.fold<double>(0, (s, v) => s + v) / h.length;
  final fa = f.fold<double>(0, (s, v) => s + v) / f.length;
  if (ha == 0) return 0;
  return (fa - ha) / ha * 100;
}

// ==========================================
// SCREEN
// ==========================================
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _api = ApiService();
  late Future<_DashboardData> _future;

  Future<_DashboardData> _load() async {
    final maps = await Future.wait([
      _api.fetchMap('forecast/latest?forecast_type=sales&horizon_label=daily'),
      _api.fetchMap('forecast/visitors/latest?horizon_label=daily'),
      _api.fetchMap('forecast/latest?forecast_type=inventory&horizon_label=daily'),
    ]);
    final r = await Future.wait([
      _api.fetchData('sales-daily-summaries'),
      _api.fetchData('ingredient-stock-histories'),
      _api.fetchData('food-ingredients'),
    ]);
    final summaries = r[0];
    _StockCardData stock;
    try {
      stock = _StockCardData.from(latestResultsRows(maps[2]), r[1], r[2]);
    } catch (_) {
      stock = _StockCardData(items: const [], monitoredCount: 0);
    }
    return _DashboardData(
      sales: SalesForecastModel.fromLatestResponses(daily: maps[0]),
      visitor: VisitorForecastModel.fromLatestResponses(daily: maps[1]),
      stock: stock,
      salesHistory: _recentDaily(summaries, 'total_omzet', 10),
      visitorHistory: _recentDaily(summaries, 'total_transaction', 10),
    );
  }

  @override
  void initState() {
    super.initState();
    _future = _load();
    _loadUser();
  }

  void _refresh() => setState(() => _future = _load());

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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _HeaderWidget(onRefresh: _refresh),
                  const SizedBox(height: 28),
                  FutureBuilder<_DashboardData>(
                    future: _future,
                    builder: (context, snap) {
                      if (snap.connectionState == ConnectionState.waiting) {
                        return const _StatusRow(loading: true);
                      }
                      if (snap.hasError) {
                        return _StatusRow(message: '${snap.error}');
                      }
                      return _PredictionRow(data: snap.data!);
                    },
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

// ==========================================
// HEADER
// ==========================================
class _HeaderWidget extends StatelessWidget {
  final VoidCallback onRefresh;
  const _HeaderWidget({required this.onRefresh});

  String _formatNowOpened() {
    final now = DateTime.now();
    final isPm = now.hour >= 12;
    final h = now.hour % 12 == 0 ? 12 : now.hour % 12;
    final mm = now.minute.toString().padLeft(2, '0');
    return 'Opened $h:$mm ${isPm ? 'pm' : 'am'}';
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
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Dasbor',
                    style: TextStyle(color: Colors.grey, fontSize: 13)),
                SizedBox(height: 6),
                Text('Ringkasan Prediksi',
                    style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Colors.black87)),
              ],
            ),
            Row(
              children: [
                IconButton(
                    onPressed: onRefresh,
                    icon: const Icon(Icons.refresh),
                    tooltip: 'Refresh data',
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
// PREDICTION ROW
// ==========================================
class _PredictionRow extends StatelessWidget {
  final _DashboardData data;
  const _PredictionRow({required this.data});

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: _Tappable(
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => const SalesForecastPage())),
              child: _SalesMiniCard(
                  model: data.sales, history: data.salesHistory),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: _Tappable(
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) =>
                      const VisitorForecastPage(storeId: _kStoreId))),
              child: _VisitorMiniCard(
                  model: data.visitor, history: data.visitorHistory),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: _Tappable(
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => const StockForecastPage())),
              child: _StockMiniCard(stock: data.stock),
            ),
          ),
        ],
      ),
    );
  }
}

class _Tappable extends StatelessWidget {
  final Widget child;
  final VoidCallback onTap;
  const _Tappable({required this.child, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: child,
    );
  }
}

// ==========================================
// CARD 1: PREDIKSI PENJUALAN
// ==========================================
class _SalesMiniCard extends StatelessWidget {
  final SalesForecastModel model;
  final List<double> history;
  const _SalesMiniCard({required this.model, required this.history});

  @override
  Widget build(BuildContext context) {
    const title = 'Prediksi Penjualan';
    if (model.dailyForecast.isEmpty &&
        model.weeklyForecast.isEmpty &&
        model.monthlyForecast.isEmpty) {
      return const _CardShell(
        child: _CardEmpty(
            title: title, message: 'Belum ada data prediksi penjualan'),
      );
    }

    final forecast = (model.dailyForecast.isNotEmpty
            ? model.dailyForecast.take(7)
            : model.weeklyForecast)
        .map((p) => p.value)
        .toList();
    final pct = _forecastVsHistory(history, forecast);

    return _CardShell(
      child: _MiniCardBody(
        title: title,
        value: model.formattedTotal7,
        pct: pct,
        subtitle: 'Total 7 hari ke depan • vs 7 hari lalu',
        chart: _MiniSparkline(
            history: history, forecast: forecast, color: _kLineGreen),
      ),
    );
  }
}

// ==========================================
// CARD 2: PREDIKSI PENGUNJUNG
// ==========================================
class _VisitorMiniCard extends StatelessWidget {
  final VisitorForecastModel model;
  final List<double> history;
  const _VisitorMiniCard({required this.model, required this.history});

  @override
  Widget build(BuildContext context) {
    const title = 'Prediksi Pengunjung';
    if (model.dailyForecast.isEmpty &&
        model.weeklyForecast.isEmpty &&
        model.monthlyForecast.isEmpty) {
      return const _CardShell(
        child: _CardEmpty(
            title: title, message: 'Belum ada data prediksi pengunjung'),
      );
    }

    final src = model.dailyForecast.isNotEmpty
        ? model.dailyForecast
        : model.weeklyForecast;
    final forecast =
        src.take(7).map((p) => p.predictedVisitors.toDouble()).toList();
    final today = src.isNotEmpty ? src.first.predictedVisitors : 0;
    final pct = _forecastVsHistory(history, forecast);

    return _CardShell(
      child: _MiniCardBody(
        title: title,
        value: '${_thousands(model.totalNext7Days)} Orang',
        pct: pct,
        subtitle: 'Total 7 hari • hari ini ${_thousands(today)} orang',
        chart: _MiniSparkline(
            history: history, forecast: forecast, color: _kVisitorBlue),
      ),
    );
  }
}

/// Isi kartu mini yang seragam: judul + badge tren, nilai besar, subtitle, chart.
class _MiniCardBody extends StatelessWidget {
  final String title;
  final String value;
  final double pct;
  final String subtitle;
  final Widget chart;
  const _MiniCardBody({
    required this.title,
    required this.value,
    required this.pct,
    required this.subtitle,
    required this.chart,
  });

  @override
  Widget build(BuildContext context) {
    final up = pct >= 0;
    final pctText = '${up ? '+' : ''}${pct.toStringAsFixed(1)}%';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                color: Colors.grey,
                fontSize: 13,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Flexible(
              child: Text(value,
                  style: const TextStyle(
                      fontSize: 22, fontWeight: FontWeight.bold),
                  overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 8),
            _Badge(
              text: pctText,
              bg: up ? const Color(0xFFE8F5E9) : const Color(0xFFFFEBEE),
              fg: up ? Colors.green : Colors.red,
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(subtitle,
            style: const TextStyle(color: Colors.grey, fontSize: 11),
            overflow: TextOverflow.ellipsis),
        const SizedBox(height: 16),
        SizedBox(height: 64, child: chart),
      ],
    );
  }
}

/// Sparkline: data real (solid abu) menyambung ke prediksi (warna + area).
class _MiniSparkline extends StatelessWidget {
  final List<double> history;
  final List<double> forecast;
  final Color color;
  const _MiniSparkline({
    required this.history,
    required this.forecast,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final all = [...history, ...forecast];
    if (all.length < 2) return const SizedBox.shrink();

    final maxV = all.reduce((a, b) => a > b ? a : b);
    final minV = all.reduce((a, b) => a < b ? a : b);
    final pad = (maxV - minV).abs() * 0.15 + 1;
    final minY = (minV - pad).clamp(0, double.infinity).toDouble();
    final maxY = maxV + pad;
    final histN = history.length;
    final n = all.length;

    final histSpots =
        List.generate(histN, (i) => FlSpot(i.toDouble(), history[i]));
    final fcSpots = <FlSpot>[];
    if (histN > 0) fcSpots.add(FlSpot((histN - 1).toDouble(), history.last));
    for (var j = 0; j < forecast.length; j++) {
      fcSpots.add(FlSpot((histN + j).toDouble(), forecast[j]));
    }

    return LineChart(LineChartData(
      minX: 0,
      maxX: (n - 1).toDouble(),
      minY: minY,
      maxY: maxY,
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      lineTouchData: const LineTouchData(enabled: false),
      lineBarsData: [
        // Prediksi (warna + area gradien)
        LineChartBarData(
          spots: fcSpots,
          isCurved: true,
          curveSmoothness: 0.3,
          color: color,
          barWidth: 2.2,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                color.withValues(alpha: 0.22),
                color.withValues(alpha: 0.02),
              ],
            ),
          ),
        ),
        // Data real (solid abu)
        LineChartBarData(
          spots: histSpots,
          isCurved: true,
          curveSmoothness: 0.3,
          color: _kHistGrey,
          barWidth: 2,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(show: false),
        ),
      ],
    ));
  }
}

// ==========================================
// CARD 3: PREDIKSI STOK
// ==========================================
class _StockMiniCard extends StatelessWidget {
  final _StockCardData stock;
  const _StockMiniCard({required this.stock});

  @override
  Widget build(BuildContext context) {
    final soonest = stock.soonest;
    final critical = stock.criticalCount;

    final Widget badge;
    if (critical > 0) {
      badge = _Badge(
          text: '$critical Kritis',
          bg: const Color(0xFFFFEBEE),
          fg: Colors.red);
    } else if (soonest != null) {
      badge = _Badge(
          text: 'Pantau', bg: const Color(0xFFFFF3E0), fg: Colors.orange);
    } else {
      badge = _Badge(
          text: 'Aman', bg: const Color(0xFFE8F5E9), fg: Colors.green);
    }

    return _CardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Flexible(
                child: Text('Prediksi Stok',
                    style: TextStyle(
                        color: Colors.grey,
                        fontSize: 13,
                        fontWeight: FontWeight.w600)),
              ),
              badge,
            ],
          ),
          const SizedBox(height: 10),
          Text(
            soonest != null ? '${soonest.days} Hari' : 'Aman',
            style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: soonest != null && soonest.days <= 3
                    ? Colors.red
                    : (soonest != null ? Colors.black87 : Colors.green)),
          ),
          const SizedBox(height: 4),
          Text(
            soonest != null
                ? '${soonest.name} paling cepat habis'
                : (stock.monitoredCount > 0
                    ? 'Semua stok dalam kondisi aman'
                    : 'Belum ada data prediksi stok'),
            style: const TextStyle(color: Colors.grey, fontSize: 11),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 16),
          if (stock.nearest.isNotEmpty)
            ...stock.nearest.map((item) => _StockItemRow(item: item))
          else
            Row(
              children: [
                Icon(Icons.check_circle_outline,
                    color: Colors.green[400], size: 18),
                const SizedBox(width: 6),
                const Text('Tidak ada item mendekati habis',
                    style: TextStyle(color: Colors.grey, fontSize: 12)),
              ],
            ),
          if (stock.monitoredCount > 0) ...[
            const SizedBox(height: 6),
            Text('${stock.monitoredCount} item dipantau',
                style: TextStyle(color: Colors.grey[500], fontSize: 11)),
          ],
        ],
      ),
    );
  }
}

class _StockItemRow extends StatelessWidget {
  final _StockItem item;
  const _StockItemRow({required this.item});

  @override
  Widget build(BuildContext context) {
    final Color badgeBg, badgeFg;
    if (item.days <= 3) {
      badgeBg = const Color(0xFFFFEBEE);
      badgeFg = Colors.red;
    } else if (item.days <= 7) {
      badgeBg = const Color(0xFFFFF3E0);
      badgeFg = Colors.orange;
    } else {
      badgeBg = const Color(0xFFEEF1F4);
      badgeFg = Colors.blueGrey;
    }

    final String label;
    if (item.days <= 0) {
      label = 'Habis';
    } else if (item.depletes) {
      label = 'Habis ${item.days} Hari';
    } else {
      label = '± ${item.days} Hari';
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Flexible(
            child: Text(item.name,
                style:
                    const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                overflow: TextOverflow.ellipsis),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
                color: badgeBg, borderRadius: BorderRadius.circular(6)),
            child: Text(label,
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: badgeFg)),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// SHARED WIDGETS
// ==========================================
class _StatusRow extends StatelessWidget {
  final bool loading;
  final String? message;
  const _StatusRow({this.loading = false, this.message});

  @override
  Widget build(BuildContext context) {
    final titles = ['Prediksi Penjualan', 'Prediksi Pengunjung', 'Prediksi Stok'];
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var i = 0; i < 3; i++) ...[
            if (i > 0) const SizedBox(width: 16),
            Expanded(
              child: _CardShell(
                child: loading
                    ? _CardLoading(title: titles[i])
                    : _CardError(title: titles[i], message: message ?? ''),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String text;
  final Color bg;
  final Color fg;
  const _Badge({required this.text, required this.bg, required this.fg});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration:
          BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Text(text,
          style:
              TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: fg)),
    );
  }
}

class _CardShell extends StatelessWidget {
  final Widget child;
  const _CardShell({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
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

class _CardLoading extends StatelessWidget {
  final String title;
  const _CardLoading({required this.title});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                color: Colors.grey,
                fontSize: 13,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 32),
        const Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
                strokeWidth: 2.5, color: _kPrimaryGreenDark),
          ),
        ),
        const SizedBox(height: 32),
      ],
    );
  }
}

class _CardError extends StatelessWidget {
  final String title;
  final String message;
  const _CardError({required this.title, required this.message});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                color: Colors.grey,
                fontSize: 13,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 18),
            const SizedBox(width: 8),
            Expanded(
                child: Text('Gagal memuat.\n$message',
                    style: const TextStyle(color: Colors.red, fontSize: 12))),
          ],
        ),
      ],
    );
  }
}

class _CardEmpty extends StatelessWidget {
  final String title;
  final String message;
  const _CardEmpty({required this.title, required this.message});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: const TextStyle(
                color: Colors.grey,
                fontSize: 13,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 24),
        Center(
          child: Column(
            children: [
              Icon(Icons.bar_chart, size: 34, color: Colors.grey[300]),
              const SizedBox(height: 8),
              Text(message,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ],
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }
}
