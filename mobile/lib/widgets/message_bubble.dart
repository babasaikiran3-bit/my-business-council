import 'package:flutter/material.dart';
import '../models/conversation.dart';
import '../theme/app_theme.dart';
import 'stage1_widget.dart';
import 'stage2_widget.dart';
import 'stage3_widget.dart';

class MessageBubble extends StatelessWidget {
  final Message message;

  const MessageBubble({
    super.key,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    if (message.role == 'user') {
      return _buildUserMessage(context);
    } else {
      return _buildAssistantMessage(context);
    }
  }

  Widget _buildUserMessage(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'YOU',
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTheme.accentPrimary,
                letterSpacing: 0.5,
              ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.accentLight,
            border: Border.all(color: AppTheme.accentPrimary),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            message.content ?? '',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
      ],
    );
  }

  Widget _buildAssistantMessage(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'AI COUNCIL',
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                letterSpacing: 0.5,
              ),
        ),
        const SizedBox(height: 12),

        // Stage 1
        if (message.loading?.stage1 == true) _buildLoadingStage('Stage 1', context),
        if (message.stage1 != null && message.stage1!.isNotEmpty)
          Stage1Widget(responses: message.stage1!),

        // Stage 2
        if (message.loading?.stage2 == true) _buildLoadingStage('Stage 2', context),
        if (message.stage2 != null && message.stage2!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Stage2Widget(
              rankings: message.stage2!,
              labelToModel: message.metadata?.labelToModel ?? {},
              aggregateRankings: message.metadata?.aggregateRankings ?? [],
            ),
          ),

        // Stage 3
        if (message.loading?.stage3 == true) _buildLoadingStage('Stage 3', context),
        if (message.stage3 != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Stage3Widget(response: message.stage3!),
          ),
      ],
    );
  }

  Widget _buildLoadingStage(String stageName, BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppTheme.bgSecondary,
        border: Border.all(color: AppTheme.borderPrimary),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppTheme.accentPrimary,
            ),
          ),
          const SizedBox(width: 12),
          Text(
            'Running $stageName...',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}
