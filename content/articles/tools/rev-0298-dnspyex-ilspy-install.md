---
id: REV-0298
title: "dnSpyEx ILSpy 설치와 사용법"
slug: "rev-0298-dnspyex-ilspy-install"
category: "tools"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["dnSpyEx", "ILSpy"]
keywords: ["dnSpyEx 설치", "ILSpy 설치", ".NET 리버싱 도구 설치", "dnSpyEx ILSpy 비교"]
aliases: ["dnSpyEx 설치법", "ILSpy 설치법", ".NET 디컴파일러 설치"]
symptom_keywords: ["dnSpyEx 설치가 안됨", "ILSpy 설치가 안됨", "dnSpyEx ILSpy 뭐가 다른지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
dnSpyEx와 ILSpy는 둘 다 설치 프로그램 없이 압축 파일만 받아서 풀면 바로 실행되는 .NET 전용 도구이며, 오프라인 대회 전에는 두 도구 모두 미리 받아 두는 것이 좋다 — ILSpy는 빠른 읽기 전용 열람, dnSpyEx는 디버깅과 라이브 패치까지 필요할 때 쓴다.

## 언제 검색해야 하나
- `.exe`/`.dll`이 .NET 어셈블리로 확인됐는데(REV-0242 참고) 어떤 도구를 어떻게 설치해야 할지 모를 때
- 오프라인 CTF 대회를 준비하면서 두 도구를 미리 받아 검증해야 할 때
- dnSpyEx와 ILSpy 중 어느 것부터 켜야 할지 헷갈릴 때

두 도구의 화면 구성, 검색 기능, 디버깅/라이브 패치 절차 같은 실제 사용법은 이 문서에서 반복하지 않는다. 아래 원본 문서를 참고할 것.
- [dnSpyEx로 .NET EXE 열기](../dotnet-android/rev-0243-dnspyex-basics.md)
- [ILSpy 기본 사용법](../dotnet-android/rev-0244-ilspy-basics.md)

## 핵심 개념
두 도구 모두 .NET 어셈블리(CIL)를 디컴파일해서 C#으로 보여준다는 점은 같지만 목적이 다르다.

| | ILSpy | dnSpyEx |
|---|---|---|
| 성격 | 가볍고 빠른 읽기 전용 뷰어 | 디컴파일러 + 디버거 + 라이브 편집기 |
| 디버깅 | 불가능 | 가능(브레이크포인트, 스텝 실행) |
| 코드 수정 후 즉시 재실행 | 불가능 | 가능(Edit Method → Compile) |
| 실행 속도/가벼움 | 더 빠름 | 상대적으로 무거움 |
| 원조 | icsharpcode/ILSpy | dnSpy(관리 중단)의 커뮤니티 후속 포크 |

실전에서는 먼저 ILSpy로 빠르게 구조를 훑고, 값을 바꿔가며 실행까지 확인해야 하는 순간(검증 로직 우회 실습 등)에 dnSpyEx로 넘어가는 흐름이 자연스럽다.

## 가장 먼저 할 것
두 도구 모두 공식 GitHub 릴리스 페이지에서 최신 버전의 압축 파일을 받아, 압축을 풀고 실행 파일을 더블클릭하는 것으로 설치가 끝난다. 대회 전 이 과정을 미리 완료해서 오프라인 상태에서도 바로 열리는지 확인해 둔다.

## 단계별 절차

### 1) ILSpy 설치
공식 GitHub 저장소(`https://github.com/icsharpcode/ILSpy/releases`)에서 자신의 .NET 실행 환경에 맞는 배포판을 받는다.
- **ILSpy(WPF, 자체 포함형)**: `.zip`으로 압축을 풀면 바로 실행 가능한 독립 실행형 배포가 제공되는 경우가 많아, 별도 .NET 런타임 설치 없이 바로 쓸 수 있는 버전을 우선 받는 것이 오프라인 환경에 유리하다.
- 실행 파일(`ILSpy.exe`)을 더블클릭하면 바로 뜬다. 설치 마법사가 없으므로 원하는 폴더에 압축을 풀어두고 그 폴더째 오프라인 대회용 USB/외장 SSD로 복사해 가면 된다.

### 2) dnSpyEx 설치
공식 GitHub 저장소(`https://github.com/dnSpyEx/dnSpy/releases`)에서 최신 릴리스의 `.zip` 파일을 받는다.
```text
dnSpy-net-win64.zip  (또는 유사한 이름의 x64 빌드)
```
압축을 풀면 `dnSpy.exe`가 들어있는 폴더가 나온다. 이 역시 설치 프로그램 없이 압축 해제만으로 실행 가능한 포터블 배포이며, 오프라인 대회용 매체에 폴더째 복사해 두면 된다.

### 3) 실행 확인
두 도구 모두 다음을 확인해서 정상 설치됐는지 검증한다.
1. 실행 파일을 더블클릭했을 때 창이 뜨는가.
2. 아무 `.NET` 어셈블리(간단한 테스트용 `.exe`)를 `File → Open`으로 열었을 때 좌측 트리에 클래스/메서드 목록이 나타나는가.
3. dnSpyEx의 경우, 테스트 어셈블리에 `F5`로 디버그 세션을 시작했을 때 정상적으로 실행되는가(방화벽/보안 소프트웨어가 디버거 동작을 막는 경우가 있으므로 대회 전 미리 확인 필요).

### 4) 필요한 .NET 런타임 확인
받은 배포판이 "자체 포함형(self-contained)"이 아니라면, 대상 PC에 해당 .NET 버전의 런타임이 설치되어 있어야 도구 자체가 실행된다. 오프라인 대회 PC에 어떤 .NET 런타임이 이미 깔려있는지 모른다면, 가능한 한 자체 포함형 배포판을 우선 받아 이 문제를 아예 피하는 것이 안전하다.

## 명령어/단축키
설치 자체에는 커맨드라인 명령이 필요 없다. 실행 후 공통적으로 알아둘 것만 정리한다.
```text
File → Open (Ctrl+O)     어셈블리 열기 (양쪽 공통)
드래그 앤 드롭             파일을 창에 끌어놓아도 열림 (양쪽 공통)
```
세부 검색/디버깅 단축키는 각 도구의 사용법 문서(REV-0243, REV-0244)에서 다룬다.

## 흔한 실수
- 두 도구를 "같은 것의 다른 이름"이라고 착각해서 디버깅이 필요한 상황에 ILSpy만 계속 붙잡고 있는 것 — ILSpy는 애초에 디버거가 없다.
- 오프라인 대회 당일 처음 압축을 풀어보다가, 대상 PC에 필요한 .NET 런타임이 없어서 실행 자체가 안 되는 것을 뒤늦게 발견하는 것 — 반드시 사전에 실제 대회용 환경(또는 최대한 비슷한 환경)에서 실행까지 검증해야 한다.
- dnSpyEx를 관리자 권한 없이 실행해서 일부 프로세스에 디버거를 붙이지 못하는 것 — 대상 프로세스의 권한에 따라 dnSpyEx를 관리자 권한으로 실행해야 할 수 있다.
- 원조 `dnSpy`(관리 중단된 프로젝트)의 오래된 배포본을 잘못 받아 최신 .NET(Core/5+)으로 컴파일된 어셈블리를 열지 못하는 것 — 반드시 `dnSpyEx`(커뮤니티 포크) 저장소에서 받아야 한다.

## 막혔을 때 다음 체크
- 이 파일이 .NET인지 자체가 불확실하면 → REV-0242 (.NET 바이너리 식별과 첫 접근, dotnet-android 카테고리)
- ILSpy 화면 구성과 검색/Export 사용법 → [ILSpy 기본 사용법](../dotnet-android/rev-0244-ilspy-basics.md)
- dnSpyEx 디버깅/라이브 패치 사용법 → [dnSpyEx로 .NET EXE 열기](../dotnet-android/rev-0243-dnspyex-basics.md)

## 미니 예제
`dnSpyEx.exe` 실행 → `File → Open` → 대상 `.exe`/`.dll` 선택 → Assembly Explorer 트리에서 `<모듈명> → 네임스페이스 → 클래스 → Main()` 더블클릭하면 바로 디컴파일된 C#이 뜬다. ILSpy도 동일한 흐름(`Open` → 트리 탐색)이며, 차이는 ILSpy는 읽기 전용 뷰어에 가깝고 dnSpyEx는 그 자리에서 F5로 실행/디버깅까지 가능하다는 점이다.

## 관련 글
- REV-0300 — Z3 angr pwntools Python 오프라인 패키지 준비
- REV-0299 — JADX apktool adb 설치와 사용법

## 출처/검증
- 배포 형태(설치 프로그램 없는 zip 포터블 배포)와 저장소 위치: ILSpy 공식 GitHub 저장소(icsharpcode/ILSpy)와 dnSpyEx 공식 GitHub 저장소(dnSpyEx/dnSpy)의 Releases 페이지 기준.
- dnSpy(원조)와 dnSpyEx(커뮤니티 포크)의 관계: 각 프로젝트 README의 프로젝트 이력 설명 기준(이 저장소의 REV-0243에서도 동일하게 확인됨).
- 이 문서의 설치 절차는 실제 파일 다운로드/실행으로 재현 검증하지 못했다. 릴리스 파일명, 자체 포함형 여부는 버전에 따라 바뀔 수 있으므로 오프라인 키트 준비 시 최신 릴리스 페이지에서 실제 파일명을 다시 확인할 것.
