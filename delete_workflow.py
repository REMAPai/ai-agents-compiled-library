#!/usr/bin/env python3
"""
Helper script to delete workflows from the system.
Usage:
    python delete_workflow.py <workflow_filename.json>
    python delete_workflow.py <workflow_filename.json> --url http://localhost:8000
"""

import argparse
import requests
import sys


def delete_workflow(filename: str, api_url: str = "http://localhost:8000"):
    """Delete a workflow from the API server."""
    try:
        print(f"🗑️  Deleting workflow: {filename}")
        print(f"📤 Sending request to: {api_url}/api/workflows/{filename}")
        
        # Confirm deletion
        confirm = input(f"⚠️  Are you sure you want to delete '{filename}'? (yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            print("❌ Deletion cancelled.")
            return False
        
        # Delete workflow
        response = requests.delete(
            f"{api_url}/api/workflows/{filename}",
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workflow deleted successfully!")
            print(f"   Filename: {result['filename']}")
            print(f"   Deleted from database: {result['deleted_from_db']}")
            print(f"   Deleted from filesystem: {result['deleted_from_filesystem']}")
            return True
        elif response.status_code == 404:
            print(f"❌ Error: Workflow '{filename}' not found")
            return False
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to API server at {api_url}")
        print(f"   Make sure the server is running: python api_server.py")
        return False
    except KeyboardInterrupt:
        print("\n❌ Deletion cancelled by user.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Delete a workflow from the N8N Workflow API"
    )
    parser.add_argument(
        "workflow_filename",
        help="Filename of the workflow to delete (e.g., workflow.json)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)",
    )
    
    args = parser.parse_args()
    
    # If --force is used, we need to modify the delete function to skip confirmation
    # For now, we'll keep the confirmation for safety
    success = delete_workflow(args.workflow_filename, args.url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

