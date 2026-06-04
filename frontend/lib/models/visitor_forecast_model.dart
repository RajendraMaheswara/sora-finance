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

  VisitorForecastPoint({required this.date, required this.predictedVisitors});

  factory VisitorForecastPoint.fromJson(Map<String, dynamic> json) {
    return VisitorForecastPoint(
      date: json['date'] ?? '',
      predictedVisitors: (json['predicted_visitors'] as num?)?.toInt() ?? 0,
    );
  }
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
  final List<VisitorForecastPoint> weeklyForecast;
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
  });

  /// Membangun model dari response array GET /api/forecast-predictions.
  factory VisitorForecastModel.fromPredictionList(List<dynamic> rawList) {
    const visitorKeywords = ['visitor', 'pengunjung', 'kunjungan'];

    var all = rawList
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    // Coba filter berdasarkan modul visitor; fallback ke semua data
    final visitorFiltered = all.where((e) {
      final m = (e['module'] as String? ?? '').toLowerCase();
      return visitorKeywords.any((k) => m.contains(k));
    }).toList();
    if (visitorFiltered.isNotEmpty) all = visitorFiltered;

    all.sort((a, b) => (a['prediction_date'] as String? ?? '')
        .compareTo(b['prediction_date'] as String? ?? ''));

    List<VisitorForecastPoint> toPoints(List<Map<String, dynamic>> preds) =>
        preds
            .map((p) => VisitorForecastPoint(
                  date: p['prediction_date'] ?? '',
                  predictedVisitors:
                      (p['predicted_value'] as num?)?.toInt() ?? 0,
                ))
            .toList();

    final weeklyData = all.take(7).toList();
    final monthlyData = all.take(30).toList();

    final weeklyPoints = toPoints(weeklyData);
    final monthlyPoints = toPoints(monthlyData);

    final total7 =
        weeklyPoints.fold<int>(0, (s, p) => s + p.predictedVisitors);
    final total30 =
        monthlyPoints.fold<int>(0, (s, p) => s + p.predictedVisitors);

    final avg7 = weeklyPoints.isEmpty ? 0.0 : total7 / weeklyPoints.length;
    final avg30 =
        monthlyPoints.isEmpty ? 0.0 : total30 / monthlyPoints.length;

    VisitorForecastPoint? highest, lowest;
    for (final p in weeklyPoints) {
      if (highest == null || p.predictedVisitors > highest.predictedVisitors) {
        highest = p;
      }
      if (lowest == null || p.predictedVisitors < lowest.predictedVisitors) {
        lowest = p;
      }
    }

    String trendDirection = 'STABLE';
    if (weeklyPoints.length >= 4) {
      final mid = weeklyPoints.length ~/ 2;
      final firstHalf = weeklyPoints
          .sublist(0, mid)
          .fold<int>(0, (s, p) => s + p.predictedVisitors);
      final secondHalf = weeklyPoints
          .sublist(mid)
          .fold<int>(0, (s, p) => s + p.predictedVisitors);
      if (secondHalf > firstHalf) {
        trendDirection = 'UPWARD';
      } else if (secondHalf < firstHalf) {
        trendDirection = 'DOWNWARD';
      }
    }

    final mapes = all
        .map((p) => (p['mape'] as num?)?.toDouble())
        .whereType<double>()
        .toList();
    final avgMape = mapes.isEmpty
        ? 15.0
        : mapes.fold<double>(0, (s, v) => s + v) / mapes.length;
    final confidenceScore = (100.0 - avgMape).clamp(0.0, 100.0);
    final confidenceLevel = confidenceScore >= 85
        ? 'Tinggi'
        : confidenceScore >= 70
            ? 'Sedang'
            : 'Rendah';

    final insights = <String>[];
    if (highest != null && highest.predictedVisitors > 0) {
      insights.add(
          'Puncak kunjungan diprediksi pada ${highest.date} dengan ${highest.predictedVisitors} orang.');
    }
    if (trendDirection == 'UPWARD') {
      insights.add(
          'Tren pengunjung menunjukkan peningkatan dalam periode prediksi.');
    } else if (trendDirection == 'DOWNWARD') {
      insights.add(
          'Tren pengunjung menunjukkan penurunan dalam periode prediksi.');
    }
    if (mapes.isNotEmpty) {
      insights.add(
          'Akurasi model: MAPE rata-rata ${avgMape.toStringAsFixed(1)}%, tingkat kepercayaan ${confidenceScore.toStringAsFixed(1)}%.');
    }

    final storeId =
        all.isNotEmpty ? (all.first['store_id'] as String? ?? '') : '';

    return VisitorForecastModel(
      storeId: storeId,
      totalNext7Days: total7,
      totalNext30Days: total30,
      avgDailyNext7Days: avg7,
      avgDailyNext30Days: avg30,
      highestPredictionDay: highest?.date ?? '',
      highestPredictionValue: highest?.predictedVisitors ?? 0,
      lowestPredictionDay: lowest?.date ?? '',
      lowestPredictionValue: lowest?.predictedVisitors ?? 0,
      trendDirection: trendDirection,
      confidenceScore: confidenceScore,
      confidenceLevel: confidenceLevel,
      insights: insights,
      weeklyForecast: weeklyPoints,
      monthlyForecast: monthlyPoints,
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
