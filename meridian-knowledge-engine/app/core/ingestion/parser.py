# app/core/ingestion/parser.py
"""5-Tier Parser -> Unified Block List."""
import magic
from typing import List, Optional, Literal
from dataclasses import dataclass, field
from uuid import UUID
from pathlib import Path

from app.config import get_settings

settings = get_settings()


@dataclass
class Block:
    """Unified structural unit from any document format."""
    block_type: Literal["heading", "paragraph", "table_row", "transcript_turn", "slide"]
    heading_path: List[str] = field(default_factory=list)  # ["4", "2"] for 4.2
    heading_level: Optional[int] = None  # 1, 2, 3
    content: str = ""
    metadata: dict = field(default_factory=dict)  # {speaker, timestamp, row_data, slide_num}
    char_start: int = 0
    char_end: int = 0


BlockList = List[Block]


class DocumentParser:
    """Single entry point for all document types -> BlockList."""

    def __init__(self):
        self.mime = magic.Magic(mime=True)

    def detect_file_type(self, content: bytes) -> str:
        """Detect file type from content (not extension)."""
        mime_type = self.mime.from_buffer(content[:8192])

        type_map = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/msword": "doc",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.ms-excel": "xls",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "application/vnd.ms-powerpoint": "ppt",
            "application/pdf": "pdf",
            "text/plain": "txt",
            "message/rfc822": "eml",
        }
        return type_map.get(mime_type, "unknown")

    def parse(self, content: bytes, filename: str = "") -> BlockList:
        """Parse any document -> Unified BlockList."""
        file_type = self.detect_file_type(content)

        if file_type in ("docx", "doc"):
            return self._parse_word(content)
        elif file_type in ("xlsx", "xls"):
            return self._parse_excel(content)
        elif file_type in ("pptx", "ppt"):
            return self._parse_powerpoint(content)
        elif file_type == "pdf":
            return self._parse_pdf(content)
        elif file_type in ("txt", "eml"):
            return self._parse_text(content)
        else:
            # Try LibreOffice conversion for legacy formats
            return self._parse_via_libreoffice(content, file_type)

    def _parse_word(self, content: bytes) -> BlockList:
        """Parse Word document preserving styles, headings, tables."""
        import io
        from docx import Document

        doc = Document(io.BytesIO(content))
        blocks = []
        char_pos = 0

        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            block_type = "heading" if para.style.name.startswith("Heading") else "paragraph"
            heading_level = int(para.style.name[-1]) if block_type == "heading" else None
            heading_path = self._build_heading_path(para) if block_type == "heading" else []

            block = Block(
                block_type=block_type,
                heading_path=heading_path,
                heading_level=heading_level,
                content=para.text,
                metadata={"style": para.style.name},
                char_start=char_pos,
                char_end=char_pos + len(para.text),
            )
            blocks.append(block)
            char_pos += len(para.text) + 1

        # Tables
        for table in doc.tables:
            for row_idx, row in enumerate(table.rows):
                row_data = [cell.text for cell in row.cells]
                block = Block(
                    block_type="table_row",
                    heading_path=[],
                    heading_level=None,
                    content=" | ".join(row_data),
                    metadata={"row_index": row_idx, "row_data": row_data},
                    char_start=char_pos,
                    char_end=char_pos + len(" | ".join(row_data)),
                )
                blocks.append(block)
                char_pos += len(" | ".join(row_data)) + 1

        return blocks

    def _parse_excel(self, content: bytes) -> BlockList:
        """Parse Excel - each sheet -> blocks, tables -> table_row blocks."""
        import io
        import pandas as pd

        blocks = []
        char_pos = 0

        xls = pd.read_excel(io.BytesIO(content), sheet_name=None)
        for sheet_name, df in xls.items():
            # Sheet header
            blocks.append(Block(
                block_type="heading",
                heading_path=[sheet_name],
                heading_level=1,
                content=sheet_name,
                metadata={"sheet": sheet_name},
                char_start=char_pos,
                char_end=char_pos + len(sheet_name),
            ))
            char_pos += len(sheet_name) + 1

            # Table rows
            for idx, row in df.iterrows():
                row_data = row.to_dict()
                blocks.append(Block(
                    block_type="table_row",
                    heading_path=[sheet_name],
                    heading_level=2,
                    content=" | ".join(f"{k}: {v}" for k, v in row_data.items()),
                    metadata={"sheet": sheet_name, "row_index": idx, "row_data": row_data},
                    char_start=char_pos,
                    char_end=char_pos + 100,  # approximate
                ))
                char_pos += 100

        return blocks

    def _parse_powerpoint(self, content: bytes) -> BlockList:
        """Parse PowerPoint - slides -> slide blocks, shapes -> text blocks."""
        import io
        from pptx import Presentation

        prs = Presentation(io.BytesIO(content))
        blocks = []
        char_pos = 0

        for slide_idx, slide in enumerate(prs.slides):
            # Slide header
            blocks.append(Block(
                block_type="slide",
                heading_path=[f"Slide {slide_idx + 1}"],
                heading_level=1,
                content=f"Slide {slide_idx + 1}",
                metadata={"slide_number": slide_idx + 1},
                char_start=char_pos,
                char_end=char_pos + 20,
            ))
            char_pos += 20

            # Shapes
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip():
                            blocks.append(Block(
                                block_type="paragraph",
                                heading_path=[f"Slide {slide_idx + 1}"],
                                heading_level=2,
                                content=para.text,
                                metadata={"slide_number": slide_idx + 1, "shape_id": shape.shape_id},
                                char_start=char_pos,
                                char_end=char_pos + len(para.text),
                            ))
                            char_pos += len(para.text) + 1

        return blocks

    def _parse_pdf(self, content: bytes) -> BlockList:
        """Parse PDF - text blocks, tables, structure from font sizes."""
        import fitz  # PyMuPDF

        blocks = []
        char_pos = 0

        doc = fitz.open(stream=content, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_dict = page.get_text("dict")

            for block in page_dict["blocks"]:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    line_text = " ".join(span["text"] for span in line["spans"])
                    if not line_text.strip():
                        continue

                    # Infer heading level from font size
                    max_font = max(span["size"] for span in line["spans"])
                    is_heading = max_font > 14
                    heading_level = 1 if max_font > 18 else (2 if max_font > 14 else 3)

                    blocks.append(Block(
                        block_type="heading" if is_heading else "paragraph",
                        heading_path=[f"Page {page_num + 1}"] if is_heading else [],
                        heading_level=heading_level if is_heading else None,
                        content=line_text,
                        metadata={"page": page_num + 1, "font_size": max_font},
                        char_start=char_pos,
                        char_end=char_pos + len(line_text),
                    ))
                    char_pos += len(line_text) + 1

        return blocks

    def _parse_text(self, content: bytes) -> BlockList:
        """Parse plain text / email / transcript."""
        text = content.decode("utf-8", errors="ignore")
        blocks = []
        char_pos = 0

        # Try to detect transcript format (speaker: text)
        lines = text.split("\n")
        for line in lines:
            if not line.strip():
                continue

            # Check for speaker pattern
            if ":" in line and len(line.split(":")[0]) < 50:
                parts = line.split(":", 1)
                speaker = parts[0].strip()
                content_text = parts[1].strip() if len(parts) > 1 else ""

                blocks.append(Block(
                    block_type="transcript_turn",
                    heading_path=[],
                    heading_level=None,
                    content=content_text,
                    metadata={"speaker": speaker},
                    char_start=char_pos,
                    char_end=char_pos + len(content_text),
                ))
            else:
                blocks.append(Block(
                    block_type="paragraph",
                    heading_path=[],
                    heading_level=None,
                    content=line,
                    metadata={},
                    char_start=char_pos,
                    char_end=char_pos + len(line),
                ))
            char_pos += len(line) + 1

        return blocks

    def _parse_via_libreoffice(self, content: bytes, file_type: str) -> BlockList:
        """Convert legacy formats via LibreOffice headless."""
        # Would use subprocess to convert to modern format, then parse
        # Placeholder
        return []

    def _build_heading_path(self, para) -> List[str]:
        """Build heading path from Word paragraph style."""
        # Simplified - would track heading hierarchy
        return []