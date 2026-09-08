---
id: REV-0138
title: "Windows API 이름으로 기능 추측하는 법"
slug: "rev-0138-guess-function-from-api-name"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Windows API", "네이밍 컨벤션", "ANSI Wide", "Nt Zw", "Hungarian notation", "함수 이름 추측"]
aliases: ["API 이름 읽는 법", "Create Get Set Is 접두사", "A W 접미사", "낯선 API 함수 이름 해석"]
symptom_keywords: ["처음 보는 API 함수 이름이다", "이 함수가 뭘 하는지 감이 안 온다", "A로 끝나는지 W로 끝나는지 헷갈린다", "Nt로 시작하는 함수가 뭔지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows API 함수 이름은 대부분 "동사+명사" 형태의 일관된 규칙으로 지어지기 때문에, MSDN 문서를 매번 찾아보지 않아도 접두사(`Create`, `Get`, `Set`, `Is`, `Nt`)와 접미사(`A`, `W`, `Ex`)의 의미만 알면 처음 보는 함수라도 대략 무슨 일을 하는지 상당히 정확하게 짐작할 수 있다.

## 언제 검색해야 하나
- 임포트 테이블에 나열된 함수 이름을 봤는데 처음 보는 이름이라 뭘 하는지 감이 안 잡힐 때
- 오프라인 환경이라 MSDN을 바로 검색할 수 없는데 함수 이름만으로 급하게 판단해야 할 때
- `CreateFileA`와 `CreateFileW`처럼 끝에 A/W가 붙은 함수가 왜 두 개씩 있는지 궁금할 때
- `NtQueryInformationProcess`, `ZwClose`처럼 `Nt`/`Zw`로 시작하는 함수를 만났을 때
- IDA가 함수 인자 이름/타입을 자동으로 안 붙여줘서 함수 이름만 갖고 역할을 유추해야 할 때

## 핵심 개념
Win32 API는 수십 년에 걸쳐 만들어졌지만, 이름 짓는 규칙만큼은 상당히 일관되게 유지되어왔다. 몇 가지 패턴을 알아두면 처음 보는 함수도 절반 이상은 추측이 가능하다.

**1) 동사 접두사(무엇을 하는가)**
- `Create*` — 새로운 객체/리소스를 만든다(예: `CreateFile`, `CreateProcess`, `CreateThread`, `CreateWindow`). 대개 핸들(`HANDLE`)을 반환한다.
- `Open*` — 이미 존재하는 객체에 접근 권한을 얻어 연다(예: `OpenProcess`, `OpenFile`). `Create`가 "새로 만들기"라면 `Open`은 "기존 것 붙잡기"에 가깝다.
- `Close*` — 핸들을 닫아 자원을 해제한다(예: `CloseHandle`).
- `Get*` / `Set*` — 어떤 속성값을 읽거나(Get) 쓴다(Set). 짝을 이루는 경우가 많다(`GetWindowText`/`SetWindowText`, `GetFileAttributes`/`SetFileAttributes`).
- `Is*` / `Has*` — 참/거짓(`BOOL`)을 묻는 질의 함수(예: `IsDebuggerPresent`, `IsWindowVisible`).
- `Enum*` — 여러 개의 항목을 콜백 함수를 통해 하나씩 순회한다(예: `EnumProcesses`, `EnumWindows`). 보통 콜백 함수 포인터를 인자로 받는다.
- `Duplicate*` — 기존 핸들을 복제한다(예: `DuplicateHandle`).
- `Alloc*` / `Free*` — 메모리를 할당/해제하는 짝 함수(예: `HeapAlloc`/`HeapFree`, `VirtualAlloc`/`VirtualFree`, `LocalAlloc`/`LocalFree`, `GlobalAlloc`/`GlobalFree`). 어떤 힙/메모리 관리자를 쓰는지가 접두사(`Heap`, `Virtual`, `Local`, `Global`)에 드러난다.
- `Read*` / `Write*` — 데이터를 읽거나 쓴다(예: `ReadFile`/`WriteFile`, `ReadProcessMemory`/`WriteProcessMemory`).

**2) 접미사 `A`와 `W`(문자 인코딩)**
Windows API 중 문자열을 다루는 함수는 대부분 두 가지 버전이 존재한다.
- `A` 접미사 — ANSI(1바이트 문자, 로케일에 따른 코드페이지 사용). 예: `CreateFileA`, `MessageBoxA`.
- `W` 접미사 — Wide(UTF-16, 2바이트 문자, 유니코드). 예: `CreateFileW`, `MessageBoxW`.

내부적으로는 대부분 `W` 버전이 진짜 구현체이고, `A` 버전은 입력받은 ANSI 문자열을 `MultiByteToWideChar`로 UTF-16으로 변환한 뒤 `W` 버전을 그대로 호출하는 얇은 래퍼(wrapper)인 경우가 많다. 그래서 문자열 처리 관련 진짜 로직을 보고 싶다면 `A` 함수보다 `W` 함수 쪽을 확인하는 것이 더 정확할 때가 있다. IDA의 임포트 목록에서 함수 이름 끝의 `A`/`W`만 보고도 "이 프로그램이 유니코드 문자열을 쓰는지 아닌지"를 짐작할 수 있다.

**3) 접미사 `Ex`(확장판)**
같은 이름에 `Ex`가 붙은 함수(예: `CreateProcessEx`, `RegisterClassEx`, `HeapAllocEx`)는 대개 원래 함수보다 인자가 더 많거나 옵션 플래그가 추가된 확장 버전이다. 오래된 함수를 유지하면서 새로운 기능을 넣을 때 Windows가 자주 쓰는 방식이다.

**4) `Nt*`/`Zw*` 접두사(네이티브 API)**
`kernel32.dll`/`user32.dll` 같은 일반 Win32 API 아래에는 `ntdll.dll`이 제공하는 더 낮은 수준의 **네이티브 API**가 있다. 이 함수들은 `Nt`(User 모드에서 호출) 또는 `Zw`(커널 모드 진입점, User 모드에서 호출 시 사실상 `Nt` 버전과 동일하게 동작) 접두사를 쓴다(예: `NtQueryInformationProcess`, `NtCreateFile`, `ZwClose`). 일반 Win32 API 함수 내부는 결국 이 `Nt*` 함수를 호출해서 실제 시스템 콜로 넘어가는 구조이므로, `Nt*` 함수가 임포트/호출되고 있다면 "일반적인 방식보다 한 단계 더 low-level로 직접 접근하고 있다"는 신호이며, 안티디버깅이나 후킹 우회 목적으로 쓰이는 경우가 흔하다.

**5) 그 외 자주 보이는 접두사**
- `Reg*` — 레지스트리 관련(`RegOpenKeyEx`, `RegQueryValueEx`).
- `Crypt*`/`BCrypt*` — 암호화 관련(REV-0140에서 자세히 다룸).
- `Wsa*`/`socket`, `connect`, `send`, `recv` — 네트워킹(Winsock) 관련.
- `Nt`/`Zw` 외에 `Rtl*`(Run-Time Library)로 시작하는 함수도 `ntdll.dll`의 저수준 유틸리티 함수군이다(예: `RtlMoveMemory`, `RtlZeroMemory`).

## 화면/코드에서 보이는 징후
- 임포트 목록에 `CreateFileW`, `GetProcAddress`, `IsDebuggerPresent` 처럼 동사로 시작하는 이름이 줄줄이 나열됨
- 동일한 이름이 `A`/`W` 두 버전으로 같이 임포트되어 있거나, 하나만 임포트되어 있어서 이 프로그램이 어떤 인코딩을 쓰는지 짐작 가능
- `ntdll.dll`이 임포트 목록에 별도로 있고 `Nt`/`Zw`로 시작하는 함수가 보임
- IDA에서 잘 알려진 Win32 함수를 임포트하면 Hex-Rays 디컴파일러가 자동으로 파라미터 이름과 타입까지 붙여서 보여줌(타입 정보 라이브러리가 있는 경우)

## 가장 먼저 할 것
1. 낯선 함수 이름을 만나면 먼저 **동사 부분**(앞쪽 단어)만 떼어서 `Create`/`Get`/`Set`/`Is`/`Open`/`Close` 중 무엇에 해당하는지 확인한다.
2. 나머지 명사 부분(`File`, `Process`, `Window`, `Thread` 등)으로 "무엇에 대한" 동작인지 파악한다.
3. 끝에 `A`/`W`/`Ex`가 붙어있으면 그건 인코딩/확장판 표시일 뿐이므로 핵심 의미와는 분리해서 생각한다.

## 단계별 절차
**1) 이름 분해**
예를 들어 `NtQueryInformationProcess`를 만났다고 하자.
- `Nt` — 네이티브 API(낮은 수준)
- `Query` — 조회(값을 얻어옴, `Get`과 비슷한 계열)
- `Information` — 정보
- `Process` — 프로세스 대상

이렇게 분해하면 "프로세스에 대한 어떤 정보를 조회하는 저수준 함수"라는 것을 이름만으로 알 수 있다. 실제로 이 함수는 디버거 부착 여부 확인(`ProcessDebugPort` 등 정보 클래스) 등 다양한 안티디버깅 용도로 쓰인다.

**2) IDA에서 시그니처 확인**
- 임포트 함수 위에서 더블클릭하거나 `Ctrl+마우스오버`로 툴팁을 보면, IDA가 알고 있는 표준 헤더 기반 함수 프로토타입(인자 개수, 타입, 반환형)이 표시되는 경우가 많다. 이는 이름 추측보다 훨씬 정확한 정보이므로 반드시 함께 확인한다.
- 인자 이름 자체가 힌트인 경우가 많다(`lpFileName`, `dwDesiredAccess`, `lpBuffer` 등 헝가리안 표기법 접두사도 타입을 암시한다: `lp`=포인터, `dw`=DWORD, `b`=BOOL, `h`=핸들, `sz`=null 종료 문자열).

**3) 오프라인 자료로 교차 확인**
- 인터넷이 안 되는 환경이라면, 이 지식베이스의 Windows API 관련 다른 글이나 로컬에 캐시된 문서를 우선 참고한다.
- 함수 이름 추측이 애매하면 REV-0139(CreateFile/ReadFile/WriteFile) 같은 구체적인 API별 글에서 정확한 인자 순서를 확인한다.

## 명령어/단축키
- IDA: 임포트 함수 이름 위에서 마우스 오버(툴팁으로 프로토타입 확인), `Y`(프로토타입 수동 지정), `Shift+F12`(문자열 검색으로 관련 문맥 파악)
- x64dbg: 함수에 브레이크포인트(`bp 함수이름`) 후 인자 레지스터/스택 값을 직접 확인해서 이름 추측이 맞는지 검증(자세한 절차는 REV-0139 참고)

## 출력 해석
- 이름 추측은 "가설"이지, 확정이 아니다. 반드시 실제 인자 값(문자열, 크기, 플래그)을 확인해서 가설이 맞는지 검증해야 한다.
- `A`/`W` 두 버전이 동시에 임포트되어 있다면, 프로그램 내부에서 문자열 인코딩을 상황에 따라 섞어 쓰고 있다는 뜻일 수 있으니 각각 어디서 쓰이는지 구분해서 본다.
- `Nt`/`Zw` 함수가 직접 호출되고 있다면 일반적인 Win32 API 경유 방식보다 탐지를 우회하려는 의도가 있는지 의심해볼 만하다.

## 흔한 실수
- 이름만 보고 100% 확신해서 실제 인자 확인을 생략하는 것. 같은 동사라도 문맥에 따라 뜻이 달라질 수 있다(예: `CreateEvent`의 `Event`는 UI 이벤트가 아니라 동기화 객체다).
- `A`와 `W`의 차이를 "그냥 이름이 다른 별개 함수"로 오해하는 것. 실제로는 인코딩만 다를 뿐 거의 동일한 기능이다.
- `Ex` 접미사가 붙은 함수를 완전히 다른 함수로 취급하는 것. 대개 원본 함수의 상위 호환 확장판이다.
- `Rtl*`, `Nt*`, `Zw*` 함수를 전부 "커널 함수라서 유저 모드에서는 못 본다"고 착각하는 것. 이들은 `ntdll.dll`에 있는 유저 모드 라이브러리 함수이며, 일반 프로그램에서도 직접 호출할 수 있다.

## 막혔을 때 다음 체크
- `CreateFile`/`ReadFile`/`WriteFile`처럼 파일 입출력 계열 함수의 정확한 인자 순서가 필요하면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적)를 확인한다.
- `Crypt*`/`BCrypt*` 접두사 함수를 만났다면 → REV-0140(Crypt API BCrypt API 흔적 찾기)으로 이동한다.
- CRT 함수 이름과 진짜 Win32 API 이름이 섞여서 헷갈린다면 → REV-0137(Visual C++ Runtime 함수가 많은 바이너리 정리법)을 참고한다.

## 미니 예제
임포트 목록에서 다음 세 함수를 봤다고 하자.

```text
IsDebuggerPresent
GetTickCount
VirtualProtect
```

- `IsDebuggerPresent` — `Is` 접두사이므로 참/거짓 질의. "디버거가 붙어있는가"를 묻는 함수임을 이름만으로 바로 알 수 있다(안티디버깅 단골 함수).
- `GetTickCount` — `Get` 접두사이므로 어떤 값을 조회. "시스템 부팅 이후 경과한 틱(ms) 수를 가져온다"는 뜻이며, 두 번 호출해서 차이를 재면 실행 시간을 측정할 수 있다(타이밍 기반 안티디버깅에 자주 쓰임).
- `VirtualProtect` — `Virtual` 접두사(가상 메모리 관리자 계열)에 `Protect`(보호 속성 변경)가 붙었으므로, "메모리 페이지의 접근 권한(읽기/쓰기/실행)을 바꾼다"는 뜻이다. 언패킹 코드에서 압축 해제된 코드를 실행 가능하게 만들 때 자주 등장한다.

이 세 함수가 한 함수 안에 같이 등장한다면, "실행 시간을 재서 느리면(디버거로 스텝 실행 중이면) 의심하고, 디버거 존재 여부도 직접 확인한 뒤, 메모리 보호 속성을 바꿔 뭔가를 실행 가능하게 만드는" 전형적인 안티디버깅+언패킹 조합일 가능성이 높다고 짐작할 수 있다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0140 — Crypt API BCrypt API 흔적 찾기

## 출처/검증
- Win32 API 네이밍 컨벤션(동사 접두사, `A`/`W`/`Ex` 접미사, 헝가리안 표기법)은 Microsoft Win32 API 공식 문서 및 스타일 가이드 기준이다.
- `Nt*`/`Zw*`/`Rtl*` 네이티브 API의 위치(`ntdll.dll`)와 Win32 API와의 관계는 Windows 내부 구조를 다루는 공식/준공식 문서(Windows Internals 계열 레퍼런스) 기준이다.
- `IsDebuggerPresent`, `GetTickCount`, `VirtualProtect` 등 개별 함수의 시그니처와 용도는 Microsoft 공식 API 문서 기준이다(2026-09-08 기준 서술).
