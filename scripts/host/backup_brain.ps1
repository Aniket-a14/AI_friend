# Backup Script for AI Friend Memory
# Usage: ./backup_brain.ps1

$TIMESTAMP = Get-Date -Format "yyyyMMdd-HHmm"
$BACKUP_DIR = "./backups/$TIMESTAMP"

# Create backup directory
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null
Write-Host "🧠 Starting Brain Backup to $BACKUP_DIR..."

# 1. Backup PostgreSQL (Conversation History + Long Term Memory)
Write-Host "   - Backing up Postgres..."
try {
    docker exec postgres_db pg_dump -U ai_friend ai_friend_db > "$BACKUP_DIR/postgres_dump.sql"
    Write-Host "   ✅ Postgres backup complete."
} catch {
    Write-Error "   ❌ Postgres backup failed."
}

# 2. Backup Neo4j (Knowledge Graph)
# Using APOC export to specific directory inside container, then copying out.
# Note: Requires APOC to be configured with 'apoc.export.file.enabled=true'
Write-Host "   - Backing up Neo4j..."
try {
   # Check if APOC export is allowed (lightweight check by attempting help)
   # For strict backup, we might need a different approach if apoc.conf isn't set.
   # This is a simplified version: dumping cypher via shell
   docker exec brain_graph cypher-shell -u neo4j -p secure_prod_neo4j_pass_8823 "CALL apoc.export.cypher.all(null, {stream:true, format:'cypher-shell'})" > "$BACKUP_DIR/neo4j_dump.cypher"
   Write-Host "   ✅ Neo4j backup complete (Cypher Dump)."
} catch {
   Write-Error "   ❌ Neo4j backup failed. Ensure APOC is active."
}

Write-Host "🎉 Backup finished in $BACKUP_DIR"
