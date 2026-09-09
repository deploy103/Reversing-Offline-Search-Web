---
id: REV-0768
title: "IDA/Ghidra 분석 결과를 버전별로 비교 관리하는 법"
slug: "rev-0768-ida-ghidra-version-diff-management"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["BinDiff", "Ghidra Version Tracking", "패치 바이너리 비교", "idb 백업", "GDT 아카이브 export", "분석 결과 재사용"]
aliases: ["바이너리 패치 diff 분석", "재분석 시 이름 재사용", "IDA Ghidra 분석 결과 이전"]
symptom_keywords: ["같은 바이너리 신버전이 나와서 처음부터 다시 분석해야 함", "패치 전후 뭐가 바뀌었는지 모르겠음", "분석 결과를 다른 바이너리에 재사용하고 싶음", "idb 파일이 여러 개 생겨서 헷갈림"]
source_ids: ["SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
같은 프로그램의 여러 버전(패치 전/후, 문제 배포 파일이 중간에 갱신된 경우 등)을 분석할 때는, 이름/주석/타입을 처음부터 다시 붙이는 대신 이전 분석 결과가 담긴 IDA `.i64`/Ghidra 프로젝트를 기준으로 **바이트/구조 유사도 기반 자동 대응(BinDiff, Ghidra Version Tracking)** 또는 **타입 라이브러리(.til/.gdt) 재사용**으로 기존 작업을 새 버전에 이전할 수 있다.

## 언제 검색해야 하나
- CTF 문제 파일이 대회 중간에 패치되어 새 바이너리가 배포됐는데, 이전에 분석하며 붙인 함수 이름/주석을 다시 쓰고 싶을 때
- 같은 시리즈의 여러 문제(예: 난이도별 crackme 1, 2, 3)가 같은 라이브러리 코드를 공유하고 있어서 한 번 분석한 결과를 재사용하고 싶을 때
- IDA/Ghidra가 크래시하거나 실수로 데이터베이스를 잘못 저장해서, 이전 백업본과 현재 상태를 비교해 무엇이 달라졌는지 확인하고 싶을 때
- 오프라인 환경이라 IDA Lumina(온라인 시그니처 공유 서비스)를 쓸 수 없어서, 로컬에서만 분석 결과를 이전할 방법이 필요할 때

## 핵심 개념

### 무엇을 "이전"할 것인가
버전 간 분석 결과에서 재사용 가치가 있는 것은 크게 세 가지다.

1. **이름(Symbol)**: 함수명, 변수명, 구조체 멤버명
2. **타입(Type)**: 사용자 정의 구조체, 함수 시그니처
3. **주석/코멘트**: 분석하며 남긴 설명, 특히 REV-0770 방식 노트의 요약

이 중 이름과 타입은 도구가 제공하는 아카이브 형식(IDA `.til`, Ghidra `.gdt`)으로 export/import가 가능하고, 함수별 대응(어떤 옛 함수가 새 바이너리의 어떤 함수와 같은가)은 바이트 유사도 기반 도구가 자동으로 찾아준다.

### IDA — BinDiff를 이용한 함수 대응
Zynamic에서 만들고 현재 Google이 공개 배포하는 **BinDiff**는 두 개의 IDA 데이터베이스(`.i64`)를 비교해 동일하거나 유사한 함수를 그래프 구조/호출 관계/상수 기반으로 자동 매칭한다. 매칭된 함수 쌍에 대해 "이전 버전에서 붙인 이름을 새 버전으로 포팅"하는 기능을 제공하며, 매칭 신뢰도(similarity, confidence 점수)를 함께 보여준다. 오프라인 설치 파일을 미리 받아두면 인터넷 없이도 로컬 비교가 가능하다.

### IDA — 타입 라이브러리(.til)와 IDC/Python 스크립트 export
BinDiff가 없다면, 더 단순한 방법으로 `File → Produce file → Dump database to IDC file` 또는 Python 스크립트(`idautils`/`idaapi`)로 "주소 → 이름" 매핑을 텍스트로 뽑아 저장해둘 수 있다. 새 버전을 열 때 이 텍스트를 참고해 (자동은 아니지만) 대응되는 함수에 수동으로 같은 이름을 다시 붙이는 방식이다. 느리지만 BinDiff 없이도 항상 쓸 수 있는 방법이다.

### Ghidra — Version Tracking 도구
Ghidra는 자체적으로 **Version Tracking** 기능을 내장하고 있다. 두 개의 Ghidra 프로그램(같은 바이너리의 다른 버전)을 놓고 바이트 일치, 함수 해시, 심볼 유사도 등 여러 상관 관계(correlator)를 적용해 매칭 후보를 만들고, 분석가가 확인(accept)하면 이름/주석/데이터 타입이 새 버전으로 그대로 마크업(markup)된다. `Version Tracking` 도구 창(`Tools → Version Tracking` 또는 별도 실행)에서 "Existing Program" ↔ "New Program"을 지정해 세션을 만든다.

### Ghidra — Data Type Archive(.gdt)와 심볼 export
Version Tracking 없이 간단히 타입만 재사용하려면, `File → Export → Data Type Archive`로 현재 프로젝트에서 정의한 구조체/typedef를 `.gdt` 파일로 저장하고, 새 프로젝트에서 `File → Parse C Source` 대신 `Data Type Manager` 우클릭 → `Open File Archive`로 불러와 그대로 적용할 수 있다.

### 오프라인/저사양 환경을 위한 대체 방법
BinDiff/Version Tracking 같은 도구가 설치되어 있지 않거나 CTF 대회 환경 특성상 설치할 수 없다면, REV-0770에서 다루는 "주소 기반 평문 노트"만으로도 최소한의 버전 관리가 가능하다. 노트에 반드시 함수의 **오프셋(파일 오프셋 또는 이미지 베이스 기준 RVA, 절대 가상 주소가 아님)**을 함께 적어두면, ASLR/재배치 없이 재컴파일된 새 버전에서도 같은 오프셋을 검색해 빠르게 대응 함수를 찾을 수 있다.

## 화면/코드에서 보이는 징후
- 문제 배포 파일이 `chall_v1`, `chall_v2`처럼 버전이 나뉘어 있거나, 같은 파일명인데 해시값(파일 크기/타임스탬프)이 달라졌다.
- 이전에 분석하며 이름 붙인 함수들이 새 파일에서는 전부 `sub_`/`FUN_`로 되돌아가 있다(당연히 새 데이터베이스이므로).
- 두 버전의 파일 크기 차이가 작아서(수 바이트~수십 바이트) 일부 함수만 패치된 것으로 추정될 때.

## 가장 먼저 할 것
새 버전을 분석하기 전에, 이전 버전의 `.i64`/Ghidra 프로젝트 파일을 안전한 곳에 백업부터 해둔다(덮어쓰기 방지). 그다음 BinDiff/Version Tracking이 설치되어 있는지 확인하고, 없다면 처음부터 REV-0770 방식으로 주소 기반 노트를 남기며 분석해 향후 버전 비교에 대비한다.

## 단계별 절차
1. 이전 버전 분석 데이터베이스(`.i64`, Ghidra 프로젝트)를 백업한다.
2. 새 버전 바이너리를 별도의 새 데이터베이스로 연다(기존 데이터베이스를 새 파일에 덮어씌우지 않는다).
3. **IDA**: BinDiff가 설치되어 있다면 두 `.i64`를 비교(`File → BinDiff → Diff Database` 등, 버전별 메뉴 위치 상이)해 매칭된 함수의 이름을 포팅한다.
4. **Ghidra**: `Version Tracking` 도구에서 기존 프로그램과 새 프로그램을 지정해 세션을 만들고, correlator를 실행해 매칭 후보를 확인 후 마크업을 적용한다.
5. 자동 도구가 없다면, 이전 분석에서 뽑아둔 "주소 → 이름 → 요약" 텍스트를 참고해 새 버전에서 같은 코드 패턴(REV-0163/0165 방식의 상수/문자열 단서)을 검색해 수동으로 이름을 다시 붙인다.
6. 구조체/타입은 `.til`/`.gdt` export-import로 재사용해 처음부터 다시 정의하는 시간을 아낀다.
7. 매칭이 안 된(새로 추가되거나 크게 변경된) 함수만 표시해 그 부분에 분석 시간을 집중한다 — 이것이 버전 비교의 가장 큰 실익이다.

## 명령어/단축키
- IDA: 데이터베이스 덤프 `File → Produce file → Dump database to IDC file`, 타입 라이브러리 export/import는 `File → Load file → Type libraries`/Local Types 창 내 export
- Ghidra: `File → Export Program`(Data Type Archive 포함 옵션), `Tools → Version Tracking`(버전에 따라 메뉴 경로 다를 수 있음), Data Type Manager 우클릭 `Open File Archive`
- 공통: 바이너리 자체의 해시(`sha256sum`)를 노트에 남겨 어떤 분석 결과가 어떤 정확한 파일 버전에 대응하는지 혼동하지 않도록 한다

## 출력 해석
- BinDiff/Version Tracking의 유사도 점수가 매우 높으면(예: 1.0 또는 그에 가까움) 함수가 바이트 단위로 거의 동일하다는 뜻이므로 이름을 그대로 신뢰하고 포팅해도 된다.
- 유사도가 중간 정도면 함수 내부 로직 일부가 바뀌었을 가능성이 크므로, 이름은 참고만 하고 내부를 다시 읽어야 한다.
- 매칭되지 않은 함수(새 버전에만 존재)는 패치로 새로 추가된 코드일 가능성이 크므로 우선 분석 대상으로 삼는다.

## 흔한 실수
- 이전 데이터베이스 파일을 새 바이너리에 그대로 열려고 시도하는 것 — IDA/Ghidra 데이터베이스는 원본 바이너리의 바이트와 강하게 결합되어 있어, 바이트가 달라지면 파일 오프셋 기반 매핑이 깨질 수 있다. 반드시 새 데이터베이스를 만들고 도구를 이용해 "매칭"해야 한다.
- 유사도 점수를 확인하지 않고 자동 매칭 결과를 100% 신뢰해 이름을 그대로 포팅하는 것 — 특히 짧고 정형화된 함수(REV-0762의 가드 함수 등)는 서로 다른 함수인데도 유사도가 높게 나올 수 있다.
- 백업 없이 기존 데이터베이스를 열어 작업하다가 실수로 저장해 이전 분석 상태를 잃어버리는 것.
- 버전 비교 도구를 설치할 수 없는 오프라인 환경인데도 이 문서의 자동화 도구만 고집하다가 시간을 낭비하는 것 — 이런 환경에서는 REV-0770의 평문 노트 방식이 가장 현실적인 대안이다.

## 막혔을 때 다음 체크
- 애초에 여러 함수를 어떻게 노트로 정리해야 할지 형식이 필요하다면 → REV-0770(여러 함수에 걸친 로직을 하나의 흐름으로 정리하는 노트 작성법)
- Ghidra 프로젝트를 처음 만들고 바이너리를 Import하는 기본 절차가 필요하다면 → REV-0156(Ghidra 프로젝트 생성과 바이너리 Import)
- 함수/변수 이름을 붙이는 기본 조작법이 필요하다면 → REV-0147(IDA 함수 변수 이름 N으로 바꾸기), REV-0161(Ghidra Rename과 Data Type 수정)
- 전체 분석 절차에서 이 단계가 어디쯤 위치하는지 궁금하다면 → REV-0767(정적분석만으로 Flag 검증 로직을 완전히 복원하는 절차)

## 미니 예제
CTF 대회 중간에 `service_v1`이 `service_v2`로 패치되어 재배포됐다고 하자.

1. `sha256sum service_v1 service_v2`로 두 파일이 실제로 다르다는 것을 먼저 확인한다.
2. `service_v1.i64`(이전 분석 결과)를 백업한 뒤, `service_v2`를 새 IDA 데이터베이스로 연다.
3. BinDiff로 두 데이터베이스를 비교하니 함수 200개 중 197개가 유사도 1.0으로 매칭되고, 3개 함수만 매칭되지 않았다.
4. 매칭된 197개 함수는 이전에 붙인 이름(`check_password`, `read_input` 등)을 그대로 포팅한다.
5. 매칭되지 않은 3개 함수만 새로 분석하면, 전체를 처음부터 다시 볼 때보다 시간을 크게 절약하면서 "이번 패치에서 정확히 무엇이 바뀌었는가"까지 함께 알아낼 수 있다.

## 관련 글
- REV-0770 — 여러 함수에 걸친 로직을 하나의 흐름으로 정리하는 노트 작성법
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0147 — IDA 함수 변수 이름 N으로 바꾸기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0767 — 정적분석만으로 Flag 검증 로직을 완전히 복원하는 절차

## 출처/검증
- BinDiff의 기능(그래프/호출 관계 기반 함수 매칭, 유사도 점수, 이름 포팅)은 Google의 BinDiff 공식 문서 및 공개 저장소 설명 기준으로 정리했다.
- Ghidra Version Tracking 도구(correlator, 마크업 적용 절차)는 Ghidra 공식 Help 문서(Version Tracking 섹션) 기준.
- IDA 데이터베이스 덤프(IDC export), 타입 라이브러리(.til) 관리는 Hex-Rays 공식 문서(IDA User Guide) 기준.
- Ghidra Data Type Archive(.gdt) export/import는 Ghidra 공식 Help 문서(Data Type Manager 섹션) 기준.
