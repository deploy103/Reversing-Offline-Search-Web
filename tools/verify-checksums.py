#!/usr/bin/env python3
"""
verify-checksums.py

tools/manifest.json 에 기록된 각 항목의 local_path 파일이 실제로 존재하는지 확인하고,
존재한다면 SHA256 해시를 계산하여 manifest.json의 sha256 값과 대조한다.

표준 라이브러리(hashlib, json, pathlib)만 사용한다 - 외부 의존성 없음.

사용법:
    python3 tools/verify-checksums.py
    python3 verify-checksums.py            (tools/ 디렉터리 안에서 실행해도 됨)

결과:
    각 항목에 대해 PASS / FAIL / SKIP 을 출력한다.
      PASS - 파일이 존재하고 SHA256이 manifest와 일치
      FAIL - 파일이 존재하지만 SHA256이 manifest와 불일치
      SKIP - manifest에 sha256이 비어있거나(수동 설치/apt 안내형), local_path에 파일이 없음

종료 코드:
    0 - FAIL이 하나도 없으면 (SKIP/PASS만 있어도 0)
    1 - 하나 이상 FAIL이 있으면
"""

import hashlib
import json
import sys
from pathlib import Path

# 이 스크립트가 어디서 실행되든 저장소 루트를 기준으로 경로를 해석한다.
# tools/verify-checksums.py 이므로 부모의 부모가 저장소 루트.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = SCRIPT_DIR / "manifest.json"

CHUNK_SIZE = 1024 * 1024  # 1 MiB


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def resolve_local_path(local_path: str) -> Path:
    p = Path(local_path)
    if p.is_absolute():
        return p
    return REPO_ROOT / p


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] manifest를 찾을 수 없음: {MANIFEST_PATH}")
        return 1

    try:
        with MANIFEST_PATH.open(encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] manifest.json 파싱 실패: {e}")
        return 1

    if not isinstance(manifest, list):
        print("[ERROR] manifest.json의 최상위 구조는 배열(list)이어야 합니다.")
        return 1

    pass_count = 0
    fail_count = 0
    skip_count = 0

    for idx, entry in enumerate(manifest):
        name = entry.get("name", f"(이름 없음 #{idx})")
        expected_sha = (entry.get("sha256") or "").strip().lower()
        local_path_str = entry.get("local_path", "")

        if not local_path_str:
            print(f"[SKIP] {name}: local_path가 비어 있음")
            skip_count += 1
            continue

        local_path = resolve_local_path(local_path_str)

        if not local_path.exists():
            print(f"[SKIP] {name}: 파일 없음 ({local_path_str})")
            skip_count += 1
            continue

        if local_path.is_dir():
            print(f"[SKIP] {name}: local_path가 디렉터리임 ({local_path_str}) - 개별 파일을 지정하세요")
            skip_count += 1
            continue

        if not expected_sha:
            print(f"[SKIP] {name}: manifest에 sha256 값이 비어 있음 (수동 설치/apt 안내형 항목, 파일은 존재함: {local_path_str})")
            skip_count += 1
            continue

        actual_sha = sha256_of_file(local_path)

        if actual_sha.lower() == expected_sha:
            print(f"[PASS] {name}: {local_path_str}")
            pass_count += 1
        else:
            print(f"[FAIL] {name}: {local_path_str}")
            print(f"        기대값(manifest): {expected_sha}")
            print(f"        실제값(계산됨) : {actual_sha}")
            fail_count += 1

    print()
    print(f"결과 요약: PASS={pass_count}  FAIL={fail_count}  SKIP={skip_count}  (전체 {len(manifest)}개 항목)")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
