---
id: REV-0242
title: ".NET 바이너리 식별과 첫 접근"
slug: "rev-0242-dotnet-identification"
category: "dotnet-android"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["dnSpyEx", "ILSpy", "Detect It Easy"]
keywords: [".NET 리버싱", ".NET 바이너리 분석", "dnSpyEx ILSpy 차이", ".NET 워크플로우", "CLR 실행파일 분석", "managed 코드 분석 순서"]
aliases: [".NET 파일 분석 어떻게 시작하나", "dnSpyEx ILSpy 뭐 써야 하나", ".NET exe 처음 열었을 때", "C# 리버싱 시작하기"]
symptom_keywords: [".NET 바이너리인 건 확인했는데 다음에 뭘 해야할지 모름", "dnSpyEx와 ILSpy 중 어느 걸 써야 할지 모름", ".NET CTF 문제를 받았는데 순서를 모름", "IDA로 열었더니 코드가 이상하게 보임 .NET 아닐까"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
DIE나 PE-bear로 어떤 `.exe`가 **.NET(C#/VB.NET) 바이너리**라는 것까지 확인했다면, 그다음부터는 IDA·Ghidra 같은 네이티브 디스어셈블러를 붙잡고 있지 말고 곧바로 **ILSpy로 빠르게 구조를 훑고, 필요하면 dnSpyEx로 넘어가서 디버깅하거나 코드를 직접 고치는** 순서로 움직이는 것이 .NET 리버싱의 기본 워크플로우다.

## 언제 검색해야 하나
- Detect It Easy나 PE-bear에서 파일을 열었더니 컴파일러 정보에 `.NET(C#)`, `Microsoft Visual C# / Basic .NET`, `mscoree.dll` 같은 문구가 보여서 ".NET 바이너리구나"까지는 알았는데, 그다음에 뭘 눌러야 할지 막막할 때
- IDA나 Ghidra로 `.NET` 실행 파일을 열었더니 함수가 몇 개 안 보이고 대부분 `mscoree.dll`을 호출하는 스텁 코드만 나와서 "뭔가 잘못 열었나?" 싶을 때
- dnSpyEx와 ILSpy 둘 다 이름은 들어봤는데 정확히 뭐가 다른지, CTF 문제 하나를 풀 때 어떤 걸 먼저 켜야 하는지 모를 때
- .NET 바이너리 리버싱을 처음 시작하면서 "네이티브 PE 분석이랑 순서가 완전히 다른가?"라는 그림을 잡고 싶을 때

## 핵심 개념

### 식별은 이미 끝났다는 전제
이 글은 어떤 파일이 .NET 바이너리인지 아닌지 **판별하는 방법 자체**는 다루지 않는다. `mscoree.dll`/`mscorlib.dll` 임포트, PE Optional Header의 `IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR`(CLR 헤더) 존재 여부, DIE의 "`.NET(C#)`" 표시 같은 판별 기준은 [REV-0136 .NET EXE인지 Native EXE인지 구분](../windows-pe/rev-0136-dotnet-vs-native.md)에서 자세히 다룬다. 여기서는 "이미 .NET이라고 확인한 뒤" 실제로 무엇을 어떤 순서로 해야 하는지, 즉 **워크플로우**에 집중한다.

### 왜 IDA/Ghidra로 계속 파면 안 되는가
.NET 실행 파일은 x86/x64 기계어가 아니라 **CIL(Common Intermediate Language)**이라는 중간 언어로 컴파일된다. 실제 실행은 CLR(Common Language Runtime)이 이 IL을 JIT(Just-In-Time) 컴파일해서 처리하기 때문에, PE 파일 안의 `.text` 섹션에는 사람이 알아볼 만한 코드가 거의 없고 대부분 CLR을 초기화하는 짧은 스텁뿐이다. IDA나 Ghidra로 이걸 열면 실제 프로그램 로직은 보이지 않고 `mscoree.dll!_CorExeMain` 같은 런타임 진입점 호출만 보인다. 반면 IL에는 클래스 이름, 메서드 이름, 변수 타입, 심지어 로컬 변수 이름 일부까지 메타데이터로 고스란히 남아 있어서, IL 전용 디컴파일러를 쓰면 **원본 C# 소스에 매우 가까운 코드**를 바로 얻을 수 있다. 그래서 .NET 바이너리는 어셈블리 명령어를 한 줄씩 읽는 대신 곧바로 디컴파일된 고급 언어 코드를 읽는 것이 정석이다.

### 워크플로우 6단계
1. **식별** — DIE/PE-bear로 .NET 여부와 대상 프레임워크(.NET Framework 4.x인지 .NET 5/6/7/8+인지)를 확인한다. 프레임워크 버전에 따라 실행 환경(설치된 런타임)이 달라질 수 있다.
2. **1차 정적 디컴파일** — ILSpy로 열어서 어셈블리 트리를 훑는다. 네임스페이스/클래스/메서드 이름만 봐도 프로그램 구조가 거의 드러난다.
3. **난독화 여부 확인** — 클래스/메서드 이름이 `a`, `b`, `<Module>{...}` 같은 의미 없는 문자열로 되어 있거나, 디컴파일이 실패하는 메서드가 많다면 난독화된 것이다([REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md) 참고).
4. **문자열/리소스 확인** — 플래그, 비밀번호, 라이선스 키 같은 단서를 [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)의 방법으로 찾는다.
5. **동적 분석 전환** — 조건 분기를 직접 확인하거나 값을 바꿔가며 실행해봐야 한다면 dnSpyEx로 옮겨서 브레이크포인트를 걸고 실행한다.
6. **필요하면 라이브 패치** — dnSpyEx의 "Edit Method (C#)" 기능으로 검증 로직 자체를 고쳐서 재컴파일 없이 즉석에서 동작을 바꿔본다(CTF/교육 목적의 우회 실습에 한정).

이 순서는 "가장 가볍고 빠른 도구부터 쓰고, 필요할 때만 무거운 도구로 넘어간다"는 원칙을 따른다. 무조건 처음부터 dnSpyEx를 켜고 디버거를 붙일 필요는 없다.

### dnSpyEx vs ILSpy, 언제 뭘 쓰나
| 상황 | 추천 도구 | 이유 |
|---|---|---|
| 코드 구조만 빠르게 훑고 싶다 | ILSpy | 가볍고 빠르며 읽기 전용 열람에 최적화 |
| 여러 어셈블리를 프로젝트로 export해서 IDE로 보고 싶다 | ILSpy | "Export Assembly" 기능으로 컴파일 가능한 프로젝트 생성 |
| 실행하면서 값/분기를 실시간으로 확인해야 한다 | dnSpyEx | 내장 디버거로 브레이크포인트, 스텝 실행, 지역변수 감시 가능 |
| 검증 로직을 즉석에서 고쳐서 우회 동작을 확인하고 싶다 | dnSpyEx | "Edit Method (C#)" 라이브 패치 기능 제공 |
| 프로세스에 붙여서(attach) 이미 실행 중인 .NET 프로그램을 분석하고 싶다 | dnSpyEx | Debug → Attach to Process 지원 |
| ILSpy에서 디컴파일이 깨지는 메서드가 있다 | dnSpyEx | 디컴파일 엔진이 다르게 동작할 때가 있어 교차 확인용으로 유용 |

실무적으로는 "**ILSpy로 먼저 훑고, 실행/패치가 필요해지는 순간 dnSpyEx로 넘어간다**"가 가장 시간 낭비가 적은 순서다. 두 도구는 서로 대체재가 아니라 단계별로 쓰는 상호보완 도구로 이해하는 것이 맞다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra로 열었을 때 함수 목록이 극도로 적고, 대부분 `mscoree.dll`, `KERNEL32.dll`의 몇 개 함수만 임포트되어 있다.
- PE-bear의 Import Directory에 `mscoree.dll`의 `_CorExeMain` 하나만 덜렁 임포트되어 있는 경우가 많다.
- ILSpy/dnSpyEx로 열면 왼쪽 트리에 어셈블리 이름, 네임스페이스, 클래스, 메서드가 계층적으로 펼쳐지고 오른쪽에 C# 코드가 바로 나타난다.

## 가장 먼저 할 것
.NET 바이너리라는 것을 확인했다면, 다른 도구를 켜기 전에 우선 **ILSpy에 파일을 드래그 앤 드롭**해서 트리 구조를 30초만 훑어본다. 클래스/메서드 이름이 사람이 읽을 수 있는 수준인지, `Main` 메서드가 바로 보이는지, 디컴파일이 정상적으로 되는지를 확인하는 것만으로도 이 파일이 "난독화 없는 평범한 .NET 프로그램"인지 "손봐야 할 대상"인지 감이 잡힌다.

## 단계별 절차

**1) 대상 프레임워크 확인**
ILSpy나 dnSpyEx로 파일을 열면 하단 상태 표시줄이나 어셈블리 정보에 `.NETFramework,Version=v4.7.2` 또는 `.NETCoreApp,Version=v8.0` 같은 대상 프레임워크(Target Framework Moniker)가 표시된다. .NET Framework면 Windows에 기본 내장된 런타임으로 바로 실행되고, .NET (Core) 계열이면 별도 런타임 설치나 self-contained 배포 여부를 확인해야 실행 테스트가 가능하다.

**2) ILSpy로 1차 훑기**
`File → Open`으로 파일을 열고 트리에서 `Main` 메서드부터 찾아 읽는다. 자세한 조작법은 [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)에서 다룬다.

**3) 난독화 판단**
클래스/메서드 이름이 의미 없는 짧은 문자열이거나 디컴파일 오류가 잦으면 [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)를 먼저 읽고 대응 전략을 세운다.

**4) 필요 시 dnSpyEx로 전환**
정적으로 읽는 것만으로 부족하면 dnSpyEx로 열어서 디버거를 붙인다. 조작법은 [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)를 참고한다.

**5) 문자열/리소스 확인**
플래그나 하드코딩된 비교값을 찾을 때는 IL 텍스트 검색이나 리소스 뷰어를 쓴다([REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)).

## 명령어/단축키
```text
ILSpy: 파일을 창에 드래그 앤 드롭하여 열기
ILSpy: Ctrl+T 로 타입/멤버 검색
dnSpyEx: Ctrl+O 로 어셈블리 열기
dnSpyEx: F5 로 디버그 시작(디버거 붙여서 실행)
dnSpyEx: 메서드 우클릭 → Edit Method (C#) 로 라이브 패치
```

## 출력 해석
- ILSpy/dnSpyEx 트리에서 `Main` 메서드 시그니처가 `static void Main(string[] args)`처럼 정상적으로 보이면 난독화가 약하거나 없는 프로그램이다.
- 트리 항목 이름이 `<>c__DisplayClass1_0`, `a`, `b` 같이 나오면 컴파일러가 자동 생성한 코드이거나 난독화된 코드이니 별도 분석 전략이 필요하다.
- 메서드를 열었는데 본문이 비어 있거나 "디컴파일 실패" 메시지가 뜨면 IL 원문 보기 모드로 전환해서 [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)의 방법으로 직접 읽는다.

## 흔한 실수
- .NET 바이너리를 IDA/Ghidra에만 계속 붙잡고 앉아서 시간을 낭비하는 것. CLR 스텁만 보이는 상태에서는 아무리 디스어셈블해도 실제 로직이 나오지 않는다.
- dnSpyEx와 ILSpy를 아무 기준 없이 아무거나 켜는 것. 단순 열람에는 ILSpy가 훨씬 빠르고, 실행/패치가 필요할 때만 dnSpyEx를 켜는 것이 시간을 아낀다.
- .NET Framework용 파일을 최신 .NET 전용 환경에서 실행하려다 런타임 누락 오류를 맞고 "파일이 손상됐다"고 오해하는 것. 대상 프레임워크 표시를 먼저 확인해야 한다.
- 난독화된 코드를 보고 바로 포기하는 것. 이름이 깨져 있어도 IL 흐름과 문자열, 호출 순서만으로도 상당 부분 추론할 수 있다.

## 막혔을 때 다음 체크
- dnSpyEx 조작법이 궁금하면 → [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)
- ILSpy 조작법이 궁금하면 → [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)
- 디컴파일이 깨진 메서드의 IL을 직접 읽어야 하면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 문자열이 안 보이면 → [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)
- 이름이 죄다 깨져 있으면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 애초에 이게 .NET인지 네이티브인지부터 헷갈리면 → [REV-0136 .NET EXE인지 Native EXE인지 구분](../windows-pe/rev-0136-dotnet-vs-native.md)

## 미니 예제
CTF에서 `Crackme.exe`라는 파일을 받았다고 하자. PE-bear로 열어보니 Import Directory에 `mscoree.dll`만 보이고 `.text` 섹션이 이상하게 작다. DIE로 다시 열어보니 상단에 "`.NET(C#) Visual Studio`"라고 표시된다. 여기서 IDA를 켜는 대신 ILSpy에 파일을 드래그 앤 드롭한다. 왼쪽 트리에 `Crackme.exe → Crackme → Program → Main(string[])`이 그대로 보이고, `Main`을 클릭하면 `if (input == "flag{...}") { Console.WriteLine("Correct!"); }` 형태의 C# 코드가 바로 나타난다. 이름이 전혀 난독화되어 있지 않으므로 이 시점에서 이미 검증 로직과 정답 문자열을 눈으로 확인할 수 있다. 만약 코드가 값을 런타임에 조립하거나 검증에 실패하면 프로그램이 조기 종료되는 구조라면, 여기서 dnSpyEx로 전환해서 `Main`에 브레이크포인트를 걸고 실제 비교 시점의 변수 값을 확인하는 단계로 넘어간다.

## 관련 글
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0244 — ILSpy 기본 사용법
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0246 — .NET 문자열과 리소스 찾기
- REV-0247 — .NET 난독화 기초
- REV-0136 — .NET EXE인지 Native EXE인지 구분

## 출처/검증
- .NET 실행 모델(CIL, CLR, JIT)과 PE 내 CLR 헤더 구조: Microsoft Learn ".NET metadata and IL" 및 "PE Format(CLR 헤더)" 공식 문서 기준 (2026-09-08 검증).
- dnSpyEx/ILSpy 기능 비교(디버거 내장 여부, Export Assembly, Edit Method): 각 프로젝트 공식 GitHub 저장소(dnSpyEx, icsharpcode/ILSpy) README 및 위키 기준.
