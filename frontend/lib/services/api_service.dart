import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user_model.dart';

class ApiService {
  // Gunakan 127.0.0.1 jika running di Edge/Chrome
  // Gunakan 10.0.2.2 jika running di Emulator Android
  static const String baseUrl = 'http://127.0.0.1:8080/api'; 

  Future<List<User>> fetchUsers() async {
    final response = await http.get(Uri.parse('$baseUrl/users'));

    if (response.statusCode == 200) {
      if (response.body == 'null') return [];
      final List<dynamic> data = json.decode(response.body);
      return data.map((json) => User.fromJson(json)).toList();
    } else {
      throw Exception('Gagal ambil data: ${response.statusCode}');
    }
  }
}