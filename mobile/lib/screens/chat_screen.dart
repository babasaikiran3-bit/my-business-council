import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/conversation_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/message_bubble.dart';
import '../widgets/message_input.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _textController = TextEditingController();
  bool _isSending = false;

  @override
  void dispose() {
    _scrollController.dispose();
    _textController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty || _isSending) return;

    setState(() => _isSending = true);
    _textController.clear();

    try {
      await context.read<ConversationProvider>().sendMessage(text);
      // Scroll to bottom after message is sent
      Future.delayed(const Duration(milliseconds: 500), _scrollToBottom);
    } finally {
      if (mounted) {
        setState(() => _isSending = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Consumer<ConversationProvider>(
          builder: (context, provider, _) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  provider.currentConversation?.title ?? 'Conversation',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                if (provider.currentConversation != null)
                  Text(
                    '${provider.currentConversation!.messageCount} messages',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            );
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              final provider = context.read<ConversationProvider>();
              if (provider.currentConversation != null) {
                provider.selectConversation(provider.currentConversation!.id);
              }
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Consumer<ConversationProvider>(
              builder: (context, provider, _) {
                if (provider.isLoading) {
                  return const Center(
                    child: CircularProgressIndicator(
                      color: AppTheme.accentPrimary,
                    ),
                  );
                }

                if (provider.error != null) {
                  return _buildErrorState(provider);
                }

                final conversation = provider.currentConversation;
                if (conversation == null || conversation.messages == null) {
                  return _buildEmptyState();
                }

                if (conversation.messages!.isEmpty) {
                  return _buildEmptyState();
                }

                // Scroll to bottom when new messages arrive
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  _scrollToBottom();
                });

                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: conversation.messages!.length,
                  itemBuilder: (context, index) {
                    final message = conversation.messages![index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 24),
                      child: MessageBubble(message: message),
                    );
                  },
                );
              },
            ),
          ),
          MessageInput(
            controller: _textController,
            onSend: _sendMessage,
            isSending: _isSending,
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.forum_outlined,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: 24),
            Text(
              'Start the Conversation',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Ask a question to consult the AI Council',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(ConversationProvider provider) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: AppTheme.error,
            ),
            const SizedBox(height: 24),
            Text(
              'Error',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              provider.error ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
