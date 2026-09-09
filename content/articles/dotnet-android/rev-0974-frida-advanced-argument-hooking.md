---
id: REV-0974
title: "Frida 스크립트로 함수 인자/반환값 후킹하기 심화"
slug: "rev-0974-frida-advanced-argument-hooking"
category: "dotnet-android"
difficulty: "intermediate"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [Frida]
keywords: ["Frida implementation 인자 조작", "Java.choose 인스턴스 탐색", "overload 후킹", "retval.replace", "Frida 배열 객체 인자 읽기"]
aliases: ["frida 인자 변조", "frida 반환값 강제 변경", "frida overload 후킹", "Java.choose 사용법"]
symptom_keywords: ["오버로드된 메서드를 후킹하고 싶다", "인자로 넘어온 객체 필드를 읽고 싶다", "반환값을 강제로 true로 바꾸고 싶다", "이미 생성된 인스턴스를 찾고 싶다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
[REV-0256](./rev-0256-frida-basics.md)에서 다룬 `Java.perform` + `implementation` 기본 후킹을 넘어, **오버로드된 메서드를 정확히 지정해서 후킹하는 법, 인자로 들어온 객체(배열/커스텀 클래스)의 내부 값을 읽는 법, 반환값을 강제로 바꿔치기하는 법, 이미 살아있는 인스턴스를 찾아 그 필드를 직접 들여다보는 법**까지 익히면 단순 관찰을 넘어 실제 검증 로직을 실행 중에 우회/조작하는 실전 CTF 워크플로우를 구성할 수 있다.

## 언제 검색해야 하나
- 같은 이름의 메서드가 인자 타입만 다르게 여러 개 있어서(`verify(String)`, `verify(byte[])`) 어떤 것을 후킹해야 할지 Frida 스크립트에서 지정법을 모를 때
- 후킹한 함수의 인자가 `String`이 아니라 커스텀 클래스 객체나 배열이라 `console.log`로 찍어도 `[object Object]`처럼 의미 없는 값만 나올 때
- 검증 함수의 반환값을 무조건 `true`로 바꿔서 결과를 강제로 통과시키고 싶을 때(학습 목적의 우회 검증)
- 이미 앱 내부에서 생성되어 돌아다니는 특정 클래스의 인스턴스를 찾아 그 안의 필드 값을 실행 중에 확인하고 싶을 때
- `implementation` 후킹 스크립트를 짰는데 `Error: ... has no overload matching` 같은 오류를 만났을 때

## 핵심 개념

### 오버로드 메서드 정확히 지정하기 — overload()
자바/코틀린은 같은 이름의 메서드를 인자 타입/개수만 다르게 여러 개 정의(오버로드)할 수 있다. `Checker.verify.implementation = ...`처럼 그냥 메서드 이름만 쓰면, 오버로드가 하나뿐일 때는 문제없지만 여러 개면 Frida가 "어떤 걸 말하는지 모르겠다"는 오류를 낸다. 이때 `.overload(...)`로 인자 타입을 정확히 지정한다.
```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.Checker");

    // verify(String) 버전만 정확히 후킹
    Checker.verify.overload("java.lang.String").implementation = function (input) {
        console.log("[*] verify(String) called: " + input);
        return this.verify(input);
    };

    // verify(byte[]) 버전은 따로 후킹
    Checker.verify.overload("[B").implementation = function (inputBytes) {
        console.log("[*] verify(byte[]) called, length=" + inputBytes.length);
        return this.verify(inputBytes);
    };
});
```
인자 타입 문자열은 자바의 완전한 클래스 이름(`java.lang.String`, `int`, `boolean`)을 쓰고, 배열은 JNI 타입 디스크립터 표기(`[B` = `byte[]`, `[Ljava.lang.String;` = `String[]`, [REV-0976](./rev-0976-jni-signature-reading.md) 참고)를 그대로 쓴다는 점이 핵심이다.

### 인자가 객체/배열일 때 값을 읽는 법
`console.log(arg)`로 커스텀 객체를 찍으면 `[object Object]`처럼 무의미한 문자열만 나온다. 객체의 실제 필드를 읽으려면 그 필드 이름으로 직접 접근하거나, 배열이라면 인덱스로 순회해야 한다.
```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.Checker");
    Checker.verify.overload("[B").implementation = function (inputBytes) {
        // Java byte[] -> JS 배열로 변환해서 값 확인
        var jsArray = [];
        for (var i = 0; i < inputBytes.length; i++) {
            jsArray.push(inputBytes[i] & 0xff);  // signed byte -> unsigned 표현
        }
        console.log("[*] bytes = " + jsArray.join(","));
        return this.verify(inputBytes);
    };

    // 커스텀 객체 인자의 필드 읽기 예시
    var Request = Java.use("com.example.ctf.Request");
    var Handler = Java.use("com.example.ctf.Handler");
    Handler.handle.overload("com.example.ctf.Request").implementation = function (req) {
        console.log("[*] req.userId = " + req.userId.value);   // 필드 접근은 .value
        console.log("[*] req.getToken() = " + req.getToken()); // 메서드는 그대로 호출
        return this.handle(req);
    };
});
```
`Java.use`로 감싼 객체의 **필드**는 `.value`를 붙여야 실제 값을 읽거나 쓸 수 있고(`req.userId.value`), **메서드**는 일반 자바 호출처럼 그냥 괄호로 호출하면 된다는 차이를 기억해야 한다.

### 반환값 강제로 바꾸기 — return 값 자체를 다르게
[REV-0256](./rev-0256-frida-basics.md)에서는 `this.xxx(...)`의 원본 결과를 그대로 `return`해서 순수 관찰만 했다. 검증 로직을 이해했는지 확인하는 학습 목적으로 결과를 강제로 바꾸고 싶다면, 원본 호출 자체를 생략하거나 결과를 무시하고 원하는 값을 반환하면 된다.
```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.Checker");
    Checker.verify.overload("java.lang.String").implementation = function (input) {
        var real = this.verify(input);
        console.log("[*] real result = " + real + " (input=" + input + ")");
        return true; // 원래 결과와 무관하게 항상 true를 반환하도록 강제
    };
});
```
이 방식은 문제 풀이 자체를 대신 해주는 것이 아니라, "이 함수가 이런 조건에서 이렇게 동작한다"는 것을 확인한 뒤 그 다음 화면/로직으로 넘어가서 마저 분석을 이어가기 위한 검증 수단으로 쓰는 것이 바람직하다.

### 이미 존재하는 인스턴스 찾기 — Java.choose
후킹을 걸기 전에 이미 생성되어 있던 객체(예: 앱이 시작하자마자 만들어 둔 설정 객체)의 현재 필드 값을 보고 싶다면, 새 인스턴스를 만들 필요 없이 힙에서 살아있는 인스턴스를 직접 찾아올 수 있다.
```javascript
Java.perform(function () {
    Java.choose("com.example.ctf.Config", {
        onMatch: function (instance) {
            console.log("[*] found instance, secretKey = " + instance.secretKey.value);
        },
        onComplete: function () {
            console.log("[*] scan complete");
        }
    });
});
```
`onMatch`는 힙에서 발견된 인스턴스마다 한 번씩 호출되고, `onComplete`는 전체 스캔이 끝났을 때 한 번 호출된다. 이 방법은 특정 시점에 값이 이미 세팅되어 있는데 그 초기화 코드가 어디인지 못 찾겠을 때 특히 유용하다.

## 화면/코드에서 보이는 징후
- 후킹 스크립트 실행 시 `Error: verify(): has more than one overload. Please use .overload(...)` 오류가 출력됨.
- `console.log`로 인자를 출력했더니 `[object Object]`나 의미 없는 해시값만 나옴.
- 같은 이름의 메서드가 JADX 트리에 여러 줄(파라미터 목록만 다르게) 나열되어 있음.

## 가장 먼저 할 것
JADX/smali에서 후킹 대상 메서드의 정확한 파라미터 타입 목록부터 확인한다. 오버로드가 있는지, 인자가 원시 타입인지 객체/배열인지를 미리 알아야 `.overload(...)` 문자열과 필드 접근 코드를 정확히 작성할 수 있다.

## 단계별 절차
1. JADX에서 후킹할 메서드의 전체 시그니처(이름, 파라미터 타입, 개수)를 확인한다.
2. 오버로드가 여러 개면 각각을 `.overload("타입1", "타입2", ...)`로 구분해서 후킹 스크립트를 작성한다.
3. 인자가 배열이면 인덱스로 순회, 커스텀 객체면 관심 필드를 `.value`로 접근하는 코드를 추가한다.
4. `frida -U -f 패키지명 -l script.js --no-pause`로 실행해 콘솔 로그로 실제 값을 확인한다.
5. 로직을 이해한 뒤 결과를 강제로 바꿔보고 싶다면 `return` 값을 원하는 값으로 고정해 앱 동작이 실제로 바뀌는지 검증한다.
6. 특정 시점의 이미 초기화된 객체 값이 궁금하면 `Java.choose`로 힙을 스캔해 직접 값을 확인한다.

## 명령어/단축키
```bash
frida -U -f com.example.ctf -l hook.js --no-pause
frida -U -n com.example.ctf -l hook.js   # 이미 실행 중인 프로세스에 스크립트 재주입
```
```javascript
// 오버로드 지정 템플릿
Klass.method.overload("java.lang.String", "int").implementation = function (s, i) { ... };

// 필드 읽기/쓰기 템플릿
instance.fieldName.value;             // 읽기
instance.fieldName.value = newValue;  // 쓰기
```

## 출력 해석
- `.overload(...)`에 넘긴 타입 문자열이 실제 시그니처와 하나라도 다르면(대소문자, 전체 패키지 경로 누락 등) 여전히 "no overload matching" 오류가 나므로, JADX에 표시된 전체 타입 이름을 정확히 그대로 옮겨야 한다.
- 강제로 `return true`를 반환했는데도 앱 동작이 안 바뀐다면, 실제 판정에 쓰이는 함수가 후킹한 함수가 아니라 그 함수를 호출하는 상위 함수일 수 있으므로 호출 스택을 한 단계 더 위로 넓혀야 한다.
- `Java.choose`의 `onMatch`가 한 번도 안 불린다면, 아직 그 클래스의 인스턴스가 생성되지 않은 시점이므로(생성 이후 다시 스캔하거나) 생성 시점 이후로 스크립트 실행 타이밍을 옮겨야 한다.

## 흔한 실수
- 오버로드가 하나뿐인 메서드에도 습관적으로 `.overload(...)`를 안 써서 나중에 새 오버로드가 추가된 앱 버전에서 스크립트가 갑자기 깨지는 것 — 처음부터 정확한 타입을 지정해두면 안전하다.
- 배열 인자를 그냥 `console.log(arr)`로 찍어서 `[object Object]` 로그만 보고 "값이 안 나온다"고 착각하는 것 — 인덱스로 순회하거나 `Array.from`류 변환이 필요하다는 것을 놓치는 경우.
- 객체 필드에 `.value` 없이 `instance.fieldName`만 접근해서 실제 값이 아니라 필드 래퍼 객체 자체를 로그로 찍어버리는 것.
- `return true`로 강제 우회했는데 그 뒤에도 추가 검증이 한 겹 더 있어서 여전히 실패하는데, 첫 번째 우회가 성공했다고 착각하고 다음 단계로 넘어가지 못하는 것 — 강제 우회 후에도 실제 앱 화면/로그로 최종 결과까지 확인해야 한다.
- `Java.choose`를 `Java.perform` 콜백 바깥에서 호출해서 "클래스를 찾을 수 없다"는 오류를 만나는 것.

## 막혔을 때 다음 체크
- Frida 기본 개념(attach/spawn, frida-server 준비)이 아직 헷갈리면 → [REV-0256 Frida로 함수 관찰하는 기본 흐름](./rev-0256-frida-basics.md)
- 네이티브(`.so`) 함수까지 후킹하고 싶다면 → [REV-0975 Frida로 Native 라이브러리 함수 후킹하기](./rev-0975-frida-native-library-hooking.md)
- JNI 타입 디스크립터(`[B`, `Ljava/lang/String;` 등) 표기 규칙이 헷갈리면 → [REV-0976 JNI 네이티브 함수 시그니처(Signature) 읽는 법](./rev-0976-jni-signature-reading.md)
- 후킹 대상 클래스/메서드를 smali 레벨에서 다시 확인하고 싶으면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)

## 미니 예제
`PasswordChecker`에 오버로드된 두 메서드가 있고, 하나는 `String`, 하나는 `byte[]`을 받는다고 하자.
```java
public class PasswordChecker {
    public boolean check(String input) { ... }
    public boolean check(byte[] inputBytes) { ... }
}
```
다음 스크립트로 두 오버로드를 각각 후킹하고, `String` 버전은 결과를 강제로 통과시켜본다.
```javascript
Java.perform(function () {
    var Checker = Java.use("com.example.ctf.PasswordChecker");

    Checker.check.overload("java.lang.String").implementation = function (input) {
        var real = this.check(input);
        console.log("[*] check(String) input=" + input + " real=" + real);
        return true; // 강제 통과 (학습/검증 목적)
    };

    Checker.check.overload("[B").implementation = function (bytes) {
        var arr = [];
        for (var i = 0; i < bytes.length; i++) arr.push(bytes[i] & 0xff);
        console.log("[*] check(byte[]) bytes=" + arr.join(","));
        return this.check(bytes);
    };
});
```
```bash
frida -U -f com.example.ctf -l hook.js --no-pause
```
앱에서 비밀번호를 입력하고 확인 버튼을 누르면, 콘솔에 실제 입력값과 원본 반환값(`real`)이 먼저 찍히고, 이후 강제로 `true`가 반환되어 앱은 항상 "성공" 화면으로 넘어간다. 이 결과로 `check(String)`이 실제로 어떤 값에 대해 `false`를 반환했는지 확인한 뒤, 그 로직 자체를 마저 정적으로 분석해 진짜 정답을 찾는 다음 단계로 넘어갈 수 있다.

## 관련 글
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0975 — Frida로 Native 라이브러리 함수 후킹하기
- REV-0976 — JNI 네이티브 함수 시그니처(Signature) 읽는 법
- REV-0252 — smali 기초 문법

## 출처/검증
- `Java.use`, `.overload(...)`, `Java.choose`, 필드 접근(`.value`) API는 Frida 공식 문서(frida.re, "JavaScript API" 및 "Frida Java Bridge")를 기준으로 정리했다.
- JNI 배열/객체 타입 디스크립터 표기(`[B`, `[Ljava.lang.String;` 등)는 오라클 공식 JNI 명세를 기준으로 확인했다.
- 위 스크립트/예제는 CTF 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다 (2026-09-09 확인).
