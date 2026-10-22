"""Retry failed local PDFs with both parsers and record page-level failure evidence."""

import argparse
import json
from collections import Counter
from pathlib import Path

import pymupdf

from rule_u.config import Settings
from rule_u.ingestion import digest, extract_pages, load_catalog, local_file, save_json


def diagnose(settings, catalog, bundle_root):
    results = []
    for game in load_catalog(catalog):
        manifest = settings.data_dir / "manifests" / f"{game['slug']}.json"
        if not manifest.exists():
            continue
        failed = {
            r["source_id"]
            for r in json.loads(manifest.read_text(encoding="utf-8"))
            if r["status"] == "failed"
        }
        for edition in game["editions"]:
            for item in edition.get("documents", []):
                if item.get("status") != "downloaded":
                    continue
                source_id = digest((edition["id"] + ":" + item["local_path"]).encode())
                if source_id not in failed:
                    continue
                path = local_file(bundle_root, item["local_path"])
                result = {
                    "game_id": game["slug"],
                    "name": game["name_ko"],
                    "edition": edition["name"],
                    "source_id": source_id,
                    "local_path": item["local_path"],
                    "attempts": {},
                    "pages": [],
                }
                if digest(path.read_bytes()) != item.get("sha256"):
                    result.update(reason="source_hash_mismatch", recoverable=False)
                else:
                    for parser in ("pypdf", "pymupdf"):
                        try:
                            pages = extract_pages(path, item.get("type"), parser)
                            result["attempts"][parser] = {"status": "success", "pages": len(pages)}
                        except Exception as exc:
                            # Diagnostic command records per-document failures and continues.
                            result["attempts"][parser] = {
                                "status": "failed",
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                    try:
                        with pymupdf.open(path) as pdf:
                            for number, page in enumerate(pdf, 1):
                                result["pages"].append(
                                    {
                                        "page": number,
                                        "characters": len(page.get_text().strip()),
                                        "image_resources": len(page.get_images()),
                                    }
                                )
                    except Exception as exc:
                        result["inspection_error"] = f"{type(exc).__name__}: {exc}"
                    result["short_pages"] = [p for p in result["pages"] if p["characters"] < 20]
                    result["recoverable"] = any(
                        a["status"] == "success" for a in result["attempts"].values()
                    )
                    result["reason"] = (
                        "recovered"
                        if result["recoverable"]
                        else "all_pages_short"
                        if result["pages"] and len(result["short_pages"]) == len(result["pages"])
                        else "some_pages_short"
                        if result["short_pages"]
                        else "parser_error"
                    )
                results.append(result)
                save_json(settings.data_dir / "retry-reports" / "remaining-49-retry.json", results)
                print(json.dumps({"game": game["slug"], "reason": result["reason"]}), flush=True)
    return results


def write_report(results, destination):
    counts = Counter(r["reason"] for r in results)
    lines = [
        "# 잔여 49게임 실패 문서 재시도 결과",
        "",
        "- 실행일: 2026-10-22",
        f"- 대상: {len({r['game_id'] for r in results})}게임, {len(results)}문서.",
        "- 각 문서를 pypdf와 PyMuPDF로 다시 추출하고, 원본 SHA-256 및 페이지별 문자 수를 확인했다.",
        f"- 추가 복구: {counts['recovered']}문서. 모든 페이지 부족: {counts['all_pages_short']}문서, "
        f"일부 페이지 부족: {counts['some_pages_short']}문서.",
        "- 실패 기준: 한 페이지라도 추출문이 공백 제거 후 20자 미만이면 문서 전체를 보류한다. "
        "짧은 표지·그림 페이지도 이 기준에 걸리므로, 실패가 곧 PDF 손상이나 전체 본문 부재를 뜻하지 않는다.",
        "- 문자 수·이미지 참조 수는 PyMuPDF 기준이다. 이미지 참조가 있다는 사실만으로 "
        "스캔본이라고 단정하지 않는다. 글자가 이미지나 벡터 윤곽선으로 저장됐거나 문자 매핑이 없는 "
        "가능성도 있어 해당 페이지의 시각 검토가 필요하다.",
        "- 원본·기존 색인은 변경하지 않았다. OCR·페이지 제외·외부 API 전송은 수행하지 않았다.",
        "- 상세 JSON: `data/retry-reports/remaining-49-retry.json` (로컬 데이터, Git 제외).",
        "",
        "## 문서별 원인과 다음 조치",
        "",
        "실패 페이지 표기는 `페이지(추출 문자 수)`이다. 페이지 번호는 PDF 물리 페이지 기준이다.",
        "",
        "| 게임 / 판본 | 실패 이유 | 부족 페이지(문자 수) | 해당 페이지 이미지 참조 | 다음 조치 |",
        "|---|---|---|---|---|",
    ]
    for row in results:
        short = row.get("short_pages", [])
        reason = {
            "all_pages_short": "모든 페이지가 20자 미만: 텍스트 레이어로 규칙을 확보하지 못함",
            "some_pages_short": "일부 페이지가 20자 미만: 나머지 본문이 있어도 현재 완전성 검사에서 보류",
            "recovered": "대체 추출 성공",
            "source_hash_mismatch": "원본 해시 불일치",
            "parser_error": "추출기 오류",
        }[row["reason"]]
        action = (
            "페이지를 확인한 뒤 한국어 OCR 또는 텍스트가 포함된 PDF 확보"
            if row["reason"] == "all_pages_short"
            else "부족 페이지가 표지·삽화인지 확인; 규칙 본문이면 OCR, 비본문이면 명시적 제외 검토"
        )
        pages = ", ".join(f"{p['page']}({p['characters']})" for p in short) or "해당 없음"
        images = ", ".join(f"{p['page']}쪽:{p['image_resources']}개" for p in short) or "해당 없음"
        title = f"{row['name']} / {row['edition']}".replace("|", "/")
        lines.append(f"| {title} | {reason} | {pages} | {images} | {action} |")
    report = "\n".join(lines) + "\n"
    if destination.exists():
        previous = destination.read_text(encoding="utf-8")
        start = previous.find("## 화면으로 추가 확인한 사례")
        end = previous.find("## 문서별 원인과 다음 조치", start)
        if start >= 0 and end > start:
            report = report.replace(
                "## 문서별 원인과 다음 조치", previous[start:end] + "## 문서별 원인과 다음 조치", 1
            )
    destination.write_text(report, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    results = diagnose(settings, args.catalog, args.bundle_root)
    destination = settings.data_dir / "retry-reports" / "failed-document-retry-report.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_report(results, destination)


if __name__ == "__main__":
    main()
