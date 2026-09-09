---
id: REV-0732
title: "IDA에서 나만의 FLIRT 시그니처 만드는 개념"
slug: "rev-0732-ida-flirt-create-custom-signature"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["FLAIR", "pelf", "pcf", "sigmake", ".pat 파일", ".sig 파일 생성", "커스텀 FLIRT 시그니처", "own signature 만들기"]
aliases: ["FLIRT 시그니처 직접 만들기", "sigmake 사용법", "FLAIR 툴킷", "커스텀 sig 파일 제작"]
symptom_keywords: ["내가 쓰는 라이브러리는 기본 sig가 없음", "회사 자체 SDK 정적 라이브러리라 시그니처가 없음", "특이한 버전의 libc라 FLIRT가 하나도 안 맞음", "sigmake collision 메시지가 뜸"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
IDA 기본 제공 `.sig`로 매칭이 안 되는 정적 라이브러리(사내 SDK, 특이한 버전의 libc, 게임 엔진 정적 라이브러리 등)를 다룬다면, Hex-Rays가 별도로 배포하는 **FLAIR(Fast Library Acquisition for Identification and Recognition)** 툴킷의 `pelf`/`pcf`로 라이브러리에서 패턴(`.pat`)을 뽑고 `sigmake`로 그 패턴을 `.sig`로 컴파일해서 직접 시그니처를 만들 수 있다.

## 언제 검색해야 하나
- 분석 대상이 사내/비공개 SDK의 정적 라이브러리(`.lib`/`.a`)를 링크하고 있어서 공개된 FLIRT `.sig`가 존재하지 않을 때
- REV-0731로 기본 제공 `.sig`를 다 시도해봐도 매칭률이 너무 낮을 때
- 같은 회사/같은 팀이 만든 여러 바이너리가 공통 정적 라이브러리를 링크하고 있어서, 한 번 시그니처를 만들어두면 이후 분석에서 계속 재사용하고 싶을 때
- CTF에서 흔치 않은 libc 빌드(특이한 배포판, 커스텀 패치가 들어간 libc)를 정적 링크한 문제를 반복해서 풀어야 할 때

## 핵심 개념

### FLAIR란 무엇인가
FLAIR는 IDA 본체와 별도로 Hex-Rays가 제공하는 커맨드라인 도구 모음으로, IDA 라이선스 계정을 통해 다운로드할 수 있다(도구 자체는 IDA GUI 안에 내장되어 있지 않다). 핵심 실행 파일은 다음과 같다.

- `pelf` / `pelf64`: ELF용 오브젝트 파일(`.o`)이나 정적 라이브러리(`.a`) 안의 함수들을 스캔해서 패턴 파일(`.pat`)을 만든다.
- `pcf`: COFF 오브젝트(Windows `.lib`/`.obj`)에서 같은 역할을 한다.
- `sigmake`: `.pat` 파일을 최종 `.sig` 파일로 컴파일한다.
- `zipsig`: 완성된 `.sig`를 압축한다(선택 사항).

### 전체 흐름
1. 시그니처를 만들고 싶은 정적 라이브러리 원본 파일(`libmysdk.a` 또는 `mysdk.lib`)을 확보한다. **바이너리(실행 파일) 자체가 아니라 링크 전 라이브러리 아카이브가 필요**하다는 점이 중요하다 — FLIRT는 애초에 "라이브러리 안에 어떤 함수가 있었는지"를 아는 상태에서 패턴을 뽑는 도구이기 때문이다.
2. 플랫폼에 맞는 도구(`pelf`/`pelf64` 또는 `pcf`)로 `.pat` 파일을 생성한다. 이 단계에서 도구는 라이브러리 안의 각 함수에 대해 앞부분 고정 바이트, 가변(재배치) 위치, CRC, 참조하는 다른 심볼 이름까지 포함한 텍스트 형식의 패턴 한 줄을 만든다.
3. `sigmake`로 `.pat`을 `.sig`로 변환한다. 이 단계에서 서로 다른 함수인데 앞부분 바이트가 완전히 같은 "충돌(collision)"이 발견되면 `sigmake`는 변환을 멈추고 `.exc`(exclude) 파일에 충돌 목록을 적어준다.
4. `.exc` 파일을 열어 각 충돌 그룹에 대해 "이 이름들 중 하나만 대표로 쓴다(주석 처리 유지)" 또는 "이 그룹 전체를 시그니처에서 제외한다(`+` 표시)"를 결정한 뒤 다시 `sigmake`를 실행해 최종 `.sig`를 만든다.
5. 완성된 `.sig`를 IDA 설치 경로의 `sig/<플랫폼 폴더>`(예: Linux 계열은 `sig/gnulnx_x86`, Windows는 `sig/pc`)에 복사해두면, 이후 REV-0731에서 다룬 `File → Load file → FLIRT signature file...`로 다른 공식 시그니처와 동일하게 적용할 수 있다.

### 왜 "개념"으로 접근해야 하는가
FLAIR 실행 파일은 IDA GUI 메뉴 안에 포함되어 있지 않고, 별도 아카이브를 받아 커맨드라인에서 실행해야 한다(운영체제/버전에 따라 사전 빌드된 실행 파일 또는 소스가 제공된다). 오프라인 CTF 환경에서는 이 도구 자체를 미리 준비해두지 않으면 그 자리에서 새로 만들기 어려우므로, 이 문서는 "만드는 법이 있다"는 사실과 전체 흐름을 이해해 두고, 실제로 필요할 때는 사전에 준비된 FLAIR 배포본에서 정확한 명령줄 옵션을 확인하는 것을 전제로 한다.

### 실전에서 자주 쓰는 대체 경로
자체 시그니처를 만들 정도로 준비가 안 됐다면, REV-0668에서 다룬 것처럼 컴파일러/라이브러리 버전을 문자열로 특정한 뒤 커뮤니티가 이미 만들어 배포한 `.sig`(예: 자주 쓰이는 Ubuntu glibc 버전들에 대한 FLIRT 시그니처 모음)를 구해서 쓰는 것이 더 현실적인 경우가 많다. 직접 제작은 "그 라이브러리를 나만(혹은 우리 팀만) 반복해서 분석해야 하는 상황"에서 투자 가치가 있다.

## 화면/코드에서 보이는 징후
- REV-0731의 절차를 다 시도해도 Signatures 서브뷰에 매칭된 함수가 거의 없다.
- 분석 대상이 공개되지 않은 사내 SDK, 특정 게임 엔진, 임베디드 벤더의 정적 라이브러리를 링크하고 있다.
- 같은 팀에서 반복적으로 같은 정적 라이브러리가 포함된 바이너리를 여러 번 분석해야 하는 상황이다.

## 가장 먼저 할 것
시그니처를 만들려는 정적 라이브러리 원본(`.a`/`.lib`)을 확보할 수 있는지부터 확인한다. 원본 라이브러리가 없으면(예: 실행 파일만 있고 빌드 산출물인 라이브러리 아카이브 자체가 없으면) FLAIR로 시그니처를 만들 수 없으므로, 이 경우 REV-0668의 수동 식별 경로로 전환해야 한다.

## 단계별 절차
1. 시그니처를 만들 정적 라이브러리(`.a` 또는 `.lib`)를 확보한다.
2. 플랫폼에 맞는 FLAIR 실행 파일을 준비한다(ELF/COFF에 따라 `pelf`/`pelf64` 또는 `pcf`).
3. `pelf64 libmysdk.a libmysdk.pat` 형태로 `.pat` 파일을 생성한다(정확한 인자 순서/옵션은 사용 중인 FLAIR 배포본의 도움말로 확인).
4. `sigmake libmysdk.pat libmysdk.sig`로 `.sig` 생성을 시도한다.
5. 충돌이 보고되면 함께 생성된 `.exc` 파일을 열어 각 충돌 그룹의 처리 방식(대표 이름 선택 또는 그룹 제외)을 정하고 저장한다.
6. `.exc` 파일 반영 후 `sigmake`를 다시 실행해 최종 `.sig`를 완성한다.
7. 완성된 `.sig`를 IDA `sig/` 아래 알맞은 플랫폼 폴더에 복사한다.
8. 실제 분석 대상 바이너리에서 REV-0731과 동일하게 `File → Load file → FLIRT signature file...`로 새로 만든 `.sig`를 적용하고 매칭 결과를 확인한다.

## 명령어/단축키
```text
pelf64 libmysdk.a libmysdk.pat      # ELF 정적 라이브러리 -> 패턴 파일
pcf mysdk.lib mysdk.pat             # COFF(Windows) 정적 라이브러리 -> 패턴 파일
sigmake libmysdk.pat libmysdk.sig   # 패턴 파일 -> 시그니처 파일 (충돌 시 .exc 생성)
zipsig libmysdk.sig                 # (선택) 시그니처 압축
```
IDA 쪽 적용은 REV-0731과 동일하게 `File → Load file → FLIRT signature file...` 메뉴를 사용한다.

## 출력 해석
- `sigmake` 실행 후 `NN new names were applied`류의 요약 대신 `collisions found`가 나오면, 앞서 생성된 `.exc` 파일을 반드시 확인해야 한다. `.exc` 파일을 건드리지 않고 그대로 재실행하면 같은 충돌이 반복된다.
- `.pat` 파일은 텍스트이므로 열어보면 각 줄이 함수 하나에 대응하며, 앞부분은 고정 바이트를 16진수로, 이후는 함수 크기·이름·참조 심볼 정보를 담고 있다. 이 형식을 직접 읽을 일은 드물지만, 특정 함수가 왜 패턴에서 빠졌는지 디버깅할 때 유용하다.
- 최종 `.sig`를 적용했는데도 매칭이 0이면, 실제 분석 대상 바이너리가 시그니처를 뽑은 라이브러리와 다른 버전/다른 최적화 옵션으로 빌드되었을 가능성이 크다.

## 흔한 실수
- 실행 파일(바이너리) 자체에서 바로 시그니처를 뽑으려 하는 것 — FLAIR는 링크 전 라이브러리 아카이브가 입력이어야 하며, 이미 링크되어 최적화/인라인이 적용된 실행 파일에서는 함수 경계를 안정적으로 뽑기 어렵다.
- `.exc` 파일의 충돌을 무시하고 그냥 넘어가는 것 — 충돌을 해결하지 않으면 `.sig`가 아예 생성되지 않거나, 여러 함수가 뒤섞인 신뢰할 수 없는 시그니처가 만들어질 수 있다.
- 생성한 `.sig`를 아무 플랫폼 폴더에나 넣어서 다른 아키텍처 바이너리에 적용하려 시도하는 것.
- 라이브러리 버전이 바뀔 때마다 시그니처를 다시 안 만들고 예전 `.sig`를 계속 재사용하는 것 — 버전이 다르면 매칭률이 떨어지므로 라이브러리가 갱신되면 시그니처도 다시 만들어야 한다.

## 막혔을 때 다음 체크
- 아직 기본 제공 `.sig`를 다 시도해보지 않았다면 → REV-0731 IDA FLIRT 시그니처 적용해서 라이브러리 함수 식별하기
- 원본 라이브러리 아카이브 자체를 구할 수 없다면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)의 수동 식별 경로로 전환
- glibc 버전이 흔치 않아 직접 만들어야 하는지 먼저 판단하고 싶다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- FLIRT 개념 자체를 다시 요약해서 보고 싶다면 → REV-0729 FLIRT 시그니처 개념과 사용 빠른 참조

## 미니 예제
사내 SDK `libgamecore.a`를 여러 번 반복해서 분석해야 하는 상황을 가정한다.

```text
$ pelf64 libgamecore.a libgamecore.pat
$ sigmake libgamecore.pat libgamecore.sig
Collisions found. See libgamecore.exc for details.
```

`libgamecore.exc`를 열어보니 `GameObject_Init`과 `GameObject_Reset`이 같은 바이트 패턴으로 충돌한다고 나온다. 두 함수 중 더 자주 쓰일 것 같은 이름 하나만 남기고 나머지 줄 앞에 제외 표시를 남긴 뒤 다시 `sigmake`를 실행하면 `libgamecore.sig`가 완성된다. 이 파일을 IDA의 `sig/pc/` 폴더에 넣어두면, 이후 이 SDK를 링크한 다른 바이너리를 열 때마다 `File → Load file → FLIRT signature file...`로 즉시 재사용할 수 있다.

## 관련 글
- REV-0731 — IDA FLIRT 시그니처 적용해서 라이브러리 함수 식별하기
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0729 — FLIRT 시그니처 개념과 사용 빠른 참조

## 출처/검증
- FLAIR 툴킷의 구성 요소(`pelf`/`pelf64`, `pcf`, `sigmake`, `zipsig`)와 `.pat`→`.sig` 변환 및 충돌 시 `.exc` 파일 처리 흐름: Hex-Rays 공식 FLIRT/FLAIR 문서 기준.
- FLAIR가 IDA 라이선스 계정을 통해 별도로 배포되는 커맨드라인 도구 모음이라는 점: Hex-Rays 공식 다운로드 페이지 설명 기준.
- 이 문서는 2026-09-09 기준 공개된 공식 문서 요약을 바탕으로 작성했으며, 실제 명령줄 옵션과 배포 형태(사전 빌드본 유무)는 Hex-Rays가 제공하는 FLAIR 버전에 따라 달라질 수 있으므로 실제 사용 시 동봉된 README를 함께 참고할 것.
