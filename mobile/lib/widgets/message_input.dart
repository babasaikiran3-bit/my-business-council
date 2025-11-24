import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class MessageInput extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onSend;
  final bool isSending;

  const MessageInput({
    super.key,
    required this.controller,
    required this.onSend,
    this.isSending = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        color: AppTheme.bgSecondary,
        border: Border(
          top: BorderSide(color: AppTheme.borderPrimary),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                maxLines: null,
                minLines: 1,
                textInputAction: TextInputAction.newline,
                style: Theme.of(context).textTheme.bodyLarge,
                decoration: InputDecoration(
                  hintText: 'Ask your question...',
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppTheme.borderPrimary),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppTheme.borderPrimary),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: AppTheme.accentPrimary,
                      width: 2,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Material(
              color: isSending || controller.text.isEmpty
                  ? AppTheme.bgTertiary
                  : AppTheme.accentPrimary,
              borderRadius: BorderRadius.circular(12),
              child: InkWell(
                onTap: isSending || controller.text.isEmpty ? null : onSend,
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  width: 56,
                  height: 56,
                  alignment: Alignment.center,
                  child: isSending
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppTheme.textSecondary,
                          ),
                        )
                      : Icon(
                          Icons.send,
                          color: controller.text.isEmpty
                              ? AppTheme.textTertiary
                              : AppTheme.textPrimary,
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
