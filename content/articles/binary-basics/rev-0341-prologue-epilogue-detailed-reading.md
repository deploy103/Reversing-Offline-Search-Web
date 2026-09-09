---
id: REV-0341
title: "함수 프롤로그와 에필로그 자세히 읽기"
slug: "rev-0341-prologue-epilogue-detailed-reading"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["함수 프롤로그", "함수 에필로그", "function prologue", "function epilogue", "leaf function", "frame pointer omission", "stack canary", "endbr64", "__chkstk"]
aliases: ["프롤로그 에필로그 자세히", "함수 시작 코드 읽는 법", "함수 끝나는 코드 읽는 법", "프롤로그 패턴 종류"]
symptom_keywords: ["함수마다 프롤로그 모양이 다 달라서 헷갈림", "push rbp mov rbp rsp가 없는 함수도 있어서 이상함", "함수 시작에 endbr64가 왜 붙는지 모르겠음", "함수 끝에서 canary 체크하는 코드가 뭔지 모르겠음", "함수 시작에 __chkstk 호출이 왜 있는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
함수 프롤로그/에필로그는 `push rbp; mov rbp, rsp; sub rsp, N`이라는 "교과서적" 한 가지 모양만 있는 게 아니라, leaf 함수인지, 콜리 세이브 레지스터를 쓰는지, 스택 카나리가 있는지, 프레임 포인터를 생략했는지, CET(`endbr64`)가 적용됐는지, 큰 스택을 확보할 때 스택 프로브(`__chkstk`)가 필요한지에 따라 최소 6~7가지 서로 다른 변형이 나타나며, 이 변형들을 구분해서 읽을 줄 알아야 실제 바이너리에서 함수 경계와 지역 변수 개수를 정확히 파악할 수 있다.

## 언제 검색해야 하나
- REV-0031(스택 프레임 기초)에서 배운 "교과서적" 프롤로그(`push rbp` / `mov rbp, rsp` / `sub rsp, N`)와 다르게 생긴 함수를 만났을 때
- 함수 시작 부분에 `endbr64` 한 줄이 항상 먼저 나와서 이게 뭔지 궁금할 때
- 큰 배열을 지역 변수로 선언한 함수(Windows PE)에서 `call __chkstk`(또는 `call ___chkstk_ms`)가 프롤로그 안에 보일 때
- 함수 끝에서 그냥 `ret`으로 안 끝나고 `mov rax, fs:[rax]` / `xor` / `call __stack_chk_fail` 같은 코드가 섞여 있어 스택 카나리 검증인지 헷갈릴 때
- 아주 짧은 함수인데 프롤로그/에필로그 자체가 거의 없어서(`push rbp`도 없이 바로 본문) 이게 정상인지 궁금할 때

## 핵심 개념

### 기준선: REV-0031에서 본 표준 프롤로그/에필로그
```asm
; 표준 프롤로그
push    rbp
mov     rbp, rsp
sub     rsp, 0x20

; 표준 에필로그
leave           ; mov rsp, rbp ; pop rbp
ret
```
이 문서는 이 기준선을 알고 있다는 전제 하에, 실제 바이너리에서 이 모양이 어떻게 변형되어 나타나는지를 하나씩 짚는다.

### 변형 1 — Leaf 함수: 프레임 자체가 없는 경우
다른 함수를 전혀 호출하지 않는 함수(leaf function)는 리턴 주소를 보호할 필요가 없어서, 컴파일러가 `push rbp`조차 생략하고 바로 본문으로 들어가는 경우가 흔하다. 지역 변수가 없거나 레지스터만으로 충분하면 `sub rsp`도 없다.
```asm
; int square(int x) { return x * x; }
square:
    mov     eax, edi
    imul    eax, edi
    ret
```
프롤로그/에필로그가 사실상 "없는" 것처럼 보이는데, 이건 비정상이 아니라 최적화의 결과다. RSP가 함수 시작부터 끝까지 전혀 움직이지 않았다는 뜻이며, 이런 함수는 스택 프레임 개념 자체를 적용할 필요가 없다.

### 변형 2 — 프레임 포인터 생략(Frame Pointer Omission, FPO)
`-O2` 등 최적화가 켜지면 RBP를 프레임 기준으로 쓰지 않고 그냥 범용 레지스터로 재활용한다. 지역 변수는 RBP 대신 **RSP 상대 오프셋**으로 직접 접근한다.
```asm
; RBP를 프레임 포인터로 안 씀
sub     rsp, 0x18
mov     [rsp+8], edi     ; 지역 변수, rbp 대신 rsp 기준
...
add     rsp, 0x18
ret
```
`push rbp` / `mov rbp, rsp`가 아예 안 보이므로 프롤로그가 없다고 착각하기 쉽지만, `sub rsp, N`이 있다면 여전히 스택 공간은 확보하고 있는 것이다. IDA/Ghidra는 이런 함수도 `var_10`처럼 RSP 기준 오프셋으로 자동 이름을 붙여준다.

### 변형 3 — 콜리 세이브(callee-saved) 레지스터 백업이 섞인 프롤로그
함수 안에서 `RBX`, `R12`~`R15` 같은 콜리 세이브 레지스터(호출받은 함수가 값을 보존해줘야 하는 레지스터)를 실제로 건드려 쓴다면, 프롤로그에서 이 레지스터들을 미리 스택에 `push`해서 백업해둔다.
```asm
push    rbp
push    rbx          ; 콜리 세이브 레지스터 추가 백업
push    r12
push    r13
mov     rbp, rsp
sub     rsp, 0x30
```
에필로그에서는 반드시 **push한 순서의 정반대 순서로 pop**해야 스택이 맞는다.
```asm
add     rsp, 0x30
pop     r13
pop     r12
pop     rbx
pop     rbp
ret
```
이런 함수는 `push`가 여러 번 연달아 나오므로 "지역 변수가 여러 개 있나?"로 착각하기 쉽지만, 실제로는 레지스터 백업이다. `push` 대상이 매번 다른 레지스터 이름(`rbx`, `r12`, `r13`)이고 뒤에 `mov rbp, rsp`가 나온다면 레지스터 백업, `push rbp` 하나만 있고 바로 `mov rbp, rsp`가 온다면 표준 프롤로그로 구분한다.

### 변형 4 — 스택 카나리(Stack Canary / Stack Protector)가 섞인 프롤로그·에필로그
스택 오버플로우 보호(`-fstack-protector`)가 켜진 함수는 프롤로그에서 카나리 값을 지역 변수 영역에 심고, 에필로그 직전에 그 값이 그대로인지 검증한다.
```asm
; 프롤로그
push    rbp
mov     rbp, rsp
sub     rsp, 0x20
mov     rax, fs:0x28        ; TLS(스레드 로컬 저장소)에서 카나리 마스터값 로드
mov     [rbp-8], rax        ; 카나리를 지역 변수 맨 끝(버퍼 바로 뒤)에 저장
xor     eax, eax             ; 카나리 값 자체가 레지스터에 남지 않도록 정리

; ... 함수 본문 (버퍼 오버플로우가 있다면 여기서 카나리를 덮어씀) ...

; 에필로그 직전 카나리 검증
mov     rax, [rbp-8]
xor     rax, fs:0x28         ; 저장해둔 값과 마스터값을 다시 비교
je      .stack_check_ok
call    __stack_chk_fail     ; 값이 달라졌으면(오버플로우 발생) 강제 종료
.stack_check_ok:
leave
ret
```
`fs:0x28` 참조, `__stack_chk_fail` 호출이 보이면 스택 카나리 보호라는 뜻이며, 이 카나리 슬롯은 지역 변수 목록에 넣지 않고 별도로 표시해서 읽어야 한다(REV-0031의 지역 변수 오프셋 수집과 헷갈리지 않도록 주의).

### 변형 5 — CET(Control-flow Enforcement Technology): `endbr64`
최근 컴파일러(GCC 8+, 특정 배포판 기본 설정)로 빌드된 x64 바이너리는 거의 모든 함수(및 간접 호출 대상이 될 수 있는 위치)의 맨 첫 줄에 `endbr64`가 붙는다.
```asm
func:
    endbr64
    push    rbp
    mov     rbp, rsp
    ...
```
`endbr64`는 CPU가 지원하는 CET의 "간접 분기 추적(Indirect Branch Tracking)" 기능을 위한 표시로, 간접 `call`/`jmp`의 목적지가 반드시 `endbr64`로 시작해야 한다는 하드웨어 레벨 제약을 표시하는 것이다. 실제 함수 로직과는 무관하므로, 프롤로그를 읽을 때는 그냥 "이 바이너리는 CET가 활성화된 최신 빌드구나" 정도로 인식하고 그 다음 줄부터 진짜 프롤로그로 읽으면 된다.

### 변형 6 — 큰 스택 확보와 스택 프로브(주로 Windows PE)
지역 배열이 매우 커서(한 페이지, 보통 4KB 이상) 스택을 한 번에 크게 내려야 하는 경우, Windows에서는 `sub rsp, N` 대신 컴파일러가 자동으로 `__chkstk`(또는 `___chkstk_ms`) 호출을 프롤로그에 끼워 넣는다.
```asm
mov     eax, 0x2000          ; 확보할 크기를 eax에 준비
call    __chkstk              ; 스택을 한 페이지씩 건드리며(touch) 가드 페이지 확인
sub     rsp, rax              ; 실제로 rsp를 내림
```
이건 스택 가드 페이지(guard page)를 건너뛰어 스택 오버플로우가 감지되지 않은 채 넘어가는 것을 막기 위한 안전장치다. `__chkstk` 호출이 보이면 "이 함수는 큰 지역 변수(대개 배열)를 갖고 있다"는 강한 신호로 읽으면 된다. 리눅스 glibc 환경에서는 이런 명시적 스택 프로브 호출 대신 컴파일러 옵션(`-fstack-clash-protection`)이 켜졌을 때 유사한 역할의 인라인 코드가 들어간다.

### 변형 7 — 여러 개의 에필로그(early return)
함수 안에 `return`이 여러 곳에 있으면, 최적화 여부에 따라 **각 리턴 지점마다 자신만의 에필로그를 따로 갖는 경우**와, **모든 리턴이 하나의 공통 에필로그로 점프(`jmp`)해서 합류하는 경우**가 있다.
```asm
; 케이스 A: 리턴마다 에필로그 중복
cmp     eax, 0
jne     .not_zero
leave
ret
.not_zero:
...
leave
ret

; 케이스 B: 공통 에필로그로 합류
cmp     eax, 0
jne     .not_zero
jmp     .epilogue
.not_zero:
...
.epilogue:
leave
ret
```
케이스 A는 코드 크기가 커지지만 분기가 단순하고, 케이스 B는 코드 크기를 줄이지만 여러 곳에서 `jmp`로 한 곳에 모인다. 디스어셈블리에서 `leave`/`ret`이 함수 안에 여러 번 등장한다고 해서 "함수가 여러 개"라고 착각하면 안 되고, 하나의 함수 안에 여러 리턴 경로가 있는 것뿐이다.

### 변형 8 — 꼬리 호출 최적화(Tail Call Optimization)로 에필로그 자체가 사라지는 경우
함수의 마지막 동작이 다른 함수를 호출하고 그 결과를 그대로 리턴하는 패턴(`return other_func(x);`)이면, 컴파일러가 `call other_func` 대신 자신의 에필로그(스택 정리)를 먼저 실행한 뒤 `call`이 아니라 `jmp other_func`로 대체하는 경우가 있다.
```asm
; return helper(x);  가 다음처럼 컴파일될 수 있음
leave
jmp     helper        ; call이 아니라 jmp! 리턴 주소를 새로 안 쌓고 그대로 재활용
```
이 경우 `helper` 함수가 끝나면 원래 호출자의 호출자에게 바로 리턴된다(스택에 프레임이 하나 덜 쌓임). 디버거로 콜스택(`bt`)을 볼 때 예상보다 프레임이 하나 적게 나온다면 꼬리 호출 최적화를 의심해야 한다.

## 화면/코드에서 보이는 징후
- 함수 시작에 `endbr64`가 항상 붙어있음 — CET 활성화 빌드, 무시하고 다음 줄부터 읽으면 됨.
- `push rbp` 없이 바로 `sub rsp, N`만 있거나, 그마저도 없이 본문으로 직행 — leaf 함수 또는 FPO.
- `push rbx`, `push r12` 등 이름이 다른 레지스터가 `push rbp` 뒤에 연달아 나옴 — 콜리 세이브 백업.
- `fs:0x28` 참조와 `__stack_chk_fail` 호출 — 스택 카나리.
- `call __chkstk`/`call ___chkstk_ms` — 큰 스택 확보(주로 Windows, 큰 배열).
- 함수 안에 `leave`/`ret` 조합이 두 번 이상 등장 — 여러 리턴 경로(early return).
- `call` 대신 함수 맨 끝이 `jmp 다른함수`로 끝남 — 꼬리 호출 최적화.

## 가장 먼저 할 것
함수의 첫 줄이 `endbr64`면 건너뛰고, 그 다음 줄부터 `push`가 몇 번 연달아 나오는지 센다. `push rbp` 하나뿐이면 표준 프레임, 여러 개면 그 중 마지막이 `rbp`인지 확인해서(콜리 세이브가 먼저, `rbp`가 나중에 오는 순서도 컴파일러마다 다를 수 있음) 콜리 세이브 레지스터 개수부터 파악한다. 그 다음 `sub rsp, N`의 유무와 `fs:0x28` 참조 여부로 카나리 유무를 확인한다.

## 단계별 절차

**1) CET 접두 코드 건너뛰기**
```asm
endbr64          ; 있으면 무시하고 다음 줄로
```

**2) push 개수와 대상 레지스터로 콜리 세이브 여부 판단**
```asm
push    rbp        ; 표준 프레임의 시작
push    rbx        ; 추가 콜리 세이브 — 이 함수는 rbx를 실제로 사용함
push    r12        ; 추가 콜리 세이브 — r12도 사용함
mov     rbp, rsp   ; 여기서부터 진짜 프레임 기준이 잡힘
```

**3) sub rsp 값으로 지역 변수 공간 크기 확인, 카나리 슬롯 분리**
```asm
sub     rsp, 0x30
mov     rax, fs:0x28
mov     [rbp-8], rax   ; 이 8바이트는 지역 변수가 아니라 카나리 — 실제 지역 변수는 0x30-8=0x28바이트
```

**4) 에필로그에서 push의 역순 pop과 카나리 검증 확인**
```asm
mov     rax, [rbp-8]
xor     rax, fs:0x28
jz      .ok
call    __stack_chk_fail
.ok:
add     rsp, 0x30
pop     r12          ; push 순서의 역순
pop     rbx
pop     rbp
ret
```

**5) 함수 끝이 ret이 아니라 jmp면 꼬리 호출 의심**
```asm
add     rsp, 0x28
pop     rbx
jmp     other_func    ; ret이 아님! 꼬리 호출
```

## 명령어/단축키
IDA: 함수 프롤로그에서 `Alt+K`로 현재 라인의 스택 포인터 변화량 확인. `push`/`pop` 균형이 안 맞으면 IDA가 경고 표시를 하는 경우가 있다.
```
(gdb) disas func_name          # 프롤로그/에필로그 전체를 한 번에 확인
(gdb) x/3i $rip                # 현재 위치부터 3개 명령어 미리보기
(gdb) bt                        # 콜스택 — 꼬리 호출로 프레임이 줄었는지 확인
```
x64dbg: 함수 진입점에 브레이크포인트(F2) 후 스택 창에서 `push`될 때마다 값이 쌓이는 것을 직접 확인.

## 출력 해석
- `push`가 N번, `pop`이 N번이 아니라면(예: push 3번, pop 2번) 디스어셈블리 경계 설정이 잘못됐을 가능성이 있다 — 함수 범위를 다시 확인해야 한다.
- 카나리 슬롯(`[rbp-8]` 등 `fs:0x28`과 연결된 위치)은 사용자가 선언한 지역 변수가 아니므로, 지역 변수 개수를 셀 때 이 슬롯을 빼고 계산해야 정확하다.
- `call __chkstk` 뒤에 오는 `sub rsp, rax`에서 `rax` 값이 예상보다 훨씬 크다면(수 KB 이상), 큰 버퍼 오버플로우 문제의 대상이 될 만한 지역 배열이 있다는 신호로 활용할 수 있다.

## 흔한 실수
- leaf 함수/FPO로 인해 `push rbp`가 없는 것을 보고 "프롤로그가 깨졌다"거나 "함수가 아니다"라고 오판하는 것.
- 콜리 세이브 레지스터 `push`들을 지역 변수 개수로 착각해서 스택 프레임 크기를 잘못 계산하는 것.
- 카나리 검증 코드(`xor`, `je`, `call __stack_chk_fail`)를 함수의 실제 비즈니스 로직으로 착각해서 분석하는 것 — 이건 보호 코드일 뿐 원래 로직과 무관하다.
- `jmp 다른함수`로 끝나는 꼬리 호출을 보고 "이 함수는 리턴을 안 한다"고 오해하거나, 콜스택 깊이를 셀 때 프레임이 하나 없어진 것을 이상 현상으로 착각하는 것.
- `endbr64`를 진짜 명령어(실행 로직)로 착각해서 분석 시간을 낭비하는 것 — CET 마커일 뿐이다.

## 막혔을 때 다음 체크
- 스택 프레임의 기본 개념, RBP/RSP 관계 자체가 헷갈리면 → REV-0031(스택 프레임이 무엇인지)로 이동.
- 함수 인자/반환값이 어디 있는지 궁금하면 → REV-0032(함수 인자와 반환값이 어디에 있는지)로 이동.
- `call`/`ret`/`leave` 개별 명령어의 정확한 동작이 궁금하면 → REV-0071(CALL), REV-0072(RET), REV-0073(LEAVE)로 이동.
- 최적화로 인해 코드가 예상과 다르게 재배치되는 전반적 현상이 궁금하면 → REV-0037(컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유)로 이동.

## 미니 예제
다음 C 함수를 스택 카나리 + 콜리 세이브 레지스터가 함께 적용된 상태로 살펴보자.

```c
int sum_and_log(int *arr, int n) {
    char buf[16];
    int total = 0;
    for (int i = 0; i < n; i++)
        total += arr[i];
    snprintf(buf, sizeof(buf), "%d", total);
    log_message(buf);
    return total;
}
```

```asm
sum_and_log:
    endbr64
    push    rbp
    push    rbx            ; 반복문에서 배열 베이스를 유지하려고 rbx 사용
    mov     rbp, rsp
    sub     rsp, 0x28
    mov     rax, fs:0x28
    mov     [rbp-8], rax    ; 카나리 저장 (지역 변수 아님)
    mov     [rbp-0x28], rdi ; arr
    mov     [rbp-0x2c], esi ; n
    mov     dword [rbp-0x18], 0   ; total = 0
    mov     dword [rbp-0x1c], 0   ; i = 0
.loop:
    mov     eax, [rbp-0x1c]
    cmp     eax, [rbp-0x2c]
    jge     .loop_end
    mov     rbx, [rbp-0x28]      ; rbx = arr (반복문 내내 유지)
    mov     eax, [rbp-0x1c]
    cdqe
    mov     eax, [rbx+rax*4]
    add     [rbp-0x18], eax       ; total += arr[i]
    add     dword [rbp-0x1c], 1   ; i++
    jmp     .loop
.loop_end:
    ; snprintf(buf, 16, "%d", total) 호출 부분 생략
    ; log_message(buf) 호출 부분 생략
    mov     eax, [rbp-0x18]       ; 반환값 준비
    mov     rdx, [rbp-8]
    xor     rdx, fs:0x28
    je      .stack_ok
    call    __stack_chk_fail
.stack_ok:
    add     rsp, 0x28
    pop     rbx                    ; push 순서의 역순으로 복원
    pop     rbp
    ret
```

이 함수 하나에서 콜리 세이브(`rbx`), 카나리(`fs:0x28`), 반복문, 그리고 표준 프레임이 전부 함께 나타난다. `push rbp` / `push rbx` 두 줄을 지역 변수로 착각하지 않고, `[rbp-8]`을 카나리로 따로 분리해서 읽으면 실제 지역 변수는 `arr`, `n`, `total`, `i`, `buf` 정도로 정확히 정리된다.

## 관련 글
- REV-0031 — 스택 프레임이 무엇인지
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유
- `../assembly/rev-0071-call.md` — CALL: 함수 호출, 반환 주소, 인자 추적
- `../assembly/rev-0072-ret.md` — RET: 함수 반환과 스택 변화
- `../assembly/rev-0073-leave.md` — LEAVE: 함수 에필로그와 스택 프레임

## 출처/검증
- 프레임 포인터 생략(`-fomit-frame-pointer`), 콜리 세이브 레지스터 규약: System V AMD64 ABI("Register Usage" 섹션) 및 GCC/Clang 공식 문서 기준.
- 스택 카나리(`-fstack-protector`)와 `__stack_chk_fail` 동작: GCC 공식 문서 및 glibc 소스의 `__stack_chk_fail` 구현 기준.
- CET `endbr64`와 간접 분기 추적(Indirect Branch Tracking): Intel 64 and IA-32 Architectures Software Developer's Manual, "Control-flow Enforcement Technology (CET)" 챕터 기준.
- Windows `__chkstk`/`___chkstk_ms` 스택 프로브: Microsoft 공식 문서("/GS", stack probing 관련) 기준.
- 꼬리 호출 최적화(tail call optimization): GCC/Clang 최적화 문서의 sibling call/tail call 관련 설명 기준 (2026-09-09 검증).
