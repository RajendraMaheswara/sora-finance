import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

import '../../core/services/api_service.dart';
import '../../models/visitor_forecast_model.dart';
import '../visitor_forecast/visitor_forecast_page.dart';

// ==========================================
// KONFIGURASI
// ==========================================
// Store ID dummy yang sama dengan contoh response forecast.
// Nanti tinggal ganti / ambil dari state global / login.
const String _kStoreId = 'b4e2f559-9615-4263-84fe-9ee97780748f';

// Endpoint forecast pengunjung. Pola URL menunggu route backend dibuat.
String _visitorForecastEndpoint(String storeId) => 'forecast/visitors/$storeId';

const Color _kPrimaryGreen = Color(0xFF8CE600);
const Color _kPrimaryGreenDark = Color(0xFF24CC14);

// ==========================================
// SCREEN
// ==========================================
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();

  late Future<VisitorForecastModel> _visitorForecastFuture;

  Future<VisitorForecastModel> _fetchVisitorForecast() async {
    final raw = await _apiService.fetchObject(
      _visitorForecastEndpoint(_kStoreId),
    );
    return VisitorForecastModel.fromJson(raw);
  }

  @override
  void initState() {
    super.initState();
    _visitorForecastFuture = _fetchVisitorForecast();
  }

  void _refresh() {
    setState(() {
      _visitorForecastFuture = _fetchVisitorForecast();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F6F7),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _SidebarWidget(),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(32, 24, 32, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _HeaderWidget(onRefresh: _refresh),
                  const SizedBox(height: 28),
                  _PredictionRow(visitorForecastFuture: _visitorForecastFuture),
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
// SIDEBAR
// ==========================================
class _SidebarWidget extends StatelessWidget {
  const _SidebarWidget();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Logo
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.eco, color: Colors.lightGreen[600], size: 22),
              const SizedBox(width: 4),
              Text(
                'sora',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: Colors.lightGreen[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Avatar
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.grey.shade200, width: 2),
              color: Colors.grey.shade200,
            ),
            child: const ClipOval(
              child: Icon(Icons.person, size: 56, color: Colors.white),
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Aminah',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 2),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Text(
                'Admin',
                style: TextStyle(
                  color: Colors.grey,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              SizedBox(width: 4),
              Text('🔴', style: TextStyle(fontSize: 9)),
            ],
          ),
          const SizedBox(height: 28),

          // Active menu: Dasbor
          const _SidebarMenuItem(
            icon: Icons.pie_chart,
            title: 'Dasbor',
            isActive: true,
          ),
        ],
      ),
    );
  }
}

class _SidebarMenuItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final bool isActive;

  const _SidebarMenuItem({
    required this.icon,
    required this.title,
    this.isActive = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 70,
      height: 70,
      decoration: BoxDecoration(
        color: isActive ? _kPrimaryGreen : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            color: isActive ? Colors.white : Colors.grey[700],
            size: 26,
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isActive ? Colors.white : Colors.grey[700],
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
    final hour12 = now.hour % 12 == 0 ? 12 : now.hour % 12;
    final mm = now.minute.toString().padLeft(2, '0');
    return 'Opened $hour12:$mm ${isPm ? 'pm' : 'am'}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Top row: just timestamp
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
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Dasbor',
                  style: TextStyle(color: Colors.grey, fontSize: 13),
                ),
                SizedBox(height: 6),
                Text(
                  'Ringkasan Penjualan',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
            Row(
              children: [
                IconButton(
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                  tooltip: 'Refresh data',
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
// PREDICTION ROW (3 KARTU)
// ==========================================
class _PredictionRow extends StatelessWidget {
  final Future<VisitorForecastModel> visitorForecastFuture;

  const _PredictionRow({required this.visitorForecastFuture});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Card 1: Prediksi Penjualan -> COMING SOON
        const Expanded(
          child: _ComingSoonCard(title: 'Prediksi Penjualan (Minggu Depan)'),
        ),
        const SizedBox(width: 16),

        // Card 2: Prediksi Pengunjung -> dari endpoint forecast (clickable)
        Expanded(
          child: Builder(
            builder: (context) => InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        const VisitorForecastPage(storeId: _kStoreId),
                  ),
                );
              },
              child: _VisitorPredictionCard(future: visitorForecastFuture),
            ),
          ),
        ),
        const SizedBox(width: 16),

        // Card 3: Prediksi Stok -> COMING SOON
        const Expanded(
          child: _ComingSoonCard(
            title: 'Prediksi Stok (Kritis)',
            badgeText: 'Warning',
            badgeBg: Color(0xFFFFEBEE),
            badgeFg: Colors.red,
          ),
        ),
      ],
    );
  }
}

// ==========================================
// CARD: COMING SOON
// ==========================================
class _ComingSoonCard extends StatelessWidget {
  final String title;
  final String? badgeText;
  final Color? badgeBg;
  final Color? badgeFg;

  const _ComingSoonCard({
    required this.title,
    this.badgeText,
    this.badgeBg,
    this.badgeFg,
  });

  @override
  Widget build(BuildContext context) {
    return _CardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: Colors.grey,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (badgeText != null)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: badgeBg ?? Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    badgeText!,
                    style: TextStyle(
                      color: badgeFg ?? Colors.grey,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 24),
          Center(
            child: Column(
              children: [
                Icon(
                  Icons.hourglass_bottom,
                  size: 36,
                  color: Colors.grey.shade400,
                ),
                const SizedBox(height: 8),
                Text(
                  'Coming Soon',
                  style: TextStyle(
                    color: Colors.grey.shade500,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Fitur prediksi belum tersedia',
                  style: TextStyle(color: Colors.grey.shade400, fontSize: 11),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

// ==========================================
// CARD: PREDIKSI PENGUNJUNG (real data)
// ==========================================
class _VisitorPredictionCard extends StatelessWidget {
  final Future<VisitorForecastModel> future;
  const _VisitorPredictionCard({required this.future});

  @override
  Widget build(BuildContext context) {
    return _CardShell(
      child: FutureBuilder<VisitorForecastModel>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const _CardLoading(
              title: 'Prediksi Pengunjung (Minggu Depan)',
            );
          }
          if (snapshot.hasError) {
            return _CardError(
              title: 'Prediksi Pengunjung (Minggu Depan)',
              message: '${snapshot.error}',
            );
          }

          final data = snapshot.data!;
          final pct = data.weeklyChangePercent;
          final pctText = '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%';
          final isUp = pct >= 0;

          // Bar data dari weekly_forecast
          final values = data.weeklyForecast
              .map((p) => p.predictedVisitors)
              .toList();
          final maxVal = values.isEmpty
              ? 1
              : values.reduce((a, b) => a > b ? a : b);

          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Prediksi Pengunjung (Minggu Depan)',
                style: TextStyle(
                  color: Colors.grey,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Text(
                    '${data.totalNext7Days} Orang',
                    style: const TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: isUp
                          ? const Color(0xFFE8F5E9)
                          : const Color(0xFFFFEBEE),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      pctText,
                      style: TextStyle(
                        color: isUp ? Colors.green : Colors.red,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Rata-rata harian: ${data.avgDailyNext7Days.toStringAsFixed(0)} Orang',
                style: const TextStyle(color: Colors.grey, fontSize: 12),
              ),
              const SizedBox(height: 20),
              SizedBox(
                height: 70,
                child: _VisitorBarChart(values: values, maxVal: maxVal),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _VisitorBarChart extends StatelessWidget {
  final List<int> values;
  final int maxVal;

  const _VisitorBarChart({required this.values, required this.maxVal});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) {
      return Center(
        child: Text(
          'Tidak ada data prediksi',
          style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
        ),
      );
    }

    // Indeks bar tertinggi: di-highlight biru tua (mengikuti gambar).
    int maxIdx = 0;
    for (var i = 0; i < values.length; i++) {
      if (values[i] > values[maxIdx]) maxIdx = i;
    }

    return BarChart(
      BarChartData(
        gridData: const FlGridData(show: false),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: false),
        alignment: BarChartAlignment.spaceEvenly,
        maxY: (maxVal * 1.15).clamp(1, double.infinity).toDouble(),
        barTouchData: BarTouchData(
          enabled: true,
          touchTooltipData: BarTouchTooltipData(
            getTooltipItem: (group, _, rod, __) {
              return BarTooltipItem(
                '${rod.toY.toInt()} pengunjung',
                const TextStyle(color: Colors.white, fontSize: 11),
              );
            },
          ),
        ),
        barGroups: List.generate(values.length, (i) {
          final isPeak = i == maxIdx;
          return BarChartGroupData(
            x: i,
            barRods: [
              BarChartRodData(
                toY: values[i].toDouble(),
                color: isPeak ? const Color(0xFF1E88E5) : Colors.blue.shade100,
                width: 18,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(4),
                ),
              ),
            ],
          );
        }),
      ),
    );
  }
}

// ==========================================
// SHARED CARD SHELL & STATES
// ==========================================
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
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
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
        Text(
          title,
          style: const TextStyle(
            color: Colors.grey,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 32),
        const Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: _kPrimaryGreenDark,
            ),
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
        Text(
          title,
          style: const TextStyle(
            color: Colors.grey,
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 16),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Gagal memuat prediksi.\n$message',
                style: const TextStyle(color: Colors.red, fontSize: 12),
              ),
            ),
          ],
        ),
      ],
    );
  }
}
