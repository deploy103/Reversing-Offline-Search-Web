---
id: REV-0981
title: "smali 코드를 수정 후 재빌드가 실패할 때"
slug: "rev-0981-smali-rebuild-fails"
category: "dotnet-android"
difficulty: "basic"
platform: [linux]
architecture: [ARM, ARM64]
format: [APK]
tools: [smali, apktool]
keywords: ["apktool b 실패", "VerifyError", "locals 레지스터 부족", "smali 재조립 오류", "smali syntax error"]
aliases: ["smali build 실패", "apktool build 오류", "smali 재빌드 안됨", "smali 수정 후 크래시"]
symptom_keywords: ["apktool b 명령이 실패함", "smali syntax error가 뜸", "재조립한 APK 설치 후 크래시", "VerifyError로 앱이 죽음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
smali를 수정한 뒤 `apktool b`가 실패하거나, 빌드는 성공했는데 앱 실행 시 크래시가 난다면 원인은 거의 항상 `.locals` 레지스터 개수 불일치, 문법 오류(오타, 세미콜론 누락), 또는 레지스터 타입 불일치(객체 레지스터에 정수 값을 넣는 등) 세 가지 중 하나다.

## 언제 검색해야 하나
- `.smali` 파일을 손으로 고친 뒤 `apktool b`를 실행했는데 오류 메시지와 함께 빌드가 중단될 때
- 빌드는 성공했는데 앱을 설치하고 실행하면 곧바로 크래시하거나 `VerifyError`가 날 때
- 새 레지스터를 코드에 추가했는데 왜 실패하는지 이유를 모를 때
- smali 문법에서 어디를 고쳐야 할지 감이 안 잡힐 때

## 핵심 개념
smali는 사람이 손으로 편집할 수 있는 텍스트지만, 결국 다시 바이트코드로 조립되어 Dalvik/ART 검증기(verifier)를 통과해야 실제로 실행된다. 검증기는 각 메서드가 선언한 것보다 많은 레지스터를 쓰지 않는지, 각 레지스터에 담긴 값의 타입이 그 시점에 기대되는 타입과 일치하는지 등을 엄격하게 검사한다.

가장 흔한 실패 원인은 `.locals N` 선언이다. 이 숫자는 그 메서드가 사용하는 **지역 레지스터**(`v0`~`vN-1`)의 개수를 뜻하는데, 코드를 수정하면서 새 레지스터(`v2` 등)를 추가로 썼다면 `.locals` 값도 그만큼 늘려야 한다. 이걸 빼먹으면 `apktool b`(내부적으로 smali 어셈블러 호출) 단계에서 "레지스터 범위를 벗어났다"는 오류로 바로 걸러지거나, 운 좋게 빌드는 되더라도 실행 시 ART 검증기가 `VerifyError`로 앱을 크래시시킨다.

두 번째 흔한 원인은 단순 문법 오류다. 타입 디스크립터의 세미콜론(`Ljava/lang/String;`)을 빼먹거나, 레이블(`:cond_0`)을 잘못 참조하거나, 명령어 이름 오타(`invoke-virual`처럼) 등이다.

세 번째는 타입 불일치다. `const/4 v0, 0x1`로 정수를 넣어놓고 그 레지스터를 나중에 객체 레지스터처럼 `invoke-virtual`의 대상으로 쓰면 검증기가 거부한다.

## 화면/코드에서 보이는 징후
- `apktool b` 실행 중 `smali.jar` 또는 어셈블러 관련 오류 메시지와 함께 특정 파일/줄 번호가 출력된다.
- 빌드는 끝났는데 APK 설치 후 실행하자마자 크래시하며 `adb logcat`에 `java.lang.VerifyError` 또는 `dalvik.system.VerifyError`가 찍힌다.
- 오류 메시지에 `invalid register` 또는 `register out of range`류의 문구가 있다.

## 가장 먼저 할 것
수정한 `.smali` 파일에서 `.locals N` 줄을 찾아, 그 메서드 안에서 실제로 쓰인 `v` 레지스터 중 가장 큰 번호가 `N-1`을 넘지 않는지부터 확인한다. 새 레지스터를 추가했다면 이 숫자부터 먼저 맞춘다.

## 단계별 절차
1. `apktool b` 오류 메시지에 나온 파일 경로와 줄 번호를 정확히 확인한다.
2. 해당 메서드의 `.locals N` 값과 실제 사용된 최대 `v` 번호를 비교한다. 부족하면 `.locals` 숫자를 늘린다.
3. 늘린 만큼 파라미터 레지스터(`p0`, `p1`, ...) 번호가 밀리지 않는지 확인한다 — `.locals`가 커지면 최신 baksmali 표기(`v`/`p` 분리)에서는 보통 파라미터 번호가 안 바뀌지만, 구버전 표기(전부 `v`로 통일된 스타일)에서는 전체 레지스터 번호 체계가 달라질 수 있으므로 표기 스타일을 먼저 확인한다.
4. 타입 디스크립터(`L...;`, `[I` 등)의 세미콜론과 슬래시 표기를 다시 확인한다.
5. 명령어 이름 오타(`invoke-virtual`, `move-result` 등)를 하나씩 다시 확인한다.
6. 빌드가 성공했는데 실행 시 크래시하면, `adb logcat`에서 `VerifyError` 메시지에 나온 정확한 클래스/메서드명을 다시 확인해 그 메서드의 레지스터/타입 일관성을 재점검한다.
7. 여전히 원인을 못 찾겠으면, 수정 범위를 최소화한 뒤(한 줄씩만 바꿔가며) 재빌드/재설치를 반복해 문제 지점을 좁힌다.

## 명령어/단축키
```bash
apktool b out -o rebuilt.apk           # 재조립
adb install -r rebuilt.apk             # 재설치(서명 후)
adb logcat | grep -i verifyerror       # 검증 오류 확인
adb logcat -c && adb shell am start -n pkg/.Activity   # 크래시 로그 새로 수집
```

## 출력 해석
- `apktool b`가 실패하면서 파일명과 줄 번호를 정확히 알려주면, 그 위치의 `.locals`나 문법부터 확인하면 대부분 바로 해결된다.
- `VerifyError: Rejecting class ... because it failed compile-time verification`은 빌드는 성공했지만 ART가 실행 시점에 바이트코드를 거부했다는 뜻이며, 로그의 클래스/메서드명을 실마리로 다시 smali를 점검해야 한다.
- 오류에 특정 레지스터 번호(`v5`)가 언급되면, 그 번호가 `.locals` 범위를 벗어났거나 그 시점에 기대한 타입과 다른 값이 들어있다는 뜻이다.

## 흔한 실수
- 새 레지스터를 코드에 추가하고 `.locals` 숫자를 안 늘리는 것 — 가장 흔한 원인.
- 문자열 타입 디스크립터의 세미콜론을 실수로 지우는 것.
- 재빌드 후 재서명(`apksigner`)을 잊고 그냥 설치하려다 별도의 서명 오류를 이 문제와 혼동하는 것.
- 크래시 로그를 확인하지 않고 "재빌드가 잘못됐나보다"라고 막연히 처음부터 다시 시작하는 것 — `adb logcat`의 `VerifyError` 메시지가 정확한 원인 위치를 알려준다.
- 여러 곳을 한꺼번에 고친 뒤 오류가 나면 어디가 문제인지 못 찾고 전체를 되돌리는 것 — 한 번에 한 곳씩 수정하고 검증하는 습관이 디버깅을 훨씬 빠르게 한다.

## 막혔을 때 다음 체크
- smali 문법 자체가 헷갈리면 → REV-0252 smali 기초 문법
- apktool 디코딩 단계 자체가 실패한다면 → REV-0979 APK가 apktool로 디코드가 안 될 때
- 재서명 후 설치가 안 되면 → REV-0984 APK 재서명 후 설치가 실패할 때

## 미니 예제
다음과 같이 항상 참을 반환하도록 `checkPassword.smali`를 수정했다고 하자.

```smali
.method private checkPassword(Ljava/lang/String;)Z
    .locals 1
    const-string v0, "correct_password"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0

    const/4 v1, 0x1
    return v1
.end method
```

여기서 `.locals 1`(레지스터 1개, `v0`만 허용)인데 새로 `v1`을 추가로 썼다. `apktool b` 실행 시 "invalid register: v1"류의 오류가 발생한다. `.locals`를 `2`로 바꾸면 즉시 해결된다.

```smali
.method private checkPassword(Ljava/lang/String;)Z
    .locals 2
    const-string v0, "correct_password"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0

    const/4 v1, 0x1
    return v1
.end method
```

## 관련 글
- REV-0252 — smali 기초 문법
- REV-0251 — apktool 기본 사용법
- REV-0979 — APK가 apktool로 디코드가 안 될 때
- REV-0984 — APK 재서명 후 설치가 실패할 때

## 출처/검증
- smali `.locals`/레지스터 규칙 및 ART/Dalvik 검증기의 `VerifyError` 동작: `JesusFreke/smali` 공식 저장소 문서 및 Android 공식 개발자 문서("ART and Dalvik") 기준으로 정리했다(2026-09-09 확인).
- apktool 빌드(`apktool b`) 오류 메시지 형식은 apktool 공식 저장소(`iBotPeaches/Apktool`) 이슈 사례 기준.
