import 'forecast_series_model.dart';

// ==========================================
// VISITOR FORECAST MODEL
// Mengikuti struktur response endpoint forecast pengunjung:
// {
//   "success": true,
//   "message": "...",
//   "data": {
//     "store_id": "...",
//     "metrics": {...},
//     "forecast_summary": {...},
//     "prediction_analysis": {...},
//     "model_confidence": {...},
//     "insights": [...],
//     "weekly_forecast": [...],
//     "monthly_forecast": [...]
//   }
// }
// ==========================================

class VisitorForecastPoint {
  final String date;
  final int predictedVisitors;
  final double? lower;
  final double? upper;
  final int? confidence;

  VisitorForecastPoint({
    required this.date,
    required this.predictedVisitors,
    this.lower,
    this.upper,
    this.confidence,
  });

  factory VisitorForecastPoint.fromJson(Map<String, dynamic> json) {
    return VisitorForecastPoint(
      date: json['date'] ?? '',
      predictedVisitors: (json['predicted_visitors'] as num?)?.toInt() ?? 0,
    );
  }

  factory VisitorForecastPoint.fromPoint(ForecastPoint p) =>
      VisitorForecastPoint(
        date: p.isoDate,
        predictedVisitors: p.value.round(),
        lower: p.lower,
        upper: p.upper,
        confidence: p.confidence,
      );
}

class VisitorForecastModel {
  final String storeId;

  // forecast_summary
  final int totalNext7Days;
  final int totalNext30Days;
  final double avgDailyNext7Days;
  final double avgDailyNext30Days;

  // prediction_analysis
  final String highestPredictionDay;
  final int highestPredictionValue;
  final String lowestPredictionDay;
  final int lowestPredictionValue;
  final String trendDirection; // UPWARD / DOWNWARD / STABLE

  // model_confidence
  final double confidenceScore;
  final String confidenceLevel;

  final List<String> insights;

  /// Tiap titik = 1 hari (run harian).
  final List<VisitorForecastPoint> dailyForecast;

  /// Tiap titik = 1 minggu (run mingguan native, ±4 minggu = 1 bulan).
  final List<VisitorForecastPoint> weeklyForecast;

  /// Tiap titik = 1 bulan (run bulanan native).
  final List<VisitorForecastPoint> monthlyForecast;

  VisitorForecastModel({
    required this.storeId,
    required this.totalNext7Days,
    required this.totalNext30Days,
    required this.avgDailyNext7Days,
    required this.avgDailyNext30Days,
    required this.highestPredictionDay,
    required this.highestPredictionValue,
    required this.lowestPredictionDay,
    required this.lowestPredictionValue,
    required this.trendDirection,
    required this.confidenceScore,
    required this.confidenceLevel,
    required this.insights,
    required this.weeklyForecast,
    required this.monthlyForecast,
    this.dailyForecast = const [],
  });

  /// Membangun model dari array GET /api/forecast-results (skema run/result).
  factory VisitorForecastModel.fromResults(List<dynamic> rawList) {
    final rows = filterResultsByType(
      rawList,
      visitorItemTypes,
      includeNullType: true,
    );
    final fr = ForecastResults.fromRows(rows);

    final daily = fr.daily.map(VisitorForecastPoint.fromPoint).toList();
    final weekly =
        fr.effectiveWeekly.map(VisitorForecastPoint.fromPoint).toList();
    final monthly =
        fr.effectiveMonthly.map(VisitorForecastPoint.fromPoint).toList();

    // Total & rata-rata mengacu run harian; turunkan dari mingguan/bulanan
    // bila run harian tidak tersedia.
    int total7, total30;
    if (fr.daily.isNotEmpty) {
      total7 = fr.daily.take(7).fold<double>(0, (s, p) => s + p.value).round();
      total30 =
          fr.daily.take(30).fold<double>(0, (s, p) => s + p.value).round();
    } else if (fr.effectiveWeekly.isNotEmpty) {
      total7 = fr.effectiveWeekly.first.value.round();
      total30 =
          fr.effectiveWeekly.fold<double>(0, (s, p) => s + p.value).round();
    } else if (fr.effectiveMonthly.isNotEmpty) {
      total30 = fr.effectiveMonthly.first.value.round();
      total7 = (total30 / 4.345).round();
    } else {
      total7 = 0;
      total30 = 0;
    }
    final days7 =
        fr.daily.isEmpty ? 7 : (fr.daily.length < 7 ? fr.daily.length : 7);
    final days30 =
        fr.daily.isEmpty ? 30 : (fr.daily.length < 30 ? fr.daily.length : 30);
    final avg7 = total7 / days7;
    final avg30 = total30 / days30;

    final basis = daily.isNotEmpty ? daily : weekly;
    VisitorForecastPoint? highest, lowest;
    for (final p in basis) {
      if (highest == null || p.predictedVisitors > highest.predictedVisitors) {
        highest = p;
      }
      if (lowest == null || p.predictedVisitors < lowest.predictedVisitors) {
        lowest = p;
      }
    }

    String trend = 'STABLE';
    if (basis.length >= 4) {
      final mid = basis.length ~/ 2;
      final first = basis
          .sublist(0, mid)
          .fold<int>(0, (s, p) => s + p.predictedVisitors);
      final second =
          basis.sublist(mid).fold<int>(0, (s, p) => s + p.predictedVisitors);
      if (second > first) {
        trend = 'UPWARD';
      } else if (second < first) {
        trend = 'DOWNWARD';
      }
    }

    final confs = (fr.daily.isNotEmpty ? fr.daily : fr.effectiveWeekly)
        .where((p) => p.confidence != null)
        .map((p) => p.confidence!.toDouble())
        .toList();
    final confScore = confs.isEmpty
        ? 80.0
        : (confs.reduce((a, b) => a + b) / confs.length).clamp(0.0, 100.0);
    final confLevel =
        confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final insights = <String>[];
    if (highest != null && highest.predictedVisitors > 0) {
      insights.add('Puncak kunjungan diprediksi pada '
          '${highest.date} dengan ${highest.predictedVisitors} orang.');
    }
    if (trend == 'UPWARD') {
      insights.add(
          'Tren pengunjung menunjukkan peningkatan dalam periode prediksi.');
    } else if (trend == 'DOWNWARD') {
      insights.add(
          'Tren pengunjung menunjukkan penurunan dalam periode prediksi.');
    }
    insights.add('Estimasi $total30 pengunjung dalam 30 hari ke depan '
        '(rata-rata ${avg7.toStringAsFixed(0)} orang/hari).');
    if (confs.isNotEmpty) {
      insights.add('Tingkat kepercayaan model: '
          '${confScore.toStringAsFixed(0)}% ($confLevel).');
    }

    return VisitorForecastModel(
      storeId: '',
      totalNext7Days: total7,
      totalNext30Days: total30,
      avgDailyNext7Days: avg7,
      avgDailyNext30Days: avg30,
      highestPredictionDay: highest?.date ?? '',
      highestPredictionValue: highest?.predictedVisitors ?? 0,
      lowestPredictionDay: lowest?.date ?? '',
      lowestPredictionValue: lowest?.predictedVisitors ?? 0,
      trendDirection: trend,
      confidenceScore: confScore,
      confidenceLevel: confLevel,
      insights: insights,
      dailyForecast: daily,
      weeklyForecast: weekly,
      monthlyForecast: monthly,
    );
  }

  factory VisitorForecastModel.fromJson(Map<String, dynamic> json) {
    final summary = (json['forecast_summary'] as Map?) ?? const {};
    final analysis = (json['prediction_analysis'] as Map?) ?? const {};
    final confidence = (json['model_confidence'] as Map?) ?? const {};

    List<VisitorForecastPoint> parsePoints(dynamic raw) {
      if (raw is! List) return const [];
      return raw
          .whereType<Map>()
          .map(
            (e) => VisitorForecastPoint.fromJson(Map<String, dynamic>.from(e)),
          )
          .toList();
    }

    return VisitorForecastModel(
      storeId: json['store_id'] ?? '',
      totalNext7Days:
          (summary['total_predicted_visitors_next_7_days'] as num?)?.toInt() ??
          0,
      totalNext30Days:
          (summary['total_predicted_visitors_next_30_days'] as num?)?.toInt() ??
          0,
      avgDailyNext7Days:
          (summary['average_daily_visitors_next_7_days'] as num?)?.toDouble() ??
          0,
      avgDailyNext30Days:
          (summary['average_daily_visitors_next_30_days'] as num?)
              ?.toDouble() ??
          0,
      highestPredictionDay: analysis['highest_prediction_day'] ?? '',
      highestPredictionValue:
          (analysis['highest_prediction_value'] as num?)?.toInt() ?? 0,
      lowestPredictionDay: analysis['lowest_prediction_day'] ?? '',
      lowestPredictionValue:
          (analysis['lowest_prediction_value'] as num?)?.toInt() ?? 0,
      trendDirection: analysis['trend_direction'] ?? '',
      confidenceScore:
          (confidence['confidence_score'] as num?)?.toDouble() ?? 0,
      confidenceLevel: confidence['confidence_level'] ?? '',
      insights:
          (json['insights'] as List?)?.whereType<String>().toList() ?? const [],
      weeklyForecast: parsePoints(json['weekly_forecast']),
      monthlyForecast: parsePoints(json['monthly_forecast']),
    );
  }

  /// Persen perubahan rata-rata harian 7 hari ke depan
  /// dibandingkan rata-rata harian 30 hari ke depan.
  double get weeklyChangePercent {
    if (avgDailyNext30Days == 0) return 0;
    return ((avgDailyNext7Days - avgDailyNext30Days) / avgDailyNext30Days) *
        100;
  }

  bool get isTrendUp => trendDirection.toUpperCase() == 'UPWARD';
}
