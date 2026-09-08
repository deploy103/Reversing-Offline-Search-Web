---
id: REV-0058
title: "NOT: 비트 반전"
slug: "rev-0058-not"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - not
  - NOT
  - Not
  - not 명령어
  - not instruction
  - bitwise not
  - 비트 반전
  - 비트 보수
  - one's complement
  - 1의 보수
  - not vs neg
  - not과 neg 차이
  - 비트 전체 뒤집기
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - not 뭐임
  - not이 뭐죠
  - not 명령
  - NOT 명령어
  - 낫 명령어
  - not이 플래그를 왜 안바꾸는지
symptom_keywords:
  - not 명령이 플래그를 안바꾸는 이유
  - not과 neg를 헷갈림
  - 비트 반전이 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`NOT`는 오퍼랜드 하나의 모든 비트를 뒤집는(0↔1) 단항 명령어로, 1의 보수(one's complement)를 만들며 **플래그를 전혀 건드리지 않는다는 점**이 가장 중요한 특징이다.

## 언제 검색해야 하나
- `not eax` 처럼 오퍼랜드가 하나뿐인 코드를 만났는데 무슨 연산인지 모를 때
- `NOT`과 `NEG`([REV-0054](rev-0054-neg.md))를 헷갈릴 때 — 둘 다 오퍼랜드가 하나지만 결과와 플래그 동작이 다르다
- 반전된 마스크를 만들어서 [AND](rev-0055-and.md)로 특정 비트를 지우는 코드를 분석할 때
- C의 `~x`(비트 NOT)와 `!x`(논리 NOT)의 어셈블리 차이를 이해하고 싶을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
NOT dest
```
- 오퍼랜드가 **하나뿐인 단항(unary) 연산**이다 (source가 따로 없음).
- `dest`는 레지스터 또는 메모리.
- `dest = ~dest` (모든 비트를 뒤집음: 1은 0으로, 0은 1로)
- 예: `not eax`, `not dword ptr [rbp-4]`, `not rax`.

### 레지스터/메모리에 미치는 효과
```
    1010 1100
NOT ---------
  = 0101 0011
```
모든 비트가 그대로 반전된다. 수학적으로는 `~x == -x - 1` (2의 보수 체계에서), 또는 `~x == 0xFFFFFFFF - x` (32비트 기준)와 동일하다.

### 플래그 변화 — NOT의 가장 중요한 특징
**`NOT`은 어떤 플래그도 건드리지 않는다 (ZF, SF, CF, OF, PF, AF 전부 그대로 유지).** 이는 AND/OR/XOR/TEST/CMP 등 대부분의 논리·비교 명령어와 뚜렷하게 다른 점이다. 이전 명령어가 세팅해 놓은 플래그가 `NOT` 이후에도 그대로 살아있으므로, `NOT` 다음에 오는 조건부 분기는 `NOT` 이전 명령어의 결과를 근거로 판단한다는 점에 유의해야 한다.

### NOT vs NEG — 반드시 구분할 것
초보자가 가장 많이 헷갈리는 지점이다.
| | `NOT eax` | `NEG eax` |
|---|---|---|
| 연산 | 모든 비트 반전 (`~x`, 1의 보수) | 2의 보수 음수 (`-x`, `~x + 1`) |
| 플래그 | **전혀 건드리지 않음** | ZF, SF, CF, OF 등 세팅됨 (SUB 0, x와 동일) |
| `eax=5`일 때 결과 | `0xFFFFFFFA` (-6) | `0xFFFFFFFB` (-5) |
| `eax=0`일 때 결과 | `0xFFFFFFFF` (-1) | `0x00000000` (0 그대로) |

`eax=0`일 때 결과가 완전히 다르다는 점이 특히 중요하다 — `NOT 0`은 `-1`이 되지만 `NEG 0`은 여전히 `0`이다.

### 신호 있음/없음(signed/unsigned) 관점
NOT은 순수 비트 반전이라 signed/unsigned 구분이 의미 없지만, 결과를 부호 있는 정수로 해석하면 흔히 "값이 갑자기 음수(또는 매우 큰 unsigned 값)로 바뀌는" 것처럼 보인다. 예: `eax = 0x00000003`에 `not eax`를 하면 `0xFFFFFFFC`가 되어, signed로는 -4, unsigned로는 4294967292가 된다.

### 스택/RSP/RIP 변화
없음.

### C의 `~`와 `!`의 어셈블리 차이 — 흔한 함정
C에서 `~x`(비트 NOT)는 정확히 `NOT` 명령어로 컴파일된다. 하지만 `!x`(논리 NOT, "x가 0이 아니면 0, x가 0이면 1")는 `NOT`으로 컴파일되지 **않는다.** `!x`는 보통 `test`/`cmp`로 x를 0과 비교한 뒤 `sete`(SETcc 계열, REV-00xx 예정)로 0/1을 만드는 형태로 컴파일된다. `NOT eax`를 실행하면 `eax=0`이 `0xFFFFFFFF`(참 같지만 실제로는 -1)가 되어버려 C의 `!` 의미와 전혀 다르다는 점이 초보자가 가장 많이 하는 실수다.

## 화면/코드에서 보이는 징후
- `not eax` — 단독으로 등장, 비트 전체 반전
- `not eax` 다음에 `and`/`or`가 이어지는 경우 — 반전된 마스크로 특정 비트만 지우거나(AND) 켜는(OR) 조합 연산
- `not eax` 다음 바로 `inc eax` — `NOT` + `INC` 조합은 `NEG`와 동일한 결과를 만드는 우회 표현(컴파일러가 드물게 이런 형태를 만들기도 함)
- 플래그가 `not` 앞뒤로 동일하게 유지되는 것을 디버거에서 확인 가능

## 가장 먼저 할 것
1. 오퍼랜드가 정말 하나뿐인지 확인 (NEG와 혼동 방지)
2. NOT 앞뒤에서 플래그가 안 바뀌는지 디버거로 확인해 "플래그 안 건드림"이라는 특성을 체감
3. NOT 결과가 곧바로 AND/OR와 결합되는지 확인 (마스크 반전 패턴)

## 단계별 절차

**1) 단순 비트 반전 인식**
```asm
not eax   ; eax = ~eax
```

**2) 반전 마스크로 특정 비트 클리어**
```asm
mov ecx, 4        ; 클리어하고 싶은 비트(bit 2)
not ecx            ; ecx = 0xFFFFFFFB (bit 2만 0, 나머지 전부 1)
and eax, ecx        ; eax의 bit 2만 0으로 강제 클리어, 나머지는 유지
```
컴파일 시점에 마스크 값이 고정 상수라면 컴파일러는 대부분 `NOT` 없이 이미 반전된 상수를 직접 인코딩한다(`and eax, 0FFFFFFFBh`). `NOT`이 실제로 등장하는 경우는 마스크가 **변수**(런타임에 결정)일 때가 많다.

**3) NOT+INC로 NEG 흉내(드문 패턴) 인식**
```asm
not eax
inc eax    ; 결과적으로 eax = -eax (NEG eax와 동일한 최종 값)
```

**4) 플래그 미변경 확인**
```asm
cmp eax, ebx   ; 여기서 ZF/SF/CF/OF 세팅
not ecx         ; ecx만 반전, 방금 cmp가 세팅한 플래그는 그대로 유지됨
jz  still_valid ; 이 jz는 not이 아니라 위의 cmp 결과를 보고 분기한다
```

## 명령어/단축키
- x64dbg/IDA 디버거: `not` 명령어 실행 전후로 플래그 레지스터(EFLAGS) 창을 비교해서 정말 변화가 없는지 직접 확인해보면 이해가 빠르다.

## 출력 해석
- IDA/Ghidra는 `not eax`를 대체로 `x = ~x`로 그대로 보여준다.
- `not` 뒤에 바로 `and`가 오는 코드는 종종 `x &= ~mask;` 형태로 정리되어 보인다.

## 흔한 실수
- `NOT`과 `NEG`를 혼동하는 것 — 표에서 정리했듯 `eax=0`일 때 결과가 완전히 다르다(`NOT`은 -1, `NEG`는 0).
- `NOT`이 플래그를 세팅한다고 착각해서, `NOT` 다음의 `jz`/`jnz`가 `NOT`의 결과를 보고 분기한다고 오해하는 것 — 실제로는 그 이전 명령어의 플래그를 보고 분기한다.
- `NOT`을 C의 논리 부정 `!`과 같다고 착각하는 것 — `NOT`은 `~`(비트 전체 반전)에 대응하며, `!`(0/1 논리 부정)은 보통 `cmp`/`test` + `sete`로 컴파일된다.

## 막혔을 때 다음 체크
- `not` 다음의 분기가 이해가 안 된다면 → `not` 앞의 명령어가 무엇인지 확인 (플래그는 거기서 온 것).
- `not` 결과가 예상과 다르게 음수로 보인다면 → 부호 있는 해석 때문이니 [REV-0024](../binary-basics/rev-0024-twos-complement.md)(2의 보수)를 참고해 정상 동작임을 확인.
- 컴파일된 코드에 `not`이 안 보이는데 소스에는 `~mask`가 있다면 → 컴파일러가 상수를 컴파일 타임에 미리 반전시켜 인코딩했을 가능성이 높음(정상).

## 미니 예제

**예제 1 — 단순 비트 반전**
```c
unsigned int y = ~x;
```
```asm
mov eax, [x]
not eax
mov [y], eax
```

**예제 2 — 특정 비트 클리어(변수 마스크)**
```c
flags &= ~bit;
```
```asm
mov eax, [bit]
not eax
and [flags], eax
```

**예제 3 — NOT과 NEG의 차이를 값으로 확인**
```asm
mov eax, 0
not eax    ; eax = 0xFFFFFFFF (-1), 플래그는 이전 상태 그대로
mov ebx, 0
neg ebx    ; ebx = 0x00000000 (0), ZF=1로 세팅됨
```

**예제 4 — NOT+INC로 NEG 흉내**
```asm
mov eax, 5
not eax    ; eax = 0xFFFFFFFA
inc eax    ; eax = 0xFFFFFFFB (-5, NEG eax와 같은 최종 값)
```

## 관련 글
- [REV-0055 — AND: 마스크와 비트 제거](rev-0055-and.md)
- [REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화](rev-0057-xor.md)
- [REV-0054 — NEG: 2의 보수 음수 만들기](rev-0054-neg.md)
- [REV-0024 — 2의 보수와 음수 표현](../binary-basics/rev-0024-twos-complement.md)

## 출처/검증
- NOT 명령어의 오퍼랜드/플래그 동작(플래그 미변경 포함): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "NOT—One's Complement Negation" 섹션 기준 (2026-09-08 검증).
