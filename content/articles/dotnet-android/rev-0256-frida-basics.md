---
id: REV-0256
title: "Frida로 함수 관찰하는 기본 흐름"
slug: "rev-0256-frida-basics"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["Frida", "adb"]
keywords: ["Frida", "Java.perform", "Interceptor.attach", "frida-server", "동적 계측", "함수 후킹"]
aliases: ["프리다 사용법", "frida 후킹 기초", "Java.perform 예제", "Interceptor.attach 예제"]
symptom_keywords: ["frida-server가 안 붙음", "Java.perform이 뭔지 모름", "함수 인자를 실행 중에 보고 싶음", "frida attach 오류"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Frida는 실행 중인 프로세스에 코드를 주입해서 특정 함수가 호출될 때 인자와 반환값을 실시간으로 관찰하거나 바꿀 수 있게 해주는 동적 계측(dynamic instrumentation) 도구이며, 정적 분석(smali, JADX, Ghidra)으로 로직을 다 이해하지 못했을 때 "일단 실행시켜서 실제 값이 뭔지 눈으로 확인하는" 가장 강력한 CTF 우회 수단이다.

## 언제 검색해야 하나
- smali/자바 코드를 읽었는데 특정 함수가 정확히 어떤 값을 주고받는지 정적으로 확신이 안 설 때
- 암호화/난독화된 값이 실행 중 메모리에서는 평문으로 잠깐 나타날 것 같은데 그 순간을 잡고 싶을 때
- 네이티브(`.so`) 함수의 인자를 정적 분석 없이 빠르게 확인하고 싶을 때
- "Frida 스크립트를 어떻게 시작해야 하냐"는 기본적인 질문이 있을 때
- `frida.get_usb_device()` 나 `frida -U` 명령이 실패해서 원인을 모를 때

## 핵심 개념
Frida는 크게 두 부분으로 구성된다. 기기(또는 에뮬레이터) 안에서 실행되며 대상 프로세스에 코드를 주입하는 역할을 하는 **frida-server**(루팅된 기기/에뮬레이터에 push해서 실행)와, PC에서 스크립트를 작성하고 명령을 내리는 **frida 클라이언트**(`frida`, `frida-trace`, `frida-ps` 같은 CLI 도구 또는 Python `frida` 모듈)다. 두 쪽의 버전이 반드시 일치해야 정상 동작한다는 점이 초보자가 가장 많이 걸리는 함정이다.

동작 원리를 간단히 설명하면, Frida는 대상 프로세스 안에 자체 JavaScript 엔진(QuickJS 또는 V8)을 주입한 뒤, 분석가가 작성한 JavaScript 코드를 그 안에서 실행시킨다. 이 스크립트 안에서 "이 함수가 호출되는 순간"을 가로채(hook) 인자를 출력하거나, 원래 함수의 실행 자체를 건너뛰고 원하는 값을 대신 반환시킬 수도 있다.

### CTF에서 Frida를 쓰는 목적 — 관찰이지 파괴가 아니다
Frida는 강력한 만큼 오남용하면 다른 사람의 실제 서비스나 앱을 무단으로 조작하는 데도 쓰일 수 있는 도구다. 이 문서(그리고 이 지식베이스 전체)에서 다루는 용도는 **CTF/wargame처럼 스스로 분석 권한이 있는 앱을 대상으로, 로직을 이해하기 위해 실행 중 값을 관찰하거나 학습 목적으로 검증 로직을 우회해보는 것**에 한정한다. 실제 타인의 서비스, 상용 앱, DRM이 걸린 소프트웨어에 대한 무단 변조나 크래킹 목적의 사용은 이 문서의 범위가 아니며 법적 문제가 될 수 있다.

### frida-server 준비
```bash
# 1. PC의 frida 클라이언트 버전 확인
frida --version

# 2. 같은 버전의 frida-server를 기기 아키텍처에 맞게 다운로드 후 push
adb push frida-server-16.x.x-android-arm64 /data/local/tmp/frida-server
adb shell chmod 755 /data/local/tmp/frida-server

# 3. 루트 권한으로 frida-server 실행 (에뮬레이터/루팅 기기)
adb shell "su -c /data/local/tmp/frida-server &"

# 4. 연결 확인
frida-ps -U
```
`frida-ps -U`(USB로 연결된 기기의 프로세스 목록)가 정상 출력되면 frida-server와 클라이언트가 잘 연결된 것이다.

### 부착 방식: attach vs spawn
Frida로 대상 프로세스에 연결하는 방법은 두 가지다.
- **attach**: 이미 실행 중인 앱 프로세스에 나중에 코드를 주입한다. `frida -U -n <프로세스이름>` 또는 Python에서 `frida.get_usb_device().attach("프로세스이름")`. 앱이 이미 켜져 있어야 하고, 앱 시작 시점(예: `Application.onCreate()`)의 로직은 놓칠 수 있다.
- **spawn**: 앱을 아예 처음부터(멈춘 상태로) 실행시킨 뒤, 첫 코드가 돌기 전에 스크립트를 미리 주입하고 나서 실행을 재개(resume)한다. `frida -U -f com.example.ctf -l script.js --no-pause`. 앱 시작 로직까지 전부 관찰하고 싶을 때 spawn을 쓴다.

CTF에서는 앱이 시작하자마자 검증 준비 로직(키 생성, 초기화)을 실행하는 경우가 많아 spawn 방식을 더 자주 쓴다.

### Java.perform과 기본 후킹 스크립트
안드로이드 앱(자바/코틀린 코드)을 후킹하려면 자바 VM이 초기화된 스레드 컨텍스트 안에서 코드를 실행해야 하는데, 이를 위한 진입점이 `Java.perform(function() { ... })`이다. 이 안에서 `Java.use("클래스 전체경로")`로 자바 클래스를 가져오고, 그 클래스의 메서드를 직접 재정의(override)하는 식으로 후킹한다.

```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.NativeChecker");

    Checker.verify.implementation = function (input) {
        console.log("[*] verify() called with input = " + input);
        var result = this.verify(input); // 원본 함수 그대로 실행
        console.log("[*] verify() returned = " + result);
        return result; // 원래 결과를 그대로 반환 (관찰만 하는 경우)
    };
});
```
이 스크립트는 `verify` 메서드가 호출될 때마다 인자(`input`)와 원본 함수의 반환값을 콘솔에 출력한다. `this.verify(input)`으로 원본 로직을 그대로 실행시키기 때문에 앱 동작 자체는 바뀌지 않고, 순수하게 "관찰"만 하는 형태다.

만약 검증 결과를 강제로 통과시키고 싶다면(로직을 이해했는지 확인하는 학습 목적) 마지막 줄을 `return true;`로 바꾸면 되지만, 이는 문제 풀이 자체를 우회하는 것이므로 어디까지나 "이 함수가 이런 식으로 동작한다"는 것을 확인하는 학습 단계에서만 활용하는 게 바람직하다.

### Interceptor.attach — 네이티브 함수 후킹
`Java.use`는 자바/코틀린 메서드용이고, `.so` 안의 네이티브 함수를 관찰하려면 `Interceptor.attach`를 쓴다.
```javascript
var libBase = Module.findBaseAddress("libchecker.so");
var targetAddr = libBase.add(0x1234); // 오프셋은 Ghidra 등으로 미리 확인

Interceptor.attach(targetAddr, {
    onEnter: function (args) {
        console.log("[*] native verify called");
        console.log("    arg0 (this/env) = " + args[0]);
        console.log("    arg2 (jstring input) = " + Java.vm.getEnv().getStringUtfChars(args[2], null).readCString());
    },
    onLeave: function (retval) {
        console.log("[*] return value = " + retval);
    }
});
```
`onEnter`는 함수 진입 시, `onLeave`는 함수 종료(반환) 시 호출되는 콜백이다. JNI 함수는 첫 번째 인자가 `JNIEnv*`, 두 번째가 `jobject`(또는 `jclass`), 그 뒤부터가 자바에서 넘긴 실제 인자이므로 인자 인덱스를 셀 때 이 규칙을 알아둬야 한다(자세한 JNI 인자 규칙은 [REV-0257](./rev-0257-jni-tracing.md) 참고).

## 화면/코드에서 보이는 징후
- 터미널에 `Failed to spawn: unable to connect to remote frida-server`가 뜨면 frida-server가 기기에서 실행되고 있지 않은 것이다.
- `frida.ProcessNotFoundError` 계열 에러는 attach 대상 프로세스 이름/PID가 틀렸거나 앱이 아직 실행 중이 아닌 것이다.
- 후킹이 성공하면 `console.log`로 출력한 문자열이 `frida` 클라이언트 터미널에 실시간으로 흘러나온다.

## 가장 먼저 할 것
`frida-ps -U`를 실행해서 frida-server와 클라이언트 연결이 정상인지부터 확인한다. 여기서 프로세스 목록이 안 뜨면, 이후 어떤 후킹 스크립트를 짜도 소용없으므로 반드시 먼저 해결한다.

## 단계별 절차
1. PC의 `frida` 버전을 확인하고, 같은 버전의 `frida-server`를 기기 아키텍처(주로 `android-arm64`)에 맞게 받아 `/data/local/tmp/`에 push한다.
2. `adb shell`로 들어가 `chmod 755`, `su -c ./frida-server &`로 frida-server를 백그라운드 실행한다.
3. PC에서 `frida-ps -U`로 연결 확인.
4. 후킹할 클래스/메서드(자바) 또는 함수 오프셋(네이티브)을 JADX/Ghidra로 미리 조사해둔다.
5. `Java.perform`(자바) 또는 `Interceptor.attach`(네이티브) 스크립트를 작성한다.
6. `frida -U -f com.example.ctf -l script.js --no-pause`로 spawn하며 스크립트를 주입한다.
7. 콘솔에 출력되는 인자/반환값을 관찰하며 로직을 검증하거나 힌트를 얻는다.

## 명령어/단축키
```bash
frida --version                          # 클라이언트 버전 확인
frida-ps -U                              # USB 기기의 프로세스 목록
frida -U -n com.example.ctf              # 이미 실행 중인 앱에 attach + REPL
frida -U -f com.example.ctf -l s.js --no-pause   # spawn하며 스크립트 주입 후 즉시 재개
frida-trace -U -j "libchecker.so!verify" com.example.ctf  # 자동 트레이싱 도구
```

## 출력 해석
- `onEnter`에서 찍은 인자 값이 사람이 읽을 수 있는 문자열이면 그대로 힌트로 쓸 수 있다.
- `onLeave`의 `retval`이 boolean을 나타내는 0/1이라면, `retval.toInt32()`로 변환해서 읽으면 더 명확하다.
- 후킹한 함수가 여러 번 호출된다면(예: 반복문 안에서), 매 호출마다 로그가 여러 줄 찍히므로 어느 호출이 최종 검증인지 흐름을 함께 확인해야 한다.

## 흔한 실수
- PC의 `frida` 클라이언트와 기기의 `frida-server` 버전이 달라서 연결 자체가 실패하는 것. 반드시 `frida --version` 결과와 동일한 버전의 frida-server를 받아야 한다.
- 루팅되지 않은 실기기에서 frida-server를 실행하려다 권한 오류가 나는 것. frida-server는 보통 root 권한이 필요하므로, 루팅 기기나 에뮬레이터(userdebug 빌드)에서 진행하는 게 훨씬 수월하다.
- `Java.perform` 밖에서 `Java.use`를 호출해서 "클래스를 못 찾는다"는 오류를 만나는 것. 자바 관련 코드는 항상 `Java.perform(function() {...})` 콜백 안에서 실행해야 한다.
- attach 방식으로 붙였는데 이미 앱이 시작 로직(초기화, 키 생성)을 다 마친 뒤라서 원하는 순간을 놓치는 것. 이땐 spawn 방식(`-f` 옵션)으로 전환해야 한다.
- 네이티브 함수 후킹 시 JNI 인자 순서(`JNIEnv*`, `jobject/jclass`가 앞에 온다는 것)를 안 지켜서 엉뚱한 인자를 읽는 것.

## 막혔을 때 다음 체크
- 후킹하려는 함수가 네이티브(`.so`) 안에 있고 정확한 오프셋을 못 찾겠다면 → [REV-0254 Native Library lib*.so가 있을 때](./rev-0254-native-library-so.md), [REV-0257 JNI 호출 Java에서 Native까지 추적](./rev-0257-jni-tracing.md)
- 후킹할 자바 클래스/메서드 시그니처를 다시 확인하고 싶다면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- `adb`로 frida-server를 push/실행하는 세부 명령이 헷갈리면 → [REV-0255 adb 기본 명령 치트시트](./rev-0255-adb-cheatsheet.md)

## 미니 예제
[REV-0254](./rev-0254-native-library-so.md)에서 다룬 `NativeChecker.verify(String input)` 예제를 Frida로 관찰해본다.
```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.NativeChecker");
    Checker.verify.implementation = function (input) {
        console.log("[*] input = " + input);
        var ret = this.verify(input);
        console.log("[*] result = " + ret);
        return ret;
    };
});
```
```bash
frida -U -f com.example.ctf -l hook.js --no-pause
```
앱을 켜고 화면에 아무 문자열이나 입력해서 "확인" 버튼을 누르면, 터미널에 다음과 같이 출력된다.
```
[*] input = test1234
[*] result = false
```
이 상태에서 여러 입력을 시도해보며 `result`가 `true`로 바뀌는 조건을 실험적으로 좁혀갈 수도 있고, 애초에 이 정보(어떤 함수가 어떤 타입의 인자를 받는지)를 확인한 뒤 Ghidra로 넘어가 네이티브 로직을 더 정확히 분석하는 다음 단계로 이어갈 수도 있다.

## 관련 글
- REV-0254 — Native Library lib*.so가 있을 때
- REV-0257 — JNI 호출 Java에서 Native까지 추적
- REV-0255 — adb 기본 명령 치트시트
- REV-0249 — JADX로 APK 분석 시작

## 출처/검증
- Frida의 `Java.perform`, `Java.use`, `Interceptor.attach` API는 Frida 공식 문서(frida.re, "JavaScript API")를 기준으로 정리했다.
- frida-server와 클라이언트의 버전 일치 요구사항은 Frida 공식 문서("Getting started with Frida on Android")를 기준으로 설명했다.
- 위 스크립트/출력 예제는 CTF 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
