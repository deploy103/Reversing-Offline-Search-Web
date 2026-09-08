---
id: REV-0069
title: "JG JGE JL JLE: Signed 비교 분기"
slug: "rev-0069-jg-jge-jl-jle"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jg
  - JG
  - jge
  - JGE
  - jl
  - JL
  - jle
  - JLE
  - jnle
  - JNLE
  - jnl
  - JNL
  - jnge
  - JNGE
  - jng
  - JNG
  - signed 비교
  - signed comparison
  - 부호 있는 비교
  - SF
  - OF
  - sign flag
  - overflow flag
  - cmp jg
  - cmp jl
  - if a > b
  - 정수 오버플로우
  - integer overflow
  - signed vs unsigned
aliases:
  - jg 뭐임
  - jl 플래그
  - jge 조건
  - jle 조건
  - signed 점프
  - 부호있는 분기
  - jg jl 차이
  - jg랑 ja 차이
symptom_keywords:
  - jg랑 ja 헷갈림
  - signed unsigned 비교 헷갈림
  - 음수 비교가 이상하게 동작함
  - 왜 분기가 반대로 됨
  - SF OF 차이 모르겠음
  - 정수 부호 버그
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`JG`/`JGE`/`JL`/`JLE`는 직전 `CMP`(또는 `SUB`) 결과를 **signed(부호 있는) 정수**로 해석해서 크다/크거나 같다/작다/작거나 같다를 판단해 분기하는 명령이다. 이 계열은 SF(Sign Flag)와 OF(Overflow Flag)의 조합을 본다 — CF(Carry Flag)를 보는 unsigned 계열([REV-0070](./rev-0070-ja-jae-jb-jbe.md))과는 완전히 다른 원리로 동작하며, 같은 비트 패턴에 대해 정반대의 분기 결과를 낼 수 있다.

> 이 글의 unsigned 버전은 [REV-0070 — JA JAE JB JBE](./rev-0070-ja-jae-jb-jbe.md)를 함께 읽어라. 이 두 글은 "같은 CMP 한 줄이 signed로 보느냐 unsigned로 보느냐에 따라 정반대로 분기할 수 있다"는 것을 보여주는 짝이며, **이 차이를 못 짚는 것이 CTF에서 가장 흔하게 문제를 놓치는 원인**이다.

## 언제 검색해야 하나
- 어셈블리에 `jg`, `jge`, `jl`, `jle`가 나오는데 각각 어떤 플래그를 보는지 모를 때
- `cmp eax, ebx` 다음에 `jg`가 왜 분기하거나 안 하는지 손으로 계산해서 확인하고 싶을 때
- IDA 디컴파일러가 어떤 변수를 `int`로 보여주는데 그게 맞는 해석인지 의심될 때
- "jg랑 ja 차이가 뭐냐"처럼 signed/unsigned 분기 계열이 헷갈릴 때
- 정수 부호 버그(길이 체크 우회 등) 관련 CTF 문제를 분석 중일 때

## 핵심 개념

### 니모닉과 별칭
이 계열은 실제로는 4개의 조건 코드이고, 각각 두 가지 이름(니모닉)을 갖는다 — 어셈블러/디스어셈블러에 따라 둘 중 어느 쪽으로 표시되어도 완전히 같은 명령(같은 opcode)이다.

| 니모닉 | 동일 니모닉 | 의미 |
|---|---|---|
| `JG` | `JNLE` (Jump if Not Less or Equal) | signed 크다 (greater) |
| `JGE` | `JNL` (Jump if Not Less) | signed 크거나 같다 (greater or equal) |
| `JL` | `JNGE` (Jump if Not Greater or Equal) | signed 작다 (less) |
| `JLE` | `JNG` (Jump if Not Greater) | signed 작거나 같다 (less or equal) |

### Intel SDM 전체 Jcc 조건 표
아래는 Intel 64 and IA-32 Architectures Software Developer's Manual이 정의하는 조건 코드 전체 표다. 이 글에서 다루는 4개는 굵게 표시된 부분(signed 계열)이고, `A/AE/B/BE`(unsigned 계열)는 [REV-0070](./rev-0070-ja-jae-jb-jbe.md)에서 다룬다.

| 접미사 | 다른 표기 | 테스트하는 플래그 조건 | 의미 |
|---|---|---|---|
| E / Z | — | ZF = 1 | equal / zero |
| NE / NZ | — | ZF = 0 | not equal / not zero |
| **G / NLE** | — | **ZF = 0 AND SF = OF** | **signed greater** |
| **GE / NL** | — | **SF = OF** | **signed greater or equal** |
| **L / NGE** | — | **SF ≠ OF** | **signed less** |
| **LE / NG** | — | **ZF = 1 OR SF ≠ OF** | **signed less or equal** |
| A / NBE | — | CF = 0 AND ZF = 0 | unsigned above |
| AE / NB / NC | — | CF = 0 | unsigned above or equal |
| B / NAE / C | — | CF = 1 | unsigned below |
| BE / NA | — | CF = 1 OR ZF = 1 | unsigned below or equal |
| S | — | SF = 1 | sign (negative) |
| NS | — | SF = 0 | not sign |
| O | — | OF = 1 | overflow |
| NO | — | OF = 0 | no overflow |
| P / PE | — | PF = 1 | parity even |
| NP / PO | — | PF = 0 | parity odd |

### 각 조건을 하나씩 정확히

| 명령 | 플래그 조건 | 뜻 |
|---|---|---|
| `JG` (`JNLE`) | **ZF = 0 AND SF = OF** | a ≠ b 이고, "진짜 부호 차이"가 양수 → a > b |
| `JGE` (`JNL`) | **SF = OF** | "진짜 부호 차이"가 음수가 아님 → a ≥ b |
| `JL` (`JNGE`) | **SF ≠ OF** | "진짜 부호 차이"가 음수 → a < b |
| `JLE` (`JNG`) | **ZF = 1 OR SF ≠ OF** | a = b 이거나 "진짜 부호 차이"가 음수 → a ≤ b |

### 왜 하필 SF와 OF를 XOR(같다/다르다)로 비교하는가 — 핵심 원리
`CMP a, b`는 내부적으로 `a - b`를 계산해서 결과는 버리고 플래그만 세팅한다. 만약 오버플로우가 전혀 없다면(`OF = 0`) 이야기는 간단하다: 결과가 음수면(`SF = 1`) `a < b`, 양수면(`SF = 0`) `a > b`다. 즉 `OF = 0`일 때는 `SF` 하나만 봐도 정답이다.

문제는 **signed 뺄셈이 오버플로우할 때**다. 예를 들어 32비트 signed 정수에서 `INT_MAX(0x7FFFFFFF) - (-1)`을 계산하면 수학적으로는 `0x80000000`인데, signed 32비트 범위(`-2147483648 ~ 2147483647`)를 벗어나므로 CPU는 이를 오버플로우로 표시한다(`OF = 1`). 이때 결과 비트 패턴 `0x80000000`의 최상위 비트는 1이라서 `SF = 1`(마치 음수인 것처럼 보임)이지만, 실제 수학적 결과(2147483648)는 **양수**다. 즉 오버플로우가 나면 `SF`가 "거짓말"을 한다.

이 거짓말을 바로잡는 방법이 `SF`와 `OF`를 비교하는 것이다:
- `OF = 0`(오버플로우 없음)일 때: `SF`는 진짜 부호와 일치 → `SF = 1`이면 진짜 음수.
- `OF = 1`(오버플로우 있음)일 때: `SF`는 진짜 부호와 반대로 뒤집혀 있음 → `SF = 0`이면 사실은 진짜 음수.

두 경우를 하나의 규칙으로 합치면: **"진짜 결과가 음수"인 조건은 `SF ≠ OF`**다 (오버플로우가 없을 때는 `OF=0`이므로 `SF≠OF`는 그냥 `SF=1`과 같고, 오버플로우가 있을 때는 `OF=1`이므로 `SF≠OF`는 `SF=0`과 같아서 뒤집힌 SF를 정확히 보정해준다). 이래서 `JL`이 `SF ≠ OF`를 테스트하고, `JGE`가 그 반대인 `SF = OF`를 테스트하는 것이다.

**구체적 오버플로우 예시**: `INT_MAX`(0x7FFFFFFF = 2147483647)와 `-1`(0xFFFFFFFF)을 signed로 비교한다고 하자.
```asm
mov eax, 7FFFFFFFh   ; eax = INT_MAX
cmp eax, 0FFFFFFFFh  ; eax - (-1) = INT_MAX - (-1), 수학적으로 2147483648 -> signed 32비트 범위 초과
```
`INT_MAX - (-1)`은 수학적으로 `INT_MAX + 1 = 2147483648`이며, 이는 32비트 signed 표현 범위(최대 2147483647)를 넘으므로 `OF = 1`이 세팅된다. 결과 비트 패턴은 `0x80000000`이라 `SF = 1`이다. 만약 `SF`만 보고 판단했다면 "결과가 음수니까 `INT_MAX < -1`"이라는 **완전히 틀린 결론**을 낼 뻔했다. 하지만 `SF ≠ OF`를 계산하면 `1 ≠ 1`은 거짓이므로 `JL`은 분기하지 않는다 — 즉 `INT_MAX < -1`이 아니라는(맞는) 결론이 나온다. 반대로 `JGE`(`SF = OF`, `1 = 1` 참)는 분기해서 `INT_MAX >= -1`이 성립함을 올바르게 판단한다.

### 0xFFFFFFFF vs 1 — signed로 해석했을 때
아래는 `CMP` 자체는 signed인지 unsigned인지 전혀 모른다는 것, 그리고 그 뒤에 붙는 Jcc가 해석을 결정한다는 것을 보여주는 핵심 예제다.
```asm
mov eax, 0FFFFFFFFh   ; eax = 0xFFFFFFFF
cmp eax, 1            ; 내부적으로 eax - 1 을 계산해 플래그만 세팅 (eax 값 자체는 안 바뀜)
```
`CMP`는 `0xFFFFFFFF - 1 = 0xFFFFFFFE`를 계산하면서 플래그를 다음처럼 세팅한다:
- `CF = 0` (unsigned 뺄셈에서 borrow 없음 — 0xFFFFFFFF는 unsigned로 1보다 크므로 안 빌림)
- `ZF = 0` (결과가 0이 아님)
- `SF = 1` (결과 0xFFFFFFFE의 최상위 비트가 1)
- `OF = 0` (signed 뺄셈 관점에서 오버플로우 없음: -1 - 1 = -2, 정상 범위)

이 **정확히 동일한 CMP 한 줄** 뒤에 어떤 Jcc를 붙이느냐로 완전히 다른 해석이 나온다:
- **signed로 해석**하면 eax는 `-1`, 비교 대상은 `1` → `-1 < 1`이므로 `JL`(`SF≠OF`: `1≠0` → 참)이 **분기하고**, `JG`는 분기하지 않는다.
- unsigned로 해석하면 eax는 `4294967295`, 비교 대상은 `1` → `4294967295 > 1`이므로 `JA`가 분기하고 `JB`는 분기하지 않는다 (자세한 unsigned 쪽 계산은 [REV-0070](./rev-0070-ja-jae-jb-jbe.md) 참고).

즉 CPU는 eax에 들어있는 비트 패턴이 "signed인지 unsigned인지" 전혀 모른다. `CMP`는 그냥 뺄셈해서 플래그만 세팅할 뿐이고, "이 값을 signed로 보겠다(JG/JL 계열 사용) vs unsigned로 보겠다(JA/JB 계열 사용)"는 순전히 그 다음에 프로그래머(컴파일러)가 어떤 Jcc 니모닉을 선택했느냐로 결정된다. 이것이 바로 signed/unsigned 버그와 CTF에서 흔히 나오는 "음수를 unsigned로 취급해서 크기 체크를 우회하는" 취약점의 근본 원리이기도 하다.

### Intel 문법과 오퍼랜드
```
JG  rel8/rel32
JGE rel8/rel32
JL  rel8/rel32
JLE rel8/rel32
```
오퍼랜드는 하나, 현재 RIP(다음 명령 주소) 기준 상대 오프셋이다. IDA/objdump 등은 이를 이미 절대 주소로 계산해서 `jg loc_401234` 같은 형태로 보여준다.

### 플래그: 읽기만 하고 바꾸지 않는다
- **읽는 플래그**: `SF`, `OF` (`JG`/`JLE`는 `ZF`도 함께 읽음)
- **바꾸는 플래그**: 없음. `Jcc` 계열은 플래그를 절대 수정하지 않는다 — 오직 직전에 `CMP`/`SUB`/`TEST` 등이 세팅해 둔 플래그를 읽기만 한다.

### 스택/RIP 변화
`Jcc`는 조건이 참이면 `RIP`를 target 주소로 바꾸고, 거짓이면 다음 명령으로 그대로 진행한다(`RIP`가 명령 길이만큼만 증가). 스택(`RSP`)은 전혀 건드리지 않는다 — `CALL`([REV-0071](./rev-0071-call.md))처럼 반환 주소를 push하지 않는다.

### 컴파일러 패턴 — signed 변수의 `if`
```c
int a, b;
if (a > b) { ... }
```
컴파일러는 `a`, `b`가 **signed** `int`로 선언되어 있으므로 다음처럼 컴파일한다:
```asm
cmp eax, ebx      ; a, b가 각각 eax, ebx에 있다고 가정
jg  true_branch   ; signed greater
```
그런데 만약 완전히 똑같이 생긴 C 코드라도 변수가 `unsigned int`로 선언되어 있었다면:
```c
unsigned int a, b;
if (a > b) { ... }
```
```asm
cmp eax, ebx
ja  true_branch   ; unsigned above
```
**컴파일러가 생성하는 어셈블리는 완전히 다르다** — `>` 연산자는 똑같이 생겼지만 변수의 선언된 타입에 따라 `jg`가 나올지 `ja`가 나올지가 결정된다. 이것이 디스어셈블리만 보고도 원본 변수가 signed였는지 unsigned였는지 역으로 알아낼 수 있는 이유다.

`for` 루프의 경계 검사도 이 계열이 자주 등장하는 자리다:
```c
for (int i = 0; i < n; i++) { ... }
```
```asm
        xor  eax, eax        ; i = 0
loop_top:
        cmp  eax, [n]
        jge  loop_exit        ; i >= n 이면 루프 탈출 (signed 비교, i와 n이 int이므로)
        ...
        inc  eax
        jmp  loop_top
loop_exit:
```

### IDA/Ghidra 디컴파일 결과에서 보이는 모습
디컴파일러는 어셈블리의 `Jcc` **니모닉을 보고 거꾸로** 변수 타입을 추정한다: `JG`/`JGE`/`JL`/`JLE` 계열이 쓰였으면 피연산자를 `int`(signed)로, `JA`/`JAE`/`JB`/`JBE` 계열이 쓰였으면 `unsigned int`로 표시한다. 즉 디컴파일러가 보여주는 `int`라는 타입 이름은 실제 변수 선언이 아니라 **니모닉으로부터의 추론 결과**다.

**디컴파일러의 추측이 의심스러울 때 원본 플래그 테스트로 되돌아가는 법**: 예를 들어 어떤 변수가 버퍼 길이나 배열 인덱스처럼 절대 음수가 될 수 없는 값인데 디컴파일러(F5 화면)에는 `int`로 표시되어 있어 뭔가 이상하다고 느껴진다면, IDA에서 **Space**를 눌러 디스어셈블리 뷰로 전환한 뒤 실제 `CMP` + `Jcc` 쌍을 찾아 정확한 니모닉 철자를 확인한다. `jg`/`jge`/`jl`/`jle`(N이 없는 신호 계열)인지 `ja`/`jae`/`jb`/`jbe`인지를 직접 읽는 것이 원본 컴파일 결과에 대한 **최종 근거**다 — 디컴파일러가 붙인 타입 이름은 그 위에 얹힌 휴리스틱 추측일 뿐이고, 특히 IDA의 지역 타입 전파는 캐스트가 섞인 코드에서 가끔 틀린다. 반대로 그 신호 불일치 자체가 "unsigned 크기를 실수로(혹은 의도적으로) signed 비교로 처리한" 진짜 버그/취약점의 흔적일 수도 있으니, 불일치를 발견하면 그냥 넘어가지 말고 이유를 따져봐야 한다.

### 리버싱에서의 의미
signed 비교 관련 버그는 고전적인 취약점 클래스다. 예를 들어 다음과 같은 길이 체크 코드를 생각해보자:
```c
int len = get_user_length();   // 공격자가 제어 가능
if (len > MAX_SIZE) {
    return -1;                  // 너무 크면 거부
}
memcpy(buf, data, len);         // len이 여기서는 size_t로 암묵 변환됨
```
`len`이 **signed** `int`이기 때문에 컴파일된 검사는 `jg`(signed greater)를 쓴다. 공격자가 음수(예: `-1`)를 넣으면 `-1 > MAX_SIZE`는 **거짓**이므로 이 체크를 통과한다. 그런데 `memcpy`의 세 번째 인자는 `size_t`(unsigned)이므로, `-1`이 그 자리에서 `0xFFFFFFFF`(또는 64비트라면 더 큰 값)로 재해석되어 사실상 무한대에 가까운 크기의 복사가 일어난다 — 전형적인 signedness 버그로 인한 버퍼 오버플로우다. 디스어셈블리에서 길이/크기 검사에 `jg`/`jl` 계열이 쓰였다면, "이 값이 정말 음수가 될 수 있는가?"를 항상 의심해봐야 한다.

## 화면/코드에서 보이는 징후
- `cmp eax, ebx` 바로 다음에 `jg`, `jge`, `jl`, `jle` 중 하나
- IDA 디스어셈블리에서 `jnle`, `jnl`, `jnge`, `jng`처럼 대체 니모닉으로 표시되는 경우(툴/버전에 따라 다름)
- 디컴파일 결과에서 `int` 타입 변수에 대한 `if (a > b)`, `if (a < b)` 형태
- `for`/`while` 루프의 탈출 조건이 `jge`/`jl` 등으로 되어 있는 경우

## 가장 먼저 할 것
1. `Jcc` 바로 위의 `CMP`(또는 `SUB`/`TEST`)가 어떤 두 값을 비교하는지 확인한다.
2. `Jcc` 니모닉의 정확한 철자를 읽는다 — `G`/`GE`/`L`/`LE`(N 접두사 형태 포함)인지, `A`/`AE`/`B`/`BE`인지 구분한다.
3. 비교 대상 변수가 문맥상 음수가 될 수 있는 값인지(신호 있는 계산 결과) 절대 음수가 될 수 없는 값인지(길이, 인덱스, 포인터) 판단하고, 실제 쓰인 니모닉과 그 판단이 일치하는지 재확인한다.
4. 필요하면 손으로 SF/OF를 계산해 분기 여부를 검증한다(위 표 활용).

## 단계별 절차

**1) CMP+JG로 `if (a > b)` 해석하기**
```asm
mov  eax, [a]
cmp  eax, [b]
jg   greater_branch
```
→ `a`(signed int)가 `b`(signed int)보다 크면 `greater_branch`로 분기. C로는 `if (a > b)`.

**2) 손으로 플래그 계산해서 분기 여부 검증하기**
`cmp eax, ebx`에서 `eax = 5`, `ebx = 10`이라면 `5 - 10 = -5`. 오버플로우 없음(`OF=0`), 결과 음수(`SF=1`). `JL`(`SF≠OF`: `1≠0` 참) → 분기함. `JG`(`ZF=0 AND SF=OF`: `SF=OF`가 `1=0`으로 거짓) → 분기 안 함. 즉 `5 < 10`이 맞다는 결론.

**3) 루프 경계 검사 읽기**
```asm
cmp  eax, [n]
jge  loop_exit    ; i >= n 이면 종료
```
→ `for (int i = 0; i < n; i++)`의 탈출 조건. `i`, `n`이 signed(int)라서 `jge`가 쓰였다.

**4) 오버플로우가 낀 비교 검증하기**
```asm
mov eax, 7FFFFFFFh  ; INT_MAX
cmp eax, 0FFFFFFFFh ; -1과 비교
jl  eax_less
```
`OF=1`, `SF=1`이므로 `SF≠OF`는 거짓 → `JL` 분기 안 함. 즉 `INT_MAX < -1`이 아니라는(맞는) 결론. `SF`만 보고 착각하면 안 되는 이유가 여기서 실증된다.

## 명령어/단축키
- IDA: `Space`(디스어셈블리 ↔ 그래프 뷰 전환), `F5`(디컴파일), 조건 분기 위에서 화살표 흐름을 눈으로 따라가며 True/False 경로(초록/빨강 화살표) 확인
- x64dbg: 조건 분기 명령 실행 전 Flags 창에서 `SF`, `OF`, `ZF` 값을 직접 확인 가능
- GDB/Pwndbg: `info registers eflags` 또는 `p $eflags`로 플래그 레지스터 확인, `x/i $pc`로 다음 명령 미리보기

## 출력 해석
- x64dbg/GDB의 플래그 창에서 `SF`, `OF`가 모두 1이거나 모두 0이면 `JGE`가 참(분기함), 서로 다르면 `JL`이 참
- IDA 그래프 뷰에서 조건 분기는 두 갈래로 갈라지며, 보통 초록 화살표가 조건 참(분기함), 빨간/파란 화살표가 조건 거짓(그대로 진행)을 나타낸다(색상은 설정에 따라 다를 수 있음) — 헷갈리면 Options에서 확인

## 흔한 실수
- **JG(signed)와 JA(unsigned)를 혼동하는 것 — 이것이 CTF에서 가장 흔한 실수다.** signed 비교(`JG`/`JGE`/`JL`/`JLE`)는 `SF`/`OF`를 보고, unsigned 비교(`JA`/`JAE`/`JB`/`JBE`)는 `CF`를 본다 — 이 둘을 절대 혼동하지 말 것. 변수가 음수를 가질 수 있는 값(길이, 크기, 인덱스가 아니라 부호 있는 계산 결과)인지, 아니면 절대 음수가 될 수 없는 값(포인터, 크기, 배열 인덱스 등 대개 unsigned)인지 문맥으로 판단하고, 그 판단이 실제 Jcc 니모닉과 일치하는지 항상 재확인하라.
- `JGE`와 `JAE`(`JNB`)가 영어로는 둘 다 "크거나 같다"처럼 들려서 같은 걸로 착각하는 것 — `JGE`는 `SF=OF`, `JAE`는 `CF=0`으로 완전히 다른 플래그를 본다. 위 0xFFFFFFFF vs 1 예제처럼 같은 CMP 뒤에서 정반대로 분기할 수 있다.
- 오버플로우가 있는 경우에 `SF`만 보고 부호를 판단하는 것 — `OF=1`일 때는 `SF`가 뒤집혀 있으므로 반드시 `SF`와 `OF`를 함께 봐야 한다.
- 디컴파일러가 보여주는 `int`/`unsigned int` 타입을 무조건 신뢰하는 것 — 실제 근거는 디스어셈블리의 `Jcc` 니모닉이다.

## 막혔을 때 다음 체크
- 분기 방향이 예상과 반대로 보인다면 → 변수가 정말 signed인지 unsigned인지부터 재확인 (니모닉이 G/L 계열인지 A/B 계열인지 Space로 디스어셈블리 확인)
- SF/OF 값이 헷갈리면 → 디버거(x64dbg Flags 창, GDB `p $eflags`)로 직접 값 찍어서 확인
- 왜 이 자리에서 signed 비교가 쓰였는지 이해가 안 되면 → 원본 C 변수가 `int`/`long` 등 signed 타입일 가능성이 높다는 뜻이니 그 값이 어디서 오는지(사용자 입력 등) 추적
- CMP의 두 오퍼랜드 순서가 헷갈리면 → `cmp a, b`는 `a - b`를 계산한다는 것을 기억 (REV-0060 CMP 글 예정 참고)

## 미니 예제

**예제 1 — 두 양수 signed 비교**
```c
int a = 5, b = 3;
if (a > b) puts("a is bigger");
```
```asm
mov  eax, 5
cmp  eax, 3       ; 5 - 3 = 2, OF=0, SF=0
jg   is_bigger    ; ZF=0 AND SF=OF(0=0) -> 참, 분기함
```

**예제 2 — 오버플로우가 SF를 속이는 경우**
```asm
mov eax, 7FFFFFFFh   ; INT_MAX
cmp eax, 0FFFFFFFFh  ; -1과 비교, 결과 SF=1이지만 OF=1이라 보정 필요
jl  eax_less         ; SF≠OF: 1≠1 거짓 -> 분기 안 함 (INT_MAX는 -1보다 작지 않음, 맞는 결론)
```

**예제 3 — 루프 탈출(JGE)**
```c
for (int i = 0; i < n; i++) { sum += arr[i]; }
```
```asm
        xor  eax, eax
loop_top:
        cmp  eax, [n]
        jge  loop_exit     ; i >= n
        ...
        inc  eax
        jmp  loop_top
loop_exit:
```

**예제 4 — 0xFFFFFFFF vs 1, signed 해석**
```asm
mov eax, 0FFFFFFFFh   ; eax = 0xFFFFFFFF (signed로는 -1)
cmp eax, 1
jl  negative_is_less   ; SF≠OF: SF=1,OF=0 -> 1≠0 참 -> 분기함 (-1 < 1, 맞는 결론)
jg  never_taken         ; ZF=0 AND SF=OF -> SF=OF가 거짓이므로 분기 안 함
```

## 관련 글
- [REV-0070 — JA JAE JB JBE: Unsigned 비교 분기](./rev-0070-ja-jae-jb-jbe.md) — 같은 CMP를 unsigned로 해석하는 짝 글, 반드시 함께 읽을 것
- [REV-0067 — JE와 JZ](./rev-0067-je-jz.md)
- [REV-0068 — JNE와 JNZ](./rev-0068-jne-jnz.md)
- [REV-0066 — JMP: 무조건 분기](./rev-0066-jmp.md)
- [REV-0075 — CMOVcc: 분기 없는 조건부 이동](./rev-0075-cmovcc.md)
- [REV-0076 — SETcc: 조건 결과를 0 또는 1로 만들기](./rev-0076-setcc.md)
- [REV-0071 — CALL: 함수 호출](./rev-0071-call.md)
- [REV-0088 — 플래그 레지스터(EFLAGS) 개요](./rev-0088-flags-overview.md)
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교 (예정)

## 출처/검증
- `Jcc` 조건 코드 전체 표(SF/OF/ZF/CF 조합): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션의 공식 조건 표 기준 (2026-09-08 검증).
- CMP/SUB의 플래그 세팅 규칙(CF/OF/SF/ZF): 동 매뉴얼, "CMP—Compare Two Operands", "SUB—Subtract" 섹션 기준.
