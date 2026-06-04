class FinanceDailySummaryDashboardModel {
  final String id;
  final String mStoreId;
  final String date;
  final double totalOmset;
  final double totalHpp;
  final double totalKeuntungan;
  final String createdAt;

  FinanceDailySummaryDashboardModel({
    required this.id,
    required this.mStoreId,
    required this.date,
    required this.totalOmset,
    required this.totalHpp,
    required this.totalKeuntungan,
    required this.createdAt,
  });

  factory FinanceDailySummaryDashboardModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return FinanceDailySummaryDashboardModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      date: json['date'] ?? json['created_at'] ?? '',
      totalOmset:
          (json['total_omset'] as num?)?.toDouble() ?? 0,
      totalHpp:
          (json['total_hpp'] as num?)?.toDouble() ?? 0,
      totalKeuntungan:
          (json['total_keuntungan'] as num?)?.toDouble() ??
          0,
      createdAt: json['created_at'] ?? '',
    );
  }
}