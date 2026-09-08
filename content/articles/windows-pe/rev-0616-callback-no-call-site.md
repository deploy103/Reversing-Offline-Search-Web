---
id: REV-0616
title: "콜백 함수 주소만 있고 호출부가 안 보일 때"
slug: "rev-0616-callback-no-call-site"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["콜백 함수", "callback", "함수 포인터", "CreateThread", "SetTimer", "qsort", "TLS Callback", "간접 호출", "call reg"]
aliases: ["콜백 xref 없음", "함수가 호출되는 곳이 없다", "콜백 주소만 저장됨", "함수 포인터 배열"]
symptom_keywords: ["함수에 CALL로 오는 xref가 하나도 없다", "IDA에서 이 함수를 부르는 곳이 안 보인다", "함수 주소가 데이터 영역에만 저장되어 있다", "콜백처럼 보이는데 호출부를 못 찾겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
함수에 `CALL` 형태의 코드 교차 참조(code xref)가 없다면, 그 함수는 **콜백**으로 쓰이고 있을 가능성이 높다. 즉 함수 자체가 직접 불리는 게 아니라 "이 주소를 나중에 불러줘"라는 뜻으로 다른 함수(스레드 생성, 타이머, 정렬 함수, 윈도우 프로시저 등)에 **주소값(데이터)**으로 전달된다. 해결은 코드 xref가 아니라 **데이터 xref**(그 주소를 읽어가는 지점)를 찾는 것이다.

## 언제 검색해야 하나
- IDA Functions 창에서 함수를 더블클릭했는데 `X`(교차 참조)를 눌러도 "No cross-references"가 나올 때
- 함수가 분명히 실행되는 것 같은데(동적 분석에서 브레이크포인트가 걸림) 정적 분석에서는 어디서 호출하는지 찾을 수 없을 때
- 전역 배열이나 구조체 안에 함수 시작 주소로 보이는 값이 들어있는데 그게 뭔지 모를 때
- `CreateThread`, `SetTimer`, `qsort`, `EnumWindows`, `AddVectoredExceptionHandler`처럼 "함수 포인터를 인자로 받는" API가 임포트되어 있을 때

## 핵심 개념
IDA의 `X`(cross-reference) 창은 기본적으로 그 주소를 "코드에서 CALL/JMP로 실행 흐름을 넘긴 지점"과 "데이터로 읽어간 지점"을 함께 보여주지만, 사람들이 흔히 코드 xref만 확인하고 데이터 xref는 지나친다. 콜백 함수는 다음처럼 항상 **주소값 자체가 데이터로서 어딘가에 저장**되고, 그 값을 나중에 다른 코드가 읽어서 간접 호출(`call eax`, `call [rdi+8]`처럼 레지스터/메모리를 통한 호출)한다.

대표적인 콜백 전달 패턴:
- **스레드 시작 함수**: `CreateThread(NULL, 0, ThreadProc, param, 0, NULL)`에서 3번째 인자 `lpStartAddress`가 콜백이다.
- **타이머 콜백**: `SetTimer(hWnd, id, elapse, TimerProc)`, `timeSetEvent(..., lpFunction, ...)`
- **정렬/검색 콜백**: `qsort(base, num, size, compare)`, `bsearch`
- **윈도우 프로시저**: `WNDCLASSEXW.lpfnWndProc`에 함수 주소를 넣고 `RegisterClassExW`로 등록
- **열거 콜백**: `EnumWindows(EnumWindowsProc, lParam)`, `EnumProcessModules` 계열
- **예외 처리기**: `AddVectoredExceptionHandler(1, VectoredHandler)`
- **TLS 콜백**: PE의 TLS 디렉터리 `AddressOfCallBacks` 배열(REV-0133 참고). 이 경우 임포트 함수 호출조차 없이 **로더가 PE 구조체를 직접 읽어서** 실행하므로 더더욱 코드 xref가 없다.
- **APC(비동기 프로시저 호출)**: `QueueUserAPC(pfnAPC, hThread, dwData)`
- **COM 가상함수 테이블(vtable)**: 인터페이스 구조체 안에 함수 포인터 배열이 들어있고 `call [ecx+offset]`처럼 간접 호출된다.

## 화면/코드에서 보이는 징후
- IDA에서 함수 이름 위에 커서를 놓고 `X`를 눌러도 코드 xref가 없거나, "데이터"로 분류된 xref 한두 개만 보임(예: `DATA obj_1234+8`)
- `.rdata`나 `.data` 섹션에서 `dd sub_401000` 또는 `dq sub_140001000`처럼 함수 주소가 그대로 박혀 있는 줄이 보임
- 함수가 `__stdcall`이나 특정 시그니처(3~4개 인자, 특정 반환형)를 가지고 있어서 API 콜백 시그니처와 비슷해 보임(예: `LRESULT CALLBACK`, `int (__cdecl *)(const void*, const void*)`)
- x64dbg로 실행하면서 그 함수 시작 주소에 브레이크포인트를 걸면 실제로 걸리는데, IDA 정적 분석에서는 호출부가 안 보임

## 가장 먼저 할 것
함수 시작 주소를 클릭한 상태에서 IDA `X`(교차 참조) 결과를 다시 확인하되, "Code" 타입뿐 아니라 "Data" 타입 xref도 함께 본다. 데이터 xref가 하나라도 있다면 그 지점(대개 `.data`/`.rdata`의 함수 포인터 테이블이나 구조체 필드)으로 이동해서, 그 값을 누가 읽어가는지 다시 추적한다.

## 단계별 절차
1. **함수가 실제로 인식됐는지 확인**: 회색(정의되지 않은 바이트)으로 보인다면 커서를 놓고 `C`(코드로 변환) → `P`(함수로 정의)를 눌러 먼저 함수로 만든다. 인식이 안 되면 애초에 xref 자체가 생성되지 않는다.
2. **데이터 xref 확인**: 함수 시작 주소에서 `X`를 눌러 나오는 목록에서 `DATA` 타입 항목을 찾는다. 이 주소가 배열의 몇 번째 원소인지, 어떤 구조체 필드인지 확인한다.
3. **그 데이터를 읽는 코드 추적**: 데이터 xref가 가리키는 주소(예: `off_402000`)에 다시 `X`를 눌러, 그 주소를 읽어가는 코드(예: `push offset off_402000` 후 `call CreateThread`)를 찾는다.
4. **API 시그니처로 역추적**: `CreateThread`, `SetTimer`, `qsort` 등 콜백을 인자로 받는 API의 임포트 xref를 먼저 찾고, `F5` 디컴파일 결과에서 그 API 호출의 콜백 인자 위치에 어떤 함수 이름이 들어가는지 직접 확인하는 것이 더 빠를 때가 많다. IDA Imports 창에서 API 이름을 더블클릭 → `X`로 호출부를 찾은 뒤, Hex-Rays(`F5`)로 인자를 한눈에 본다.
5. **TLS 콜백이 의심되면**: IDA는 `.tls` 섹션과 TLS 디렉터리를 자동 인식해 `Functions` 창에 별도로 표시하는 경우가 많다. 안 보이면 Optional Header의 `DataDirectory[9]`(TLS Directory)를 직접 확인한다(REV-0133 참고).
6. **동적 분석으로 교차 검증**: x64dbg에서 의심되는 함수 시작 주소에 `bp <주소>`를 걸고 실행해, 실제로 멈추는지, 멈췄을 때 콜 스택(Call Stack 창)에 어떤 함수가 찍히는지 확인한다. 콜 스택에 `CreateThread`나 `ntdll.RtlUserThreadStart` 같은 이름이 보이면 스레드 시작 함수라는 확증이다.

## 명령어/단축키
- IDA: `X`(교차 참조, Code/Data 모두 확인), `C`(코드로 변환), `P`(함수로 정의), `F5`(Hex-Rays 디컴파일)
- IDA: Imports 창에서 API 더블클릭 후 `X`로 호출부 찾기
- x64dbg: `bp <주소>`(임의 주소에 브레이크포인트), Call Stack 창으로 호출 경로 확인

## 출력 해석
- 데이터 xref만 있고 코드 xref가 없다 = 100% 간접 호출(콜백)로 쓰인다는 뜻이다. 이는 버그가 아니라 정상적인 함수 포인터 패턴이다.
- 콜 스택 최상단에 `BaseThreadInitThunk`나 `RtlUserThreadStart`가 보이면 `CreateThread`로 시작된 스레드 함수라는 뜻이다.
- TLS 콜백은 `main`/`WinMain`보다도 먼저 실행되므로, 이 함수 안에서 안티디버깅 체크나 초기화 로직이 들어있는 경우가 흔하다.

## 흔한 실수
- `X` 결과에서 "No cross-references"만 보고 포기하는 것. Data 타입 xref는 별도 필터가 걸려 있거나 목록 아래쪽에 있을 수 있으니 전체 목록을 스크롤해서 확인해야 한다.
- 함수가 아직 정의되지 않은 바이트(빨간/회색)로 남아 있어서 애초에 xref 분석 대상이 안 된 경우를 놓치는 것.
- 간접 호출(`call eax`, `call [rdi+8]`)은 IDA가 대상 주소를 정적으로 알 수 없기 때문에 자동으로 xref를 연결해주지 못한다. 이런 경우는 동적 분석(브레이크포인트) 없이는 정적으로 100% 확정하기 어렵다.
- TLS 콜백을 "그냥 임포트 함수 중 하나"로 착각해서 Imports 창에서만 찾으려 하는 것. TLS 콜백은 임포트가 아니라 PE 구조체(TLS Directory)에 직접 기록된다.

## 막혔을 때 다음 체크
- 콜백이 여러 스레드에서 실행 순서가 뒤섞여 헷갈린다면 → REV-0617(실행마다 API 호출 순서가 달라 보일 때)을 확인한다.
- main 이전에 실행되는 코드가 의심된다면 → REV-0133(TLS Callback과 main 이전 코드)을 먼저 읽는다.
- 함수 이름만으로 역할을 짐작하기 어렵다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
IDA에서 `sub_401500`이라는 함수를 열었는데 `X`를 눌러도 코드 xref가 없다고 하자. `.rdata` 섹션을 스트링/데이터로 훑다가 다음 줄을 발견했다.

```text
.rdata:00402010  dword_402010  dd offset sub_401500
```

이 `dword_402010`에 다시 `X`를 눌러보니 다음 코드가 나온다.

```asm
push    0               ; lpThreadId
push    0               ; dwCreationFlags
push    0               ; lpParameter
push    dword_402010    ; lpStartAddress = sub_401500
push    0               ; dwStackSize
push    0               ; lpThreadAttributes
call    CreateThread
```

`sub_401500`이 `CreateThread`의 4번째 인자(`lpStartAddress`)로 전달되는 스레드 함수임을 확인했다. 이제 이 함수 이름을 `ThreadProc_Worker` 같은 이름으로 바꿔두면 이후 분석이 훨씬 명확해진다.

## 관련 글
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0617 — 실행마다 API 호출 순서가 달라 보일 때(멀티스레드)

## 출처/검증
- IDA의 코드/데이터 교차 참조 동작과 간접 호출(레지스터/메모리 대상 CALL)을 정적으로 완전히 해석할 수 없다는 한계는 IDA 공식 문서 및 일반적인 리버싱 실무 지식 기준이다.
- `CreateThread`, `SetTimer`, `qsort`, `EnumWindows`, `AddVectoredExceptionHandler`, `QueueUserAPC`의 함수 시그니처와 콜백 인자 위치는 Microsoft Win32 API 공식 문서 기준이다.
- TLS 콜백 디렉터리 구조는 Microsoft PE/COFF 공식 문서 기준이며, 세부 예제는 설명을 위해 구성했다(2026-09-08 기준 서술).
