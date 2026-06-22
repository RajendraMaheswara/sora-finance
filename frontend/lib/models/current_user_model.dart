class CurrentUserModel {
  final String id;
  final String name;
  final String username;
  final String email;
  final String avatarUrl;

  CurrentUserModel({
    required this.id,
    required this.name,
    required this.username,
    required this.email,
    required this.avatarUrl,
  });

  factory CurrentUserModel.fromJson(Map<String, dynamic> json) {
    return CurrentUserModel(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      username: json['username'] ?? '',
      email: json['email'] ?? '',
      avatarUrl: json['avatar_url'] ?? '',
    );
  }
}