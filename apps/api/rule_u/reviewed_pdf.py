"""Explicit visual reviews bound to original PDF hashes and physical page numbers."""

import hashlib
from pathlib import Path

import pymupdf


def reviewed_pages(path, reviews):
    source = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    excluded = {"cover", "illustration", "foreign_language", "credits",
                "advertisement", "blank_template"}
    pages = []
    with pymupdf.open(path) as document:
        if document.needs_pass:
            raise ValueError("encrypted_pdf")
        for number, page in enumerate(document, 1):
            text = page.get_text()
            result = {"page": number, "locator": f"page:{number}", "text": text}
            review = reviews.get(f"{source}:{number}")
            if review:
                if (review.get("source_id") != source or review.get("page") != number
                        or review.get("reviewer") != "assistant_visual"):
                    raise ValueError("invalid_visual_review_identity")
                image_hash = hashlib.sha256(Path(review["path"]).read_bytes()).hexdigest()
                if image_hash != review.get("image_hash"):
                    raise ValueError("review_image_hash_mismatch")
                kind = review["kind"]
                if kind in {"rules", "diagram"}:
                    if not review.get("text", "").strip():
                        raise ValueError("empty_visual_review")
                    result["text"] = review["text"]
                    result["extraction_method"] = "assistant_visual_summary"
                elif kind in excluded:
                    result["text"] = ""
                    result["extraction_method"] = "visually_reviewed_exclusion"
                else:
                    raise ValueError("unknown_visual_review_kind")
                result["review_note"] = review.get("note", "")
                result["review_kind"] = kind
                result["image_hash"] = image_hash
            elif len(text.strip()) < 20:
                raise ValueError(f"missing_visual_review:page:{number}")
            pages.append(result)
    if not pages:
        raise ValueError("empty_pdf")
    return pages
