---
id: REV-0978
title: "ILSpy에서 참조 어셈블리를 못 찾을 때"
slug: "rev-0978-ilspy-reference-assembly-missing"
category: "dotnet-android"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [ILSpy]
keywords: ["ILSpy 참조 어셈블리 못 찾음", "Could not find assembly", "ILSpy References 빨간 X", "ILSpy 어셈블리 검색 경로", ".NET 참조 DLL 누락"]
aliases: ["ILSpy DLL 못 찾음", "ILSpy references 오류", "ILSpy 타입 해석 실패", "ILSpy assembly resolve 실패"]
symptom_keywords: ["References 트리에 빨간 표시가 뜸", "타입이 unknown으로 나옴", "Could not find assembly 메시지", "ILSpy에서 상속 관계가 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ILSpy가 대상 어셈블리는 정상적으로 열었는데 `References` 트리에 빨간 표시가 뜨거나 코드에 `unresolved type`류의 표기가 보인다면, 그건 파일이 손상된 게 아니라 이 어셈블리가 참조하는 다른 DLL(커스텀 라이브러리나 특정 프레임워크 버전)을 ILSpy가 검색 경로 안에서 찾지 못했기 때문이다.

## 언제 검색해야 하나
- ILSpy의 `References` 트리 노드에 경고 아이콘이나 빨간 X 표시가 붙어 있을 때
- 디컴파일된 코드에서 부모 클래스나 인터페이스 이름이 온전한 타입명 대신 이상하게 표기될 때
- 특정 메서드의 매개변수 타입이 낯선 커스텀 DLL에 정의된 타입이라 코드가 제대로 안 풀릴 때
- 앱이 여러 DLL로 나뉘어 있는데 딱 하나의 EXE/DLL만 ILSpy에 던져놓고 열었을 때

## 핵심 개념
.NET 어셈블리는 필요한 다른 어셈블리(예: 자체 제작 라이브러리 DLL, 특정 버전의 NuGet 패키지, 특정 버전의 .NET 런타임 참조 어셈블리)의 이름과 버전 정보만 메타데이터에 기록해두고, 실제 그 DLL의 바이트를 자기 안에 포함하지는 않는다. 이걸 어셈블리 참조(assembly reference)라고 한다. ILSpy는 열려 있는 어셈블리 목록과 프레임워크 기본 참조 경로 정도만 자동으로 뒤져서 참조를 해석하려 시도하는데, 대상 프로그램이 배포된 폴더 전체(같은 폴더의 커스텀 DLL들)를 통째로 열지 않고 EXE 파일 하나만 달랑 열면 그 안의 커스텀 타입을 찾을 참조 어셈블리가 없어 해석이 실패한다.

이 문제는 파일 손상이나 ILSpy 버그가 아니라, "이 프로그램을 이해하려면 원래 배포 폴더에 있던 DLL들이 전부 필요하다"는 아주 자연스러운 의존성 문제다.

## 화면/코드에서 보이는 징후
- `References` 노드 아래 특정 항목에 경고 아이콘이 붙어 있다.
- 코드에서 부모 클래스가 `?` 나 완전 정규화되지 않은 이상한 이름으로 나온다.
- 특정 메서드 시그니처의 매개변수/반환 타입에 물음표나 원래 이름과 다른 placeholder가 보인다.
- 상태 표시줄이나 로그에 `Could not find assembly 'CustomLib, Version=...'` 류의 메시지가 뜬다.

## 가장 먼저 할 것
대상 EXE/DLL이 있던 원래 폴더 전체를 확인한다. 보통 같은 폴더 안에 `.deps.json`, 여러 개의 `.dll` 파일이 함께 있을 텐데, 이걸 전부 무시하고 실행 파일 하나만 ILSpy에 던져 넣었는지부터 점검한다.

## 단계별 절차
1. 대상 파일이 있던 배포 폴더 전체를 확인해서 함께 있는 모든 `.dll` 파일 목록을 파악한다.
2. ILSpy `File → Open`에서 EXE뿐 아니라 같은 폴더의 관련 DLL들도 함께(다중 선택으로) 연다.
3. 트리에서 여전히 경고가 남은 참조가 있다면, 그 참조의 이름/버전을 확인하고 시스템에 설치된 .NET 런타임/SDK 참조 어셈블리 폴더에서 같은 이름의 DLL이 있는지 찾아본다.
4. NuGet 패키지 참조라면, 프로젝트가 사용한 NuGet 캐시 폴더(`~/.nuget/packages` 등)에서 해당 버전을 찾아 함께 열 수도 있다.
5. 그래도 해석이 안 되는 참조는 대개 실행에 필요하지만 리버싱 목표(핵심 로직 파악)에는 중요하지 않은 프레임워크 하위 의존성인 경우가 많으므로, 어떤 타입이 실제로 안 풀리는지 먼저 확인하고 우선순위를 정한다.

## 명령어/단축키
```text
File → Open (다중 선택)     여러 DLL을 한 번에 열기
우클릭 References → ...     참조 상세 확인(버전에 따라 메뉴명 다름)
Ctrl+T                       열린 모든 어셈블리 대상 타입/문자열 검색
```

## 출력 해석
- 경고 아이콘이 붙은 참조 이름과 버전을 그대로 기록해두면, 어떤 DLL을 추가로 구해야 하는지 명확해진다.
- 코드에서 타입이 완전히 깨지지 않고 이름만 나온다면, 실제 멤버 목록(필드/메서드)까지는 몰라도 호출 관계 정도는 여전히 유추 가능한 경우가 많다.
- 여러 참조 중 시스템 프레임워크 DLL(`System.*`, `Microsoft.*`)이 안 풀리는 경우는 대부분 무시해도 핵심 로직 분석에는 지장이 없다.

## 흔한 실수
- 배포 폴더의 DLL들을 다 무시하고 EXE 파일 하나만 열어서 "왜 코드가 이상하게 나오지"라고 착각하는 것.
- 참조 어셈블리 경고를 파일 손상 신호로 오해해서 처음부터 다시 파일을 구하러 다니는 것.
- 시스템 프레임워크 DLL 참조 경고까지 전부 해결하려고 시간을 쏟는 것 — 핵심 로직에 필요한 커스텀 DLL만 먼저 확보하면 충분한 경우가 대부분이다.

## 막혔을 때 다음 체크
- 그래도 특정 메서드 코드 자체가 안 보이면(디컴파일 실패) → REV-0977 dnSpyEx가 어셈블리를 디컴파일하지 못할 때
- IL 원문을 직접 봐야 한다면 → REV-0245 CIL IL 명령어를 C#과 연결해서 읽기
- 애초에 어떤 파일부터 열어야 할지 모르겠으면 → REV-0242 .NET 바이너리 식별과 첫 접근

## 미니 예제
`GameLauncher.exe`를 ILSpy에 열었더니 `References` 아래 `GameCore, Version=1.2.0.0`에 경고 아이콘이 붙어 있었다. `Program` 클래스의 한 메서드 매개변수가 `GameCore.SaveData` 타입인데, 이 타입 정의를 볼 수 없어 필드 목록이 비어 보였다. 원래 배포 폴더를 확인해보니 `GameLauncher.exe` 옆에 `GameCore.dll`이 함께 있었고, 이를 ILSpy에 추가로 열자 `SaveData` 타입의 실제 필드와 프로퍼티가 정상적으로 펼쳐졌다.

## 관련 글
- REV-0977 — dnSpyEx가 어셈블리를 디컴파일하지 못할 때
- REV-0244 — ILSpy 기본 사용법
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기

## 출처/검증
- 어셈블리 참조 해석 방식과 배포 폴더 의존성 개념은 .NET 공식 문서("Assembly resolution", "Managing dependencies")를 기준으로 정리했다(2026-09-09 확인).
- ILSpy의 References 트리 및 타입 해석 실패 표시는 ILSpy 공식 GitHub 저장소(icsharpcode/ILSpy) 문서 기준.
