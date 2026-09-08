---
id: REV-0045
title: "POP: 스택에서 값 꺼내기"
slug: "rev-0045-pop"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - pop
  - POP
  - Pop
  - pop instruction
  - pop 명령어
  - "pop rbp"
  - "pop rax"
  - "pop eax"
  - "pop qword ptr"
  - stack pop
  - 스택 팝
  - 스택에서 꺼내기
  - 스택 꺼내기
  - RSP 증가
  - ESP 증가
  - 스택 복원
aliases:
  - pop 뭐임
  - pop이 뭐죠
  - pop 명령
  - POP 명령어
  - 스택 꺼내기
  - 스택 복원 명령어
symptom_keywords:
  - pop 했는데 값이 왜 안 지워지는지 모르겠음
  - 스택 데이터가 pop 후에도 메모리에 남아있음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`POP dst`는 스택 맨 위(`[RSP]`)의 값을 `dst`에 읽어온 뒤, 스택 포인터(`RSP`/`ESP`)를 증가시키는 명령어다. [PUSH](./rev-0044-push.md)와 정확히 반대 동작이며, x64에서는 항상 8바이트 단위로 스택이 줄어든다(정확히는 "늘어난다", 사용 영역 관점에서는 줄어드는 것).

## 언제 검색해야 하나
- `pop rbp` 같은 코드가 함수 끝에 반복돼서 왜 있는지 궁금할 때
- POP이 스택의 데이터를 실제로 "지우는" 것인지 궁금할 때
- PUSH와 POP의 순서/짝이 맞는지 확인하고 싶을 때(LIFO 구조 이해)
- 함수 에필로그에서 여러 개의 POP이 나오는 순서가 프롤로그의 PUSH 순서와 왜 반대인지 궁금할 때

## 핵심 개념

### POP의 정확한 동작 순서 (PUSH와 반대)
```
POP dst:
  1. dst = [RSP]                     ; 먼저 현재 스택 최상단 값을 읽는다
  2. RSP = RSP + (오퍼랜드 크기)    ; 그 다음 스택 포인터를 늘린다
```
[PUSH](./rev-0044-push.md)가 "감소 먼저, 쓰기 나중"이었다면, POP은 "읽기 먼저, 증가 나중"이다. 순서가 정확히 대칭이다.

```asm
; 실행 전: RSP = 0x7ffedff8, [0x7ffedff8] = 0x1234
pop rax
; 실행 후: RAX = 0x1234, RSP = 0x7ffee000 (8만큼 증가)
```

### POP은 메모리를 "지우지" 않는다
아주 흔한 오해: POP을 실행해도 스택에 있던 원래 값은 **메모리에서 지워지지 않는다.** 그저 RSP가 그 값을 "더 이상 유효한 스택 영역이 아니다"라고 가리키게 될 뿐이다. 그 주소를 디버거에서 직접 들여다보면 POP 이후에도 예전 값이 그대로 남아있는 걸 볼 수 있다(다음 PUSH가 그 자리를 덮어쓰기 전까지). 이건 보안적으로도 의미가 있다 — 스택에 남은 이전 값(스택 잔여 데이터)이 정보 유출로 이어질 수 있는 이유가 바로 이것이다.

### 오퍼랜드
- 레지스터: `pop rax`, `pop rbp`
- 메모리: `pop qword ptr [rbx]` (스택 값을 메모리 위치에 직접 저장)
- 세그먼트 레지스터(x86 레거시): 이 사전에서는 다루지 않음
- 즉시값은 POP의 목적지가 될 수 없다(당연히 상수에는 값을 쓸 수 없다).

### 플래그
`POP`은 **플래그를 전혀 바꾸지 않는다.** (예외: `POPF`는 플래그 레지스터 자체를 스택에서 복원하는 별개의 명령어이며, [PUSHF/POPF](./rev-0046-pushf-popf.md)에서 다룬다.)

### LIFO(후입선출) 구조와 PUSH/POP 순서의 대칭
스택은 Last-In-First-Out 구조다 — **가장 나중에 PUSH한 값이 가장 먼저 POP된다.** 그래서 함수 프롤로그에서 여러 레지스터를 PUSH했다면, 에필로그의 POP은 **정확히 역순**이어야 한다:
```asm
; 프롤로그
push rbp     ; ① 첫 번째로 push
push rbx     ; ② 두 번째로 push
push r12     ; ③ 세 번째로 push
...
; 에필로그 (반드시 역순!)
pop  r12     ; ③을 먼저 pop
pop  rbx     ; ②를 그 다음 pop
pop  rbp     ; ①을 마지막에 pop
ret
```
이 순서가 뒤바뀌면 레지스터에 엉뚱한 값이 복원되어 프로그램이 오작동한다. 리버싱할 때 프롤로그의 PUSH 순서와 에필로그의 POP 순서가 정확히 대칭인지 확인하는 습관을 들이면 스택 프레임을 훨씬 빠르게 읽을 수 있다.

### 함수 에필로그에서의 POP — 레지스터 복원
```asm
pop r12          ; 프롤로그에서 저장해둔 콜리-세이브 레지스터 복원
pop rbx
pop rbp           ; 마지막으로 이전 RBP 복원
ret                ; 반환 주소 pop -> RIP
```
이 패턴은 [CALL](./rev-0071-call.md)/[RET](./rev-0072-ret.md) 문서에서 다루는 함수 호출 규약과 짝을 이루는, 함수가 자신이 건드린 콜리-세이브 레지스터를 원상복구해서 호출자에게 "나는 이 레지스터들을 안 건드린 것처럼 보이게" 만드는 표준 패턴이다.

## 화면/코드에서 보이는 징후
- `pop rbp` — 함수 에필로그, 프롤로그의 `push rbp`와 짝
- `pop rbx`, `pop r12`~`r15` — 콜리-세이브 레지스터 복원
- `pop rcx` (사용하지 않는 목적지) — 스택 정리 트릭. 예를 들어 `call`+`add rsp, 8` 대신 `pop rcx`(아무 레지스터나 희생시켜서) 스택만 정리하는 최적화/난독화 패턴
- `pop qword ptr [rbp-0x8]` — 스택 값을 바로 지역 변수에 저장

## 가장 먼저 할 것
1. 이 POP이 어떤 PUSH와 짝을 이루는지(프롤로그-에필로그 대응) 찾는다.
2. 목적지 레지스터가 실제 사용할 값을 받는 건지, 아니면 그냥 스택 정리용(희생 레지스터)인지 구분한다.
3. 함수 전체에서 PUSH 횟수와 POP 횟수(및 CALL/RET)가 맞는지 센다.

## 단계별 절차
**1) 에필로그의 POP 인식**
```asm
pop rbx
pop rbp
ret
```
→ 함수가 곧 끝난다는 신호. 프롤로그에서 `push rbp` / `push rbx`가 있었는지 거슬러 올라가 확인.

**2) 순서 대칭 검증**
```
프롤로그: push rbp -> push rsi -> push rdi
에필로그: pop rdi -> pop rsi -> pop rbp   (정확히 역순, 정상)
```
만약 순서가 안 맞으면(예: `pop rsi -> pop rdi -> pop rbp`) 레지스터 값이 뒤바뀌어 복원되는 버그이거나, 애초에 그 POP들이 서로 다른 PUSH와 짝이 아닐 수 있다 — 다시 확인해야 한다.

**3) "희생 레지스터" POP 인식**
```asm
call some_func
pop rcx           ; 반환값(rax)은 안 쓰고, 그냥 스택에 남은 8바이트를 정리하는 용도
```
→ 이는 `add rsp, 8`과 동일한 효과를 내지만 코드 크기가 더 작아서(1바이트) 컴파일러/셸코드 작성자가 선호하는 트릭이다. `rcx`에 들어간 값 자체는 이후 코드에서 안 쓰인다면 무시해도 된다.

## 명령어/단축키
- IDA: 스택 뷰에서 POP마다 스택 프레임이 줄어드는(정확히는 사용 영역이 위로 줄어드는) 것을 시각적으로 확인, `F5` 디컴파일에서는 대개 지역변수 복원으로 자연스럽게 흡수되어 안 보임
- x64dbg: 하단 스택 창에서 POP 실행마다 RSP가 아래에서 위로(주소가 커지는 방향으로) 이동하는 것을 확인
- GDB/Pwndbg: `x/4gx $rsp`로 스택 최상단 확인 후 `stepi`로 POP 실행, 다시 `info registers rsp`와 목적지 레지스터 값 비교

## 출력 해석
- POP 실행 직후 목적지 레지스터 값이 POP 직전 `[RSP]` 값과 정확히 같으면 정상.
- POP 실행 후 RSP가 정확히 8만큼 늘어나 있으면 정상(x64 기준).
- 함수 끝에서 POP들을 모두 실행하고 `ret`를 실행했을 때 RSP가 이 함수의 CALL 실행 직전 값과 정확히 같아야 한다 — 그렇지 않으면 스택 불균형이다.

## 흔한 실수
- **POP이 메모리 값을 지운다고 착각**하는 것 — 지우지 않는다. RSP만 이동할 뿐, 이전 스택 데이터는 메모리에 그대로 남는다(다음에 그 자리가 덮어써지기 전까지).
- **PUSH 순서와 POP 순서가 같아야 한다고 착각**하는 것 — 실제로는 정반대(역순)여야 정상이다. LIFO 구조이기 때문이다.
- **POP의 목적지 레지스터가 항상 "쓸모 있는 값"을 받는다고 가정**하는 것 — `pop rcx`처럼 스택 정리 목적의 "버림용" POP도 흔하다.
- POP이 플래그를 바꾼다고 착각하는 것 — 바꾸지 않는다.
- 함수 안에서 PUSH보다 POP을 더 많이(또는 반대로) 실행해서 스택이 불균형해지는 코드를 정상이라고 넘기는 것 — RET이 엉뚱한 주소로 튀는 원인이 된다.

## 막혔을 때 다음 체크
- POP한 값이 이상하면 → 그 직전에 정말 원하는 값이 PUSH되어 있었는지, 혹은 그 사이에 다른 PUSH/CALL이 끼어들어서 스택 최상단이 바뀐 건 아닌지 확인한다.
- 함수 에필로그의 POP 개수와 프롤로그의 PUSH 개수가 안 맞으면 → 중간에 `add rsp, N`으로 스택을 직접 조정하는 코드가 있는지, 혹은 [LEAVE](./rev-0073-leave.md)가 대신 쓰였는지 확인한다.
- RET 이후 실행이 이상한 곳으로 튀면 → PUSH/POP 균형이 깨졌을 가능성을 의심하고 함수 전체를 처음부터 다시 센다.

## 미니 예제

**예제 1 — 함수 에필로그의 레지스터 복원**
```c
void func(void) {
    // 함수 본문에서 rbx, r12 사용
}
```
```asm
func:
    push rbp
    mov  rbp, rsp
    push rbx
    push r12
    ...                  ; 함수 본문
    pop  r12              ; 역순 복원 시작
    pop  rbx
    pop  rbp
    ret
```

**예제 2 — 스택에서 지역 변수로 직접 복원**
```asm
call get_value          ; 반환값이 스택에 쌓여있다고 가정하는 특수 상황(호출 규약에 따라 다름)
pop  qword ptr [rbp-0x8]  ; 스택 값을 바로 지역 변수에 저장
```

**예제 3 — "희생 레지스터"를 이용한 스택 정리**
```c
some_func();   // 반환값을 쓰지 않는 호출
```
```asm
call some_func
pop  rcx            ; add rsp, 8 대신 사용 (반환값도, rcx 이전 값도 신경 안 씀)
```

**예제 4 — PUSH/POP으로 값 두 개를 임시로 뒤집기**
```asm
push rax     ; 스택: [rax]
push rbx     ; 스택: [rbx, rax]
pop  rax      ; rax = 원래 rbx 값
pop  rbx      ; rbx = 원래 rax 값  -> 결과적으로 rax, rbx가 스왑됨 (XCHG와 같은 효과)
```

## 관련 글
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [PUSHF와 POPF: 플래그 저장과 복원](./rev-0046-pushf-popf.md)
- [XCHG: 두 값 교환](./rev-0043-xchg.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [RET: 함수 반환과 스택 변화](./rev-0072-ret.md)
- [LEAVE: 함수 에필로그와 스택 프레임](./rev-0073-leave.md)

## 출처/검증
- POP 명령어 동작(RSP 증가 순서, x64에서 8바이트 고정): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "POP—Pop a Value from the Stack" 섹션 기준 (2026-09-08 검증).
- 콜리-세이브 레지스터 복원 규약: Microsoft Learn "x64 calling convention" 및 System V AMD64 ABI 공식 스펙 기준.
