class OrderModel {
  final String id;
  final String mStoreId;
  final String mCustomerId;
  final String mTableId;
  final String mStorePaymentMethodId;
  final int mOrderStatusId;
  final int mOrderPaymentStatusId;
  final String mCashierId;

  final String orderNumber;
  final String customerName;
  final String customerPhone;

  final double totalItemPrice;
  final double totalRegulation;
  final double subTotal;

  final double totalAdminDebitFee;
  final double totalAdminEwalletFee;

  final double roundingPrice;
  final double totalPaid;
  final double totalReturn;
  final double totalPrice;

  final String createdAt;
  final String createdBy;

  OrderModel({
    required this.id,
    required this.mStoreId,
    required this.mCustomerId,
    required this.mTableId,
    required this.mStorePaymentMethodId,
    required this.mOrderStatusId,
    required this.mOrderPaymentStatusId,
    required this.mCashierId,
    required this.orderNumber,
    required this.customerName,
    required this.customerPhone,
    required this.totalItemPrice,
    required this.totalRegulation,
    required this.subTotal,
    required this.totalAdminDebitFee,
    required this.totalAdminEwalletFee,
    required this.roundingPrice,
    required this.totalPaid,
    required this.totalReturn,
    required this.totalPrice,
    required this.createdAt,
    required this.createdBy,
  });

  factory OrderModel.fromJson(Map<String, dynamic> json) {
    return OrderModel(
      id: json['id'] ?? '',
      mStoreId: json['m_store_id'] ?? '',
      mCustomerId: json['m_customer_id'] ?? '',
      mTableId: json['m_table_id'] ?? '',
      mStorePaymentMethodId:
          json['m_store_payment_method_id'] ?? '',
      mOrderStatusId: json['m_order_status_id'] ?? 0,
      mOrderPaymentStatusId:
          json['m_order_payment_status_id'] ?? 0,
      mCashierId: json['m_cashier_id'] ?? '',

      orderNumber: json['order_number'] ?? '',
      customerName: json['customer_name'] ?? '',
      customerPhone: json['customer_phone'] ?? '',

      totalItemPrice:
          (json['total_item_price'] ?? 0).toDouble(),
      totalRegulation:
          (json['total_regulation'] ?? 0).toDouble(),
      subTotal:
          (json['sub_total'] ?? 0).toDouble(),

      totalAdminDebitFee:
          (json['total_admin_debit_fee'] ?? 0).toDouble(),
      totalAdminEwalletFee:
          (json['total_admin_ewallet_fee'] ?? 0).toDouble(),

      roundingPrice:
          (json['rounding_price'] ?? 0).toDouble(),
      totalPaid:
          (json['total_paid'] ?? 0).toDouble(),
      totalReturn:
          (json['total_return'] ?? 0).toDouble(),
      totalPrice:
          (json['total_price'] ?? 0).toDouble(),

      createdAt: json['created_at'] ?? '',
      createdBy: json['created_by'] ?? '',
    );
  }
}