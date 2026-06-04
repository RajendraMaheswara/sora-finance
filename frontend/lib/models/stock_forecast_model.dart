class StockForecastPoint {
  final String date;
  final double quantity;
  final double? lowerBound;
  final double? upperBound;

  const StockForecastPoint({
    required this.date,
    required this.quantity,
    this.lowerBound,
    this.upperBound,
  });
}

class StockItemSummary {
  final String itemId;
  final String itemType;
  final double totalPredicted;
  final double avgPredicted;

  const StockItemSummary({
    required this.itemId,
    required this.itemType,
    required this.totalPredicted,
    required this.avgPredicted,
  });
}

class StockForecastModel {
  final double totalQuantity7Days;
  final double totalQuantity30Days;
  final double avgDailyQuantity;
  final double confidenceScore;
  final String confidenceLevel;
  final String trendDirection;
  final List<String> insights;
  final List<StockForecastPoint> weeklyForecast;
  final List<StockForecastPoint> monthlyForecast;
  final List<StockItemSummary> itemBreakdown;

  const StockForecastModel({
    required this.totalQuantity7Days,
    required this.totalQuantity30Days,
    required this.avgDailyQuantity,
    required this.confidenceScore,
    required this.confidenceLevel,
    required this.trendDirection,
    required this.insights,
    required this.weeklyForecast,
    required this.monthlyForecast,
    required this.itemBreakdown,
  });

  double get weeklyChangePercent {
    if (totalQuantity30Days == 0) return 0;
    final avg30 = totalQuantity30Days / 30;
    return ((avgDailyQuantity - avg30) / avg30) * 100;
  }

  /// Bangun dari forecast_predictions (filter stok) + forecast_results (detail item).
  factory StockForecastModel.fromSources(
    List<dynamic> predictions,
    List<dynamic> results,
  ) {
    const stockKeywords = ['inventory', 'stock', 'stok', 'inventaris', 'gudang'];

    final allPred = predictions
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    var filtered = allPred.where((e) {
      final m = (e['module'] as String? ?? '').toLowerCase();
      return stockKeywords.any((k) => m.contains(k));
    }).toList();

    final allResults = results
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    // Jika tidak ada prediksi stok khusus, gunakan forecast_results sebagai sumber utama
    final bool usingResults = filtered.isEmpty && allResults.isNotEmpty;
    if (usingResults) filtered = [];

    filtered.sort((a, b) => (a['prediction_date'] as String? ?? '')
        .compareTo(b['prediction_date'] as String? ?? ''));

    allResults.sort((a, b) =>
        (a['target_date'] as String? ?? '').compareTo(b['target_date'] as String? ?? ''));

    StockForecastPoint predToPoint(Map<String, dynamic> p) => StockForecastPoint(
          date: p['prediction_date'] ?? '',
          quantity: (p['predicted_value'] as num?)?.toDouble() ?? 0.0,
          lowerBound: (p['lower_bound'] as num?)?.toDouble(),
          upperBound: (p['upper_bound'] as num?)?.toDouble(),
        );

    StockForecastPoint resultToPoint(Map<String, dynamic> r) {
      final raw = (r['target_date'] as String? ?? '');
      final date = raw.length >= 10 ? raw.substring(0, 10) : raw;
      return StockForecastPoint(
        date: date,
        quantity: (r['predicted_value'] as num?)?.toDouble() ?? 0.0,
        lowerBound: (r['lower_bound'] as num?)?.toDouble(),
        upperBound: (r['upper_bound'] as num?)?.toDouble(),
      );
    }

    final List<StockForecastPoint> weekly;
    final List<StockForecastPoint> monthly;

    if (usingResults) {
      weekly = allResults.take(7).map(resultToPoint).toList();
      monthly = allResults.take(30).map(resultToPoint).toList();
    } else if (filtered.isNotEmpty) {
      weekly = filtered.take(7).map(predToPoint).toList();
      monthly = filtered.take(30).map(predToPoint).toList();
    } else {
      // Fallback: semua prediksi tanpa filter
      final fallback = allPred
        ..sort((a, b) => (a['prediction_date'] as String? ?? '')
            .compareTo(b['prediction_date'] as String? ?? ''));
      weekly = fallback.take(7).map(predToPoint).toList();
      monthly = fallback.take(30).map(predToPoint).toList();
    }

    // Item breakdown dari forecast_results
    final itemMap = <String, List<double>>{};
    final itemTypeMap = <String, String>{};
    for (final r in allResults) {
      final itemId = r['item_id'] as String?;
      if (itemId != null && itemId.isNotEmpty) {
        itemMap.putIfAbsent(itemId, () => []);
        itemMap[itemId]!.add((r['predicted_value'] as num?)?.toDouble() ?? 0.0);
        itemTypeMap[itemId] = r['item_type'] as String? ?? '';
      }
    }

    final itemBreakdown = itemMap.entries.map((e) {
      final total = e.value.fold<double>(0, (s, v) => s + v);
      return StockItemSummary(
        itemId: e.key,
        itemType: itemTypeMap[e.key] ?? '',
        totalPredicted: total,
        avgPredicted: e.value.isEmpty ? 0 : total / e.value.length,
      );
    }).toList()
      ..sort((a, b) => b.totalPredicted.compareTo(a.totalPredicted));

    final total7 = weekly.fold<double>(0, (s, p) => s + p.quantity);
    final total30 = monthly.fold<double>(0, (s, p) => s + p.quantity);
    final avg7 = weekly.isEmpty ? 0.0 : total7 / weekly.length;

    String trend = 'STABLE';
    if (weekly.length >= 4) {
      final mid = weekly.length ~/ 2;
      final first = weekly.sublist(0, mid).fold<double>(0, (s, p) => s + p.quantity);
      final second = weekly.sublist(mid).fold<double>(0, (s, p) => s + p.quantity);
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
    final confLevels = allResults
        .map((r) => (r['confidence_level'] as num?)?.toDouble())
        .whereType<double>()
        .toList();

    double confScore;
    if (mapes.isNotEmpty) {
      final avgMape = mapes.fold<double>(0, (s, v) => s + v) / mapes.length;
      confScore = (100.0 - avgMape).clamp(0.0, 100.0);
    } else if (confLevels.isNotEmpty) {
      confScore = confLevels.fold<double>(0, (s, v) => s + v) / confLevels.length;
    } else {
      confScore = 80.0;
    }
    final confLevel = confScore >= 85 ? 'Tinggi' : confScore >= 70 ? 'Sedang' : 'Rendah';

    final insights = <String>[];
    if (itemBreakdown.isNotEmpty) {
      insights.add(
          'Terdapat ${itemBreakdown.length} item dengan data prediksi stok tersedia.');
      if (itemBreakdown.first.totalPredicted > 0) {
        insights.add(
            'Kebutuhan tertinggi: ${itemBreakdown.first.itemId} (${itemBreakdown.first.totalPredicted.toStringAsFixed(0)} unit total).');
      }
    }
    if (trend == 'UPWARD') {
      insights.add('Prediksi kebutuhan stok menunjukkan tren peningkatan.');
    } else if (trend == 'DOWNWARD') {
      insights.add('Prediksi kebutuhan stok menunjukkan tren penurunan.');
    }
    if (weekly.isEmpty && monthly.isEmpty) {
      insights.add('Belum ada data prediksi stok di database.');
    }

    return StockForecastModel(
      totalQuantity7Days: total7,
      totalQuantity30Days: total30,
      avgDailyQuantity: avg7,
      confidenceScore: confScore,
      confidenceLevel: confLevel,
      trendDirection: trend,
      insights: insights,
      weeklyForecast: weekly,
      monthlyForecast: monthly,
      itemBreakdown: itemBreakdown,
    );
  }
}
