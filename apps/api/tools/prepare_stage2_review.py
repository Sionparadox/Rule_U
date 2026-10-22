"""Build source inventory and small, manually page-labelled retrieval smoke set."""

import json
from pathlib import Path

from rule_u.config import Settings
from rule_u.discovery import inventory
from rule_u.ingestion import digest, load_catalog, save_json

root = Path(__file__).resolve().parents[3]
rows = load_catalog(root.parent / "data/games")
settings = Settings()
game = next(r for r in rows if r["slug"] == "codenames")
edition = game["editions"][0]
document = edition["documents"][0]
reviews = {digest((edition["id"] + ":" + document["local_path"]).encode()): {
    "sha256": document["sha256"], "status": "official_verified",
    "edition_review": "Korean PDF at publisher URL; exact print revision unconfirmed",
    "evidence": "2026-10-22 publisher game page and Korean 8-page PDF checked: "
                + document["source_url"] + " ; " + document["download_url"],
    "license_note": "Publisher provides rule PDF; all rights reserved. "
                    "No blanket redistribution/embedding licence confirmed.",
}}
save_json(root / "config/source-reviews.json", reviews)
for slug, evidence in [
    ("6-nimmt", "https://blog.amigo-spiele.de/content/ws/plenty.php?id=4910&select=downloads "
                "Manual Korean link matches registered download URL; PDF fetch timed out."),
    ("7-wonders-architects", "https://www.rprod.com/en/games/7-wonders-architects "
                            "KR rules link matches registered download URL; web PDF size limit."),
]:
    game = next(r for r in rows if r["slug"] == slug)
    for edition in game["editions"]:
        for document in edition["documents"]:
            reviews[digest((edition["id"] + ":" + document["local_path"]).encode())] = {
                "sha256": document["sha256"], "status": "official_verified",
                "edition_review": "Publisher Korean rules link verified; print revision unconfirmed",
                "evidence": "2026-10-22 " + evidence,
                "license_note": "Public rule download confirmed; redistribution licence unconfirmed.",
            }
save_json(root / "config/source-reviews.json", reviews)
save_json(root / "reports/source-inventory.json", inventory(settings, rows, reviews))

cases = []
for game_id, question, pages in [
    ("codenames", "힌트 숫자가 3이면 최대 몇 번 추리할 수 있나요?", [5]),
    ("codenames", "암살자 카드를 고르면 어떻게 되나요?", [5]),
    ("codenames", "힌트 숫자로 0을 말하면 무엇이 달라지나요?", [7]),
    ("catan", "차례가 아닌 사람들끼리 자원을 거래해도 되나요?", [2]),
    ("catan", "도로 건설 진보 카드는 어떤 효과인가요?", [1, 3]),
    ("coup", "돈을 10개 이상 가진 경우 반드시 쿠데타를 해야 하나요?", [1]),
    ("6-nimmt", "게임을 시작할 때 각자 카드를 몇 장 받나요?", [1]),
    ("7-wonders-architects", "불가사의를 완성하면 게임은 언제 끝나나요?", [3]),
]:
    source = json.loads((settings.data_dir / "manifests" / f"{game_id}.json")
                        .read_text(encoding="utf-8"))[0]
    cases.append({"game_id": game_id, "edition_id": source["edition_id"],
                  "document_id": source["document_id"], "question": question, "pages": pages})
save_json(root / "evals/retrieval-smoke-cases.json", cases)
print({"documents": len(inventory(settings, rows, reviews)), "cases": len(cases)})
