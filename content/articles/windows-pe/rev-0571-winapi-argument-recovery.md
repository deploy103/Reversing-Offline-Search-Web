---
id: REV-0571
title: "WinAPI 함수 인자를 스택/레지스터에서 순서대로 복원하는 실전 팁"
slug: "rev-0571-winapi-argument-recovery"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["함수 인자 복원", "stdcall push 순서", "x64 RCX RDX R8 R9", "MSDN 함수 시그니처", "argument recovery", "call stack"]
aliases: ["API 인자 읽는 법", "함수 호출 전 인자 확인", "스택에서 인자 읽기", "레지스터에서 인자 읽기"]
symptom_keywords: ["call 하기 전에 push가 몇 번 되는지 세야 한다", "x64에서 인자가 어느 레지스터에 있는지 모르겠다", "MSDN 함수 원형과 어셈블리를 매칭하고 싶다", "다섯 번째 인자는 어디서 찾나"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
API 호출(`call`) 직전의 어셈블리 코드에서 실제로 어떤 값이 몇 번째 인자로 전달되는지 정확히 읽어내는 능력은, x86에서는 `call` 직전의 `push` 명령어들을 역순으로 읽고 x64(Windows 호출 규약)에서는 처음 네 개 인자가 `RCX, RDX, R8, R9`에, 다섯 번째부터는 스택에 쌓인다는 규칙만 알면 되지만, 실제 디스어셈블리에서는 최적화, 레지스터 재사용, 구조체 전달 등으로 헷갈리기 쉬우므로 체계적인 확인 절차가 필요하다.

## 언제 검색해야 하나
- IDA/x64dbg에서 `call CreateFileW` 같은 API 호출을 봤는데, 그 함수가 정확히 몇 개의 인자를 받고 각각이 무엇을 의미하는지 MSDN 원형과 매칭이 안 될 때
- x64 디스어셈블리에서 `call` 직전에 `push`가 안 보이는데 인자를 어디서 찾아야 할지 모를 때
- x64dbg로 API 호출 직전에 멈춰서 실제 문자열/값 인자를 확인하고 싶은데 레지스터 이름과 인자 순서 대응이 헷갈릴 때
- 다섯 개 이상 인자를 받는 API(`CreateProcessW` 등)를 분석하다가 다섯 번째 이후 인자를 스택 어디서 읽어야 할지 모를 때

## 핵심 개념
Windows API 인자를 복원하는 첫 단계는 **어떤 호출 규약(calling convention)이 쓰였는지 파악하는 것**이다. x86(32비트)에서 Win32 API는 거의 전부 `__stdcall`을 쓰고(REV-0123 참고), x64에서는 사실상 하나의 통일된 규약인 Microsoft x64 Calling Convention만 쓰인다(REV-0122 참고).

**x86 `__stdcall`에서 인자 복원**: 함수 호출 전에 인자들이 **오른쪽에서 왼쪽 순서로**(C 원형 기준 마지막 인자부터) 스택에 `push`된다. 즉 디스어셈블리에서 `call` 바로 위쪽에 쌓여있는 `push` 명령어들을 **아래에서 위로**(즉 `call`에 가장 가까운 `push`가 먼저 `pop`되어 첫 번째 인자가 됨) 읽으면 C 함수 원형의 인자 순서와 일치한다. 예를 들어 `MSDN`에 `CreateFileA(lpFileName, dwDesiredAccess, dwShareMode, ...)`로 정의되어 있다면, `call CreateFileA` 바로 위의 `push`가 마지막 인자(`hTemplateFile`)이고, 가장 위쪽(즉 `call`에서 가장 먼 `push`)이 첫 번째 인자(`lpFileName`)다. `__stdcall`은 호출된 함수(callee) 쪽에서 `ret n`으로 스택을 정리하므로, `call` 직후에 `add esp, N` 같은 스택 정리 코드가 보통 없다 — 있다면 `__cdecl`일 가능성을 의심해야 한다.

**x64 Microsoft 호출 규약에서 인자 복원**: 정수/포인터 인자 기준으로 첫 번째부터 네 번째까지는 각각 `RCX`, `RDX`, `R8`, `R9`에 담긴다(부동소수점은 `XMM0`~`XMM3`을 쓰지만 레지스터 슬롯 번호는 공유). 다섯 번째 인자부터는 스택에 쌓이는데, 이때 스택 상의 위치는 `RSP+0x20`(다섯 번째 인자, 4개의 레지스터 인자를 위해 예약된 "shadow space" 32바이트 다음, REV-0124 참고), `RSP+0x28`(여섯 번째), 이런 식으로 8바이트씩 증가한다. 문제는 컴파일러가 최적화하면서 `RCX`에 값을 넣는 `mov` 명령어가 `call` 바로 위가 아니라 훨씬 앞쪽에 미리 배치되는 경우가 많다는 것이다. 따라서 `call` 직전만 보지 말고, 함수 시작부터 각 인자 레지스터(`RCX`, `RDX`, `R8`, `R9`)에 마지막으로 값이 쓰인 지점을 거꾸로 추적해야 한다.

**인자 개수와 의미 확인**: 어셈블리만 봐서는 몇 개의 인자를 받는지 확신하기 어려우므로, 반드시 Microsoft Learn의 해당 API 문서(예: "CreateFileW function")에서 공식 원형을 찾아 인자 개수와 각 인자의 타입/의미를 대조해야 한다. IDA는 잘 알려진 API에 대해 타입 정보(Type Library, 흔히 `.til` 파일)를 갖고 있어서, Imports에 있는 함수라면 `Y`(Set item type) 없이도 자동으로 인자 이름이 pseudocode에 표시되는 경우가 많다.

## 화면/코드에서 보이는 징후
- x86: `call` 위에 여러 개의 `push` 명령어가 연속으로 나열되고, 그 사이사이 `lea`/`mov`로 값을 준비하는 코드가 섞여 있음
- x86 `call` 직후에 `add esp, imm`이 없으면 `__stdcall`(호출된 함수가 스택 정리), 있으면 `__cdecl`(호출자가 스택 정리) 가능성
- x64: `call` 직전에 `push`가 거의 없고 대신 `mov rcx, ...`, `mov rdx, ...`, `mov r8d, ...`, `mov r9, ...`가 흩어져 있음
- x64: `call` 직전에 `mov [rsp+20h], ...`, `mov [rsp+28h], ...` 형태로 다섯 번째 이후 인자가 스택에 쌓임
- IDA F5 디컴파일 결과에서 이미 `CreateFileW(lpFileName, GENERIC_READ, ...)`처럼 인자 이름이 자동으로 채워진 경우 — 가장 편한 케이스

## 가장 먼저 할 것
1. 대상 API의 정확한 원형을 Microsoft Learn 문서에서 먼저 찾아 인자 순서/개수/타입을 메모지에 적어둔다. 이것 없이 어셈블리만 봐서는 절대 정확히 복원할 수 없다.
2. IDA에서 해당 `call` 명령을 더블클릭해 함수로 이동한 뒤, IDA가 이미 시그니처를 인식하고 있는지(함수 이름 위에 원형 주석이 있는지) 확인한다. 인식되어 있다면 `F5` 디컴파일 결과가 훨씬 읽기 편하다.

## 단계별 절차
**1) x86: push 순서 거꾸로 읽기**
- `call` 명령어부터 위로 올라가며 연속된 `push`들을 순서대로 나열한다.
- 나열한 리스트를 뒤집으면(가장 마지막에 나온 `push`, 즉 `call`에서 가장 먼 것이 첫 번째) MSDN 원형의 인자 순서와 일치한다.
- 각 `push`의 오퍼랜드가 상수인지, 레지스터인지, 스택 변수(`[ebp-8]` 등)인지 확인하고 그 값이 어디서 왔는지 위쪽 코드에서 추적한다.

**2) x64: 레지스터별 마지막 대입 지점 추적**
- `call` 명령어에서 위로 올라가며 `rcx`/`ecx`, `rdx`/`edx`, `r8`/`r8d`, `r9`/`r9d`에 값이 쓰이는 가장 가까운 `mov`를 각각 찾는다. 순서(코드 상 위치)는 중요하지 않고, "그 레지스터에 마지막으로 쓰인 값"만 중요하다.
- 다섯 번째 이후 인자는 `[rsp+20h]`부터 8바이트씩 증가하는 위치에서 찾는다. 단, 이 스택 오프셋은 함수 진입 시 `sub rsp, N`으로 확보한 지역 프레임 크기에 따라 달라지므로, 실제 `rsp` 기준 오프셋을 정확히 계산해야 한다.

**3) x64dbg로 실제 값 확인(동적 검증)**
- 대상 `call` 명령어에 브레이크포인트(`F2`)를 건다.
- 실행이 멈추면 레지스터 창에서 `RCX`, `RDX`, `R8`, `R9` 값을 바로 확인한다. 포인터 값이면 우클릭 → `Follow in Dump`로 실제 가리키는 데이터(문자열 등)를 확인한다.
- 다섯 번째 이후 인자는 Dump 창에서 `RSP+20`, `RSP+28` 위치로 이동(`Ctrl+G`에 `rsp+20` 입력)해 값을 읽는다.
- x64dbg의 콜스택(`Call Stack`) 창은 API 호출 시 자동으로 알려진 함수의 인자를 이름과 함께 보여주는 경우가 많아, 이 창을 적극 활용하면 수동 계산 없이도 인자를 바로 확인할 수 있다.

**4) 구조체 인자 처리**
- 인자가 구조체 포인터(예: `STARTUPINFO*`)인 경우, 포인터가 가리키는 메모리를 덤프해 구조체 정의(MSDN 문서의 필드 오프셋)와 대조하며 각 필드 값을 읽는다. IDA에서는 `Alt+T`로 구조체 타입을 적용하면 pseudocode에 필드 이름이 자동으로 표시된다.

## 명령어/단축키
- IDA: `F5`(디컴파일), 함수 원형 위 우클릭 `Set call type`, `Y`(변수/함수 타입 지정), `Alt+T`(구조체 적용)
- x64dbg: `F2`(브레이크포인트), `Ctrl+G`(주소/레지스터 표현식 이동, 예: `rsp+20`), 레지스터 창 우클릭 `Follow in Dump`, `Call Stack` 창

## 출력 해석
- x64에서 `RCX`가 핸들 값처럼 작은 정수(예: `0xFFFFFFFFFFFFFFFF` 같은 `INVALID_HANDLE_VALUE` 또는 작은 정수 핸들)라면 파일/커널 핸들 인자일 가능성이 높다.
- 포인터인데 `Follow in Dump` 했을 때 유니코드 텍스트(2바이트 간격 ASCII처럼 보임)가 나오면 `LPCWSTR` 문자열 인자다(REV-0128 참고).
- 값이 0이거나 `NULL`이면 옵션성 인자(예: 보안 속성, 예약된 파라미터)일 가능성이 크므로 기능 이해에 큰 영향이 없는 경우가 많다.

## 흔한 실수
- x86에서 `push` 순서를 뒤집지 않고 코드에 나온 순서 그대로 인자 순서라고 착각하는 것. 반드시 역순으로 읽어야 한다.
- x64에서 `call` 바로 위쪽만 보고 "레지스터 대입이 없으니 인자가 없다"고 판단하는 것. 최적화된 코드는 훨씬 앞쪽에서 레지스터를 채워두는 경우가 흔하다.
- 32비트 레지스터 이름(`ecx`)과 64비트 이름(`rcx`)이 같은 레지스터의 하위/전체 비트라는 것을 모르고 다른 값으로 착각하는 것.
- 다섯 번째 인자 이후의 스택 오프셋을 계산할 때 함수의 로컬 스택 프레임 크기(`sub rsp, N`)를 반영하지 않아 엉뚱한 위치를 읽는 것.
- MSDN 원형을 확인하지 않고 인자 개수를 어셈블리만으로 추측하는 것 — 옵션 인자나 예약된 인자가 있는 API에서는 특히 위험하다.

## 막혔을 때 다음 체크
- 호출 규약 자체가 헷갈리면 → REV-0122(Microsoft x64 Calling Convention), REV-0123(Windows x86 stdcall cdecl fastcall thiscall)을 먼저 복습한다.
- x64에서 다섯 번째 인자 스택 위치가 헷갈리면 → REV-0124(Shadow Space가 무엇인지)를 확인한다.
- 인자를 다 복원했는데 API 이름 자체가 뭘 하는 함수인지 모르겠다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
x64 디스어셈블리 예시:
```asm
mov     rcx, [rbp-8]            ; 1번째 인자 (hFile)
lea     rdx, [rbp+0x20]         ; 2번째 인자 (lpBuffer, 지역 버퍼 주소)
mov     r8d, 0x100              ; 3번째 인자 (nNumberOfBytesToRead)
lea     r9, [rbp-0x30]          ; 4번째 인자 (lpNumberOfBytesRead, 지역 변수 주소)
mov     qword ptr [rsp+0x20], 0 ; 5번째 인자 (lpOverlapped = NULL, 스택 전달)
call    ReadFile
```
`ReadFile`의 MSDN 원형은 `ReadFile(HANDLE hFile, LPVOID lpBuffer, DWORD nNumberOfBytesToRead, LPDWORD lpNumberOfBytesRead, LPOVERLAPPED lpOverlapped)`이다. 이 코드에서 `RCX=hFile`, `RDX=lpBuffer`, `R8=nNumberOfBytesToRead`, `R9=lpNumberOfBytesRead`라는 고정 슬롯 매핑을 그대로 대입하고, 다섯 번째 인자 `lpOverlapped`은 shadow space 바로 뒤인 `[rsp+0x20]`에서 읽는다. 여기서 핵심은 "몇 번째로 나온 `mov`인가"가 아니라 "어느 레지스터/스택 위치에 값이 들어갔는가"이다 — 컴파일러 최적화 순서에 따라 `mov` 명령어들의 코드상 순서는 얼마든지 뒤바뀔 수 있지만, 최종적으로 `call` 시점에 `RCX/RDX/R8/R9`와 `[rsp+0x20]`에 어떤 값이 들어있는지만 확인하면 인자 순서는 항상 동일하게 복원된다.

## 관련 글
- REV-0122 — Microsoft x64 Calling Convention
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall
- REV-0124 — Shadow Space가 무엇인지
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- x86 `__stdcall`의 우→좌 push 순서 및 callee 스택 정리 규칙은 Microsoft Learn "Argument Passing and Naming Conventions" 문서 기준이다.
- x64 Microsoft Calling Convention의 `RCX/RDX/R8/R9` 정수 인자 슬롯과 shadow space 규칙은 Microsoft Learn "x64 calling convention" 공식 문서 기준이다.
- 개별 API(`CreateFileW`, `ReadFile` 등)의 정확한 인자 순서와 타입은 실습 시 Microsoft Learn의 해당 함수 문서를 직접 대조해 확인할 것을 권장한다(2026-09-08 기준 서술).
