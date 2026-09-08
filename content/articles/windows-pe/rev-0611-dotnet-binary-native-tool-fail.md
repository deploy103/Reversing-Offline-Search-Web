---
id: REV-0611
title: ".NET 바이너리인데 Native 도구로 분석이 안 될 때"
slug: "rev-0611-dotnet-binary-native-tool-fail"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "dnSpyEx", ILSpy, "Detect It Easy"]
keywords: ["IMAGE_COR20_HEADER", "IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR", "mscoree.dll", "_CorExeMain", "CLR", "MSIL", "dnSpyEx"]
aliases: [".NET 어셈블리 분석 실패", "IDA에서 함수가 안 보임", "CorExeMain만 있는 임포트", "MSIL 디컴파일"]
symptom_keywords: ["IDA에서 함수가 거의 안 보인다", "임포트가 mscoree.dll _CorExeMain 하나뿐이다", "디스어셈블리가 의미 없어 보인다", ".text .rsrc 섹션만 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Import 테이블에 `mscoree.dll`의 `_CorExeMain`(또는 DLL이면 `_CorDllMain`) 하나만 있고 함수가 거의 안 보인다면 이 파일은 실제 로직이 x86/x64 네이티브 코드가 아니라 MSIL(CIL) 바이트코드로 컴파일된 .NET 어셈블리이므로, IDA 대신 dnSpyEx나 ILSpy 같은 .NET 디컴파일러로 열어야 정상적으로 분석된다.

## 언제 검색해야 하나
- IDA로 EXE를 열었는데 함수 목록이 비정상적으로 적고, 디스어셈블리를 봐도 의미 있는 로직이 거의 안 보일 때
- Import 테이블을 확인했더니 `mscoree.dll`이라는 모듈 하나에 `_CorExeMain`(또는 `_CorDllMain`) 함수 하나만 임포트되어 있을 때
- 섹션이 `.text`, `.rsrc`, `.reloc` 정도로 단순하고 엔트로피도 낮아서 패킹된 것 같지는 않은데 코드가 이상하게 적을 때

## 핵심 개념
Windows 로더는 PE 파일을 로드할 때 COFF 옵션 헤더의 데이터 디렉터리 중 인덱스 14번, `IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR`(COM 디스크립터 디렉터리)를 확인한다. 이 값이 0이 아니면 로더는 이 파일을 **관리 코드(managed code)**, 즉 .NET 어셈블리로 판단하고 일반적인 네이티브 로딩 절차 대신 특별한 경로를 탄다.

- 이 디렉터리가 가리키는 곳에는 `IMAGE_COR20_HEADER`(흔히 "CLR 헤더" 또는 "Cor20 헤더"라고 부름) 구조체가 있으며, 여기에는 런타임 버전 정보, 메타데이터 위치, 그리고 관리 코드 진입점을 가리키는 `EntryPointToken`(메서드 정의 테이블의 특정 행을 가리키는 토큰) 등이 담겨 있다.
- 이런 파일의 PE 헤더상의 진입점(Entry Point)은 항상 `mscoree.dll`의 `_CorExeMain`(EXE의 경우) 또는 `_CorDllMain`(DLL의 경우)을 가리키도록 되어 있다. 이 함수가 하는 일은 CLR(Common Language Runtime)을 초기화하고, `IMAGE_COR20_HEADER`의 `EntryPointToken`이 가리키는 진짜 관리 코드 진입점을 찾아 실행을 넘기는 것뿐이다.
- 결과적으로 Import 테이블에는 `mscoree.dll`의 함수 단 하나만 존재하게 되고, 실제 프로그램 로직(사용자가 작성한 함수들)은 x86/x64 기계어가 아니라 **MSIL(Microsoft Intermediate Language, CIL이라고도 함)**이라는 스택 기반 바이트코드로 메타데이터 영역에 저장되어 있다. IDA 같은 네이티브 디스어셈블러는 이 바이트코드를 x86/x64 명령어로 잘못 해석하려 하기 때문에 의미 없는 결과가 나오거나, 애초에 코드로 인식하지도 못한다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭에 모듈이 `mscoree.dll` 하나, 함수가 `_CorExeMain` 또는 `_CorDllMain` 하나뿐
- 파일 속성(우클릭 → 속성 → 세부 정보) 또는 `dotnet-trace`/`corflags` 등에서 ".NET Assembly" 관련 정보가 보임(닷넷 설치 환경에서 실행하면 "관리되는 실행 파일" 관련 표시가 뜨는 경우도 있음)
- Detect It Easy(DIE)로 열면 "PE" 항목 아래에 `.NET(C#)` 또는 `Microsoft Visual Studio .NET` 같은 표시가 자동으로 뜸
- IDA 디스어셈블리 창에서 코드처럼 보이는 부분이 극히 짧고, 나머지는 대부분 데이터/문자열로 표시됨(메타데이터/MSIL이 코드로 인식되지 않기 때문)

## 가장 먼저 할 것
1. Detect It Easy로 파일을 열어 ".NET" 여부를 자동 판별한다. 언어/컴파일러 정보(예: "Microsoft Visual C# / Basic .NET" 등)까지 함께 표시된다.
2. .NET으로 확인되면 IDA를 닫고, dnSpyEx(dnSpy의 유지보수 포크)나 ILSpy 같은 .NET 전용 디컴파일러로 다시 연다.
3. dnSpyEx/ILSpy에서 왼쪽 트리를 펼쳐 네임스페이스 → 클래스 → 메서드 순서로 실제 C# 유사 코드(디컴파일된 소스)를 바로 읽는다.

## 단계별 절차
**1) .NET 여부 확정하기**
- Detect It Easy로 열어 자동 판별 결과를 확인하거나, IDA Imports에서 `mscoree.dll`/`_CorExeMain` 조합을 직접 확인한다.
- 더 확실하게 하려면 PE-bear 등으로 데이터 디렉터리 목록을 보고 `COM Descriptor`(인덱스 14) 항목의 `VirtualAddress`/`Size`가 0이 아닌지 확인한다.

**2) 적절한 도구로 갈아타기**
- **dnSpyEx**: 디컴파일뿐 아니라 디버깅(중단점, 스텝 실행), IL 코드 직접 편집, 재컴파일까지 가능해 CTF 문제 풀이에 가장 널리 쓰인다.
- **ILSpy**: 읽기 전용 디컴파일에 특화되어 있고 가볍다. 여러 언어(C#, IL, VB 스타일)로 디컴파일 결과를 바꿔볼 수 있다.
- 두 도구 모두 파일을 열면 어셈블리 트리(네임스페이스 → 클래스 → 메서드)가 그대로 펼쳐지며, 각 메서드를 클릭하면 원본에 가까운 C# 코드가 즉시 보인다.

**3) 실제 로직 분석**
- 사용자가 작성한 클래스/메서드 이름이 난독화되지 않았다면 이름만으로도 대략적인 기능을 유추할 수 있다.
- 문자열 리터럴, 상수 등은 IDA의 Strings 창과 달리 디컴파일된 코드 안에 그대로 자연스럽게 나타난다.

**4) 난독화된 경우**
- ConfuserEx 같은 .NET 난독화 도구가 적용된 경우 클래스/메서드 이름이 의미 없는 문자로 바뀌어 있거나, 문자열이 암호화되어 있거나, 제어 흐름이 뒤섞여 있을 수 있다. 이 경우 de4dot 같은 전용 언패커를 먼저 시도하거나, dnSpyEx의 디버거로 실제 실행 흐름을 따라가며 분석해야 한다.

## 명령어/단축키
- dnSpyEx: 파일 열기 후 좌측 Assembly Explorer 트리 탐색, `F5`(디버그 시작), 메서드 우클릭 → "Edit Method (C#)"으로 직접 수정
- ILSpy: 좌측 트리 탐색, 언어 드롭다운에서 IL/C# 전환
- Detect It Easy: 파일 열면 자동으로 상단에 형식/컴파일러 정보 표시

## 출력 해석
- Import가 `mscoree.dll`/`_CorExeMain` 하나뿐이라는 것 자체가 곧 ".NET 어셈블리다"라는 강한 증거다. 다른 정상적인 Win32 API 임포트(`kernel32.dll`, `user32.dll` 등)가 안 보인다고 해서 파일이 손상된 것이 아니라, 원래 이런 파일들은 그 API들을 CLR을 통해 간접적으로만 사용하기 때문이다.
- `IMAGE_COR20_HEADER`의 `Flags` 필드에 `COMIMAGE_FLAGS_ILONLY`가 켜져 있으면 순수 MSIL만 있는 파일이라는 뜻이고, 꺼져 있으면 네이티브 코드가 일부 섞인 혼합 어셈블리(mixed-mode assembly, C++/CLI 등)일 수 있어 IDA 분석이 부분적으로 필요할 수도 있다.

## 흔한 실수
- IDA에서 함수가 거의 안 보이는 것을 "패킹되어 있다"고 오해해서 언패킹 도구부터 찾아 헤매는 것. 먼저 Import 테이블과 DIE로 .NET 여부부터 확인해야 한다.
- .NET 어셈블리를 억지로 IDA에서 분석하려고 시도하며 시간을 낭비하는 것. IDA도 확장 플러그인으로 어느 정도 .NET을 다룰 수는 있지만, 기본적으로는 dnSpyEx/ILSpy 같은 전용 도구가 압도적으로 효율적이다.
- 혼합 모드 어셈블리(C++/CLI)를 순수 MSIL로 착각해서 네이티브 코드 부분을 놓치는 것. `COMIMAGE_FLAGS_ILONLY` 플래그를 반드시 확인한다.

## 막혔을 때 다음 체크
- .NET인지 네이티브인지부터 헷갈린다면 → REV-0136(.NET EXE인지 Native EXE인지 구분)을 먼저 읽는다.
- Import Table 구조 자체를 더 잘 이해하고 싶다면 → REV-0119(Import Table에서 중요한 API 찾기)를 확인한다.
- 난독화된 .NET 어셈블리라 이름과 문자열이 다 깨져 있다면 → 패킹/난독화 관련 항목을 함께 확인한다.

## 미니 예제
IDA로 `sample.exe`를 열었더니 Imports 탭에 다음 한 줄만 있었다.

```text
mscoree.dll    _CorExeMain
```

디스어셈블리도 진입점 근처에 몇 개의 명령어(`_CorExeMain` 호출 스텁)만 있고 그 외 함수가 거의 없었다. Detect It Easy로 다시 열어보니 "PE64" 아래에 ".NET(C#)"이 표시되었다. dnSpyEx로 같은 파일을 열자 좌측 트리에 `Program`, `MainWindow` 같은 클래스가 그대로 펼쳐졌고, `Program.Main(string[] args)` 메서드를 클릭하니 원본과 거의 동일한 C# 코드가 바로 보였다.

## 관련 글
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0135 — DLL 문제 분석 시작하기

## 출처/검증
- 로더가 `IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR`(인덱스 14)를 확인해 관리 코드 여부를 판단하고, `IMAGE_COR20_HEADER`(Cor20/CLR 헤더)를 통해 메타데이터와 진입점(`EntryPointToken`)을 찾는다는 점, .NET 실행 파일의 Import 테이블이 `mscoree.dll`의 `_CorExeMain`/`_CorDllMain` 하나로만 구성된다는 점은 Microsoft 공식 문서(`_CorExeMain`, `_CorValidateImage` 문서)와 공개된 PE/.NET 파일 포맷 분석 자료(dotnetfile 프로젝트 문서 등) 기준이다.
- dnSpyEx/ILSpy가 .NET 어셈블리 디컴파일 및 디버깅에 널리 쓰이는 표준 도구라는 점은 각 도구의 공식 저장소 및 커뮤니티 자료 기준이다(2026-09-08 확인).
