---
id: REV-0810
title: "x64dbg 플러그인 목록과 용도 빠른 참조"
slug: "rev-0810-x64dbg-plugin-list-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg plugin", "ScyllaHide", "TitanHide", "xAnalyzer", "x64dbg 플러그인 설치", "x64dbg 플러그인 목록"]
aliases: ["x64dbg 플러그인 추천", "x64dbg 안티안티디버깅 플러그인", "x64dbg 분석 보조 플러그인"]
symptom_keywords: ["x64dbg 플러그인이 뭐가 있는지 모름", "x64dbg 안티디버깅 우회 플러그인 필요함", "x64dbg 함수 분석 플러그인 찾음", "x64dbg 플러그인 폴더 어디인지 모름", "x64dbg 플러그인 로드 안됨"]
source_ids: ["SRC-X64DBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg는 `.dp32`/`.dp64` 확장자의 DLL 플러그인을 `release/x32(x64)/plugins` 폴더에 넣으면 자동으로 불러오는 구조이며, 안티-안티-디버깅(ScyllaHide/TitanHide), 함수 분석 보조(xAnalyzer), 유틸리티(SwissArmyKnife) 등 목적별로 널리 쓰이는 플러그인이 정리되어 있다.

## 언제 검색해야 하나
- 패커/보호 프로그램이 디버거를 탐지해서 x64dbg가 붙자마자 종료될 때 어떤 플러그인으로 우회하는지 찾을 때
- 함수 호출 인자/문자열 참조를 x64dbg가 자동으로 더 잘 분석해줬으면 할 때
- 새 플러그인을 받았는데 어느 폴더에 넣어야 하는지, 왜 로드가 안 되는지 확인할 때
- 커널 레벨까지 디버거 흔적을 숨겨야 하는 고급 상황에서 어떤 도구가 필요한지 알고 싶을 때

## 핵심 개념

### 목적별 대표 플러그인
| 플러그인 | 목적 | 동작 방식 |
|---|---|---|
| ScyllaHide | 안티-안티-디버깅(유저 모드) | `IsDebuggerPresent`, `CheckRemoteDebuggerPresent` 등 안티디버깅에 쓰이는 Windows API들을 후킹해서 디버거가 없는 것처럼 응답을 조작 |
| TitanHide | 안티-안티-디버깅(커널 모드) | 드라이버를 통해 커널 레벨에서 디버거 흔적을 숨김. 유저 모드 후킹만으로 안 되는 강한 보호에 사용 |
| xAnalyzer | 함수 호출/분석 보조 | x64dbg 내부 명령을 호출해 인자 추정, 문자열/함수 참조 등 부가 분석 정보를 자동으로 덧붙임(OllyDbg의 analysis 기능과 유사) |
| SwissArmyKnife | 유틸리티 | 링커 맵 파일 로드, 파일 diff, PEiD/IDA 시그니처 활용, 코드 시그니처 생성 등 여러 잡다한 기능 모음 |
| HighlightFish | 화면 커스터마이징 | 레지스터/코드 강조 색상 등 UI 하이라이트를 원하는 대로 바꿈 |
| Multiline Ultimate Assembler | 어셈블/디스어셈블 보조 | 여러 줄짜리 어셈블리 코드를 한 번에 어셈블(패치)하거나 디스어셈블 |
| xHotSpots | 이벤트 지점 관찰 | 특정 이벤트(예: 예외, 특정 API 호출)가 발생하는 지점을 미리 계산해 접근 가능하게 함(예전 MagicPoints의 후속) |

### 코어 라이브러리 vs 플러그인의 차이
TitanEngine, Zydis, Yara, Scylla, asmjit, snowman 같은 이름은 x64dbg 자체가 내부적으로 쓰는 **코어 라이브러리**이지 사용자가 따로 설치하는 플러그인이 아니다. 반면 ScyllaHide나 xAnalyzer는 x64dbg의 플러그인 API에 맞춰 만들어진 별도 DLL로, 사용자가 직접 다운로드해서 넣어야 한다.

### 설치 위치와 확장자
플러그인은 x64dbg 실행 파일이 있는 폴더 아래 `plugins` 폴더에 넣는다.
```text
release\x32\plugins\   # 32비트(x32dbg)용, 확장자 .dp32
release\x64\plugins\   # 64비트(x64dbg)용, 확장자 .dp64
```
32비트/64비트는 서로 다른 빌드이므로, 32비트 대상 바이너리를 분석할 때는 x32dbg용 플러그인 파일을, 64비트 대상일 때는 x64dbg용 플러그인 파일을 넣어야 한다.

## 화면/코드에서 보이는 징후
플러그인이 정상적으로 로드되면 x64dbg 메뉴바에 플러그인 전용 메뉴 항목(예: ScyllaHide는 `Plugins → ScyllaHide`)이 새로 생기고, 로그(Log 탭)에 해당 플러그인의 초기화 메시지가 출력된다. 로드에 실패하면 Log 탭에 오류 메시지가 남고 메뉴 항목도 나타나지 않는다.

## 가장 먼저 할 것
지금 겪는 문제가 "디버거가 탐지당해서 프로그램이 종료/이상 동작"이면 ScyllaHide부터, "분석 정보가 부족해서 코드 읽기가 힘들다"면 xAnalyzer부터 설치를 검토한다.

## 단계별 절차

**1) 아키텍처 확인**
분석 대상 PE가 32비트인지 64비트인지 확인한다(REV-0182 Memory Map/모듈 정보 또는 PE 헤더로 확인 가능).

**2) 맞는 플러그인 파일 받기**
공식 저장소(GitHub `x64dbg/ScyllaHide` 등)에서 대상 아키텍처에 맞는 `.dp32`/`.dp64` 파일을 받는다.

**3) plugins 폴더에 배치**
```text
x64dbg 설치 폴더\release\x64\plugins\ScyllaHide.dp64
```

**4) x64dbg 재시작**
플러그인은 시작 시 자동으로 로드되므로, 이미 실행 중이었다면 x64dbg를 재시작한다.

**5) 메뉴에서 로드 확인**
`Plugins` 메뉴에 해당 플러그인 항목이 보이면 정상 로드된 것이다.

**6) 안티디버깅 우회가 목적이면 ScyllaHide 설정 켜기**
`Plugins → ScyllaHide → Options`에서 우회하고 싶은 탐지 기법(예: PEB.BeingDebugged, NtQueryInformationProcess 등)에 체크한 뒤 디버깅 세션을 다시 시작한다.

## 명령어/단축키
```text
plugins 폴더 위치        : <x64dbg 폴더>\release\x32(또는 x64)\plugins\
32비트 확장자            : .dp32
64비트 확장자            : .dp64
Plugins 메뉴             : 로드된 플러그인의 UI 진입점
Log 탭                   : 플러그인 로드 성공/실패 메시지 확인
```

## 출력 해석
Log 탭에 `[PluginName] Loaded plugin`류의 메시지가 보이면 정상 로드다. 반대로 `Could not load plugin`, 아키텍처 불일치, DLL 의존성 누락 관련 오류가 보이면 해당 플러그인 파일이 지금 실행 중인 비트수(x32/x64)와 맞는지부터 확인해야 한다.

## 흔한 실수
- 64비트용 `.dp64` 플러그인을 32비트 x32dbg의 plugins 폴더에 넣거나 그 반대로 넣어서 조용히 로드가 안 되는 것.
- 코어 라이브러리(TitanEngine, Zydis 등)를 "플러그인"으로 착각해서 별도로 설치하려는 것 — 이들은 x64dbg 본체에 이미 포함되어 있다.
- ScyllaHide를 넣기만 하고 옵션에서 실제 우회 기법을 켜지 않아 "설치했는데도 여전히 탐지당한다"고 헷갈리는 것.
- 플러그인 로드 실패 원인을 확인하지 않고 무작정 재설치만 반복하는 것 — Log 탭 오류 메시지를 먼저 확인해야 원인(비트수 불일치, DLL 누락 등)을 알 수 있다.

## 막혔을 때 다음 체크
- ScyllaHide로도 해결 안 되는 강한 안티디버깅 우회가 필요하면 커널 모드 도구(TitanHide) 사용을 검토한다.
- x64dbg 자체의 기본 기능(브레이크포인트/조건식)부터 다시 확인하고 싶다면 → REV-0178 x64dbg Breakpoint 설정과 삭제, REV-0806 x64dbg 표현식(Expression) 문법 빠른 참조.
- 스크립트/플러그인이 아예 로드조차 안 되는 구체적인 실패 사례는 → REV-0591 x64dbg 스크립트/플러그인 로드 실패할 때.

## 미니 예제
```text
상황: 대상 프로그램이 x64dbg로 붙이자마자 즉시 종료됨(안티디버깅 의심)

1. ScyllaHide.dp64를 release\x64\plugins\에 배치 후 x64dbg 재시작
2. Plugins → ScyllaHide → Options에서 기본 항목 전부 체크
3. 다시 File → Open으로 대상 실행
4. 더 이상 즉시 종료되지 않으면 우회 성공, 여전히 종료되면 어떤 탐지 기법인지 추가로 조사 필요
```

## 관련 글
- REV-0591 — x64dbg 스크립트/플러그인 로드 실패할 때
- REV-0806 — x64dbg 표현식(Expression) 문법 빠른 참조
- REV-0178 — x64dbg Breakpoint 설정과 삭제
- REV-0182 — x64dbg Memory Map과 Module View

## 출처/검증
- ScyllaHide의 유저 모드 API 후킹 기반 안티-안티-디버깅 동작과 TitanEngine/x64dbg 플러그인 아키텍처 구조: x64dbg/ScyllaHide 공식 GitHub 저장소 및 문서 기준.
- TitanHide의 커널 모드 안티-안티-디버깅 방식, xAnalyzer/SwissArmyKnife/HighlightFish/Multiline Ultimate Assembler/xHotSpots의 기능 설명: x64dbg 공식 Plugins 위키 페이지(github.com/x64dbg/x64dbg/wiki/Plugins) 기준.
- 플러그인 폴더 경로(`release/x32|x64/plugins`)와 확장자(`.dp32`/`.dp64`) 규칙: x64dbg 공식 문서 Plugins 관련 페이지 기준 (2026-09-09 조사).
