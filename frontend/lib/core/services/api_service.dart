import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/api_constants.dart';

class ApiService {

  Future<Map<String, String>> _headers() async {
    final prefs = await SharedPreferences.getInstance();

    final token = prefs.getString('token');

    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  Future<List<dynamic>> fetchData(String endpoint) async {
    final response = await http.get(
      Uri.parse('${ApiConstants.baseUrl}/$endpoint'),
      headers: await _headers(),
    );

    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body);
      // Endpoint list yang kosong bisa mengembalikan `null` (nil slice di Go).
      if (decoded == null) return <dynamic>[];
      if (decoded is List) return decoded;
      // Kalau dibungkus {"data": [...]}.
      if (decoded is Map && decoded['data'] is List) {
        return decoded['data'] as List<dynamic>;
      }
      return <dynamic>[];
    }

    throw Exception('Failed to load data');
  }

  Future<dynamic> fetchDetail(
    String endpoint,
    String id,
  ) async {
    final response = await http.get(
      Uri.parse('${ApiConstants.baseUrl}/$endpoint/$id'),
      headers: await _headers(),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception('Failed to load detail');
  }
}