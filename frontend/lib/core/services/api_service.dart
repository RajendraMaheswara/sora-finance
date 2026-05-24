import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:8080/api';

  Future<List<dynamic>> fetchData(String endpoint) async {
    final response = await http.get(Uri.parse('$baseUrl/$endpoint'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load data');
    }
  }

  Future<dynamic> fetchDetail(String endpoint, String id) async {
    final response = await http.get(Uri.parse('$baseUrl/$endpoint/$id'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load detail');
    }
  }

  /// Mengambil response berbentuk objek `{success, message, data}`.
  /// Mengembalikan field `data` saja agar caller cukup parsing isinya.
  Future<Map<String, dynamic>> fetchObject(String endpoint) async {
    final response = await http.get(Uri.parse('$baseUrl/$endpoint'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load object: ${response.statusCode}');
    }

    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) {
      // Jika response dibungkus { success, data }, kembalikan `data`-nya.
      if (decoded.containsKey('data') && decoded['data'] is Map) {
        return Map<String, dynamic>.from(decoded['data'] as Map);
      }
      return decoded;
    }
    throw Exception('Unexpected response shape (not an object).');
  }
}
