---
id: REV-0984
title: "APK 재서명 후 설치가 실패할 때"
slug: "rev-0984-apk-resign-install-fails"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [apktool]
keywords: ["INSTALL_PARSE_FAILED_NO_CERTIFICATES", "INSTALL_FAILED_UPDATE_INCOMPATIBLE", "apksigner", "APK 서명 실패", "APK 설치 오류"]
aliases: ["APK 재서명 설치 안됨", "apksigner 오류", "APK 서명 불일치", "재조립 APK 설치 실패"]
symptom_keywords: ["INSTALL_PARSE_FAILED_NO_CERTIFICATES 오류", "INSTALL_FAILED_UPDATE_INCOMPATIBLE 오류", "signature 관련 오류로 설치 실패", "재서명한 APK가 설치가 안됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
apktool로 수정하고 재조립한 APK가 설치되지 않는다면, 재조립된 APK에 아예 서명이 없거나(`INSTALL_PARSE_FAILED_NO_CERTIFICATES`), 기존에 설치된 앱과 서명이 달라서 업데이트 설치가 거부되거나(`INSTALL_FAILED_UPDATE_INCOMPATIBLE`), APK 정렬(zipalign) 문제 중 하나가 원인이다.

## 언제 검색해야 하나
- `adb install rebuilt.apk`를 실행했더니 `INSTALL_PARSE_FAILED_NO_CERTIFICATES`가 뜰 때
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE` 또는 서명 관련 문구가 뜰 때
- 재조립한 APK가 설치는 되는데 실행 시 이상 동작을 할 때
- 원본 앱이 이미 기기에 설치돼 있는 상태에서 수정판을 새로 설치하려 할 때

## 핵심 개념
안드로이드는 모든 APK가 디지털 서명되어 있어야만 설치를 허용한다. apktool의 `apktool b`(build)는 리소스와 코드를 다시 패키징만 할 뿐, 서명은 별도로 해줘야 하는 작업이다. 서명 없이 그냥 설치하려 하면 시스템이 인증서 자체가 없다는 이유로 설치를 거부한다.

또한 안드로이드는 같은 패키지명(`applicationId`)을 가진 앱을 업데이트 설치할 때, 새 APK의 서명이 기존에 설치된 앱의 서명과 일치해야만 허용한다. apktool로 코드를 수정한 APK를 디버그 키로 새로 서명하면, 이 서명이 원본 앱(원래 개발사의 서명 키)과 다르기 때문에 기존 앱이 설치되어 있는 상태에서는 "업데이트 불가"로 거부된다. 이때는 먼저 기존 앱을 완전히 제거해야 한다.

마지막으로 일부 안드로이드 버전/설정은 APK 내부 파일들이 4바이트 경계에 정렬(zipalign)되어 있어야 최적의 상태로 설치/실행되며, 정렬되지 않은 APK는 경고나 설치 실패로 이어질 수 있다.

## 화면/코드에서 보이는 징후
- `adb install`이 `Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES]`를 출력한다.
- `adb install -r`이 `Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: ... signatures do not match]`를 출력한다.
- `apksigner verify`가 서명 검증 실패를 보고한다.

## 가장 먼저 할 것
`apksigner sign` 명령을 실행했는지, 그 결과물을 설치하려는 것인지부터 확인한다. 재조립 직후(`apktool b`) 파일을 서명 없이 바로 설치하려 한 것이 가장 흔한 원인이다.

## 단계별 절차
1. `apktool b out -o rebuilt.apk`로 재조립된 파일이 있는지 확인한다.
2. 디버그 키스토어(없다면 `keytool`로 새로 생성)를 이용해 `apksigner sign --ks debug.keystore rebuilt.apk`로 서명한다.
3. `apksigner verify rebuilt.apk`로 서명이 정상 적용됐는지 확인한다.
4. 기존에 같은 패키지명의 앱이 설치돼 있다면 `adb uninstall <패키지명>`으로 완전히 제거한다.
5. `adb install rebuilt.apk`(재설치가 아니라 새로 설치)로 설치한다.
6. 여전히 실패하면 `zipalign`을 먼저 적용한 뒤 서명하는 순서(정렬 → 서명, apksigner v2/v3 서명 방식 기준)를 확인한다.

## 명령어/단축키
```bash
apktool b out -o rebuilt.apk                                   # 재조립
zipalign -v -p 4 rebuilt.apk aligned.apk                        # 정렬(서명 전, 도구/버전에 따라 순서 상이할 수 있음)
apksigner sign --ks debug.keystore --ks-pass pass:android aligned.apk
apksigner verify aligned.apk                                    # 서명 검증
adb uninstall com.example.app                                    # 기존 앱 제거(서명 불일치 대비)
adb install aligned.apk                                           # 새로 설치
```

## 출력 해석
- `INSTALL_PARSE_FAILED_NO_CERTIFICATES`는 인증서(서명) 자체가 없다는 뜻 — 서명 단계를 빠뜨렸다는 신호다.
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE ... signatures do not match`는 기존 설치본과 서명이 다르다는 뜻 — 기존 앱을 지우고 새로 설치해야 한다.
- `apksigner verify` 성공 메시지가 뜨면 서명 자체는 유효하다는 뜻이므로, 설치 실패의 원인은 서명 불일치(기존 앱 존재) 쪽으로 좁혀진다.

## 흔한 실수
- `apktool b` 직후 서명 없이 바로 설치를 시도하는 것.
- 기존 원본 앱을 지우지 않고 `adb install -r`(업데이트 설치)로 덮어쓰려는 것 — 서명이 다르면 반드시 실패한다.
- 서명은 했는데 정렬(zipalign) 순서를 헷갈려서 서명이 깨지는 것 — apksigner 서명 방식에 따라 정렬을 서명 전에 해야 하는지 확인해야 한다.
- 디버그 키스토어의 비밀번호(`android`가 기본값인 경우가 많음)를 잘못 입력해 서명 자체가 실패하는 것을 설치 문제로 착각하는 것.

## 막혔을 때 다음 체크
- 애초에 재조립 자체가 실패한다면 → REV-0981 smali 코드를 수정 후 재빌드가 실패할 때
- adb 설치 명령 자체가 헷갈리면 → REV-0255 adb 기본 명령 치트시트
- 기기 연결이 안 되는 상태라면 → REV-0982 adb 기기 연결이 안 될 때(device not found)

## 미니 예제
`apktool b out -o rebuilt.apk`로 수정된 APK를 만든 뒤 곧바로 `adb install rebuilt.apk`를 실행했더니 `Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES]`가 떴다. `apksigner sign --ks debug.keystore --ks-pass pass:android rebuilt.apk`로 서명한 뒤 다시 설치하니, 이번에는 원본 앱이 이미 설치돼 있어 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`이 떴다. `adb uninstall com.example.ctf`로 기존 앱을 지운 뒤 `adb install rebuilt.apk`를 실행하니 정상적으로 설치되었다.

## 관련 글
- REV-0981 — smali 코드를 수정 후 재빌드가 실패할 때
- REV-0251 — apktool 기본 사용법
- REV-0255 — adb 기본 명령 치트시트

## 출처/검증
- APK 서명 요구사항 및 `INSTALL_PARSE_FAILED_NO_CERTIFICATES`/`INSTALL_FAILED_UPDATE_INCOMPATIBLE` 오류 코드: Android 공식 개발자 문서("Sign your app", `PackageManager` 설치 실패 코드) 기준으로 정리했다(2026-09-09 확인).
- `apksigner`/`zipalign` 사용 절차: Android 공식 빌드 도구 문서 기준.
