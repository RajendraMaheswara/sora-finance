import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

import '../../core/services/api_service.dart';
import '../../models/finance_daily_summary_dashboard_model.dart';
import '../../models/ingredient_stock_history_dashboard_model.dart';
import '../../models/customer_model.dart';

// ==========================================
// DATA CLASS: menampung semua hasil fetch
// ==========================================
class _DashboardData {
  final List<FinanceDailySummaryDashboardModel> dailySummaries;
  final List<CustomerModel> customers;
  final List<IngredientStockHistoryDashboardModel> stockHistories;

  _DashboardData({
    required this.dailySummaries,
    required this.customers,
    required this.stockHistories,
  });

  double get totalOmset =>
      dailySummaries.fold(0, (s, e) => s + e.totalOmset);

  double get totalHpp =>
      dailySummaries.fold(0, (s, e) => s + e.totalHpp);

  double get totalKeuntungan =>
      dailySummaries.fold(0, (s, e) => s + e.totalKeuntungan);

  double get selisihPersen =>
      totalOmset == 0 ? 0 : (totalKeuntungan / totalOmset) * 100;

  double get avgHarian =>
      dailySummaries.isEmpty ? 0 : totalOmset / dailySummaries.length;

  // Ambil 7 data terakhir, konversi ke juta untuk chart
  List<double> get revenueChartData =>
      dailySummaries
          .take(7)
          .map((e) => e.totalOmset / 1_000_000)
          .toList();

  // Stok paling kritis (quantity paling sedikit)
  List<IngredientStockHistoryDashboardModel> get criticalStocks {
    final sorted = [...stockHistories]
      ..sort((a, b) => a.quantity.compareTo(b.quantity));
    return sorted.take(3).toList();
  }

  String formatRupiah(double value) {
    if (value >= 1_000_000) {
      return 'Rp ${(value / 1_000_000).toStringAsFixed(1)}jt';
    } else if (value >= 1_000) {
      return 'Rp ${(value / 1_000).toStringAsFixed(0)}rb';
    }
    return 'Rp ${value.toStringAsFixed(0)}';
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
  final ApiService _apiService = ApiService();

  late Future<_DashboardData> _dashboardData;

  Future<_DashboardData> _fetchDashboardData() async {
    final results = await Future.wait([
      _apiService.fetchData('finance-daily-summaries'),
      _apiService.fetchData('customers'),
      _apiService.fetchData('ingredient-stock-histories'),
    ]);

    return _DashboardData(
      dailySummaries: (results[0])
          .map((e) => FinanceDailySummaryDashboardModel.fromJson(e))
          .toList(),
      customers: (results[1])
          .map((e) => CustomerModel.fromJson(e))
          .toList(),
      stockHistories: (results[2])
          .map((e) => IngredientStockHistoryDashboardModel.fromJson(e))
          .toList(),
    );
  }

  @override
  void initState() {
    super.initState();
    _dashboardData = _fetchDashboardData();
  }

  void _refresh() {
    setState(() {
      _dashboardData = _fetchDashboardData();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          const _SidebarWidget(),
          Expanded(
            child: FutureBuilder<_DashboardData>(
              future: _dashboardData,
              builder: (context, snapshot) {
                // Loading
                if (snapshot.connectionState ==
                    ConnectionState.waiting) {
                  return const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(
                          color: Color(0xFF8CE600),
                        ),
                        SizedBox(height: 16),
                        Text(
                          'Memuat data...',
                          style: TextStyle(color: Colors.grey),
                        ),
                      ],
                    ),
                  );
                }

                // Error
                if (snapshot.hasError) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(
                          Icons.wifi_off,
                          size: 48,
                          color: Colors.red,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Gagal memuat data.\n${snapshot.error}',
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.red),
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _refresh,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Coba Lagi'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF8CE600),
                            foregroundColor: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  );
                }

                // Success
                final data = snapshot.data!;
                return SingleChildScrollView(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _HeaderWidget(onRefresh: _refresh),
                      const SizedBox(height: 24),
                      _SummaryCardsRow(data: data),
                      const SizedBox(height: 24),
                      _ChartsSectionRow(data: data),
                      const SizedBox(height: 24),
                      _PredictionSectionRow(data: data),
                    ],
                  ),
                );
              },
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
      width: 180,
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 12),
      child: Column(
        children: [
          Text(
            'sora abadi',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: Colors.lightGreen[700],
            ),
          ),
          const SizedBox(height: 20),
          const CircleAvatar(
            radius: 35,
            backgroundColor: Colors.grey,
            child: Icon(Icons.person, size: 40, color: Colors.white),
          ),
          const SizedBox(height: 8),
          const Text(
            'Aminah',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.green[50],
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Text(
              'Admin 🟢',
              style: TextStyle(
                color: Colors.green,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: GridView.count(
              crossAxisCount: 2,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
              children: const [
                _SidebarMenuItem(
                  icon: Icons.pie_chart,
                  title: 'Dasbor',
                  isActive: true,
                ),
                _SidebarMenuItem(icon: Icons.calculate, title: 'Kasir'),
                _SidebarMenuItem(icon: Icons.receipt_long, title: 'Tagihan'),
                _SidebarMenuItem(icon: Icons.shopping_bag, title: 'Pesanan'),
                _SidebarMenuItem(
                  icon: Icons.restaurant_menu,
                  title: 'Resep',
                ),
                _SidebarMenuItem(icon: Icons.percent, title: 'Promo'),
                _SidebarMenuItem(icon: Icons.layers, title: 'Bahanbaku'),
                _SidebarMenuItem(
                  icon: Icons.assignment_ind,
                  title: 'Absensi',
                ),
                _SidebarMenuItem(
                  icon: Icons.contact_support,
                  title: 'Support',
                ),
                _SidebarMenuItem(icon: Icons.settings, title: 'Pengaturan'),
              ],
            ),
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
      decoration: BoxDecoration(
        color: isActive ? const Color(0xFF8CE600) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            color: isActive ? Colors.white : Colors.grey[700],
            size: 24,
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

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Dasbor',
              style: TextStyle(color: Colors.grey, fontSize: 14),
            ),
            SizedBox(height: 4),
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
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.storefront, size: 18),
              label: const Text('Soramen'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: Colors.black87,
                side: BorderSide(color: Colors.grey.shade300),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ==========================================
// SUMMARY CARDS
// ==========================================
class _SummaryCardsRow extends StatelessWidget {
  final _DashboardData data;
  const _SummaryCardsRow({required this.data});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MiniSummaryCard(
            title: 'Omset',
            value: data.formatRupiah(data.totalOmset),
            percentage: '+2.89%',
            isPositive: true,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _MiniSummaryCard(
            title: 'Hpp',
            value: data.formatRupiah(data.totalHpp),
            percentage: '-1.09%',
            isPositive: false,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _MiniSummaryCard(
            title: 'Keuntungan',
            value: data.formatRupiah(data.totalKeuntungan),
            percentage: data.totalKeuntungan >= 0
                ? '+${data.selisihPersen.toStringAsFixed(1)}%'
                : '${data.selisihPersen.toStringAsFixed(1)}%',
            isPositive: data.totalKeuntungan >= 0,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _MiniSummaryCard(
            title: 'Selisih',
            value: '${data.selisihPersen.toStringAsFixed(1)}%',
            percentage: '-1.07%',
            isPositive: false,
          ),
        ),
      ],
    );
  }
}

class _MiniSummaryCard extends StatelessWidget {
  final String title;
  final String value;
  final String percentage;
  final bool isPositive;

  const _MiniSummaryCard({
    required this.title,
    required this.value,
    required this.percentage,
    required this.isPositive,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade100),
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
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(
                  value,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 6,
                  vertical: 2,
                ),
                decoration: BoxDecoration(
                  color: isPositive ? Colors.green[50] : Colors.red[50],
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  percentage,
                  style: TextStyle(
                    color: isPositive ? Colors.green : Colors.red,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'vs. previous',
            style: TextStyle(color: Colors.grey, fontSize: 11),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// CHARTS SECTION
// ==========================================
class _ChartsSectionRow extends StatelessWidget {
  final _DashboardData data;
  const _ChartsSectionRow({required this.data});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Line Chart: Pendapatan
        Expanded(
          flex: 2,
          child: Container(
            height: 340,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                Container(
                  color: const Color(0xFF8CE600),
                  padding: const EdgeInsets.all(16),
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Pendapatan',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${data.dailySummaries.length} hari terakhir',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.7),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 24, 24, 16),
                    child: _RevenueLineChart(
                      chartData: data.revenueChartData,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 16),

        // Bar Chart: Penjualan Harian
        Expanded(
          flex: 1,
          child: Container(
            height: 340,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                Container(
                  color: const Color(0xFF8CE600),
                  padding: const EdgeInsets.all(16),
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Penjualan harian',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        data.dailySummaries.isNotEmpty
                            ? '${data.formatRupiah(data.avgHarian)} Rata-rata'
                            : 'Belum ada data',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.9),
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 24, 12, 16),
                    child: _DailySalesBarChart(
                      chartData: data.revenueChartData,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RevenueLineChart extends StatelessWidget {
  final List<double> chartData;
  const _RevenueLineChart({required this.chartData});

  @override
  Widget build(BuildContext context) {
    if (chartData.isEmpty) {
      return const Center(
        child: Text(
          'Tidak ada data',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    final spots = chartData
        .asMap()
        .entries
        .map((e) => FlSpot(e.key.toDouble(), e.value))
        .toList();
    final maxY =
        (chartData.reduce((a, b) => a > b ? a : b) * 1.2).clamp(
          1.0,
          double.infinity,
        );

    return LineChart(
      LineChartData(
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          getDrawingHorizontalLine: (value) =>
              FlLine(color: Colors.grey.shade100, strokeWidth: 1),
        ),
        titlesData: FlTitlesData(
          rightTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          topTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 40,
              getTitlesWidget: (value, meta) => Text(
                '${value.toStringAsFixed(1)}M',
                style: const TextStyle(fontSize: 10, color: Colors.grey),
              ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final idx = value.toInt();
                if (idx >= 0 && idx < chartData.length) {
                  return Text(
                    'H-${chartData.length - idx}',
                    style: const TextStyle(fontSize: 10, color: Colors.grey),
                  );
                }
                return const Text('');
              },
            ),
          ),
        ),
        borderData: FlBorderData(show: false),
        minX: 0,
        maxX: (chartData.length - 1).toDouble(),
        minY: 0,
        maxY: maxY,
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            gradient: const LinearGradient(
              colors: [Color(0xFF24CC14), Color(0xFF8CE600)],
            ),
            barWidth: 4,
            isStrokeCapRound: true,
            dotData: const FlDotData(show: true),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF8CE600).withOpacity(0.25),
                  const Color(0xFF8CE600).withOpacity(0.0),
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DailySalesBarChart extends StatelessWidget {
  final List<double> chartData;
  const _DailySalesBarChart({required this.chartData});

  @override
  Widget build(BuildContext context) {
    if (chartData.isEmpty) {
      return const Center(
        child: Text(
          'Tidak ada data',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    final maxY =
        chartData.reduce((a, b) => a > b ? a : b) * 1.2;

    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: maxY.clamp(1.0, double.infinity),
        barTouchData: BarTouchData(enabled: true),
        titlesData: FlTitlesData(
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final idx = value.toInt();
                if (idx >= 0 && idx < chartData.length) {
                  return Text(
                    'H${idx + 1}',
                    style: const TextStyle(
                      fontSize: 10,
                      color: Colors.grey,
                    ),
                  );
                }
                return const Text('');
              },
            ),
          ),
          leftTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          topTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          rightTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
        ),
        gridData: const FlGridData(show: false),
        borderData: FlBorderData(show: false),
        barGroups: chartData.asMap().entries.map((e) {
          return BarChartGroupData(
            x: e.key,
            barRods: [
              BarChartRodData(
                toY: e.value,
                gradient: const LinearGradient(
                  colors: [Color(0xFF24CC14), Color(0xFF8CE600)],
                  begin: Alignment.bottomCenter,
                  end: Alignment.topCenter,
                ),
                width: 16,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }
}

// ==========================================
// PREDICTION SECTION
// ==========================================
class _PredictionSectionRow extends StatelessWidget {
  final _DashboardData data;
  const _PredictionSectionRow({required this.data});

  @override
  Widget build(BuildContext context) {
    final prediksiMingguDepan = data.avgHarian * 7;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Card 1: Prediksi Penjualan
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Prediksi Penjualan (Minggu Depan)',
                  style: TextStyle(
                    color: Colors.grey,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        data.formatRupiah(prediksiMingguDepan),
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.green[50],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        '+8.5%',
                        style: TextStyle(
                          color: Colors.green,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Rata-rata harian: ${data.formatRupiah(data.avgHarian)}',
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
                const SizedBox(height: 24),
                _MiniSparkLineChart(chartData: data.revenueChartData),
              ],
            ),
          ),
        ),
        const SizedBox(width: 16),

        // Card 2: Prediksi Pengunjung
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Prediksi Pengunjung (Minggu Depan)',
                  style: TextStyle(
                    color: Colors.grey,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Text(
                      '${data.customers.length} Orang',
                      style: const TextStyle(
                        fontSize: 20,
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
                        color: Colors.green[50],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        '+12.2%',
                        style: TextStyle(
                          color: Colors.green,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Total customer terdaftar: ${data.customers.length} orang',
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
                const SizedBox(height: 24),
                const _MiniSparkBarChart(),
              ],
            ),
          ),
        ),
        const SizedBox(width: 16),

        // Card 3: Prediksi Stok Kritis
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Prediksi Stok (Kritis)',
                      style: TextStyle(
                        color: Colors.grey,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.red[50],
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'Warning',
                        style: TextStyle(
                          color: Colors.red,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  '${data.criticalStocks.length} Item',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Text(
                  'Diprediksi habis dalam < 3 hari',
                  style: TextStyle(color: Colors.grey, fontSize: 12),
                ),
                const SizedBox(height: 16),
                if (data.criticalStocks.isEmpty)
                  const Text(
                    'Stok aman ✅',
                    style: TextStyle(color: Colors.green),
                  )
                else
                  ...data.criticalStocks.asMap().entries.map((entry) {
                    final isUrgent = entry.key == 0;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _StockStatusRow(
                        name: entry.value.ingredientName,
                        status: isUrgent ? 'Habis 1 Hari' : 'Habis 3 Hari',
                        isUrgent: isUrgent,
                      ),
                    );
                  }),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

// ==========================================
// SPARKLINE & SPARKBAR
// ==========================================
class _MiniSparkLineChart extends StatelessWidget {
  final List<double> chartData;
  const _MiniSparkLineChart({required this.chartData});

  @override
  Widget build(BuildContext context) {
    final spots = chartData.isEmpty
        ? [const FlSpot(0, 1), const FlSpot(1, 2), const FlSpot(2, 1.5)]
        : chartData
            .asMap()
            .entries
            .map((e) => FlSpot(e.key.toDouble(), e.value))
            .toList();

    final maxY =
        spots.map((s) => s.y).reduce((a, b) => a > b ? a : b) * 1.3;

    return SizedBox(
      height: 45,
      child: LineChart(
        LineChartData(
          gridData: const FlGridData(show: false),
          titlesData: const FlTitlesData(show: false),
          borderData: FlBorderData(show: false),
          minX: 0,
          maxX: (spots.length - 1).toDouble(),
          minY: 0,
          maxY: maxY,
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              color: const Color(0xFF24CC14),
              barWidth: 3,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(
                show: true,
                color: const Color(0xFF24CC14).withOpacity(0.1),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniSparkBarChart extends StatelessWidget {
  const _MiniSparkBarChart();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 45,
      child: BarChart(
        BarChartData(
          gridData: const FlGridData(show: false),
          titlesData: const FlTitlesData(show: false),
          borderData: FlBorderData(show: false),
          alignment: BarChartAlignment.spaceEvenly,
          maxY: 5,
          barGroups: [
            _makeGroup(0, 1.5),
            _makeGroup(1, 2.5),
            _makeGroup(2, 2.0),
            _makeGroup(3, 3.8),
            _makeGroup(4, 3.0),
            _makeGroup(5, 4.8),
          ],
        ),
      ),
    );
  }

  BarChartGroupData _makeGroup(int x, double y) {
    return BarChartGroupData(
      x: x,
      barRods: [
        BarChartRodData(
          toY: y,
          color: Colors.blue[400],
          width: 10,
          borderRadius: BorderRadius.circular(3),
        ),
      ],
    );
  }
}

class _StockStatusRow extends StatelessWidget {
  final String name;
  final String status;
  final bool isUrgent;

  const _StockStatusRow({
    required this.name,
    required this.status,
    required this.isUrgent,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Flexible(
          child: Text(
            name,
            style: const TextStyle(
              fontWeight: FontWeight.w500,
              fontSize: 13,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: isUrgent ? Colors.red[50] : Colors.orange[50],
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            status,
            style: TextStyle(
              color: isUrgent ? Colors.red : Colors.orange[800],
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ],
    );
  }
}