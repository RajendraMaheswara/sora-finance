class CustomerModel {
  final String id;
  final String mStoreId;

  final String name;
  final String phone;

  final String createdAt;
  final String createdBy;

  CustomerModel({
    required this.id,
    required this.mStoreId,
    required this.name,
    required this.phone,
    required this.createdAt,
    required this.createdBy,
  });

  factory CustomerModel.fromJson(Map<String, dynamic> json) {
    return CustomerModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',

      name: json['name'] ?? '',
      phone: json['phone'] ?? '',

      createdAt: json['created_at'] ?? '',
      createdBy: json['created_by'] ?? '',
    );
  }
}