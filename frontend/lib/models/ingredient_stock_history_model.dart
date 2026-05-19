class IngredientStockHistoryModel {
  final String id;
  final String mStoreId;
  final String mFoodIngredientId;

  final double added;
  final double currentStock;
  final String date;
  final String note;
  final double previousStock;
  final double reduced;

  final double remainingCapital;
  final String status;
  final double stockChange;

  final double totalRemainingCapital;
  final double totalUnitPrice;

  final String type;
  final double unitPrice;

  final String createdAt;
  final String createdBy;

  IngredientStockHistoryModel({
    required this.id,
    required this.mStoreId,
    required this.mFoodIngredientId,
    required this.added,
    required this.currentStock,
    required this.date,
    required this.note,
    required this.previousStock,
    required this.reduced,
    required this.remainingCapital,
    required this.status,
    required this.stockChange,
    required this.totalRemainingCapital,
    required this.totalUnitPrice,
    required this.type,
    required this.unitPrice,
    required this.createdAt,
    required this.createdBy,
  });

  factory IngredientStockHistoryModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return IngredientStockHistoryModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      mFoodIngredientId:
          json['m_food_ingredient_id'] ?? '',

      added: (json['added'] ?? 0).toDouble(),
      currentStock:
          (json['current_stock'] ?? 0).toDouble(),

      date: json['date'] ?? '',
      note: json['note'] ?? '',

      previousStock:
          (json['previous_stock'] ?? 0).toDouble(),

      reduced: (json['reduced'] ?? 0).toDouble(),

      remainingCapital:
          (json['remaining_capital'] ?? 0).toDouble(),

      status: json['status'] ?? '',

      stockChange:
          (json['stock_change'] ?? 0).toDouble(),

      totalRemainingCapital:
          (json['total_remaining_capital'] ?? 0)
              .toDouble(),

      totalUnitPrice:
          (json['total_unit_price'] ?? 0).toDouble(),

      type: json['type'] ?? '',

      unitPrice:
          (json['unit_price'] ?? 0).toDouble(),

      createdAt: json['created_at'] ?? '',
      createdBy: json['created_by'] ?? '',
    );
  }
}