---
id: REV-0489
title: "스택 정렬이 안 맞아서 크래시가 나는 것처럼 보일 때"
slug: "rev-0489-stack-alignment-crash"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - stack alignment
  - 스택 정렬
  - 16바이트 정렬
  - RSP 16 align
  - movaps crash
  - "#GP"
  - general protection fault
  - "sub rsp, 8"
  - shadow space
  - call 직전 정렬
  - and rsp, -16
  - and rsp, 0xfffffff0
aliases:
  - 스택이 안 맞아서 죽어요
  - movaps에서 크래시
  - rsp 정렬이 뭔지 모르겠음
  - call 하면 죽는데 이유를 모르겠음
  - 16바이트 정렬이 왜 필요한지 모르겠음
symptom_keywords:
  - movaps에서 access violation
  - call 직후 SIMD 함수에서 죽음
  - rsp가 16의 배수가 아님
  - printf 호출하면 크래시남
  - 스택이 한 칸 어긋난 것 같음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CALL` 명령이 실행되는 순간 `RSP`(스택 포인터)는 x64 ABI 규약상 항상 16의 배수 - 8이어야 하며(즉 함수 진입 직후 기준으로 16의 배수), 이 정렬이 깨지면 함수 내부에서 정렬을 요구하는 SIMD 명령(`movaps` 등)이나 가변 인자 함수에서 크래시가 나는데 — 이는 로직 버그가 아니라 스택에 홀수 개의 `PUSH`/어긋난 `SUB RSP`가 있었다는 신호다.

## 언제 검색해야 하나
- `movaps`가 실행되는 순간 접근 위반(access violation) / `SIGSEGV` / `#GP`가 뜰 때
- 직접 작성하거나 패치한 어셈블리/셸코드에서 `printf`, `malloc` 같은 라이브러리 함수를 호출했더니 이유 없이 죽을 때
- 함수 호출 스택 깊이나 `PUSH` 개수를 바꿨더니 (디버깅/패치 중) 멀쩡하던 코드가 갑자기 크래시가 날 때
- x64dbg/GDB로 크래시 시점의 `RSP` 값을 봤는데 16으로 나눠떨어지지 않을 때(`RSP % 16 != 0`)

## 핵심 개념

### 왜 16바이트 정렬이 필요한가
x64에서 도입된 SIMD 레지스터(`XMM`)를 다루는 일부 명령(`movaps`, `movdqa` 등, "Aligned" 계열)은 **메모리 주소가 16의 배수일 때만** 정상 동작하도록 설계되어 있다. 정렬 안 된 주소로 접근하면 CPU가 `#GP`(General Protection) 예외를 던진다. 그래서 x64 ABI(SysV, Microsoft 둘 다)는 함수 호출 시점에 스택이 16바이트 경계에 맞춰져 있도록 강제하는 규약을 정해두었다 — 함수 내부에서 지역 변수로 `XMM` 값을 스택에 저장할 때 `movaps`를 안전하게 쓸 수 있게 하기 위해서다.

### 정확한 규칙: "CALL 실행 직전에 RSP % 16 == 0"
x64 SysV ABI와 Microsoft x64 ABI 모두 다음을 요구한다:

```
CALL 명령을 실행하기 직전 시점: RSP는 16의 배수여야 한다.
```

`CALL`이 실행되면 반환 주소(8바이트)가 자동으로 PUSH되므로, **함수에 막 진입한 시점(첫 명령이 실행되기 직전)의 RSP는 "16의 배수 - 8"**, 즉 16으로 나누면 나머지가 8이 되는 값이다. 이게 헷갈리는 지점이다.

```
호출자에서 CALL 실행 직전:  RSP = 0x7ffee020   (16의 배수, 0x20 = 32)
CALL 실행 (반환주소 8바이트 push):  RSP = 0x7ffee018   (16 배수 - 8)
함수 진입 직후 (아직 프롤로그 전): RSP = 0x7ffee018   <- 이 상태가 "정상"
```

그래서 함수 프롤로그에서 `push rbp`를 한 번 하면 다시 16의 배수로 돌아온다(8바이트 push로 정렬이 맞춰짐):
```
push rbp        ; RSP -= 8  -> 0x7ffee010 (16의 배수로 복귀)
mov  rbp, rsp
sub  rsp, 0x20   ; 지역 변수 확보, 0x20은 16의 배수라 정렬 유지됨
```

**핵심 포인트**: 함수 내부에서 스택을 조작할 때(`PUSH`/`POP`/`SUB RSP`/`ADD RSP`) 8바이트 단위로 홀수 번 어긋나게 만들면, 그 함수가 다시 다른 함수를 `CALL`하는 시점에 정렬이 깨져서 피호출 함수 내부의 `movaps`가 예외를 던진다.

### 깨지는 대표 시나리오
1. **`PUSH`를 홀수 번 한 뒤 `CALL`하는 경우**: 함수 안에서 인자를 스택에 쌓느라 `push`를 3번 했는데(24바이트, 16의 배수), 원래 정렬이 8만큼 어긋난 상태(예: 프롤로그에서 `push rbp`를 안 하고 바로 시작)였다면 최종 `CALL` 시점에 정렬이 깨진다.
2. **셸코드/직접 작성한 어셈блли에서 정렬을 신경 안 쓴 경우**: CTF pwn 문제나 직접 짠 어셈블리 스텁에서 `call printf` 전에 `RSP`가 16의 배수인지 확인하지 않으면, 시스템에 따라(특히 `libc` 내부가 `movaps`를 쓰는 최신 배포판) 크래시가 난다.
3. **인라인 어셈블리(`__asm`)에서 `PUSH`/`POP` 균형이 안 맞는 경우**: 컴파일러가 생성한 정렬 보장 코드를 인라인 어셈블리가 깨뜨리는 경우.
4. **Windows x64 Shadow Space를 빼먹은 경우**: Microsoft x64 ABI는 `CALL` 전에 처음 4개 인자용으로 32바이트의 "shadow space"를 추가로 확보해야 하는데, 이를 빼먹으면 정렬 자체는 맞아도 호출된 함수가 자신의 인자를 저장할 공간을 침범해서 다른 종류의 손상이 발생할 수 있다(정렬 문제와는 별개지만 같이 자주 헷갈리는 원인).

### 32비트(x86)에서는 상대적으로 느슨하다
x86(32비트)은 ABI 관례상 정렬 요구가 더 느슨한 경우가 많지만(스택 항목이 4바이트 단위), 최신 컴파일러와 SIMD 최적화가 늘면서 x86에서도 특정 함수(특히 SSE를 쓰는)에서 16바이트 정렬을 기대하는 코드가 생길 수 있다. 하지만 이 문제는 x64에서 압도적으로 더 자주, 더 엄격하게 나타난다.

## 화면/코드에서 보이는 징후
```asm
; 정렬이 깨진 예 - push를 홀수 번 하고 바로 call
push    rax          ; RSP -= 8 (정렬이 8만큼 어긋남)
call    some_libc_func ; 이 시점 RSP가 16의 배수가 아님!
; -> some_libc_func 내부에서 movaps [rsp+x], xmm6 같은 코드가 있으면 #GP
```
디버거에서 크래시 순간 `RSP` 값을 확인했을 때:
```text
RSP = 0x00007ffddead1008   ; 마지막 세 자리가 ...008 -> 16으로 나누면 나머지 8, CALL 직전이라면 비정상
```

## 가장 먼저 할 것
크래시 지점이 `movaps`/`movdqa` 계열 명령이라면(또는 라이브러리 함수 내부 깊은 곳에서 이유 없이 죽는다면), 가장 먼저 그 함수를 호출한 지점(콜 스택 한 단계 위)으로 가서 `CALL` 실행 직전의 `RSP` 값이 16의 배수인지 계산한다(`RSP % 16`).

## 단계별 절차
**1) 크래시 명령 확인**

디버거의 크래시 로그에서 정확히 어떤 명령에서 예외가 났는지 확인한다. `movaps`, `movdqa`처럼 이름에 "Aligned"가 들어가는 SIMD 명령이면 이 문서의 시나리오일 가능성이 매우 높다.

**2) 콜 스택을 한 단계 거슬러 올라가기**

x64dbg는 "Call Stack" 창, GDB는 `bt`(backtrace)로 이 함수를 호출한 지점을 찾는다.

**3) 그 CALL 직전의 RSP 확인**

호출자 함수에서 문제의 `call` 명령 바로 위에 브레이크포인트를 걸고 `RSP` 값을 16으로 나눠본다.
```text
(gdb) x/1gx $rsp
(gdb) p $rsp % 16
```
결과가 0이 아니면 정렬이 깨진 것이다.

**4) 정렬이 깨진 지점까지 거슬러 올라가기**

호출자 함수의 시작부터 `push`/`pop`/`sub rsp`/`add rsp` 명령의 누적 바이트 수를 세어본다. 짝이 안 맞는 `push`나 `sub rsp`에 16의 배수가 아닌 값(`sub rsp, 8`처럼 8만 뺀 경우 등)이 있는지 확인한다.

**5) 직접 작성/패치한 코드라면 정렬 보정 추가**

셸코드나 인라인 어셈블리를 직접 작성 중이라면, 라이브러리 함수를 호출하기 직전에 명시적으로 정렬을 맞춘다:
```asm
and     rsp, -0x10   ; RSP를 16의 배수로 내림 정렬 (원래 RSP는 별도로 저장해뒀다가 나중에 복원)
```
단, 이렇게 원본 `RSP`를 강제로 버리면 이후 스택 기반 지역 변수 접근이 깨질 수 있으므로, 정렬 전에 원래 `RSP`를 별도 레지스터에 저장해두는 것이 안전하다.

## 명령어/단축키
- GDB/Pwndbg: `p $rsp`, `p $rsp % 16`, `bt`(backtrace로 호출자 확인), `x/4i $pc`(크래시 지점 근처 명령 확인)
- x64dbg: 크래시 시 자동으로 멈춘 지점에서 레지스터 패널의 `RSP` 확인, "Call Stack" 탭으로 호출 경로 추적
- IDA 디버거: 크래시 시 `Exceptions` 로그, 레지스터 창에서 `RSP` 값, Alt+K(스택 뷰)로 스택 내용 확인

## 출력 해석
- `RSP % 16 == 8`(CALL 직전 기준) → 정상. 함수에 막 진입한 시점 기준으로는 이 값이 맞다.
- `RSP % 16 == 0`(함수 내부, `push rbp` 이후) → 정상.
- 그 외의 나머지 값(1~7, 9~15) → 정렬이 깨진 상태. 어딘가에서 홀수 개의 8바이트 단위 스택 조작(`push` 단독, `sub rsp, 8`)이 짝이 안 맞게 일어났다는 뜻이다.

## 흔한 실수
- 정렬 깨짐을 "메모리 손상 버그(힙 오버플로우 등)"로 오인하고 엉뚱한 곳(힙, 전역 변수)을 뒤지는 것 — 크래시 지점이 `movaps`라면 먼저 스택 정렬부터 의심하는 게 훨씬 빠르다.
- x86(32비트) 코드에서도 x64와 똑같이 16바이트 정렬이 항상 필수라고 오해하는 것 — x86은 상대적으로 요구가 느슨하다(다만 컴파일러/라이브러리에 따라 SSE를 쓰면 여전히 문제가 될 수 있음).
- 직접 셸코드를 짤 때 `call printf`류의 라이브러리 함수 호출 전에 정렬을 전혀 신경 쓰지 않는 것 — 오래된 libc에서는 우연히 동작했더라도, SIMD 최적화가 들어간 최신 libc(예: `memcpy`/`strlen`의 AVX 구현)에서는 바로 크래시가 난다.
- 정렬을 맞추려고 `and rsp, -16`을 쓰면서 원래 `RSP`를 저장해두지 않아, 함수가 끝날 때 원래 스택 위치로 복귀하지 못해 다른 크래시를 만드는 것.

## 막혔을 때 다음 체크
- 크래시 지점이 `movaps`가 아니라 다른 명령이면 → 이 문서의 범위가 아닐 수 있다(순수 널 포인터 역참조, 버퍼 오버플로우 등 다른 원인 우선 의심).
- Windows x64 API 호출인데 정렬은 맞는 것 같은데도 크래시가 난다면 → Shadow space(32바이트)를 확보했는지 확인(REV-0071의 Microsoft x64 호출 규약 설명 참고).
- 직접 작성한 어셈블리가 원인이면 → 함수 진입부터 크래시 지점까지 모든 `push`/`pop`/`sub rsp`/`add rsp`를 순서대로 나열해서 누적 바이트 수를 손으로 계산해본다.

## 미니 예제

**예제 1 — 정상: push rbp로 정렬이 자연스럽게 맞는 경우**
```asm
func:
    push    rbp         ; RSP -= 8 (진입 시 16배수-8 이었다면 -> 16배수로 복귀)
    mov     rbp, rsp
    sub     rsp, 0x20    ; 16의 배수만큼 확보, 정렬 유지
    call    printf        ; 이 시점 RSP는 16의 배수 -> 정상
```

**예제 2 — 깨짐: push를 한 번 더 해서 정렬이 어긋난 경우**
```asm
func:
    push    rbp
    mov     rbp, rsp
    push    rax          ; 추가 push 1회 -> 정렬이 8만큼 어긋남
    call    printf         ; 이 시점 RSP가 16의 배수가 아님 -> printf 내부에서 크래시 가능
```

**예제 3 — 셸코드에서 정렬을 명시적으로 맞추는 패턴**
```asm
mov     r15, rsp        ; 원래 RSP 백업
and     rsp, -0x10        ; 16의 배수로 정렬(내림)
call    some_libc_func     ; 정렬된 상태로 안전하게 호출
mov     rsp, r15          ; 원래 RSP로 복원
```

**예제 4 — GDB로 정렬 깨짐 확인**
```text
(gdb) run
Program received signal SIGSEGV, Segmentation fault.
0x00007ffff7a52340 in __memmove_avx_unaligned_erms ()
(gdb) p $rsp
$1 = (void *) 0x7fffffffe018
(gdb) p $rsp % 16
$2 = 8
```
크래시 지점이 SIMD 관련 libc 내부 함수이고 `$rsp % 16`이 `CALL` 직전 기준으로 맞지 않는 값이면, 이 문서에서 설명한 정렬 문제일 가능성이 높다.

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기
- REV-0487 — SIMD 명령이 나와서 디컴파일이 이상해 보일 때
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동

## 출처/검증
- x64 ABI의 CALL 직전 16바이트 스택 정렬 요구사항: System V Application Binary Interface AMD64 Architecture Processor Supplement, "The Stack Frame" 섹션 기준 (2026-09-08 검증).
- Microsoft x64 호출 규약의 스택 정렬 및 Shadow Space: Microsoft Learn "x64 calling convention" 공식 문서 기준.
- `MOVAPS`/`MOVDQA`의 정렬 요구사항과 `#GP` 예외: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 해당 명령어 "Exceptions" 섹션 기준.
