#!/usr/bin/env python3
"""
Helper script to manage workflow categories.
Usage:
    python manage_categories.py add "My New Category"
    python manage_categories.py assign workflow.json "My New Category"
    python manage_categories.py list
"""

import argparse
import requests
import json
import sys
from pathlib import Path


def add_category(category_name: str, api_url: str = "http://localhost:8000"):
    """Add a new category to the system."""
    try:
        print(f"📝 Adding category: {category_name}")
        
        response = requests.post(
            f"{api_url}/api/categories",
            json={"category": category_name},
            headers={"Content-Type": "application/json"},
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("added"):
                print(f"✅ Category '{category_name}' created successfully!")
                print(f"   It will now appear in the dropdown.")
            else:
                print(f"ℹ️  Category '{category_name}' already exists.")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to API server at {api_url}")
        print(f"   Make sure the server is running: python api_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def assign_category(filename: str, category: str, api_url: str = "http://localhost:8000"):
    """Assign a workflow to a category."""
    try:
        print(f"📝 Assigning '{filename}' to category '{category}'")
        
        response = requests.put(
            f"{api_url}/api/workflows/{filename}/category",
            json={"filename": filename, "category": category},
            headers={"Content-Type": "application/json"},
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['message']}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to API server at {api_url}")
        print(f"   Make sure the server is running: python api_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_categories(api_url: str = "http://localhost:8000"):
    """List all available categories."""
    try:
        response = requests.get(f"{api_url}/api/categories")
        
        if response.status_code == 200:
            result = response.json()
            categories = result.get("categories", [])
            
            print(f"📋 Available Categories ({len(categories)}):")
            print()
            for i, category in enumerate(categories, 1):
                print(f"   {i}. {category}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text}")
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
        description="Manage workflow categories in N8N Workflow API"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API server URL (default: http://localhost:8000)",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Add category command
    add_parser = subparsers.add_parser("add", help="Add a new category")
    add_parser.add_argument("category", help="Category name to add")
    
    # Assign category command
    assign_parser = subparsers.add_parser("assign", help="Assign workflow to category")
    assign_parser.add_argument("filename", help="Workflow filename (e.g., workflow.json)")
    assign_parser.add_argument("category", help="Category name")
    
    # List categories command
    list_parser = subparsers.add_parser("list", help="List all categories")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "add":
        success = add_category(args.category, args.url)
    elif args.command == "assign":
        success = assign_category(args.filename, args.category, args.url)
    elif args.command == "list":
        success = list_categories(args.url)
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

