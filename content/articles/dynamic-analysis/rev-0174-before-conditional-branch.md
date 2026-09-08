---
id: REV-0174
title: "조건 분기 직전에 무엇을 봐야 하는가"
slug: "rev-0174-before-conditional-branch"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg]
keywords:
  - conditional branch
  - 조건 분기
  - Jcc
  - jz jnz je jne
  - jg jl ja jb
  - flags
  - 플래그 레지스터
  - ZF CF SF OF
  - cmp test
  - branch taken
aliases:
  - 분기 직전에 뭘봐야하나
  - Jcc 전에 확인할것
  - 조건점프 전 확인
  - jz jnz 왜 되는지
  - 분기가 왜 그렇게되는지
  - 플래그 확인하는법
symptom_keywords:
  - 왜 이 분기로 가는지 모르겠음
  - 조건 점프가 이해안됨
  - 플래그 값이 뭔지 모르겠음
  - jg jl 헷갈림
  - 분기 조건 확인하는법
  - 이 if문이 왜 참인지 모르겠음
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
조건 분기(`Jcc`, 예: `je`/`jne`/`jg`/`jl`) 직전에는 반드시 그 위에 있는 `cmp`나 `test` 명령이 무엇을 비교했는지, 그리고 그 결과로 어떤 플래그(ZF, SF, OF, CF)가 세팅됐는지를 확인해야 하며, 디버거의 플래그 창(x64dbg) 또는 `info registers`(GDB)로 이 값을 직접 보면 "왜 이 분기로 갔는지"를 추측이 아니라 확인으로 알 수 있다.

## 언제 검색해야 하나
- IDA에서 `cmp eax, 0Ah` 다음에 `jg loc_401250`가 나오는데, 왜 이쪽으로 분기했는지 손으로 계산하기 귀찮거나 헷갈릴 때
- `jg`(signed 초과)와 `ja`(unsigned 초과)처럼 비슷해 보이는 조건 분기가 실제로 다른 결과를 낼 때 그 이유를 확인하고 싶을 때
- 크랙미(crackme)의 시리얼 검증 로직에서 "이 분기만 반대로 가면 통과할 것 같다"는 지점을 실행 중 정확히 찾고 싶을 때
- x64dbg 플래그 창의 ZF, CF, SF, OF, PF 체크박스가 각각 무슨 뜻인지 모를 때
- GDB `info registers`의 `eflags` 줄에 나오는 `[ ZF PF ]` 같은 표기를 어떻게 읽어야 할지 모를 때

## 핵심 개념

### 왜 CMP/TEST와 Jcc를 항상 같이 봐야 하는가
x86/x64에서 조건 분기(`Jcc` 계열)는 스스로 값을 비교하지 않는다. **직전에 실행된 명령어가 남긴 플래그 레지스터(EFLAGS/RFLAGS)의 상태**를 읽어서 분기 여부를 결정할 뿐이다. 대부분의 경우 그 "직전 명령어"는 `cmp`(REV-0060) 또는 `test`(REV-0059)이지만, 사실 플래그를 바꾸는 어떤 산술/논리 명령(`sub`, `add`, `and`, `or` 등)이든 그 직후의 `Jcc`에 영향을 줄 수 있다. 따라서 조건 분기를 이해하려면 **그 분기 바로 위에서 가장 최근에 플래그를 변경한 명령어가 무엇인지**부터 찾아야 한다.

### CMP가 세팅하는 플래그
`cmp a, b`는 내부적으로 `a - b`를 계산하되 결과를 저장하지 않고 플래그만 남긴다(REV-0060 참고). 이때 세팅되는 주요 플래그:
- **ZF(Zero Flag)**: 결과가 0이면 1 (즉 `a == b`)
- **SF(Sign Flag)**: 결과의 최상위 비트(부호 비트)
- **CF(Carry Flag)**: unsigned 뺄셈에서 빌림(borrow)이 발생했는가 (`a < b`, unsigned 기준)
- **OF(Overflow Flag)**: signed 뺄셈에서 오버플로우가 발생했는가

### TEST가 세팅하는 플래그
`test a, b`는 `a AND b`를 계산하되 결과를 저장하지 않고 플래그만 남긴다(REV-0059 참고). 흔히 `test eax, eax`처럼 자기 자신과 AND해서 "이 값이 0인가, 음수인가"만 빠르게 확인하는 용도로 쓰인다. 이때 CF와 OF는 항상 0으로 세팅되고, ZF와 SF만 의미 있게 쓰인다.

### Jcc가 어떤 플래그 조합을 보는지 (REV-0088 요약)
- `JE`/`JZ` — ZF=1이면 분기 (같음/0)
- `JNE`/`JNZ` — ZF=0이면 분기 (다름/0아님)
- `JG`/`JNLE` (signed 초과) — ZF=0 그리고 SF=OF
- `JL`/`JNGE` (signed 미만) — SF≠OF
- `JGE`/`JNL` (signed 이상) — SF=OF
- `JLE`/`JNG` (signed 이하) — ZF=1 또는 SF≠OF
- `JA`/`JNBE` (unsigned 초과) — CF=0 그리고 ZF=0
- `JB`/`JNAE` (unsigned 미만) — CF=1
- `JAE`/`JNB` (unsigned 이상) — CF=0
- `JBE`/`JNA` (unsigned 이하) — CF=1 또는 ZF=1

signed 비교(`jg`/`jl` 계열)와 unsigned 비교(`ja`/`jb` 계열)가 **같은 CMP 결과**를 보고도 다르게 판단할 수 있다는 것이 리버싱에서 자주 헷갈리는 지점이다 — 자세한 진리표와 예시는 REV-0088을 참고한다.

### 실행 중 직접 확인하는 절차
정적으로 손 계산하는 대신, 디버거로 다음을 그대로 확인하면 훨씬 빠르고 정확하다.
1. `Jcc` 명령어 주소, 또는 그 직전 `cmp`/`test` 명령어 주소에 브레이크포인트를 건다(REV-0169).
2. 실행을 멈춘 시점에 비교 대상 값(레지스터 또는 메모리)의 실제 값을 확인한다(REV-0172).
3. 플래그 창(x64dbg) 또는 `info registers`의 eflags(GDB)에서 ZF/SF/OF/CF의 실제 상태를 확인한다.
4. 한 스텝(F7/F8 또는 `si`) 더 진행해서 실제로 분기했는지(RIP가 점프 대상으로 이동했는지) 아니면 분기하지 않고 다음 줄로 넘어갔는지 확인한다.

### 분기 결과를 직접 바꿔서 실험하기 (플래그 강제 조작)
디버거는 플래그 값을 실행 중 수동으로 바꿀 수 있게 해준다. x64dbg의 플래그 창에서 체크박스를 클릭하면 즉시 그 플래그 비트가 뒤집히고, 다음 `Jcc`가 다르게 동작하는지 바로 실험해볼 수 있다. GDB에서는 `set $eflags = ...` 또는 개별 비트를 조작하는 방식으로 가능하다(Pwndbg에서는 `set $zf = 1` 같은 편의 명령을 제공하기도 한다). 이는 "이 분기만 반대로 가면 어떻게 되는지" 크랙미 분석에서 매우 실용적인 확인 방법이다 — 실제 패치 없이도 그 자리에서 분기 결과를 테스트해볼 수 있다.

## 화면/코드에서 보이는 징후
- 어셈블리에서 `cmp`/`test` 바로 다음 줄에 `j`로 시작하는 명령어(`je`, `jne`, `jg`, `ja` 등)가 오는 패턴이 조건 분기의 표준 형태다.
- x64dbg 플래그 창에서 체크된 플래그는 보통 초록/강조색으로 표시되고, 체크 해제된 플래그는 회색으로 표시된다.
- x64dbg 디스어셈블리 창에서 분기 명령어 줄에 실제로 분기할지 여부를 미리 화살표나 하이라이트로 암시해주는 경우가 있다(정지 상태에서 다음 실행될 경로를 표시).
- GDB `info registers`의 `eflags` 줄: `eflags   0x246   [ PF ZF IF ]` — 대괄호 안에 나열된 이름이 현재 1로 세팅된 플래그들이다.

## 가장 먼저 할 것
1. 분기 명령어(`Jcc`) 바로 위에서 가장 가까운 `cmp`/`test`(또는 플래그를 바꾸는 다른 산술 명령)를 찾는다.
2. 그 명령어가 signed 계열 분기(`jg`,`jl`,`jge`,`jle`)를 위한 것인지, unsigned 계열(`ja`,`jb`,`jae`,`jbe`)을 위한 것인지 확인한다(REV-0088).
3. `cmp`/`test` 명령어 주소에 브레이크포인트를 걸고 비교 대상 값을 실제로 확인한다.

## 단계별 절차

**x64dbg**
1. IDA/Ghidra에서 분석하려는 `Jcc` 명령어와 그 직전 `cmp`/`test`를 확인하고 주소를 메모한다.
2. x64dbg에서 그 `cmp`/`test` 명령어 줄을 클릭하고 `F2`로 브레이크포인트를 건다.
3. `F9`로 실행해서 그 지점까지 도달시킨다.
4. 레지스터 창에서 비교 대상 값(예: EAX, 또는 메모리 오퍼랜드가 가리키는 값)을 확인한다.
5. `F7`(또는 `F8`, CALL이 아니므로 동일)로 한 스텝 진행해서 `cmp`/`test`를 실행시킨다.
6. 플래그 창에서 ZF, SF, OF, CF의 현재 값을 확인한다.
7. 다시 한 스텝 진행해서 `Jcc`가 실제로 분기하는지, RIP가 어디로 이동하는지 확인한다.
8. (선택) 결과를 바꿔서 실험하고 싶다면, `Jcc` 실행 전에 플래그 창에서 관련 플래그 체크박스를 클릭해 값을 뒤집어 보고 분기가 달라지는지 확인한다.

**GDB / Pwndbg**
1. `cmp`/`test` 명령어 주소에 브레이크포인트를 건다:
   ```
   break *0x401230
   ```
2. `run`으로 실행한다.
3. 비교 대상 레지스터/메모리 값을 확인한다:
   ```
   p $eax
   p/x $eax
   ```
4. 한 스텝 진행해서 `cmp`/`test`를 실행시킨다:
   ```
   si
   ```
5. 플래그 상태를 확인한다:
   ```
   info registers eflags
   ```
   또는 전체 레지스터에서 `eflags` 줄을 확인한다(`info registers`). Pwndbg를 쓰면 정지할 때마다 `context` 화면 상단에 플래그가 항상 표시된다.
6. 한 스텝 더 진행해서 실제 분기 여부를 확인한다:
   ```
   si
   p $pc
   ```

## 명령어/단축키
- x64dbg: 플래그 창(기본 표시, ZF/CF/SF/OF/PF 체크박스), `F2`(브레이크포인트), `F9`(실행), `F7`/`F8`(스텝), 플래그 체크박스 직접 클릭(값 강제 변경)
- GDB/Pwndbg: `break *<주소>`, `si`(명령어 단위 스텝), `info registers eflags`(또는 `info registers`), `p $eflags`, `set $eflags = ...`(플래그 강제 변경), Pwndbg `context`(플래그 자동 상시 표시)

## 출력 해석
- x64dbg 플래그 창에서 ZF가 체크되어 있으면 직전 `cmp`/`test` 결과가 0(같음)이었다는 뜻이다.
- GDB `info registers eflags` 출력에서 `[ CF PF ZF ]`처럼 나열된 이름이 현재 1인 플래그들이다 — 나열되지 않은 플래그(SF, OF 등)는 0이다.
- 한 스텝 더 진행했을 때 RIP(또는 x64dbg의 현재 실행 화살표)가 `Jcc`의 목적지 주소로 이동했다면 분기가 "일어난(taken)" 것이고, 그냥 다음 줄로 넘어갔다면 분기가 "안 일어난(not taken)" 것이다.

## 흔한 실수
- `Jcc` 바로 위 줄이 `cmp`/`test`가 아닌 경우(예: 중간에 다른 명령이 끼어 있거나, 플래그와 무관한 `mov`가 있는 경우) 무작정 그 직전 줄을 비교 대상으로 착각하는 것 — `mov`는 플래그를 바꾸지 않으므로, 플래그를 실제로 바꾼 가장 가까운 명령을 찾아야 한다.
- signed 분기(`jg`)와 unsigned 분기(`ja`)를 같은 것으로 취급해서, CMP 결과가 같으니 분기 결과도 같을 거라 착각하는 것 — 음수가 낀 비교에서는 결과가 정반대로 나올 수 있다(REV-0088 예시 참고).
- `test eax, eax` 다음의 `jns`/`js`(부호 분기)를 보고 뭘 비교하는지 모르겠다며 당황하는 것 — `test eax, eax`는 사실상 "eax가 0인가, 음수인가"만 확인하는 관용구다.
- 플래그를 실행 전에 미리 보려고 `Jcc` 명령어 자체에 브레이크포인트를 걸어놓고, 그 명령어가 실행되기 **전** 플래그를 보고 있다는 걸 착각하지 않는 것 — 브레이크포인트에서 멈춘 시점은 "그 명령어가 아직 실행되지 않은" 상태이므로, `cmp`/`test`가 이미 실행된 뒤(그 다음 스텝)의 플래그를 봐야 한다.

## 막혔을 때 다음 체크
- 플래그 값과 예상 분기 결과가 안 맞는다면 → CMP/TEST의 오퍼랜드 순서(`cmp a, b`는 `a-b`이지 `b-a`가 아니다)를 다시 확인한다.
- signed/unsigned를 헷갈렸다면 → REV-0088의 진리표와 대조하며 CF/OF/SF/ZF를 하나씩 다시 짚는다.
- CMP/TEST가 안 보이고 다른 산술 명령(`sub`, `dec`, `and`) 직후 바로 Jcc가 온다면 → 그 산술 명령의 결과가 곧 비교 결과라는 뜻이니 그 명령어의 플래그 영향을 확인한다.
- 실험적으로 분기를 반대로 만들고 싶다면 → 플래그 값을 디버거에서 직접 뒤집어서(x64dbg 체크박스, GDB `set $eflags`) 그 자리에서 검증한다.

## 미니 예제

**x64dbg — signed 비교 분기 확인**
```asm
cmp     eax, 0Ah      ; eax와 10 비교
jg      loc_401250     ; eax > 10 (signed) 이면 분기
```
`cmp` 줄에 `F2` → `F9`로 도달 → 레지스터 창에서 EAX 확인(예: `0xFFFFFFFF`, 즉 -1) → `F7`로 `cmp` 실행 → 플래그 창 확인: SF=1, OF=0 (SF≠OF이므로 `jl` 조건이지 `jg` 조건이 아님) → `F7`로 `jg` 실행 → 실제로 분기 안 하고 다음 줄로 넘어가는 것을 확인.

**GDB/Pwndbg — 플래그를 직접 읽어 분기 예측**
```
(gdb) break *0x401230
(gdb) run
(gdb) p/x $eax
$1 = 0xffffffff
(gdb) si
(gdb) info registers eflags
eflags   0x287   [ CF SF IF ]
```
SF가 세팅되어 있고 OF는 없으므로 SF≠OF → `jg`는 분기하지 않고 `jl`은 분기한다. 실제로 `si`를 한 번 더 실행해서 `$pc`(RIP)가 어디로 이동하는지 확인하면 검증된다.

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0172 — 레지스터 값을 실행 중 추적하는 법
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- CMP/TEST가 세팅하는 플래그(ZF, SF, CF, OF)와 각 Jcc의 플래그 조건: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CMP—Compare Two Operands", "TEST—Logical Compare", Volume 1 "EFLAGS Register" 섹션 기준.
- x64dbg 플래그 창(체크박스로 직접 값 변경 가능) 동작: x64dbg 공식 문서(Debugging, Flags) 기준.
- GDB `info registers eflags` 출력 형식과 `$eflags` 조작: GNU GDB 공식 매뉴얼 "Registers" 챕터 기준.
- 2026-09-08 검증.
