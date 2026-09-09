---
id: REV-0744
title: "Ghidra Version Tracking으로 두 바이너리 비교하기"
slug: "rev-0744-ghidra-version-tracking-binary-diff"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Version Tracking", "Ghidra VT Session", "Ghidra 바이너리 비교", "Ghidra correlator", "Ghidra 패치 비교"]
aliases: ["Ghidra 버전 비교", "Ghidra BinDiff 대체", "Ghidra 패치 전후 비교"]
symptom_keywords: ["Ghidra로 패치 전후 바이너리 비교하는 법", "Ghidra Version Tracking 여는 법", "두 바이너리 함수 매칭", "Ghidra에서 BinDiff 같은 기능"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Version Tracking은 서로 다른 버전(패치 전/후, 다른 컴파일 옵션, 다른 라이브러리 버전)의 두 바이너리를 놓고 이미 분석한 쪽(Source)의 함수 이름·타입·코멘트를 아직 분석 안 한 쪽(Destination)에 자동으로 옮겨 붙여주는, Ghidra 내장 무료 오프라인 BinDiff 대체 기능이다.

## 언제 검색해야 하나
- 패치된 바이너리 두 개를 받았는데 함수가 너무 많아 눈으로 diff하기 어려울 때
- 이미 분석해 둔 비슷한 바이너리가 있는데 새 바이너리에 이름을 다시 붙이기 귀찮을 때
- 같은 라이브러리의 다른 버전을 나란히 비교해 함수 시그니처 차이를 직접 확인하고 싶을 때
- strip된 바이너리와 심볼 있는 참조 바이너리를 매칭시켜 이름을 대량으로 옮기고 싶을 때

## 핵심 개념

### Version Tracking이 하는 일
서로 다른 버전의 두 바이너리를 두고, 이미 분석/이름 붙인 쪽(Source Program)의 함수 이름·타입·코멘트를 아직 분석 안 한 쪽(Destination Program)에 자동으로 옮겨 붙인다. 상용 BinDiff와 비슷한 역할을 Ghidra 안에서 무료로, 완전히 오프라인으로 수행한다.

### 세션 만들기
Version Tracking 세션은 CodeBrowser가 아니라 Ghidra Project Window에서 시작한다. 두 바이너리를 각각 Import File로 프로젝트에 추가하고 Auto-Analysis를 완료한 뒤, Project Window에서 두 프로그램을 함께 선택 → 우클릭 → Version Tracking(또는 File → New → Version Tracking Session)으로 Source Program과 Destination Program을 각각 지정한다.

### Correlator(매칭 알고리즘)
세션 생성 마법사에서 어떤 correlator를 돌릴지 고를 수 있다.
- Exact Match: 바이트/심볼 단위 완전 일치
- Symbol Name correlator: 같은 이름이 이미 있는 경우
- Function Hash correlator: 구조적 유사도 기반
- Data Reference / Function Reference correlator: 주변 참조 관계로 매칭

여러 correlator를 순서대로 돌리면, 먼저 확실한 매칭(Exact)부터 잡고 남은 애매한 함수를 유사도 기반 correlator로 좁혀가는 식으로 전체 매칭률을 높일 수 있다.

### Version Tracking 창 구성
매칭 결과는 Version Tracking 창에 표 형태로 나온다: Source 함수, Destination 함수, 매칭 스코어(Similarity/Confidence), 상태(Accepted/Rejected/미결정). 함수 쌍을 선택하면 하단에 두 함수의 Listing/Decompile이 나란히 보여, 실제로 같은 로직인지 눈으로 비교할 수 있다.

### 마크업 적용(Apply Markup)
매칭이 맞다고 판단되면 그 행을 선택하고 Apply Markup을 눌러, Source 쪽 함수 이름/시그니처/코멘트를 Destination 쪽에 실제로 복사해 붙인다. 잘못된 매칭은 Reject로 표시해 다음 라운드에서 제외한다.

### CTF/리버싱에서의 활용
- 패치 전/후 바이너리 비교: 어느 함수가 바뀌었는지, 새로 추가된 함수는 무엇인지 낮은 매칭 스코어로 빠르게 좁힌다.
- 같은 라이브러리의 다른 버전 비교: REV-0648에서 다룬 함수 시그니처 차이를 실제로 나란히 보면서 확인한다.
- strip된 바이너리 vs 심볼 있는 참조 바이너리: 이미 분석해 둔 참조 바이너리를 Source로, 대상 바이너리를 Destination으로 삼아 이름을 대량으로 옮겨오는 REV-0741의 오프라인 대안 중 하나로도 쓸 수 있다.

## 화면/코드에서 보이는 징후
패치된 바이너리 두 개를 받았는데 어디가 바뀌었는지 눈으로 diff하기엔 함수가 너무 많거나, 이미 분석해 둔 비슷한 바이너리가 있는데 새 바이너리에 이름을 다시 붙이기 귀찮을 때.

## 가장 먼저 할 것
두 바이너리를 각각 Ghidra 프로젝트에 임포트하고 Auto-Analysis를 먼저 끝낸 뒤(둘 다 분석 완료 상태여야 Version Tracking이 제대로 동작한다), Project Window에서 두 프로그램을 함께 선택해 Version Tracking 세션을 만든다.

## 단계별 절차
1. 두 바이너리를 각각 Import File로 프로젝트에 추가, Auto-Analysis 완료
2. Project Window에서 두 프로그램 선택 → 우클릭 → Version Tracking → New Session
3. Source Program(분석 잘 된 쪽/이전 버전), Destination Program(대상/새 버전) 지정
4. 마법사에서 correlator 선택(우선 Exact Match류부터), Finish로 세션 생성
5. Version Tracking 창에서 매칭 결과 검토, 스코어 높은 것부터 Apply Markup
6. 애매한 매칭은 Listing/Decompile 나란히 보기로 직접 확인 후 Accept/Reject
7. 남은 미매칭 함수에 대해 다른 correlator(Function Hash 등)를 추가로 실행해 반복

## 명령어/단축키
- Project Window → File → New → Version Tracking Session
- Version Tracking 창의 Apply Markup 버튼
- 창 툴바의 correlator 추가 실행 버튼

## 출력 해석
스코어(Similarity/Confidence)가 1.0에 가까우면 사실상 동일 함수, 낮으면(0.5 근처 등) 이름은 비슷해도 내부 로직이 바뀌었을 가능성이 있으므로 Decompile 비교 창에서 실제 차이를 눈으로 확인해야 한다.

## 흔한 실수
- 두 바이너리 중 하나를 Auto-Analysis 없이 그대로 세션에 넣어 매칭이 거의 안 되는 것.
- 스코어만 보고 기계적으로 전부 Apply Markup 눌러버려 잘못된 이름이 옮겨붙는 것.
- Source와 Destination을 반대로 지정해 이미 이름이 있는 쪽이 오히려 덮어써지는 것.

## 막혔을 때 다음 체크
- 매칭 자체가 왜 필요한지(오프라인 시그니처 대안) 궁금하면 → REV-0741 IDA Lumina 없이 오프라인 환경에서의 대안 찾기
- glibc 버전 차이로 인한 시그니처 변화가 궁금하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법
- 반복되는 매칭/적용 작업을 스크립트로 자동화하고 싶으면 → REV-0743 Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초
- 정적 링킹 바이너리를 비교 대상으로 쓰는 배경이 궁금하면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```text
Source Program: chall_v1 (이미 분석 완료, check_flag 등 이름 붙어 있음)
Destination Program: chall_v2 (패치된 새 버전, 함수 대부분 FUN_ 상태)

Exact Match correlator 실행 -> 90% 함수가 바로 매칭(스코어 1.0)
남은 10% 중 하나: check_flag_v1(스코어 0.62) <-> FUN_00401800
Decompile 비교 창에서 로직 확인 -> 상수 값 하나만 바뀐 동일 로직 확인
-> Accept 후 Apply Markup으로 이름/코멘트 복사
```

## 관련 글
- REV-0741 — IDA Lumina 없이 오프라인 환경에서의 대안 찾기
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0743 — Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법

## 출처/검증
Ghidra 공식 Help 문서(Version Tracking, Correlators, Apply Markup 관련 topic) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며 공식 문서 기준 메뉴 경로로 작성했다(2026-09-09).
