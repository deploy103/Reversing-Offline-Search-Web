---
id: REV-0743
title: "Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초"
slug: "rev-0743-ghidra-scripting-python-java-basics"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Script Manager", "GhidraScript", "Ghidra Python 스크립트", "Ghidrathon", "Jython", "Ghidra 자동화"]
aliases: ["Ghidra 자동화 스크립트", "Ghidra 파이썬 스크립팅", "Ghidra 스크립트 매니저 사용법"]
symptom_keywords: ["Ghidra에서 함수 이름을 한번에 바꾸고 싶다", "Ghidra Script Manager 여는 법", "Ghidra 파이썬으로 자동화", "Ghidra 반복 작업 스크립트로 처리"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Script Manager는 Jython(내장) 또는 Java, 그리고 확장을 설치하면 실제 Python3(Ghidrathon)로 `currentProgram`, `FunctionManager`, `SymbolTable` 같은 API를 다뤄 이름 바꾸기·주석 달기 같은 반복 작업을 프로그램 전체에 자동으로 적용하게 해준다.

## 언제 검색해야 하나
- 같은 패턴(예: `FUN_`으로 시작하는 미분석 함수)을 여러 개 반복해서 손으로 이름 바꾸고 있을 때
- CTF에서 같은 종류의 바이너리 여러 개를 매번 같은 방식으로 분석해야 할 때
- Ghidra Script Manager 창을 열었는데 어디서부터 시작해야 할지 모를 때
- IDAPython처럼 Ghidra에도 스크립팅 API가 있는지 궁금할 때

## 핵심 개념

### Script Manager 열기
Window → Script Manager(또는 CodeBrowser 툴바의 스크립트 아이콘)로 연다. 카테고리 트리에 기본 제공 예제 스크립트(Examples, Analysis 등)가 다수 들어 있어 처음 시작할 때 좋은 참고 자료가 된다.

### Jython vs Ghidrathon(Python3)
Ghidra는 기본적으로 Jython(JVM 위에서 동작하는 파이썬 2 계열 구현)을 내장 스크립트 언어로 제공한다. 최신 파이썬 라이브러리(예: 순수 C 확장 기반 패키지)를 못 쓰는 한계가 있어, 커뮤니티 확장인 Ghidrathon을 설치하면 실제 CPython3 인터프리터를 붙여 쓸 수 있다(오프라인 환경이면 설치 파일과 의존 패키지를 미리 받아둬야 한다). Java로도 스크립트를 작성할 수 있으며, GhidraDev 플러그인을 Eclipse에 연결하면 더 편하게 개발할 수 있다.

### GhidraScript API 핵심 객체
스크립트 안에서 바로 쓸 수 있는 전역 변수/메서드가 있다.
- `currentProgram`: 현재 열린 Program 객체
- `currentAddress` / `currentLocation`: 커서 위치
- `getFunctionManager()`: 함수 목록 조회/생성
- `getSymbolTable()`: 심볼 조회/생성
- `askString` / `askAddress` / `askYesNo`: 사용자 입력을 받는 GUI 대화상자
- `println`: Console 창에 출력

### 새 스크립트 만들기
Script Manager 툴바의 Create New Script(+) 아이콘 → 언어(Java/Python) 선택 → 카테고리와 파일명 입력하면, 기본 템플릿(주석 헤더 + `run()` 메서드 뼈대)이 담긴 편집기가 열린다.

### 반복 작업 자동화 예시 - 패턴 이름 일괄 변경
```python
# Jython 예시: FUN_ 로 시작하는 함수 이름을 sub_ 접두사로 통일
fm = currentProgram.getFunctionManager()
funcs = fm.getFunctions(True)
count = 0
for f in funcs:
    if f.getName().startswith("FUN_"):
        addr = f.getEntryPoint()
        newName = "sub_" + addr.toString()
        f.setName(newName, ghidra.program.model.symbol.SourceType.USER_DEFINED)
        count += 1
println("renamed %d functions" % count)
```
실제로는 여기에 조건(문자열 참조 여부, 호출 횟수, 함수 크기 등)을 추가해 원하는 함수만 골라 처리하도록 확장한다.

### 실행 방법
Script Manager 목록에서 스크립트를 더블클릭하면 즉시 실행되고, 출력은 Window → Console 창에 나타난다. 반복 실행할 스크립트는 즐겨찾기(별 아이콘)로 등록해 두면 다음에 빨리 찾을 수 있다.

## 화면/코드에서 보이는 징후
같은 종류의 rename/comment 작업을 여러 함수에 반복해서 손으로 하고 있거나, CTF에서 같은 패턴의 바이너리 여러 개를 매번 같은 방식으로 분석하고 있을 때.

## 가장 먼저 할 것
Script Manager를 열어 Examples 카테고리의 기존 스크립트 하나를 읽어보며 API 스타일에 먼저 익숙해진다.

## 단계별 절차
1. Window → Script Manager 열기
2. Examples 카테고리에서 비슷한 목적의 기존 스크립트를 검색창 키워드로 찾기
3. Create New Script(+) 아이콘으로 새 스크립트 생성, 언어 선택
4. `FunctionManager`/`SymbolTable` 등 필요한 API로 로직 작성
5. 더블클릭 실행, Console에서 결과 확인
6. 잘 동작하면 오프라인 키트에 스크립트 파일 보관, 다음 프로젝트에서 재사용

## 명령어/단축키
- Window → Script Manager
- 새 스크립트: Script Manager 툴바 `+` 아이콘
- 즐겨찾기 등록: 스크립트 목록의 별 아이콘 토글
- 출력 확인: Window → Console

## 출력 해석
Console에 예외 스택 트레이스가 나오면 대부분 API 객체가 `None`이거나(예: `currentProgram`이 없는 상태에서 실행) 타입 캐스팅 오류다. 스택 트레이스의 라인 번호를 보고 어느 API 호출에서 실패했는지 먼저 확인한다.

## 흔한 실수
- Jython 문법을 Python3처럼 쓰다가 `print` 문법/문자열 포맷 오류가 나는 것.
- 프로그램을 통째로 순회하는 스크립트를 트랜잭션(되돌리기 단위) 고려 없이 실행해, 잘못됐을 때 되돌리기 어려워지는 것 — 큰 변경 전에는 프로젝트 백업을 권장한다.
- `askString` 같은 GUI 대화상자를 배치 실행 환경에서 사용해 자동화가 중간에 멈추는 것.

## 막혔을 때 다음 체크
- 두 바이너리를 자동으로 비교하고 싶으면 → REV-0744 Ghidra Version Tracking으로 두 바이너리 비교하기
- 반복 작업 대신 구조체를 임포트해서 문제를 해결하고 싶으면 → REV-0742 Ghidra Data Type Manager로 구조체 임포트/정의하기
- P-code를 스크립트에서 직접 다루고 싶으면 → REV-0745 Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)
- IDA의 IDAPython과 비교하고 싶으면 → REV-0147 IDA 함수 변수 이름 N으로 바꾸기

## 미니 예제
위 코드 스니펫을 `RenameFunPrefix.py`로 저장하고 Script Manager에서 실행하면, 프로그램 안의 모든 `FUN_xxxxx` 함수가 `sub_xxxxx`로 바뀌고 Console에 `renamed N functions`가 출력된다.

## 관련 글
- REV-0742 — Ghidra Data Type Manager로 구조체 임포트/정의하기
- REV-0744 — Ghidra Version Tracking으로 두 바이너리 비교하기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0745 — Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)

## 출처/검증
Ghidra 공식 Developer Guide 및 GhidraScript API 문서, Ghidrathon 공식 저장소 문서 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서 기준 API 이름과 메뉴 경로로 작성했다(2026-09-09).
