---
id: REV-0976
title: "JNI 네이티브 함수 시그니처(Signature) 읽는 법"
slug: "rev-0976-jni-signature-reading"
category: "dotnet-android"
difficulty: "intermediate"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [JADX]
keywords: ["JNI 타입 디스크립터", "메서드 시그니처 문자열", "GetMethodID 시그니처", "Ljava/lang/String;", "배열 타입 디스크립터 [I [B"]
aliases: ["jni signature 읽는법", "GetMethodID 시그니처 문법", "자바 타입 디스크립터 표기", "JNI 메서드 시그니처 계산"]
symptom_keywords: ["(Ljava/lang/String;I)Z가 뭔지 모르겠다", "GetMethodID 세번째 인자가 뭔지 모르겠다", "배열 타입 디스크립터를 모르겠다", "메서드 시그니처 문자열을 손으로 계산 못하겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
JNI(및 JVM 클래스 파일 명세 전반)는 자바 타입을 `Ljava/lang/String;`, `[I`, `Z`처럼 문자열 하나로 압축해서 표현하는 **타입 디스크립터(descriptor)** 표기법을 쓰며, 이 표기 규칙만 알면 `GetMethodID`/`GetFieldID`에 넘기는 시그니처 문자열이나 Ghidra 디컴파일 코드에 박혀 있는 시그니처 리터럴을 직접 읽고 계산할 수 있다 — 이는 [REV-0257](./rev-0257-jni-tracing.md)에서 다룬 **심볼 이름 규칙**(함수 이름 자체를 어떻게 짓는가)과는 별개로, **함수의 인자/반환 타입을 어떻게 문자열로 표현하는가**에 대한 규칙이다.

## 언제 검색해야 하나
- Ghidra/JADX 디컴파일 결과에 `(Ljava/lang/String;I)Z` 같은 문자열 리터럴이 `GetMethodID` 호출의 인자로 나오는데 이게 무슨 뜻인지 모를 때
- `RegisterNatives`([REV-0257](./rev-0257-jni-tracing.md) 참고)로 등록되는 `JNINativeMethod` 배열 안의 시그니처 문자열을 손으로 해석해야 할 때
- Frida에서 `.overload(...)`([REV-0974](./rev-0974-frida-advanced-argument-hooking.md) 참고)에 넘길 정확한 타입 문자열을 계산해야 할 때
- 자바 메서드가 오버로드되어 있어서 "긴 이름(long name)" JNI 심볼과 함께 시그니처까지 구분해야 할 때
- `Ljava/lang/String;`처럼 세미콜론이 붙은 표기가 오타가 아니라 정식 문법이라는 것을 확인하고 싶을 때

## 핵심 개념

### 타입 디스크립터 — 자바 타입을 한 글자/한 문자열로
JVM 클래스 파일 명세(그리고 이를 그대로 계승한 JNI)는 타입을 표현할 때 사람이 쓰는 `String`, `int[]` 같은 표기가 아니라, 파싱하기 쉬운 압축된 문자열 표기를 쓴다.

**기본 타입(1글자 코드)**
| 코드 | 자바 타입 |
|---|---|
| `B` | byte |
| `C` | char |
| `D` | double |
| `F` | float |
| `I` | int |
| `J` | long |
| `S` | short |
| `Z` | boolean |
| `V` | void (반환 타입에만 쓰임) |

**참조 타입**: `L`로 시작해서 `;`로 끝나며, 그 사이에 클래스의 전체 경로를 슬래시(`/`)로 구분해 적는다. 예를 들어 `java.lang.String`은 `Ljava/lang/String;`이 된다. 자바의 점(`.`)이 JNI 표기에서는 슬래시(`/`)가 된다는 점, 그리고 반드시 끝에 세미콜론(`;`)이 붙는다는 점이 핵심이다(오타가 아니라 필수 문법).

**배열 타입**: 대괄호(`[`)를 원소 타입 앞에 붙인다. 다차원 배열은 `[`를 차원 수만큼 반복한다.
| 표기 | 의미 |
|---|---|
| `[I` | int[] |
| `[B` | byte[] |
| `[Ljava/lang/String;` | String[] |
| `[[I` | int[][] |

### 메서드 시그니처 — (인자타입들)반환타입
메서드 전체 시그니처는 괄호 안에 인자 타입들을 순서대로 이어붙이고, 괄호 뒤에 반환 타입을 붙이는 형태다.
```
(인자타입1인자타입2...)반환타입
```
예를 들어 자바 메서드가 다음과 같다면
```java
public boolean verify(String input, int attempts)
```
JNI 시그니처 문자열은 다음과 같이 계산된다.
```
(Ljava/lang/String;I)Z
```
괄호 안에 `Ljava/lang/String;`(첫 번째 인자, String)과 `I`(두 번째 인자, int)가 구분자 없이 그대로 이어붙고, 괄호 뒤에 `Z`(반환 타입, boolean)가 붙는다. 인자 사이에 쉼표나 공백이 전혀 없다는 점이 처음 보면 헷갈리기 쉬운 부분이다 — 각 타입 디스크립터 자체가 `;`나 정해진 길이로 끝나는 것을 알고 있으면 파서(그리고 사람도)가 어디서 끊어 읽어야 할지 알 수 있다.

### 이 시그니처 문자열이 실제로 쓰이는 곳
1. **`GetMethodID`/`GetStaticMethodID`**: 네이티브 코드가 자바 메서드를 호출하려면 먼저 그 메서드의 ID를 얻어야 하는데, 이때 메서드 이름과 함께 정확한 시그니처 문자열을 넘겨야 한다. 같은 이름의 오버로드 메서드가 있으면 시그니처가 다르므로 이 문자열로 정확히 어떤 오버로드인지 구분된다.
   ```c
   jmethodID mid = (*env)->GetMethodID(env, clazz, "verify", "(Ljava/lang/String;I)Z");
   ```
2. **`RegisterNatives`의 `JNINativeMethod` 배열**([REV-0257](./rev-0257-jni-tracing.md) 참고): 동적으로 네이티브 함수를 등록할 때도 각 항목에 이름, 시그니처, 함수 포인터 세 가지가 필요하다.
   ```c
   static JNINativeMethod methods[] = {
       {"verify", "(Ljava/lang/String;I)Z", (void *)my_verify_impl}
   };
   ```
3. **Frida의 `.overload(...)`**([REV-0974](./rev-0974-frida-advanced-argument-hooking.md) 참고): Frida는 사람이 읽기 쉬운 전체 클래스 이름(`"java.lang.String"`, `"[B"`)을 쓰지만, 그 표기 규칙의 뿌리는 여기서 다루는 JNI 디스크립터와 사실상 같은 체계에서 나왔다.

### 오버로드가 있을 때의 JNI "긴 이름" 규칙
[REV-0257](./rev-0257-jni-tracing.md)에서 다룬 짧은 이름 규칙(`Java_패키지_클래스_메서드`)은 같은 이름의 메서드가 오버로드 없이 하나뿐일 때만 통한다. 오버로드된 네이티브 메서드가 여러 개 있으면, 그중 하나를 제외한 나머지는 이름 뒤에 인자 타입을 추가로 인코딩한 "긴 이름"이 필요하다. 이때 인자 타입 부분은 위에서 설명한 디스크립터를 그대로 쓰되, 심볼 이름에 쓸 수 없는 문자(`;`, `[`, `/`)를 각각 `_2`, `_3`, `_`로 치환한 형태가 덧붙는다. CTF에서는 오버로드된 네이티브 메서드 자체가 흔치 않으므로, 이 부분은 "그런 경우가 있다" 정도로 알아두고 실제로 마주치면 짧은 이름으로 찾은 함수가 여러 오버로드 중 어느 것인지 시그니처 문자열로 교차 확인하는 것으로 충분하다.

## 화면/코드에서 보이는 징후
- Ghidra/IDA로 `JNI_OnLoad` 근처를 열었을 때 `"(Ljava/lang/String;I)Z"` 같은 문자열 상수가 `GetMethodID` 호출 인자 자리에 보임.
- strings 출력에 `(Ljava/lang/String;)V`, `[B`, `Ljava/lang/Object;` 같은 패턴이 반복해서 나타남 — 대부분 JNI 시그니처 문자열이다.
- Frida `.overload(...)` 스크립트를 짤 때 JADX가 보여주는 `String[]`, `byte[]` 같은 표기를 그대로 못 쓰고 변환이 필요함을 느낌.

## 가장 먼저 할 것
JADX/smali에서 후킹하거나 분석하려는 메서드의 정확한 자바 시그니처(파라미터 타입 목록, 반환 타입)부터 확인한다. 그 다음 위 표의 기본 타입 코드와 참조/배열 표기 규칙을 그대로 대입해서 손으로 디스크립터 문자열을 계산해본다.

## 단계별 절차
1. JADX/smali에서 대상 메서드의 자바 시그니처(예: `boolean verify(String input, int attempts)`)를 확인한다.
2. 각 인자 타입을 기본 타입 코드 또는 `L.../...;` 참조 타입, 또는 `[...` 배열 표기로 하나씩 변환한다.
3. 변환된 인자 디스크립터를 괄호 안에 순서대로 이어붙인다(구분자 없음).
4. 반환 타입도 같은 규칙으로 변환해 괄호 뒤에 붙인다.
5. 완성된 시그니처 문자열을 Ghidra 디컴파일 코드의 `GetMethodID` 호출이나 `RegisterNatives` 테이블에서 검색해 실제로 일치하는지 대조한다.
6. Frida `.overload(...)`용으로 쓸 경우, 위 JNI 디스크립터를 Frida가 요구하는 전체 클래스 이름 표기(`java.lang.String`, `[B` 그대로 등)로 다시 옮긴다.

## 명령어/단축키
```bash
# 바이너리에서 JNI 시그니처 패턴 문자열 찾기
strings libchecker.so | grep -E '^\(L|^\(\[|^\([A-Z]'

# GetMethodID 호출 주변 문자열 상수 확인 (Ghidra 디컴파일 결과 텍스트로 저장 후)
grep -B2 -A2 "GetMethodID" checker_decompiled.c
```

## 출력 해석
- 시그니처 문자열이 `(Ljava/lang/String;I)Z`로 확인되면: 인자는 `String`, `int` 순서 두 개, 반환은 `boolean`이다. 이 순서와 개수가 그대로 네이티브 함수의 세 번째 인자부터([REV-0257](./rev-0257-jni-tracing.md)의 `JNIEnv*`, `jobject/jclass` 다음)에 대응된다.
- `[Ljava/lang/String;`처럼 `[`와 `L...;`가 같이 나오면 "String 배열"이며, JNI 네이티브 코드에서는 `jobjectArray` 타입으로 받는다.
- 시그니처에 `L`이 여러 번 등장하는데 세미콜론 위치를 잘못 짚으면 타입 구분이 완전히 어긋나므로, 항상 `L`부터 다음 `;`까지를 한 덩어리로 묶어 읽어야 한다.

## 흔한 실수
- `Ljava/lang/String;`의 끝 세미콜론을 무시하고 다음 문자부터 다른 타입이 시작한다고 착각해서 인자 개수를 잘못 세는 것 — 세미콜론이 그 참조 타입의 끝을 표시하는 필수 구분자다.
- 배열 표기 `[I`를 "대괄호와 I는 별개의 타입"이라고 오해하는 것 — `[`는 반드시 바로 뒤의 타입과 붙어 "그 타입의 배열"이라는 하나의 단위를 이룬다.
- 자바의 점(`.`) 표기(`java.lang.String`)와 JNI의 슬래시(`/`) 표기(`Ljava/lang/String;`)를 섞어 써서 `GetMethodID` 호출이나 Frida `.overload(...)`가 대상을 못 찾는 것.
- 반환 타입이 `void`일 때 아무것도 안 쓰는 게 아니라 반드시 `V`를 명시해야 한다는 것을 잊는 것(예: `(I)V`).
- 시그니처 문자열이 길고 복잡할 때 손으로 세다가 인자 하나를 빠뜨리거나 순서를 바꿔 적어서, 실제로는 존재하지 않는 오버로드를 찾으려 헤매는 것.

## 막혔을 때 다음 체크
- JNI 함수 이름 자체의 명명 규칙(`Java_패키지_클래스_메서드`)과 `RegisterNatives` 동적 등록 구분이 헷갈리면 → [REV-0257 JNI 호출 Java에서 Native까지 추적](./rev-0257-jni-tracing.md)
- 이 시그니처 표기를 Frida `.overload(...)`에 실제로 적용하는 법이 궁금하면 → [REV-0974 Frida 스크립트로 함수 인자/반환값 후킹하기 심화](./rev-0974-frida-advanced-argument-hooking.md)
- 네이티브 함수 자체를 심볼/오프셋으로 후킹하는 절차가 궁금하면 → [REV-0975 Frida로 Native 라이브러리 함수 후킹하기](./rev-0975-frida-native-library-hooking.md)
- smali 상의 메서드 시그니처 표기(자바 타입 기호)와 비교하고 싶으면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)

## 미니 예제
Ghidra로 `JNI_OnLoad`를 디컴파일했더니 다음과 같은 코드가 나왔다고 하자(의사 코드로 단순화).
```c
jclass clazz = FindClass(env, "com/example/ctf/NativeChecker");
jmethodID mid = GetMethodID(env, clazz, "buildKey", "([BI)Ljava/lang/String;");
```
시그니처 `([BI)Ljava/lang/String;`를 한 조각씩 풀어보자.
- 괄호 안(인자부): `[B`(byte 배열) 다음에 `I`(int) — 즉 인자는 `byte[]` 하나, `int` 하나, 총 두 개.
- 괄호 뒤(반환부): `Ljava/lang/String;` — 반환 타입은 `String`.

따라서 이 메서드의 자바 원본 시그니처는 다음과 같이 복원된다.
```java
String buildKey(byte[] data, int seed);
```
이 정보를 그대로 Frida 스크립트의 `.overload("[B", "int")`에 적용하거나, JADX에서 `buildKey`를 검색해 실제 자바 코드와 대조하면 정확히 일치하는 것을 확인할 수 있다. 이렇게 시그니처 문자열 하나만으로도 네이티브 코드가 호출하려는 자바 메서드의 인자/반환 타입 전체를 손으로 복원할 수 있다.

## 관련 글
- REV-0257 — JNI 호출 Java에서 Native까지 추적
- REV-0974 — Frida 스크립트로 함수 인자/반환값 후킹하기 심화
- REV-0975 — Frida로 Native 라이브러리 함수 후킹하기
- REV-0252 — smali 기초 문법

## 출처/검증
- JNI 타입 디스크립터 표기(기본 타입 코드, `L...;` 참조 타입, `[` 배열 표기)와 메서드 시그니처 문법(`(인자들)반환`)은 Oracle 공식 JNI 명세(Java Native Interface Specification, "Type Signatures") 및 JVM 클래스 파일 명세(The Java Virtual Machine Specification, "Descriptors")를 기준으로 정리했다.
- JNI 오버로드 시 "긴 이름" 심볼 인코딩 규칙은 동일한 JNI 공식 명세("Resolving Native Method Names")를 기준으로 확인했다.
- 위 코드 예제는 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다 (2026-09-09 확인).
