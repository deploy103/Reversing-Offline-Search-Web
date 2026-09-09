---
id: REV-0787
title: "Ghidra 스크립트 실행이 오류로 멈출 때"
slug: "rev-0787-ghidra-script-execution-error"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Script Manager 오류", "Ghidra 스크립트 예외", "Ghidra Console 에러", "GhidraScript exception", "Ghidra Python 스크립트 실패"]
aliases: ["Ghidra 스크립트가 멈춤", "Ghidra Script Manager 빨간 에러", "Ghidra 스크립트 실행 중 exception"]
symptom_keywords: ["Ghidra 스크립트 실행 중 빨간 글씨 에러", "Ghidra Console에 stack trace가 뜸", "Ghidra 스크립트가 도중에 멈춤", "Ghidra 스크립트 컴파일 에러"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra 스크립트(Java/Jython 기반 GhidraScript)가 실행 중 멈추는 것은 대부분 **스크립트 코드 자체의 예외(NullPointerException 등)이거나, 현재 커서/선택 상태가 스크립트가 기대하는 조건(함수 위에 커서가 있어야 함 등)과 맞지 않기 때문**이며, `Console` 창에 출력되는 스택 트레이스의 맨 위 줄과 스크립트 소스의 해당 줄을 대조하면 원인을 빠르게 좁힐 수 있다.

## 언제 검색해야 하나
- Script Manager에서 스크립트를 실행했는데 도중에 멈추고 Console 창에 빨간 글씨 에러가 뜰 때
- 직접 작성한 GhidraScript가 컴파일 단계에서부터 실패할 때
- 예제 스크립트를 그대로 실행했는데도 특정 함수/커서 상태에 따라 실패할 때
- 스크립트가 특정 바이너리에서는 되는데 다른 바이너리에서는 예외를 던질 때

## 핵심 개념
Ghidra의 스크립트는 Script Manager(`Window → Script Manager`)를 통해 실행되며, Java 또는 Jython(Python 2 문법) 기반 GhidraScript API로 작성된다. 실행 흐름과 실패 지점을 이해하려면 다음을 알아야 한다.

1. **컴파일 단계 vs 실행 단계**: Java 스크립트는 실행 전에 먼저 컴파일된다. 이 단계에서 문법 오류가 있으면 "실행이 멈춘 것"이 아니라 애초에 시작도 못 한 것이며, Console에 컴파일 에러 메시지가 뜬다. 실행 단계 실패는 컴파일은 성공했지만 런타임에 예외가 발생한 경우다.
2. **API가 요구하는 전제 조건**: 많은 GhidraScript API(`getFunctionContaining(currentAddress)` 등)는 "현재 커서가 유효한 함수/주소 위에 있음"을 가정한다. 커서가 데이터 영역이나 함수 밖에 있으면 `null`을 반환하고, 이를 그대로 사용하면 `NullPointerException`이 발생한다.
3. **Undo 트랜잭션 관련 오류**: 프로그램을 수정하는 스크립트는 내부적으로 트랜잭션을 열어야 하는데, 이미 다른 트랜잭션이 열려 있거나 스크립트가 트랜잭션을 제대로 닫지 못하면 관련 예외가 발생할 수 있다.
4. **Headless 모드와 GUI 모드의 차이**: Script Manager에서 GUI로 실행할 때와 `analyzeHeadless`로 배치 실행할 때는 `currentProgram`, `currentAddress` 같은 컨텍스트 변수의 초기값이 다르므로, GUI 전용 로직(예: 팝업 대화상자)이 Headless에서 예외를 낼 수 있다.
5. **스크립트 자체의 로직 버그**: 배열 인덱스 초과, 잘못된 캐스팅 등 일반적인 프로그래밍 오류도 물론 흔한 원인이다.

## 화면/코드에서 보이는 징후
- `Window → Console` 창에 빨간색으로 예외 이름(`java.lang.NullPointerException` 등)과 스택 트레이스가 여러 줄 출력된다.
- Script Manager의 실행 버튼(초록 삼각형)을 눌렀는데 진행바가 잠깐 뜨다가 바로 사라지고 아무 결과도 없다.
- 스크립트 편집기(Eclipse 플러그인 또는 내장 에디터)에서 저장 시 빨간 밑줄로 컴파일 오류가 표시된다.

## 가장 먼저 할 것
Console 창을 열어 스택 트레이스의 **맨 위 줄**(가장 구체적인 예외 발생 지점)과 **스크립트 이름 옆에 표시된 줄 번호**부터 확인한다. 대부분 그 줄이 바로 문제의 원인이다.

## 단계별 절차

**1) Console 창 열기 및 스택 트레이스 확인**

`Window → Console`을 열어 방금 실행 결과를 스크롤해 확인한다. 예외 클래스 이름(`NullPointerException`, `ArrayIndexOutOfBoundsException` 등)과 그 아래 나열된 파일명:줄번호 목록을 본다.

**2) 내 스크립트 코드가 언급된 줄 찾기**

스택 트레이스에서 Ghidra 내부 API 클래스가 아니라 **자신이 작성한 스크립트 파일명**이 나오는 줄을 찾는다. 그 줄 번호가 실제 문제가 발생한 위치다.

**3) 그 줄에서 사용한 API의 전제 조건 확인**

해당 줄에서 `null`이 반환될 수 있는 API(`getFunctionAt`, `getFunctionContaining`, `getSymbol` 등)를 쓰고 있다면, 호출 직후 `null` 체크를 추가했는지 확인한다. 커서 위치나 선택 영역이 스크립트가 기대하는 상태(예: 함수 안)인지도 함께 점검한다.

**4) 컴파일 오류라면 문법부터 재확인**

실행 버튼을 누르자마자 실행 자체가 안 되고 에디터에 빨간 밑줄이 있다면, 괄호/세미콜론 누락, import 누락 같은 기본 문법 오류부터 확인한다. Jython 스크립트라면 Python 2 문법(예: `print` 문 형태, 들여쓰기)을 따르고 있는지도 확인한다.

**5) 최소 재현으로 좁히기**

스크립트가 길다면, 문제가 되는 부분만 남기고 나머지를 주석 처리한 뒤 다시 실행해 어느 블록에서 예외가 나는지 이분법으로 좁힌다.

**6) 트랜잭션 관련 오류라면 API 사용 패턴 재확인**

프로그램을 수정하는 스크립트에서 트랜잭션 관련 예외가 난다면, `GhidraScript`가 기본 제공하는 `start()`/`end()` 또는 자동 트랜잭션 처리 방식을 그대로 쓰고 있는지, 직접 트랜잭션을 열고 제대로 닫는지(try/finally) 확인한다.

**7) Headless 모드 문제라면 GUI 전용 호출 제거**

`analyzeHeadless`로 실행할 스크립트에서는 `askString`, `askYesNo` 같은 사용자 입력을 받는 GUI 전용 API 대신 명령줄 인자나 고정값을 쓰도록 수정한다.

## 명령어/단축키
```text
Window → Script Manager        스크립트 목록/실행/편집 진입점
Window → Console                실행 로그와 예외 스택 트레이스 확인
Script Manager 상단 초록 삼각형   선택한 스크립트 실행
Script Manager 상단 편집 아이콘   스크립트 소스 편집(내장 에디터/Eclipse 연동)
```

## 출력 해석
- 스택 트레이스 맨 위 줄이 `NullPointerException`이고 그 아래 자신의 스크립트 파일명이 바로 나오면, 그 줄에서 사용한 API가 `null`을 돌려줬다는 뜻이다.
- 컴파일 에러 메시지에 `cannot find symbol` 또는 `';' expected` 같은 문구가 있으면 Java 문법 오류이며, 줄 번호가 함께 표시되므로 그 줄부터 확인한다.
- 예외 없이 스크립트가 조용히 끝났는데 기대한 결과가 안 보이면, 예외가 아니라 로직 자체가 조건을 못 만족한 것일 수 있으니 중간중간 `println()`으로 값을 출력해 확인한다.

## 흔한 실수
- Console 창을 확인하지 않고 "스크립트가 멈췄다"고만 판단해 원인을 못 찾는 것 — 대부분 Console에 정확한 원인이 이미 출력되어 있다.
- 커서를 함수 밖에 둔 채로 "현재 함수를 대상으로" 동작하는 스크립트를 실행해 `null` 관련 예외를 겪는 것.
- Python 2 문법(Jython)과 Python 3 문법을 혼동해서 `print` 사용법이나 문자열 처리에서 오류를 겪는 것.
- 트랜잭션을 열어놓고 예외 발생 시 닫지 않아, 다음 실행에서 "이미 트랜잭션이 열려 있다"는 연쇄 오류를 겪는 것.

## 막혔을 때 다음 체크
- 스크립트로 이름을 바꾸거나 타입을 수정하려는 것이라면 수동 방법과 비교해 → REV-0161.
- 스크립트가 xref/call graph 관련 API를 쓰고 있다면 개념 확인용으로 → REV-0160, REV-0166.
- 분석 자체(Auto Analysis)가 아직 안 끝난 상태에서 스크립트를 돌려 API가 불완전한 결과를 돌려주는 것이라면 → REV-0781.

## 미니 예제
현재 함수의 이름을 출력하는 간단한 Jython 스크립트를 실행하다가 예외를 만난 상황이다.

```python
func = getFunctionContaining(currentAddress)
print(func.getName())
```

1. 커서를 데이터 영역(문자열) 위에 두고 스크립트를 실행하면 Console에 `NullPointerException`이 뜬다.
2. 스택 트레이스 맨 위에 자신의 스크립트 파일명과 `print(func.getName())` 줄 번호가 나온다.
3. `getFunctionContaining`이 함수가 아닌 위치에서는 `None`(null)을 반환한다는 것을 확인.
4. 코드를 아래처럼 방어적으로 수정한다.

```python
func = getFunctionContaining(currentAddress)
if func is None:
    print("Cursor is not inside a function")
else:
    print(func.getName())
```

5. 함수 안에 커서를 두고 다시 실행하면 정상적으로 함수 이름이 출력된다.

## 관련 글
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- REV-0781 — Ghidra Auto Analysis가 끝나지 않을 때

## 출처/검증
- Script Manager/Console 창의 역할, GhidraScript가 Java/Jython으로 작성되며 컴파일 단계와 실행 단계가 분리되어 있다는 점: Ghidra 공식 개발자 문서(`GhidraScript` API Javadoc 및 공식 Help 문서의 Script Manager 토픽) 기준.
- `getFunctionContaining` 등 다수의 조회 API가 대상이 없을 때 `null`을 반환한다는 규약: Ghidra 공식 Flat API(`FlatProgramAPI`) Javadoc 기준.
- 이 문서는 특정 스크립트의 실제 실행을 재현 검증하지 않았으며, 공식 API 문서와 일반적인 자바/자이썬 예외 처리 원칙을 바탕으로 정리했다.
