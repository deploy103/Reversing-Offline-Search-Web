---
id: REV-0969
title: ".NET 리플렉션(Reflection) 기반 난독화 알아보기"
slug: "rev-0969-dotnet-reflection-obfuscation"
category: "dotnet-android"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [dnSpyEx]
keywords: ["System.Reflection", "MethodInfo.Invoke", "Type.GetMethod", "Activator.CreateInstance", "Delegate.CreateDelegate", "리플렉션 기반 간접 호출 은닉"]
aliases: ["닷넷 리플렉션 난독화", "MethodInfo Invoke 난독화", "Activator.CreateInstance 우회", "리플렉션으로 호출 숨기기"]
symptom_keywords: ["Analyze Used By가 비어있는데 실제로는 호출된다", "MethodInfo.Invoke가 자꾸 나온다", "문자열로 된 메서드 이름이 있다", "Activator.CreateInstance가 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
리플렉션 기반 난독화는 `A.Method(x)`처럼 컴파일 타임에 고정된 직접 호출 대신 `typeof(A).GetMethod("Method").Invoke(obj, new object[]{x})`처럼 **런타임에 이름 문자열로 대상을 찾아 호출**하는 방식을 써서, 디컴파일러의 정적 호출 그래프(`Analyze` → Uses/Used By)에서 그 호출 관계가 아예 보이지 않게 숨기는 기법이며, 핵심 대응은 "정적으로 안 보이면 동적으로 관찰한다"는 원칙이다.

## 언제 검색해야 하나
- dnSpyEx/ILSpy의 `Analyze` → **Used By**를 확인했는데 분명히 실행되는 것 같은 메서드인데 호출자가 하나도 안 나올 때
- 코드에 `typeof(...)`, `GetType()`, `GetMethod`, `GetField`, `Invoke`, `Activator.CreateInstance` 같은 이름이 반복해서 등장할 때
- 메서드/타입 이름이 문자열 리터럴로 코드 여기저기 흩어져 있어서 이게 왜 필요한지 이해가 안 될 때
- `Delegate.CreateDelegate`나 `Expression` 트리로 무언가를 조립해서 실행하는 코드를 만났을 때
- [REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 이름 맹글링/제어 흐름/문자열 암호화로는 설명이 안 되는, "호출 관계 자체가 안 보이는" 패턴을 만났을 때

## 핵심 개념

### 왜 리플렉션이 난독화 수단이 되는가
.NET의 리플렉션 API(`System.Reflection` 네임스페이스)는 원래 플러그인 로딩, 직렬화, 의존성 주입(DI) 프레임워크처럼 "실행 시점에야 어떤 타입/메서드를 쓸지 결정되는" 정당한 시나리오를 위해 설계된 기능이다. 그런데 이 특성을 뒤집으면, **컴파일 타임에는 이미 어떤 메서드를 호출할지 다 알고 있으면서도 일부러 리플렉션으로 감싸서** 디컴파일러가 정적으로 추적하지 못하게 만드는 용도로도 쓸 수 있다. IL 레벨에서 `call SomeClass::SomeMethod(...)` 같은 직접 호출 명령어(`call`/`callvirt`)가 아예 나타나지 않고, 대신 `ldstr "SomeMethod"`(메서드 이름 문자열) → `callvirt System.Reflection.MethodInfo::Invoke(...)`만 보이기 때문에, IL 자체를 코드로 인식하는 디컴파일러의 정적 분석(Analyze의 Uses/Used By 포함)은 이 호출을 실제 호출 관계로 연결하지 못한다.

상용 난독화 도구 중 일부(및 수작업으로 추가되는 "안티 디컴파일" 패치)가 특히 민감한 검증 로직이나 라이선스 체크 함수 하나만 골라 이 방식으로 감싸는 경우가 흔하다. 프로그램 전체를 리플렉션으로 바꾸면 성능이 크게 떨어지고 코드도 지나치게 복잡해지므로, 대개 "숨기고 싶은 특정 함수 몇 개"에만 국소적으로 적용된다는 점이 특징이다.

### 패턴 1: Type.GetMethod + MethodInfo.Invoke
가장 흔한 형태다.
```csharp
Type t = typeof(Validator);
MethodInfo mi = t.GetMethod("CheckKey", BindingFlags.NonPublic | BindingFlags.Static);
object result = mi.Invoke(null, new object[] { inputKey });
bool ok = (bool)result;
```
정상적인 코드라면 그냥 `bool ok = Validator.CheckKey(inputKey);`로 끝날 한 줄이, 타입 조회 → 메서드 조회(이름 문자열로) → 인자 배열 포장 → 호출 → 반환값 언박싱까지 여러 단계로 늘어난다. `BindingFlags.NonPublic`이 붙어 있으면 `private`/`internal` 멤버까지 이름만으로 찾아낼 수 있다는 뜻이므로, 접근 제한자로 숨겨진 검증 로직을 리플렉션이 우회하고 있다는 신호이기도 하다.

### 패턴 2: Activator.CreateInstance
생성자 호출 자체를 이름으로 감추는 패턴이다.
```csharp
Type t = Type.GetType("MyApp.Internal.LicenseChecker");
object instance = Activator.CreateInstance(t);
```
`new LicenseChecker()`가 코드 어디에도 `newobj` 명령어로 나타나지 않고, 대신 `Type.GetType`에 넘긴 **문자열**(`"MyApp.Internal.LicenseChecker"`, 네임스페이스 포함 전체 이름)로만 그 클래스가 존재한다는 사실을 알 수 있다. 이 문자열 자체가 흩어져 있거나([REV-0971](./rev-0971-dotnet-string-encryption-traces.md)처럼 암호화되어 있을 수도 있음) 조합되어 있으면 정적으로 어떤 클래스가 실제로 인스턴스화되는지 알아내기가 훨씬 어려워진다.

### 패턴 3: Delegate.CreateDelegate / Func·Action 위임
```csharp
MethodInfo mi = typeof(Validator).GetMethod("CheckKey");
var del = (Func<string, bool>)Delegate.CreateDelegate(typeof(Func<string, bool>), mi);
bool ok = del(inputKey);
```
메서드를 델리게이트(함수 포인터에 대응하는 .NET 개념)로 감싸서 저장해두고 나중에 호출하는 방식이다. IL에서는 `ldftn`(함수 포인터 로드) 또는 `ldvirtftn` 명령어가 등장하는데, 이 역시 일반 `call`이 아니므로 디컴파일러의 정적 호출 그래프에는 잘 반영되지 않는다. 정상적인 콜백/이벤트 핸들러 등록에도 흔히 쓰이는 패턴이라 그 자체가 곧바로 "수상하다"는 신호는 아니지만, 검증 로직 근처에서 나타나면 의심해볼 만하다.

### 패턴 4: Expression 트리 / 동적 코드 생성
`System.Linq.Expressions`나 `Reflection.Emit`으로 아예 런타임에 IL을 조립해서 실행하는 극단적인 경우도 있다. 이 경우 실제 로직에 해당하는 IL 코드가 원본 어셈블리 안에 존재하지 않고, 실행 시점에 메모리 상에서만 생성되므로 정적 디컴파일로는 원천적으로 볼 수 없다. 이런 경우 동적 분석(디버거로 실행 중 메모리를 들여다보는 것)이 사실상 유일한 경로가 된다.

## 화면/코드에서 보이는 징후
- `Type.GetMethod(...)`, `Type.GetField(...)`, `Type.GetType("...")`, `Activator.CreateInstance(...)`, `MethodInfo.Invoke(...)` 같은 API 이름이 코드에 직접 등장한다.
- 문자열 리터럴로 클래스/메서드 전체 이름이 박혀 있다(예: `"MyApp.Internal.LicenseChecker"`, `"CheckKey"`).
- `Analyze`(dnSpyEx/ILSpy)에서 특정 메서드의 **Used By**가 비어 있는데, 실행하면 분명히 그 코드가 동작한다.
- IL을 직접 보면 `call`/`callvirt` 대신 `callvirt instance object [mscorlib]System.Reflection.MethodBase::Invoke(...)` 형태가 반복된다.

## 가장 먼저 할 것
`Ctrl+Shift+F`(전체 문자열 검색, [REV-0967](./rev-0967-dnspyex-ilspy-shortcuts.md) 참고)로 `GetMethod`, `Invoke`, `Activator.CreateInstance` 같은 API 이름 자체를 검색해서, 리플렉션이 코드 전체에서 몇 군데나 쓰이는지부터 파악한다. 몇 군데 안 되면 하나씩 손으로 추적 가능한 범위다.

## 단계별 절차
1. `Ctrl+Shift+F`로 `GetMethod(`, `GetField(`, `Invoke(`, `CreateInstance(` 문자열을 검색해 리플렉션 사용 지점을 전부 찾는다.
2. 각 지점에서 `GetMethod("이름", ...)`/`Type.GetType("이름")`에 넘겨진 문자열 리터럴을 확인한다. 이 문자열이 바로 실제로 호출되는 대상의 이름이다.
3. 그 이름으로 다시 `Ctrl+Shift+K`(멤버 검색)를 돌려 실제 대상 클래스/메서드를 트리에서 찾아 코드를 읽는다.
4. `BindingFlags`가 `NonPublic`을 포함하면 `private`/`internal` 멤버까지 대상이 될 수 있음을 감안하고 검색 범위를 넓힌다.
5. 문자열이 정적으로 안 보이거나(암호화/조합) 대상이 `Reflection.Emit`/`Expression`으로 동적으로 만들어진다면, dnSpyEx 디버거로 `Invoke` 호출 직전/직후에 브레이크포인트를 걸어 `mi.Name`, `t.FullName` 같은 런타임 값을 직접 확인한다.
6. 확인된 실제 대상 메서드에 dnSpyEx `F2`(Rename)로 알아보기 쉬운 이름을 붙여 이후 분석 흐름을 표시해 둔다.

## 명령어/단축키
```text
dnSpyEx: Ctrl+Shift+F                전체 어셈블리 문자열 검색(GetMethod, Invoke 등 API 이름)
dnSpyEx: Ctrl+Shift+K                멤버 이름 검색(리플렉션이 가리키는 실제 대상 찾기)
dnSpyEx: F9 (Invoke 호출 줄) → F5    Invoke 호출 직전에 멈춰서 mi/t 값 확인
dnSpyEx: F10                         Invoke 호출을 한 줄로 지나치며 반환값만 확인
```
```csharp
// 디버거 Watch/Immediate에서 실제 대상 확인 (의사 코드)
mi.Name          // 호출되는 실제 메서드 이름
mi.DeclaringType.FullName  // 그 메서드가 속한 클래스 전체 이름
```

## 출력 해석
- `mi.Name`이 `"CheckKey"`처럼 사람이 읽을 수 있는 값으로 확인되면, 그 이름으로 트리에서 바로 검색해 실제 구현을 읽으면 된다.
- `t.FullName`(또는 `Type.GetType(...)`에 넘긴 문자열)이 네임스페이스까지 포함된 전체 경로라면, 그 경로 그대로 dnSpyEx 트리에서 어셈블리 → 네임스페이스 → 클래스 순으로 펼쳐 찾아갈 수 있다.
- 브레이크포인트에서 확인한 이름이 프로그램 실행마다 달라진다면(예: 배열에서 인덱스로 골라 조합), 이름 자체가 동적으로 계산되는 것이므로 그 조합 로직까지 별도로 추적해야 한다.

## 흔한 실수
- 리플렉션 API 이름만 보고 "이건 분석 불가능하다"고 포기하는 것. 대부분의 경우 `GetMethod`/`GetType`에 넘기는 문자열 리터럴이 코드에 그대로 남아 있어서, 정적으로 검색만 해도 대상이 바로 드러난다.
- `Analyze`의 Used By가 비었다는 것만으로 그 메서드가 죽은 코드(사용되지 않는 코드)라고 단정하는 것 — 리플렉션으로만 호출되는 메서드는 정적 분석 도구 입장에서 "사용되지 않는 것처럼" 보일 뿐 실제로는 핵심 로직일 수 있다.
- `BindingFlags.NonPublic`을 놓치고 `public` 멤버만 검색해서 실제 대상(`private`/`internal`)을 못 찾는 것.
- 리플렉션으로 감싸진 호출 하나를 발견하고 나서, 같은 패턴이 프로그램 다른 곳에도 더 있는지 전체 검색을 하지 않고 그 지점 하나만 보고 분석을 끝내버리는 것.
- 동적으로 생성된 코드(`Reflection.Emit`/`Expression`)까지 정적 디컴파일로 억지로 읽으려 하며 시간을 낭비하는 것 — 이 경우는 애초에 디버거로 실행 중 값을 관찰하는 것이 유일하게 실용적인 경로다.

## 막혔을 때 다음 체크
- 리플렉션으로 찾은 실제 대상 메서드 안이 또 이름 맹글링/제어 흐름 난독화로 뒤섞여 있다면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- `GetMethod`에 넘긴 이름 문자열 자체가 암호화되어 안 보인다면 → [REV-0971 .NET 문자열 암호화 흔적 알아보기](./rev-0971-dotnet-string-encryption-traces.md)
- 이 리플렉션 패턴이 ConfuserEx 같은 특정 도구가 자동 삽입한 것인지 확인하고 싶다면 → [REV-0970 ConfuserEx 흔적 알아보기](./rev-0970-confuserex-traces.md)
- IL 레벨에서 `ldftn`/`callvirt Invoke` 같은 명령어를 직접 읽는 법이 헷갈리면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)

## 미니 예제
디컴파일된 `Main` 메서드가 다음과 같다고 하자.
```csharp
static void Main(string[] args)
{
    string input = Console.ReadLine();
    Type t = typeof(Program).Assembly.GetType("MyApp.Internal.Validator");
    MethodInfo mi = t.GetMethod("CheckKey", BindingFlags.NonPublic | BindingFlags.Static);
    object result = mi.Invoke(null, new object[] { input });
    Console.WriteLine((bool)result ? "OK" : "FAIL");
}
```
`Validator.CheckKey`를 dnSpyEx 트리에서 `Ctrl+Shift+K`로 검색해도, `Main`의 `Analyze` → Used By에는 이 호출이 전혀 잡히지 않는다(직접 `call`이 아니라 `Invoke`를 거치기 때문이다). 하지만 코드에 그대로 남아 있는 문자열 `"MyApp.Internal.Validator"`와 `"CheckKey"`를 그대로 `Ctrl+Shift+K`로 검색하면 실제 구현 클래스와 메서드를 바로 찾을 수 있다. 만약 이 문자열들마저 암호화되어 안 보인다면, `mi.Invoke(...)` 호출 줄에 `F9`로 브레이크포인트를 걸고 `F5`로 실행한 뒤 Locals/Watch 창에서 `mi.Name`과 `t.FullName`을 직접 확인하면 이름이 무엇이든 실행 시점의 실제 값이 그대로 드러난다.

## 관련 글
- REV-0247 — .NET 난독화 기초
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0967 — dnSpyEx/ILSpy 단축키 빠른 참조
- REV-0970 — ConfuserEx 흔적 알아보기
- REV-0971 — .NET 문자열 암호화 흔적 알아보기

## 출처/검증
- `System.Reflection` API(`Type.GetMethod`, `MethodInfo.Invoke`, `Activator.CreateInstance`, `Delegate.CreateDelegate`)의 동작은 Microsoft 공식 .NET API 문서(learn.microsoft.com, `System.Reflection` 네임스페이스)를 기준으로 설명했다.
- IL 명령어 `callvirt`, `ldftn`, `ldvirtftn`의 의미는 ECMA-335(Common Language Infrastructure) 명세를 기준으로 확인했다.
- 리플렉션을 이용한 호출 은닉이 정적 분석/디컴파일러의 호출 그래프 추적을 어렵게 만든다는 일반적 패턴은 .NET 리버싱 관련 보안 리서치 자료 및 커뮤니티 문서에서 공통적으로 설명하는 내용을 기준으로 정리했다 (2026-09-09 확인).
