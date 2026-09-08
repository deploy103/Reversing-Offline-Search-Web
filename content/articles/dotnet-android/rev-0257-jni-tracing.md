---
id: REV-0257
title: "JNI 호출 Java에서 Native까지 추적"
slug: "rev-0257-jni-tracing"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [arm, arm64]
format: [APK, ELF]
tools: ["JADX", "apktool", "Ghidra", "readelf"]
keywords: ["JNI naming convention", "Java_com_example", "RegisterNatives", "JNIEnv", "네이티브 심볼 찾기"]
aliases: ["jni 함수 이름 규칙", "Java_ 심볼 찾기", "native 메서드 추적", "RegisterNatives 동적 등록"]
symptom_keywords: ["native 함수를 so에서 못 찾겠음", "Java_로 시작하는 심볼이 없음", "JNI 이름 규칙을 모름", "RegisterNatives가 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
자바 코드의 `native` 메서드 선언 하나는 JNI의 정해진 이름 변환 규칙에 따라 `.so` 안의 `Java_패키지_클래스_메서드명`이라는 심볼로 정확히 대응되며, 이 규칙만 알면 "자바에서 어떤 메서드가 native로 빠지는지"부터 "그 로직이 실제로 `.so`의 어느 함수에 있는지"까지 한 줄씩 손으로 추적할 수 있다.

## 언제 검색해야 하나
- [REV-0254](./rev-0254-native-library-so.md)에서 `native` 메서드와 `.so` 파일의 존재까지는 확인했는데, 정확히 어느 함수를 봐야 하는지 못 찾겠을 때
- `nm -D` 결과에 `Java_...`로 시작하는 심볼이 안 보여서 당황스러울 때
- 클래스나 메서드 이름에 특수문자(밑줄 `_` 등)가 있어서 JNI 심볼 이름 규칙이 헷갈릴 때
- `RegisterNatives`라는 용어를 처음 봤을 때
- Ghidra에서 네이티브 함수까지는 열었는데 이게 자바의 어느 인자에 대응하는지 파악이 안 될 때

## 핵심 개념
JNI(Java Native Interface)는 자바 VM과 네이티브(C/C++) 코드가 서로의 함수를 호출할 수 있도록 정의된 표준 인터페이스다. 자바 쪽에서 `native` 키워드로 선언한 메서드는, VM이 그 라이브러리가 로드될 때 "이 메서드 이름에 대응하는 네이티브 함수가 어디 있는지" 찾아서 연결(bind)해야 실제로 호출할 수 있다. 이 연결 방법은 크게 두 가지, **이름 규칙에 의한 정적 연결**과 **`RegisterNatives`에 의한 동적 연결**이 있다.

### 정적 연결: 이름 규칙(naming convention)
가장 기본적인 방식은, C/C++ 함수 이름을 정해진 규칙에 따라 지으면 JNI가 자동으로 그 이름을 찾아 연결해주는 것이다. 규칙은 다음과 같다.
```
Java_<패키지를 밑줄로 치환>_<클래스명>_<메서드명>
```
구체적인 변환 규칙:
1. 접두사 `Java_`를 붙인다.
2. 자바 패키지 이름의 점(`.`)을 전부 밑줄(`_`)로 바꾼다.
3. 클래스 이름을 이어 붙인다.
4. 메서드 이름을 이어 붙인다.
5. 만약 원래 패키지/클래스/메서드 이름 자체에 밑줄(`_`)이 있다면, 충돌을 피하기 위해 그 밑줄은 `_1`로 치환된다(이 규칙을 모르면 밑줄이 포함된 이름에서 심볼을 못 찾고 헤매게 된다).
6. 메서드가 오버로드(같은 이름, 다른 파라미터)되어 있다면, 이름 뒤에 파라미터 타입을 인코딩한 문자열이 추가로 붙는 "긴 이름(long name)" 규칙이 별도로 있다 — 이 경우는 흔치 않으므로 CTF에서는 대부분 짧은 이름 규칙만 알아도 충분하다.

**예시**
```java
package com.example.ctf;

public class NativeChecker {
    public native boolean verifyFlag(String input);
}
```
이 `verifyFlag` 메서드는 다음 심볼 이름으로 변환된다.
```
Java_com_example_ctf_NativeChecker_verifyFlag
```
패키지 `com.example.ctf`의 점이 밑줄로 바뀌고, 클래스 이름 `NativeChecker`와 메서드 이름 `verifyFlag`가 그대로 이어 붙었다.

만약 메서드 이름 자체에 밑줄이 있었다면(`verify_flag`), `_`가 `_1`로 바뀌어 `Java_com_example_ctf_NativeChecker_verify_1flag`처럼 된다.

### 실제 C/C++ 함수 시그니처
JNI 규칙으로 이름 붙은 네이티브 함수는 다음과 같은 고정 형태를 갖는다.
```c
JNIEXPORT jboolean JNICALL
Java_com_example_ctf_NativeChecker_verifyFlag(JNIEnv *env, jobject thiz, jstring input) {
    const char *cstr = (*env)->GetStringUTFChars(env, input, NULL);
    // ... 실제 검증 로직 ...
    (*env)->ReleaseStringUTFChars(env, input, cstr);
    return JNI_TRUE;
}
```
여기서 핵심은 **인자가 자바 쪽 시그니처보다 항상 2개 더 많다**는 점이다.
- 첫 번째 인자 `JNIEnv *env`: 이 스레드에서 JNI 함수(문자열 변환, 객체 필드 접근 등)를 호출할 때 쓰는 컨텍스트 포인터. 거의 모든 JNI 함수 호출에 이 값이 필요하다.
- 두 번째 인자 `jobject thiz`(인스턴스 메서드인 경우) 또는 `jclass clazz`(static 메서드인 경우): 자바 쪽의 `this`에 해당.
- 세 번째 인자부터가 자바 메서드에 실제로 선언된 파라미터(`jstring input`)와 순서대로 대응된다.

Frida로 네이티브 함수를 후킹할 때([REV-0256](./rev-0256-frida-basics.md) 참고) `args[0]`, `args[1]`, `args[2]`를 셀 때 이 순서를 꼭 기억해야 한다. 자바에서 첫 번째로 보이는 인자(`input`)는 네이티브 함수에서는 세 번째 인자(`args[2]`)다.

자바 타입과 JNI 타입의 대응 관계도 알아두면 좋다: `boolean`→`jboolean`, `int`→`jint`, `long`→`jlong`, `String`→`jstring`, 객체 배열/일반 객체→`jobject`, 자바 배열(`int[]`)→`jintArray` 등 전용 타입이 있다.

### 동적 연결: RegisterNatives
심볼 이름 규칙을 따르지 않고도 네이티브 메서드를 연결하는 방법이 있는데, 라이브러리가 로드될 때 자동 호출되는 `JNI_OnLoad` 함수 안에서 `(*env)->RegisterNatives(...)`를 직접 호출해 "이 자바 메서드는 이 함수 포인터에 연결하라"고 런타임에 명시적으로 등록하는 방식이다.
```c
static JNINativeMethod methods[] = {
    {"verifyFlag", "(Ljava/lang/String;)Z", (void *)my_verify_impl}
};

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env;
    (*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6);
    jclass clazz = (*env)->FindClass(env, "com/example/ctf/NativeChecker");
    (*env)->RegisterNatives(env, clazz, methods, 1);
    return JNI_VERSION_1_6;
}
```
이 방식을 쓰면 실제 구현 함수 이름은 `my_verify_impl`처럼 완전히 자유로운 이름이어도 되므로, `nm -D`로 `Java_...` 형태의 심볼을 검색해도 아무것도 안 나온다. 이는 CTF 문제에서 "일부러 심볼 이름 규칙을 안 쓰고 리버서를 헷갈리게 하려는" 의도적인 난독화 기법으로 자주 쓰인다. 이 경우 다음 방법으로 실제 구현 위치를 찾아야 한다.
- `JNI_OnLoad` 함수 자체를 찾아 디컴파일해서, `RegisterNatives` 호출에 넘겨지는 함수 포인터 배열(`methods`)을 직접 확인한다.
- Frida의 `Java.perform` + `implementation` 후킹은 심볼 이름과 무관하게 자바 쪽 클래스/메서드 이름만으로 동작하므로([REV-0256](./rev-0256-frida-basics.md) 참고), 심볼이 안 보여도 동적 관찰 자체는 그대로 가능하다.

## 화면/코드에서 보이는 징후
- `nm -D --defined-only libchecker.so | grep Java_`에서 심볼이 정상적으로 나오면 정적 이름 규칙을 쓰는 라이브러리다.
- 아무것도 안 나오면 strip되었거나 `RegisterNatives` 동적 등록 방식일 수 있으므로, `JNI_OnLoad` 심볼이 있는지 다시 확인한다.
- Ghidra에서 함수 목록에 `Java_com_example_ctf_NativeChecker_verifyFlag`처럼 긴 이름의 함수가 자동으로 인식되어 있으면 이름 규칙을 따르는 라이브러리라는 뜻이다.

## 가장 먼저 할 것
JADX에서 확인한 `native` 메서드의 정확한 패키지/클래스/메서드 이름을 위 변환 규칙에 따라 손으로 한 번 계산해보고, `nm -D` 또는 `readelf -sD`로 그 이름이 실제로 `.so`에 있는지 검색한다.

## 단계별 절차
1. JADX/smali에서 `native` 메서드의 전체 패키지 경로, 클래스 이름, 메서드 이름을 정확히 기록한다.
2. 패키지의 점을 밑줄로, 이름 안의 밑줄을 `_1`로 바꾸는 규칙을 적용해 예상 심볼 이름을 계산한다.
3. `nm -D --defined-only lib이름.so | grep <계산한 이름 일부>`로 실제 존재 여부를 확인한다.
4. 심볼이 있으면 Ghidra에서 그 이름으로 함수를 검색해 바로 이동한다.
5. 심볼이 없으면 `JNI_OnLoad` 함수를 찾아 `RegisterNatives` 호출부를 디컴파일하고, 등록된 함수 포인터 테이블에서 실제 구현 주소를 확인한다.
6. 함수를 찾았으면 인자 순서(`JNIEnv*`, `jobject/jclass`, 이후 실제 인자)를 기준으로 디컴파일 코드를 읽는다.

## 명령어/단축키
```bash
# 예상 심볼 이름으로 직접 검색
nm -D --defined-only libchecker.so | grep verifyFlag

# JNI_OnLoad 존재 여부 확인
nm -D --defined-only libchecker.so | grep JNI_OnLoad

# 심볼이 strip된 경우 문자열에서 힌트 찾기
strings libchecker.so | grep -E 'verifyFlag|NativeChecker'

# readelf로 동적 심볼 테이블 확인 (nm 대안)
readelf -sD libchecker.so | grep Java_
```

## 출력 해석
- `nm -D` 결과에 `T Java_com_example_ctf_NativeChecker_verifyFlag`처럼 `T`(text 섹션, 실제 실행 코드)로 표시되면 이 함수가 실제 코드로 존재한다는 뜻이다. `U`(undefined)로 표시되면 이 라이브러리가 그 심볼을 내부에서 쓰기만 하고 외부(다른 라이브러리)에서 가져와야 한다는 뜻이므로 다른 `.so`를 찾아야 한다.
- 밑줄이 포함된 자바 메서드 이름을 계산했는데 `nm` 결과와 안 맞으면, `_1` 치환 규칙을 빠뜨렸을 가능성이 크므로 다시 확인한다.
- `JNI_OnLoad`는 있는데 예상한 이름의 `Java_...` 심볼이 전혀 없다면 100% 동적 등록(`RegisterNatives`) 방식이다.

## 흔한 실수
- 클래스/메서드 이름의 밑줄(`_`)을 그냥 밑줄로만 치환해서 실제 심볼(`_1`로 치환되어야 함)과 다른 이름을 찾다가 "심볼이 없다"고 오판하는 것.
- static 메서드인데 인자 개수를 인스턴스 메서드처럼 세어서(두 번째 인자를 `jobject thiz`로 착각) 인자 인덱스를 하나씩 밀려서 읽는 것 — static native 메서드의 두 번째 인자는 `jclass`이지만, 개수 자체는 동일하게 앞에 2개가 추가된다는 점은 같다.
- 심볼이 하나도 안 보이는 것을 "이 라이브러리엔 native 구현이 없다"고 결론짓는 것. 대부분은 strip이나 `RegisterNatives` 때문이며, `JNI_OnLoad`를 반드시 확인해야 한다.
- 오버로드된 메서드(같은 이름, 다른 파라미터)가 있는데 짧은 이름 규칙만 검색해서 여러 후보 중 어느 게 맞는지 헷갈리는 것 — 이 경우 파라미터 타입까지 인코딩한 "긴 이름" 규칙이 필요하다는 것을 기억해야 한다.
- Frida로 후킹할 때 JNI 함수 인자 순서를 무시하고 `args[0]`을 자바 쪽 첫 번째 인자로 착각하는 것 — 항상 `args[0]=JNIEnv*`, `args[1]=this/class`, `args[2]`부터가 실제 자바 인자다.

## 막혔을 때 다음 체크
- `.so` 자체를 어떻게 꺼내고 기본 정보를 확인하는지 처음부터 다시 보고 싶다면 → [REV-0254 Native Library lib*.so가 있을 때](./rev-0254-native-library-so.md)
- 실행 중 인자 값을 직접 눈으로 확인하고 싶다면 → [REV-0256 Frida로 함수 관찰하는 기본 흐름](./rev-0256-frida-basics.md)
- ELF 자체의 심볼 테이블, 섹션 구조가 궁금하면 → [ELF 헤더 읽는 법](../linux-elf/rev-0089-elf-header.md)
- 자바 쪽 native 선언과 smali 상의 흔적을 다시 확인하고 싶다면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)

## 미니 예제
자바 코드가 다음과 같다고 하자.
```java
package com.example.ctf;

public class Native_Checker {
    public static native int check_input(String input);
}
```
패키지: `com.example.ctf` → `com_example_ctf`
클래스: `Native_Checker` → 밑줄이 있으므로 `Native_1Checker`
메서드: `check_input` → 밑줄이 있으므로 `check_1input`

전부 합치면 예상 심볼 이름은 다음과 같다.
```
Java_com_example_ctf_Native_1Checker_check_1input
```
```bash
$ nm -D --defined-only libchecker.so | grep check_1input
0000000000002a10 T Java_com_example_ctf_Native_1Checker_check_1input
```
정확히 일치하는 심볼을 찾았다. 이 함수는 `static native` 메서드이므로 C 시그니처는 다음과 같은 형태다.
```c
JNIEXPORT jint JNICALL
Java_com_example_ctf_Native_1Checker_check_1input(JNIEnv *env, jclass clazz, jstring input);
```
`args[0]`은 `JNIEnv*`, `args[1]`은 `jclass`(static이므로 `thiz`가 아니라 `clazz`), `args[2]`가 자바에서 넘긴 실제 `input` 문자열이다. 이 정보를 그대로 Ghidra의 함수 시그니처 편집이나 Frida의 `Interceptor.attach` 인자 인덱스에 반영하면, 정적/동적 분석 모두에서 정확한 값을 읽을 수 있다.

## 관련 글
- REV-0254 — Native Library lib*.so가 있을 때
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0252 — smali 기초 문법
- REV-0089 — ELF 헤더 읽는 법

## 출처/검증
- JNI 함수 이름 규칙(패키지 점→밑줄, 밑줄→`_1` 치환, 긴 이름 오버로드 규칙)은 Oracle 공식 JNI 명세(Java Native Interface Specification, "Resolving Native Method Names")를 기준으로 정리했다.
- `JNIEnv*`/`jobject`/`jclass` 인자 순서와 `RegisterNatives`/`JNI_OnLoad` 동작은 동일한 JNI 공식 명세 및 Android NDK 공식 문서(developer.android.com, "JNI tips")를 기준으로 설명했다.
- 위 코드 예제는 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
