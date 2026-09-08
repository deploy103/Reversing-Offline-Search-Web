---
id: REV-0254
title: "Native Library lib*.so가 있을 때"
slug: "rev-0254-native-library-so"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [arm, arm64]
format: [APK, ELF]
tools: ["apktool", "JADX", "Ghidra", "readelf"]
keywords: ["System.loadLibrary", "lib.so", "native method", "JNI", "libs 폴더", "네이티브 라이브러리"]
aliases: ["안드로이드 so 파일 분석", "System.loadLibrary가 뭔지", "native 키워드 함수", "lib*.so 리버싱"]
symptom_keywords: ["코드에 System.loadLibrary가 있음", "native 키워드가 붙은 함수를 못 찾겠음", "lib 폴더에 so 파일이 있음", "자바 코드에 함수 본문이 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
자바/코틀린 코드에서 `System.loadLibrary("native")`와 함께 본문이 없는 `native` 메서드 선언이 보인다면, 실제 검증 로직이 자바 코드가 아니라 APK 안의 `lib/<아키텍처>/libnative.so`라는 네이티브 ELF 바이너리 안에 있다는 뜻이며, 이 순간부터 리버싱 작업은 JADX/smali 분석에서 Ghidra/IDA를 이용한 ARM ELF 정적 분석으로 완전히 전환해야 한다.

## 언제 검색해야 하나
- JADX로 연 자바 코드에 `static { System.loadLibrary("xxx"); }` 같은 줄이 보일 때
- 메서드 선언에 `public native int check(String input);`처럼 `native` 키워드는 있는데 `{ ... }` 본문이 없을 때
- apktool로 디코딩한 폴더 안에 `lib/arm64-v8a/`, `lib/armeabi-v7a/` 폴더가 있고 그 안에 `.so` 파일이 있을 때
- "이 앱은 코드가 너무 짧은데 뭔가 이상하다"고 느껴져서 숨겨진 로직이 어디 있는지 찾고 있을 때

## 핵심 개념
안드로이드 앱은 성능이 중요한 연산(암호화, 압축, 게임 물리 엔진)이나, 반대로 **역공학을 어렵게 만들기 위한 목적**으로 일부 로직을 C/C++로 작성한 뒤 컴파일해서 `.so`(공유 라이브러리, Linux ELF 포맷과 동일)로 앱에 포함시키는 경우가 많다. CTF에서는 후자의 목적, 즉 "자바 바이트코드는 smali로 쉽게 읽히니까, 진짜 flag 검증 로직은 네이티브 코드 안에 숨겨서 난이도를 올리는" 패턴이 매우 흔하다.

### JNI란 무엇인가
자바/코틀린 코드가 네이티브(C/C++로 컴파일된 기계어) 함수를 호출하려면 **JNI(Java Native Interface)**라는 다리가 필요하다. JNI는 자바 진영에서 "이 함수는 자바 코드로 구현되어 있지 않고, 나중에 로드될 네이티브 라이브러리 안에 있다"고 선언하는 방법과, 반대편 C/C++ 진영에서 "이 C 함수가 특정 자바 클래스의 특정 메서드에 대응한다"는 것을 이름 규칙(naming convention)으로 연결하는 방법을 함께 정의한다. 이 연결 규칙의 자세한 내용은 [REV-0257](./rev-0257-jni-tracing.md)에서 예제와 함께 다룬다.

### System.loadLibrary
```java
public class NativeChecker {
    static {
        System.loadLibrary("native-lib");
    }
    public native boolean checkFlag(String input);
}
```
`static { System.loadLibrary("native-lib"); }`는 이 클래스가 처음 사용될 때 `libnative-lib.so`라는 파일을 시스템 라이브러리 검색 경로(주로 APK 안의 `lib/<ABI>/` 폴더가 설치 시 앱 전용 네이티브 라이브러리 디렉터리로 복사됨)에서 찾아 프로세스 메모리에 로드하라는 뜻이다. 이름에 `lib` 접두사와 `.so` 확장자는 자동으로 붙으므로, `"native-lib"`라는 이름을 넘기면 실제로는 `libnative-lib.so` 파일을 찾는다.

`public native boolean checkFlag(String input);`처럼 메서드 선언 뒤에 `{ ... }` 본문 없이 세미콜론으로 끝나고 `native` 키워드가 붙어 있으면, "이 메서드의 실제 구현은 자바 코드에 없고, 로드된 네이티브 라이브러리 안에서 찾아야 한다"는 뜻이다. JADX나 smali 어디를 뒤져도 이 메서드의 본문은 나오지 않는다 — 애초에 자바 바이트코드 자체에 구현이 없기 때문이다.

### lib 폴더의 아키텍처별 구조
APK를 apktool로 디코딩하거나 그냥 압축을 풀면 다음과 같은 구조를 볼 수 있다.
```
lib/
├── armeabi-v7a/     (32비트 ARM)
│   └── libnative-lib.so
├── arm64-v8a/       (64비트 ARM, 최신 실기기 대부분)
│   └── libnative-lib.so
├── x86/             (32비트 x86, 에뮬레이터용)
│   └── libnative-lib.so
└── x86_64/          (64비트 x86, 에뮬레이터용)
    └── libnative-lib.so
```
같은 이름의 `.so`가 아키텍처별로 여러 개 들어있는 이유는, 실제 실기기(대부분 ARM)와 에뮬레이터(대부분 x86/x86_64)에서 각각 실행 가능하도록 같은 소스를 여러 타겟으로 컴파일해 함께 넣어두기 때문이다. 실기기에서 분석 중이면 `arm64-v8a`(또는 구형 기기라면 `armeabi-v7a`)를, 에뮬레이터나 Frida로 후킹하며 분석 중이라면 `x86_64`(또는 `x86`)를 열어야 한다는 점을 헷갈리지 않아야 한다. 어느 아키텍처를 선택하든 로직 자체는 동일하므로, 정적 분석 도구(Ghidra 등)를 다루기 더 편한 아키텍처를 골라도 무방하다.

### 왜 "리버싱 작업이 확장된다"고 표현하는가
`.so` 파일은 안드로이드 전용 포맷이 아니라 리눅스와 완전히 동일한 **ELF(Executable and Linkable Format)** 바이너리다. 즉 이 시점부터는 지금까지 다룬 apktool/JADX/smali 지식만으로는 부족하고, ELF 헤더 구조([../linux-elf/rev-0089-elf-header.md](../linux-elf/rev-0089-elf-header.md)에서 다룬 `e_machine`, entry point 등)와 함수/심볼 분석, 그리고 Ghidra나 IDA로 ARM(또는 x86) 어셈블리를 디스어셈블·디컴파일하는 작업이 함께 필요해진다. `e_machine` 값이 `EM_ARM`(40)이면 32비트 ARM, `EM_AARCH64`(183)이면 64비트 ARM으로 컴파일된 것이므로, ELF 헤더만 확인해도 어떤 명령어 세트로 디스어셈블해야 하는지 바로 알 수 있다.

## 화면/코드에서 보이는 징후
- JADX에서 클래스를 열었는데 메서드 개수는 몇 개 없고 대부분 `native` 키워드가 붙어 본문이 비어있다.
- `strings libnative-lib.so | grep -i Java_`처럼 검색했을 때 `Java_com_example_ctf_NativeChecker_checkFlag` 같은 이름이 나온다.
- apktool 디코딩 결과 최상위에 `lib/` 폴더가 있고, 그 안에 아키텍처별 `.so` 파일들이 있다.
- `file libnative-lib.so`를 실행하면 `ELF 64-bit LSB shared object, ARM aarch64, ...` 같은 결과가 나온다.

## 가장 먼저 할 것
JADX나 apktool 디코딩 결과에서 `lib/` 폴더가 보이는지, 그리고 자바 코드에 `System.loadLibrary`와 `native` 메서드가 있는지부터 확인한다. 있다면 지체 없이 `arm64-v8a/libxxx.so`(또는 분석 환경에 맞는 아키텍처)를 꺼내서 `file`과 `readelf -h`로 기본 정보를 확인하고 Ghidra로 로드한다.

## 단계별 절차
1. JADX에서 `System.loadLibrary("이름")`으로 로드하는 라이브러리 이름을 확인한다.
2. `native` 키워드가 붙은 메서드들의 자바 시그니처(클래스 전체 경로, 메서드 이름, 파라미터/반환 타입)를 적어둔다 — 이후 JNI 심볼 이름을 계산할 때 그대로 쓴다([REV-0257](./rev-0257-jni-tracing.md) 참고).
3. APK(zip) 또는 apktool 디코딩 결과의 `lib/arm64-v8a/lib이름.so`를 꺼낸다.
4. `file lib이름.so`, `readelf -h lib이름.so`로 아키텍처와 기본 헤더를 확인한다([../linux-elf/rev-0089-elf-header.md](../linux-elf/rev-0089-elf-header.md) 참고).
5. `nm -D --defined-only lib이름.so` 또는 `readelf -sD lib이름.so`로 익스포트된(외부에 공개된) 심볼 목록을 확인해서, 2단계에서 적어둔 자바 메서드에 대응하는 `Java_...` 이름의 함수가 있는지 찾는다.
6. Ghidra(또는 IDA)로 `.so` 파일을 열어 해당 함수부터 디스어셈블/디컴파일을 시작한다.
7. 정적 분석이 막히면 Frida로 해당 네이티브 함수의 인자/반환값을 직접 관찰한다([REV-0256](./rev-0256-frida-basics.md) 참고).

## 명령어/단축키
```bash
# APK 안의 so 파일 목록 확인 (APK는 zip이므로 unzip으로도 목록 확인 가능)
unzip -l app.apk | grep '\.so$'

# 특정 아키텍처의 so 파일만 추출
unzip app.apk 'lib/arm64-v8a/*' -d extracted

# 파일 종류/아키텍처 확인
file extracted/lib/arm64-v8a/libnative-lib.so

# ELF 헤더 확인
readelf -h extracted/lib/arm64-v8a/libnative-lib.so

# JNI 함수 심볼(Java_로 시작하는 이름) 찾기
nm -D --defined-only extracted/lib/arm64-v8a/libnative-lib.so | grep Java_
# nm이 없거나 strip된 바이너리라면:
strings extracted/lib/arm64-v8a/libnative-lib.so | grep Java_
```

## 출력 해석
- `readelf -h`의 `Machine` 필드가 `AArch64`면 64비트 ARM, `ARM`이면 32비트 ARM이다. Ghidra에서 프로젝트를 만들 때 이 정보에 맞는 프로세서 옵션을 선택해야 한다(대부분 자동 인식되지만 확인 습관을 들여둔다).
- `nm -D` 결과에 `Java_com_example_ctf_NativeChecker_checkFlag`가 보이면, 이게 바로 자바의 `checkFlag` native 메서드와 연결된 진짜 구현 함수다. 이 이름이 안 보이면 라이브러리가 strip되었거나 `RegisterNatives`라는 동적 등록 방식을 쓴 것일 수 있다(이 경우도 [REV-0257](./rev-0257-jni-tracing.md)에서 다룬다).
- 심볼 목록에 `JNI_OnLoad`가 있다면, 라이브러리가 로드되는 시점에 실행되는 초기화 함수가 있다는 뜻이므로 이 함수부터 확인하면 동적 심볼 등록 여부를 알 수 있다.

## 흔한 실수
- `.so` 파일을 JADX로 열려고 시도하는 것. JADX는 Dalvik/자바 바이트코드(`.dex`, `.apk`, `.jar`)만 다루며 ELF 네이티브 바이너리는 열 수 없다. `.so`는 반드시 Ghidra, IDA, radare2 같은 네이티브 바이너리 분석 도구로 열어야 한다.
- 여러 아키텍처 폴더 중 실행 중인 기기/에뮬레이터와 다른 아키텍처의 `.so`를 분석해서, Frida로 후킹할 때 심볼 주소가 안 맞아 혼란스러워하는 것. 정적 분석용 `.so`와 동적 분석(Frida) 대상 프로세스의 아키텍처를 항상 맞춰야 한다.
- `native` 메서드의 본문이 안 보인다고 "이 기능은 존재하지 않는다"고 오판하는 것. 오히려 native로 넘어갔다는 것은 그 로직이 더 중요해서(또는 숨기고 싶어서) C/C++로 옮겨졌을 가능성이 높다는 신호로 받아들여야 한다.
- 심볼이 strip(제거)되어 `nm -D`에 아무것도 안 나온다고 포기하는 것. `readelf -h`의 entry point나 문자열 검색, 또는 Frida의 `Module.getExportByName`/`Interceptor.attach`로 런타임에 함수 주소를 알아내는 우회 방법이 있다.

## 막혔을 때 다음 체크
- ELF 헤더를 어떻게 읽는지 기초부터 알고 싶으면 → [ELF 헤더 읽는 법](../linux-elf/rev-0089-elf-header.md)
- 자바 `native` 메서드 이름이 정확히 어떤 규칙으로 `.so` 안의 심볼 이름이 되는지 궁금하면 → [REV-0257 JNI 호출 Java에서 Native까지 추적](./rev-0257-jni-tracing.md)
- 정적 분석이 막혀서 실행하면서 인자/반환값을 직접 보고 싶다면 → [REV-0256 Frida로 함수 관찰하는 기본 흐름](./rev-0256-frida-basics.md)
- 애초에 이 native 메서드를 자바 코드 어디서 부르는지 다시 확인하고 싶다면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)

## 미니 예제
JADX에서 다음 자바 코드를 발견했다고 하자.
```java
public class NativeChecker {
    static {
        System.loadLibrary("checker");
    }
    public native boolean verify(String input);
}
```
이 코드만으로는 `verify`가 실제로 무엇을 검사하는지 전혀 알 수 없다. 다음 순서로 진행한다.
```bash
unzip app.apk 'lib/arm64-v8a/libchecker.so' -d extracted
file extracted/lib/arm64-v8a/libchecker.so
# ELF 64-bit LSB shared object, ARM aarch64, ...
nm -D --defined-only extracted/lib/arm64-v8a/libchecker.so | grep Java_
# 0000000000001234 T Java_com_example_ctf_NativeChecker_verify
```
`Java_com_example_ctf_NativeChecker_verify`라는 심볼이 주소 `0x1234`에서 발견되었다. 이제 이 주소를 Ghidra에서 열어 `libchecker.so`를 로드하고 해당 함수로 이동하면, 실제 flag 검증 어셈블리/디컴파일 코드를 볼 수 있다. 여기서부터는 일반적인 ARM 네이티브 바이너리 리버싱(레지스터 규약, 분기 명령, 문자열 비교 패턴)이 그대로 적용되며, 자바/smali 지식은 "이 함수가 자바의 어떤 메서드와 연결되어 있고 인자가 무엇인지" 파악하는 데까지만 쓰인다.

## 관련 글
- REV-0257 — JNI 호출 Java에서 Native까지 추적
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0249 — JADX로 APK 분석 시작
- REV-0089 — ELF 헤더 읽는 법

## 출처/검증
- `System.loadLibrary`, JNI `native` 메서드 선언 규칙은 Android 공식 개발자 문서(developer.android.com, "Get started with the NDK") 및 Oracle JNI 명세를 기준으로 정리했다.
- APK 내 `lib/<ABI>/` 디렉터리 구조와 ABI 종류(armeabi-v7a, arm64-v8a, x86, x86_64)는 Android NDK 공식 문서(ABI Management)를 기준으로 설명했다.
- `.so` 파일이 ELF 포맷이라는 사실 및 `readelf`/`nm` 출력 형식은 GNU binutils 공식 문서를 기준으로 확인했다(2026-09-08).
