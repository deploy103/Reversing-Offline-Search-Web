---
id: REV-0979
title: "APK가 apktool로 디코드가 안 될 때"
slug: "rev-0979-apktool-decode-fails"
category: "dotnet-android"
difficulty: "basic"
platform: [linux, windows]
architecture: [ARM, ARM64]
format: [APK]
tools: [apktool]
keywords: ["apktool d 실패", "AndrolibException", "framework-res.apk 못 찾음", "apktool 버전 오류", "apktool 디코딩 오류"]
aliases: ["apktool decode 실패", "apktool d 오류", "apktool 리소스 디코딩 오류", "apktool empty-framework-dir"]
symptom_keywords: ["apktool d 명령이 실패함", "AndrolibException이 뜸", "framework-res.apk를 못 찾는다는 오류", "apktool이 특정 리소스에서 멈춤"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`apktool d`가 실패하는 원인은 대부분 apktool 버전이 대상 APK를 빌드한 최신 안드로이드 SDK/리소스 포맷을 아직 지원하지 못하거나, 제조사 커스텀 프레임워크 리소스(`framework-res.apk`)를 못 찾거나, 이전 실행에서 남은 프레임워크 캐시가 손상됐기 때문이며, 셋 다 apktool 자체의 버그가 아니라 환경/버전 문제인 경우가 대부분이다.

## 언제 검색해야 하나
- `apktool d app.apk -o out`을 실행했는데 `brut.androlib.exceptions.AndrolibException` 계열 예외로 멈출 때
- `framework-res.apk`나 특정 리소스 ID를 못 찾는다는 오류 메시지가 뜰 때
- 디코딩은 끝났는데 특정 XML 리소스가 깨지거나 경고가 잔뜩 뜰 때
- apktool을 최근에 새로 설치했는데 예전에 잘 되던 APK도 실패할 때

## 핵심 개념
apktool은 APK 안의 바이너리 XML(AXML)과 압축 리소스(`resources.arsc`)를 텍스트로 복원하기 위해 안드로이드 프레임워크의 리소스 ID 매핑 정보(`framework-res.apk`)를 참조한다. 최신 안드로이드 버전이 새로 도입한 리소스 타입이나 속성을 구버전 apktool이 아직 모르면 디코딩 도중 예외가 난다. 또한 삼성/샤오미 등 제조사 전용 앱은 표준 안드로이드 프레임워크가 아니라 제조사 전용 프레임워크 리소스를 참조하는 경우가 있어, 이 프레임워크를 별도로 설치(`apktool if framework.apk`)해주지 않으면 리소스 ID를 못 찾는다. 마지막으로, 한 번 실패한 디코딩 시도가 `~/.local/share/apktool/framework` (또는 OS별 캐시 경로)에 불완전한 프레임워크 캐시를 남기면, 이후 정상적인 재시도도 같은 캐시 손상 때문에 계속 실패할 수 있다.

## 화면/코드에서 보이는 징후
- `brut.androlib.exceptions.AndrolibException: Can't find framework resources for package of id: 2`처럼 패키지 ID를 못 찾는다는 메시지.
- `W: ... Cannot find resource...` 경고가 대량으로 출력된다.
- `apktool`이 특정 파일 처리 중 스택트레이스와 함께 갑자기 종료된다.
- 같은 APK를 다른 apktool 버전에서 실행하면 성공하는 경우가 있다.

## 가장 먼저 할 것
`apktool --version`으로 현재 버전을 확인하고, apktool 공식 GitHub 릴리스 페이지에서 최신 버전이 있는지 대조한다. 대부분의 최신 안드로이드 리소스 포맷 관련 실패는 apktool을 최신 버전으로 교체하는 것만으로 해결된다.

## 단계별 절차
1. `apktool --version`으로 현재 버전을 확인한다.
2. 최신 버전(공식 GitHub `iBotPeaches/Apktool` 릴리스)으로 교체해서 다시 시도한다.
3. 여전히 실패하면 `apktool empty-framework-dir --force`로 손상됐을 수 있는 프레임워크 캐시를 비운 뒤 다시 시도한다.
4. 제조사 커스텀 앱이 의심되면(대상 기기에 특정 제조사 프레임워크 APK가 있는 경우), 해당 프레임워크를 `apktool if <framework.apk>`로 먼저 설치한 뒤 다시 디코딩한다.
5. 리소스 디코딩 자체가 필요 없고 smali 코드만 급하게 봐야 한다면, 임시로 `-r`(리소스 디코딩 생략) 옵션을 붙여 우회할 수 있다.
6. 그래도 안 되면 문제되는 리소스 파일을 특정해서(로그의 파일 경로) 그 리소스만 건너뛸 방법이 있는지 apktool 이슈 트래커에서 유사 사례를 찾아본다.

## 명령어/단축키
```bash
apktool --version                       # 버전 확인
apktool d app.apk -o out                # 디코딩
apktool d app.apk -o out -r             # 리소스 디코딩 생략, smali만
apktool empty-framework-dir --force      # 프레임워크 캐시 초기화
apktool if custom-framework.apk          # 커스텀 프레임워크 설치
apktool d app.apk -o out -f              # 기존 폴더 덮어쓰고 재시도
```

## 출력 해석
- `Can't find framework resources for package of id: 2`는 표준 안드로이드 프레임워크(ID 1)가 아니라 다른 패키지 ID(보통 제조사 커스텀 프레임워크)를 참조한다는 뜻이다 — 해당 프레임워크를 `apktool if`로 설치해야 한다.
- `Cannot find resource` 경고만 있고 최종적으로 디코딩이 완료됐다면, 대부분 사소한 리소스 참조 누락으로 무시 가능하지만 재조립 후 크래시가 나면 이 경고 근처를 다시 봐야 한다.
- 버전 교체 후 같은 APK가 성공하면, 원인이 확실히 apktool의 리소스 포맷 지원 범위였다는 뜻이다.

## 흔한 실수
- 오래된 apktool 버전을 계속 쓰면서 "이 APK가 특별히 이상한가보다"라고 오해하는 것 — 대부분 버전 업데이트로 해결된다.
- `empty-framework-dir` 없이 캐시가 손상된 상태로 계속 재시도하는 것.
- 제조사 커스텀 프레임워크가 필요한 상황인지 모른 채 계속 표준 apktool만으로 씨름하는 것.
- 리소스 디코딩 오류가 무서워서 `-r` 옵션을 영구적으로 습관화하는 것 — 리소스 XML(특히 문자열 힌트)이 실제로 필요할 수 있으므로 임시 우회로만 써야 한다.

## 막혔을 때 다음 체크
- smali 문법 자체를 모르겠다면 → REV-0252 smali 기초 문법
- 재빌드 단계에서 오류가 나면 → REV-0981 smali 코드를 수정 후 재빌드가 실패할 때
- JADX로 먼저 코드만 훑어보고 싶다면 → REV-0980 JADX 디컴파일 결과가 깨질 때

## 미니 예제
최신 안드로이드 버전으로 빌드된 `newapp.apk`를 오래된 apktool 2.4.x로 열었더니 `AndrolibException: Multiple resources: type=... name=... config=...` 오류가 났다. `apktool --version`으로 확인해보니 2.4.1이었고, GitHub 릴리스 페이지에서 2.9.x 최신 버전을 받아 교체한 뒤 같은 명령을 다시 실행하자 정상적으로 `out/` 폴더가 생성되며 `smali/`, `res/`가 모두 정상 디코딩됐다.

## 관련 글
- REV-0251 — apktool 기본 사용법
- REV-0981 — smali 코드를 수정 후 재빌드가 실패할 때
- REV-0980 — JADX 디컴파일 결과가 깨질 때
- REV-0252 — smali 기초 문법

## 출처/검증
- apktool의 프레임워크 리소스 매핑 및 `empty-framework-dir`, `if` 명령: apktool 공식 저장소(`iBotPeaches/Apktool`, GitHub) 문서 및 이슈 트래커 사례 기준으로 정리했다(2026-09-09 확인).
- 안드로이드 리소스 포맷이 SDK 버전에 따라 확장된다는 사실은 Android 공식 개발자 문서의 리소스 시스템 설명과 일치한다.
