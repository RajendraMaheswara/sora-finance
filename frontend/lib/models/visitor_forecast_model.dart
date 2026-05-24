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
