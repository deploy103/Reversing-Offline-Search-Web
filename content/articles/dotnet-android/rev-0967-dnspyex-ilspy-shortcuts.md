---
id: REV-0967
title: "dnSpyEx/ILSpy 단축키 빠른 참조"
slug: "rev-0967-dnspyex-ilspy-shortcuts"
category: "dotnet-android"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [dnSpyEx, ILSpy]
keywords: ["dnSpyEx 단축키", "ILSpy 단축키", "F9 breakpoint", "Go to Entry Point", "Analyze Uses Used By", "F11 F10 F5 디버깅"]
aliases: ["dnSpyEx 키보드 단축키", "ILSpy 단축키 표", "dnSpyEx 디버깅 단축키", "닷넷 디컴파일러 단축키"]
symptom_keywords: ["dnSpyEx 단축키를 모르겠다", "F11이 뭔지 모르겠다", "Analyze 단축키가 뭔지 모르겠다", "ILSpy 검색 단축키를 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
dnSpyEx와 ILSpy는 둘 다 Visual Studio 스타일의 디버깅/탐색 단축키(F5/F9/F10/F11)를 공유하지만, dnSpyEx만 실행 중인 프로세스에 실제로 브레이크포인트를 걸고 값을 바꿀 수 있는 반면 ILSpy는 순수 디컴파일/탐색 전용이라는 차이를 알아두면 어느 도구에서 어떤 단축키를 써야 할지 헷갈리지 않는다.

## 언제 검색해야 하나
- dnSpyEx에서 브레이크포인트를 걸고 싶은데 단축키를 몰라 매번 메뉴를 클릭할 때
- ILSpy/dnSpyEx에서 특정 멤버가 어디서 호출되는지(Analyze) 찾는 단축키를 모를 때
- 트리에서 타입/멤버 이름으로 빠르게 검색하는 단축키를 모를 때
- Step Into/Step Over/Step Out 단축키가 헷갈릴 때
- 여러 창(Locals, Watch, Call Stack, Modules)을 여는 단축키를 몰라 매번 메뉴를 뒤질 때

## 핵심 개념
두 도구 모두 원본이 ILSpy 코드베이스에서 파생되었거나(dnSpyEx는 dnSpy의 후속 포크) 같은 계열이라 트리 탐색, 검색, 디컴파일 언어 전환 단축키가 거의 동일하다. 차이는 **디버거 유무**다. dnSpyEx는 실행 파일을 실제로 시작하거나 실행 중인 프로세스에 attach해서 라이브 디버깅(브레이크포인트, 스텝 실행, 로컬 변수 확인, 메서드 본문 즉석 수정 후 핫패치)이 가능하고, ILSpy는 정적 디컴파일과 어셈블리 탐색/검색에 특화되어 있어 F5/F9/F11 같은 디버그 계열 단축키 자체가 없다.

## 화면/코드에서 보이는 징후
메뉴의 `Debug`, `View`, `Edit`, `File` 항목 옆에 단축키 조합이 회색 글씨로 표기되어 있으므로, 메뉴를 한 번씩 열어보며 확인할 수도 있다.

## 가장 먼저 할 것
분석 초반에는 `Ctrl+Shift+K`(멤버 이름 검색)와 `Ctrl+Shift+F`(전체 텍스트/문자열 검색)부터 눌러보는 습관을 들인다. 트리를 손으로 펼쳐가며 찾는 것보다 압도적으로 빠르다.

## 단계별 절차
1. 어셈블리를 로드한 뒤 `Ctrl+Shift+K`로 클래스/메서드 이름 검색부터 시작한다.
2. 의심 문자열이 있다면 `Ctrl+Shift+F`로 전체 어셈블리에서 문자열 검색을 수행한다.
3. 특정 메서드를 찾았으면 `Alt+F12`(또는 우클릭 Analyze)로 Uses/Used By를 확인해 호출 그래프를 넓힌다.
4. dnSpyEx라면 의심 지점에 `F9`로 브레이크포인트를 걸고 `F5`로 실행, `F10`/`F11`로 한 줄씩 따라간다.
5. 실행 중 값은 `Debug` 메뉴의 `Windows` 하위 항목(`Alt+4` Locals 등)으로 연 창에서 확인한다.

## 명령어/단축키
```text
[공통 - 탐색/검색]
Ctrl+Shift+K       멤버(타입/메서드/필드) 이름으로 검색
Ctrl+Shift+F       전체 어셈블리에서 문자열/텍스트 검색
Ctrl+F             현재 열린 코드 창 안에서 검색
F12                정의로 이동(Go to Definition)
Ctrl+F12           선언으로 이동
Alt+F12            Analyze 창 열기(Uses / Used By)
Ctrl+Alt+Left/Right  뒤로/앞으로(탐색 히스토리 이동)
Ctrl+E             언어 콤보(디컴파일 대상 언어: C#/IL/VB 등) 전환 포커스

[공통 - 편집/보기]
F2                 트리 항목 Rename
Ctrl+Shift+C       역참조 코드 복사
Ctrl+O             모듈/어셈블리 열기

[dnSpyEx 전용 - 디버깅]
F5                 디버깅 시작 / 계속 실행(Continue)
Shift+F5           디버깅 중지
Ctrl+F5            디버거 없이 실행
F9                 현재 줄에 브레이크포인트 토글
F10                Step Over(한 줄 실행, 호출 내부로 안 들어감)
F11                Step Into(호출 내부로 들어감)
Shift+F11          Step Out(현재 함수에서 빠져나감)
Ctrl+Shift+F9      모든 브레이크포인트 삭제
Alt+4              Locals 창
Alt+7              Call Stack 창
Ctrl+Alt+B         Breakpoints 창
Ctrl+D,E           Modules 창
```

## 출력 해석
- `Alt+F12`(Analyze)에서 **Used By**가 비어 있으면 그 메서드는 어디서도 직접 호출되지 않는 죽은 코드이거나, 리플렉션([REV-0969](./rev-0969-dotnet-reflection-obfuscation.md) 참고)으로만 간접 호출되는 코드일 수 있다.
- dnSpyEx에서 `F11`(Step Into)을 눌렀는데 외부 프레임워크 DLL 안으로 들어가 버리면, 대개 심볼/소스가 없는 BCL 코드이므로 `Shift+F11`(Step Out)로 바로 빠져나오는 게 낫다.
- `Ctrl+Shift+F` 검색 결과가 하나도 없다면 문자열이 암호화되어 있을 가능성이 크다([REV-0971](./rev-0971-dotnet-string-encryption-traces.md) 참고).

## 흔한 실수
- ILSpy에서 `F9`/`F5` 같은 디버그 단축키를 눌러도 반응이 없다고 당황하는 것 — ILSpy는 애초에 라이브 디버거가 없는 도구다. 디버깅이 필요하면 dnSpyEx로 전환해야 한다.
- `F10`(Step Over)과 `F11`(Step Into)의 차이를 헷갈려서, 호출한 함수 내부를 보고 싶은데 계속 `F10`만 눌러 그냥 지나쳐버리는 것.
- `Ctrl+Shift+K` 검색 결과가 너무 많이 나올 때 필터(타입만/메서드만 등) 옵션을 안 써서 원하는 항목을 못 찾고 스크롤만 하는 것.
- Rename(`F2`)으로 임시 이름을 붙인 뒤 저장(모듈 저장)까지 해버려서 원본 파일을 실수로 덮어쓰는 것 — 분석은 항상 사본에서 진행해야 한다.

## 막혔을 때 다음 체크
- dnSpyEx로 처음 파일을 여는 기본 절차 자체가 궁금하면 → [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)
- ILSpy 기본 사용법이 궁금하면 → [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)
- Analyze로 찾은 호출 그래프를 IL 레벨까지 더 깊이 보고 싶으면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)

## 미니 예제
`Crackme.exe`를 dnSpyEx로 열고 `Ctrl+Shift+K`를 눌러 `Check`를 검색하니 `CheckLicense(string)` 메서드 하나가 나온다. 더블클릭해 코드로 이동한 뒤, 조건문이 있는 줄 번호에 마우스를 놓고 `F9`를 눌러 브레이크포인트를 건다. 이어서 `F5`로 앱을 실행하고 입력값을 넣으면 그 줄에서 실행이 멈춘다. `Alt+4`로 Locals 창을 열어 지역 변수 값을 확인하고, `F10`으로 한 줄씩 내려가며 어느 분기로 빠지는지 관찰한다. 검증에 사용되는 다른 클래스의 메서드가 궁금해지면 그 메서드 이름 위에서 `Alt+F12`를 눌러 Uses/Used By를 확인해 호출 관계를 넓혀간다.

## 관련 글
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0244 — ILSpy 기본 사용법
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0969 — .NET 리플렉션(Reflection) 기반 난독화 알아보기
- REV-0971 — .NET 문자열 암호화 흔적 알아보기

## 출처/검증
- dnSpyEx 단축키 목록은 dnSpyEx 공식 GitHub 저장소(`dnSpyEx/dnSpy`) 문서 및 기본 키 바인딩 설정 기준으로 정리했다.
- ILSpy 단축키 목록은 ILSpy 공식 GitHub 저장소(`icsharpcode/ILSpy`) 문서 기준으로 정리했다.
- dnSpyEx의 라이브 디버깅 기능과 ILSpy의 정적 디컴파일 전용 특성 구분은 두 프로젝트의 공식 README/위키 설명을 기준으로 확인했다 (2026-09-09 확인).
