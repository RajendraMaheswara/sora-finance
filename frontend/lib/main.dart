import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'models/user_model.dart'; // Ganti ke model user

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sora Finance',
      debugShowCheckedModeBanner: false, // Menghilangkan banner debug
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
      ),
      home: const UserScreen(), // Ubah ke UserScreen
    );
  }
}

class UserScreen extends StatefulWidget {
  const UserScreen({super.key});

  @override
  State<UserScreen> createState() => _UserScreenState();
}

class _UserScreenState extends State<UserScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<User>> _futureUsers; // Ganti ke User

  @override
  void initState() {
    super.initState();
    // Memanggil fungsi fetchUsers dari api_service.dart
    _futureUsers = _apiService.fetchUsers();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daftar User', style: TextStyle(color: Colors.white)),
        backgroundColor: Theme.of(context).colorScheme.primary,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: () {
              // Refresh data
              setState(() {
                _futureUsers = _apiService.fetchUsers();
              });
            },
          )
        ],
      ),
      body: FutureBuilder<List<User>>(
        future: _futureUsers,
        builder: (context, snapshot) {
          // 1. Status Loading (Saat mengambil data dari Golang)
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          
          // 2. Status Error (Jika server mati atau CORS bermasalah)
          else if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  'Terjadi Kesalahan:\n${snapshot.error}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            );
          }
          
          // 3. Status Kosong (Jika API mengembalikan null atau [])
          else if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text('Belum ada data user di database.'));
          }

          // 4. Status Sukses (Data berhasil ditarik)
          final users = snapshot.data!;
          return ListView.separated(
            itemCount: users.length,
            separatorBuilder: (context, index) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final user = users[index];
              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                  child: const Icon(Icons.account_circle),
                ),
                title: Text(
                  user.username, 
                  style: const TextStyle(fontWeight: FontWeight.bold)
                ),
                subtitle: Text(user.email),
                trailing: const Icon(Icons.verified_user, size: 16, color: Colors.teal),
              );
            },
          );
        },
      ),
    );
  }
}