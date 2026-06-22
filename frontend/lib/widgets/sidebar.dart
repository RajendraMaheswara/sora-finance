import 'package:flutter/material.dart';

import '../../core/services/auth_service.dart';
import '../../models/current_user_model.dart';
import '../pages/auth/login_page.dart';

const Color _kPrimaryGreen = Color(0xFF8CE600);

class SidebarWidget extends StatelessWidget {
  final String userName;
  final String name;

  const SidebarWidget({super.key, 
    required this.userName,
    required this.name,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Logo
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.eco, color: Colors.lightGreen[600], size: 22),
              const SizedBox(width: 4),
              Text('sora',
                  style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Colors.lightGreen[700])),
            ],
          ),
          const SizedBox(height: 24),

          // Avatar
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.grey.shade200, width: 2),
              color: Colors.grey.shade200,
            ),
            child: const ClipOval(
                child: Icon(Icons.person, size: 56, color: Colors.white)),
          ),
          const SizedBox(height: 8),

          // Username
          FutureBuilder<CurrentUserModel>(
            future: AuthService().getCurrentUser(),
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const Text("Loading...");
              return Text("Hello, ${snapshot.data!.username}");
            },
          ),
          const SizedBox(height: 2),

          // Status
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('🔴', style: TextStyle(fontSize: 9)),
              const SizedBox(width: 4),
              Text(
                name,
                style: const TextStyle(
                  color: Colors.grey,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 28),

          // Menu item — Dasbor (inline, tanpa class terpisah)
          Container(
            width: 70,
            height: 70,
            decoration: BoxDecoration(
              color: _kPrimaryGreen,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.grey.shade200),
            ),
            child: const Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.pie_chart, color: Colors.white, size: 26),
                SizedBox(height: 4),
                Text('Dasbor',
                    style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: Colors.white)),
              ],
            ),
          ),
          const Spacer(),

SizedBox(
  width: double.infinity,
  child: OutlinedButton.icon(
    icon: const Icon(
      Icons.logout,
      color: Colors.red,
    ),
    label: const Text(
      'Logout',
      style: TextStyle(
        color: Colors.red,
        fontWeight: FontWeight.w600,
      ),
    ),
    onPressed: () async {
      final confirm = await showDialog<bool>(
        context: context,
        builder: (context) {
          return AlertDialog(
            title: const Text('Logout'),
            content: const Text(
              'Apakah Anda yakin ingin keluar?',
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(context, false);
                },
                child: const Text('Batal'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                ),
                onPressed: () {
                  Navigator.pop(context, true);
                },
                child: const Text('Logout'),
              ),
            ],
          );
        },
      );

      if (confirm == true) {
        await AuthService().logout();

        if (context.mounted) {
          Navigator.pushAndRemoveUntil(
            context,
            MaterialPageRoute(
              builder: (_) => const LoginPage(),
            ),
            (route) => false,
          );
        }
      }
    },
  ),
),
        ],
      ),
    );
  }
}