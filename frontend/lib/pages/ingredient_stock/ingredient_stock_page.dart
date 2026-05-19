import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/ingredient_stock_history_model.dart';

class IngredientStockPage extends StatefulWidget {
  const IngredientStockPage({super.key});

  @override
  State<IngredientStockPage> createState() =>
      _IngredientStockPageState();
}

class _IngredientStockPageState
    extends State<IngredientStockPage> {
  final ApiService apiService = ApiService();

  late Future<List<IngredientStockHistoryModel>>
      ingredientStocks;

  Future<List<IngredientStockHistoryModel>>
      getIngredientStocks() async {
    final data = await apiService.fetchData(
      'ingredient-stock-histories',
    );

    return data
        .map<IngredientStockHistoryModel>(
          (e) =>
              IngredientStockHistoryModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    ingredientStocks = getIngredientStocks();
  }

  String formatCurrency(double value) {
    return 'Rp ${value.toStringAsFixed(0)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<
          List<IngredientStockHistoryModel>>(
        future: ingredientStocks,
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
              child: Text(
                'No ingredient stock history found',
              ),
            );
          }

          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final stock = data[index];

              final isReduced =
                  stock.status == 'reduced';

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
                          CircleAvatar(
                            backgroundColor: isReduced
                                ? Colors.red.shade100
                                : Colors.green.shade100,
                            child: Icon(
                              isReduced
                                  ? Icons.remove
                                  : Icons.add,
                              color: isReduced
                                  ? Colors.red
                                  : Colors.green,
                            ),
                          ),

                          const SizedBox(width: 12),

                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment
                                      .start,
                              children: [
                                Text(
                                  stock.type
                                      .toUpperCase(),
                                  style:
                                      const TextStyle(
                                    fontSize: 18,
                                    fontWeight:
                                        FontWeight.bold,
                                  ),
                                ),
                                Text(
                                  stock.date,
                                  style:
                                      const TextStyle(
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),

                          Chip(
                            label: Text(
                              stock.status,
                            ),
                            backgroundColor: isReduced
                                ? Colors.red.shade100
                                : Colors.green.shade100,
                          ),
                        ],
                      ),

                      const SizedBox(height: 16),

                      buildItem(
                        'Previous Stock',
                        stock.previousStock
                            .toStringAsFixed(2),
                      ),

                      buildItem(
                        'Current Stock',
                        stock.currentStock
                            .toStringAsFixed(2),
                      ),

                      buildItem(
                        'Added',
                        stock.added
                            .toStringAsFixed(2),
                      ),

                      buildItem(
                        'Reduced',
                        stock.reduced
                            .toStringAsFixed(2),
                      ),

                      buildItem(
                        'Stock Change',
                        stock.stockChange
                            .toStringAsFixed(2),
                      ),

                      buildItem(
                        'Unit Price',
                        formatCurrency(
                          stock.unitPrice,
                        ),
                      ),

                      buildItem(
                        'Total Unit Price',
                        formatCurrency(
                          stock.totalUnitPrice,
                        ),
                      ),

                      buildItem(
                        'Remaining Capital',
                        formatCurrency(
                          stock.remainingCapital,
                        ),
                      ),

                      buildItem(
                        'Total Remaining Capital',
                        formatCurrency(
                          stock
                              .totalRemainingCapital,
                        ),
                      ),

                      const SizedBox(height: 12),

                      const Text(
                        'Note',
                        style: TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      const SizedBox(height: 4),

                      Text(stock.note),

                      const Divider(height: 24),

                      Text(
                        'Ingredient ID: ${stock.mFoodIngredientId}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),

                      const SizedBox(height: 4),

                      Text(
                        'Created By: ${stock.createdBy}',
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
            style: const TextStyle(
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}