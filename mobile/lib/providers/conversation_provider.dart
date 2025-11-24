import 'package:flutter/foundation.dart';
import '../models/conversation.dart';
import '../services/api_service.dart';

class ConversationProvider with ChangeNotifier {
  final ApiService _apiService;

  List<Conversation> _conversations = [];
  Conversation? _currentConversation;
  bool _isLoading = false;
  String? _error;

  ConversationProvider(this._apiService);

  List<Conversation> get conversations => _conversations;
  Conversation? get currentConversation => _currentConversation;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Load all conversations
  Future<void> loadConversations() async {
    try {
      _isLoading = true;
      _error = null;
      notifyListeners();

      _conversations = await _apiService.getConversations();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  // Create a new conversation
  Future<void> createNewConversation() async {
    try {
      _error = null;

      final newConv = await _apiService.createConversation();
      _conversations.insert(0, newConv);
      _currentConversation = newConv;

      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  // Select a conversation
  Future<void> selectConversation(String id) async {
    try {
      _isLoading = true;
      _error = null;
      notifyListeners();

      _currentConversation = await _apiService.getConversation(id);

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  // Send a message with streaming
  Future<void> sendMessage(String content) async {
    if (_currentConversation == null) return;

    try {
      _error = null;

      // Add user message optimistically
      final userMessage = Message(role: 'user', content: content);
      final messages = List<Message>.from(_currentConversation!.messages ?? []);
      messages.add(userMessage);

      // Add placeholder assistant message
      final assistantMessage = Message(
        role: 'assistant',
        loading: LoadingState(stage1: false, stage2: false, stage3: false),
      );
      messages.add(assistantMessage);

      _currentConversation = Conversation(
        id: _currentConversation!.id,
        createdAt: _currentConversation!.createdAt,
        title: _currentConversation!.title,
        messageCount: messages.length,
        messages: messages,
      );
      notifyListeners();

      // Stream the response
      await for (var event in _apiService.sendMessageStream(
        _currentConversation!.id,
        content,
      )) {
        _handleStreamEvent(event);
      }

      // Reload conversation after streaming completes
      await selectConversation(_currentConversation!.id);
      await loadConversations(); // Refresh the list

    } catch (e) {
      _error = e.toString();
      notifyListeners();

      // Remove optimistic messages on error
      if (_currentConversation != null && _currentConversation!.messages != null) {
        final messages = List<Message>.from(_currentConversation!.messages!);
        if (messages.length >= 2) {
          messages.removeLast(); // Remove assistant message
          messages.removeLast(); // Remove user message
          _currentConversation = Conversation(
            id: _currentConversation!.id,
            createdAt: _currentConversation!.createdAt,
            title: _currentConversation!.title,
            messageCount: messages.length,
            messages: messages,
          );
          notifyListeners();
        }
      }
    }
  }

  void _handleStreamEvent(Map<String, dynamic> event) {
    if (_currentConversation == null || _currentConversation!.messages == null) {
      return;
    }

    final messages = List<Message>.from(_currentConversation!.messages!);
    if (messages.isEmpty) return;

    final lastMessage = messages.last;
    final eventType = event['type'] as String?;

    switch (eventType) {
      case 'stage1_start':
        messages[messages.length - 1] = lastMessage.copyWith(
          loading: LoadingState(stage1: true, stage2: false, stage3: false),
        );
        break;

      case 'stage1_complete':
        final stage1Data = event['data'] as List?;
        if (stage1Data != null) {
          final stage1 = stage1Data
              .map((s) => Stage1Response.fromJson(s as Map<String, dynamic>))
              .toList();
          messages[messages.length - 1] = lastMessage.copyWith(
            stage1: stage1,
            loading: LoadingState(stage1: false, stage2: false, stage3: false),
          );
        }
        break;

      case 'stage2_start':
        messages[messages.length - 1] = lastMessage.copyWith(
          loading: LoadingState(stage1: false, stage2: true, stage3: false),
        );
        break;

      case 'stage2_complete':
        final stage2Data = event['data'] as List?;
        final metadataData = event['metadata'] as Map<String, dynamic>?;
        if (stage2Data != null) {
          final stage2 = stage2Data
              .map((s) => Stage2Ranking.fromJson(s as Map<String, dynamic>))
              .toList();
          final metadata = metadataData != null
              ? ConversationMetadata.fromJson(metadataData)
              : null;
          messages[messages.length - 1] = lastMessage.copyWith(
            stage2: stage2,
            metadata: metadata,
            loading: LoadingState(stage1: false, stage2: false, stage3: false),
          );
        }
        break;

      case 'stage3_start':
        messages[messages.length - 1] = lastMessage.copyWith(
          loading: LoadingState(stage1: false, stage2: false, stage3: true),
        );
        break;

      case 'stage3_complete':
        final stage3Data = event['data'] as Map<String, dynamic>?;
        if (stage3Data != null) {
          final stage3 = Stage3Response.fromJson(stage3Data);
          messages[messages.length - 1] = lastMessage.copyWith(
            stage3: stage3,
            loading: LoadingState(stage1: false, stage2: false, stage3: false),
          );
        }
        break;

      case 'title_complete':
        // Title updated, refresh conversations list
        loadConversations();
        break;

      case 'error':
        _error = event['message']?.toString() ?? 'Unknown error';
        break;
    }

    _currentConversation = Conversation(
      id: _currentConversation!.id,
      createdAt: _currentConversation!.createdAt,
      title: _currentConversation!.title,
      messageCount: messages.length,
      messages: messages,
    );
    notifyListeners();
  }
}
