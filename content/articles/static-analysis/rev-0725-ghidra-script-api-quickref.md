---
id: REV-0725
title: "Ghidra 스크립트 API 빠른 참조(기초)"
slug: "rev-0725-ghidra-script-api-quickref"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Script Manager", "GhidraScript", "currentProgram", "FlatProgramAPI", "Ghidra Python 스크립트", "Ghidra Java 스크립트", "askString getFunctionAt"]
aliases: ["Ghidra 스크립트 작성법", "Ghidra 자동화 스크립트", "Ghidra Script Manager 사용법", "GhidraScript 기초"]
symptom_keywords: ["Ghidra에서 반복 작업을 자동화하고 싶음", "Ghidra 스크립트를 어떻게 짜는지 모름", "Script Manager 창이 뭔지 모름", "currentProgram이 뭔지 모름", "Ghidra Python으로 함수 목록을 뽑고 싶음"]
source_ids: ["SRC-GHIDRA-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra는 `Window → Script Manager`에서 Java 또는 Python(Jython 기반 구버전, 최신 버전은 PyGhidra/CPython 지원)으로 작성한 스크립트를 실행할 수 있으며, 스크립트 안에서는 `currentProgram`, `getFunctionAt()`, `getReferencesTo()` 같은 **FlatProgramAPI**(GhidraScript 기본 클래스가 제공하는 단순화된 API)를 통해 반복 작업(전체 함수 이름 일괄 변경, 문자열 일괄 추출 등)을 자동화할 수 있다.

## 언제 검색해야 하나
- 같은 종류의 이름 변경/타입 적용을 수십~수백 개 함수에 반복해야 해서 손으로 하기엔 너무 오래 걸릴 때
- 바이너리 안의 모든 문자열, 모든 함수 주소, 모든 xref를 한 번에 텍스트로 뽑아 별도 분석(Python 스크립트, grep 등)에 넘기고 싶을 때
- Ghidra Script Manager 창을 처음 열어봤는데 어떤 API로 시작해야 할지 모를 때
- 이미 REV-0724에서 만든 구조체를 특정 조건에 맞는 변수들에 스크립트로 일괄 적용하고 싶을 때

## 핵심 개념

### Script Manager
`Window → Script Manager`를 열면 카테고리별로 정리된 예제 스크립트 목록과, 사용자가 직접 만든 스크립트를 관리할 수 있는 창이 뜬다. 새 스크립트는 창 상단의 "새 스크립트 만들기" 아이콘으로 생성하며, 이때 언어(Java 또는 Python)를 선택한다. 만든 스크립트는 목록에서 더블클릭하거나 선택 후 실행 아이콘을 눌러 바로 실행할 수 있다.

### GhidraScript와 FlatProgramAPI
새로 만든 스크립트는 기본적으로 `GhidraScript`(Java) 클래스를 상속하며, 이 클래스가 **FlatProgramAPI**라는 단순화된 API 세트를 제공한다. FlatProgramAPI 덕분에 복잡한 내부 객체 구조를 몰라도 `getFunctionAt(addr)`, `getFirstFunction()`, `getReferencesTo(addr)`, `createLabel(addr, name, ...)` 같은 함수 호출 몇 줄로 대부분의 반복 작업을 처리할 수 있다.

### 자주 쓰는 진입점
- `currentProgram` — 지금 Ghidra에서 열려 있는 프로그램(바이너리) 객체. 거의 모든 스크립트의 출발점이다.
- `currentAddress` / `currentLocation` — 스크립트 실행 시점에 커서가 있던 위치.
- `getFunctionManager()` — 함수 목록 전체를 순회하는 `FunctionIterator`를 얻을 때 사용.
- `askString(title, message)` / `askAddress(...)` — 스크립트 실행 중 사용자에게 값을 입력받는 대화상자를 띄운다.
- `println(...)` — Script Manager의 콘솔 창에 결과를 출력한다. 디버깅 겸 결과 확인용으로 가장 많이 쓴다.

### Java와 Python 중 선택
Java 스크립트는 컴파일 후 실행되며 Ghidra 전체 API에 접근하기 가장 안정적이다. Python 스크립트는 문법이 간단해 짧은 자동화에 편하지만, Ghidra 버전에 따라 내부적으로 Jython(구버전, Python 2 문법 기반)을 쓰는지 최신 PyGhidra(CPython 기반)를 쓰는지가 달라 사용 가능한 라이브러리와 문법 세부사항이 다를 수 있다. 오프라인 환경에서는 대회 전에 어떤 Python 실행 방식이 설치되어 있는지 미리 확인해두는 것이 안전하다.

## 화면/코드에서 보이는 징후
"이 이름 변경 패턴을 함수 200개에 다 적용해야 하는데 하나씩 `L`을 누르기엔 너무 많다"거나, "문자열이 500개가 넘어서 Strings 창을 스크롤하는 것보다 텍스트로 한 번에 뽑고 싶다"는 상황이 스크립트를 쓸 신호다.

## 가장 먼저 할 것
`Window → Script Manager`를 열고, 예제 스크립트 카테고리(특히 `Examples`, `Functions` 등)에서 하고 싶은 작업과 비슷한 기존 스크립트가 있는지 먼저 찾아본다. 바닥부터 새로 짜기보다 예제를 수정하는 편이 훨씬 빠르다.

## 단계별 절차

**1) Script Manager 열기**

`Window → Script Manager`.

**2) 새 스크립트 생성**

상단의 새 스크립트 아이콘 클릭 → 언어(Java/Python) 선택 → 이름 지정.

**3) 기본 골격 작성**

```python
# Python (버전에 따라 Jython/CPython) 예시
def run():
    fm = currentProgram.getFunctionManager()
    for func in fm.getFunctions(True):
        println("%s @ %s" % (func.getName(), func.getEntryPoint()))

run()
```

**4) 실행 및 콘솔 확인**

Script Manager에서 스크립트를 선택하고 실행 아이콘을 누르면 Ghidra 콘솔 창에 `println` 결과가 출력된다.

**5) 결과를 실제 분석에 반영**

xref를 순회하며 특정 조건(예: 특정 임포트 함수 호출)에 맞는 함수 주소만 골라 리스트업하거나, 그 주소들에 자동으로 라벨/주석을 붙이는 식으로 확장한다.

## 명령어/단축키
| API/메뉴 | 동작 |
|---|---|
| `Window → Script Manager` | 스크립트 관리 창 열기 |
| `currentProgram` | 현재 열린 프로그램 객체 |
| `getFunctionManager().getFunctions(true)` | 전체 함수 순회(true=주소 오름차순) |
| `getReferencesTo(addr)` | 특정 주소를 참조하는 곳 목록(xref) |
| `askString(title, msg)` / `askAddress(title, msg)` | 실행 중 사용자 입력 받기 |
| `println(...)` | 콘솔에 출력 |
| `createLabel(addr, name, true)` | 지정 주소에 라벨(이름) 생성 |

## 출력 해석
- `println` 결과는 Script Manager 하단 콘솔에 시간순으로 쌓인다. 스크립트가 오래 걸리면 중간 진행 상황을 `println`으로 찍어두면 멈춘 것인지 진행 중인지 구분할 수 있다.
- 스크립트 실행 중 예외(에러)가 발생하면 콘솔에 Java 스택 트레이스가 그대로 출력된다 — 어떤 API 호출에서 실패했는지 그 트레이스의 맨 위 줄을 먼저 확인한다.
- 함수/주소를 못 찾아 `None`/`null`이 반환되는 경우가 흔하다 — API 호출 전에 항상 결과가 유효한지 확인하는 방어 코드를 넣는 습관이 필요하다.

## 흔한 실수
- Java와 Python(Jython/PyGhidra) 문법을 혼동해서 다른 언어 예제 코드를 그대로 붙여넣고 실행하는 것.
- `currentProgram`이 비어있는(아무 파일도 안 열린) 상태에서 스크립트를 실행해 널 포인터류 에러를 만나는 것.
- 대량의 이름 변경/라벨 생성 스크립트를 테스트 없이 전체 바이너리에 바로 실행해서, 잘못된 로직이면 되돌리기 번거로운 상태가 되는 것 — 먼저 소수의 함수에만 적용해 결과를 확인하고 확장하는 것이 안전하다.
- 오프라인 대회 환경에서 특정 Python 런타임(Jython vs CPython 기반)이 설치되어 있지 않아 스크립트가 아예 안 돌아가는 것을 대회 당일에야 알게 되는 것.

## 막혔을 때 다음 체크
- 스크립트로 만들 구조체/타입 자체를 어떻게 정의하는지 모르면 → REV-0724 Ghidra Data Type Manager 빠른 참조.
- xref 개념 자체가 헷갈리면 → REV-0160 Ghidra XREF 따라가기.
- 이름/타입을 수동으로 바꾸는 기본기가 부족하면 → REV-0161 Ghidra Rename과 Data Type 수정.
- Decompile 결과를 스크립트에서 함께 다루고 싶다면(더 고급) Ghidra 공식 문서의 Decompiler API 섹션을 별도로 참고해야 한다(본 문서는 기초 FlatProgramAPI만 다룬다).

## 미니 예제
```python
# 특정 이름 패턴을 가진 함수만 골라 콘솔에 출력
def run():
    fm = currentProgram.getFunctionManager()
    for func in fm.getFunctions(True):
        name = func.getName()
        if "check" in name or "verify" in name:
            println("candidate: %s @ %s" % (name, func.getEntryPoint()))

run()
```
검증/체크 로직으로 의심되는 함수 이름만 골라 빠르게 후보 목록을 만들 때 쓰는 최소 예제다.

## 관련 글
- REV-0724 — Ghidra Data Type Manager 빠른 참조
- REV-0160 — Ghidra XREF 따라가기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0158 — Ghidra Decompiler 창 읽기

## 출처/검증
- Script Manager 창, GhidraScript/FlatProgramAPI 개념, `currentProgram`/`getFunctionManager`/`getReferencesTo`/`askString`/`println` 등 API는 Ghidra 공식 문서(Ghidra API Javadoc, NationalSecurityAgency/ghidra 공식 저장소의 스크립팅 관련 문서)를 기준으로 정리했다(2026-09-09 검증).
- Python 스크립팅 실행 방식(Jython 기반 구버전 vs PyGhidra/CPython 기반 최신 버전)은 Ghidra 버전에 따라 다르므로, 실제 설치본에서 지원되는 Python 실행 방식을 먼저 확인할 것을 권장한다.
