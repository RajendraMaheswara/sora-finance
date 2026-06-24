import 'dart:math' as math;

import 'forecast_series_model.dart';

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

  factory SalesForecastPoint.fromPoint(ForecastPoint p) => SalesForecastPoint(
        date: p.isoDate,
        value: p.value,
        lowerBound: p.lower,
        upperBound: p.upper,
      );
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

  /// Tiap titik = 1 hari (run harian, ±30 titik).
  final List<SalesForecastPoint> dailyForecast;

  /// Tiap titik = 1 minggu (run mingguan, ±4 titik = 1 bulan).
  final List<SalesForecastPoint> weeklyForecast;

  /// Tiap titik = 1 bulan (run bulanan, ±3 titik).
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
    required this.dailyForecast,
    required this.weeklyForecast,
    required this.monthlyForecast,
  });

  static const _empty = SalesForecastModel(
    total7Days: 0, total30Days: 0, avg7Days: 0, avg30Days: 0,
    highestDay: '', highestValue: 0, lowestDay: '', lowestValue: 0,
    trendDirection: 'STABLE', confidenceScore: 0, confidenceLevel: '-',
    insights: [], dailyForecast: [], weeklyForecast: [], monthlyForecast: [],
  );

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
  // LOADER: HANYA hasil model nyata dari forecast_results
  // ================================================================
  static Future<SalesForecastModel> loadFromApi(
    Future<List<dynamic>> Function(String) fetchData,
  ) async {
    final results = await fetchData('forecast-results');
    return SalesForecastModel.fromResults(results);
  }

  /// Bangun model hanya dari hasil model nyata di forecast_results
  /// (item_type 'sales'). TIDAK ada proyeksi buatan dari data historis —
  /// kalau belum ada forecast penjualan, kembalikan kosong supaya UI
  /// menampilkan state "belum ada data prediksi".
  factory SalesForecastModel.fromResults(List<dynamic> results) {
    final rows = filterResultsByType(results, salesItemTypes);
    if (rows.isEmpty) return _empty;
    final fr = ForecastResults.fromRows(rows);
    if (fr.isEmpty) return _empty;
    return _fromForecast(fr);
  }

  // ----------------------------------------------------------------
  // Sumber utama: forecast_results (run harian/mingguan/bulanan)
  // ----------------------------------------------------------------
  static SalesForecastModel _fromForecast(ForecastResults fr) {
    final daily = fr.daily.map(SalesForecastPoint.fromPoint).toList();
    final weekly = fr.effectiveWeekly.map(SalesForecastPoint.fromPoint).toList();
    final monthly =
        fr.effectiveMonthly.map(SalesForecastPoint.fromPoint).toList();

    // Total/average mengacu ke run harian bila ada; jika tidak, turunkan dari
    // run mingguan/bulanan.
    double total7, total30;
    if (fr.daily.isNotEmpty) {
      total7 = fr.daily.take(7).fold<double>(0, (s, p) => s + p.value);
      total30 = fr.daily.take(30).fold<double>(0, (s, p) => s + p.value);
    } else if (fr.effectiveWeekly.isNotEmpty) {
      total7 = fr.effectiveWeekly.first.value;
      total30 = fr.effectiveWeekly.fold<double>(0, (s, p) => s + p.value);
    } else if (fr.effectiveMonthly.isNotEmpty) {
      total30 = fr.effectiveMonthly.first.value;
      total7 = total30 / 4.345;
    } else {
      total7 = 0;
      total30 = 0;
    }
    final days7 = fr.daily.isEmpty ? 7 : math.min(7, fr.daily.length);
    final days30 = fr.daily.isEmpty ? 30 : math.min(30, fr.daily.length);
    final avg7 = total7 / days7;
    final avg30 = total30 / days30;

    // Puncak & terendah dari run harian (atau mingguan sebagai cadangan).
    final basis = fr.daily.isNotEmpty ? fr.daily : fr.effectiveWeekly;
    ForecastPoint? highest, lowest;
    for (final p in basis) {
      if (highest == null || p.value > highest.value) highest = p;
      if (lowest == null || p.value < lowest.value) lowest = p;
    }

    final trend = _trendOf(basis.map((p) => p.value).toList());

    final confs = basis
        .where((p) => p.confidence != null)
        .map((p) => p.confidence!.toDouble())
        .toList();
    final confScore = confs.isEmpty
        ? 80.0
        : (confs.reduce((a, b) => a + b) / confs.length).clamp(0.0, 100.0);
    final confLevel =
        confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final insights = <String>[];
    if (highest != null && highest.value > 0) {
      insights.add('Puncak penjualan diprediksi pada '
          '${_human(highest.isoDate)} (${formatRupiah(highest.value)}).');
    }
    if (trend == 'UPWARD') {
      insights.add('Tren penjualan menunjukkan peningkatan dalam periode prediksi.');
    } else if (trend == 'DOWNWARD') {
      insights.add('Tren penjualan menunjukkan penurunan dalam periode prediksi.');
    }
    insights.add('Estimasi penjualan 30 hari ke depan: '
        '${formatRupiah(total30)} (rata-rata ${formatRupiah(avg7)}/hari).');
    if (confs.isNotEmpty) {
      insights.add('Tingkat kepercayaan model: '
          '${confScore.toStringAsFixed(0)}% ($confLevel).');
    }

    return SalesForecastModel(
      total7Days: total7,
      total30Days: total30,
      avg7Days: avg7,
      avg30Days: avg30,
      highestDay: highest?.isoDate ?? '',
      highestValue: highest?.value ?? 0,
      lowestDay: lowest?.isoDate ?? '',
      lowestValue: lowest?.value ?? 0,
      trendDirection: trend,
      confidenceScore: confScore,
      confidenceLevel: confLevel,
      insights: insights,
      dailyForecast: daily,
      weeklyForecast: weekly,
      monthlyForecast: monthly,
    );
  }

  // ----------------------------------------------------------------
  // Util
  // ----------------------------------------------------------------
  static String _trendOf(List<double> values) {
    if (values.length < 4) return 'STABLE';
    final mid = values.length ~/ 2;
    final first = values.sublist(0, mid).fold<double>(0, (s, v) => s + v);
    final second = values.sublist(mid).fold<double>(0, (s, v) => s + v);
    if (second > first) return 'UPWARD';
    if (second < first) return 'DOWNWARD';
    return 'STABLE';
  }

  static const _months = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mei', 6: 'Jun',
    7: 'Jul', 8: 'Agu', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Des',
  };

  static String _human(String iso) {
    final d = parseDate(iso);
    if (d == null) return iso;
    return '${d.day} ${_months[d.month]} ${d.year}';
  }
}
