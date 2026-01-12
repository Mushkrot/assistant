"""REST API routes for knowledge management and session info."""

import os
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["api"])

# Workspaces directory
WORKSPACES_DIR = Path("./workspaces")


class WorkspaceInfo(BaseModel):
    """Workspace information."""
    name: str
    file_count: int
    total_size: int


class FileInfo(BaseModel):
    """File information."""
    filename: str
    size: int


class WorkspaceStats(BaseModel):
    """Workspace statistics."""
    name: str
    file_count: int
    total_size: int
    files: List[FileInfo]


# Workspace endpoints

@router.post("/workspaces", response_model=WorkspaceInfo)
async def create_workspace(name: str):
    """Create a new workspace."""
    workspace_path = WORKSPACES_DIR / name

    if workspace_path.exists():
        raise HTTPException(status_code=400, detail="Workspace already exists")

    workspace_path.mkdir(parents=True, exist_ok=True)

    return WorkspaceInfo(name=name, file_count=0, total_size=0)


@router.get("/workspaces", response_model=List[WorkspaceInfo])
async def list_workspaces():
    """List all workspaces."""
    if not WORKSPACES_DIR.exists():
        WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        return []

    workspaces = []
    for workspace_path in WORKSPACES_DIR.iterdir():
        if workspace_path.is_dir():
            files = list(workspace_path.glob("*.md"))
            total_size = sum(f.stat().st_size for f in files)
            workspaces.append(WorkspaceInfo(
                name=workspace_path.name,
                file_count=len(files),
                total_size=total_size
            ))

    return workspaces


@router.get("/workspaces/{name}/stats", response_model=WorkspaceStats)
async def get_workspace_stats(name: str):
    """Get workspace statistics."""
    workspace_path = WORKSPACES_DIR / name

    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    files = []
    total_size = 0

    for file_path in workspace_path.glob("*.md"):
        size = file_path.stat().st_size
        total_size += size
        files.append(FileInfo(filename=file_path.name, size=size))

    return WorkspaceStats(
        name=name,
        file_count=len(files),
        total_size=total_size,
        files=files
    )


@router.post("/workspaces/{name}/files")
async def upload_file(name: str, file: UploadFile = File(...)):
    """Upload a file to workspace."""
    workspace_path = WORKSPACES_DIR / name

    if not workspace_path.exists():
        workspace_path.mkdir(parents=True, exist_ok=True)

    # Only allow .md files
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are allowed")

    file_path = workspace_path / file.filename

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {"filename": file.filename, "size": len(content)}


@router.get("/workspaces/{name}/files", response_model=List[FileInfo])
async def list_files(name: str):
    """List files in workspace."""
    workspace_path = WORKSPACES_DIR / name

    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    files = []
    for file_path in workspace_path.glob("*.md"):
        files.append(FileInfo(
            filename=file_path.name,
            size=file_path.stat().st_size
        ))

    return files


@router.delete("/workspaces/{name}/files/{filename}")
async def delete_file(name: str, filename: str):
    """Delete a file from workspace."""
    file_path = WORKSPACES_DIR / name / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(file_path)

    return {"deleted": filename}


# Session info endpoint

@router.get("/session")
async def get_session_info(request: Request):
    """Get current session info."""
    session_manager = request.app.state.session_manager

    if session_manager.current_session:
        return session_manager.current_session.to_status_dict()

    return {"session": None}


# Config endpoint (non-sensitive)

@router.get("/config")
async def get_config():
    """Get non-sensitive configuration."""
    settings = get_settings()
    return {
        "ollama_model": settings.ollama_model,
        "sample_rate": 16000,
        "frame_duration_ms": 20,
    }
