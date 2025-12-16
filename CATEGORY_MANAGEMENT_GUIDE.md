# Category Management Guide

This guide explains how to add new categories to your workflow dropdown and assign workflows to them.

## Overview

Categories are used to organize and filter workflows in the dashboard. You can:
- ✅ Add new categories dynamically
- ✅ Assign workflows to categories
- ✅ Categories automatically appear in the dropdown
- ✅ Categories are stored in `context/unique_categories.json`

## Methods to Add Categories

### Method 1: Using the Helper Script (Recommended)

```bash
# Add a new category
python manage_categories.py add "My New Category"

# List all categories
python manage_categories.py list

# Assign a workflow to a category
python manage_categories.py assign "workflow.json" "My New Category"
```

### Method 2: Using curl

```bash
# Add a new category
curl -X POST "http://localhost:8000/api/categories" \
  -H "Content-Type: application/json" \
  -d '{"category": "My New Category"}'

# Assign workflow to category
curl -X PUT "http://localhost:8000/api/workflows/workflow.json/category" \
  -H "Content-Type: application/json" \
  -d '{"filename": "workflow.json", "category": "My New Category"}'
```

### Method 3: Using Python requests

```python
import requests

# Add a new category
response = requests.post(
    'http://localhost:8000/api/categories',
    json={'category': 'My New Category'}
)
print(response.json())

# Assign workflow to category
response = requests.put(
    'http://localhost:8000/api/workflows/workflow.json/category',
    json={'filename': 'workflow.json', 'category': 'My New Category'}
)
print(response.json())
```

### Method 4: During Workflow Upload

When uploading a workflow, you can specify a category. If the category doesn't exist, it will be automatically created:

```bash
python upload_workflow.py workflow.json \
  --category "My New Category" \
  --active true
```

## API Endpoints

### POST `/api/categories`

Create a new category.

**Request Body:**
```json
{
  "category": "My New Category",
  "description": "Optional description"
}
```

**Response:**
```json
{
  "message": "Category 'My New Category' created successfully",
  "category": "My New Category",
  "added": true
}
```

### PUT `/api/workflows/{filename}/category`

Assign a workflow to a category.

**Request Body:**
```json
{
  "filename": "workflow.json",
  "category": "My New Category"
}
```

**Response:**
```json
{
  "message": "Workflow 'workflow.json' assigned to category 'My New Category'",
  "filename": "workflow.json",
  "category": "My New Category"
}
```

### GET `/api/categories`

Get all available categories (used by the dropdown).

**Response:**
```json
{
  "categories": [
    "AI Agent Development",
    "Business Process Automation",
    "Financial & Accounting",
    "My New Category",
    ...
  ]
}
```

## How It Works

1. **Adding a Category:**
   - Category is added to `context/unique_categories.json`
   - Category immediately appears in the dropdown
   - No server restart needed

2. **Assigning Workflow:**
   - Workflow category is stored in `context/search_categories.json`
   - Category is automatically added to unique categories if new
   - Workflow appears when filtering by that category

3. **Dynamic Updates:**
   - Categories are dynamically extracted from both files
   - New categories from `search_categories.json` automatically appear
   - Dropdown refreshes when page reloads

## Example Workflow

### Step 1: Add a New Category

```bash
python manage_categories.py add "Healthcare Automation"
```

### Step 2: Upload Workflow with Category

```bash
python upload_workflow.py healthcare_workflow.json \
  --category "Healthcare Automation" \
  --active true
```

Or assign existing workflow:

```bash
python manage_categories.py assign "healthcare_workflow.json" "Healthcare Automation"
```

### Step 3: Verify in Dashboard

1. Open `http://localhost:8000`
2. Check the category dropdown - "Healthcare Automation" should appear
3. Select the category to filter workflows

## Common Categories

Here are some common category suggestions:

- **Industry-Specific:**
  - Healthcare Automation
  - Education & E-Learning
  - Real Estate Management
  - Legal & Compliance
  - Manufacturing & Supply Chain

- **Function-Specific:**
  - Customer Support Automation
  - Inventory Management
  - HR & Recruitment
  - Financial Reporting
  - Quality Assurance

- **Technology-Specific:**
  - API Integration
  - Database Management
  - Cloud Infrastructure
  - Security & Monitoring

## Notes

- Category names are case-sensitive
- Categories are automatically sorted alphabetically
- "Uncategorized" is always available as a default
- Categories persist across server restarts
- You can assign multiple workflows to the same category

## Troubleshooting

**Category not appearing in dropdown:**
- Refresh the page (categories are loaded on page load)
- Check that the category was added successfully
- Verify the API server is running

**Workflow not showing in category filter:**
- Ensure the workflow is assigned to the category
- Check the workflow filename matches exactly
- Reindex workflows: `python reindex_workflows.py`

