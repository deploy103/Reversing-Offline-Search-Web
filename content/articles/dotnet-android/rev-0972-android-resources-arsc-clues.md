---
id: REV-0972
title: "Android 리소스(resources.arsc)에서 단서 찾기"
slug: "rev-0972-android-resources-arsc-clues"
category: "dotnet-android"
difficulty: "intermediate"
platform: [linux, android]
architecture: [ARM, ARM64]
format: [APK]
tools: [apktool]
keywords: ["resources.arsc", "res/values/strings.xml", "R.string R.id", "public.xml 리소스 ID", "AAPT2 리소스 테이블"]
aliases: ["resources.arsc 분석", "안드로이드 리소스 테이블 구조", "strings.xml에서 flag 찾기", "R클래스 리소스 ID 매핑"]
symptom_keywords: ["resources.arsc를 어떻게 열어야 할지 모르겠다", "R.string.xxx가 실제로 뭔지 모르겠다", "strings.xml에 플래그가 있을까 궁금하다", "public.xml이 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`resources.arsc`는 APK 안의 모든 문자열/색상/치수/스타일 등 리소스 값을 정수 ID(`0x7fXXXXXX` 형태의 리소스 ID)와 매핑해 저장한 바이너리 테이블이며, 코드에서 `R.string.flag_hint`처럼 이름으로만 보이던 참조가 실제로 어떤 리소스 ID·값과 연결되는지 이 파일을 통해 확인할 수 있어서 [REV-0248](./rev-0248-apk-structure.md)의 파일 구조 개요보다 한 단계 더 깊이 리소스 자체를 뒤져야 할 때 필요하다.

## 언제 검색해야 하나
- JADX/smali 코드에 `R.string.something`, `getString(R.string.xxx)`처럼 리소스 ID 참조가 나오는데 실제 값이 뭔지 바로 안 보일 때
- APK를 압축 해제했더니 사람이 읽을 수 있는 `res/values/strings.xml` 원본이 아니라 `res/` 안에 이미 컴파일된 바이너리 XML(`res/layout/activity_main.xml` 등)만 있을 때
- `apktool d`로 디코딩했는데 리소스 오류(`AndrolibException`)가 나서 원인을 파악해야 할 때
- 특정 문자열 리소스가 어느 화면(레이아웃)에서 쓰이는지, 반대로 어떤 리소스 ID가 어느 XML 값에 대응하는지 추적하고 싶을 때
- 앱 안에 숨겨진 문자열(플래그, 서버 URL, 디버그 메시지)이 코드가 아니라 리소스 쪽에 있을 것 같다고 의심될 때

## 핵심 개념

### 왜 APK 안의 XML/문자열이 텍스트가 아닌가
안드로이드는 빌드 시점에 AAPT/AAPT2(Android Asset Packaging Tool)가 `res/` 폴더 아래의 모든 XML(레이아웃, 문자열, 색상, 메뉴 등)을 사람이 읽는 텍스트가 아니라 **컴파일된 바이너리 XML(Binary XML, 확장자는 그대로 `.xml`)** 형태로 변환해서 APK에 넣는다. 이는 난독화 목적이 아니라 파싱 속도와 파일 크기를 위한 정상적인 빌드 최적화다. 그리고 이 XML들이 참조하는 모든 리소스(문자열, 색상, 치수, 드로어블 등)의 이름과 실제 값은 `res/` 폴더 전체가 아니라 APK 루트의 **`resources.arsc`** 파일 하나에 테이블 형태로 모여 저장된다.

### 리소스 ID 구조
자바/코틀린 코드에서 쓰는 `R.string.app_name` 같은 이름은 컴파일되면 정수 하나(리소스 ID)로 바뀐다. 이 정수는 32비트이며 관례상 다음처럼 구성된다.
```
0x  7f        02        0001
    패키지ID   타입ID     엔트리 인덱스
```
- **패키지 ID**(최상위 바이트): 앱 자체 리소스는 보통 `0x7f`. 안드로이드 프레임워크 제공 리소스(`android.R....`)는 `0x01`.
- **타입 ID**: `string`, `layout`, `drawable`, `id`, `color` 등 리소스 종류마다 다른 번호가 배정된다(정확한 번호는 `resources.arsc`의 타입 스트링 풀에 정의되어 있고 빌드마다 조금씩 다를 수 있다).
- **엔트리 인덱스**: 같은 타입 안에서 몇 번째 리소스인지.

`apktool d`로 디코딩하면 이 매핑이 `res/values/public.xml` 파일에 사람이 읽을 수 있는 형태로 복원되어 나온다.
```xml
<public type="string" name="flag_hint" id="0x7f0f001a" />
```
즉 코드에서 본 `0x7f0f001a`라는 상수가 실제로는 `R.string.flag_hint`라는 이름의 문자열 리소스라는 것을 이 파일로 역으로 확인할 수 있다.

### apktool 디코딩 후 리소스 구조
`apktool d app.apk -o out`을 실행하면 `resources.arsc`의 내용이 다음처럼 원본에 가까운 텍스트/파일 구조로 복원된다.
- `out/res/values/strings.xml` — 모든 문자열 리소스의 이름과 실제 값.
- `out/res/values/public.xml` — 리소스 이름 ↔ 리소스 ID(정수) 매핑표.
- `out/res/layout/*.xml`, `out/res/drawable*/`, `out/res/values-*/`(언어/화면밀도별 자원) 등 — 나머지 리소스 원본.
- `out/AndroidManifest.xml` — 리소스 디코딩과 별도로 함께 복원되는 매니페스트([REV-0250](./rev-0250-androidmanifest-clues.md) 참고).

`apktool`이 없거나 리소스 디코딩만 별도로 빠르게 훑고 싶다면, `aapt2 dump resources app.apk` 또는 `aapt dump --values resources app.apk`로도 리소스 테이블 내용을 텍스트로 덤프할 수 있다(Android SDK build-tools에 포함).

### 왜 CTF에서 리소스를 뒤져볼 가치가 있는가
문제 출제자가 플래그나 힌트를 코드(smali/자바)가 아니라 **문자열 리소스**(`strings.xml`)나 **드로어블 이미지 안**, 또는 흔히 간과되는 **`res/raw/`**(원본 그대로 포함되는 임의 파일) 안에 숨겨두는 경우가 종종 있다. 코드만 보고 로직을 다 이해했는데 정답이 안 보인다면, 리소스 쪽을 아직 안 봤을 가능성을 의심해야 한다.

## 화면/코드에서 보이는 징후
- 코드에 `getResources().getString(R.string.xxx)`, smali에 `sget v0, Lcom/example/R$string;->xxx:I` 형태로 리소스 ID 참조가 있음.
- APK를 그냥 `unzip`으로 풀어보면 `res/layout/activity_main.xml`을 텍스트 에디터로 열었을 때 사람이 읽을 수 없는 바이너리로 보임(정상 — apktool 없이 열면 이렇게 보인다).
- `resources.arsc` 파일 자체는 `file resources.arsc` 시 "Android binary resource file" 계열로 식별됨.

## 가장 먼저 할 것
`apktool d app.apk -o out`으로 디코딩부터 하고(REV-0251), `out/res/values/strings.xml`을 열어 사람이 읽을 수 있는 모든 문자열 리소스를 먼저 훑어본다. 대부분의 CTF용 힌트는 이 파일 하나로 바로 드러난다.

## 단계별 절차
1. `apktool d app.apk -o out`으로 리소스를 포함해 전체 디코딩한다.
2. `grep -i "flag\|ctf\|secret\|key" out/res/values/strings.xml`로 의심스러운 문자열을 우선 검색한다.
3. 코드에서 본 리소스 ID(`0x7f0f001a` 등)가 있다면 `grep "0x7f0f001a" out/res/values/public.xml`로 그 ID가 어떤 이름(`R.string.xxx`)에 대응하는지 확인한다.
4. 그 이름으로 다시 `out/res/values*/strings.xml`을 검색해 실제 값(그리고 언어별로 값이 다른 `values-ko/`, `values-en/` 등)을 확인한다.
5. 문자열에서 못 찾았다면 `out/res/raw/`, `out/res/drawable*/`, `out/assets/`([REV-0248](./rev-0248-apk-structure.md) 참고)까지 넓혀 탐색한다.
6. apktool 디코딩이 오류로 실패한다면, `aapt2 dump resources app.apk`로 원본 APK에서 직접 리소스 테이블만 텍스트로 덤프해 대안적으로 확인한다.

## 명령어/단축키
```bash
# 리소스 포함 전체 디코딩
apktool d app.apk -o out

# 문자열 리소스에서 의심 키워드 검색
grep -in "flag\|secret\|password\|ctf" out/res/values/strings.xml

# 리소스 ID -> 이름 매핑 확인
grep "0x7f0f001a" out/res/values/public.xml

# apktool 없이 aapt2로 리소스 테이블 직접 덤프(Android SDK build-tools 필요)
aapt2 dump resources app.apk | less

# aapt(구버전)로 문자열 값 위주 덤프
aapt dump --values resources app.apk | grep -A2 "string/flag"

# res/raw, assets까지 넓게 문자열 검색
grep -rn "flag{" out/res/ out/assets/ 2>/dev/null
```

## 출력 해석
- `public.xml`의 한 줄 `<public type="string" name="flag_hint" id="0x7f0f001a" />`는 "리소스 ID `0x7f0f001a`는 이름이 `flag_hint`인 문자열 리소스다"라는 뜻이며, 코드에서 본 정수 상수를 사람이 읽을 수 있는 이름으로 뒤집어 확인하는 유일한 공식 경로다.
- `strings.xml`에 `<string name="flag_hint">Look inside res/raw</string>` 같은 값이 있다면, 이는 플래그 자체가 아니라 다음 탐색 위치를 알려주는 힌트일 수 있으므로 값의 내용을 그대로 정답으로 오해하지 않아야 한다.
- `values-ko/strings.xml`처럼 언어별 폴더가 따로 있으면, 같은 이름의 문자열이라도 언어 설정에 따라 다른 값을 반환할 수 있으니 기본(`values/`) 폴더 외의 값도 함께 확인해야 한다.
- `aapt2 dump resources`의 출력은 `apktool`의 `public.xml`+`strings.xml`을 합친 것과 비슷한 정보를 한 파일에 텍스트로 담고 있어서, apktool 디코딩이 실패할 때 좋은 대안이 된다.

## 흔한 실수
- 리소스 ID(`0x7f0f001a`)를 코드 안의 다른 정수 상수와 혼동해서, 리소스가 아닌 값을 리소스인 것처럼 잘못 추적하는 것 — 상위 바이트가 `0x7f`(또는 프레임워크의 `0x01`)로 시작하는지부터 확인하는 습관이 필요하다.
- `strings.xml`만 보고 `res/raw/`나 `assets/`([REV-0248](./rev-0248-apk-structure.md) 참고)에 숨겨진 원본 파일까지는 확인하지 않아 힌트를 놓치는 것.
- 언어별 리소스 폴더(`values-ko/`, `values-en/` 등)의 존재를 모르고 기본 `values/strings.xml`만 봐서 실제 실행 환경에서 쓰이는 값과 다른 값을 봤다고 착각하는 것.
- `apktool d` 디코딩이 리소스 오류로 실패했는데, 원인 분석 없이 포기하는 것 — 커스텀 프레임워크 리소스가 있으면 `apktool if`로 프레임워크 apk를 먼저 등록해야 하는 경우가 많다([REV-0968](./rev-0968-jadx-apktool-options-quickref.md) 참고).
- `R$string`, `R$id` 같은 스마리 내부 클래스 이름을 보고 이것이 실제 리소스 값 자체라고 착각하는 것 — 이 클래스들은 이름과 ID의 매핑만 갖고 있을 뿐, 실제 값은 항상 `resources.arsc`(디코딩 후 `strings.xml` 등)에 있다.

## 막혔을 때 다음 체크
- APK 전체 파일 구조에서 리소스가 어디 위치하는지 큰 그림이 헷갈리면 → [REV-0248 APK 파일 구조 기초](./rev-0248-apk-structure.md)
- apktool 자체의 옵션(리소스만 디코딩, 강제 덮어쓰기 등)이 궁금하면 → [REV-0968 JADX/apktool 옵션 빠른 참조](./rev-0968-jadx-apktool-options-quickref.md), [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)
- `AndroidManifest.xml`에서도 단서를 찾고 싶다면 → [REV-0250 AndroidManifest.xml에서 단서 찾기](./rev-0250-androidmanifest-clues.md)
- 리소스가 아니라 코드(smali) 안의 문자열 상수를 찾고 싶다면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)

## 미니 예제
JADX로 디컴파일한 자바 코드에 다음 줄이 있다고 하자.
```java
String hint = getString(R.string.flag_hint);
Toast.makeText(this, hint, Toast.LENGTH_LONG).show();
```
smali로 보면 `R.string.flag_hint`가 리소스 ID 상수로 컴파일되어 있다.
```smali
const v0, 0x7f0f001a
invoke-virtual {p0, v0}, Lcom/example/ctf/MainActivity;->getString(I)Ljava/lang/String;
```
`apktool d app.apk -o out` 후 `out/res/values/public.xml`에서 해당 ID를 검색한다.
```bash
$ grep "0x7f0f001a" out/res/values/public.xml
    <public type="string" name="flag_hint" id="0x7f0f001a" />
```
이제 이름이 `flag_hint`임을 알았으니 `strings.xml`에서 실제 값을 확인한다.
```bash
$ grep -A1 "flag_hint" out/res/values/strings.xml
<string name="flag_hint">Check res/raw/secret.txt</string>
```
이 결과로 실제 플래그가 문자열 자체가 아니라 `res/raw/secret.txt`라는 별도 파일 안에 있다는 힌트를 얻었다. `cat out/res/raw/secret.txt`로 이어서 확인하면 된다. 이렇게 "코드의 리소스 ID → `public.xml`의 이름 → `strings.xml`의 값" 세 단계를 거치는 것이 리소스 기반 힌트를 추적하는 표준 경로다.

## 관련 글
- REV-0248 — APK 파일 구조 기초
- REV-0250 — AndroidManifest.xml에서 단서 찾기
- REV-0251 — apktool 기본 사용법
- REV-0968 — JADX/apktool 옵션 빠른 참조
- REV-0252 — smali 기초 문법

## 출처/검증
- `resources.arsc`의 구조(문자열 풀, 타입/키 스트링 풀, 리소스 ID 구성 `패키지/타입/엔트리`)는 Android 오픈소스 프로젝트(AOSP) `ResourceTypes.h` 및 공식 개발자 문서(developer.android.com, "App resources overview")를 기준으로 정리했다.
- `apktool`의 리소스 디코딩 결과물(`public.xml`, `res/values/*.xml` 등) 형식은 apktool 공식 문서(apktool.org) 기준으로 확인했다.
- `aapt2 dump resources` 명령 및 출력 형식은 Android SDK 공식 문서(developer.android.com, "aapt2") 기준으로 확인했다 (2026-09-09 확인).
