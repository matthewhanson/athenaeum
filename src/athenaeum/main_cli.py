# src/athenaeum/main_cli.py
import json
import os
import signal
import subprocess
import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import typer
import warnings
from pydantic.warnings import UnsupportedFieldAttributeWarning

warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)

# Import refactored modules
from athenaeum.indexer import build_index, collect_pdfs, convert_pdfs_to_markdown
from athenaeum.retriever import query_index

app = typer.Typer(help="Athenaeum CLI — Give your LLM a library. Build and query local FAISS indexes.")

def _pkg_version() -> str:
    try:
        return version("athenaeum")
    except PackageNotFoundError:
        return "0.0.0+local"

@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version_: bool = typer.Option(False, "--version", "-V", is_eager=True, help="Show version and exit."),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity (-v, -vv)."),
):
    if version_:
        typer.echo(_pkg_version())
        raise typer.Exit()
    
    # If no subcommand is provided and no version flag, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("convert")
def cmd_convert(
    inputs: list[Path] = typer.Argument(..., help="PDF files and/or directories to convert."),
    out_dir: Path = typer.Option(Path("./md_out"), "--out", "-o", help="Directory for Markdown output."),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Recurse when inputs include directories."),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite", help="Overwrite existing .md files."),
    engine: str = typer.Option("hybrid", "--engine", "-e", help="Conversion engine: hybrid | unstructured | pymupdf | docling"),
    extract_images: bool = typer.Option(False, "--images/--no-images", help="Extract and save images from PDFs."),
):
    """
    Convert PDF(s) to Markdown.
    Engines:
      - hybrid: combines unstructured (headings) + docling (tables) - RECOMMENDED for complex PDFs
      - unstructured: best heading/section fidelity
      - pymupdf: fast fallback (PyMuPDF + pymupdf4llm)
      - docling: strong structure (optional, if installed)
    """
    # Collect PDFs using library function
    pdfs = collect_pdfs(inputs, recursive)
    if not pdfs:
        raise typer.BadParameter("No PDF files found in the given inputs.")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Process conversions and display progress
    eng = engine.lower().strip()
    try:
        for status in convert_pdfs_to_markdown(pdfs, out_dir, engine=eng, overwrite=overwrite, extract_images=extract_images):
            if status["status"] == "skip":
                typer.echo(f"[skip] {status['md_path']} exists (use --overwrite).")
            elif status["status"] == "converting":
                typer.echo(f"[{status['index']}/{status['total']}] Converting ({eng}): {status['pdf']}")
            elif status["status"] == "processing":
                step = status.get("step", "processing")
                typer.echo(f"  → {step}...")
            elif status["status"] == "done":
                msg = f"[ok] {status['md_path']}"
                images = status.get("images", 0)
                if images > 0:
                    msg += f" ({images} images extracted)"
                tables = status.get("tables_found", 0)
                if tables > 0:
                    msg += f" ({tables} tables)"
                typer.echo(msg)
    except (ImportError, ValueError) as e:
        raise typer.BadParameter(str(e))

    typer.echo(f"[done] Wrote Markdown to {out_dir.resolve()}")


@app.command("index")
def cmd_index(
    input_path: list[Path] = typer.Argument(..., help="Files and/or directories to ingest."),
    output: Path = typer.Option(Path("./index"), "--output", "-o", help="Index output directory."),
    embed_model: str = typer.Option("sentence-transformers/all-MiniLM-L6-v2", help="HuggingFace embedding model."),
    chunk_size: int = typer.Option(800, help="Chunk size (tokens/approx)."),
    chunk_overlap: int = typer.Option(120, help="Chunk overlap."),
    include: list[str] = typer.Option(["**/*"], "--include", "-i", help="Glob patterns to include (repeatable)."),
    exclude: list[str] = typer.Option(
        ["**/.git/**", "**/__pycache__/**", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif"],
        "--exclude", "-x", help="Glob patterns to exclude (repeatable).",
    ),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Recurse into subdirectories."),
    max_files: int | None = typer.Option(None, help="Limit number of files ingested."),
    show_stats: bool = typer.Option(True, help="Print basic stats after indexing."),
):
    """Build/update a local FAISS-backed index from your files."""
    stats = build_index(
        inputs=input_path,
        index_dir=output,
        embed_model=embed_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        include=include,
        exclude=exclude,
        recursive=recursive,
        max_files=max_files,
        return_stats=show_stats,
    )
    typer.echo(f"[ok] Index persisted to: {output.resolve()}")
    if show_stats and stats:
        typer.echo(json.dumps(stats, indent=2))


@app.command("query")
def cmd_query(
    output: Path = typer.Option(Path("./index"), "--output", "-o", help="Index directory."),
    embed_model: str = typer.Option("sentence-transformers/all-MiniLM-L6-v2", help="HuggingFace embedding model."),
    top_k: int = typer.Option(5, help="Top-k nodes to retrieve."),
    question: str = typer.Argument(..., help="Your question for the indexed corpus."),
    print_sources: bool = typer.Option(True, "--sources/--no-sources", help="Print sources after the answer."),
):
    """Run a quick retrieval against an existing index."""
    result = query_index(
        index_dir=output,
        question=question,
        embed_model=embed_model,
        top_k=top_k,
    )
    typer.echo("\n=== Answer ===")
    typer.echo(result["answer"])
    if print_sources and result.get("sources"):
        typer.echo("\n=== Sources ===")
        for i, s in enumerate(result["sources"], 1):
            typer.echo(f"[{i}] {s['path']} (score={s.get('score')})")


@app.command("serve")
def cmd_serve(
    index_dir: Path = typer.Option(Path("./index"), "--index", "-i", help="Index directory."),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind the server to."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the server on."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (development)."),
):
    """Start the MCP server for RAG functionality."""
    if not index_dir.exists():
        typer.echo(f"Error: Index directory not found: {index_dir}")
        raise typer.Exit(code=1)
    
    # Set environment variable for the server to find the index
    os.environ["ATHENAEUM_INDEX_DIR"] = str(index_dir.absolute())
    
    # Prepare the uvicorn command
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "athenaeum.mcp_server:app", 
        "--host", host, 
        "--port", str(port)
    ]
    
    if reload:
        cmd.append("--reload")
    
    typer.echo(f"Starting MCP server with index: {index_dir}")
    typer.echo(f"API will be available at: http://{host}:{port}")
    
    # Run the server process
    try:
        process = subprocess.Popen(cmd)
        typer.echo("Server running. Press Ctrl+C to stop.")
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            typer.echo("\nShutting down server...")
            process.terminate()
            process.wait(timeout=5)
            typer.echo("Server stopped.")
            raise typer.Exit()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Wait for the process to complete
        process.wait()
        
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        typer.echo("Server stopped.")


def main() -> None:
    app()
