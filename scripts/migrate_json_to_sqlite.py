#!/usr/bin/env python3
"""
Migration script to convert JSON storage to SQLite.

This script migrates all conversations from the JSON file-based storage
to the new SQLite database storage.

Usage:
    python scripts/migrate_json_to_sqlite.py [--json-dir PATH] [--db-path PATH]

Example:
    python scripts/migrate_json_to_sqlite.py
    python scripts/migrate_json_to_sqlite.py --json-dir data/conversations --db-path data/conversations.db
"""

import argparse
import sys
import os
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.storage.json_storage import JSONStorageBackend
from backend.storage.sqlite_storage import SQLiteStorageBackend


def migrate_conversations(json_dir: str, db_path: str, dry_run: bool = False):
    """
    Migrate conversations from JSON to SQLite.

    Args:
        json_dir: Directory containing JSON conversation files
        db_path: Path to SQLite database file
        dry_run: If True, only show what would be migrated without writing
    """
    print(f"Migration Configuration:")
    print(f"  JSON directory: {json_dir}")
    print(f"  SQLite database: {db_path}")
    print(f"  Dry run: {dry_run}")
    print()

    # Check if JSON directory exists
    if not os.path.exists(json_dir):
        print(f"Error: JSON directory '{json_dir}' does not exist.")
        return False

    # Check if database already exists
    if os.path.exists(db_path) and not dry_run:
        response = input(f"Database '{db_path}' already exists. Overwrite? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Migration cancelled.")
            return False
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    # Initialize backends
    json_backend = JSONStorageBackend(json_dir)

    if not dry_run:
        sqlite_backend = SQLiteStorageBackend(db_path)

    # Get all conversations from JSON
    conversations = json_backend.list_conversations()

    if not conversations:
        print(f"No conversations found in {json_dir}")
        return True

    print(f"Found {len(conversations)} conversations to migrate\n")

    # Migrate each conversation
    migrated_count = 0
    error_count = 0

    for conv_meta in conversations:
        conv_id = conv_meta['id']

        try:
            # Load full conversation from JSON
            conversation = json_backend.get_conversation(conv_id)

            if conversation is None:
                print(f"⚠️  Warning: Could not load conversation {conv_id}")
                error_count += 1
                continue

            print(f"Migrating: {conv_id}")
            print(f"  Title: {conversation['title']}")
            print(f"  Messages: {len(conversation['messages'])}")

            if dry_run:
                print(f"  [DRY RUN] Would migrate this conversation")
            else:
                # Create conversation in SQLite
                sqlite_backend.create_conversation(conv_id)

                # Update title
                if conversation.get('title') != "New Conversation":
                    sqlite_backend.update_conversation_title(conv_id, conversation['title'])

                # Migrate messages
                for message in conversation['messages']:
                    if message['role'] == 'user':
                        sqlite_backend.add_user_message(conv_id, message['content'])
                    elif message['role'] == 'assistant':
                        sqlite_backend.add_assistant_message(
                            conv_id,
                            message.get('stage1', []),
                            message.get('stage2', []),
                            message.get('stage3', {})
                        )

                print(f"  ✓ Migrated successfully")

            migrated_count += 1

        except Exception as e:
            print(f"  ✗ Error migrating {conv_id}: {e}")
            error_count += 1

    print()
    print("=" * 60)
    print("Migration Summary:")
    print(f"  Total conversations: {len(conversations)}")
    print(f"  Successfully migrated: {migrated_count}")
    print(f"  Errors: {error_count}")

    if dry_run:
        print("\nThis was a dry run. No data was written.")
    else:
        print(f"\n✓ Migration complete! Database saved to: {db_path}")
        print("\nNext steps:")
        print("  1. Update your .env file to use SQLite backend:")
        print("     STORAGE_BACKEND=sqlite")
        print(f"     DB_PATH={db_path}")
        print("  2. Restart your application")
        print(f"  3. (Optional) Backup and remove old JSON directory: {json_dir}")

    return error_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Migrate conversations from JSON to SQLite storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate with default paths
  python scripts/migrate_json_to_sqlite.py

  # Specify custom paths
  python scripts/migrate_json_to_sqlite.py --json-dir data/conversations --db-path data/conversations.db

  # Dry run to see what would be migrated
  python scripts/migrate_json_to_sqlite.py --dry-run
        """
    )

    parser.add_argument(
        '--json-dir',
        default='data/conversations',
        help='Directory containing JSON conversation files (default: data/conversations)'
    )

    parser.add_argument(
        '--db-path',
        default='data/conversations.db',
        help='Path to SQLite database file (default: data/conversations.db)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually writing to database'
    )

    args = parser.parse_args()

    try:
        success = migrate_conversations(args.json_dir, args.db_path, args.dry_run)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
