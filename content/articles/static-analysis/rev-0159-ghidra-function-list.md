---
id: REV-0159
title: "Ghidra Function 목록과 Symbol Tree"
slug: "rev-0159-ghidra-function-list"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Symbol Tree", "Ghidra Functions 폴더", "Ghidra Namespaces", "Ghidra Data Types 패널", "Ghidra Exports Imports 목록"]
aliases: ["Ghidra 함수 목록", "Ghidra 심볼 트리", "Ghidra 함수 찾기"]
symptom_keywords: ["Ghidra에서 main 함수를 못 찾음", "Ghidra Symbol Tree가 뭔지 모름", "Ghidra 함수가 너무 많아서 못 찾겠음", "Ghidra Imports 목록 보는 법"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CodeBrowser 왼쪽의 **Symbol Tree** 패널은 바이너리 안의 모든 심볼(함수, 전역 변수, 네임스페이스, Import/Export)을 카테고리별 트리로 보여주는 창으로, 여기서 `Functions` 폴더를 정렬/필터링하는 법과 `Imports`/`Exports`를 구분해서 읽는 법을 알면 원하는 함수를 빠르게 찾을 수 있다.

## 언제 검색해야 하나
- CodeBrowser 왼쪽 패널에 폴더 트리가 잔뜩 있는데 뭐가 뭔지 모를 때
- 함수가 수백 개라서 원하는 함수(예: 검증 로직이 있을 법한 함수)를 어떻게 찾아야 할지 막막할 때
- `Imports`와 `Exports`가 무슨 차이인지, 어디서 봐야 하는지 모를 때
- 함수 이름순/주소순으로 정렬하는 법을 모를 때

## 핵심 개념
Ghidra CodeBrowser의 왼쪽 패널은 기본적으로 **Symbol Tree**다(가장 왼쪽 탭이 보통 이 트리이며, 옆에 Data Type Manager 탭이 함께 있다). Symbol Tree는 다음 폴더들로 구성된다:

- **Imports**: 이 바이너리가 외부(DLL, 공유 라이브러리)에서 가져와 쓰는 함수 목록. Windows PE라면 `KERNEL32.dll`, `MSVCRT.dll` 등에서 가져온 `CreateFileA`, `strcmp` 같은 함수들이 여기 나열된다. IDA의 Imports 탭과 동일한 역할이다.
- **Exports**: 이 바이너리 자신이 외부에 공개하는 심볼(주로 DLL을 분석할 때 의미가 크다). 일반 실행 파일(EXE)에는 보통 거의 없거나 `entry` 정도만 있다.
- **Functions**: 이 바이너리 안에 실제로 정의된 모든 함수. Import된 외부 함수는 여기 포함되지 않고, 이 바이너리의 코드 섹션 안에서 디스어셈블되어 함수로 인식된 것들만 나온다. 이름이 자동으로 안 붙은 함수는 `FUN_00401230`처럼 주소 기반 이름으로 보인다.
- **Labels**: 함수는 아니지만 이름이 붙은 주소(예: 점프 테이블 라벨, 수동으로 이름 붙인 위치).
- **Namespaces / Classes**: C++ 바이너리에서 클래스/네임스페이스 구조가 인식된 경우 계층으로 표시된다.
- **Global**: 위 카테고리에 속하지 않는 전역 심볼들의 기본 네임스페이스.

이 패널 옆에는 보통 **Data Type Manager**(자료형 목록, REV-0161에서 사용)와 CodeBrowser 상단에 **Filter** 입력창이 있어, 이름 일부만 입력해도 트리가 실시간으로 좁혀진다.

또한 Ghidra는 IDA의 "Functions window"에 해당하는 별도의 테이블 형태 창도 제공한다. **Window → Functions**를 열면 모든 함수를 표 형태로 보여주며, 이름/주소/크기 등 컬럼을 클릭해 정렬할 수 있어 "코드 크기가 큰 함수부터 훑어보기" 같은 전략에 유용하다.

## 화면/코드에서 보이는 징후
- CodeBrowser 왼쪽에 트리 구조 패널이 있고, 최상위에 `Imports`, `Exports`, `Functions`, `Labels`, `Namespaces` 등의 폴더 아이콘이 보인다.
- `Functions` 폴더를 펼치면 함수들이 알파벳/주소 순으로 나열되며, 기본 이름은 `FUN_` 접두사, 라이브러리로 식별된 함수는 실제 이름이 보인다.
- 패널 상단에 필터 텍스트박스(돋보기 아이콘)가 있다.

## 가장 먼저 할 것
Symbol Tree에서 `Functions` 폴더를 펼쳐서 전체 함수 개수를 가늠하고, 상단 필터 박스에 찾고 싶은 이름의 일부(예: `main`, `check`, `verify`)를 입력해 좁혀본다. `Imports` 폴더도 한 번 펼쳐서 이 바이너리가 어떤 외부 함수를 쓰는지(`strcmp`, `MessageBoxA` 등) 훑어본다.

## 단계별 절차

**1) Symbol Tree 열기**

CodeBrowser 왼쪽에 기본적으로 열려 있다. 안 보이면 **Window → Symbol Tree**로 다시 켠다.

**2) Functions 폴더 탐색**

`Functions` 폴더를 펼쳐서(화살표 클릭) 함수 목록을 본다. 이름 기준으로 이미 정렬되어 있다.

**3) 필터로 좁히기**

패널 상단 필터 텍스트박스에 검색어를 입력하면 트리가 실시간으로 좁혀진다. 예를 들어 `check`를 입력하면 이름에 `check`가 들어간 함수/심볼만 남는다. 아직 사람이 이름을 안 붙인 함수(`FUN_...`)는 이 방식으로 못 찾으므로, 초반에는 `Imports` 폴더를 먼저 보는 것이 더 효율적일 때가 많다.

**4) Imports로 단서 찾기**

`Imports` 폴더를 펼쳐서 `strcmp`, `strncmp`, `memcmp`, `MessageBoxA`, `GetDlgItemTextA` 등 "검증/입력 처리"와 관련 있어 보이는 함수가 있는지 훑어본다. 이 목록에서 함수를 더블클릭하면 Listing이 해당 Import 항목(thunk/stub)으로 이동한다.

**5) Functions window로 표 보기(선택)**

**Window → Functions**를 열면 모든 함수가 표로 나오고, 컬럼 헤더(Name, Location, Function Size 등)를 클릭해 정렬할 수 있다. 예를 들어 Function Size로 내림차순 정렬하면 "가장 코드가 복잡한 함수"부터 볼 수 있어, 메인 로직이 들어있을 법한 함수를 추정하는 데 도움이 된다.

**6) 함수로 이동해서 분석 시작**

Symbol Tree나 Functions window에서 더블클릭하면 Listing과 Decompile 창이 동시에 그 함수 위치로 이동한다(REV-0158 참고).

## 명령어/단축키
- Symbol Tree 열기: **Window → Symbol Tree**
- Functions 표 창 열기: **Window → Functions**
- 필터 입력: 패널 상단 텍스트박스에 바로 입력(별도 단축키 불필요)
- 이전/다음 함수로 이동: `Ctrl+↑` / `Ctrl+↓` (Listing에서 커서가 함수 시작 주소로 이동)
- 이름으로 아무 위치나 찾기: `G`(Go To) 후 함수명 입력

## 출력 해석
- `Imports` 폴더에 나오는 함수는 이 바이너리의 코드가 아니라 **외부 DLL/공유 라이브러리의 함수를 가리키는 자리표시자(thunk)**다. 실제 로직은 그 안에 없고, 이 함수를 "누가 호출하는지"를 추적하는 것이 목적이다(REV-0160, REV-0164 참고).
- `Functions` 폴더에서 이름이 `FUN_` 접두사인 것은 전부 "이 바이너리에서 정의된, 아직 사람이 의미를 파악하지 못한 함수"다. 개수가 많다고 겁먹을 필요 없이, 실제로 봐야 할 함수는 Imports를 통해 후보를 좁힌 뒤 XREF로 찾아가는 경우가 대부분이다.
- Functions window에서 Function Size가 유난히 큰 함수는 컴파일러가 생성한 초기화 루틴(`__scrt_common_main`, C 런타임 초기화 등)이거나, 반대로 실제 핵심 로직이 몰려있는 함수일 수 있으니 크기만으로 단정하지 말고 REV-0167(Compiler Generated Code와 실제 문제 로직 구분)을 함께 참고한다.

## 흔한 실수
- `Functions` 폴더만 보고 `FUN_` 이름들을 하나씩 순서대로 다 열어보는 것 — 함수가 수백 개면 비효율적이다. `Imports`나 문자열(REV-0163)에서 단서를 먼저 잡고 거꾸로 추적하는 것이 훨씬 빠르다.
- `Imports`와 `Functions`를 혼동해서, Import된 라이브러리 함수(`strcmp` 등) 안에 이 바이너리의 로직이 있다고 착각하는 것 — 라이브러리 함수 자체는 바이너리 밖의 코드이므로, 그 함수를 "누가 호출하는지"를 봐야 실제 로직에 닿는다.
- 필터 박스에 검색어를 입력했는데 결과가 안 나온다고 포기하는 것 — 아직 이름이 안 붙은 함수는 텍스트로 검색되지 않으니, 이름 검색 대신 XREF나 문자열 참조로 접근 방법을 바꿔야 한다.
- `main` 함수를 못 찾아서 헤매는 것 — 최적화되었거나 스트립된 바이너리에서는 `main`이 곧바로 `entry`가 아니라 C 런타임 초기화 코드(`__scrt_common_main_seh` 등)를 몇 단계 거친 뒤에 호출되므로, `entry`부터 Function Call Graph(REV-0166)로 따라 들어가야 한다.

## 막혔을 때 다음 체크
- `Imports`에서 의심되는 함수를 찾았는데 그 함수를 누가 부르는지 모르겠다면 → REV-0160(Ghidra XREF 따라가기).
- 함수는 찾았는데 이름이 `FUN_`이라 뭐 하는 함수인지 모르겠다면 → REV-0158(Ghidra Decompiler 창 읽기)로 로직을 먼저 읽고, REV-0161로 이름을 정리.
- `Imports` 목록 자체에서 후보를 좁히는 전략이 궁금하다면 → REV-0164(Imports에서 검증 함수 후보 좁히기).
- 함수는 많은데 어디가 핵심 로직인지 감이 안 잡히면 → REV-0166(함수 Call Graph로 핵심 로직 좁히기).

## 미니 예제
CTF crackme를 Symbol Tree로 훑어보는 상황:

1. `Imports` 폴더를 펼치니 `strcmp`, `printf`, `scanf`, `exit`가 보인다.
2. `strcmp`를 더블클릭 → Listing이 Import thunk 위치로 이동.
3. 이 thunk에 XREF(참조하는 곳)가 딱 하나, `FUN_00401550`이라고 표시된 것을 확인(XREF 읽는 법은 REV-0160).
4. `FUN_00401550`을 더블클릭 → Decompile 창에 `strcmp(input, "S3cr3t_P4ss")` 비슷한 코드가 보인다.
5. 이 함수가 검증 로직의 핵심이라는 가설을 세우고, REV-0161로 `FUN_00401550`을 `check_password`처럼 의미 있는 이름으로 바꿔 이후 분석을 더 읽기 쉽게 만든다.

## 관련 글
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0160 — Ghidra XREF 따라가기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- ../triage/rev-0009-finding-main.md — main 함수 찾기(트리아지 관점)

## 출처/검증
- Symbol Tree 구성(Imports/Exports/Functions/Labels/Namespaces)과 Window → Functions 표 창: Ghidra 공식 Help 문서(Symbol Tree, Functions Window 관련 topic) 기준.
- 라이브 Ghidra 실행 화면을 직접 캡처해 재검증하지는 않았으며, 공식 문서와 널리 알려진 버전 동작을 기준으로 작성되었다.
