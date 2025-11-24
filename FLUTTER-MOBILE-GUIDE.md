# Flutter Mobile App - Quick Start Guide

## 🎉 Complete Mobile App Created!

A beautiful Flutter mobile application for AI Council with modern dark theme, real-time streaming, and professional UI/UX.

---

## 📱 Features

### ✨ Modern Design
- **Dark theme** with indigo accents (#6366F1) matching web app
- **Google Fonts (Inter)** for professional typography
- **Smooth animations** and transitions
- **Material Design 3** components
- **Gradient effects** on Stage 3 final answer

### 🚀 Real-Time Experience
- **Server-Sent Events (SSE)** streaming
- **Progressive updates** as each stage completes
- **Loading indicators** for each stage
- **Pull-to-refresh** on conversation list
- **Optimistic UI updates**

### 📊 3-Stage Display
- **Stage 1**: Tab view of individual model responses with markdown rendering
- **Stage 2**: Peer rankings with aggregate scores and de-anonymization
- **Stage 3**: Final synthesized answer with special highlighting
- **Markdown support** for code blocks, lists, headers, etc.

### 🎯 User-Friendly
- **Intuitive navigation**
- **Error handling** with retry
- **Empty states** with helpful messaging
- **Conversation history**
- **Message persistence**

---

## 🚀 Getting Started

### Prerequisites

1. **Install Flutter**:
   ```bash
   # Download from https://flutter.dev

   # Verify installation
   flutter doctor
   ```

2. **Start the Backend**:
   ```bash
   # From project root
   cd server && npm run dev
   ```

### Run the App

1. **Navigate to mobile directory**:
   ```bash
   cd mobile
   ```

2. **Install dependencies**:
   ```bash
   flutter pub get
   ```

3. **Configure backend URL** in `lib/main.dart`:

   **For Android Emulator** (most common):
   ```dart
   final apiService = ApiService(baseUrl: 'http://10.0.2.2:8001');
   ```

   **For iOS Simulator**:
   ```dart
   final apiService = ApiService(baseUrl: 'http://localhost:8001');
   ```

   **For Physical Device**:
   ```dart
   // Replace with your computer's IP address
   final apiService = ApiService(baseUrl: 'http://192.168.1.100:8001');
   ```

   To find your IP:
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "

   # Windows
   ipconfig
   ```

4. **Run the app**:
   ```bash
   # List available devices
   flutter devices

   # Run on default device
   flutter run

   # Run on specific device
   flutter run -d <device-id>
   ```

---

## 📁 Project Structure

```
mobile/
├── lib/
│   ├── main.dart                      # App entry point
│   │
│   ├── theme/
│   │   └── app_theme.dart            # Dark theme config
│   │
│   ├── models/
│   │   └── conversation.dart         # Data models
│   │
│   ├── services/
│   │   └── api_service.dart          # HTTP client + SSE
│   │
│   ├── providers/
│   │   └── conversation_provider.dart # State management
│   │
│   ├── screens/
│   │   ├── home_screen.dart          # Conversation list
│   │   └── chat_screen.dart          # Chat interface
│   │
│   └── widgets/
│       ├── message_bubble.dart       # Message display
│       ├── message_input.dart        # Input field
│       ├── stage1_widget.dart        # Stage 1 tabs
│       ├── stage2_widget.dart        # Stage 2 rankings
│       └── stage3_widget.dart        # Stage 3 final answer
│
├── pubspec.yaml                       # Dependencies
├── analysis_options.yaml              # Linter rules
└── README.md                          # Full documentation
```

---

## 🎨 Design System

### Color Palette

```dart
// Backgrounds
bgPrimary:    #0A0A0B  // Main background
bgSecondary:  #111113  // Card backgrounds
bgTertiary:   #1A1A1D  // Elevated surfaces
bgHover:      #222225  // Hover state

// Text
textPrimary:   #FFFFFF  // Primary text
textSecondary: #A0A0A8  // Secondary text
textTertiary:  #6B6B75  // Tertiary text

// Accent
accentPrimary: #6366F1  // Primary accent (indigo)
accentHover:   #4F46E5  // Hover state
accentLight:   #1A6366F1 // Light accent (with alpha)

// Status
success: #10B981  // Stage 3 indicator
warning: #F59E0B  // Warnings
error:   #EF4444  // Errors
```

### Typography

- **Font Family**: Inter (via Google Fonts)
- **Monospace**: Fira Code (for model names and code)
- **Sizes**: 11px - 32px range
- **Weights**: 400 (normal), 500 (medium), 600 (semibold), 700 (bold)

---

## 🔧 Key Components

### 1. API Service (`services/api_service.dart`)
- HTTP client for REST endpoints
- SSE client for streaming responses
- Automatic JSON parsing
- Error handling

### 2. Conversation Provider (`providers/conversation_provider.dart`)
- State management with Provider
- Conversation CRUD operations
- Message sending with streaming
- Optimistic UI updates

### 3. Theme Configuration (`theme/app_theme.dart`)
- Complete Material 3 theme
- Custom color scheme
- Typography configuration
- Component theming

### 4. Stage Widgets
- **Stage 1**: Tab controller with markdown rendering
- **Stage 2**: Aggregate rankings + individual evaluations
- **Stage 3**: Highlighted final answer with gradient

---

## 📖 Usage Examples

### Creating a Conversation

```dart
final provider = context.read<ConversationProvider>();
await provider.createNewConversation();

// Navigate to chat
Navigator.push(
  context,
  MaterialPageRoute(builder: (_) => const ChatScreen()),
);
```

### Sending a Message

```dart
final provider = context.read<ConversationProvider>();
await provider.sendMessage('What is quantum computing?');

// Provider handles:
// - Optimistic UI update
// - SSE streaming
// - Progressive stage updates
// - Error handling
```

### Displaying Stages

```dart
// In MessageBubble widget
if (message.stage1 != null) {
  Stage1Widget(responses: message.stage1!);
}

if (message.stage2 != null) {
  Stage2Widget(
    rankings: message.stage2!,
    labelToModel: message.metadata?.labelToModel ?? {},
    aggregateRankings: message.metadata?.aggregateRankings ?? [],
  );
}

if (message.stage3 != null) {
  Stage3Widget(response: message.stage3!);
}
```

---

## 🔨 Building for Production

### Android

```bash
# Build APK
flutter build apk --release

# Build App Bundle (for Play Store)
flutter build appbundle --release

# Output:
# build/app/outputs/flutter-apk/app-release.apk
# build/app/outputs/bundle/release/app-release.aab
```

### iOS

```bash
# Build (macOS only)
flutter build ios --release

# Then use Xcode:
# 1. Open ios/Runner.xcworkspace
# 2. Archive the app
# 3. Distribute
```

---

## 🐛 Troubleshooting

### Can't Connect to Backend

**Problem**: "Failed to connect to server"

**Solutions**:
1. ✅ Verify backend is running: `cd server && npm run dev`
2. ✅ Check URL in `lib/main.dart` matches your setup
3. ✅ For Android emulator, use `http://10.0.2.2:8001`
4. ✅ For physical device, use your computer's IP
5. ✅ Ensure firewall allows port 8001

### Markdown Not Rendering

**Problem**: Text appears without formatting

**Solution**:
```bash
flutter clean
flutter pub get
flutter run
```

### Hot Reload Not Working

**Problem**: Changes don't appear

**Solution**:
```bash
# Stop app (Ctrl+C)
flutter clean
flutter run
```

---

## 📊 API Integration

The app uses these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/conversations` | GET | List conversations |
| `/api/conversations` | POST | Create conversation |
| `/api/conversations/:id` | GET | Get conversation |
| `/api/conversations/:id/message/stream` | POST | Send message (SSE) |

### SSE Event Types

```dart
switch (event['type']) {
  case 'stage1_start':    // Stage 1 started
  case 'stage1_complete': // Stage 1 responses ready
  case 'stage2_start':    // Stage 2 started
  case 'stage2_complete': // Stage 2 rankings ready
  case 'stage3_start':    // Stage 3 started
  case 'stage3_complete': // Stage 3 final answer ready
  case 'title_complete':  // Conversation title updated
  case 'complete':        // All done
  case 'error':           // Error occurred
}
```

---

## 🎯 Best Practices

### State Management
- Use Provider for global state (conversations)
- Use StatefulWidget for local UI state (text input, tabs)
- Avoid unnecessary rebuilds with Consumer

### Performance
- Use ListView.builder for long lists
- Implement lazy loading for messages
- Cache responses in Provider

### Error Handling
- Try-catch around all API calls
- Show user-friendly error messages
- Provide retry mechanisms

### UI/UX
- Show loading indicators during async operations
- Use optimistic updates for better UX
- Implement pull-to-refresh
- Handle empty states

---

## 🚀 Next Steps

### Recommended Enhancements
1. **Local Persistence**: Add SQLite for offline storage
2. **Push Notifications**: Notify when deliberation completes
3. **Voice Input**: Add speech-to-text
4. **Export**: Save conversations as PDF
5. **Search**: Find conversations by content
6. **Themes**: Add light mode toggle
7. **Settings**: Configure API URL in-app
8. **Analytics**: Track usage patterns

### Advanced Features
- [ ] Conversation sharing
- [ ] Favorite conversations
- [ ] Message reactions
- [ ] Multi-user support
- [ ] Real-time collaboration
- [ ] Custom model selection

---

## 📚 Resources

### Documentation
- **Flutter**: [flutter.dev/docs](https://flutter.dev/docs)
- **Provider**: [pub.dev/packages/provider](https://pub.dev/packages/provider)
- **Material 3**: [m3.material.io](https://m3.material.io)

### Tools
- **Flutter DevTools**: Debug and profile your app
- **VS Code Extensions**: Flutter, Dart
- **Android Studio**: Full IDE for Flutter

### Community
- **Stack Overflow**: [stackoverflow.com/questions/tagged/flutter](https://stackoverflow.com/questions/tagged/flutter)
- **Flutter Discord**: Join the community
- **GitHub Issues**: Report bugs and request features

---

## ✅ Checklist for First Run

- [ ] Flutter SDK installed and verified (`flutter doctor`)
- [ ] Backend server running on port 8001
- [ ] Backend URL configured in `lib/main.dart`
- [ ] Dependencies installed (`flutter pub get`)
- [ ] Device/emulator connected (`flutter devices`)
- [ ] App running (`flutter run`)
- [ ] Can create new conversation
- [ ] Can send message and see all 3 stages
- [ ] Markdown renders correctly
- [ ] Pull-to-refresh works

---

**Congratulations! Your AI Council mobile app is ready! 🎉**

For full details, see `mobile/README.md`
