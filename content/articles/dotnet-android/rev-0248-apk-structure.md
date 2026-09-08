---
id: REV-0248
title: "APK 파일 구조 기초"
slug: "rev-0248-apk-structure"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [x86, x64]
format: [APK]
tools: ["JADX"]
keywords: ["APK 구조", "AndroidManifest.xml", "classes.dex", "resources.arsc", "APK 서명", "META-INF"]
aliases: ["APK란", "APK 파일 열어보는 법", "안드로이드 앱 구조", "APK zip 구조", "dex 파일이란"]
symptom_keywords: ["APK 파일을 처음 받았는데 뭘 봐야할지 모름", "AndroidManifest.xml이 뭔지 모름", "classes.dex가 뭔지 모름", "APK를 압축 풀면 나오는 폴더들이 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
APK(Android Package)는 실제로는 **ZIP 압축 컨테이너**일 뿐이며, 그 안에 앱 실행에 필요한 모든 것 — 권한/컴포넌트 정의(`AndroidManifest.xml`), 컴파일된 자바/코틀린 바이트코드(`classes.dex`), 컴파일된 리소스 테이블(`resources.arsc`), 원본 리소스 파일(`res/`), 네이티브 라이브러리(`lib/`), 서명 정보(`META-INF/`)가 정해진 이름의 폴더/파일로 들어있으므로, 압축을 풀어 이 이름들만 알아보면 APK 분석의 첫 그림을 잡을 수 있다.

## 언제 검색해야 하나
- APK 파일을 처음 받아서 압축을 풀어봤는데 나오는 폴더/파일 이름(`AndroidManifest.xml`, `classes.dex`, `res/`, `lib/`, `META-INF/`)이 각각 뭘 하는 건지 모를 때
- APK가 실제로 ZIP 포맷이라는 걸 몰라서 "어떤 전용 도구로만 열어야 하나?" 헷갈릴 때
- JADX 같은 도구로 분석을 시작하기 전에 APK 내부 구조를 먼저 전체적으로 정리하고 싶을 때
- `classes.dex`와 `.NET`의 IL, 네이티브 PE의 코드 섹션이 어떻게 다른지 비교하며 이해하고 싶을 때

## 핵심 개념

### APK는 그냥 ZIP이다
APK 확장자를 `.zip`으로 바꾸면 대부분의 압축 프로그램(7-Zip, WinRAR 등)으로 그대로 열린다. 이것은 우연이 아니라 공식 스펙이다 — APK는 JAR(Java Archive)와 마찬가지로 표준 ZIP 포맷을 그대로 사용하는 컨테이너다. 이 사실을 알면 "APK를 열려면 반드시 전용 도구가 있어야 한다"는 부담이 사라지고, 구조를 파악하는 첫 단계는 그냥 압축 풀기라는 것을 알 수 있다. 다만 코드/리소스가 이진 형태로 컴파일되어 있어서, 압축을 풀어도 사람이 바로 읽을 수 있는 것은 아니다. 그 이진 포맷들을 해석해주는 것이 JADX 같은 전용 분석 도구의 역할이다.

### 압축을 풀면 나오는 주요 항목
```
MyApp.apk (ZIP)
 ├─ AndroidManifest.xml     앱 메타데이터 (이진 XML 형식)
 ├─ classes.dex             컴파일된 Java/Kotlin 바이트코드 (DEX)
 ├─ classes2.dex, ...       코드량이 많으면 여러 개로 분할(멀티덱스)
 ├─ resources.arsc          컴파일된 리소스 테이블(문자열, 스타일, ID 매핑)
 ├─ res/                    이미지, 레이아웃, 문자열 XML 등 원본 리소스
 ├─ assets/                 컴파일되지 않은 원본 파일(임의 형식 데이터, DB 등)
 ├─ lib/                    네이티브 라이브러리(.so, ARM/x86 아키텍처별 폴더)
 └─ META-INF/               서명 인증서, 매니페스트 체크섬(APK 서명 정보)
```

### AndroidManifest.xml — 앱의 설계도
모든 APK는 루트에 `AndroidManifest.xml`을 반드시 포함한다. 이 파일은 앱 패키지명, 최소/타깃 Android SDK 버전, 사용하는 권한(`<uses-permission>`), 그리고 앱을 구성하는 4대 컴포넌트 — Activity(화면), Service(백그라운드 작업), BroadcastReceiver(이벤트 수신), ContentProvider(데이터 공유) — 를 선언한다. 리버싱 관점에서는 이 파일만 봐도 "이 앱이 어떤 권한을 요구하는지", "어떤 화면(Activity)에서 시작하는지(`intent-filter`의 `MAIN`/`LAUNCHER`)", "외부에 노출된 컴포넌트가 있는지(`exported="true"`)"를 빠르게 파악할 수 있다. 단, 압축을 풀어 원본을 텍스트 에디터로 열면 사람이 읽을 수 없는 **이진 XML(AXML)** 형식이므로, 반드시 JADX 같은 도구로 디코딩해서 봐야 한다.

### classes.dex — 컴파일된 앱 코드
Android 앱은 Java 또는 Kotlin으로 작성되지만, 일반 JVM용 `.class` 파일로 컴파일되는 대신 **DEX(Dalvik Executable)**라는 Android 전용 바이트코드 포맷으로 다시 변환되어 `classes.dex`에 담긴다. DEX는 여러 클래스 파일을 하나로 합치고 문자열/타입/메서드 테이블을 공유하도록 최적화된 포맷으로, Dalvik 또는 ART(Android Runtime)가 이를 실행한다. .NET의 CIL과 마찬가지로 DEX도 원본 소스에 가까운 정보(클래스명, 메서드명, 타입)를 상당 부분 보존하고 있어서, JADX 같은 도구로 자바 소스에 가까운 형태로 디컴파일할 수 있다. 다만 이는 [REV-0245](./rev-0245-cil-to-csharp.md)에서 다룬 CIL과는 완전히 다른 바이트코드 포맷이며, 명령어 집합도 다르다는 점에 주의해야 한다. 코드가 많은 앱은 하나의 DEX가 담을 수 있는 메서드 개수(약 65,536개) 제한 때문에 `classes2.dex`, `classes3.dex`처럼 여러 개로 나뉘는 **멀티덱스** 구조를 갖기도 한다.

### resources.arsc와 res/ — 리소스 두 갈래
`res/` 폴더에는 이미지(`drawable/`), 레이아웃(`layout/`), 문자열(`values/strings.xml`) 등 리소스 원본이 들어 있지만, 빌드 과정에서 이 리소스들 중 다수(특히 XML 기반 리소스, 문자열 테이블)는 컴파일되어 `resources.arsc`라는 단일 이진 테이블로 합쳐진다. 이 테이블은 리소스 ID(정수)와 실제 값(문자열, 참조 등)을 매핑하는 역할을 하며, 코드에서 `R.string.app_name` 같은 식으로 참조되는 리소스 ID가 실제로 어떤 값인지 알아내려면 이 `resources.arsc`를 해석해야 한다. JADX는 APK를 열 때 이 테이블을 자동으로 해석해서 `res/values/strings.xml` 같은 읽을 수 있는 형태로 복원해준다.

### lib/ — 네이티브 코드
많은 앱, 특히 게임이나 성능이 중요한 앱, 또는 안티 디버깅/난독화가 강한 앱은 일부 로직을 Java/Kotlin이 아니라 **C/C++로 작성해 JNI(Java Native Interface)를 통해 호출**한다. 이런 네이티브 코드는 컴파일되어 `lib/{아키텍처}/*.so` (예: `lib/arm64-v8a/libnative.so`) 형태로 APK에 포함된다. 이 `.so` 파일은 일반 ELF 공유 라이브러리이므로, JADX가 아니라 Ghidra나 IDA 같은 네이티브 디스어셈블러로 분석해야 한다. 즉 하나의 APK 안에서도 "자바/코틀린으로 된 부분"과 "네이티브 코드로 된 부분"이 함께 있을 수 있고, 두 부분은 서로 다른 분석 도구가 필요하다.

### META-INF/ — 서명과 무결성
`META-INF/` 폴더에는 `MANIFEST.MF`(각 파일의 체크섬 목록), `CERT.SF`(서명 대상 목록의 해시), `CERT.RSA`(또는 `.DSA`, 개발자 서명 인증서) 같은 파일이 들어 있다. Android는 서명되지 않은 APK의 설치를 기본적으로 허용하지 않으며, 이 서명은 "누가 이 앱을 만들었는지"를 증명하고 업데이트 시 동일 서명자인지 검증하는 데 쓰인다. 최신 Android는 이보다 발전된 **APK Signature Scheme v2/v3**(서명 블록을 ZIP 구조 자체에 별도로 삽입)도 함께 지원하지만, 기본 개념(체크섬 + 인증서로 무결성/출처 증명)은 동일하다.

## 화면/코드에서 보이는 징후
- 파일 탐색기에서 APK 확장자를 `.zip`으로 바꾸면 일반 압축 프로그램으로 내용물이 그대로 보인다.
- JADX로 APK를 열면 좌측에 `Source code`(디컴파일된 자바 코드), `Resources`(리소스), `AndroidManifest.xml` 등의 탭/트리가 자동으로 구성된다.
- 압축을 풀었을 때 `lib/arm64-v8a/`, `lib/armeabi-v7a/`, `lib/x86_64/` 처럼 아키텍처별 폴더가 여러 개 보이면 네이티브 코드가 여러 CPU 아키텍처를 지원하도록 빌드된 것이다.

## 가장 먼저 할 것
APK 파일을 받으면 바로 JADX부터 켜기 전에, 우선 압축 프로그램으로 열어(또는 확장자를 `.zip`으로 바꿔서) 최상위 폴더 구조를 30초만 훑어본다. `lib/` 폴더가 있는지(네이티브 코드 여부), `classes.dex`가 하나뿐인지 여러 개인지(멀티덱스 여부), `assets/`에 수상한 파일(암호화된 리소스, DB 등)이 있는지를 먼저 파악하면 이후 JADX 분석의 우선순위를 정하기 쉬워진다.

## 단계별 절차

**1) 압축 해제로 전체 구조 훑기**
`.apk`를 `.zip`으로 바꾸거나 7-Zip 등으로 직접 연 뒤 최상위 목록을 확인한다.

**2) AndroidManifest.xml 확인**
루트의 `AndroidManifest.xml`은 이진 형식이라 직접 읽을 수 없으므로, JADX나 `apktool`로 디코딩해서 패키지명, 권한, 컴포넌트, 시작 Activity를 확인한다.

**3) classes.dex 개수 확인**
`classes.dex`만 있는지 `classes2.dex` 이상이 더 있는지 확인해서 코드 규모(멀티덱스 여부)를 가늠한다.

**4) lib/ 폴더 유무로 네이티브 코드 여부 판단**
`lib/` 폴더가 있으면 일부 로직이 네이티브(`.so`)에 있을 수 있다는 뜻이므로, 자바 코드만 보고 전체 로직을 판단하지 않도록 주의한다.

**5) resources.arsc와 res/ 관계 이해**
문자열 등 리소스 값이 코드에서 안 보이면 `R.string.xxx` 같은 리소스 참조를 따라 `resources.arsc`(JADX가 자동 복원해주는 `res/values/strings.xml`)를 확인해야 한다는 것을 기억해둔다.

**6) META-INF로 서명 확인**
서명 인증서 유무/내용으로 이 APK가 공식 배포판인지, 리패키징(재서명)된 변형본인지 짐작할 단서를 얻는다.

## 명령어/단축키
```text
APK를 ZIP으로 취급해서 압축 해제: 확장자를 .zip으로 변경 후 압축 프로그램으로 열기
apktool d MyApp.apk -o out/   AndroidManifest.xml과 res/를 사람이 읽을 수 있는 형태로 디코딩
JADX: 파일을 창에 드래그 앤 드롭하여 APK를 열고 자동 디컴파일
```

## 출력 해석
- `AndroidManifest.xml`에서 `android:debuggable="true"`가 보이면 디버깅이 허용된 빌드(테스트/개발용 또는 의도적으로 취약하게 만든 CTF용)일 가능성이 높다.
- `minSdkVersion`/`targetSdkVersion` 값으로 이 앱이 지원하는 Android 버전 범위를 알 수 있고, 오래된 `targetSdkVersion`은 최신 보안 정책(권한 모델 등)이 느슨하게 적용된다는 뜻이기도 하다.
- `lib/` 안의 `.so` 파일 이름과 개수를 보면 이 앱이 네이티브 코드에 얼마나 의존하는지 가늠할 수 있다. 이름이 `libil2cpp.so`라면 Unity(IL2CPP) 게임일 가능성이 매우 높다는 특징적인 신호다.

## 흔한 실수
- APK를 무조건 전용 도구로만 열 수 있다고 생각해서 구조 파악 없이 바로 무거운 분석 도구부터 켜는 것. ZIP이라는 사실만 알아도 빠르게 훑어볼 수 있다.
- `classes.dex`가 앱의 전체 로직이라고 가정하고 `lib/`의 네이티브 코드를 놓치는 것. 안티 리버싱이 강한 앱일수록 핵심 로직을 네이티브로 옮겨두는 경우가 흔하다.
- `resources.arsc`를 무시하고 코드에 하드코딩된 문자열만 찾다가, 실제로는 리소스 문자열 테이블에 있는 값을 놓치는 것.
- APK 서명(`META-INF/`)이 있다고 해서 내용이 변조되지 않았다고 오해하는 것. 리패키징 도구로 코드를 수정한 뒤 자체 서명으로 재서명하면 서명 자체는 유효하게(다른 인증서로) 생성될 수 있으므로, 서명 존재 여부가 아니라 서명 발급자(인증서)가 원래 개발자와 같은지를 확인해야 한다.

## 막혔을 때 다음 체크
- JADX로 실제로 이 구조를 열어서 분석하는 방법이 궁금하면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- DEX 바이트코드가 .NET IL과 어떻게 다른지 비교하며 이해하고 싶으면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 네이티브 `.so` 라이브러리 자체를 분석해야 하면 → Linux/ELF 카테고리의 공유 라이브러리 분석 관련 글을 참고한다.

## 미니 예제
CTF에서 받은 `challenge.apk`의 확장자를 `.zip`으로 바꿔 열어보니 최상위에 `AndroidManifest.xml`, `classes.dex`, `resources.arsc`, `res/`, `META-INF/`가 보이고 `lib/` 폴더는 없다. `lib/`가 없다는 것은 이 문제의 핵심 로직이 네이티브 코드가 아니라 순수 Java/Kotlin(`classes.dex`) 안에 있을 가능성이 높다는 뜻이므로, 다음 단계에서는 곧바로 JADX로 `classes.dex`를 디컴파일해서 코드를 읽는 데 집중하면 된다는 분석 우선순위를 세울 수 있다.

## 관련 글
- REV-0249 — JADX로 APK 분석 시작
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0242 — .NET 바이너리 식별과 첫 접근

## 출처/검증
- APK 구조(ZIP 컨테이너, `AndroidManifest.xml`, `classes.dex`, `resources.arsc`, `lib/`, `META-INF/`)와 DEX/멀티덱스 개념: Android 공식 개발자 문서(developer.android.com, "APK 구성" 및 "Multidex support" 항목) 기준 (2026-09-08 확인).
- APK 서명 체계(META-INF, Signature Scheme v2/v3): Android 공식 개발자 문서 "APK 서명" 항목 기준.
