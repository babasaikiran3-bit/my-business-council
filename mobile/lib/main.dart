import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'theme/app_theme.dart';
import 'services/api_service.dart';
import 'providers/conversation_provider.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    // Configure your backend URL here
    // For Android emulator: http://10.0.2.2:8001
    // For iOS simulator: http://localhost:8001
    // For physical device: http://your-computer-ip:8001
    final apiService = ApiService(baseUrl: 'http://10.0.2.2:8001');

    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => ConversationProvider(apiService)..loadConversations(),
        ),
      ],
      child: MaterialApp(
        title: 'AI Council',
        theme: AppTheme.darkTheme,
        debugShowCheckedModeBanner: false,
        home: const HomeScreen(),
      ),
    );
  }
}
