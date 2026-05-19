import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/sales_daily_summary_model.dart';

class SalesDailyPage extends StatefulWidget {
  const SalesDailyPage({super.key});

  @override
  State<SalesDailyPage> createState() =>
      _SalesDailyPageState();
}

class _SalesDailyPageState
    extends State<SalesDailyPage> {
  final ApiService apiService = ApiService();

  late Future<List<SalesDailySummaryModel>>
      sales;

  Future<List<SalesDailySummaryModel>>
      getSales() async {
    final data = await apiService.fetchData(
      'sales-daily-summaries',
    );

    return data
        .map<SalesDailySummaryModel>(
          (e) =>
              SalesDailySummaryModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    sales = getSales();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body:
          FutureBuilder<
              List<SalesDailySummaryModel>>(
        future: sales,
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
              child:
                  Text('No Sales Data Found'),
            );
          }

          // Success
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final sale = data[index];

              return Card(
                margin:
                    const EdgeInsets.symmetric(
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
                        mainAxisAlignment:
                            MainAxisAlignment
                                .spaceBetween,
                        children: [
                          const Text(
                            'Daily Sales',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight:
                                  FontWeight.bold,
                            ),
                          ),

                          Chip(
                            label: Text(
                              '${sale.totalTransaction} Transactions',
                            ),
                            backgroundColor:
                                Colors.indigo
                                    .shade100,
                          ),
                        ],
                      ),

                      const SizedBox(height: 12),

                      // Date
                      const Text(
                        'Date:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(sale.date),

                      const Divider(height: 24),

                      // Financial Data
                      Text(
                        'Total Omzet: Rp ${sale.totalOmzet.toStringAsFixed(0)}',
                        style: const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                          color: Colors.blue,
                        ),
                      ),

                      const SizedBox(height: 6),

                      Text(
                        'Total HPP: Rp ${sale.totalHpp.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Total Profit: Rp ${sale.totalProfit.toStringAsFixed(0)}',
                        style: const TextStyle(
                          color: Colors.green,
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        'Total Regulation: Rp ${sale.totalRegulation.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Total Discount: Rp ${sale.totalDiscount.toStringAsFixed(0)}',
                      ),

                      Text(
                        'Total Rounding: Rp ${sale.totalRounding.toStringAsFixed(0)}',
                      ),

                      const Divider(height: 24),

                      // Store ID
                      const Text(
                        'Store ID:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        sale.mStoreId,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),

                      const SizedBox(height: 12),

                      // Summary ID
                      const Text(
                        'Summary ID:',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        sale.id,
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