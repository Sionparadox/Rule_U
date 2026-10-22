import hashlib

import pymupdf
import pytest

from rule_u.ingestion import chunks_for
from rule_u.reviewed_pdf import reviewed_pages


def test_review_requires_bound_hash_and_keeps_physical_pages(tmp_path):
    pdf = tmp_path / "rules.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.new_page()
        document.save(pdf)
    source = hashlib.sha256(pdf.read_bytes()).hexdigest()
    image = tmp_path / "review.png"
    image.write_bytes(b"reviewed image fixture")
    base = {"source_id": source, "reviewer": "assistant_visual", "path": str(image),
            "image_hash": hashlib.sha256(image.read_bytes()).hexdigest()}
    reviews = {
        f"{source}:1": dict(base, page=1, kind="cover", text=""),
        f"{source}:2": dict(base, page=2, kind="rules", text="Reviewed rule text."),
    }
    pages = reviewed_pages(pdf, reviews)
    chunks = chunks_for(pages, source)
    assert len(pages) == 2
    assert len(chunks) == 1
    assert chunks[0]["page_start"] == 2
    assert chunks[0]["extraction_method"] == "assistant_visual_summary"
    with pytest.raises(ValueError, match="missing_visual_review"):
        reviewed_pages(pdf, {})
    reviews[f"{source}:2"]["reviewer"] = "unreviewed_draft"
    with pytest.raises(ValueError, match="invalid_visual_review_identity"):
        reviewed_pages(pdf, reviews)
    reviews[f"{source}:2"]["reviewer"] = "assistant_visual"
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="review_image_hash_mismatch"):
        reviewed_pages(pdf, reviews)
