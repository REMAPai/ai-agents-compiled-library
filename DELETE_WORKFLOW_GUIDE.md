# Delete Workflow Guide

This guide explains how to remove/delete workflows from your N8N workflows app.

## Overview

When you delete a workflow, it will be:
- ✅ Removed from the database
- ✅ Deleted from the filesystem
- ✅ Removed from category mappings
- ✅ No longer searchable or accessible

## Methods to Delete Workflows

### Method 1: Using the Helper Script (Recommended)

```bash
# Delete a workflow (with confirmation prompt)
python delete_workflow.py workflow.json

# Delete with custom API URL
python delete_workflow.py workflow.json --url http://localhost:8000
```

The script will ask for confirmation before deleting.

### Method 2: Using curl

```bash
# Delete a workflow
curl -X DELETE "http://localhost:8000/api/workflows/workflow.json"
```

**Response:**
```json
{
  "message": "Workflow 'workflow.json' deleted successfully",
  "filename": "workflow.json",
  "deleted_from_db": true,
  "deleted_from_filesystem": true
}
```

### Method 3: Using Python requests

```python
import requests

# Delete a workflow
response = requests.delete(
    'http://localhost:8000/api/workflows/workflow.json'
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ {result['message']}")
    print(f"   Deleted from DB: {result['deleted_from_db']}")
    print(f"   Deleted from filesystem: {result['deleted_from_filesystem']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
```

### Method 4: Using Database CLI (Database Only)

If you only want to remove from the database (not delete the file):

```bash
python -m workflow_db --delete workflow.json
```

**Note:** This only removes from the database, not the filesystem.

## API Endpoint

### DELETE `/api/workflows/{filename}`

Delete a workflow by filename.

**Parameters:**
- `filename` (path parameter): The workflow filename (e.g., `workflow.json`)

**Response:**
```json
{
  "message": "Workflow 'workflow.json' deleted successfully",
  "filename": "workflow.json",
  "deleted_from_db": true,
  "deleted_from_filesystem": true
}
```

**Error Responses:**
- `404`: Workflow not found
- `400`: Invalid filename format
- `429`: Rate limit exceeded
- `500`: Server error

## What Gets Deleted

When you delete a workflow:

1. **Database Entry:**
   - Removed from `workflows` table
   - Removed from `workflows_fts` (full-text search) table
   - Database triggers handle FTS cleanup automatically

2. **File System:**
   - JSON file is deleted from the `workflows/` directory
   - File is removed from its subdirectory (e.g., `workflows/Webhook/workflow.json`)

3. **Category Mappings:**
   - Entry removed from `context/search_categories.json`
   - Category remains in `unique_categories.json` (if other workflows use it)

## Security Features

- ✅ Filename validation (prevents path traversal attacks)
- ✅ Rate limiting protection
- ✅ File path verification (ensures file is within workflows directory)
- ✅ Confirmation prompt in helper script

## Examples

### Example 1: Delete a Specific Workflow

```bash
# Find the workflow filename first
curl "http://localhost:8000/api/workflows?q=financial"

# Delete it
python delete_workflow.py financial_report.json
```

### Example 2: Delete Multiple Workflows

```bash
# Create a script to delete multiple workflows
for workflow in workflow1.json workflow2.json workflow3.json; do
    python delete_workflow.py "$workflow"
done
```

### Example 3: Delete via API with Error Handling

```python
import requests

workflows_to_delete = ["workflow1.json", "workflow2.json"]

for filename in workflows_to_delete:
    try:
        response = requests.delete(
            f'http://localhost:8000/api/workflows/{filename}'
        )
        if response.status_code == 200:
            print(f"✅ Deleted: {filename}")
        elif response.status_code == 404:
            print(f"⚠️  Not found: {filename}")
        else:
            print(f"❌ Error deleting {filename}: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception deleting {filename}: {e}")
```

## Troubleshooting

### Workflow Not Found

If you get a 404 error:
- Check the exact filename (case-sensitive)
- Verify the workflow exists: `curl "http://localhost:8000/api/workflows?q=filename"`
- Make sure the workflow was indexed in the database

### File Not Deleted from Filesystem

If `deleted_from_filesystem` is `false`:
- Check file permissions
- Verify the file path is correct
- Check server logs for errors

### Database Entry Not Removed

If the workflow still appears in search:
- The database delete should work automatically via triggers
- Try reindexing: `python reindex_workflows.py`
- Check database directly if needed

## Important Notes

⚠️ **Warning:** Deletion is permanent! There is no undo.

- Deleted workflows cannot be recovered
- Make sure you have backups if needed
- Consider archiving important workflows before deletion

## Best Practices

1. **Backup First:**
   ```bash
   # Download workflow before deleting
   curl "http://localhost:8000/api/workflows/workflow.json/download" \
     -o backup_workflow.json
   ```

2. **Verify Before Delete:**
   ```bash
   # Check workflow details first
   curl "http://localhost:8000/api/workflows/workflow.json"
   ```

3. **Use Confirmation:**
   - The helper script asks for confirmation
   - Always double-check the filename

4. **Batch Operations:**
   - Delete workflows one at a time
   - Verify each deletion was successful

## Related Commands

- **List workflows:** `curl "http://localhost:8000/api/workflows"`
- **Search workflows:** `curl "http://localhost:8000/api/workflows?q=search_term"`
- **Get workflow details:** `curl "http://localhost:8000/api/workflows/workflow.json"`
- **Reindex after deletion:** `python reindex_workflows.py`

