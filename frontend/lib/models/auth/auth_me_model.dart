class AuthMeModel {
  final String userId;
  final String storeId;
  final String username;
  final String name;
  final int exp;

  AuthMeModel({
    required this.userId,
    required this.storeId,
    required this.username,
    required this.name,
    required this.exp,
  });

  factory AuthMeModel.fromJson(Map<String, dynamic> json) {
    return AuthMeModel(
      userId: json['user_id'] ?? '',
      storeId: json['store_id'] ?? '',
      username: json['username'] ?? '',
      name: json['name'] ?? '',
      exp: json['exp'] ?? 0,
    );
  }
}
