---
id: REV-0299
title: "JADX apktool adb 설치와 사용법"
slug: "rev-0299-jadx-apktool-adb-install"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [arm, arm64]
format: [APK]
tools: ["JADX", "apktool", "adb"]
keywords: ["JADX 설치", "apktool 설치", "adb 설치", "안드로이드 리버싱 도구 설치", "Android SDK Platform Tools"]
aliases: ["JADX 설치법", "apktool 설치법", "adb 설치법", "안드로이드 분석 도구 셋업"]
symptom_keywords: ["jadx 명령이 없다고 뜸", "apktool 설치가 안됨", "adb 명령이 없다고 뜸", "안드로이드 리버싱 도구를 처음 준비함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
안드로이드 APK를 분석하려면 자바 소스처럼 읽는 **JADX**, 리소스/smali를 분해·재조립하는 **apktool**, 실제 기기·에뮬레이터를 제어하는 **adb** 세 도구가 한 세트로 필요하며, 셋 다 설치 프로그램 없이 압축 파일이나 단일 실행 파일을 받는 것으로 준비가 끝난다.

## 언제 검색해야 하나
- APK 파일을 처음 받았는데 어떤 도구부터 설치해야 할지 모를 때
- 오프라인 대회 전에 안드로이드 분석 도구 세트를 미리 준비해야 할 때
- `jadx`, `apktool`, `adb` 명령이 "찾을 수 없음"으로 뜰 때

세 도구 각각의 상세 사용법(화면 구성, smali 수정, adb 세부 명령)은 이 문서에서 반복하지 않는다. 아래 원본 문서를 참고할 것.
- apktool 상세 사용법 → [apktool 기본 사용법](../dotnet-android/rev-0251-apktool-basics.md)
- adb 상세 사용법 → [adb 기본 명령 치트시트](../dotnet-android/rev-0255-adb-cheatsheet.md)
- JADX 상세 사용법은 dotnet-android 카테고리의 JADX 전용 문서(작성 예정/병행 작성 중)를 참고할 것 — 이 문서 작성 시점에는 아직 존재하지 않았다.

## 핵심 개념
세 도구는 역할이 겹치지 않고 이어진다.

| 도구 | 역할 |
|---|---|
| JADX | `classes.dex`를 자바 소스에 가깝게 디컴파일해서 읽기 전용으로 보여줌 |
| apktool | APK를 리소스+smali로 분해(decode)하고, 수정 후 다시 APK로 조립(build) |
| adb | PC에서 실제 기기/에뮬레이터에 APK를 설치·실행하고 로그·파일을 확인 |

일반적인 흐름은 "JADX로 구조 파악 → (수정 필요시) apktool로 분해·smali 수정·재조립 → adb로 설치·실행·로그 확인"이다.

## 가장 먼저 할 것
세 도구 모두 자바(JRE) 또는 안드로이드 자체 런타임에 의존하므로, 설치 전 자바가 설치되어 있는지 먼저 확인한다.
```bash
java -version
```
JADX와 apktool은 둘 다 자바로 작성된 도구라 JRE 8 이상이 필요하다(도구별 최소 버전은 공식 문서에서 확인). 자바가 없다면 OpenJDK 등을 먼저 설치해 둔다.

## 단계별 절차

### 1) JADX 설치
공식 GitHub 저장소(`https://github.com/skylot/jadx/releases`)에서 `jadx-<버전>.zip`을 받는다. 압축을 풀면 `bin/` 폴더 안에 두 가지 실행 스크립트가 있다.
```text
jadx        # 커맨드라인 버전 (텍스트로 자바 소스 export)
jadx-gui    # GUI 버전 (트리 탐색, 검색, 클릭으로 코드 열람)
```
Windows는 `jadx.bat`/`jadx-gui.bat`, Linux/Mac은 `jadx`/`jadx-gui` 쉘 스크립트를 실행한다. 설치 프로그램이 없는 순수 압축 배포이므로 폴더째 오프라인 매체에 복사해 가면 된다.
```bash
./bin/jadx-gui        # GUI로 바로 실행
./bin/jadx -d out app.apk   # 커맨드라인으로 out/ 폴더에 자바 소스 export
```

### 2) apktool 설치
공식 사이트(`https://apktool.org`) 또는 GitHub(`ibotpeaches/Apktool`)에서 두 가지를 받는다.
1. 실행 가능한 jar 파일(`apktool.jar`로 이름을 맞춘다)
2. 운영체제별 wrapper 스크립트(`apktool.bat` for Windows, `apktool` for Linux/Mac)

두 파일을 같은 PATH 폴더에 넣으면 `apktool` 명령을 어디서든 쓸 수 있다.
```bash
apktool --version
```
버전이 출력되면 정상 설치된 것이다. 자세한 사용법(`d`/`b` 등)은 [apktool 기본 사용법](../dotnet-android/rev-0251-apktool-basics.md)에서 다룬다.

### 3) adb 설치
adb는 Android SDK Platform Tools의 일부로 배포된다. 공식 페이지(`https://developer.android.com/tools/releases/platform-tools`)에서 운영체제에 맞는 zip을 받아 압축만 풀면 그 안에 `adb`(또는 `adb.exe`) 실행 파일이 있다.
```bash
# 압축을 푼 폴더 안에서
./adb version
```
Android Studio 전체를 설치할 필요는 없다 — Platform Tools 패키지 하나만으로 `adb`는 충분히 동작한다. 오프라인 대회를 준비한다면 이 zip 하나만 미리 받아 두면 된다.

### 4) PATH 등록(선택이지만 강력 권장)
세 도구 모두 매번 전체 경로를 타이핑하지 않으려면, 압축을 푼 각 폴더(또는 `bin/` 하위 폴더)를 시스템 PATH 환경변수에 등록해 둔다. Windows에서는 "시스템 속성 → 환경 변수 → Path 편집"에서, Linux에서는 `~/.bashrc`에 `export PATH="$PATH:/경로/jadx/bin"` 형태로 추가한다.

### 5) 동작 확인 3종 세트
```bash
java -version     # JADX/apktool 실행에 필요
jadx --version
apktool --version
adb version
```
네 명령 모두 오류 없이 버전 정보를 출력하면 안드로이드 분석 준비가 끝난 것이다.

## 명령어/단축키
```bash
jadx -d out app.apk        # 커맨드라인으로 자바 소스 export
jadx-gui                   # GUI 실행
apktool d app.apk -o out   # 리소스+smali 분해
apktool b out -o rebuilt.apk  # 재조립
adb devices                # 연결된 기기/에뮬레이터 확인
adb install app.apk        # 앱 설치
```

## 흔한 실수
- 자바(JRE)를 설치하지 않은 채 JADX/apktool을 실행해서 "명령을 찾을 수 없다"거나 알 수 없는 오류를 만나는 것 — 두 도구 모두 자바 위에서 동작한다.
- apktool의 jar 파일 이름을 `apktool.jar`가 아닌 다른 이름(`apktool_2.9.3.jar` 등)으로 그대로 두어 wrapper 스크립트가 못 찾는 것 — 공식 안내대로 파일명을 `apktool.jar`로 맞춰야 한다.
- Android Studio 전체(수 GB)를 설치해야 `adb`를 쓸 수 있다고 오해하는 것 — Platform Tools 패키지 하나만으로 충분하다.
- 오프라인 대회 당일 처음 실행해보다가 방화벽/보안 소프트웨어가 `adb`의 USB 통신을 막아 기기를 못 찾는 것 — 사전에 실제 대회 환경과 최대한 비슷한 조건에서 검증해야 한다.

## 막혔을 때 다음 체크
- APK를 분해·재조립하고 smali를 수정하는 절차 → [apktool 기본 사용법](../dotnet-android/rev-0251-apktool-basics.md)
- 기기 연결, 설치, 로그, 앱 데이터 접근 → [adb 기본 명령 치트시트](../dotnet-android/rev-0255-adb-cheatsheet.md)
- 매니페스트에서 시작점(exported 컴포넌트 등)을 먼저 찾고 싶다면 → dotnet-android 카테고리의 AndroidManifest 관련 문서

## 미니 예제
```bash
$ adb devices
List of devices attached
emulator-5554   device

$ adb install ./challenge.apk
Success

$ java -jar jadx-cli.jar -d out ./challenge.apk
INFO  ... load ...
INFO  ... done
```
세 줄로 "에뮬레이터에 APK를 설치하고, 동시에 JADX로 소스를 뽑아 `out/` 폴더에서 읽을 준비"까지 끝났다.

## 관련 글
- REV-0300 — Z3 angr pwntools Python 오프라인 패키지 준비
- REV-0298 — dnSpyEx ILSpy 설치와 사용법

## 출처/검증
- JADX 배포 형태와 실행 스크립트(`jadx`, `jadx-gui`) 구조: JADX 공식 GitHub 저장소(skylot/jadx) README 기준.
- apktool 설치 방식(jar + wrapper 스크립트): apktool 공식 문서(apktool.org) 및 GitHub 저장소(ibotpeaches/Apktool) 기준.
- adb 배포(Android SDK Platform Tools)와 최소 요구사항: Android 공식 개발자 문서(developer.android.com) 기준.
- 이 문서에서 언급한 "JADX 전용 사용법 문서"는 이 저장소의 dotnet-android 카테고리에서 병행 작성 중이며, 이 문서 작성 시점에는 파일이 존재하지 않아 직접 확인하지 못했다. 통합 시 경로/제목을 다시 검증할 것.
