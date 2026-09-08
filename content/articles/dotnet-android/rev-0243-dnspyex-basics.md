---
id: REV-0243
title: "dnSpyEx로 .NET EXE 열기"
slug: "rev-0243-dnspyex-basics"
category: "dotnet-android"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["dnSpyEx"]
keywords: ["dnSpyEx 사용법", "dnSpyEx 디버거", "Edit Method C#", ".NET 라이브 패치", "dnSpyEx 단축키", "dnSpyEx Main 찾기"]
aliases: ["dnSpyEx란", "dnSpy 후속 프로젝트", "dnSpyEx 설치", "dnSpyEx 디버깅 방법", ".NET exe 실시간 패치"]
symptom_keywords: ["dnSpyEx를 처음 켰는데 뭘 눌러야 할지 모름", "dnSpyEx에서 Main 함수를 못 찾음", "dnSpyEx로 코드를 고치고 싶은데 방법을 모름", "dnSpyEx 디버거를 어떻게 켜는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**dnSpyEx**는 원조 dnSpy가 관리 중단된 뒤 커뮤니티가 이어받은 후속 프로젝트로, .NET 어셈블리를 C# 코드로 디컴파일해서 보여줄 뿐 아니라 **디버거를 내장**하고 있고, 심지어 메서드를 우클릭해서 **"Edit Method (C#)"로 코드를 직접 고쳐 즉시 반영**할 수 있는, .NET 리버싱에서 가장 강력한 만능 도구다.

## 언제 검색해야 하나
- dnSpyEx를 처음 설치하고 실행했는데 화면 구성이 낯설어서 어디서부터 봐야 할지 모를 때
- 어셈블리를 열었지만 `Main` 메서드나 특정 클래스를 어떻게 찾아야 하는지 모를 때
- 특정 문자열이나 메서드 이름으로 코드를 검색하고 싶은데 방법을 모를 때
- CTF 문제에서 "이 검증 로직을 우회해서 통과 메시지를 보라"는 식의 실습을 할 때 실제로 코드를 고쳐서 다시 실행해보고 싶은데 방법을 모를 때
- 브레이크포인트를 걸고 실행 중 변수 값을 확인하고 싶은데 dnSpyEx 디버거 사용법을 모를 때

## 핵심 개념

### dnSpyEx는 무엇이고 dnSpy와 무슨 관계인가
원조 `dnSpy`는 .NET 디컴파일러 겸 디버거로 오랫동안 사실상 표준 도구였지만 2020년 이후 개발이 멈췄다. 이후 커뮤니티가 `dnSpyEx`라는 이름으로 포크해서 최신 .NET(Core/5/6/7/8+) 지원, 버그 수정, UI 개선을 이어가고 있다. 사용법과 화면 구성은 원조 dnSpy와 거의 동일하므로, 예전 dnSpy 자료를 보고 배워도 대부분 그대로 적용된다. 이 글에서는 별도 표기가 없는 한 dnSpyEx 최신 버전 기준으로 설명한다.

### 화면 구성 한눈에 보기
dnSpyEx를 실행하면 기본적으로 다음과 같은 영역으로 나뉜다.
- **좌측 Assembly Explorer** — 열린 어셈블리들을 트리 형태로 보여준다. 어셈블리 → 네임스페이스 → 클래스 → 메서드/필드/프로퍼티 순으로 계층 구조가 펼쳐진다.
- **중앙 코드 뷰(탭 영역)** — 선택한 메서드나 클래스를 디컴파일된 C# 코드로 보여준다. 상단 언어 선택 드롭다운에서 C#, VB, IL(원문 CIL) 중 표시 방식을 바꿀 수 있다.
- **하단 Output/Log 창** — 디버깅 중 출력이나 오류 메시지가 표시된다.
- **디버깅 시 추가 창** — `Locals`(지역변수), `Breakpoints`, `Call Stack`, `Watch` 창이 나타나며, 값을 실시간으로 확인/수정할 수 있다.

### "읽기 전용 열람"과 "실행하며 분석"의 차이를 이해하기
dnSpyEx는 크게 두 가지 모드로 쓰인다. 첫째는 ILSpy처럼 파일을 열고 코드만 읽는 정적 열람 모드고, 둘째는 실제로 프로그램을 실행시키면서 브레이크포인트로 멈추고 변수를 들여다보는 동적 디버깅 모드다. 초심자가 자주 헷갈리는 지점은 "그냥 열기(더블클릭/드래그)"와 "디버그로 시작(F5)"이 서로 다른 동작이라는 것이다. 전자는 코드를 읽기만 하고, 후자는 실제로 프로세스를 띄워서 실행한다.

## 화면/코드에서 보이는 징후
- Assembly Explorer 트리 최상단에 어셈블리 이름(예: `Crackme.exe`)이 있고, 그 아래 `References`(참조 DLL 목록)와 실제 네임스페이스/모듈이 나열된다.
- 클릭한 메서드 코드 상단에 `.method public hidebysig static ...` 같은 IL 시그니처 주석이 붙어 있을 수 있다(옵션에 따라 다름).
- 디버깅 중 브레이크포인트가 걸린 줄은 빨간 점, 현재 실행 중인 줄은 노란 화살표로 표시된다.

## 가장 먼저 할 것
dnSpyEx를 실행한 뒤 `File → Open` (또는 창에 파일을 드래그 앤 드롭)으로 대상 `.exe`를 연다. 그다음 Assembly Explorer 트리에서 어셈블리 노드를 펼쳐(`▶` 클릭 또는 화살표 키) 네임스페이스 → 클래스 순으로 내려가며, 보통 `Program` 클래스 안에 있는 `Main` 메서드를 먼저 찾아 클릭한다. 대부분의 콘솔/WinForms 프로그램은 `Main`이 진입점이므로 여기서부터 코드 흐름을 따라가면 된다.

## 단계별 절차

**1) 어셈블리 열기**
`File → Open` (단축키 `Ctrl+O`)을 누르고 대상 `.exe` 또는 `.dll` 파일을 선택한다. 여러 파일을 동시에 열 수도 있다.

**2) Assembly Explorer에서 Main 찾기**
좌측 트리에서 어셈블리 이름을 펼치고, 보통 어셈블리 이름과 같은 네임스페이스 아래의 `Program` 클래스를 찾는다. 그 안에 `Main(string[] args)` 메서드가 진입점이다. 빠르게 찾으려면 어셈블리 노드를 우클릭 → **Go to Entry Point**를 사용하면 즉시 진입점 메서드로 이동한다.

**3) 이름으로 검색하기**
`Ctrl+Shift+K` (또는 상단 메뉴 `Edit → Search Assemblies`)로 검색창을 열고, 클래스명/메서드명 일부를 입력하면 일치하는 항목이 실시간으로 나열된다. 검색 대상 범위(Type, Method, Field, Property, Event, Resource 등)를 상단 필터로 좁힐 수 있다.

**4) 문자열로 검색하기**
검색창에서 필터를 `String`으로 바꾸면 어셈블리 안의 모든 문자열 리터럴을 대상으로 검색할 수 있다. 플래그, 비밀번호 후보, 오류 메시지 등을 찾을 때 유용하다. 문자열을 더블클릭하면 해당 문자열이 사용된 IL 위치로 바로 이동한다.

**5) 코드 읽기 모드 전환**
상단 도구모음이나 우클릭 메뉴에서 표시 언어를 C#, IL(원문 CIL), VB 등으로 바꿀 수 있다. 디컴파일이 이상하게 나오면 IL 원문 모드로 바꿔서 실제 바이트코드를 직접 확인한다([REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md) 참고).

**6) 브레이크포인트 걸고 디버깅 시작**
확인하고 싶은 코드 줄의 왼쪽 여백을 클릭하면 빨간 점(브레이크포인트)이 생긴다. 그 상태에서 `F5` 또는 `Debug → Start` 를 누르면 dnSpyEx가 프로그램을 실행시키고, 브레이크포인트에 도달하면 실행이 멈춘다. 이때 `Locals` 창에서 현재 지역변수 값을, `Watch` 창에서 특정 표현식 값을 확인할 수 있다.

**7) 스텝 실행으로 흐름 따라가기**
`F10`(Step Over, 현재 줄 실행 후 다음 줄로), `F11`(Step Into, 호출된 메서드 내부로 진입), `Shift+F11`(Step Out, 현재 메서드에서 빠져나오기)로 한 줄씩 흐름을 따라가며 조건 분기가 어느 쪽으로 가는지 직접 확인한다.

**8) 메서드를 직접 고쳐서 라이브 패치하기 (CTF/교육용)**
검증 로직을 확인만 하는 게 아니라 실제로 우회 동작을 실습해보고 싶다면, 해당 메서드를 우클릭 → **Edit Method (C#)** 를 선택한다. 팝업 편집창이 뜨고 여기서 C# 코드를 자유롭게 고칠 수 있다(예: `if (input == correctKey)`를 `if (true)`로 바꾸기). `Compile`(또는 `Ctrl+Shift+B` 계열 단축키, 버전에 따라 다름)을 누르면 dnSpyEx가 내부적으로 수정한 C#을 다시 IL로 컴파일해서 메모리상의 메서드를 즉시 교체한다. 이후 `File → Save Module...`로 실제 `.exe` 파일에 패치를 저장할 수도 있다. 이 기능은 CTF/워게임에서 검증 로직을 직접 눈으로 이해하고, 교육 목적으로 "코드를 이렇게 고치면 통과 조건이 이렇게 바뀐다"는 것을 확인하는 용도로 사용한다.

## 명령어/단축키
```text
Ctrl+O            어셈블리 열기
Ctrl+Shift+K       타입/메서드/문자열 검색창 열기
F5                 디버그 시작
F9                 현재 줄에 브레이크포인트 토글
F10                Step Over
F11                Step Into
Shift+F11          Step Out
Ctrl+Shift+F5      디버그 재시작
Shift+F5           디버그 중지
우클릭 메서드 → Edit Method (C#)   메서드 코드 직접 편집(라이브 패치)
우클릭 어셈블리 → Go to Entry Point   Main 등 진입점으로 즉시 이동
```

## 출력 해석
- `Locals` 창에 표시된 변수 값이 예상과 다르면, 그 값이 어디서 조립되는지 상위 호출을 따라 올라가며 확인해야 한다.
- `Edit Method (C#)` 에서 `Compile` 시 오류가 나면 대개 편집한 코드가 원래 메서드 시그니처(반환 타입, 매개변수 개수)와 맞지 않거나 존재하지 않는 지역변수/타입을 참조했기 때문이다. 오류 메시지에 나온 줄 번호를 먼저 확인한다.
- 디버깅 중 브레이크포인트에 전혀 걸리지 않는다면, 해당 메서드가 JIT 최적화로 인라인되었거나 다른 어셈블리(예: 지연 로드되는 플러그인 DLL)에 있는 코드일 수 있다.

## 흔한 실수
- "그냥 열기"만 하고 F5로 디버그 시작을 하지 않은 채 브레이크포인트가 안 걸린다고 착각하는 것. 브레이크포인트는 반드시 디버그 세션이 실행 중일 때만 동작한다.
- Edit Method (C#)에서 코드를 고친 뒤 `Compile`을 누르지 않고 바로 실행해서 "패치가 안 먹힌다"고 오해하는 것.
- Assembly Explorer에서 `References`(참조 DLL)까지 전부 펼쳐보려다가 트리가 너무 커져서 정작 찾아야 할 자기 코드(`Program`, 자체 네임스페이스)를 놓치는 것. 검색 기능(`Ctrl+Shift+K`)을 적극적으로 쓰는 편이 빠르다.
- 원본 파일을 직접 열어 패치하고 저장(`Save Module`)해서 원본을 덮어써버리는 것. 항상 사본을 만들어두고 작업하는 습관을 들여야 한다.

## 막혔을 때 다음 체크
- 애초에 이 파일이 .NET인지부터 다시 확인하고 싶으면 → [REV-0242 .NET 바이너리 식별과 첫 접근](./rev-0242-dotnet-identification.md)
- 디버깅 없이 빠르게 코드만 훑고 싶으면 → [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)
- 디컴파일이 깨져서 IL 원문을 읽어야 하면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 이름이 죄다 난독화되어 검색이 잘 안 되면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 리소스/문자열 테이블을 더 체계적으로 뒤지고 싶으면 → [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)

## 미니 예제
`Crackme.exe`를 dnSpyEx로 연다. Assembly Explorer에서 어셈블리를 우클릭 → **Go to Entry Point**를 누르면 곧바로 `Program.Main(string[])`으로 이동한다. 코드를 보니 다음과 같은 구조다.

```csharp
static void Main(string[] args)
{
    Console.Write("Enter key: ");
    string input = Console.ReadLine();
    if (CheckKey(input))
        Console.WriteLine("Correct!");
    else
        Console.WriteLine("Wrong!");
}
```

`CheckKey`를 더블클릭해서 이동하면 내부에서 문자열을 비교하는 로직이 보인다. 여기서 `CheckKey`를 우클릭 → **Edit Method (C#)** 을 선택하고, 본문을 `return true;` 한 줄로 바꾼 뒤 `Compile`을 누른다. 이제 `F5`로 디버그를 시작해서 아무 값이나 입력해도 "Correct!"가 출력되는 것을 직접 확인할 수 있다. 이런 실습은 검증 로직이 정확히 어떤 조건으로 통과/실패를 가르는지 확인하는 CTF 학습용 우회 실습에 해당한다.

## 관련 글
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0244 — ILSpy 기본 사용법
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0247 — .NET 난독화 기초

## 출처/검증
- dnSpyEx 기능(Assembly Explorer, 디버거, Edit Method, Search) 및 단축키: dnSpyEx 공식 GitHub 저장소(dnSpyEx/dnSpy) 문서/위키 기준 (2026-09-08 확인).
- dnSpy와 dnSpyEx의 관계(원조 프로젝트 관리 중단 후 커뮤니티 포크): 각 프로젝트 GitHub README의 프로젝트 이력 설명 기준.
