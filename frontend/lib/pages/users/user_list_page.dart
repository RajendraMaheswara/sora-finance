import 'package:flutter/material.dart';

import '../../core/services/api_service.dart';
import '../../models/user_model.dart';

class UserListPage
    extends StatefulWidget {
  const UserListPage({super.key});

  @override
  State<UserListPage> createState() =>
      _UserListPageState();
}

class _UserListPageState
    extends State<UserListPage> {
  final ApiService apiService =
      ApiService();

  late Future<List<UserModel>> users;

  Future<List<UserModel>> getUsers() async {
    final data =
        await apiService.fetchData(
      'users',
    );

    return data
        .map<UserModel>(
          (e) => UserModel.fromJson(e),
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    users = getUsers();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body:
          FutureBuilder<List<UserModel>>(
        future: users,
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
                'No users found',
              ),
            );
          }

          // list
          return ListView.builder(
            itemCount: data.length,
            itemBuilder: (context, index) {
              final user = data[index];

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
                            radius: 30,
                            backgroundImage:
                                user.avatarUrl
                                        .isNotEmpty
                                    ? NetworkImage(
                                        user
                                            .avatarUrl,
                                      )
                                    : null,
                            child:
                                user.avatarUrl
                                        .isEmpty
                                    ? Text(
                                        user
                                            .name[0]
                                            .toUpperCase(),
                                      )
                                    : null,
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
                                  user.name,
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
                                  '@${user.username}',
                                  style:
                                      const TextStyle(
                                    color: Colors
                                        .grey,
                                  ),
                                ),
                              ],
                            ),
                          ),

                          Icon(
                            user.isActive
                                ? Icons
                                    .check_circle
                                : Icons.cancel,
                            color:
                                user.isActive
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
                        'Email:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(user.email),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'Phone:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(user.phone),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'Address:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(user.address),

                      const SizedBox(
                        height: 8,
                      ),

                      Text(
                        'NIP: ${user.nip}',
                      ),

                      const SizedBox(
                        height: 8,
                      ),

                      Row(
                        children: [
                          Chip(
                            label: Text(
                              user
                                      .isEmailVerified
                                  ? 'Email Verified'
                                  : 'Email Not Verified',
                            ),
                            backgroundColor:
                                user
                                        .isEmailVerified
                                    ? Colors
                                        .green
                                        .shade100
                                    : Colors
                                        .red
                                        .shade100,
                          ),

                          const SizedBox(
                            width: 8,
                          ),

                          Chip(
                            label: Text(
                              user
                                      .isPhoneVerified
                                  ? 'Phone Verified'
                                  : 'Phone Not Verified',
                            ),
                            backgroundColor:
                                user
                                        .isPhoneVerified
                                    ? Colors
                                        .green
                                        .shade100
                                    : Colors
                                        .orange
                                        .shade100,
                          ),
                        ],
                      ),

                      const SizedBox(
                        height: 12,
                      ),

                      Text(
                        'User ID:',
                        style:
                            const TextStyle(
                          fontWeight:
                              FontWeight.bold,
                        ),
                      ),

                      Text(
                        user.id,
                        style:
                            const TextStyle(
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