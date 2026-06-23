"""
Knowledge base ingestion CLI.

Usage examples:

  # Ingest a single PDF
  python scripts/ingest.py --file docs/faq.pdf

  # Ingest all PDFs in a directory
  python scripts/ingest.py --dir docs/

  # Override the doc_id (single file only)
  python scripts/ingest.py --file docs/faq.pdf --doc-id faq-v2

  # Custom chunk settings
  python scripts/ingest.py --dir docs/ --chunk-size 600 --overlap 80

  # Preview what would be ingested without writing to ChromaDB
  python scripts/ingest.py --file docs/faq.pdf --dry-run

  # Delete a document from the knowledge base
  python scripts/ingest.py --delete faq-v1

  # Tag all chunks with extra metadata
  python scripts/ingest.py --dir docs/ --tag category=faq --tag language=nl
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ai.rag.knowledge_base_service import ChromaKnowledgeBase
from app.knowledge.document_ingestion import DocumentIngestionPipeline, IngestionResult


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_tags(raw: list[str]) -> dict:
    tags: dict = {}
    for item in raw or []:
        if "=" not in item:
            print(f"[warn] Ignoring malformed tag (expected key=value): {item}")
            continue
        key, _, value = item.partition("=")
        tags[key.strip()] = value.strip()
    return tags


def _print_result(result: IngestionResult) -> None:
    status = "OK" if result.success else "FAILED"
    print(
        f"  [{status}] {result.source_file}"
        f" — {result.pages_extracted} pages"
        f", {result.chunks_stored} chunks"
        f"  (hash: {result.file_hash[:12]}…)"
    )
    for err in result.errors:
        print(f"         error: {err}")


# ── Core actions ──────────────────────────────────────────────────────────────


async def _run_ingest(args: argparse.Namespace) -> int:
    extra_metadata = _parse_tags(args.tag)
    kb = ChromaKnowledgeBase()

    pipeline = DocumentIngestionPipeline(
        store_fn=kb.ingest_chunks_batch,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    results: list[IngestionResult] = []

    if args.file:
        path = Path(args.file)
        if args.dry_run:
            await _dry_run_file(path, pipeline)
            return 0
        result = await pipeline.ingest_pdf(path, doc_id=args.doc_id, extra_metadata=extra_metadata)
        results.append(result)

    elif args.dir:
        if args.dry_run:
            await _dry_run_dir(Path(args.dir), pipeline)
            return 0
        results = await pipeline.ingest_directory(
            Path(args.dir), extra_metadata=extra_metadata
        )

    print(f"\nIngestion summary — {len(results)} file(s)")
    print("─" * 60)
    for r in results:
        _print_result(r)

    failed = sum(1 for r in results if not r.success)
    total_chunks = sum(r.chunks_stored for r in results)
    print("─" * 60)
    print(f"Total chunks stored : {total_chunks}")
    print(f"Failed              : {failed}")

    return 1 if failed else 0


async def _run_delete(doc_id: str) -> int:
    kb = ChromaKnowledgeBase()
    print(f"Deleting document '{doc_id}' from knowledge base…")
    await kb.delete_document(doc_id)
    print("Done.")
    return 0


async def _dry_run_file(path: Path, pipeline: DocumentIngestionPipeline) -> None:
    from app.knowledge.document_ingestion import PDFExtractor

    print(f"\n[dry-run] {path.name}")
    pages = await PDFExtractor().extract(path)
    total_chunks = 0
    for page in pages:
        chunks = pipeline._chunker.chunk(page.text)
        print(f"  Page {page.page_number:3d} → {len(chunks):3d} chunk(s)")
        total_chunks += len(chunks)
    print(f"  Total: {len(pages)} pages, {total_chunks} chunks — nothing written.")


async def _dry_run_dir(dir_path: Path, pipeline: DocumentIngestionPipeline) -> None:
    pdfs = sorted(dir_path.glob("**/*.pdf"))
    print(f"\n[dry-run] {dir_path}  ({len(pdfs)} PDF file(s) found)")
    for pdf in pdfs:
        await _dry_run_file(pdf, pipeline)


# ── Entry point ───────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kinderuniversiteit knowledge base ingestion CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--file", metavar="PATH", help="Single PDF file to ingest")
    source.add_argument("--dir", metavar="DIR", help="Directory of PDFs to ingest recursively")
    source.add_argument("--delete", metavar="DOC_ID", help="Delete a document from the knowledge base")

    parser.add_argument("--doc-id", metavar="ID", help="Override doc_id (single file only)")
    parser.add_argument("--chunk-size", type=int, default=800, metavar="N", help="Max chars per chunk (default: 800)")
    parser.add_argument("--overlap", type=int, default=100, metavar="N", help="Overlap chars between chunks (default: 100)")
    parser.add_argument("--tag", action="append", metavar="key=value", help="Extra metadata tag (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Preview chunking without writing to ChromaDB")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not any([args.file, args.dir, args.delete]):
        parser.print_help()
        sys.exit(0)

    if args.doc_id and args.dir:
        parser.error("--doc-id can only be used with --file, not --dir")

    if args.delete:
        exit_code = asyncio.run(_run_delete(args.delete))
    else:
        exit_code = asyncio.run(_run_ingest(args))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
