---
id: REV-0127
title: "x64dbg로 EXE 첫 분석 시작"
slug: "rev-0127-x64dbg-first-analysis"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg 사용법", "x64dbg 첫 실행", "System Breakpoint", "TLS Callback", "x64dbg entry point", "x64dbg Symbols", "x64dbg Memory Map", "x64dbg Log", "x64dbg 초기 화면"]
aliases: ["x64dbg 처음 사용법", "엑스64디버그", "x32dbg", "x64dbg 시작하기", "x64dbg 첫 분석"]
symptom_keywords: ["x64dbg 열자마자 뭐부터 해야 할지 모르겠음", "x64dbg 실행하니까 ntdll에서 멈춤", "x64dbg 첫 브레이크포인트가 어딘지 모르겠음", "x64dbg에서 main 어떻게 찾음", "x64dbg TLS callback이 뭔지 모르겠음", "x64dbg System Breakpoint 뭔지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg로 EXE를 열면 실제 프로그램 코드가 시작되기 전, 운영체제/런타임이 먼저 실행하는 **System Breakpoint(ntdll 초기화 지점)**에서 자동으로 한 번 멈추는데, 여기서 곧바로 F9(Run)를 눌러 진짜 진입점(entry point)까지 이동한 뒤 Symbols·Memory Map·Log 창을 순서대로 확인하는 것이 표준적인 초반 루틴이다.

## 언제 검색해야 하나
- x64dbg를 처음 설치하고 파일을 열었는데 알 수 없는 위치(`ntdll.dll` 어딘가)에서 멈춰서 당황스러울 때
- "System Breakpoint"라는 표시가 뜨는데 이게 뭔지, 왜 프로그램 코드가 아닌 곳에서 멈추는지 궁금할 때
- 실제 작성한 `main`/`WinMain` 함수까지 어떻게 이동해야 하는지 모를 때
- x64dbg 창에 있는 여러 탭(CPU, Log, Symbols, Memory Map 등) 중 뭐부터 봐야 할지 감이 안 잡힐 때
- IDA로 정적 분석은 어느 정도 해봤지만, 실제로 실행시키면서 값을 확인하는 동적 분석은 처음 시작해볼 때

## 핵심 개념

### x64dbg가 뭐고 왜 쓰나
x64dbg(32비트 파일용은 x32dbg, 같은 설치 패키지에 함께 들어있다)는 Windows용 오픈소스 사용자 모드(user-mode) 디버거다. IDA/Ghidra가 "코드를 읽으면서" 분석하는 정적 분석 툴이라면, x64dbg는 프로그램을 실제로 한 줄씩 실행시키면서 그 순간의 레지스터·메모리·스택 값을 직접 눈으로 확인하는 동적 분석 툴이다. "이 조건 분기가 왜 여기로 빠지는지 코드만 봐서는 헷갈릴 때", "입력값이 실제로 어떻게 변환되는지 값으로 확인하고 싶을 때" 결정적으로 유용하다.

### Windows 프로세스가 시작되는 순서
EXE 파일을 더블클릭했을 때 실제로 벌어지는 일은 여러 단계로 나뉜다.

1. **프로세스 생성** — Windows 커널이 새 프로세스를 만들고, PE 헤더를 읽어 이미지를 메모리에 매핑한다.
2. **ntdll.dll 초기화** — 모든 Windows 프로세스는 사용자 모드 코드가 실행되기 전 `ntdll.dll`의 프로세스 초기화 루틴을 거친다. 이 루틴이 로더(loader)를 동작시켜 필요한 DLL들(`kernel32.dll`, `user32.dll` 등)을 로드하고 Import Table을 해석해 함수 주소를 채워 넣는다.
3. **TLS 콜백(TLS Callback)** — PE에 TLS(Thread Local Storage) 디렉토리가 있고 콜백 함수가 등록되어 있다면, `main`/`WinMain`보다 **먼저** 이 콜백이 실행된다. 일부 안티디버깅/패킹 기법은 이 지점을 악용해서 디버거가 진짜 엔트리 포인트에 도달하기 전에 먼저 검사를 수행한다.
4. **엔트리 포인트(Entry Point) 실행** — PE Optional Header의 `AddressOfEntryPoint`가 가리키는 코드가 실행된다. 이는 대개 사람이 작성한 `main`이 아니라 컴파일러/CRT가 자동으로 붙인 시작 함수(`__scrt_common_main` 계열 등)이며, 이 코드가 전역 변수 초기화, C 런타임 셋업 등을 마친 뒤 최종적으로 실제 `main`/`WinMain`을 호출한다.

x64dbg는 기본 설정에서 이 흐름 중 **2번(ntdll 초기화)** 시점에 자동으로 멈추도록 되어 있는데, 이를 **System Breakpoint**라고 부른다.

### System Breakpoint에서 멈추는 이유
디버거가 프로세스를 생성하자마자 곧바로 사용자 코드까지 실행시켜버리면, 로더가 DLL을 로드하는 과정이나 초반 조작(예: 언패킹 스텁, 안티디버깅 체크)을 놓칠 수 있다. 그래서 Windows 디버깅 API 자체가 "로더 초기화가 어느 정도 끝난 시점"에 한 번 멈추도록 설계되어 있고, x64dbg는 이 지점을 그대로 보여준다. 이 시점의 코드는 `ntdll.dll` 내부이며, **사용자가 작성한 프로그램 코드가 아니다.** 여기서 바로 F8/F7로 한 줄씩 실행하면 낯선 시스템 코드만 보게 되므로 초보자는 대개 혼란스러워한다.

### 진짜 엔트리 포인트까지 가는 방법
가장 간단한 방법은 System Breakpoint에서 **F9(Run)를 한 번 더 누르는 것**이다. x64dbg는 기본 옵션(`Options → Preferences → Events`)에서 "System Breakpoint"와 "Entry breakpoint"(모듈 진입점 도달 시 자동 정지)를 모두 활성화해두는 경우가 많아서, System Breakpoint 이후 F9를 누르면 곧바로 PE의 `AddressOfEntryPoint`, 즉 실제 프로그램 이미지의 시작 코드에서 다시 멈춘다. 이 옵션이 꺼져 있다면 프로그램이 그냥 끝까지 실행되어버릴 수 있으니, 처음 설정할 때 `Options → Preferences → Events` 탭에서 "Entry breakpoint" 체크박스가 켜져 있는지 확인해두면 편하다.

### main/WinMain까지 더 들어가기
엔트리 포인트에 도달해도 그 코드는 사람이 짠 `main`이 아니라 CRT 시작 함수다. 여기서부터 `main`/`WinMain`까지 가려면:
- 코드를 눈으로 따라 읽으면서 CRT 초기화 호출들(`security_init_cookie`, `_initterm` 등, 함수 이름이 심볼로 안 보이면 `sub_XXXXXX` 형태) 이후에 나오는, 인자를 3~4개 세팅하고 부르는 **마지막 큰 `call`**을 찾는다. 대개 이 마지막 call이 `main`/`WinMain`이다.
- 또는 Step Over(F8)로 각 `call`을 하나씩 건너뛰면서, 짧게 끝나는 함수(CRT 내부 셋업)들을 지나 상대적으로 규모가 커 보이는 함수로 Step Into(F7)한다.
- IDA로 미리 정적 분석을 해서 `main`의 주소를 알아낸 뒤, x64dbg에서 그 주소에 직접 브레이크포인트(`bp <주소>`)를 걸고 F9로 한 번에 이동하는 것이 실전에서 가장 빠르다.

## 화면/코드에서 보이는 징후
- 파일을 열자마자(File → Open File) 상태 바나 타이틀에 "System Breakpoint" 문구가 표시되고, 디스어셈블리 창의 현재 위치가 `ntdll.dll` 모듈 내부 어딘가로 되어 있다.
- CPU 탭 오른쪽 위 Registers 패널에 `RIP`(64비트 기준) 값이 `ntdll.xxxxxxxx` 형태로 표시된다.
- TLS 콜백이 있는 바이너리라면 System Breakpoint 이후 F9를 눌렀을 때 `AddressOfEntryPoint`보다 먼저 다른 위치(TLS 콜백 함수)에서 한 번 더 멈출 수 있다.
- 진짜 엔트리 포인트에 도달하면 현재 모듈 이름이 `ntdll`이 아니라 실행 파일 자신의 이름(예: `sample.exe`)으로 바뀐다.
- 하단 Log 창에 "DLL Loaded", "Entry breakpoint" 같은 이벤트 로그가 순서대로 쌓인다.

## 가장 먼저 할 것
파일을 연 직후 System Breakpoint에서 멈춘 화면을 보면, 아무 코드도 살펴보지 말고 곧바로 **F9(Run)를 눌러 실제 엔트리 포인트까지 이동**한다. 그 다음에야 디스어셈블리를 읽기 시작하는 것이 순서다. 이 단계를 건너뛰고 System Breakpoint 위치에서 바로 분석을 시작하면 `ntdll.dll`의 로더 코드를 사용자 프로그램 코드로 착각해 시간을 낭비하게 된다.

## 단계별 절차

**1) 파일 열기**

`File → Open File...`(또는 `Ctrl+O`)로 exe를 선택한다. 32비트 exe는 x32dbg로, 64비트 exe는 x64dbg로 열어야 하므로, 확실하지 않다면 먼저 Detect It Easy(REV-0126)나 PE-bear(REV-0125)로 아키텍처를 확인해두면 실수를 줄일 수 있다.

**2) System Breakpoint 확인 및 통과**

파일이 로드되면 자동으로 `ntdll.dll` 어딘가의 System Breakpoint에서 멈춘다. 이 상태에서 **F9**를 눌러 계속 실행한다.

**3) Entry breakpoint 옵션 확인(최초 1회)**

만약 F9를 눌렀는데 프로그램이 곧바로 끝까지 실행되어버리고 진짜 엔트리 포인트에서 안 멈춘다면, `Options → Preferences → Events` 탭에서 "System Breakpoint"와 "Entry breakpoint" 체크박스가 켜져 있는지 확인하고 다시 시도한다.

**4) 엔트리 포인트에서 코드 확인**

이제 현재 모듈이 `ntdll`이 아니라 대상 exe 자신으로 바뀐 것을 Registers 패널의 `RIP`/`EIP` 값 옆 모듈명으로 확인한다. 이 지점이 PE Optional Header의 `AddressOfEntryPoint`다.

**5) main/WinMain으로 더 들어가기**

Step Over(F8)로 CRT 초기화 call들을 건너뛰면서 코드를 따라가거나, 미리 IDA에서 확인해둔 `main` 주소에 `bp <주소>` 명령으로 브레이크포인트를 걸고 F9로 바로 이동한다.

**6) Symbols 창 확인**

`View → Symbols`(또는 `Alt+E`)를 눌러 현재 로드된 모듈들과 각 모듈이 export하는 함수 심볼 목록을 확인한다. 특정 API(`IsDebuggerPresent`, `CreateFileW` 등) 이름을 검색해서 그 주소에 바로 브레이크포인트를 걸 수도 있다.

**7) Memory Map 창 확인**

`View → Memory Map`(또는 `Alt+M`)을 눌러 프로세스에 매핑된 모든 메모리 영역(이미지 자신, 로드된 DLL들, 힙, 스택 등)과 각 영역의 권한(R/W/E)을 확인한다. 실행 가능하면서 쓰기도 가능한 의심스러운 영역이 있는지 여기서 눈여겨본다.

**8) Log 창 확인**

`View → Log`(또는 `Alt+L`)를 눌러 지금까지 발생한 이벤트(모듈 로드/언로드, 브레이크포인트 히트, 예외 발생 등)를 시간 순서로 확인한다. 뭔가 예상과 다르게 동작했을 때 가장 먼저 봐야 할 창이다.

## 명령어/단축키
- `Ctrl+O` : 파일 열기
- `F9` : Run(다음 브레이크포인트/이벤트까지 실행)
- `F8` : Step Over(현재 줄 실행, `call`은 통째로 건너뜀)
- `F7` : Step Into(현재 줄 실행, `call`이면 그 함수 내부로 들어감)
- `F2` : 현재 커서 위치에 브레이크포인트 설정/해제 토글
- `bp <주소 또는 함수명>` : 커맨드바에서 브레이크포인트 설정(예: `bp main`, `bp IsDebuggerPresent`)
- `Alt+E` : Symbols 창
- `Alt+M` : Memory Map 창
- `Alt+L` : Log 창
- `Ctrl+F2` : 프로세스 재시작(처음부터 다시 실행)
- `Ctrl+F9` : Execute till return(현재 함수가 끝날 때까지 실행)

## 출력 해석
- Registers 패널에서 `RIP`(또는 `EIP`) 옆 모듈명이 `ntdll`이면 아직 System Breakpoint 근처, 대상 프로그램 이름이면 엔트리 포인트 이후다.
- Log 창에 `DLL Loaded: "kernel32.dll"`처럼 여러 줄이 쌓이면 로더가 정상적으로 필요한 DLL들을 붙이는 중이라는 뜻이다.
- Memory Map에서 대상 실행 파일의 이미지 베이스 행(Base 열이 파일 자신인 것) 옆에 `PE`, `Executable`같은 표시가 있다.
- F9를 눌렀는데 프로그램이 즉시 종료되고 프로세스가 사라졌다면, Entry breakpoint 옵션이 꺼져 있어서 끝까지 실행돼버렸거나, 프로그램이 안티디버깅으로 디버거를 감지하고 스스로 종료했을 가능성도 있다(REV-0130 참고).

## 흔한 실수
- System Breakpoint에서 멈춘 `ntdll.dll` 코드를 대상 프로그램의 코드로 착각해서 그 안에서 헤매는 것.
- Entry breakpoint 옵션이 꺼진 줄 모르고 F9를 눌렀다가 프로그램이 끝까지 실행돼버려서 "왜 멈추질 않지"라며 당황하는 것 — `Options → Preferences → Events`를 먼저 확인해야 한다.
- TLS 콜백이 있는 바이너리에서 TLS 콜백 실행 지점을 진짜 엔트리 포인트로 착각하는 것 — 모듈명과 함수 위치가 프로그램 자신의 `AddressOfEntryPoint`와 일치하는지 다시 확인해야 한다.
- 32비트 exe를 x64dbg로, 64비트 exe를 x32dbg로 잘못 열어서 애초에 로드가 안 되거나 이상하게 동작하는 것.
- Step Into(F7)로 모든 `call`에 다 들어가버려서 CRT 내부의 방대한 초기화 코드 속에서 길을 잃는 것 — 익숙하지 않은 초반에는 Step Over(F8)를 기본으로 쓰고, 정말 들어가야 할 함수만 선택적으로 F7을 쓰는 편이 낫다.

## 막혔을 때 다음 체크
- 엔트리 포인트 주소를 미리 알고 싶다면 → REV-0125 PE-bear로 헤더 분석하는 방법에서 `AddressOfEntryPoint` 값을 먼저 확인
- 코드가 알아볼 수 없는 스텁으로만 보인다면 → REV-0126 Detect It Easy로 컴파일러 패커 확인으로 패킹 여부부터 점검
- 함수 프롤로그의 `sub rsp, 0x28` 같은 스택 조작이 낯설다면 → REV-0124 Shadow Space가 무엇인지
- `call` 직전 인자가 어느 레지스터에 담기는지 헷갈린다면 → REV-0122 Microsoft x64 호출 규약
- 정적 분석 도구와 함께 대조하고 싶다면 → ../static-analysis/rev-0142-ida-first-open.md

## 미니 예제
64비트 콘솔 프로그램 `sample.exe`를 x64dbg로 처음 여는 전형적인 흐름:

```text
1. Ctrl+O → sample.exe 선택
2. 자동으로 System Breakpoint에서 정지 (모듈: ntdll.dll)
3. F9 실행 → Entry breakpoint에서 정지 (모듈: sample.exe, RIP = AddressOfEntryPoint)
4. Alt+M으로 Memory Map 확인 → sample.exe 이미지 베이스, kernel32.dll, ntdll.dll 등 매핑 확인
5. Alt+E로 Symbols 확인 → kernel32.dll의 CreateFileW, ReadFile 등 export 목록 확인
6. IDA에서 미리 확인해둔 main 주소(예: 0x401450)에 bp 0x401450 입력 후 F9
7. main 함수 진입 지점에서 정지 → 여기서부터 F8/F7로 실제 로직을 한 줄씩 추적
```

## 관련 글
- REV-0125 — PE-bear로 헤더 분석하는 방법
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0124 — Shadow Space가 무엇인지
- REV-0122 — Microsoft x64 Calling Convention
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기
- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것

## 출처/검증
- Windows 프로세스 시작 순서(로더 초기화, TLS 콜백, 엔트리 포인트, CRT 시작 함수)는 Microsoft 공식 문서(learn.microsoft.com, "C run-time initialization", "TLS callback functions" 관련 문서) 기준.
- x64dbg의 System Breakpoint / Entry breakpoint 동작과 단축키는 x64dbg 공식 문서(help.x64dbg.com) 및 x64dbg 기본 UI 동작 기준(2026-09-08 확인). 정확한 메뉴 위치/기본값은 버전에 따라 달라질 수 있으므로 실제 설치본에서 `Options → Preferences`를 직접 확인할 것을 권장한다.
