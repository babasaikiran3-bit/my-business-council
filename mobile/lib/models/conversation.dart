class Conversation {
  final String id;
  final String createdAt;
  final String title;
  final int messageCount;
  final List<Message>? messages;

  Conversation({
    required this.id,
    required this.createdAt,
    required this.title,
    required this.messageCount,
    this.messages,
  });

  factory Conversation.fromJson(Map<String, dynamic> json) {
    return Conversation(
      id: json['id'] as String,
      createdAt: json['created_at'] as String,
      title: json['title'] as String,
      messageCount: json['message_count'] as int? ??
                    (json['messages'] as List?)?.length ?? 0,
      messages: json['messages'] != null
          ? (json['messages'] as List)
              .map((m) => Message.fromJson(m as Map<String, dynamic>))
              .toList()
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'created_at': createdAt,
      'title': title,
      'message_count': messageCount,
      if (messages != null)
        'messages': messages!.map((m) => m.toJson()).toList(),
    };
  }
}

class Message {
  final String role;
  final String? content;
  final List<Stage1Response>? stage1;
  final List<Stage2Ranking>? stage2;
  final Stage3Response? stage3;
  final ConversationMetadata? metadata;
  final LoadingState? loading;

  Message({
    required this.role,
    this.content,
    this.stage1,
    this.stage2,
    this.stage3,
    this.metadata,
    this.loading,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      role: json['role'] as String,
      content: json['content'] as String?,
      stage1: json['stage1'] != null
          ? (json['stage1'] as List)
              .map((s) => Stage1Response.fromJson(s as Map<String, dynamic>))
              .toList()
          : null,
      stage2: json['stage2'] != null
          ? (json['stage2'] as List)
              .map((s) => Stage2Ranking.fromJson(s as Map<String, dynamic>))
              .toList()
          : null,
      stage3: json['stage3'] != null
          ? Stage3Response.fromJson(json['stage3'] as Map<String, dynamic>)
          : null,
      metadata: json['metadata'] != null
          ? ConversationMetadata.fromJson(
              json['metadata'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'role': role,
      if (content != null) 'content': content,
      if (stage1 != null) 'stage1': stage1!.map((s) => s.toJson()).toList(),
      if (stage2 != null) 'stage2': stage2!.map((s) => s.toJson()).toList(),
      if (stage3 != null) 'stage3': stage3!.toJson(),
      if (metadata != null) 'metadata': metadata!.toJson(),
    };
  }

  Message copyWith({
    String? role,
    String? content,
    List<Stage1Response>? stage1,
    List<Stage2Ranking>? stage2,
    Stage3Response? stage3,
    ConversationMetadata? metadata,
    LoadingState? loading,
  }) {
    return Message(
      role: role ?? this.role,
      content: content ?? this.content,
      stage1: stage1 ?? this.stage1,
      stage2: stage2 ?? this.stage2,
      stage3: stage3 ?? this.stage3,
      metadata: metadata ?? this.metadata,
      loading: loading ?? this.loading,
    );
  }
}

class Stage1Response {
  final String model;
  final String response;

  Stage1Response({
    required this.model,
    required this.response,
  });

  factory Stage1Response.fromJson(Map<String, dynamic> json) {
    return Stage1Response(
      model: json['model'] as String,
      response: json['response'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'model': model,
      'response': response,
    };
  }
}

class Stage2Ranking {
  final String model;
  final String ranking;
  final List<String> parsedRanking;

  Stage2Ranking({
    required this.model,
    required this.ranking,
    required this.parsedRanking,
  });

  factory Stage2Ranking.fromJson(Map<String, dynamic> json) {
    return Stage2Ranking(
      model: json['model'] as String,
      ranking: json['ranking'] as String,
      parsedRanking: (json['parsed_ranking'] as List)
          .map((r) => r as String)
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'model': model,
      'ranking': ranking,
      'parsed_ranking': parsedRanking,
    };
  }
}

class Stage3Response {
  final String model;
  final String response;

  Stage3Response({
    required this.model,
    required this.response,
  });

  factory Stage3Response.fromJson(Map<String, dynamic> json) {
    return Stage3Response(
      model: json['model'] as String,
      response: json['response'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'model': model,
      'response': response,
    };
  }
}

class ConversationMetadata {
  final Map<String, String> labelToModel;
  final List<AggregateRanking> aggregateRankings;

  ConversationMetadata({
    required this.labelToModel,
    required this.aggregateRankings,
  });

  factory ConversationMetadata.fromJson(Map<String, dynamic> json) {
    return ConversationMetadata(
      labelToModel: Map<String, String>.from(
          json['label_to_model'] as Map? ?? {}),
      aggregateRankings: (json['aggregate_rankings'] as List? ?? [])
          .map((r) => AggregateRanking.fromJson(r as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'label_to_model': labelToModel,
      'aggregate_rankings': aggregateRankings.map((r) => r.toJson()).toList(),
    };
  }
}

class AggregateRanking {
  final String model;
  final double averageRank;
  final int rankingsCount;

  AggregateRanking({
    required this.model,
    required this.averageRank,
    required this.rankingsCount,
  });

  factory AggregateRanking.fromJson(Map<String, dynamic> json) {
    return AggregateRanking(
      model: json['model'] as String,
      averageRank: (json['average_rank'] as num).toDouble(),
      rankingsCount: json['rankings_count'] as int,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'model': model,
      'average_rank': averageRank,
      'rankings_count': rankingsCount,
    };
  }
}

class LoadingState {
  final bool stage1;
  final bool stage2;
  final bool stage3;

  LoadingState({
    this.stage1 = false,
    this.stage2 = false,
    this.stage3 = false,
  });

  LoadingState copyWith({
    bool? stage1,
    bool? stage2,
    bool? stage3,
  }) {
    return LoadingState(
      stage1: stage1 ?? this.stage1,
      stage2: stage2 ?? this.stage2,
      stage3: stage3 ?? this.stage3,
    );
  }
}
