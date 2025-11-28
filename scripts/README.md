# Scripts

This directory contains utility scripts for LLM Council maintenance and migration.

## Migration Scripts

### migrate_json_to_sqlite.py

Migrates conversations from the legacy JSON file-based storage to the new SQLite database storage.

**Usage:**

```bash
# Dry run to see what would be migrated
python scripts/migrate_json_to_sqlite.py --dry-run

# Migrate with default paths
python scripts/migrate_json_to_sqlite.py

# Migrate with custom paths
python scripts/migrate_json_to_sqlite.py \
  --json-dir data/conversations \
  --db-path data/conversations.db
```

**When to use:**

- When upgrading from a version using JSON storage to SQLite
- When you have existing conversations in `data/conversations/` directory
- Before changing `STORAGE_BACKEND` environment variable to `sqlite`

**What it does:**

1. Reads all JSON conversation files from the specified directory
2. Creates a new SQLite database at the specified path
3. Migrates all conversations, messages, and metadata
4. Preserves creation timestamps and conversation titles
5. Shows a summary of migrated conversations

**Safety features:**

- Prompts for confirmation if database already exists
- Supports `--dry-run` mode to preview migration without writing
- Detailed error reporting for each conversation
- Does not delete original JSON files (you can remove them manually after verification)

**Example output:**

```
Migration Configuration:
  JSON directory: data/conversations
  SQLite database: data/conversations.db
  Dry run: False

Found 15 conversations to migrate

Migrating: abc-123-def
  Title: Python decorators explained
  Messages: 4
  ✓ Migrated successfully

...

Migration Summary:
  Total conversations: 15
  Successfully migrated: 15
  Errors: 0

✓ Migration complete! Database saved to: data/conversations.db

Next steps:
  1. Update your .env file to use SQLite backend:
     STORAGE_BACKEND=sqlite
     DB_PATH=data/conversations.db
  2. Restart your application
  3. (Optional) Backup and remove old JSON directory: data/conversations
```

## Future Scripts

Additional utility scripts may be added here for:
- Database backups
- Data exports (markdown, CSV, etc.)
- Performance benchmarking
- Database maintenance and cleanup
