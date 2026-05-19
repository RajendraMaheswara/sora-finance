class StoreModel {
  final String id;
  final int mSubscriptionTypeId;
  final int coins;
  final String expiredDate;
  final bool isActive;
  final String name;
  final String createdAt;
  final String createdBy;
  final String updatedAt;
  final String updatedBy;
  final bool isTutorialCompleted;
  final int tutorialStep;

  StoreModel({
    required this.id,
    required this.mSubscriptionTypeId,
    required this.coins,
    required this.expiredDate,
    required this.isActive,
    required this.name,
    required this.createdAt,
    required this.createdBy,
    required this.updatedAt,
    required this.updatedBy,
    required this.isTutorialCompleted,
    required this.tutorialStep,
  });

  factory StoreModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return StoreModel(
      id: json['id'] ?? '',
      mSubscriptionTypeId:
          json['m_subscription_type_id'] ?? 0,
      coins: json['coins'] ?? 0,
      expiredDate:
          json['expired_date'] ?? '',
      isActive:
          json['is_active'] ?? false,
      name: json['name'] ?? '',
      createdAt:
          json['created_at'] ?? '',
      createdBy:
          json['created_by'] ?? '',
      updatedAt:
          json['updated_at'] ?? '',
      updatedBy:
          json['updated_by'] ?? '',
      isTutorialCompleted:
          json['is_tutorial_completed'] ??
              false,
      tutorialStep:
          json['tutorial_step'] ?? 0,
    );
  }
}