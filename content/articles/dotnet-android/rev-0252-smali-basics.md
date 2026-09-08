---
id: REV-0252
title: "smali 기초 문법"
slug: "rev-0252-smali-basics"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["apktool", "JADX"]
keywords: ["smali", "smali 문법", "invoke-virtual", "move-result", "const-string", "if-eqz", "레지스터 v0 p0"]
aliases: ["smali란", "smali 어셈블리", "달빅 바이트코드 문법", "smali 레지스터"]
symptom_keywords: ["smali 코드를 못 읽겠음", "v0 p0가 뭔지 모름", "invoke-virtual이 뭔지 모름", "smali if문 해석 못함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
smali는 안드로이드 앱이 실제로 실행하는 Dalvik 바이트코드(`classes.dex`)를 사람이 읽고 쓸 수 있는 텍스트 형태로 표현한 어셈블리어이며, x86 어셈블리와 마찬가지로 레지스터·명령어·분기문의 조합으로 이루어져 있어서 문법 패턴 몇 가지만 익히면 짧은 메서드는 바로 읽을 수 있다.

## 언제 검색해야 하나
- apktool로 APK를 디코딩했더니 `.smali` 파일들이 나왔는데 이게 무슨 언어인지 모를 때
- JADX 디컴파일이 실패하거나 이상하게 나와서 원본 바이트코드 수준(smali)에서 직접 확인해야 할 때
- `v0`, `p0`, `invoke-virtual`, `move-result` 같은 단어의 의미를 모를 때
- smali 코드를 직접 패치(수정)해서 검증 로직을 우회하고 싶은데 문법을 몰라서 못 건드릴 때
- 자바 `if`문이 smali에서 어떻게 생기는지 감이 안 잡힐 때

## 핵심 개념
Dalvik(그리고 최신 안드로이드의 ART 런타임)은 x86이나 ARM 같은 실제 CPU 명령어 세트가 아니라, 가상의 **레지스터 기반 바이트코드**를 실행한다. 이 바이트코드를 그대로 16진수로 보면 사람이 읽을 수 없으므로, `baksmali`(smali의 디스어셈블러, apktool 내부에서 사용됨)라는 도구가 이를 사람이 읽고 쓸 수 있는 텍스트 표현으로 바꿔주는데, 이 텍스트 문법을 **smali**라고 부른다. 반대로 텍스트 smali를 다시 바이트코드로 조립하는 도구는 `smali`(어셈블러)라고 부르며, apktool의 `b`(build) 명령이 내부적으로 이걸 호출한다.

x86/ARM 어셈블리와 결정적으로 다른 점은, smali의 레지스터 수는 메서드마다 자유롭게 선언할 수 있고(`v0`, `v1`, `v2`, ... 얼마든지) CPU의 물리 레지스터가 아니라 그 메서드 전용의 로컬 변수 슬롯이라는 점이다.

### 클래스와 메서드 선언
```smali
.class public Lcom/example/ctf/MainActivity;
.super Landroidx/appcompat/app/AppCompatActivity;

.method public checkPassword(Ljava/lang/String;)Z
    .locals 2
    ...
.end method
```
- `.class public Lcom/example/ctf/MainActivity;` — 클래스 선언. `L`로 시작하고 `;`로 끝나는 표기는 자바의 타입 디스크립터(descriptor) 문법으로, 슬래시(`/`)는 자바에서의 점(`.`)에 해당한다. 즉 `Lcom/example/ctf/MainActivity;`는 `com.example.ctf.MainActivity` 클래스를 뜻한다.
- `.super` — 부모 클래스.
- `.method ... 이름(파라미터타입)리턴타입` — 메서드 시그니처. `(Ljava/lang/String;)Z`는 "String 하나를 인자로 받고 boolean(`Z`)을 반환한다"는 뜻이다. 자주 쓰이는 타입 기호: `V`(void), `Z`(boolean), `I`(int), `J`(long), `F`(float), `D`(double), `Ljava/lang/String;`(String 객체), `[I`(int 배열).
- `.locals N` — 이 메서드 안에서 쓸 지역 레지스터 개수. 인자(파라미터) 레지스터는 여기 포함되지 않는다.

### 레지스터: v0~vN vs p0~pN
smali 메서드 안에는 두 종류의 레지스터 이름이 나온다.
- `v0`, `v1`, `v2`, ... : `.locals`로 선언한 지역 변수용 레지스터.
- `p0`, `p1`, `p2`, ... : 메서드에 전달된 파라미터(인자) 레지스터. **인스턴스 메서드(static이 아닌 메서드)라면 `p0`은 항상 `this`(자기 자신 객체)**이고, 실제 첫 번째 인자는 `p1`부터 시작한다. `static` 메서드라면 `this`가 없으므로 `p0`부터가 첫 번째 인자다.

예를 들어 `.method public checkPassword(Ljava/lang/String;)Z` (static이 아님)에서 `p0`은 `this`, `p1`이 인자로 넘어온 `String`이다.

레지스터 표기에는 두 가지 스타일이 있는데, 위처럼 `v`/`p`를 분리해서 쓰는 것이 최신 baksmali의 기본(`--use-locals`)이고, 오래된 도구나 옵션에 따라 모든 레지스터를 `v0`부터 순서대로 쓰고 파라미터가 뒤쪽 v 번호에 배치되는 방식(`v` 전용 표기)도 있다. 둘 다 같은 내용을 표현하는 다른 표기법일 뿐이므로, `.locals` 값과 실제 쓰인 최대 `v` 번호를 비교해서 어떤 표기인지 구분하면 된다.

### 자주 나오는 명령어
- `const-string v0, "abc"` — 문자열 상수 `"abc"`를 `v0`에 저장한다. x86의 `mov`와 비슷한 역할이다.
- `const/4 v1, 0x1` — 작은 정수 상수(4비트 범위)를 레지스터에 저장한다. `const/16`, `const`는 더 큰 범위의 정수용이다.
- `invoke-virtual {p0, v0}, Lclass;->method(params)ret` — 객체의 가상 메서드(오버라이드 가능한 일반 메서드)를 호출한다. 중괄호 안은 인자 목록이며 첫 번째는 보통 호출 대상 객체(`this`)다.
- `invoke-static {p1}, Lclass;->method(params)ret` — static 메서드 호출. `this` 없이 인자만 넘긴다.
- `invoke-direct` — 생성자나 private 메서드처럼 오버라이드될 수 없는 메서드 호출.
- `move-result v1` — 방금 `invoke-*`로 호출한 메서드의 반환값을 `v1`에 옮긴다. **호출(invoke) 명령 자체는 반환값을 레지스터에 직접 넣지 않고, 반드시 바로 다음 줄의 `move-result`(또는 `move-result-object`, `move-result-wide`)로 받아야 한다**는 점이 x86과 다른 독특한 규칙이다.
- `if-eqz v1, :cond_label` — `v1`이 0(또는 false, 또는 null)이면 `:cond_label`로 분기한다. `if-nez`는 반대(0이 아니면 분기), `if-eq`/`if-ne`/`if-lt`/`if-ge` 등은 두 레지스터를 비교하는 버전이다.
- `return v1` / `return-void` / `return-object v0` — 메서드 종료 및 반환. 반환 타입에 따라 `return`(int/boolean 등), `return-object`(객체), `return-wide`(long/double) 중 하나가 쓰인다.

## 화면/코드에서 보이는 징후
apktool로 디코딩한 폴더의 `smali/` 아래에서 `.smali` 확장자 파일들을 열면 위와 같은 텍스트가 그대로 보인다. JADX에서도 우측 상단이나 설정에서 "Smali" 보기 모드를 켜면 자바 코드와 나란히 smali를 같이 볼 수 있는 버전도 있어 대조하며 익히기 좋다.

## 가장 먼저 할 것
아주 짧은 메서드(파라미터 1개, if문 하나짜리) 하나를 골라서 자바로 상상해보며 한 줄씩 손으로 번역해보는 연습을 가장 먼저 한다. 아래 미니 예제가 그 연습의 표준 형태다.

## 단계별 절차
1. `.method` 줄에서 시그니처를 읽어 파라미터 개수와 타입, 반환 타입을 파악한다.
2. `.locals N`을 확인해서 지역 레지스터가 몇 개인지 파악한다.
3. `p0`(있다면 `this`)부터 `p1`, `p2`, ...가 각각 원래 자바 코드의 어떤 인자였는지 매핑한다.
4. 위에서 아래로 한 줄씩 읽으며 `const-string`/`const`로 상수가 어디에 채워지는지 표시한다.
5. `invoke-*` 다음에 오는 `move-result*`를 짝지어서 "이 호출의 결과가 이 레지스터에 들어간다"고 기록한다.
6. `if-*` 분기와 라벨(`:cond_0` 등)을 따라가며 자바의 `if`/`else` 구조로 재구성한다.
7. `return` 계열 명령을 만나면 그 시점 레지스터 값이 메서드의 최종 반환값이라고 결론짓는다.

## 명령어/단축키
```bash
# apktool로 smali까지 디코딩
apktool d app.apk -o out

# smali 텍스트만 빠르게 검색 (예: 특정 문자열 상수를 참조하는 곳 찾기)
grep -rn "const-string" out/smali | grep "flag"

# 특정 클래스의 smali만 열기
less out/smali/com/example/ctf/MainActivity.smali
```

## 출력 해석
- `if-eqz v1, :cond_0` 뒤에 실패 처리 코드가 바로 이어지고, `:cond_0` 라벨 아래에 성공 처리 코드가 있다면 → "`v1`이 0이 아니어야(참이어야) 성공"이라는 뜻이다. 반대로 `:cond_0` 아래가 실패 코드라면 조건이 뒤집힌 것이므로 라벨이 어디를 가리키는지 항상 끝까지 따라가 봐야 한다.
- `move-result v1` 바로 앞 줄의 `invoke-virtual` 대상이 `Ljava/lang/String;->equals(Ljava/lang/Object;)Z`라면, 자바의 `a.equals(b)` 호출과 100% 동일하다. 즉 [REV-0196](../algorithms/rev-0196-strcmp-check-pattern.md)에서 다룬 `strcmp` 패턴의 안드로이드/자바 버전이라고 봐도 된다.
- 여러 `if-*`가 연쇄로 이어지고 각 조건이 실패하면 같은 라벨(`:fail`)로 모이는 구조라면, 자바의 `&&`로 묶인 여러 조건 검사가 컴파일된 형태다.

## 흔한 실수
- `p0`을 항상 "첫 번째 인자"로 착각하는 것. 인스턴스 메서드에서 `p0`은 `this`이며, 실제 첫 번째 매개변수는 `p1`부터다. `static` 메서드인지 아닌지(`.method` 줄에 `static` 키워드가 있는지)를 반드시 먼저 확인해야 한다.
- `invoke-*` 명령 자체가 값을 반환한다고 착각하는 것. 실제로는 바로 다음 `move-result*` 줄이 있어야 결과를 레지스터로 가져올 수 있고, 호출 결과를 쓰지 않는 코드라면 `move-result`가 아예 생략되기도 한다.
- `if-eqz`/`if-nez`처럼 이름 끝에 `z`가 붙은 명령을 "eq"(같다)/"ne"(다르다)로만 읽고 "0과 비교"라는 부분(`z` = zero)을 놓치는 것. `if-eqz v0, label`은 "`v0 == 0`이면 분기"이지, 다른 레지스터와 비교하는 게 아니다.
- 문자열 타입 디스크립터(`Ljava/lang/String;`)의 세미콜론을 문법 오류로 착각하고 지우는 것. smali에서는 객체 타입 디스크립터 끝에 반드시 `;`가 붙는 표기 규칙이다.
- smali를 손으로 고칠 때 `.locals` 숫자를 새로 추가한 레지스터 개수에 맞게 늘리지 않아서 재조립 후 `VerifyError`로 앱이 크래시나는 것.

## 막혔을 때 다음 체크
- 이 smali가 원래 코틀린 코드였고 유난히 코드가 길고 null 체크가 많다면 → [REV-0253 Java Kotlin 코드와 smali 연결](./rev-0253-smali-to-java-kotlin.md)
- smali를 어떻게 뽑고 다시 조립하는지 절차가 궁금하면 → [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)
- 같은 로직을 자바 소스 형태로 더 편하게 보고 싶다면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)

## 미니 예제
다음 자바 코드를 smali로 어떻게 컴파일되는지, 그리고 거꾸로 smali를 자바로 어떻게 다시 읽는지 함께 살펴본다.

**원본 자바 코드**
```java
public boolean checkPassword(String input) {
    if (input.equals("s3cr3t")) {
        return true;
    }
    return false;
}
```

**컴파일된 smali (개념적으로 재구성)**
```smali
.method public checkPassword(Ljava/lang/String;)Z
    .locals 2

    const-string v0, "s3cr3t"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1

    if-eqz v1, :cond_0
    const/4 v0, 0x1
    return v0

    :cond_0
    const/4 v0, 0x0
    return v0
.end method
```

**한 줄씩 번역**
1. `.method public checkPassword(Ljava/lang/String;)Z` — `p0`는 `this`, `p1`은 인자로 받은 `input` 문자열.
2. `const-string v0, "s3cr3t"` — `v0`에 리터럴 문자열 `"s3cr3t"`를 넣는다.
3. `invoke-virtual {p1, v0}, Ljava/lang/String;->equals(...)Z` — `p1.equals(v0)`를 호출한다. 즉 `input.equals("s3cr3t")`.
4. `move-result v1` — 방금 호출의 boolean 결과를 `v1`에 저장한다.
5. `if-eqz v1, :cond_0` — `v1`이 0(false)이면 `:cond_0`로 점프. 즉 같지 않으면 실패 분기로 간다.
6. `const/4 v0, 0x1` / `return v0` — (조건이 참일 때, 즉 문자열이 같을 때) 1(true)을 반환.
7. `:cond_0` 아래 `const/4 v0, 0x0` / `return v0` — 실패 시 0(false)을 반환.

즉 이 smali는 정확히 원본 자바 코드와 같은 의미이며, 정답 문자열이 `"s3cr3t"`라는 것도 `const-string v0, "s3cr3t"` 한 줄만 봐도 바로 알 수 있다. 이런 식으로 `const-string` → `invoke-virtual ...equals...` → `if-eqz` 3종 세트는 안드로이드 앱의 비밀번호/flag 검증에서 가장 자주 보이는 smali 패턴이므로 익혀두면 큰 도움이 된다.

## 관련 글
- REV-0251 — apktool 기본 사용법
- REV-0253 — Java Kotlin 코드와 smali 연결
- REV-0249 — JADX로 APK 분석 시작
- REV-0257 — JNI 호출 Java에서 Native까지 추적

## 출처/검증
- smali/baksmali 문법 및 명령어 의미는 공식 저장소(`JesusFreke/smali`, GitHub)의 문서와 wiki를 기준으로 정리했다.
- 타입 디스크립터 표기(`L...;`, `Z`, `I` 등)는 JVM/Dalvik 클래스 파일 명세의 필드 디스크립터 규칙을 기준으로 설명했다.
- 위 예제 코드는 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
