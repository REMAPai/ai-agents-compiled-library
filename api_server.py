#!/usr/bin/env python3
"""
FastAPI Server for N8N Workflow Documentation
High-performance API with sub-100ms response times.
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any, Tuple
import json
import os
import re
import urllib.parse
from pathlib import Path
import uvicorn
import time
from collections import defaultdict

from workflow_db import WorkflowDatabase

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# SendGrid email integration
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    print("[WARNING] SendGrid not installed. Install with: pip install sendgrid")

# Initialize FastAPI app
app = FastAPI(
    title="N8N Workflow Documentation API",
    description="Fast API for browsing and searching workflow documentation",
    version="2.0.0",
)

# Security: Rate limiting storage
rate_limit_storage = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 60  # Configure as needed

# Add middleware for performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Security: Configure CORS properly - restrict origins in production
# For local development, you can use localhost
# For production, replace with your actual domain
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "https://zie619.github.io",  # GitHub Pages
    "https://n8n-workflows-1-xxgm.onrender.com",  # Community deployment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Security fix: Restrict origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Security fix: Only allow needed methods
    allow_headers=["Content-Type", "Authorization"],  # Security fix: Restrict headers
)

# Initialize database
db = WorkflowDatabase()


# Security: Helper function for rate limiting
def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit."""
    current_time = time.time()
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp
        for timestamp in rate_limit_storage[client_ip]
        if current_time - timestamp < 60
    ]
    # Check rate limit
    if len(rate_limit_storage[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        return False
    # Add current request
    rate_limit_storage[client_ip].append(current_time)
    return True


# Security: Helper function to validate and sanitize filenames
def validate_filename(filename: str) -> bool:
    """
    Validate filename to prevent path traversal attacks.
    Returns True if filename is safe, False otherwise.
    """
    # Decode URL encoding multiple times to catch encoded traversal attempts
    decoded = filename
    for _ in range(3):  # Decode up to 3 times to catch nested encodings
        try:
            decoded = urllib.parse.unquote(decoded, errors="strict")
        except:
            return False  # Invalid encoding

    # Check for path traversal patterns
    dangerous_patterns = [
        "..",  # Parent directory
        "..\\",  # Windows parent directory
        "../",  # Unix parent directory
        "\\",  # Backslash (Windows path separator)
        "/",  # Forward slash (Unix path separator)
        "\x00",  # Null byte
        "\n",
        "\r",  # Newlines
        "~",  # Home directory
        ":",  # Drive letter or stream (Windows)
        "|",
        "<",
        ">",  # Shell redirection
        "*",
        "?",  # Wildcards
        "$",  # Variable expansion
        ";",
        "&",  # Command separators
    ]

    for pattern in dangerous_patterns:
        if pattern in decoded:
            return False

    # Check for absolute paths
    if decoded.startswith("/") or decoded.startswith("\\"):
        return False

    # Check for Windows drive letters
    if len(decoded) >= 2 and decoded[1] == ":":
        return False

    # Only allow alphanumeric, dash, underscore, and .json extension
    if not re.match(r"^[a-zA-Z0-9_\-]+\.json$", decoded):
        return False

    # Additional check: filename should end with .json
    if not decoded.endswith(".json"):
        return False

    return True


# Startup function to verify database
@app.on_event("startup")
async def startup_event():
    """Verify database connectivity on startup."""
    try:
        stats = db.get_stats()
        if stats["total"] == 0:
            print("[WARNING] No workflows found in database. Run indexing first.")
        else:
            print(f"[OK] Database connected: {stats['total']} workflows indexed")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        raise


# Response models
class WorkflowSummary(BaseModel):
    id: Optional[int] = None
    filename: str
    name: str
    active: bool
    description: str = ""
    trigger_type: str = "Manual"
    complexity: str = "low"
    node_count: int = 0
    integrations: List[str] = []
    tags: List[str] = []
    category: str = "Uncategorized"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        # Allow conversion of int to bool for active field
        validate_assignment = True

    @field_validator("active", mode="before")
    @classmethod
    def convert_active(cls, v):
        if isinstance(v, int):
            return bool(v)
        return v


class SearchResponse(BaseModel):
    workflows: List[WorkflowSummary]
    total: int
    page: int
    per_page: int
    pages: int
    query: str
    filters: Dict[str, Any]


class StatsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    triggers: Dict[str, int]
    complexity: Dict[str, int]
    total_nodes: int
    unique_integrations: int
    last_indexed: str


class WorkflowUploadResponse(BaseModel):
    message: str
    filename: str
    filepath: str
    indexed: bool


@app.get("/")
async def root():
    """Serve the main documentation page."""
    static_dir = Path("static")
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            """
        <html><body>
        <h1>Setup Required</h1>
        <p>Static files not found. Please ensure the static directory exists with index.html</p>
        <p>Current directory: """
            + str(Path.cwd())
            + """</p>
        </body></html>
        """
        )
    return FileResponse(str(index_file))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "N8N Workflow API is running"}


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get workflow database statistics."""
    try:
        stats = db.get_stats()
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


@app.get("/api/workflows", response_model=SearchResponse)
async def search_workflows(
    q: str = Query("", description="Search query"),
    trigger: str = Query("all", description="Filter by trigger type"),
    complexity: str = Query("all", description="Filter by complexity"),
    category: str = Query("all", description="Filter by category"),
    active_only: bool = Query(False, description="Show only active workflows"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Search and filter workflows with pagination."""
    try:
        offset = (page - 1) * per_page

        workflows, total = db.search_workflows(
            query=q,
            trigger_filter=trigger,
            complexity_filter=complexity,
            category_filter=category,
            active_only=active_only,
            limit=per_page,
            offset=offset,
        )

        # Convert to Pydantic models with error handling
        workflow_summaries = []
        for workflow in workflows:
            try:
                # Get category - handle None, empty string, or missing
                category_value = workflow.get("category")
                if not category_value or (isinstance(category_value, str) and category_value.strip() == ""):
                    category_value = "Uncategorized"
                # Ensure it's a string
                category_value = str(category_value) if category_value else "Uncategorized"
                
                # Remove extra fields that aren't in the model
                clean_workflow = {
                    "id": workflow.get("id"),
                    "filename": workflow.get("filename", ""),
                    "name": workflow.get("name", ""),
                    "active": workflow.get("active", False),
                    "description": workflow.get("description", ""),
                    "trigger_type": workflow.get("trigger_type", "Manual"),
                    "complexity": workflow.get("complexity", "low"),
                    "node_count": workflow.get("node_count", 0),
                    "integrations": workflow.get("integrations", []),
                    "tags": workflow.get("tags", []),
                    "category": category_value,
                    "created_at": workflow.get("created_at"),
                    "updated_at": workflow.get("updated_at"),
                }
                workflow_summaries.append(WorkflowSummary(**clean_workflow))
            except Exception as e:
                print(
                    f"Error converting workflow {workflow.get('filename', 'unknown')}: {e}"
                )
                # Continue with other workflows instead of failing completely
                continue

        pages = (total + per_page - 1) // per_page  # Ceiling division

        return SearchResponse(
            workflows=workflow_summaries,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            query=q,
            filters={
                "trigger": trigger,
                "complexity": complexity,
                "category": category,
                "active_only": active_only,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching workflows: {str(e)}"
        )


@app.get("/api/workflows/{filename}")
async def get_workflow_detail(filename: str, request: Request):
    """Get detailed workflow information including raw JSON."""
    try:
        # Security: Validate filename to prevent path traversal
        if not validate_filename(filename):
            print(f"Security: Blocked path traversal attempt for filename: {filename}")
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        # Get workflow metadata from database
        workflows, _ = db.search_workflows(f'filename:"{filename}"', limit=1)
        if not workflows:
            raise HTTPException(
                status_code=404, detail="Workflow not found in database"
            )

        workflow_meta = workflows[0]

        # Load raw JSON from file with security checks
        workflows_path = Path("workflows").resolve()

        # Find the file safely
        matching_file = None
        for subdir in workflows_path.iterdir():
            if subdir.is_dir():
                target_file = subdir / filename
                if target_file.exists() and target_file.is_file():
                    # Verify the file is actually within workflows directory
                    try:
                        target_file.resolve().relative_to(workflows_path)
                        matching_file = target_file
                        break
                    except ValueError:
                        print(
                            f"Security: Blocked access to file outside workflows: {target_file}"
                        )
                        continue

        if not matching_file:
            print(f"Warning: File {filename} not found in workflows directory")
            raise HTTPException(
                status_code=404,
                detail=f"Workflow file '{filename}' not found on filesystem",
            )

        with open(matching_file, "r", encoding="utf-8") as f:
            raw_json = json.load(f)

        return {"metadata": workflow_meta, "raw_json": raw_json}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading workflow: {str(e)}")


@app.get("/api/workflows/{filename}/download")
async def download_workflow(filename: str, request: Request):
    """Download workflow JSON file with security validation."""
    try:
        # Security: Validate filename to prevent path traversal
        if not validate_filename(filename):
            print(f"Security: Blocked path traversal attempt for filename: {filename}")
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        # Only search within the workflows directory
        workflows_path = Path("workflows").resolve()  # Get absolute path

        # Find the file safely
        json_files = []
        for subdir in workflows_path.iterdir():
            if subdir.is_dir():
                target_file = subdir / filename
                if target_file.exists() and target_file.is_file():
                    # Verify the file is actually within workflows directory (defense in depth)
                    try:
                        target_file.resolve().relative_to(workflows_path)
                        json_files.append(target_file)
                    except ValueError:
                        # File is outside workflows directory
                        print(
                            f"Security: Blocked access to file outside workflows: {target_file}"
                        )
                        continue

        if not json_files:
            print(f"File {filename} not found in workflows directory")
            raise HTTPException(
                status_code=404, detail=f"Workflow file '{filename}' not found"
            )

        file_path = json_files[0]

        # Final security check: Ensure file is within workflows directory
        try:
            file_path.resolve().relative_to(workflows_path)
        except ValueError:
            print(
                f"Security: Blocked final attempt to access file outside workflows: {file_path}"
            )
            raise HTTPException(status_code=403, detail="Access denied")

        return FileResponse(
            str(file_path), media_type="application/json", filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading workflow {filename}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error downloading workflow: {str(e)}"
        )


@app.delete("/api/workflows/{filename}")
async def delete_workflow(filename: str, request: Request):
    """Delete a workflow from both the database and filesystem."""
    try:
        # Security: Validate filename to prevent path traversal
        if not validate_filename(filename):
            print(f"Security: Blocked path traversal attempt for filename: {filename}")
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        # Check if workflow exists in database
        workflows, _ = db.search_workflows(f'filename:"{filename}"', limit=1)
        if not workflows:
            raise HTTPException(
                status_code=404, detail="Workflow not found in database"
            )

        # Find and delete the file
        workflows_path = Path("workflows").resolve()
        matching_file = None
        
        for subdir in workflows_path.iterdir():
            if subdir.is_dir():
                target_file = subdir / filename
                if target_file.exists() and target_file.is_file():
                    try:
                        target_file.resolve().relative_to(workflows_path)
                        matching_file = target_file
                        break
                    except ValueError:
                        continue

        # Delete from database
        deleted_from_db = db.delete_workflow(filename)
        if not deleted_from_db:
            raise HTTPException(
                status_code=500, detail="Failed to delete workflow from database"
            )

        # Delete file from filesystem
        file_deleted = False
        if matching_file:
            try:
                matching_file.unlink()
                file_deleted = True
                print(f"[OK] Deleted workflow file: {matching_file}")
            except Exception as e:
                print(f"⚠️  Warning: Could not delete file {matching_file}: {e}")

        # Remove from category mappings if exists
        try:
            search_categories_file = Path("context/search_categories.json")
            if search_categories_file.exists():
                with open(search_categories_file, "r", encoding="utf-8") as f:
                    categories = json.load(f)
                
                # Remove entry for this filename
                categories = [item for item in categories if item.get("filename") != filename]
                
                with open(search_categories_file, "w", encoding="utf-8") as f:
                    json.dump(categories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Warning: Could not update category mappings: {e}")

        return {
            "message": f"Workflow '{filename}' deleted successfully",
            "filename": filename,
            "deleted_from_db": True,
            "deleted_from_filesystem": file_deleted
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting workflow: {str(e)}"
        )


@app.get("/api/workflows/{filename}/diagram")
async def get_workflow_diagram(filename: str, request: Request):
    """Get Mermaid diagram code for workflow visualization."""
    try:
        # Security: Validate filename to prevent path traversal
        if not validate_filename(filename):
            print(f"Security: Blocked path traversal attempt for filename: {filename}")
            raise HTTPException(status_code=400, detail="Invalid filename format")

        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        # Only search within the workflows directory
        workflows_path = Path("workflows").resolve()

        # Find the file safely
        matching_file = None
        for subdir in workflows_path.iterdir():
            if subdir.is_dir():
                target_file = subdir / filename
                if target_file.exists() and target_file.is_file():
                    # Verify the file is actually within workflows directory
                    try:
                        target_file.resolve().relative_to(workflows_path)
                        matching_file = target_file
                        break
                    except ValueError:
                        print(
                            f"Security: Blocked access to file outside workflows: {target_file}"
                        )
                        continue

        if not matching_file:
            print(f"Warning: File {filename} not found in workflows directory")
            raise HTTPException(
                status_code=404,
                detail=f"Workflow file '{filename}' not found on filesystem",
            )

        with open(matching_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])
        connections = data.get("connections", {})

        # Generate Mermaid diagram
        diagram = generate_mermaid_diagram(nodes, connections)

        return {"diagram": diagram}
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in {filename}: {str(e)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON in workflow file: {str(e)}"
        )
    except Exception as e:
        print(f"Error generating diagram for {filename}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating diagram: {str(e)}"
        )


def determine_workflow_directory(workflow_data: Dict) -> str:
    """Determine the appropriate subdirectory for a workflow based on its content."""
    nodes = workflow_data.get("nodes", [])
    if not nodes:
        return "Manual"  # Default directory
    
    # Get the first non-utility node to determine category
    service_mappings = {
        "telegram": "Telegram",
        "discord": "Discord",
        "slack": "Slack",
        "gmail": "Gmail",
        "googlesheets": "Googlesheets",
        "googledrive": "Googledrive",
        "webhook": "Webhook",
        "http": "Http",
        "schedule": "Schedule",
        "cron": "Cron",
        "postgres": "Postgres",
        "mysql": "Mysqltool",
        "mongodb": "Mongodbtool",
        "airtable": "Airtable",
        "github": "Github",
        "gitlab": "Gitlab",
        "jira": "Jira",
        "openai": "Openai",
        "notion": "Notion",
        "shopify": "Shopify",
        "stripe": "Stripe",
        "twitter": "Twitter",
        "linkedin": "Linkedin",
        "facebook": "Facebook",
        "instagram": "Instagram",
        "whatsapp": "Whatsapp",
        "trello": "Trello",
        "asana": "Asana",
        "mondaycom": "Mondaycom",
        "dropbox": "Dropbox",
        "onedrive": "Microsoftonedrive",
        "outlook": "Microsoftoutlook",
        "calendly": "Calendly",
        "typeform": "Typeform",
        "youtube": "Youtube",
        "wordpress": "Wordpress",
        "woocommerce": "Woocommerce",
    }
    
    # Check all nodes to find the primary service
    primary_service = None
    for node in nodes:
        node_type = node.get("type", "").lower()
        node_name = node.get("name", "").lower()
        
        # Check for webhook first (common trigger)
        if "webhook" in node_type or "webhook" in node_name:
            if not primary_service or primary_service == "Manual":
                primary_service = "Webhook"
        
        # Check for scheduled/cron
        if "cron" in node_type or "schedule" in node_type:
            if not primary_service or primary_service == "Manual":
                primary_service = "Schedule"
        
        # Check for service mappings
        for key, directory in service_mappings.items():
            if key in node_type or key in node_name:
                if not primary_service or primary_service in ["Manual", "Webhook", "Schedule"]:
                    primary_service = directory
                    break
        
        if primary_service and primary_service not in ["Manual", "Webhook", "Schedule"]:
            break
    
    # If no specific service found, use the first node type or default
    if not primary_service or primary_service == "Manual":
        if nodes:
            first_node_type = nodes[0].get("type", "")
            if "n8n-nodes-base." in first_node_type:
                service_name = first_node_type.replace("n8n-nodes-base.", "").split(".")[0]
                # Capitalize first letter
                primary_service = service_name.capitalize()
            else:
                primary_service = "Manual"
        else:
            primary_service = "Manual"
    
    return primary_service


def save_workflow_file(workflow_data: Dict, filename: Optional[str] = None) -> Tuple[str, str]:
    """Save workflow JSON to the appropriate directory and return (filepath, filename)."""
    workflows_dir = Path("workflows")
    workflows_dir.mkdir(exist_ok=True)
    
    # Determine subdirectory
    subdirectory = determine_workflow_directory(workflow_data)
    subdir_path = workflows_dir / subdirectory
    subdir_path.mkdir(exist_ok=True)
    
    # Generate filename if not provided
    if not filename:
        # Use workflow name or ID to create filename
        workflow_name = workflow_data.get("name", "workflow")
        workflow_id = workflow_data.get("id", "")
        
        # Clean name for filename
        clean_name = re.sub(r'[^\w\s-]', '', workflow_name).strip()
        clean_name = re.sub(r'[-\s]+', '_', clean_name)
        
        if workflow_id:
            filename = f"{workflow_id}_{clean_name}.json"
        else:
            # Use timestamp if no ID
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{clean_name}.json"
    
    # Ensure .json extension
    if not filename.endswith(".json"):
        filename += ".json"
    
    # Validate filename
    if not validate_filename(filename):
        # Sanitize filename if invalid
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        if not filename.endswith(".json"):
            filename += ".json"
    
    filepath = subdir_path / filename
    
    # Write workflow JSON
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(workflow_data, f, indent=2, ensure_ascii=False)
    
    return str(filepath), filename


def generate_mermaid_diagram(nodes: List[Dict], connections: Dict) -> str:
    """Generate Mermaid.js flowchart code from workflow nodes and connections."""
    if not nodes:
        return "graph TD\n  EmptyWorkflow[No nodes found in workflow]"

    # Create mapping for node names to ensure valid mermaid IDs
    mermaid_ids = {}
    for i, node in enumerate(nodes):
        node_id = f"node{i}"
        node_name = node.get("name", f"Node {i}")
        mermaid_ids[node_name] = node_id

    # Start building the mermaid diagram
    mermaid_code = ["graph TD"]

    # Add nodes with styling
    for node in nodes:
        node_name = node.get("name", "Unnamed")
        node_id = mermaid_ids[node_name]
        node_type = node.get("type", "").replace("n8n-nodes-base.", "")

        # Determine node style based on type
        style = ""
        if any(x in node_type.lower() for x in ["trigger", "webhook", "cron"]):
            style = "fill:#b3e0ff,stroke:#0066cc"  # Blue for triggers
        elif any(x in node_type.lower() for x in ["if", "switch"]):
            style = "fill:#ffffb3,stroke:#e6e600"  # Yellow for conditional nodes
        elif any(x in node_type.lower() for x in ["function", "code"]):
            style = "fill:#d9b3ff,stroke:#6600cc"  # Purple for code nodes
        elif "error" in node_type.lower():
            style = "fill:#ffb3b3,stroke:#cc0000"  # Red for error handlers
        else:
            style = "fill:#d9d9d9,stroke:#666666"  # Gray for other nodes

        # Add node with label (escaping special characters)
        clean_name = node_name.replace('"', "'")
        clean_type = node_type.replace('"', "'")
        label = f"{clean_name}<br>({clean_type})"
        mermaid_code.append(f'  {node_id}["{label}"]')
        mermaid_code.append(f"  style {node_id} {style}")

    # Add connections between nodes
    for source_name, source_connections in connections.items():
        if source_name not in mermaid_ids:
            continue

        if isinstance(source_connections, dict) and "main" in source_connections:
            main_connections = source_connections["main"]

            for i, output_connections in enumerate(main_connections):
                if not isinstance(output_connections, list):
                    continue

                for connection in output_connections:
                    if not isinstance(connection, dict) or "node" not in connection:
                        continue

                    target_name = connection["node"]
                    if target_name not in mermaid_ids:
                        continue

                    # Add arrow with output index if multiple outputs
                    label = f" -->|{i}| " if len(main_connections) > 1 else " --> "
                    mermaid_code.append(
                        f"  {mermaid_ids[source_name]}{label}{mermaid_ids[target_name]}"
                    )

    # Format the final mermaid diagram code
    return "\n".join(mermaid_code)


@app.post("/api/reindex")
async def reindex_workflows(
    background_tasks: BackgroundTasks,
    request: Request,
    force: bool = False,
    admin_token: Optional[str] = Query(None, description="Admin authentication token"),
):
    """Trigger workflow reindexing in the background (requires authentication)."""
    # Security: Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Please try again later."
        )

    # Security: Basic authentication check
    # In production, use proper authentication (JWT, OAuth, etc.)
    # For now, check for environment variable or disable endpoint

    expected_token = os.environ.get("ADMIN_TOKEN", None)

    if not expected_token:
        # If no token is configured, disable the endpoint for security
        raise HTTPException(
            status_code=503,
            detail="Reindexing endpoint is disabled. Set ADMIN_TOKEN environment variable to enable.",
        )

    if admin_token != expected_token:
        print(f"Security: Unauthorized reindex attempt from {client_ip}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    def run_indexing():
        try:
            db.index_all_workflows(force_reindex=force)
            print(f"Reindexing completed successfully (requested by {client_ip})")
        except Exception as e:
            print(f"Error during reindexing: {e}")

    background_tasks.add_task(run_indexing)
    return {"message": "Reindexing started in background", "requested_by": client_ip}


@app.get("/api/integrations")
async def get_integrations():
    """Get list of all unique integrations."""
    try:
        stats = db.get_stats()
        # For now, return basic info. Could be enhanced to return detailed integration stats
        return {"integrations": [], "count": stats["unique_integrations"]}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching integrations: {str(e)}"
        )


@app.get("/api/categories")
async def get_categories():
    """Get available workflow categories for filtering."""
    try:
        # Try to load from the generated unique categories file
        categories_file = Path("context/unique_categories.json")
        if categories_file.exists():
            with open(categories_file, "r", encoding="utf-8") as f:
                categories = json.load(f)
            return {"categories": categories}
        else:
            # Fallback: extract categories from search_categories.json
            search_categories_file = Path("context/search_categories.json")
            if search_categories_file.exists():
                with open(search_categories_file, "r", encoding="utf-8") as f:
                    search_data = json.load(f)

                unique_categories = set()
                for item in search_data:
                    if item.get("category"):
                        unique_categories.add(item["category"])
                    else:
                        unique_categories.add("Uncategorized")

                categories = sorted(list(unique_categories))
                return {"categories": categories}
            else:
                # Last resort: return basic categories
                return {"categories": ["Uncategorized"]}

    except Exception as e:
        print(f"Error loading categories: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching categories: {str(e)}"
        )


def send_purchase_notification_email(user_email: str, description: str, workflow_name: str, workflow_filename: str):
    """Send email notification to admin about purchase request using SendGrid."""
    if not SENDGRID_AVAILABLE:
        print("[WARNING] SendGrid not available, skipping email notification")
        return False

    # Get SendGrid API key from environment variable
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    if not sendgrid_api_key:
        print("[WARNING] SENDGRID_API_KEY not set, skipping email notification")
        return False

    admin_email = "tq@remap.ai"
    from_email = os.environ.get("SMTP_EMAIL", "support@aiagents.co.id")
    
    try:
        # Create email content
        subject = f"New Purchase Request: {workflow_name}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #3151DD;">New Agent Request</h2>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #3151DD;">Request Details</h3>
                    <p><strong>User Email:</strong> {user_email}</p>
                    <p><strong>Workflow Name:</strong> {workflow_name}</p>
                    <p><strong>Workflow Filename:</strong> {workflow_filename}</p>
                    <p><strong>Request Time:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <div style="background: #ffffff; padding: 15px; border-left: 4px solid #3151DD; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #3151DD;">Description</h3>
                    <p style="white-space: pre-wrap;">{description}</p>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
                    <p>This is an automated notification from the Workflow Library system.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
New Agent Purchase Request

User Email: {user_email}
Workflow Name: {workflow_name}
Workflow Filename: {workflow_filename}
Request Time: {time.strftime('%Y-%m-%d %H:%M:%S')}

Description:
{description}

---
This is an automated notification from the Workflow Library system.
        """

        # Create Mail object
        message = Mail(
            from_email=Email(from_email, "Workflow Library"),
            to_emails=To(admin_email),
            subject=subject,
            plain_text_content=text_content,
            html_content=html_content
        )

        # Send email
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print(f"[OK] Purchase request email sent to {admin_email}")
            return True
        else:
            print(f"[ERROR] SendGrid returned status {response.status_code}: {response.body}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to send purchase request email: {str(e)}")
        return False


@app.post("/api/purchase-request")
async def submit_purchase_request(request: Request, background_tasks: BackgroundTasks):
    """Handle purchase request submission and notify admin."""
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        description = data.get("description", "").strip()
        workflow_name = data.get("workflowName", "")
        workflow_filename = data.get("workflowFilename", "")
        user_role = data.get("userRole", "user")

        if not email or not description:
            raise HTTPException(
                status_code=400, detail="Email and description are required"
            )

        # Log the purchase request
        print(f"[PURCHASE REQUEST]")
        print(f"  Email: {email}")
        print(f"  Description: {description}")
        print(f"  Workflow: {workflow_name} ({workflow_filename})")
        print(f"  User Role: {user_role}")
        print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Send email notification to admin in background
        background_tasks.add_task(
            send_purchase_notification_email,
            email,
            description,
            workflow_name,
            workflow_filename
        )

        return {
            "success": True,
            "message": "Purchase request submitted successfully. Admin will be notified.",
            "email": email,
            "workflow": workflow_name,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error submitting purchase request: {str(e)}"
        )


@app.get("/api/category-mappings")
async def get_category_mappings():
    """Get filename to category mappings for client-side filtering."""
    try:
        search_categories_file = Path("context/search_categories.json")
        if not search_categories_file.exists():
            return {"mappings": {}}

        with open(search_categories_file, "r", encoding="utf-8") as f:
            search_data = json.load(f)

        # Convert to a simple filename -> category mapping
        mappings = {}
        for item in search_data:
            filename = item.get("filename")
            category = item.get("category") or "Uncategorized"
            if filename:
                mappings[filename] = category

        return {"mappings": mappings}

    except Exception as e:
        print(f"Error loading category mappings: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching category mappings: {str(e)}"
        )


@app.get("/api/workflows/category/{category}", response_model=SearchResponse)
async def search_workflows_by_category(
    category: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Search workflows by service category (messaging, database, ai_ml, etc.)."""
    try:
        offset = (page - 1) * per_page

        workflows, total = db.search_by_category(
            category=category, limit=per_page, offset=offset
        )

        # Convert to Pydantic models with error handling
        workflow_summaries = []
        for workflow in workflows:
            try:
                clean_workflow = {
                    "id": workflow.get("id"),
                    "filename": workflow.get("filename", ""),
                    "name": workflow.get("name", ""),
                    "active": workflow.get("active", False),
                    "description": workflow.get("description", ""),
                    "trigger_type": workflow.get("trigger_type", "Manual"),
                    "complexity": workflow.get("complexity", "low"),
                    "node_count": workflow.get("node_count", 0),
                    "integrations": workflow.get("integrations", []),
                    "tags": workflow.get("tags", []),
                    "created_at": workflow.get("created_at"),
                    "updated_at": workflow.get("updated_at"),
                }
                workflow_summaries.append(WorkflowSummary(**clean_workflow))
            except Exception as e:
                print(
                    f"Error converting workflow {workflow.get('filename', 'unknown')}: {e}"
                )
                continue

        pages = (total + per_page - 1) // per_page

        return SearchResponse(
            workflows=workflow_summaries,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            query=f"category:{category}",
            filters={"category": category},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching by category: {str(e)}"
        )


@app.post("/api/workflows/upload", response_model=WorkflowUploadResponse)
async def upload_workflow(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    workflow_json: Optional[str] = Form(None),
):
    """
    Upload a new workflow JSON file.
    Can accept either a file upload or JSON string in form data.
    """
    try:
        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        workflow_data = None
        provided_filename = None

        # Handle file upload
        if file:
            if not file.filename.endswith(".json"):
                raise HTTPException(
                    status_code=400, detail="File must be a JSON file (.json extension)"
                )
            
            provided_filename = file.filename
            content = await file.read()
            try:
                workflow_data = json.loads(content.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid JSON in file: {str(e)}"
                )
        
        # Handle JSON string in form data
        elif workflow_json:
            try:
                workflow_data = json.loads(workflow_json)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid JSON string: {str(e)}"
                )
        
        # Handle raw JSON in request body (if Content-Type is application/json)
        else:
            try:
                body = await request.body()
                if body:
                    workflow_data = await request.json()
            except:
                raise HTTPException(
                    status_code=400,
                    detail="No workflow data provided. Send JSON in body, file upload, or workflow_json form field.",
                )

        if not workflow_data:
            raise HTTPException(
                status_code=400, detail="No valid workflow data provided"
            )

        # Validate workflow structure
        if not isinstance(workflow_data, dict):
            raise HTTPException(
                status_code=400, detail="Workflow data must be a JSON object"
            )

        # Save workflow file
        filepath, filename = save_workflow_file(workflow_data, provided_filename)

        # Index the workflow in background
        def index_workflow():
            try:
                db.index_all_workflows(force_reindex=False)
                print(f"[OK] Workflow {filename} indexed successfully")
            except Exception as e:
                print(f"[ERROR] Error indexing workflow {filename}: {e}")

        background_tasks.add_task(index_workflow)

        return WorkflowUploadResponse(
            message="Workflow uploaded successfully",
            filename=filename,
            filepath=filepath,
            indexed=True,  # Will be indexed in background
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error uploading workflow: {str(e)}"
        )


@app.post("/api/workflows/upload-json")
async def upload_workflow_json(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Upload a workflow by sending JSON directly in the request body.
    Content-Type should be application/json.
    """
    try:
        # Security: Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded. Please try again later."
            )

        # Parse JSON from request body
        workflow_data = await request.json()

        if not isinstance(workflow_data, dict):
            raise HTTPException(
                status_code=400, detail="Workflow data must be a JSON object"
            )

        # Save workflow file
        filepath, filename = save_workflow_file(workflow_data)

        # Index the workflow in background
        def index_workflow():
            try:
                db.index_all_workflows(force_reindex=False)
                print(f"[OK] Workflow {filename} indexed successfully")
            except Exception as e:
                print(f"[ERROR] Error indexing workflow {filename}: {e}")

        background_tasks.add_task(index_workflow)

        return WorkflowUploadResponse(
            message="Workflow uploaded successfully",
            filename=filename,
            filepath=filepath,
            indexed=True,
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error uploading workflow: {str(e)}"
        )


# Custom exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500, content={"detail": f"Internal server error: {str(exc)}"}
    )


# Mount static files AFTER all routes are defined
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print(f"[OK] Static files mounted from {static_dir.absolute()}")
else:
    print(f"[WARNING] Static directory not found at {static_dir.absolute()}")


def create_static_directory():
    """Create static directory if it doesn't exist."""
    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)
    return static_dir


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    # Ensure static directory exists
    create_static_directory()

    # Debug: Check database connectivity
    try:
        stats = db.get_stats()
        print(f"[OK] Database connected: {stats['total']} workflows found")
        if stats["total"] == 0:
            print("[INFO] Database is empty. Indexing workflows...")
            db.index_all_workflows()
            stats = db.get_stats()
    except Exception as e:
        print(f"[ERROR] Database error: {e}")
        print("[INFO] Attempting to create and index database...")
        try:
            db.index_all_workflows()
            stats = db.get_stats()
            print(f"[OK] Database created: {stats['total']} workflows indexed")
        except Exception as e2:
            print(f"[ERROR] Failed to create database: {e2}")
            stats = {"total": 0}

    # Debug: Check static files
    static_path = Path("static")
    if static_path.exists():
        files = list(static_path.glob("*"))
        print(f"[OK] Static files found: {[f.name for f in files]}")
    else:
        print(f"[WARNING] Static directory not found at: {static_path.absolute()}")

    print("[START] Starting N8N Workflow Documentation API")
    print(f"[INFO] Database contains {stats['total']} workflows")
    print(f"[INFO] Server will be available at: http://{host}:{port}")
    print(f"[INFO] Static files at: http://{host}:{port}/static/")

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        access_log=True,  # Enable access logs for debugging
        log_level="info",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="N8N Workflow Documentation API Server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    run_server(host=args.host, port=args.port, reload=args.reload)
