"""Integration tests for the Supabase storage module.

Tests the FK design where:
- messages table contains only user messages
- assistant_responses table contains AI responses linked via foreign key
"""

import pytest
from backend import storage


class TestCreateConversation:
    """Tests for create_conversation function."""

    def test_create_conversation_basic(self, test_user_id, test_conversation_id):
        """Test creating a basic conversation."""
        conversation = storage.create_conversation(test_conversation_id, user_id=test_user_id)

        assert conversation is not None
        assert conversation["id"] == test_conversation_id
        assert conversation["title"] == "New Conversation"
        assert conversation["messages"] == []
        assert "created_at" in conversation

    def test_create_conversation_with_organization(self, test_user_id, test_conversation_id):
        """Test creating a conversation with organization ID."""
        org_id = "org_test_123"
        conversation = storage.create_conversation(
            test_conversation_id, user_id=test_user_id, organization_id=org_id
        )

        assert conversation is not None
        assert conversation["id"] == test_conversation_id


class TestGetConversation:
    """Tests for get_conversation function."""

    def test_get_conversation_exists(self, test_user_id, test_conversation_id):
        """Test getting an existing conversation."""
        # First create the conversation
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        # Then retrieve it
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)

        assert conversation is not None
        assert conversation["id"] == test_conversation_id
        assert conversation["title"] == "New Conversation"

    def test_get_conversation_not_found(self, test_user_id):
        """Test getting a non-existent conversation."""
        import uuid
        # Use a valid UUID format that doesn't exist
        non_existent_uuid = str(uuid.uuid4())
        conversation = storage.get_conversation(non_existent_uuid, user_id=test_user_id)
        assert conversation is None

    def test_get_conversation_wrong_user(self, test_user_id, test_conversation_id):
        """Test that users cannot access other users' conversations."""
        # Create conversation for one user
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        # Try to access with different user
        conversation = storage.get_conversation(test_conversation_id, user_id="other_user_id")
        assert conversation is None


class TestListConversations:
    """Tests for list_conversations function with pagination."""

    def test_list_conversations_empty(self, test_user_id):
        """Test listing conversations for user with no conversations."""
        result = storage.list_conversations(user_id=test_user_id)
        # Should return paginated response with empty conversations list
        assert isinstance(result, dict)
        assert "conversations" in result
        assert "has_more" in result
        assert isinstance(result["conversations"], list)

    def test_list_conversations_with_data(self, test_user_id):
        """Test listing conversations after creating some."""
        import uuid
        conv_id1 = str(uuid.uuid4())
        conv_id2 = str(uuid.uuid4())

        storage.create_conversation(conv_id1, user_id=test_user_id)
        storage.create_conversation(conv_id2, user_id=test_user_id)

        result = storage.list_conversations(user_id=test_user_id)

        assert len(result["conversations"]) >= 2
        conv_ids = [c["id"] for c in result["conversations"]]
        assert conv_id1 in conv_ids
        assert conv_id2 in conv_ids

    def test_list_conversations_pagination(self, test_user_id):
        """Test pagination of conversations."""
        import uuid
        # Create 5 conversations
        conv_ids = []
        for _ in range(5):
            conv_id = str(uuid.uuid4())
            conv_ids.append(conv_id)
            storage.create_conversation(conv_id, user_id=test_user_id)

        # Get first page (limit 2)
        result1 = storage.list_conversations(user_id=test_user_id, limit=2, offset=0)
        assert len(result1["conversations"]) == 2
        assert result1["has_more"] is True

        # Get second page (limit 2, offset 2)
        result2 = storage.list_conversations(user_id=test_user_id, limit=2, offset=2)
        assert len(result2["conversations"]) == 2
        assert result2["has_more"] is True

        # Get third page (limit 2, offset 4)
        result3 = storage.list_conversations(user_id=test_user_id, limit=2, offset=4)
        assert len(result3["conversations"]) >= 1
        # has_more depends on whether there are other conversations from previous tests


class TestAddUserMessage:
    """Tests for add_user_message function."""

    def test_add_user_message(self, test_user_id, test_conversation_id):
        """Test adding a user message to a conversation."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Hello, world!"
        )

        # Verify message ID is returned
        assert user_message_id is not None

        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"]) == 1
        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][0]["content"] == "Hello, world!"


class TestAddAssistantResponse:
    """Tests for add_assistant_response function (FK design)."""

    def test_add_assistant_response_basic(
        self,
        test_user_id,
        test_conversation_id,
        sample_stage1_responses,
        sample_stage2_evaluations,
        sample_stage3_synthesis,
    ):
        """Test adding an assistant response linked to a user message."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        # First add a user message to get its ID
        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="What is AI?"
        )

        # Then add an assistant response linked to that user message
        response_id = storage.add_assistant_response(
            user_message_id,
            stage1=sample_stage1_responses,
            stage2=sample_stage2_evaluations,
            stage3=sample_stage3_synthesis,
        )

        assert response_id is not None

        # Verify the conversation has both messages
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"]) == 2
        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][1]["role"] == "assistant"

    def test_add_assistant_response_with_timing(
        self,
        test_user_id,
        test_conversation_id,
        sample_stage1_responses,
        sample_stage2_evaluations,
        sample_stage3_synthesis,
        sample_metadata,
    ):
        """Test adding an assistant response with timing metrics."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Tell me about ML"
        )

        storage.add_assistant_response(
            user_message_id,
            stage1=sample_stage1_responses,
            stage2=sample_stage2_evaluations,
            stage3=sample_stage3_synthesis,
            stage1_duration_ms=1500,
            stage2_duration_ms=2500,
            stage3_duration_ms=1000,
            metadata=sample_metadata,
        )

        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"]) == 2
        # Note: timing is stored but may not be returned in the message dict
        # This test verifies the function doesn't error with timing params


class TestUpdateConversationTitle:
    """Tests for update_conversation_title function."""

    def test_update_title(self, test_user_id, test_conversation_id):
        """Test updating conversation title."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        storage.update_conversation_title(
            test_conversation_id, user_id=test_user_id, title="My Updated Title"
        )

        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert conversation["title"] == "My Updated Title"


class TestUpdateConversationQueries:
    """Tests for update_conversation_queries function."""

    def test_update_original_query(self, test_user_id, test_conversation_id):
        """Test updating original query."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        storage.update_conversation_queries(
            test_conversation_id,
            user_id=test_user_id,
            original_query="What is the meaning of life?"
        )

        # Verify by checking the database directly or via get_conversation
        # (depends on whether get_conversation returns these fields)
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert conversation is not None

    def test_update_improved_query(self, test_user_id, test_conversation_id):
        """Test updating improved query."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        storage.update_conversation_queries(
            test_conversation_id,
            user_id=test_user_id,
            original_query="what is life",
            improved_query="What is the philosophical meaning of life and human existence?"
        )

        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert conversation is not None


class TestConversationFlow:
    """Tests for complete conversation flows using FK design."""

    def test_full_conversation_flow(
        self,
        test_user_id,
        test_conversation_id,
        sample_stage1_responses,
        sample_stage2_evaluations,
        sample_stage3_synthesis,
    ):
        """Test a complete conversation flow with FK design."""
        # Create conversation
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        # Store original query
        storage.update_conversation_queries(
            test_conversation_id,
            user_id=test_user_id,
            original_query="Tell me about AI"
        )

        # Add user message and get its ID
        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Tell me about AI"
        )

        # Add assistant response linked to user message (FK design)
        storage.add_assistant_response(
            user_message_id,
            stage1=sample_stage1_responses,
            stage2=sample_stage2_evaluations,
            stage3=sample_stage3_synthesis,
            stage1_duration_ms=2000,
            stage2_duration_ms=3000,
            stage3_duration_ms=1500,
        )

        # Update title
        storage.update_conversation_title(
            test_conversation_id, user_id=test_user_id, title="AI Discussion"
        )

        # Verify final state
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert conversation["title"] == "AI Discussion"
        assert len(conversation["messages"]) == 2

        # First message is user
        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][0]["content"] == "Tell me about AI"

        # Second message is assistant
        assert conversation["messages"][1]["role"] == "assistant"
        assert "stage1" in conversation["messages"][1]
        assert "stage2" in conversation["messages"][1]
        assert "stage3" in conversation["messages"][1]


class TestIncrementalPersistence:
    """Tests for incremental persistence pattern (placeholder → stage1 → stage2 → stage3)."""

    def test_create_response_placeholder(
        self,
        test_user_id,
        test_conversation_id,
    ):
        """Test creating an empty response placeholder."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test query"
        )

        response_id = storage.create_response_placeholder(user_message_id)
        assert response_id is not None

        # Verify conversation shows user message but assistant response has empty stages
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"]) == 2
        assert conversation["messages"][1]["role"] == "assistant"
        # Placeholder has empty stages (stage3 is None to prevent "Chairman: Unknown" UI bug)
        assert conversation["messages"][1]["stage1"] == []
        assert conversation["messages"][1]["stage2"] == []
        assert conversation["messages"][1]["stage3"] is None

    def test_incremental_stage_updates(
        self,
        test_user_id,
        test_conversation_id,
        sample_stage1_responses,
        sample_stage2_evaluations,
        sample_stage3_synthesis,
        sample_metadata,
    ):
        """Test updating stages incrementally (simulates streaming endpoint)."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        user_message_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Incremental test"
        )

        # Create placeholder
        response_id = storage.create_response_placeholder(user_message_id)

        # Update stage 1
        storage.update_response_stage1(response_id, sample_stage1_responses, 1500)

        # Verify stage 1 is saved
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"][1]["stage1"]) > 0
        assert conversation["messages"][1]["stage2"] == []

        # Update stage 2
        storage.update_response_stage2(
            response_id, sample_stage2_evaluations, 2500, sample_metadata
        )

        # Verify stage 2 is saved (stage3 is None until updated)
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"][1]["stage2"]) > 0
        assert conversation["messages"][1]["stage3"] is None

        # Update stage 3
        storage.update_response_stage3(response_id, sample_stage3_synthesis, 1000)

        # Verify all stages are saved
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"][1]["stage1"]) > 0
        assert len(conversation["messages"][1]["stage2"]) > 0
        assert conversation["messages"][1]["stage3"] != {}


class TestMultiTurnConversation:
    """Tests for multi-turn conversations with FK design."""

    def test_multi_turn_conversation(
        self,
        test_user_id,
        test_conversation_id,
        sample_stage1_responses,
        sample_stage2_evaluations,
        sample_stage3_synthesis,
    ):
        """Test a multi-turn conversation with multiple user/assistant pairs."""
        storage.create_conversation(test_conversation_id, user_id=test_user_id)

        # Turn 1
        user_msg_1 = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="First question"
        )
        storage.add_assistant_response(
            user_msg_1,
            stage1=sample_stage1_responses,
            stage2=sample_stage2_evaluations,
            stage3=sample_stage3_synthesis,
        )

        # Turn 2
        user_msg_2 = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Follow-up question"
        )
        storage.add_assistant_response(
            user_msg_2,
            stage1=sample_stage1_responses,
            stage2=sample_stage2_evaluations,
            stage3=sample_stage3_synthesis,
        )

        # Verify conversation has 4 messages in correct order
        conversation = storage.get_conversation(test_conversation_id, user_id=test_user_id)
        assert len(conversation["messages"]) == 4

        assert conversation["messages"][0]["role"] == "user"
        assert conversation["messages"][0]["content"] == "First question"
        assert conversation["messages"][1]["role"] == "assistant"
        assert conversation["messages"][2]["role"] == "user"
        assert conversation["messages"][2]["content"] == "Follow-up question"
        assert conversation["messages"][3]["role"] == "assistant"


class TestIncrementalPersistence:
    """Tests for incremental persistence of model responses."""

    def test_save_model_response(self, test_user_id, test_conversation_id):
        """Test saving individual model responses during Stage 1."""
        # Setup: create conversation, message, and response placeholder
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Save a model response
        storage.save_model_response(
            assistant_response_id=response_id,
            stage=1,
            model_name="openai/gpt-4",
            response_content={"content": "Test response from GPT-4"},
            elapsed_ms=1500,
            success=True,
        )

        # Verify it was saved
        partial = storage.get_partial_stage_responses(response_id, stage=1)
        assert len(partial) == 1
        assert partial[0]["model_name"] == "openai/gpt-4"
        assert partial[0]["response_content"]["content"] == "Test response from GPT-4"
        assert partial[0]["elapsed_ms"] == 1500

    def test_save_multiple_model_responses(self, test_user_id, test_conversation_id):
        """Test saving multiple model responses for smart retry."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Save multiple model responses
        models = [
            ("openai/gpt-4", "Response from GPT-4", True),
            ("anthropic/claude-3", "Response from Claude", True),
            ("google/gemini-pro", None, False),  # Failed model
        ]
        for model, content, success in models:
            storage.save_model_response(
                assistant_response_id=response_id,
                stage=1,
                model_name=model,
                response_content={"content": content} if content else None,
                elapsed_ms=1000,
                success=success,
                error_message=None if success else "Model failed",
            )

        # Verify only successful responses are returned
        partial = storage.get_partial_stage_responses(response_id, stage=1)
        assert len(partial) == 2
        model_names = [p["model_name"] for p in partial]
        assert "openai/gpt-4" in model_names
        assert "anthropic/claude-3" in model_names
        assert "google/gemini-pro" not in model_names

    def test_update_response_status(self, test_user_id, test_conversation_id):
        """Test updating response status through stages."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Update status through stages
        storage.update_response_status(response_id, "stage1_in_progress")
        result = storage.get_response_with_partial_stages(response_id)
        assert result["response"]["response_status"] == "stage1_in_progress"

        storage.update_response_status(response_id, "stage1_complete")
        result = storage.get_response_with_partial_stages(response_id)
        assert result["response"]["response_status"] == "stage1_complete"

    def test_set_response_error(self, test_user_id, test_conversation_id):
        """Test marking a response as failed with error details."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Mark as failed
        storage.set_response_error(response_id, "All models failed", "stage1")

        # Verify error details
        result = storage.get_response_with_partial_stages(response_id)
        assert result["response"]["response_status"] == "failed"
        assert result["response"]["error_details"]["message"] == "All models failed"
        assert result["response"]["error_details"]["stage"] == "stage1"

    def test_get_response_with_partial_stages(self, test_user_id, test_conversation_id):
        """Test retrieving response with all partial stage data."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Save some model responses
        storage.save_model_response(
            assistant_response_id=response_id,
            stage=1,
            model_name="openai/gpt-4",
            response_content={"content": "Test response"},
            elapsed_ms=1500,
            success=True,
        )

        # Get full response with partial stages
        result = storage.get_response_with_partial_stages(response_id)
        assert result is not None
        assert "response" in result
        assert "partial_stages" in result
        assert 1 in result["partial_stages"]
        assert len(result["partial_stages"][1]) == 1

    def test_cleanup_partial_stage_responses(self, test_user_id, test_conversation_id):
        """Test that partial responses are cleaned up after completion."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Save model responses
        storage.save_model_response(
            assistant_response_id=response_id,
            stage=1,
            model_name="openai/gpt-4",
            response_content={"content": "Test response"},
            elapsed_ms=1500,
            success=True,
        )

        # Verify they exist
        partial = storage.get_partial_stage_responses(response_id, stage=1)
        assert len(partial) == 1

        # Clean up
        storage.cleanup_partial_stage_responses(response_id)

        # Verify they're gone
        partial = storage.get_partial_stage_responses(response_id, stage=1)
        assert len(partial) == 0

    def test_model_response_upsert(self, test_user_id, test_conversation_id):
        """Test that saving the same model response twice updates instead of duplicating."""
        # Setup
        storage.create_conversation(test_conversation_id, user_id=test_user_id)
        user_msg_id = storage.add_user_message(
            test_conversation_id, user_id=test_user_id, content="Test question"
        )
        response_id = storage.create_response_placeholder(user_msg_id)

        # Save initial response
        storage.save_model_response(
            assistant_response_id=response_id,
            stage=1,
            model_name="openai/gpt-4",
            response_content={"content": "First response"},
            elapsed_ms=1000,
            success=True,
        )

        # Save again (simulating retry)
        storage.save_model_response(
            assistant_response_id=response_id,
            stage=1,
            model_name="openai/gpt-4",
            response_content={"content": "Updated response"},
            elapsed_ms=1500,
            success=True,
        )

        # Verify only one record exists with updated content
        partial = storage.get_partial_stage_responses(response_id, stage=1)
        assert len(partial) == 1
        assert partial[0]["response_content"]["content"] == "Updated response"
        assert partial[0]["elapsed_ms"] == 1500

