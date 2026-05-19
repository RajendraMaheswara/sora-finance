class FoodIngredientModel {
  final String id;
  final String mStoreId;
  final String mFoodUnitId;
  final String code;
  final String name;
  final int stockLimit;
  final int unitPrice;
  final String createdAt;
  final String createdBy;

  FoodIngredientModel({
    required this.id,
    required this.mStoreId,
    required this.mFoodUnitId,
    required this.code,
    required this.name,
    required this.stockLimit,
    required this.unitPrice,
    required this.createdAt,
    required this.createdBy,
  });

  factory FoodIngredientModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return FoodIngredientModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      mFoodUnitId:
          json['m_food_unit_id'] ?? '',
      code: json['code'] ?? '',
      name: json['name'] ?? '',
      stockLimit:
          json['stock_limit'] ?? 0,
      unitPrice:
          json['unit_price'] ?? 0,
      createdAt:
          json['created_at'] ?? '',
      createdBy:
          json['created_by'] ?? '',
    );
  }
}