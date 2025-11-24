import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../models/conversation.dart';

class ApiService {
  final String baseUrl;

  ApiService({this.baseUrl = 'http://localhost:8001'});

  // Get all conversations
  Future<List<Conversation>> getConversations() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/conversations'),
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((json) => Conversation.fromJson(json)).toList();
      } else {
        throw Exception('Failed to load conversations: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Failed to connect to server: $e');
    }
  }

  // Create a new conversation
  Future<Conversation> createConversation() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/conversations'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({}),
      );

      if (response.statusCode == 200) {
        return Conversation.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to create conversation: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Failed to create conversation: $e');
    }
  }

  // Get a specific conversation
  Future<Conversation> getConversation(String id) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/conversations/$id'),
      );

      if (response.statusCode == 200) {
        return Conversation.fromJson(json.decode(response.body));
      } else if (response.statusCode == 404) {
        throw Exception('Conversation not found');
      } else {
        throw Exception('Failed to load conversation: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Failed to load conversation: $e');
    }
  }

  // Send a message (non-streaming)
  Future<Map<String, dynamic>> sendMessage(
    String conversationId,
    String content,
  ) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/conversations/$conversationId/message'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'content': content}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to send message: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Failed to send message: $e');
    }
  }

  // Send a message with streaming (SSE)
  Stream<Map<String, dynamic>> sendMessageStream(
    String conversationId,
    String content,
  ) async* {
    try {
      final request = http.Request(
        'POST',
        Uri.parse('$baseUrl/api/conversations/$conversationId/message/stream'),
      );
      request.headers['Content-Type'] = 'application/json';
      request.body = json.encode({'content': content});

      final streamedResponse = await request.send();

      if (streamedResponse.statusCode != 200) {
        throw Exception('Failed to send message: ${streamedResponse.statusCode}');
      }

      // Process the SSE stream
      await for (var chunk in streamedResponse.stream.transform(utf8.decoder)) {
        // Split by lines
        final lines = chunk.split('\n');

        for (var line in lines) {
          line = line.trim();

          // SSE format: "data: {...}"
          if (line.startsWith('data: ')) {
            final jsonStr = line.substring(6); // Remove "data: " prefix

            try {
              final data = json.decode(jsonStr);
              yield data;
            } catch (e) {
              // Skip invalid JSON
              continue;
            }
          }
        }
      }
    } catch (e) {
      throw Exception('Failed to stream message: $e');
    }
  }
}
