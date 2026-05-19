class UserModel {
  final String id;
  final String mStoreId;
  final String mRoleAccessId;
  final String mRoleId;
  final int mUserVerificationTypeId;

  final String address;
  final String avatarUrl;
  final String cityOfBirth;
  final String dateOfBirth;

  final String email;
  final String emailVerifiedAt;

  final bool isActive;
  final bool isEmailVerified;
  final bool isPhoneVerified;

  final String name;
  final String nip;
  final String phone;
  final String phoneVerifiedAt;
  final String username;

  final String createdAt;
  final String createdBy;

  final String updatedAt;
  final String updatedBy;

  UserModel({
    required this.id,
    required this.mStoreId,
    required this.mRoleAccessId,
    required this.mRoleId,
    required this.mUserVerificationTypeId,
    required this.address,
    required this.avatarUrl,
    required this.cityOfBirth,
    required this.dateOfBirth,
    required this.email,
    required this.emailVerifiedAt,
    required this.isActive,
    required this.isEmailVerified,
    required this.isPhoneVerified,
    required this.name,
    required this.nip,
    required this.phone,
    required this.phoneVerifiedAt,
    required this.username,
    required this.createdAt,
    required this.createdBy,
    required this.updatedAt,
    required this.updatedBy,
  });

  factory UserModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return UserModel(
      id: json['id'] ?? '',

      mStoreId:
          json['m_store_id'] ?? '',

      mRoleAccessId:
          json['m_role_access_id'] ?? '',

      mRoleId:
          json['m_role_id'] ?? '',

      mUserVerificationTypeId:
          json['m_user_verification_type_id'] ??
              0,

      address:
          json['address'] ?? '',

      avatarUrl:
          json['avatar_url'] ?? '',

      cityOfBirth:
          json['city_of_birth'] ?? '',

      dateOfBirth:
          json['date_of_birth'] ?? '',

      email:
          json['email'] ?? '',

      emailVerifiedAt:
          json['email_verified_at'] ?? '',

      isActive:
          json['is_active'] ?? false,

      isEmailVerified:
          json['is_email_verified'] ??
              false,

      isPhoneVerified:
          json['is_phone_verified'] ??
              false,

      name:
          json['name'] ?? '',

      nip:
          json['nip'] ?? '',

      phone:
          json['phone'] ?? '',

      phoneVerifiedAt:
          json['phone_verified_at'] ?? '',

      username:
          json['username'] ?? '',

      createdAt:
          json['created_at'] ?? '',

      createdBy:
          json['created_by'] ?? '',

      updatedAt:
          json['updated_at'] ?? '',

      updatedBy:
          json['updated_by'] ?? '',
    );
  }
}