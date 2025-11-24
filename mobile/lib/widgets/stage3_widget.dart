import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/conversation.dart';
import '../theme/app_theme.dart';

class Stage3Widget extends StatelessWidget {
  final Stage3Response response;

  const Stage3Widget({
    super.key,
    required this.response,
  });

  String _getModelShortName(String fullName) {
    final parts = fullName.split('/');
    return parts.length > 1 ? parts[1] : fullName;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppTheme.bgSecondary,
            AppTheme.bgTertiary,
          ],
        ),
        border: Border.all(color: AppTheme.accentPrimary, width: 2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(
                      Icons.check_circle,
                      color: AppTheme.success,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'STAGE 3: FINAL COUNCIL ANSWER',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppTheme.success,
                            letterSpacing: 0.5,
                          ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Chairman: ${_getModelShortName(response.model)}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'FiraCode',
                      ),
                ),
              ],
            ),
          ),
          Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.bgTertiary,
              border: Border.all(color: AppTheme.borderPrimary),
              borderRadius: BorderRadius.circular(8),
            ),
            child: MarkdownBody(
              data: response.response,
              styleSheet: MarkdownStyleSheet(
                p: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      height: 1.7,
                    ),
                h1: Theme.of(context).textTheme.headlineLarge,
                h2: Theme.of(context).textTheme.headlineMedium,
                h3: Theme.of(context).textTheme.headlineSmall,
                strong: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary,
                    ),
                code: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontFamily: 'FiraCode',
                      backgroundColor: AppTheme.bgPrimary,
                      color: AppTheme.accentPrimary,
                    ),
                codeblockDecoration: BoxDecoration(
                  color: AppTheme.bgPrimary,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.borderPrimary),
                ),
                blockquote: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontStyle: FontStyle.italic,
                      color: AppTheme.textSecondary,
                    ),
                blockquoteDecoration: const BoxDecoration(
                  border: Border(
                    left: BorderSide(
                      color: AppTheme.accentPrimary,
                      width: 3,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
