---
id: REV-0429
title: "CBW CWD CDQ CQO: 부호 확장 전용 명령"
slug: "rev-0429-cbw-cwd-cdq-cqo"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - CBW
  - CWD
  - CDQ
  - CQO
  - sign extension
  - 부호 확장
  - cdq 명령어
  - cwd 명령어
  - cqo 명령어
  - EDX EAX
  - RDX RAX
  - idiv 앞에 cdq
  - signed division sign extend
aliases:
  - cdq가 뭔가요
  - cwd가 뭔가요
  - cqo가 뭔가요
  - cdq 명령
  - idiv 앞에 나오는 cdq
  - cdq cwd 차이
symptom_keywords:
  - idiv 앞에 cdq가 왜 있는지 모르겠음
  - cdq가 뭘 하는지 모르겠음
  - edx eax가 같이 쓰이는 이유
  - div 앞에는 왜 xor edx edx만 있는지
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CBW`/`CWD`/`CDQ`/`CQO`는 오퍼랜드 없이 **정해진 누산기 레지스터(AL/AX/EAX/RAX)의 값을 부호 확장해서 더 넓은 레지스터 쌍(AX, DX:AX, EDX:EAX, RDX:RAX)에 채워 넣는** 전용 명령으로, 대부분 `IDIV`(부호 있는 나눗셈) 직전에 피제수를 준비하기 위해 나타난다.

## 언제 검색해야 하나
- `idiv` 바로 앞에 항상 붙어 있는 `cdq`(또는 `cwd`, `cqo`)가 무슨 일을 하는지 모를 때
- `cdq` 대신 `xor edx, edx`가 나오는 코드와 차이가 뭔지 궁금할 때 — 원본 변수가 `int`였는지 `unsigned int`였는지 구분하는 단서를 찾고 있을 때
- `movsx`/`movzx`와 `cdq` 계열이 어떻게 다른지 헷갈릴 때

## 핵심 개념

### 네 명령의 공통점: 오퍼랜드가 없다
이 네 명령은 모두 **피연산자를 전혀 받지 않는다.** 소스와 목적지가 모두 고정된 누산기 레지스터로 CPU 안에 내장되어 있다. 어셈블리 코드에도 `cdq` 한 단어만 덩그러니 나온다.

### 각각이 하는 일
| 명령 | 소스 | 목적지 | 폭 |
|---|---|---|---|
| `CBW` (Convert Byte to Word) | `AL` | `AX` | 8비트 → 16비트 |
| `CWD` (Convert Word to Doubleword) | `AX` | `DX:AX` | 16비트 → 32비트(두 레지스터에 분리) |
| `CDQ` (Convert Doubleword to Quadword) | `EAX` | `EDX:EAX` | 32비트 → 64비트(두 레지스터에 분리) |
| `CQO` (Convert Quadword to Octaword) | `RAX` | `RDX:RAX` | 64비트 → 128비트(두 레지스터에 분리), x64 전용 |

`CBW`만 결과가 레지스터 하나(`AX`)에 온전히 들어가고, 나머지 셋(`CWD`/`CDQ`/`CQO`)은 결과가 원래 폭의 두 배이므로 레지스터 두 개(`DX:AX`, `EDX:EAX`, `RDX:RAX`)로 나눠 담긴다. 이때 상위 레지스터(`DX`/`EDX`/`RDX`)에는 하위 레지스터 값의 **부호 비트를 그대로 전체 비트에 복사한 값**, 즉 `0x00000000`(양수/0일 때) 또는 `0xFFFFFFFF`(음수일 때)가 들어간다.

### 왜 IDIV 앞에 오는가
`IDIV`(부호 있는 나눗셈, [REV-0053](./rev-0053-idiv.md))는 32비트 나눗셈이라면 `EDX:EAX`(64비트짜리 피제수)를 나누는 명령으로 정의되어 있다. `int a, b; int q = a / b;`처럼 32비트끼리 나누고 싶어도, CPU 명령 자체는 항상 그 두 배 폭의 피제수를 요구한다. 이때 `EAX`에 들어있는 32비트 값을 부호를 유지한 채 64비트로 확장해서 `EDX:EAX`를 채워주는 것이 `CDQ`의 역할이다. `EDX`를 그냥 `0`으로 채우면 음수일 때 완전히 틀린 값이 되므로, 반드시 부호에 맞게(음수면 `0xFFFFFFFF`) 채워야 한다.

### 왜 CDQ 대신 XOR EDX, EDX가 나오기도 하는가
`DIV`(부호 없는 나눗셈, [REV-0052](./rev-0052-div.md))는 애초에 음수 개념이 없으므로 상위 레지스터를 그냥 `0`으로 클리어하기만 하면 된다. 그래서 컴파일러는 unsigned 나눗셈 앞에는 `xor edx, edx`(EDX=0)를 넣고, signed 나눗셈 앞에는 `cdq`(부호 확장)를 넣는다. **이 차이가 바로 스트립된 바이너리에서 원본 변수가 `int`였는지 `unsigned int`였는지 역추론하는 핵심 단서다.**

### 플래그 변화
`CBW`/`CWD`/`CDQ`/`CQO`는 **어떤 플래그도 바꾸지 않는다.** 순수하게 레지스터 값만 채우는 명령이다.

### 스택/RSP/RIP 변화
스택에는 영향이 없다. `RIP`는 명령 길이(1바이트, prefix 포함해도 짧음)만큼만 이동한다.

### MOVSX/MOVSXD와의 차이
[REV-0041 — MOVSX/MOVSXD](./rev-0041-movsx-movsxd.md)는 **임의의** 레지스터/메모리 값을 **임의의** 더 넓은 레지스터로 명시적인 오퍼랜드를 지정해 부호 확장하는 범용 명령이다. 반면 `CBW`/`CWD`/`CDQ`/`CQO`는 오퍼랜드가 없고 오직 누산기(AL/AX/EAX/RAX → AX/DX:AX/EDX:EAX/RDX:RAX)만을 대상으로 하는 특수 목적 명령이다. 용도가 겹치는 것처럼 보이지만 실제로는 거의 항상 `CDQ`/`CQO`는 나눗셈 직전에만, `MOVSX`는 그 외 일반적인 타입 확장 대입에 쓰인다.

## 화면/코드에서 보이는 징후
- `cdq` 바로 다음 줄에 `idiv ecx`(또는 다른 32비트 레지스터/메모리) — signed 32비트 나눗셈
- `cqo` 바로 다음 줄에 `idiv rcx` — signed 64비트 나눗셈
- `xor edx, edx` 다음 `div ecx` — unsigned 나눗셈(비교 대상으로 함께 기억해두면 좋음)
- `cwd` 다음 `idiv cx` — 흔치 않지만 16비트 signed 나눗셈에서 등장
- `cbw`는 최신 x64 코드에서는 매우 드묾(8비트 signed 나눗셈 자체가 드물기 때문)

## 가장 먼저 할 것
1. `cdq`/`cqo`/`cwd`/`cbw` 바로 다음 명령이 `idiv`인지 확인한다 — 거의 항상 그렇다.
2. `idiv`의 오퍼랜드(나누는 값)를 확인해서 `EAX / operand` 형태의 signed 나눗셈으로 해석한다.
3. 이 명령이 없이 `xor edx, edx`만 있다면 원본이 unsigned 타입이었다고 추론한다.

## 단계별 절차
**1) 32비트 signed 나눗셈 패턴 인식**
```asm
mov  eax, [rbp-4]   ; 피제수(예: a)
cdq                  ; EDX:EAX = sign_extend(EAX)
idiv dword ptr [rbp-8]   ; EAX = EDX:EAX / [rbp-8], EDX = 나머지
```
→ `int a, b; int q = a / b; int r = a % b;`로 해석한다(몫은 EAX, 나머지는 EDX).

**2) 64비트 signed 나눗셈 패턴 인식**
```asm
mov  rax, [rbp-8]
cqo                  ; RDX:RAX = sign_extend(RAX)
idiv rcx
```

**3) unsigned 버전과 비교해서 부호 여부 역추론**
```asm
xor  edx, edx        ; EDX = 0 (unsigned니까 부호 확장 불필요)
div  ecx
```
같은 위치에 `cdq`가 아니라 `xor edx, edx`가 있다면 원본 변수가 `unsigned int`였다는 뜻이다.

## 명령어/단축키
- IDA: F5로 디컴파일하면 대개 `cdq`+`idiv` 조합이 그냥 `a / b`(signed) 표현식으로 깔끔하게 사라져서 보인다.
- x64dbg/GDB: `cdq`/`cqo` 실행 전후로 EDX/RDX 레지스터 값이 `0x00000000`에서 `0xFFFFFFFF`(또는 그 반대)로 바뀌는지 F7/stepi로 직접 관찰하면 이해가 빠르다.

## 출력 해석
- `CDQ` 실행 후 `EDX == 0`이면 EAX가 양수(또는 0)였다는 뜻이고, `EDX == 0xFFFFFFFF`면 EAX가 음수였다는 뜻이다.
- `IDIV` 실행 후 몫은 항상 EAX(또는 32비트 나눗셈 기준), 나머지는 항상 EDX에 남는다.

## 흔한 실수
- `CDQ`가 무언가를 "계산"하는 산술 명령이라고 착각하는 것 — 사실은 순수하게 EAX의 부호 비트를 EDX 전체로 복사만 하는 명령이다.
- `CWD`(16비트)와 `CDQ`(32비트)를 헷갈려서 잘못된 레지스터 폭으로 해석하는 것.
- `CDQ`가 항상 나온다고 가정해서, `EDX`를 그냥 `0`으로 만든 `xor edx, edx` 뒤에 오는 `div`(unsigned)까지 signed로 잘못 해석하는 것.
- `IDIV`의 나머지가 `EAX`에 남는다고 착각하는 것 — 나머지는 `EDX`, 몫은 `EAX`다.

## 막혔을 때 다음 체크
- `cdq`/`cqo`가 왜 나왔는지 확신이 안 서면 → 바로 다음 명령이 `idiv`/`div`인지부터 확인한다. 거의 예외가 없다.
- signed인지 unsigned인지 헷갈리면 → `cdq`(또는 `cqo`, `cwd`) vs `xor edx, edx`(또는 `xor rdx, rdx`) 중 어느 쪽이 나오는지로 판단한다.
- 나눗셈 자체의 자세한 동작이 궁금하면 → [REV-0052 DIV](./rev-0052-div.md), [REV-0053 IDIV](./rev-0053-idiv.md)로 이동한다.

## 미니 예제
**예제 1 — signed 32비트 나눗셈**
```c
int div_signed(int a, int b) { return a / b; }
```
```asm
mov  eax, edi     ; a (System V 첫 인자)
cdq                ; EDX:EAX = sign_extend(EAX)
idiv esi           ; b로 나눔
; 결과: EAX = 몫
```

**예제 2 — unsigned 32비트 나눗셈과의 대조**
```c
unsigned int div_unsigned(unsigned int a, unsigned int b) { return a / b; }
```
```asm
mov  eax, edi
xor  edx, edx      ; CDQ 대신 EDX를 단순히 0으로
div  esi
```

**예제 3 — 64비트 signed 나눗셈(CQO)**
```c
long long div64(long long a, long long b) { return a / b; }
```
```asm
mov  rax, rdi
cqo                 ; RDX:RAX = sign_extend(RAX)
idiv rsi
```

**예제 4 — CBW로 8비트를 16비트로 확장**
```asm
mov  al, [byte_val]   ; AL = 부호 있는 8비트 값
cbw                     ; AX = sign_extend(AL)
```

## 관련 글
- REV-0053 — IDIV: Signed 나눗셈
- REV-0052 — DIV: Unsigned 나눗셈
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해
- REV-0040 — MOVZX: Zero Extension 이해
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- `CBW`/`CWD`/`CDQ`/`CQO`의 정의와 대상 레지스터: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CBW/CWDE/CDQE—Convert Byte to Word/Convert Word to Doubleword/Convert Doubleword to Quadword" 및 "CWD/CDQ/CQO—Convert Word to Doubleword/Convert Doubleword to Quadword" 섹션 기준 (2026-09-08 검증).
- `IDIV` 직전 부호 확장 관용구, `DIV` 직전 `xor edx,edx` 관용구: GCC/Clang/MSVC 컴파일러 출력에서 공통적으로 관찰되는 표준 코드 생성 패턴 기준.
