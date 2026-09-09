---
id: REV-0324
title: "오래된 대회 문제(레거시 컴파일러) 특징 알아보기"
slug: "rev-0324-legacy-compiler-old-contest-binary"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, "Detect It Easy", checksec]
keywords: ["레거시 컴파일러", "오래된 CTF 바이너리", "VC6 바이너리", "Borland C++ 리버싱", "구식 32비트 바이너리 특징"]
aliases: ["오래된 문제 특징", "옛날 컴파일러 바이너리", "구버전 GCC 바이너리", "레트로 CTF 리버싱"]
symptom_keywords: ["checksec 결과가 전부 꺼져있음", "함수 이름이 낯선 방식으로 되어있음", "32비트인데 보호기법이 하나도 없음", "IDA가 컴파일러를 옛날 버전으로 인식함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
오래된 대회(2000년대~2010년대 초반) 문제나 레트로 컴필레이션 문제는 32비트 전용, 보호기법(Canary/NX/PIE) 전무, VC6/Borland C++ 같은 구형 컴파일러 특유의 이름 규칙과 런타임 코드가 섞여 있는 경우가 많으므로, 최신 컴파일러 기준으로 학습한 패턴을 그대로 적용하면 오히려 헷갈릴 수 있다는 점을 미리 인지하고 접근해야 한다.

## 언제 검색해야 하나
- `checksec` 결과에 Canary/NX/PIE/RELRO가 전부 `No`/`disabled`로 나와서 최신 문제와 확연히 다른 느낌일 때
- Detect It Easy(DIE)가 컴파일러를 `Microsoft Visual C++ 6.0`, `Borland C++`, `Turbo C` 같은 옛날 이름으로 표시할 때
- 함수 이름이 `@ILT+...` 형태(VC6 incremental linking thunk)이거나 `@함수명$qi` 같은 낯선 데코레이션이 보일 때
- 32비트 전용이고 64비트 버전이 아예 없는 오래된 문제를 접했을 때
- 오래된 wargame 사이트(2010년대 초중반 개설)의 문제를 풀 때 최신 IDA/Ghidra 분석 결과가 예상과 다를 때

## 핵심 개념

### 왜 오래된 바이너리가 다르게 보이는가
컴파일러와 OS 보안 기능은 시간이 지나며 계속 발전했다. 2000년대~2010년대 초반에 컴파일된 바이너리는 지금 기준으로 당연한 보호기법(스택 카나리, NX, ASLR/PIE, RELRO)이 아예 적용되지 않은 채로 빌드된 경우가 많다. 또한 당시 주류였던 32비트 컴파일러(VC6, 초기 GCC, Borland C++/Turbo C++)는 지금의 GCC/Clang/MSVC와 코드 생성 스타일, 이름 규칙(name mangling), 런타임 초기화 코드가 다르다.

### 컴파일러별 특징
- **MSVC 구버전(VC6, VS2003~2005)**: 함수 진입점에 incremental linking thunk(`jmp` 한 줄짜리 함수, IDA에서 `@ILT+0(...)` 같은 이름으로 보임)가 남아있을 수 있다. C++ 이름 데코레이션은 `?funcname@@YAXH@Z` 같은 MSVC decoration 규칙을 따르며, 이는 최신 MSVC와 큰 틀은 같지만 세부 규칙이 버전마다 조금씩 다르다.
- **Borland C++ / Turbo C++**: 함수 이름 앞에 `@`가 붙는 Borland 고유 데코레이션(`@ClassName@FuncName$qv` 등)을 쓴다. calling convention도 기본이 `register`(파스칼 계열 영향)라서 MSVC의 `cdecl`/`stdcall`과 인자 전달 방식이 다를 수 있다.
- **구버전 GCC(2.x~3.x, 32비트)**: 최신 GCC의 스택 보호(`__stack_chk_fail`), PIE 관련 코드가 아예 없다. C++이라면 GNU v2 ABI(구버전, `__14ClassNamestring` 형태) 데코레이션이 나올 수도 있는데 최신 GNU v3 ABI(Itanium ABI, `_ZN...`)와 전혀 다르게 생겼다.
- **정적 링킹 비중이 높음**: 배포 편의를 위해 정적 링킹된 경우가 지금보다 흔했다. 정적 바이너리 분석 전략은 REV-0646을 그대로 따르되, 시그니처 데이터베이스(FLIRT/FID)가 최신 컴파일러 위주라 오래된 컴파일러 버전과 매칭률이 낮을 수 있다는 점을 감안해야 한다.

### 도구로 먼저 확인한다
직접 코드를 눈으로 보고 "옛날 코드 같다"고 추측하기보다, Detect It Easy(DIE, REV-0126)로 컴파일러/링커 정보를 먼저 확인하는 것이 훨씬 정확하다. DIE는 알려진 컴파일러/패커 시그니처 데이터베이스를 갖고 있어 `Microsoft Visual C++ 6.0`, `Borland C++` 같은 구체적인 이름까지 짚어주는 경우가 많다.

## 화면/코드에서 보이는 징후
- `checksec` 결과: `Canary: No`, `NX: disabled`, `PIE: No`, `RELRO: No`가 동시에 나타남(REV-0105)
- IDA Functions 창에 `@ILT+20(func)`, `sub_401000` 같은 thunk성 이름이 다수 존재
- 문자열에 옛날 컴파일러/IDE 관련 흔적(`Runtime Error`, `Borland`, `TASM` 등)이 남아있음
- 32비트 전용이며 x64 버전이 아예 존재하지 않음
- Detect It Easy가 컴파일러 항목에 구체적인 옛날 버전명을 표시

## 가장 먼저 할 것
Detect It Easy로 파일을 열어 컴파일러/링커 정보부터 확인하고, `checksec`으로 보호기법 상태를 함께 기록한다. 두 결과를 합치면 "이 바이너리가 어느 시대, 어느 컴파일러로 만들어졌는지"에 대한 1차 그림이 나온다.

## 단계별 절차
1. Detect It Easy로 컴파일러/링커/패커 정보 확인 (REV-0126)
2. `checksec ./chall` 또는 PE-bear로 보호기법 상태 확인 — 옛날 바이너리는 대부분 전무
3. 32비트/64비트 여부 확인, C++이면 함수 이름 데코레이션 방식으로 컴파일러 계열 추정(MSVC `?...@@Y`, Borland `@...$q`, GNU v2 `__` 계열, GNU v3(Itanium) `_ZN`)
4. Import 목록에서 낯선 이름의 런타임 함수(구버전 CRT, Borland RTL 함수 등)가 보이면 REV-0137(VC Runtime 노이즈 정리)과 같은 방식으로 실제 로직과 컴파일러 생성 코드를 구분
5. FLIRT/FID 시그니처 매칭 시도 — 매칭률이 낮으면 시그니처 DB가 최신 컴파일러 위주라는 것을 인지하고 수동 분석 비중을 높임
6. 정적 링킹이면 REV-0646 절차로 전환
7. 실행 환경(오래된 32비트 DOS/Win9x 스타일 문제라면 에뮬레이터나 호환 모드 필요 여부)까지 확인 후 동적 분석 도구(x64dbg/GDB) 호환성 점검

## 명령어/단축키
```bash
file ./chall
checksec --file=./chall
strings ./chall | grep -iE "borland|turbo|microsoft.*c\+\+|runtime error"
```
Detect It Easy: 파일 드래그 → 상단에 컴파일러/링커 이름 표시 확인.

## 출력 해석
- DIE가 `Microsoft Visual C++ 6.0`을 표시하면 함수 데코레이션과 예외 처리(SEH) 방식이 최신 MSVC와 세부적으로 다를 수 있음을 감안한다.
- `checksec` 전항목이 비활성이면 pwn 관점에서는 공격이 상대적으로 쉬운 세팅이지만, 순수 리버싱 관점에서는 스택 카나리 검사 코드가 없어 함수 프롤로그/에필로그가 더 단순하게 보인다는 의미다.
- FLIRT/FID 매칭률이 낮게 나오면 "시그니처가 안 맞는 것"이지 "분석이 잘못된 것"이 아니므로, 수동으로 `_start`/`main` 추적(REV-0646 절차)으로 전환하는 것이 맞는 대응이다.

## 흔한 실수
- 구형 컴파일러의 함수 데코레이션을 최신 Itanium ABI(`_ZN...`) 기준으로 해석하려다 클래스/네임스페이스 구조를 잘못 추정하는 것.
- 보호기법이 전무하다고 방심하고 리버싱 로직 분석 자체를 소홀히 하는 것 — 보호기법 유무와 검증 로직의 복잡도는 별개다.
- 최신 IDA/Ghidra의 자동 분석 결과를 무조건 신뢰하는 것 — 구형 컴파일러 코드는 함수 경계 인식(REV-0154)이 최신 컴파일러보다 더 자주 틀릴 수 있다.
- Borland/구형 GCC의 독특한 calling convention을 무시하고 무조건 cdecl로 가정해 인자 개수/순서를 잘못 읽는 것.

## 막혔을 때 다음 체크
- 컴파일러 식별 자체가 안 된다 → REV-0126 Detect It Easy로 컴파일러 패커 확인
- VC 런타임 관련 노이즈 함수가 너무 많아 실제 로직을 못 찾겠다 → REV-0137 Visual C++ Runtime 함수가 많은 바이너리 정리법
- 정적 링킹된 구형 바이너리라 함수가 수천 개다 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- IDA가 함수 경계를 잘못 잡는 것 같다 → REV-0154 IDA Wrong Function Boundary
- 보호기법 항목 자체의 의미가 헷갈린다 → REV-0105 Canary NX PIE RELRO 한 번에 이해

## 미니 예제
```text
$ checksec --file=./old_crackme
    Canary   : No
    NX       : disabled
    PIE      : No
    RELRO    : No

DIE 분석 결과: Compiler: Microsoft Visual C++ 6.0 (1998)
```
이 결과는 이 바이너리가 1998년경 출시된 VC6로 컴파일되었고, 보호기법이 전무한 순수 32비트 코드라는 것을 보여준다. 이 정보만으로도 "최신 GCC의 스택 카나리 검사 코드가 있을 것"이라는 잘못된 가정을 미리 배제하고, VC6 특유의 함수 데코레이션과 incremental linking thunk 가능성을 염두에 두고 분석을 시작할 수 있다.

## 관련 글
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0154 — IDA에서 함수 경계가 잘못 잡혔을 때

## 출처/검증
- MSVC 함수 이름 데코레이션(name mangling) 규칙과 incremental linking thunk 동작: Microsoft C++ 컴파일러 공식 문서(Decorated Names) 기준.
- Borland C++ 고유 데코레이션과 기본 calling convention: Embarcadero(구 Borland) C++Builder 공식 문서 기준.
- GNU v2 대 GNU v3(Itanium C++ ABI) 이름 규칙 차이: Itanium C++ ABI 공식 명세 기준 (2026-09-09 검증).
