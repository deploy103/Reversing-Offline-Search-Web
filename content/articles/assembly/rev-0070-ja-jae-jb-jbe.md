---
id: REV-0070
title: "JA JAE JB JBE: Unsigned 비교 분기"
slug: "rev-0070-ja-jae-jb-jbe"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - ja
  - JA
  - jae
  - JAE
  - jb
  - JB
  - jbe
  - JBE
  - jnbe
  - JNBE
  - jnb
  - JNB
  - jnae
  - JNAE
  - jna
  - JNA
  - jc
  - JC
  - jnc
  - JNC
  - unsigned 비교
  - unsigned comparison
  - 부호 없는 비교
  - CF
  - carry flag
  - cmp ja
  - cmp jb
  - size_t 비교
  - 배열 경계 검사
  - array bounds check
  - integer underflow
  - 정수 언더플로우
  - signed vs unsigned
aliases:
  - ja 뭐임
  - jb 플래그
  - jae 조건
  - jbe 조건
  - unsigned 점프
  - 부호없는 분기
  - ja jb 차이
  - ja랑 jg 차이
symptom_keywords:
  - ja랑 jg 헷갈림
  - signed unsigned 비교 헷갈림
  - 음수가 매우 큰 값으로 보임
  - 배열 경계 체크 우회
  - 크기 체크가 이상함
  - CF 플래그 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`JA`/`JAE`/`JB`/`JBE`는 직전 `CMP`(또는 `SUB`) 결과를 **unsigned(부호 없는) 정수**로 해석해서 크다/크거나 같다/작다/작거나 같다를 판단해 분기하는 명령이다. 이 계열은 CF(Carry Flag) 하나만 본다 — SF/OF 조합을 보는 signed 계열([REV-0069](./rev-0069-jg-jge-jl-jle.md))보다 규칙은 단순하지만, 같은 비트 패턴에 대해 signed 계열과 정반대의 분기 결과를 낼 수 있다.

> 이 글의 signed 버전은 [REV-0069 — JG JGE JL JLE](./rev-0069-jg-jge-jl-jle.md)를 함께 읽어라. 이 두 글은 "같은 CMP 한 줄이 signed로 보느냐 unsigned로 보느냐에 따라 정반대로 분기할 수 있다"는 것을 보여주는 짝이며, **이 차이를 못 짚는 것이 CTF에서 가장 흔하게 문제를 놓치는 원인**이다.

## 언제 검색해야 하나
- 어셈블리에 `ja`, `jae`, `jb`, `jbe`가 나오는데 각각 어떤 플래그를 보는지 모를 때
- 배열 인덱스나 버퍼 크기 검사 코드(`cmp idx, size` / `jae fail`)를 분석 중일 때
- `size_t`/`unsigned int` 뺄셈 결과가 이상하게 큰 값이 되는(언더플로우) 상황을 의심할 때
- "ja랑 jg 차이가 뭐냐"처럼 signed/unsigned 분기 계열이 헷갈릴 때
- 정수 부호 버그(길이 체크 우회 등) 관련 CTF 문제를 분석 중일 때

## 핵심 개념

### 니모닉과 별칭
`JAE`와 `JB`는 각각 세 가지 이름을 가진다 — 전부 opcode가 같은 완전히 동일한 명령이다.

| 니모닉 | 동일 니모닉 | 의미 |
|---|---|---|
| `JA` | `JNBE` (Jump if Not Below or Equal) | unsigned 크다 (above) |
| `JAE` | `JNB`, `JNC` (Jump if Not Below / Not Carry) | unsigned 크거나 같다 (above or equal) |
| `JB` | `JNAE`, `JC` (Jump if Not Above or Equal / Jump if Carry) | unsigned 작다 (below) |
| `JBE` | `JNA` (Jump if Not Above) | unsigned 작거나 같다 (below or equal) |

`JC`/`JNC`("jump if carry"/"jump if not carry")는 `CMP` 뒤뿐 아니라 `ADD`/`SUB` 직후 **unsigned 오버플로우/언더플로우(자리올림/빌림) 여부만 확인하고 싶을 때**도 일반적으로 쓰인다 — 꼭 "비교" 문맥이 아니어도 등장한다는 점을 기억해두면 좋다.

### Intel SDM 전체 Jcc 조건 표
아래는 Intel SDM이 정의하는 조건 코드 전체 표다. 이 글에서 다루는 4개는 굵게 표시된 부분(unsigned 계열)이고, `G/GE/L/LE`(signed 계열)는 [REV-0069](./rev-0069-jg-jge-jl-jle.md)에서 다룬다.

| 접미사 | 다른 표기 | 테스트하는 플래그 조건 | 의미 |
|---|---|---|---|
| E / Z | — | ZF = 1 | equal / zero |
| NE / NZ | — | ZF = 0 | not equal / not zero |
| G / NLE | — | ZF = 0 AND SF = OF | signed greater |
| GE / NL | — | SF = OF | signed greater or equal |
| L / NGE | — | SF ≠ OF | signed less |
| LE / NG | — | ZF = 1 OR SF ≠ OF | signed less or equal |
| **A / NBE** | — | **CF = 0 AND ZF = 0** | **unsigned above** |
| **AE / NB / NC** | — | **CF = 0** | **unsigned above or equal** |
| **B / NAE / C** | — | **CF = 1** | **unsigned below** |
| **BE / NA** | — | **CF = 1 OR ZF = 1** | **unsigned below or equal** |
| S | — | SF = 1 | sign (negative) |
| NS | — | SF = 0 | not sign |
| O | — | OF = 1 | overflow |
| NO | — | OF = 0 | no overflow |
| P / PE | — | PF = 1 | parity even |
| NP / PO | — | PF = 0 | parity odd |

### 각 조건을 하나씩 정확히

| 명령 | 플래그 조건 | 뜻 |
|---|---|---|
| `JA` (`JNBE`) | **CF = 0 AND ZF = 0** | 빌림 없음 & 같지 않음 → a > b |
| `JAE` (`JNB`/`JNC`) | **CF = 0** | 빌림 없음 → a ≥ b |
| `JB` (`JNAE`/`JC`) | **CF = 1** | 빌림 있음 → a < b |
| `JBE` (`JNA`) | **CF = 1 OR ZF = 1** | 빌림 있거나 같음 → a ≤ b |

### 왜 CF 하나만 보면 되는가 — signed 계열과의 대비
`CMP a, b`는 `a - b`를 계산한다. `CF`는 이 뺄셈에서 **unsigned 관점의 빌림(borrow)** 여부를 나타내는 플래그다: `a`를 unsigned 값으로 봤을 때 `a`가 `b`보다 작으면 뺄셈 과정에서 최상위 비트 밖에서 빌려와야 하므로 `CF = 1`이 세팅되고, `a`가 `b`보다 크거나 같으면 빌릴 필요가 없으므로 `CF = 0`이다. 이건 "a와 b를 unsigned로 봤을 때 대소관계가 어떤가"를 CF 하나가 직접적으로 말해주는 것이라, [REV-0069](./rev-0069-jg-jge-jl-jle.md)의 signed 계열처럼 오버플로우를 보정하기 위해 두 플래그(SF, OF)를 조합할 필요가 없다.

**정리**: unsigned 비교는 `CF` 하나만 보면 되므로 signed 비교(`SF`와 `OF`를 함께 봐야 함)보다 오히려 규칙이 단순하다. 다만 이 단순함이 역설적으로 실수를 유발하기도 한다 — 아래 "흔한 실수" 참고.

### 0xFFFFFFFF vs 1 — unsigned로 해석했을 때
```asm
mov eax, 0FFFFFFFFh   ; eax = 0xFFFFFFFF
cmp eax, 1            ; 내부적으로 eax - 1 을 계산해 플래그만 세팅 (eax 값 자체는 안 바뀜)
```
`CMP`는 `0xFFFFFFFF - 1 = 0xFFFFFFFE`를 계산하면서 플래그를 다음처럼 세팅한다:
- `CF = 0` (unsigned 뺄셈에서 borrow 없음 — 0xFFFFFFFF는 unsigned로 1보다 크므로 안 빌림)
- `ZF = 0` (결과가 0이 아님)
- `SF = 1` (결과 0xFFFFFFFE의 최상위 비트가 1)
- `OF = 0` (signed 뺄셈 관점에서 오버플로우 없음: -1 - 1 = -2, 정상 범위)

이제 이 값을 **unsigned로 해석**하면 eax는 `4294967295`, 비교 대상은 `1`이다. `4294967295 > 1`이므로 `JA`(`CF=0 AND ZF=0`: `0=0 AND 0=0` → 참)가 **분기하고**, `JB`(`CF=1`: 거짓)는 분기하지 않는다.

[REV-0069](./rev-0069-jg-jge-jl-jle.md)(JG/JL 글)에서는 이 **완전히 동일한 CMP 명령**을 signed로 해석해서 정반대의 결론(`JL`이 분기함, `-1 < 1`)을 냈다. 같은 비트, 같은 CMP, 정반대 분기 — 그 차이는 오직 그 다음에 붙는 Jcc가 signed 계열(`JG`/`JL`)인지 unsigned 계열(`JA`/`JB`)인지에 달려 있다.

### Intel 문법과 오퍼랜드
```
JA  rel8/rel32
JAE rel8/rel32
JB  rel8/rel32
JBE rel8/rel32
```
오퍼랜드는 하나, 현재 RIP 기준 상대 오프셋이다.

### 플래그: 읽기만 하고 바꾸지 않는다
- **읽는 플래그**: `CF` (`JA`/`JBE`는 `ZF`도 함께 읽음)
- **바꾸는 플래그**: 없음. 직전 `CMP`/`SUB`/`TEST`가 세팅해 둔 플래그를 읽기만 한다.

### 스택/RIP 변화
조건이 참이면 `RIP`가 target 주소로 바뀌고, 거짓이면 다음 명령으로 진행한다. `RSP`는 건드리지 않는다.

### 컴파일러 패턴 — unsigned 변수의 `if`
```c
unsigned int a, b;
if (a > b) { ... }
```
```asm
cmp eax, ebx
ja  true_branch   ; unsigned above
```
[REV-0069](./rev-0069-jg-jge-jl-jle.md)에서 본 것과 똑같이 생긴 `if (a > b)`라도, 변수가 `unsigned int`로 선언되어 있으면 `ja`가 나오고 `int`였다면 `jg`가 나온다 — 변수 선언의 signedness가 최종 어셈블리를 완전히 바꾼다.

**포인터 비교는 항상 unsigned다.** 예를 들어 `if (ptr1 > ptr2)`처럼 C에서 포인터를 `>`로 비교하면, 포인터가 문법적으로 signed/unsigned 표시가 없더라도 주소값 자체가 본질적으로 부호 없는 값이므로 컴파일러는 항상 `JA`/`JAE`/`JB`/`JBE` 계열을 생성한다.

배열 경계/버퍼 크기 검사는 이 계열이 가장 흔하게 나타나는 자리다:
```c
if (idx >= size) goto out_of_bounds;   // idx, size가 size_t/unsigned
```
```asm
cmp  eax, [size]
jae  out_of_bounds   ; idx >= size (unsigned)
```

### IDA/Ghidra 디컴파일 결과에서 보이는 모습
디컴파일러가 어떤 변수를 `unsigned int`/`size_t`나 포인터 타입으로 표시하면서, 그 배경의 디스어셈블리가 실제로 `JA`/`JAE`/`JB`/`JBE` 니모닉을 쓰고 있다면 그 비교가 진짜 unsigned라는 것이 확인된 것이다. 반대로 디컴파일러가 평범한 `int`로 표시했는데 디스어셈블리에는 실제로 `ja`/`jb` 계열이 쓰여 있다면, **디스어셈블리 쪽을 신뢰**해야 한다 — 니모닉이 원본 컴파일 결과에 대한 최종 근거이고, 디컴파일러의 타입 이름은 그 위에 얹힌 휴리스틱 추측일 뿐이다. 확인 방법은 IDA에서 `Space`를 눌러 디스어셈블리로 전환한 뒤 해당 `CMP`+`Jcc` 쌍의 정확한 철자를 읽는 것이다.

### 리버싱에서의 의미
이 계열은 **unsigned 뺄셈 언더플로우(integer underflow)** 버그가 사는 자리다. 예를 들어:
```c
size_t len, offset;   // 둘 다 unsigned
if (len - offset > buf_size) { error(); }
```
만약 `len < offset`이면 `len - offset`은 수학적으로 음수지만 `size_t`(unsigned)에서는 **엄청나게 큰 값으로 wrap-around**한다 — 예를 들어 `len=5, offset=10`이면 `5 - 10`은 32비트 unsigned에서 `0xFFFFFFFB`(4294967291)가 된다. 이 wrap-around된 값을 그 다음 `JA`/`JB` 경계 검사가 어떻게 다루느냐에 따라, 체크를 통과시켜서는 안 되는 상황을 오히려 통과시키거나(체크 방향에 따라) 반대로 정상 입력을 거부하는 등 예상치 못한 동작이 나온다. 이는 실제 CVE에서도 반복적으로 나타나는 매우 흔한 패턴이고, CTF에서도 자주 등장하는 취약점 유형이다.

또한 `cmp idx, size` / `jae out_of_bounds` 같은 형태는 **배열 경계 검사**의 표준 패턴이므로, 이 패턴을 눈에 익혀두면 바이너리에서 경계 검사가 어디 있는지(혹은 아예 빠져 있는지) 빠르게 찾을 수 있다.

## 화면/코드에서 보이는 징후
- `cmp eax, ebx` 바로 다음에 `ja`, `jae`, `jb`, `jbe` 중 하나
- `cmp idx, [size]` / `jae`(또는 `jb`) 형태의 배열 경계 검사
- 대체 니모닉 `jnbe`, `jnb`/`jnc`, `jnae`/`jc`, `jna`
- 디컴파일 결과에서 `unsigned int`, `size_t`, 포인터 타입에 대한 `if (a > b)` 형태
- `sub`(뺄셈) 직후 결과를 `size_t`/`unsigned`로 계속 사용하는 코드 — 언더플로우 의심 지점

## 가장 먼저 할 것
1. `Jcc` 바로 위의 `CMP`(또는 `SUB`)가 어떤 두 값을 비교하는지 확인한다.
2. 니모닉이 `A`/`AE`/`B`/`BE`(unsigned) 계열인지 `G`/`GE`/`L`/`LE`(signed) 계열인지 정확히 읽는다.
3. 비교 대상이 절대 음수가 될 수 없는 값(길이, 크기, 인덱스, 포인터)인지 확인하고, 그 값이 뺄셈으로 계산된 것이라면 언더플로우 가능성을 의심한다.
4. 필요하면 손으로 CF를 계산해 분기 여부를 검증한다.

## 단계별 절차

**1) CMP+JA로 `if (a > b)` 해석하기**
```asm
mov  eax, [a]
cmp  eax, [b]
ja   greater_branch
```
→ `a`(unsigned)가 `b`(unsigned)보다 크면 분기. C로는 `if (a > b)` (a, b는 unsigned).

**2) 배열 경계 검사 읽기**
```asm
cmp  eax, [size]     ; eax = idx
jae  out_of_bounds    ; idx >= size 이면 실패 처리로 분기
```
→ `if (idx >= size) goto out_of_bounds;`

**3) 언더플로우 위험 코드 읽기**
```asm
mov  eax, [len]
sub  eax, [offset]    ; len - offset, 결과가 unsigned로 wrap될 수 있음
cmp  eax, [buf_size]
ja   error             ; len-offset이 wrap돼서 매우 커지면 이 체크에 걸림 (의도했든 안 했든)
```
→ `len < offset`인 입력을 넣으면 `eax`가 거대한 값이 되어 `ja error`가 예상외로 항상 참이 될 수 있다 — 혹은 체크 방향이 반대라면 오히려 위험한 큰 크기가 통과해버릴 수도 있다. 실제 취약점 여부는 체크 방향과 그 뒤에 이 값이 어떻게 쓰이는지 함께 봐야 한다.

**4) 0xFFFFFFFF vs 1, unsigned 해석 검증**
```asm
mov eax, 0FFFFFFFFh
cmp eax, 1
ja  huge_value    ; CF=0 AND ZF=0 -> 참 -> 분기함 (4294967295 > 1)
```

## 명령어/단축키
- IDA: `Space`(디스어셈블리 전환), `F5`(디컴파일), 조건 분기 화살표로 흐름 확인
- x64dbg: Flags 창에서 `CF` 값 직접 확인
- GDB/Pwndbg: `info registers eflags` 또는 `p $eflags`로 확인

## 출력 해석
- x64dbg/GDB 플래그 창에서 `CF=0`이면 `JAE` 참, `CF=1`이면 `JB` 참
- IDA 그래프 뷰의 True/False 분기 화살표로 어느 쪽이 조건 성립인지 확인

## 흔한 실수
- **JA(unsigned)와 JG(signed)를 혼동하는 것 — 이것이 CTF에서 가장 흔한 실수다.** unsigned 비교(`JA`/`JAE`/`JB`/`JBE`)는 `CF`만 본다 — signed 비교처럼 `SF`/`OF` 조합을 볼 필요가 없다. 반대로 이 단순함 때문에 signed 값을 실수로 unsigned로 비교(또는 그 반대)하면 음수가 "매우 큰 양수"로 둔갑해서 크기 검사를 통과해버리는 취약점이 생긴다.

  구체적인 우회 방향을 정확히 짚으면: 음수(signed로는 작은 값)를 unsigned로 해석하면 항상 매우 큰 값이 된다. 그래서 `if ((unsigned)len > MAX)` 처럼 **unsigned 체크**를 쓰는 코드에 음수 `len`을 넣으면, 그 음수가 거대한 unsigned 값(예: `0xFFFFFFFF` = 4294967295)으로 보여서 오히려 이 상한 체크에 **걸려버려 통과하지 못한다** — 즉 이 방향에서는 unsigned 체크가 음수 입력을 잘 막아준다. 문제는 **반대 방향**이다: 원래 unsigned 값을 다뤄야 하는데 코드가 실수로 **signed 체크**(`jg`/`jl`)를 써버린 경우, 거대한 unsigned 값(예: `0xFFFFFFFF`)이 signed로는 `-1`(음수)로 보이기 때문에 `if (len > MAX)` 같은 signed 상한 체크를 "음수라서 크지 않다"는 이유로 **통과해버릴 수 있다**. 즉 취약점은 "signed 값을 unsigned로 착각"할 때가 아니라, "원래 unsigned여야 할 크기 값을 signed 비교로 잘못 검사"할 때 주로 발생한다 — 항상 어느 쪽 타입/비교가 실제 코드에 쓰였는지 니모닉으로 확인해야 한다.
- `JAE`(`JNB`)와 `JGE`가 영어로는 둘 다 "크거나 같다"처럼 들려서 같은 걸로 착각하는 것 — `JAE`는 `CF=0`, `JGE`는 `SF=OF`로 완전히 다른 플래그를 본다.
- 뺄셈 결과를 그대로 unsigned로 계속 사용하면서 언더플로우 가능성을 놓치는 것 — `sub`/`cmp` 조합을 볼 때마다 "이 뺄셈이 음수가 될 수 있는가"를 항상 의심한다.
- 디컴파일러의 타입 표시를 무조건 신뢰하는 것 — 실제 근거는 디스어셈블리의 `Jcc` 니모닉이다.

## 막혔을 때 다음 체크
- 분기 방향이 예상과 반대로 보인다면 → 니모닉이 A/B 계열인지 G/L 계열인지 Space로 디스어셈블리에서 재확인
- CF 값이 헷갈리면 → 디버거로 직접 플래그 레지스터 확인
- `sub` 뒤에 이상하게 큰 값이 나온다면 → 언더플로우(wrap-around) 가능성부터 의심
- 배열 경계 검사가 안 보인다면 → 검사가 아예 빠져있거나(취약점), 다른 함수/매크로에서 이미 처리됐을 수 있으니 호출 전후 코드까지 넓게 확인

## 미니 예제

**예제 1 — 두 unsigned 값 비교**
```c
unsigned int a = 5, b = 3;
if (a > b) puts("a is bigger");
```
```asm
mov  eax, 5
cmp  eax, 3       ; CF=0 (5 unsigned >= 3, 안 빌림), ZF=0
ja   is_bigger    ; CF=0 AND ZF=0 -> 참, 분기함
```

**예제 2 — 배열 경계 검사**
```c
if (idx >= size) return -1;   // idx, size는 size_t
```
```asm
cmp  eax, [size]
jae  bounds_fail    ; CF=0 -> idx >= size -> 참이면 분기
```

**예제 3 — 언더플로우 위험**
```asm
mov  eax, [len]      ; len = 5
sub  eax, [offset]   ; offset = 10 -> eax = 0xFFFFFFFB (wrap, unsigned로 매우 큰 값)
cmp  eax, [buf_size]
ja   reject           ; wrap된 큰 값 때문에 거의 항상 참이 되어버림
```

**예제 4 — 0xFFFFFFFF vs 1, unsigned 해석**
```asm
mov eax, 0FFFFFFFFh   ; eax = 0xFFFFFFFF (unsigned로는 4294967295)
cmp eax, 1
ja  huge_value          ; CF=0 AND ZF=0 -> 참 -> 분기함 (4294967295 > 1, 맞는 결론)
jb  never_taken          ; CF=1 -> 거짓 -> 분기 안 함
```

## 관련 글
- [REV-0069 — JG JGE JL JLE: Signed 비교 분기](./rev-0069-jg-jge-jl-jle.md) — 같은 CMP를 signed로 해석하는 짝 글, 반드시 함께 읽을 것
- [REV-0067 — JE와 JZ](./rev-0067-je-jz.md)
- [REV-0068 — JNE와 JNZ](./rev-0068-jne-jnz.md)
- [REV-0066 — JMP: 무조건 분기](./rev-0066-jmp.md)
- [REV-0075 — CMOVcc: 분기 없는 조건부 이동](./rev-0075-cmovcc.md)
- [REV-0076 — SETcc: 조건 결과를 0 또는 1로 만들기](./rev-0076-setcc.md)
- [REV-0071 — CALL: 함수 호출](./rev-0071-call.md)
- [REV-0088 — 플래그 레지스터(EFLAGS) 개요](./rev-0088-flags-overview.md)
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교

## 출처/검증
- `Jcc` 조건 코드 전체 표(CF/ZF 조합): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션의 공식 조건 표 기준 (2026-09-08 검증).
- CMP/SUB의 CF(빌림) 세팅 규칙: 동 매뉴얼, "CMP—Compare Two Operands", "SUB—Subtract" 섹션 기준.
