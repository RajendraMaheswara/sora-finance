import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/food_ingredient_model.dart';

class FoodIngredientListPage
    extends StatefulWidget {
  const FoodIngredientListPage({
    super.key,
  });

  @override
  State<FoodIngredientListPage>
      createState() =>
          _FoodIngredientListPageState();
}

class _FoodIngredientListPageState
    extends State<FoodIngredientListPage> {
  final ApiService apiService =
      ApiService();

  late Future<List<FoodIngredientModel>>
      ingredients;

  Future<List<FoodIngredientModel>>
      getIngredients() async {
    final data =
        await apiService.fetchData(
      'food-ingredients',
    );

    return data
        .map<FoodIngredientModel>(
          (e) =>
              FoodIngredientModel.fromJson(
            e,
          ),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    ingredients = getIngredients();
  }

  String formatRupiah(int value) {
    return 'Rp $value';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body:
          FutureBuilder<
              List<FoodIngredientModel>>(
        future: ingredients,
        builder: (context, snapshot) {
          // loading
          if (snapshot.connectionState ==
              ConnectionState.waiting) {
            return const Center(
              child:
                  CircularProgressIndicator(),
            );
          }

          // error
          if (snapshot.hasError) {
            return Center(
              child: Text(
                'Error: ${snapshot.error}',
              ),
            );
          }

          final data =
              snapshot.data ?? [];

          // kosong
          if (data.isEmpty) {
            return const Center(
              child: Text(
                'No ingredients found',
              ),
            );
          }

          // list
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final ingredient =
                  data[index];

              return Card(
                margin:
                    const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                elevation: 4,
                child: Padding(
                  padding:
                      const EdgeInsets.all(
                    16,
                  ),
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment
                            .start,
                    children: [
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 28,
                            child: Text(
                              ingredient.name[0]
                                  .toUpperCase(),
                              style:
                                  const TextStyle(
                                fontSize: 20,
                                fontWeight:
                                    FontWeight
                                        .bold,
                              ),
                            ),
                          ),

                          const SizedBox(
                            width: 16,
                          ),

                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment
                                      .start,
                              children: [
                                Text(
                                  ingredient
                                      .name,
                                  style:
                                      const TextStyle(
                                    fontSize:
                                        20,
                                    fontWeight:
                                        FontWeight
                                            .bold,
                                  ),
                                ),

                                const SizedBox(
                                  height: 4,
                                ),

                                Text(
                                  ingredient
                                      .code,
                                  style:
                                      const TextStyle(
                                    color: Colors
                                        .grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(
                        height: 16,
                      ),

                      Text(
                        'Stock Limit: ${ingredient.stockLimit}',
                      ),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'Unit Price:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        formatRupiah(
                          ingredient
                              .unitPrice,
                        ),
                        style:
                            const TextStyle(
                          fontSize: 16,
                          color:
                              Colors.green,
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      const SizedBox(
                        height: 12,
                      ),

                      Text(
                        'Ingredient ID:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        ingredient.id,
                        style:
                            const TextStyle(
                          fontSize: 12,
                          color:
                              Colors.grey,
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