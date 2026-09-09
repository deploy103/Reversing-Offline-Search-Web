---
id: REV-1101
title: "ARM/ARM64 레지스터와 호출 규약 기초"
slug: "rev-1101-arm-registers-calling-convention"
category: "other-targets"
difficulty: "basic"
platform: [linux, android]
architecture: [ARM, ARM64]
format: [ELF]
tools: [Ghidra, IDA, GDB]
keywords: ["AAPCS", "AAPCS64", "ARM 호출 규약", "ARM64 호출 규약", "R0 R1 R2 R3", "X0 X7", "링크 레지스터", "LR"]
aliases: ["ARM calling convention", "ARM64 인자 전달", "ARM에서 함수 인자는 어디에 있나", "링크 레지스터가 뭔가"]
symptom_keywords: ["ARM 바이너리인데 스택에서 인자를 못 찾겠음", "call 명령어가 안 보임", "리턴 주소가 스택에 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
ARM(32비트, AAPCS)은 처음 네 개의 정수 인자를 `R0`~`R3`에, ARM64(AAPCS64)는 처음 여덟 개를 `X0`~`X7`에 담아 전달하며, 함수 복귀 주소는 x86처럼 스택에 자동으로 push되는 것이 아니라 `BL`/`BLX` 명령이 실행되는 순간 링크 레지스터(ARM `LR`=R14, ARM64 `X30`)에 저장된다는 점이 x86 CALL/스택 기반 인자 전달과 가장 크게 다르다.

## 언제 검색해야 하나
- Ghidra/IDA로 ARM 바이너리를 열었는데 함수 시작 부분에 `PUSH {R4, R5, LR}` 같은 명령이 보이고 인자가 어디 있는지 모를 때
- `main` 함수 진입부에서 스택 대신 `R0`, `R1` 레지스터 값을 봐야 한다는 걸 알았지만 몇 번째 인자가 어느 레지스터인지 헷갈릴 때
- GDB(`gdb-multiarch`)로 ARM 바이너리를 디버깅하며 `info registers`를 쳤는데 x86의 `RSP`/`RIP` 감각으로 레지스터를 못 찾을 때
- 함수 반환 명령이 `RET` 대신 `BX LR`이나 `POP {..., PC}`로 되어 있어서 당황할 때

## 핵심 개념

### 레지스터 세트 개요
ARM(AArch32, 32비트)은 범용 레지스터 16개(`R0`~`R15`)를 갖는다. 이 중 몇 개는 특수 역할이 고정되어 있다.
- `R0`~`R3` (별칭 `a1`~`a4`): 함수 인자 전달용, 반환값은 `R0`
- `R4`~`R11`: 콜리 세이브(callee-saved) 일반 레지스터
- `R12` (`IP`): 스크래치 레지스터(intra-procedure call)
- `R13` (`SP`): 스택 포인터
- `R14` (`LR`): 링크 레지스터, 복귀 주소 저장
- `R15` (`PC`): 프로그램 카운터

ARM64(AArch64, 64비트)는 범용 레지스터가 31개(`X0`~`X30`)로 늘어나고, 32비트 뷰는 같은 레지스터의 하위 32비트를 가리키는 `W0`~`W30`으로 접근한다.
- `X0`~`X7`: 함수 인자 전달용(부동소수점/SIMD는 별도로 `V0`~`V7`), 반환값은 `X0`(128비트 반환 시 `X0:X1`)
- `X8`: 큰 구조체(16바이트 초과)를 값으로 반환할 때 결과를 쓸 메모리 주소를 담는 간접 결과 레지스터
- `X9`~`X15`: 콜러 세이브(caller-saved) 스크래치
- `X16`, `X17` (`IP0`, `IP1`): 링커/PLT 스텁이 임시로 쓰는 인트라프로시저 호출 스크래치 레지스터
- `X19`~`X28`: 콜리 세이브(callee-saved)
- `X29` (`FP`): 프레임 포인터
- `X30` (`LR`): 링크 레지스터
- `SP`: 별도의 스택 포인터 레지스터(범용 레지스터 번호에 포함되지 않음)

### x86과의 결정적 차이 — 인자 전달
x86(SysV AMD64, REV-0106)은 처음 여섯 개 정수 인자를 `RDI, RSI, RDX, RCX, R8, R9`에 담고, Windows x64(REV-0122)는 `RCX, RDX, R8, R9`를 쓴다. ARM 계열도 "레지스터로 인자를 전달한다"는 큰 그림은 같지만 구체적 레지스터 이름과 개수가 다르다: ARM32는 4개(`R0`-`R3`), ARM64는 8개(`X0`-`X7`)까지 레지스터로 전달하고 그 이상은 스택으로 넘어간다. 64비트 타입(예: `long long`)은 ARM32에서 두 개의 연속된 레지스터 쌍(`R0`/`R1` 등)을 차지한다.

### x86과의 결정적 차이 — CALL/RET vs BL/BX
x86의 `CALL`(REV-0071)은 반환 주소를 스택에 push한 뒤 점프하고, `RET`(REV-0072)은 스택에서 그 주소를 pop해 되돌아간다. ARM은 스택을 쓰지 않고 전용 레지스터를 쓴다.
- 함수 호출: `BL <주소>`(Branch with Link)가 실행되면, 현재 명령어 다음 주소가 자동으로 `LR`(ARM32) 또는 `X30`(ARM64)에 저장되고 지정된 주소로 분기한다.
- 함수 복귀: 리프 함수(다른 함수를 호출하지 않는 함수)는 그냥 `BX LR`(ARM32) 또는 `RET`(ARM64, 내부적으로 `X30`을 사용하는 특수 분기)로 복귀한다.
- 논리프 함수(다른 함수를 호출하는 함수)는 진입부에서 `LR`/`X30`을 스택에 저장해두지 않으면, 안에서 다시 `BL`을 호출하는 순간 `LR`이 덮어써져 원래 복귀 주소를 잃어버린다. 그래서 논리프 함수의 프롤로그에는 거의 항상 `LR`/`X30`을 저장하는 코드가 있다.

```asm
; ARM32 예 - 논리프 함수 프롤로그/에필로그
PUSH {R4, LR}      ; LR을 스택에 저장(다른 함수 호출에 대비)
...
BL   sub_func       ; 호출 - LR이 여기서 갱신됨
...
POP  {R4, PC}       ; 저장해둔 LR 값을 PC에 직접 복원 = 복귀
```
```asm
; ARM64 예
STP  X29, X30, [SP, #-16]!   ; 프레임 포인터, LR(X30)을 함께 저장
MOV  X29, SP
BL   sub_func
LDP  X29, X30, [SP], #16     ; 복원
RET                          ; X30 주소로 복귀
```

### 프레임 포인터 관례
ARM64는 `X29`가 관례적으로 프레임 포인터(FP) 역할을 하며, `X30`(LR)과 함께 `STP`/`LDP`(pair 저장/로드) 명령으로 짝지어 스택에 저장되는 패턴이 매우 흔하다. ARM32는 `R11`(또는 `R7`, ABI/컴파일러에 따라 다름)이 프레임 포인터로 쓰이기도 하지만 최적화 빌드에서는 생략되는 경우가 많다.

## 화면/코드에서 보이는 징후
- 함수 진입부에 `PUSH {..., LR}`(ARM32) 또는 `STP X29, X30, [SP, #-N]!`(ARM64)가 보임
- 함수 인자로 보이는 값이 스택이 아니라 `R0`, `R1`, `X0`, `X1` 레지스터에서 곧바로 쓰임
- `CALL` 대신 `BL`, `RET` 대신 `BX LR` 또는 단독 `RET`가 보임
- Ghidra/IDA 디스어셈블리 상단에 아키텍처가 `ARM` 또는 `AARCH64`로 표시됨

## 가장 먼저 할 것
Ghidra/IDA에서 함수를 열었을 때 파라미터 개수가 4개(또는 8개) 이하라면 레지스터 이름(`R0`~`R3` 또는 `X0`~`X7`)만 보고도 몇 번째 인자인지 바로 알 수 있다는 점을 기억하고, 함수 진입부의 `PUSH`/`STP`에 `LR`/`X30`이 포함되어 있는지부터 확인해 리프 함수인지 판단한다.

## 단계별 절차
1. 바이너리 아키텍처가 ARM32인지 ARM64인지 먼저 확인(REV-1104 참고)
2. 함수 진입부(`PUSH`/`STP`)에서 `LR`/`X30`이 저장되는지 확인 — 저장되면 논리프 함수, 저장 안 되면 리프 함수
3. 함수 인자 개수를 확인하고 ARM32는 `R0`부터, ARM64는 `X0`부터 순서대로 대응
4. 4개(ARM32)/8개(ARM64)를 넘는 인자가 있으면 스택(`[SP, #N]`)에서 나머지를 찾음
5. 함수 반환 직전에 `R0`/`X0`에 쓰인 마지막 값이 반환값임을 확인
6. GDB(`gdb-multiarch`)로 실제 실행 중이면 `info registers`로 `r0-r3`/`x0-x7`, `lr`/`x30` 값을 직접 확인해 정적 분석과 대조

## 명령어/단축키
```bash
# gdb-multiarch에서 ARM 레지스터 확인
(gdb) info registers
(gdb) p $r0        # ARM32
(gdb) p $x0        # ARM64
(gdb) p $lr         # 링크 레지스터 (ARM32)
(gdb) p $x30        # 링크 레지스터 (ARM64)

# 디스어셈블에서 BL/RET 위치만 빠르게 찾기
objdump -d chall | grep -E "bl |bx lr|ret"
```

## 출력 해석
- `PUSH {R4, R5, LR}` → 이 함수는 `R4`, `R5`를 보존해야 하고(콜리 세이브 레지스터 사용) 내부에서 다른 함수를 호출한다(`LR` 저장).
- `MOV R0, #0` 다음 `POP {..., PC}` → 반환값 0을 `R0`에 넣고 저장해뒀던 복귀 주소를 `PC`에 직접 복원해 복귀하는 것 — x86의 `MOV EAX, 0; RET`와 동일한 의미.
- ARM64에서 `STP X29, X30, [SP, #-32]!` → 프레임 포인터와 링크 레지스터를 스택에 한 번에 저장하며 스택을 32바이트 확보(`!`는 사전 인덱싱 후 SP 갱신).

## 흔한 실수
- x86 습관대로 스택에서 인자를 찾으려는 것 — ARM/ARM64는 처음 몇 개 인자가 항상 레지스터에 있다.
- `BL`을 보고 x86 `CALL`처럼 "스택에 복귀 주소가 쌓였겠지"라고 가정하는 것 — ARM은 레지스터(`LR`/`X30`)에 저장한다.
- 리프 함수(내부에서 `BL`을 쓰지 않는 짧은 함수)에서 `LR`이 스택에 저장되지 않는 것을 보고 "버그"라고 오해하는 것 — 저장할 필요가 없으므로 정상이다.
- ARM32와 ARM64의 레지스터 이름을 혼동하는 것(`R0`-`R3` vs `X0`-`X7`, 개수와 접두문자가 다름).

## 막혔을 때 다음 체크
- x86 SysV/Windows 호출 규약과 정확히 비교하고 싶다면 → REV-0106 SysV AMD64 Calling Convention, REV-0122 Microsoft x64 Calling Convention
- 반환 명령/CALL 명령 자체의 x86 의미가 헷갈리면 → REV-0071 CALL, REV-0072 RET
- 어셈블리가 16비트 Thumb 명령으로 보여서 레지스터 목록이 안 맞는 것 같으면 → REV-1102 ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- Ghidra/IDA에서 이 아키텍처로 처음 불러오는 법 자체가 궁금하면 → REV-1104 Ghidra/IDA에서 ARM 바이너리 아키텍처 설정하기

## 미니 예제
```asm
; ARM32: int add3(int a, int b, int c) 형태의 함수
add3:
    PUSH {LR}          ; 리프가 아니라고 가정, LR 보존
    ADD  R0, R0, R1     ; a + b, R0에 결과
    ADD  R0, R0, R2     ; + c
    POP  {PC}          ; 저장해둔 복귀 주소로 바로 복귀
```
```asm
; ARM64: 동일 로직
add3:
    ADD  W0, W0, W1
    ADD  W0, W0, W2
    RET
```
ARM64 쪽은 세 인자를 더하기만 하고 다른 함수를 호출하지 않는 완전한 리프 함수라서 `X30`을 저장할 필요조차 없다 — `RET` 한 줄로 바로 복귀한다.

## 관련 글
- REV-0106 — SysV AMD64 Calling Convention
- REV-0122 — Microsoft x64 Calling Convention
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-1102 — ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- REV-1104 — Ghidra/IDA에서 ARM 바이너리 아키텍처 설정하기

## 출처/검증
- ARM32 레지스터 역할(`R0`-`R3` 인자, `R12` IP, `R13` SP, `R14` LR, `R15` PC)과 인자 전달 규칙: ARM-software/abi-aa 공식 저장소 AAPCS32 명세 (https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst) 기준 확인(2026-09-10).
- ARM64 레지스터 역할(`X0`-`X7` 인자, `X8` 간접 결과, `X16`/`X17` IP0/IP1, `X29` FP, `X30` LR)과 8개 인자 규칙: ARM-software/abi-aa 공식 저장소 AAPCS64 명세 (https://github.com/ARM-software/abi-aa/blob/main/aapcs64/aapcs64.rst) 및 공식 PDF(Procedure Call Standard for the Arm 64-bit Architecture) 기준.
- `BL`이 링크 레지스터에 복귀 주소를 저장하고 `BX`/`RET`으로 복귀하는 동작, 논리프 함수의 `LR` 저장 관례: ARM 공식 문서 및 다수 ARM 어셈블리 튜토리얼(Azeria Labs 등) 교차 확인.
