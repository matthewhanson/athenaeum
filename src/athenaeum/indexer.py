"""
Business logic for building FAISS-backed vector indexes using LlamaIndex.
Includes PDF conversion preprocessing and index building.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Iterator
from pathlib import Path
from fnmatch import fnmatch

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.faiss import FaissVectorStore
import faiss

from athenaeum.utils import setup_settings


# ============================================================================
# PDF Conversion (Preprocessing for Indexing)
# ============================================================================

def collect_pdfs(inputs: List[Path], recursive: bool) -> List[Path]:
    """
    Collect PDF files from input paths (files or directories).
    
    Args:
        inputs: List of file paths or directories
        recursive: Whether to search directories recursively
        
    Returns:
        List of PDF file paths
    """
    pdfs: List[Path] = []
    for p in inputs:
        if p.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            pdfs.extend(sorted(p.glob(pattern)))
        elif p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)
    return pdfs


def convert_pdfs_to_markdown(
    pdfs: List[Path], 
    out_dir: Path, 
    engine: str = "unstructured",
    overwrite: bool = False,
    extract_images: bool = False
) -> Iterator[Dict[str, Any]]:
    """
    Convert PDFs to Markdown using specified engine.
    
    Args:
        pdfs: List of PDF files to convert
        out_dir: Output directory for Markdown files
        engine: Conversion engine ('unstructured', 'pymupdf', 'docling', or 'hybrid')
        overwrite: Whether to overwrite existing files
        extract_images: Whether to extract and save images from PDFs (unstructured/hybrid only)
        
    Yields:
        Status dictionaries with conversion progress
    
    Recommended for game PDFs with images and tables:
        - 'hybrid': Combines unstructured (headings) + docling (tables) - Best for complex PDFs
        - 'unstructured': Best heading/section fidelity
        - 'docling': Best table extraction
        - 'pymupdf': Fast, simple extraction
    """
    if engine == "hybrid":
        yield from _convert_with_hybrid(pdfs, out_dir, overwrite, extract_images)
    elif engine == "unstructured":
        yield from _convert_with_unstructured(pdfs, out_dir, overwrite, extract_images)
    elif engine == "pymupdf":
        yield from _convert_with_pymupdf(pdfs, out_dir, overwrite)
    elif engine == "docling":
        yield from _convert_with_docling(pdfs, out_dir, overwrite)
    else:
        raise ValueError(f"Unknown engine: {engine}. Use: unstructured | pymupdf | docling | hybrid")


def _convert_with_unstructured(pdfs: List[Path], out_dir: Path, overwrite: bool, extract_images: bool = False) -> Iterator[Dict[str, Any]]:
    """Convert PDFs using unstructured library."""
    import re
    from base64 import b64decode
    
    # Register HEIF opener so image plugins don't explode
    try:
        import pillow_heif as _pheif
        _pheif.register_heif_opener()
    except Exception:
        pass

    try:
        from unstructured.partition.pdf import partition_pdf
        from unstructured.staging.base import elements_to_markdown
        have_md_staging = True
    except Exception:
        have_md_staging = False
        from unstructured.partition.pdf import partition_pdf

    def sanitize_filename(text: str) -> str:
        """Convert text to safe filename."""
        # Remove/replace unsafe characters
        safe = re.sub(r'[^\w\s-]', '', text)
        safe = re.sub(r'[-\s]+', '-', safe)
        return safe.strip('-')[:100]  # Limit length

    def save_images(elements, img_dir: Path, stem: str) -> Dict[str, str]:
        """Extract and save images from elements. Returns dict of element_id -> image_path."""
        img_dir.mkdir(parents=True, exist_ok=True)
        saved_images = {}
        image_counter = 1
        last_caption = None
        
        for el in elements:
            el_type = el.__class__.__name__
            
            # Track captions for next image
            if el_type in ("FigureCaption", "Caption"):
                caption_text = getattr(el, "text", "").strip()
                if caption_text:
                    last_caption = caption_text
            
            # Save images
            if el_type == "Image":
                meta = getattr(el, "metadata", None)
                if meta:
                    # Try to get image data
                    image_data = None
                    image_base64 = getattr(meta, "image_base64", None)
                    if image_base64:
                        try:
                            image_data = b64decode(image_base64)
                        except Exception:
                            pass
                    
                    if image_data:
                        # Create filename from caption or counter
                        if last_caption:
                            filename = sanitize_filename(last_caption)
                            if not filename:
                                filename = f"image_{image_counter:03d}"
                        else:
                            filename = f"image_{image_counter:03d}"
                        
                        # Save as PNG (most common format from PDFs)
                        img_path = img_dir / f"{filename}.png"
                        
                        # Handle duplicates
                        counter = 1
                        while img_path.exists():
                            img_path = img_dir / f"{filename}_{counter}.png"
                            counter += 1
                        
                        img_path.write_bytes(image_data)
                        
                        # Store relative path for markdown
                        rel_path = f"images/{stem}/{img_path.name}"
                        element_id = id(el)
                        saved_images[element_id] = rel_path
                        
                        image_counter += 1
                        last_caption = None  # Reset after using
        
        return saved_images

    def render_md(elements, saved_images=None):
        if saved_images is None:
            saved_images = {}
            
        if have_md_staging and not saved_images:
            # Use standard conversion if no custom images
            from unstructured.staging.base import elements_to_markdown
            return elements_to_markdown(elements)
        
        # Custom renderer with image support
        lines = []
        for el in elements:
            name = el.__class__.__name__
            text = (getattr(el, "text", "") or "").strip()
            meta = getattr(el, "metadata", None)
            el_id = id(el)
            
            # Check if this element has an associated image
            if el_id in saved_images:
                img_path = saved_images[el_id]
                caption = text if name in ("FigureCaption", "Caption") else "Image"
                lines.append(f"![{caption}]({img_path})")
                if text and name in ("FigureCaption", "Caption"):
                    lines.append(f"*{text}*")
                continue
            
            if not text:
                continue
            
            if name == "Title":
                level = 2
                if meta:
                    level = getattr(meta, "heading_level", None) or 2
                lines.append(f"{'#' * max(1, min(6, int(level)))} {text}")
            elif name in ("ListItem", "ListElement"):
                lines.append(f"- {text}")
            elif name == "Table":
                lines.append("\n" + text + "\n")
            elif name in ("FigureCaption", "Caption"):
                lines.append(f"*{text}*")
            elif name in ("Header", "Footer", "PageBreak"):
                continue
            else:
                lines.append(text)
        return "\n\n".join(lines)

    for i, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        md_path = out_dir / f"{stem}.md"
        if md_path.exists() and not overwrite:
            yield {"status": "skip", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
            continue

        yield {"status": "converting", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
        
        elements = partition_pdf(
            filename=str(pdf),
            strategy="hi_res",
            extract_images_in_pdf=extract_images,
            infer_table_structure=True,
            include_page_breaks=False,
        )
        
        # Extract and save images (only if requested)
        saved_images = {}
        if extract_images:
            img_dir = out_dir / "images" / stem
            saved_images = save_images(elements, img_dir, stem)
        
        md_text = render_md(elements, saved_images)
        md_path.write_text(md_text, encoding="utf-8")
        
        yield {"status": "done", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs), "images": len(saved_images)}


def _convert_with_pymupdf(pdfs: List[Path], out_dir: Path, overwrite: bool) -> Iterator[Dict[str, Any]]:
    """Convert PDFs using PyMuPDF."""
    try:
        import fitz
        import pymupdf4llm
    except ImportError as e:
        raise ImportError(
            "Engine 'pymupdf' requires: pymupdf, pymupdf4llm.\n"
            "Install: uv add pymupdf pymupdf4llm"
        ) from e

    for i, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        md_path = out_dir / f"{stem}.md"
        if md_path.exists() and not overwrite:
            yield {"status": "skip", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
            continue

        yield {"status": "converting", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
        
        with fitz.open(pdf) as doc:
            img_dir = out_dir / "images" / stem
            img_dir.mkdir(parents=True, exist_ok=True)
            try:
                md_text = pymupdf4llm.to_markdown(doc, image_path=str(img_dir))
            except TypeError:
                try:
                    md_text = pymupdf4llm.to_markdown(doc, image_dir=str(img_dir))
                except TypeError:
                    md_text = pymupdf4llm.to_markdown(doc)
        md_path.write_text(md_text, encoding="utf-8")
        
        yield {"status": "done", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}


def _convert_with_docling(pdfs: List[Path], out_dir: Path, overwrite: bool) -> Iterator[Dict[str, Any]]:
    """Convert PDFs using Docling."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        raise ImportError(
            "Engine 'docling' requires: docling.\n"
            "Install: uv add docling"
        ) from e

    converter = DocumentConverter()
    for i, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        md_path = out_dir / f"{stem}.md"
        if md_path.exists() and not overwrite:
            yield {"status": "skip", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
            continue

        yield {"status": "converting", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
        
        result = converter.convert(str(pdf))
        md_text = result.document.export_to_markdown()
        md_path.write_text(md_text, encoding="utf-8")
        
        yield {"status": "done", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}


def _convert_with_hybrid(pdfs: List[Path], out_dir: Path, overwrite: bool, extract_images: bool = False) -> Iterator[Dict[str, Any]]:
    """
    Hybrid converter: Uses unstructured for text/headings + docling for tables.
    Best for complex PDFs like game settings with images, decorative elements, and tables.
    
    Process:
    1. Run unstructured (hi_res) for heading hierarchy and text extraction
    2. Run docling for superior table extraction
    3. Merge results, preserving heading structure from unstructured and tables from docling
    4. Create output with markers for manual review
    """
    import re
    
    # Check for unstructured
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError as e:
        raise ImportError(
            "Engine 'hybrid' requires unstructured library.\n"
            "Install: uv add unstructured\n"
            f"Error: {e}"
        ) from e
    
    # Try to import elements_to_markdown (optional, will use fallback if not available)
    try:
        from unstructured.staging.base import elements_to_markdown
        have_md_staging = True
    except (ImportError, AttributeError):
        have_md_staging = False
    
    # Check for docling
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        raise ImportError(
            "Engine 'hybrid' requires docling library.\n"
            "Install: uv add docling\n"
            f"Error: {e}"
        ) from e

    # Register HEIF opener
    try:
        import pillow_heif as _pheif
        _pheif.register_heif_opener()
    except Exception:
        pass
    
    from base64 import b64decode
    
    def sanitize_filename(text: str) -> str:
        """Convert text to safe filename."""
        safe = re.sub(r'[^\w\s-]', '', text)
        safe = re.sub(r'[-\s]+', '-', safe)
        return safe.strip('-')[:100]
    
    def save_images(elements, img_dir: Path, stem: str) -> Dict[str, str]:
        """Extract and save images from elements. Returns dict of element_id -> image_path."""
        img_dir.mkdir(parents=True, exist_ok=True)
        saved_images = {}
        image_counter = 1
        last_caption = None
        
        for el in elements:
            el_type = el.__class__.__name__
            
            if el_type in ("FigureCaption", "Caption"):
                caption_text = getattr(el, "text", "").strip()
                if caption_text:
                    last_caption = caption_text
            
            if el_type == "Image":
                meta = getattr(el, "metadata", None)
                if meta:
                    image_data = None
                    image_base64 = getattr(meta, "image_base64", None)
                    if image_base64:
                        try:
                            image_data = b64decode(image_base64)
                        except Exception:
                            pass
                    
                    if image_data:
                        if last_caption:
                            filename = sanitize_filename(last_caption)
                            if not filename:
                                filename = f"image_{image_counter:03d}"
                        else:
                            filename = f"image_{image_counter:03d}"
                        
                        img_path = img_dir / f"{filename}.png"
                        counter = 1
                        while img_path.exists():
                            img_path = img_dir / f"{filename}_{counter}.png"
                            counter += 1
                        
                        img_path.write_bytes(image_data)
                        rel_path = f"images/{stem}/{img_path.name}"
                        element_id = id(el)
                        saved_images[element_id] = rel_path
                        
                        image_counter += 1
                        last_caption = None
        
        return saved_images
    
    # Define markdown renderer with image support
    def render_md(elements, saved_images=None):
        if saved_images is None:
            saved_images = {}
            
        if have_md_staging and not saved_images:
            return elements_to_markdown(elements)
        
        lines = []
        for el in elements:
            name = el.__class__.__name__
            text = (getattr(el, "text", "") or "").strip()
            meta = getattr(el, "metadata", None)
            el_id = id(el)
            
            if el_id in saved_images:
                img_path = saved_images[el_id]
                caption = text if name in ("FigureCaption", "Caption") else "Image"
                lines.append(f"![{caption}]({img_path})")
                if text and name in ("FigureCaption", "Caption"):
                    lines.append(f"*{text}*")
                continue
            
            if not text:
                continue
            
            if name == "Title":
                level = 2
                if meta:
                    level = getattr(meta, "heading_level", None) or 2
                lines.append(f"{'#' * max(1, min(6, int(level)))} {text}")
            elif name in ("ListItem", "ListElement"):
                lines.append(f"- {text}")
            elif name == "Table":
                lines.append("\n" + text + "\n")
            elif name in ("FigureCaption", "Caption"):
                lines.append(f"*{text}*")
            elif name in ("Header", "Footer", "PageBreak"):
                continue
            else:
                lines.append(text)
        return "\n\n".join(lines)

    docling_converter = DocumentConverter()
    
    for i, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        md_path = out_dir / f"{stem}.md"
        if md_path.exists() and not overwrite:
            yield {"status": "skip", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs)}
            continue

        yield {"status": "converting", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs), "engine": "hybrid"}
        
        # Pass 1: Unstructured for heading hierarchy, text, and optionally images
        yield {"status": "processing", "step": "unstructured", "pdf": pdf, "index": i, "total": len(pdfs)}
        elements = partition_pdf(
            filename=str(pdf),
            strategy="hi_res",
            extract_images_in_pdf=extract_images,  # Extract images if requested
            infer_table_structure=False,  # Let docling handle tables
            include_page_breaks=False,
        )
        
        # Extract and save images (only if requested)
        saved_images = {}
        if extract_images:
            img_dir = out_dir / "images" / stem
            saved_images = save_images(elements, img_dir, stem)
        
        # Extract text with heading hierarchy using the render function
        unstructured_md = render_md(elements, saved_images)
        
        # Pass 2: Docling for tables
        yield {"status": "processing", "step": "docling", "pdf": pdf, "index": i, "total": len(pdfs)}
        docling_result = docling_converter.convert(str(pdf))
        docling_md = docling_result.document.export_to_markdown()
        
        # Extract tables from docling output (tables are usually between | characters)
        table_pattern = r'(\|[^\n]+\|(?:\n\|[^\n]+\|)+)'
        docling_tables = re.findall(table_pattern, docling_md, re.MULTILINE)
        
        # Pass 3: Merge - Start with unstructured structure, enhance with docling tables
        merged_md = unstructured_md
        
        # Add tables section at the end if docling found tables
        if docling_tables:
            merged_md += "\n\n---\n## Tables Extracted by Docling\n\n"
            merged_md += "<!-- MANUAL REVIEW: Check if these tables should be inserted inline above -->\n\n"
            for idx, table in enumerate(docling_tables, 1):
                merged_md += f"\n### Table {idx}\n\n{table}\n\n"
        
        # Add metadata header
        header = f"""<!-- HYBRID CONVERSION RESULT -->
<!-- Source: {pdf.name} -->
<!-- Pass 1: Unstructured (headings, text structure) -->
<!-- Pass 2: Docling (tables) -->
<!-- MANUAL REVIEW RECOMMENDED: Check heading levels, merge tables inline, remove decorative text -->

---

"""
        final_md = header + merged_md
        
        # Write output
        md_path.write_text(final_md, encoding="utf-8")
        
        # Also save individual outputs for comparison
        comparison_dir = out_dir / "comparison" / stem
        comparison_dir.mkdir(parents=True, exist_ok=True)
        (comparison_dir / f"{stem}_unstructured.md").write_text(unstructured_md, encoding="utf-8")
        (comparison_dir / f"{stem}_docling.md").write_text(docling_md, encoding="utf-8")
        
        yield {"status": "done", "pdf": pdf, "md_path": md_path, "index": i, "total": len(pdfs), 
               "comparison_dir": comparison_dir, "tables_found": len(docling_tables), "images": len(saved_images)}


# ============================================================================
# Index Building
# ============================================================================

def _validate_paths(inputs: List[Path]) -> List[Path]:
    """Validate that input paths exist."""
    paths = [p for p in inputs if p.exists()]
    if not paths:
        raise FileNotFoundError("No valid input paths found.")
    return paths


def _build_document_reader(
    input_paths: list[Path],
    glob_include: list[str] | None,
    glob_exclude: list[str] | None,
    recursive: bool,
    max_files: Optional[int],
) -> SimpleDirectoryReader:
    """Build a SimpleDirectoryReader that respects include/exclude globs."""
    # Flatten directories and files into a list of paths
    paths: list[str] = []
    for p in input_paths:
        if p.is_dir():
            if recursive:
                paths.extend(str(f) for f in p.rglob("*") if f.is_file())
            else:
                paths.extend(str(f) for f in p.glob("*") if f.is_file())
        else:
            paths.append(str(p))

    # Apply inclusion/exclusion globs
    include_patterns = glob_include or ["**/*"]
    exclude_patterns = glob_exclude or []

    filtered_paths = []
    for path in paths:
        if any(fnmatch(path, ex) for ex in exclude_patterns):
            continue
        if any(fnmatch(path, inc) for inc in include_patterns):
            filtered_paths.append(path)

    if max_files:
        filtered_paths = filtered_paths[:max_files]

    return SimpleDirectoryReader(
        input_files=filtered_paths,
        file_metadata=lambda p: {"source_path": p},
        exclude_hidden=True,
    )


def _create_faiss_storage(index_dir: Path) -> StorageContext:
    """Create or load a FAISS vector store."""
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss_path = index_dir / "faiss.index"

    if faiss_path.exists():
        vector_store = FaissVectorStore.from_persist_path(str(faiss_path))
    else:
        # Create a new FAISS index (384 dims for all-MiniLM-L6-v2)
        faiss_index = faiss.IndexFlatL2(384)
        vector_store = FaissVectorStore(faiss_index=faiss_index)

    return StorageContext.from_defaults(vector_store=vector_store)


def _persist_index(storage_context: StorageContext, index_dir: Path) -> None:
    """Persist the storage context to disk."""
    index_dir.mkdir(parents=True, exist_ok=True)
    storage_context.vector_store.persist(persist_path=str(index_dir / "faiss.index"))
    storage_context.persist(persist_dir=str(index_dir))


def _generate_stats(docs, index: VectorStoreIndex) -> dict:
    """Generate statistics about the indexed documents."""
    num_docs = len(docs)
    nodes_indexed = None
    try:
        nodes_indexed = sum(len(d.nodes) for d in index.docstore.docs.values())
    except Exception:
        pass
    return {
        "documents_ingested": num_docs,
        "index_summary": {"vector_store": "faiss", "nodes_indexed": nodes_indexed},
    }


def build_index(
    inputs: List[Path],
    index_dir: Path,
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    recursive: bool = True,
    max_files: Optional[int] = None,
    return_stats: bool = True,
) -> Dict[str, Any] | None:
    """
    Build/update a FAISS-backed index from the given files/directories.
    
    Args:
        inputs: List of file paths or directories to index
        index_dir: Directory to store the index
        embed_model: HuggingFace embedding model name
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        include: Glob patterns to include
        exclude: Glob patterns to exclude
        recursive: Whether to search directories recursively
        max_files: Maximum number of files to index
        return_stats: Whether to return statistics
        
    Returns:
        Stats dict if return_stats=True, else None
    """
    paths = _validate_paths(inputs)
    setup_settings(embed_model, chunk_size, chunk_overlap)

    reader = _build_document_reader(
        paths, 
        include or ["**/*"], 
        exclude or [], 
        recursive, 
        max_files
    )
    documents = reader.load_data()
    
    if not documents:
        return {"warning": "No documents loaded after filtering."} if return_stats else None

    storage = _create_faiss_storage(index_dir)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage,
        show_progress=True,
        store_nodes=True,
    )
    _persist_index(storage, index_dir)

    return _generate_stats(documents, index) if return_stats else None
