# src/athenaeum/main_cli.py
import json
import os
import signal
import subprocess
import sys
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import typer
from pydantic.warnings import UnsupportedFieldAttributeWarning

warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)

app = typer.Typer(help="Athenaeum CLI — Give your LLM a library. Build and query markdown indexes.")


def _pkg_version() -> str:
    try:
        return version("athenaeum")
    except PackageNotFoundError:
        return "0.0.0+local"


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version_: bool = typer.Option(
        False, "--version", "-V", is_eager=True, help="Show version and exit."
    ),
    _verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Increase verbosity (-v, -vv)."
    ),
):
    if version_:
        typer.echo(_pkg_version())
        raise typer.Exit()

    # If no subcommand is provided and no version flag, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("index")
def cmd_index(
    input_path: list[Path] = typer.Argument(
        ..., help="Markdown files and/or directories to index."
    ),
    output: Path = typer.Option(Path("./index"), "--output", "-o", help="Index output directory."),
    embed_model: str = typer.Option(
        "sentence-transformers/all-MiniLM-L6-v2", help="HuggingFace embedding model."
    ),
    chunk_size: int = typer.Option(1024, help="Chunk size for markdown parsing."),
    chunk_overlap: int = typer.Option(200, help="Chunk overlap for markdown parsing."),
    include: list[str] = typer.Option(
        None,
        "--include",
        "-i",
        help="Glob patterns to include (repeatable). Defaults to *.md files.",
    ),
    exclude: list[str] = typer.Option(
        ["**/.git/**", "**/__pycache__/**", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif"],
        "--exclude",
        "-x",
        help="Glob patterns to exclude (repeatable).",
    ),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Recurse into subdirectories."
    ),
    max_files: int | None = typer.Option(None, help="Limit number of files ingested."),
    show_stats: bool = typer.Option(True, help="Print basic stats after indexing."),
):
    """Build/update a local FAISS-backed index from markdown files using MarkdownNodeParser."""
    from athenaeum.indexer import build_index

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


@app.command("search")
def cmd_search(
    output: Path = typer.Option(Path("./index"), "--output", "-o", help="Index directory."),
    embed_model: str = typer.Option(
        "sentence-transformers/all-MiniLM-L6-v2", help="HuggingFace embedding model."
    ),
    top_k: int = typer.Option(5, help="Top-k nodes to retrieve."),
    question: str = typer.Argument(..., help="Your search query."),
):
    """Search the index and return relevant chunks (no LLM)."""
    from athenaeum.retriever import retrieve_context

    contexts = retrieve_context(
        index_dir=output,
        question=question,
        embed_model=embed_model,
        top_k=top_k,
    )

    typer.echo(f"\n=== Found {len(contexts)} results ===\n")
    for i, ctx in enumerate(contexts, 1):
        typer.echo(f"[{i}] {ctx['metadata']['path']} (score={ctx['metadata'].get('score')})")
        typer.echo(ctx["content"])
        typer.echo()


@app.command("chat")
def cmd_chat(
    output: Path = typer.Option(Path("./index"), "--output", "-o", help="Index directory."),
    embed_model: str = typer.Option(
        "sentence-transformers/all-MiniLM-L6-v2", help="HuggingFace embedding model."
    ),
    llm_provider: str = typer.Option(
        "openai", "--llm-provider", help="LLM provider: 'openai' or 'bedrock'."
    ),
    llm_model: str = typer.Option("gpt-4o-mini", "--llm-model", help="LLM model name."),
    top_k: int = typer.Option(5, help="Top-k nodes to retrieve."),
    question: str = typer.Argument(..., help="Your question for the indexed corpus."),
    print_sources: bool = typer.Option(
        True, "--sources/--no-sources", help="Print sources after the answer."
    ),
):
    """Query the index with RAG (retrieval + LLM answer generation)."""
    from athenaeum.retriever import query_index

    result = query_index(
        index_dir=output,
        question=question,
        embed_model=embed_model,
        llm_provider=llm_provider,
        llm_model=llm_model,
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
        host: str = typer.Option("0.0.0.0", "--host", help="Host to bind the server to."),  # noqa: S104
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the server on."),
    reload: bool = typer.Option(
        False, "--reload", help="Auto-reload on code changes (development)."
    ),
):
    """Start the MCP server for RAG functionality."""
    if not index_dir.exists():
        typer.echo(f"Error: Index directory not found: {index_dir}")
        raise typer.Exit(code=1)

    # Set environment variable for the server to find the index
    os.environ["ATHENAEUM_INDEX_DIR"] = str(index_dir.absolute())

    # Prepare the uvicorn command
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "athenaeum.mcp_server:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    if reload:
        cmd.append("--reload")

    typer.echo(f"Starting MCP server with index: {index_dir}")
    typer.echo(f"API will be available at: http://{host}:{port}")

    # Run the server process
    try:
        process = subprocess.Popen(cmd)  # noqa: S603
        typer.echo("Server running. Press Ctrl+C to stop.")

        # Handle graceful shutdown
        def signal_handler(_sig, _frame):
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
