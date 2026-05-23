import 'package:flutter/material.dart';
import 'package:sora2/pages/dashboard/dashboard_page.dart';

import 'customers/customer_list_page.dart';
import 'orders/order_list_page.dart';
import 'stores/store_list_page.dart';
import 'food_ingredients/food_ingredient_page.dart';
import 'monthly_summaries/monthly_summary_page.dart';
import 'sales_daily/sales_daily_page.dart';
import 'ingredient_stock/ingredient_stock_page.dart';
import 'users/user_list_page.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 9,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Sora Finance'),
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'Dashboard'),
              Tab(text: 'Customers'),
              Tab(text: 'Orders'),
              Tab(text: 'Stores'),
              Tab(text: 'Food Ingredient'),
              Tab(text: 'Monthly'),
              Tab(text: 'Sales'),
              Tab(text: 'Ingredients'),
              Tab(text: 'Users',)
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            DashboardScreen(),
            CustomerListPage(),
            OrderListPage(),
            StoreListPage(),
            FoodIngredientListPage(),
            MonthlySummaryPage(),
            SalesDailyPage(),
            IngredientStockPage(),
            UserListPage(),
          ],
        ),
      ),
    );
  }
}