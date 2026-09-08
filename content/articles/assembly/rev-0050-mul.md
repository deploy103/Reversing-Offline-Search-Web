---
id: REV-0050
title: "MUL: Unsigned 곱셈"
slug: "rev-0050-mul"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - mul
  - MUL
  - Mul
  - mul 명령어
  - mul instruction
  - unsigned multiply
  - unsigned 곱셈
  - 부호없는 곱셈
  - "mul ebx"
  - "mul rbx"
  - "mul ecx"
  - "mul byte ptr"
  - "mul dword ptr"
  - "mul qword ptr"
  - AX = AL * r/m8
  - DX:AX
  - EDX:EAX
  - RDX:RAX
  - 레지스터 페어
  - register pair
  - 더블워드 결과
  - 곱셈 결과 두 레지스터
  - CF OF undefined
  - MUL 플래그
  - size_t 곱셈
  - unsigned int 곱셈
  - overflow 곱셈
  - EDX에 값이 들어감
  - RDX에 값이 들어감
  - 곱셈 오버플로우
aliases:
  - mul 뭐임
  - mul이 뭐죠
  - mul 명령
  - MUL 명령어
  - 뮬 명령어
  - 곱셈 명령어
  - imul이랑 mul 차이
  - mul과 imul 차이
  - edx에 이상한 값이
symptom_keywords:
  - 곱셈 결과가 이상해요
  - edx에 이상한 값이 들어있어요
  - rdx에 값이 왜 있는지 모르겠음
  - 곱셈했는데 eax만 보면 값이 틀려요
  - mul 명령 결과가 어디 저장되는지 모르겠음
  - 부호없는 곱셈이 뭔지 모르겠음
  - 곱셈 명령어가 왜 오퍼랜드가 하나뿐인지
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`MUL`은 "AL/AX/EAX/RAX에 들어있는 값과 오퍼랜드로 지정한 값을 **부호없는(unsigned)** 정수로 곱한 뒤, 그 결과를 **두 배 크기의 레지스터 쌍**(AX, DX:AX, EDX:EAX, RDX:RAX)에 저장하는" 명령어다.

## 언제 검색해야 하나
- 어셈블리에 `mul ebx`, `mul ecx`, `mul qword ptr [rax]`처럼 오퍼랜드가 하나뿐인 곱셈 명령이 나오는데 결과가 어디 저장되는지 모를 때
- `mul` 실행 직후에 `EAX`만 확인했는데 값이 이상하고, `EDX`에도 값이 들어있는 걸 발견했을 때 ("edx에 이상한 값이 들어있어요")
- `MUL`과 `IMUL`을 언제 구분해서 써야 하는지 헷갈릴 때
- IDA/Ghidra 디컴파일에서 `(unsigned __int64)a * b` 같은 캐스팅이 왜 붙는지 궁금할 때
- 곱셈 명령 이후 플래그(CF, OF)가 어떤 조건에서 세팅되는지 확인해야 할 때

## 핵심 개념

### 오퍼랜드가 왜 하나뿐인가
`MUL`은 소스 오퍼랜드를 하나만 명시적으로 받는다. 나머지 하나는 **암묵적으로(implicit)** 항상 AL/AX/EAX/RAX에서 가져온다. 즉 "곱하는 대상 중 하나는 이미 정해진 레지스터에 있어야 한다"는 제약이 있다.

| 형태 | 암묵적 피연산자 | 명시적 오퍼랜드 | 결과 저장 위치 |
|---|---|---|---|
| `MUL r/m8`  | AL  | 8비트 레지스터/메모리  | **AX** (16비트) |
| `MUL r/m16` | AX  | 16비트 레지스터/메모리 | **DX:AX** (DX=상위16, AX=하위16) |
| `MUL r/m32` | EAX | 32비트 레지스터/메모리 | **EDX:EAX** (EDX=상위32, EAX=하위32) |
| `MUL r/m64` | RAX | 64비트 레지스터/메모리 | **RDX:RAX** (RDX=상위64, RAX=하위64) |

### 가장 중요한 함정: 결과는 "레지스터 하나"가 아니라 "레지스터 쌍"
초보자가 가장 많이 하는 실수는 `mul ebx` 실행 후 **EAX만** 확인하고 끝내는 것이다. 하지만 32비트 × 32비트 곱은 최대 64비트 크기가 나올 수 있으므로, MUL은 결과를 **EDX:EAX**라는 64비트 레지스터 쌍에 나눠 담는다. EAX에는 하위 32비트, EDX에는 상위 32비트가 들어간다.

구체적인 숫자로 보자:
```
EAX = 0x80000000   (10진수로 2,147,483,648)
EBX = 0x00000004   (10진수로 4)

mul ebx
; 진짜 결과 = 0x80000000 * 4 = 0x200000000  (10진수 8,589,934,592)
; 이 값은 32비트(EAX 하나)에 다 안 들어간다!

실행 후:
EAX = 0x00000000   ; 하위 32비트
EDX = 0x00000002   ; 상위 32비트  <- 여기에 "진짜 값의 나머지"가 들어있다
```
`EAX`만 보면 결과가 `0x00000000`, 즉 "곱셈했더니 0이 됐다"는 완전히 틀린 결론을 내리게 된다. 실제 값은 `EDX:EAX = 0x0000000200000000`이다. **MUL을 볼 때마다 습관적으로 EDX(또는 DX, RDX)도 같이 확인**해야 한다.

### 플래그: CF와 OF만 의미 있음, 나머지는 정의되지 않음
- **CF(Carry Flag)**와 **OF(Overflow Flag)**: 상위 절반 레지스터(AH, DX, EDX, RDX)가 **0이 아니면 SET(1)**, **0이면 CLEAR(0)**된다. 즉 "결과가 하위 절반만으로는 표현이 안 돼서 상위 절반까지 필요했다"는 뜻이 CF=1/OF=1이다.
  - 위 예제에서는 EDX=0x00000002로 0이 아니므로 CF=1, OF=1이 세팅된다.
- **SF, ZF, AF, PF**: Intel SDM에 "undefined(정의되지 않음)"라고 명시되어 있다. MUL 실행 직후 이 플래그들의 값에 의존하는 코드를 작성하거나, 리버싱 중에 이 플래그로 뭔가를 판단하려 하면 안 된다. 컴파일러도 이 플래그들을 신뢰하지 않는다.

### Unsigned 전용인 이유
MUL은 두 오퍼랜드를 **항상 부호없는 이진수**로 해석해서 곱한다. 만약 그 비트 패턴이 원래 음수(signed negative)를 의미하는 값이었다면, MUL은 그 사실을 전혀 모르고 "아주 큰 양수"로 취급해버린다.

예를 들어 `EAX = 0xFFFFFFFF`는 signed로 보면 `-1`이지만, unsigned로 보면 `4,294,967,295`(약 43억)이다.
```
EAX = 0xFFFFFFFF   ; signed로는 -1, unsigned로는 4294967295
EBX = 0x00000002   ; 2

mul ebx
; MUL은 무조건 unsigned로 계산: 4294967295 * 2 = 8589934590 = 0x1FFFFFFFE
; 결과: EDX = 0x00000001, EAX = 0xFFFFFFFE

; 만약 "-1 * 2 = -2"를 signed로 기대했다면 완전히 틀린 결과다.
; 이런 계산이 필요하면 MUL이 아니라 IMUL을 써야 한다 (REV-0051 참고).
```
그래서 컴파일러는 C 소스의 변수 타입이 `unsigned int`, `unsigned long`, `size_t`처럼 부호없는 타입일 때만 MUL을 생성하고, `int`나 `long`처럼 부호있는 타입이면 IMUL을 생성한다.

### 컴파일러 패턴
- `unsigned int a, b; unsigned long long r = (unsigned long long)a * b;` 처럼 **곱셈의 전체(더블워드) 결과가 실제로 필요한 경우**(오버플로우 검사, 해시 계산, 큰 수 연산 라이브러리 등) MUL이 그대로 나타난다.
- 배열 인덱스 계산(`array[i]`)에서 `i`의 타입이 `size_t`(unsigned)이고 원소 크기를 곱해야 할 때도 MUL 또는 IMUL이 쓰일 수 있다(어느 쪽을 쓰는지는 컴파일러/최적화 수준에 따라 다르지만, 상위 절반이 버려져도 되는 상황이면 컴파일러가 더 값싼 IMUL 2-오퍼랜드 형태나 LEA/SHL로 대체하는 경우가 많다 — REV-0051 참고).
- 순수하게 "오버플로우 여부까지 정확히 검사해야 하는 unsigned 곱셈"에서는 MUL 다음에 CF를 검사하는 `jc`/`jnc` 분기가 바로 따라오는 패턴이 흔하다.

### IDA/Ghidra 디컴파일 표현
- 상위 절반(EDX/RDX)을 코드가 실제로 사용하지 않으면, 디컴파일러는 그냥 `a * b`처럼 단순하게 보여준다.
- 상위 절반을 사용하면(예: 64비트 전체 결과가 필요한 경우) `(unsigned __int64)a * b` 같은 명시적 캐스팅이 붙거나, 결과를 `__int128`/구조체 형태로 표현하기도 한다.
- IDA 구버전 의사코드에서는 상·하위 32비트를 각각 꺼내는 매크로로 `HIDWORD(result)`, `LODWORD(result)` 형태가 보이기도 한다. 이는 "이 곱셈의 상위 32비트를 실제로 쓰고 있다"는 신호이므로, 그 값이 나중에 어디에 쓰이는지(오버플로우 체크? 다음 계산의 입력?) 추적할 가치가 있다.

### 리버싱에서의 의의
- MUL을 보면 그 순간 "이 값은 unsigned로 다뤄지고 있다"는 확실한 타입 단서를 얻는다. 변수의 원래 C 타입을 추정할 때 매우 유용하다.
- EDX(또는 DX, RDX)가 이후 코드에서 실제로 읽히는지 확인하면, 이 곱셈이 "단순 곱"인지 "오버플로우까지 신경 쓰는 안전한 곱셈"인지 구분할 수 있다.
- CF/OF를 검사하는 분기가 MUL 바로 뒤에 있으면, 그 코드는 정수 오버플로우를 방어하는 로직(예: `malloc(n * size)` 앞의 오버플로우 체크)일 가능성이 높다 — 취약점 분석에서 중요한 패턴이다.

## 화면/코드에서 보이는 징후
- `mul ebx`, `mul ecx`, `mul r8d` — 오퍼랜드가 하나뿐인 곱셈, 결과는 EDX:EAX
- `mul byte ptr [rbp-1]` — 메모리에서 8비트 값을 읽어 AL과 곱함, 결과는 AX
- `mul` 직후 `jc`/`jnc`(Jump if Carry) 분기 — 오버플로우 체크 패턴
- `mul` 직후 EDX/RDX를 다른 레지스터로 옮기거나 스택에 저장 — 상위 절반을 실제로 쓰는 코드
- `mul` 직후 EAX만 쓰고 EDX를 안 건드림 — 상위 절반을 버리는(오버플로우를 신경 안 쓰는) 단순 곱셈

## 가장 먼저 할 것
1. 오퍼랜드가 몇 비트인지 확인 (r/m8, 16, 32, 64) → 결과가 어느 레지스터 쌍에 들어가는지 결정
2. MUL 실행 직후 EDX/RDX(또는 DX, AH)를 반드시 같이 확인 — EAX/AX만 보지 않기
3. 이 값이 음수(signed)로 쓰일 여지가 있는 변수인지 확인 — 만약 그렇다면 실제로는 IMUL이어야 정상이므로, 코드/디스어셈블리를 다시 확인
4. MUL 직후 CF/OF를 검사하는 분기가 있는지 확인 (오버플로우 방어 로직 여부)

## 단계별 절차

**1) 결과 레지스터 쌍 식별**
```asm
mul ecx        ; EAX(암묵) * ECX(명시) -> EDX:EAX
```
오퍼랜드가 32비트(ECX)이므로 암묵적 피연산자는 EAX, 결과는 EDX:EAX 64비트 쌍.

**2) EDX가 실제로 0이 아닐 수 있는지 손으로 계산**
```
EAX = 0x0000_1000  (4096)
ECX = 0x0010_0000  (1,048,576)
진짜 곱 = 4096 * 1,048,576 = 4,294,967,296 = 0x1_0000_0000
```
32비트 하나로는 표현 불가 → EDX=0x00000001, EAX=0x00000000이 될 것을 예상할 수 있다. 디버거에서 실제로 확인해서 검증한다.

**3) 플래그 확인**
`mul` 직후 CF, OF를 확인한다 (x64dbg/IDA 디버거 Flags 창). 위 예제처럼 EDX가 0이 아니면 CF=1, OF=1이어야 정상이다.

**4) 다음 코드에서 EDX 사용 여부 추적**
```asm
mul ebx
jc  overflow_error   ; CF=1이면(EDX!=0) 오버플로우 처리로 분기
mov [result], eax    ; 정상 범위면 EAX만 저장
```
이런 패턴이면 "곱셈 결과가 32비트를 넘지 않는지 검사하는 안전한 곱셈"이라고 해석한다.

## 명령어/단축키
- IDA: 레지스터 값은 디버거 사용 중 Registers 창에서 EAX/EDX(또는 RAX/RDX) 동시 확인, `F5`로 디컴파일해서 캐스팅(`unsigned __int64` 등) 확인
- x64dbg: 우측 레지스터 패널에서 RAX/RDX, EFLAGS의 CF/OF 비트 확인, `F7`(Step In)/`F8`(Step Over)로 MUL 한 줄씩 실행
- GDB/Pwndbg: `info registers rax rdx eflags` 또는 `p/x $rax`, `p/x $rdx`로 값 확인, `nexti`로 한 줄 실행 후 비교

## 출력 해석
- 디버거에서 MUL 실행 직후 `EDX = 0x00000000`이면 결과가 32비트 안에 완전히 들어갔다는 뜻(CF=OF=0). `EDX`가 0이 아니면 결과가 64비트 전체를 차지한다는 뜻(CF=OF=1).
- IDA 의사코드에서 `(unsigned __int64)a * b`처럼 명시적 unsigned 캐스팅이 보이면, 원본 C 코드도 unsigned 타입으로 계산했을 가능성이 매우 높다.
- GDB에서 `p/x $rax`, `p/x $rdx`를 나란히 찍어보면 두 값을 이어붙인 것이 실제 64비트(또는 128비트) 결과라는 것을 눈으로 확인할 수 있다.

## 흔한 실수
- **MUL 실행 후 EAX/AX만 확인하고 EDX/DX를 무시하는 것** — 결과가 상위 절반까지 걸쳐 있으면 EAX만으로는 틀린 값을 읽게 된다. 가장 흔하고 가장 위험한 실수다.
- **MUL을 signed 값에 그대로 쓰는 것** — MUL은 항상 unsigned로 계산하므로, 음수 비트 패턴(`0xFFFFFFFF` 등)을 아주 큰 양수로 곱해버려 완전히 다른 결과가 나온다. signed 곱셈이 필요하면 IMUL을 써야 한다.
- **MUL 직후 SF/ZF/AF/PF를 보고 조건을 판단하는 것** — 이 플래그들은 정의되지 않은(undefined) 값이라 신뢰할 수 없다. 오직 CF/OF만 의미가 있다.
- MUL이 오퍼랜드를 하나만 받는 것을 보고 "두 번째 피연산자가 없다"고 착각하는 것 — 두 번째 피연산자는 항상 AL/AX/EAX/RAX에 암묵적으로 존재한다.

## 막혔을 때 다음 체크
- 곱셈 결과가 이상하다면 → EDX/RDX(또는 DX, AH)도 같이 확인했는지부터 점검.
- 음수가 섞인 계산인데 결과가 이상하다면 → 실제로는 MUL이 아니라 IMUL이어야 하는 상황은 아닌지, 혹은 애초에 이 값이 unsigned로 설계된 게 맞는지 원본 로직을 재검토.
- MUL 다음에 분기가 있는데 의미를 모르겠다면 → CF를 검사하는 `jc`/`jnc`인지 확인 (REV-0088 플래그 개요 참고), 오버플로우 방어 코드일 가능성.
- 두 배 크기 결과가 왜 필요한지 모르겠다면 → 이후 코드에서 EDX/RDX가 어디로 옮겨지고 어떤 계산에 쓰이는지 xref처럼 손으로 따라가본다.

## 미니 예제

**예제 1 — 32비트 MUL, EDX에 값이 남는 경우**
```c
// 원본 C 코드 (unsigned)
unsigned int a = 0x80000000;
unsigned int b = 4;
unsigned long long r = (unsigned long long)a * b;
```
```asm
mov     eax, 80000000h
mov     ebx, 4
mul     ebx            ; EDX:EAX = EAX * EBX
; 결과: EAX = 0x00000000, EDX = 0x00000002
; 즉 r = 0x0000000200000000 (8,589,934,592)
```

**예제 2 — 8비트 MUL, 결과는 AX**
```c
unsigned char a = 200;
unsigned char b = 200;
unsigned short r = (unsigned short)a * b;  // 40000, 8비트 두 개 곱이 8비트를 넘어감
```
```asm
mov     al, 0C8h        ; 200
mov     bl, 0C8h        ; 200
mul     bl              ; AX = AL * BL
; 결과: AX = 0x9C40 (40,000) - AH에 상위 바이트, AL에 하위 바이트가 걸쳐 있음
```

**예제 3 — 흔한 실수: EAX만 보고 틀린 결론 내리기**
```asm
mov     eax, 0FFFFFFFFh   ; 4,294,967,295 (unsigned)
mov     ecx, 2
mul     ecx               ; EDX:EAX = EAX * ECX = 8,589,934,590
; 결과: EAX = 0xFFFFFFFE, EDX = 0x00000001
```
여기서 초보자가 `EAX = 0xFFFFFFFE`만 보고 "곱셈 결과는 0xFFFFFFFE(약 43억)"이라고 결론내리면 틀린다. 진짜 결과는 `EDX:EAX = 0x00000001FFFFFFFE`(8,589,934,590)이다.

**예제 4 — 오버플로우 체크 패턴 (CF 검사)**
```c
unsigned int n, size;
if (n > SIZE_MAX / size) { /* 오버플로우 방지 */ }
void *p = malloc((size_t)n * size);
```
```asm
mov     eax, n
mul     size            ; EDX:EAX = n * size
jc      overflow_error  ; CF=1 이면(EDX!=0, 즉 32비트를 넘음) 오버플로우로 분기
push    eax             ; 안전하면 곱셈 결과(하위 32비트)만 malloc에 전달
call    malloc
```

## 관련 글
- [REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴](./rev-0051-imul.md)
- [REV-0052 — DIV: Unsigned 나눗셈](./rev-0052-div.md)
- [REV-0053 — IDIV: Signed 나눗셈](./rev-0053-idiv.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가 (예정)
- REV-0061 — SHL과 SAL: 왼쪽 시프트 (예정)
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교 (예정)

## 출처/검증
- MUL 명령어 동작, 오퍼랜드 형태, 플래그(CF/OF 설정 조건, SF/ZF/AF/PF undefined): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "MUL—Unsigned Multiply" 섹션 기준 (2026-09-08 검증).
- IDA/Ghidra 의사코드에서의 unsigned 곱셈 캐스팅 표현: Hex-Rays/Ghidra 디컴파일러 일반 동작 관례 기준.
