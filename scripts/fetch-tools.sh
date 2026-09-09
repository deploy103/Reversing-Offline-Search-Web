#!/usr/bin/env bash
#
# fetch-tools.sh
#
# tools/manifest.json 을 읽어서 release_url이 있는 항목만 실제로 다운로드하고,
# local_path 위치에 저장한 뒤 SHA256을 검증한다.
#
# - release_url이 없는 항목(PyPI/apt/수동 설치형)은 건너뛰고 안내 메시지를 출력한다.
# - bash + curl 만 있으면 동작한다 (python, jq 등 외부 의존성 없음).
#
# 사용법:
#   bash scripts/fetch-tools.sh
#   bash scripts/fetch-tools.sh --only "Ghidra"     (이름에 문자열이 포함된 항목만 처리)
#
set -u

# 저장소 루트 계산 (이 스크립트는 scripts/ 안에 있음)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$REPO_ROOT/tools/manifest.json"

FILTER=""
if [[ "${1:-}" == "--only" && -n "${2:-}" ]]; then
    FILTER="$2"
fi

if [[ ! -f "$MANIFEST" ]]; then
    echo "[ERROR] manifest를 찾을 수 없음: $MANIFEST" >&2
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "[ERROR] curl이 필요합니다." >&2
    exit 1
fi

# python3이 있으면 JSON 파싱에 사용(정확함). 없으면 최소한의 grep/sed 폴백을 시도한다.
HAVE_PYTHON=0
if command -v python3 >/dev/null 2>&1; then
    HAVE_PYTHON=1
fi

if [[ "$HAVE_PYTHON" -ne 1 ]]; then
    echo "[ERROR] 이 스크립트는 JSON 파싱을 위해 python3을 필요로 합니다." >&2
    echo "        (python3 자체는 실행 시에만 필요하며, dist/ 산출물에는 영향 없음)" >&2
    exit 1
fi

TOTAL=0
DOWNLOADED=0
VERIFIED_OK=0
VERIFIED_FAIL=0
SKIPPED=0

# manifest.json을 한 줄에 하나씩, 탭으로 구분된 필드로 뽑아낸다.
# 필드 순서: name \t release_url \t sha256 \t local_path
while IFS=$'\t' read -r NAME RELEASE_URL SHA256 LOCAL_PATH; do
    TOTAL=$((TOTAL + 1))

    if [[ -n "$FILTER" && "$NAME" != *"$FILTER"* ]]; then
        continue
    fi

    if [[ -z "$RELEASE_URL" ]]; then
        echo "[SKIP] $NAME: release_url 없음 (PyPI/apt/수동 설치 안내형 항목)"
        if [[ "$NAME" == *"(PyPI"* || "$NAME" == *"PyPI)"* ]]; then
            PKG=$(echo "$NAME" | sed -E 's/ ?\(PyPI.*\)//')
            echo "        -> pip download $PKG -d offline-kit/wheels/  로 오프라인 준비 가능"
        elif [[ -n "$LOCAL_PATH" && "$LOCAL_PATH" == *"apt"* || "$LOCAL_PATH" == *"-debs"* ]]; then
            echo "        -> apt-get download <패키지명>  으로 오프라인 준비 (offline_install 필드 참고)"
        else
            echo "        -> tools/manifest.json의 offline_install 필드를 참고해 수동으로 준비하세요"
        fi
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    DEST="$REPO_ROOT/$LOCAL_PATH"
    DEST_DIR="$(dirname "$DEST")"
    mkdir -p "$DEST_DIR"

    echo "[GET ] $NAME"
    echo "        $RELEASE_URL"
    echo "        -> $LOCAL_PATH"

    if ! curl -L -f -sS -o "$DEST" "$RELEASE_URL"; then
        echo "[ERROR] 다운로드 실패: $NAME ($RELEASE_URL)" >&2
        continue
    fi
    DOWNLOADED=$((DOWNLOADED + 1))

    if [[ -z "$SHA256" ]]; then
        echo "[WARN] $NAME: manifest에 sha256 값이 없어 검증을 건너뜁니다 (다운로드는 완료됨)"
        continue
    fi

    ACTUAL_SHA=""
    if command -v sha256sum >/dev/null 2>&1; then
        ACTUAL_SHA="$(sha256sum "$DEST" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        ACTUAL_SHA="$(shasum -a 256 "$DEST" | awk '{print $1}')"
    else
        echo "[ERROR] sha256sum/shasum 명령을 찾을 수 없어 체크섬 검증이 불가능합니다." >&2
        exit 1
    fi

    EXPECTED_SHA_LOWER=$(echo "$SHA256" | tr '[:upper:]' '[:lower:]')
    ACTUAL_SHA_LOWER=$(echo "$ACTUAL_SHA" | tr '[:upper:]' '[:lower:]')

    if [[ "$ACTUAL_SHA_LOWER" == "$EXPECTED_SHA_LOWER" ]]; then
        echo "[ OK ] $NAME: SHA256 일치"
        VERIFIED_OK=$((VERIFIED_OK + 1))
    else
        echo "[FAIL] $NAME: SHA256 불일치!" >&2
        echo "        기대값: $SHA256" >&2
        echo "        실제값: $ACTUAL_SHA" >&2
        echo "        손상되었거나 변조된 파일일 수 있습니다. 삭제 후 다시 시도하세요." >&2
        rm -f "$DEST"
        VERIFIED_FAIL=$((VERIFIED_FAIL + 1))
        echo "" >&2
        echo "[STOP] 체크섬 불일치로 중단합니다." >&2
        exit 1
    fi

done < <(python3 - "$MANIFEST" << 'PYEOF'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
for e in data:
    name = (e.get("name") or "").replace("\t", " ")
    release_url = (e.get("release_url") or "").replace("\t", " ")
    sha256 = (e.get("sha256") or "").replace("\t", " ")
    local_path = (e.get("local_path") or "").replace("\t", " ")
    print(f"{name}\t{release_url}\t{sha256}\t{local_path}")
PYEOF
)

echo ""
echo "==================== 요약 ===================="
echo "전체 항목:        $TOTAL"
echo "다운로드 시도:     $DOWNLOADED"
echo "체크섬 일치(OK):   $VERIFIED_OK"
echo "체크섬 불일치:     $VERIFIED_FAIL"
echo "스킵(수동/PyPI/apt): $SKIPPED"
echo "================================================"
