---
id: REV-0003
title: "처음 보는 EXE 문제 접근 순서"
slug: "rev-0003-first-exe"
category: "triage"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, Ghidra, "Detect It Easy", "PE-bear", x64dbg]
keywords: [EXE 분석 순서, PE 파일 분석, Windows 리버싱 시작, .NET 확인, DIE 사용법, PE-bear 사용법, 콘솔 앱 GUI 앱 구분, PE 처음]
aliases: ["exe 문제 어떻게 풀어", "윈도우 문제 처음 접근", "exe 받았는데 뭐부터", "PE 파일 분석 순서", "PE 처음", "pe 처음 보기", "pe 처음 시작", "처음 보는 PE"]
symptom_keywords: ["exe 파일 뭐부터 봐야 할지 모르겠음", "윈도우 문제 처음 봄", "PE 파일 막힘", ".NET인지 모르겠음", "exe 열었는데 아무것도 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows `.exe` 문제는 **Detect It Easy로 실제 형식·컴파일러·패커부터 확인 → PE-bear로 섹션/임포트 훑기 → IDA/Ghidra로 F5 → 필요하면 x64dbg로 동적 확인** 순서로 접근하면 헤매지 않는다.

## 언제 검색해야 하나
- CTF/워게임에서 `.exe` 파일 하나만 던져줬고, IDA부터 켤지 x64dbg부터 켤지 감이 안 잡힐 때
- IDA로 열었더니 함수가 거의 없거나 이상한 코드만 보여서 "이게 진짜 이 프로그램 코드가 맞나" 싶을 때
- .NET인지 네이티브(C/C++)인지조차 구분이 안 될 때

## 핵심 개념
`.exe`라는 확장자는 실제로 아무것도 보장하지 않는다. Windows에서 "실행 가능한 파일"은 전부 PE(Portable Executable) 포맷을 쓰지만, 그 안에는 완전히 다른 세계가 여럿 있다.

- **네이티브 C/C++ (MSVC/MinGW로 컴파일)**: IDA/Ghidra로 바로 디스어셈블/디컴파일이 가능한 전형적인 경우.
- **.NET (C#/VB.NET)**: PE 헤더는 있지만 실제 코드는 CIL(중간 언어) 바이트코드다. IDA로 열면 어셈블리 명령어가 거의 안 보이고 `mscoree.dll`, `_CorExeMain` 같은 것만 보인다. 이 경우 IDA가 아니라 **dnSpyEx**나 **ILSpy**로 열어야 한다.
- **패킹된 실행파일**: UPX 등으로 패킹되어 있으면 원본 코드가 압축/암호화되어 있어서 정적 분석이 거의 불가능하다. 실행 후 메모리에서 언패킹된 상태를 봐야 한다.
- **설치 프로그램/스크립트 래퍼**: 실제로는 자체 압축 실행파일(SFX)이거나 인스톨러여서 리버싱 대상이 아닐 수도 있다.

이 구분을 안 하고 무작정 IDA의 F5(디컴파일)를 누르면, .NET인 경우 쓰레기 같은 코드만 보고 시간을 낭비하게 된다. 그래서 첫 단계는 항상 "이게 정확히 뭐냐"를 확인하는 것이다.

## 화면/코드에서 보이는 징후
- IDA로 열었는데 Functions 창(Ctrl+P)에 함수가 5개 이하이고 이름이 전부 `.NET`, `CorExeMain` 관련이면 .NET 앱이다.
- 문자열(Shift+F12)에 `mscorlib`, `System.Windows.Forms`, `<Module>` 같은 게 보이면 .NET 확정.
- 섹션이 `.text`, `.rdata`, `.data`만 있고 크기가 매우 작은데 파일 전체 크기는 크다면 리소스에 다른 데이터(추가 실행파일, 압축 데이터)가 숨어 있을 수 있다.
- IDA Functions 창에 함수가 거의 없고 `.text` 섹션 이름이 `UPX0`, `UPX1`처럼 바뀌어 있으면 UPX 패킹이다.

## 가장 먼저 할 것
IDA를 켜기 전에 **Detect It Easy(DIE)** 를 먼저 켠다. 파일을 DIE 창에 드래그 앤 드롭하면 우측 상단에 파일 형식(PE32/PE32+, 즉 32비트/64비트), 컴파일러(Microsoft Visual C/C++, .NET, MinGW 등)가 바로 표시된다. 하단의 "Scan" 버튼을 누르면 패커(UPX, Themida 등) 탐지도 자동으로 해준다.

## 단계별 절차

**1) DIE로 형식 확인**

DIE 실행 → 파일 드래그 → 상단 표시를 읽는다.
- `PE32` = 32비트, `PE32+` = 64비트.
- "Compiler" 칸에 `Microsoft Visual C/C++`가 뜨면 네이티브 코드다. 바로 IDA로 넘어가면 된다.
- "Compiler" 칸에 `.NET(C#)` 또는 `Microsoft Visual Studio .NET`이 뜨면 → IDA는 나중으로 미루고 **dnSpyEx**(무료, 디컴파일+디버깅 가능)로 열어야 한다. .NET 앱은 원본 C# 소스에 가깝게 복원되기 때문에 오히려 분석이 훨씬 쉽다.
- 하단 "Scan" 버튼을 눌러서 나오는 결과에 `Packer: UPX`처럼 뜨면 언패킹부터 해야 한다(UPX라면 `upx -d 파일명.exe`로 대부분 바로 풀린다).

**2) PE-bear로 구조 훑기**

네이티브 코드라고 확인됐으면 PE-bear를 열어서:
- 좌측 트리에서 **Sections** 탭 → `.text`(코드), `.rdata`(읽기전용 데이터, 문자열 상수 포함), `.data`(전역변수) 크기를 본다.
- **Imports** 탭 → 어떤 DLL의 어떤 함수를 쓰는지 목록이 쭉 나온다. `scanf`, `strcmp`, `MessageBoxA` 같은 이름이 보이면 "입력받고 비교해서 메시지박스로 결과를 보여주는 프로그램"이라는 그림이 그려진다. `IsDebuggerPresent`, `CheckRemoteDebuggerPresent`가 있으면 안티디버깅이 있다는 뜻.
- **Optional Header** 탭 → `Subsystem` 값이 `WINDOWS_CUI`면 콘솔(터미널) 앱, `WINDOWS_GUI`면 윈도우 창을 띄우는 앱이다. 콘솔 앱이면 x64dbg로 실행해도 콘솔 창이 뜨고 입력을 넣을 수 있다.

**3) IDA/Ghidra로 정적 분석 시작**

- IDA에서 파일을 열면 자동으로 분석이 시작되고 `Entry point`에 커서가 놓인다.
- Ctrl+P로 함수 목록을 열어 `main`이 있는지 확인한다. 없으면 [rev-0009-finding-main.md](./rev-0009-finding-main.md) 절차를 따른다.
- Shift+F12로 Strings 창을 열어 "Correct", "Wrong", "flag" 관련 문자열을 찾는다. 찾았으면 [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md) 방식으로 역추적한다.

**4) 필요하면 x64dbg로 동적 확인**

정적으로 로직이 잘 안 보이거나(예: 문자열이 런타임에 생성됨, 안티디버깅 있음) 확인하고 싶으면 x64dbg로 실행하며 브레이크포인트를 건다. x64dbg는 32비트 파일은 x32dbg로 열어야 한다는 점에 주의한다(비트수가 다르면 아예 실행이 안 되거나 잘못 로드된다).

## 명령어/단축키
- DIE: 드래그 앤 드롭 → 상단 정보 확인 → 하단 "Scan" 버튼
- IDA: `Ctrl+P`(함수 목록), `Shift+F12`(문자열), `F5`(디컴파일), `X`(xref)
- UPX 언패킹: `upx -d challenge.exe`
- x64dbg: `F9`(실행/계속), `F2`(브레이크포인트), `F7`(스텝 인투), `F8`(스텝 오버)

## 출력 해석
- DIE의 "Compiler" 칸이 `.NET`이면 정적 분석 도구는 IDA가 아니라 dnSpyEx여야 한다 — 이걸 놓치면 몇 시간을 IDA에서 헤맬 수 있다.
- PE-bear Imports에 `KERNEL32.dll`만 잔뜩 있고 `MSVCRT.dll`이 없다면 순수 WinAPI로 짜인 프로그램일 가능성이 높다 — `scanf` 대신 `ReadConsoleA` 같은 함수를 찾아야 한다.
- Subsystem이 `WINDOWS_GUI`인데 콘솔 출력을 기대하고 있었다면, 실제로는 `MessageBoxA`나 다이얼로그로 결과가 나올 것이다.

## 흔한 실수
- 파일 형식 확인 없이 곧바로 IDA를 켜고 F5를 눌러서 .NET 어셈블리를 억지로 디스어셈블리로 읽으려는 것.
- 32비트 파일을 x64dbg(64비트 전용)로 열어서 "왜 안 열리지"라며 당황하는 것 — x32dbg를 써야 한다.
- 패킹된 걸 모르고 IDA에서 함수가 안 보인다고 스크롤만 계속 내리는 것.
- Subsystem이 GUI 앱인데 콘솔에서 실행하고 입력이 안 된다고 착각하는 것.

## 막혔을 때 다음 체크
- 함수가 거의 없다 → [rev-0009-finding-main.md](./rev-0009-finding-main.md), [rev-0010-stripped-entry-point.md](./rev-0010-stripped-entry-point.md)
- 정적으로 볼지 동적으로 볼지 애매하다 → [rev-0005-static-vs-dynamic.md](./rev-0005-static-vs-dynamic.md)
- 확장자와 실제 형식이 다른 것 같다 → [rev-0002-dont-trust-extension.md](./rev-0002-dont-trust-extension.md)
- 5분째 아무 진전이 없다 → [rev-0015-five-minute-checklist.md](./rev-0015-five-minute-checklist.md)

## 미니 예제
`crackme.exe`를 받았다고 하자.
1. DIE에 드롭 → `PE32+`, `Microsoft Visual C/C++`, Scan 결과 패커 없음.
2. PE-bear Imports → `scanf`, `strcmp`, `printf`가 보임 → "입력 받아서 strcmp로 비교하는 전형적인 crackme"라는 가설 수립.
3. IDA로 열고 Shift+F12 → `Wrong password!`, `Correct!` 문자열 발견.
4. `Correct!` 더블클릭 → `X`(xref) → 이 문자열을 참조하는 함수로 이동 → 그 함수 안에서 `strcmp` 호출을 발견하면 바로 검증 로직 도달.

## 관련 글
- [rev-0001-first-30-seconds.md](./rev-0001-first-30-seconds.md)
- [rev-0002-dont-trust-extension.md](./rev-0002-dont-trust-extension.md)
- [rev-0004-first-elf.md](./rev-0004-first-elf.md)
- [rev-0005-static-vs-dynamic.md](./rev-0005-static-vs-dynamic.md)
- [rev-0009-finding-main.md](./rev-0009-finding-main.md)
- [rev-0010-stripped-entry-point.md](./rev-0010-stripped-entry-point.md)

## 출처/검증
- Detect It Easy 공식 GitHub(horsicq/Detect-It-Easy) 기능 설명 기준.
- PE-bear 공식 문서(hasherezade/pe-bear) 기준.
- PE 포맷 Subsystem 필드: Microsoft Learn "PE Format" 문서 기준 (2026-09-08 검증).
