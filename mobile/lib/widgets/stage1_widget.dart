import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/conversation.dart';
import '../theme/app_theme.dart';

class Stage1Widget extends StatefulWidget {
  final List<Stage1Response> responses;

  const Stage1Widget({
    super.key,
    required this.responses,
  });

  @override
  State<Stage1Widget> createState() => _Stage1WidgetState();
}

class _Stage1WidgetState extends State<Stage1Widget>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: widget.responses.length,
      vsync: this,
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  String _getModelShortName(String fullName) {
    final parts = fullName.split('/');
    return parts.length > 1 ? parts[1] : fullName;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.bgSecondary,
        border: Border.all(color: AppTheme.borderPrimary),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Text(
              'Stage 1: Individual Responses',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            margin: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: AppTheme.bgTertiary,
              borderRadius: BorderRadius.circular(8),
            ),
            child: TabBar(
              controller: _tabController,
              isScrollable: true,
              indicatorSize: TabBarIndicatorSize.tab,
              indicator: BoxDecoration(
                color: AppTheme.accentPrimary,
                borderRadius: BorderRadius.circular(6),
              ),
              labelColor: AppTheme.textPrimary,
              unselectedLabelColor: AppTheme.textSecondary,
              labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
              tabs: widget.responses
                  .map((r) => Tab(
                        text: _getModelShortName(r.model),
                      ))
                  .toList(),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 400,
            child: TabBarView(
              controller: _tabController,
              children: widget.responses
                  .map((response) => _buildResponseContent(response))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResponseContent(Stage1Response response) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.bgTertiary,
        border: Border.all(color: AppTheme.borderPrimary),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            response.model,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontFamily: 'FiraCode',
                ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: SingleChildScrollView(
              child: MarkdownBody(
                data: response.response,
                styleSheet: MarkdownStyleSheet(
                  p: Theme.of(context).textTheme.bodyLarge,
                  h1: Theme.of(context).textTheme.headlineLarge,
                  h2: Theme.of(context).textTheme.headlineMedium,
                  h3: Theme.of(context).textTheme.headlineSmall,
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
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
