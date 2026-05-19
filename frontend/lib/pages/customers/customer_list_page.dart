import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/customer_model.dart';

class CustomerListPage extends StatefulWidget {
  const CustomerListPage({super.key});

  @override
  State<CustomerListPage> createState() =>
      _CustomerListPageState();
}

class _CustomerListPageState
    extends State<CustomerListPage> {
  final ApiService apiService = ApiService();

  late Future<List<CustomerModel>> customers;

  Future<List<CustomerModel>> getCustomers() async {
    final data = await apiService.fetchData(
      'customers',
    );

    return data
        .map<CustomerModel>(
          (e) => CustomerModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    customers = getCustomers();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<CustomerModel>>(
        future: customers,
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
              child: Text(
                'No Customers Found',
              ),
            );
          }

          // Success
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final customer = data[index];

              return Card(
                margin: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                elevation: 4,
                child: Padding(
                  padding:
                      const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 28,
                            child: Text(
                              customer.name
                                  .isNotEmpty
                                  ? customer.name[0]
                                      .toUpperCase()
                                  : '?',
                            ),
                          ),

                          const SizedBox(width: 16),

                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment
                                      .start,
                              children: [
                                Text(
                                  customer.name,
                                  style:
                                      const TextStyle(
                                    fontSize: 18,
                                    fontWeight:
                                        FontWeight
                                            .bold,
                                  ),
                                ),

                                const SizedBox(
                                  height: 4,
                                ),

                                Text(
                                  customer.phone,
                                  style:
                                      const TextStyle(
                                    color:
                                        Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const Divider(
                        height: 24,
                      ),

                      // Store ID
                      const Text(
                        'Store ID:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        customer.mStoreId,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),

                      const SizedBox(height: 12),

                      // Created At
                      const Text(
                        'Created At:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(customer.createdAt),

                      const SizedBox(height: 12),

                      // Customer ID
                      const Text(
                        'Customer ID:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        customer.id,
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