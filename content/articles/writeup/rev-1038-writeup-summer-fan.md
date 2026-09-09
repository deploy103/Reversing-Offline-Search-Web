---
id: REV-1038
title: "[Write-up] Summer Fan"
slug: "rev-1038-writeup-summer-fan"
category: "writeup"
difficulty: "basic"
platform: [windows, android]
architecture: [x64, arm]
format: [PE, APK]
tools: [IDA, JADX, x64dbg]
keywords: ["dreamhack Summer Fan", "드림핵 Summer Fan", "Summer Fan 리버싱"]
aliases: ["Summer Fan 풀이", "Summer Fan 못풀겠음"]
symptom_keywords: ["드림핵 Summer Fan 어떻게 풀어야 할지 모르겠음", "Summer Fan 타이머가 0에서 멈춰있음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
"Summer Fan"(Bronze 3)이라는 이름과 완전히 같은 write-up 하나가 검색되긴 했지만, 그 글은 드림핵 워게임이 아니라 "BOB 정보보안 CTF(BISC)"라는 별도 대회의 안드로이드 앱 리버싱 문제를 다루고 있어 동일 문제인지 확정할 수 없다. 다만 시간(time) 관련 조건으로 플래그를 생성하는 패턴이 이름("Summer Fan"이 여름/시간과 연관된 소재)과 자연스럽게 맞물리므로, 시스템 시간 또는 카운터 조건을 검사해 특정 조건에서만 플래그를 만들어내는 문제로 추정해볼 수 있다.

## 언제 검색해야 하나
- "Summer Fan"을 검색했는데 나오는 write-up이 안드로이드 앱(APK) 분석 글이라 드림핵 워게임 문제와 형태가 다른 것 같아 혼란스러울 때
- 프로그램을 실행했더니 타이머나 시간 표시가 있고 그 값이 특정 조건에 도달해야 무언가가 일어나는 것처럼 보일 때
- Windows PE 바이너리라고 생각했는데 첨부 파일이 실제로는 APK이거나 반대의 경우여서 분석 도구 선택부터 헷갈릴 때

## 핵심 개념
WebSearch 결과 velog에 게시된 "[CTF]Mobile_AOS_SUMMER_FAN Writeup"이라는 글이 확인되었다. 이 글은 드림핵이 아니라 "BOB 정보보안 CTF(BISC)"의 리버싱 카테고리 문제를 다루며, 안드로이드 APK 파일이 주어지고 앱을 설치하면 타이머가 0에서 멈춘 화면과 부채(fan) 그림이 표시된다고 설명한다. Jadx로 APK를 열어 `MainActivity`를 분석하면 `generateFlag()`라는 이름의 함수와, 특정 시간 조건이 되면 그 함수를 호출하는 `checkTime()` 함수가 존재한다는 내용이 이 글의 핵심 요지다.

이 글이 다루는 문제가 드림핵 워게임의 "Summer Fan"(Bronze 3)과 완전히 동일한 문제인지, 아니면 이름만 우연히 같은 다른 대회의 별도 문제인지는 이번 조사로는 확정할 수 없었다. 드림핵은 자체 제작 워게임 문제를 여러 대회/플랫폼에 재사용하는 사례가 실제로 있으므로 동일 문제일 가능성도 있지만, 대회 주최 측(BOB/BISC)이 다르다는 점에서 신중하게 접근해야 한다. 이 문서에서는 이 사실을 명확히 구분해 서술하며, 확정된 정답으로 취급하지 않는다.

만약 동일하거나 유사한 구조라면 접근법은 다음과 같이 정리할 수 있다.

- 정적 리버싱 도구(APK라면 Jadx, PE라면 IDA)로 시간/타이머와 관련된 함수를 먼저 찾는다.
- 그 함수가 실제 시스템 시간을 읽는지, 아니면 단순 카운터를 흉내 내는지 구분한다.
- 실제 시간을 요구하는 조건이라면, 기기/환경의 시간을 조작(에뮬레이터 시간 변경, 또는 디버거로 조건 분기 우회)해 플래그 생성 함수에 도달하게 만든다.

## 화면/코드에서 보이는 징후
- 실행/설치 화면에 타이머 또는 시계 UI가 표시되고 값이 0 또는 특정 값에서 멈춰 있는 것처럼 보임
- (APK인 경우) `MainActivity`에 `generateFlag`, `checkTime` 같은 이름의 함수가 존재
- (PE인 경우) `GetLocalTime`, `GetSystemTime`, `time()` 계열 API 호출과 그 결과를 비교하는 조건문이 존재할 가능성

## 가장 먼저 할 것
첨부된 파일이 PE인지 APK인지부터 `file` 또는 확장자로 확인한다. APK라면 Jadx로 열어 `MainActivity`부터 훑고, PE라면 IDA로 시간 관련 API의 import를 먼저 확인한다.

## 단계별 절차
1. 파일 형식 확인(PE vs APK) 후 맞는 도구 선택
2. 시간/타이머 관련 함수 또는 API 호출 지점 탐색
3. 그 값을 비교하는 조건문과, 조건을 만족했을 때 호출되는 함수(플래그 생성/출력) 확인
4. 조건이 실제 시간이라면 시간을 조작하거나 조건 분기를 디버거로 우회, 조건이 단순 카운터라면 그 값을 맞추는 입력 계산
5. 조건 통과 후 생성되는 값을 실제로 출력해 플래그 형식 확인

## 명령어/단축키
```text
JADX: MainActivity.java 더블클릭 → Ctrl+클릭으로 함수 정의 이동
IDA: Alt+T 텍스트 검색으로 "time" 관련 import 이름 검색
x64dbg: 시간 비교 조건 분기 지점에 F2 → 분기 플래그 레지스터를 직접 수정해 우회
```

## 출력 해석
시간 비교 조건이 실기기/에뮬레이터의 현재 시각과 맞물려 있다면, 그 시각을 그대로 기다리는 것보다 시간 자체를 앞당기거나 비교 분기를 반대로 뒤집는 패치가 훨씬 빠르다. 조건이 몇 초 단위의 짧은 타이머라면 그냥 기다리는 것도 방법이 될 수 있다.

## 흔한 실수
- 이름이 같은 다른 대회의 write-up(BISC "Summer Fan")을 드림핵 워게임 문제의 확정된 정답으로 오인하는 것
- APK 문제인데 PE 분석 도구만 준비해서 시간을 낭비하거나, 반대로 PE 문제인데 APK로 착각하는 것
- 시간 조건을 실제로 기다리려다가 현실적으로 도달할 수 없는 조건(예: 몇 달 뒤)이라는 것을 늦게 깨닫는 것

## 막혔을 때 다음 체크
- 같은 입력에도 결과가 실행 시점마다 다르게 느껴진다면 → REV-0331 같은 입력인데 실행마다 다른 결과가 나올 때
- 시드가 시간 기반일 가능성이 있다면 → REV-0894 시간 기반 시드(seed = time())를 역산하는 접근
- APK 분석 도구 사용법이 낯설다면 → REV-0249 JADX로 APK 분석 시작, REV-0248 APK 파일 구조 기초
- PE 쪽에서 시간 API 관련 정적 분석이 필요하면 → REV-0761 Import된 CRT 함수 이름으로 원본 로직 추정하기

## 미니 예제
```java
// BISC의 유사 명명 문제(Summer Fan)에서 확인된 함수 이름 구조를 일반화해 표현(실제 코드 전문 아님)
void checkTime() {
    if (currentTime >= targetTime) {
        generateFlag();
    }
}
```
이 예시는 검색으로 확인한 함수 이름("checkTime", "generateFlag")의 존재만을 반영한 구조적 요약이며, 실제 조건식이나 로직 전문을 그대로 복제한 것이 아니다. 또한 이 구조가 드림핵 워게임의 "Summer Fan"과 완전히 같은지는 확정되지 않았다.

## 관련 글
- REV-0331 — 같은 입력인데 실행마다 다른 결과가 나올 때
- REV-0894 — 시간 기반 시드(seed = time())를 역산하는 접근
- REV-0249 — JADX로 APK 분석 시작
- REV-0248 — APK 파일 구조 기초
- REV-0761 — Import된 CRT 함수 이름으로 원본 로직 추정하기
- REV-1039 — [Write-up] Happy New Year!

## 출처/검증
- WebSearch로 "dreamhack Summer Fan writeup 리버싱"을 검색한 결과 velog.io/@arahan/summerfan 글이 확인되었으며, 이 글은 "BOB 정보보안 CTF(BISC)"의 안드로이드 리버싱 문제를 다룬다(2026-09-10 검증). 드림핵 워게임 "Summer Fan"(Bronze 3)과 동일 문제인지는 이번 조사에서 확정하지 못했다.
- 함수명(`MainActivity`, `checkTime`, `generateFlag`)과 화면 설명(타이머, 부채 그림)은 위 글의 요약 내용을 참고해 재서술했으며, 원문 코드나 문장을 그대로 복제하지 않았다.
- platform/format을 windows/PE와 android/APK 둘 다 표기한 것은 실제 형식이 확인되지 않아 두 가능성을 모두 열어둔 것이다.
