"""Migra las conversaciones JSON legacy (data/conversations/*.json) a SQLite.

Idempotente: omite las conversaciones que ya existen en la DB.
Uso:  python -m backend.migrate_to_sqlite
"""

import json
import os

from .config import DATA_DIR
from . import storage


def migrate() -> int:
    storage.init_db()
    if not os.path.isdir(DATA_DIR):
        print(f"No hay directorio legacy {DATA_DIR}, nada que migrar.")
        return 0

    migrated = 0
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, filename)
        with open(path, "r") as f:
            conv = json.load(f)

        if storage.get_conversation(conv["id"]) is not None:
            print(f"  = {conv['id']} ya existe, omito")
            continue

        # save_conversation reescribe todo el documento (conv + mensajes) en SQLite.
        conv.setdefault("title", "New Conversation")
        conv.setdefault("messages", [])
        storage.save_conversation(conv)
        migrated += 1
        print(f"  + {conv['id']}  ({conv.get('title')!r}, {len(conv['messages'])} msgs)")

    print(f"Migradas {migrated} conversaciones a {storage.DB_PATH}.")
    return migrated


if __name__ == "__main__":
    migrate()
