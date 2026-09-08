---
id: REV-0450
title: "함수 인자가 레지스터에서 스택으로 스필되는 패턴"
slug: "rev-0450-register-spill-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - register spill
  - 레지스터 스필
  - shadow space 저장
  - home space
  - 인자 스택 저장
  - callee-saved
  - caller-saved
  - push rbx rbp
  - 지역변수 스택 오프셋
aliases:
  - 함수 시작에 mov rsp rcx가 왜 있는지 모르겠음
  - 인자가 바로 스택에 저장되는 이유
  - shadow space가 뭔지 모르겠음
  - push rbx push rsi가 왜 있는지 모르겠음
symptom_keywords:
  - 함수 진입 직후 mov rsp+8 rcx 같은 코드가 반복됨
  - 인자를 쓰지도 않는데 스택에 저장함
  - push rbx push r12가 함수 초반에 몰려있음
  - 함수 끝에서 pop이 push 역순으로 나옴
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수에 들어오자마자 인자 레지스터(RCX/RDX/R8/R9 또는 RDI/RSI/RDX/RCX/R8/R9)의 값을 곧바로 스택(`[rbp-N]` 또는 `[rsp+N]`)에 옮겨 적는 코드는 프로그래머가 짠 로직이 아니라, "이 레지스터 값이 나중에 또 필요할 수 있으니 미리 안전한 곳(스택)에 백업해둔다"는 컴파일러의 기계적인 관례이며, 이를 **레지스터 스필(register spill)** 이라 부른다.

## 언제 검색해야 하나
- 함수 시작 부분에서 인자로 받은 것 같은 레지스터를 아무 계산도 없이 바로 `[rsp+8]`, `[rbp-0x20]` 같은 스택 위치에 저장하는 코드가 나올 때
- Windows x64 바이너리에서 함수 진입 직후 `mov [rsp+8], rcx` / `mov [rsp+0x10], rdx` 같은 패턴이 매번 똑같이 반복될 때
- 함수 초반에 `push rbx`, `push rbp`, `push r12`~`r15` 등이 몰려 있고, 함수 끝에는 정확히 반대 순서로 `pop`이 있을 때
- 지역 변수가 별로 없어 보이는데도 함수 안에서 레지스터를 계속 스택에 저장했다가 다시 불러오는 코드가 많아서 "왜 이렇게 왔다갔다 하지?"라는 의문이 들 때

## 핵심 개념

### 스필이 왜 생기는가
CPU 레지스터 개수는 유한하다(x64 기준 범용 레지스터 16개). 함수 하나가 처리해야 할 값(인자, 지역 변수, 중간 계산 결과)이 이보다 많아지거나, 그 값을 **다른 함수를 호출하는 동안에도 유지**해야 하면, 컴파일러는 값을 레지스터에서 스택 메모리로 "쏟아낸다(spill)"— 그리고 필요할 때 다시 불러온다(reload). 이는 최적화 부족이 아니라, 유한한 레지스터로 무한히 복잡한 계산을 표현하기 위한 필연적인 절충이다.

### 1) Windows x64의 강제 스필 — Shadow Space(Home Space)
Microsoft x64 호출 규약(REV-0122)에서는, 함수가 호출될 때 처음 4개 인자(RCX, RDX, R8, R9)를 레지스터로 받더라도, **호출하는 쪽이 이 4개 인자를 위한 32바이트 스택 공간(Shadow Space, REV-0124)을 항상 미리 확보**해야 한다. 그리고 실제로 대부분의 함수는 프롤로그에서 이 공간에 인자 레지스터 값을 그대로 복사해 넣는다.
```asm
sub_401000 proc near
    mov     [rsp+8], rcx     ; 1번째 인자를 홈 스페이스에 저장
    mov     [rsp+10h], rdx    ; 2번째 인자
    mov     [rsp+18h], r8      ; 3번째 인자
    mov     [rsp+20h], r9      ; 4번째 인자
    sub     rsp, 28h
    ...
```
이건 **함수가 그 인자를 실제로 쓰든 안 쓰든, 최적화 여부와 무관하게 디버그 빌드(`/Od`)에서 매우 흔하게** 나타난다(최적화가 켜지면 실제로 스택에 안 쓰고 레지스터에 남겨두는 경우도 늘어난다). 디버거가 스택을 보고도 인자 값을 확인할 수 있게 하려는 목적, 그리고 함수 내부에서 그 레지스터를 다른 용도로 재사용해야 할 때 원본 인자를 잃지 않기 위한 목적이 크다.

### 2) 함수 호출을 가로지르는 값 보존 — Caller-saved vs Callee-saved
x64에는 두 종류의 레지스터가 있다.
- **Caller-saved(volatile, 호출자 저장)**: `RAX`, `RCX`, `RDX`, `R8`~`R11` (SysV는 RDI, RSI도 포함) — 호출된 함수(callee)가 마음대로 값을 덮어써도 된다. 그래서 호출하는 쪽(caller)이 "이 값을 CALL 이후에도 계속 쓰고 싶다"면, CALL 전에 **직접 스택이나 다른 레지스터에 저장**해둬야 한다.
- **Callee-saved(non-volatile, 호출된 함수 저장)**: `RBX`, `RBP`, `RDI`, `RSI`(Windows에서만 비휘발), `R12`~`R15` — 호출된 함수가 이 레지스터를 쓰고 싶다면, 함수 시작에서 `PUSH`로 원래 값을 저장해두고 끝에서 `POP`으로 반드시 복원해야 한다. 이는 "호출한 쪽 입장에서는 CALL 전후로 이 레지스터 값이 그대로 유지된다"는 약속(ABI 규약)이기 때문이다.

```asm
sub_402000 proc near
    push    rbx              ; callee-saved 레지스터 백업
    push    rbp
    push    r12
    sub     rsp, 20h
    ...
    ; rbx, rbp, r12를 함수 내부에서 자유롭게 사용
    ...
    add     rsp, 20h
    pop     r12               ; push의 정확히 역순으로 복원
    pop     rbp
    pop     rbx
    ret
```
**PUSH/POP 순서는 항상 정확히 반대(LIFO, 스택 구조)여야 한다** — `push rbx; push rbp; push r12`로 시작했다면 반드시 `pop r12; pop rbp; pop rbx` 순으로 끝나야 스택이 균형을 이룬다(REV-0044, REV-0045 참고).

### 3) 함수 호출을 가로지르는 임시값 스필
caller-saved 레지스터(RAX, RCX, RDX 등)에 담긴 계산 중간값을, 다른 함수를 호출하기 직전에 잃어버리지 않기 위해 스택에 잠깐 저장했다가 CALL 이후 다시 불러오는 패턴도 매우 흔하다.
```asm
mov     eax, [rbp-4]      ; 계산 중간값
mov     [rbp-0x18], eax    ; CALL 전에 스택으로 스필 (RAX가 곧 덮어써질 것이므로)
mov     ecx, arg1
call    some_func           ; RAX가 반환값으로 덮어써짐 (caller-saved)
mov     eax, [rbp-0x18]     ; 스필해둔 값을 다시 로드(reload)
add     eax, [rax_result]
```

### 레지스터/메모리 효과와 플래그
- `MOV`, `PUSH`, `POP`은 **EFLAGS를 변경하지 않는다.** 스필/리로드 자체가 조건 분기 로직에 어떤 부수효과도 남기지 않는다는 뜻이므로, 이 코드를 만나도 플래그 흐름은 신경 쓸 필요가 없다.
- `PUSH`는 RSP를 오퍼랜드 크기(x64에서 항상 8바이트 단위)만큼 감소시키고, `POP`은 그만큼 증가시킨다(REV-0044, REV-0045). 스택 불균형(push/pop 개수 불일치)이 있으면 REV-0072(RET)에서 다룬 "positive sp value" 경고나 크래시로 이어질 수 있다.
- signed/unsigned은 스필 자체와 무관하다 — 어떤 값이든 그대로 바이트 단위로 옮겨질 뿐이다.

## 화면/코드에서 보이는 징후
```asm
; Windows x64 shadow space 저장 (함수 진입 직후, 매우 전형적)
mov     [rsp+8], rcx
mov     [rsp+10h], rdx
mov     [rsp+18h], r8
```
```asm
; callee-saved 레지스터 백업/복원 쌍
push    rbx
push    rsi
push    rdi
...
pop     rdi
pop     rsi
pop     rbx
```
```asm
; CALL을 가로지르는 caller-saved 값 스필
mov     [rbp-0x30], eax
call    helper
mov     eax, [rbp-0x30]
```

## 가장 먼저 할 것
1. 함수 진입 직후 몇 줄이 인자 레지스터(RCX/RDX/R8/R9 또는 RDI/RSI/RDX/RCX/R8/R9)를 스택에 그대로 옮기는 것뿐이라면, 이는 로직이 아니라 shadow space 저장이므로 건너뛰고 다음 실질 코드를 본다.
2. `PUSH`가 여러 번 연달아 있으면 그 레지스터 이름을 기억해두고, 함수 끝에서 정확히 역순 `POP`이 있는지 확인한다 — 있으면 단순 callee-saved 백업/복원이다.
3. `CALL` 직전에 `MOV [스택], reg`가 있고 `CALL` 이후 같은 스택 위치에서 다시 `MOV reg, [스택]`로 불러오면, 이는 그 값이 CALL을 넘어 필요했기 때문에 임시로 스필된 것이다.

## 단계별 절차

**1) 스필된 값이 "진짜 지역 변수"인지 "그냥 백업"인지 구분**

같은 스택 오프셋을 함수 전체에서 여러 번, 다른 값으로 갱신하며 실제 계산에 쓴다면 진짜 지역 변수다. 반대로 딱 한 번 저장하고 CALL 이후 한 번 그대로 불러와서 바로 다음 계산에 쓰고 끝난다면 단순 스필/리로드다.

**2) Shadow space 위치 확인**

Windows x64에서 `[rsp+8]`, `[rsp+0x10]`, `[rsp+0x18]`, `[rsp+0x20]`(또는 `sub rsp, N` 이후 `[rsp+N+8]` 등 프레임 크기만큼 밀린 위치)에 대한 저장은 거의 항상 shadow space이니, IDA 스택 뷰(`Alt+K` 또는 함수 상단 프레임 레이아웃)에서 이 영역을 `var_arg1` 등으로 구분해서 표시하는지 확인한다.

**3) Callee-saved 레지스터 사용처 확인**

`PUSH`로 백업된 레지스터(RBX, RBP, R12~R15 등)가 함수 본문에서 어떤 값을 담는 용도로 재사용되는지 추적하면, 이 함수가 어떤 값을 "오래 유지"해야 했는지(예: 루프 카운터, 배열 베이스 주소) 알 수 있다.

**4) 최적화 수준 가늠**

스필/리로드가 유난히 많고 같은 값이 반복적으로 저장·로드된다면 최적화가 낮은 빌드(`-O0`, `/Od`)일 가능성이 높다. 반대로 스필이 거의 없고 값들이 레지스터에서 레지스터로 바로 이동한다면 높은 최적화(`-O2`/`-O3`, `/O2`) 빌드다 — 이는 디버깅 난이도와 심볼 존재 가능성을 가늠하는 데도 참고가 된다.

## 명령어/단축키
- IDA: 함수 열고 `Alt+K`(스택 프레임 뷰)로 각 스택 오프셋이 어떤 변수/인자로 매핑되는지 확인, `N`으로 오프셋에 의미 있는 이름 부여
- Ghidra: Decompile 창에서 자동으로 `param_1`~`param_4`, `local_*`로 분리되는지 확인, Listing에서 스택 프레임(Function → Edit Function 또는 스택 변수 창)으로 오프셋 목록 확인
- x64dbg/GDB: 함수 진입 시 브레이크포인트를 걸고, 레지스터 창과 스택 덤프 창을 나란히 띄워 스필되는 순간의 값이 일치하는지 직접 눈으로 확인

## 출력 해석
- IDA/Ghidra 디컴파일에서 shadow space 저장은 대개 **자동으로 생략되고** `func(a1, a2, a3)`처럼 깔끔한 인자로만 보인다 — 즉 디컴파일 결과에는 안 보여도 실제 어셈블리에는 있는 게 정상이다.
- Callee-saved `PUSH`/`POP` 쌍은 디컴파일 결과에 전혀 나타나지 않는다(컴파일러가 알아서 처리). 어셈블리에서만 확인 가능한 정보다.
- 스택 오프셋이 함수 전체에서 계속 다른 값으로 갱신되며 여러 곳에서 읽힌다면 디컴파일러가 이를 `int local_20;` 같은 진짜 지역 변수로 표시해준다.

## 흔한 실수
- Shadow space 저장 코드를 "이 함수가 인자를 스택에서 처리하는 특별한 로직"으로 오해하는 것 — 대부분은 그냥 ABI가 요구하는 의무적인 백업이며, 실질적인 알고리즘과 무관하다.
- Callee-saved `PUSH`/`POP`의 순서를 무시하고 아무 레지스터나 임의로 값을 넣었다고 착각하는 것 — 순서는 항상 LIFO로 짝을 이루며, 이 순서가 깨져 있다면(예: 코드 패치, 셸코드 삽입) 스택 불균형으로 크래시가 나거나 리턴 주소가 잘못 해석될 수 있다.
- 스필된 값과 실제 인자 개수를 혼동해서, shadow space에 저장된 4개 슬롯을 "이 함수가 인자 4개를 받는다"는 확정적 증거로 오판하는 것 — Windows x64에서는 인자가 1개뿐이어도 shadow space 32바이트는 항상 확보되므로, 실제 인자 개수는 함수 본문에서 어떤 레지스터/슬롯이 실제로 읽히는지를 봐야 정확히 알 수 있다.
- CALL을 가로지르는 스필/리로드 쌍을 보고 "이 값이 이후에도 중요하게 쓰이는 핵심 변수"라고 과대 해석하는 것 — 단지 "레지스터가 하나 부족해서 잠깐 치워뒀다가 되찾아온 것"뿐일 수 있다.

## 막혔을 때 다음 체크
- Shadow space와 실제 지역 변수를 구분하기 어렵다면 → IDA `Alt+K` 스택 뷰에서 `arg_0`/`arg_8`처럼 자동 명명된 영역과 `var_`로 시작하는 영역을 구분해서 본다.
- 어떤 레지스터가 caller-saved인지 callee-saved인지 헷갈리면 → REV-0106(SysV) 또는 REV-0122(Microsoft x64) 문서의 레지스터 보존 규칙 표를 다시 확인한다.
- Shadow space 크기(32바이트)나 이유가 궁금하면 → REV-0124(Shadow Space가 무엇인지)로 이동한다.
- 스택 불균형이 의심되면 → REV-0044(PUSH), REV-0045(POP), REV-0072(RET) 각각의 스택 변화 규칙을 다시 확인한다.

## 미니 예제

**예제 1 — Windows x64 shadow space 저장 (전형적 프롤로그)**
```c
int add3(int a, int b, int c) {
    return a + b + c;
}
```
```asm
add3 proc near
    mov     [rsp+8], ecx      ; a
    mov     [rsp+10h], edx     ; b
    mov     [rsp+18h], r8d      ; c
    mov     eax, [rsp+8]
    add     eax, [rsp+10h]
    add     eax, [rsp+18h]
    ret
```
최적화가 켜지면 이런 스필 없이 그냥 `add eax, edx` / `add eax, r8d`로 바로 계산해버리므로, 이 예제는 최적화가 낮을 때(`/Od`) 전형적으로 나타나는 형태다.

**예제 2 — Callee-saved 레지스터를 쓰는 루프 함수**
```c
long sum_array(long *arr, int n) {
    long total = 0;
    for (int i = 0; i < n; i++) total += arr[i];
    return total;
}
```
```asm
sum_array proc near
    push    rbx               ; rbx를 루프 내내 베이스 포인터로 재사용할 것이므로 백업
    mov     rbx, rcx           ; rbx = arr (callee-saved라 CALL이 껴도 안전)
    xor     eax, eax
    xor     ecx, ecx
loop_top:
    cmp     ecx, edx
    jge     loop_end
    add     rax, [rbx+rcx*8]
    inc     ecx
    jmp     loop_top
loop_end:
    pop     rbx                ; 원래 값 복원
    ret
```

**예제 3 — CALL을 가로지르는 스필**
```c
int compute(int x) {
    int y = expensive(x);
    int z = another(x);
    return y + z;
}
```
```asm
mov     ecx, [rbp+x]
call    expensive
mov     [rbp-4], eax     ; y를 스필 (RAX가 another 호출로 곧 덮어써질 것이므로)
mov     ecx, [rbp+x]
call    another
add     eax, [rbp-4]     ; y를 다시 로드해서 z(현재 eax)와 더함
```

## 관련 글
- REV-0124 — Shadow Space가 무엇인지
- REV-0106 — SysV AMD64 Calling Convention
- REV-0122 — Microsoft x64 Calling Convention
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- Windows x64 Shadow Space(32바이트, 4개 인자용) 요구사항: Microsoft Learn "x64 calling convention" 및 "x64 software conventions" 공식 문서 기준.
- Caller-saved/Callee-saved 레지스터 분류(RBX, RBP, RDI, RSI, R12–R15는 non-volatile 등): Microsoft x64 ABI 문서 및 System V AMD64 ABI 문서의 레지스터 사용 규칙(Register Usage) 섹션 기준.
- `PUSH`/`POP`/`MOV`가 EFLAGS를 변경하지 않는다는 내용: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 각 명령어 항목 기준.
