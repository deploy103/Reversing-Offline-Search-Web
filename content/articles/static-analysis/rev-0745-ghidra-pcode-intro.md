---
id: REV-0745
title: "Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)"
slug: "rev-0745-ghidra-pcode-intro"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra P-code", "Pcode", "SLEIGH", "Ghidra 중간 표현", "intermediate representation", "Varnode"]
aliases: ["Ghidra IR", "Ghidra 피코드", "SLEIGH 프로세서 스펙", "Ghidra Instruction Info"]
symptom_keywords: ["Ghidra P-code가 뭔가", "Ghidra 디컴파일러 원리", "왜 여러 아키텍처를 하나의 디컴파일러로 지원하나", "Ghidra 디컴파일 결과가 이상함 원인"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra는 x86, ARM, MIPS 등 수십 개의 서로 다른 아키텍처를 하나의 디컴파일러 엔진으로 지원하기 위해, 각 아키텍처의 실제 명령어를 먼저 공통된 저수준 연산 집합인 P-code로 변환하고 디컴파일러는 오직 이 P-code만 이해하도록 설계되어 있다.

## 언제 검색해야 하나
- Decompile 결과가 이상하게 나오는데 원인을 못 찾겠을 때
- Ghidra가 왜 하나의 디컴파일러로 여러 아키텍처를 지원할 수 있는지 궁금할 때
- Instruction Info 창에 나오는 알 수 없는 연산 이름(`COPY`, `CBRANCH`, `INT_ADD` 등)의 의미가 궁금할 때
- Ghidra 스크립트에서 저수준 데이터 흐름을 직접 다루고 싶을 때

## 핵심 개념

### 왜 중간 표현(IR)이 필요한가
Ghidra는 x86, ARM, MIPS, RISC-V 등 수십 개의 아키텍처를 단 하나의 디컴파일러 엔진으로 지원한다. 만약 각 아키텍처의 실제 기계어 명령을 디컴파일러가 직접 이해해야 한다면, 아키텍처마다 디컴파일러 로직을 전부 새로 짜야 한다. 이를 피하기 위해 Ghidra는 모든 아키텍처의 명령어를 공통된 저수준 연산 집합인 P-code로 먼저 변환하고, 디컴파일러는 오직 이 P-code만 이해하면 되도록 설계했다.

### SLEIGH - 명령어를 P-code로 바꾸는 규칙
각 아키텍처(프로세서)마다 `.slaspec`으로 작성된 SLEIGH 명세가 있으며, 이 파일이 "이 opcode 패턴을 만나면 이런 P-code 연산으로 바꿔라"는 규칙을 정의한다. 예를 들어 x86의 `ADD EAX, EBX` 한 줄은 내부적으로 `EAX = EAX + EBX` 연산과 함께 플래그(ZF, CF, OF 등)를 계산하는 여러 개의 P-code 연산으로 풀어 쓰여진다. 즉 어셈블리 한 줄이 P-code 여러 줄로 나뉘는 것이 일반적이다.

### Varnode - P-code의 기본 단위
P-code 연산은 Varnode(값이 저장된 위치 + 크기)를 피연산자로 갖는다. Varnode는 레지스터, 메모리 주소, 또는 상수를 가리킬 수 있다. 디컴파일러는 이 Varnode들이 어떻게 연결되는지(데이터 흐름)를 추적해서 최종적으로 C 코드 형태의 변수/표현식으로 재구성한다.

### P-code를 직접 보는 법
Listing 창에서 명령어 위에 커서를 놓고 우클릭 → Instruction Info를 열면 해당 명령어가 어떤 P-code 연산들로 분해되는지 목록으로 보여준다. 디컴파일 결과가 이상하게 나올 때 이 창에서 실제 P-code를 확인하면 왜 그렇게 렌더링됐는지 원인을 알 수 있는 경우가 많다.

### 리버서 입장에서 알아야 할 실익
- 디컴파일 결과가 이상하다면(예: 플래그 계산이 이상하게 보임, 조건문이 뒤집힌 것처럼 보임) 원인은 대개 P-code 레벨의 변환/최적화 단계에 있다. Instruction Info로 실제 P-code를 보면 Ghidra가 무엇을 "본" 것인지 알 수 있다.
- Ghidra 스크립트(REV-0743)에서 저수준 데이터 흐름 분석을 직접 하고 싶을 때 `PcodeOp`, `Varnode` 클래스를 사용한다.
- 잘 알려지지 않은 아키텍처(펌웨어 등)를 분석할 때, 그 아키텍처의 SLEIGH 스펙이 있는지 여부가 곧 Ghidra 지원 여부를 결정한다.

## 화면/코드에서 보이는 징후
Decompile 결과가 이상하게 나오는데 원인을 못 찾겠거나, Function Graph/Listing에서 명령어 수와 실제 로직이 안 맞아 보일 때.

## 가장 먼저 할 것
이상하게 디컴파일된 그 명령어 위에서 우클릭 → Instruction Info로 P-code부터 먼저 확인한다.

## 단계별 절차
1. 문제가 되는 명령어(주소) 찾기
2. Listing에서 그 줄 우클릭 → Instruction Info
3. 나열된 P-code 연산(`COPY`, `INT_ADD`, `CBRANCH`, `LOAD`, `STORE` 등)을 하나씩 읽으며 실제 어떤 Varnode를 다루는지 확인
4. 디컴파일 결과와 P-code를 대조해 어느 단계에서 예상과 달라졌는지 특정
5. 필요하면 REV-0743의 스크립트 API로 P-code를 순회하며 프로그램적으로 분석

## 명령어/단축키
- 명령어 우클릭 → Instruction Info(P-code 목록 표시)
- 고급: 커스텀 SLEIGH 스펙 작성 시 관련 프로세서 매니저 도구 사용

## 출력 해석
`CBRANCH`는 조건부 분기, `BRANCH`는 무조건 분기, `LOAD`/`STORE`는 메모리 읽기/쓰기, `INT_ADD`/`INT_SUB`/`INT_EQUAL` 등은 이름 그대로의 산술/비교 연산이다. 플래그 레지스터는 별도의 작은 Varnode(예: ZF, CF에 해당하는 임시 레지스터)로 계산되어 이후 `CBRANCH`의 조건으로 쓰인다.

## 흔한 실수
- P-code를 어셈블리와 1:1로 대응한다고 착각하는 것 — 실제로는 한 명령어가 여러 P-code로 풀린다.
- P-code 레벨의 문제를 디컴파일러 버그로 단정하고 더 깊이 확인하지 않는 것.
- 비표준 아키텍처에서 SLEIGH 스펙 자체를 수정해야 하는 상황임을 모르고 헤매는 것.

## 막혔을 때 다음 체크
- Decompile 창 자체 읽는 법이 기억 안 나면 → REV-0158 Ghidra Decompiler 창 읽기
- Function Graph에서 CBRANCH가 실제로 어떻게 분기로 그려지는지 보고 싶으면 → REV-0746 Ghidra Function Graph로 제어 흐름 보기
- P-code를 스크립트로 다루고 싶으면 → REV-0743 Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초

## 미니 예제
```text
어셈블리: ADD EAX, EBX

Instruction Info에서 보이는 P-code(개념적 예시):
  $U100 = INT_ADD EAX, EBX
  EAX = $U100
  ZF = INT_EQUAL $U100, 0x0
  CF = INT_CARRY EAX, EBX
  OF = INT_SCARRY EAX, EBX

-> 한 줄의 ADD가 값 계산 1개 + 플래그 계산 3개, 총 4~5개의 P-code로 풀린다.
```

## 관련 글
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0746 — Ghidra Function Graph로 제어 흐름 보기
- REV-0743 — Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초

## 출처/검증
Ghidra 공식 문서(P-code Reference Manual, SLEIGH 관련 topic) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 예제의 구체적 P-code 연산 이름은 공식 문서의 opcode 목록을 기준으로 한 개념 설명용 예시다(2026-09-09).
