class SalesForecastPoint {
  final String date;
  final double value;
  final double? lowerBound;
  final double? upperBound;

  const SalesForecastPoint({
    required this.date,
    required this.value,
    this.lowerBound,
    this.upperBound,
  });
}

class SalesForecastModel {
  final double total7Days;
  final double total30Days;
  final double avg7Days;
  final double avg30Days;
  final String highestDay;
  final double highestValue;
  final String lowestDay;
  final double lowestValue;
  final String trendDirection;
  final double confidenceScore;
  final String confidenceLevel;
  final List<String> insights;
  final List<SalesForecastPoint> weeklyForecast;
  final List<SalesForecastPoint> monthlyForecast;

  const SalesForecastModel({
    required this.total7Days,
    required this.total30Days,
    required this.avg7Days,
    required this.avg30Days,
    required this.highestDay,
    required this.highestValue,
    required this.lowestDay,
    required this.lowestValue,
    required this.trendDirection,
    required this.confidenceScore,
    required this.confidenceLevel,
    required this.insights,
    required this.weeklyForecast,
    required this.monthlyForecast,
  });

  static String formatRupiah(double v) {
    if (v >= 1e9) return 'Rp ${(v / 1e9).toStringAsFixed(1)}M';
    if (v >= 1e6) return 'Rp ${(v / 1e6).toStringAsFixed(1)}Jt';
    if (v >= 1e3) return 'Rp ${(v / 1e3).toStringAsFixed(0)}Rb';
    return 'Rp ${v.toStringAsFixed(0)}';
  }

  String get formattedTotal7 => formatRupiah(total7Days);
  String get formattedAvg7 => formatRupiah(avg7Days);

  double get weeklyChangePercent {
    if (avg30Days == 0) return 0;
    return ((avg7Days - avg30Days) / avg30Days) * 100;
  }

  factory SalesForecastModel.fromPredictionList(List<dynamic> rawList) {
    const salesKeywords = ['revenue', 'sales', 'penjualan', 'omzet', 'pendapatan'];
    const skipKeywords = ['visitor', 'pengunjung', 'inventory', 'stock', 'stok', 'inventaris'];

    var all = rawList
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    var filtered = all.where((e) {
      final m = (e['module'] as String? ?? '').toLowerCase();
      return salesKeywords.any((k) => m.contains(k));
    }).toList();

    if (filtered.isEmpty) {
      filtered = all.where((e) {
        final m = (e['module'] as String? ?? '').toLowerCase();
        return !skipKeywords.any((k) => m.contains(k));
      }).toList();
    }

    if (filtered.isEmpty) filtered = all;

    filtered.sort((a, b) => (a['prediction_date'] as String? ?? '')
        .compareTo(b['prediction_date'] as String? ?? ''));

    SalesForecastPoint toPoint(Map<String, dynamic> p) => SalesForecastPoint(
          date: p['prediction_date'] ?? '',
          value: (p['predicted_value'] as num?)?.toDouble() ?? 0.0,
          lowerBound: (p['lower_bound'] as num?)?.toDouble(),
          upperBound: (p['upper_bound'] as num?)?.toDouble(),
        );

    final weekly = filtered.take(7).map(toPoint).toList();
    final monthly = filtered.take(30).map(toPoint).toList();

    final total7 = weekly.fold<double>(0, (s, p) => s + p.value);
    final total30 = monthly.fold<double>(0, (s, p) => s + p.value);
    final avg7 = weekly.isEmpty ? 0.0 : total7 / weekly.length;
    final avg30 = monthly.isEmpty ? 0.0 : total30 / monthly.length;

    SalesForecastPoint? highest, lowest;
    for (final p in weekly) {
      if (highest == null || p.value > highest.value) highest = p;
      if (lowest == null || p.value < lowest.value) lowest = p;
    }

    String trend = 'STABLE';
    if (weekly.length >= 4) {
      final mid = weekly.length ~/ 2;
      final first = weekly.sublist(0, mid).fold<double>(0, (s, p) => s + p.value);
      final second = weekly.sublist(mid).fold<double>(0, (s, p) => s + p.value);
      if (second > first) {
        trend = 'UPWARD';
      } else if (second < first) {
        trend = 'DOWNWARD';
      }
    }

    final mapes = filtered
        .map((p) => (p['mape'] as num?)?.toDouble())
        .whereType<double>()
        .toList();
    final avgMape = mapes.isEmpty
        ? 15.0
        : mapes.fold<double>(0, (s, v) => s + v) / mapes.length;
    final confScore = (100.0 - avgMape).clamp(0.0, 100.0);
    final confLevel = confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final insights = <String>[];
    if (highest != null && highest.value > 0) {
      insights.add(
          'Puncak penjualan diprediksi pada ${highest.date} dengan nilai ${formatRupiah(highest.value)}.');
    }
    if (trend == 'UPWARD') {
      insights.add('Tren penjualan menunjukkan peningkatan dalam periode prediksi.');
    } else if (trend == 'DOWNWARD') {
      insights.add('Tren penjualan menunjukkan penurunan dalam periode prediksi.');
    }
    if (mapes.isNotEmpty) {
      insights.add(
          'Akurasi model: MAPE ${avgMape.toStringAsFixed(1)}%, kepercayaan ${confScore.toStringAsFixed(1)}%.');
    }

    return SalesForecastModel(
      total7Days: total7,
      total30Days: total30,
      avg7Days: avg7,
      avg30Days: avg30,
      highestDay: highest?.date ?? '',
      highestValue: highest?.value ?? 0,
      lowestDay: lowest?.date ?? '',
      lowestValue: lowest?.value ?? 0,
      trendDirection: trend,
      confidenceScore: confScore,
      confidenceLevel: confLevel,
      insights: insights,
      weeklyForecast: weekly,
      monthlyForecast: monthly,
    );
  }
}
