---
id: REV-0136
title: ".NET EXE인지 Native EXE인지 구분"
slug: "rev-0136-dotnet-vs-native"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", "dnSpyEx"]
keywords: [".NET", "CLR", "IMAGE_COR20_HEADER", "mscoree.dll", "_CorExeMain", "managed", "native", "dotnet-tools"]
aliases: ["닷넷인지 확인", "매니지드 바이너리 구분", "CLR 헤더 확인", "IL 코드인지 확인"]
symptom_keywords: ["IDA로 열었는데 함수가 거의 없다", "임포트가 mscoree.dll 하나뿐이다", "디컴파일 결과가 이상하게 비어있다", "이 파일이 C++인지 C#인지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
겉보기엔 똑같은 `.exe` 확장자라도 C/C++로 만든 네이티브 실행 파일과 C#/.NET(VB.NET 등 CLR 기반)으로 만든 관리형(managed) 실행 파일은 내부 구조와 분석 도구가 완전히 다르므로, IDA/x64dbg로 어셈블리를 붙잡고 씨름하기 전에 반드시 PE 헤더 안의 CLR 헤더 유무부터 확인해서 처음부터 올바른 도구(IDA/x64dbg vs dnSpyEx/ILSpy)를 골라야 시간을 낭비하지 않는다.

## 언제 검색해야 하나
- IDA로 EXE를 열었는데 함수가 거의 없고 임포트도 몇 개 안 되는데 파일 크기는 꽤 클 때
- 임포트 테이블을 봤더니 `mscoree.dll`이 거의 유일한 임포트이고 `_CorExeMain` 같은 낯선 함수만 보일 때
- 디컴파일된 코드가 이상하게 텅 비어 있거나 의미 없는 스텁처럼 보일 때
- 파일을 실행했을 때 ".NET Framework가 필요합니다" 같은 메시지가 뜬 적이 있을 때
- 문제 설명에 C#, .NET, CLR, IL 같은 단어가 언급될 때

## 핵심 개념
Windows EXE/DLL은 크게 두 종류로 나뉜다.

**네이티브(Native) 바이너리**: C/C++ 등으로 작성되어 컴파일 시점에 x86/x64 기계어로 완전히 변환된 파일. CPU가 이 기계어를 직접 실행한다. IDA/Ghidra/x64dbg가 다루는 것은 기본적으로 이 형태다.

**관리형(Managed/.NET) 바이너리**: C#, VB.NET, F# 등으로 작성되어 컴파일 시점에는 CPU 기계어가 아니라 **CIL(Common Intermediate Language, 흔히 IL이라 부름)**이라는 중간 언어로 변환된 파일. 실제 실행 시점에는 `.NET` 런타임(CLR, Common Language Runtime)이 이 IL 코드를 JIT(Just-In-Time) 컴파일해서 기계어로 바꿔가며 실행한다.

두 형태 모두 파일 포맷은 똑같은 PE(EXE)이지만, .NET 바이너리는 PE 옵셔널 헤더의 데이터 디렉터리 중 **14번째 항목(`IMAGE_DIRECTORY_ENTRY_COMHEADER`, 흔히 ".NET 헤더"라고 부름)**이 `IMAGE_COR20_HEADER`라는 구조체를 가리킨다는 결정적인 차이가 있다. 이 헤더가 있으면 그 파일은 100% .NET(관리형) 바이너리다. `IMAGE_COR20_HEADER`에는 CLR 버전 요구사항, 메타데이터(타입/메서드/필드 정보) 위치, 엔트리 포인트 토큰 등이 담겨 있다.

또한 .NET 바이너리는 네이티브 코드 실행을 위한 아주 얇은 stub만 갖고 있는데, 이 stub의 역할은 사실상 `mscoree.dll`(또는 최신 .NET Core/5+에서는 `hostfxr.dll`)의 `_CorExeMain`(또는 유사 진입 함수)을 호출해서 CLR을 초기화하고 IL 코드를 넘겨주는 것뿐이다. 그래서 임포트 테이블을 보면 놀랍도록 임포트가 적고(거의 `mscoree.dll` 하나) 실제 프로그램 로직이 담긴 함수가 임포트/코드 섹션 어디에도 안 보이는데, 이는 실제 로직이 기계어가 아니라 IL 형태로 메타데이터 영역에 저장되어 있기 때문이다.

## 화면/코드에서 보이는 징후
- PE-bear의 "Optional Header" → "Data Directories" 목록에서 ".NET"(`COM Descriptor` 또는 `CLR Header`) 항목의 RVA/Size가 0이 아님
- 임포트 테이블에 `mscoree.dll`만 있고 `_CorExeMain`(x86/구버전) 또는 `_CorDllMain`(DLL) 같은 이름만 보임
- IDA로 열었을 때 함수 개수가 극단적으로 적고(보통 한두 개), Strings 창에도 사람이 읽을 수 있는 로직 관련 문자열이 거의 안 보임(문자열이 UTF-16 메타데이터 형태로 별도 저장되어 있기 때문)
- DOS 스텁("This program cannot be run in DOS mode") 뒤에 이어지는 헤더 구조를 열어보면 옵셔널 헤더 크기나 데이터 디렉터리 개수가 15개(네이티브는 보통 16개 중 마지막 예약 영역만 다르고, .NET은 14번 COM 디스크립터 항목이 실제로 채워져 있음)
- `dotnet-tools`류(예: `dotnet-trace`, `corflags.exe`) 또는 dnSpyEx로 열었을 때 정상적으로 클래스/메서드 트리가 보임(네이티브 바이너리라면 애초에 열리지 않거나 아무 내용도 안 나옴)

## 가장 먼저 할 것
1. PE-bear로 파일을 열어 **Data Directories** 탭에서 ".NET"(또는 "COM Descriptor") 항목의 RVA/Size가 0이 아닌지부터 확인한다. 이게 가장 빠르고 확실한 방법이다.
2. 확실치 않으면 임포트 테이블을 보고 `mscoree.dll`(또는 `.NET Core`의 경우 `hostfxr.dll`, `coreclr.dll`)이 유일하거나 지배적인 임포트인지 확인한다.
3. .NET로 판명되면 IDA/x64dbg 대신 **dnSpyEx**(또는 ILSpy)로 다시 열어서 분석을 시작한다. 이 도구들은 IL 코드를 사람이 읽을 수 있는 C# 코드에 가깝게 역디컴파일해준다.

## 단계별 절차
**1) PE-bear로 CLR 헤더 확인**
- 파일을 PE-bear로 연다.
- 좌측 트리에서 `Optional Header → Data Directories`로 이동한다.
- 목록 중 `.NET`(도구 버전에 따라 "COM Descriptor Table"로 표기) 항목을 찾아 RVA와 Size 값을 확인한다. 둘 다 0이면 네이티브, 0이 아니면 .NET이다.

**2) 임포트 테이블로 보조 확인**
- `Imports` 탭에서 DLL 목록을 본다. `mscoree.dll`이 거의 유일하게 보이고 `KERNEL32.dll`, `USER32.dll` 등 일반적인 Win32 API 임포트가 거의 없다면 .NET일 가능성이 매우 높다.
- 네이티브 EXE라면 보통 수십~수백 개의 Win32 API 함수가 여러 시스템 DLL에서 임포트된다.

**3) 확정 후 적절한 도구로 전환**
- .NET로 확인되면 **dnSpyEx**로 파일을 연다. 좌측 트리에서 어셈블리 → 네임스페이스 → 클래스 → 메서드 순으로 펼치면 거의 원본 C# 소스에 가까운 코드가 바로 보인다(디버그 심볼이 없어도 IL 자체가 고급 정보를 담고 있어 디컴파일 품질이 네이티브보다 훨씬 좋다).
- 실행 파일이 `.NET Core`/`.NET 5+` 기반이면 `dotnet-tools`(예: `corflags`나 `dotnet --info`)로 타깃 프레임워크 버전을 확인하거나, 함께 배포된 `.deps.json`/`.runtimeconfig.json` 파일이 있는지 확인하면 어떤 런타임이 필요한지 알 수 있다.
- 네이티브로 확인되면 그대로 IDA/x64dbg로 진행한다.

## 명령어/단축키
- PE-bear: `Optional Header → Data Directories`(.NET 항목 RVA/Size 확인)
- dnSpyEx: 좌측 트리에서 클래스/메서드 더블클릭 시 바로 디컴파일된 코드 표시, `Ctrl+Shift+K`(어셈블리 검색), `Ctrl+F`(전체 검색으로 문자열/메서드 찾기)
- 커맨드라인(참고): `corflags.exe 파일.exe` — CLR 헤더 플래그(32BITREQUIRED 등)를 텍스트로 바로 확인 가능(.NET Framework SDK 도구)
- `dotnet-tools`(예: `dotnet --info`) — 설치된 .NET 런타임/SDK 정보 확인용, 대상 파일 자체 분석과는 별개

## 출력 해석
- ".NET" 데이터 디렉터리 RVA가 0이 아니고 Size가 보통 0x48(72바이트, `IMAGE_COR20_HEADER` 크기)이면 100% .NET 바이너리다.
- 임포트가 `mscoree.dll`만 있고 함수가 `_CorExeMain` 하나뿐이면, 이 EXE는 사실상 "CLR을 불러와서 IL을 실행해줘"라는 요청 한 줄만 담긴 껍데기이며, 실제 로직은 어셈블리 자체의 메타데이터/IL 스트림에 있다.
- dnSpyEx에서 클래스 트리가 정상적으로 펼쳐지고 메서드 본문이 C#과 거의 흡사한 코드로 나온다면 분석 준비가 된 것이다.

## 흔한 실수
- .NET 바이너리를 IDA로 계속 붙잡고 어셈블리 레벨에서 분석하려고 시도하는 것. IL은 스택 기반 가상 머신 코드라서 x86/x64 디스어셈블리와 전혀 다르며, dnSpyEx/ILSpy를 쓰는 것이 압도적으로 빠르고 정확하다.
- 반대로 네이티브 바이너리를 dnSpyEx로 열어보고 "아무것도 안 보인다"고 당황하는 것. dnSpyEx는 .NET 어셈블리 전용이므로 네이티브 PE는 애초에 의미 있는 트리를 보여주지 못한다.
- `.NET`이면서 동시에 일부 함수만 네이티브 C++/CLI(`/clr` 컴파일 옵션)로 섞여 있는 **혼합 어셈블리(mixed-mode assembly)**의 존재를 모르는 것. 이 경우 CLR 헤더도 있고 실제 네이티브 코드도 섞여 있어서, dnSpyEx와 IDA를 함께 써야 할 수 있다.
- CLR 헤더가 있다고 반드시 최신 .NET(Core/5+)이라고 단정하는 것. `.NET Framework`(구버전, `mscoree.dll` 사용)와 `.NET Core/5+`(자체 포함 런타임 또는 `hostfxr.dll` 사용) 구분이 필요할 수 있으며, 이는 이후 별도의 `.NET` 카테고리 글에서 더 깊이 다룰 예정이다(현재 이 지식베이스에는 아직 전용 `.NET` 카테고리가 없다).

## 막혔을 때 다음 체크
- 파일이 DLL 형태의 .NET 어셈블리라면 → REV-0135(DLL 문제 분석 시작하기)의 "익스포트 확인" 절차보다는, .NET 어셈블리는 DllMain 대신 CLR이 클래스/메서드를 직접 호출하는 방식이므로 dnSpyEx로 여는 것이 우선이다.
- .NET이 아니라 네이티브로 확인됐는데 함수 목록이 CRT 함수로 도배되어 실제 로직을 못 찾겠다면 → REV-0137(Visual C++ Runtime 함수가 많은 바이너리 정리법)을 참고한다.
- 네이티브로 확인됐고 임포트 함수 이름이 낯설다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
어떤 `challenge.exe`를 받아 PE-bear로 열었더니 다음과 같이 나왔다고 하자.

```text
Data Directories:
  .NET (COM Descriptor)   RVA: 0x2008   Size: 0x48
Imports:
  mscoree.dll
    _CorExeMain
```

RVA/Size가 0이 아니고 임포트가 `mscoree.dll`의 `_CorExeMain` 하나뿐이므로 이 파일은 .NET 바이너리로 확정할 수 있다. IDA로 열어 함수 목록을 봐도 실제 로직은 보이지 않고 스텁 코드만 있을 것이다. 이 경우 즉시 dnSpyEx로 다시 열어 좌측 어셈블리 트리에서 `Program` 클래스의 `Main` 메서드를 찾아 들어가면, 거의 원본 C# 소스와 동일한 형태의 코드를 바로 읽을 수 있다.

## 관련 글
- REV-0135 — DLL 문제 분석 시작하기
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `IMAGE_COR20_HEADER`와 데이터 디렉터리 14번(`IMAGE_DIRECTORY_ENTRY_COMHEADER`)의 존재는 Microsoft PE/COFF 형식 및 .NET 메타데이터 공식 문서 기준이다.
- CLR이 IL을 JIT 컴파일해서 실행하는 구조와 `_CorExeMain`/`mscoree.dll`의 역할은 Microsoft .NET 런타임 공식 문서 기준이다.
- dnSpyEx/ILSpy의 디컴파일 방식과 PE-bear의 Data Directories 확인 절차는 각 도구의 공식 문서 및 일반적인 사용법 기준이다(2026-09-08 기준 서술).
