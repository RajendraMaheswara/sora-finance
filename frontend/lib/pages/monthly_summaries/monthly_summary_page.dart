import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/monthly_summary_model.dart';

class MonthlySummaryPage extends StatefulWidget {
  const MonthlySummaryPage({super.key});

  @override
  State<MonthlySummaryPage> createState() =>
      _MonthlySummaryPageState();
}

class _MonthlySummaryPageState
    extends State<MonthlySummaryPage> {
  final ApiService apiService = ApiService();

  late Future<List<MonthlySummaryModel>> monthlySummaries;

  Future<List<MonthlySummaryModel>> getMonthlySummaries() async {
    final data =
        await apiService.fetchData('monthly-summaries');

    return data
        .map<MonthlySummaryModel>(
          (e) => MonthlySummaryModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    monthlySummaries = getMonthlySummaries();
  }

  String formatCurrency(double value) {
    return 'Rp ${value.toStringAsFixed(0)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<MonthlySummaryModel>>(
        future: monthlySummaries,
        builder: (context, snapshot) {
          if (snapshot.connectionState ==
              ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }

          if (snapshot.hasError) {
            return Center(
              child: Text(
                'Error: ${snapshot.error}',
              ),
            );
          }

          final data = snapshot.data ?? [];

          if (data.isEmpty) {
            return const Center(
              child: Text('No monthly summary found'),
            );
          }

          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final monthly = data[index];

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
                      Row(
                        children: [
                          const Icon(
                            Icons.calendar_month,
                            size: 32,
                            color: Colors.indigo,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Monthly Finance Summary',
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight:
                                        FontWeight.bold,
                                  ),
                                ),
                                Text(
                                  monthly.date,
                                  style: const TextStyle(
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 20),

                      buildItem(
                        'Total Income',
                        formatCurrency(
                            monthly.totalIncome),
                        Colors.green,
                      ),

                      buildItem(
                        'Net Income',
                        formatCurrency(
                            monthly.totalNetIncome),
                        Colors.blue,
                      ),

                      buildItem(
                        'Total HPP',
                        formatCurrency(monthly.totalHpp),
                        Colors.orange,
                      ),

                      buildItem(
                        'Total Cost & Expense',
                        formatCurrency(
                          monthly.totalCostAndExpense,
                        ),
                        Colors.red,
                      ),

                      buildItem(
                        'Total Cash',
                        formatCurrency(
                            monthly.totalCash),
                        Colors.teal,
                      ),

                      buildItem(
                        'Total Debit',
                        formatCurrency(
                            monthly.totalDebit),
                        Colors.purple,
                      ),

                      buildItem(
                        'Total E-Wallet',
                        formatCurrency(
                            monthly.totalEwallet),
                        Colors.indigo,
                      ),

                      buildItem(
                        'Outlet Regulation',
                        formatCurrency(
                          monthly.totalRegulationOutlet,
                        ),
                        Colors.brown,
                      ),

                      buildItem(
                        'Customer Regulation',
                        formatCurrency(
                          monthly
                              .totalRegulationCustomer,
                        ),
                        Colors.deepOrange,
                      ),

                      buildItem(
                        'Total Discount',
                        formatCurrency(
                            monthly.totalDiscount),
                        Colors.pink,
                      ),

                      buildItem(
                        'Total Rounding',
                        formatCurrency(
                            monthly.totalRounding),
                        Colors.grey,
                      ),

                      const Divider(height: 24),

                      Text(
                        'Store ID: ${monthly.mStoreId}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),

                      const SizedBox(height: 4),

                      Text(
                        'Created By: ${monthly.createdBy}',
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

  Widget buildItem(
    String title,
    String value,
    Color color,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment:
            MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w600,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}