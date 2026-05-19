import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/store_model.dart';

class StoreListPage extends StatefulWidget {
  const StoreListPage({super.key});

  @override
  State<StoreListPage> createState() =>
      _StoreListPageState();
}

class _StoreListPageState
    extends State<StoreListPage> {
  final ApiService apiService = ApiService();

  late Future<List<StoreModel>> stores;

  Future<List<StoreModel>> getStores() async {
    final data = await apiService.fetchData(
      'stores',
    );

    return data
        .map<StoreModel>(
          (e) => StoreModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    stores = getStores();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FutureBuilder<List<StoreModel>>(
        future: stores,
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

          // Kosong
          if (data.isEmpty) {
            return const Center(
              child: Text(
                'No stores found',
              ),
            );
          }

          // List Data
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final store = data[index];

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
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 28,
                            child: Text(
                              store.name[0]
                                  .toUpperCase(),
                              style:
                                  const TextStyle(
                                fontWeight:
                                    FontWeight
                                        .bold,
                                fontSize: 20,
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
                                  store.name,
                                  style:
                                      const TextStyle(
                                    fontSize: 20,
                                    fontWeight:
                                        FontWeight
                                            .bold,
                                  ),
                                ),

                                const SizedBox(
                                  height: 4,
                                ),

                                Text(
                                  store.isActive
                                      ? 'Active'
                                      : 'Inactive',
                                  style:
                                      TextStyle(
                                    color: store
                                            .isActive
                                        ? Colors
                                            .green
                                        : Colors
                                            .red,
                                    fontWeight:
                                        FontWeight
                                            .bold,
                                  ),
                                ),
                              ],
                            ),
                          ),

                          Icon(
                            store.isActive
                                ? Icons
                                    .check_circle
                                : Icons.cancel,
                            color:
                                store.isActive
                                    ? Colors
                                        .green
                                    : Colors.red,
                          ),
                        ],
                      ),

                      const SizedBox(
                        height: 16,
                      ),

                      Text(
                        'Store ID:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(store.id),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'Subscription Type: ${store.mSubscriptionTypeId}',
                      ),

                      Text(
                        'Coins: ${store.coins}',
                      ),

                      Text(
                        'Tutorial Step: ${store.tutorialStep}',
                      ),

                      Text(
                        'Tutorial Completed: ${store.isTutorialCompleted}',
                      ),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'Expired Date:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        store.expiredDate,
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