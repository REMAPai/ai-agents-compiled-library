#!/usr/bin/env python3
"""
Helper script to upload a workflow JSON file to the FastAPI server.
Usage:
    python upload_workflow.py <workflow.json>
    python upload_workflow.py <workflow.json> --url http://localhost:8000
"""

import argparse
import json
import sys
from pathlib import Path
import requests


def upload_workflow(
    file_path: str, 
    api_url: str = "http://localhost:8000",
    active: bool = None,
    category: str = None
):
    """Upload a workflow JSON file to the API server."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ Error: File '{file_path}' not found")
        return False
    
    if not file_path.suffix == ".json":
        print(f"⚠️  Warning: File '{file_path}' is not a .json file")
    
    try:
        # Read workflow JSON
        with open(file_path, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)
        
        print(f"📄 Reading workflow from: {file_path}")
        print(f"📤 Uploading to: {api_url}/api/workflows/upload-json")
        
        # Build query parameters
        params = {}
        if active is not None:
            params["active"] = str(active).lower()
            print(f"   Active: {active}")
        if category:
            params["category"] = category
            print(f"   Category: {category}")
        
        # Upload to API
        response = requests.post(
            f"{api_url}/api/workflows/upload-json",
            json=workflow_data,
            headers={"Content-Type": "application/json"},
            params=params,
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow uploaded successfully!")
            print(f"   Filename: {result['filename']}")
            print(f"   Filepath: {result['filepath']}")
            print(f"   Indexed: {result['indexed']}")
            return True
        else:
            print(f"❌ Error uploading workflow: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file: {e}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to API server at {api_url}")
        print(f"   Make sure the server is running: python api_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Upload a workflow JSON file to the N8N Workflow API"
    )
    parser.add_argument(
        "workflow_file",
        help="Path to the workflow JSON file",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--active",
        type=lambda x: x.lower() == "true",
        help="Set workflow as active (true/false)",
    )
    parser.add_argument(
        "--category",
        help="Assign workflow to a category (e.g., 'Financial & Accounting')",
    )
    
    args = parser.parse_args()
    
    success = upload_workflow(
        args.workflow_file, 
        args.url,
        active=args.active,
        category=args.category
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


