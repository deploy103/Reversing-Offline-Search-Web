---
id: REV-0157
title: "Ghidra Auto Analysis 옵션"
slug: "rev-0157-ghidra-auto-analysis"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Auto Analysis", "Ghidra Analyze", "Ghidra 분석 옵션", "Decompiler Parameter ID", "Stack analyzer", "Function ID Ghidra"]
aliases: ["Ghidra 자동 분석", "Ghidra 분석 다시 돌리기", "Ghidra Analyze All"]
symptom_keywords: ["Ghidra 분석이 안 끝남", "Ghidra 함수가 안 잡힘", "Ghidra 분석 다시 해야 함", "Ghidra Auto Analyze 창이 뭔지 모름"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Ghidra의 Auto Analysis는 Import된 바이너리에 **함수 경계 인식, 문자열 추출, 참조(XREF) 계산, 스택 프레임 분석, 라이브러리 함수 식별 등 수십 개의 개별 Analyzer를 순차 실행**하는 과정이며, 이 결과가 부실하면 이후 Symbol Tree와 Decompiler가 보여주는 모든 정보의 품질이 함께 떨어진다.

## 언제 검색해야 하나
- CodeBrowser로 파일을 처음 열었을 때 "Analyze <파일명>?" 대화상자가 떠서 무엇을 선택해야 할지 모를 때
- Auto Analysis Options 창에 체크박스가 잔뜩 나와서 뭘 켜고 꺼야 할지 모를 때
- 분석이 끝났는데도 함수가 거의 안 잡히거나, 문자열 창(Defined Strings)이 텅 비어 있을 때
- 코드를 수동으로 많이 고친 뒤 "다시 분석"이 필요할 때

## 핵심 개념
Ghidra는 하나의 거대한 분석기가 아니라, **Analyzer라는 이름의 독립된 분석 모듈들의 모음**을 순서대로(또는 서로의 결과에 의존하며) 실행하는 구조다. CodeBrowser로 파일을 처음 열면 "Would you like to analyze it now?"라고 묻는데, **Yes**를 누르면 "Analysis Options" 창이 뜨고, 여기서 어떤 Analyzer를 켤지 고를 수 있다.

대표적인 Analyzer들:
- **ASCII Strings**: 메모리에서 출력 가능한 ASCII/유니코드 문자열을 찾아 Defined Data로 등록한다. 이후 문자열 창과 문자열 XREF가 여기서 나온다.
- **Disassemble Entry Points**: entry point와 알려진 코드 시작점부터 디스어셈블을 시작한다.
- **Function Start Search / Function ID**: 코드 패턴을 보고 함수 시작 위치를 추정하거나, 알려진 라이브러리 함수 시그니처(FID 데이터베이스)와 비교해 이름을 자동으로 붙인다(예: statically linked된 `printf` 계열 함수 식별).
- **Stack**: 각 함수의 스택 프레임(지역 변수, 인자)이 어느 스택 오프셋에 있는지 계산한다. IDA의 SP-analysis와 비슷한 역할이며, 잘못되면 지역 변수 표시가 엉망이 된다.
- **Decompiler Switch Analysis / Decompiler Parameter ID**: 디컴파일러를 실제로 돌려서 switch-case 점프 테이블을 해석하거나 함수 인자 개수/타입을 추정한다. 이 두 Analyzer는 디컴파일러를 내부적으로 호출하기 때문에 느리다.
- **Demangler (GNU/Microsoft)**: C++ mangled name(`_Z...`, `?...@@...`)을 사람이 읽을 수 있는 형태(`ClassName::MethodName(int)`)로 복원한다.
- **Non-Returning Functions - Discovered/Known**: `exit`, `abort`, `_CRT_error` 같은 함수를 "리턴하지 않는 함수"로 표시해서, 그 뒤에 이어지는 바이트를 코드로 잘못 해석하지 않도록 막는다.
- **Windows x86 PE Exception Handling / DWARF**: PE의 SEH나 ELF의 DWARF 디버그 정보가 있으면 함수 경계와 타입 정보를 더 정확히 복원한다.

이 Analyzer들은 서로 순서와 의존성이 있다. 예를 들어 함수 경계가 먼저 잡혀야 Stack 분석이 의미 있고, Stack 분석이 끝나야 Decompiler Parameter ID가 정확한 인자 개수를 추정할 수 있다. 그래서 Auto Analysis는 보통 한 번에 끝나지 않고 몇 차례 반복 수렴하며 실행된다.

## 화면/코드에서 보이는 징후
- CodeBrowser에서 파일을 처음 열면 "Auto Analysis?" 확인 대화상자가 뜬다.
- 분석 진행 중에는 화면 하단에 진행률 표시줄과 현재 실행 중인 Analyzer 이름이 표시된다.
- 분석이 끝나면 Symbol Tree의 Functions 폴더에 다수의 `FUN_xxxxxxxx` 함수와, 라이브러리에서 식별된 경우 실제 함수 이름(`printf`, `strcmp` 등)이 채워진다.

## 가장 먼저 할 것
처음 Import한 파일이라면 "Analyze?" 대화상자에서 **Yes**를 눌러 기본 옵션 그대로 한 번 전체 분석을 돌린다. 이미 분석이 끝난 파일에서 특정 영역만 다시 분석하고 싶다면 **Analysis 메뉴 → Auto Analyze '<파일명>'...**을 다시 연다.

## 단계별 절차

**1) 최초 분석 실행**

CodeBrowser가 열리며 뜨는 "Would you like to analyze it now?" 대화상자에서 **Yes**를 선택한다.

**2) Analysis Options 창 확인**

체크박스 목록이 있는 "Analysis Options" 창이 뜬다. 항목을 클릭하면 오른쪽에 해당 Analyzer의 설명과 우선순위(priority)가 표시된다. CTF/워게임용 일반 바이너리라면 기본값(대부분 체크되어 있음)을 그대로 두고 **Analyze**를 눌러도 충분하다.

**3) 시간이 오래 걸리는 Analyzer 선택적으로 끄기(선택 사항)**

바이너리가 매우 크거나 1차 훑어보기만 빠르게 하고 싶다면 **Decompiler Switch Analysis**, **Decompiler Parameter ID**처럼 디컴파일러를 직접 호출하는 무거운 Analyzer를 일단 꺼서 1차 분석을 빠르게 끝낸 뒤, 필요할 때 특정 함수만 다시 분석하는 전략도 가능하다.

**4) 분석 완료 대기**

분석 중에는 CodeBrowser 하단 상태 바에 진행 상황이 표시된다. 바이너리 크기에 따라 수 초에서 수 분까지 걸릴 수 있다. 이 시간 동안 다른 창을 조작해도 대부분 문제없지만, 분석이 끝나기 전에는 함수 목록/문자열/XREF가 불완전하므로 판단을 유보하는 것이 안전하다.

**5) 필요 시 재분석**

수동으로 함수 경계를 고치거나(Undefine 후 다시 Create Function), 새 데이터 타입을 정의한 뒤에는 그 영향을 반영하기 위해 **Analysis → Auto Analyze '<파일명>'...**을 다시 실행해 전체 또는 일부 Analyzer를 재실행할 수 있다. 특정 함수 하나만 다시 분석하고 싶다면 그 함수를 Undefine(단축키 없음, 메뉴 Edit → Undefine 또는 우클릭)한 뒤 다시 Create Function으로 잡는 방법도 있다.

**6) One Shot 분석**

전체 재분석이 아니라 특정 Analyzer 하나만 지금 이 순간 실행하고 싶다면 **Analysis** 메뉴 아래에 개별 Analyzer가 "One Shot" 항목으로 나열되어 있어(예: ASCII Strings를 지금 바로 다시 돌리기) 그중 하나를 선택해 실행할 수 있다.

## 명령어/단축키
- 분석 옵션 다시 열기: **Analysis → Auto Analyze '<파일명>'...**
- 개별 Analyzer 즉시 실행: **Analysis** 메뉴의 One Shot 항목들
- 함수 재정의: 우클릭 → **Clear Code Bytes**(또는 Undefine) 후 커서를 시작 주소에 놓고 우클릭 → **Create Function**
- 진행 상황: CodeBrowser 하단 상태 바(Status bar)

## 출력 해석
- Symbol Tree의 Functions 폴더에 이름이 `FUN_00401230`처럼 나오는 함수는 "라이브러리로 식별되지 않은, 이 바이너리 고유의 코드"라는 뜻이다. 반대로 `printf`, `strcmp`처럼 실제 이름이 붙어 있으면 Function ID Analyzer가 알려진 라이브러리 함수 시그니처와 매칭에 성공했다는 뜻이다.
- 분석 로그(Analysis Options 창 하단 또는 Console 창 유사 로그)에 특정 Analyzer가 오류를 냈다는 메시지가 남을 수 있는데, 이는 IDA의 Output window 경고와 비슷한 역할을 한다. 특히 Stack 관련 Analyzer가 실패하면 IDA의 "positive sp value" 경고(rev-0151-positive-sp-value.md 참고)와 유사하게 그 함수의 지역 변수 오프셋이 신뢰할 수 없어진다.

## 흔한 실수
- Auto Analysis가 끝나기도 전에 함수 목록이 비어 있다고 판단해서 파일이 잘못됐다고 오해하는 것 — 분석 진행 중에는 결과가 계속 채워지는 중이므로 상태 바가 "완료"로 바뀔 때까지 기다려야 한다.
- 모든 Analyzer를 습관적으로 다 꺼버리고 "빠른 확인"만 하다가, 정작 XREF/문자열/함수 경계가 하나도 없는 상태로 디컴파일 결과를 신뢰하는 것.
- 수동으로 코드를 대거 수정한 뒤 재분석을 한 번도 하지 않아서, Symbol Tree/Decompiler가 옛날 정보를 계속 보여주는 것을 눈치채지 못하는 것.
- 패킹된 바이너리에 Auto Analysis를 그대로 돌리고 "함수가 왜 이렇게 적지"라고 헤매는 것 — 언패킹 전 스텁 코드만 분석 대상이 되므로 결과가 빈약한 게 정상이다.

## 막혔을 때 다음 체크
- 분석은 끝났는데 진입점 근처 코드가 이상하다면 → REV-0158(Ghidra Decompiler 창 읽기)에서 디컴파일 결과 읽는 법 확인.
- 원하는 함수를 목록에서 못 찾겠다면 → REV-0159(Ghidra Function 목록과 Symbol Tree).
- 문자열은 보이는데 그 문자열을 쓰는 함수로 어떻게 가는지 모르겠다면 → REV-0163(문자열에서 검증 함수로 이동하는 정적 분석).
- 특정 함수의 스택 프레임이 깨져 보인다면 → IDA의 동일 증상 문서인 rev-0151-positive-sp-value.md의 원인 설명(호출 규약 오판, 함수 원형 오판)이 Ghidra의 Stack Analyzer 실패 원인과 근본적으로 같은 개념이니 참고.

## 미니 예제
32비트 PE `crackme.exe`를 Import 직후 처음 여는 상황을 가정한다.

1. CodeBrowser가 열리며 "Would you like to analyze crackme.exe now?" 대화상자가 뜬다 → **Yes**.
2. Analysis Options 창에서 기본 체크 상태 그대로 **Analyze** 클릭.
3. 하단 상태 바에 "Analyzing crackme.exe... ASCII Strings" → "... Stack" → "... Decompiler Switch Analysis" 순으로 진행률이 바뀌는 것을 관찰.
4. 완료 후 Symbol Tree → Functions를 펼치면 `entry`, `FUN_00401000`, `strcmp`(라이브러리 식별됨) 등이 나열된 것을 확인.
5. 나중에 함수 하나의 경계를 수동으로 다시 잡았다면, Analysis 메뉴에서 재분석을 한 번 더 돌려 Stack/Decompiler 관련 정보를 최신 상태로 갱신한다.

## 관련 글
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- rev-0151-positive-sp-value.md — 스택 분석이 틀렸을 때 나타나는 증상(IDA 사례, 개념은 Ghidra Stack Analyzer와 동일)

## 출처/검증
- Auto Analysis 대화상자 흐름("Analyze now?" → Options → 진행률 표시)과 대표 Analyzer 목록(ASCII Strings, Stack, Decompiler Switch Analysis, Decompiler Parameter ID, Function ID, Non-Returning Functions 등): Ghidra 공식 Help 문서(AutoAnalysisPlugin 토픽) 및 Ghidra 소스 저장소의 Analyzer 설명 문자열 기준.
- 이 문서는 라이브 Ghidra 실행 화면을 직접 캡처해 재검증하지 않았으며, 공식 문서와 널리 통용되는 버전의 UI 구성을 기준으로 작성되었다. 실제 설치된 Ghidra 버전에 따라 일부 Analyzer 이름/기본 On-Off 상태는 다를 수 있다.
