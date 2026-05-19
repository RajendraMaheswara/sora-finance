class MonthlySummaryModel {
  final String id;
  final String mStoreId;
  final String date;

  final double totalCash;
  final double totalRounding;
  final double totalDebit;
  final double totalEwallet;

  final double totalIncome;
  final double totalRegulationOutlet;
  final double totalRegulationCustomer;

  final double totalHpp;
  final double totalDiscount;
  final double totalCostAndExpense;
  final double totalNetIncome;

  final String createdAt;
  final String createdBy;

  MonthlySummaryModel({
    required this.id,
    required this.mStoreId,
    required this.date,
    required this.totalCash,
    required this.totalRounding,
    required this.totalDebit,
    required this.totalEwallet,
    required this.totalIncome,
    required this.totalRegulationOutlet,
    required this.totalRegulationCustomer,
    required this.totalHpp,
    required this.totalDiscount,
    required this.totalCostAndExpense,
    required this.totalNetIncome,
    required this.createdAt,
    required this.createdBy,
  });

  factory MonthlySummaryModel.fromJson(Map<String, dynamic> json) {
    return MonthlySummaryModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      date: json['date'] ?? '',

      totalCash: (json['total_cash'] ?? 0).toDouble(),
      totalRounding: (json['total_rounding'] ?? 0).toDouble(),
      totalDebit: (json['total_debit'] ?? 0).toDouble(),
      totalEwallet: (json['total_ewallet'] ?? 0).toDouble(),

      totalIncome: (json['total_income'] ?? 0).toDouble(),
      totalRegulationOutlet:
          (json['total_regulation_outlet'] ?? 0).toDouble(),
      totalRegulationCustomer:
          (json['total_regulation_customer'] ?? 0).toDouble(),

      totalHpp: (json['total_hpp'] ?? 0).toDouble(),
      totalDiscount: (json['total_discount'] ?? 0).toDouble(),
      totalCostAndExpense:
          (json['total_cost_and_expense'] ?? 0).toDouble(),
      totalNetIncome: (json['total_net_income'] ?? 0).toDouble(),

      createdAt: json['created_at'] ?? '',
      createdBy: json['created_by'] ?? '',
    );
  }
}