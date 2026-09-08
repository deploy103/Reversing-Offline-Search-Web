---
id: REV-0073
title: "LEAVE: 함수 에필로그와 스택 프레임"
slug: "rev-0073-leave"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - leave
  - LEAVE
  - Leave
  - leave instruction
  - leave 명령어
  - "mov rsp rbp"
  - "mov rsp, rbp"
  - "pop rbp"
  - function epilogue
  - 함수 에필로그
  - 스택 프레임 해제
  - stack frame
  - 스택 프레임
  - frame pointer
  - 프레임 포인터
  - base pointer restore
aliases:
  - leave 뭐임
  - leave가 뭐죠
  - leave 명령
  - LEAVE 명령어
  - 에필로그 명령어
  - 스택 프레임 정리
symptom_keywords:
  - 함수 끝에서 leave가 왜 있는지 모르겠음
  - mov rsp rbp pop rbp가 뭔지 모르겠음
  - 스택 프레임이 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LEAVE`는 `mov rsp, rbp` (스택 포인터를 프레임 포인터 값으로 되돌림) 다음 `pop rbp` (이전 함수의 프레임 포인터 복원)를 **한 명령어로 압축한** 것이다. 함수 프롤로그의 `push rbp; mov rbp, rsp`를 정확히 되감는 표준 에필로그 명령어다.

## 언제 검색해야 하나
- 함수 끝, `ret` 바로 앞에 있는 `leave`가 정확히 뭘 하는지 궁금할 때
- `mov rsp, rbp` + `pop rbp` 두 줄이 `leave` 한 줄로 대체된 코드와, 두 줄 그대로 나온 코드를 비교하고 싶을 때
- "스택 프레임"이 정확히 무엇을 가리키는지, RBP가 어떤 역할을 하는지 이해가 안 될 때
- 지역 변수가 많은 함수에서 `sub rsp, N`으로 만들어둔 공간을 어떻게 정리하는지 궁금할 때

## 핵심 개념

### 스택 프레임과 RBP(프레임 포인터)란
함수가 호출되면, 그 함수만의 "작업 공간"이 스택 위에 만들어진다. 이걸 **스택 프레임(stack frame)**이라 부른다. 전통적으로 컴파일러는 `RBP`(x86에서는 `EBP`)를 **프레임 포인터**로 써서, 그 함수의 프레임이 시작하는 지점을 고정된 기준점으로 삼는다. 함수 프롤로그에서 이 기준점을 세우는 방법은 항상 같다:
```asm
push rbp        ; ① 호출자의 RBP 값을 스택에 백업
mov  rbp, rsp     ; ② 지금 이 순간의 RSP를 "이 함수의 기준점"으로 고정
sub  rsp, 20h      ; ③ 지역 변수를 위한 공간 확보 (RSP를 더 내림)
```
이후 함수 본문은 지역 변수를 `[rbp-0x4]`, `[rbp-0x10]`처럼 **RBP 기준 고정 오프셋**으로 접근한다. `sub rsp, N`으로 RSP는 함수 실행 중에도 계속 움직일 수 있지만(추가 PUSH 등), RBP는 함수가 끝날 때까지 절대 안 바뀌므로 안정적인 기준점 역할을 한다.

### LEAVE = 이 프롤로그를 정확히 되감는 것
함수가 끝날 때는 프롤로그의 반대 순서로 되돌려야 한다:
```asm
mov rsp, rbp     ; ③의 역: RSP를 다시 RBP 위치로 되돌림 (지역변수 공간 전부 반납, sub rsp 값과 무관하게 한 번에 정리됨)
pop rbp            ; ①의 역: 스택 최상단(호출자의 RBP였던 값)을 꺼내 RBP에 복원
```
`LEAVE`는 이 두 줄을 **정확히 이 순서 그대로 수행하는 단일 명령어**다:
```
LEAVE:
  1. RSP = RBP        ; mov rsp, rbp 와 동일
  2. RBP = [RSP]        ; pop rbp 와 동일 (읽고)
  3. RSP = RSP + 8       ; (역시 pop의 나머지 절반)
```
즉 `LEAVE`는 `mov rsp, rbp` + `pop rbp`를 기계어 코드 한 바이트(`C9`)로 압축한 것뿐, 동작 자체는 완전히 동일하다. 컴파일러가 어느 쪽을 쓰는지는 최적화 옵션이나 컴파일러 버전에 따라 다르며, 둘 다 자주 보인다 — **`leave` 하나만 보이든 `mov rsp, rbp`/`pop rbp` 두 줄이 보이든 똑같이 해석하면 된다.**

### 왜 `sub rsp, N` 값을 몰라도 LEAVE가 항상 맞게 정리하는가
LEAVE(또는 `mov rsp, rbp`)는 프롤로그에서 지역 변수용으로 `sub rsp, 20h`든 `sub rsp, 100h`든 **얼마나 뺐는지 전혀 몰라도** 한 번에 정확히 되돌릴 수 있다. RBP가 "함수 시작 시점의 RSP"를 그대로 기억하고 있기 때문에, `RSP = RBP`라는 한 번의 대입만으로 그 사이 스택에서 일어난 모든 증감(지역 변수 공간, 함수 내에서 추가로 PUSH한 것들)을 한꺼번에 무효화할 수 있는 것이다. 이것이 프레임 포인터를 쓰는 가장 큰 실용적 이유다.

### 전형적인 함수 에필로그 순서
```asm
leave     ; RSP=RBP, RBP=pop
ret        ; 반환 주소 pop, RIP로 이동
```
`LEAVE`와 [`RET`](./rev-0072-ret.md)이 거의 항상 붙어 다니는 이유는, LEAVE가 스택 프레임을 정리해서 RSP를 "반환 주소가 있는 바로 그 위치"까지 되돌려놓기 때문이다 — LEAVE 실행 직후 `[RSP]`는 정확히 CALL이 push한 반환 주소를 가리키게 되고, 그래서 바로 이어지는 RET이 문제없이 동작한다.

### RBP를 안 쓰는 최적화 코드(frame pointer omission)에서는 LEAVE도 없다
최적화가 강하게 걸린 코드나 x64에서 흔한 "FPO(Frame Pointer Omission)" 방식에서는 애초에 RBP를 프레임 포인터로 쓰지 않고 RSP만으로 모든 걸 계산한다(지역 변수를 `[rsp+N]`으로 직접 접근). 이런 함수는 프롤로그에 `push rbp`/`mov rbp, rsp`가 없으므로, 에필로그에도 당연히 `leave`가 없고 대신 `add rsp, N` 같은 명시적 스택 조정만 나온다. **`leave`가 없다고 해서 코드가 이상한 게 아니라, 그냥 그 컴파일러/최적화 수준이 프레임 포인터를 생략한 것**이라고 이해하면 된다.

### 플래그
`LEAVE`는 **플래그를 전혀 바꾸지 않는다.**

## 화면/코드에서 보이는 징후
- `leave` 다음 바로 `ret` — 표준 함수 에필로그의 가장 흔한 형태
- `mov rsp, rbp` + `pop rbp` — LEAVE와 동일한 의미를 풀어서 쓴 형태(최적화/컴파일러에 따라)
- 함수 프롤로그에 `push rbp; mov rbp, rsp`가 있는 함수에서만 LEAVE가 짝으로 등장 — 프롤로그가 없으면 LEAVE도 없다
- IDA 디컴파일에서는 LEAVE 자체가 코드로 드러나지 않고 그냥 함수의 자연스러운 종료(반환문)로 흡수됨

## 가장 먼저 할 것
1. 이 함수의 프롤로그가 `push rbp; mov rbp, rsp` 형태였는지 확인한다(있어야 LEAVE가 의미를 가진다).
2. LEAVE 실행 직후 RSP가 정확히 "반환 주소 위치"가 되는지(즉 CALL 직전 RSP - 8) 확인한다.
3. LEAVE 바로 다음에 RET이 오는 표준 패턴인지 확인한다.

## 단계별 절차
**1) 프롤로그-에필로그 대응 확인**
```asm
func:
    push rbp          ; 프롤로그 시작
    mov  rbp, rsp
    sub  rsp, 30h
    ...                  ; 함수 본문
    leave                 ; 에필로그: mov rsp,rbp 후 pop rbp
    ret
```

**2) LEAVE를 두 줄로 풀어서 이해하기**
```asm
; leave 는 다음 두 줄과 완전히 같다
mov rsp, rbp
pop rbp
```
어느 쪽이 나오든 똑같이 해석한다.

**3) LEAVE 이후 스택 상태 확인**
```
LEAVE 실행 전: RSP = 0x7ffedfc0 (지역변수 공간 포함, RBP=0x7ffedff0)
LEAVE 1단계 (RSP=RBP): RSP = 0x7ffedff0
LEAVE 2단계 (pop rbp): RBP = [0x7ffedff0] (호출자의 RBP), RSP = 0x7ffedff8
-> 이제 [RSP] = 반환 주소, 바로 다음 RET이 정상 동작
```

**4) FPO(프레임 포인터 생략) 코드와 구분**
```asm
func_optimized:
    sub rsp, 28h
    ...                  ; [rsp+N] 형태로 지역변수 직접 접근, rbp 안 씀
    add rsp, 28h
    ret                    ; leave 없이 add rsp로 직접 정리
```
→ 이런 함수는 애초에 RBP를 프레임 포인터로 안 썼으므로 LEAVE도 필요 없다.

## 명령어/단축키
- IDA: 스택 뷰에서 LEAVE 실행 전후 RSP가 RBP 값으로 점프하듯 바뀌는 것을 확인, `F5` 디컴파일에서는 그냥 함수 종료(`return`)로 자연스럽게 표현됨
- x64dbg: LEAVE에 브레이크포인트를 걸고 실행 전/후 RSP, RBP 레지스터 값을 나란히 비교
- GDB/Pwndbg: `stepi`로 LEAVE 실행 전후 `info registers rsp rbp` 비교, pwndbg의 `stack` 명령으로 스택 프레임 경계가 어떻게 정리되는지 시각적으로 확인

## 출력 해석
- LEAVE 실행 직후 RSP 값이 실행 직전 RBP 값과 정확히 같다면(1단계까지는) 정상.
- LEAVE가 완전히 끝난 후 RBP 값이 이 함수를 호출한 쪽(caller)에서 쓰던 원래 RBP 값으로 복원되어 있으면 정상.
- LEAVE 직후 `[RSP]`를 확인했을 때 유효한 코드 주소(반환 주소)가 보이면, 바로 이어지는 RET이 정상적으로 그 위치로 복귀할 준비가 된 것이다.

## 흔한 실수
- **모든 함수 에필로그에 LEAVE가 있어야 한다고 착각**하는 것 — RBP를 프레임 포인터로 쓰지 않는 최적화된 함수는 LEAVE 없이 `add rsp, N`만으로 끝난다.
- **LEAVE가 RET까지 함께 수행한다고 착각**하는 것 — LEAVE는 스택 프레임만 정리할 뿐, 반환(RIP 변경)은 별도의 RET이 담당한다.
- **`sub rsp, N`으로 확보한 지역 변수 공간을 LEAVE가 어떻게 정확히 아는지 몰라서** N 값을 직접 계산하려 드는 것 — LEAVE는 N 값을 몰라도 되고, RBP가 이미 "정리해야 할 목표 RSP 값"을 그대로 기억하고 있으므로 한 번에 해결된다.
- LEAVE와 `mov rsp, rbp` + `pop rbp` 두 줄짜리 형태를 서로 다른 것으로 오해하는 것 — 완전히 동일한 동작이다.

## 막혔을 때 다음 체크
- LEAVE가 안 보이는데 함수가 정상적으로 끝나는 것 같으면 → 프롤로그에 `push rbp`가 애초에 없었는지(FPO) 확인한다.
- LEAVE 이후 RET이 이상한 곳으로 튀면 → LEAVE 전에 스택이 이미 불균형했을 가능성을 의심하고, 함수 내부 PUSH/POP 개수를 [PUSH](./rev-0044-push.md)/[POP](./rev-0045-pop.md) 관점에서 다시 센다.
- RBP 값이 함수 진입 전과 다르게 복원됐다면 → 프롤로그의 `push rbp` 자체가 실행됐는지, 혹은 함수 중간에 RBP를 다른 용도로 잘못 덮어쓰는 코드가 있는지 확인한다.

## 미니 예제

**예제 1 — 표준 프롤로그/에필로그 대응**
```c
int compute(int a) {
    int local = a * 2;
    return local + 1;
}
```
```asm
compute:
    push rbp
    mov  rbp, rsp
    mov  [rbp-0x4], ecx     ; local 저장 공간 확보(암묵적) 후 a 저장
    mov  eax, [rbp-0x4]
    add  eax, eax             ; local = a*2
    mov  [rbp-0x4], eax
    mov  eax, [rbp-0x4]
    add  eax, 1
    leave                       ; mov rsp,rbp; pop rbp
    ret
```

**예제 2 — LEAVE를 풀어쓴 동일 코드**
```asm
compute_unrolled:
    push rbp
    mov  rbp, rsp
    ...
    mov  rsp, rbp    ; leave의 1단계
    pop  rbp           ; leave의 2단계
    ret
```

**예제 3 — 지역 변수가 많아도 LEAVE 한 줄로 정리**
```c
void big_locals(void) {
    char buf[256];
    int  arr[10];
    ...
}
```
```asm
big_locals:
    push rbp
    mov  rbp, rsp
    sub  rsp, 120h        ; buf[256]+arr[10]+정렬 등 총 0x120 바이트 확보
    ...
    leave                   ; sub rsp 값(0x120)을 몰라도 RSP=RBP로 한 번에 정리
    ret
```

**예제 4 — FPO(프레임 포인터 생략) 최적화 코드: LEAVE 없음**
```asm
fast_func:
    sub rsp, 18h
    mov [rsp+0x8], ecx
    ...
    add rsp, 18h
    ret                     ; leave 없이 add rsp로 직접 정리
```

## 관련 글
- [RET: 함수 반환과 스택 변화](./rev-0072-ret.md)
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [POP: 스택에서 값 꺼내기](./rev-0045-pop.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)

## 출처/검증
- LEAVE 명령어 동작(`mov rsp, rbp` + `pop rbp`와 동일): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LEAVE—High Level Procedure Exit" 섹션 기준 (2026-09-08 검증).
- 프레임 포인터(RBP) 관례와 FPO(Frame Pointer Omission) 최적화: Microsoft Learn x64 스택 사용 규약 문서 및 컴파일러 일반 최적화 참고자료 기준.
