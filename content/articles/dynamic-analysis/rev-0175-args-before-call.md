---
id: REV-0175
title: "CALL 직전 함수 인자 확인하는 법"
slug: "rev-0175-args-before-call"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - function arguments
  - 함수 인자
  - CALL 직전
  - RDI RSI RDX RCX R8 R9
  - RCX RDX R8 R9
  - SysV calling convention
  - Windows x64 calling convention
  - argument registers
  - 인자 레지스터
aliases:
  - CALL 전에 인자 보는법
  - 함수 인자 확인하는법
  - RDI RSI 인자 확인
  - RCX RDX 인자 확인
  - 함수 호출 직전 레지스터
  - 인자가 몇번째 레지스터인지
symptom_keywords:
  - 함수 인자가 뭔지 모르겠음
  - CALL 직전에 뭘 봐야하는지 모르겠음
  - RDI RSI 인자 확인하는법
  - RCX RDX R8 R9 인자
  - 함수에 뭘 넘기는지 모르겠음
  - 인자 개수가 몇개인지 모르겠음
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CALL 명령어가 실행되기 **직전**(아직 실행 안 된 그 줄)에 브레이크포인트를 걸면, 그 순간 인자 레지스터(SysV Linux는 RDI/RSI/RDX/RCX/R8/R9, Windows x64는 RCX/RDX/R8/R9)에 이미 세팅되어 있는 실제 값을 디버거에서 그대로 읽어 "이 함수가 무엇을 인자로 받는지"를 확정할 수 있다.

## 언제 검색해야 하나
- IDA에서 `call sub_401500` 같은 코드를 봤는데 이 함수가 인자를 몇 개, 어떤 값으로 받는지 정적 분석만으로는 계산이 복잡해서 헷갈릴 때
- 인자가 레지스터가 아니라 계산된 값(예: 이전 함수의 반환값, 복잡한 산술 결과)이라서 코드만 봐서는 실제 값을 가늠하기 어려울 때
- Windows 바이너리인데 SysV 순서(RDI, RSI...)로 착각하고 엉뚱한 레지스터를 보고 있을 때, 또는 그 반대일 때
- 인자가 5개 이상이라 스택으로 넘어가는 부분까지 있는 함수를 분석할 때
- CALL 직전에 정확히 몇 번째 줄에 브레이크포인트를 걸어야 하는지 감이 안 잡힐 때

## 핵심 개념

### 왜 "CALL 직전"이라는 타이밍이 중요한가
호출 규약(calling convention)에 따라 함수를 부르기 전에 호출자가 정해진 레지스터(또는 스택)에 인자 값을 미리 세팅해 둔다(REV-0071 참고). 이 세팅은 CALL 명령어 이전 여러 줄에 걸쳐 이루어질 수 있고, 순서도 코드 작성 순서와 다를 수 있다(컴파일러 최적화). 따라서 "인자가 뭔지 확인하고 싶다"면, **CALL 명령어 자체의 주소**(즉 CALL이 아직 실행되지 않은 시점)에 브레이크포인트를 걸어야 한다. 이 시점이면 그 위의 모든 `mov`/`lea`/`xor` 등에 의한 레지스터 세팅이 이미 끝나 있고, 아직 함수 내부로 들어가지 않았으므로 "호출 직전의 완전한 인자 스냅샷"을 볼 수 있다.

CALL 명령어 **다음** 주소에 브레이크포인트를 걸면 이미 함수 안으로 들어가 있을 수도 있고(Step Into 상황), 레지스터 값이 함수 내부 로직에 의해 이미 변경되었을 수도 있으므로 늦다.

### SysV AMD64 (Linux/macOS) 인자 레지스터
정수/포인터 인자는 순서대로 다음 레지스터에 담긴다.
```
1번째: RDI
2번째: RSI
3번째: RDX
4번째: RCX
5번째: R8
6번째: R9
7번째 이후: 스택 (오른쪽 인자부터 PUSH)
```
부동소수점 인자(float/double)는 별도로 XMM0~XMM7 순서를 쓴다.

### Microsoft x64 (Windows) 인자 레지스터
정수/포인터 인자는 순서대로 다음 레지스터에 담긴다.
```
1번째: RCX
2번째: RDX
3번째: R8
4번째: R9
5번째 이후: 스택
```
Windows x64는 **shadow space**라는 개념이 있다 — 호출자가 CALL 전에 스택에 최소 32바이트(4개 인자용 슬롯)를 미리 확보해 둬야 한다(실제로 처음 4개 인자가 레지스터로 전달되더라도, 피호출 함수가 필요시 그 값을 저장할 여분 공간이다). 디스어셈블리에서 `sub rsp, 0x20` 뒤에 CALL이 오는 패턴이 이 shadow space 확보다.

### 어느 규약을 쓰는지 빠르게 판단하는 법
- 바이너리가 **PE(.exe/.dll)** 이면 Microsoft x64 규약(RCX, RDX, R8, R9)
- 바이너리가 **ELF** 이면 SysV AMD64 규약(RDI, RSI, RDX, RCX, R8, R9)
- x86(32비트)는 두 플랫폼 모두 보통 스택으로 인자를 전달한다(cdecl/stdcall 등, 레지스터 인자 규약은 x64에서만 표준화됨).
- IDA/Ghidra는 이 판단을 자동으로 해서 디컴파일 결과에 `func(a1, a2, a3)` 형태로 정리해 보여주지만, 어셈블리 원문이나 디버거의 레지스터 창을 직접 읽을 때는 이 순서를 외워두는 게 훨씬 빠르다.

### 5번째 이후 인자(스택 인자) 확인하기
인자가 5개(Windows) 또는 7개(SysV)를 넘어가면 나머지는 CALL 직전 스택에 PUSH되어 있다. 이 경우 CALL 직전 시점에 RSP가 가리키는 스택 맨 위부터 순서대로 5번째(또는 7번째) 인자, 6번째 인자... 가 쌓여 있다. 디버거의 스택 창(REV-0173 참고)에서 RSP 기준으로 위에서부터 읽으면 된다.

### 포인터 인자는 그 자체가 아니라 가리키는 내용도 확인
인자가 포인터(주소)인 경우, 레지스터 값 자체(주소)만 봐서는 무슨 데이터를 넘기는지 알 수 없다. x64dbg에서는 레지스터를 우클릭 → "Follow in Dump"로, GDB에서는 `x/s $rdi`(문자열이라면) 또는 `x/8xb $rdi`(바이트로) 등으로 그 주소가 가리키는 실제 데이터를 확인해야 한다.

## 화면/코드에서 보이는 징후
- CALL 직전 여러 줄에 걸쳐 `mov`, `lea`, `xor` 등이 RDI/RSI/RDX/RCX/R8/R9(또는 RCX/RDX/R8/R9) 중 몇 개를 채우는 패턴이 반복해서 보인다.
- Windows x64에서 CALL 직전에 `sub rsp, 0x20`(또는 0x28, 0x30 등 32의 배수 이상) 후 CALL이 오면 shadow space 확보 패턴이다.
- IDA 디컴파일 화면에서 `func(a1, a2)`처럼 인자가 정리된 형태로 보이면, IDA가 이미 이 레지스터 순서를 분석해서 보여준 것이다.

## 가장 먼저 할 것
1. 바이너리가 PE인지 ELF인지 확인해서 어느 호출 규약(Windows x64 vs SysV)을 적용할지 정한다.
2. 분석할 CALL 명령어의 정확한 주소를 IDA/Ghidra에서 확인한다.
3. 그 CALL 주소 자체(CALL이 실행되기 직전)에 브레이크포인트를 건다.

## 단계별 절차

**x64dbg**
1. 디스어셈블리 창에서 분석할 `call` 명령어 줄을 찾는다(`Ctrl+G`로 주소 이동 가능).
2. 그 `call` 줄을 클릭하고 `F2`로 브레이크포인트를 건다.
3. `F9`로 실행해서 그 지점까지 도달시킨다 — 이 시점에서 CALL은 아직 실행되지 않았다.
4. 레지스터 창에서 순서대로 확인한다.
   - Windows PE라면: RCX(1번째), RDX(2번째), R8(3번째), R9(4번째)
   - Linux ELF라면: RDI(1번째), RSI(2번째), RDX(3번째), RCX(4번째), R8(5번째), R9(6번째)
5. 인자가 더 있다면 Stack 창에서 RSP 기준 위에서부터 순서대로 확인한다.
6. 포인터 인자라면 해당 레지스터를 우클릭 → "Follow in Dump"로 실제 데이터를 확인한다.

**GDB / Pwndbg**
1. CALL 명령어 주소에 브레이크포인트를 건다:
   ```
   break *0x401234
   ```
2. `run`으로 실행한다.
3. 인자 레지스터를 순서대로 확인한다.
   - SysV(Linux, ELF):
     ```
     p/x $rdi
     p/x $rsi
     p/x $rdx
     p/x $rcx
     p/x $r8
     p/x $r9
     ```
   - Windows x64(PE, WSL에서 Windows 바이너리를 GDB로 볼 때 등):
     ```
     p/x $rcx
     p/x $rdx
     p/x $r8
     p/x $r9
     ```
4. Pwndbg를 쓰면 CALL 직전에 정지했을 때 `context` 화면에 이미 다음 호출의 인자 후보가 자동으로 정리되어 나오는 경우가 많다(레지스터 값이 스택/문자열을 가리키면 자동 풀이).
5. 포인터 인자의 실제 내용을 보려면:
   ```
   x/s $rdi        ; 문자열로 해석
   x/8xb $rdi       ; 바이트 단위로 확인
   ```
6. 스택으로 넘어간 인자(5번째/7번째 이후)를 확인하려면:
   ```
   x/4xg $rsp
   ```

## 명령어/단축키
- x64dbg: `F2`(브레이크포인트), `F9`(실행), 레지스터 창(RCX/RDX/R8/R9 또는 RDI/RSI/RDX/RCX/R8/R9 직접 확인), 레지스터 우클릭 → "Follow in Dump"
- GDB/Pwndbg: `break *<CALL 주소>`, `run`, `p/x $rdi`~`$r9`(SysV) 또는 `p/x $rcx $rdx $r8 $r9`(Windows x64), `x/s <reg>`(문자열 확인), `x/Nxg $rsp`(스택 인자 확인)

## 출력 해석
- Windows x64 바이너리에서 CALL 직전 RCX가 어떤 유효한 힙/스택 주소이고, GDB `x/s`나 x64dbg Dump에서 문자열이 보인다면 그 함수의 첫 인자가 문자열 포인터(예: `LPCWSTR`)라는 뜻이다.
- SysV 바이너리에서 CALL 직전 RDI가 작은 정수(예: `0x3`)이고 RSI가 유효한 메모리 주소, RDX가 다른 작은 정수라면 `read(fd, buf, count)`처럼 `(int, void*, size_t)` 형태의 함수 원형을 짐작할 수 있다.
- 인자로 예상한 레지스터 값이 함수 시작부에서 즉시 스택(`[rbp-...]`)으로 다시 저장되는 코드가 보인다면, 그 함수가 인자를 지역 변수 공간에 백업해 두고 쓰는 전형적인 패턴이다 — 저장 이후에는 레지스터가 아니라 그 스택 위치의 값을 계속 추적해야 한다.

## 흔한 실수
- CALL **다음** 주소에 브레이크포인트를 걸어놓고 인자를 확인하려는 것 — 이미 함수 안에서 인자 레지스터가 다른 용도로 재사용됐을 수 있으므로 반드시 CALL **자체의 주소**에 걸어야 한다.
- Windows PE 바이너리인데 SysV 순서(RDI부터)로 읽거나, 반대로 ELF인데 Windows 순서(RCX부터)로 읽는 것 — 플랫폼(PE/ELF)을 먼저 확인하는 습관을 들인다.
- 3번째 인자부터 두 규약에서 레지스터 이름이 겹치는 경우(RDX)가 있다고 착각하는 것 — SysV의 3번째는 RDX, Windows x64의 2번째도 RDX이지만 이건 순서상 위치가 다른 것이지 우연히 이름이 겹치는 것뿐이다. 반드시 몇 번째 인자인지부터 세어야 한다.
- 부동소수점 인자를 정수 레지스터(RDI 등)에서 찾으려는 것 — float/double 인자는 XMM0~XMM7 레지스터를 따로 쓴다.
- shadow space(Windows x64의 `sub rsp, 0x20`)를 인자 전달의 일부로 착각하는 것 — 이건 스택 공간 예약일 뿐, 5번째 이후 인자가 없다면 실제 데이터가 안 담겨 있을 수 있다.

## 막혔을 때 다음 체크
- 인자 값이 이상하다면 → 정말 CALL 직전(실행 전) 시점에 멈춰 있는지, 혹시 이미 한 스텝 더 지나가지 않았는지 확인한다.
- 어느 규약인지 헷갈린다면 → 파일 형식(PE/ELF)부터 다시 확인한다(REV-0175는 두 규약 모두를 항상 같이 대조하는 습관을 권장한다).
- 인자가 몇 개인지 모르겠다면 → IDA에서 해당 함수를 F5로 디컴파일해서 함수 시그니처를 먼저 확인하거나, 함수 내부에서 어느 레지스터들이 실제로 읽히는지(사용되는지) 관찰한다.
- 포인터 인자가 가리키는 값이 계속 바뀐다면 → 그 메모리 주소에 워치포인트를 걸어(REV-0169) 언제 채워지는지 추적한다.

## 미니 예제

**x64dbg — Windows x64 API 호출 직전 인자 확인**
```asm
lea     rcx, [rip+FileName]  ; 1번째 인자 (RCX)
mov     edx, 80000000h        ; 2번째 인자 (RDX) - GENERIC_READ
mov     r8d, 1                 ; 3번째 인자 (R8) - FILE_SHARE_READ
xor     r9d, r9d               ; 4번째 인자 (R9) - lpSecurityAttributes = NULL
sub     rsp, 20h                ; shadow space 확보
call    cs:__imp_CreateFileW
```
`call` 줄에 `F2` → `F9` → 레지스터 창에서 RCX(경로 포인터, Follow in Dump로 문자열 확인), RDX(0x80000000), R8(1), R9(0) 확인.

**GDB/Pwndbg — SysV read() 호출 직전 인자 확인**
```asm
mov     edi, 0          ; 1번째 인자 (RDI) - fd = 0 (stdin)
lea     rsi, [rbp-0x30]  ; 2번째 인자 (RSI) - buf
mov     edx, 0x40        ; 3번째 인자 (RDX) - count = 64
call    read
```
```
(gdb) break *0x401234
(gdb) run
(gdb) p/x $rdi
$1 = 0x0
(gdb) p $rsi
$2 = (void *) 0x7fffffffe420
(gdb) p/x $rdx
$3 = 0x40
```
→ `read(0, 0x7fffffffe420, 0x40)` 형태로 호출된다는 것을 실제 값으로 확인했다.

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0172 — 레지스터 값을 실행 중 추적하는 법
- REV-0173 — 스택 값을 실행 중 추적하는 법
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- SysV AMD64 인자 레지스터 순서(RDI, RSI, RDX, RCX, R8, R9)와 스택 전달 규칙: System V Application Binary Interface AMD64 Architecture Processor Supplement 공식 스펙, "Parameter Passing" 절 기준.
- Microsoft x64 인자 레지스터 순서(RCX, RDX, R8, R9)와 shadow space(32바이트): Microsoft Learn "x64 calling convention" 공식 문서 기준.
- x64dbg 브레이크포인트/레지스터/Dump 기능: x64dbg 공식 문서 기준.
- GDB 레지스터 조회(`print`, `x`) 명령: GNU GDB 공식 매뉴얼 "Examining Data", "Examining Memory" 챕터 기준.
- 2026-09-08 검증.
