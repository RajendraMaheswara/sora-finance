import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/api_constants.dart';
import '../../models/current_user_model.dart';

class AuthService {
  Future<bool> login({
    required String username,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConstants.baseUrl}/auth/login'),
      headers: {
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'username': username,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);

      final token = data['token'];

      final prefs = await SharedPreferences.getInstance();

      await prefs.setString('token', token);

      return true;
    }

    return false;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();

    await prefs.remove('token');
    await prefs.remove('current_user');
  }

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();

    return prefs.getString('token');
  }

  Future<bool> isLoggedIn() async {
    return await getToken() != null;
    
  }
  
  Future<CurrentUserModel> getCurrentUser() async {
  final token = await getToken();

  final response = await http.get(
    Uri.parse('${ApiConstants.baseUrl}/auth/me'),
    headers: {
      'Authorization': 'Bearer $token',
    },
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);

    return CurrentUserModel.fromJson(data);
  }

  throw Exception('Failed to load profile');
}


}