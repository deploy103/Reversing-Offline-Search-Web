---
id: REV-0121
title: "Entry Point와 WinMain 찾기"
slug: "rev-0121-entry-point-winmain"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["AddressOfEntryPoint", "WinMainCRTStartup", "mainCRTStartup", "WinMain", "wWinMain", "CRT startup", "Subsystem", "진입점 찾기"]
aliases: ["exe 진입점이란", "WinMain 찾는법", "main 어디서 시작하는지", "CRT startup이란", "엔트리포인트에서 main까지"]
symptom_keywords: ["엔트리포인트가 main이 아닌 이유를 모름", "WinMainCRTStartup이 뭔지 모름", "IDA start 함수 안이 낯설다", "WinMain 인자가 뭔지 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`OptionalHeader.AddressOfEntryPoint`가 가리키는 코드는 우리가 작성한 `main`/`WinMain`이 아니라 컴파일러가 자동으로 붙이는 **CRT(C Runtime) 시작 함수**(`mainCRTStartup` 또는 `WinMainCRTStartup`)이며, 이 함수가 힙·표준입출력·전역 객체 등을 초기화한 뒤에야 실제 사용자 코드인 `main`/`WinMain`을 호출한다.

## 언제 검색해야 하나
- IDA가 `start` 함수로 자동 이동시켰는데, 그 안의 코드가 우리가 작성한 로직과 전혀 다른 낯선 초기화 코드로 가득할 때
- `WinMainCRTStartup`, `mainCRTStartup`, `__scrt_common_main_seh` 같은 함수 이름이 콜스택이나 디스어셈블리에 보여서 이게 뭔지 궁금할 때
- `WinMain`의 정확한 매개변수(`HINSTANCE`, `HINSTANCE`, `LPSTR`, `int`) 각각이 어디서 오는지 궁금할 때
- 콘솔 프로그램(`main`)과 GUI 프로그램(`WinMain`)이 진입점부터 어떻게 다른 경로를 타는지 궁금할 때
- stripped 바이너리라서 함수 이름이 다 지워졌을 때, 진입점에서부터 실제 사용자 로직 함수까지 어떻게 따라가야 할지 모를 때

## 핵심 개념

### AddressOfEntryPoint가 가리키는 곳은 사용자 코드가 아니다
REV-0116에서 다뤘듯 `OptionalHeader.AddressOfEntryPoint`는 실행이 시작되는 지점을 RVA로 담고 있다. 하지만 이 지점은 **C/C++ 런타임 초기화 코드**의 시작점이지, 우리가 IDE에서 작성한 `int main()`이나 `int WinMain(...)`이 아니다. Windows 로더가 프로세스를 만들고 이 진입점으로 제어를 넘기면, 그 코드는 다음과 같은 준비 작업을 순서대로 처리한다.

- 힙, 스택 가드(`/GS`), 예외 처리(SEH) 인프라 초기화
- C 표준 라이브러리 전역 상태(예: `stdio` 버퍼) 초기화
- C++ 전역/정적 객체의 생성자 호출(C++ 프로그램인 경우)
- 명령줄 인자 파싱, 환경 변수 준비
- 마지막으로 사용자 `main`(또는 `WinMain`)을 호출하고, 그 반환값을 `ExitProcess`에 넘겨서 프로세스를 종료

이 전체 과정을 담당하는 코드를 통틀어 **CRT startup**이라 부른다.

### Subsystem에 따라 갈리는 두 경로
REV-0116에서 다룬 `OptionalHeader.Subsystem` 값에 따라 링커가 최종적으로 어떤 CRT startup 함수를 진입점으로 지정하는지가 갈린다.

```text
Subsystem == IMAGE_SUBSYSTEM_WINDOWS_CUI (3, 콘솔 프로그램)
   AddressOfEntryPoint → mainCRTStartup (또는 유니코드 진입인 wmainCRTStartup)
       └─ 내부에서 사용자 정의 main(int argc, char** argv, char** envp) 호출

Subsystem == IMAGE_SUBSYSTEM_WINDOWS_GUI (2, GUI 프로그램)
   AddressOfEntryPoint → WinMainCRTStartup (또는 wWinMainCRTStartup)
       └─ 내부에서 사용자 정의 WinMain(HINSTANCE, HINSTANCE, LPSTR, int) 호출
```

MSVC(Visual Studio)로 빌드한 실행 파일이라면 이 CRT startup 함수들은 최신 버전에서 내부적으로 `__scrt_common_main_seh`라는 공통 함수를 거쳐 사용자 진입 함수(`main`/`WinMain`)를 호출하는 구조로 되어 있다. 함수 이름이 디버그 심볼 없이도 보이는 경우가 있는데, 이는 Visual Studio가 배포하는 공개 PDB/심볼 서버 정보를 IDA/WinDbg가 자동으로 매칭해주기 때문이다(인터넷 연결이 있는 환경 기준. 이 위키를 쓰는 오프라인 환경에서는 이런 자동 심볼 매칭이 동작하지 않을 수 있으므로, 함수 이름이 안 보인다면 아래 "단계별 절차"의 패턴 인식 방법을 쓴다).

### WinMain의 네 매개변수
GUI 프로그램의 사용자 진입점 시그니처는 다음과 같다.
```c
int WINAPI WinMain(
    HINSTANCE hInstance,      // 이 프로세스(모듈)의 인스턴스 핸들, 보통 ImageBase와 같은 값
    HINSTANCE hPrevInstance,  // 항상 NULL (16비트 Windows의 유물, 현재는 의미 없음)
    LPSTR     lpCmdLine,      // 명령줄 인자 문자열 (프로그램 이름 제외)
    int       nCmdShow        // 창을 어떻게 보여줄지 힌트 (SW_SHOW 등)
);
```
`hInstance`는 실무적으로 매우 중요한데, 이 값이 대개 이 실행 파일의 `ImageBase`와 동일하다 — 즉 `LoadLibrary`나 리소스 API 호출에 이 핸들이 그대로 쓰인다. `hPrevInstance`는 사실상 죽은 매개변수로 항상 `NULL`이 전달된다(과거 16비트 Windows에서 같은 프로그램이 이미 실행 중인지 확인하는 용도였으나 32비트 이후로는 무의미해졌다).

### 콘솔 프로그램의 main
```c
int main(int argc, char** argv, char** envp);
```
Linux ELF의 `main`과 시그니처는 비슷하지만, 이 인자들이 실제로 준비되는 경로는 완전히 다르다. Linux는 `_start` → `__libc_start_main`이 커널이 스택에 이미 얹어둔 `argc`/`argv`/`envp`를 그대로 전달하는 구조인 반면(ELF 쪽은 이 위키의 대응 글에서 다룬다), Windows는 CRT startup 코드가 `GetCommandLineA/W()`로 전체 명령줄 문자열을 가져온 뒤, 자체 파싱 로직으로 공백/따옴표를 처리해 `argv` 배열을 직접 만들어낸다. 그래서 Windows에서는 커맨드라인 인자 파싱 버그(따옴표 처리 등)가 프로그램마다 미묘하게 다르게 나타날 수 있다.

### stripped 바이너리에서 진입점→main을 찾는 실전 패턴
디버그 정보가 없어서 함수 이름이 자동으로 안 붙는 경우, 다음 패턴을 기억해두면 빠르게 찾을 수 있다.
1. `AddressOfEntryPoint`로 이동하면 처음 보이는 함수가 CRT startup이다. 이 함수는 대개 상당히 길고, `GetStartupInfo`, `HeapCreate` 계열 API를 호출하는 게 특징이다.
2. 이 함수 끝부분(또는 중간의 특정 분기) 근처에서, **인자를 거의 받지 않거나 표준 시그니처(`argc, argv, envp` 또는 `HINSTANCE, HINSTANCE, LPSTR, int`)에 맞는 개수의 인자로 호출되는 CALL**을 찾는다. 이게 바로 사용자 `main`/`WinMain`으로 가는 호출이다.
3. Subsystem이 GUI(2)인데 그 함수 안에서 곧바로 `CreateWindow`, `RegisterClass`, 메시지 루프(`GetMessage`/`DispatchMessage`)가 나온다면 `WinMain`을 제대로 찾은 것이다. 콘솔 프로그램이라면 표준입출력 관련 호출(`printf`, `scanf` 등)이나 실제 문제 로직이 여기서부터 시작된다.
4. IDA는 이 CRT startup 패턴을 FLIRT 시그니처로 자동 인식해서 `main`/`WinMain`에 자동으로 이름을 붙여주는 경우가 많다 — 이름이 이미 보인다면 이 수동 추적 과정을 생략해도 된다.

## 화면/코드에서 보이는 징후
- IDA가 파일을 열자마자 자동으로 이동시키는 `start` 함수 안에 `GetStartupInfoW`, `HeapSetInformation`, `__security_init_cookie` 같은 낯선 함수 호출들이 보임
- x64dbg에서 프로그램을 실행(F9) 없이 처음 멈춘 위치가 `mainCRTStartup` 또는 `WinMainCRTStartup` 근처 코드
- IDA Functions 창에 `main`이라는 이름이 아예 없고, `entry`, `start`, `sub_140001000` 같은 이름만 보임(stripped 바이너리)
- `WinMain`을 찾았다면 그 함수 안에서 `RegisterClassEx`, `CreateWindowEx`, `ShowWindow`, `GetMessage` 순서의 전형적인 Win32 GUI 초기화 패턴이 보임

## 가장 먼저 할 것
IDA에서 파일을 열면 자동으로 이동하는 위치가 곧 `AddressOfEntryPoint`다. 이 함수를 CRT startup으로 인식하고, 이름이 이미 `main`/`WinMain`으로 자동 붙어 있는지 Functions 창(`Ctrl+F` 또는 좌측 함수 목록 검색)에서 먼저 확인한다. 이름이 붙어 있다면 바로 더블클릭해서 이동하면 되고, 안 붙어 있다면 진입점 함수 내부를 훑으며 "인자 개수가 4개(WinMain) 또는 3개(main) 정도이고, 그 이후로 실제 프로그램 로직처럼 보이는 코드로 이어지는 CALL"을 찾는다.

## 단계별 절차

**1) Subsystem 먼저 확인 (REV-0116 참고)**
`OptionalHeader.Subsystem`이 `2`(GUI)인지 `3`(CUI/콘솔)인지에 따라 `WinMain`을 찾을지 `main`을 찾을지 미리 방향을 정한다.

**2) IDA로 AddressOfEntryPoint 코드 확인**
파일을 열면 자동으로 이 위치로 이동한다. 함수 이름이 `mainCRTStartup`/`WinMainCRTStartup`처럼 자동 인식되어 있는지 확인한다.

**3) CRT startup 내부에서 사용자 진입 함수로의 CALL 찾기**
함수 본문을 따라 내려가며, 표준 시그니처에 맞는 인자 개수로 호출되는 지점을 찾는다. 최신 MSVC 빌드에서는 `__scrt_common_main_seh` 같은 중간 함수를 한 단계 더 거칠 수 있다.

**4) x64dbg로 실제 실행하며 확인(동적 검증)**
```text
x64dbg로 실행 → 진입점에서 자동 정지
F8(Step Over)로 CRT 초기화 코드를 건너뛰며 진행
main/WinMain으로 보이는 CALL에서 F7(Step Into)로 들어가서 확인
```

**5) WinMain을 찾았다면 인자 확인**
```text
64비트: RCX=hInstance, RDX=hPrevInstance(항상 0), R8=lpCmdLine, R9=nCmdShow
```
(레지스터 인자 전달 규칙 자체는 REV-0122에서 자세히 다룬다.)

## 명령어/단축키
```text
IDA: 파일 열면 자동으로 entry point로 이동. Functions 창(단축키: Functions list)에서 "main" 검색
IDA: Edit → Function → Rename(단축키 N)으로 수동으로 이름 붙이기
x64dbg: F9(Run to entry, 기본 설정에 따라 다름), F8(Step Over), F7(Step Into)
```

## 출력 해석
- CRT startup 함수 안에서 `HeapCreate`, `GetStartupInfo`, `SetUnhandledExceptionFilter` 같은 호출이 여러 번 보이면 아직 CRT 초기화 단계이고, 사용자 코드는 더 아래쪽에 있다.
- 함수 인자가 정확히 4개이고 그중 두 번째 인자가 상수 `0`으로 고정되어 있으면(`hPrevInstance`는 항상 `NULL`) `WinMain` 호출일 가능성이 매우 높다.
- 그 함수 진입 직후 `RegisterClassEx`/`CreateWindowEx`가 보이면 GUI 애플리케이션의 진짜 `WinMain`을 찾은 것이 확실하다.
- 콘솔 프로그램에서 `main`으로 추정되는 함수에 들어갔는데 파일 입출력이나 특정 알고리즘 로직이 바로 보이면 CTF/wargame 문제에서 찾던 "진짜 로직"에 도달한 것이다.

## 흔한 실수
- `AddressOfEntryPoint`가 가리키는 함수를 `main`이라고 착각하고 그 안의 CRT 초기화 코드를 애써 분석하는 것 — 이 코드는 거의 항상 컴파일러가 자동 생성한 정형화된 코드이므로, CTF 문제의 답은 대개 여기 없다.
- GUI 프로그램인데 `main`을 찾으려고 헤매는 것 — `Subsystem == 2`(GUI)라면 사용자 진입점은 `WinMain`이지 `main`이 아니다(단, 최신 MSVC는 `Subsystem`과 무관하게 소스에서 `main`을 쓰는 것도 허용하므로 100% 규칙은 아니지만, 링커가 생성하는 CRT startup 이름 자체는 Subsystem 값을 따른다).
- `hPrevInstance`가 항상 `NULL`이라는 걸 모르고 이 값을 실제로 의미 있는 값으로 취급해 분석 시간을 쓰는 것.
- Windows의 `argv` 파싱이 Linux의 커널 제공 방식과 동일하다고 착각하는 것 — Windows는 CRT가 `GetCommandLineA/W`로 가져온 전체 문자열을 자체 규칙(따옴표, 이스케이프)으로 직접 파싱해서 `argv`를 만든다.
- 오프라인 환경에서 Microsoft 심볼 서버에 연결되지 않아 `mainCRTStartup` 등의 이름이 자동으로 안 붙는데, 이걸 "분석이 잘못됐다"고 오해하는 것 — 이럴 때는 이름이 안 보여도 이 글의 패턴 인식 방법으로 수동으로 찾으면 된다.

## 막혔을 때 다음 체크
- `AddressOfEntryPoint`, `Subsystem` 필드 자체가 정의된 위치가 헷갈리면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- `main`/`WinMain`으로 들어가는 CALL의 인자가 레지스터 어디에 있는지 정확히 알고 싶으면 → [REV-0122 Microsoft x64 Calling Convention](./rev-0122-ms-x64-calling-convention.md)
- 함수를 아예 못 찾겠고 이름이 하나도 없는 극단적인 stripped 상황이면 → [main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)
- Import Table을 먼저 훑어서 이 프로그램이 GUI인지 콘솔인지 함수 목록으로 짐작하고 싶으면 → [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- Linux ELF의 대응 개념(`_start`, `__libc_start_main`)과 비교하고 싶으면 → [ELF 헤더 읽는 법](../linux-elf/rev-0089-elf-header.md)

## 미니 예제
콘솔 프로그램 하나를 IDA로 열었더니 진입점 함수가 자동으로 `mainCRTStartup`이라는 이름으로 인식됐다고 하자.

```asm
mainCRTStartup:
    sub  rsp, 0x28
    call __security_init_cookie
    call GetStartupInfoW    ; 콘솔 표준 핸들 정보 등 준비
    ...
    lea  rcx, [환경변수 포인터]      ; envp
    lea  rdx, [argv 배열 포인터]     ; argv
    mov  ecx, [argc 값]              ; 실제로는 순서가 최적화에 따라 달라질 수 있음
    call main                        ; ★ 여기서 사용자 main으로 진입
    mov  ecx, eax                    ; main의 반환값을 받아
    call exit                        ; ExitProcess 경로로 프로세스 종료
```

`call main` 지점에서 `F7`(Step Into)로 들어가면 비로소 우리가 소스코드에서 작성한(또는 CTF 문제가 숨겨둔) 실제 로직이 시작된다. 여기까지 오는 동안의 `__security_init_cookie`, `GetStartupInfoW` 같은 호출들은 전부 CRT가 자동으로 붙인 정형화된 초기화 코드이므로 분석 우선순위에서 낮게 둬도 된다.

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0122 — Microsoft x64 Calling Convention
- REV-0114 — PE 파일 구조 한 번에 보기
- REV-0009 — main 함수가 안 보일 때 찾는 방법

## 출처/검증
- `AddressOfEntryPoint`와 `Subsystem`에 따른 CRT startup 함수 선택(`mainCRTStartup`/`WinMainCRTStartup`): Microsoft Learn "PE Format" 문서 및 Microsoft C Runtime(CRT) 소스/문서 기준 (2026-09-08 검증).
- `WinMain` 함수 시그니처 및 매개변수 의미: Microsoft Learn Win32 API `WinMain` 함수 공식 문서 기준.
- Windows 커맨드라인 인자 파싱이 CRT 자체 로직으로 이뤄진다는 설명: Microsoft Learn "Parsing C Command-Line Arguments" 문서 기준.
