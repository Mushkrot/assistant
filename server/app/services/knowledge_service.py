"""Knowledge Service for managing and retrieving knowledge from .md files."""

import json
import re
from pathlib import Path
from collections import Counter
from typing import List, Optional

import structlog

from app.config import MAX_CONTEXT_TOKENS

logger = structlog.get_logger()

# Common English stop words to filter out
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "also", "now", "here", "there",
}

WORKSPACES_DIR = Path("./workspaces")


def extract_keywords(text: str, top_n: int = 50) -> List[str]:
    """Extract top N keywords from text."""
    # Tokenize: extract words
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    # Filter stop words
    words = [w for w in words if w not in STOP_WORDS]

    # Count frequencies
    counter = Counter(words)

    # Return top N
    return [word for word, _ in counter.most_common(top_n)]


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + max_chars

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end near the boundary
            for punct in [".", "!", "?", "\n\n"]:
                last_punct = text.rfind(punct, start + max_chars // 2, end)
                if last_punct > start:
                    end = last_punct + 1
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks


class FileIndex:
    """Index for a single file."""

    def __init__(self, filename: str, title: str, keywords: List[str], chunks: List[dict]):
        self.filename = filename
        self.title = title
        self.keywords = set(keywords)
        self.chunks = chunks  # List of {"text": str, "keywords": set}

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "title": self.title,
            "keywords": list(self.keywords),
            "chunks": [
                {"text": c["text"], "keywords": list(c["keywords"])}
                for c in self.chunks
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileIndex":
        return cls(
            filename=data["filename"],
            title=data["title"],
            keywords=data["keywords"],
            chunks=[
                {"text": c["text"], "keywords": set(c["keywords"])}
                for c in data["chunks"]
            ]
        )


class KnowledgeService:
    """Service for managing knowledge files and retrieval."""

    def __init__(self):
        self._index_cache: dict[str, List[FileIndex]] = {}

    def index_workspace(self, workspace: str) -> None:
        """Index all files in a workspace."""
        workspace_path = WORKSPACES_DIR / workspace

        if not workspace_path.exists():
            logger.warning("Workspace not found", workspace=workspace)
            return

        indices = []

        for file_path in workspace_path.glob("*.md"):
            try:
                index = self._index_file(file_path)
                indices.append(index)
                logger.info("Indexed file",
                           workspace=workspace,
                           filename=file_path.name)
            except Exception as e:
                logger.error("Failed to index file",
                            filename=file_path.name,
                            error=str(e))

        self._index_cache[workspace] = indices

        # Save index to disk
        self._save_index(workspace, indices)

    def _index_file(self, file_path: Path) -> FileIndex:
        """Index a single markdown file."""
        content = file_path.read_text(encoding="utf-8")

        # Extract title (first heading or filename)
        title = file_path.stem
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

        # Extract keywords from full content
        keywords = extract_keywords(content)

        # Create chunks
        chunks = []
        for chunk_text_content in chunk_text(content):
            chunk_keywords = extract_keywords(chunk_text_content, top_n=20)
            chunks.append({
                "text": chunk_text_content,
                "keywords": set(chunk_keywords)
            })

        return FileIndex(
            filename=file_path.name,
            title=title,
            keywords=keywords,
            chunks=chunks
        )

    def _save_index(self, workspace: str, indices: List[FileIndex]) -> None:
        """Save index to disk."""
        workspace_path = WORKSPACES_DIR / workspace
        index_path = workspace_path / ".index.json"

        data = [idx.to_dict() for idx in indices]

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_index(self, workspace: str) -> Optional[List[FileIndex]]:
        """Load index from disk."""
        workspace_path = WORKSPACES_DIR / workspace
        index_path = workspace_path / ".index.json"

        if not index_path.exists():
            return None

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [FileIndex.from_dict(d) for d in data]
        except Exception as e:
            logger.error("Failed to load index", error=str(e))
            return None

    def _get_index(self, workspace: str) -> List[FileIndex]:
        """Get index for workspace, loading or creating if needed."""
        if workspace in self._index_cache:
            return self._index_cache[workspace]

        # Try to load from disk
        indices = self._load_index(workspace)
        if indices:
            self._index_cache[workspace] = indices
            return indices

        # Create new index
        self.index_workspace(workspace)
        return self._index_cache.get(workspace, [])

    def retrieve(self, workspace: str, query: str, top_k: int = 3) -> str:
        """Retrieve relevant chunks for a query."""
        indices = self._get_index(workspace)
        if not indices:
            return ""

        # Extract query keywords
        query_keywords = set(extract_keywords(query, top_n=10))
        if not query_keywords:
            return ""

        # Score all chunks
        scored_chunks = []

        for file_index in indices:
            for chunk in file_index.chunks:
                # Calculate overlap score
                overlap = len(query_keywords & chunk["keywords"])
                if overlap > 0:
                    scored_chunks.append({
                        "text": chunk["text"],
                        "score": overlap,
                        "filename": file_index.filename,
                    })

        # Sort by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        # Take top K
        top_chunks = scored_chunks[:top_k]

        if not top_chunks:
            return ""

        # Build context string
        context_parts = []
        total_chars = 0
        max_chars = MAX_CONTEXT_TOKENS * 4  # Rough char to token ratio

        for chunk in top_chunks:
            text = chunk["text"]
            if total_chars + len(text) > max_chars:
                # Truncate this chunk
                remaining = max_chars - total_chars
                if remaining > 100:
                    text = text[:remaining] + "..."
                else:
                    break

            context_parts.append(f"[From {chunk['filename']}]\n{text}")
            total_chars += len(text)

        return "\n\n".join(context_parts)

    def get_workspace_files(self, workspace: str) -> List[str]:
        """Get list of files in workspace."""
        workspace_path = WORKSPACES_DIR / workspace

        if not workspace_path.exists():
            return []

        return [f.name for f in workspace_path.glob("*.md")]
