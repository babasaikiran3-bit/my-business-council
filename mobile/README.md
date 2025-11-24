# AI Council Mobile

A beautiful Flutter mobile application for the AI Council - a collaborative LLM deliberation system with a modern dark theme.

## Features

✨ **Beautiful Modern UI**
- Dark theme with indigo accents matching the web app
- Smooth animations and transitions
- Material Design 3 components
- Google Fonts (Inter) for professional typography

🚀 **Real-time Streaming**
- Server-Sent Events (SSE) for live updates
- Progressive display of all 3 stages
- Loading indicators for each stage

📱 **Mobile-Optimized**
- Responsive layout for all screen sizes
- Native iOS and Android support
- Offline conversation caching (via Provider)
- Pull-to-refresh

🎨 **Stage-by-Stage Display**
- **Stage 1**: Tab view of individual model responses
- **Stage 2**: Peer rankings with aggregate scores
- **Stage 3**: Final synthesized answer with special highlighting

## Architecture

### Tech Stack
- **Flutter**: Latest stable version (3.x+)
- **State Management**: Provider
- **HTTP Client**: http package with SSE support
- **Markdown Rendering**: flutter_markdown
- **Typography**: Google Fonts (Inter)

### Project Structure

```
mobile/
├── lib/
│   ├── main.dart                  # App entry point
│   ├── theme/
│   │   └── app_theme.dart         # Dark theme configuration
│   ├── models/
│   │   └── conversation.dart      # Data models
│   ├── services/
│   │   └── api_service.dart       # API client
│   ├── providers/
│   │   └── conversation_provider.dart  # State management
│   ├── screens/
│   │   ├── home_screen.dart       # Conversation list
│   │   └── chat_screen.dart       # Chat interface
│   └── widgets/
│       ├── message_bubble.dart    # Message display
│       ├── message_input.dart     # Input field
│       ├── stage1_widget.dart     # Stage 1 display
│       ├── stage2_widget.dart     # Stage 2 display
│       └── stage3_widget.dart     # Stage 3 display
├── pubspec.yaml                   # Dependencies
└── README.md                      # This file
```

## Getting Started

### Prerequisites

1. **Flutter SDK**: Install Flutter from [flutter.dev](https://flutter.dev)
   ```bash
   # Verify installation
   flutter doctor
   ```

2. **Backend Server**: Ensure the AI Council backend is running
   ```bash
   # From project root
   cd server && npm run dev
   ```

### Installation

1. **Navigate to mobile directory**:
   ```bash
   cd mobile
   ```

2. **Install dependencies**:
   ```bash
   flutter pub get
   ```

3. **Configure backend URL**:

   Edit `lib/main.dart` and set the correct backend URL:
   ```dart
   // For Android Emulator
   final apiService = ApiService(baseUrl: 'http://10.0.2.2:8001');

   // For iOS Simulator
   final apiService = ApiService(baseUrl: 'http://localhost:8001');

   // For Physical Device (replace with your computer's IP)
   final apiService = ApiService(baseUrl: 'http://192.168.1.100:8001');
   ```

4. **Run the app**:
   ```bash
   # For Android
   flutter run

   # For iOS (macOS only)
   flutter run -d ios

   # For a specific device
   flutter devices  # List available devices
   flutter run -d <device-id>
   ```

## Configuration

### Backend URL

The mobile app needs to connect to your backend server. Choose the appropriate URL based on your setup:

| Platform | URL | Notes |
|----------|-----|-------|
| Android Emulator | `http://10.0.2.2:8001` | Maps to host machine's localhost |
| iOS Simulator | `http://localhost:8001` | Direct localhost access |
| Physical Device | `http://YOUR_IP:8001` | Replace with your computer's local IP |

To find your computer's IP:
```bash
# macOS/Linux
ifconfig | grep "inet "

# Windows
ipconfig
```

### Theme Customization

The app uses a dark theme matching the web app. To customize colors, edit `lib/theme/app_theme.dart`:

```dart
class AppTheme {
  static const Color accentPrimary = Color(0xFF6366F1);  // Change accent color
  static const Color bgPrimary = Color(0xFF0A0A0B);      // Change background
  // ... more colors
}
```

## Usage

### Creating a New Conversation

1. Tap the **"New Chat"** floating action button
2. Type your question in the input field
3. Press send or hit enter

### Viewing Stages

As the AI Council processes your question:

1. **Stage 1** appears first with individual model responses in tabs
2. **Stage 2** shows peer rankings and aggregate scores
3. **Stage 3** displays the final synthesized answer (highlighted with green border)

### Navigation

- **Pull down** to refresh conversations list
- **Tap** a conversation to view its full history
- **Back button** returns to conversation list

## Building for Production

### Android

```bash
# Build APK
flutter build apk --release

# Build App Bundle (for Google Play)
flutter build appbundle --release

# Output locations:
# APK: build/app/outputs/flutter-apk/app-release.apk
# Bundle: build/app/outputs/bundle/release/app-release.aab
```

### iOS

```bash
# Build IPA (macOS only)
flutter build ios --release

# Then use Xcode to:
# 1. Open ios/Runner.xcworkspace
# 2. Archive the app
# 3. Distribute to App Store or Ad Hoc
```

## Troubleshooting

### Connection Issues

**Error**: "Failed to connect to server"

**Solutions**:
1. Verify backend is running: `cd server && npm run dev`
2. Check backend URL in `lib/main.dart`
3. For physical devices, ensure both device and computer are on same WiFi
4. Check firewall settings allow port 8001

### Build Issues

**Error**: "flutter: command not found"

**Solution**: Install Flutter SDK from [flutter.dev](https://flutter.dev/docs/get-started/install)

**Error**: "Gradle build failed"

**Solution**:
```bash
cd android
./gradlew clean
cd ..
flutter clean
flutter pub get
flutter run
```

### Rendering Issues

**Problem**: Markdown not rendering correctly

**Solution**: Ensure `flutter_markdown` is installed:
```bash
flutter pub get
```

## API Compatibility

The mobile app is compatible with the AI Council backend API:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/conversations` | GET | List all conversations |
| `/api/conversations` | POST | Create new conversation |
| `/api/conversations/:id` | GET | Get conversation details |
| `/api/conversations/:id/message` | POST | Send message (blocking) |
| `/api/conversations/:id/message/stream` | POST | Send message (SSE streaming) |

## Performance Tips

1. **Lazy Loading**: Messages are loaded on-demand
2. **Caching**: Conversations cached in memory via Provider
3. **Streaming**: SSE updates UI progressively
4. **Optimized Scrolling**: ListView.builder for efficient rendering

## Future Enhancements

- [ ] Local persistence with SQLite
- [ ] Push notifications for completed deliberations
- [ ] Offline mode support
- [ ] Export conversations to PDF
- [ ] Voice input integration
- [ ] Dark/Light theme toggle
- [ ] Custom model selection
- [ ] Conversation search

## Screenshots

### Home Screen
- List of conversations
- Create new conversation
- Pull-to-refresh

### Chat Screen
- Message bubbles for user/assistant
- Progressive stage display
- Markdown rendering
- Loading indicators

### Stages Display
- **Stage 1**: Tabbed model responses
- **Stage 2**: Rankings with aggregates
- **Stage 3**: Final answer with highlighting

## License

MIT

## Support

For issues or questions:
1. Check this README for common solutions
2. Review the main project documentation
3. Ensure backend is running correctly
4. Verify network connectivity

---

Built with ❤️ using Flutter
