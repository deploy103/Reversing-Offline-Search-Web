---
id: REV-0742
title: "Ghidra Data Type Manager로 구조체 임포트/정의하기"
slug: "rev-0742-ghidra-data-type-manager-struct-import"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Data Type Manager", "Ghidra gdt 파일", "Ghidra Parse C Source", "Ghidra 구조체 임포트", "Ghidra Type Archive"]
aliases: ["Ghidra 구조체 가져오기", "Ghidra 헤더 파일 파싱", "Ghidra 타입 아카이브 만들기"]
symptom_keywords: ["Ghidra에 구조체 정의를 어떻게 넣나", "Ghidra 헤더 파일 임포트하는 법", "Ghidra gdt 파일이 뭔가", "Ghidra 여러 바이너리에서 같은 구조체 재사용"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra의 Data Type Manager는 프로그램마다 흩어져 있는 구조체/열거형/typedef 정의를 `.gdt`(Ghidra Data Type Archive) 단위로 저장하고 여러 프로젝트에서 재사용하게 해주는 창으로, C 헤더 파일을 직접 파싱(Parse C Source)하거나 다른 곳에서 만든 `.gdt`를 열어(Open File Archive) 구조체를 그대로 가져올 수 있다.

## 언제 검색해야 하나
- 같은 라이브러리를 여러 바이너리에서 반복 분석할 때 구조체를 매번 새로 만들기 귀찮을 때
- 공개된 헤더 파일(`.h`)이 있는데 그 구조체 정의를 Ghidra 안에 그대로 넣고 싶을 때
- 팀원이 만든 구조체 정의를 오프라인 상태로 공유하고 싶을 때
- Data Type Manager 창을 어떻게 열고 어디서 구조체를 찾는지 모를 때

## 핵심 개념

### Data Type Manager 창 열기
Window → Data Type Manager 메뉴로 연다. 기본적으로 CodeBrowser 좌측 하단 탭에 있으며, 트리 최상단에 Built In Types, 현재 프로그램 이름(예: `chall.exe`), 그리고 로드된 외부 Archive들이 나열된다.

### Type Archive vs 프로그램 안의 타입
Ghidra는 구조체를 두 군데 저장할 수 있다. 하나는 현재 열려 있는 프로그램 자체의 데이터베이스 안이고, 다른 하나는 프로그램과 독립적으로 존재하는 `.gdt` 파일이다. `.gdt`는 재사용 가능한 타입 라이브러리로, Data Type Manager 툴바의 New File Archive 아이콘으로 새로 만들거나, Open File Archive로 기존 것을 열 수 있다.

### C 헤더 파일 파싱(Parse C Source)
Data Type Manager 우측 상단 또는 File 메뉴의 Parse C Source를 실행하면 `.h` 파일을 선택해 구조체/typedef/enum을 한 번에 임포트할 수 있다. 파싱 전에 Parse Configuration에서 매크로 정의(`#define`), include 경로, 사용할 파서 프로파일(표준 clib, windows.h 관련 기본 프로파일 등)을 지정해야 하며, 프로파일이 안 맞으면 파싱 에러가 무더기로 난다. 결과는 지정한 Archive(또는 새로 만든 Archive)에 저장된다.

### 다른 프로젝트에서 만든 `.gdt` 임포트
Data Type Manager 툴바의 Open File Archive 아이콘으로 다른 곳에서 만든 `.gdt` 파일을 그대로 불러올 수 있다. 팀원이 미리 만들어 둔 `.gdt`를 오프라인 USB로 전달받아 열기만 하면, 그 안의 모든 구조체/enum이 트리에 나타난다. 이후 구조체를 실제 변수에 적용하려면 트리에서 구조체를 확인한 뒤, 변수 위에서 `Ctrl+L`(Retype Variable)로 구조체 이름을 입력한다.

### 구조체 자체를 직접 만들기
빈 구조체는 프로그램 노드나 Archive 노드 우클릭 → New → Structure로 만들고, Structure Editor에서 필드를 오프셋/타입/이름 순으로 채운다. 필드 사이 패딩(정렬)은 Structure Editor 하단 Component 목록에서 자동 계산되며, Align 옵션을 켜면 컴파일러 정렬 규칙을 흉내낼 수 있다.

### Export - 만든 구조체를 다시 파일로
Archive를 우클릭해 Export하면 지금까지 만든 구조체를 다시 `.gdt`로 내보낼 수 있다. 이렇게 만든 `.gdt`를 오프라인 키트에 보관해 두면 다음 분석 세션이나 다른 팀원에게 그대로 재사용시킬 수 있다.

## 화면/코드에서 보이는 징후
Decompile 창에 `undefined4 field_0x4`처럼 알 수 없는 필드가 반복해서 보이거나, 여러 바이너리에서 매번 같은 구조체를 손으로 다시 그리고 있을 때.

## 가장 먼저 할 것
Window → Data Type Manager를 열어 현재 이미 로드된 Archive 목록부터 확인한다(기본 제공되는 `generic_clib*`, `windows_vs*` 등의 Archive가 이미 있을 수 있다).

## 단계별 절차
1. Window → Data Type Manager 열기
2. 새 Archive 만들기: 툴바 New File Archive 아이콘 → 저장 경로 지정 → 이름 입력
3. 헤더로 임포트: File → Parse C Source → 헤더 파일 선택 → Parse Configuration에서 매크로/include 경로 확인 → 파싱 실행
4. 기존 `.gdt` 임포트: 툴바 Open File Archive 아이콘 → `.gdt` 파일 선택
5. 구조체 적용: 대상 변수 위 `Ctrl+L` → 구조체 이름 입력(포인터면 `구조체이름 *`)
6. 만든 구조체 내보내기: Archive 우클릭 → Export

## 명령어/단축키
- Window → Data Type Manager
- New File Archive / Open File Archive 툴바 아이콘
- File → Parse C Source
- 구조체 적용: `Ctrl+L`(Retype Variable)
- 구조체 만들기: 우클릭 → New → Structure

## 출력 해석
파싱 후 에러 로그 창에 파싱 에러가 여러 줄 나오면 include 경로나 매크로가 빠진 것이다. 핵심 구조체가 정상적으로 만들어졌다면 나머지 파싱 에러(관계없는 매크로 등)는 무시해도 되는 경우가 많지만, 필요한 구조체 자체가 안 만들어졌다면 Parse Configuration을 다시 확인해야 한다.

## 흔한 실수
- Parse Configuration에서 프로파일을 잘못 골라(예: Windows 헤더인데 Linux clib 프로파일 사용) 파싱이 통째로 실패하는 것.
- 구조체를 Archive가 아니라 프로그램 안에만 만들어서 다른 바이너리 분석 시 재사용하지 못하는 것.
- 필드 정렬(패딩)을 무시하고 손으로 오프셋을 잘못 채워 실제 메모리 값과 어긋나는 것.

## 막혔을 때 다음 체크
- 정의가 아예 없는 구조체를 코드 패턴만으로 추론하고 싶으면 → REV-0750 Ghidra에서 구조체를 역으로 추론해서 만드는 법
- 변수 Retype 기본기가 헷갈리면 → REV-0161 Ghidra Rename과 Data Type 수정
- IDA에서 타입을 지정하는 법이 궁금하면 → REV-0148 IDA Y로 타입 지정하기
- 이 작업을 여러 바이너리에 반복 적용하고 싶으면 → REV-0743 Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초

## 미니 예제
```c
// point.h
typedef struct {
    int x;
    int y;
    char *label;
} Point;
```
1. Data Type Manager 툴바에서 New File Archive로 `my_types.gdt` 생성
2. File → Parse C Source → `point.h` 선택, 파싱 실행 → Archive 트리에 `Point` 구조체 등장
3. Decompile 창에서 `undefined4 *param_1`으로 되어 있던 변수 위 `Ctrl+L` → `Point *` 입력
4. 이후 코드가 `*(int *)(param_1 + 0)` 대신 `param_1->x`로 렌더링됨
5. Archive 우클릭 → Export로 `my_types.gdt` 저장, 다음 바이너리 분석 시 그대로 Open File Archive

## 관련 글
- REV-0750 — Ghidra에서 구조체를 역으로 추론해서 만드는 법
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0148 — IDA Y로 타입 지정하기
- REV-0743 — Ghidra 스크립트(Python/Java)로 반복 작업 자동화 기초

## 출처/검증
Ghidra 공식 Help 문서(Data Type Manager, Parse C Source, Type Archive 관련 topic) 기준. 실제 Ghidra 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서 및 널리 통용되는 메뉴 경로를 기준으로 작성했다(2026-09-09).
