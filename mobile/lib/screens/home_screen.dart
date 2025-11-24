import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/conversation_provider.dart';
import '../theme/app_theme.dart';
import 'chat_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // Load conversations on startup
    Future.microtask(() {
      context.read<ConversationProvider>().loadConversations();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: Consumer<ConversationProvider>(
                builder: (context, provider, _) {
                  if (provider.isLoading && provider.conversations.isEmpty) {
                    return const Center(
                      child: CircularProgressIndicator(
                        color: AppTheme.accentPrimary,
                      ),
                    );
                  }

                  if (provider.error != null) {
                    return _buildErrorState(context, provider);
                  }

                  if (provider.conversations.isEmpty) {
                    return _buildEmptyState(context);
                  }

                  return _buildConversationsList(provider);
                },
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _createNewConversation(context),
        backgroundColor: AppTheme.accentPrimary,
        icon: const Icon(Icons.add),
        label: const Text('New Chat'),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: const BoxDecoration(
        color: AppTheme.bgTertiary,
        border: Border(
          bottom: BorderSide(color: AppTheme.borderPrimary),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShaderMask(
            shaderCallback: (bounds) => const LinearGradient(
              colors: [Color(0xFF667EEA), Color(0xFF764BA2)],
            ).createShader(bounds),
            child: Text(
              'AI Council',
              style: Theme.of(context).textTheme.displayMedium?.copyWith(
                    color: Colors.white,
                  ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Collaborative LLM deliberation',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(48),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.chat_bubble_outline,
              size: 64,
              color: AppTheme.textTertiary,
            ),
            const SizedBox(height: 24),
            Text(
              'No conversations yet',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Start a new conversation to consult\nthe AI Council',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, ConversationProvider provider) {
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
              'Connection Error',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              provider.error ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => provider.loadConversations(),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConversationsList(ConversationProvider provider) {
    return RefreshIndicator(
      onRefresh: () => provider.loadConversations(),
      color: AppTheme.accentPrimary,
      backgroundColor: AppTheme.bgSecondary,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: provider.conversations.length,
        itemBuilder: (context, index) {
          final conversation = provider.conversations[index];
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: InkWell(
              onTap: () => _openConversation(context, conversation.id),
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.bgSecondary,
                  border: Border.all(color: AppTheme.borderPrimary),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: AppTheme.accentLight,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.chat,
                        color: AppTheme.accentPrimary,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            conversation.title,
                            style: Theme.of(context).textTheme.labelLarge,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${conversation.messageCount} messages',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.chevron_right,
                      color: AppTheme.textTertiary,
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Future<void> _createNewConversation(BuildContext context) async {
    final provider = context.read<ConversationProvider>();
    await provider.createNewConversation();

    if (provider.currentConversation != null && mounted) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => const ChatScreen(),
        ),
      );
    }
  }

  void _openConversation(BuildContext context, String id) async {
    final provider = context.read<ConversationProvider>();
    await provider.selectConversation(id);

    if (mounted) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => const ChatScreen(),
        ),
      );
    }
  }
}
