---
id: REV-0253
title: "Java Kotlin 코드와 smali 연결"
slug: "rev-0253-smali-to-java-kotlin"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["apktool", "JADX"]
keywords: ["smali 반복문", "companion object", "Intrinsics.checkNotNull", "코틀린 smali", "루프 smali", "goto smali"]
aliases: ["smali 루프 읽는 법", "코틀린 컴파일 결과", "companion object smali", "Intrinsics 체크"]
symptom_keywords: ["smali에 goto가 많아서 못 읽음", "코틀린 앱 smali가 너무 복잡함", "Intrinsics.checkNotNull이 뭔지 모름", "companion object가 smali에서 이상하게 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
smali 코드는 항상 원본 자바 또는 코틀린 소스에서 컴파일된 결과이므로, 반복문·조건문·메서드 호출이 smali에서 어떤 패턴으로 나타나는지 알면 JADX 디컴파일이 실패했을 때도 smali만 보고 원래 로직을 재구성할 수 있으며, 특히 코틀린으로 작성된 앱은 null 체크와 `companion object` 관련 코드가 자동으로 잔뜩 추가되어 자바보다 smali가 훨씬 장황(verbose)해진다는 점을 알아둬야 한다.

## 언제 검색해야 하나
- smali 코드에 `goto`, `:goto_0`, `:cond_1` 같은 라벨이 여러 개 얽혀 있어서 원래 반복문이 뭐였는지 감이 안 잡힐 때
- 코틀린으로 작성된 것으로 보이는 앱의 smali에 `Intrinsics.checkNotNull`, `Companion` 같은 낯선 이름이 계속 나올 때
- JADX가 특정 메서드를 디컴파일하지 못하고 깨진 코드나 주석만 남길 때, smali로 직접 원래 로직을 재구성해야 할 때
- REV-0252로 smali 기초 문법은 익혔는데 실제 앱의 좀 더 긴 메서드를 못 읽을 때

## 핵심 개념
[REV-0252](./rev-0252-smali-basics.md)에서 다룬 것은 분기 하나짜리 아주 짧은 메서드였다. 실제 CTF 앱은 반복문, 여러 단계의 조건 검사, 다른 클래스 메서드 호출이 섞인 조금 더 긴 코드가 대부분이다. 이 글에서는 그런 "조금 더 현실적인" smali를 자바/코틀린으로 되짚어 읽는 방법과, 코틀린이 자바보다 smali를 얼마나 더 복잡하게 만드는지를 다룬다.

### 반복문(loop)은 smali에서 결국 조건 분기 + goto
smali에는 `for`나 `while` 같은 반복문 전용 명령어가 따로 없다. 컴파일러는 모든 반복문을 "조건을 검사해서 반복 블록으로 들어가거나 빠져나가는 분기 + 블록 끝에서 시작 지점으로 되돌아가는 `goto`"의 조합으로 풀어버린다. 즉 x86 어셈블리에서 `for` 루프가 `cmp`/`jge`/`jmp`의 조합으로 보이는 것과 원리가 완전히 같다.

### 메서드 호출 체인
클래스 내부에서 다른 메서드를 부르거나, 다른 클래스의 static 메서드를 부르는 코드는 `invoke-static`/`invoke-virtual` 뒤에 정확한 클래스 경로가 그대로 노출되므로, 오히려 자바 소스보다 "이 메서드가 정확히 어느 클래스의 어느 시그니처를 호출하는지"를 smali에서 더 명확하게 확인할 수 있는 경우도 많다.

### 코틀린이 smali를 복잡하게 만드는 이유
코틀린 컴파일러는 코틀린 언어의 기능(null 안전성, 기본 인자, companion object, 확장 함수, 데이터 클래스 등)을 자바 바이트코드로 표현하기 위해 자바에는 없는 보조 코드를 자동으로 끼워 넣는다. 이 보조 코드가 smali에도 그대로 나타나서, 순수 자바 앱의 smali보다 코틀린 앱의 smali가 훨씬 길고 산만하게 느껴진다.

- **`Intrinsics.checkNotNull` / `Intrinsics.checkNotNullParameter`**: 코틀린은 함수 매개변수나 반환값에 non-null 타입(`String`처럼 `?`가 안 붙은 타입)을 지정하면, 컴파일러가 함수 진입부에 자동으로 null 검사 코드를 삽입한다. 이 검사는 `kotlin.jvm.internal.Intrinsics` 클래스의 static 메서드 호출로 나타난다.
```smali
invoke-static {p1, v0}, Lkotlin/jvm/internal/Intrinsics;->checkNotNullParameter(Ljava/lang/Object;Ljava/lang/String;)V
```
이 줄은 실제 로직과 무관한 "코틀린이 자동으로 넣은 안전장치"이므로, 검증 로직을 읽을 때는 그냥 건너뛰어도 된다. 반대로 이런 줄이 메서드 맨 앞에 여러 번 나온다면 "이 클래스는 코틀린으로 작성됐다"는 확실한 신호로 활용할 수 있다.

- **Companion object**: 코틀린의 `companion object`(자바의 static 멤버와 비슷한 역할)는 실제로는 별도의 내부 클래스(`ClassName$Companion`)로 컴파일되고, 원래 클래스에는 그 companion 인스턴스를 담는 `static final Companion Companion;` 필드가 생긴다. smali에서 `MainActivity$Companion` 같은 클래스 파일이 별도로 보이고, `MainActivity.smali` 안에 `sget-object v0, Lcom/example/ctf/MainActivity;->Companion:Lcom/example/ctf/MainActivity$Companion;` 같은 코드가 있다면 companion object를 거쳐서 무언가를 호출하고 있다는 뜻이다.

- **nullable 타입 검사**: `String?`처럼 nullable 타입을 다루는 코드는 실제 로직 분기 전에 `if-eqz`/`if-nez`로 null 여부를 먼저 검사하는 코드가 추가로 들어가는 경우가 많아, 진짜 로직에 해당하는 분기와 컴파일러가 넣은 안전장치용 분기를 구분해야 한다.

- **기본 인자(default argument)**: 코틀린에서 기본값이 있는 함수 매개변수를 쓰면, 컴파일러가 그 함수의 오버로드 버전을 하나 더 만들고 끝에 `$default`가 붙은 별도 메서드(`checkPassword$default`)를 생성한다. smali에서 이런 이름을 만나면 "코틀린 기본 인자 문법이 만든 자동 생성 메서드"라고 이해하면 된다.

이런 배경 지식이 없으면 코틀린 앱의 smali는 실제 로직보다 훨씬 길어 보여서 초보자가 쉽게 압도당한다. 핵심은 `Intrinsics`, `$Companion`, `$default`처럼 이름에 특징적인 패턴이 보이면 "이건 코틀린 컴파일러가 자동으로 넣은 부분"이라고 먼저 걸러내고, 남은 부분에서 진짜 검증 로직(문자열 비교, 반복문, 산술 연산)을 찾는 것이다.

## 화면/코드에서 보이는 징후
- `goto :goto_0`, `:goto_0`, `:cond_0`, `:cond_1` 같은 라벨이 한 메서드 안에 3개 이상 얽혀 있으면 반복문 + 조건 분기가 합쳐진 코드일 가능성이 크다.
- 메서드 맨 위 몇 줄이 전부 `Intrinsics.checkNotNullParameter` 호출이면 코틀린 파일이라는 신호다.
- 클래스 이름 뒤에 `$Companion`, `$WhenMappings`, `$1`(익명 클래스/람다) 같은 접미사가 붙은 별도 smali 파일이 여러 개 있으면 코틀린 특유의 컴파일 산출물이다.

## 가장 먼저 할 것
긴 메서드를 만나면 처음부터 한 줄씩 읽으려 하지 말고, 먼저 `:cond_`, `:goto_` 라벨이 몇 개나 있는지 스크롤로 훑어서 "이 메서드에 반복문이 있는지, 몇 단계 분기가 있는지" 전체 그림부터 파악한다. 그다음 `Intrinsics` 호출처럼 로직과 무관한 줄을 눈으로 걸러내고, 실제 값 비교(`invoke-virtual ...equals...`, `if-*`)가 있는 줄에만 집중한다.

## 단계별 절차
1. 메서드의 라벨(`:cond_N`, `:goto_N`) 목록을 먼저 훑어 전체 제어 흐름의 개수를 파악한다.
2. `goto :goto_N`이 있으면 그 라벨이 어디를 가리키는지 찾고, 보통 그 라벨이 반복 블록의 시작(조건 검사 지점)이라는 걸 확인한다.
3. `Intrinsics.checkNotNull*` 호출 줄은 로직에서 제외하고 넘어간다.
4. `$Companion` 참조가 있으면 해당 `$Companion.smali` 파일을 열어 실제 호출되는 메서드 본문을 확인한다.
5. 남은 코드에서 `const-string`, `invoke-virtual ...equals/compareTo...`, 산술 명령(`add-int`, `xor-int` 등), `if-*` 분기만 골라 순서대로 자바 의사코드로 옮겨 적는다.
6. 옮겨 적은 의사코드를 REV-0252에서 배운 요령으로 최종 자바/코틀린 스타일 코드로 정리한다.

## 명령어/단축키
```bash
# 특정 메서드 안의 라벨 개수 빠르게 세기
grep -c ':cond_\|:goto_' out/smali/com/example/ctf/MainActivity.smali

# Intrinsics 호출이 있는지로 코틀린 여부 빠르게 판별
grep -l "Intrinsics" out/smali/com/example/ctf/*.smali

# Companion 클래스 찾기
find out/smali -name "*\$Companion.smali"
```

## 출력 해석
- `goto :goto_0`가 메서드 끝부분에 있고 `:goto_0` 라벨이 메서드 앞쪽의 조건 검사 지점을 가리킨다면 → 전형적인 `while`/`for` 루프 구조다.
- `if-ge v1, v2, :cond_end` 형태로 두 값을 비교해서 루프를 빠져나가는 코드가 있다면 → 자바의 `for (i = 0; i < n; i++)`에서 `i < n` 조건 부분이다.
- `Intrinsics.checkNotNullParameter` 호출 뒤에 바로 실제 로직이 시작된다면, 그 함수의 코틀린 원본 시그니처는 `fun check(input: String): Boolean`처럼 `input`이 non-null 타입이었다는 뜻이다.

## 흔한 실수
- `Intrinsics.checkNotNull*` 호출을 실제 검증 로직의 일부로 착각해서 시간을 낭비하는 것. 이건 거의 항상 컴파일러가 자동으로 넣은 안전장치다.
- `goto`를 보고 "이건 스파게티 코드다, 원래 이렇게 짜여 있었을 것"이라 오해하는 것. smali에는 고급 반복문 문법이 없어서 모든 반복문이 `goto` 기반으로 컴파일될 뿐이며, 원본 코틀린/자바 코드에는 평범한 `for`/`while`이 있었을 가능성이 높다.
- companion object의 메서드 호출(`sget-object ...Companion...` 다음 `invoke-virtual`)을 보고 원래 클래스에 그 메서드가 있다고 착각하는 것. 실제 구현은 `$Companion.smali` 파일 안에 있다.
- 반복문 안에서 레지스터 값이 매 회전마다 바뀌는 것을 놓치고, 반복문 진입 시점의 값만 보고 전체 로직을 판단하는 것. 루프 안에서 값이 누적/변형되는 연산(`add-int/2addr`, `xor-int/2addr` 등)이 있는지 꼭 확인한다.

## 막혔을 때 다음 체크
- smali의 기본 문법(`invoke-*`, `move-result`, `if-eqz` 등)이 아직 헷갈리면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)
- JADX가 이 메서드를 그나마 자바처럼 보여줄 수 있는지 먼저 확인하고 싶다면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- 이 메서드가 결국 `System.loadLibrary`로 네이티브 함수를 부르는 것으로 끝난다면 → [REV-0254 Native Library lib*.so가 있을 때](./rev-0254-native-library-so.md)
- 반복문 안의 값 변형이 XOR/ADD 등 익숙한 패턴이라면 → [REV-0199 XOR 반복 변환 역산](../algorithms/rev-0199-xor-loop-inversion.md)에서 해당 변환의 역산 방법을 확인한다.

## 미니 예제
다음 코틀린 함수가 있다고 하자.
```kotlin
fun checkFlag(input: String): Boolean {
    var sum = 0
    for (c in input) {
        sum += c.code
    }
    return sum == 1337
}
```
이 함수는 문자열의 모든 문자 코드값을 더해서 1337이 되는지 검사하는 간단한 반복문이다. 컴파일된 smali는 대략 다음과 같은 형태가 된다(가독성을 위해 실제 baksmali 산출물을 단순화했다).
```smali
.method public final checkFlag(Ljava/lang/String;)Z
    .locals 4

    invoke-static {p1, v0}, Lkotlin/jvm/internal/Intrinsics;->checkNotNullParameter(Ljava/lang/Object;Ljava/lang/String;)V

    const/4 v0, 0x0        # sum = 0
    const/4 v1, 0x0        # i = 0 (인덱스)
    invoke-virtual {p1}, Ljava/lang/String;->length()I
    move-result v2         # v2 = input.length()

    :goto_0
    if-ge v1, v2, :cond_0   # i >= length 이면 루프 탈출
    invoke-virtual {p1, v1}, Ljava/lang/String;->charAt(I)C
    move-result v3          # v3 = input.charAt(i)
    add-int/2addr v0, v3    # sum += (int) c
    add-int/lit8 v1, v1, 0x1 # i++
    goto :goto_0

    :cond_0
    const/16 v3, 0x539      # 0x539 = 1337
    if-ne v0, v3, :cond_1
    const/4 v0, 0x1
    return v0

    :cond_1
    const/4 v0, 0x0
    return v0
.end method
```
읽는 순서를 따라가보면 다음과 같다.
1. `Intrinsics.checkNotNullParameter` 줄은 무시하고 넘어간다(코틀린이 자동 삽입한 null 체크).
2. `v0`(sum)과 `v1`(i)을 0으로 초기화, `v2`에 문자열 길이를 저장.
3. `:goto_0`부터가 루프의 조건 검사 지점 — `if-ge v1, v2, :cond_0`는 "i >= length면 `:cond_0`(루프 이후)로 탈출"이라는 뜻이다.
4. 루프 본문에서 `charAt(i)`를 호출하고 결과를 `sum`에 더한 뒤(`add-int/2addr`), `i`를 1 증가시키고(`add-int/lit8 v1, v1, 0x1`) 다시 `:goto_0`로 돌아간다.
5. 루프가 끝나면(`:cond_0`) `sum`을 상수 `0x539`(= 10진수 1337)와 비교해서 같으면 참을 반환한다.

이렇게 `Intrinsics` 호출을 걸러내고, `goto`/`cond` 라벨을 루프 구조로 재구성하고 나면, 원본 코틀린 코드와 거의 1:1로 대응되는 것을 확인할 수 있다. 문자별 코드값 합이 1337이 되는 문자열을 파이썬으로 역산해서 만들면 이 검사를 통과하는 입력을 구할 수 있다.

## 관련 글
- REV-0252 — smali 기초 문법
- REV-0249 — JADX로 APK 분석 시작
- REV-0254 — Native Library lib*.so가 있을 때
- REV-0257 — JNI 호출 Java에서 Native까지 추적

## 출처/검증
- Kotlin이 non-null 매개변수에 삽입하는 `Intrinsics.checkNotNullParameter` 호출과 companion object 컴파일 방식은 Kotlin 공식 문서(kotlinlang.org, "Calling Java from Kotlin"/"Java interoperability") 및 Kotlin 컴파일러(`kotlinc`)의 실측 바이트코드 산출물을 기준으로 정리했다.
- smali의 반복문/분기 컴파일 패턴(`goto`, `:cond_`, `:goto_` 라벨)은 baksmali 실측 산출물과 Dalvik 바이트코드 명세(Dalvik Executable format)를 기준으로 설명했다.
- 위 예제 코드는 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
