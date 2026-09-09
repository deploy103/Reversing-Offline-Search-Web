---
id: REV-0305
title: "Diffing으로 패치된 버전과 원본 비교하는 기초"
slug: "rev-0305-diffing-patched-vs-original"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, "BinDiff", "diaphora", objdump, diff]
keywords: [바이너리 diffing, 패치 비교, BinDiff, diaphora, 원본과 패치본 비교, n-day 분석]
aliases: ["패치 전후 비교", "바이너리 diff 방법", "두 버전 비교하기", "패치된 함수 찾기"]
symptom_keywords: ["패치 전후 파일 두 개를 받았는데 뭐가 다른지 모르겠음", "업데이트로 뭐가 바뀌었는지 확인해야 함", "n-day 취약점 문제인데 diff를 어떻게 하는지 모름", "함수는 그대로인데 바이트가 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
패치 전/후 두 바이너리가 주어지면 파일 전체를 읽는 대신 **함수 단위 diffing 도구(BinDiff, diaphora)로 변경된 함수만 자동으로 추려낸 뒤**, 그 함수들만 집중 분석하는 것이 표준 접근이다.

## 언제 검색해야 하나
- 문제에 `patched`/`original`, `before`/`after`, 버전 번호가 다른 바이너리 두 개가 함께 첨부되어 있을 때
- "이 업데이트로 어떤 취약점이 고쳐졌는가"를 찾아야 하는 n-day류 문제를 만났을 때
- 두 바이너리의 크기/해시가 다른데 육안으로는 차이를 못 찾겠을 때

## 핵심 개념
Diffing(바이너리 비교)은 두 바이너리의 함수를 서로 매칭시킨 뒤, 매칭된 함수 쌍 중 **명령어/그래프 구조가 다른 함수만** 골라내는 작업이다. 단순 텍스트 diff(`diff` 명령)는 바이너리에는 거의 쓸모가 없다 — 컴파일러가 함수 순서를 바꾸거나 주소가 살짝 밀리기만 해도 파일 전체가 다르게 보이기 때문이다. 그래서 전용 도구가 필요하다.

- **BinDiff**(zynamics/Google, 무료): IDA 데이터베이스(`.idb`/`.i64`) 두 개를 비교해서 함수를 그래프 구조(콜그래프, 제어흐름그래프)와 문자열/상수 유사도로 매칭한다. 결과를 "Similarity" 점수(0.0~1.0)로 보여주며, 점수가 1.0이면 완전히 동일, 낮을수록 많이 바뀐 함수다.
- **Diaphora**(오픈소스, 무료): BinDiff와 유사한 목적의 IDA/Ghidra 플러그인. SQLite 기반으로 두 데이터베이스의 함수 시그니처를 비교한다.
- **objdump + diff 조합**(초간단 대안): 도구 설치가 어려운 환경에서 `objdump -d`로 두 바이너리를 각각 어셈블리 텍스트로 뽑고, 주소를 제거한 뒤 `diff`로 비교하는 방법. 정밀하진 않지만 급할 때 쓸 수 있다.

n-day 취약점 분석에서 diffing이 중요한 이유는, 벤더가 "보안 패치"라고만 공지하고 세부 내용을 밝히지 않는 경우가 많기 때문이다. 패치 전/후 바이너리를 diffing하면 **어떤 함수가 바뀌었는지**, 그리고 그 함수의 변경 내용(범위 체크 추가, 조건문 추가, 함수 호출 추가 등)으로 **원래 무엇이 취약했는지**를 역으로 추론할 수 있다.

## 화면/코드에서 보이는 징후
- `chall_v1`, `chall_v2`처럼 버전이 다른 두 바이너리, 또는 `chall.old`, `chall.new`라는 이름의 파일이 첨부되어 있다.
- 두 파일의 SHA256 해시가 다른데 `strings` 결과는 거의 동일하다.
- 문제 설명에 "이 프로그램의 최신 버전에서 패치된 취약점을 찾아 익스플로잇하세요" 같은 문구가 있다.

## 가장 먼저 할 것
두 바이너리를 각각 IDA(또는 Ghidra)로 열어 자동 분석을 완료시킨다(초기 오토 애널리시스가 끝날 때까지 대기). IDA를 쓴다면 각각 `.i64`로 저장해두고, 이후 BinDiff로 이 두 파일을 비교한다.

## 단계별 절차

**1) 두 바이너리 기본 정보 대조**
```bash
sha256sum chall_old chall_new
diff <(strings chall_old) <(strings chall_new)
```
문자열 목록 차이만으로도 새로 추가된 에러 메시지("Invalid length!" 등)가 보이면, 그 근처에 범위 체크 코드가 추가됐을 가능성이 높다는 1차 힌트를 얻는다.

**2) IDA에서 각각 오토 애널리시스 후 저장**
`chall_old`, `chall_new`를 각각 IDA로 열고 자동 분석이 끝나면 File → Save로 `.idb`/`.i64` 저장.

**3) BinDiff 실행**
BinDiff GUI에서 두 `.idb`/`.i64` 파일을 각각 primary/secondary로 선택해 diff를 실행한다. 결과 창에 "Matched Functions" 목록이 similarity 점수와 함께 표시된다.

**4) similarity가 낮은 함수부터 정렬해서 확인**
결과 테이블을 Similarity 오름차순으로 정렬한다. 1.0(완전 동일)인 함수는 무시하고, 0.5~0.95 사이의 함수(구조는 비슷하지만 일부 명령어가 바뀐 함수)를 우선 확인한다. 완전히 새로 추가된 함수("Unmatched" 목록)도 별도로 확인한다.

**5) 변경된 함수를 나란히 놓고 어셈블리/디컴파일 비교**
BinDiff 결과에서 함수 쌍을 더블클릭하면 두 함수의 그래프를 나란히 보여주는 뷰(Primary/Secondary 그래프)가 뜬다. 색으로 표시된 차이(보통 빨강/초록 계열로 추가/삭제된 베이직 블록 강조)를 보고 어떤 분기/체크가 추가되었는지 확인한다. IDA에서 각 함수를 F5로 디컴파일해서 나란히 띄우고 비교해도 좋다.

**6) Diaphora 대안 절차(BinDiff 설치가 어려운 경우)**
Diaphora는 각 IDA 인스턴스에서 스크립트를 실행해 `.sqlite` 데이터베이스를 export한 뒤, 별도 Diaphora GUI로 두 sqlite 파일을 diff한다. 결과 화면 구성은 BinDiff와 유사하게 매칭 함수/유사도 목록을 보여준다.

**7) 취약점 추론**
변경된 함수에서 새로 추가된 조건문이 길이 체크, 인덱스 범위 체크, NULL 체크라면, **패치 전 버전에는 그 체크가 없었다**는 뜻이다. 즉 패치 전 버전에서 그 체크가 없어서 발생하던 취약점(버퍼 오버플로우, OOB 접근 등)을 거꾸로 추론할 수 있다.

## 명령어/단축키
```bash
sha256sum chall_old chall_new
diff <(strings chall_old) <(strings chall_new)
objdump -d chall_old | sed -E 's/^\s*[0-9a-f]+:/ADDR:/' > old.asm
objdump -d chall_new | sed -E 's/^\s*[0-9a-f]+:/ADDR:/' > new.asm
diff old.asm new.asm
```
BinDiff: primary/secondary `.idb` 선택 → Diff 실행 → Matched Functions 테이블 Similarity 열 정렬.
Diaphora: IDA에서 export 스크립트 실행 → 두 `.sqlite` 로드 → Best/Partial/Unmatched 탭 확인.

## 출력 해석
- BinDiff Similarity가 1.0인 함수는 완전히 동일한 코드이므로 분석에서 제외해도 안전하다.
- Similarity가 0.5 전후인 함수는 그래프 구조(분기 개수)는 비슷하지만 일부 명령어가 바뀐 것이다 — 상수 값 변경, 조건 반전 등을 의심한다.
- "Unmatched" 목록에 있는 함수는 완전히 새로 추가되었거나 완전히 삭제된 함수다. 새로 추가된 함수가 `validate_length`, `check_bounds` 같은 이름(또는 strip되어 있어도 단순 비교 후 함수 호출 패턴)이면 그 자체가 패치의 핵심이다.
- `objdump` 텍스트 diff에서는 주소값 자체가 달라 거의 모든 줄이 다르게 나올 수 있으므로, 반드시 주소를 정규식으로 제거(마스킹)한 뒤 비교해야 의미 있는 결과가 나온다.

## 흔한 실수
- 두 바이너리를 처음부터 끝까지 손으로 함수 하나하나 대조하려다 시간을 다 쓰는 것 — 함수가 수십~수백 개면 반드시 도구를 써야 한다.
- `objdump` 텍스트를 마스킹 없이 그냥 `diff`해서 "전부 다르다"는 무의미한 결과만 얻는 것.
- BinDiff Similarity가 낮은 함수만 보고 "Unmatched"(아예 매칭 안 된 새 함수/삭제된 함수) 목록은 확인하지 않아 핵심 변경을 놓치는 것.
- 컴파일러/최적화 옵션이 달라서 생긴 무관한 차이(레지스터 할당 차이, 인라이닝 차이)를 전부 "취약점 패치"로 오인하는 것 — 반드시 실제 조건문/체크 로직 추가 여부로 판단해야 한다.

## 막혔을 때 다음 체크
- 변경된 함수를 찾았는데 그 함수의 로직 자체가 이해가 안 된다 → REV-0011 디컴파일 코드가 이상할 때 어셈블리로 돌아가는 기준
- 패치 전 버전에서 실제로 취약점을 트리거하는 입력을 만들어야 한다 → REV-0007 입력 함수부터 역추적하는 방법
- 정적으로 원인은 찾았는데 실제 크래시를 재현해서 검증하고 싶다 → REV-0005 문제를 정적 분석부터 할지 동적 분석부터 할지 결정하는 법

## 미니 예제
`libfoo_1.0.so`(패치 전), `libfoo_1.1.so`(패치 후) 두 파일이 주어졌다고 하자.

1. `diff <(strings libfoo_1.0.so) <(strings libfoo_1.1.so)` → `1.1`에만 있는 문자열 `"buffer too long"` 발견.
2. 두 파일을 IDA로 열어 각각 분석 후 저장, BinDiff 실행.
3. Similarity 오름차순 정렬 → `parse_request` 함수가 0.62로 가장 낮게 나옴.
4. 그래프 비교 뷰에서 `parse_request`에 새 베이직 블록(초록색 강조)이 추가된 것을 확인 → `if (len > 256) return -1;` 형태의 조건문이 새로 삽입됨.
5. 결론: 패치 전 `libfoo_1.0.so`의 `parse_request`는 길이 체크 없이 고정 크기 버퍼에 복사했을 가능성이 높음 → 이 지점을 스택/힙 버퍼 오버플로우 후보로 확정하고 다음 분석(동적 검증)으로 넘어간다.

## 관련 글
- REV-0011 — 디컴파일 코드가 이상할 때 어셈블리로 돌아가는 기준
- REV-0007 — 입력 함수부터 역추적하는 방법
- REV-0005 — 문제를 정적 분석부터 할지 동적 분석부터 할지 결정하는 법

## 출처/검증
- BinDiff 매칭 알고리즘(그래프/콜그래프 기반 유사도): zynamics/Google BinDiff 공식 문서 기준.
- Diaphora 동작 방식(SQLite export 후 비교): Diaphora 공식 GitHub 저장소 문서 기준.
- n-day 패치 diffing을 통한 취약점 추론 관행: 다수의 공개 보안 리서치/CTF writeup 요약 (2026-09-09 검증).
