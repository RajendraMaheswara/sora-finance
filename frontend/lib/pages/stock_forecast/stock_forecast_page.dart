import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:sora2/widgets/sidebar.dart';

import '../../core/services/api_service.dart';
import '../../core/services/auth_service.dart';
import '../../models/forecast_series_model.dart';
import '../../widgets/forecast_chart.dart';

// ==========================================
// COLORS
// ==========================================
const Color _kGreen = Color(0xFF8CE600);
const Color _kGreenDark = Color(0xFF24CC14);
const Color _kLineGreen = Color(0xFF43A047);
const Color _kLineRed = Color(0xFFE53935);

// ==========================================
// DATA MODELS (internal)
// ==========================================
enum _StockStatus { normal, warning, critical, outOfStock }

extension _StockStatusLabel on _StockStatus {
  String get label {
    switch (this) {
      case _StockStatus.normal: return 'Normal';
      case _StockStatus.warning: return 'Warning';
      case _StockStatus.critical: return 'Kritis';
      case _StockStatus.outOfStock: return 'Out of Stock';
    }
  }

  Color get bgColor {
    switch (this) {
      case _StockStatus.normal: return const Color(0xFFE8F5E9);
      case _StockStatus.warning: return const Color(0xFFFFF3E0);
      case _StockStatus.critical: return const Color(0xFFFFEBEE);
      case _StockStatus.outOfStock: return const Color(0xFFB71C1C);
    }
  }

  Color get fgColor {
    switch (this) {
      case _StockStatus.normal: return Colors.green;
      case _StockStatus.warning: return Colors.orange;
      case _StockStatus.critical: return Colors.red;
      case _StockStatus.outOfStock: return Colors.white;
    }
  }
}

class _DayForecast {
  final String date;
  final double predictedUsage;
  final double? lower;
  final double? upper;
  final double estimatedRemaining;
  final _StockStatus status;
  final int? confidence;

  const _DayForecast({
    required this.date,
    required this.predictedUsage,
    required this.estimatedRemaining,
    required this.status,
    this.lower,
    this.upper,
    this.confidence,
  });
}

class _HistoryPoint {
  final String date;
  final double stock;
  const _HistoryPoint({required this.date, required this.stock});
}

class _ItemData {
  final String id;
  final String name;
  final double currentStock;
  final double stockLimit;
  final List<_HistoryPoint> history; // last N days actual stock
  final List<_DayForecast> forecasts;

  // confidence_level dari run native tiap granularitas (sesuai DB), supaya
  // "Tingkat Keyakinan" berubah sesuai tab (bukan selalu nilai run harian).
  final int? confDaily;
  final int? confWeekly;
  final int? confMonthly;

  const _ItemData({
    required this.id,
    required this.name,
    required this.currentStock,
    required this.stockLimit,
    required this.history,
    required this.forecasts,
    this.confDaily,
    this.confWeekly,
    this.confMonthly,
  });

  /// Tingkat keyakinan untuk periode tertentu (fallback ke harian bila run
  /// granularitas itu tidak ada).
  double confidenceFor(_Period p) {
    final v = switch (p) {
      _Period.daily => confDaily,
      _Period.weekly => confWeekly ?? confDaily,
      _Period.monthly => confMonthly ?? confDaily,
    };
    return (v ?? 80).toDouble();
  }

  bool get hasCi =>
      forecasts.any((f) => f.lower != null && f.upper != null);

  int get daysUntilDepletion {
    for (var i = 0; i < forecasts.length; i++) {
      if (forecasts[i].estimatedRemaining <= 0) return i + 1;
    }
    return -1; // not depleting within forecast horizon
  }

  _StockStatus get overallStatus {
    final d = daysUntilDepletion;
    if (d > 0 && d <= 2) return _StockStatus.outOfStock;
    if (d > 0 && d <= 4) return _StockStatus.critical;
    if (d > 0 && d <= 7) return _StockStatus.warning;
    return _StockStatus.normal;
  }
}

// ==========================================
// VIEW MODEL — fetches & combines all data
// ==========================================
class _ViewModel {
  final List<_ItemData> items;
  const _ViewModel({required this.items});

  static Future<_ViewModel> load(ApiService api) async {
    final results = await Future.wait([
      api.fetchData('forecast-results'),
      api.fetchData('ingredient-stock-histories'),
      api.fetchData('food-ingredients'),
    ]);

    final rawResults = results[0];
    final rawStockHistories = results[1];
    final rawIngredients = results[2];

    // Map ingredient id → name, stockLimit
    final ingredientNames = <String, String>{};
    final ingredientLimits = <String, double>{};
    for (final raw in rawIngredients) {
      final m = raw as Map;
      final id = m['id'] as String? ?? '';
      ingredientNames[id] = m['name'] as String? ?? id;
      ingredientLimits[id] = (m['stock_limit'] as num?)?.toDouble() ?? 0.0;
    }

    // Map ingredient id → latest current_stock + history
    final stockByItem = <String, List<Map<String, dynamic>>>{};
    for (final raw in rawStockHistories) {
      final m = Map<String, dynamic>.from(raw as Map);
      final itemId = m['m_food_ingredient_id'] as String? ?? '';
      if (itemId.isEmpty) continue;
      stockByItem.putIfAbsent(itemId, () => []).add(m);
    }

    // Sort stock histories by date descending
    for (final list in stockByItem.values) {
      list.sort((a, b) {
        final da = (a['date'] as String? ?? '');
        final db = (b['date'] as String? ?? '');
        return db.compareTo(da); // descending
      });
    }

    // Group forecast_results by item_id (ingredient). Sales/visitors rows
    // punya item_id null sehingga otomatis terabaikan di sini.
    final rowsByItem = <String, List<Map<String, dynamic>>>{};
    for (final raw in rawResults) {
      final m = Map<String, dynamic>.from(raw as Map);
      final itemId = m['item_id'] as String? ?? '';
      if (itemId.isEmpty) continue;
      rowsByItem.putIfAbsent(itemId, () => []).add(m);
    }

    // Build item data
    final items = <_ItemData>[];
    for (final entry in rowsByItem.entries) {
      final itemId = entry.key;

      // Tiap ingredient bisa punya run harian/mingguan/bulanan terpisah yang
      // semuanya masuk ke forecast_results. Untuk penipisan stok kita pakai
      // HANYA run harian (fallback ke mingguan/bulanan bila tidak ada) supaya
      // perhitungan sisa stok tidak tercampur antar granularitas.
      final fr = ForecastResults.fromRows(entry.value);
      final series = fr.daily.isNotEmpty
          ? fr.daily
          : (fr.weekly.isNotEmpty ? fr.weekly : fr.monthly);
      if (series.isEmpty) continue;

      final name = ingredientNames[itemId] ?? itemId;
      final stockLimit = ingredientLimits[itemId] ?? 0.0;

      // Current stock from latest stock history entry
      final histList = stockByItem[itemId] ?? [];
      final currentStock = histList.isNotEmpty
          ? (histList.first['current_stock'] as num?)?.toDouble() ?? 0.0
          : 0.0;

      // Historical stock points (last 7 entries, ascending order)
      final historyPoints = histList
          .take(7)
          .toList()
          .reversed
          .map((h) => _HistoryPoint(
                date: h['date'] as String? ?? '',
                stock: (h['current_stock'] as num?)?.toDouble() ?? 0.0,
              ))
          .toList();

      // Compute depletion forecast
      double remaining = currentStock;
      final forecasts = <_DayForecast>[];
      for (final p in series) {
        final usage = p.value;
        remaining -= usage;

        _StockStatus status;
        if (remaining <= 0) {
          status = _StockStatus.outOfStock;
        } else if (stockLimit > 0 && remaining < stockLimit * 0.15) {
          status = _StockStatus.critical;
        } else if (stockLimit > 0 && remaining < stockLimit * 0.35) {
          status = _StockStatus.warning;
        } else {
          status = _StockStatus.normal;
        }

        forecasts.add(_DayForecast(
          date: p.isoDate,
          predictedUsage: usage,
          estimatedRemaining: remaining,
          status: status,
          lower: p.lower,
          upper: p.upper,
          confidence: p.confidence,
        ));
      }

      // Sembunyikan item yang namanya belum ter-resolve (masih berupa UUID)
      if (name == itemId) continue;

      items.add(_ItemData(
        id: itemId,
        name: name,
        currentStock: currentStock,
        stockLimit: stockLimit,
        history: historyPoints,
        forecasts: forecasts,
        confDaily: _avgConfidence(fr.daily),
        confWeekly:
            fr.weekly.isNotEmpty ? _avgConfidence(fr.weekly) : null,
        confMonthly:
            fr.monthly.isNotEmpty ? _avgConfidence(fr.monthly) : null,
      ));
    }

    // Sort items: critical first
    items.sort((a, b) {
      final aStatus = a.overallStatus.index;
      final bStatus = b.overallStatus.index;
      return bStatus.compareTo(aStatus);
    });

    return _ViewModel(items: items);
  }
}

// ==========================================
// PAGE
// ==========================================
class StockForecastPage extends StatefulWidget {
  const StockForecastPage({super.key});

  @override
  State<StockForecastPage> createState() => _StockForecastPageState();
}

class _StockForecastPageState extends State<StockForecastPage> {
  final ApiService _api = ApiService();
  late Future<_ViewModel> _future;

  @override
  void initState() {
    super.initState();
    _future = _ViewModel.load(_api);
    _loadUser();
  }

  void _refresh() => setState(() => _future = _ViewModel.load(_api));

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
              child: FutureBuilder<_ViewModel>(
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
                      else if (snapshot.data!.items.isEmpty)
                        _EmptyPanel(onRetry: _refresh)
                      else
                        _StockSummaryGrid(vm: snapshot.data!),
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
                    Text('Prediksi Stok',
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
// LOADING / ERROR / EMPTY
// ==========================================
class _LoadingPanel extends StatelessWidget {
  const _LoadingPanel();

  @override
  Widget build(BuildContext context) => const SizedBox(
        height: 480,
        child: Center(child: CircularProgressIndicator(color: _kGreenDark)),
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
          Text('Gagal memuat data stok.\n$message',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Coba Lagi'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kGreen, foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}

class _EmptyPanel extends StatelessWidget {
  final VoidCallback onRetry;
  const _EmptyPanel({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(40),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Icon(Icons.inventory_2_outlined, size: 48, color: Colors.grey[400]),
          const SizedBox(height: 12),
          const Text('Belum ada data prediksi stok.',
              style: TextStyle(color: Colors.grey, fontSize: 15)),
          const SizedBox(height: 4),
          const Text(
              'Pastikan data tersimpan di tabel forecast_results.',
              style: TextStyle(color: Colors.grey, fontSize: 12)),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Refresh'),
            style: ElevatedButton.styleFrom(
                backgroundColor: _kGreen, foregroundColor: Colors.white),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// SUMMARY GRID — kotak ringkasan tiap bahan (dibuka saat klik "Prediksi Stok")
// ==========================================
class _StockSummaryGrid extends StatelessWidget {
  final _ViewModel vm;
  const _StockSummaryGrid({required this.vm});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
            '${vm.items.length} bahan dipantau • diurutkan dari yang paling '
            'mendesak',
            style: const TextStyle(color: Colors.grey, fontSize: 12)),
        const SizedBox(height: 16),
        Wrap(
          spacing: 16,
          runSpacing: 16,
          children: [
            for (final item in vm.items)
              SizedBox(
                width: 260,
                child: _StockSummaryCard(item: item),
              ),
          ],
        ),
      ],
    );
  }
}

class _StockSummaryCard extends StatelessWidget {
  final _ItemData item;
  const _StockSummaryCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final status = item.overallStatus;
    final days = item.daysUntilDepletion;
    final avgUsage = item.forecasts.isEmpty
        ? 0.0
        : item.forecasts.take(7).fold<double>(0, (s, f) => s + f.predictedUsage) /
            item.forecasts.take(7).length;

    return Container(
      padding: const EdgeInsets.all(18),
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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(item.name,
                    style: const TextStyle(
                        fontSize: 14, fontWeight: FontWeight.w700),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ),
              const SizedBox(width: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                    color: status.bgColor,
                    borderRadius: BorderRadius.circular(6)),
                child: Text(status.label,
                    style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: status.fgColor)),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            item.currentStock > 0
                ? '${item.currentStock.toStringAsFixed(1)} Kg'
                : 'N/A',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 2),
          const Text('Stok saat ini',
              style: TextStyle(color: Colors.grey, fontSize: 11)),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.schedule, size: 13, color: Colors.grey[500]),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  days > 0 ? 'Habis dalam $days hari' : 'Stok aman',
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: days > 0 && days <= 3
                          ? _kLineRed
                          : Colors.grey[700]),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text('Rata-rata pakai ${avgUsage.toStringAsFixed(1)} Kg/hari',
              style: const TextStyle(color: Colors.grey, fontSize: 11)),
          const SizedBox(height: 14),
          const Divider(height: 1),
          const SizedBox(height: 10),
          InkWell(
            onTap: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => _StockItemDetailPage(itemId: item.id))),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text('Detail',
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: _kGreenDark)),
                SizedBox(width: 4),
                Icon(Icons.arrow_forward_ios, size: 10, color: _kGreenDark),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// DETAIL PAGE — dibuka dari tombol "Detail" pada kotak ringkasan
// ==========================================
class _StockItemDetailPage extends StatefulWidget {
  final String itemId;
  const _StockItemDetailPage({required this.itemId});

  @override
  State<_StockItemDetailPage> createState() => _StockItemDetailPageState();
}

class _StockItemDetailPageState extends State<_StockItemDetailPage> {
  final ApiService _api = ApiService();
  late Future<_ViewModel> _future;

  @override
  void initState() {
    super.initState();
    _future = _ViewModel.load(_api);
    _loadUser();
  }

  void _refresh() => setState(() => _future = _ViewModel.load(_api));

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
              child: FutureBuilder<_ViewModel>(
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
                      else if (snapshot.data!.items.isEmpty)
                        _EmptyPanel(onRetry: _refresh)
                      else
                        _StockBody(
                            vm: snapshot.data!, initialItemId: widget.itemId),
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
// PERIOD
// ==========================================
enum _Period { daily, weekly, monthly }

extension on _Period {
  String get label {
    switch (this) {
      case _Period.daily: return 'Harian';
      case _Period.weekly: return 'Mingguan';
      case _Period.monthly: return 'Bulanan';
    }
  }
}

const _kStockMonths = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
  7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
};
const _kStockDayShort = {
  1: 'Sen', 2: 'Sel', 3: 'Rab', 4: 'Kam', 5: 'Jum', 6: 'Sab', 7: 'Min',
};
const _kStockDayFull = {
  1: 'Senin', 2: 'Selasa', 3: 'Rabu', 4: 'Kamis',
  5: 'Jumat', 6: 'Sabtu', 7: 'Minggu',
};

String _stockDateLabel(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${d.day} ${_kStockMonths[d.month]} ${d.year}';
}

/// Label tanggal dengan nama hari (untuk tab Harian).
String _stockDateLabelWithDay(String iso) {
  final d = DateTime.tryParse(iso);
  if (d == null) return iso;
  return '${_kStockDayFull[d.weekday]}, ${d.day} ${_kStockMonths[d.month]} '
      '${d.year}';
}

/// Rata-rata confidence_level (dibulatkan) dari sederet titik forecast.
int? _avgConfidence(List<ForecastPoint> pts) {
  final c = pts.where((p) => p.confidence != null).map((p) => p.confidence!);
  return c.isEmpty ? null : (c.reduce((a, b) => a + b) / c.length).round();
}

/// Agregasi forecast harian ke bucket (per minggu / per bulan). Sisa stok
/// diambil dari hari terakhir bucket (kondisi di akhir periode), pemakaian &
/// batas CI dijumlahkan, status mengikuti sisa di akhir bucket.
///
/// Bucket yang belum genap satu periode penuh (mis. sisa horizon < 7 hari
/// untuk mingguan, atau bulan yang cuma sebagian hari untuk bulanan) DIBUANG
/// supaya grafik/tabel tidak menampilkan bar yang tiba-tiba anjlok hanya
/// karena periode itu belum lengkap.
List<_DayForecast> _aggregateForecasts(
    List<_DayForecast> daily, _Period period) {
  if (period == _Period.daily || daily.isEmpty) return daily;

  final buckets = <List<_DayForecast>>[];
  if (period == _Period.weekly) {
    for (var i = 0; i + 7 <= daily.length; i += 7) {
      buckets.add(daily.sublist(i, i + 7));
    }
  } else {
    // Bulanan: kelompokkan per bulan kalender (YYYY-MM), hanya bulan penuh.
    final byMonth = <String, List<_DayForecast>>{};
    final order = <String>[];
    for (final f in daily) {
      final key = f.date.length >= 7 ? f.date.substring(0, 7) : f.date;
      if (!byMonth.containsKey(key)) order.add(key);
      byMonth.putIfAbsent(key, () => []).add(f);
    }
    for (final k in order) {
      final chunk = byMonth[k]!;
      if (chunk.length >= daysInMonth(k)) buckets.add(chunk);
    }
  }

  return buckets.map((b) {
    final usage = b.fold<double>(0, (s, f) => s + f.predictedUsage);
    final allLo = b.every((f) => f.lower != null);
    final allHi = b.every((f) => f.upper != null);
    final confs = b.where((f) => f.confidence != null).map((f) => f.confidence!);
    return _DayForecast(
      date: b.first.date,
      predictedUsage: usage,
      lower: allLo ? b.fold<double>(0, (s, f) => s + f.lower!) : null,
      upper: allHi ? b.fold<double>(0, (s, f) => s + f.upper!) : null,
      estimatedRemaining: b.last.estimatedRemaining,
      status: b.last.status,
      confidence: confs.isEmpty
          ? null
          : (confs.reduce((a, c) => a + c) / confs.length).round(),
    );
  }).toList();
}

// ==========================================
// BODY — manages selected item & period
// ==========================================
class _StockBody extends StatefulWidget {
  final _ViewModel vm;
  final String? initialItemId;
  const _StockBody({required this.vm, this.initialItemId});

  @override
  State<_StockBody> createState() => _StockBodyState();
}

class _StockBodyState extends State<_StockBody> {
  late int _selectedIdx;
  _Period _period = _Period.daily;

  @override
  void initState() {
    super.initState();
    final id = widget.initialItemId;
    final idx =
        id == null ? -1 : widget.vm.items.indexWhere((i) => i.id == id);
    _selectedIdx = idx >= 0 ? idx : 0;
  }

  _ItemData get _item => widget.vm.items[_selectedIdx];

  List<_DayForecast> get _periodForecasts {
    switch (_period) {
      case _Period.daily:
        // Detail per hari sepanjang horizon (hingga ~1 bulan).
        return _item.forecasts;
      case _Period.weekly:
        // Agregasi per minggu (7 hari).
        return _aggregateForecasts(_item.forecasts, _Period.weekly);
      case _Period.monthly:
        // Agregasi per bulan kalender.
        return _aggregateForecasts(_item.forecasts, _Period.monthly);
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    final forecasts = _periodForecasts;
    final status = item.overallStatus;
    final days = item.daysUntilDepletion;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Item selector + period switcher
        Row(
          children: [
            // Item dropdown
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  value: _selectedIdx,
                  isDense: true,
                  borderRadius: BorderRadius.circular(12),
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  items: List.generate(widget.vm.items.length, (i) {
                    final it = widget.vm.items[i];
                    return DropdownMenuItem(
                      value: i,
                      child: Row(
                        children: [
                          const Icon(Icons.inventory_2_outlined,
                              size: 14, color: Colors.grey),
                          const SizedBox(width: 6),
                          Text('Ingredient: ${it.name}',
                              style: const TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    );
                  }),
                  onChanged: (v) {
                    if (v != null) setState(() => _selectedIdx = v);
                  },
                ),
              ),
            ),
            const SizedBox(width: 12),
            // Period switcher
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: _Period.values.map((p) {
                  final isActive = p == _period;
                  return GestureDetector(
                    onTap: () => setState(() => _period = p),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: isActive ? _kGreen : Colors.transparent,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(p.label,
                          style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color:
                                  isActive ? Colors.white : Colors.grey[700])),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Warning banner
        if (status != _StockStatus.normal)
          _WarningBanner(
              itemName: item.name, daysUntilDepletion: days, status: status),
        if (status != _StockStatus.normal) const SizedBox(height: 16),

        // Summary cards
        _SummaryCards(item: item, period: _period),
        const SizedBox(height: 20),

        // Chart + metrik + tabel — hanya bila periode aktif punya minimal
        // satu bucket LENGKAP (lihat _aggregateForecasts). Kalau belum ada
        // (mis. horizon prediksi belum menutupi 1 minggu/bulan penuh),
        // tampilkan info kosong daripada bar yang anjlok karena data parsial.
        if (forecasts.isEmpty)
          _PeriodEmptyPanel(period: _period)
        else ...[
          _DepletionChart(item: item, period: _period, forecasts: forecasts),
          const SizedBox(height: 20),

          // Metrik & penjelasan (pemakaian). Tingkat keyakinan mengikuti run
          // native granularitas aktif (sesuai DB) lewat confidenceScore; bar
          // sengaja tanpa confidence agar tidak menimpanya.
          ForecastMetricsPanel(
            bars: forecasts
                .map((f) => ForecastBar(
                      label: '',
                      fullLabel: _stockDateLabel(f.date),
                      value: f.predictedUsage,
                      lower: f.lower,
                      upper: f.upper,
                    ))
                .toList(),
            fmt: (v) => '${v.toStringAsFixed(1)} Kg',
            confidenceScore: item.confidenceFor(_period),
            accent: _kGreenDark,
          ),
          const SizedBox(height: 20),

          // Table
          _ForecastTable(item: item, forecasts: forecasts, period: _period),
        ],
        const SizedBox(height: 20),

        // Insight
        _StockInsightsCard(insights: _stockInsights(item)),
      ],
    );
  }

  List<String> _stockInsights(_ItemData item) {
    final daily = item.forecasts;
    if (daily.isEmpty) return const [];
    final days = item.daysUntilDepletion;
    final head = daily.take(7).toList();
    final avg =
        head.fold<double>(0, (s, f) => s + f.predictedUsage) / head.length;
    _DayForecast peak = daily.first;
    for (final f in daily) {
      if (f.predictedUsage > peak.predictedUsage) peak = f;
    }
    final conf = item.confidenceFor(_Period.daily);

    return [
      days > 0
          ? 'Stok "${item.name}" diprediksi habis dalam $days hari — segera '
              'rencanakan restock.'
          : 'Stok "${item.name}" diprediksi aman sepanjang ${daily.length} '
              'hari ke depan.',
      'Puncak pemakaian diprediksi pada ${_stockDateLabel(peak.date)} '
          '(~${peak.predictedUsage.toStringAsFixed(1)} Kg).',
      'Rata-rata pemakaian ~${avg.toStringAsFixed(1)} Kg/hari, tingkat '
          'keyakinan model ${conf.toStringAsFixed(0)}%.',
    ];
  }
}

/// Ditampilkan saat periode aktif (mingguan/bulanan) belum punya satu bucket
/// pun yang lengkap dalam horizon prediksi — lebih baik kosong daripada
/// menampilkan bar hasil agregasi sebagian hari yang menyesatkan.
class _PeriodEmptyPanel extends StatelessWidget {
  final _Period period;
  const _PeriodEmptyPanel({required this.period});

  @override
  Widget build(BuildContext context) {
    return ForecastCardShell(
      padding: const EdgeInsets.all(32),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.timeline, size: 36, color: Colors.grey[300]),
            const SizedBox(height: 10),
            Text(
              'Belum ada periode ${period.label.toLowerCase()} yang lengkap '
              'dalam rentang prediksi ini',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.grey, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// WARNING BANNER
// ==========================================
class _WarningBanner extends StatelessWidget {
  final String itemName;
  final int daysUntilDepletion;
  final _StockStatus status;

  const _WarningBanner({
    required this.itemName,
    required this.daysUntilDepletion,
    required this.status,
  });

  @override
  Widget build(BuildContext context) {
    final msg = daysUntilDepletion > 0
        ? 'Peringatan: Stok "$itemName" diprediksi habis dalam '
            '$daysUntilDepletion hari ke depan berdasarkan forecast pemakaian!'
        : 'Peringatan: Stok "$itemName" diprediksi sudah kritis berdasarkan forecast pemakaian!';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFEBEE),
        borderRadius: BorderRadius.circular(10),
        border: const Border(
            left: BorderSide(color: _kLineRed, width: 3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: _kLineRed, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(msg,
                style: const TextStyle(
                    fontSize: 13,
                    color: _kLineRed,
                    fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// SUMMARY CARDS
// ==========================================
class _SummaryCards extends StatelessWidget {
  final _ItemData item;
  final _Period period;
  const _SummaryCards({required this.item, required this.period});

  @override
  Widget build(BuildContext context) {
    final days = item.daysUntilDepletion;
    final status = item.overallStatus;
    final avgUsage = item.forecasts.isEmpty
        ? 0.0
        : item.forecasts.take(7).fold<double>(0, (s, f) => s + f.predictedUsage) /
            item.forecasts.take(7).length;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: _Card(
            title: 'Stok Saat Ini',
            valueWidget: Text(
              item.currentStock > 0
                  ? '${item.currentStock.toStringAsFixed(1)} Kg'
                  : 'N/A',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            subtitle: 'Gudang Utama',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _Card(
            title: 'Prediksi Habis',
            valueWidget: Text(
              days > 0 ? '$days Hari' : 'Aman',
              style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: days > 0 && days <= 3 ? _kLineRed : Colors.black87),
            ),
            subtitle:
                'Pemakaian rata-rata: ${avgUsage.toStringAsFixed(1)} Kg / hari',
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _Card(
            title: 'Status Barang',
            valueWidget: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: status.bgColor,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(status.label,
                  style: TextStyle(
                      color: status.fgColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 14)),
            ),
            subtitle: switch (status) {
              _StockStatus.outOfStock => 'Butuh Restock Segera (PO)',
              _StockStatus.critical => 'Butuh Restock Segera (PO)',
              _StockStatus.warning => 'Perlu Perhatian',
              _StockStatus.normal => 'Stok Aman',
            },
          ),
        ),
      ],
    );
  }
}

class _Card extends StatelessWidget {
  final String title;
  final Widget valueWidget;
  final String subtitle;

  const _Card({
    required this.title,
    required this.valueWidget,
    required this.subtitle,
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
          const SizedBox(height: 10),
          valueWidget,
          const SizedBox(height: 6),
          Text(subtitle,
              style: const TextStyle(color: Colors.grey, fontSize: 11)),
        ],
      ),
    );
  }
}

// ==========================================
// DEPLETION CHART
// ==========================================
class _DepletionChart extends StatelessWidget {
  final _ItemData item;
  final _Period period;
  final List<_DayForecast> forecasts;

  const _DepletionChart(
      {required this.item, required this.period, required this.forecasts});

  @override
  Widget build(BuildContext context) {
    final histPoints = item.history;
    final predForecasts = forecasts;
    // Max y
    final allVals = [
      item.currentStock,
      ...histPoints.map((h) => h.stock),
      ...predForecasts.map((f) => f.estimatedRemaining),
    ];
    final maxY = allVals
            .where((v) => v > 0)
            .fold<double>(0, (a, b) => a > b ? a : b) *
        1.15;

    // X layout: history from x=0..histCount-1, prediction from histCount..
    final histCount = histPoints.length;

    final histSpots = List.generate(
        histCount, (i) => FlSpot(i.toDouble(), histPoints[i].stock));

    // Connect: last hist → first pred shares a point at x=histCount-1
    final predSpots = <FlSpot>[];
    if (histCount > 0) {
      predSpots.add(histSpots.last); // connecting point
    }
    for (var i = 0; i < predForecasts.length; i++) {
      predSpots.add(FlSpot(
          (histCount + i).toDouble(),
          predForecasts[i].estimatedRemaining));
    }

    // Pita confidence interval untuk sisa stok: akumulasi batas bawah/atas
    // pemakaian harian → batas atas/bawah sisa stok (pemakaian kecil = sisa
    // lebih banyak, dan sebaliknya).
    final upperRemain = <FlSpot>[];
    final lowerRemain = <FlSpot>[];
    if (histCount > 0) {
      upperRemain.add(histSpots.last);
      lowerRemain.add(histSpots.last);
    }
    double cumLo = 0, cumHi = 0;
    for (var i = 0; i < predForecasts.length; i++) {
      final f = predForecasts[i];
      cumLo += f.lower ?? f.predictedUsage;
      cumHi += f.upper ?? f.predictedUsage;
      final x = (histCount + i).toDouble();
      upperRemain.add(FlSpot(x, (item.currentStock - cumLo).clamp(0.0, maxY)));
      lowerRemain.add(FlSpot(x, (item.currentStock - cumHi).clamp(0.0, maxY)));
    }
    final hasBand =
        predForecasts.any((f) => f.lower != null && f.upper != null);

    // Find depletion point (stock hits 0)
    int? depletionIdx;
    for (var i = 0; i < predForecasts.length; i++) {
      if (predForecasts[i].estimatedRemaining <= 0) {
        depletionIdx = histCount + i;
        break;
      }
    }

    // X labels — pada tab Harian, sertakan nama hari (mis. "Sen\n1/7").
    String xlabel(String d) {
      if (d.length < 10) return d;
      if (period == _Period.daily) {
        final dt = DateTime.tryParse(d);
        if (dt != null) {
          return '${_kStockDayShort[dt.weekday]}\n${dt.day}/${dt.month}';
        }
      }
      return '${_dd(d)}\n${_mm(d)}';
    }

    final xLabels = <int, String>{};
    for (var i = 0; i < histCount; i++) {
      xLabels[i] = xlabel(histPoints[i].date);
    }
    for (var i = 0; i < predForecasts.length; i++) {
      xLabels[histCount + i] = xlabel(predForecasts[i].date);
    }

    final totalPoints = histCount + predForecasts.length;

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
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
              Text(
                  'Grafik Historis & Prediksi Pengurangan Stok (${period.label})',
                  style: const TextStyle(
                      color: Colors.grey,
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
              Row(
                children: [
                  _LegendLine(color: _kLineGreen, dashed: false, label: 'Historis'),
                  const SizedBox(width: 12),
                  _LegendLine(color: _kLineRed, dashed: true, label: 'Prediksi'),
                  if (hasBand) ...[
                    const SizedBox(width: 12),
                    _LegendBand(
                        color: _kLineRed.withValues(alpha: 0.12),
                        label: 'Interval'),
                  ],
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 280,
            child: LineChart(LineChartData(
              minX: 0,
              maxX: (totalPoints - 1).toDouble(),
              minY: 0,
              maxY: maxY,
              clipData: const FlClipData.all(),
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                getDrawingHorizontalLine: (_) =>
                    FlLine(color: Colors.grey.shade100, strokeWidth: 1),
              ),
              extraLinesData: ExtraLinesData(horizontalLines: [
                // Batas Habis line at y=0 (shown just above 0 for visibility)
                HorizontalLine(
                  y: 0,
                  color: _kLineRed.withValues(alpha: 0.5),
                  strokeWidth: 1.5,
                  dashArray: [6, 4],
                  label: HorizontalLineLabel(
                    show: true,
                    alignment: Alignment.topLeft,
                    padding: const EdgeInsets.only(left: 4, bottom: 4),
                    style: const TextStyle(
                        fontSize: 10,
                        color: _kLineRed,
                        fontWeight: FontWeight.w600),
                    labelResolver: (line) => 'Batas Habis (0 kg)',
                  ),
                ),
              ]),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 48,
                    getTitlesWidget: (v, meta) => Padding(
                      padding: const EdgeInsets.only(right: 4),
                      child: Text('${v.toStringAsFixed(0)} kg',
                          style: const TextStyle(
                              fontSize: 9, color: Colors.grey)),
                    ),
                  ),
                ),
                rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 28,
                    interval: 1,
                    getTitlesWidget: (v, meta) {
                      final i = v.toInt();
                      if (!xLabels.containsKey(i)) {
                        return const SizedBox.shrink();
                      }
                      final step = totalPoints > 10 ? 2 : 1;
                      if (i % step != 0) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(xLabels[i]!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 8, color: Colors.grey)),
                      );
                    },
                  ),
                ),
              ),
              borderData: FlBorderData(show: false),
              // Indeks lineBarsData: 0=batas atas (transparan), 1=batas bawah
              // (transparan), 2=prediksi, 3=historis. Pita di antara 0 & 1.
              betweenBarsData: hasBand
                  ? [
                      BetweenBarsData(
                        fromIndex: 0,
                        toIndex: 1,
                        color: _kLineRed.withValues(alpha: 0.12),
                      ),
                    ]
                  : const [],
              lineBarsData: [
                // 0: batas atas sisa (transparan)
                LineChartBarData(
                  spots: upperRemain,
                  color: Colors.transparent,
                  barWidth: 0,
                  dotData: const FlDotData(show: false),
                ),
                // 1: batas bawah sisa (transparan)
                LineChartBarData(
                  spots: lowerRemain,
                  color: Colors.transparent,
                  barWidth: 0,
                  dotData: const FlDotData(show: false),
                ),
                // 2: prediction (red dashed)
                LineChartBarData(
                  spots: predSpots,
                  color: _kLineRed,
                  isCurved: false,
                  barWidth: 2.5,
                  dashArray: const [8, 5],
                  dotData: FlDotData(
                    show: true,
                    getDotPainter: (spot, pct, bar, idx) {
                      final isDepletion = depletionIdx != null &&
                          spot.x.toInt() == depletionIdx;
                      return FlDotCirclePainter(
                        radius: isDepletion ? 7 : 3,
                        color: _kLineRed,
                        strokeWidth: isDepletion ? 2 : 1,
                        strokeColor: Colors.white,
                      );
                    },
                  ),
                  belowBarData: BarAreaData(show: false),
                ),
                // 3: historical (green solid)
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
                  getTooltipColor: (_) => Colors.black.withValues(alpha: 0.82),
                  fitInsideHorizontally: true,
                  fitInsideVertically: true,
                  getTooltipItems: (spots) => spots.map((s) {
                    // Lewati garis batas transparan (0 & 1).
                    if (s.barIndex == 0 || s.barIndex == 1) return null;
                    final label = xLabels[s.x.toInt()] ?? '';
                    if (s.barIndex == 2) {
                      double? bandHi, bandLo;
                      for (final sp in upperRemain) {
                        if (sp.x == s.x) bandHi = sp.y;
                      }
                      for (final sp in lowerRemain) {
                        if (sp.x == s.x) bandLo = sp.y;
                      }
                      final ci = (hasBand && bandLo != null && bandHi != null)
                          ? '\nInterval: ${bandLo.toStringAsFixed(1)}–'
                              '${bandHi.toStringAsFixed(1)} kg'
                          : '';
                      return LineTooltipItem(
                        'Sisa Prediksi\n$label\n${s.y.toStringAsFixed(1)} kg$ci',
                        const TextStyle(color: Colors.white, fontSize: 11));
                    }
                    return LineTooltipItem(
                      'Sisa Aktual\n$label\n${s.y.toStringAsFixed(1)} kg',
                      const TextStyle(color: Colors.white, fontSize: 11));
                  }).toList(),
                ),
              ),
            )),
          ),
        ],
      ),
    );
  }

  static String _dd(String iso) {
    if (iso.length < 10) return iso;
    return iso.substring(8, 10);
  }

  static String _mm(String iso) {
    if (iso.length < 10) return iso;
    final m = int.tryParse(iso.substring(5, 7));
    const months = {
      1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
      7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
    };
    return months[m] ?? iso.substring(5, 7);
  }
}

// Legend widgets
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
          child: CustomPaint(painter: _LinePainter(color: color, dashed: dashed)),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}

class _LegendBand extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendBand({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 18,
          height: 11,
          decoration: BoxDecoration(
              color: color, borderRadius: BorderRadius.circular(2)),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
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
      var x = 0.0;
      while (x < size.width) {
        canvas.drawLine(Offset(x, y),
            Offset((x + 5).clamp(0, size.width), y), paint);
        x += 8;
      }
    } else {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ==========================================
// FORECAST TABLE
// ==========================================
class _ForecastTable extends StatelessWidget {
  final _ItemData item;
  final List<_DayForecast> forecasts;
  final _Period period;

  const _ForecastTable(
      {required this.item, required this.forecasts, required this.period});

  @override
  Widget build(BuildContext context) {
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
          Text(
              'Tabel Prediksi Pemakaian ${period.label} (${item.name})',
              style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          // Header
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(children: const [
              Expanded(flex: 2, child: _TH('Tanggal')),
              Expanded(flex: 2, child: _TH('Prediksi Pemakaian')),
              Expanded(flex: 3, child: _TH('Estimasi Sisa Stok Akhir Hari')),
              Expanded(flex: 2, child: _TH('Status')),
            ]),
          ),
          const Divider(height: 1),
          for (final f in forecasts) ...[
            _ForecastRow(f: f, period: period),
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

class _ForecastRow extends StatelessWidget {
  final _DayForecast f;
  final _Period period;
  const _ForecastRow({required this.f, required this.period});

  @override
  Widget build(BuildContext context) {
    final remaining = f.estimatedRemaining;
    final isDeficit = remaining < 0;
    final remainingText = isDeficit
        ? '${remaining.toStringAsFixed(1)} Kg (Defisit)'
        : '${remaining.toStringAsFixed(1)} Kg';
    final remainingColor =
        f.status == _StockStatus.outOfStock || isDeficit
            ? _kLineRed
            : f.status == _StockStatus.critical
                ? Colors.deepOrange
                : Colors.black87;

    // Tab Harian: tampilkan nama hari juga (mis. "Senin, 1 Jul 2026").
    final dateText = period == _Period.daily
        ? _stockDateLabelWithDay(f.date)
        : _fmtDate(f.date);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 13),
      child: Row(children: [
        Expanded(
            flex: 2,
            child: Text(dateText, style: const TextStyle(fontSize: 13))),
        Expanded(
            flex: 2,
            child: Text('${f.predictedUsage.toStringAsFixed(1)} Kg',
                style: const TextStyle(fontSize: 13))),
        Expanded(
            flex: 3,
            child: Text(
              remainingText,
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: remainingColor),
            )),
        Expanded(
            flex: 2,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                  color: f.status.bgColor,
                  borderRadius: BorderRadius.circular(6)),
              child: Text(f.status.label,
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: f.status.fgColor)),
            )),
      ]),
    );
  }

  static String _fmtDate(String iso) {
    try {
      final dt = DateTime.parse(iso);
      const months = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
        7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
      };
      return '${dt.day} ${months[dt.month]} ${dt.year}';
    } catch (_) {
      return iso;
    }
  }
}

// ==========================================
// INSIGHT PREDIKSI STOK
// ==========================================
class _StockInsightsCard extends StatelessWidget {
  final List<String> insights;
  const _StockInsightsCard({required this.insights});

  @override
  Widget build(BuildContext context) {
    return ForecastCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(children: [
            Icon(Icons.lightbulb_outline, color: _kGreenDark, size: 18),
            SizedBox(width: 8),
            Text('Insight Prediksi Stok',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          ]),
          const SizedBox(height: 12),
          ...insights.map((t) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Icon(Icons.circle, size: 6, color: _kGreenDark),
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
              )),
        ],
      ),
    );
  }
}
