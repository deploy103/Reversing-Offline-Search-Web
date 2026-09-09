---
id: REV-1103
title: "ARM에서 조건부 실행(비트) 읽는 법"
slug: "rev-1103-arm-conditional-execution"
category: "other-targets"
difficulty: "basic"
platform: [linux, android]
architecture: [ARM, ARM64]
format: [ELF]
tools: [Ghidra, IDA, GDB]
keywords: ["ARM 조건부 실행", "NZCV", "조건 코드", "condition code", "IT block", "ITTE", "ARM EQ NE GE LT"]
aliases: ["ARM 조건 접미사", "ARM에서 if문 찾기", "ADDEQ 뜻", "IT 블록이란"]
symptom_keywords: ["명령어 뒤에 EQ NE 같은 게 붙어있음", "분기(branch) 없이 조건이 걸린 것 같음", "IT 명령어가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
ARM은 x86처럼 `CMP` 다음에 `Jcc`로 분기하는 것 말고도, 거의 모든 명령어 뒤에 `EQ`/`NE`/`GE`/`LT` 같은 두 글자 조건 접미사를 붙여 그 명령어 자체를 조건부로 실행할 수 있는데, 이 조건은 상태 레지스터의 NZCV(Negative/Zero/Carry/oVerflow) 플래그를 검사해 판단되며 Thumb 코드에서는 `IT`(If-Then) 명령이 뒤따르는 최대 4개 명령어의 조건 실행 여부를 미리 지정한다.

## 언제 검색해야 하나
- 디스어셈블리에서 `ADDEQ`, `MOVNE`, `SUBGE`처럼 명령어 뒤에 알파벳 두 글자가 붙어 있는데 이게 뭔지 모를 때
- `CMP` 다음에 분기(branch) 명령이 안 보이는데도 마치 if문처럼 동작하는 코드를 볼 때
- Thumb 코드에서 `IT`, `ITE`, `ITTE` 같은 명령어를 처음 볼 때
- ARM64(AArch64) 코드에서 `CCMP`, `CSEL` 같이 분기 없이 조건을 처리하는 명령을 볼 때

## 핵심 개념

### NZCV 플래그
ARM의 APSR(Application Program Status Register)에는 4개의 조건 플래그가 있다.
- **N**(Negative): 결과가 음수(최상위 비트가 1)면 설정
- **Z**(Zero): 결과가 0이면 설정
- **C**(Carry): 부호 없는 덧셈에서 자리올림, 뺄셈에서는 "빌림이 없었음"을 의미(주의: x86의 CF와 반대 의미로 설정되는 경우가 있어 뺄셈 결과 해석 시 특히 주의)
- **V**(oVerflow): 부호 있는 연산에서 오버플로우 발생 시 설정

x86의 `ZF`, `SF`, `CF`, `OF`(REV-0088)와 대응 개념이지만, ARM은 이 플래그를 데이터 처리 명령어에서 훨씬 적극적으로, 그리고 선택적으로 갱신한다.

### 플래그는 "S" 접미사가 있어야 갱신된다
x86은 `ADD`, `SUB` 등 대부분의 산술 명령이 항상 플래그를 갱신하지만, ARM의 일반 데이터 처리 명령은 기본적으로 플래그를 바꾸지 않는다. 플래그를 갱신하려면 명령어에 `S` 접미사를 명시적으로 붙여야 한다(예: `ADDS`, `SUBS`, `MOVS`). 반면 `CMP`, `TST`, `TEQ`, `CMN` 같은 비교 전용 명령은 플래그 갱신이 유일한 목적이므로 `S` 없이도 항상 플래그를 갱신한다.

### 조건 접미사로 명령어 자체를 조건부로 만들기
ARM의 가장 독특한 특징은, `Bcc`(조건 분기)뿐 아니라 거의 모든 명령어에 조건 코드를 접미사로 붙여 "이 조건이 참일 때만 이 명령어를 실행"하도록 만들 수 있다는 점이다. 예를 들어 `ADDEQ R0, R1, R2`는 "직전에 설정된 플래그가 EQ(Z=1) 조건을 만족할 때만 R0 = R1 + R2를 실행"한다는 뜻이며, 조건이 거짓이면 그 명령어는 아무 일도 하지 않는 NOP처럼 처리된다.

주요 조건 코드:
| 접미사 | 의미 | 플래그 조건 |
|---|---|---|
| `EQ` | 같음(Equal) | Z=1 |
| `NE` | 다름(Not Equal) | Z=0 |
| `GE` | 이상(signed Greater/Equal) | N=V |
| `LT` | 미만(signed Less Than) | N≠V |
| `GT` | 초과(signed Greater Than) | Z=0 and N=V |
| `LE` | 이하(signed Less/Equal) | Z=1 or N≠V |
| `CS`/`HS` | 부호 없는 이상(Carry Set) | C=1 |
| `CC`/`LO` | 부호 없는 미만(Carry Clear) | C=0 |
| `MI` | 음수(Minus) | N=1 |
| `PL` | 양수 또는 0(Plus) | N=0 |
| `VS`/`VC` | 오버플로우 발생/없음 | V=1 / V=0 |

이 조건부 실행 덕분에 짧은 if문(예: `if (a == b) x = 1;`)을 분기 명령 없이 몇 개의 조건부 명령어만으로 구현할 수 있어, 분기 예측 실패로 인한 파이프라인 손실을 피하고 코드도 짧아진다.

### Thumb의 IT 블록
32비트 ARM 모드는 거의 모든 명령어에 조건 접미사를 자유롭게 붙일 수 있지만, 기본 Thumb(16비트) 명령어는 인코딩 공간이 부족해 조건 접미사를 붙일 자리가 없다. 이를 보완하기 위해 Thumb-2에서 `IT`(If-Then) 명령이 도입되었다. `IT` 뒤에 최대 3개의 `T`(Then)/`E`(Else) 문자를 추가로 붙여(`ITTE`, `ITE` 등) 그 뒤에 오는 최대 4개 명령어 각각이 조건을 그대로 따를지(T) 반대로 따를지(E)를 지정한다.

```asm
ITTE NE          ; 다음 3개 명령: NE, NE, EQ(반대) 조건
ANDNE R0, R0, R1  ; NE 조건이면 실행, 플래그 안 바꿈
ADDSNE R2, R2, #1 ; NE 조건이면 실행, S이므로 플래그 갱신
MOVEQ R3, #0      ; 반대 조건(EQ)일 때만 실행
```

### ARM64(AArch64)의 변화 — CSEL/CCMP
ARM64는 `IT` 블록이 폐지되고, 대신 조건부 선택/비교 명령(`CSEL`, `CSET`, `CCMP`, `CCMN` 등)으로 분기 없는 조건 처리를 한다. 예를 들어 `CSEL X0, X1, X2, EQ`는 "EQ 조건이면 X0=X1, 아니면 X0=X2"를 분기 없이 한 줄로 처리한다. `CCMP`는 두 개의 비교를 연쇄해 `a > 0 && b > 0` 같은 복합 조건을 분기 없이 표현할 때 쓰인다.

## 화면/코드에서 보이는 징후
- `MOVEQ`, `ADDNE`, `SUBGE`처럼 명령어 뒤에 두 글자 조건 접미사가 붙어 있음
- `CMP` 직후 분기 명령 없이 조건부 명령어 몇 개가 이어짐
- Thumb 디스어셈블리에 `IT`, `ITE`, `ITTE` 등이 보이고 바로 뒤 명령어들의 우측에 조건이 표시됨
- ARM64 디스어셈블리에 `CSEL`, `CSET`, `CCMP`가 보임

## 가장 먼저 할 것
명령어 뒤에 붙은 두 글자를 위 표와 대조해 어떤 조건인지 먼저 확인하고, 바로 앞에서 어떤 명령(`CMP`, `SUBS` 등)이 플래그를 갱신했는지 찾아 그 비교의 의미(무엇과 무엇을 비교했는지)를 파악한다.

## 단계별 절차
1. 조건부 명령어를 발견하면 직전에 플래그를 갱신한 명령(`CMP`, `TST`, `S` 접미사가 붙은 명령)을 역방향으로 탐색
2. 그 명령의 피연산자로 실제 "무엇과 무엇을 비교"하는지 확인
3. 조건 접미사를 표에서 찾아 C/C++ 관계 연산자로 치환(예: `GT` → `>`, `LE` → `<=`)
4. Thumb이면 `IT` 블록의 `T`/`E` 패턴을 보고 각 명령어가 조건을 그대로 따르는지 반전해서 따르는지 구분
5. ARM64면 `CSEL`/`CCMP` 계열을 삼항 연산자(`? :`) 또는 `&&`/`||` 체인으로 재구성

## 명령어/단축키
```bash
# GDB에서 현재 플래그 확인 (ARM32)
(gdb) p $cpsr
(gdb) info registers cpsr

# Ghidra/IDA 디컴파일 결과에서 조건부 명령이 자동으로 if문으로 재구성되는 경우가 많으므로
# 디스어셈블리 옆의 디컴파일(Decompile) 창을 같이 열어 비교하며 읽는 것이 실전에서 가장 빠르다.
```

## 출력 해석
```asm
CMP  R0, #10
MOVGT R1, #1     ; R0 > 10 (signed) 이면 R1 = 1
MOVLE R1, #0     ; 아니면(R0 <= 10) R1 = 0
```
이 세 줄은 분기(branch) 명령이 전혀 없지만 `if (R0 > 10) R1 = 1; else R1 = 0;`과 완전히 동일한 의미다. x86이라면 `CMP`, `JLE`, `MOV`, `JMP`, `MOV` 식으로 최소 두 개의 분기가 필요했을 로직이 ARM에서는 분기 없이 3줄로 끝난다.

## 흔한 실수
- 조건 접미사를 무시하고 모든 명령어가 항상 실행된다고 가정해 디컴파일 로직을 잘못 재구성하는 것.
- `GT`/`GE`(부호 있는 비교)와 `HI`/`HS`(부호 없는 비교)를 혼동하는 것 — signed/unsigned 비교 조건이 서로 다른 플래그 조합을 쓴다.
- Thumb의 `IT` 블록에서 `E`(Else)가 붙은 명령어의 조건이 반전된다는 것을 잊고 전부 같은 조건으로 읽는 것.
- ARM의 뺄셈 관련 Carry 플래그 의미가 x86의 빌림(borrow) 플래그와 반대 극성으로 동작하는 경우가 있다는 것을 모르고 `CC`/`CS` 조건을 잘못 해석하는 것.

## 막혔을 때 다음 체크
- x86 쪽 플래그/Jcc 대응 관계부터 다시 보고 싶다면 → REV-0088 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기, REV-0060 CMP
- Thumb 모드 자체가 왜 존재하고 어떻게 ARM과 섞이는지 헷갈리면 → REV-1102 ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- 레지스터/호출 규약 기초가 필요하면 → REV-1101 ARM/ARM64 레지스터와 호출 규약 기초

## 미니 예제
```asm
; ARM64: if (a == b) return x; else return y; 형태
CMP  X0, X1
CSEL X0, X2, X3, EQ   ; X0 == X1이면 X0=X2(x), 아니면 X0=X3(y)
RET
```
분기 명령 없이 `CSEL` 한 줄로 삼항 연산자 전체가 표현된 예다. Ghidra/IDA의 디컴파일 창은 이런 패턴을 대부분 자동으로 `x0 = (x0 == x1) ? x2 : x3;` 형태의 C 코드로 복원해 보여주므로, 어셈블리 조건 코드 표는 디스어셈블리를 직접 읽어야 할 때(디컴파일 결과가 이상하거나 없을 때)를 위한 것이다.

## 관련 글
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-1101 — ARM/ARM64 레지스터와 호출 규약 기초
- REV-1102 — ARM Thumb 모드가 무엇이고 왜 헷갈리는지

## 출처/검증
- ARM의 조건 접미사 메커니즘(거의 모든 명령어에 두 글자 조건을 붙여 조건부 실행), NZCV 플래그와 EQ/NE/GE/LT 등 조건 코드의 의미: Azeria Labs - Conditional Execution and Branching (Part 6) (https://azeria-labs.com/arm-conditional-execution-and-branching-part-6/), DaveSpace - Introduction to ARM: Conditional Execution (https://www.davespace.co.uk/arm/introduction-to-arm/conditional.html), ARM 공식 문서 Cortex-R Conditional execution (https://support.arm.com/documentation/den0042/0100/Unified-Assembly-Language-Instructions/Instruction-set-basics/Conditional-execution) 기준 확인(2026-09-10).
- 데이터 처리 명령이 `S` 접미사가 있을 때만 플래그를 갱신하고 `CMP`/`TST` 등은 항상 플래그를 갱신한다는 규칙, Thumb `IT` 블록 문법(`IT{x{y{z}}}`, `ITTE` 예시)과 최대 4개 명령어 제한: 위 Azeria Labs 자료 및 ARM 아키텍처 참조 매뉴얼 기반 자료 교차 확인.
- ARM64의 `CCMP`를 이용한 조건 체이닝 예시(NZCV=0 강제 설정으로 GE 결과를 흉내내는 방식): The Old New Thing - The AArch64 processor, part 16: Conditional execution (https://devblogs.microsoft.com/oldnewthing/20220817-00/?p=106998) 기준.
