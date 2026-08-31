# Disaster Recovery & Backup Guide

AI Friend stores state across four independent datastores. To make backups atomic and foolproof, dedicated backup and restoration utilities are included in `backend/scripts/`.

---

## What is Captured in an Archive

An export archive (`.tar.gz`) bundles:

1. **PostgreSQL Relational & Vector Data**: 9 tables serialized to JSONL (`memories`, `conversations`, `entities`, `agent_configs`, etc.).
2. **Neo4j Semantic Knowledge Graph**: Cypher statements recreating all nodes, labels, and dynamic relationship edges.
3. **SQLite Affect Cache**: State snapshots from `state_cache.db` (19 PAD and neurochemical values).
4. **Identity Files**: Tracked personality and biography documents from `.identity_state/`.

---

## Creating an Export Archive

Run the export script from the repository root:

```bash
cd backend
../.venv/bin/python -m scripts.export_friend --out ~/backups/my_friend_2026.tar.gz
```

Output:
```text
==> Exporting PostgreSQL tables (9 tables)...
==> Dumping Neo4j knowledge graph...
==> Backing up SQLite affect state...
==> Packaging identity files...
✓ Created archive: /Users/username/backups/my_friend_2026.tar.gz (1.8 MB)
```

---

## Restoring on a New Computer

To migrate your friend to a new workstation or restore after hardware failure:

```bash
cd backend
../.venv/bin/python -m scripts.import_friend ~/backups/my_friend_2026.tar.gz --force
```

The `--force` flag is mandatory to prevent accidental overwrites of existing live agent configs. Once complete, restart the stack to resume conversations exactly where you left off.
