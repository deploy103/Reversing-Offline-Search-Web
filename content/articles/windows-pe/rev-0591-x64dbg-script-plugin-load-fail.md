---
id: REV-0591
title: "x64dbg 스크립트/플러그인 로드 실패할 때"
slug: "rev-0591-x64dbg-script-plugin-load-fail"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg plugin", "plugins 폴더", "x32dbg x64dbg 비트 불일치", "ScyllaHide", "x64dbg script engine", "Log 탭"]
aliases: ["x64dbg 플러그인이 안뜸", "x64dbg 스크립트 오류", "플러그인 목록에 안보임"]
symptom_keywords: ["x64dbg에 플러그인을 넣었는데 메뉴에 안 나온다", "Plugins 메뉴가 비어있다", "x64dbg 스크립트 실행하면 invalid command 오류가 난다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
x64dbg의 `plugins` 폴더에 DLL을 넣었는데 `Plugins` 메뉴에 안 나타나는 가장 흔한 원인은 **플러그인 비트(32비트/64비트)가 실행 중인 디버거(x32dbg/x64dbg)와 안 맞기 때문**이고, 스크립트 실행이 줄 단위로 실패한다면 x64dbg 자체 Script 엔진 문법과 다른 도구(OllyDbg 등)의 스크립트 문법을 혼동한 경우가 많으므로 하단 `Log`/`Script` 탭의 오류 줄 번호부터 확인해야 한다.

## 언제 검색해야 하나
- 플러그인 DLL을 `plugins` 폴더에 복사했는데 x64dbg를 재시작해도 `Plugins` 메뉴에 아무것도 안 뜰 때
- ScyllaHide 같은 안티안티디버깅 플러그인을 설치했는데 동작하지 않을 때
- `.txt` 스크립트를 x64dbg의 Script 탭에서 실행했는데 특정 줄에서 "invalid command" 류의 오류가 날 때
- x96dbg/OllyDbg용으로 작성된 스크립트를 x64dbg에서 그대로 돌리려다 실패할 때

## 핵심 개념
x64dbg는 실질적으로 두 개의 실행 파일로 배포된다. 32비트 대상을 디버깅하는 `x32dbg.exe`와 64비트 대상을 디버깅하는 `x64dbg.exe`이며, 각각 별도의 `release\x32\plugins`, `release\x64\plugins` 폴더를 갖는다. 플러그인은 x64dbg SDK를 이용해 빌드된 DLL인데, **DLL 자체의 비트가 그 폴더에 대응하는 디버거의 비트와 정확히 일치해야** 로드된다. 32비트 플러그인 DLL을 `x64\plugins`에 넣거나 그 반대로 넣으면, 로더가 DLL을 매핑하는 단계에서 이미 실패하므로 메뉴에 아무 흔적도 안 남고 조용히 무시되거나 Log에 짧은 오류만 남는다.

또한 x64dbg 플러그인은 `pluginit`, `plugstop`, `plugsetup` 같은 정해진 익스포트 함수를 가진 DLL이어야 하며, x64dbg SDK 버전이 크게 다르면(오래된 플러그인 vs 최신 x64dbg) 초기화 과정에서 실패할 수 있다.

한편 x64dbg에는 자체 내장 **Script 엔진**이 있어서(`Script` 탭), `.txt` 형식의 스크립트를 한 줄씩 명령으로 실행할 수 있다. 이 스크립트 문법은 x64dbg 고유의 명령어 집합(`bp`, `run`, `cmp`, `jmp label` 등)을 따르는데, OllyDbg의 ODbgScript 플러그인 문법이나 다른 디버거의 스크립트 문법과는 다르다. 인터넷에서 구한 "OllyDbg 스크립트"를 x64dbg Script 탭에 그대로 붙여넣으면 명령어 이름이 안 맞아 특정 줄에서 파싱 오류가 난다.

## 화면/코드에서 보이는 징후
- `plugins` 폴더에 DLL을 넣고 재시작했는데도 상단 `Plugins` 메뉴 항목 자체가 안 생김
- 하단 `Log` 탭에 플러그인 로드 관련 오류/경고 메시지가 짧게 남거나 아예 아무 언급도 없음
- Script 탭에서 스크립트를 실행(▶ 버튼 또는 `Run`)했는데 특정 줄 번호에서 실행이 멈추고 오류로 표시됨
- 플러그인 폴더 안 DLL 파일 속성에서 확인한 아키텍처(32비트/64비트)가 현재 실행 중인 `x32dbg.exe`/`x64dbg.exe`와 다름

## 가장 먼저 할 것
문제가 플러그인이면 DLL의 비트와 폴더가 맞는지부터 확인한다. 문제가 스크립트면 오류가 난 줄 번호를 Log/Script 탭에서 먼저 확인하고, 그 줄이 x64dbg 고유 명령어 문법을 따르는지 대조한다.

## 단계별 절차
**1) 플러그인 비트 확인 및 올바른 폴더 배치**
- 플러그인 DLL을 우클릭 → 속성, 또는 PE-bear/CFF Explorer로 열어 `Machine` 필드가 `IMAGE_FILE_MACHINE_I386`(32비트)인지 `IMAGE_FILE_MACHINE_AMD64`(64비트)인지 확인한다.
- 32비트 DLL은 x64dbg 설치 폴더의 `x32\plugins`(또는 배포판에 따라 `release\x32\plugins`), 64비트 DLL은 `x64\plugins`에 넣는다.
- x64dbg를 완전히 종료했다가 다시 실행한다(플러그인은 시작 시에만 스캔한다).

**2) 플러그인 로드 로그 확인**
- 하단 `Log` 탭에서 시작 직후 로그를 위로 스크롤해 플러그인 관련 줄을 찾는다. 로드에 성공한 플러그인은 이름과 버전이, 실패한 플러그인은 오류 메시지가 남는 경우가 많다.
- `Plugins → Plugin Manager`(버전에 따라 명칭이 다를 수 있음)가 있다면 여기서 로드된/실패한 플러그인 목록을 한눈에 볼 수 있다.

**3) 스크립트 오류 진단**
- Script 탭에서 오류가 난 줄 번호를 확인한다.
- 해당 줄의 명령어가 x64dbg 공식 명령어 목록(`bp`, `bpc`, `run`, `StepInto`, `cmp`, `jmp`, `ret` 등 Script 전용 명령)에 있는 것인지 확인한다.
- 다른 디버거용 스크립트를 이식하는 중이라면, ODbgScript 문법이 아니라 x64dbg 자체 문법으로 다시 작성하거나, ODbgScript 호환 플러그인이 별도로 필요한지 확인한다.

**4) SDK/버전 불일치 의심 시**
- 오래된 플러그인이 최신 x64dbg에서 실패한다면, 그 플러그인의 배포 페이지에서 최신 빌드나 x64dbg 버전 호환 정보를 확인한다. 자체 컴파일이 가능하다면 최신 x64dbg SDK로 재빌드한다.

## 명령어/단축키
```text
x64dbg: 플러그인 폴더 - release\x32\plugins (x32dbg용) / release\x64\plugins (x64dbg용)
x64dbg: 하단 Log 탭에서 시작 시 플러그인 로드 메시지 확인
x64dbg: Script 탭 - 스크립트 로드/실행, 오류 시 해당 줄 강조 표시
```

## 출력 해석
- Log에 플러그인 이름과 버전이 정상적으로 찍히면 로드에 성공한 것이고, `Plugins` 메뉴에서 해당 항목을 찾을 수 있어야 한다.
- 아무 로그도 없이 조용히 무시된 경우 비트 불일치일 가능성이 가장 높다 — DLL이 애초에 로드 시도조차 안 됐다는 뜻이다.
- Script 오류가 특정 줄 번호와 함께 뜨면 그 줄의 명령어 철자나 인자 개수부터 의심한다.

## 흔한 실수
- x32dbg와 x64dbg의 plugins 폴더가 서로 다르다는 것을 모르고 한쪽에만 넣어두는 것.
- 32비트 대상을 분석 중인데 실수로 `x64dbg.exe`를 실행해서 플러그인은 물론 파일 자체도 제대로 안 열리는 것(파일을 열려면 대상 아키텍처에 맞는 디버거를 써야 한다).
- ScyllaHide 같은 플러그인을 설치만 하고 실제로 활성화(플러그인 메뉴에서 옵션 체크)하지 않은 채 "설치했는데 안 먹는다"고 오해하는 것.
- 다른 디버거의 스크립트 문법을 그대로 복사해서 x64dbg Script 탭에 붙여넣고 문법 오류를 스크립트 자체의 버그로 착각하는 것.

## 막혔을 때 다음 체크
- 애초에 x64dbg가 파일을 아예 못 여는 상황이라면 → REV-0582(x64dbg가 실행 파일을 로드하지 못할 때)를 먼저 확인한다.
- 안티디버깅 우회 목적으로 ScyllaHide를 쓰려는 것이었다면 → REV-0583(x64dbg로 붙였는데 바로 종료(anti-attach)될 때)과 함께 본다.
- 32/64비트 자체가 헷갈리는 상황이라면 → REV-0596(32비트 바이너리를 64비트 도구로 열어서 이상해질 때)을 참고한다.

## 미니 예제
64비트 대상을 분석하려고 ScyllaHide 플러그인 DLL을 받았는데, 실수로 `release\x32\plugins` 폴더에 넣고 `x64dbg.exe`를 실행했다고 하자. `Plugins` 메뉴에 ScyllaHide 항목이 전혀 안 보인다. 파일 속성을 확인해보니 해당 DLL은 32비트(`x86`) 빌드였다. 올바른 64비트 빌드 DLL을 받아 `release\x64\plugins`에 넣고 x64dbg를 재시작하자 `Plugins → ScyllaHide` 메뉴가 정상적으로 나타났다.

## 관련 글
- REV-0582 — x64dbg가 실행 파일을 로드하지 못할 때
- REV-0583 — x64dbg로 붙였는데 바로 종료(anti-attach)될 때
- REV-0596 — 32비트 바이너리를 64비트 도구로 열어서 이상해질 때
- REV-0127 — x64dbg로 EXE 첫 분석 시작

## 출처/검증
- x64dbg 플러그인 시스템(x32/x64 분리 폴더, 필수 익스포트 함수)은 x64dbg 공식 GitHub 문서(plugin SDK) 기준.
- Script 엔진 문법과 ODbgScript의 차이는 x64dbg 공식 문서 및 커뮤니티 위키 기준이며, 정확한 메뉴 문구/명칭은 버전에 따라 다를 수 있어 실습 시 실제 화면을 우선한다(2026-09-08 기준 서술).
