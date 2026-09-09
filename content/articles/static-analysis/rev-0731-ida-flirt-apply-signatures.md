---
id: REV-0731
title: "IDA FLIRT 시그니처 적용해서 라이브러리 함수 식별하기"
slug: "rev-0731-ida-flirt-apply-signatures"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["FLIRT", "Fast Library Identification and Recognition Technology", "IDA 시그니처", "sig 파일 적용", "Load file FLIRT signature file", "Signatures 서브뷰", "라이브러리 함수 식별"]
aliases: ["IDA FLIRT 적용법", "sig 파일 로드", "IDA 시그니처 매칭 사용법", "라이브러리 함수 자동 인식"]
symptom_keywords: ["함수 이름이 전부 sub_로 나옴", "IDA가 알아서 함수 이름을 붙여줬는데 어디서 온 건지 모르겠음", "FLIRT를 어떻게 적용하는지 모르겠음", "sig 파일을 어디에 넣어야 하는지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
IDA의 FLIRT(Fast Library Identification and Recognition Technology)는 정적으로 링크된 라이브러리 함수(예: MSVC 런타임, glibc)의 바이트 패턴을 미리 계산해 둔 `.sig` 파일과 대조해서 `sub_401230` 같은 무명 함수에 `strcpy`, `malloc` 같은 실제 이름을 자동으로 붙여주는 기능이며, `File → Load file → FLIRT signature file...` 메뉴와 **Signatures** 서브뷰로 직접 조작할 수 있다.

## 언제 검색해야 하나
- IDA로 PE/ELF 바이너리를 열었더니 함수 몇 개는 자동으로 `_strcpy`, `_memcpy` 같은 이름이 붙어 있는데, 왜/어떻게 붙었는지 원리를 모를 때
- 정적 링킹된 바이너리라 함수가 수천 개인데 자동 적용된 시그니처의 매칭률이 낮아서 추가로 다른 `.sig` 파일을 더 적용하고 싶을 때
- 이미 적용된 시그니처 목록을 확인하거나, 잘못 적용된 것 같은 이름을 지우고 다른 시그니처를 다시 시도하고 싶을 때
- MSVC로 빌드된 Windows PE인데 C 런타임 함수 이름이 하나도 안 보여서, 그에 맞는 `vc*` 계열 시그니처를 수동으로 로드해야 할 때

## 핵심 개념

### FLIRT가 하는 일
같은 컴파일러·같은 버전·같은 최적화 옵션으로 컴파일된 라이브러리 함수는 명령어 바이트 시퀀스가 거의 동일하게 나온다. 다만 상대 주소를 담은 오퍼랜드(다른 함수를 부르는 `call`/`jmp` 대상 등)는 바이너리마다 달라지므로, FLIRT는 이런 가변 바이트를 와일드카드로 마스킹한 뒤 나머지 고정 바이트의 패턴/체크섬을 `.sig`(또는 중간 산출물인 `.pat`) 파일에 미리 저장해둔다. IDA는 분석 중인 바이너리의 코드 바이트를 이 패턴들과 비교해서 일치하면 그 함수에 알려진 이름을 자동으로 붙인다.

### 자동 적용과 수동 적용
IDA는 바이너리를 처음 열 때 컴파일러 시그니처(예: PE의 `.idata`/컴파일러 배너, ELF의 `.comment` 섹션 등)를 보고 관련성이 높아 보이는 `.sig` 파일을 스스로 골라 자동 적용을 시도한다. 이때 Output window에 `Compiler function 'xxx' has been found`처럼 매칭된 함수 이름이 로그로 뜬다. 그러나 자동 선택이 틀리거나(예: 실제로는 다른 컴파일러 버전) 아예 아무것도 안 붙는 경우가 흔하므로, 다음 메뉴로 수동 적용한다.

```
File → Load file → FLIRT signature file...
```

이 메뉴를 열면 IDA 설치 폴더의 `sig/` 아래 아키텍처별 하위 폴더(Windows PE는 보통 `sig/pc/`, Linux 계열은 `sig/gnulnx_x86` 등)에 있는 `.sig` 목록이 나온다. 원하는 항목(예: `vc32rtf`, `vc142_ucrt`, `gnu_x64_glibc` 계열)을 선택하면 IDA가 전체 데이터베이스를 다시 스캔해서 일치하는 함수에 이름을 붙인다. 하나의 데이터베이스에 여러 `.sig`를 순서대로 여러 번 적용할 수도 있으며, 먼저 적용된 시그니처가 이미 이름 붙인 함수는 건드리지 않고 아직 무명인 함수만 추가로 매칭을 시도한다.

### Signatures 서브뷰로 적용 현황 확인
`View → Open subviews → Signatures`를 열면 현재 데이터베이스에 적용된 `.sig` 파일 목록과 각각의 **매칭 함수 개수(% matched 유사 정보)**가 표시된다. 여기서 우클릭하면 특정 시그니처를 다시 전체 적용하거나, 목록에서 제거(다음 재분석 때 더 이상 시도하지 않게)할 수 있다. 여러 시그니처를 적용해본 뒤 어떤 것이 실제로 도움이 됐는지 이 창에서 비교하는 것이 좋다.

### 매칭 충돌과 신뢰도
같은 바이트 패턴이 서로 다른 함수 이름 후보와 동시에 일치하는 경우(라이브러리 버전 차이로 인한 충돌), IDA는 이름 앞에 `_` 접두사를 붙이거나 Output window에 "collision" 계열 경고를 남기고 하나만 골라 적용한다. 이런 이름은 확정된 사실이 아니라 확률적 추정이므로, 중요한 함수라면 REV-0165(상수 검색)나 GDB/x64dbg로 실제 동작을 재현해 이름이 맞는지 검증하는 습관이 필요하다.

### Windows PE와 Linux ELF의 차이
Windows PE는 MSVC 런타임(`vcruntime`, `ucrt`), MFC 등 IDA가 기본 제공하는 `.sig`가 비교적 풍부하고 자동 적용도 잘 되는 편이다. Linux ELF, 특히 정적 링킹된 glibc 바이너리는 배포판/버전 조합이 매우 다양해서 IDA 기본 제공 `.sig`만으로는 매칭률이 낮은 경우가 많다. 이때는 REV-0668에서 다루는 것처럼 컴파일러/glibc 버전을 먼저 특정한 뒤, 그 버전에 맞는 커뮤니티 제작 `.sig`(또는 REV-0732에서 다루는 직접 제작)를 구해 적용해야 한다.

## 화면/코드에서 보이는 징후
- Functions 창에 `strcpy`, `memcpy`, `_vsnprintf` 등 이름 앞에 밑줄이 붙은 함수가 섞여 있다(FLIRT로 자동 인식된 함수는 관례적으로 언더스코어가 붙는 경우가 많다).
- Output window에 `The function 'sub_XXXXXX' was matched...` 또는 컴파일러 시그니처 적용 로그가 스크롤될 때 나타난다.
- 정적 링킹된 바이너리에서 함수 수천 개 중 극히 일부만 이름이 붙어 있고 나머지는 여전히 `sub_` 그대로다.

## 가장 먼저 할 것
Output window를 위로 스크롤해서 IDA가 바이너리를 열 때 어떤 `.sig`를 자동 적용했는지(또는 아예 시도하지 않았는지) 확인한다. 이미 적용된 시그니처는 `View → Open subviews → Signatures`에서 다시 확인하고, 매칭 함수 수가 너무 적다면 아래 절차대로 다른 `.sig`를 추가로 적용한다.

## 단계별 절차
1. `View → Open subviews → Signatures`를 열어 현재 적용된 `.sig` 목록과 매칭 개수를 확인한다.
2. `readelf -p .comment ./chall`(ELF) 또는 PE의 링커 버전 정보, 빌드 도구 버전을 확인해 어떤 컴파일러/런타임 조합인지 추정한다(REV-0646, REV-0668 참고).
3. `File → Load file → FLIRT signature file...`을 열고, 추정한 조합에 가장 가까운 `.sig` 항목을 선택해 적용한다.
4. 적용 직후 Output window에 새로 매칭된 함수 개수가 몇 개인지 확인하고, Functions 창을 새로고침해서 이름이 실제로 바뀌었는지 확인한다.
5. 매칭 결과가 미미하면 다른 후보 `.sig`(예: 다른 버전, 다른 아키텍처 세부 옵션)를 순서대로 추가 적용해본다. 이미 이름 붙은 함수는 재적용해도 덮어써지지 않으므로 여러 번 시도해도 안전하다.
6. 충돌(collision)로 의심되는 이름이 나오면 REV-0165의 상수 검색이나 실제 실행 관찰로 이름이 맞는지 교차 검증한다.
7. IDA 기본 제공 `.sig`로 충분치 않다면 REV-0732(FLIRT 시그니처 직접 만들기)로 넘어간다.

## 명령어/단축키
- `File → Load file → FLIRT signature file...`: `.sig` 파일 수동 적용
- `View → Open subviews → Signatures`: 현재 적용된 시그니처 목록/매칭 현황 확인(우클릭으로 재적용/제거)
- Output window 스크롤: 자동 적용 로그 및 매칭 결과 확인
- 기본 단축키는 없으며 메뉴 경로로 조작하는 것이 일반적이다(버전에 따라 메뉴 문구가 조금 다를 수 있음).

## 출력 해석
- Output window에 매칭된 함수 이름이 나열되면 그만큼 함수가 자동으로 이름 붙었다는 뜻이다. 개수가 0이면 선택한 `.sig`가 이 바이너리와 맞지 않는 조합이다.
- Signatures 서브뷰에서 특정 `.sig`의 매칭 함수 수가 매우 적다면(전체 함수 대비), 컴파일러/버전이 실제와 다를 가능성이 크므로 다른 `.sig`를 시도해야 한다.
- 함수 이름 앞에 언더스코어(`_`)가 붙어 있다면 대개 FLIRT로 자동 매칭된 라이브러리 함수라는 관례적 표시이지, 사용자가 직접(N으로) 지정한 이름과는 출처가 다르다.

## 흔한 실수
- 자동 적용된 시그니처 이름을 검증 없이 100% 신뢰하고 로직을 해석하는 것 — 충돌/오탐 가능성이 있다.
- ELF 바이너리에 Windows용 `.sig`를, PE 바이너리에 Linux용 `.sig`를 적용하려 시도하는 것 — 각 플랫폼/아키텍처 하위 폴더의 `.sig`만 해당 데이터베이스에 유효하게 적용된다.
- 매칭이 하나도 안 됐다고 FLIRT 자체가 고장났다고 오해하는 것 — 대부분은 컴파일러/버전 조합이 시그니처 DB와 안 맞는 것이며, REV-0668의 버전 특정 절차를 먼저 거쳐야 한다.
- Signatures 서브뷰를 확인하지 않고 같은 `.sig`를 반복 적용하며 시간을 낭비하는 것 — 이미 적용된 것은 매칭 개수가 그대로이므로 서브뷰로 먼저 확인하는 것이 빠르다.

## 막혔을 때 다음 체크
- glibc 버전을 먼저 특정해야 한다면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- 정적 링킹 바이너리 분석 전략 전체가 궁금하다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- IDA 기본 제공 시그니처로 안 된다면 → REV-0732 IDA에서 나만의 FLIRT 시그니처 만드는 개념
- musl 기반이라 glibc 시그니처가 전혀 안 맞는다면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향
- FLIRT 개념 자체를 요약된 표로 빠르게 보고 싶다면 → REV-0729 FLIRT 시그니처 개념과 사용 빠른 참조

## 미니 예제
strip되지 않은 정적 PE 바이너리를 IDA로 열었더니 Output window에 다음과 같은 로그가 스크롤된다.

```
Compiler function 'strcpy' has been found
Compiler function '_memcpy' has been found
... 214 function names have been applied
```

이는 IDA가 바이너리를 열자마자 관련성 높은 `vc*` 계열 `.sig`를 자동 적용해 214개 함수에 이름을 붙였다는 뜻이다. 만약 이 로그가 전혀 없거나 매칭 수가 한 자릿수라면, `View → Open subviews → Signatures`에서 현재 상태를 확인한 뒤 `File → Load file → FLIRT signature file...`로 더 정확한 버전의 `.sig`를 직접 골라 적용한다. 적용 후 Functions 창을 다시 보면 이전에 `sub_401A00`였던 함수가 `_strcpy`로 바뀐 것을 확인할 수 있다.

## 관련 글
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향
- REV-0732 — IDA에서 나만의 FLIRT 시그니처 만드는 개념
- REV-0165 — 상수 검색으로 알고리즘 찾기
- REV-0729 — FLIRT 시그니처 개념과 사용 빠른 참조

## 출처/검증
- FLIRT의 원리(가변 바이트 마스킹 후 패턴/체크섬 대조)와 `.sig`/`.pat` 파일 구조: Hex-Rays 공식 문서(FLIRT technology 설명) 기준.
- `File → Load file → FLIRT signature file...` 메뉴 경로와 Signatures 서브뷰(`View → Open subviews → Signatures`)의 존재: Hex-Rays 공식 사용자 가이드(Open subviews 목록) 기준.
- 이 문서는 2026-09-09 기준 공개된 Hex-Rays 공식 문서 검색 결과를 바탕으로 작성했으며, 정확한 메뉴 문구/서브폴더 이름은 설치된 IDA 버전에 따라 다를 수 있으므로 실제 환경에서 재확인할 것을 권장한다.
