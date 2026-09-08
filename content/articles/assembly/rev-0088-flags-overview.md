---
id: REV-0088
title: "플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기"
slug: "rev-0088-flags-overview"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - EFLAGS
  - RFLAGS
  - flags register
  - 플래그 레지스터
  - CF
  - ZF
  - SF
  - OF
  - PF
  - AF
  - carry flag
  - zero flag
  - sign flag
  - overflow flag
  - parity flag
  - auxiliary carry flag
  - 캐리 플래그
  - 제로 플래그
  - 사인 플래그
  - 오버플로우 플래그
  - 패리티 플래그
  - JE
  - JZ
  - JNE
  - JNZ
  - JG
  - JGE
  - JL
  - JLE
  - JA
  - JAE
  - JB
  - JBE
  - JS
  - JNS
  - JO
  - JNO
  - JP
  - JNP
  - JC
  - JNC
  - JNAE
  - JNBE
  - JNA
  - JNB
  - SETcc
  - CMOVcc
  - 조건부 분기
  - signed unsigned 비교
  - 부호있는 비교
  - 부호없는 비교
  - Jcc 조건
  - 조건 점프
aliases:
  - 플래그가 뭔가요
  - cf zf sf of 차이
  - jg랑 ja 차이가 뭐죠
  - 플래그 레지스터 뭐임
  - signed unsigned 점프 차이
  - jl이랑 jb 차이
  - 오버플로우 플래그가 뭔지
  - 캐리 플래그가 뭔지
  - 플래그 비트 읽는법
  - 조건 점프 플래그 정리
symptom_keywords:
  - signed unsigned 비교가 헷갈려요
  - jg jl 헷갈림
  - 왜 ja를 쓰는지 모르겠음
  - 오버플로우 플래그가 뭔지 모르겠음
  - cmp 다음에 무슨 점프가 오는지 모르겠음
  - sf만 보고 음수인지 판단해도 되나요
  - setcc가 뭔지 모르겠음
  - cmovcc가 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CPU에는 `EFLAGS`(x86, 32비트) / `RFLAGS`(x64, 하위 32비트가 EFLAGS와 동일하게 쓰임)라는 특수 레지스터가 있고, 그 안의 개별 비트인 `CF`(캐리) `ZF`(제로) `SF`(사인) `OF`(오버플로우) `PF`(패리티) 등이 직전 연산 결과의 성질을 기록한다. 모든 조건 분기(`Jcc`), 조건부 값 설정(`SETcc`), 조건부 이동(`CMOVcc`)은 이 비트들의 조합을 검사해서 동작을 결정하며, 이 매핑을 외우면 디스어셈블리의 `if`/`while`/비교 연산자를 손으로 직접 읽을 수 있게 된다.

## 언제 검색해야 하나
- `cmp eax, ebx` 다음에 `jg`가 왜 오는지, `ja`가 왜 오는지 차이를 모를 때
- `jl`과 `jb`가 둘 다 "작으면 점프"인데 뭐가 다른지 헷갈릴 때
- IDA/Ghidra 디컴파일에서 `if (a > b)`로 보이는 코드가 원본 어셈블리에서는 `SF`, `OF`를 비교하는 이상한 조건으로 보일 때
- 값 하나가 `0xFFFFFFFF`처럼 "크게도, 음수로도" 보일 수 있는 상황에서 실제로 어느 쪽으로 분기하는지 확신이 안 설 때
- `sete al`, `cmovl eax, ebx` 같은 `SETcc`/`CMOVcc` 명령을 처음 봤을 때
- "signed unsigned 비교가 헷갈려요", "jg jl 헷갈림" 같은 증상으로 검색해서 들어온 경우

## 핵심 개념

### EFLAGS/RFLAGS란 무엇인가
`EFLAGS`는 EAX, EBX 같은 범용 레지스터가 아니라, 각 **비트 하나하나가 독립적인 참/거짓 정보**를 담는 특수 레지스터다. x64에서는 `RFLAGS`라는 64비트 레지스터가 있지만 실제로 쓰이는 비트는 EFLAGS와 동일한 하위 32비트뿐이고 상위 비트는 예약되어 있다. 그래서 실전에서는 그냥 "EFLAGS"라고 불러도 무방하다.

일반 레지스터처럼 `mov eax, eflags` 같은 명령으로 직접 값을 읽어올 수는 없다. 대신:
- `PUSHF`/`POPF` ([REV-0046](./rev-0046-pushf-popf.md), 예정) 명령으로 스택을 거쳐 통째로 저장/복원할 수 있고,
- 디버거(IDA 디버거, x64dbg, GDB/Pwndbg)는 레지스터 창에 `CF=0 ZF=1 SF=0 OF=0 PF=1 ...` 형태로 각 플래그를 이름으로 직접 보여준다.

가장 중요한 사실: **거의 모든 산술/논리/비교 명령은 실행될 때마다 이 플래그들을 자동으로 갱신한다.** 프로그래머가 명시적으로 손대지 않아도 `ADD`, `SUB`, `CMP`, `AND`, `TEST` 같은 명령을 실행하는 순간 CPU가 알아서 플래그를 세팅하고, 바로 다음에 오는 `Jcc`/`SETcc`/`CMOVcc`가 그 플래그를 읽어서 동작을 결정한다.

### 플래그 하나씩 뜯어보기

#### CF (Carry Flag, 캐리 플래그)
**의미**: 부호 없는(unsigned) 연산에서 결과가 넘쳤을 때 1이 된다. 덧셈이면 최상위 비트에서 자리올림(carry out)이 발생했을 때, 뺄셈이면 빌림(borrow)이 필요했을 때 1이 된다.

**예시**:
```asm
mov al, 0xFF     ; AL = 255 (unsigned로 보면 8비트 최댓값)
add al, 0x01     ; 255 + 1 = 256, 그런데 AL은 8비트라 담을 수 없음
                 ; 결과: AL = 0x00, CF = 1  (8비트를 벗어나는 자리올림 발생)
```
`255 + 1`은 unsigned 8비트 범위(0~255)를 벗어나므로 CF가 1이 된다. **CF는 오직 unsigned 연산의 오버플로우/언더플로우만 신경 쓴다** — 이 점이 뒤에서 나올 OF와의 결정적인 차이다.

주의할 특이 케이스: `INC`와 `DEC`는 예외적으로 **CF를 절대 건드리지 않는다** (자세한 이유는 [REV-0049 — INC와 DEC](./rev-0049-inc-dec.md) 참고). 그래서 반복문 카운터에 CF가 이미 어떤 다른 이유로 세팅되어 있었다면, `INC`/`DEC`를 실행해도 그 값이 그대로 유지된다.

CF는 `ADC`(Add with Carry), `SBB`(Subtract with Borrow) 명령이 여러 워드짜리(예: 64비트를 넘는 128비트) 큰수 연산을 이어붙일 때 "이전 자리에서 넘어온 캐리"를 전달하는 용도로도 쓰이고, `SHL`/`SHR`/`SAR`/`ROL`/`ROR` 같은 시프트/로테이트 명령에서는 "밀려나간 마지막 비트"가 CF에 저장된다.

#### ZF (Zero Flag, 제로 플래그)
**의미**: 연산 결과가 정확히 0일 때 1이 된다. signed든 unsigned든 상관없이 그냥 "결과 비트 패턴이 전부 0인가"만 본다.

**예시**:
```asm
mov eax, 5
cmp eax, 5      ; 내부적으로 eax - 5 = 0 을 계산 (eax 값 자체는 안 바뀜)
                ; 결과: ZF = 1
```
`CMP`는 내부적으로 뺄셈을 수행하지만 그 결과를 레지스터에 저장하지 않고 플래그만 갱신한다 ([REV-0060 — CMP](./rev-0060-cmp.md), 예정). ZF는 "두 값이 같은가"를 확인하는 가장 흔한 질문(`==`, `!=`)에 직결되기 때문에 실전에서 가장 자주 검사되는 플래그다 (`JE`/`JZ`, `JNE`/`JNZ`).

#### SF (Sign Flag, 사인 플래그)
**의미**: 결과의 최상위 비트(MSB)를 그대로 복사한 값이다. 8비트면 bit 7, 32비트면 bit 31, 64비트면 bit 63. 즉 "결과의 비트 패턴이 2의 보수로 봤을 때 음수처럼 생겼는가"만 기계적으로 반영할 뿐, 그 연산이 원래 signed였는지 unsigned였는지는 전혀 신경 쓰지 않는다.

**예시**:
```asm
mov eax, 0x80000000
sub eax, 0        ; 결과 = 0x80000000, 최상위 비트(bit 31) = 1
                  ; SF = 1
```
이 값이 프로그래머 입장에서 unsigned 변수였더라도(즉 실제로는 2,147,483,648이라는 "큰 양수"였더라도) SF는 그저 최상위 비트가 1이라는 사실만 보고 1이 된다.

**여기가 이 글에서 가장 중요한 함정이다**: **SF 하나만 보고 "이 결과는 음수다"라고 판단하면 안 된다.** signed 오버플로우가 발생한 상황에서는 SF가 진짜 부호를 거짓으로 알려주기 때문이다. 진짜 부호를 알려면 SF와 OF를 **함께** 봐야 한다 — 이건 아래 "Jcc 매핑" 절에서 실제 숫자로 증명한다.

#### OF (Overflow Flag, 오버플로우 플래그)
**의미**: signed(부호 있는) 연산에서 결과가 그 크기의 signed 표현 범위를 벗어났을 때 1이 된다. 예를 들어 "양수 + 양수인데 결과가 음수처럼 나옴" 또는 "음수 + 음수인데 결과가 양수처럼 나옴" 같은, signed 수학적으로 있을 수 없는 결과가 나왔을 때 CPU가 "이 결과는 못 믿는다"는 신호로 세운다.

**예시 (CF와의 결정적 대조)**:
```asm
mov al, 0x7F     ; AL = 127 (8비트 signed 최댓값)
add al, 0x01     ; 127 + 1 = 128
                 ; 결과: AL = 0x80
```
이 한 줄로 두 플래그를 동시에 계산해보자:
- **CF 관점(unsigned)**: `127 + 1 = 128`. unsigned 8비트 범위는 0~255이므로 128은 전혀 문제없이 담긴다. → **CF = 0**
- **OF 관점(signed)**: `127 + 1`을 signed 8비트로 보면 결과가 `0x80`인데, 이는 2의 보수로 `-128`이다. "양수(127) + 양수(1) = 음수(-128)"라는 것은 signed 수학에서 불가능한 결과이므로 → **OF = 1**

즉 **같은 연산, 같은 비트 패턴 결과인데 CF=0이고 OF=1**이다. 이것이 "unsigned 오버플로우"와 "signed 오버플로우"가 서로 완전히 다른 신호라는 것을 보여주는 가장 명확한 예시다. CF는 unsigned 세계의 오버플로우 감시자, OF는 signed 세계의 오버플로우 감시자라고 기억하면 된다.

#### PF (Parity Flag, 패리티 플래그)
**의미**: 결과값의 **최하위 1바이트**에 들어있는 1비트의 개수가 짝수개면 1, 홀수개면 0이 된다. 8080 시절부터 내려온 레거시 플래그로, 현대 x64 리버싱에서 의도적으로 쓰이는 경우는 매우 드물다(가끔 난독화된 코드나 오래된 시리얼 검증 루틴에서 발견될 수 있다).

**예시**:
```asm
mov al, 0x03     ; 0b00000011 → 1비트가 2개 (짝수개)
test al, al      ; PF = 1 (짝수 개수)
```

#### AF (Auxiliary Carry Flag) — 참고만
bit 3과 bit 4 사이의 자리올림/빌림을 기록하는 플래그로, `DAA`/`DAS`/`AAA`/`AAS` 같은 레거시 BCD(2진화 10진수) 명령에서만 쓰인다. 현대 x64 바이너리 리버싱에서는 사실상 볼 일이 없으므로, "존재는 한다" 정도만 알아두고 무시해도 된다.

### 어떤 명령어가 어떤 플래그를 바꾸는가

| 명령어 | 영향받는 플래그 | 비고 |
|---|---|---|
| `ADD`, `SUB`, `CMP`, `ADC`, `SBB`, `NEG` | CF, OF, SF, ZF, AF, PF 전부 | 표준 산술 연산 |
| `INC`, `DEC` | OF, SF, ZF, AF, PF (**CF는 그대로 유지**) | 루프 카운터에서 CF 보존이 중요 |
| `AND`, `OR`, `XOR`, `TEST`, `NOT` | SF, ZF, PF 세팅 / **CF=0, OF=0으로 강제 클리어** | `NOT`은 플래그를 아예 바꾸지 않음 |
| `MUL`, `IMUL` | CF, OF만 의미 있음 (상위 절반이 0/부호 확장인지 여부) / SF, ZF, AF, PF는 **정의되지 않음(undefined)** | [REV-0050 — MUL](./rev-0050-mul.md), [REV-0051 — IMUL](./rev-0051-imul.md) |
| `DIV`, `IDIV` | **모든 플래그가 정의되지 않음(undefined)** | [REV-0052 — DIV](./rev-0052-div.md), [REV-0053 — IDIV](./rev-0053-idiv.md) |
| `SHL`/`SAL`, `SHR`, `SAR`, `ROL`, `ROR` | CF = 마지막으로 밀려난 비트 / OF는 1비트 시프트일 때만 의미 있음 | 예정: REV-0061~REV-0065 |

관련 산술 명령어 각각의 전체 설명은 [REV-0047 — ADD](./rev-0047-add.md), [REV-0048 — SUB](./rev-0048-sub.md), [REV-0049 — INC와 DEC](./rev-0049-inc-dec.md), [REV-0054 — NEG](./rev-0054-neg.md) 참고. `AND`/`OR`/`XOR`/`NOT`/`TEST`(REV-0055~REV-0059), `CMP`(REV-0060), `SHL`/`SAL`/`SHR`/`SAR`/`ROL`/`ROR`(REV-0061~REV-0065)는 모두 예정.

### 핵심: 플래그 조합 → Jcc / SETcc / CMOVcc 매핑표

모든 `Jcc`(조건 분기)는 `SETcc`(조건에 따라 레지스터를 0/1로 설정)와 `CMOVcc`(조건에 따라 값을 이동)로 그대로 대응되는 형제 명령이 있다. 셋 다 **정확히 같은 플래그 조건**을 검사한다.

**단일 플래그만 보는 것들:**

| 플래그 조건 | Jcc | SETcc | CMOVcc | 의미 |
|---|---|---|---|---|
| ZF=1 | `JE`/`JZ` | `SETE`/`SETZ` | `CMOVE`/`CMOVZ` | 같다(==) / 결과가 0 |
| ZF=0 | `JNE`/`JNZ` | `SETNE` | `CMOVNE` | 다르다(!=) / 결과가 0 아님 |
| SF=1 | `JS` | `SETS` | `CMOVS` | 결과의 최상위 비트가 1 |
| SF=0 | `JNS` | `SETNS` | `CMOVNS` | 결과의 최상위 비트가 0 |
| CF=1 | `JC`/`JB`/`JNAE` | `SETC`/`SETB` | `CMOVC`/`CMOVB` | 캐리 발생 |
| CF=0 | `JNC`/`JAE`/`JNB` | `SETNC`/`SETAE` | `CMOVNC`/`CMOVAE` | 캐리 없음 |
| OF=1 | `JO` | `SETO` | `CMOVO` | signed 오버플로우 발생 |
| OF=0 | `JNO` | `SETNO` | `CMOVNO` | signed 오버플로우 없음 |
| PF=1 | `JP`/`JPE` | `SETP` | `CMOVP` | 짝수 패리티 |
| PF=0 | `JNP`/`JPO` | `SETNP` | `CMOVNP` | 홀수 패리티 |

**`CMP a, b` (내부적으로 a - b 계산) 다음에 쓰는 비교용 — unsigned:**

| 조건 | 의미 | Jcc | 플래그 조건 |
|---|---|---|---|
| a > b | above (unsigned 초과) | `JA`/`JNBE` | CF=0 **AND** ZF=0 |
| a >= b | above or equal | `JAE`/`JNB` | CF=0 |
| a < b | below (unsigned 미만) | `JB`/`JNAE` | CF=1 |
| a <= b | below or equal | `JBE`/`JNA` | CF=1 **OR** ZF=1 |

**`CMP a, b` 다음에 쓰는 비교용 — signed:**

| 조건 | 의미 | Jcc | 플래그 조건 |
|---|---|---|---|
| a > b | greater (signed 초과) | `JG`/`JNLE` | ZF=0 **AND** SF=OF |
| a >= b | greater or equal | `JGE`/`JNL` | SF=OF |
| a < b | less (signed 미만) | `JL`/`JNGE` | SF≠OF |
| a <= b | less or equal | `JLE`/`JNG` | ZF=1 **OR** SF≠OF |

**외우는 요령**: 영문 알파벳으로 구분된다. **A/B(Above/Below)로 시작하는 계열은 전부 unsigned이고 CF를 검사**하고, **G/L(Greater/Less)로 시작하는 계열은 전부 signed이고 SF와 OF의 관계를 검사**한다.

### 왜 "SF = OF"가 "크거나 같다"를 의미하는가 (핵심 원리)

이 규칙이 직관적으로 이해가 안 되는 게 정상이다. 원리는 이렇다:

- **오버플로우가 없었다면(OF=0)**: `a - b`의 결과 비트 패턴이 진짜 수학적으로 옳은 값이므로, SF를 그대로 믿을 수 있다. SF=0이면 결과가 0 이상이라는 뜻이므로 `a >= b`. 그래서 OF=0일 때는 "SF=0"이 곧 "크거나 같다"이고, 이는 "SF와 OF가 둘 다 0이라 같다(SF=OF)"와 동치다.
- **오버플로우가 있었다면(OF=1)**: 진짜 결과가 signed 범위를 벗어나서 부호 비트가 "거짓말"을 하고 있는 상태다. 이때는 SF가 뒤집혀서 보이므로, 반대로 해석해야 진짜 답이 나온다. OF=1일 때 SF=1이면 실제로는 결과가 양수(즉 `a >= b`)였다는 뜻이고, 이 역시 "SF와 OF가 둘 다 1이라 같다(SF=OF)"와 동치다.

즉 오버플로우가 있든 없든, **"SF와 OF가 같은 값이면 진짜 결과는 0 이상"**이라는 규칙이 항상 성립한다. 그래서 `JGE`(signed >=)는 정확히 `SF=OF` 하나만 검사하면 된다.

**직접 손으로 검증하는 예제 (8비트 signed, 오버플로우 발생 케이스):**

`a = -100`, `b = 100`을 8비트로 비교한다고 하자. `-100`은 2의 보수로 `0x9C`, `100`은 `0x64`다.

```asm
mov al, 0x9C   ; al = -100 (signed로 해석 시)
cmp al, 0x64   ; al - 0x64 = 0x9C - 0x64 = 0x38 (56)
```

수학적으로 진짜 답은 `-100 - 100 = -200`인데, 이는 8비트 signed 범위(`-128`~`127`)를 벗어난다 → **OF = 1**.

실제 계산된 결과 비트 패턴은 `0x38`(십진수 56), 최상위 비트(bit 7)가 0이므로 → **SF = 0**.

여기서 `SF(0) ≠ OF(1)`이므로 `JL`(SF≠OF) 조건이 참이 되어 "less than" 분기가 선택된다. 결과 비트 패턴만 보면 `0x38`은 "양수처럼" 보여서 얼핏 `a > b`처럼 착각하기 쉽지만, OF=1이라는 신호 덕분에 CPU는 이 부호 비트를 믿지 않고 뒤집어서 해석하여 **정확하게 `-100 < 100`이라는 진짜 답**을 낸다. 이것이 SF 하나만 보면 안 되고 SF와 OF를 함께 봐야 하는 이유다.

### JG vs JA, JL vs JB — 같은 비트를 놓고 완전히 다른 답을 낼 수 있다

`0xFFFFFFFF`(32비트)와 `1`을 비교하는 상황을 보자.

```asm
mov eax, 0FFFFFFFFh
cmp eax, 1        ; eax - 1 = 0xFFFFFFFE
```

이 하나의 `CMP`로 완전히 상반된 두 가지 결론이 동시에 성립한다:
- **signed로 해석하면**: `0xFFFFFFFF`는 `-1`이다. `-1 < 1`이므로 **`JL`이 선택되어야 맞다** (실제로 SF=1, OF=0이라 SF≠OF → JL 조건 성립).
- **unsigned로 해석하면**: `0xFFFFFFFF`는 `4294967295`라는 매우 큰 수다. `4294967295 > 1`이므로 **`JA`가 선택되어야 맞다** (실제로 CF=0, ZF=0 → JA 조건 성립).

**같은 비교, 같은 CMP, 같은 플래그 값 집합인데, 어떤 Jcc를 골랐는지에 따라 정반대의 분기가 나온다.** 컴파일러는 원본 C 변수가 `int`(signed)였는지 `unsigned int`였는지에 따라 처음부터 `JL`을 쓸지 `JA`를 쓸지 결정해서 코드를 생성해 놓는다. 그래서 리버싱할 때는 **이미 박혀 있는 Jcc 니모닉을 보고 거꾸로 원본 변수의 부호 여부를 추론**할 수 있다 — 이건 [REV-0052 — DIV](./rev-0052-div.md)/[REV-0053 — IDIV](./rev-0053-idiv.md)에서 나오는 "CDQ가 있으면 signed, `xor edx,edx`면 unsigned" 휴리스틱과 완전히 같은 원리다.

**정리**: `CMP` 뒤에 `JA`/`JAE`/`JB`/`JBE`가 오면 → 원본 변수는 unsigned였다. `JG`/`JGE`/`JL`/`JLE`가 오면 → 원본 변수는 signed(int)였다. 이건 스트립된 바이너리에서 변수 타입을 복원할 때 매우 강력한 단서다.

## 화면/코드에서 보이는 징후
- `cmp eax, ebx` 바로 다음 줄에 `jg`, `jl`, `jge`, `jle` 중 하나가 온다 → signed 비교
- `cmp eax, ebx` 바로 다음 줄에 `ja`, `jb`, `jae`, `jbe` 중 하나가 온다 → unsigned 비교
- `test eax, eax` 다음에 `jz`/`je` (0인지 검사) 또는 `js` (부호 비트만 검사) — [REV-0059 TEST](./rev-0059-test.md), 예정
- `sete al`, `setl al`, `setg al` 같은 명령이 `cmp` 직후에 등장 — boolean 반환값(`bool`, `int` 0/1)을 만드는 코드
- `cmovl eax, ebx`, `cmovge eax, ecx` 같은 명령 — 분기 없이 조건을 처리하는 최적화 코드(삼항 연산자 `?:`가 이렇게 컴파일되는 경우가 많음)
- IDA/Ghidra 디컴파일에서 `if (a > b)`인데 원본 어셈블리는 `SF`/`OF` 비교처럼 보임 → signed 비교였다는 뜻

## 가장 먼저 할 것
`Jcc`/`SETcc`/`CMOVcc`를 만나면 순서대로 확인한다:
1. 바로 위에 어떤 명령이 있었는가 (`CMP`, `TEST`, `SUB`, 아니면 다른 산술 명령인가) — 그 명령이 지금 보는 플래그를 만들었다.
2. 그 니모닉이 `A/B` 계열인가 `G/L` 계열인가, 아니면 `E/Z`, `S`, `O`, `C`, `P` 단일 플래그 계열인가.
3. `A/B` 계열이면 unsigned 비교, `G/L` 계열이면 signed 비교임을 확정한다.
4. 위 매핑표에서 정확한 플래그 조건을 찾아 실제 값(디버거의 레지스터 창)과 대조해본다.

## 단계별 절차

**1) 디버거에서 플래그 직접 확인하기**

x64dbg나 IDA 디버거의 레지스터 창에는 `EFLAGS` 옆에 `C 0  Z 1  S 0  O 0  P 1  A 0` 처럼 각 플래그가 0/1로 나열된다. `CMP`나 `ADD` 한 줄을 실행(F7/F8 step)한 직후 이 값이 어떻게 바뀌는지 직접 관찰하면 매핑표를 몸으로 익힐 수 있다.

```
(gdb) i r eflags
eflags         0x246               [ PF ZF IF ]
```
GDB/Pwndbg에서는 `info registers eflags` 또는 `i r eflags`로 확인하면 세팅된 플래그 이름만 대괄호 안에 나열해서 보여준다. 위 예시는 PF와 ZF가 1이라는 뜻이다.

**2) 소스 CMP와 다음 Jcc를 짝지어 읽기**

```asm
cmp eax, 10
jg  greater_branch
```
→ `CMP`가 `eax - 10`을 계산하고 ZF, SF, OF, CF를 세팅한다. `JG`는 `ZF=0 AND SF=OF`를 검사한다. 즉 이 코드는 `if (eax > 10) goto greater_branch;`를 signed로 비교한 것이다.

**3) A/B 계열이면 unsigned, G/L 계열이면 signed로 원본 타입을 역추론**

```asm
cmp ecx, 0
jb  handle_negative_as_error   ; unsigned 관점에서 "0보다 작다"는 불가능하지만
                                ; 컴파일러가 unsigned 변수에 대해 이런 비교를 넣는 경우
                                ; ecx가 unsigned 타입임을 알려주는 강한 단서
```

**4) SETcc/CMOVcc는 Jcc와 똑같은 조건표로 해석**

```asm
cmp eax, ebx
setg al        ; al = (eax > ebx) ? 1 : 0   (signed)
```
Jcc 대신 SETcc/CMOVcc가 나와도 당황하지 말고 위 매핑표에서 같은 접미사(`G`, `L`, `A`, `B`, `E` 등)를 찾아 동일한 플래그 조건을 적용하면 된다.

## 명령어/단축키
- IDA/x64dbg 레지스터 창: EFLAGS 옆에 각 플래그가 개별 체크박스/글자로 표시됨 (더블클릭하면 값을 직접 토글할 수도 있음 — 조건 분기를 강제로 바꿔서 실행해보는 패치 없는 임시 우회 트릭으로 쓰이기도 함)
- GDB/Pwndbg: `info registers eflags` (`i r eflags`) — 세팅된 플래그 이름 목록으로 표시
- Pwndbg: `context` 실행 시 레지스터 영역에 플래그가 자동으로 색깔 강조되어 표시됨
- IDA: 명령어 위에서 `Shift+F5`(범용) 대신, `Alt+G`로 그래프 뷰에서 조건 분기의 True/False 방향을 시각적으로 색깔(초록/빨강)로 구분해서 볼 수 있음

## 출력 해석
- 디버거에서 `CF=0 ZF=1 SF=0 OF=0`처럼 보이면, 방금 실행된 명령의 결과가 "0이고, 음수가 아니며, 오버플로우도 캐리도 없었다"는 뜻 — 전형적인 "두 값이 정확히 같다"는 CMP 결과다.
- `SF=1, OF=1`처럼 SF와 OF가 **같은 값**이면 (`SF=OF`) → signed 비교에서 "크거나 같다"(`JGE`)가 참이 되는 상태.
- `SF=0, OF=1`처럼 SF와 OF가 **다른 값**이면 (`SF≠OF`) → signed 비교에서 "작다"(`JL`)가 참이 되는 상태. 이때 SF만 보면 "양수 결과"처럼 착각하기 쉬우니 항상 OF를 같이 확인한다.
- 디컴파일러(IDA F5, Ghidra)는 이 플래그 조합을 이미 해석해서 `if (a > b)`, `if (a >= b)` 같은 고수준 조건으로 보여준다 — 원본 어셈블리를 볼 필요 없이 디컴파일 결과의 비교 연산자와 변수 타입(`int` vs `unsigned int`)만 봐도 같은 정보를 얻을 수 있지만, 디컴파일이 실패하거나 이상하게 나올 때는 이 절의 매핑표로 직접 원본 어셈블리를 읽어야 한다.

## 흔한 실수
- **`JG`와 `JA`가 "영어로는 둘 다 크다는 뜻이니 같은 거겠지"라고 착각하는 것** — `0xFFFFFFFF`와 `1`을 비교하는 예시에서 봤듯, signed로는 `JL`(작다)이 맞고 unsigned로는 `JA`(크다)가 맞다. 완전히 반대 결론이 나올 수 있다. 반드시 니모닉이 A/B 계열인지 G/L 계열인지부터 구분해야 한다.
- **SF 하나만 보고 "이 결과는 음수다"라고 단정하는 것** — signed 오버플로우가 발생하면 SF가 진짜 부호를 거짓으로 보여준다. 항상 OF와 함께 판단해야 한다(`SF=OF`인지 `SF≠OF`인지).
- **TEST와 CMP가 피연산자 값을 바꾼다고 착각하는 것** — 둘 다 내부적으로 연산(AND, SUB)을 수행하지만 그 결과를 어디에도 저장하지 않고 **플래그만** 갱신한다. `test eax, eax`는 `eax`가 0인지(`ZF`) 또는 음수인지(`SF`)만 검사하는 매우 흔한 관용구다.
- **MUL/IMUL, DIV/IDIV 직후에 ZF나 SF를 믿고 분기 코드를 분석하는 것** — 곱셈은 CF/OF만 의미가 있고 나머지는 undefined, 나눗셈은 전체 플래그가 undefined다. 컴파일러도 이 사실을 알기 때문에 곱셈/나눗셈 직후 바로 조건 분기가 오는 경우는 거의 없고, 대개 별도의 `CMP`나 `TEST`가 먼저 삽입된다.

## 막혔을 때 다음 체크
- 어떤 Jcc를 봐도 표에서 못 찾겠다면 → 니모닉 전체를 다시 읽어본다. `JNAE`, `JNBE`, `JNGE`, `JNLE`처럼 `N` 접두사 + 반대말 조합으로 된 별칭들이 많다(예: `JNAE`는 `JB`와 완전히 동일한 명령의 다른 이름일 뿐이다). 어셈블러/디스어셈블러가 어느 이름을 표시하느냐는 도구마다 다를 수 있다.
- CMP와 Jcc 사이에 다른 명령이 끼어있어서 플래그가 이미 덮어써진 것 같다면 → CMP 바로 다음 줄이 Jcc가 맞는지, 혹은 컴파일러가 사이에 플래그를 보존하는 명령(예: `LEA`, `MOV` — 이들은 플래그를 바꾸지 않음)만 넣었는지 확인한다. `LEA`와 `MOV`는 플래그를 전혀 건드리지 않으므로 안전하게 건너뛰어도 된다.
- 원본 변수가 signed인지 unsigned인지 여전히 헷갈리면 → 같은 함수 안에서 이 변수에 대해 쓰인 다른 Jcc들을 모두 모아서 계열이 일관되게 A/B인지 G/L인지 확인한다.
- 디컴파일 결과와 어셈블리가 다르게 보인다면 → 디컴파일러가 타입을 잘못 추론했을 가능성이 있으니, 원본 어셈블리의 Jcc 계열을 최종 근거로 삼는다.

## 미니 예제

**예제 1 — signed 비교가 컴파일되는 방식**
```c
int a, b;
if (a > b) {
    do_something();
}
```
```asm
cmp eax, ebx      ; a - b 계산, ZF/SF/OF 세팅
jle skip          ; a <= b 이면(ZF=1 OR SF≠OF) 건너뜀
call do_something
skip:
```

**예제 2 — 같은 비트, 정반대 결론 (0xFFFFFFFF vs 1)**
```asm
mov eax, 0FFFFFFFFh
cmp eax, 1
jl  is_negative     ; signed로 보면 -1 < 1 이므로 여기로 분기 (SF≠OF)
; ja  is_larger      ; 만약 코드가 unsigned였다면 이 니모닉이 대신 쓰였을 것 (CF=0, ZF=0)
```
같은 `cmp eax, 1` 한 줄이지만, 컴파일러가 `eax`를 `int`로 선언했느냐 `unsigned int`로 선언했느냐에 따라 `jl`이 나올지 `ja`가 나올지가 결정된다.

**예제 3 — SETcc로 bool 값 만들기**
```c
bool eq = (a == b);
```
```asm
cmp  eax, ebx
sete al           ; al = (ZF==1) ? 1 : 0
movzx eax, al     ; 상위 바이트 0으로 확장 (REV-0040 참고)
```

**예제 4 — CMOVcc로 분기 없는 max 만들기**
```c
int max(int a, int b) {
    return (a < b) ? b : a;
}
```
```asm
; eax = a, ebx = b 라고 가정
cmp  eax, ebx
cmovl eax, ebx   ; SF≠OF (즉 a < b)이면 eax에 ebx 값을 덮어씀 → eax = max(a,b)
```
`cmovl`은 조건이 거짓이면 아무 일도 하지 않고 `eax`를 그대로 둔다 — 분기(`Jcc`)가 아예 없으므로 CPU의 분기 예측 실패 페널티가 없다. 이런 패턴은 삼항 연산자나 단순 `if-else` 대입문에서 컴파일러 최적화로 흔히 나타난다.

## 관련 글
- [REV-0047 — ADD: 덧셈과 플래그](./rev-0047-add.md)
- [REV-0048 — SUB: 뺄셈과 플래그](./rev-0048-sub.md)
- [REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의](./rev-0049-inc-dec.md)
- [REV-0050 — MUL: Unsigned 곱셈](./rev-0050-mul.md)
- [REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴](./rev-0051-imul.md)
- [REV-0052 — DIV: Unsigned 나눗셈](./rev-0052-div.md)
- [REV-0053 — IDIV: Signed 나눗셈](./rev-0053-idiv.md)
- [REV-0054 — NEG: 2의 보수 음수 만들기](./rev-0054-neg.md)
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0055~REV-0058 — AND, OR, XOR, NOT (예정)
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0061~REV-0065 — SHL/SAL, SHR, SAR, ROL, ROR (예정)
- REV-0066 — JMP: 무조건 분기
- REV-0067~REV-0070 — JE/JZ, JNE/JNZ, JG/JGE/JL/JLE, JA/JAE/JB/JBE 각 Jcc 계열 상세 (예정)
- REV-0075 — CMOVcc: 분기 없는 조건부 이동
- REV-0076 — SETcc: 조건 결과를 0 또는 1로 만들기

## 출처/검증
- EFLAGS/RFLAGS 레지스터 구조와 각 비트 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, "3.4.3 EFLAGS Register" 섹션 기준 (2026-09-08 검증).
- 산술/논리 명령별 플래그 영향(Flags Affected): Intel SDM Volume 2A/2B, 각 명령어(`ADD`, `SUB`, `CMP`, `INC`, `DEC`, `AND`, `OR`, `XOR`, `TEST`, `MUL`, `IMUL`, `DIV`, `IDIV`) 개별 레퍼런스 페이지의 "Flags Affected" 절 기준.
- `Jcc`/`SETcc`/`CMOVcc` 조건 코드와 대응 플래그 조합표: Intel SDM Volume 2A, "Jcc—Jump if Condition Is Met", "SETcc—Set Byte on Condition", "CMOVcc—Conditional Move" 섹션의 조건 코드(tttn) 표 기준.
