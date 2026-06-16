class LoginResponseModel {
  final String token;
  final UserAuthModel user;

  LoginResponseModel({
    required this.token,
    required this.user,
  });

  factory LoginResponseModel.fromJson(Map<String, dynamic> json) {
    return LoginResponseModel(
      token: json['token'] ?? '',
      user: UserAuthModel.fromJson(json['user'] ?? {}),
    );
  }
}

class UserAuthModel {
  final String id;
  final String storeId;
  final String roleId;
  final String username;
  final String name;
  final String email;
  final String storeName;

  UserAuthModel({
    required this.id,
    required this.storeId,
    required this.roleId,
    required this.username,
    required this.name,
    required this.email,
    required this.storeName,
  });

  factory UserAuthModel.fromJson(Map<String, dynamic> json) {
    return UserAuthModel(
      id: json['id'] ?? '',
      storeId: json['store_id'] ?? '',
      roleId: json['role_id'] ?? '',
      username: json['username'] ?? '',
      name: json['name'] ?? '',
      email: json['email'] ?? '',
      storeName: json['store_name'] ?? '',
    );
  }
}