---
id: REV-0250
title: "AndroidManifest.xml에서 단서 찾기"
slug: "rev-0250-androidmanifest-clues"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["apktool", "JADX", "Frida", "adb"]
keywords: ["AndroidManifest.xml", "permission", "exported", "intent-filter", "package name", "minSdkVersion", "targetSdkVersion"]
aliases: ["안드로이드 매니페스트 분석", "AndroidManifest 읽는 법", "exported activity 찾기", "매니페스트 권한 확인"]
symptom_keywords: ["AndroidManifest.xml이 바이너리로 보임", "어떤 액티비티부터 봐야 할지 모름", "권한 목록이 뭘 의미하는지 모름", "exported true가 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`AndroidManifest.xml`은 앱을 실제로 실행하거나 코드를 한 줄도 읽기 전에, "이 앱이 무엇을 할 수 있고 어디서부터 공격/분석을 시작해야 하는지"를 알려주는 안드로이드 앱의 설계도이며, 특히 권한(permission) 목록과 `exported` 속성이 붙은 컴포넌트가 CTF에서 가장 먼저 확인해야 할 단서다.

## 언제 검색해야 하나
- APK를 받자마자 어디부터 봐야 할지 막막할 때
- apktool이나 JADX로 연 `AndroidManifest.xml`에 나온 태그들(`<activity>`, `<service>`, `<receiver>`, `<provider>`)의 의미를 모를 때
- `exported="true"`라는 속성이 왜 중요한지 궁금할 때
- `intent-filter`가 뭘 뜻하는지, 앱을 어떻게 실행시켜야 할지 감이 안 잡힐 때
- 문제 설명에 "이 액티비티를 직접 실행해보라"는 식의 힌트가 있을 때

## 핵심 개념
모든 안드로이드 앱은 APK 최상위에 `AndroidManifest.xml`이라는 파일을 하나 반드시 갖는다. 이 파일은 앱을 설치·실행하기 전에 시스템(정확히는 `PackageManager`)이 먼저 읽는 메타데이터로, 앱의 패키지 이름, 필요한 권한, 어떤 화면(액티비티)들이 있는지, 백그라운드에서 도는 서비스가 있는지, 다른 앱이 이 앱의 어떤 부분을 실행시킬 수 있는지를 전부 선언해 놓은 문서다. 실행 코드(로직)는 하나도 들어있지 않지만, "이 앱이 무엇을 하도록 설계되었는가"에 대한 전체 지도 역할을 한다.

CTF 관점에서 이 파일이 중요한 이유는, 실제 디컴파일된 자바/코틀린 코드를 한 줄도 안 읽어도 앱의 공격 표면(attack surface)과 기능 구조를 대략 파악할 수 있기 때문이다. 예를 들어 액티비티가 10개 있는데 그중 하나만 `exported="true"`로 설정돼 있다면, 문제 출제자는 "이 액티비티부터 봐라"라는 신호를 준 것이나 마찬가지다.

### 패키지 이름과 컴포넌트 이름
`<manifest package="com.example.ctf">`의 `package` 속성은 앱의 고유 식별자다. `adb shell pm list packages`로 설치된 패키지를 찾거나, `adb shell run-as com.example.ctf`로 앱 데이터 디렉터리에 접근할 때 이 값을 그대로 써야 하므로 가장 먼저 적어둘 값이다. 각 컴포넌트(`<activity android:name=".MainActivity">`)의 `android:name`은 실제 자바/코틀린 클래스 이름과 매칭되며, 점(`.`)으로 시작하면 패키지 이름이 앞에 자동으로 붙는다는 것도 기억해두면 JADX에서 클래스를 찾을 때 헷갈리지 않는다.

### 권한(uses-permission)
`<uses-permission android:name="android.permission.INTERNET"/>` 같은 줄은 앱이 요청하는 권한 목록이다. 권한만 봐도 앱의 기능을 짐작할 수 있다.
- `INTERNET`이 있으면 서버와 통신할 가능성이 높다 → Frida로 네트워크 함수를 후킹하거나 `adb logcat`/Wireshark로 트래픽을 볼 준비를 한다.
- `READ_EXTERNAL_STORAGE`/`WRITE_EXTERNAL_STORAGE`가 있으면 SD카드나 파일에서 flag를 읽거나 쓸 가능성이 있다.
- `RECEIVE_SMS`, `READ_CONTACTS`처럼 문제 목적과 안 맞아 보이는 권한이 있다면, 그 권한과 관련된 코드(브로드캐스트 리시버 등)를 중점적으로 봐야 한다는 힌트일 수 있다.
- 권한이 거의 없는 미니멀한 앱이라면, 로직이 순수하게 앱 내부(로컬 계산, 문자열 비교, 네이티브 라이브러리)에 있을 가능성이 크다.

### 4대 컴포넌트: activity, service, receiver, provider
안드로이드 앱은 크게 네 가지 컴포넌트로 구성된다.
- **Activity**: 화면 하나. 사용자가 보는 UI 단위다. `<activity>` 태그로 선언되고, 앱을 켰을 때 처음 뜨는 화면은 보통 `MAIN`/`LAUNCHER` intent-filter가 붙은 액티비티다.
- **Service**: 화면 없이 백그라운드에서 도는 컴포넌트. 오래 걸리는 작업이나 지속적인 검사 로직이 여기 숨어있을 수 있다.
- **BroadcastReceiver**: 시스템이나 다른 앱이 보내는 "이벤트"를 받아서 처리하는 컴포넌트. 예를 들어 "부팅 완료"나 "SMS 수신" 같은 이벤트를 받으면 특정 로직이 실행되도록 만들 수 있다.
- **ContentProvider**: 앱 간에 데이터를 공유하는 창구. DB나 파일 접근 로직이 여기 있을 수 있다.

각 컴포넌트는 `android:exported` 속성을 가질 수 있는데, 이 값이 `true`면 **다른 앱(또는 `adb shell am start`로 직접)**이 이 컴포넌트를 실행시킬 수 있다는 뜻이다. `intent-filter`가 하나라도 있는 컴포넌트는 명시적으로 `exported`를 지정하지 않아도 최신 안드로이드(targetSdkVersion 31 이상)에서는 반드시 `exported` 값을 명시해야 하므로, 이 속성이 있다는 것 자체가 "출제자가 이 컴포넌트를 외부에서 건드려보라고 의도했다"는 신호일 확률이 높다. CTF 문제에서 흔히 "숨겨진 액티비티를 `adb`로 직접 실행해서 flag를 얻으라"는 패턴이 나오는데, 이때 필요한 정보가 정확히 이 `exported="true"`인 액티비티의 이름이다.

### intent-filter
`<intent-filter>`는 이 컴포넌트가 어떤 종류의 "요청"에 응답할지를 정의한다. 대표적으로 `<action android:name="android.intent.action.MAIN"/>`과 `<category android:name="android.intent.category.LAUNCHER"/>`가 함께 있으면 "런처 아이콘을 눌렀을 때 실행되는 진입점"이라는 뜻이다. 이 조합이 없는 다른 액티비티들은 앱 실행 중 코드 로직에 의해서만 열리거나, 혹은 `adb`로 직접 지정해서 열어야 하는 "숨은 화면"일 수 있다. `<data android:scheme="ctf"/>` 같은 태그가 있으면 커스텀 URL 스킴(딥링크)으로 이 컴포넌트를 열 수 있다는 뜻이며, 이 경우 브라우저 주소창이나 `adb shell am start -a android.intent.action.VIEW -d "ctf://..."` 형태로 트리거할 수 있다.

### minSdkVersion / targetSdkVersion
`<uses-sdk android:minSdkVersion="21" android:targetSdkVersion="33"/>`는 앱이 지원하는 안드로이드 버전 범위다. `minSdkVersion`이 낮으면 에뮬레이터에서 구버전 API를 켜야 할 수도 있고, `targetSdkVersion`이 최신이면 위에서 언급한 `exported` 명시 규칙이나 다른 보안 정책(예: 클리어텍스트 트래픽 차단)이 적용된다는 뜻이므로, Frida로 후킹하거나 네트워크를 가로챌 때 추가 설정(네트워크 보안 설정 무력화 등)이 필요할 수 있다는 걸 미리 예상할 수 있다.

## 화면/코드에서 보이는 징후
apktool로 디코딩한 `AndroidManifest.xml`은 사람이 읽을 수 있는 XML 텍스트로 나온다.
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.ctf">
    <uses-permission android:name="android.permission.INTERNET"/>
    <application android:label="CTF App" android:icon="@mipmap/ic_launcher">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <activity android:name=".SecretActivity" android:exported="true"/>
        <service android:name=".CheckService" android:exported="false"/>
    </application>
    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34"/>
</manifest>
```
반면 APK 안에 원본 그대로 들어있는 `AndroidManifest.xml`은 AXML(Android Binary XML)이라는 바이너리 포맷이라서, 텍스트 에디터로 열면 알아볼 수 없는 바이트가 잔뜩 보인다. 이걸 보고 "파일이 깨졌다"고 오해하는 초보자가 많다.

## 가장 먼저 할 것
apktool로 APK를 디코딩(`apktool d app.apk`, 자세한 절차는 [REV-0251](./rev-0251-apktool-basics.md) 참고)하면 사람이 읽을 수 있는 형태의 `AndroidManifest.xml`이 나온다. 이 파일을 열어서 위에서 설명한 순서(패키지 이름 → 권한 → exported 컴포넌트 → intent-filter)로 훑어보는 것을 가장 먼저 한다.

## 단계별 절차
1. `apktool d app.apk -o out` 명령으로 APK를 디코딩한다.
2. `out/AndroidManifest.xml`을 텍스트 에디터로 연다.
3. `package="..."` 값을 적어둔다 — 이후 `adb` 명령에서 계속 쓴다.
4. `<uses-permission>` 목록을 위에서 아래로 훑으며 눈에 띄는(비정상적인) 권한이 있는지 확인한다.
5. `<activity>`, `<service>`, `<receiver>`, `<provider>` 각각에서 `android:exported="true"`가 붙은 항목을 모두 표시한다.
6. `<intent-filter>`가 있는 컴포넌트는 어떤 액션/카테고리/데이터로 열리는지 기록한다.
7. `MAIN`/`LAUNCHER` intent-filter가 없는 `exported="true"` 액티비티가 있다면, 이게 "숨겨진 진입점"일 가능성이 매우 크므로 우선순위를 높여서 [REV-0255](./rev-0255-adb-cheatsheet.md)의 `adb shell am start` 명령으로 직접 실행해본다.
8. JADX로 소스를 보며(자세한 절차는 REV-0249 참고) 매니페스트에서 표시해둔 클래스 이름부터 찾아 들어간다.

## 명령어/단축키
```bash
# apktool로 매니페스트를 포함한 전체 디코딩
apktool d app.apk -o out

# 디코딩 없이 aapt로 매니페스트만 빠르게 요약해서 보기
aapt dump badging app.apk

# 권한만 빠르게 grep
grep -o 'android:name="android.permission[^"]*"' out/AndroidManifest.xml

# exported 컴포넌트만 빠르게 grep (근사치, 정확한 파싱은 아님)
grep -B2 'exported="true"' out/AndroidManifest.xml
```

## 출력 해석
- `exported="true"`가 붙었고 `intent-filter`도 없는 컴포넌트: 다른 앱은 명시적으로 클래스 이름을 지정해야 실행할 수 있지만, `adb shell am start -n 패키지/.클래스명`으로는 누구나 바로 열 수 있다. CTF에서 "숨겨진 관리자 화면"류 문제의 전형적인 형태다.
- `permission` 속성이 컴포넌트에 별도로 붙어있다면(`android:permission="com.example.CUSTOM_PERM"`), 이 커스텀 권한을 가진 앱만 접근 가능하다는 뜻이므로 우회 방법을 별도로 고민해야 한다.
- `android:debuggable="true"`가 `<application>` 태그에 있다면 릴리즈 빌드가 아니라 디버그 빌드라는 뜻이며, Frida 부착이나 `adb shell run-as` 없이도 디버거를 붙이기 훨씬 쉬워진다는 중요한 힌트다.

## 흔한 실수
- APK 안의 원본 `AndroidManifest.xml`을 그냥 텍스트 에디터로 열어서 "깨진 파일"이라고 착각하는 것. 반드시 apktool이나 aapt 같은 도구로 디코딩해야 사람이 읽을 수 있다.
- `exported` 속성이 명시되지 않았다고 무조건 `false`로 간주하는 것. `intent-filter`가 있는 컴포넌트는 구버전 안드로이드에서는 기본값이 `true`였으므로, `targetSdkVersion`과 함께 반드시 확인해야 한다.
- 패키지 이름과 클래스 이름을 혼동해서 `adb shell am start -n` 명령의 인자를 잘못 넣는 것. `-n` 뒤에는 `패키지이름/클래스전체경로` 형태(예: `com.example.ctf/.SecretActivity`)가 정확히 들어가야 한다.
- 권한 목록만 보고 코드를 안 읽어도 될 거라 판단하는 것. 매니페스트는 어디까지나 "지도"일 뿐, 실제 검증 로직은 결국 코드(자바/코틀린 또는 네이티브)를 봐야 알 수 있다.

## 막혔을 때 다음 체크
- 매니페스트를 텍스트로 뽑는 방법이 궁금하면 → [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)
- 매니페스트에서 찾은 클래스를 실제 자바/코틀린 코드로 읽고 싶으면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- `exported` 액티비티를 실제로 실행해보고 싶으면 → [REV-0255 adb 기본 명령 치트시트](./rev-0255-adb-cheatsheet.md)
- APK 전체 구조가 궁금하면 → [REV-0248 APK 파일 구조 기초](./rev-0248-apk-structure.md)

## 미니 예제
문제 APK의 매니페스트에서 다음 부분을 발견했다고 하자.
```xml
<activity android:name=".FlagActivity" android:exported="true">
    <intent-filter>
        <action android:name="com.example.ctf.ACTION_SHOW_FLAG"/>
    </intent-filter>
</activity>
```
`MAIN`/`LAUNCHER`가 아니라 커스텀 액션 `com.example.ctf.ACTION_SHOW_FLAG`이 붙어 있으므로, 런처 아이콘을 눌러서는 이 화면에 도달할 수 없다. 대신 다음처럼 `adb`로 직접 이 액션을 발생시켜 액티비티를 열 수 있다.
```bash
adb shell am start -n com.example.ctf/.FlagActivity \
    -a com.example.ctf.ACTION_SHOW_FLAG
```
이 액티비티의 `onCreate()`가 실행되면서 flag를 화면에 표시하거나 로그로 출력하는 코드가 있다면, 코드를 한 줄도 분석하지 않고도 문제를 풀 수 있는 경우도 있다. 물론 실제로는 `onCreate()` 안에서 별도의 검증(예: 특정 extra 값이 있어야 함)이 걸려있는 경우가 많으므로, 이 시점부터는 [REV-0249](./rev-0249-jadx-basics.md)로 `FlagActivity` 클래스를 열어 로직을 확인하는 다음 단계로 넘어간다.

## 관련 글
- REV-0248 — APK 파일 구조 기초
- REV-0249 — JADX로 APK 분석 시작
- REV-0251 — apktool 기본 사용법
- REV-0255 — adb 기본 명령 치트시트

## 출처/검증
- `AndroidManifest.xml` 태그와 속성(`exported`, `intent-filter`, `uses-permission` 등)의 의미는 Android 공식 개발자 문서(developer.android.com, App Manifest Overview)를 기준으로 정리했다.
- `targetSdkVersion 31` 이상에서 `intent-filter`가 있는 컴포넌트의 `exported` 속성 명시 강제 규칙은 Android 공식 문서(Behavior changes: apps targeting Android 12) 기준.
- 위 예제 코드는 CTF 스타일 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
