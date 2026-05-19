class SalesDailySummaryModel {
  final String id;
  final String mStoreId;

  final String date;

  final double totalOmzet;
  final double totalHpp;
  final double totalProfit;

  final double totalDiscount;
  final double totalRegulation;

  final int totalTransaction;

  final double totalRounding;

  final String createdAt;
  final String createdBy;

  SalesDailySummaryModel({
    required this.id,
    required this.mStoreId,
    required this.date,
    required this.totalOmzet,
    required this.totalHpp,
    required this.totalProfit,
    required this.totalDiscount,
    required this.totalRegulation,
    required this.totalTransaction,
    required this.totalRounding,
    required this.createdAt,
    required this.createdBy,
  });

  factory SalesDailySummaryModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return SalesDailySummaryModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',

      date: json['date'] ?? '',

      totalOmzet:
          (json['total_omzet'] ?? 0).toDouble(),

      totalHpp:
          (json['total_hpp'] ?? 0).toDouble(),

      totalProfit:
          (json['total_profit'] ?? 0).toDouble(),

      totalDiscount:
          (json['total_discount'] ?? 0).toDouble(),

      totalRegulation:
          (json['total_regulation'] ?? 0)
              .toDouble(),

      totalTransaction:
          json['total_transaction'] ?? 0,

      totalRounding:
          (json['total_rounding'] ?? 0)
              .toDouble(),

      createdAt: json['created_at'] ?? '',
      createdBy: json['created_by'] ?? '',
    );
  }
}