"""
Common intermediate representation for all supported document formats.

Format-specific extractors convert their source into these simple
structures. The main pipeline then processes them without needing
to know whether the source was DOCX, PDF, XLSX, or CSV.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedTable:
    data: Any
    source_page: str
    extraction_method: str


@dataclass
class ExtractedDocument:
    paragraphs: list[str] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    images: list[str] = field(default_factory=list)