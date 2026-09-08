---
id: REV-0251
title: "apktool 기본 사용법"
slug: "rev-0251-apktool-basics"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["apktool", "JADX", "adb"]
keywords: ["apktool", "apktool d", "apktool b", "smali 디코딩", "APK 리소스 디코딩", "APK 리빌드"]
aliases: ["apktool 사용법", "apk 디코딩 도구", "apktool decode build", "apk 리소스 추출"]
symptom_keywords: ["apktool 명령어를 모름", "apk를 smali로 바꾸고 싶음", "apk를 다시 조립하고 싶음", "apktool 오류남"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`apktool`은 APK를 리소스(이미지, XML, 매니페스트)와 smali 코드(Dalvik 바이트코드를 사람이 편집 가능한 텍스트로 표현한 것)로 분해(`d`, decode)했다가 다시 APK로 조립(`b`, build)해주는 도구로, 코드를 직접 수정해서 재패키징해야 하거나 원본 리소스 파일에 접근해야 할 때 반드시 필요하다.

## 언제 검색해야 하나
- APK 파일을 받았는데 어떤 도구로 어떻게 열어야 할지 모를 때
- JADX로 자바 코드는 봤는데 smali 코드나 원본 리소스 XML도 봐야 할 때
- 앱의 로직을 바꿔서(예: 검증 조건을 우회하도록 smali를 수정) 다시 설치 가능한 APK로 만들어야 할 때
- `apktool d`, `apktool b` 명령을 실행했는데 오류가 나서 원인을 모를 때
- apktool과 JADX 중 어떤 걸 먼저 써야 하는지 헷갈릴 때

## 핵심 개념
APK 파일은 사실 ZIP 압축 포맷이므로 압축 프로그램으로 그냥 열 수도 있지만, 그렇게 열면 두 가지 문제가 있다. 첫째, `AndroidManifest.xml`이나 `res/` 안의 XML 파일들이 AXML이라는 바이너리 포맷으로 압축돼 있어서 텍스트 에디터로 보면 알아볼 수 없다. 둘째, 실행 코드가 담긴 `classes.dex`는 Dalvik 바이트코드라는 이진 형식이라 사람이 직접 읽거나 고칠 수 없다.

`apktool`은 이 두 문제를 모두 해결해준다.
- 바이너리 XML(AXML)을 사람이 읽고 편집할 수 있는 텍스트 XML로 복원한다.
- `classes.dex`를 **smali**라는 사람이 읽고 쓸 수 있는 어셈블리 스타일 텍스트 코드로 역어셈블한다(smali 문법 자체는 [REV-0252](./rev-0252-smali-basics.md)에서 다룬다).
- 리소스(이미지, 레이아웃 XML, values 등)를 원본과 거의 동일한 형태로 복원한다.
- 이렇게 수정한 결과물을 다시 APK로 조립(build)할 수 있다.

이 도구가 하는 일은 딱 "분해와 재조립"이지, 자바/코틀린 소스코드로 복원해주는 것은 아니다. 자바 소스처럼 읽고 싶다면 JADX([REV-0249](./rev-0249-jadx-basics.md))를 써야 한다.

### apktool vs JADX — 언제 무엇을 쓰나
초보자가 가장 헷갈리는 부분이 "둘 다 APK를 여는 도구인데 뭐가 다르냐"이다. 역할이 다르다.

| 상황 | 도구 |
|---|---|
| 로직을 빠르게 읽고 이해하고 싶다 (읽기 전용) | JADX |
| 원본 리소스 파일(이미지, XML 레이아웃, 매니페스트 원문)에 접근하고 싶다 | apktool |
| 코드를 수정해서 다시 설치 가능한 APK로 만들어야 한다 | apktool (smali 수정 후 build) |
| 코틀린 문법이 뒤섞인 자바 코드를 그나마 읽기 편하게 보고 싶다 | JADX |
| JADX 디컴파일이 실패하거나 깨진 부분을 원본 바이트코드 수준에서 확인하고 싶다 | apktool (smali) |

실무에서는 두 도구를 같이 쓰는 경우가 훨씬 많다. 처음엔 JADX로 전체 구조와 로직을 빠르게 파악하고, 실제로 코드를 고쳐서 검증 로직을 우회해야 하는 문제라면 apktool로 다시 디코딩해서 해당 smali 파일만 정확히 찾아 수정한 뒤 재조립한다. JADX도 "Save as Gradle project" 기능이 있어 코드 수정이 아예 불가능한 건 아니지만, 실제 CTF 워크플로우에서는 smali를 직접 고치는 방식이 훨씬 안정적이고 널리 쓰인다.

### 설치
apktool은 자바로 만들어졌으므로 JRE가 필요하다. 공식 GitHub(`ibotpeaches/Apktool`)에서 실행 가능한 jar 파일과 wrapper 스크립트(`apktool.bat`, `apktool`)를 받아 PATH에 넣으면 `apktool` 명령을 어디서든 쓸 수 있다. Windows에서는 `apktool.bat`를 PATH 안의 폴더에 두고, jar 파일 이름을 `apktool.jar`로 맞춰야 wrapper 스크립트가 정상 동작한다.

## 화면/코드에서 보이는 징후
apktool로 정상 디코딩하면 다음과 같은 폴더 구조가 만들어진다.
```
out/
├── AndroidManifest.xml       (사람이 읽을 수 있는 텍스트 XML)
├── apktool.yml                (디코딩 메타정보 - 재조립 시 필요)
├── res/                        (리소스: 레이아웃, 문자열, 이미지 등)
│   ├── layout/
│   ├── values/
│   │   └── strings.xml
│   └── drawable/
├── smali/                      (classes.dex를 역어셈블한 smali 코드)
│   └── com/example/ctf/
│       ├── MainActivity.smali
│       └── CheckService.smali
├── smali_classes2/             (dex 파일이 여러 개면 classes2.dex → smali_classes2)
└── original/                   (서명 정보 등 원본 메타데이터)
```
`smali_classes2`, `smali_classes3`처럼 숫자가 붙은 폴더가 여러 개 있다면, 이 앱이 멀티덱스(multidex, 메서드 수가 6만 5천 개를 넘어 dex 파일을 여러 개로 나눈 경우)라는 뜻이다.

## 가장 먼저 할 것
APK 파일이 있는 폴더에서 `apktool d app.apk -o out` 한 줄만 실행해본다. 몇 초~수십 초 안에 `out` 폴더가 생기고 그 안에 `smali/`와 `res/`가 보이면 정상 동작한 것이다.

## 단계별 절차
**1) 디코딩(decode)**
```bash
apktool d app.apk -o out
```
- `-o out`은 결과물을 `out` 폴더에 저장하라는 뜻이다. 생략하면 APK 파일명으로 폴더가 자동 생성된다.
- 이미 같은 이름의 폴더가 있으면 오류가 나므로, 다시 하려면 `-f`(force, 기존 폴더 덮어쓰기) 옵션을 추가한다: `apktool d app.apk -o out -f`

**2) 내용 확인**
`out/AndroidManifest.xml`([REV-0250](./rev-0250-androidmanifest-clues.md) 참고), `out/res/`, `out/smali/` 순서로 열어본다. 특히 `MainActivity.smali`처럼 매니페스트에서 찾은 클래스 이름의 smali 파일을 열어 실제 코드가 어떻게 생겼는지 확인한다.

**3) (필요시) smali 수정**
텍스트 에디터로 `.smali` 파일을 열어 직접 코드를 편집한다. 조건 분기를 강제로 통과시키거나, 로그를 추가하는 식의 수정이 흔하다. smali 문법은 [REV-0252](./rev-0252-smali-basics.md)를 참고한다.

**4) 재조립(build)**
```bash
apktool b out -o app_modified.apk
```
`out` 폴더(디코딩 시 만든 폴더, `apktool.yml`이 있어야 함)를 다시 APK로 조립해서 `app_modified.apk`를 만든다.

**5) 서명**
재조립된 APK는 서명이 없으므로 그대로는 설치되지 않는다. `apksigner`나 `uber-apk-signer` 같은 도구로 디버그 키 서명을 해야 `adb install`이 가능하다.
```bash
apksigner sign --ks debug.keystore --ks-pass pass:android app_modified.apk
```

## 명령어/단축키
```bash
apktool d app.apk -o out          # 디코딩
apktool d app.apk -o out -f       # 기존 폴더 덮어쓰고 디코딩
apktool d app.apk -o out -r       # 리소스 디코딩 생략(smali만 빠르게 필요할 때)
apktool d app.apk -o out -s       # smali 디코딩 생략(리소스만 필요할 때)
apktool b out -o rebuilt.apk      # 재조립
apktool --version                 # 버전 확인
apktool empty-framework-dir --force   # 프레임워크 캐시 문제 해결용
```

## 출력 해석
- `I: Baksmaling classes.dex...` 로그가 보이면 정상적으로 smali 역어셈블이 진행 중이라는 뜻이다.
- `W: ... Cannot find resource...` 같은 경고는 대부분 무시해도 되는 경미한 리소스 참조 문제인 경우가 많지만, 재조립 후 앱이 크래시나면 이 경고 근처를 다시 살펴봐야 한다.
- `brut.androlib.exceptions.AndrolibException` 계열의 예외가 뜨면 대부분 프레임워크 리소스(예: 특정 제조사 커스텀 APK)를 못 찾는 경우이며, `-r` 옵션으로 리소스 디코딩을 생략하거나 `1: framework-res.apk`를 별도로 설치해야 할 수 있다.
- 재조립 후 APK 크기가 원본보다 눈에 띄게 작다면 리소스 압축 방식이 달라진 것일 수 있으니, 필요하면 원본 리소스 압축 옵션(`apktool.yml`의 `doNotCompress`)을 확인한다.

## 흔한 실수
- 디코딩만 하고 재조립 없이 smali 파일만 고쳐서 "왜 앱이 안 바뀌었냐"고 착각하는 것. 수정 후 반드시 `apktool b`로 재조립하고, `apksigner`로 서명한 뒤, 기존 앱을 `adb uninstall`로 지우고 새로 `adb install`해야 한다(서명이 다르면 업데이트 설치가 거부된다).
- `apktool d`를 두 번째 실행할 때 `-f` 없이 실행해서 "폴더가 이미 존재합니다" 오류를 만나는 것.
- smali 파일 안의 레지스터 개수(`.registers N`)를 안 맞추고 코드를 추가해서 재조립은 성공했는데 실행 시 `VerifyError`로 크래시나는 것 — 이 부분은 [REV-0252](./rev-0252-smali-basics.md)에서 자세히 다룬다.
- JADX로 볼 수 있는 걸 굳이 apktool 텍스트 smali로만 읽으려다 시간을 낭비하는 것. 로직 이해가 목적이면 JADX가 압도적으로 빠르다. apktool은 "고쳐야 할 때" 쓰는 도구라고 기억하면 된다.
- 재조립한 APK를 서명 없이 그냥 설치하려다 `INSTALL_PARSE_FAILED_NO_CERTIFICATES` 오류를 만나는 것.

## 막혔을 때 다음 체크
- smali 문법 자체를 모르겠다면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)
- 매니페스트 해석이 궁금하면 → [REV-0250 AndroidManifest.xml에서 단서 찾기](./rev-0250-androidmanifest-clues.md)
- 코드를 그냥 읽기만 하고 싶다면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- 수정한 APK를 기기/에뮬레이터에 설치하고 싶다면 → [REV-0255 adb 기본 명령 치트시트](./rev-0255-adb-cheatsheet.md)

## 미니 예제
간단한 검증 로직이 있는 `CheckActivity.smali`를 apktool로 열었더니 다음과 같았다고 하자.
```smali
.method private checkPassword(Ljava/lang/String;)Z
    .locals 2
    const-string v0, "correct_password"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    return v1
.method end
```
이 메서드는 인자로 받은 문자열(`p1`)이 `"correct_password"`와 같은지 비교해서 그 결과를 그대로 반환한다. 즉 `p1`(사용자 입력)이 `"correct_password"`이면 참(1)을 반환한다는 뜻이다. 이 예제처럼 smali는 짧은 메서드라면 자바 코드보다 오히려 검증 로직이 한눈에 더 명확하게 보이는 경우도 많다. 만약 이 검사 자체를 강제로 항상 통과시키고 싶다면, `return v1`을 `const/4 v1, 0x1` 다음 `return v1`로 바꿔서 무조건 참을 반환하도록 패치하고 `apktool b`로 재조립하면 된다(smali 명령어의 의미는 REV-0252에서 자세히 설명한다).

## 관련 글
- REV-0248 — APK 파일 구조 기초
- REV-0249 — JADX로 APK 분석 시작
- REV-0250 — AndroidManifest.xml에서 단서 찾기
- REV-0252 — smali 기초 문법

## 출처/검증
- apktool 명령어 및 옵션은 공식 저장소(`ibotpeaches/Apktool`, GitHub) 및 공식 문서(apktool.org)를 기준으로 정리했다.
- APK/AXML/멀티덱스 개념은 Android 공식 개발자 문서를 기준으로 설명했다.
- 재서명 절차는 Android 공식 `apksigner` 문서를 기준으로 정리했다(2026-09-08 확인).
