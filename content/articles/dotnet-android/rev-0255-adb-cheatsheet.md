---
id: REV-0255
title: "adb 기본 명령 치트시트"
slug: "rev-0255-adb-cheatsheet"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [arm, arm64]
format: [APK]
tools: ["adb"]
keywords: ["adb devices", "adb install", "adb logcat", "adb pull", "adb shell run-as", "adb shell pm list packages"]
aliases: ["adb 명령어 모음", "adb 사용법", "안드로이드 디버그 브릿지", "adb 치트시트"]
symptom_keywords: ["adb devices에 기기가 안 뜸", "adb install 오류", "앱 데이터 폴더에 접근이 안 됨", "logcat 사용법을 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`adb`(Android Debug Bridge)는 PC에서 USB나 에뮬레이터로 연결된 안드로이드 기기를 명령줄로 제어하는 공식 도구로, 앱 설치/실행/로그 확인/파일 추출/앱 전용 데이터 접근까지 안드로이드 동적 분석의 거의 모든 첫 단계에서 쓰인다.

## 언제 검색해야 하나
- APK를 실제 기기나 에뮬레이터에 설치하고 실행해서 동작을 봐야 할 때
- 앱이 출력하는 로그(`Log.d`, `System.out.println`, 크래시 스택트레이스)를 실시간으로 보고 싶을 때
- 앱이 `/data/data/<패키지명>/` 아래에 만든 파일(설정값, DB, SharedPreferences)을 꺼내보고 싶을 때
- `adb shell run-as`가 뭔지, 왜 필요한지 모를 때
- 매니페스트에서 찾은 `exported` 컴포넌트를 직접 실행시키는 명령을 모를 때

## 핵심 개념
`adb`는 세 부분으로 이루어진 클라이언트-서버 구조 도구다. PC에서 실행하는 `adb` 클라이언트, PC에서 백그라운드로 도는 `adb server`, 그리고 기기(또는 에뮬레이터) 안에서 실행되는 `adbd` 데몬이 USB 또는 TCP로 통신한다. 이 구조를 몰라도 명령을 쓰는 데는 문제없지만, `adb devices`에 기기가 안 뜰 때 `adb kill-server` → `adb start-server`로 서버를 재시작해보는 이유가 바로 이 구조 때문이라는 것만 기억해두면 된다.

CTF에서 `adb`가 중요한 이유는, 정적 분석(apktool, JADX, smali)만으로는 앱이 실제로 무슨 값을 화면에 찍는지, 어떤 로그를 남기는지, 파일 시스템에 무엇을 남기는지 알 수 없기 때문이다. `adb`는 이런 동적 정보를 확인하는 가장 기본적이고 확실한 수단이다.

### 기기 연결 확인
```bash
adb devices
```
연결된 기기/에뮬레이터 목록과 상태(`device`, `unauthorized`, `offline`)가 출력된다. `unauthorized`가 뜨면 기기 화면에서 "USB 디버깅을 허용하시겠습니까?" 팝업을 승인해야 한다. 아무것도 안 뜨면 USB 디버깅이 꺼져있거나(설정 → 개발자 옵션 → USB 디버깅 켜기), 에뮬레이터가 아예 실행 중이 아닌 것이다.

### 앱 설치/삭제
```bash
adb install app.apk              # 새로 설치
adb install -r app.apk           # 기존 앱 유지하며 재설치(데이터 보존)
adb uninstall com.example.ctf    # 완전 삭제
```
apktool로 smali를 수정하고 재조립·재서명한 APK를 설치할 때는, 서명이 원본과 다르므로 기존 앱을 먼저 `uninstall`해야 설치가 성공하는 경우가 많다.

### 설치된 패키지 확인
```bash
adb shell pm list packages              # 전체 패키지 목록
adb shell pm list packages | grep ctf   # 이름으로 필터
adb shell pm path com.example.ctf       # 해당 패키지의 APK 실제 경로 확인
```
`pm path`로 확인한 경로는 `adb pull`로 설치된 APK 원본을 기기에서 그대로 뽑아올 때도 유용하다(문제에서 APK를 직접 안 주고 "기기에 이미 설치돼 있다"는 형태로 낼 때 특히 필요).

### 앱 실행 (컴포넌트 직접 실행)
```bash
adb shell am start -n com.example.ctf/.MainActivity
```
`-n` 뒤에는 `패키지이름/클래스이름` 형태로 실행할 액티비티를 지정한다. [REV-0250](./rev-0250-androidmanifest-clues.md)에서 찾은 `exported="true"` 액티비티를 런처 아이콘 없이 직접 실행할 때 이 명령을 쓴다. 커스텀 액션이 필요하면 `-a` 옵션을 추가한다.
```bash
adb shell am start -n com.example.ctf/.SecretActivity -a com.example.ctf.ACTION_SHOW
```

### 로그 확인 (logcat)
```bash
adb logcat                          # 전체 로그 스트리밍
adb logcat | grep -i ctf            # 특정 키워드로 필터
adb logcat -c                       # 기존 로그 버퍼 비우기(새로 시작할 때 유용)
adb logcat *:E                      # Error 레벨 이상만 보기
```
안드로이드 앱은 `Log.d`, `Log.e`, 예외 스택트레이스, 시스템 메시지를 전부 logcat이라는 공용 로그 스트림에 남긴다. 문제 앱이 디버깅용으로 `Log.d("CTF", "flag check: " + input)` 같은 코드를 실수로(혹은 의도적으로 힌트로) 남겨뒀다면 `adb logcat`만으로 flag가 그대로 노출되기도 한다. 실행 전 `adb logcat -c`로 버퍼를 비운 뒤 앱을 실행하면 필요한 로그만 깔끔하게 볼 수 있다.

### 앱 데이터 접근: run-as와 pull
안드로이드는 각 앱의 데이터 디렉터리(`/data/data/<패키지명>/`)를 다른 앱이나 일반 shell 사용자가 못 읽도록 격리한다. 루트 권한이 없는 일반 기기에서 이 안을 들여다보려면 `run-as`를 쓴다.
```bash
adb shell run-as com.example.ctf ls -la /data/data/com.example.ctf/
adb shell run-as com.example.ctf cat /data/data/com.example.ctf/shared_prefs/config.xml
```
`run-as`는 해당 패키지가 **디버그 가능(`android:debuggable="true"`) 상태이거나, 기기가 루팅/에뮬레이터의 userdebug 빌드**일 때 동작한다. CTF용 앱은 대부분 debuggable로 빌드되므로 보통 문제없이 동작한다.

파일을 PC로 직접 꺼내고 싶다면 `run-as`로 임시 위치에 복사한 뒤 `adb pull`로 가져오는 방식을 흔히 쓴다.
```bash
adb shell "run-as com.example.ctf cat /data/data/com.example.ctf/files/secret.db" > secret.db
```
또는 에뮬레이터/루팅 기기라면 `adb root` 후 바로 `adb pull /data/data/com.example.ctf/files/secret.db ./`도 가능하다.

## 화면/코드에서 보이는 징후
- 터미널에서 `adb devices`를 쳤을 때 `List of devices attached` 아래 아무 줄도 없으면 연결된 기기가 없는 것이다.
- `adb install` 실패 시 `INSTALL_FAILED_UPDATE_INCOMPATIBLE` 또는 `INSTALL_FAILED_ALREADY_EXISTS` 같은 오류 메시지가 뜬다.
- `run-as` 실패 시 `run-as: Package 'com.example.ctf' is not debuggable` 메시지가 뜬다.

## 가장 먼저 할 것
`adb devices`로 기기 연결부터 확인한다. 정상이면 `device`라는 상태 문구가 기기 시리얼 옆에 뜬다. 이게 안 되면 이후 모든 명령이 소용없으므로 반드시 첫 단계로 확인한다.

## 단계별 절차
1. `adb devices`로 연결 확인.
2. `adb install app.apk`로 앱 설치.
3. `adb shell pm list packages | grep <힌트>`로 정확한 패키지 이름 확인(모를 경우).
4. `adb logcat -c`로 로그 버퍼 비우기.
5. `adb shell am start -n <패키지>/<액티비티>`로 앱(또는 특정 컴포넌트) 실행.
6. `adb logcat | grep -i <패키지 또는 flag>`로 실행 중 로그 관찰.
7. 필요하면 `adb shell run-as <패키지> ls /data/data/<패키지>/`로 앱 데이터 확인 후 `adb pull`이나 `cat` 리다이렉션으로 파일 추출.

## 명령어/단축키
```bash
adb devices                                  # 연결된 기기 목록
adb kill-server && adb start-server          # adb 서버 재시작
adb install app.apk                          # 설치
adb install -r app.apk                       # 재설치(데이터 유지)
adb uninstall com.example.ctf                # 삭제
adb shell pm list packages                   # 패키지 목록
adb shell pm path com.example.ctf            # 설치 경로 확인
adb shell am start -n pkg/.Activity          # 컴포넌트 실행
adb logcat                                   # 로그 확인
adb logcat -c                                # 로그 버퍼 비우기
adb pull /data/data/pkg/files/x.db ./        # 파일 꺼내오기(root/에뮬레이터)
adb push local.txt /sdcard/local.txt         # 파일 넣기
adb shell run-as com.example.ctf <명령>       # 앱 권한으로 명령 실행
adb shell                                    # 대화형 쉘 진입
```

## 출력 해석
- `adb devices` 결과가 `unauthorized`면 기기 화면의 RSA 키 승인 팝업을 확인해야 한다. `offline`이면 케이블을 다시 꽂거나 `adb kill-server`부터 다시 시도한다.
- `pm list packages`는 `package:com.example.ctf` 형태로 출력되므로, 실제 패키지 이름을 쓸 때는 `package:` 접두사를 빼야 한다.
- `am start` 성공 시 `Starting: Intent { ... }`가 출력되고 기기 화면이 전환된다. `Error: Activity class {...} does not exist`가 뜨면 패키지/클래스 이름 오타이거나 해당 컴포넌트가 존재하지 않는 것이다.

## 흔한 실수
- `pm list packages` 출력의 `package:` 접두사를 그대로 포함해서 다음 명령에 쓰는 것.
- `am start -n`에서 클래스 이름 앞의 점(`.`)을 빼먹는 것. 매니페스트에서 `android:name=".MainActivity"`였다면 `pkg/.MainActivity`처럼 점을 포함해야 한다(매니페스트 표기 규칙은 [REV-0250](./rev-0250-androidmanifest-clues.md) 참고).
- `run-as`가 항상 되는 줄 알고 릴리즈 빌드(non-debuggable) 앱에도 시도해서 "안 된다"고 당황하는 것 — CTF 문제가 아닌 일반 상용 앱에서는 대부분 막혀 있다.
- 로그가 너무 많이 쏟아져서 원하는 줄을 못 찾는 것. `adb logcat -c`로 미리 비우고, `grep`으로 패키지명이나 태그로 필터링하는 습관을 들여야 한다.
- 에뮬레이터와 실기기가 동시에 연결돼 있을 때 `adb`가 어느 쪽에 명령을 보낼지 몰라 오류가 나는 것. 이럴 땐 `adb devices`로 시리얼을 확인하고 `adb -s <시리얼> <명령>` 형태로 대상을 명시해야 한다.

## 막혔을 때 다음 체크
- `exported` 컴포넌트를 어떻게 찾는지 모르면 → [REV-0250 AndroidManifest.xml에서 단서 찾기](./rev-0250-androidmanifest-clues.md)
- `run-as`로도 안 열리는 파일이 있다면 Frida로 프로세스 내부에서 직접 파일 접근 코드를 후킹하는 방법을 고려 → [REV-0256 Frida로 함수 관찰하는 기본 흐름](./rev-0256-frida-basics.md)
- 앱을 수정해서 재설치해야 한다면 → [REV-0251 apktool 기본 사용법](./rev-0251-apktool-basics.md)

## 미니 예제
CTF 문제 APK를 받아 처음부터 끝까지 `adb`로 훑어보는 흐름 예시다.
```bash
$ adb devices
List of devices attached
emulator-5554   device

$ adb install app.apk
Success

$ adb shell pm list packages | grep ctf
package:com.example.ctf

$ adb logcat -c
$ adb shell am start -n com.example.ctf/.MainActivity
Starting: Intent { cmp=com.example.ctf/.MainActivity }

$ adb logcat | grep -i ctf
D/CTF: input received: test123
D/CTF: expected length: 16
```
로그에서 "expected length: 16"이라는 힌트를 확인했다면, flag 길이가 16자라는 정보를 얻은 것이다. 이어서 `run-as`로 앱 데이터를 들여다본다.
```bash
$ adb shell run-as com.example.ctf ls /data/data/com.example.ctf/shared_prefs/
config.xml

$ adb shell run-as com.example.ctf cat /data/data/com.example.ctf/shared_prefs/config.xml
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="hint">flag_prefix_is_CTF</string>
</map>
```
이런 식으로 정적 분석 없이 `adb` 명령 몇 줄만으로도 문제 해결에 필요한 힌트를 꽤 많이 모을 수 있다.

## 관련 글
- REV-0250 — AndroidManifest.xml에서 단서 찾기
- REV-0251 — apktool 기본 사용법
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0249 — JADX로 APK 분석 시작

## 출처/검증
- `adb` 명령어 전체 목록과 옵션은 Android 공식 개발자 문서(developer.android.com, "Android Debug Bridge (adb)")를 기준으로 정리했다.
- `run-as`의 debuggable 요건은 Android 공식 문서(Application manifest, `android:debuggable` 속성 설명) 및 AOSP `run-as` 도구 소스 기준.
- 위 로그/설정 예제는 CTF 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다(2026-09-08 확인).
