---
id: REV-0055
title: "AND: 마스크와 비트 제거"
slug: "rev-0055-and"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - and
  - AND
  - And
  - and 명령어
  - and instruction
  - "and eax, eax"
  - "and eax, 0FFh"
  - bitwise and
  - 비트 AND
  - 비트마스크
  - 비트 마스크
  - mask
  - 마스크 연산
  - 하위 비트만 남기기
  - 정렬 마스크
  - align mask
  - stack alignment and rsp
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - and 뭐임
  - and이 뭐죠
  - and 명령
  - AND 명령어
  - 앤드 명령어
  - and 왜씀
  - and 0xff 왜함
symptom_keywords:
  - and 0xff가 왜 나오는지 모르겠음
  - and rsp가 왜 있는지 모르겠음
  - and 명령이 값을 왜 줄이는지 모르겠음
  - 비트를 지우는 코드가 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`AND`는 두 오퍼랜드를 비트 단위로 AND 연산해서 첫 번째 오퍼랜드(목적지)에 저장하는 명령어로, "특정 비트만 남기고 나머지는 0으로 지우는" 마스킹에 가장 흔하게 쓰인다.

## 언제 검색해야 하나
- `and eax, 0FFh`, `and rsp, 0FFFFFFFFFFFFFFF0h` 같은 코드가 나오는데 무슨 뜻인지 모를 때
- 스택 정렬(alignment) 코드에서 `and rsp, -16`(또는 `-0x10`)이 왜 있는지 모를 때
- 값이 특정 범위(0~255, 0~65535 등)로 강제로 잘리는 것처럼 보이는데 원인을 못 찾을 때
- 특정 플래그 비트 하나만 검사하는 코드(`and eax, 1`)를 만났을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
AND dest, src
```
- `dest`는 항상 왼쪽, `src`는 항상 오른쪽 (Intel 문법 공통 규칙).
- `dest = dest AND src` — 결과가 **dest에 다시 저장**된다(원본 dest 값은 사라짐).
- `dest`는 레지스터 또는 메모리, `src`는 레지스터/메모리/즉시값(immediate)이 될 수 있다. 단, `dest`와 `src`가 동시에 둘 다 메모리일 수는 없다(x86 인코딩 제약).
- 예: `and eax, ebx`, `and eax, 0FFh`, `and dword ptr [rbp-4], 0FFh`, `and rsp, -16`.

### 레지스터/메모리에 미치는 효과
비트별로 두 값이 모두 1일 때만 결과 비트가 1이 되고, 하나라도 0이면 결과는 0이다.
```
  1010 1100
AND 0000 1111
= 0000 1100
```
즉 `src`의 비트가 1인 자리는 `dest`의 원래 값을 그대로 통과시키고, `src`의 비트가 0인 자리는 강제로 0으로 만든다. 이 성질 때문에 AND는 "필터" 또는 "마스크"로 불린다.

### 플래그 변화
- **ZF**: 결과가 0이면 1
- **SF**: 결과의 최상위 비트(부호 비트)가 1이면 1
- **PF**: 결과의 하위 1바이트에서 1비트 개수가 짝수면 1
- **CF = 0**, **OF = 0** (항상 무조건 0으로 클리어됨)
- **AF**: 정의되지 않음(undefined) — 사용하지 말 것

CF/OF가 항상 0이 된다는 점이 중요하다. 이후에 `jl`/`jg`(부호 있는 비교 분기, OF 기반)를 쓰면 `and`가 만든 OF=0을 근거로 판단하므로, "AND 직후 부호 비교 분기"는 사실상 결과값과 0의 비교와 동일하게 동작한다.

### 신호 있음/없음(signed/unsigned) 관점
AND 자체는 부호를 신경 쓰지 않는 순수 비트 연산이다. 다만 마스크로 상위 비트를 지우면 **음수였던 값이 양수로 바뀔 수 있다.** 예를 들어 `eax = 0xFFFFFFFF`(부호 있는 -1)에 `and eax, 0FFh`를 하면 결과는 `0x000000FF`(255, 양수)가 된다. 마스킹은 "부호 확장의 반대 방향" 연산이라고 이해하면 편하다.

### 스택/RSP/RIP 변화
AND 자체는 스택 포인터를 직접 건드리지 않지만, **`and rsp, -16` 같은 형태로 RSP 자체를 조작해서 스택을 특정 바이트 경계에 정렬시키는 데 매우 흔하게 쓰인다.** 이건 함수 프롤로그에서 SSE/AVX 명령어가 요구하는 16바이트 정렬을 맞추기 위한 컴파일러 관용구다. RIP는 변하지 않는다(분기 명령이 아니므로).

## 화면/코드에서 보이는 징후
- `and eax, 0FFh` — 하위 1바이트만 남김 (마스킹, [REV-0026](../binary-basics/rev-0026-bit-masks.md) 참고)
- `and eax, 0FFFFh` — 하위 2바이트만 남김
- `and rsp, 0FFFFFFFFFFFFFFF0h` 또는 `and rsp, -10h` — 스택을 16바이트 경계로 정렬
- `and eax, 1` — 최하위 비트(LSB)만 검사 (홀짝 판정, 플래그 비트 하나 확인)
- `and eax, ecx` — 두 값의 공통 비트만 남김 (플래그 조합 검사)

## 가장 먼저 할 것
1. `src` 오퍼랜드가 즉시값(상수)인지 레지스터인지 확인
2. 상수라면 16진수를 2진수로 변환해서 어떤 비트가 살아남는지 확인 (`0xFF` = 하위 8비트 전부 1)
3. 결과가 이후에 어떻게 쓰이는지(비교, 인덱스, 저장) 추적

## 단계별 절차

**1) 마스크 상수 해석**
```asm
and eax, 0FFh    ; eax = eax & 0xFF -> 결과 범위 0~255
```
`0xFF`는 이진수로 `11111111`(8비트 전부 1)이므로 하위 1바이트만 유지되고 나머지는 0이 된다.

**2) 비트 클리어(특정 비트를 0으로 강제) 패턴 인식**
```asm
and eax, 0FFFFFFFEh   ; LSB(최하위 비트)만 0으로 강제 클리어, 나머지는 유지
```
`0xFFFFFFFE`는 최하위 1비트만 0이고 나머지는 전부 1이다. 즉 "짝수로 강제 정렬"하는 관용구다(포인터 태그 비트를 지우는 등의 용도로도 쓰인다).

**3) 스택 정렬 코드 인식**
```asm
push rbp
mov  rbp, rsp
and  rsp, 0FFFFFFFFFFFFFFF0h   ; RSP를 16바이트 경계로 내림 정렬
sub  rsp, 20h
```
이후 `movaps`/`movdqa` 같은 정렬 필요 SSE 명령어가 안전하게 동작할 수 있다.

**4) 비트 플래그 검사 패턴**
```asm
and eax, 4        ; eax의 3번째 비트(값 4 = 0b100)만 추출
jz   flag_not_set  ; 결과가 0이면(그 비트가 꺼져 있으면) 분기
```
C의 `if (flags & FLAG_X)`가 정확히 이 패턴으로 컴파일된다.

## 명령어/단축키
- IDA: 오퍼랜드 위에서 `R`을 눌러 16진수 ↔ 10진수 ↔ 2진수 표시 전환 가능(비트 패턴 확인에 유용)
- Python으로 마스크 확인: `bin(0xFF)`, `hex(x & 0xFF)`

## 출력 해석
- IDA/Ghidra 디컴파일러는 `and eax, 0FFh`를 대체로 `x & 0xFF` 또는 캐스팅 `(uint8_t)x`로 보여준다.
- Ghidra가 `and rsp, ...` 스택 정렬 코드를 만나면 보통 의사코드에는 드러나지 않고 함수 프레임 설정의 일부로 흡수해서 보여준다.
- `and eax, N` 뒤에 `jz`가 오면 Ghidra/IDA는 흔히 `if ((x & N) == 0)`로 표시한다.

## 흔한 실수
- `and`가 "논리 AND(`&&`)"와 같다고 착각하는 것 — 어셈블리 `AND`는 항상 **비트 단위** AND다. C의 논리 AND(`&&`)에 대응하는 어셈블리는 보통 각 피연산자를 개별적으로 `test`/`cmp`한 뒤 `jz`를 연쇄시키는 형태로 컴파일된다.
- 마스크의 F 개수를 잘못 세는 것 — `0xFFFFFF`(F 6개=24비트)와 `0xFFFFFFFF`(F 8개=32비트)를 혼동하기 쉽다. 자세한 내용은 [REV-0026](../binary-basics/rev-0026-bit-masks.md) 참고.
- `and eax, eax`를 보고 뭔가 특별한 마스킹이라 착각하는 것 — 이건 사실 자기 자신과 AND하는 것이므로 값은 전혀 바뀌지 않고, `test eax, eax`(REV-0059 참고)와 마찬가지로 "ZF/SF를 eax==0, eax<0 여부로 세팅하는" 목적으로만 쓰인다(다만 실제 코드에서는 `test eax, eax`가 훨씬 더 흔하다).

## 막혔을 때 다음 체크
- 결과 범위가 이상하게 좁아 보인다면 → 마스크 상수의 비트 수를 다시 세어본다.
- AND 직후 분기가 나오면 → `jz`/`jnz`인지 확인하고 [REV-0067](rev-0067-je-jz.md)/[REV-0068](rev-0068-jne-jnz.md)에서 ZF 분기 의미를 확인한다.
- `and`로 정렬된 값이 왜 필요한지 모르겠다면 → 그 값이 이후 SIMD 명령어(`movaps` 등)나 함수 호출 전 스택 정렬에 쓰이는지 확인한다.

## 미니 예제

**예제 1 — 하위 바이트 마스킹**
```c
unsigned char b = (unsigned char)x;
```
```asm
mov eax, [x]
and eax, 0FFh    ; eax = x & 0xFF
```

**예제 2 — 플래그 비트 검사**
```c
if (flags & 0x04) { do_something(); }
```
```asm
mov eax, [flags]
and eax, 4
jz  skip
call do_something
skip:
```

**예제 3 — 스택 16바이트 정렬**
```asm
push rbp
mov  rbp, rsp
and  rsp, 0FFFFFFFFFFFFFFF0h  ; RSP 하위 4비트를 0으로 강제 -> 16바이트 배수
```

**예제 4 — 비트 클리어**
```c
x &= ~1;   // 최하위 비트를 0으로 (짝수로 만들기)
```
```asm
and eax, 0FFFFFFFEh
```

## 관련 글
- [REV-0026 — 8비트 16비트 24비트 32비트 64비트 마스크](../binary-basics/rev-0026-bit-masks.md)
- [REV-0056 — OR: 비트 설정](rev-0056-or.md)
- [REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화](rev-0057-xor.md)
- [REV-0058 — NOT: 비트 반전](rev-0058-not.md)
- [REV-0059 — TEST: 값을 바꾸지 않는 AND 비교](rev-0059-test.md)
- [REV-0067 — JE와 JZ: ZF가 1일 때 분기](rev-0067-je-jz.md)
- [REV-0068 — JNE와 JNZ: ZF가 0일 때 분기](rev-0068-jne-jnz.md)

## 출처/검증
- AND 명령어의 오퍼랜드/플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "AND—Logical AND" 섹션 기준 (2026-09-08 검증).
- 스택 16바이트 정렬 관용구: System V AMD64 ABI 및 Microsoft x64 호출 규약 문서의 스택 정렬 요구사항 기준.
