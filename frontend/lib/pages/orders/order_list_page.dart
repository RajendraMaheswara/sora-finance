import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/order_model.dart';

class OrderListPage extends StatefulWidget {
  const OrderListPage({super.key});

  @override
  State<OrderListPage> createState() => _OrderListPageState();
}

class _OrderListPageState extends State<OrderListPage> {
  final ApiService apiService = ApiService();

  late Future<List<OrderModel>> orders;

  Future<List<OrderModel>> getOrders() async {
    final data = await apiService.fetchData('orders');

    return data
        .map<OrderModel>((e) => OrderModel.fromJson(e))
        .toList();
  }

  @override
  void initState() {
    super.initState();
    orders = getOrders();
  }

  Color getPaymentStatusColor(int status) {
    if (status == 200) {
      return Colors.green;
    }
    return Colors.orange;
  }

  String getPaymentStatusText(int status) {
    if (status == 200) {
      return 'Paid';
    }
    return 'Pending';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<OrderModel>>(
        future: orders,
        builder: (context, snapshot) {
          // Loading
          if (snapshot.connectionState ==
              ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          // Error
          if (snapshot.hasError) {
            return Center(
              child: Text(
                'Error: ${snapshot.error}',
              ),
            );
          }

          final data = snapshot.data ?? [];

          // Empty
          if (data.isEmpty) {
            return const Center(
              child: Text('No Orders Found'),
            );
          }

          // Success
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final order = data[index];

              return Card(
                margin: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                elevation: 4,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        mainAxisAlignment:
                            MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            order.orderNumber,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),

                          Chip(
                            label: Text(
                              getPaymentStatusText(
                                order
                                    .mOrderPaymentStatusId,
                              ),
                            ),
                            backgroundColor:
                                getPaymentStatusColor(
                              order
                                  .mOrderPaymentStatusId,
                            ).withOpacity(0.2),
                          ),
                        ],
                      ),

                      const SizedBox(height: 12),

                      // Customer
                      Text(
                        'Customer: ${order.customerName}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),

                      const SizedBox(height: 4),

                      Text(
                        'Phone: ${order.customerPhone}',
                      ),

                      const Divider(height: 24),

                      // Price Detail
                      Text(
                        'Subtotal: Rp ${order.subTotal.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Total Item: Rp ${order.totalItemPrice.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Regulation: Rp ${order.totalRegulation.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Rounding: Rp ${order.roundingPrice.toStringAsFixed(0)}',
                      ),

                      const SizedBox(height: 8),

                      Text(
                        'Total Paid: Rp ${order.totalPaid.toStringAsFixed(0)}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),

                      Text(
                        'Return: Rp ${order.totalReturn.toStringAsFixed(0)}',
                        style: const TextStyle(
                          color: Colors.red,
                        ),
                      ),

                      const Divider(height: 24),

                      // Footer
                      Text(
                        'Created At:',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),

                      Text(order.createdAt),

                      const SizedBox(height: 8),

                      Text(
                        'Order ID:',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                        ),
                      ),

                      Text(
                        order.id,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}