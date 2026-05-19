import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl =
      'http://localhost:8080/api';

  Future<List<dynamic>> fetchData(
    String endpoint,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/$endpoint'),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load data');
    }
  }

  Future<dynamic> fetchDetail(
    String endpoint,
    String id,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/$endpoint/$id'),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to load detail');
    }
  }
}