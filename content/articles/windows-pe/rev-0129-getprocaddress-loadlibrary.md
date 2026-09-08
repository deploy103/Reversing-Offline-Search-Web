---
id: REV-0129
title: "GetProcAddress LoadLibrary 동적 API 해석"
slug: "rev-0129-getprocaddress-loadlibrary"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["GetProcAddress", "LoadLibraryA", "LoadLibraryW", "동적 API 해석", "dynamic API resolution", "런타임 링킹", "import table 숨기기", "함수 포인터 해석"]
aliases: ["동적 API 로딩", "런타임 함수 찾기", "GetProcAddress LoadLibrary 패턴", "API 해시 로딩"]
symptom_keywords: ["import table에 함수가 거의 없는데 뭔가 더 씀", "GetProcAddress 호출 뒤에 뭘 하는지 모르겠음", "LoadLibraryA 인자로 문자열이 넘어가는데 뭔지 모르겠음", "함수 포인터를 call로 바로 호출하는데 어디로 가는지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LoadLibraryA/W`로 DLL을 메모리에 로드하고 `GetProcAddress`로 그 안의 함수 주소를 문자열 이름으로 직접 찾아오는 패턴은, Import Table에 함수 이름이 아예 안 남기 때문에 정적 분석만으로는 "이 프로그램이 실제로 어떤 API를 쓰는지" 알아내기 어렵게 만드는 흔한 기법이며, 이 패턴을 알아보는 것이 정적 분석의 사각지대를 메우는 첫걸음이다.

## 언제 검색해야 하나
- Import Table을 봤는데 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress` 딱 이 두 개(또는 소수)만 있고 나머지 API는 안 보일 때
- 디스어셈블리에서 문자열을 인자로 넘기며 `call`을 두 번 연속(한 번은 DLL 이름, 한 번은 함수 이름) 하는 패턴을 봤을 때
- `call`의 대상이 상수 주소가 아니라 레지스터(`call rax`, `call rbx` 등)라서 IDA가 이름을 자동으로 못 붙여줄 때
- 악성코드/패커/난독화된 바이너리가 정적 Import Table을 최소화하려고 왜 이런 패턴을 쓰는지 이해하고 싶을 때

## 핵심 개념

### 정적 링킹 vs 동적(런타임) 해석
일반적인 프로그램은 컴파일/링크 시점에 "이 함수는 `kernel32.dll`의 `CreateFileW`다"라는 정보를 Import Table에 기록해두고, Windows 로더가 프로세스 시작 시 이 테이블을 보고 자동으로 함수 주소를 채워 넣는다(정적 임포트). 반면 프로그램은 실행 중에 직접 다음 두 API 조합으로 원하는 함수의 주소를 스스로 찾아낼 수도 있다(동적/런타임 해석).

```c
HMODULE LoadLibraryA(LPCSTR lpLibFileName);
HMODULE LoadLibraryW(LPCWSTR lpLibFileName);
FARPROC GetProcAddress(HMODULE hModule, LPCSTR lpProcName);
```

- `LoadLibraryA`/`W`는 DLL 이름 문자열(`"user32.dll"` 등)을 받아 해당 DLL을 프로세스 메모리에 로드하고(이미 로드되어 있으면 그 핸들을 그대로 반환) 모듈 핸들(`HMODULE`)을 돌려준다.
- `GetProcAddress`는 그 모듈 핸들과 함수 이름 문자열(`"MessageBoxW"` 등, ANSI만 받는다는 점에 주의 — `W` 버전이 없다)을 받아, 해당 함수의 실제 메모리 주소를 `FARPROC`(함수 포인터) 타입으로 돌려준다.

이렇게 얻은 함수 포인터는 이후 `call rax`처럼 레지스터를 통해 간접 호출된다.

### 왜 이 패턴을 쓰는가
- **정적 분석 방해**: Import Table만 훑어보는 자동화 툴이나 사람은 이 프로그램이 실제로 무슨 API를 쓰는지 알 수 없다. 악성코드나 상용 프로텍터가 흔히 쓰는 이유다.
- **함수 이름 자체를 숨기기 위한 추가 인코딩**: 문자열 `"CreateFileW"`를 그대로 두면 문자열 검색(REV-0128)만으로 걸리므로, 문자열을 XOR 등으로 인코딩해뒀다가 호출 직전에 복호화해서 `GetProcAddress`에 넘기는 경우도 흔하다.
- **API 해시(hashing) 기법**: 더 나아가면 함수 이름 문자열 자체도 남기지 않고, 이름의 해시값(예: ROR13 해시, CRC32 등)만 코드에 상수로 박아두고, Export Table을 순회하며 각 함수 이름의 해시를 직접 계산해서 비교하는 방식도 있다. 이 경우 `GetProcAddress`조차 호출하지 않고 PE 구조(Export Directory)를 직접 파싱하므로 더 추적하기 어렵다. 이 문서에서는 기본적인 `GetProcAddress`/`LoadLibrary` 패턴까지만 다룬다.
- **지연 로딩(lazy loading)**: 항상 필요하지 않은 DLL을 조건에 따라 그때그때 로드해서 시작 속도를 줄이거나, 특정 OS 버전에만 있는 API를 안전하게 확인 후 쓰기 위한 정상적인 용도로도 널리 쓰인다 — 이 패턴이 항상 악의적인 것은 아니다.

## 화면/코드에서 보이는 징후
- Import Table에 `LoadLibraryA`(또는 `W`), `GetProcAddress`만 눈에 띄게 있고 그 외 API가 극단적으로 적음(REV-0125의 Import Table 확인 절차와 연결됨).
- 디스어셈블리에서 문자열 주소를 인자로 넘기며 `call LoadLibraryA` → 반환값(`RAX`/`EAX`)을 다음 호출의 첫 인자로 재사용 → 다른 문자열을 두 번째 인자로 넘기며 `call GetProcAddress` 순서가 반복됨.
- `GetProcAddress` 호출 직후 반환값(`RAX`)을 전역 변수나 스택에 저장했다가, 나중에 그 값을 레지스터에 옮긴 뒤 `call rax`처럼 간접 호출하는 코드.
- IDA에서 이런 간접 호출 지점은 이름이 자동으로 안 붙기 때문에 `call rax`처럼만 보이고, 그래프 뷰에서 화살표로 다음 함수까지 안 이어져 분석 흐름이 끊긴 것처럼 보임.
- Strings 창에 DLL 이름(`.dll` 확장자 포함 문자열)과 API 함수 이름처럼 보이는 문자열들이 여럿 모여 있음.

## 가장 먼저 할 것
`GetProcAddress` 호출을 발견하면 곧바로 그 직전의 **두 번째 인자(함수 이름 문자열)**부터 확인한다. Windows x64라면 `RDX`, x86 stdcall이라면 스택의 두 번째 인자 위치를 본다. 이 문자열 값만 알아내면 "이 프로그램이 결국 어떤 함수를 쓰려는 것인지" 즉시 알 수 있고, 이후의 간접 호출(`call rax` 등)이 사실상 그 함수를 부르는 것과 같다고 이해하고 분석을 이어갈 수 있다.

## 단계별 절차

**1) LoadLibrary 호출 지점 찾기**

IDA Imports 창에서 `LoadLibraryA`/`LoadLibraryW`를 찾아 `X`(xref)로 호출 지점을 추적한다. 호출 직전 인자(x64: `RCX`, x86: 스택 첫 인자)에 어떤 DLL 이름 문자열이 들어가는지 확인한다.

**2) LoadLibrary 반환값의 행선지 추적**

`call LoadLibraryA` 이후 `RAX`(또는 `EAX`) 값이 어느 레지스터/지역 변수에 저장되는지 따라간다. 이 값이 바로 다음 `GetProcAddress` 호출의 첫 번째 인자(`HMODULE`)로 쓰인다.

**3) GetProcAddress 호출과 두 번째 인자(함수 이름) 확인**

`call GetProcAddress` 직전, 두 번째 인자(x64: `RDX`, x86: 스택 두 번째 인자)에 들어가는 문자열 주소를 확인한다. 이 문자열이 바로 실제로 찾으려는 함수 이름이다. IDA에서 해당 주소로 이동해 문자열 내용을 직접 읽는다.

**4) 반환값(함수 포인터)이 쓰이는 지점(간접 호출) 찾기**

`GetProcAddress`의 반환값이 저장되는 변수를 찾고, 그 변수가 나중에 `call reg`나 `call [mem]` 형태로 호출되는 지점을 xref로 추적한다. 이 지점에 도달하면, "이 `call`은 사실 함수 이름 문자열에서 확인한 그 API를 부르는 것"이라고 주석을 달아두면 이후 분석이 훨씬 쉬워진다.

**5) 문자열이 인코딩되어 있다면 복호화 로직부터 확인**

`GetProcAddress`에 넘기는 문자열이 사람이 읽을 수 없는 값이라면, 그 문자열이 만들어지기 직전의 루프(XOR 복호화 등)를 먼저 분석해서 원래 함수 이름을 복원해야 한다.

**6) x64dbg로 동적 검증**

`GetProcAddress`에 브레이크포인트를 걸고 실제 실행 중에 인자 값을 직접 읽으면, 정적 분석에서 문자열 추적이 헷갈렸던 부분을 빠르게 확인할 수 있다.

```text
bp GetProcAddress
run
; x64: RCX = HMODULE, RDX = 함수 이름 문자열 포인터
dq rdx        ; 또는 문자열 뷰로 [RDX] 확인
```

## 명령어/단축키
- IDA: `X`(xref로 호출 지점 추적), Imports 창에서 `LoadLibraryA`/`GetProcAddress` 검색
- x64dbg: `bp GetProcAddress`(브레이크포인트), Registers 창에서 `RCX`(모듈 핸들)/`RDX`(함수 이름 포인터) 확인, 우클릭 → `Follow in Dump`로 문자열 내용 확인
- x64dbg 커맨드바: `bp LoadLibraryA`, `bp LoadLibraryW`도 함께 걸어두면 로드되는 DLL 순서까지 추적 가능

## 출력 해석
- `GetProcAddress`의 두 번째 인자 문자열이 정상적인 함수 이름(`"VirtualAlloc"` 등)으로 바로 읽힌다면 단순 지연 로딩/동적 해석 패턴이다.
- 두 번째 인자가 숫자(정수)처럼 보인다면, 이는 함수 이름이 아니라 **Ordinal(순번)로 함수를 찾는 것**이다 — `MAKEINTRESOURCE` 매크로로 만든 값이며, 이 경우 함수 이름은 Export Table의 순번 매핑을 따로 확인해야 알 수 있다.
- `GetProcAddress`가 `NULL(0)`을 반환하면 해당 함수를 못 찾았다는 뜻이며, 이후 코드에서 `test rax, rax` / `jz`로 실패 처리를 하는 분기가 이어질 가능성이 높다.
- 반환된 함수 포인터가 곧바로 저장되지 않고 다른 함수의 인자로 즉시 전달된다면(예: 콜백 등록 API에 넘기는 경우), 이 함수가 나중에 이벤트/콜백 형태로 호출될 것이라는 뜻이다.

## 흔한 실수
- `GetProcAddress`의 반환값(함수 포인터)이 곧바로 호출되지 않아서 "이 API는 안 쓰이는구나"라고 오판하는 것 — 저장됐다가 한참 뒤 다른 곳에서 간접 호출될 수 있으므로 끝까지 xref를 추적해야 한다.
- 첫 번째 인자와 두 번째 인자를 헷갈려서, `LoadLibrary`가 반환한 모듈 핸들을 함수 이름으로 착각하거나 그 반대로 착각하는 것.
- Ordinal(정수) 기반 `GetProcAddress` 호출을 문자열 기반과 똑같이 취급해서 두 번째 인자 주소에서 억지로 문자열을 읽으려다 엉뚱한 데이터를 읽는 것.
- 간접 호출(`call rax`)을 그냥 "알 수 없는 호출"로 넘기고 분석을 포기하는 것 — 앞선 `GetProcAddress` 호출만 추적하면 대부분 실제 대상 함수를 특정할 수 있다.

## 막혔을 때 다음 체크
- `call` 직전 인자가 어느 레지스터에 담기는지 다시 확인하려면 → REV-0122 Microsoft x64 호출 규약
- 함수 이름 문자열이 UTF-16으로 저장되어 있어서 안 보이는 것 같다면 → REV-0128 Windows 문자열 ASCII와 UTF-16 찾기(단, `GetProcAddress`의 함수 이름 인자는 항상 ANSI/1바이트라는 점에 주의)
- 이 패턴이 안티디버깅 API(`IsDebuggerPresent` 등)를 동적으로 숨기려는 목적이라면 → REV-0130 IsDebuggerPresent 안티디버깅 식별
- x64dbg로 직접 실행하며 확인하는 기본기가 필요하다면 → REV-0127 x64dbg로 EXE 첫 분석 시작

## 미니 예제
```c
HMODULE h = LoadLibraryA("user32.dll");
FARPROC fn = GetProcAddress(h, "MessageBoxA");
((int(WINAPI*)(HWND,LPCSTR,LPCSTR,UINT))fn)(NULL, "Hi", "Title", MB_OK);
```
x64 디스어셈블리로는 대략 다음과 같이 나타난다.
```asm
lea  rcx, [dll_name]       ; "user32.dll"
call LoadLibraryA
mov  [module_handle], rax  ; HMODULE 저장

mov  rcx, [module_handle]
lea  rdx, [func_name]      ; "MessageBoxA"
call GetProcAddress
mov  [fn_ptr], rax         ; 함수 포인터 저장

mov  r9d, 0                ; MB_OK
lea  r8, [title_str]       ; "Title"
lea  rdx, [msg_str]        ; "Hi"
xor  ecx, ecx               ; NULL
call qword ptr [fn_ptr]     ; 사실상 MessageBoxA 호출
```
마지막 `call qword ptr [fn_ptr]`은 IDA가 이름을 자동으로 못 붙이지만, 앞선 `GetProcAddress` 인자 `"MessageBoxA"`를 확인했다면 이 호출이 곧 `MessageBoxA(NULL, "Hi", "Title", MB_OK)`라는 것을 알 수 있다.

## 관련 글
- REV-0122 — Microsoft x64 Calling Convention
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- `LoadLibraryA/W`, `GetProcAddress` 함수 시그니처와 동작(Ordinal 조회 포함)은 Microsoft 공식 문서(learn.microsoft.com, "LoadLibraryA function", "GetProcAddress function") 기준.
- 동적 API 해석이 정적 분석 회피에 쓰이는 관례는 일반 리버싱/악성코드 분석 레퍼런스 기준(2026-09-08 확인).
