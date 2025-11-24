import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/conversation.dart';
import '../theme/app_theme.dart';

class Stage2Widget extends StatefulWidget {
  final List<Stage2Ranking> rankings;
  final Map<String, String> labelToModel;
  final List<AggregateRanking> aggregateRankings;

  const Stage2Widget({
    super.key,
    required this.rankings,
    required this.labelToModel,
    required this.aggregateRankings,
  });

  @override
  State<Stage2Widget> createState() => _Stage2WidgetState();
}

class _Stage2WidgetState extends State<Stage2Widget>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(
      length: widget.rankings.length,
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

  String _deAnonymizeText(String text) {
    String result = text;
    widget.labelToModel.forEach((label, model) {
      final shortName = _getModelShortName(model);
      result = result.replaceAll(label, '**$shortName**');
    });
    return result;
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Stage 2: Peer Rankings',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                Text(
                  'Each model evaluated all responses (anonymized)',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),

          // Aggregate Rankings
          if (widget.aggregateRankings.isNotEmpty)
            _buildAggregateRankings(context),

          // Tabs for individual rankings
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Text(
              'Raw Evaluations',
              style: Theme.of(context).textTheme.labelLarge,
            ),
          ),
          const SizedBox(height: 12),
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
              tabs: widget.rankings
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
              children: widget.rankings
                  .map((ranking) => _buildRankingContent(ranking))
                  .toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAggregateRankings(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.bgTertiary,
        border: Border.all(color: AppTheme.borderPrimary),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Aggregate Rankings (Street Cred)',
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: AppTheme.accentPrimary,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            'Combined results across all peer evaluations',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          ...widget.aggregateRankings.asMap().entries.map((entry) {
            final index = entry.key;
            final ranking = entry.value;
            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTheme.bgHover,
                border: Border.all(color: AppTheme.borderPrimary),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppTheme.accentLight,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      '#${index + 1}',
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color: AppTheme.accentPrimary,
                          ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _getModelShortName(ranking.model),
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            fontFamily: 'FiraCode',
                          ),
                    ),
                  ),
                  Text(
                    'Avg: ${ranking.averageRank.toStringAsFixed(2)}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontFamily: 'FiraCode',
                        ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '(${ranking.rankingsCount} votes)',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildRankingContent(Stage2Ranking ranking) {
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
            ranking.model,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontFamily: 'FiraCode',
                ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  MarkdownBody(
                    data: _deAnonymizeText(ranking.ranking),
                    styleSheet: MarkdownStyleSheet(
                      p: Theme.of(context).textTheme.bodyMedium,
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
                  if (ranking.parsedRanking.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.only(top: 16),
                      decoration: const BoxDecoration(
                        border: Border(
                          top: BorderSide(color: AppTheme.borderPrimary),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Extracted Ranking:',
                            style: Theme.of(context)
                                .textTheme
                                .labelMedium
                                ?.copyWith(
                                  color: AppTheme.accentPrimary,
                                ),
                          ),
                          const SizedBox(height: 8),
                          ...ranking.parsedRanking.asMap().entries.map((e) {
                            final index = e.key;
                            final label = e.value;
                            final model = widget.labelToModel[label];
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 4),
                              child: Text(
                                '${index + 1}. ${model != null ? _getModelShortName(model) : label}',
                                style: Theme.of(context)
                                    .textTheme
                                    .bodySmall
                                    ?.copyWith(
                                      fontFamily: 'FiraCode',
                                    ),
                              ),
                            );
                          }),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
