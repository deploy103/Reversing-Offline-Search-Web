---
id: REV-0528
title: "Windows 예외 코드(Exception Code) 빠른 참조표"
slug: "rev-0528-windows-exception-code-quickref"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["EXCEPTION_ACCESS_VIOLATION", "STATUS_BREAKPOINT", "EXCEPTION_CODE", "0xC0000005", "0x80000003", "Windows exception code"]
aliases: ["예외 코드 표", "윈도우 STATUS 코드 표", "0xC0000005 뜻", "예외 코드 사전"]
symptom_keywords: ["0xC0000005 에러가 떴는데 뜻을 모르겠음", "x64dbg가 access violation이라며 멈춤", "0x80000003 예외가 뭔지 모르겠음", "STATUS_STACK_OVERFLOW가 뭔지 모르겠음", "예외 코드 16진수를 봐도 무슨 뜻인지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg나 WinDbg가 프로그램을 멈추면서 보여주는 `0xC0000005` 같은 8자리 16진수는 Windows가 정의한 예외 코드(`EXCEPTION_CODE`/`NTSTATUS`)이며, 앞자리 패턴(`0xC0` 계열은 오류, `0x80` 계열은 경고/브레이크포인트성)만 알아도 프로그램이 왜 멈췄는지 코드 값만 보고 대략 짐작할 수 있다.

## 언제 검색해야 하나
- x64dbg가 실행을 멈추고 상태 표시줄이나 로그 창에 `Access violation` 또는 `0xC0000005` 같은 값을 보여줄 때
- IDA 디버거가 예외를 잡고 "Exception ... occurred"라는 메시지를 보여줄 때 그 코드가 정상적인 것인지(예: 소프트웨어 브레이크포인트) 실제 버그인지 구분하고 싶을 때
- CTF 문제 바이너리가 특정 입력에서 크래시가 나는데, 그 크래시의 정확한 원인 분류(널 포인터 역참조, 스택 오버플로, 정수 나눗셈 오류 등)를 코드로 확인하고 싶을 때
- 코드에서 `SetUnhandledExceptionFilter`나 SEH(REV-0134)로 특정 예외 코드를 걸러내는 부분을 만났을 때 그 상수 값의 의미를 찾고 싶을 때

## 핵심 개념

### 코드 값의 구조
Windows 예외 코드는 `NTSTATUS` 값 형식(32비트)을 따르며, 최상위 니블(4비트)이 심각도를 나타낸다.

| 최상위 니블 | 심각도 | 의미 |
|---|---|---|
| `0x0` | Success | 성공 |
| `0x4` | Informational | 정보성 |
| `0x8` | Warning | 경고(디버깅 관련 이벤트가 많음) |
| `0xC` | Error | 오류(대부분의 크래시성 예외) |

이 때문에 실전에서 자주 보이는 값들이 `0xC0000...`(진짜 오류) 아니면 `0x8000...`(브레이크포인트/싱글스텝 같은 디버깅 이벤트) 둘 중 하나로 크게 갈린다.

### 자주 만나는 예외 코드 표
| 코드 값 | 이름 | 의미 |
|---|---|---|
| `0xC0000005` | `EXCEPTION_ACCESS_VIOLATION` | 접근할 수 없는 메모리를 읽거나/쓰거나/실행하려 함(널 포인터 역참조, 잘못된 포인터 등 가장 흔한 크래시) |
| `0xC0000094` | `EXCEPTION_INT_DIVIDE_BY_ZERO` | 정수 나눗셈에서 0으로 나눔 |
| `0xC0000095` | `EXCEPTION_INT_OVERFLOW` | 정수 연산 오버플로(`INTO` 명령 관련, 드묾) |
| `0xC00000FD` | `EXCEPTION_STACK_OVERFLOW` | 스택 공간 소진(과도한 재귀, 거대한 지역 배열 등) |
| `0xC0000025` | `EXCEPTION_NONCONTINUABLE_EXCEPTION` | 계속 진행할 수 없는 예외를 계속하려고 시도함 |
| `0xC000001D` | `EXCEPTION_ILLEGAL_INSTRUCTION` | 잘못된/정의되지 않은 명령어 실행(`ud2` 등) |
| `0xC0000008` | `EXCEPTION_INVALID_HANDLE` | 유효하지 않은 핸들 사용 |
| `0x80000003` | `EXCEPTION_BREAKPOINT` | 소프트웨어 브레이크포인트(`int3`, `0xCC`) 도달 — 디버거가 의도적으로 설정한 경우가 대부분 |
| `0x80000004` | `EXCEPTION_SINGLE_STEP` | 싱글 스텝(Trap Flag) 실행 완료 — Step Into/Over 직후 정상적으로 발생 |
| `0xC0000135` | `STATUS_DLL_NOT_FOUND` | 필요한 DLL을 찾지 못함 |
| `0xC0000139` | `STATUS_ENTRYPOINT_NOT_FOUND` | DLL에서 필요한 함수(엔트리포인트)를 찾지 못함 |
| `0xC000041D` | `STATUS_FATAL_USER_CALLBACK_EXCEPTION` | 사용자 콜백 함수 내부에서 처리되지 않은 예외 발생 |
| `0x40010006` | `DBG_PRINTEXCEPTION_C` | `OutputDebugStringA`가 사용하는 정보성 예외(REV-0535 참고) |

### ACCESS_VIOLATION의 추가 정보
`EXCEPTION_ACCESS_VIOLATION`이 발생하면 예외 레코드에 추가 파라미터 2개가 함께 전달된다: 첫 번째는 "읽기 시도였는지(0)/쓰기 시도였는지(1)/실행 시도였는지(8, DEP 위반)"를 나타내고, 두 번째는 접근하려던 실제 주소다. x64dbg는 이 정보를 상태 표시줄에 `Access violation when reading/writing/executing [주소]` 형태로 그대로 풀어서 보여준다.

## 화면/코드에서 보이는 징후
- x64dbg 하단 상태 표시줄에 `Access violation when writing to 0000000000000000` 같은 문구와 함께 실행이 자동으로 멈춘다.
- IDA 디버거는 상단에 `Exception c0000005 occurred (first chance)` 같은 형태로 메시지를 띄운다. `first chance`는 "예외가 발생했고, 프로그램의 예외 핸들러가 아직 이걸 처리할 기회를 갖기 전"이라는 뜻으로, 이 시점에 디버거가 먼저 멈춰서 보여준다.
- `int3`(0xCC 바이트)를 코드에 심어 안티디버깅용 트랩으로 쓰는 바이너리는, 디버거 없이 실행하면 `EXCEPTION_BREAKPOINT`(`0x80000003`)가 처리되지 않아 그냥 크래시하고, 디버거가 붙어 있으면 이 예외를 디버거가 소비해 정상 실행되는 것처럼 보이는 차이를 만들기도 한다.

## 가장 먼저 할 것
멈췄을 때 표시된 예외 코드의 최상위 니블(`0xC`인지 `0x8`인지)부터 확인한다. `0x8`로 시작하면 대부분 정상적인 디버깅 이벤트(브레이크포인트, 싱글스텝)이므로 당황하지 말고 계속 진행(F9/Run)하면 되고, `0xC`로 시작하면 실제 오류이므로 원인을 조사해야 한다.

## 단계별 절차

**1) 코드 값 확인**

x64dbg 상태 표시줄 또는 IDA 예외 메시지에서 8자리 16진수 코드를 읽는다.

**2) 표에서 이름 찾기**

위 표(또는 WinDbg의 `!analyze -v`, MSDN `ntstatus.h`)에서 해당 코드의 공식 이름을 확인한다.

**3) ACCESS_VIOLATION이면 접근 종류와 주소 확인**

x64dbg 상태 표시줄의 "reading/writing/executing" 문구와 주소를 확인한다. 주소가 `0x0000000000000000` 근처라면 널 포인터 역참조 가능성이 크고, 임의의 이상한 값(예: `0x4141414141414141`)이라면 버퍼 오버플로 등으로 포인터/리턴 주소가 덮어써졌을 가능성을 의심한다.

**4) 크래시 지점의 명령어 확인**

x64dbg의 CPU 창에서 현재 `RIP`가 가리키는 명령어를 확인한다. `mov [rax], ...` 형태인데 `RAX`가 `0`이면 널 포인터 쓰기, `call rax`인데 `RAX`가 이상한 값이면 잘못된 함수 포인터 호출이다.

**5) 반복되는 브레이크포인트/싱글스텝 예외는 무시하고 계속 진행**

`0x80000003`, `0x80000004`가 반복해서 뜨는 것은 디버거가 정상적으로 동작하고 있다는 신호이므로, "Pass exception to program"(x64dbg의 예외 처리 옵션) 설정을 확인하고 계속 진행한다.

## 명령어/단축키
- x64dbg: 상태 표시줄에서 예외 코드 확인, `Options > Preferences > Exceptions`에서 특정 예외를 프로그램에 전달할지(Pass) 디버거가 잡을지 설정
- IDA: `Debugger > Debugger options > Exceptions` 탭에서 예외별 처리 방식(중단/무시) 설정
- WinDbg(설치되어 있다면): `!analyze -v`로 크래시 원인 자동 분석, `.exr -1`로 마지막 예외 레코드 확인

## 출력 해석
- `EXCEPTION_ACCESS_VIOLATION` + 쓰기 시도 + 주소가 `0x0`이면 전형적인 널 포인터에 값을 쓰려는 버그다.
- `EXCEPTION_STACK_OVERFLOW`는 대개 재귀 함수가 종료 조건 없이 무한히 자기 자신을 호출하는 경우이며, x64dbg의 콜스택 창에 같은 함수가 수백~수천 번 반복해서 쌓인 모습으로 확인된다.
- `STATUS_DLL_NOT_FOUND`/`STATUS_ENTRYPOINT_NOT_FOUND`는 코드 버그가 아니라 실행 환경 문제(필요한 DLL이 없거나 버전이 다름)인 경우가 대부분이므로, Dependency 확인 도구로 누락된 DLL을 먼저 찾는 것이 우선이다.

## 흔한 실수
- `0x80000003`(브레이크포인트)을 심각한 오류로 오해하고 크래시 원인을 찾아 헤매는 것 — 디버거가 붙어있을 때 정상적으로 뜨는 이벤트다.
- 예외 코드 앞자리(`0xC`/`0x8`)를 확인하지 않고 뒷자리 숫자만 외워서 매번 표를 처음부터 훑는 것 — 앞자리로 먼저 큰 분류를 하면 훨씬 빠르다.
- `first chance` 예외를 보고 바로 프로그램이 죽었다고 판단하는 것 — first chance는 아직 프로그램 자체의 예외 핸들러(SEH)가 처리를 시도하기 전 단계이므로, 계속 진행(F9)하면 프로그램이 스스로 복구할 수도 있다.
- ACCESS_VIOLATION의 "읽기/쓰기/실행" 구분을 무시하고 무조건 같은 원인으로 취급하는 것 — 실행 시도(코드 실행 방지, DEP)로 인한 위반은 원인이 완전히 다르다(예: 셸코드 실행 방지).

## 막혔을 때 다음 체크
- SEH가 예외를 어떻게 가로채는지 배경 지식이 필요하다면 → REV-0134 SEH와 예외 기반 제어 흐름 기초
- `OutputDebugString` 관련 예외(`0x40010006`)의 안티디버깅 활용이 궁금하다면 → REV-0535 OutputDebugString을 이용한 안티디버깅 탐지
- 프로세스 생성/디버깅 관련 플래그가 궁금하다면 → REV-0530 Windows 프로세스 생성 플래그 빠른 참조표
- x64dbg 기본 조작이 아직 낯설다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```text
x64dbg 상태 표시줄:
Access violation when writing to 0000000000000000 - use Shift+F9/F7/F8/F9 to pass exception to program

CPU 창 현재 위치:
mov [rax], ecx    ; RAX = 0 인 상태에서 실행됨 -> 널 포인터에 4바이트 쓰기 시도

해석: EXCEPTION_ACCESS_VIOLATION(0xC0000005), 쓰기(write) 시도,
대상 주소 0x0 -> 전형적인 널 포인터 역참조 버그.
```

## 관련 글
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0535 — OutputDebugString을 이용한 안티디버깅 탐지
- REV-0530 — Windows 프로세스 생성 플래그 빠른 참조표
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- 예외 코드 값과 `NTSTATUS` 심각도 니블 구조는 Microsoft 공식 문서(learn.microsoft.com, "NTSTATUS values", winnt.h의 `EXCEPTION_*`/`STATUS_*` 상수) 및 WinDbg 공식 문서 기준(2026-09-08 확인).
