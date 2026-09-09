---
id: REV-0968
title: "JADX/apktool 옵션 빠른 참조"
slug: "rev-0968-jadx-apktool-options-quickref"
category: "dotnet-android"
difficulty: "basic"
platform: [linux, windows]
architecture: [ARM, ARM64]
format: [APK]
tools: [JADX, apktool]
keywords: ["jadx 옵션", "apktool 옵션", "jadx -d -e --deobf", "apktool d b -r -f", "jadx-gui 단축키"]
aliases: ["jadx 명령줄 옵션표", "apktool 명령줄 옵션표", "jadx-gui 옵션", "apktool decode build 옵션"]
symptom_keywords: ["jadx 옵션이 헷갈린다", "apktool d 옵션을 모르겠다", "apktool b 빌드가 실패한다", "jadx deobfuscation 옵션을 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
JADX는 `apk`를 자바 소스로 디컴파일하는 도구, apktool은 `apk`를 smali/리소스 원본 형태로 분해(decode)했다가 다시 조립(build)하는 도구인데 각각 CLI 옵션이 많아 처음엔 어떤 플래그를 언제 써야 할지 헷갈리므로, 자주 쓰는 옵션만 표로 정리해두면 명령어를 검색하지 않고 바로 찾아 쓸 수 있다.

## 언제 검색해야 하나
- `jadx`로 디컴파일했는데 이름이 다 깨져 있어서 `--deobf` 계열 옵션이 필요할 때
- `apktool d`로 디코딩할 때 리소스를 빼고 싶거나(`-s`), 강제로 덮어쓰고 싶을 때(`-f`)
- `apktool b`로 다시 빌드했는데 실패해서 어떤 옵션이 문제인지 확인하고 싶을 때
- `jadx-gui`에서 검색/네비게이션 단축키를 모를 때
- 리소스 없이 코드만, 또는 코드 없이 리소스만 뽑고 싶을 때

## 핵심 개념
두 도구는 목적이 다르다. **JADX**는 `classes.dex`를 역컴파일해서 자바 소스에 가까운 결과를 만드는 데 특화되어 있고, 코드를 다시 조립(rebuild)하는 기능은 없다(읽기 전용 분석용). **apktool**은 반대로 `.smali` 텍스트와 리소스(XML, 이미지 등)를 원래 포맷에 최대한 가깝게 분해/재조립하는 데 특화되어 있어서, 패치 후 재빌드가 필요할 때는 apktool을 쓴다. 즉 "읽기 쉬운 코드로 보고 싶다"면 JADX, "리소스/smali를 고쳐서 다시 APK로 만들고 싶다"면 apktool이라고 기억하면 선택이 쉬워진다.

## 화면/코드에서 보이는 징후
터미널에서 `jadx --help`, `apktool --help` 또는 `apktool d --help`/`apktool b --help`를 치면 아래 표에 나온 옵션들이 실제로 나열되는 것을 확인할 수 있다.

## 가장 먼저 할 것
`jadx <apk경로> -d out_jadx`로 기본 디컴파일 결과부터 뽑아보고, 동시에 `apktool d <apk경로> -o out_apktool`로 smali/리소스 원본도 함께 뽑아 둔다. 둘 다 뽑아두면 이후 상황에 따라 필요한 쪽을 바로 참조할 수 있다.

## 단계별 절차
1. `jadx app.apk -d out_jadx`로 자바 소스 형태 디컴파일 결과를 생성한다.
2. 이름이 깨져 있으면 `jadx app.apk -d out_jadx --deobf`로 자동 이름 복원을 시도한다.
3. 리소스/smali 원본이 필요하면 `apktool d app.apk -o out_apktool`로 디코딩한다.
4. smali를 수정했다면 `apktool b out_apktool -o patched.apk`로 재조립한다.
5. 재조립한 APK는 서명이 없으므로 `apksigner`(Android SDK build-tools 포함) 등으로 서명 후 설치해야 실행 가능하다.

## 명령어/단축키
```text
[JADX - CLI]
jadx app.apk -d out                 out/ 폴더에 디컴파일 결과 저장
jadx app.apk -d out --deobf         난독화된 이름 자동 복원 시도
jadx app.apk -d out -e              리소스(res/AndroidManifest 등)는 빼고 코드만
jadx app.apk -d out --no-res        위와 동일한 의미의 최신 표기(버전에 따라 다름)
jadx app.apk -d out --show-bad-code 디컴파일 실패 부분도 억지로 표시(주석 형태 오류 포함)
jadx app.apk -d out -j 4            병렬 스레드 수 지정(속도 조절)
jadx app.apk -d out --deobf-min 3 --deobf-max 64   자동 이름 복원 대상 이름 길이 범위 조정

[JADX-GUI]
Ctrl+Alt+F / Ctrl+F      전체 프로젝트 검색 / 현재 파일 내 검색
Ctrl+G                   특정 줄로 이동
Ctrl+Alt+H               클래스 계층(Hierarchy) 보기
Ctrl+Alt+B               스마리(Smali) 보기 토글

[apktool]
apktool d app.apk -o out            디코딩(smali + 리소스 전부)
apktool d app.apk -o out -r         리소스 디코딩 생략, smali만
apktool d app.apk -o out -s         smali(코드) 디코딩 생략, 리소스만
apktool d app.apk -o out -f         out 폴더가 이미 있어도 강제 덮어쓰기
apktool d app.apk -o out --no-res   -r과 유사(리소스 스킵), 버전에 따라 옵션명 다름
apktool b out -o patched.apk        out/ 폴더 내용을 다시 apk로 빌드
apktool b out -o patched.apk -d     디버그 정보 유지하며 빌드
apktool if framework-res.apk        커스텀/프레임워크 리소스 apk 설치(리소스 디코딩 오류 시 필요)
```

## 출력 해석
- `jadx`가 특정 메서드에서 `// jadx: failed to find 'out' variable`, `//$FF: renamed from: ...` 같은 주석을 남기면, 그 메서드의 디컴파일이 완전하지 않다는 뜻이므로 `--show-bad-code` 옵션으로 원인이 되는 IL/바이트코드 패턴을 더 확인하거나 [REV-0252](./rev-0252-smali-basics.md)의 smali 원문으로 직접 확인해야 한다.
- `apktool d`가 `Warning: brut.androlib.exceptions.AndrolibException` 계열 리소스 오류를 내면, 대개 커스텀 리소스 타입(예: `frameworks`)이 있는 앱이라 `apktool if`로 프레임워크 apk를 먼저 설치해야 하는 경우다.
- `apktool b`가 성공했는데 설치가 안 되면, APK 서명이 안 됐기 때문일 확률이 가장 높다 — apktool은 리빌드까지만 하고 서명은 별도 도구(`apksigner`, `uber-apk-signer` 등)가 담당한다.

## 흔한 실수
- `apktool d`로 뽑은 smali를 고친 뒤 `jadx`로 다시 빌드하려는 것 — JADX에는 빌드(재조립) 기능이 없다. 재조립은 항상 apktool의 `b` 명령이다.
- `apktool d`를 여러 번 실행하며 매번 폴더 이름 충돌 오류를 만나는 것 — `-f` 옵션으로 강제 덮어쓰기하거나 출력 폴더 이름을 바꿔야 한다.
- `--deobf` 없이 JADX를 돌리고 "이름이 왜 이렇게 이상하냐"고 헷갈리는 것. `--deobf`는 완벽하지 않지만 최소한 `C0512a` 같은 이름을 사람이 조금 더 읽기 쉬운 형태로 바꿔주려 시도한다.
- 재조립한 APK가 서명 없이 설치되지 않는데 apktool 자체의 버그로 오해하는 것 — 서명은 apktool의 책임 범위가 아니다.
- `-r`(리소스 스킵)과 `-s`(smali 스킵)를 반대로 기억해서 원하는 부분이 빠진 채로 디코딩하는 것.

## 막혔을 때 다음 체크
- JADX로 처음 APK를 여는 기본 흐름 자체가 궁금하면 → [REV-0249 JADX로 APK 분석 시작](./rev-0249-jadx-basics.md)
- apktool 기본 사용법과 smali 재조립 흐름이 궁금하면 → [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)
- 디코딩된 smali 문법 자체를 읽는 법이 궁금하면 → [REV-0252 smali 기초 문법](./rev-0252-smali-basics.md)
- 리소스(`resources.arsc`) 안에서 단서를 더 찾고 싶으면 → REV-0972 Android 리소스(resources.arsc)에서 단서 찾기

## 미니 예제
```bash
$ jadx target.apk -d out_jadx --deobf
INFO  - loading ...
INFO  - processing ...
INFO  - done

$ apktool d target.apk -o out_apktool -f
I: Using Apktool 2.9.3 on target.apk
I: Loading resource table...
I: Decoding AndroidManifest.xml with resources...
I: Decoding file-resources...
I: Decoding values */* XMLs...
I: Baksmaling classes.dex...
I: Copying assets and libs...

# smali를 수정한 뒤
$ apktool b out_apktool -o patched.apk
I: Using Apktool 2.9.3
I: Checking whether sources has changed...
I: Smaling smali folder into classes.dex...
I: Building resources...
I: Building apk file...
```
`out_jadx/`에는 사람이 읽기 쉬운 자바 소스가, `out_apktool/smali/`에는 수정 가능한 smali 원본이 생성된다. 로직 파악은 `out_jadx`로, 실제 패치/재빌드는 `out_apktool`로 진행하는 역할 분담이 이 두 도구를 함께 쓰는 표준적인 방식이다.

## 관련 글
- REV-0249 — JADX로 APK 분석 시작
- REV-0251 — apktool 기본 사용법
- REV-0252 — smali 기초 문법
- REV-0972 — Android 리소스(resources.arsc)에서 단서 찾기

## 출처/검증
- JADX CLI 옵션(`-d`, `-e`, `--deobf`, `--deobf-min/max`, `--show-bad-code` 등)은 JADX 공식 GitHub 저장소(`skylot/jadx`) README 및 `--help` 출력 기준으로 정리했다.
- apktool 옵션(`d`/`b`, `-r`, `-s`, `-f`, `if`)은 apktool 공식 문서(apktool.org 및 GitHub `iBotPeaches/Apktool`) 기준으로 정리했다 (2026-09-09 확인).
