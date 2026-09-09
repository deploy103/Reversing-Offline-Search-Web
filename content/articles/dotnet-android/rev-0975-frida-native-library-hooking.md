---
id: REV-0975
title: "Frida로 Native 라이브러리 함수 후킹하기"
slug: "rev-0975-frida-native-library-hooking"
category: "dotnet-android"
difficulty: "intermediate"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [Frida]
keywords: ["Module.findExportByName", "Interceptor.attach onEnter onLeave", "NativeFunction", "Module.enumerateExports", "retval.replace 네이티브 함수 우회"]
aliases: ["frida so 함수 후킹", "frida native 오프셋 후킹", "frida strcmp 후킹", "frida NativeFunction 사용법"]
symptom_keywords: ["Module.findBaseAddress가 null을 반환한다", "so 파일 안 함수를 오프셋으로 후킹하고 싶다", "네이티브 함수 반환값을 강제로 바꾸고 싶다", "Module.enumerateExports가 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
네이티브(`.so`) 라이브러리 함수는 심볼 이름으로 바로 찾아 후킹(`Module.findExportByName` + `Interceptor.attach`)하거나, 심볼이 없으면 Ghidra 등에서 확인한 파일 오프셋에 로드 베이스 주소를 더해 직접 후킹해야 하며, `onEnter`/`onLeave` 콜백과 `NativeFunction`을 조합하면 자바 코드뿐 아니라 C/C++로 작성된 검증 로직도 실행 중에 관찰·조작할 수 있다.

## 언제 검색해야 하나
- [REV-0254](./rev-0254-native-library-so.md)/[REV-0257](./rev-0257-jni-tracing.md)에서 `.so` 안의 `native` 함수를 정적으로 찾았고, 이제 그 함수를 실행 중에 직접 후킹해서 인자/반환값을 보고 싶을 때
- 심볼이 strip되어 이름으로 찾을 수 없고 Ghidra 등에서 확인한 파일 오프셋만 갖고 있을 때
- 후킹 대상이 앱 자체 함수가 아니라 `libc.so`의 `strcmp`, `memcmp` 같은 표준 라이브러리 함수라서 안티 디버깅/검증 우회에 활용하고 싶을 때
- 네이티브 함수 자체를 후킹하지 않고, 그 함수를 스크립트 쪽에서 직접 호출해보고 싶을 때(`NativeFunction`)
- `Module.findBaseAddress("libfoo.so")`가 `null`을 반환해서 원인을 모를 때

## 핵심 개념

### 심볼 이름으로 후킹 — Module.findExportByName + Interceptor.attach
[REV-0257](./rev-0257-jni-tracing.md)에서 JNI 이름 규칙(`Java_com_example_...`)이나 `RegisterNatives`로 등록된 함수 이름을 알아냈다면, 심볼이 export되어 있는 한 이름만으로 바로 후킹할 수 있다.
```javascript
var targetPtr = Module.findExportByName("libchecker.so", "Java_com_example_ctf_NativeChecker_verifyFlag");
if (targetPtr === null) {
    console.log("[!] symbol not found, use offset-based hooking instead");
} else {
    Interceptor.attach(targetPtr, {
        onEnter: function (args) {
            // JNI 함수이므로 args[0]=JNIEnv*, args[1]=jobject, args[2]부터 실제 자바 인자
            this.inputPtr = args[2];
            var jstr = Java.vm.getEnv().getStringUtfChars(this.inputPtr, null).readCString();
            console.log("[*] verifyFlag input = " + jstr);
        },
        onLeave: function (retval) {
            console.log("[*] verifyFlag returned = " + retval.toInt32());
        }
    });
}
```

### 심볼이 없을 때 — 오프셋 기반 후킹
strip된 라이브러리이거나 `RegisterNatives`로 동적 등록되어 이름이 없다면([REV-0257](./rev-0257-jni-tracing.md) 참고), Ghidra/IDA로 파일 오프셋을 미리 확인해두고 런타임 로드 베이스 주소에 그 오프셋을 더해서 후킹한다.
```javascript
var libBase = Module.findBaseAddress("libchecker.so");
if (libBase === null) {
    console.log("[!] library not loaded yet — hook after it's loaded, or check the exact name");
} else {
    var targetAddr = libBase.add(0x4520); // Ghidra에서 확인한 파일 오프셋
    Interceptor.attach(targetAddr, {
        onEnter: function (args) {
            console.log("[*] native func called, arg0=" + args[0]);
        },
        onLeave: function (retval) {
            console.log("[*] returned=" + retval);
        }
    });
}
```
여기서 오프셋은 **파일 오프셋(정적 분석 도구가 보여주는 값)과 ASLR이 적용된 런타임 가상 주소가 다르다**는 점을 반드시 기억해야 한다. Frida의 `Module.findBaseAddress`가 돌려주는 값은 이미 그 프로세스에서 실제로 로드된 베이스 주소이므로, 여기에 파일 상의 오프셋(가상 주소 기준, 세그먼트 정렬을 고려한 오프셋)을 더하면 실행 중 실제 주소가 나온다. ELF 세그먼트가 여러 개이고 정렬이 복잡한 경우 Ghidra의 "Image Base"를 0으로 두고 계산한 상대 오프셋을 쓰는 것이 가장 안전하다.

### 라이브러리가 아직 로드되지 않았을 때
`Module.findBaseAddress`가 `null`을 반환하는 흔한 이유는, 스크립트가 attach된 시점에 해당 `.so`가 아직 `dlopen`되지 않았기 때문이다. 이 경우 라이브러리 로드를 기다렸다가 후킹을 걸어야 한다.
```javascript
var interval = setInterval(function () {
    var base = Module.findBaseAddress("libchecker.so");
    if (base !== null) {
        clearInterval(interval);
        console.log("[*] libchecker.so loaded at " + base);
        // 여기서 Interceptor.attach 진행
    }
}, 100);
```
또는 spawn 방식([REV-0256](./rev-0256-frida-basics.md) 참고)으로 앱을 처음부터 멈춰서 실행하고, `Process.getModuleByName` 계열 API나 `Module.enumerateExports`로 라이브러리 export 목록을 미리 훑어 원하는 심볼이 있는지 확인하는 것도 좋은 사전 점검이다.

### libc 함수 후킹 — 안티 디버깅/체크섬 우회
검증 로직이 직접 구현되어 있지 않고 `strcmp`, `memcmp`, `strstr` 같은 libc 표준 함수를 그대로 호출해서 비교하는 경우, 그 표준 함수 자체를 후킹해서 인자를 관찰하거나 결과를 조작할 수 있다.
```javascript
Interceptor.attach(Module.findExportByName("libc.so", "strcmp"), {
    onEnter: function (args) {
        this.s1 = args[0].readCString();
        this.s2 = args[1].readCString();
    },
    onLeave: function (retval) {
        console.log("[*] strcmp(\"" + this.s1 + "\", \"" + this.s2 + "\") = " + retval.toInt32());
    }
});
```
이 방식은 어떤 라이브러리가 됐든 `strcmp`를 호출하는 모든 지점을 한 번에 관찰할 수 있어서, 검증에 쓰이는 정확한 비교 대상 문자열이 어디 있는지 모를 때 탐색용으로 매우 강력하다. 다만 `strcmp`가 앱 전체에서 매우 자주 호출되므로(문자열 비교는 프레임워크 내부에서도 흔함), 관심 있는 문자열 패턴만 걸러서 로그를 찍는 조건문을 추가하는 것이 실용적이다.

### 반환값 조작 — retval.replace
`onLeave`에서 `retval`은 읽기 전용 로그 대상만이 아니라, `.replace(...)`로 실제 반환값 자체를 바꿔치기할 수도 있다.
```javascript
Interceptor.attach(targetAddr, {
    onLeave: function (retval) {
        console.log("[*] original return = " + retval.toInt32());
        retval.replace(1); // 항상 성공(1)을 반환하도록 강제
    }
});
```
이는 [REV-0974](./rev-0974-frida-advanced-argument-hooking.md)에서 다룬 자바 레벨의 `return true` 강제와 같은 발상을, 네이티브 함수 레벨에서 적용하는 것이다.

### NativeFunction — 함수를 직접 호출해보기
후킹(가로채기)이 아니라, 스크립트에서 능동적으로 네이티브 함수를 직접 호출해서 결과를 실험해보고 싶을 때는 `NativeFunction`을 쓴다.
```javascript
var libBase = Module.findBaseAddress("libchecker.so");
var decryptFn = new NativeFunction(libBase.add(0x3a10), "pointer", ["pointer", "int"]);
var result = decryptFn(Memory.allocUtf8String("test"), 4);
console.log("[*] direct call result = " + result.readCString());
```
`NativeFunction(주소, "반환타입", ["인자타입", ...])` 형태로 함수 시그니처를 지정하면, 실제 앱 흐름과 무관하게 원하는 인자로 그 함수를 몇 번이든 직접 호출해볼 수 있다. 암호화/복호화 함수처럼 "입력을 바꿔가며 결과를 관찰"하고 싶은 순수 함수에 특히 유용하다.

## 화면/코드에서 보이는 징후
- `Module.findExportByName(...)`이 `null`을 반환하며 후킹이 걸리지 않음(심볼 없음 또는 라이브러리 미로드).
- `Interceptor.attach`에 성공했는데 콘솔에 아무 로그도 안 찍힘(주소 계산이 틀렸거나, 그 코드 경로가 실제로 실행되지 않음).
- `retval.replace(...)` 이후 앱 동작이 실제로 바뀌는지 여부로 그 함수가 진짜 판정 지점인지 확인 가능.

## 가장 먼저 할 것
`frida-trace -U -j "libchecker.so!*" com.example.ctf`로 라이브러리 안의 모든 export 함수 호출을 자동으로 트레이싱해보고, 어떤 함수가 실제로 몇 번 호출되는지부터 감을 잡는다. 이후 관심 함수만 골라 직접 `Interceptor.attach` 스크립트로 전환한다.

## 단계별 절차
1. `frida-trace -U -j "libchecker.so!*" com.example.ctf`로 라이브러리 전체 함수 호출을 자동 트레이싱해 대략적인 호출 빈도를 파악한다.
2. 심볼이 있는 함수는 `Module.findExportByName`으로 바로 후킹 스크립트를 작성한다.
3. 심볼이 없으면 Ghidra 등에서 확인한 파일 오프셋을 `Module.findBaseAddress(...).add(오프셋)`으로 변환해 후킹한다.
4. 라이브러리가 늦게 로드되는 경우 `setInterval`로 로드 완료를 기다린 뒤 후킹을 건다.
5. `onEnter`에서 인자를, `onLeave`에서 반환값을 로그로 확인한다.
6. 로직 이해 후 검증이 필요하면 `retval.replace(...)`로 반환값을 강제 조작해 앱 동작 변화를 관찰한다.
7. 순수 계산 함수(암복호화 등)라면 `NativeFunction`으로 직접 호출해 다양한 입력에 대한 출력을 실험한다.

## 명령어/단축키
```bash
frida-trace -U -j "libchecker.so!*" com.example.ctf   # 라이브러리 전체 export 자동 트레이싱
frida -U -f com.example.ctf -l native_hook.js --no-pause
```
```javascript
// 심볼 유무와 무관하게 항상 동작하는 안전한 후킹 헬퍼 패턴
function hookByOffset(libName, offset, callbacks) {
    var base = Module.findBaseAddress(libName);
    if (base === null) {
        console.log("[!] " + libName + " not loaded");
        return;
    }
    Interceptor.attach(base.add(offset), callbacks);
}
```

## 출력 해석
- `onEnter`의 `args[N]`은 항상 `NativePointer` 타입이므로, 문자열이면 `.readCString()`/`.readUtf8String()`, 정수면 `.toInt32()`로 변환해야 사람이 읽을 수 있는 값이 된다.
- `retval`도 마찬가지로 `NativePointer`이며, 정수 반환값은 `.toInt32()`로, 반환값 자체를 바꾸려면 `.replace(새값)`을 쓴다.
- `frida-trace`가 만들어주는 `__handlers__/` 폴더 아래 자동 생성된 JS 파일들을 열어보면, 각 함수별로 `onEnter`/`onLeave` 템플릿이 이미 만들어져 있어 이를 그대로 편집해서 커스텀 로직을 채우면 빠르다.

## 흔한 실수
- 정적 분석 도구(Ghidra)가 보여주는 오프셋을 ASLR 적용 여부를 고려하지 않고 그대로 절대 주소처럼 사용하는 것 — 반드시 `Module.findBaseAddress(...)`로 얻은 런타임 베이스에 상대 오프셋을 더해야 한다.
- 라이브러리가 아직 로드되기 전에 후킹을 시도해서 `null` 오류만 보고 "함수가 없다"고 오판하는 것 — spawn 시점 직후에는 아직 `dlopen`이 안 됐을 수 있으므로 로드 대기 로직이 필요하다.
- `libc.so`의 `strcmp` 등을 후킹하면서 로그 필터링을 안 해서, 앱 전체에서 쏟아지는 무관한 문자열 비교 로그에 파묻혀 정작 찾는 호출을 놓치는 것.
- `retval.replace(...)`로 반환값만 바꾸고, 그 반환값을 사용하는 호출자 쪽 로직이 또 다른 검증을 하고 있다는 것을 놓쳐서 우회가 실제로는 통하지 않는 것.
- `NativeFunction`의 인자/반환 타입 문자열을 실제 C 시그니처와 다르게 지정해서(`int`를 `pointer`로 잘못 쓰는 등) 크래시나 잘못된 값을 얻는 것.

## 막혔을 때 다음 체크
- `.so` 파일 자체를 처음 다루는 기초가 궁금하면 → [REV-0254 Native Library lib*.so가 있을 때](./rev-0254-native-library-so.md)
- JNI 심볼 이름 규칙과 RegisterNatives 동적 등록 구분이 헷갈리면 → [REV-0257 JNI 호출 Java에서 Native까지 추적](./rev-0257-jni-tracing.md)
- JNI 함수 파라미터 타입 디스크립터(`Ljava/lang/String;` 등)를 읽는 법이 궁금하면 → [REV-0976 JNI 네이티브 함수 시그니처(Signature) 읽는 법](./rev-0976-jni-signature-reading.md)
- 자바 레벨 인자/반환값 후킹(오버로드, 객체 필드 읽기)이 궁금하면 → [REV-0974 Frida 스크립트로 함수 인자/반환값 후킹하기 심화](./rev-0974-frida-advanced-argument-hooking.md)
- Frida 기본 개념(attach/spawn, frida-server 준비)이 헷갈리면 → [REV-0256 Frida로 함수 관찰하는 기본 흐름](./rev-0256-frida-basics.md)

## 미니 예제
Ghidra로 `libchecker.so`를 열어 strip된 검증 함수를 찾았고, Image Base를 0으로 뒀을 때 함수 주소가 `0x00004520`으로 확인됐다고 하자. 이 함수는 `int verify(const char *input)` 형태로 추정된다.
```javascript
Java.perform(function () {
    var libBase = Module.findBaseAddress("libchecker.so");
    if (libBase === null) {
        console.log("[!] libchecker.so not loaded yet");
        return;
    }
    var targetAddr = libBase.add(0x4520);
    Interceptor.attach(targetAddr, {
        onEnter: function (args) {
            this.input = args[0].readCString();
            console.log("[*] verify(\"" + this.input + "\") called");
        },
        onLeave: function (retval) {
            console.log("[*] original return = " + retval.toInt32());
            retval.replace(1); // 강제로 성공(1)을 반환
        }
    });
});
```
```bash
frida -U -f com.example.ctf -l native_hook.js --no-pause
```
앱에서 아무 값이나 입력하고 확인 버튼을 누르면, 콘솔에 실제 입력값과 원본 반환값(대개 실패를 뜻하는 0)이 먼저 찍히고, 이후 강제로 1이 반환되어 앱은 검증을 통과한 것처럼 동작한다. 원본 반환값이 항상 0이라는 것을 확인했다면, 이제 `0x4520` 함수 내부를 Ghidra로 마저 분석해 어떤 조건에서 실제로 1을 반환하는지(즉 진짜 정답 조건) 정적으로 파고드는 다음 단계로 넘어갈 수 있다.

## 관련 글
- REV-0254 — Native Library lib*.so가 있을 때
- REV-0257 — JNI 호출 Java에서 Native까지 추적
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0974 — Frida 스크립트로 함수 인자/반환값 후킹하기 심화
- REV-0976 — JNI 네이티브 함수 시그니처(Signature) 읽는 법

## 출처/검증
- `Module.findExportByName`, `Module.findBaseAddress`, `Module.enumerateExports`, `Interceptor.attach`, `NativeFunction`, `retval.replace` API는 Frida 공식 문서(frida.re, "JavaScript API")를 기준으로 정리했다.
- `frida-trace`의 `-j` 옵션과 자동 생성 핸들러 동작은 Frida 공식 문서("frida-trace") 기준으로 확인했다.
- ELF 로드 베이스 주소와 파일 오프셋의 관계(ASLR 적용 시 런타임 주소 = 로드 베이스 + 상대 오프셋)는 System V ABI 및 ELF 명세를 기준으로 설명했다.
- 위 스크립트/예제는 CTF 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다 (2026-09-09 확인).
