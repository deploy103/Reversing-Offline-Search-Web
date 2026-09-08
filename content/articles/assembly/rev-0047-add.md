---
id: REV-0047
title: "ADD: 덧셈과 플래그"
slug: "rev-0047-add"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - add
  - ADD
  - Add
  - add 명령어
  - add instruction
  - "add eax, ebx"
  - "add rsp, 20h"
  - "add eax, 1"
  - "add rax, rbx"
  - 덧셈
  - 더하기
  - 정수 덧셈
  - CF
  - Carry Flag
  - 캐리 플래그
  - OF
  - Overflow Flag
  - 오버플로우 플래그
  - unsigned overflow
  - signed overflow
  - 부호 없는 오버플로우
  - 부호 있는 오버플로우
  - ADC
  - add with carry
  - 스택 정리
  - stack cleanup
  - epilogue add rsp
  - 128비트 덧셈
  - multi precision add
  - LEA와 ADD 차이
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - add가 뭐임
  - add 명령이 뭐죠
  - add 뭐하는 명령어
  - 어셈블리 덧셈
  - CF랑 OF 차이
  - 캐리랑 오버플로우 차이
  - add rsp가 왜 있음
  - add eax ebx 뜻
  - 정수 오버플로우 어셈블리
symptom_keywords:
  - add 다음에 rsp 왜 더함
  - CF OF 뭐가 다른지 모르겠음
  - 덧셈했는데 플래그가 이상함
  - add rsp 0x20 무슨 뜻
  - 오버플로우 났는지 어떻게 확인
  - 부호 있는 덧셈 오버플로우 확인법
last_verified: "2026-09-08"
---

## 한 줄 요약
`ADD dest, src`는 "`dest = dest + src` 를 계산해서 결과를 `dest`에 다시 쓰고, 그 결과에 따라 CF·OF·SF·ZF·AF·PF 여섯 개 플래그를 전부 갱신하는" 가장 기본적인 정수 덧셈 명령어다.

## 언제 검색해야 하나
- `add eax, ebx`, `add rsp, 0x20`, `add rax, 8` 같은 코드를 보고 정확히 뭘 계산하는지 확인하고 싶을 때
- 함수 에필로그에서 `add rsp, 0x30` 처럼 스택 포인터에 더하는 코드를 봤을 때 (스택 정리인지 다른 의미인지 헷갈릴 때)
- 덧셈 뒤에 CF나 OF를 검사하는 분기가 있어서 "언제 캐리가 뜨고 언제 오버플로우가 뜨는지" 정확히 알아야 할 때
- IDA 디컴파일에서 `v1 = v2 + v3;` 또는 `v1 += v2;` 형태로 보이는 코드의 원본 어셈블리를 확인하고 싶을 때

## 핵심 개념

### ADD가 실제로 하는 일
`ADD dest, src`는 두 오퍼랜드를 받는다.
- **dest**: 레지스터 또는 메모리. 연산 결과가 저장되는 곳(목적지).
- **src**: 레지스터, 메모리, 또는 즉시값(immediate). 단, dest와 src가 둘 다 메모리일 수는 없다(x86은 메모리-메모리 연산을 허용하지 않는다).

동작은 `dest = dest + src` 이고, 이 결과값이 dest에 그대로 덮어써진다. 원래 dest에 있던 값은 사라진다.

```asm
add eax, ebx      ; EAX = EAX + EBX
add rax, 8        ; RAX = RAX + 8
add dword [rbp-4], 1   ; 메모리에 있는 4바이트 값 += 1
```

### 플래그 — ADD는 6개를 전부 건드린다
`ADD`는 산술 명령어이므로 EFLAGS/RFLAGS의 다음 6개 플래그를 **전부** 결과에 맞춰 갱신한다:
- **CF (Carry Flag)** — unsigned 관점에서 자리올림(캐리)이 발생했는가. 즉 결과가 dest의 비트폭(8/16/32/64비트)을 넘어서 흘러넘쳤는가.
- **OF (Overflow Flag)** — signed 관점에서 오버플로우가 발생했는가. 즉 두 signed 정수를 더한 결과가 그 비트폭의 signed 표현 범위를 벗어났는가.
- **SF (Sign Flag)** — 결과의 최상위 비트(부호 비트)와 동일.
- **ZF (Zero Flag)** — 결과가 0이면 1.
- **AF (Auxiliary Carry Flag)** — 4비트 단위(니블) 자리올림. BCD 연산에서나 쓰이고 일반 리버싱에서는 거의 무시해도 된다.
- **PF (Parity Flag)** — 결과의 하위 8비트에서 1인 비트 개수가 짝수면 1. 요즘 코드에서는 거의 안 쓰인다.

이 여섯 개를 다 갱신한다는 점이 다음 글([REV-0049 — INC와 DEC](./rev-0049-inc-dec.md))에서 다루는 `INC`/`DEC`와의 결정적 차이다. `INC`/`DEC`는 CF는 건드리지 않는다.

### CF vs OF — 8비트 예제로 정확히 구분하기
CF와 OF는 완전히 다른 질문에 답한다. **CF는 "unsigned로 봤을 때 넘쳤는가"**, **OF는 "signed로 봤을 때 넘쳤는가"** 다. 같은 비트 연산 결과라도 두 플래그가 서로 다르게(혹은 같게) 나올 수 있다.

**예 1: `0xFF + 0x01` (8비트 레지스터 AL 기준)**
```
  0xFF = 1111_1111
+ 0x01 = 0000_0001
---------------------
  결과   1_0000_0000  → 8비트에는 0x00만 남고, 9번째 비트(캐리)가 넘침
```
- **CF = 1** — unsigned로 보면 `255 + 1 = 256`인데 8비트로는 256을 표현 못 하니 자리올림 발생 → CF 세팅.
- **OF = 0** — signed로 보면 `0xFF`는 `-1`이다. `-1 + 1 = 0`이고 이건 8비트 signed 범위(-128~127) 안에 정확히 들어간다 → 오버플로우 아님 → OF = 0.

**예 2: `0x7F + 0x01`**
```
  0x7F = 0111_1111
+ 0x01 = 0000_0001
---------------------
  결과   1000_0000 = 0x80
```
- **CF = 0** — unsigned로 보면 `127 + 1 = 128`이고 8비트 unsigned 범위(0~255) 안에 들어간다 → 자리올림 없음 → CF = 0.
- **OF = 1** — signed로 보면 `0x7F`는 `127`(signed 최댓값)이다. `127 + 1`은 signed 8비트 범위를 넘어 `-128`로 뒤집혀 버린다 → 오버플로우 발생 → OF = 1.

이 두 예제가 CF와 OF의 존재 이유를 정확히 보여준다: **같은 비트 패턴이라도 그 값을 unsigned로 해석하느냐 signed로 해석하느냐에 따라 "넘쳤다"의 기준이 다르다.** 그래서 x86은 두 플래그를 따로 둔다. 이후 unsigned 비교 분기(`JA`/`JB` 계열, [REV-0070 예정])는 CF를 보고, signed 비교 분기(`JG`/`JL` 계열, [REV-0069 예정])는 OF와 SF를 함께 본다. 자세한 매핑은 [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)에서 종합적으로 정리한다.

### ADD와 LEA의 차이 — "덧셈처럼 보이는데 플래그를 안 건드리는" 경우
`LEA rax, [rbx+rcx*4+8]` 같은 명령은 겉보기에 덧셈/곱셈을 하는 것처럼 보이지만, 사실은 **주소 계산 전용 명령**이라 EFLAGS를 전혀 건드리지 않는다. 컴파일러는 "플래그가 필요 없는 순수한 산술 계산"(포인터 연산, 배열 인덱싱, 심지어 `x = a + b` 같은 일반 정수 덧셈까지)을 최적화할 때 `ADD` 대신 `LEA`를 즐겨 쓴다. 예를 들어 `lea eax, [ebx+ecx]`는 `add eax, ecx`(단, eax=ebx일 때)와 결과값은 같지만 플래그를 바꾸지 않고, 3-오퍼랜드 형태(`dest`가 `src`들과 다른 레지스터)로 쓸 수 있다는 장점이 있다. 리버싱 중 "이 덧셈은 플래그에 영향을 주는가?"를 판단할 때 `LEA`인지 `ADD`인지를 반드시 구분해야 한다.

### 스택/RSP 변화 — 에필로그의 `add rsp, N`
함수 에필로그(끝부분)에서 흔히 보이는 패턴이다:
```asm
add rsp, 0x20    ; 함수 진입 시 sub rsp, 0x20으로 확보했던 지역 변수 공간을 되돌려줌
ret
```
`sub rsp, N`으로 지역 변수용 공간을 스택에 확보했다면, 함수가 끝날 때 `add rsp, N`으로 RSP를 원래 값으로 되돌린다. 이건 스택 프레임을 접는 동작이고, RIP 자체는 바뀌지 않는다(그건 뒤따르는 `ret`의 역할). `RSP`만 증가시켜 "그 아래 있던 데이터는 더 이상 유효하지 않다"고 표시하는 셈이다.

### 컴파일러 패턴
- `add eax, ebx` — 가장 단순한 정수 덧셈 `a + b`.
- `add rsp, 0x20` — 함수 에필로그에서 지역 변수 공간 반환.
- `add [rbp-4], 1` — `count++`가 메모리 변수에 직접 적용된 경우 (레지스터에 안 올리고 바로 메모리에 연산).
- **다중 정밀도(128비트 이상) 덧셈**: 64비트 레지스터 하나로 표현 못 하는 큰 수를 더할 때, 하위 64비트는 `ADD`로 더하고 상위 64비트는 `ADC`(Add with Carry, 하위에서 발생한 CF까지 더해줌)로 더한다.
  ```asm
  add rax, rcx     ; 하위 64비트 더하기, 여기서 CF가 세팅될 수 있음
  adc rdx, rbx     ; 상위 64비트 더하기 + 방금 CF까지 포함
  ```
  이 패턴을 보면 "64비트를 넘는 정수 연산(예: 128비트 정수, 빅넘버 라이브러리)"이라고 바로 짐작할 수 있다.

### IDA/Ghidra 디컴파일 렌더링
- `add eax, ebx` → `v1 = v1 + v2;` 또는 `v1 += v2;`
- `add rsp, 0x20` → 에필로그의 일부라 보통 디컴파일 결과에는 아예 안 보인다(스택 정리는 컴파일러가 자동 처리하는 것으로 취급되어 디컴파일러가 생략).
- 루프 안의 `add esi, 4` (포인터를 4바이트씩 전진) → `p += 4;` 또는 배열 인덱스 증가로 `i++` 형태로 정리되어 보이는 경우가 많다.

### 리버싱에서의 의미
- ADD 직후 `jc`/`jnc`가 오면 → **unsigned 덧셈 오버플로우(자리올림) 검사**. 정수 오버플로우 취약점을 찾을 때 이런 패턴을 주의 깊게 본다.
- ADD 직후 `jo`/`jno`가 오면 → **signed 덧셈 오버플로우 검사**. 드물지만 안전한 정수 연산 라이브러리에서 보인다.
- `add rsp, N`을 보면 즉시 "이 함수가 스택에 얼마나 지역 변수 공간을 썼는지"(진입부의 `sub rsp, N`과 짝을 이루는지) 확인하는 습관을 들이면 스택 불균형 버그나 함수 경계를 빠르게 파악할 수 있다.

## 화면/코드에서 보이는 징후
- `add eax, ebx`, `add eax, 1`, `add [rbp-8], eax` — 일반적인 덧셈
- `add rsp, 0x??` — 함수 에필로그의 스택 정리 (진입부 `sub rsp, 0x??`와 반드시 값이 대응)
- `add ...` 뒤에 바로 `jc`/`jnc`/`jo`/`jno` — 오버플로우 검사
- `add` 다음 줄에 `adc` — 다중 정밀도(64비트 초과) 덧셈

## 가장 먼저 할 것
1. dest와 src가 각각 레지스터/메모리/즉시값 중 무엇인지 확인
2. 이 ADD가 "값 계산"인지 "스택 정리(`add rsp, N`)"인지 구분
3. ADD 직후에 CF나 OF를 검사하는 분기가 있는지 확인 → 있다면 오버플로우 방어 코드
4. 이 값이 signed로 쓰이는지 unsigned로 쓰이는지(변수 타입) 확인해서 CF/OF 중 어느 게 의미 있는지 판단

## 단계별 절차

**1) 단순 덧셈 확인**
```asm
mov eax, [rbp-4]   ; a
add eax, [rbp-8]   ; a += b
mov [rbp-4], eax   ; a 저장
```
→ C로는 `a = a + b;`.

**2) 스택 정리인지 확인**
함수 시작 부분에서 `sub rsp, 0x30`을 봤다면, 함수 끝의 `add rsp, 0x30`은 그 짝이다. 값이 서로 다르면 중간에 `push`/`pop`이 더 있었는지 다시 세어본다.

**3) 오버플로우 검사 패턴 확인**
```asm
add eax, ebx
jo  overflow_handler   ; signed overflow 발생 시 분기
```
→ 이 코드는 signed 정수 덧셈 오버플로우를 명시적으로 검사하는 방어 코드(안전한 산술 라이브러리, 보안이 중요한 계산 등)라고 해석한다.

**4) 다중 정밀도 덧셈 확인**
```asm
add rax, rcx
adc rdx, rbx
```
→ RDX:RAX와 RBX:RCX 두 128비트 값을 더하는 코드로 해석한다.

## 명령어/단축키
- IDA/x64dbg/GDB에서 특별한 단축키는 없지만, 레지스터 창에서 `add` 실행 전후 CF/OF/ZF/SF 비트를 직접 비교하면 플래그 변화를 눈으로 확인할 수 있다.
- x64dbg: 명령어에 F7/F8로 한 줄씩 실행하면서 우측 플래그 패널에서 C(CF)/O(OF)/Z(ZF)/S(SF) 표시가 바뀌는지 관찰.
- GDB/Pwndbg: `info registers eflags` 또는 Pwndbg의 레지스터 화면에서 `CF OF SF ZF` 등이 색으로 표시된다.

## 출력 해석
- x64dbg/Pwndbg 플래그 창에서 실행 직후 `CF=1`이면 unsigned 덧셈이 자리올림을 일으켰다는 뜻 (예: `0xFFFFFFFF + 1`).
- `OF=1`이면 signed 관점에서 결과가 부호를 잘못 뒤집을 만큼 컸다는 뜻 (예: `INT_MAX + 1`).
- IDA 디컴파일에서 `v1 += v2;` 형태는 원본 `ADD` 명령이 결과를 dest에 다시 쓴다는 특성을 그대로 반영한 것이다.

## 흔한 실수
- CF와 OF를 같은 의미로 착각하는 것 — CF는 unsigned 오버플로우, OF는 signed 오버플로우다. 변수가 `unsigned int`인데 OF를 보고 판단하거나, `int`인데 CF를 보고 판단하면 틀린 결론을 내리게 된다.
- `add rsp, N`을 "값 계산"으로 착각해서 함수 로직으로 분석하려는 것 — 대부분은 단순 스택 정리다.
- ADD가 항상 플래그를 갱신한다고 해서, LEA도 그럴 거라 착각하는 것 — LEA는 겉보기에 덧셈 같아도 EFLAGS를 전혀 바꾸지 않는다.
- 다중 정밀도 덧셈에서 `ADC` 없이 `ADD`만 두 번 쓰인 코드를 보고 128비트 연산이라 착각하는 것 — 진짜 다중 정밀도 덧셈이려면 반드시 상위 워드에 `ADC`가 와야 한다(하위의 캐리를 반영해야 하므로).

## 막혔을 때 다음 체크
- ADD 뒤에 이어지는 분기가 CF를 보는지 OF를 보는지 헷갈린다면 → [REV-0088 — 플래그 레지스터와 Jcc 연결](./rev-0088-flags-overview.md)에서 각 Jcc가 정확히 어떤 플래그 조합을 보는지 표로 확인.
- `add rsp, N`의 N 값이 진입부 `sub rsp, N`과 안 맞는다면 → 중간에 `push`/`pop`이 몇 번 있었는지 다시 세어보거나, 정렬(alignment)을 위한 추가 조정이 있었는지 확인.
- 왜 컴파일러가 `add`가 아니라 `lea`를 썼는지 궁금하다면 → 플래그가 필요 없는 위치의 덧셈이라서 그렇다(REV-0042 LEA 예정 참고).

## 미니 예제

**예제 1 — 기본 덧셈과 CF/OF 구분**
```c
unsigned char a = 0xFF;
unsigned char b = 0x01;
unsigned char c = a + b;   // c = 0, unsigned 관점에서 자리올림 발생
```
```asm
mov al, 0FFh
add al, 1        ; AL = 0x00, CF=1 (unsigned 255+1 넘침), OF=0 (signed -1+1=0 정상)
```

**예제 2 — 스택 정리**
```c
void func(void) {
    char buf[32];
    // ...
}
```
```asm
func:
    push rbp
    mov  rbp, rsp
    sub  rsp, 0x20     ; buf[32]용 공간 확보
    ; ... 함수 본문 ...
    add  rsp, 0x20     ; 확보했던 공간 반환
    pop  rbp
    ret
```

**예제 3 — 오버플로우 방어 코드**
```c
int add_checked(int a, int b, int *out) {
    int r = a + b;
    if (((a ^ r) & (b ^ r)) < 0) return -1; // 개념적으로 이런 오버플로우 검사
    *out = r;
    return 0;
}
```
```asm
mov  eax, [a]
add  eax, [b]      ; signed 덧셈
jo   overflow_case  ; OF=1이면 signed overflow → 별도 처리
```

**예제 4 — 128비트(다중 정밀도) 덧셈**
```asm
; RDX:RAX(피연산자1) + RBX:RCX(피연산자2), 결과는 RDX:RAX에 저장
add rax, rcx    ; 하위 64비트
adc rdx, rbx    ; 상위 64비트 (하위에서 넘어온 CF까지 더함)
```

## 관련 글
- [REV-0048 — SUB: 뺄셈과 플래그](./rev-0048-sub.md)
- [REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의](./rev-0049-inc-dec.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기

## 출처/검증
- ADD 명령어 동작과 플래그 영향: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "ADD—Add" 섹션 기준 (2026-09-08 검증).
- CF/OF의 unsigned/signed 오버플로우 구분: Intel SDM Volume 1, "3.4.3 EFLAGS Register" 섹션 기준.
- LEA가 플래그를 변경하지 않는다는 점: Intel SDM Volume 2A, "LEA—Load Effective Address" 섹션 기준.
