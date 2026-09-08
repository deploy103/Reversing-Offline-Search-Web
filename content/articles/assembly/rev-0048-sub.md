---
id: REV-0048
title: "SUB: 뺄셈과 플래그"
slug: "rev-0048-sub"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - sub
  - SUB
  - Sub
  - sub 명령어
  - sub instruction
  - "sub eax, ebx"
  - "sub rsp, 30h"
  - "sub esp, 20h"
  - "sub eax, 1"
  - 뺄셈
  - 빼기
  - 정수 뺄셈
  - CF
  - borrow flag
  - 빌림 플래그
  - 빌려오기
  - OF
  - Overflow Flag
  - signed overflow
  - unsigned underflow
  - 언더플로우
  - SBB
  - subtract with borrow
  - 스택 프레임 할당
  - stack frame allocation
  - sub rsp 지역변수
  - CMP와 SUB 관계
  - 포인터 차이
  - pointer subtraction
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - sub가 뭐임
  - sub 명령이 뭐죠
  - sub 뭐하는 명령어
  - 어셈블리 뺄셈
  - sub rsp가 왜 있음
  - sub esp 무슨 뜻
  - CF가 빌림이라는게 뭔소리
  - cmp랑 sub 차이
  - 뺄셈 플래그 정리
symptom_keywords:
  - sub 다음에 rsp 왜 뺌
  - sub rsp 0x30 무슨 뜻
  - CF가 borrow라는게 뭔지 모르겠음
  - 뺄셈했는데 플래그가 이상함
  - 언더플로우 어떻게 확인
  - cmp가 sub랑 뭐가 다른지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`SUB dest, src`는 "`dest = dest - src` 를 계산해서 결과를 `dest`에 다시 쓰고, CF(빌림)·OF·SF·ZF·AF·PF 여섯 개 플래그를 전부 갱신하는" 뺄셈 명령어이며, `CMP`가 내부적으로 수행하는 연산과 완전히 동일하다(결과를 버리는지 여부만 다르다).

## 언제 검색해야 하나
- `sub eax, ebx`, `sub rsp, 0x30`, `sub rax, 1` 같은 코드의 정확한 의미를 확인하고 싶을 때
- 함수 시작 부분에서 `sub rsp, N`을 보고 "스택에 지역 변수 공간을 얼마나 할당했는지" 확인하고 싶을 때
- `SUB` 뒤에 `jc`/`jb`(unsigned) 또는 `jl`/`jg`(signed) 분기가 붙어서 정확히 무엇을 비교하는지 알아야 할 때
- `CMP`가 왜 "값을 바꾸지 않는 SUB"라고 불리는지 궁금할 때

## 핵심 개념

### SUB가 실제로 하는 일
`SUB dest, src`는 `ADD`([REV-0047](./rev-0047-add.md))와 오퍼랜드 규칙이 동일하다.
- **dest**: 레지스터 또는 메모리 (결과가 저장되는 목적지)
- **src**: 레지스터, 메모리, 즉시값 (dest와 src가 둘 다 메모리일 수는 없음)

동작은 `dest = dest - src`이고, 결과가 dest에 그대로 덮어써진다.

```asm
sub eax, ebx      ; EAX = EAX - EBX
sub rsp, 0x30     ; RSP = RSP - 0x30
sub dword [rbp-4], 1   ; 메모리 값 -= 1
```

### 플래그 — SUB도 6개를 전부 건드린다
`ADD`와 마찬가지로 `SUB`도 CF, OF, SF, ZF, AF, PF를 모두 결과에 맞춰 갱신한다. 단 CF의 의미가 덧셈 때와 다르게 해석된다.

- **CF (Carry Flag, 뺄셈에서는 "Borrow" 역할)** — `dest < src`를 **unsigned로 비교**했을 때 참이면 CF=1. 즉 "빌림(borrow)이 발생했는가"를 의미한다. 예를 들어 `0x01 - 0x02`(8비트)를 계산하면 결과는 `0xFF`가 되는데, unsigned로 보면 1은 2보다 작으므로 뺄 수 없어서 빌려와야 했다는 뜻으로 CF=1이 세팅된다.
- **OF (Overflow Flag)** — 두 signed 정수를 뺀 결과가 그 비트폭의 signed 표현 범위를 벗어나면 1. 예: `INT_MIN - 1`.
- **SF/ZF/AF/PF** — ADD와 동일한 의미(결과의 부호/0 여부/니블 캐리/패리티).

**CF를 "빌림"으로 읽는 법**: unsigned 관점에서 `dest - src`를 계산할 때 `dest`가 `src`보다 작으면, 실제 하드웨어는 더 높은 자리에서 자릿수를 "빌려와야" 결과를 낼 수 있다. 이 빌림이 발생했다는 표시가 CF=1이다. 그래서 **CF=1은 곧 "unsigned로 봤을 때 dest < src였다"** 라는 뜻이며, unsigned 비교 분기(`JB`, `JAE` 등, [REV-0070 예정])는 바로 이 CF를 검사해서 대소 관계를 판단한다.

### SUB와 CMP의 관계
`CMP dest, src` ([REV-0060, 예정])는 내부적으로 정확히 `SUB dest, src`와 동일한 연산을 수행해서 **플래그만 갱신하고 dest에 결과를 쓰지 않는다.** 즉 `CMP`는 "결과를 버리는 SUB"라고 이해하면 정확하다.
```asm
sub eax, ebx   ; EAX = EAX - EBX (dest가 바뀜)
cmp eax, ebx   ; EAX - EBX을 계산은 하지만 EAX는 그대로, 플래그만 바뀜
```
그래서 `cmp a, b` 다음에 오는 `jl`/`jg`/`jb`/`ja` 등의 조건 분기는 사실 "SUB 결과의 플래그"를 보고 판단하는 것과 완전히 동일한 원리다. `SUB`의 플래그 규칙을 이해하면 `CMP` + `Jcc` 조합을 통째로 이해하는 셈이다.

### 스택/RSP 변화 — 함수 진입부의 `sub rsp, N`
함수가 시작할 때 지역 변수를 위한 공간을 스택에 미리 확보하는 가장 흔한 패턴이다:
```asm
push rbp
mov  rbp, rsp
sub  rsp, 0x30    ; 지역 변수 48바이트어치 공간 확보 (RSP가 더 낮은 주소로 이동)
```
스택은 높은 주소에서 낮은 주소로 자라기 때문에, "공간을 확보한다"는 것은 RSP 값을 **감소**시키는 것과 같다. 그래서 `SUB`가 쓰인다(반대로 공간을 반환할 때는 [REV-0047 ADD](./rev-0047-add.md)의 `add rsp, N`을 쓴다). RIP 자체는 변하지 않는다.

### 컴파일러 패턴
- `sub eax, ebx` — 단순 정수 뺄셈 `a - b`.
- `sub rsp, N` — 함수 프롤로그에서 지역 변수 공간 할당. N은 지역 변수 크기의 합을 16바이트 정렬에 맞춰 올림한 값인 경우가 많다.
- **포인터 차이 계산**: `p2 - p1` 같은 포인터 뺄셈은 `sub`로 바이트 차이를 구한 뒤, 원소 크기로 나누는 `sar`/`idiv`가 뒤따르는 경우가 많다(포인터 산술은 REV-0033 예정 참고).
- **루프 카운트 계산**: `sub ecx, eax` 로 반복 횟수(trip count)를 미리 계산해 두고 그 값을 루프 카운터로 쓰는 패턴.
- **다중 정밀도(64비트 초과) 뺄셈**: 하위 워드는 `SUB`, 상위 워드는 `SBB`(Subtract with Borrow, 하위에서 발생한 CF/빌림까지 반영)를 쓴다.
  ```asm
  sub rax, rcx     ; 하위 64비트, 여기서 빌림(CF)이 발생할 수 있음
  sbb rdx, rbx     ; 상위 64비트 - 방금 빌림까지 반영
  ```

### IDA/Ghidra 디컴파일 렌더링
- `sub eax, ebx` → `v1 = v1 - v2;` 또는 `v1 -= v2;`
- `sub rsp, N`(프롤로그) → 디컴파일 결과에는 보통 안 보이고, 대신 지역 변수 선언(`char buf[32];` 등)으로 표현된다.
- `cmp`로 변환되어 보이는 SUB는 대부분 `if (a < b)`, `if (a == b)` 같은 조건문의 일부로 나타난다.

### 리버싱에서의 의미
- SUB 직후 `jb`/`jae`(CF 기반, unsigned)가 오면 → **unsigned 비교/뺄셈 언더플로우 검사**. 버퍼 크기 계산 등에서 언더플로우(음수가 되면 안 되는데 unsigned라서 거대한 양수로 뒤집히는) 취약점을 찾을 때 이 패턴을 주목한다. 예: `remaining = buf_size - used;` 에서 `used > buf_size`이면 `remaining`이 거대한 값으로 뒤집혀 버퍼 오버플로우로 이어질 수 있다.
- SUB 직후 `jl`/`jg`(OF/SF 기반, signed)가 오면 → signed 비교.
- `sub rsp, N`을 보면 그 함수가 스택에 몇 바이트를 쓰는지 즉시 파악할 수 있어, 지역 변수 배열의 대략적 크기를 짐작하는 데 유용하다.

## 화면/코드에서 보이는 징후
- `sub eax, ebx`, `sub eax, 1`, `sub [rbp-8], eax` — 일반적인 뺄셈
- `sub rsp, 0x??` — 함수 프롤로그의 지역 변수 공간 할당 (에필로그의 `add rsp, 0x??`와 값이 대응)
- `sub ...` 뒤에 바로 `jb`/`jae`/`jc`/`jnc` — unsigned 언더플로우/빌림 검사
- `sub` 다음 줄에 `sbb` — 다중 정밀도(64비트 초과) 뺄셈
- `cmp`로 컴파일된 코드는 겉보기엔 안 보이지만 내부 동작은 `sub`와 동일

## 가장 먼저 할 것
1. dest와 src가 레지스터/메모리/즉시값 중 무엇인지 확인
2. 이 SUB가 "값 계산"인지 "스택 프레임 할당(`sub rsp, N`)"인지 구분
3. 뒤따르는 분기가 unsigned(CF 기반: JB/JAE/JC/JNC)인지 signed(OF/SF 기반: JL/JG)인지 확인
4. 언더플로우 가능성이 있는지(unsigned 변수끼리 뺄셈인데 결과가 음수가 될 수 있는 상황인지) 점검

## 단계별 절차

**1) 단순 뺄셈 확인**
```asm
mov eax, [rbp-4]   ; a
sub eax, [rbp-8]   ; a -= b
mov [rbp-4], eax   ; a 저장
```
→ C로는 `a = a - b;`.

**2) 스택 프레임 할당인지 확인**
함수 시작부의 `sub rsp, 0x30`을 봤다면, 함수 끝에서 이 값과 정확히 같은 크기만큼 `add rsp, 0x30`이 나오는지 대조한다. 지역 변수 배열 크기를 짐작하는 데도 쓸 수 있다.

**3) 언더플로우 취약점 의심 패턴 확인**
```c
size_t remaining = total_size - used_size;  // used_size > total_size면 언더플로우
```
```asm
mov  eax, [total_size]
sub  eax, [used_size]     ; unsigned 뺄셈, used_size가 더 크면 거대한 값으로 wrap
mov  [remaining], eax
```
→ `total_size`와 `used_size`의 대소 관계를 사전에 검사하는 코드가 없다면 정수 언더플로우 취약점 후보로 표시해 둔다.

**4) CMP와 동일 동작임을 활용**
```asm
cmp eax, 10
jl  less_than_10
```
→ 이건 내부적으로 `eax - 10`을 계산하고 그 결과(부호/오버플로우)로 분기하는 것과 동일하다. `eax`가 실제로 바뀌지 않을 뿐이다.

## 명령어/단축키
- x64dbg: F7/F8로 SUB 실행 전후 플래그 패널의 C(CF)/O(OF) 비트 변화를 직접 관찰.
- GDB/Pwndbg: `info registers eflags`로 CF/OF 확인. `p/x $eax` 등으로 결과값을 직접 확인.
- IDA: SUB 직후 CF/OF를 보는 분기(Jcc)에 커서를 올리면 어떤 플래그를 참조하는지 상태표시줄/툴팁에서 확인 가능.

## 출력 해석
- `CF=1`이 SUB 직후 나오면 unsigned 관점에서 `dest < src`였다는 뜻(빌림 발생).
- `OF=1`이 SUB 직후 나오면 signed 관점에서 결과가 표현 범위를 벗어났다는 뜻.
- `ZF=1`이면 두 값이 정확히 같았다는 뜻(`SUB`든 `CMP`든 동일).

## 흔한 실수
- SUB의 CF를 "오버플로우"라고 부르는 것 — 정확한 용어는 "빌림(borrow)"이다. SUB에서 CF=1은 unsigned 뺄셈이 음수 방향으로 넘어갔다(빌려왔다)는 뜻이지, ADD의 "자리올림"과는 방향이 반대다.
- `unsigned` 변수끼리 뺄셈해서 음수가 될 수 있는 상황을 놓치는 것 — `unsigned`는 절대 음수가 될 수 없으므로 언더플로우가 나면 거대한 양수로 뒤집힌다. 이건 실제 버그/취약점의 흔한 원인이다.
- `SUB`와 `CMP`를 완전히 다른 명령으로 생각하는 것 — 플래그 계산 로직은 100% 동일하다. `CMP`를 이해 못 하겠으면 `SUB`로 바꿔서 생각해보면 된다.
- `sub rsp, N`을 실제 값 계산으로 오해해서 그 결과를 추적하려는 것 — 대부분은 순수한 스택 공간 확보이며 계산 로직과 무관하다.

## 막혔을 때 다음 체크
- SUB 뒤 분기가 CF를 보는지 OF/SF를 보는지 헷갈린다면 → [REV-0088 — 플래그 레지스터와 Jcc 연결](./rev-0088-flags-overview.md) 참고.
- 함수 프롤로그의 `sub rsp, N`과 에필로그의 `add rsp, N`이 값이 다르면 → 중간에 `push`/`pop`이나 정렬(16바이트) 조정이 있었는지 재확인.
- 언더플로우 취약점인지 확신이 안 서면 → 두 오퍼랜드의 실제 타입이 `unsigned`인지 `signed`인지, 그리고 그 값이 사용자 입력에서 오는지부터 확인.

## 미니 예제

**예제 1 — 기본 뺄셈과 빌림(CF)**
```c
unsigned char a = 0x01;
unsigned char b = 0x02;
unsigned char c = a - b;   // c = 0xFF, unsigned 관점에서 빌림 발생
```
```asm
mov al, 1
sub al, 2         ; AL = 0xFF, CF=1 (1 < 2, 빌림 발생), SF=1, ZF=0
```

**예제 2 — 스택 프레임 할당**
```c
void func(void) {
    char buf[48];
    // ...
}
```
```asm
func:
    push rbp
    mov  rbp, rsp
    sub  rsp, 0x30     ; buf[48]과 정렬 패딩을 위해 0x30(48)바이트 확보
    ; ...
    add  rsp, 0x30
    pop  rbp
    ret
```

**예제 3 — 언더플로우 취약 패턴**
```c
size_t remaining = buf_size - offset;   // offset > buf_size면 거대한 값으로 wrap
memcpy(dst, src + offset, remaining);   // 버퍼 오버리드 가능성
```
```asm
mov  eax, [buf_size]
sub  eax, [offset]     ; offset이 더 크면 EAX가 0에 가까운 곳에서 거대한 값으로 뒤집힘
mov  [remaining], eax
```
→ `offset <= buf_size` 검사가 SUB 이전에 없다면 취약점 후보.

**예제 4 — CMP는 SUB와 동일 원리**
```asm
cmp eax, 100      ; 내부적으로 EAX - 100 계산, 결과는 버리고 플래그만 갱신
jge too_big        ; SF == OF (signed >=)면 분기
```

## 관련 글
- [REV-0047 — ADD: 덧셈과 플래그](./rev-0047-add.md)
- [REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의](./rev-0049-inc-dec.md)
- [REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기](./rev-0088-flags-overview.md)
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기

## 출처/검증
- SUB 명령어 동작과 플래그 영향: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "SUB—Subtract" 섹션 기준 (2026-09-08 검증).
- CMP가 SUB와 동일한 플래그 로직을 쓴다는 점: Intel SDM Volume 2A, "CMP—Compare Two Operands" 섹션 기준.
- CF의 빌림(borrow) 의미: Intel SDM Volume 1, "3.4.3 EFLAGS Register" 섹션 기준.
