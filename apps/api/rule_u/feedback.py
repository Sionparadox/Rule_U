"""Export "wrong answer" feedback for manual review before it becomes an evaluation case."""

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from rule_u.config import Settings
from rule_u.db import make_engine, make_sessions
from rule_u.ingestion import save_json
from rule_u.models import AnswerFeedback, Citation, Conversation, Message


def export(settings, include_helpful=False):
    """Reviewers decide the expected pages; nothing here becomes a label automatically."""
    engine = make_engine(settings)
    items = []
    try:
        with make_sessions(engine)() as db:
            query = select(AnswerFeedback).order_by(AnswerFeedback.created_at)
            if not include_helpful:
                query = query.where(AnswerFeedback.rating == "wrong")
            for feedback in db.scalars(query):
                message = db.get(Message, feedback.message_id)
                conversation = db.get(Conversation, message.conversation_id)
                question = db.scalar(select(Message.content).where(
                    Message.conversation_id == message.conversation_id, Message.role == "user",
                    Message.created_at <= message.created_at).order_by(
                        Message.created_at.desc(), Message.id.desc()).limit(1)) or ""
                citations = list(db.scalars(select(Citation).where(
                    Citation.message_id == message.id)))
                items.append({
                    "status": "needs_review",
                    "game_id": conversation.game_id,
                    "edition_id": conversation.edition_id,
                    "question": question,
                    "answer": message.content,
                    "verdict": message.verdict,
                    "cited": [{"document_id": c.document_id, "page_start": c.page_start}
                              for c in citations],
                    "rating": feedback.rating,
                    "reason": feedback.reason,
                    "note": feedback.note,
                    "message_id": message.id,
                    "reported_at": feedback.created_at.isoformat(),
                })
    finally:
        engine.dispose()
    return {"count": len(items), "items": items}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["export"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-helpful", action="store_true")
    args = parser.parse_args()
    result = export(Settings(), args.include_helpful)
    save_json(args.output, result)
    print(json.dumps({"output": str(args.output), "count": result["count"]}))


if __name__ == "__main__":
    main()
