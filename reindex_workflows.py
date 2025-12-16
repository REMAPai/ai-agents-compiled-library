#!/usr/bin/env python3
"""
Manually trigger workflow reindexing.
Use this script to index new workflows that were added to the workflows folder.
"""

from workflow_db import WorkflowDatabase
import sys

def main():
    """Reindex all workflows in the workflows directory."""
    print("🔄 Starting workflow reindexing...")
    
    db = WorkflowDatabase()
    
    # Get initial stats
    initial_stats = db.get_stats()
    print(f"📊 Current database: {initial_stats['total']} workflows")
    
    # Index all workflows (will skip unchanged files)
    print("📚 Indexing workflows...")
    index_stats = db.index_all_workflows(force_reindex=False)
    
    print(f"\n✅ Indexing complete!")
    print(f"   • Processed: {index_stats['processed']} new/changed")
    print(f"   • Skipped: {index_stats['skipped']} unchanged")
    print(f"   • Errors: {index_stats['errors']}")
    
    # Get final stats
    final_stats = db.get_stats()
    print(f"\n📊 Final database: {final_stats['total']} workflows")
    
    if index_stats['processed'] > 0:
        print(f"\n✨ Successfully indexed {index_stats['processed']} workflow(s)!")
        return 0
    else:
        print(f"\n💡 No new workflows found. All workflows are up to date.")
        return 0

if __name__ == "__main__":
    sys.exit(main())

