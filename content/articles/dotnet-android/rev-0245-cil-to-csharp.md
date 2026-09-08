---
id: REV-0245
title: "CIL IL 명령어를 C#과 연결해서 읽기"
slug: "rev-0245-cil-to-csharp"
category: "dotnet-android"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["dnSpyEx", "ILSpy"]
keywords: ["CIL 명령어", "IL 어셈블리 읽는 법", "ldarg ldstr call ceq brtrue", ".NET 바이트코드", "IL 스택 머신", "MSIL 읽기"]
aliases: ["CIL이란", "IL 코드 읽는 법", ".NET 어셈블리어", "MSIL 명령어 뜻", "디컴파일 실패했을 때 IL 읽기"]
symptom_keywords: ["디컴파일이 실패해서 IL만 남았을 때", "ldarg ldstr call 이 뜻하는 게 뭔지 모름", "ceq brtrue.s가 뭘 하는 명령어인지 모름", "IL 코드를 보고 C# 로직을 추론하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CIL(Common Intermediate Language)은 x86 어셈블리와 마찬가지로 사람이 직접 읽을 수 있는 저수준 명령어 집합이지만, **레지스터가 아니라 스택(stack)을 기반으로 값을 주고받는다**는 점만 이해하면 `ldarg.0`(인자 push), `ldstr`(문자열 push), `call`(메서드 호출), `ceq`(비교), `brtrue.s`(조건 분기), `ret`(반환) 같은 명령어 몇 개만으로도 디컴파일이 실패한 난독화 코드조차 C# 로직으로 손으로 번역해낼 수 있다.

## 언제 검색해야 하나
- ILSpy나 dnSpyEx에서 특정 메서드를 열었는데 "디컴파일 실패" 메시지가 뜨고 IL 원문만 보일 때
- 강하게 난독화된 .NET 바이너리에서 C# 복원이 의미 없는 코드로 나와서 IL을 직접 읽어야 할 때
- `ldarg.0`, `ldstr`, `call`, `ceq`, `brtrue.s` 같은 명령어를 처음 보고 각각이 무슨 뜻인지 모를 때
- IL 코드 한 줄 한 줄이 C# 소스의 어느 부분에 대응하는지 감을 잡고 싶을 때

## 핵심 개념

### CIL은 스택 머신이다
x86 어셈블리는 `mov eax, ebx`처럼 레지스터끼리 값을 주고받지만, CIL에는 범용 레지스터라는 개념이 없다. 대신 모든 연산이 **평가 스택(evaluation stack)**이라는 임시 저장 공간을 통해 이뤄진다. 값을 스택에 밀어 넣는(push) 명령어와, 스택에서 값을 꺼내(pop) 연산한 뒤 결과를 다시 스택에 넣는 명령어들의 연속으로 프로그램이 표현된다. 이 원칙 하나만 기억하면 낯선 IL 명령어를 만나도 "스택에 뭘 넣나, 스택에서 뭘 꺼내나"를 따라가며 해석할 수 있다.

### 핵심 명령어 6개
| 명령어 | 스택 동작 | 의미 |
|---|---|---|
| `ldarg.0` | push | 0번째 인자를 스택에 올린다. 인스턴스 메서드에서는 0번이 `this`이고, static 메서드에서는 0번이 첫 번째 매개변수다. |
| `ldstr "..."` | push | 문자열 리터럴을 스택에 올린다. |
| `call 메서드시그니처` | pop N개 → push 0/1개 | 스택 최상단부터 필요한 인자 개수만큼 꺼내 메서드를 호출하고, 반환값이 있으면 다시 스택에 올린다. |
| `ceq` | pop 2개 → push 1개(bool) | 스택 최상단 두 값을 꺼내 같으면 `1`(true), 다르면 `0`(false)을 스택에 올린다. |
| `brtrue.s 대상` | pop 1개 | 스택 최상단 값을 꺼내 `0`이 아니면(true면) 지정한 IL 오프셋으로 분기하고, `0`이면 다음 줄로 이어서 실행한다. `.s`는 짧은 오프셋(short form)이라는 표시일 뿐 동작은 동일하다. |
| `ret` | pop 0/1개 | 현재 메서드를 종료한다. 반환 타입이 `void`가 아니면 스택 최상단 값을 반환값으로 사용한다. |

### 예제: C# 소스와 IL을 나란히 놓고 읽기
다음과 같은 아주 단순한 검증 메서드가 있다고 하자.

```csharp
static void CheckPassword(string input)
{
    if (input == "flag{test}")
    {
        Console.WriteLine("Correct!");
    }
    else
    {
        Console.WriteLine("Wrong!");
    }
}
```

Release 최적화 없이(디버그 빌드 기준) Roslyn 컴파일러가 생성하는 IL은 대략 다음과 같은 형태다. dnSpyEx/ILSpy에서 언어 표시를 **IL**로 바꾸면 이와 거의 동일한 코드를 볼 수 있다.

```text
.method private hidebysig static void CheckPassword(string input) cil managed
{
    .maxstack 2
    .locals init ([0] bool V_0)

    IL_0000: ldarg.0
    IL_0001: ldstr      "flag{test}"
    IL_0006: call       bool [mscorlib]System.String::op_Equality(string, string)
    IL_000b: ldc.i4.0
    IL_000c: ceq
    IL_000e: stloc.0
    IL_000f: ldloc.0
    IL_0010: brtrue.s   IL_001e

    IL_0012: ldstr      "Correct!"
    IL_0017: call       void [mscorlib]System.Console::WriteLine(string)
    IL_001c: br.s       IL_0029

    IL_001e: ldstr      "Wrong!"
    IL_0023: call       void [mscorlib]System.Console::WriteLine(string)

    IL_0029: ret
}
```

### 한 줄씩 스택을 따라가며 번역하기
1. `IL_0000: ldarg.0` — 매개변수 `input`(static 메서드이므로 0번째 인자)을 스택에 올린다. 스택: `[input]`
2. `IL_0001: ldstr "flag{test}"` — 문자열 리터럴을 스택에 올린다. 스택: `[input, "flag{test}"]`
3. `IL_0006: call op_Equality(string, string)` — `String.op_Equality`는 C#의 `==` 연산자가 컴파일된 형태다. 스택에서 두 값을 꺼내 비교하고 `bool` 결과를 push한다. 이 시점에서 이미 `input == "flag{test}"`라는 C# 코드 한 줄과 정확히 대응된다는 것을 알 수 있다. 스택: `[bool]`
4. `IL_000b: ldc.i4.0` — 정수 상수 `0`(false)을 스택에 올린다. 스택: `[bool, 0]`
5. `IL_000c: ceq` — 방금 올린 `0`과 비교 결과를 다시 비교한다. 즉 "비교 결과가 false와 같은가?"를 계산하는 것으로, 결과적으로 **논리 부정(NOT)**과 같은 효과를 낸다. 디버그 빌드에서 Roslyn이 `if` 조건을 이렇게 이중으로 뒤집어 컴파일하는 것은 흔한 패턴이다.
6. `IL_000e~000f: stloc.0 / ldloc.0` — 결과를 임시 지역변수에 저장했다가 다시 불러온다. 디버그 빌드 특유의 최적화 없는 코드 패턴이며, 논리적으로는 3~5단계 결과를 그대로 쓰는 것과 같다.
7. `IL_0010: brtrue.s IL_001e` — 스택 값이 true(즉 "원래 비교가 false였다")면 `IL_001e`(else 블록, `"Wrong!"` 출력)로 분기한다. false면(즉 원래 비교가 true, 문자열이 같았다면) 다음 줄로 이어져 `IL_0012`(`"Correct!"` 출력)로 진행한다.
8. `IL_0012~001c` — `"Correct!"`를 출력하고 `br.s IL_0029`로 메서드 끝(`ret`)까지 무조건 점프해서 else 블록을 건너뛴다.
9. `IL_001e~0028` — else 블록. `"Wrong!"`을 출력한다.
10. `IL_0029: ret` — 메서드 종료.

이렇게 스택을 손으로 따라가면, 설령 도구의 디컴파일이 완전히 실패하거나 클래스/메서드 이름이 전부 난독화되어 있더라도, **문자열 리터럴("flag{test}")과 분기 구조("같으면 통과, 다르면 실패")만은 정확히 복원**할 수 있다. 이것이 IL을 직접 읽을 줄 알아야 하는 이유다.

### 흔히 보는 추가 명령어
위 6개 외에도 실전에서 자주 마주치는 명령어를 알아두면 좋다. `ldc.i4.X`(정수 상수 X를 push), `ldloc.N`/`stloc.N`(지역변수 N번을 push/저장), `br.s`(조건 없이 무조건 분기), `brfalse.s`(스택 값이 false면 분기, `brtrue.s`의 반대), `newobj`(객체 생성자 호출), `throw`(예외 발생) 정도만 추가로 알아도 대부분의 검증 로직 IL을 읽을 수 있다.

## 화면/코드에서 보이는 징후
- dnSpyEx/ILSpy 언어 드롭다운을 IL로 바꾸면 `IL_XXXX:` 형태의 오프셋 라벨과 함께 명령어가 나열된다.
- `brtrue.s`/`brfalse.s`/`br.s` 뒤에 오는 대상은 항상 같은 메서드 안의 `IL_XXXX` 라벨이다 — 즉 함수 내부 점프만 표현하며, 다른 메서드로 건너뛰지 않는다.
- `call` 뒤에는 항상 완전한 메서드 시그니처(반환 타입, 선언 타입, 매개변수 타입)가 함께 적혀 있어서, 이름만 봐도 어떤 표준 라이브러리 함수를 호출하는지 바로 알 수 있다.

## 가장 먼저 할 것
디컴파일이 실패한 메서드를 만나면 당황하지 말고 우선 IL 표시 모드로 전환한 뒤, `ldstr`로 시작하는 줄들을 먼저 눈으로 훑어서 그 메서드 안에 어떤 문자열 리터럴이 있는지부터 파악한다. 문자열만 알아도 그 메서드가 무엇을 검증/출력하는지 대략적인 목적을 짐작할 수 있다.

## 단계별 절차

**1) 언어 표시를 IL로 전환**
dnSpyEx/ILSpy 상단 언어 드롭다운에서 **IL** 또는 **IL with C#**을 선택한다. 후자는 대응 관계를 눈으로 확인하기 좋아서 학습 단계에서는 이쪽을 추천한다.

**2) 스택 초기 상태를 0으로 놓고 한 줄씩 시뮬레이션**
종이나 메모장에 스택 상태를 적어가며 각 명령어가 push/pop하는 값을 따라간다. 위 예제처럼 표로 정리하면 실수가 줄어든다.

**3) call 시그니처로 라이브러리 함수 파악**
`call` 대상이 `System.String::op_Equality`면 `==`, `System.String::Concat`이면 `+`(문자열 연결), `System.Convert::ToInt32`면 형변환 등, 표준 라이브러리 호출은 C# 연산자/구문과 1:1로 매핑되는 경우가 많다.

**4) 분기 명령어로 조건문 구조 복원**
`brtrue.s`/`brfalse.s`/`br.s`의 목적지 라벨을 따라가며 `if`/`else`/`while`/`for`의 경계가 어디인지 표시해본다. 이때 `ceq` 뒤에 곧바로 `brtrue.s`나 `brfalse.s`가 오는 패턴은 거의 항상 원본 소스의 `==`/`!=` 비교 후 분기임을 기억해두면 빠르게 읽힌다.

**5) 필요하면 문자열/메서드 이름을 검색으로 교차 확인**
IL만으로 확신이 안 서면 같은 문자열이나 메서드가 다른 곳에서 어떻게 쓰이는지 [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)의 검색/Analyze 기능으로 교차 확인한다.

## 명령어/단축키
```text
dnSpyEx/ILSpy 언어 드롭다운: C# / IL / IL with C# 전환
dnSpyEx: 메서드 우클릭 → Edit IL Instructions (버전에 따라 지원, IL 직접 수정)
ILSpy: Ctrl+T 검색 필터를 Literal로 두고 문자열 먼저 훑기
```

## 출력 해석
- `call`로 호출된 메서드가 `System.String::op_Equality`이면 원본은 `==`, `System.String::op_Inequality`이면 `!=`다.
- `ceq` 바로 앞뒤에 `ldc.i4.0`이 있으면 "결과를 false와 비교"하는 것이므로 논리 부정(`!`) 패턴일 가능성이 높다. `ldc.i4.1`과 비교하면 반대로 "true와 비교"이므로 부정 없는 그대로의 조건이다.
- 스택이 비어 있어야 할 지점(예: 메서드 끝 `ret` 직전, `void` 반환)에 값이 남아 있는 것처럼 손으로 계산된다면 명령어 하나를 빠뜨리고 읽은 것이니 처음부터 다시 확인해야 한다.

## 흔한 실수
- CIL도 x86처럼 레지스터를 쓴다고 착각하고 `eax` 같은 걸 찾으려는 것. CIL에는 범용 레지스터가 없고 전부 스택으로 처리된다.
- `brtrue.s`가 "조건이 참이면 실행을 계속한다"는 뜻이라고 반대로 이해하는 것. 정확히는 "스택 값이 true(0이 아님)면 지정된 라벨로 점프한다"이며, false면 그냥 다음 줄로 진행한다.
- `ceq` 다음에 오는 분기 명령어를 확인하지 않고 `ceq`만 보고 바로 "이건 같다는 뜻이다"라고 단정하는 것. `ceq` 결과가 `brtrue.s`로 이어지는지 `brfalse.s`로 이어지는지에 따라, 그리고 직전에 비교 대상이 `0`(false)이었는지에 따라 실제 의미(긍정/부정)가 달라진다.
- IL 오프셋(`IL_0010` 등)이 파일 오프셋이나 가상 주소라고 착각하는 것. 이것은 해당 메서드 본문 안에서만 유효한 상대적 위치 라벨이다.

## 막혔을 때 다음 체크
- IL을 읽기 전에 애초에 도구부터 다시 정리하고 싶으면 → [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md), [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md)
- 문자열/메서드 이름 자체가 난독화되어 있어 추론이 어려우면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 문자열이 코드가 아니라 리소스에 암호화되어 저장돼 있을 수도 있으면 → [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)
- 네이티브 x86/x64 어셈블리와 비교해서 이해하고 싶으면 → Assembly Dictionary의 `CMP`, `JE/JZ`, `CALL` 항목(스택 대신 플래그 레지스터로 비교/분기하는 네이티브 방식과 대조해서 보면 이해가 빠르다)

## 미니 예제
위에서 다룬 `CheckPassword` IL을 다시 요약하면, `ldarg.0`(입력값 push) → `ldstr`(정답 문자열 push) → `call op_Equality`(비교) → `ceq`+`brtrue.s`(부정 후 분기)라는 뼈대만 알아보면, 클래스/메서드 이름이 `a.b(string c)`처럼 완전히 난독화되어 있어도 "매개변수를 `"flag{test}"`와 비교해서 같으면 통과 메시지를, 다르면 실패 메시지를 출력하는 함수"라는 결론에 도달할 수 있다. 이것이 디컴파일러 없이도 IL만으로 CTF 검증 로직을 읽어내는 기본기다.

## 관련 글
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0244 — ILSpy 기본 사용법
- REV-0247 — .NET 난독화 기초

## 출처/검증
- CIL 명령어 셋(`ldarg`, `ldstr`, `call`, `ceq`, `brtrue.s`, `ret` 등)의 스택 동작과 공식 정의: ECMA-335 Common Language Infrastructure(CLI) 표준 문서 기준 (2026-09-08 확인).
- `String.op_Equality`가 C# `==` 연산자와 대응된다는 점 및 디버그 빌드 IL 패턴: Microsoft Learn ".NET 컴파일 및 IL 생성" 관련 문서 및 Roslyn 컴파일러 공개 동작 기준.
