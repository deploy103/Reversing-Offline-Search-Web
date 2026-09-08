---
id: REV-0474
title: "명령어 프리픽스(REX, 66h, F2h/F3h)가 붙는 이유 개요"
slug: "rev-0474-instruction-prefixes-rex-66-f2-f3"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - REX prefix
  - REX 프리픽스
  - operand size override
  - 66h 프리픽스
  - F2h F3h 프리픽스
  - REPNE REP 프리픽스
  - legacy prefix
  - 레거시 프리픽스
  - REX.W REX.R REX.X REX.B
  - opcode prefix
aliases:
  - 48이 왜 붙음
  - REX 프리픽스 뭐임
  - 66 F2 F3 차이
  - 명령어 앞에 붙는 바이트
symptom_keywords:
  - 같은 opcode인데 명령어가 다르게 해석됨
  - 명령어 바이트 앞에 40대 숫자가 있음
  - 66 F2 F3로 시작하는 바이트
  - 수동으로 바이트 패치하다가 명령어가 깨짐
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x86/x64 명령어 앞에 붙는 프리픽스 바이트(`66h` 오퍼랜드 크기 재정의, `F2h`/`F3h` REP 계열 또는 SSE 스칼라 선택자, `40h~4Fh` REX)는 **같은 기본 opcode를 재사용하면서도 오퍼랜드 크기·레지스터 범위·명령어 의미 자체를 바꿔주는 스위치** 역할을 하며, 디스어셈블러는 이걸 자동으로 해석해주지만 원리를 알아야 바이트를 직접 다루거나(패치, 쉘코드) 낯선 인코딩을 만났을 때 헷갈리지 않는다.

## 언제 검색해야 하나
- 명령어 바이트를 헥스 에디터나 디버거에서 직접 볼 때 opcode 앞에 `48`, `66`, `F2`, `F3` 같은 바이트가 붙어 있어서 어떤 역할인지 궁금할 때
- 같은 `0F 10` opcode인데 어떤 곳에서는 `MOVUPS`로, 어떤 곳에서는 `MOVSS`/`MOVSD`/`MOVUPD`로 다르게 디스어셈블 되어서 이유가 궁금할 때
- 수동으로 바이트 패치(예: `jmp` 명령을 다른 곳으로 리다이렉트)를 하다가 REX 프리픽스를 빼먹어서 의도와 다른 레지스터가 동작하는 문제를 겪을 때
- x64에서 32비트 레지스터(`eax`)와 64비트 레지스터(`rax`)를 구분 짓는 바이트가 어디 있는지 알고 싶을 때

## 핵심 개념

### 프리픽스란 무엇인가
x86 명령어는 `[프리픽스들] [opcode] [ModRM] [SIB] [변위] [즉시값]` 순서로 구성된다. 프리픽스는 opcode 앞에 붙어서 opcode의 기본 동작을 바꿔주는 1바이트(REX는 예외적으로 정해진 범위 `40h~4Fh`) 값들이다. 크게 두 그룹으로 나뉜다: **레거시 프리픽스**(x86부터 있던 것)와 **REX 프리픽스**(x64에서 새로 생긴 것).

### 레거시 프리픽스
| 프리픽스 | 이름 | 역할 |
|---|---|---|
| `66h` | Operand-Size Override | 기본 오퍼랜드 크기를 32비트↔16비트로 전환. SSE 명령에서는 정수/double precision 계열을 선택하는 용도로도 쓰임 |
| `67h` | Address-Size Override | 주소 계산에 쓰이는 레지스터 폭을 전환(64비트↔32비트) |
| `F0h` | LOCK | 원자적(atomic) 연산 보장(REV-0432 참고) |
| `F2h` | REPNE/REPNZ 또는 SSE 스칼라 double 선택자 | 문자열 명령에서는 "같지 않을 때까지 반복", SSE에서는 `MOVSD`/`ADDSD`처럼 double precision 스칼라 연산 선택 |
| `F3h` | REP/REPE 또는 SSE 스칼라 single 선택자 | 문자열 명령에서는 "반복", SSE에서는 `MOVSS`/`ADDSS`처럼 single precision 스칼라 연산 선택. x64에서는 `PAUSE`(`F3 90`)에도 쓰임 |
| `2Eh, 36h, 3Eh, 26h, 64h, 65h` | 세그먼트 오버라이드 | `CS/SS/DS/ES/FS/GS` 세그먼트를 명시적으로 선택. x64에서는 TEB/TLS 접근에 `FS`(Windows)/`GS`(Linux)가 자주 쓰임 |

가장 헷갈리는 부분은 **`66h`/`F2h`/`F3h`가 SSE 명령어 앞에 붙으면 REP/오퍼랜드 크기 재정의가 아니라 "어떤 데이터 타입을 다루는 SSE 명령인지 고르는 선택자"로 재해석**된다는 점이다. 같은 opcode `0F 10`(MOVUPS 계열)이:
```
0F 10          -> MOVUPS   (프리픽스 없음, packed single)
66 0F 10       -> MOVUPD   (66h 붙음, packed double)
F3 0F 10       -> MOVSS    (F3h 붙음, scalar single)
F2 0F 10       -> MOVSD    (F2h 붙음, scalar double)
```
이렇게 하나의 opcode가 프리픽스 조합에 따라 4개의 서로 다른 명령어로 갈라진다. REV-0386(MOVAPS), REV-0471(AVX/SSE)에서 다루는 SSE 계열 명령어들이 왜 서로 이렇게 닮은 이름을 갖는지도 바로 이 프리픽스 재활용 때문이다.

### REX 프리픽스 (x64 전용)
x64는 기존 8개였던 범용 레지스터를 16개(R8~R15 추가)로 늘리고, 64비트 전체를 쓰는 연산을 지원해야 했다. 이를 위해 `40h~4Fh` 범위의 REX 프리픽스가 도입됐다. REX 바이트는 4개의 비트 필드로 구성된다:
```
0100 WRXB   (0x4 상위 니블 고정, 하위 4비트가 W R X B)
```
- **W (Width)**: 1이면 오퍼랜드 크기를 64비트로 확장 (`mov eax,...` → `mov rax,...`). `REX.W` 없이 x64에서 32비트 연산을 하면 상위 32비트는 자동으로 0으로 채워진다(zero-extension)는 점도 함께 기억해두면 좋다.
- **R (ModRM.reg 확장)**: ModRM 바이트의 `reg` 필드에 1비트를 더해 R8~R15까지 표현 가능하게 함
- **X (SIB.index 확장)**: SIB 바이트의 index 필드 확장
- **B (ModRM.rm 또는 SIB.base 또는 opcode 내장 레지스터 확장)**: rm/base 필드나 opcode에 포함된 레지스터 번호 확장

예를 들어 `48 89 D8`은 `REX.W=1`(48h = 0100 1000, W비트=1) + `89`(MOV r/m64, r64) + ModRM(`D8` = rax ← rbx)으로, `mov rax, rbx`를 인코딩한다. REX 프리픽스가 없는 `89 D8`은 32비트 버전인 `mov eax, ebx`가 된다. **REX 유무 자체가 오퍼랜드 크기(32비트냐 64비트냐)를 결정짓는 핵심 신호**라는 걸 기억하면 헥스 덤프를 직접 읽을 때 큰 도움이 된다.

또한 REX 프리픽스가 있으면 1바이트 레지스터 인코딩도 달라진다 — REX 없이 `AH/CH/DH/BH`로 해석되던 자리가, REX가 있으면 `SPL/BPL/SIL/DIL`(각각 RSP/RBP/RSI/RDI의 하위 1바이트)로 바뀐다.

### 여러 프리픽스가 겹칠 때
하나의 명령어에 레거시 프리픽스와 REX가 동시에 붙을 수 있다. 이때 **REX는 항상 다른 레거시 프리픽스들보다 opcode에 가장 가까운 위치(맨 뒤)에 와야 한다**는 순서 규칙이 있다 — 순서가 틀리면 CPU가 다르게 해석하거나 `#UD`(잘못된 opcode) 예외가 날 수 있다.
```
66 48 0F 6E C0    ; 66h(피연산자 재정의, SSE 정수 선택) + REX.W + 0F 6E(MOVD/MOVQ) -> movq xmm0, rax
```

## 화면/코드에서 보이는 징후
```asm
89 D8              ; mov eax, ebx          (REX 없음 -> 32비트)
48 89 D8           ; mov rax, rbx          (REX.W=1 -> 64비트)
4C 89 D8           ; mov rax, r11          (REX.W=1, REX.R=1 -> r11 확장 레지스터 인코딩)
F3 0F 6F C1        ; movdqu xmm0, xmm1     (F3h -> 정수 unaligned SSE)
66 0F 6F C1        ; movdqa xmm0, xmm1     (66h -> 정수 aligned SSE)
F2 0F 10 C1        ; movsd  xmm0, xmm1     (F2h -> scalar double)
```

## 가장 먼저 할 것
1. 헥스 바이트를 직접 읽을 때는 opcode 바로 앞의 바이트가 `40h~4Fh` 범위인지 먼저 확인해서 REX 프리픽스 여부(64비트 연산 여부)를 판단한다.
2. `0F`로 시작하는 2바이트 opcode(SSE 계열이 많다) 앞에 `66h`/`F2h`/`F3h`가 있으면, 그건 REP나 크기 재정의가 아니라 "SSE 명령어 종류 선택자"일 가능성이 높다고 의심한다.
3. 직접 패치할 때는 원본 명령어와 **정확히 같은 프리픽스 조합**을 유지해야 오퍼랜드 크기/레지스터 해석이 어긋나지 않는다.

## 단계별 절차
**1) REX 여부 판단**
opcode 직전 바이트가 `0x40~0x4F`면 REX. 그 값을 이진수로 펼쳐서(`0100WRXB`) W/R/X/B 비트를 각각 확인한다.

**2) 레거시 프리픽스 존재 여부 판단**
opcode(또는 REX) 앞에 `66`, `67`, `F0`, `F2`, `F3`, 세그먼트 오버라이드 바이트가 있는지 확인한다. 여러 개가 겹쳐 있을 수도 있다(순서 주의).

**3) opcode 자체와 프리픽스 조합으로 최종 명령어 판단**
같은 opcode라도 프리픽스 조합에 따라 완전히 다른 명령어가 된다는 걸 염두에 두고 Intel SDM의 opcode map(또는 디스어셈블러 결과)과 대조한다.

**4) 수동 패치 시 바이트 수 변화 주의**
REX를 추가/제거하면 명령어 전체 길이가 1바이트 늘거나 준다. 상대 주소(rel8/rel32)를 쓰는 분기 명령을 패치할 때는 이 길이 변화가 이후 오프셋 계산에 영향을 줄 수 있으므로 반드시 다시 어셈블해서 확인한다.

## 명령어/단축키
- IDA: Hex View(`Alt+2`)에서 명령어 바이트 직접 확인, 명령어 위에서 우클릭 → "Text view" 옆에 바이트 길이 표시
- objdump: `objdump -d ./binary`는 기본적으로 프리픽스 해석까지 포함된 최종 니모닉만 보여주지만, `-M raw` 유사 옵션이나 hex dump(`objdump -s`)로 원본 바이트도 병행 확인 가능
- 온라인/오프라인 x86 opcode 참조표(Intel SDM Volume 2 Appendix A, Opcode Map)를 오프라인 문서로 함께 갖춰두면 프리픽스 조합을 빠르게 찾을 수 있다.

## 출력 해석
- 디스어셈블러가 보여주는 최종 니모닉(`mov rax, rbx`)은 이미 프리픽스 해석이 끝난 결과다. 굳이 프리픽스를 직접 셀 필요는 평소엔 없지만, 헥스 패치나 쉘코드 작성/디버깅, 명령어 길이 계산이 필요할 때는 원본 바이트를 봐야 한다.
- 같은 논리 연산(`mov`)이라도 REX.W 유무에 따라 바이트 수가 다르므로, "이 함수는 X바이트다"라고 셀 때 프리픽스 유무를 놓치면 오프셋 계산이 틀어질 수 있다.

## 흔한 실수
- REX 프리픽스를 무시하고 opcode만 보고 오퍼랜드 크기를 32비트로 단정하는 것 — `48` 같은 REX.W가 붙으면 64비트 연산이다.
- SSE 명령어 앞의 `F2`/`F3`을 문자열 REP 프리픽스로 착각해서 "이게 반복 명령이구나"라고 오해하는 것 — opcode가 `0F`로 시작하는 SSE 계열이면 REP가 아니라 스칼라 타입 선택자다.
- 바이트 패치 시 REX 프리픽스 바이트 하나를 빠뜨려서(또는 반대로 불필요하게 추가해서) 의도한 레지스터가 아닌 다른 레지스터가 동작하게 만드는 것.
- 프리픽스 순서(레거시 프리픽스들이 REX보다 항상 앞에 와야 함)를 무시하고 아무렇게나 바이트를 조합해 무효한 인코딩을 만드는 것.

## 막혔을 때 다음 체크
- SSE/AVX 명령어의 프리픽스별 의미가 계속 헷갈린다면 → REV-0386(MOVAPS), REV-0471(AVX vs SSE)을 함께 참고해서 표를 옆에 두고 대조한다.
- REP 프리픽스 자체의 동작(문자열 명령과 함께 쓰일 때)이 궁금하다면 → REV-0080(REP Prefix)을 참고한다.
- 마이크로옵/디코딩 단계까지 더 깊이 알고 싶다면 → REV-0475(마이크로옵 개념)로 이동한다.

## 미니 예제
**예제 1 — REX.W로 32비트와 64비트 MOV 구분**
```asm
89 D8        ; mov eax, ebx     (REX 없음, 32비트, 상위 32비트는 자동 0)
48 89 D8     ; mov rax, rbx     (REX.W=1, 64비트 전체)
```

**예제 2 — 같은 opcode, 다른 프리픽스로 갈라지는 SSE 명령**
```asm
0F 10 C1        ; movups xmm0, xmm1
66 0F 10 C1     ; movupd xmm0, xmm1
F3 0F 10 C1     ; movss  xmm0, xmm1
F2 0F 10 C1     ; movsd  xmm0, xmm1
```

**예제 3 — REX.R로 확장 레지스터(R8~R15) 인코딩**
```asm
89 D8        ; mov eax, ebx
44 89 D8     ; mov eax, r11d    (REX.R=1 -> ModRM.reg가 r11d를 가리킴)
```

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0471 — AVX 명령이 보일 때 SSE와 다른 점 개요
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0475 — 명령어 하나가 여러 마이크로옵으로 나뉜다는 개념(참고용)
- REV-0039 — MOV: 값 복사와 레지스터 메모리 이동

## 출처/검증
- 레거시 프리픽스와 REX 프리픽스 인코딩(바이트 범위, W/R/X/B 비트 필드): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, Chapter 2 "Instruction Format" 기준.
- SSE 명령어의 66h/F2h/F3h 선택자 재해석(MOVUPS/MOVUPD/MOVSS/MOVSD 등): 같은 매뉴얼 Volume 2, "Instruction Set Reference" 각 명령어 섹션 기준.
- 위 헥스 바이트 예제는 x86-64 명령어 인코딩 규칙에 따라 직접 재구성한 예시다(2026-09-08 검증).
