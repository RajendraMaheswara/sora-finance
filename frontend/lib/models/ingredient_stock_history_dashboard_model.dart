class IngredientStockHistoryDashboardModel {
  final String id;
  final String mStoreId;
  final String ingredientName;
  final double quantity;
  final String unit;
  final String createdAt;

  IngredientStockHistoryDashboardModel({
    required this.id,
    required this.mStoreId,
    required this.ingredientName,
    required this.quantity,
    required this.unit,
    required this.createdAt,
  });

  factory IngredientStockHistoryDashboardModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return IngredientStockHistoryDashboardModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      ingredientName:
          json['ingredient_name'] ?? json['name'] ?? '',
      quantity:
          (json['quantity'] as num?)?.toDouble() ?? 0,
      unit: json['unit'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }
}