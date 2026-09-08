---
id: REV-0586
title: "DLL이 로드되지 않아 실행이 안 될 때(Missing DLL)"
slug: "rev-0586-missing-dll"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, "Process Monitor", "PE-bear"]
keywords: ["Missing DLL", "DLL 검색 순서", "DLL search order", "KnownDLLs", "LoadLibrary 실패", "STATUS_DLL_NOT_FOUND", "api-ms-win-core", "side-by-side"]
aliases: ["dll이 없어서 실행이 안됨", "프로그램을 시작할 수 없습니다 dll", "dll not found 오류", "실행 파일 더블클릭하면 dll 오류"]
symptom_keywords: ["exe를 실행하면 dll이 없다는 창이 뜬다", "The code execution cannot proceed because x.dll was not found", "프로그램이 시작되지 않고 dll 오류만 뜬다", "x64dbg로 열었는데 모듈 로드에 실패한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
실행 파일을 더블클릭했을 때 "The code execution cannot proceed because *.dll was not found. Reinstalling the program may fix this problem." 같은 오류가 뜨는 것은 Windows 로더가 Import Table(REV-0119)에 적힌 DLL을 정해진 검색 순서대로 찾다가 끝내 못 찾았다는 뜻이며, 해결의 핵심은 어떤 DLL이 어느 검색 경로에서 빠졌는지를 Process Monitor나 x64dbg의 모듈 로그로 정확히 짚어내는 것이다.

## 언제 검색해야 하나
- exe를 더블클릭하자마자 실행되지도 않고 바로 오류 창만 뜰 때
- x64dbg로 파일을 열었는데 프로세스가 시작 직후 바로 죽거나 모듈 목록(Modules 탭)에 예상한 DLL이 안 보일 때
- CTF 문제 파일을 배포받았는데 실행 자체가 안 돼서 분석을 시작조차 못 할 때
- 특정 환경(내 PC)에서는 실행되는데 다른 PC에서는 DLL 오류가 나는 이유가 궁금할 때

## 핵심 개념
PE 실행 파일이 시작될 때 Windows 로더는 Import Table(REV-0119)에 나열된 각 DLL을 다음과 같은 순서로 찾는다(SafeDllSearchMode 기준, XP SP2 이후 기본값).

1. **KnownDLLs**: `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\KnownDLLs` 레지스트리에 등록된 핵심 시스템 DLL(kernel32.dll, ntdll.dll 등)은 검색 순서와 무관하게 항상 System32에서 로드된다(DLL 플랜팅 공격 방지 목적).
2. 애플리케이션이 로드된 디렉터리(exe가 있는 폴더)
3. 시스템 디렉터리(`GetSystemDirectory`, 보통 `C:\Windows\System32`)
4. Windows 디렉터리(`GetWindowsDirectory`)
5. 현재 작업 디렉터리
6. `PATH` 환경 변수에 등록된 디렉터리들

이 중 어디에서도 못 찾으면 로더는 프로세스 생성을 실패시키고(`STATUS_DLL_NOT_FOUND`), 사용자에게는 앞서 본 오류 대화상자가 뜬다. 참고로 최신 애플리케이션은 `SetDllDirectory`, `AddDllDirectory`, `LOAD_LIBRARY_SEARCH_*` 플래그를 써서 이 기본 검색 순서를 프로그램 내부에서 바꿀 수도 있다.

CTF/wargame 환경에서 흔한 원인은 세 가지다.
- 문제 출제자가 개발 PC에는 있지만 배포 파일에는 빠뜨린 DLL(자체 제작 DLL, 특정 라이브러리)
- Visual C++ 재배포 패키지 미설치로 `vcruntime140.dll`, `msvcp140.dll`, `ucrtbase.dll` 등이 없는 경우(REV-0595 참고)
- `api-ms-win-core-*.dll`처럼 실제 파일이 아니라 Universal CRT의 API Set 계약(Forwarder) 이름이라서, 이름만 보고 "이 파일을 어디서 구해야 하나" 헤매는 경우 — 이건 Windows 10 이상이면 시스템에 내장되어 있어야 정상이므로 오히려 OS 버전 문제일 수 있다.

## 화면/코드에서 보이는 징후
- "`<프로그램명>.exe - 시스템 오류`" 또는 "`<프로그램명>.exe - System Error`" 제목의 팝업에 "The code execution cannot proceed because `<dll이름>`.dll was not found. Reinstalling the program may fix this problem." 문구
- 구버전 Windows에서는 "This application has failed to start because `<dll>` was not found. Re-installing the application may fix this problem." 형태로 문구가 다를 수 있음
- x64dbg의 Log 창에 대상 DLL 로드 실패 관련 메시지가 남거나, Modules 탭에 기대한 DLL이 목록에 없음
- IDA로 정적 분석 시 Import Table에는 이름이 분명히 있는데, 실제 실행 환경 폴더에는 해당 DLL 파일이 존재하지 않음

## 가장 먼저 할 것
오류 창에 적힌 DLL 이름을 그대로 메모한 뒤, 그 DLL이 exe와 같은 폴더에 있는지부터 확인한다. 없다면 우선 exe와 같은 폴더에 복사해 넣고 다시 실행해본다 — 이것만으로 해결되는 경우가 절반 이상이다. 그래도 안 되면 아래 Process Monitor 절차로 정확한 검색 경로 실패 지점을 확인한다.

## 단계별 절차
**1) Process Monitor로 정확한 실패 지점 추적**
- Sysinternals Process Monitor를 관리자 권한으로 실행한다.
- `Filter → Filter...`에서 `Process Name is <프로그램명>.exe`, `Path ends with .dll`, `Result is NAME NOT FOUND` 세 조건을 AND로 추가한다.
- 대상 exe를 실행한 뒤 캡처된 로그를 보면, 로더가 어떤 순서로 어떤 경로들을 시도했다가 실패했는지가 시간순으로 그대로 남는다. 마지막 시도 경로가 곧 "여기에 넣으면 된다"는 힌트다.

**2) x64dbg로 모듈 로드 확인**
- x64dbg(파일이 32비트면 x32dbg)로 대상을 연다(`File → Open`).
- 상단 `Log` 탭에서 모듈 로드/언로드 메시지를 확인하고, `Modules` 탭(하단 탭 목록)에서 Import Table에 있던 DLL이 실제로 로드됐는지 대조한다.
- 로드에 실패한 DLL이 있다면 그 이름으로 검색해 필요한 재배포 패키지나 원본 DLL을 구한다.

**3) 필요한 DLL 확보 및 배치**
- 자체 제작/서드파티 DLL이라면 exe와 같은 폴더에 복사한다.
- `vcruntime140.dll`, `msvcp140.dll` 등 VC++ 런타임 계열이면 REV-0595 절차대로 Microsoft 공식 재배포 패키지를 설치한다.
- 시스템 DLL(`kernel32.dll` 등)인데도 없다고 뜬다면 OS 자체가 손상됐거나, 32비트 바이너리를 잘못된 시스템 폴더 구조에서 실행 중일 가능성(REV-0596 참고)을 의심한다.

## 명령어/단축키
```text
Process Monitor: Ctrl+L(필터 열기), Ctrl+E(캡처 토글), Ctrl+F(로그 안 검색)
x64dbg: File → Open, 하단 Log/Modules 탭 확인
PE-bear: Import Directory 탭에서 필요한 DLL 목록 전체 확인
```

## 출력 해석
- Process Monitor에서 `Result: NAME NOT FOUND`가 연속으로 여러 줄 뜨고 마지막이 `PATH` 환경 변수 디렉터리들이라면, 그 DLL이 애초에 시스템 어디에도 설치돼 있지 않다는 뜻이다.
- 반대로 `Result: SUCCESS`가 exe 폴더가 아닌 System32에서 뜬다면 시스템에 이미 설치되어 있던 DLL을 정상적으로 찾은 것이니 오류의 원인이 아니다.
- x64dbg Modules 탭에 DLL이 아예 안 보이면 로드 자체가 실패한 것이고, 보이지만 함수 주소가 이상하면 다른 문제(REV-0587의 ordinal 문제 등)일 수 있다.

## 흔한 실수
- 오류 창의 DLL 이름만 보고 인터넷에서 아무 사이트에서나 같은 이름의 DLL을 내려받아 System32에 복사하는 것. 출처가 불분명한 DLL은 버전이 안 맞아 또 다른 오류(0xc000007b 등)를 유발하거나 악성 코드일 위험이 있다. 반드시 Microsoft 공식 재배포 패키지나 신뢰할 수 있는 출처를 사용한다.
- 32비트 DLL을 64비트 System32에, 혹은 그 반대로 넣는 것. 아키텍처가 안 맞으면 로드는 되지만 곧바로 `0xc000007b`류 오류로 이어진다(REV-0596 참고).
- Import Table에 이름은 있지만 실제로는 지연 로딩(Delay Load)이라 `LoadLibrary`/`GetProcAddress`(REV-0129)로 조건부 호출되는 DLL을, 무조건 필수 DLL로 오해하고 시간을 낭비하는 것.

## 막혔을 때 다음 체크
- DLL은 찾았는데 함수가 이름이 아니라 번호로만 임포트되어 있어 헷갈리면 → REV-0587(Ordinal 번호로 Import가 표시될 때)을 참고한다.
- DLL은 로드됐는데 특정 함수 호출에서만 죽는다면 → REV-0135(DLL 문제 분석 시작하기)를 참고한다.
- VC++ 재배포 패키지 관련 오류(`msvcp140.dll` 등)라면 → REV-0595를 바로 확인한다.
- 32비트/64비트 혼동이 의심되면 → REV-0596을 확인한다.

## 미니 예제
Process Monitor 로그에서 다음과 같은 패턴을 봤다고 하자.

```text
Path: C:\ctf\chall.exe          Result: SUCCESS
Path: C:\ctf\helper.dll         Result: NAME NOT FOUND
Path: C:\Windows\System32\helper.dll   Result: NAME NOT FOUND
Path: C:\Windows\helper.dll     Result: NAME NOT FOUND
Path: C:\...\PATH의 각 폴더\helper.dll  Result: NAME NOT FOUND (반복)
```

exe 자체(`chall.exe`)는 정상적으로 로드됐지만, `helper.dll`은 검색 순서상 모든 후보 경로에서 `NAME NOT FOUND`가 떴다. 즉 이 DLL은 시스템에 전혀 설치돼 있지 않고, 문제 배포 파일에 원래 같이 있었어야 하는 커스텀 DLL일 가능성이 크다. 배포 zip을 다시 확인해 `helper.dll`이 exe와 같은 폴더에 있는지 보고, 없다면 문제 파일이 불완전하게 배포된 것이니 원본 출처를 다시 확인해야 한다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0135 — DLL 문제 분석 시작하기
- REV-0587 — Ordinal 번호로 Import가 표시되어 함수명을 모를 때
- REV-0595 — Visual C++ 재배포 패키지 오류로 실행이 안 될 때
- REV-0596 — 32비트 바이너리를 64비트 도구로 열어서 이상해질 때

## 출처/검증
- DLL 검색 순서(애플리케이션 디렉터리 → 시스템 디렉터리 → Windows 디렉터리 → 현재 디렉터리 → PATH)와 KnownDLLs 우선 로드 규칙은 Microsoft Learn "Dynamic-Link Library Search Order" 공식 문서 기준.
- "The code execution cannot proceed because ... was not found" 오류 문구는 Windows 10/11에서 흔히 관찰되는 표준 시스템 오류 대화상자 문구이며, OS 버전에 따라 문구가 다를 수 있으므로 실습 시 실제 화면 문구를 우선한다(2026-09-08 기준 서술).
- Process Monitor 필터 사용법은 Sysinternals 공식 문서 기준.
