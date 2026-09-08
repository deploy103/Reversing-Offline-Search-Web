---
id: REV-0527
title: "x64 Calling Convention 레지스터 사용 빠른 참조표"
slug: "rev-0527-x64-calling-convention-register-quickref"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["x64 calling convention", "RCX RDX R8 R9", "volatile nonvolatile register", "shadow space", "Windows x64 ABI"]
aliases: ["x64 레지스터 사용 규칙표", "윈도우 x64 호출 규약 표", "RCX RDX R8 R9 인자 순서", "volatile register 표"]
symptom_keywords: ["RCX RDX R8 R9 중 어디까지가 인자인지 헷갈림", "이 레지스터가 volatile인지 nonvolatile인지 모르겠음", "함수 호출 후 어떤 레지스터가 보존되는지 모르겠음", "다섯 번째 인자는 어디서 찾는지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows x64 호출 규약은 처음 네 개의 정수/포인터 인자를 `RCX, RDX, R8, R9` 순서로 넘기고, 다섯 번째부터는 스택에 쌓으며, 어떤 레지스터가 함수 호출 후에도 값이 보존되는지(nonvolatile)와 그렇지 않은지(volatile)를 표로 외워두면 디스어셈블리를 읽을 때 "이 레지스터 값이 왜 갑자기 바뀌었지"를 훨씬 빠르게 판단할 수 있다.

## 언제 검색해야 하나
- IDA/x64dbg에서 `call` 직전에 `RCX`, `RDX`, `R8`, `R9`에 값을 채우는 코드를 보고 이게 몇 번째 인자인지 바로 확인하고 싶을 때
- 함수 호출 이후 어떤 레지스터 값을 믿고 계속 써도 되는지(nonvolatile), 다시 읽어야 하는지(volatile) 헷갈릴 때
- 다섯 번째 이상 인자가 어디 있는지 찾다가 스택 어디를 봐야 하는지 모를 때
- 부동소수점 인자(`float`/`double`)가 `RCX`가 아니라 `XMM0`에 들어있는 이유를 확인하고 싶을 때

## 핵심 개념

### 정수/포인터 인자 레지스터 순서
Windows x64 호출 규약(REV-0122에서 상세히 다룸)은 왼쪽부터 순서대로 처음 4개의 정수형/포인터 인자를 다음 레지스터에 담는다.

| 인자 순번 | 레지스터(64비트) | 32비트 별칭 | 16비트 별칭 | 8비트 별칭 |
|---|---|---|---|---|
| 1번째 | `RCX` | `ECX` | `CX` | `CL` |
| 2번째 | `RDX` | `EDX` | `DX` | `DL` |
| 3번째 | `R8` | `R8D` | `R8W` | `R8B` |
| 4번째 | `R9` | `R9D` | `R9W` | `R9B` |
| 5번째 이상 | 스택(REV-0124 Shadow Space 다음 위치) | — | — | — |

부동소수점 인자(`float`, `double`)는 같은 순번이라도 정수 레지스터가 아니라 `XMM0`~`XMM3`에 담긴다. 즉 인자가 `(int, double, int, double)`이면 정수용 레지스터와 XMM 레지스터가 순번은 같지만 종류가 나뉘어 각각 채워진다(정수는 RCX/R8, 부동소수점은 XMM1/XMM3 — 순번 슬롯 자체는 공유하되 타입에 따라 다른 레지스터 파일을 쓴다).

### volatile(호출 시 파괴됨) vs nonvolatile(호출 후 보존됨) 레지스터
| 분류 | 레지스터 목록 | 의미 |
|---|---|---|
| Volatile(휘발성) | `RAX, RCX, RDX, R8, R9, R10, R11`, `XMM0`~`XMM5` | 함수 호출(`call`) 후 값이 보존된다는 보장이 없음. 호출된 함수가 자유롭게 덮어써도 됨 |
| Nonvolatile(비휘발성) | `RBX, RBP, RDI, RSI, RSP, R12, R13, R14, R15`, `XMM6`~`XMM15` | 함수가 이 레지스터를 사용하려면 진입 시 저장(`push`)하고 리턴 전 복원해야 함. 호출자는 `call` 이후에도 이 값들이 그대로라고 믿어도 됨 |

`RAX`는 반환값을 담는 용도이면서 동시에 volatile이므로, `call` 직후 `RAX`를 즉시 확인하지 않고 다른 코드를 거치면 값이 덮어써질 수 있다는 점을 기억해야 한다.

### Shadow Space와의 관계
호출자는 인자 개수와 무관하게 `call` 이전에 최소 32바이트(`RCX`/`RDX`/`R8`/`R9` 각각을 위한 8바이트씩)의 스택 공간, 즉 Shadow Space를 확보해야 한다(REV-0124). 다섯 번째 이상 인자는 이 Shadow Space 위쪽(`RSP+0x20` 이후 위치)에 스택으로 쌓인다.

### RSP 정렬 규칙
`call` 명령이 실행되는 시점에서 `RSP`는 16바이트 정렬되어 있어야 한다(`call` 자체가 8바이트 반환 주소를 푸시하므로, 함수 진입 직후 `RSP`는 `16의 배수 - 8` 상태가 정상). 디스어셈블리에서 `sub rsp, 0x28`처럼 딱 떨어지지 않는 홀수 배수의 값을 보게 되는 이유가 바로 이 정렬 요구사항과 Shadow Space 확보가 함께 계산된 결과다.

## 화면/코드에서 보이는 징후
- `call` 직전 코드에서 `mov rcx, ...`, `mov rdx, ...`, `mov r8d, ...`, `mov r9, ...` 순서로 값을 채우는 패턴이 반복된다.
- 함수 프롤로그에서 `push rbx`, `push rsi`, `push rdi` 등이 보이면 이 함수가 nonvolatile 레지스터를 내부적으로 사용하고, 대신 진입 시 저장해두고 있다는 뜻이다.
- IDA의 의사코드(Hex-Rays)에서는 이런 레지스터 배치가 이미 `func(a1, a2, a3, a4)` 형태의 인자 목록으로 정리되어 보이므로, 레지스터를 직접 볼 필요가 어셈블리 뷰보다는 적다.

## 가장 먼저 할 것
분석 중인 `call` 직전 최대 4줄 정도를 확인해 `RCX/RDX/R8/R9`(또는 그 하위 별칭)에 어떤 값이 들어가는지부터 확인한다. 이 네 레지스터만 봐도 대부분의 Win32 API 호출 인자를 바로 읽어낼 수 있다.

## 단계별 절차

**1) call 직전 역순으로 스캔**

`call` 명령 바로 위부터 위쪽으로 훑으며 `rcx`, `edx`, `r8d`, `r9` 등이 나오는 줄을 찾는다. 보통 컴파일러는 이 순서를 지키지 않고 뒤섞어 배치하기도 하므로, 등장 순서가 아니라 어떤 레지스터인지로 인자 번호를 판단한다.

**2) 각 레지스터를 인자 번호로 매핑**

`RCX`→1번째, `RDX`→2번째, `R8`→3번째, `R9`→4번째로 즉시 매핑한다. IDA에서 해당 API의 원형(prototype)이 인식되어 있다면 Hex-Rays 의사코드에서 이미 이름이 붙은 인자로 보이므로 이 단계를 생략할 수 있다.

**3) 5번째 이상 인자는 스택에서 찾기**

`RSP+0x20`, `RSP+0x28` 등으로 접근하는 `mov [rsp+0x20], ...` 코드가 있으면 5번째 인자부터 여기 쌓인다.

**4) 호출 후 어떤 레지스터를 신뢰할지 판단**

`call` 직후 이어지는 코드가 `RAX`가 아닌 다른 레지스터(예: `RBX`)를 그대로 참조한다면, 그 값은 호출 전에 저장돼 있던 nonvolatile 레지스터 값일 가능성이 높다 — 즉 이 함수 호출과 무관하게 유지된 값이다.

## 명령어/단축키
- IDA: 함수 원형이 인식되면 인자에 자동으로 이름이 붙음(`Y`로 타입 강제 지정 가능)
- x64dbg: Registers 창에서 `call` 직전 `RCX/RDX/R8/R9` 값을 직접 확인, `F7`(Step Into)로 호출된 함수 내부까지 들어가서 프롤로그의 `push` 목록 확인
- x64dbg: 스택 창에서 `RSP+0x20` 이후 영역을 보면 5번째 이상 인자 확인 가능

## 출력 해석
- `RCX`에 포인터 같은 값(작은 정수가 아니라 유효 주소로 보이는 값)이 들어있다면 대부분 `this` 포인터(멤버 함수) 또는 문자열/버퍼 주소다.
- `call` 직후 `test rax, rax`나 `cmp eax, ...`가 바로 이어진다면 반환값을 즉시 검사하는 전형적인 패턴이므로, 그 함수의 반환 의미(성공/실패, 개수, 포인터 등)를 확인하면 이후 분기를 바로 이해할 수 있다.
- 함수 프롤로그에 `push rbx`가 있는데 본문 어디에도 `rbx`를 쓰는 코드가 안 보인다면, 컴파일러가 최적화 과정에서 레지스터 스케줄링을 위해 형식적으로 남겨둔 경우도 있으니 실제 사용처를 끝까지 확인 후 판단한다.

## 흔한 실수
- `RCX`가 항상 1번째 인자라고 외웠다가, 멤버 함수(`this` 포인터가 암묵적 1번째 인자)나 특수 호출 규약(`__fastcall`이 아닌 다른 규약)에서는 다를 수 있다는 점을 놓치는 것.
- volatile 레지스터(`R10`, `R11` 등)의 값을 `call` 이후에도 그대로 유지된다고 가정하고 분석을 이어가는 것 — 반드시 nonvolatile 목록과 대조해야 한다.
- 5번째 인자를 찾을 때 Shadow Space(32바이트)를 빼먹고 `RSP+0x0`부터 세는 것 — 5번째 인자는 보통 `RSP+0x20`부터 시작한다.
- x86(32비트) 호출 규약(REV-0123)과 x64 규약을 혼동해서, 32비트 코드에서도 `RCX/RDX`에 인자가 들어있을 거라 기대하는 것.

## 막혔을 때 다음 체크
- 이 표의 배경이 되는 전체 규약 설명이 필요하다면 → REV-0122 Microsoft x64 Calling Convention
- Shadow Space가 왜 필요한지 더 자세히 알고 싶다면 → REV-0124(Shadow Space) 문서 참고
- 32비트(x86) 호출 규약과의 차이가 궁금하다면 → REV-0123 Windows x86 stdcall cdecl fastcall thiscall
- 실제 도구에서 레지스터 값을 확인하는 법이 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
// CreateFileW(lpFileName, dwDesiredAccess, dwShareMode, lpSecurityAttributes,
//             dwCreationDisposition, dwFlagsAndAttributes, hTemplateFile)
```
7개 인자 중 처음 4개만 레지스터로 넘어가고 나머지는 스택에 쌓인다.
```asm
lea  rcx, [file_path]      ; 1번째: lpFileName
mov  edx, 0x80000000       ; 2번째: dwDesiredAccess (GENERIC_READ)
mov  r8d, 1                ; 3번째: dwShareMode (FILE_SHARE_READ)
xor  r9d, r9d               ; 4번째: lpSecurityAttributes (NULL)
mov  [rsp+0x20], 3          ; 5번째: dwCreationDisposition (OPEN_EXISTING) - Shadow Space 바로 위
mov  dword ptr [rsp+0x28], 0x80   ; 6번째: dwFlagsAndAttributes (FILE_ATTRIBUTE_NORMAL)
mov  qword ptr [rsp+0x30], 0      ; 7번째: hTemplateFile (NULL)
call CreateFileW
; 반환값(HANDLE)은 RAX에 담김
```

## 관련 글
- REV-0122 — Microsoft x64 Calling Convention
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall
- REV-0526 — PE Characteristics 플래그 사전
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적

## 출처/검증
- Windows x64 호출 규약, volatile/nonvolatile 레지스터 목록, Shadow Space 및 스택 정렬 규칙은 Microsoft 공식 문서(learn.microsoft.com, "x64 calling convention", "x64 software conventions") 기준(2026-09-08 확인).
