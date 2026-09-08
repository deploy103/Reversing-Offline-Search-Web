---
id: REV-0056
title: "OR: 비트 설정"
slug: "rev-0056-or"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - or
  - OR
  - Or
  - or 명령어
  - or instruction
  - "or eax, eax"
  - "or eax, -1"
  - bitwise or
  - 비트 OR
  - 비트 설정
  - set bit
  - 플래그 비트 설정
  - bitfield
  - 비트필드 조합
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - or 뭐임
  - or이 뭐죠
  - or 명령
  - OR 명령어
  - 오어 명령어
  - or eax eax 왜함
symptom_keywords:
  - or eax eax가 왜 나오는지 모르겠음
  - or 명령이 비트를 왜 켜는지 모르겠음
  - or -1이 왜 나오는지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`OR`는 두 오퍼랜드를 비트 단위로 OR 연산해서 목적지에 저장하는 명령어로, "특정 비트를 강제로 1(켜기)로 만드는" 데 쓰인다 — AND(비트 제거)의 정반대 역할이다.

## 언제 검색해야 하나
- `or eax, 4` 처럼 특정 비트를 켜는 코드를 만났을 때
- `or eax, eax` 를 만났는데 값이 안 바뀌는 것 같아서 왜 있는지 모를 때
- `or eax, -1` (또는 `or eax, 0FFFFFFFFh`)처럼 값을 전부 1로 채우는 코드를 만났을 때
- 플래그/옵션 비트를 조합하는 코드(`flags | OPTION_A | OPTION_B`)를 분석할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
OR dest, src
```
- `dest = dest OR src`, 결과는 dest에 저장.
- `dest`는 레지스터/메모리, `src`는 레지스터/메모리/즉시값. 메모리-메모리 조합은 불가.
- 예: `or eax, ebx`, `or eax, 4`, `or dword ptr [rbp-4], 1`.

### 레지스터/메모리에 미치는 효과
비트별로 둘 중 하나라도 1이면 결과가 1, 둘 다 0일 때만 결과가 0이다.
```
  1010 0000
OR  0000 0100
= 1010 0100
```
`src`의 비트가 1인 자리는 결과가 무조건 1이 되고(원래 dest 값과 무관하게 "켜짐"), `src`의 비트가 0인 자리는 dest의 원래 값이 그대로 유지된다. 즉 OR는 "특정 비트를 강제로 켜고, 나머지는 건드리지 않는" 연산이다.

### 플래그 변화
- **ZF**: 결과가 0이면 1
- **SF**: 결과의 최상위 비트(부호 비트)가 1이면 1
- **PF**: 결과 하위 1바이트의 1비트 개수가 짝수면 1
- **CF = 0**, **OF = 0** (항상 무조건 클리어)
- **AF**: 정의되지 않음

### 신호 있음/없음(signed/unsigned) 관점
OR도 AND처럼 순수 비트 연산이라 부호 개념이 없다. 다만 최상위 비트(부호 비트)를 OR로 켜면 값이 음수로 바뀔 수 있다. 예: `eax = 0x00000005`에 `or eax, 80000000h`를 하면 `0x80000005`가 되어 부호 있는 해석으로는 음수가 된다.

### 스택/RSP/RIP 변화
없음. OR는 스택이나 명령어 포인터를 건드리지 않는다.

### `or eax, eax` — 옛 스타일 제로 체크
`or eax, eax`는 자기 자신과 OR하는 것이므로 값 자체는 절대 바뀌지 않지만, **ZF/SF가 eax의 값에 따라 세팅되는 부수효과**를 이용해 "eax가 0인가?"를 검사하는 용도로 쓰인다. 오늘날 컴파일러는 거의 항상 [`test eax, eax`](rev-0059-test.md)를 대신 쓰지만(같은 인코딩 크기), 손으로 쓴 어셈블리나 오래된 MASM/16비트 시절 코드, 일부 컴파일러 최적화 패스에서는 `or eax, eax`가 여전히 등장한다. 의미상 `test eax, eax`와 동일한 목적(제로 체크)이라고 이해하면 된다.

### `or reg, -1` — 전부 1로 채우기
`or eax, -1`(즉 `or eax, 0FFFFFFFFh`)은 원래 값과 상관없이 결과를 항상 `0xFFFFFFFF`(부호 있는 -1)로 만든다. `src`의 모든 비트가 1이므로 OR 정의상 결과 모든 비트가 강제로 1이 되기 때문이다. `NOT eax` 없이 레지스터를 -1로 세팅하는 짧은 관용구로 쓰인다.

## 화면/코드에서 보이는 징후
- `or eax, 4` — 3번째 비트를 켬 (`flags |= FLAG_X`)
- `or eax, eax` 다음에 `jz`/`jnz` — 옛 스타일 제로 체크
- `or eax, -1` — eax를 무조건 0xFFFFFFFF로 세팅 (에러 코드 -1 반환 등)
- `or al, 20h` — 아스키 문자를 소문자로 변환하는 고전 트릭 (`'A'|0x20 = 'a'`)

## 가장 먼저 할 것
1. `or eax, eax`처럼 자기 자신과의 OR인지 먼저 확인 (값 변화 없음, 플래그 세팅 목적)
2. 상수라면 어떤 비트가 켜지는지 확인
3. 결과가 이후 어떻게 쓰이는지(비교, 저장, 반환) 추적

## 단계별 절차

**1) 자기 자신 OR (제로 체크) 인식**
```asm
or  eax, eax
jz  is_zero
```
`test eax, eax; jz`와 동일한 의미로 해석한다.

**2) 비트 설정 인식**
```asm
or eax, 8    ; flags |= 0x8
```
결과의 해당 비트는 무조건 켜지고 다른 비트는 그대로 유지된다.

**3) 전체 1 채우기 인식**
```asm
or eax, -1   ; eax = 0xFFFFFFFF, 함수가 -1(에러)을 반환하는 흔한 패턴
ret
```

**4) 소문자 변환 트릭 인식**
```asm
or al, 20h   ; 아스키 대문자 -> 소문자 (비트 5를 켜서)
```

## 명령어/단축키
- IDA: 오퍼랜드 위에서 `R` 키로 진법 전환하며 비트 패턴 확인
- x64dbg: 레지스터 창에서 값 우클릭 → Binary로 표시하면 어떤 비트가 켜졌는지 바로 확인 가능

## 출력 해석
- IDA/Ghidra는 `or eax, 4`를 대체로 `x | 4` 또는 `x |= 4`로 그대로 보여준다.
- `or eax, eax` + `jz`는 종종 `if (x == 0)`으로 정리되어 표시된다(TEST와 동일하게 처리).
- `or eax, -1`은 보통 `x = -1` 또는 `x = 0xFFFFFFFF`로 단순화되어 보인다.

## 흔한 실수
- `or`이 C의 논리 OR(`||`)와 같다고 착각하는 것 — 어셈블리 `OR`는 항상 비트 단위 연산이다. 논리 OR는 보통 여러 개의 `test`/`cmp` + `jnz`를 연쇄시켜 컴파일된다.
- `or eax, eax`를 보고 "값이 바뀌는 연산"이라 오해하는 것 — 값은 절대 바뀌지 않으며 오직 플래그(ZF, SF)만 갱신된다.
- OR로 설정한 비트를 다시 끄려면 OR가 아니라 [`AND`](rev-0055-and.md)에 반전된 마스크를 써야 한다는 점을 혼동하는 것 — OR는 절대 비트를 끌 수 없다.

## 막혔을 때 다음 체크
- 값이 이상하게 큰(또는 음수인) 상수와 OR된다면 → 어떤 비트가 켜지는지 2진수로 풀어서 확인.
- OR 직후 분기가 나온다면 → `or eax, eax` 스타일 제로 체크인지 먼저 의심.
- OR로 조합된 값이 함수 인자로 들어간다면 → Windows API의 플래그 파라미터(예: `CreateFile`의 `dwFlagsAndAttributes`)를 조합하는 코드일 가능성이 높다.

## 미니 예제

**예제 1 — 플래그 비트 켜기**
```c
options |= OPTION_VERBOSE;   // OPTION_VERBOSE = 0x2
```
```asm
mov eax, [options]
or  eax, 2
mov [options], eax
```

**예제 2 — 옛 스타일 제로 체크**
```c
if (ptr == NULL) { return; }
```
```asm
mov eax, [ptr]
or  eax, eax
jz  do_return
```

**예제 3 — 함수가 -1(에러)을 반환**
```c
return -1;
```
```asm
or  eax, -1
ret
```

**예제 4 — 아스키 소문자 변환**
```c
char lower = c | 0x20;
```
```asm
mov al, [c]
or  al, 20h
```

## 관련 글
- [REV-0055 — AND: 마스크와 비트 제거](rev-0055-and.md)
- [REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화](rev-0057-xor.md)
- [REV-0058 — NOT: 비트 반전](rev-0058-not.md)
- [REV-0059 — TEST: 값을 바꾸지 않는 AND 비교](rev-0059-test.md)
- [REV-0067 — JE와 JZ: ZF가 1일 때 분기](rev-0067-je-jz.md)
- [REV-0068 — JNE와 JNZ: ZF가 0일 때 분기](rev-0068-jne-jnz.md)

## 출처/검증
- OR 명령어의 오퍼랜드/플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "OR—Logical Inclusive OR" 섹션 기준 (2026-09-08 검증).
