---
id: REV-0135
title: "DLL 문제 분석 시작하기"
slug: "rev-0135-dll-analysis-start"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, "PE-bear"]
keywords: ["DLL", "DllMain", "Export Directory", "LoadLibrary", "rundll32", "regsvr32", "익스포트 함수"]
aliases: ["DLL 분석 시작", "DLL은 어떻게 실행시키나", "DllMain이 뭔가", "익스포트 함수 확인"]
symptom_keywords: ["문제 파일이 exe가 아니라 dll이다", "더블클릭해도 아무 일도 안 일어난다", "DLL을 어떻게 실행시켜야 할지 모르겠다", "익스포트된 함수 이름만 있고 뭘 하는지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
DLL은 더블클릭해서 실행되는 파일이 아니라 다른 프로그램이 불러써야 동작하는 "부품"이기 때문에, DLL 문제를 처음 받으면 우선 익스포트된 함수 목록과 `DllMain`부터 확인하고, `rundll32`나 로더 스텁을 이용해 강제로 코드를 실행시켜야 분석을 시작할 수 있다.

## 언제 검색해야 하나
- CTF나 과제로 받은 파일 확장자가 `.exe`가 아니라 `.dll`일 때
- 더블클릭했더니 아무 창도 안 뜨고 아무 반응이 없어서 당황스러울 때
- IDA/x64dbg에 DLL을 어떻게 불러와야 실행이 되는지 모를 때
- "이 DLL이 익스포트하는 함수가 몇 개나 되는지, 이름이 뭔지" 확인해야 할 때
- 서비스나 다른 프로세스에 인젝션되는 DLL(악성코드 분석 맥락)을 분석해야 할 때

## 핵심 개념
DLL(Dynamic Link Library)은 EXE와 같은 PE 포맷을 쓰지만, PE 헤더의 `Characteristics` 필드에 `IMAGE_FILE_DLL` 플래그가 켜져 있다는 점이 다르다. 이 플래그 때문에 Windows 로더는 이 파일을 "직접 실행할 프로그램"이 아니라 "다른 프로세스의 주소 공간에 매핑해서 함수 호출을 받는 라이브러리"로 취급한다.

DLL에는 다음 두 가지 핵심 개념이 있다.

**1) `DllMain`**: EXE의 진입점(`main`/`WinMain`)에 대응하는 것이 DLL의 `DllMain`이다. 시그니처는 다음과 같다.

```c
BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved);
```

`fdwReason`(호출 이유)이 핵심인데, 다음 네 가지 값 중 하나로 호출된다.

- `DLL_PROCESS_ATTACH`(1): 이 DLL이 어떤 프로세스에 처음 로드될 때(가장 중요, 초기화 로직이 대부분 여기)
- `DLL_THREAD_ATTACH`(2): 프로세스 안에서 새 스레드가 생성될 때
- `DLL_THREAD_DETACH`(3): 스레드가 종료될 때
- `DLL_PROCESS_DETACH`(0): DLL이 언로드되거나 프로세스가 종료될 때(정리/해제 로직)

즉 DLL을 분석할 때 "이상한 동작이 프로세스 로드 시점에 자동으로 일어난다"면 대부분 `DllMain`의 `DLL_PROCESS_ATTACH` 분기를 봐야 한다.

**2) 익스포트 함수(Export)**: DLL이 외부(다른 EXE나 DLL)에서 호출할 수 있도록 공개한 함수들이다. PE의 익스포트 디렉터리(`IMAGE_EXPORT_DIRECTORY`)에 함수 이름과 RVA(상대 주소), 그리고 서수(ordinal, 이름 없이 번호로만 호출 가능한 경우도 있음)가 정리되어 있다. `.NET`이 아닌 네이티브 DLL 분석에서는 이 익스포트 함수 하나하나가 사실상 "이 DLL이 제공하는 API 목록"이므로, 함수 이름만 봐도 대략 무슨 기능인지 짐작할 수 있는 경우가 많다(이름 추측법은 REV-0138 참고).

DLL은 또한 EXE와 마찬가지로 TLS 콜백(REV-0133 참고)을 가질 수 있으며, 이 경우 `DllMain`보다도 먼저 실행된다는 점을 함께 기억해야 한다.

## 화면/코드에서 보이는 징후
- 파일을 `file` 명령이나 PE-bear로 열었을 때 `Characteristics`에 `DLL` 플래그가 켜져 있음
- IDA로 열면 자동으로 진입점이 `DllMain` 형태의 함수로 인식되고, `Exports` 탭(`Ctrl+E` 또는 화면 하단 탭)에 함수 목록이 나열됨
- 더블클릭하면 "이 앱을 실행할 수 없습니다" 또는 아무 반응 없이 종료됨(정상적인 현상, DLL은 단독 실행 대상이 아니기 때문)
- 파일명이 `mscoree.dll`, `bcrypt.dll` 등 익숙한 시스템 DLL 이름을 사칭한 경우(악성코드에서 흔함)

## 가장 먼저 할 것
1. PE-bear나 IDA로 열어 **아키텍처(x86/x64)**부터 확인한다. DLL은 이를 로드하는 프로세스와 반드시 같은 비트수여야 하므로, 32비트 DLL은 32비트 x64dbg(x32dbg)로, 64비트 DLL은 64비트 x64dbg로 열어야 한다.
2. **Exports 탭**에서 익스포트된 함수 이름 목록을 확인한다. 이름이 있으면(`DllRegisterServer`, `Run`, `Init` 등) 그 자체가 강력한 힌트가 된다. 이름이 없고 서수만 있다면 좀 더 파고들 준비를 한다.
3. TLS 디렉터리가 있는지 확인한다(REV-0133). 있다면 `DllMain`보다 먼저 실행되는 코드가 있다는 뜻이다.

## 단계별 절차
**1) 정적으로 구조 파악(PE-bear/IDA)**
- PE-bear의 `Export Directory` 탭에서 함수 이름, RVA, ordinal을 한눈에 확인한다.
- IDA로 파일을 직접 열면(IDA는 DLL도 EXE처럼 로드해서 분석 가능) 진입점이 `DllMain`으로 자동 인식되는지 확인하고, 안 되어 있으면 `Entry point` 위치로 이동(`Ctrl+E`에서 첫 항목 더블클릭)해서 직접 확인한다.

**2) 강제로 실행시키기**
DLL은 그 자체로 실행 파일이 아니므로, 코드를 실제로 돌려보려면 다음 방법 중 하나를 쓴다.

- **`rundll32.exe`로 특정 익스포트 함수 호출**:
```text
rundll32.exe 대상.dll,익스포트함수이름 [인자]
```
예: `rundll32.exe sample.dll,Run`
- **COM DLL이면 `regsvr32`로 등록**: `DllRegisterServer`를 익스포트하는 DLL(주로 ActiveX/COM 컴포넌트)은 `regsvr32 대상.dll`로 등록하면서 `DllRegisterServer`가 실행된다. 다만 관리자 권한과 실제 레지스트리 변경이 동반되므로, 분석용 가상 환경(스냅샷 있는 VM)에서만 실행할 것.
- **직접 로더 스텁 작성**: Python(`ctypes.WinDLL("대상.dll")`)이나 간단한 C 프로그램으로 `LoadLibrary` + `GetProcAddress` + 함수 호출을 직접 작성해서 원하는 인자로 원하는 함수만 정확히 실행시킬 수 있다. CTF에서는 이 방법이 가장 유연하다.

**3) 디버거로 붙이기**
- x64dbg에서 `File → Open`으로 DLL을 직접 열면, x64dbg가 내부적으로 로더 스텁(`x64dbg`가 제공하는 더미 호스트 프로세스)을 이용해 DLL을 로드하고 `DllMain`에서 멈춰준다.
- 이미 실행 중인 프로세스에 로드된 DLL을 분석하려면 `File → Attach`로 해당 프로세스에 붙은 뒤, `Symbols` 탭에서 대상 DLL의 모듈을 찾아 원하는 함수에 브레이크포인트를 건다.

## 명령어/단축키
- `rundll32.exe 파일.dll,함수이름` — 특정 익스포트 함수 직접 실행
- `regsvr32 파일.dll` — COM DLL 등록(`DllRegisterServer` 실행), 등록 해제는 `regsvr32 /u 파일.dll`
- x64dbg: `File → Open`(DLL 직접 로드), `File → Attach`(실행 중 프로세스에 붙기), `Ctrl+E`(익스포트/진입점 확인, IDA 기준)
- Python: `python -c "import ctypes; ctypes.WinDLL(r'대상.dll').함수이름()"` 형태로 간단히 테스트 가능

## 출력 해석
- `rundll32.exe`로 실행했는데 아무 일도 안 일어나면, 함수 시그니처가 `rundll32`가 기대하는 형태(`void CALLBACK 함수이름(HWND, HINSTANCE, LPSTR, int)`)와 다를 수 있다. 이 경우 직접 로더 스텁을 작성하는 편이 확실하다.
- IDA Exports 탭에 함수 이름 대신 `Ordinal1`, `Ordinal2`처럼만 나온다면, 이름이 익스포트되지 않고 서수로만 공개된 것이다. `GetProcAddress`를 서수로 호출해야 하며(`MAKEINTRESOURCE(서수)`), 이름만으로 기능을 짐작할 단서가 사라지므로 코드를 더 깊이 봐야 한다.
- `DllMain`의 `fdwReason` 분기에서 `DLL_PROCESS_ATTACH`(값 1) 조건만 처리하고 나머지는 그냥 `return TRUE`라면, 이 DLL의 핵심 로직은 프로세스 로드 시점에 자동으로 실행된다는 뜻이다.

## 흔한 실수
- 32비트 DLL을 64비트 x64dbg로 열려고 시도하는 것. 반드시 x32dbg를 써야 한다.
- TLS 콜백의 존재를 잊고 `DllMain`만 보고 "여기가 시작점"이라고 단정하는 것(REV-0133 참고).
- `rundll32`로 익스포트 함수를 호출했는데 시그니처가 안 맞아서 크래시가 나는 것을 "이 DLL이 이상하다"고 오해하는 것. `rundll32`가 기대하는 콜백 시그니처를 지키지 않으면 정상 DLL도 크래시가 날 수 있다.
- 익스포트 함수 이름이 없다고(서수만 있다고) 분석을 포기하는 것. 함수 크기, 호출되는 API, 문자열 참조 등 다른 단서로 여전히 기능을 유추할 수 있다.

## 막혔을 때 다음 체크
- 이 DLL이 `.NET`으로 만들어진 것 같다면(익스포트가 거의 없고 `mscoree.dll` 관련 임포트만 보임) → REV-0136(.NET EXE인지 Native EXE인지 구분)을 먼저 확인한다.
- 임포트/익스포트 함수 이름이 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- CRT 관련 함수가 너무 많아 실제 로직을 못 찾겠다면 → REV-0137(Visual C++ Runtime 함수가 많은 바이너리 정리법)을 참고한다.

## 미니 예제
`sample.dll`을 PE-bear로 열어 Export Directory를 확인했더니 다음과 같은 함수가 하나 있었다고 하자.

```text
Name: Decode
RVA: 0x1050
Ordinal: 1
```

이 경우 다음처럼 강제로 실행시켜 볼 수 있다.

```text
rundll32.exe sample.dll,Decode
```

만약 `Decode`가 `rundll32`가 기대하는 4개 인자 콜백 시그니처가 아니라 별도의 인자(예: 문자열 하나)를 받는 함수라면, 대신 Python으로 직접 호출한다.

```python
import ctypes
dll = ctypes.WinDLL(r"C:\path\sample.dll")
dll.Decode(b"test_input")
```

이렇게 강제로 함수를 실행시킨 뒤 x64dbg를 프로세스에 `Attach`해서 `Decode` 함수 시작 주소에 브레이크포인트를 걸면, 실제 동작을 동적으로 관찰할 수 있다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- DLL의 `IMAGE_FILE_DLL` 플래그, `DllMain` 시그니처와 `fdwReason` 값(`DLL_PROCESS_ATTACH` 등)은 Microsoft PE/COFF 및 Win32 DLL 공식 문서 기준이다.
- 익스포트 디렉터리(`IMAGE_EXPORT_DIRECTORY`) 구조는 Microsoft PE/COFF 형식 공식 문서 기준이다.
- `rundll32.exe`/`regsvr32.exe` 사용법은 Microsoft 공식 도구 문서 기준이며, 분석 시 격리된 VM 환경 사용을 권장한다(2026-09-08 기준 서술).
