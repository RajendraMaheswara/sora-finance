import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../models/visitor_forecast_model.dart';
import '../../models/sales_forecast_model.dart';
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

// ==========================================
// HELPER DATA CLASSES
// ==========================================
class _CriticalItem {
  final String name;
  final int days;
  _CriticalItem({required this.name, required this.days});
}

class _StockCardData {
  final List<_CriticalItem> items;
  _StockCardData({required this.items});

  int get criticalCount => items.where((i) => i.days <= 3).length;

  static Future<_StockCardData> load(ApiService api) async {
    try {
      final results = await Future.wait([
        api.fetchData('forecast-results'),
        api.fetchData('ingredient-stock-histories'),
        api.fetchData('food-ingredients'),
      ]);
      return _StockCardData._from(results[0], results[1], results[2]);
    } catch (_) {
      return _StockCardData(items: []);
    }
  }

  factory _StockCardData._from(
    List<dynamic> rawResults,
    List<dynamic> rawHistories,
    List<dynamic> rawIngredients,
  ) {
    // Ingredient name map
    final nameMap = <String, String>{};
    for (final r in rawIngredients) {
      final m = r as Map;
      final id = (m['id'] as String?) ?? '';
      if (id.isNotEmpty) nameMap[id] = (m['name'] as String?) ?? id;
    }

    // Current stock per ingredient (most recent entry)
    final stockMap = <String, double>{};
    final histByItem = <String, List<Map<String, dynamic>>>{};
    for (final h in rawHistories) {
      final m = Map<String, dynamic>.from(h as Map);
      final id = (m['m_food_ingredient_id'] as String?) ?? '';
      if (id.isEmpty) continue;
      histByItem.putIfAbsent(id, () => []).add(m);
    }
    for (final entry in histByItem.entries) {
      entry.value.sort((a, b) =>
          ((b['date'] as String?) ?? '').compareTo((a['date'] as String?) ?? ''));
      stockMap[entry.key] =
          (entry.value.first['current_stock'] as num?)?.toDouble() ?? 0.0;
    }

    // Average daily usage per item from forecast_results
    final usageMap = <String, List<double>>{};
    for (final r in rawResults) {
      final m = r as Map;
      final id = (m['item_id'] as String?) ?? '';
      if (id.isEmpty) continue;
      final v = (m['predicted_value'] as num?)?.toDouble() ?? 0.0;
      usageMap.putIfAbsent(id, () => []).add(v);
    }

    // Calculate days until depletion
    final criticals = <_CriticalItem>[];
    for (final entry in usageMap.entries) {
      final id = entry.key;
      final usages = entry.value;
      if (usages.isEmpty) continue;
      final avg = usages.fold<double>(0, (s, v) => s + v) / usages.length;
      if (avg <= 0) continue;
      // Skip item yang namanya belum ter-resolve (UUID mentah)
      final name = nameMap[id];
      if (name == null) continue;

      final stock = stockMap[id] ?? 0.0;
      final days = stock <= 0 ? 0 : (stock / avg).ceil();
      if (days <= 7) {
        criticals.add(_CriticalItem(name: name, days: days));
      }
    }
    criticals.sort((a, b) => a.days.compareTo(b.days));

    return _StockCardData(items: criticals.take(5).toList());
  }
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

  late Future<List<dynamic>> _predictionsFuture;
  late Future<SalesForecastModel> _salesModelFuture;
  late Future<_StockCardData> _stockFuture;

  Future<SalesForecastModel> _loadSalesModel() =>
      SalesForecastModel.loadFromApi(_api.fetchData);

  @override
  void initState() {
    super.initState();
    _predictionsFuture = _api.fetchData('forecast-predictions');
    _salesModelFuture = _loadSalesModel();
    _stockFuture = _StockCardData.load(_api);
    _loadUser();
  }

  void _refresh() {
    setState(() {
      _predictionsFuture = _api.fetchData('forecast-predictions');
      _salesModelFuture = _loadSalesModel();
      _stockFuture = _StockCardData.load(_api);
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _HeaderWidget(onRefresh: _refresh),
                  const SizedBox(height: 28),
                  _PredictionRow(
                    predictionsFuture: _predictionsFuture,
                    salesModelFuture: _salesModelFuture,
                    stockFuture: _stockFuture,
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
                Text('Ringkasan Penjualan',
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
  final Future<List<dynamic>> predictionsFuture;
  final Future<SalesForecastModel> salesModelFuture;
  final Future<_StockCardData> stockFuture;

  const _PredictionRow({
    required this.predictionsFuture,
    required this.salesModelFuture,
    required this.stockFuture,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SalesForecastPage()),
            ),
            child: _SalesMiniCard(future: salesModelFuture),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                  builder: (_) =>
                      const VisitorForecastPage(storeId: _kStoreId)),
            ),
            child: _VisitorMiniCard(future: predictionsFuture),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const StockForecastPage()),
            ),
            child: _StockMiniCard(future: stockFuture),
          ),
        ),
      ],
    );
  }
}

// ==========================================
// CARD 1: PREDIKSI PENJUALAN
// Line chart hijau dengan area fill
// ==========================================
class _SalesMiniCard extends StatelessWidget {
  final Future<SalesForecastModel> future;
  const _SalesMiniCard({required this.future});

  @override
  Widget build(BuildContext context) {
    return _CardShell(
      child: FutureBuilder<SalesForecastModel>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const _CardLoading(title: 'Prediksi Penjualan (Minggu Depan)');
          }
          if (snap.hasError) {
            return _CardError(
                title: 'Prediksi Penjualan (Minggu Depan)',
                message: '${snap.error}');
          }
          final data = snap.data!;
          final pct = data.weeklyChangePercent;
          final pctText =
              '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%';
          final isUp = pct >= 0;
          // Baseline: estimasi "minggu ini" = avg30Days * 7
          final baseline = data.avg30Days * 7;
          final vals = data.weeklyForecast.map((p) => p.value).toList();

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Prediksi Penjualan (Minggu Depan)',
                  style: TextStyle(
                      color: Colors.grey,
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Flexible(
                    child: Text(
                      data.formattedTotal7,
                      style: const TextStyle(
                          fontSize: 22, fontWeight: FontWeight.bold),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  _Badge(
                    text: pctText,
                    bg: isUp
                        ? const Color(0xFFE8F5E9)
                        : const Color(0xFFFFEBEE),
                    fg: isUp ? Colors.green : Colors.red,
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'vs. Penjualan minggu ini (${SalesForecastModel.formatRupiah(baseline)})',
                style: const TextStyle(color: Colors.grey, fontSize: 11),
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 16),
              SizedBox(height: 60, child: _SalesLineChart(values: vals)),
            ],
          );
        },
      ),
    );
  }
}

class _SalesLineChart extends StatelessWidget {
  final List<double> values;
  const _SalesLineChart({required this.values});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();
    final maxY = values.reduce((a, b) => a > b ? a : b) * 1.2;
    final spots =
        List.generate(values.length, (i) => FlSpot(i.toDouble(), values[i]));

    return LineChart(LineChartData(
      minX: 0,
      maxX: (values.length - 1).toDouble(),
      minY: 0,
      maxY: maxY,
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      lineTouchData: const LineTouchData(enabled: false),
      lineBarsData: [
        LineChartBarData(
          spots: spots,
          isCurved: true,
          curveSmoothness: 0.35,
          color: _kLineGreen,
          barWidth: 2,
          dotData: const FlDotData(show: false),
          belowBarData: BarAreaData(
            show: true,
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                _kLineGreen.withValues(alpha: 0.28),
                _kLineGreen.withValues(alpha: 0.02),
              ],
            ),
          ),
        ),
      ],
    ));
  }
}

// ==========================================
// CARD 2: PREDIKSI PENGUNJUNG
// Bar chart dengan highlight bar tertinggi
// ==========================================
class _VisitorMiniCard extends StatelessWidget {
  final Future<List<dynamic>> future;
  const _VisitorMiniCard({required this.future});

  @override
  Widget build(BuildContext context) {
    return _CardShell(
      child: FutureBuilder<List<dynamic>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const _CardLoading(
                title: 'Prediksi Pengunjung (Minggu Depan)');
          }
          if (snap.hasError) {
            return _CardError(
                title: 'Prediksi Pengunjung (Minggu Depan)',
                message: '${snap.error}');
          }
          final data = VisitorForecastModel.fromPredictionList(snap.data!);
          final pct = data.weeklyChangePercent;
          final pctText =
              '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%';
          final isUp = pct >= 0;
          final today =
              data.weeklyForecast.isNotEmpty
                  ? data.weeklyForecast.first.predictedVisitors
                  : 0;
          final vals = data.weeklyForecast
              .map((p) => p.predictedVisitors.toDouble())
              .toList();
          final maxVal =
              vals.isEmpty ? 1.0 : vals.reduce((a, b) => a > b ? a : b);

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Prediksi Pengunjung (Minggu Depan)',
                  style: TextStyle(
                      color: Colors.grey,
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    '${_fmt(data.totalNext7Days)} Orang',
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(width: 8),
                  _Badge(
                    text: pctText,
                    bg: isUp
                        ? const Color(0xFFE8F5E9)
                        : const Color(0xFFFFEBEE),
                    fg: isUp ? Colors.green : Colors.red,
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text('Pengunjung hari ini: ${_fmt(today)} Orang',
                  style:
                      const TextStyle(color: Colors.grey, fontSize: 11)),
              const SizedBox(height: 16),
              SizedBox(
                  height: 60,
                  child: _VisitorBarChart(values: vals, maxVal: maxVal)),
            ],
          );
        },
      ),
    );
  }

  /// Format angka dengan titik ribuan gaya Indonesia: 1240 → "1.240"
  static String _fmt(int n) {
    if (n < 1000) return n.toString();
    final s = n.toString();
    final buf = StringBuffer();
    for (var i = 0; i < s.length; i++) {
      if (i > 0 && (s.length - i) % 3 == 0) buf.write('.');
      buf.write(s[i]);
    }
    return buf.toString();
  }
}

class _VisitorBarChart extends StatelessWidget {
  final List<double> values;
  final double maxVal;
  const _VisitorBarChart({required this.values, required this.maxVal});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();

    int maxIdx = 0;
    for (var i = 0; i < values.length; i++) {
      if (values[i] > values[maxIdx]) maxIdx = i;
    }

    return BarChart(BarChartData(
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      alignment: BarChartAlignment.spaceEvenly,
      maxY: (maxVal * 1.15).clamp(1, double.infinity),
      barTouchData: const BarTouchData(enabled: false),
      barGroups: List.generate(values.length, (i) {
        return BarChartGroupData(x: i, barRods: [
          BarChartRodData(
            toY: values[i],
            color: i == maxIdx
                ? const Color(0xFF1E88E5)
                : Colors.blue.shade100,
            width: 18,
            borderRadius:
                const BorderRadius.vertical(top: Radius.circular(4)),
          ),
        ]);
      }),
    ));
  }
}

// ==========================================
// CARD 3: PREDIKSI STOK (KRITIS)
// Daftar item kritis dengan countdown hari
// ==========================================
class _StockMiniCard extends StatelessWidget {
  final Future<_StockCardData> future;
  const _StockMiniCard({required this.future});

  @override
  Widget build(BuildContext context) {
    return _CardShell(
      child: FutureBuilder<_StockCardData>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const _CardLoading(title: 'Prediksi Stok (Kritis)');
          }
          if (snap.hasError) {
            return _CardError(
                title: 'Prediksi Stok (Kritis)',
                message: '${snap.error}');
          }

          final stock = snap.data!;
          final count = stock.items.length;
          final hasCritical = count > 0;

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Flexible(
                    child: Text('Prediksi Stok (Kritis)',
                        style: TextStyle(
                            color: Colors.grey,
                            fontSize: 13,
                            fontWeight: FontWeight.w600)),
                  ),
                  if (hasCritical)
                    _Badge(
                      text: 'Warning',
                      bg: const Color(0xFFFFEBEE),
                      fg: Colors.red,
                    ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                hasCritical ? '$count Item' : 'Aman',
                style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: hasCritical ? Colors.black87 : Colors.green),
              ),
              const SizedBox(height: 4),
              Text(
                hasCritical
                    ? 'Diprediksi habis dalam < ${stock.items.last.days} hari'
                    : 'Semua stok dalam kondisi aman',
                style: const TextStyle(color: Colors.grey, fontSize: 11),
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 14),
              if (hasCritical)
                ...stock.items.take(3).map((item) => _StockItemRow(item: item))
              else
                Row(
                  children: [
                    Icon(Icons.check_circle_outline,
                        color: Colors.green[400], size: 18),
                    const SizedBox(width: 6),
                    const Text('Tidak ada item kritis',
                        style: TextStyle(color: Colors.grey, fontSize: 12)),
                  ],
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StockItemRow extends StatelessWidget {
  final _CriticalItem item;
  const _StockItemRow({required this.item});

  @override
  Widget build(BuildContext context) {
    final isUrgent = item.days <= 1;
    final badgeBg = isUrgent
        ? const Color(0xFFFFEBEE)
        : const Color(0xFFFFF3E0);
    final badgeFg = isUrgent ? Colors.red : Colors.orange;
    final label = item.days <= 0 ? 'Habis' : 'Habis ${item.days} Hari';

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Flexible(
            child: Text(
              item.name,
              style: const TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
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
          style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.bold, color: fg)),
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
                    style:
                        const TextStyle(color: Colors.red, fontSize: 12))),
          ],
        ),
      ],
    );
  }
}
