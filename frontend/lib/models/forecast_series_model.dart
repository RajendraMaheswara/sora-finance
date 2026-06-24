// ============================================================================
// FORECAST SERIES MODEL (shared)
// ----------------------------------------------------------------------------
// Sumber data prediksi sekarang berasal dari dua tabel: `forecast_runs` dan
// `forecast_results` (tabel lama `forecast_predictions` sudah dihapus).
//
// Endpoint `GET /api/forecast-results` mengembalikan SEMUA baris hasil dari
// SEMUA run yang tergabung jadi satu array, dibedakan hanya oleh `run_id`.
// Forecast service membuat run TERPISAH per granularitas:
//   - run harian   -> ~30 titik (jarak antar tanggal ±1 hari)
//   - run mingguan -> ~4 titik  (jarak ±7 hari)   = kurang lebih 1 bulan
//   - run bulanan  -> ~3 titik  (jarak ±30 hari)
//
// Helper ini mengelompokkan hasil per `run_id`, menebak granularitas tiap run
// dari jarak antar tanggal, lalu mengambil run TERBARU untuk masing-masing
// granularitas. Dengan begitu tampilan "Mingguan" memakai run mingguan asli
// (tidak lagi memotong 30 hari jadi 5 minggu yang melewati 1 bulan).
// ============================================================================

/// Satu titik prediksi dari `forecast_results`.
class ForecastPoint {
  final DateTime date;
  final double value;
  final double? lower;
  final double? upper;
  final int? confidence;
  final String? itemId;
  final String? itemType;

  const ForecastPoint({
    required this.date,
    required this.value,
    this.lower,
    this.upper,
    this.confidence,
    this.itemId,
    this.itemType,
  });

  String get isoDate =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}

enum ForecastGranularity { daily, weekly, monthly }

/// Hasil parsing forecast_results untuk SATU jenis prediksi (mis. seluruh baris
/// sales, atau seluruh baris satu ingredient).
class ForecastResults {
  /// Titik run harian (terurut tanggal naik). Bisa kosong.
  final List<ForecastPoint> daily;

  /// Titik run mingguan asli (tiap titik = 1 minggu). Bisa kosong.
  final List<ForecastPoint> weekly;

  /// Titik run bulanan asli (tiap titik = 1 bulan). Bisa kosong.
  final List<ForecastPoint> monthly;

  const ForecastResults({
    required this.daily,
    required this.weekly,
    required this.monthly,
  });

  static const empty = ForecastResults(daily: [], weekly: [], monthly: []);

  bool get isEmpty => daily.isEmpty && weekly.isEmpty && monthly.isEmpty;

  /// Mingguan efektif: pakai run mingguan asli; bila tidak ada, agregasi run
  /// harian menjadi minggu-minggu yang DIBATASI pada bulan pertama saja
  /// (supaya tampilan mingguan tidak pernah melebihi 1 bulan).
  List<ForecastPoint> get effectiveWeekly =>
      weekly.isNotEmpty ? weekly : weeksFromDaily(daily);

  /// Bulanan efektif: pakai run bulanan asli; bila tidak ada, agregasi run
  /// harian per bulan kalender.
  List<ForecastPoint> get effectiveMonthly =>
      monthly.isNotEmpty ? monthly : monthsFromDaily(daily);

  // --------------------------------------------------------------------------
  // PARSING
  // --------------------------------------------------------------------------

  /// [rows] adalah baris forecast_results yang SUDAH difilter ke satu jenis
  /// (mis. hanya item_type 'sales', atau hanya satu item_id ingredient).
  factory ForecastResults.fromRows(List<Map<String, dynamic>> rows) {
    final byRun = <int, List<ForecastPoint>>{};
    for (final r in rows) {
      final runId = (r['run_id'] as num?)?.toInt();
      final date = parseDate(r['target_date']);
      if (runId == null || date == null) continue;
      byRun.putIfAbsent(runId, () => []).add(ForecastPoint(
            date: date,
            value: (r['predicted_value'] as num?)?.toDouble() ?? 0.0,
            lower: (r['lower_bound'] as num?)?.toDouble(),
            upper: (r['upper_bound'] as num?)?.toDouble(),
            confidence: (r['confidence_level'] as num?)?.toInt(),
            itemId: r['item_id'] as String?,
            itemType: r['item_type'] as String?,
          ));
    }
    if (byRun.isEmpty) return empty;

    for (final list in byRun.values) {
      list.sort((a, b) => a.date.compareTo(b.date));
    }

    // Pilih run TERPADAT per granularitas. Penting: run bulanan sering hanya
    // berisi 1 titik, dan kalau run_id-nya lebih besar dari run harian (30
    // titik) ia tidak boleh menimpa daily. Jadi jumlah titik terbanyak menang;
    // bila seri jumlahnya sama, run_id lebih baru (iterasi menaik) yang menang.
    final ptsByGran = <ForecastGranularity, List<ForecastPoint>>{};
    final countByGran = <ForecastGranularity, int>{};
    final runIds = byRun.keys.toList()..sort();
    for (final runId in runIds) {
      final pts = byRun[runId]!;
      final g = _classify(pts);
      if (pts.length >= (countByGran[g] ?? -1)) {
        ptsByGran[g] = pts;
        countByGran[g] = pts.length;
      }
    }

    return ForecastResults(
      daily: ptsByGran[ForecastGranularity.daily] ?? const [],
      weekly: ptsByGran[ForecastGranularity.weekly] ?? const [],
      monthly: ptsByGran[ForecastGranularity.monthly] ?? const [],
    );
  }

  /// Tebak granularitas run dari median jarak antar tanggal (dalam hari).
  static ForecastGranularity _classify(List<ForecastPoint> pts) {
    // Run 1 titik tak bisa diukur jaraknya. Run forecast bulanan memang sering
    // hanya 1 titik, jadi anggap bulanan (paling kasar) — bukan harian — supaya
    // tidak salah menimpa run harian yang padat.
    if (pts.length < 2) return ForecastGranularity.monthly;
    final deltas = <int>[];
    for (var i = 1; i < pts.length; i++) {
      deltas.add(pts[i].date.difference(pts[i - 1].date).inDays.abs());
    }
    deltas.sort();
    final median = deltas[deltas.length ~/ 2];
    if (median >= 20) return ForecastGranularity.monthly;
    if (median >= 5) return ForecastGranularity.weekly;
    return ForecastGranularity.daily;
  }

  // --------------------------------------------------------------------------
  // AGREGASI FALLBACK (dari run harian)
  // --------------------------------------------------------------------------

  /// Pecah titik harian jadi minggu 7-harian, DIBATASI pada bulan pertama.
  static List<ForecastPoint> weeksFromDaily(List<ForecastPoint> daily) {
    if (daily.isEmpty) return const [];
    final firstMonth = _ym(daily.first.date);
    final monthDays =
        daily.where((p) => _ym(p.date) == firstMonth).toList();
    final out = <ForecastPoint>[];
    for (var i = 0; i < monthDays.length; i += 7) {
      out.add(_sumChunk(
          monthDays.sublist(i, (i + 7).clamp(0, monthDays.length))));
    }
    return out;
  }

  /// Kelompokkan titik harian per bulan kalender.
  static List<ForecastPoint> monthsFromDaily(List<ForecastPoint> daily) {
    if (daily.isEmpty) return const [];
    final byMonth = <String, List<ForecastPoint>>{};
    for (final p in daily) {
      byMonth.putIfAbsent(_ym(p.date), () => []).add(p);
    }
    final keys = byMonth.keys.toList()..sort();
    return keys.map((k) => _sumChunk(byMonth[k]!)).toList();
  }

  static ForecastPoint _sumChunk(List<ForecastPoint> chunk) {
    final value = chunk.fold<double>(0, (s, p) => s + p.value);
    final allLower = chunk.every((p) => p.lower != null);
    final allUpper = chunk.every((p) => p.upper != null);
    final confs =
        chunk.where((p) => p.confidence != null).map((p) => p.confidence!);
    return ForecastPoint(
      date: chunk.first.date,
      value: value,
      lower: allLower ? chunk.fold<double>(0, (s, p) => s + p.lower!) : null,
      upper: allUpper ? chunk.fold<double>(0, (s, p) => s + p.upper!) : null,
      confidence: confs.isEmpty
          ? null
          : (confs.reduce((a, b) => a + b) / confs.length).round(),
    );
  }

  static String _ym(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}';
}

// ============================================================================
// HELPER TOP-LEVEL
// ============================================================================

/// Parse `target_date` yang bisa berupa RFC3339 ("2026-06-24T00:00:00Z")
/// atau tanggal polos ("2026-06-24").
DateTime? parseDate(dynamic raw) {
  if (raw is! String || raw.isEmpty) return null;
  final s = raw.length >= 10 ? raw.substring(0, 10) : raw;
  final parts = s.split('-');
  if (parts.length >= 3) {
    final y = int.tryParse(parts[0]);
    final m = int.tryParse(parts[1]);
    final d = int.tryParse(parts[2]);
    if (y != null && m != null && d != null) return DateTime(y, m, d);
  }
  return DateTime.tryParse(raw);
}

/// Filter baris forecast_results ke jenis tertentu berdasarkan `item_type`.
///
/// [keywords] dicocokkan sebagai substring (lower-case). Set [includeNullType]
/// true untuk visitors — pada skema baru baris visitors menyimpan item_type
/// NULL (hanya run-nya yang bertipe 'visitors').
List<Map<String, dynamic>> filterResultsByType(
  List<dynamic>? raw,
  Set<String> keywords, {
  bool includeNullType = false,
}) {
  if (raw == null) return const [];
  return raw
      .whereType<Map>()
      .map((e) => Map<String, dynamic>.from(e))
      .where((e) {
    final t = (e['item_type'] as String? ?? '').trim().toLowerCase();
    if (t.isEmpty) return includeNullType;
    return keywords.any((k) => t.contains(k));
  }).toList();
}

const salesItemTypes = {'sales', 'revenue', 'penjualan', 'omzet', 'omset'};
const visitorItemTypes = {'visitor', 'pengunjung', 'kunjungan'};
const inventoryItemTypes = {
  'ingredient',
  'inventory',
  'stock',
  'stok',
  'bahan'
};
