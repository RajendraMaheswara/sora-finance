import 'dart:math' as math;

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
  /// Apakah data berasal dari proyeksi historis (bukan model ML).
  final bool isProjection;

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
    this.isProjection = false,
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

  // ================================================================
  // FACTORY UTAMA: coba 3 sumber secara berurutan
  // ================================================================
  static Future<SalesForecastModel> loadFromApi(
    Future<List<dynamic>> Function(String) fetchData,
  ) async {
    final results = await Future.wait([
      fetchData('forecast-predictions'),
      fetchData('forecast-results'),
      fetchData('sales-daily-summaries'),
    ]);
    return SalesForecastModel.fromSources(results[0], results[1], results[2]);
  }

  factory SalesForecastModel.fromSources(
    List<dynamic> predictions,
    List<dynamic> results,
    List<dynamic> salesSummaries,
  ) {
    const salesKeywords = [
      'revenue', 'sales', 'penjualan', 'omzet', 'pendapatan'
    ];

    // 1. Cari di forecast_predictions berdasarkan module
    final predFiltered = predictions
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .where((e) {
          final m = (e['module'] as String? ?? '').toLowerCase();
          return salesKeywords.any((k) => m.contains(k));
        })
        .toList()
      ..sort((a, b) => (a['prediction_date'] as String? ?? '')
          .compareTo(b['prediction_date'] as String? ?? ''));

    if (predFiltered.isNotEmpty) {
      return _fromPredictions(predFiltered);
    }

    // 2. Cari di forecast_results berdasarkan item_type
    var resultFiltered = results
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .where((e) {
          final t = (e['item_type'] as String? ?? '').toLowerCase();
          return salesKeywords.any((k) => t.contains(k));
        })
        .toList();

    // Tidak ada fallback lebar — hanya gunakan forecast_results jika
    // item_type secara eksplisit berisi kata kunci penjualan.
    if (resultFiltered.isNotEmpty) {
      resultFiltered.sort((a, b) =>
          (a['target_date'] as String? ?? '')
              .compareTo(b['target_date'] as String? ?? ''));
      return _fromResults(resultFiltered);
    }

    // 3. Fallback: proyeksi dari sales_daily_summaries
    final summaries = salesSummaries
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList()
      ..sort((a, b) =>
          (a['date'] as String? ?? '').compareTo(b['date'] as String? ?? ''));

    if (summaries.isNotEmpty) {
      return _fromSalesSummaries(summaries);
    }

    return const SalesForecastModel(
      total7Days: 0, total30Days: 0, avg7Days: 0, avg30Days: 0,
      highestDay: '', highestValue: 0, lowestDay: '', lowestValue: 0,
      trendDirection: 'STABLE', confidenceScore: 0, confidenceLevel: '-',
      insights: [], weeklyForecast: [], monthlyForecast: [],
    );
  }

  // ----------------------------------------------------------------
  // Sumber 1: forecast_predictions
  // ----------------------------------------------------------------
  static SalesForecastModel _fromPredictions(
      List<Map<String, dynamic>> rows) {
    SalesForecastPoint toPoint(Map<String, dynamic> p) => SalesForecastPoint(
          date: p['prediction_date'] ?? '',
          value: (p['predicted_value'] as num?)?.toDouble() ?? 0.0,
          lowerBound: (p['lower_bound'] as num?)?.toDouble(),
          upperBound: (p['upper_bound'] as num?)?.toDouble(),
        );
    final weekly = rows.take(7).map(toPoint).toList();
    final monthly = rows.take(30).map(toPoint).toList();
    return _buildModel(weekly, monthly, rows
        .map((p) => (p['mape'] as num?)?.toDouble())
        .whereType<double>()
        .toList());
  }

  // ----------------------------------------------------------------
  // Sumber 2: forecast_results
  // ----------------------------------------------------------------
  static SalesForecastModel _fromResults(
      List<Map<String, dynamic>> rows) {
    SalesForecastPoint toPoint(Map<String, dynamic> r) {
      final raw = (r['target_date'] as String? ?? '');
      final date = raw.length >= 10 ? raw.substring(0, 10) : raw;
      return SalesForecastPoint(
        date: date,
        value: (r['predicted_value'] as num?)?.toDouble() ?? 0.0,
        lowerBound: (r['lower_bound'] as num?)?.toDouble(),
        upperBound: (r['upper_bound'] as num?)?.toDouble(),
      );
    }
    final weekly = rows.take(7).map(toPoint).toList();
    final monthly = rows.take(30).map(toPoint).toList();
    return _buildModel(weekly, monthly, []);
  }

  // ----------------------------------------------------------------
  // Sumber 3: proyeksi sederhana dari sales_daily_summaries
  // ----------------------------------------------------------------
  static SalesForecastModel _fromSalesSummaries(
      List<Map<String, dynamic>> rows) {
    // Ambil omzet harian (gunakan total_omzet atau total_omset)
    double omzetOf(Map<String, dynamic> r) =>
        (r['total_omzet'] as num?)?.toDouble() ??
        (r['total_omset'] as num?)?.toDouble() ??
        0.0;

    // Gunakan 30 entri terbaru untuk menghitung tren
    final recent = rows.length > 30 ? rows.sublist(rows.length - 30) : rows;
    if (recent.isEmpty) {
      return const SalesForecastModel(
        total7Days: 0, total30Days: 0, avg7Days: 0, avg30Days: 0,
        highestDay: '', highestValue: 0, lowestDay: '', lowestValue: 0,
        trendDirection: 'STABLE', confidenceScore: 0, confidenceLevel: '-',
        insights: [], weeklyForecast: [], monthlyForecast: [],
      );
    }

    final last7 = recent.length >= 7
        ? recent.sublist(recent.length - 7)
        : recent;
    final prev7 = recent.length >= 14
        ? recent.sublist(recent.length - 14, recent.length - 7)
        : last7;

    final avg7 = last7.fold<double>(0, (s, r) => s + omzetOf(r)) /
        last7.length;
    final avgPrev7 = prev7.fold<double>(0, (s, r) => s + omzetOf(r)) /
        prev7.length;
    final avg30 =
        recent.fold<double>(0, (s, r) => s + omzetOf(r)) / recent.length;

    // Laju pertumbuhan harian — dibatasi ±1% agar proyeksi tidak turun/naik
    // terlalu drastis di horizon panjang (mingguan/bulanan).
    final rawGrowth =
        avgPrev7 > 0 ? (avg7 - avgPrev7) / (7.0 * avgPrev7) : 0.0;
    final dailyGrowth = rawGrowth.clamp(-0.01, 0.01);

    final now = DateTime.now();
    SalesForecastPoint project(int daysAhead) {
      final date = now.add(Duration(days: daysAhead));
      final dateStr =
          '${date.year}-${date.month.toString().padLeft(2, '0')}-'
          '${date.day.toString().padLeft(2, '0')}';
      // Nilai proyeksi tidak boleh lebih dari ±25% dari avg7
      final v = (avg7 * (1 + dailyGrowth * daysAhead))
          .clamp(avg7 * 0.75, avg7 * 1.25);
      // CI tidak diset — data ini proyeksi historis, bukan output model ML.
      return SalesForecastPoint(date: dateStr, value: v);
    }

    final weekly = List.generate(7, (i) => project(i + 1));
    final monthly = List.generate(30, (i) => project(i + 1));

    final total7 = weekly.fold<double>(0, (s, p) => s + p.value);
    final total30 = monthly.fold<double>(0, (s, p) => s + p.value);

    // std dev dari data historis → confidence
    final mean = avg30;
    final variance = recent.fold<double>(
            0, (s, r) => s + math.pow(omzetOf(r) - mean, 2).toDouble()) /
        recent.length;
    final stdDev = math.sqrt(variance);
    final cv = mean > 0 ? stdDev / mean : 0.5;
    final confScore = ((1 - cv) * 100).clamp(50.0, 95.0);
    final confLevel =
        confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final pctChange = avgPrev7 > 0 ? (avg7 - avgPrev7) / avgPrev7 * 100 : 0.0;
    final trend = pctChange > 1
        ? 'UPWARD'
        : pctChange < -1
            ? 'DOWNWARD'
            : 'STABLE';

    return SalesForecastModel(
      total7Days: total7,
      total30Days: total30,
      avg7Days: avg7,
      avg30Days: avg30,
      highestDay: weekly.reduce((a, b) => a.value > b.value ? a : b).date,
      highestValue:
          weekly.reduce((a, b) => a.value > b.value ? a : b).value,
      lowestDay: weekly.reduce((a, b) => a.value < b.value ? a : b).date,
      lowestValue:
          weekly.reduce((a, b) => a.value < b.value ? a : b).value,
      trendDirection: trend,
      confidenceScore: confScore,
      confidenceLevel: confLevel,
      insights: [
        'Proyeksi dihitung dari rata-rata penjualan ${recent.length} hari terakhir '
            '(${formatRupiah(avg7)}/hari).',
        if (trend == 'UPWARD')
          'Tren penjualan menunjukkan kenaikan '
              '${pctChange.abs().toStringAsFixed(1)}% per minggu.',
        if (trend == 'DOWNWARD')
          'Tren penjualan menunjukkan penurunan '
              '${pctChange.abs().toStringAsFixed(1)}% per minggu.',
        'Data historis tersedia: ${recent.length} hari. '
            'Akurasi proyeksi: ${confScore.toStringAsFixed(0)}%.',
      ],
      weeklyForecast: weekly,
      monthlyForecast: monthly,
      isProjection: true,
    );
  }

  // ----------------------------------------------------------------
  // Builder bersama untuk stat summary
  // ----------------------------------------------------------------
  static SalesForecastModel _buildModel(
    List<SalesForecastPoint> weekly,
    List<SalesForecastPoint> monthly,
    List<double> mapes,
  ) {
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
      final first = weekly
          .sublist(0, mid)
          .fold<double>(0, (s, p) => s + p.value);
      final second =
          weekly.sublist(mid).fold<double>(0, (s, p) => s + p.value);
      if (second > first) {
        trend = 'UPWARD';
      } else if (second < first) {
        trend = 'DOWNWARD';
      }
    }

    final avgMape = mapes.isEmpty
        ? 15.0
        : mapes.fold<double>(0, (s, v) => s + v) / mapes.length;
    final confScore = (100.0 - avgMape).clamp(0.0, 100.0);
    final confLevel =
        confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final insights = <String>[];
    if (highest != null && highest.value > 0) {
      insights.add(
          'Puncak penjualan diprediksi pada ${highest.date} '
          '(${formatRupiah(highest.value)}).');
    }
    if (trend == 'UPWARD') {
      insights.add(
          'Tren penjualan menunjukkan peningkatan dalam periode prediksi.');
    } else if (trend == 'DOWNWARD') {
      insights.add(
          'Tren penjualan menunjukkan penurunan dalam periode prediksi.');
    }
    if (mapes.isNotEmpty) {
      insights.add(
          'Akurasi model: MAPE ${avgMape.toStringAsFixed(1)}%, '
          'kepercayaan ${confScore.toStringAsFixed(1)}%.');
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

  /// Kompatibilitas dengan pemanggil lama (dashboard mini card).
  factory SalesForecastModel.fromPredictionList(List<dynamic> rawList) =>
      SalesForecastModel.fromSources(rawList, [], []);
}
