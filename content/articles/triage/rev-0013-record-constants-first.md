---
id: REV-0013
title: "문제에서 주어진 상수와 문자열을 먼저 기록해야 하는 이유"
slug: "rev-0013-record-constants-first"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: [상수 기록, 매직넘버 기록, 문자열 기록, 노트 작성, 반복 방지, 상수 정리]
aliases: ["상수 적어두기", "매직넘버 정리", "값 기록하기", "왜 값을 적어야 하나"]
symptom_keywords: ["같은 값을 또 찾고 있음", "이 상수 어디서 봤는데 기억이 안 남", "값을 또 확인하러 감", "어디서 봤는지 기억이 안 남"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이너리에서 나오는 상수(비교값, 배열, XOR 키)와 문자열을 발견 즉시 노트에 주소와 함께 적어두지 않으면, 나중에 솔버를 짤 때 같은 곳을 다시 찾아 헤매거나 값을 잘못 옮겨 적어 몇 시간을 날릴 수 있다.

## 언제 검색해야 하나
- "이 숫자 아까 어디서 봤는데..."라며 이미 봤던 상수를 다시 찾으러 IDA를 뒤지고 있을 때
- 솔버 스크립트를 짜다가 상수 값이 기억이 안 나서 다시 바이너리를 열어야 할 때
- 여러 개의 배열/상수가 나오는 문제에서 어떤 게 어떤 용도였는지 헷갈릴 때

## 핵심 개념
리버싱은 짧으면 몇 분, 길면 며칠씩 걸리는 작업이다. 그 사이에 사람의 기억은 생각보다 빨리 사라진다. 특히 다음과 같은 정보는 **발견한 순간이 가장 정확하게 기록할 수 있는 시점**이고, 나중에 다시 찾으려면 처음 찾을 때보다 훨씬 오래 걸린다.

- **비교 상수**: `if (v1 == 0x1A2B)`에서 `0x1A2B`.
- **배열/버퍼 초기값**: `key[16] = {0x12, 0x34, ...}` 같은 XOR 키, 룩업 테이블.
- **문자열 리터럴**: 정답 후보, 포맷 문자열, 에러 메시지.
- **주소**: 이 상수가 어느 함수, 어느 주소에 있었는지(다시 찾을 때 필요).
- **가설**: "이 함수는 아마 체크섬 계산인 것 같다" 같은 그 순간의 직관.

기록을 안 하면 벌어지는 전형적인 문제:
1. 같은 배열을 두 번 다른 값으로 옮겨 적어서 나중에 어느 게 맞는지 헷갈린다(오타로 인한 디버깅 지옥).
2. 솔버 스크립트(Python 등)를 짜는 도중 상수가 필요한데 기억이 안 나서 IDA를 다시 열고, 어디서 봤는지부터 다시 찾아야 한다.
3. 여러 함수를 왔다갔다 분석하다 보면 "아까 그 상수, 이 함수 상수랑 같은 건가 다른 건가"를 확신할 수 없게 된다.

리버싱에서 상수를 정확하게, 발견 즉시 기록하는 습관은 사소해 보이지만 실제 CTF 풀이 시간의 상당 부분을 절약해준다. 특히 배열처럼 손으로 옮겨 적어야 하는 데이터는 **눈으로 보고 타이핑하지 말고 도구로 그대로 추출**하는 게 오타를 막는 핵심이다.

## 화면/코드에서 보이는 징후
- 디컴파일 코드에 `unsigned char key[] = { 0x3A, 0x1F, 0x22, ... }`처럼 배열이 나열되어 있다.
- `.rodata`/`.rdata` 섹션에 원시 바이트 배열이 있고 IDA가 이를 자동으로 문자열이나 배열로 인식하지 못해 `db 3Ah, 1Fh, 22h ...`처럼 나열된 형태로 보인다.
- 같은 함수를 두 번째 방문했는데 "이 상수 처음 보는 건가 아까 봤던 건가" 헷갈리는 느낌이 든다면 이미 기록이 필요했던 시점이다.

## 가장 먼저 할 것
비교 상수나 배열을 발견하면, 바로 다음 분석으로 넘어가기 전에 **주소 + 값 + 용도 추정**을 한 줄이라도 노트에 적는다. 텍스트 파일(`notes.md`)이나 IDA 자체의 주석 기능(단축키 `:`)을 활용한다.

## 단계별 절차

**1) IDA/Ghidra 주석으로 즉시 기록**
- IDA: 값이 있는 줄에 커서를 놓고 **콜론(`:`)** 키를 누르면 그 줄에 대한 주석(comment)을 입력할 수 있다. 예: `key XOR value, used in check_flag+0x20`.
- 함수 전체에 대한 요약은 함수 시작 줄에서 **콜론** 또는 함수 목록에서 우클릭 → `Add comment`.
- Ghidra: 해당 줄 우클릭 → `Comments → Set EOL Comment`(단축키 `;`) 또는 `Set Plate Comment`(함수 전체 요약용, 단축키 없으면 메뉴 사용).

**2) 배열/버퍼는 손으로 옮기지 말고 그대로 추출**
- IDA 디스어셈블리 뷰에서 배열 데이터 영역을 드래그로 선택 → 우클릭 → `Export data`(또는 `Edit → Export data`) 로 헥스 덤프를 파일로 저장할 수 있다.
- 더 간단한 방법: 동적 분석 중이라면 x64dbg/GDB에서 해당 메모리를 덤프한다.
  - GDB: `dump binary memory key_dump.bin 0x<시작주소> 0x<끝주소>`
  - x64dbg: 메모리 뷰에서 범위 선택 → 우클릭 → `Binary → Save To a File`
- 이렇게 저장한 바이너리 덤프를 Python에서 바로 읽으면(`open('key_dump.bin', 'rb').read()`) 손으로 옮겨 적다가 생기는 오타를 원천 차단할 수 있다.

**3) 외부 노트 파일에 구조적으로 정리**
IDA 주석은 나중에 다시 찾기 편하지만, 전체 그림을 한눈에 보려면 별도 텍스트 노트가 필요하다. 다음과 같은 형식을 권장한다.
```
[상수] key_arr @ 0x402010 (16 bytes)
  12 34 56 78 9A BC DE F0 11 22 33 44 55 66 77 88
  용도: input과 XOR되는 것으로 추정 (check_flag+0x30에서 사용)

[상수] MAGIC @ check_flag+0x55
  0x1A2B3C4D
  용도: 최종 비교값
```
이 형식은 [rev-0014-reversing-notes.md](./rev-0014-reversing-notes.md)에서 더 자세히 다룬다.

**4) 발견 즉시 vs 나중 정리 — 발견 즉시를 원칙으로**
"나중에 한꺼번에 정리해야지"라고 미루면 십중팔구 잊어버리거나 순서가 꼬인다. 상수를 본 그 자리에서 최소 한 줄이라도 즉시 적는 습관이 가장 중요하다.

## 명령어/단축키
- IDA: `:`(주석 추가), `N`(이름 바꾸기), 데이터 선택 후 우클릭 `Export data`
- Ghidra: 우클릭 `Comments → Set EOL Comment` / `Set Plate Comment`
- GDB: `dump binary memory <파일명> <시작주소> <끝주소>`, `x/16xb <주소>`(16바이트를 16진수로 출력)
- x64dbg: 메모리 뷰 우클릭 → `Binary → Save To a File`

## 출력 해석
- GDB `x/16xb 0x404020` 출력 예시: `0x404020: 0x12 0x34 0x56 0x78 ...` — 이 값을 그대로 Python 리스트로 옮기면 안전하다(복사-붙여넣기 후 정규식으로 정리하는 것을 권장, 손으로 타이핑하지 않는다).
- `dump binary memory`로 저장한 파일은 `xxd 파일명`(Linux)으로 다시 확인 가능.

## 흔한 실수
- 상수를 화면으로만 보고 정신적으로 기억하려다가 다음 날(또는 몇 시간 뒤) 다시 찾는 것.
- 배열을 손으로 옮겨 적으면서 자릿수를 하나 빠뜨리거나 순서를 바꿔 적는 것 — 이런 오타는 발견하기 매우 어렵고, 나중에 솔버가 안 돌아가는 원인을 다른 데서 찾느라 시간을 낭비하게 만든다.
- 여러 상수를 같은 이름 없이 "그 값"이라고만 기억해서 나중에 서로 헷갈리는 것 — 반드시 발견한 주소나 함수명을 같이 적는다.
- IDA를 닫으면 세션이 끝난다고 착각해서 주석을 안 남기는 것 — IDA는 데이터베이스(.idb/.i64) 파일에 주석이 저장되므로 다시 열면 그대로 남아있다.

## 막혔을 때 다음 체크
- 상수를 어떻게 노트에 구조적으로 정리할지 모르겠다 → [rev-0014-reversing-notes.md](./rev-0014-reversing-notes.md)
- 이 상수로 로직을 어떻게 복원할지 모르겠다 → [rev-0017-recover-logic-before-solver.md](./rev-0017-recover-logic-before-solver.md)
- 검증 함수 자체를 아직 못 찾았다 → [rev-0006-finding-check-function.md](./rev-0006-finding-check-function.md)

## 미니 예제
디컴파일 코드에서 다음을 발견했다고 하자.
```c
unsigned char key[8] = {0x1, 0x3, 0x3, 0x7, 0xC, 0xA, 0xF, 0xE};
for (int i = 0; i < 8; i++)
    input[i] ^= key[i];
if (memcmp(input, target, 8) == 0)
    puts("Correct!");
```
이 시점에서 바로 노트에 다음을 적는다.
```
[상수] key[8] @ check_flag+0x10
  01 03 03 07 0C 0A 0F 0E
  용도: input을 인덱스별로 XOR

[상수] target @ check_flag+0x40 (memcmp 대상, 8 bytes)
  값 확인 필요 - 다음 단계에서 추출
```
`target` 배열도 같은 방식으로 즉시 추출해서 적어두면, 이후 Python으로 `bytes(a ^ b for a, b in zip(target, key))`처럼 바로 역산할 수 있다.

## 관련 글
- [rev-0014-reversing-notes.md](./rev-0014-reversing-notes.md)
- [rev-0006-finding-check-function.md](./rev-0006-finding-check-function.md)
- [rev-0017-recover-logic-before-solver.md](./rev-0017-recover-logic-before-solver.md)
- [rev-0012-hints-from-problem.md](./rev-0012-hints-from-problem.md)

## 출처/검증
- IDA 주석/데이터 export 기능: Hex-Rays 공식 문서 기준.
- GDB `dump binary memory` 명령: GDB 공식 매뉴얼(sourceware.org gdb documentation) 기준 (2026-09-08 검증).
