---
id: REV-0042
title: "LEA: 주소 계산인데 왜 산술 연산처럼 보이는가"
slug: "rev-0042-lea"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - lea
  - LEA
  - Lea
  - lea instruction
  - lea 명령어
  - "lea rax [rbx+rcx*4]"
  - "lea rax, [rbx+rcx*4]"
  - "lea eax, [eax+eax*2]"
  - "lea rdi, [rip+0x2000]"
  - load effective address
  - 유효 주소 로드
  - 주소 계산
  - 산술 연산으로 쓰이는 lea
  - lea 곱셈
  - lea 트릭
  - scale index base
  - SIB
  - RIP relative lea
aliases:
  - lea 뭐임
  - lea가 뭐죠
  - lea 명령
  - LEA 명령어
  - lea랑 mov 차이
  - lea와 mov 차이
  - 주소 로드 명령어
symptom_keywords:
  - lea인데 왜 곱셈처럼 쓰이는지 모르겠음
  - lea가 메모리를 읽는건지 헷갈림
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LEA dst, [mem]`은 `[...]` 안의 **주소 계산 결과 값 자체**를 dst 레지스터에 넣는 명령어다. `[...]`가 메모리를 나타내는 문법처럼 생겼지만 **실제로 메모리를 읽지 않는다** — 그래서 컴파일러는 이걸 곱셈/덧셈 대신 산술 연산 트릭으로도 즐겨 쓴다.

## 언제 검색해야 하나
- `lea rax, [rbx+rcx*4]`처럼 `[...]` 문법인데 `mov`가 아니라 `lea`인 코드를 만났을 때
- LEA가 실제로 메모리에서 값을 읽어오는 건지, 아니면 주소만 계산하는 건지 헷갈릴 때
- `lea eax, [eax+eax*2]`처럼 곱셈도 덧셈도 안 나온 코드인데 컴파일러가 곱셈을 이렇게 표현한 걸 이해하고 싶을 때
- `lea rdi, [rip+0x2f10]` 같은 RIP 상대 주소 계산을 문자열/전역변수 참조로 해석해야 할 때

## 핵심 개념

### LEA와 MOV의 결정적 차이
`mov eax, [rbx]`는 RBX가 **가리키는 메모리 위치를 실제로 읽어서** 그 값을 EAX에 넣는다(역참조, dereference).
`lea eax, [rbx]`는 `[rbx]`라는 **주소 계산식 자체의 결과값**(이 경우 그냥 RBX 값)을 EAX에 넣는다 — **메모리 접근이 전혀 일어나지 않는다.**

C로 비유하면:
```c
int *p = ...;
int  a = *p;      // mov: p가 가리키는 값을 읽음 (역참조)
int *b = p;        // lea: p라는 주소 자체를 복사 (역참조 없음, 정확히는 &(*p))
```
더 정확한 비유는 `lea reg, [expr]`이 `reg = &(expr)`과 같다는 것이다. 그래서 이름이 "Load **Effective Address**"(유효 주소 로드)다.

### 왜 산술 연산처럼 보이는가 — SIB(Scale-Index-Base) 인코딩 재활용
x86/x64의 메모리 주소 표현 문법은 `[base + index*scale + disp]` 형태를 하드웨어 차원에서 지원한다(scale은 1/2/4/8, disp는 상수 오프셋). 이건 원래 배열 인덱싱(`arr[i]`)이나 구조체 필드 접근(`obj+offset`)을 위한 문법이다. 그런데 이 계산 능력 자체가 "레지스터 하나 + 레지스터*배수 + 상수"를 **한 명령어로, 플래그도 안 건드리고** 계산해주는 훌륭한 산술 도구이기도 하다. 그래서 컴파일러는 메모리를 다룰 의도가 전혀 없어도 LEA를 곱셈/덧셈 대체용으로 자주 쓴다.
```asm
; int y = x * 3;  을 표현하는 전형적인 컴파일러 출력
lea eax, [rax+rax*2]   ; eax = rax + rax*2 = rax*3  (곱셈 명령어 IMUL 없이 계산)
```
```asm
; int z = a + b;
lea eax, [rax+rbx]      ; eax = rax + rbx (ADD 대신)
```
이런 트릭이 쓰이는 이유는 LEA가 ADD/IMUL보다 **더 빠르거나, 최소한 플래그를 건드리지 않아서 다른 코드에 영향을 안 주기 때문**이다(현대 CPU에서 LEA는 보통 1사이클, 포트 활용도 더 유리한 경우가 많다).

### 오퍼랜드 형태
```
LEA dst, [base]
LEA dst, [base + disp]
LEA dst, [base + index*scale]
LEA dst, [base + index*scale + disp]
LEA dst, [rip + disp]          ; x64 RIP 상대 주소
```
- scale은 반드시 1, 2, 4, 8 중 하나만 가능(각각 byte/word/dword/qword 배열 원소 크기에 대응).
- dst는 항상 레지스터(메모리가 될 수 없다) — LEA는 항상 "레지스터 ← 주소 계산식"이다.
- `[...]` 안에 어떤 크기 지정자(`byte ptr` 등)도 필요 없다 — 메모리를 읽지 않으므로 크기가 의미 없다.

### 플래그
`LEA`는 **플래그를 전혀 바꾸지 않는다.** 이 점이 산술 연산(ADD, IMUL 등) 대신 LEA를 쓰는 핵심 이유 중 하나다 — 컴파일러가 플래그를 아직 건드리면 안 되는 자리에서 값을 계산해야 할 때 안전하게 쓸 수 있다.

### 배열/구조체 접근에서의 진짜 쓰임
LEA의 원래 목적대로, 배열 원소의 **주소**(값이 아니라)를 구할 때도 자주 쓰인다:
```c
int arr[10];
int *p = &arr[3];
```
```asm
lea rax, [rbx+0Ch]   ; rax = &arr[3]  (arr 시작주소 + 3*4바이트 = +12)
```
포인터를 함수 인자로 넘기기 직전(`lea rdi, [rbp-0x20]`처럼 지역 변수의 주소를 구해서 인자로 넘기는 패턴)에도 매우 흔하게 나온다.

### RIP 상대 주소와 문자열/전역변수 참조
x64에서 문자열 리터럴이나 전역 변수의 주소를 구할 때 컴파일러는 거의 항상 이 패턴을 쓴다:
```asm
lea rcx, [rip+0x2f10]   ; rcx = "Hello, world!" 문자열의 주소
call printf
```
IDA는 이런 코드를 자동으로 `lea rcx, aHelloWorld`처럼 실제 심볼 이름으로 보여준다. **문자열 xref를 추적할 때 LEA 명령어를 찾는 것이 핵심 시작점**이 되는 이유다.

## 화면/코드에서 보이는 징후
- `lea eax, [rax+rax*2]` — 곱셈(×3) 대체 산술 트릭
- `lea eax, [rax*4+rax]` — 곱셈(×5) 대체
- `lea rax, [rbx+rcx*4]` — 배열 인덱싱 주소 계산(`&arr[i]`, 원소 크기 4바이트)
- `lea rdi, [rbp-0x20]` — 지역 변수의 주소를 구해서 함수 인자로 넘기기 직전
- `lea rcx, [rip+0x2f10]` — 문자열 리터럴/전역 변수 주소 참조 (x64)
- IDA 디컴파일에서 `&arr[i]`, `&local_var`, 문자열 상수, 또는 그냥 `x * 3` 같은 산술식으로 표현됨

## 가장 먼저 할 것
1. LEA 뒤 목적지가 레지스터인지 확인한다(항상 그렇다).
2. `[...]` 안의 표현식이 단순 주소 참조인지, 곱셈/덧셈 패턴(예: `reg + reg*2`, `reg*4 + reg`)인지 구분한다.
3. 곱셈 패턴이면 산술 연산으로 해석하고, 단순 `[base+disp]`나 `[rip+disp]`면 주소(포인터/문자열/전역변수) 참조로 해석한다.

## 단계별 절차
**1) 산술 트릭 여부 판단**
```asm
lea eax, [rax+rax*4]
```
→ `eax = rax + rax*4 = rax*5`. 곱셈 5배 연산.

**2) 배열 인덱싱 주소 계산**
```asm
lea rax, [rdi+rsi*8]
```
→ `rax = rdi + rsi*8`. `rdi`가 `long arr[]`의 시작 주소, `rsi`가 인덱스라면 `&arr[rsi]`.

**3) 지역 변수 주소를 인자로 전달**
```asm
lea rdi, [rbp-0x30]   ; &buffer
call gets
```
→ `gets(&buffer)` 형태. 버퍼 오버플로우 분석 시 이 패턴이 시작점이 되는 경우가 많다.

**4) 문자열/전역 참조**
```asm
lea rcx, [rip+2f10h]
call puts
```
→ IDA에서 해당 주소를 더블클릭하면 실제 문자열 내용을 바로 확인할 수 있다.

## 명령어/단축키
- IDA: LEA의 `[rip+...]` 오퍼랜드를 더블클릭하면 참조하는 데이터(문자열/전역변수)로 바로 이동, `X`로 그 데이터의 Xrefs 확인, `F5`로 디컴파일하면 산술식 또는 `&var` 형태로 정리되어 보임
- x64dbg: LEA 실행 후 목적지 레지스터 값을 보면 계산된 주소를 바로 확인 가능, 그 주소를 덤프 창에 따라가서 실제 데이터 확인
- GDB/Pwndbg: `stepi` 후 `x/s $rax`(문자열로 보기) 또는 `x/gx $rax`(8바이트 값으로 보기)로 LEA 결과 주소가 가리키는 내용 확인

## 출력 해석
- LEA 실행 직후 목적지 레지스터 값이 유효한 메모리 주소처럼 보이면(예: `0x00007ff...`, `0x0000000140001000` 등) 이건 십중팔구 포인터/주소 계산이다.
- LEA 실행 직후 목적지 값이 원래 레지스터의 몇 배수/합으로 딱 떨어지면(`rax*3`, `rax*5`, `rax+rbx` 등) 이건 산술 트릭이다.
- IDA가 `lea rcx, aSomeString`처럼 니모닉 뒤에 사람이 읽을 수 있는 이름을 붙여줬다면 그 이름을 더블클릭해서 실제 문자열 내용을 확인한다.

## 흔한 실수
- **LEA가 메모리를 읽는다고 착각**하는 것 — `lea eax, [rbx]`는 `mov eax, [rbx]`와 완전히 다르다. LEA는 절대 메모리 접근을 하지 않는다.
- **`[...]` 문법만 보고 무조건 "메모리에서 값을 가져온다"고 판단**하는 것 — mnemonic이 `lea`인지 `mov`인지 반드시 먼저 확인해야 한다.
- **LEA를 이용한 곱셈 트릭을 못 알아보고 "이상한 덧셈"이라고 넘어가는 것** — `lea eax, [rax+rax*2]` 같은 패턴은 곱셈 연산이 소스코드에 있었다는 신호다.
- LEA가 플래그를 바꾼다고 착각하는 것 — 바꾸지 않는다. 그래서 `lea` 다음에 오는 조건 분기는 항상 그 이전의 `cmp`/`test`를 봐야 한다.

## 막혔을 때 다음 체크
- LEA 결과가 산술인지 주소인지 애매하면 → 이후 코드에서 이 레지스터가 어떻게 쓰이는지 본다(메모리 접근에 쓰이면 주소, 산술/비교에 쓰이면 계산값일 가능성이 높다).
- `[rip+offset]` 계산의 실제 목표를 모르겠으면 → IDA/Ghidra에서 해당 오퍼랜드를 더블클릭하거나, 디스어셈블리 주소 + `rip`(다음 명령 주소) + offset을 직접 계산한다.

## 미니 예제

**예제 1 — 곱셈 대체 (x3)**
```c
int y = x * 3;
```
```asm
mov eax, [rbp-0x4]     ; eax = x
lea eax, [rax+rax*2]    ; eax = x + x*2 = x*3
```

**예제 2 — 배열 원소 주소 구하기**
```c
int *p = &arr[i];
```
```asm
mov  eax, [rbp-0x4]      ; eax = i
mov  rcx, [rbp-0x10]      ; rcx = arr (배열 시작주소)
lea  rax, [rcx+rax*4]     ; rax = &arr[i] (int는 4바이트)
```

**예제 3 — 지역 변수 주소를 함수 인자로**
```c
char buf[64];
read(0, buf, sizeof(buf));
```
```asm
lea  rsi, [rbp-0x40]   ; buf의 주소 -> 2번째 인자(RSI, SysV)
mov  edi, 0              ; 0 -> 1번째 인자(fd)
mov  edx, 40h             ; 64 -> 3번째 인자
call read
```

**예제 4 — RIP 상대 문자열 참조**
```c
puts("done");
```
```asm
lea rcx, [rip+0x2f10]   ; "done" 문자열의 주소
call puts
```

## 관련 글
- [MOV: 값 복사와 레지스터 메모리 이동](./rev-0039-mov.md)
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)

## 출처/검증
- LEA 명령어 동작(유효 주소 계산, 메모리 접근 없음, 플래그 불변): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LEA—Load Effective Address" 섹션 기준 (2026-09-08 검증).
- LEA를 이용한 산술 연산 대체 최적화 패턴: 컴파일러 코드 생성 관련 일반 참고자료 기준.
