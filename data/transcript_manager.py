import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Any

class TranscriptManager:
    """Manages transcript files on disk."""

    def __init__(self, base_path: Optional[Path] = None):
        if base_path is None:
            from config import TRANSCRIPTS_PATH
            self.base_path = TRANSCRIPTS_PATH
        else:
            self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_transcript_path(self, library_id: str, extension: str = "txt") -> Path:
        """Get the path for a transcript file."""
        return self.base_path / f"{library_id}.{extension}"

    def write_transcript(self, library_id: str, text_content: str, json_content: Optional[Dict[str, Any]] = None) -> None:
        """Write transcript content to .txt and optionally .json files."""
        # Always write .txt file
        txt_path = self.get_transcript_path(library_id, "txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_content)

        # Write .json file if content is provided
        if json_content:
            json_path = self.get_transcript_path(library_id, "json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_content, f, indent=2)

    def read_transcript_text(self, library_id: str) -> Optional[str]:
        """Read the plain text content of a transcript."""
        txt_path = self.get_transcript_path(library_id, "txt")
        if txt_path.exists():
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                # Fallback for encoding errors
                with open(txt_path, "r", encoding="cp1252") as f:
                    return f.read()
        return None

    def read_transcript_json(self, library_id: str) -> Optional[Dict[str, Any]]:
        """Read the JSON content of a transcript."""
        json_path = self.get_transcript_path(library_id, "json")
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def delete_transcript(self, library_id: str) -> None:
        """Delete all transcript files for a given library ID."""
        txt_path = self.get_transcript_path(library_id, "txt")
        json_path = self.get_transcript_path(library_id, "json")
        if txt_path.exists():
            os.remove(txt_path)
        if json_path.exists():
            os.remove(json_path)

    def get_token_count(self, text_content: str) -> int:
        """
        Estimate the number of tokens in a string.
        A simple approximation is to count words.
        """
        return len(text_content.split())
