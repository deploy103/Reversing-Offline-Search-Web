---
id: REV-0244
title: "ILSpy 기본 사용법"
slug: "rev-0244-ilspy-basics"
category: "dotnet-android"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["ILSpy"]
keywords: ["ILSpy 사용법", "ILSpy 단축키", "ILSpy Export Assembly", "ILSpy Main 찾기", "ILSpy 검색", ".NET 디컴파일러"]
aliases: ["ILSpy란", "ILSpy 설치", "ILSpy 트리 구조", "ILSpy 프로젝트 export", ".NET 소스 복원 도구"]
symptom_keywords: ["ILSpy를 처음 켰는데 뭘 봐야할지 모름", "ILSpy에서 Main 함수를 못 찾음", "ILSpy 검색 기능을 어떻게 쓰는지 모름", "ILSpy로 프로젝트를 통째로 저장하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**ILSpy**는 .NET 어셈블리를 열어 C#/IL/VB 코드로 즉시 디컴파일해서 보여주는 가볍고 빠른 읽기 전용 도구로, 디버거는 없지만 트리 탐색·검색·프로젝트 export가 강력해서 ".NET 코드를 빠르게 읽기만 하면 되는" 대부분의 상황에서 가장 먼저 켜야 할 도구다.

## 언제 검색해야 하나
- ILSpy를 처음 실행했는데 화면 구성이 낯설어서 어디를 봐야 할지 모를 때
- 열어놓은 어셈블리에서 `Main` 메서드나 특정 클래스를 빠르게 찾고 싶을 때
- 여러 클래스에 걸쳐 특정 메서드 이름이나 문자열이 어디서 쓰이는지 검색하고 싶을 때
- 디컴파일된 코드를 Visual Studio 같은 IDE에서 통째로 열어보고 싶어서 프로젝트로 export하는 방법이 궁금할 때
- dnSpyEx까지는 필요 없고 그냥 코드만 빠르게 읽고 싶을 때

## 핵심 개념

### ILSpy는 왜 가벼운가
ILSpy는 디버거, 라이브 패치 기능 없이 **디컴파일과 탐색/검색에만 집중**한 도구다. 그만큼 실행이 빠르고 UI가 단순해서, "이 파일이 대충 뭘 하는 프로그램인지" 훑어보는 첫 단계에 적합하다. 내부적으로 ICSharpCode.Decompiler 엔진을 사용하며, 이 엔진은 dnSpyEx를 포함한 여러 .NET 리버싱 도구에서도 공유되거나 유사한 방식으로 쓰인다.

### 트리 구조 이해하기
ILSpy 왼쪽 패널은 다음과 같은 계층으로 구성된다.
```
어셈블리 (예: Crackme.exe)
 ├─ References              참조하는 다른 DLL 목록
 ├─ Resources                임베디드 리소스(.resources 등)
 └─ {네임스페이스}
     └─ {클래스}
         ├─ 필드(Field)
         ├─ 프로퍼티(Property)
         ├─ 메서드(Method)
         └─ 이벤트(Event)
```
각 노드 왼쪽의 `▶`를 클릭하거나 방향키(`→`/`←`)로 펼치고 접을 수 있다. 클래스나 메서드를 클릭하면 오른쪽 메인 영역에 디컴파일된 코드가 즉시 표시된다.

### 언어 표시 모드
상단 도구모음의 언어 드롭다운에서 표시 방식을 바꿀 수 있다.
- **C#** — 기본값. 대부분의 경우 원본 소스에 가깝게 복원된다.
- **IL** — 원문 CIL 바이트코드를 그대로 보여준다. 디컴파일이 실패하거나 컴파일러가 이상한 코드를 생성한 경우 원인 파악에 필요하다.
- **IL with C#** — IL과 C#을 나란히 보여줘서 어떤 IL 명령어가 어떤 C# 구문에 대응하는지 학습하기 좋다.

## 화면/코드에서 보이는 징후
- 상단 탭에 열린 어셈블리 파일명이 표시되고, 좌측 트리 최상단에 같은 이름의 노드가 나타난다.
- 메서드를 클릭했을 때 코드가 회색으로 흐릿하거나 `// Could not decompile`류의 주석이 붙어 있으면 디컴파일이 부분적으로 실패했다는 뜻이다.
- 검색 결과 창에 일치 항목이 타입별 아이콘(클래스는 상자, 메서드는 초록 사각형 등)과 함께 나열된다.

## 가장 먼저 할 것
`File → Open` 또는 창에 파일을 드래그 앤 드롭해서 대상 어셈블리를 연다. 그다음 좌측 트리에서 어셈블리 노드를 우클릭해 **Go to Entry Point** (또는 `Main`이 있을 법한 `Program` 클래스를 직접 펼쳐서) 진입점 메서드부터 읽기 시작한다. 이 한 번의 클릭만으로도 프로그램이 콘솔 입력을 받는지, 파일을 읽는지, 네트워크 통신을 하는지 등 전체적인 그림이 잡힌다.

## 단계별 절차

**1) 어셈블리 열기**
`File → Open File...` (단축키 `Ctrl+O`)으로 대상 `.exe`/`.dll`을 선택하거나, ILSpy 창에 파일을 드래그 앤 드롭한다.

**2) 진입점으로 이동**
좌측 트리에서 어셈블리 노드를 우클릭 → **Go to Entry Point**를 선택하면 `Main` 메서드로 바로 이동한다. 이 메뉴가 없는 버전이라면 네임스페이스를 펼쳐 보통 `Program` 클래스의 `Main`을 직접 찾는다.

**3) 타입/멤버 검색**
`Ctrl+T` (Search 상자, 버전에 따라 `Edit → Search` 메뉴)를 누르면 검색창이 뜬다. 클래스명, 메서드명 일부를 입력하면 실시간으로 일치 항목이 나열된다. 상단 필터에서 검색 범위를 `Type and Member`, `Type`, `Member`, `Literal(문자열/상수)` 등으로 좁힐 수 있다.

**4) 문자열 리터럴 검색**
검색 필터를 `Literal`로 바꾸면 코드 안에 하드코딩된 문자열/숫자 상수를 대상으로 검색한다. 플래그나 비교값을 찾을 때 유용하다.

**5) 코드 흐름 따라가기**
메서드 안에서 다른 메서드를 호출하는 부분(파란색 링크처럼 보이는 식별자)을 더블클릭하면 그 메서드 정의로 바로 이동한다. 반대로 특정 메서드가 어디서 호출되는지 알고 싶으면 메서드를 우클릭 → **Analyze**를 선택하면 "이 메서드를 사용하는 곳(Used By)"과 "이 메서드가 사용하는 것(Uses)"이 트리로 펼쳐진다. 이는 네이티브 리버싱의 xref(교차 참조)와 같은 개념이다.

**6) IL 원문으로 전환해서 확인**
디컴파일 결과가 이상하거나 실패하면 상단 언어 드롭다운을 **IL**로 바꿔서 원문 CIL 명령어를 직접 읽는다. 읽는 방법은 [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)에서 다룬다.

**7) 프로젝트로 export하기**
`File → Save Code...` (또는 우클릭 어셈블리 노드 → **Export to project**)를 선택하면 디컴파일된 전체 코드를 `.csproj`가 포함된 Visual Studio 프로젝트 형태로 저장한다. 이렇게 export하면 Visual Studio 등 IDE의 "모든 참조 찾기(Find All References)", 전역 검색 같은 강력한 코드 탐색 기능을 그대로 활용할 수 있어서 코드가 방대한 프로그램을 분석할 때 특히 유용하다.

## 명령어/단축키
```text
Ctrl+O             어셈블리 파일 열기
Ctrl+T             타입/멤버/문자열 검색창 열기
우클릭 노드 → Go to Entry Point   Main 등 진입점으로 이동
우클릭 멤버 → Analyze              Used By / Uses(xref) 트리 보기
F3 / Ctrl+F         현재 코드 뷰 안에서 텍스트 찾기
File → Save Code...  전체 어셈블리를 Visual Studio 프로젝트로 export
언어 드롭다운 (C# / IL / IL with C#)   디컴파일 표시 방식 전환
```

## 출력 해석
- `Analyze` 결과의 **Used By** 목록이 비어 있으면 이 메서드가 리플렉션 등으로 동적 호출되거나, 실제로는 죽은 코드(dead code)이거나, 진입점에서만 호출되는 최상위 메서드일 가능성이 있다.
- IL 모드에서 특정 메서드가 `.method ... cil managed` 다음에 본문이 거의 없이 `newobj`, `throw` 정도만 있다면 스텁이거나 예외를 던지는 더미 구현일 수 있다.
- 검색 결과에 같은 이름의 메서드가 여러 개(오버로드) 나오면 매개변수 목록까지 확인해서 정확히 어떤 오버로드가 호출되는지 구분해야 한다.

## 흔한 실수
- ILSpy로 값을 바꿔가며 "실행"해볼 수 있다고 착각하는 것. ILSpy는 읽기 전용 디컴파일러이며 디버거가 없다. 실행하며 확인하려면 [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)로 넘어가야 한다.
- `References` 트리까지 전부 펼쳐서 표준 라이브러리(`mscorlib`, `System.*`) 코드까지 헤매는 것. 대상 프로그램 자체의 어셈블리/네임스페이스만 먼저 집중해서 봐야 한다.
- 검색창에서 필터를 `Type and Member`로 둔 채 문자열 리터럴을 찾으려다가 "검색이 안 된다"고 오해하는 것. 문자열을 찾을 때는 필터를 `Literal`로 바꿔야 한다.
- Export한 프로젝트를 그대로 컴파일하면 원본과 100% 동일하게 동작할 거라 기대하는 것. 디컴파일 결과는 원본 소스와 근접하지만 완전히 동일하지는 않으며, 컴파일러 자동 생성 코드(클로저, 이터레이터의 상태 머신 등)는 원본과 표현이 다를 수 있다.

### ILSpy 확장과 대안 빌드
ILSpy 자체는 오픈소스이며 Visual Studio 확장(ILSpy for Visual Studio)이나 커맨드라인 도구(`ilspycmd`)로도 배포된다. GUI를 켤 여건이 안 되거나 여러 어셈블리를 한 번에 자동으로 소스로 export해야 하는 경우 `ilspycmd`를 스크립트에 넣어 배치 처리할 수 있다. 또한 ILSpy 코드베이스에서 파생된 여러 파생 프로젝트(예: 특정 플러그인을 추가한 커스텀 빌드)가 존재하지만, 기본 사용법과 트리 구조, 검색/Analyze 개념은 공통적으로 동일하다.

## 막혔을 때 다음 체크
- 값을 바꿔가며 실행/디버깅해야 한다면 → [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)
- IL 원문을 C#과 짝지어 읽는 방법이 궁금하면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 문자열/리소스를 더 체계적으로 찾고 싶으면 → [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)
- 클래스/메서드 이름이 죄다 의미 없는 문자로 되어 있으면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 전체 워크플로우 상 지금 이 단계가 맞는지 다시 확인하려면 → [REV-0242 .NET 바이너리 식별과 첫 접근](./rev-0242-dotnet-identification.md)

## 미니 예제
`Crackme.exe`를 ILSpy에 드래그 앤 드롭한다. 좌측 트리에서 어셈블리 노드를 우클릭 → **Go to Entry Point**를 누르면 곧바로 `Program.Main(string[])`으로 이동하고, 우측에는 다음과 같은 코드가 나타난다고 하자.

```csharp
private static void Main(string[] args)
{
    Console.Write("Enter key: ");
    string text = Console.ReadLine();
    if (Validator.Check(text))
        Console.WriteLine("Correct!");
    else
        Console.WriteLine("Wrong!");
}
```

`Validator.Check`를 더블클릭하면 `Validator` 클래스의 `Check` 메서드로 이동한다. 여기서 비교에 쓰이는 상수 문자열이 궁금하면 `Ctrl+T`로 검색창을 열고 필터를 `Literal`로 바꾼 뒤 짐작 가는 키워드(`flag`, `key`, `pass` 등)를 입력해 코드 전체에서 관련 문자열을 한 번에 찾아낼 수 있다. 이렇게 ILSpy만으로 검증 로직과 정답 후보 문자열까지 확인했다면, 실제 입력값을 넣어 통과 여부를 실행으로 확인할 때만 dnSpyEx로 넘어가면 된다.

## 관련 글
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기

## 출처/검증
- ILSpy 기능(트리 탐색, Analyze, Export to project, 언어 표시 모드) 및 단축키: ILSpy 공식 GitHub 저장소(icsharpcode/ILSpy) 문서/위키 기준 (2026-09-08 확인).
- ICSharpCode.Decompiler 엔진 관련 설명: 동일 저장소의 프로젝트 개요 문서 기준.
