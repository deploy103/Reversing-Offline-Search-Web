---
id: REV-0746
title: "Ghidra Function Graph로 제어 흐름 보기"
slug: "rev-0746-ghidra-function-graph-control-flow"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Function Graph", "Ghidra 그래프뷰", "Ghidra Graph Perspective", "control flow graph", "Ghidra Satellite View"]
aliases: ["Ghidra CFG 보기", "Ghidra 그래프 모드", "Ghidra 블록 다이어그램"]
symptom_keywords: ["Ghidra에서 IDA처럼 그래프로 보는 법", "Ghidra Function Graph 여는 법", "Ghidra 블록 색깔 의미", "Ghidra 반복문 시각화"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Function Graph는 IDA Graph View(REV-0150)에 대응하는 기능으로, 함수를 기본 블록 단위 노드와 그 사이의 분기 화살표로 시각화해 텍스트만으로는 파악하기 어려운 반복문/분기 구조를 한눈에 보여준다.

## 언제 검색해야 하나
- 반복문/분기가 복잡해서 Listing만으로는 전체 흐름이 잘 안 보일 때
- IDA Graph View에 익숙한데 Ghidra에서 비슷한 기능을 못 찾을 때
- 노드 색상(초록/빨강 화살표)이 무슨 의미인지 궁금할 때
- 함수 안의 루프 경계를 빠르게 파악하고 싶을 때

## 핵심 개념

### Function Graph가 무엇인가
Listing/Decompile이 텍스트 순서로 코드를 보여주는 반면, Function Graph는 실제 제어 흐름(어디서 어디로 점프하는지)을 도형으로 보여준다. 각 노드는 하나의 기본 블록(분기 없이 순차 실행되는 명령어 묶음)이고, 노드 사이 화살표가 분기 관계를 나타낸다.

### 여는 법
함수 안에 커서를 두고 Window → Function Graph를 선택하거나, CodeBrowser 툴바의 Function Graph 아이콘을 누른다. 처음 열면 Listing과 별도의 탭/창으로 뜨며, 같은 함수를 Listing과 동시에 보면서 대조할 수도 있다.

### 노드와 엣지 색상
- 각 노드는 하나의 기본 블록이다.
- 조건부 분기의 두 갈래는 보통 초록(조건 성립/true 쪽)과 빨강(조건 불성립/false 쪽) 화살표로 구분된다(색상은 Format Manager에서 커스터마이즈 가능).
- 무조건 분기(`JMP` 등)는 파란 계열 화살표로 표시되는 것이 기본값이다.
- 루프백 엣지(반복문 뒤에서 앞으로 돌아가는 화살표)는 다른 블록과 겹쳐서 그려지는 경우가 많아, 레이아웃을 재배치하면 더 잘 보인다.

### 레이아웃과 확대/축소
Function Graph 툴바에는 여러 자동 레이아웃 알고리즘(Tree, Nested Code Layout 등)을 고를 수 있는 옵션이 있다. 함수가 너무 복잡해 노드가 겹치면 레이아웃을 바꿔보거나, Satellite View(우측 하단 미니맵)로 전체 구조를 먼저 파악한 뒤 특정 영역으로 확대한다.

### 노드 안에서 직접 편집
Function Graph의 각 노드 안에는 실제 Listing이 그대로 들어 있어, 그 안에서 바로 Rename(`L`), Retype(`Ctrl+L`), Comment 추가 등 일반 Listing과 동일한 편집이 가능하다. 즉 그래프는 읽기 전용 뷰가 아니라 편집 가능한 또 다른 창이다.

### IDA Graph View와의 차이
IDA는 F5 디컴파일과 그래프 뷰가 같은 창에서 전환되는 느낌이지만(Space바로 그래프/텍스트 전환), Ghidra는 Listing, Decompile, Function Graph가 각각 독립된 창으로 동시에 열려 있다가 서로 클릭하면 동기화되는 구조다. 즉 Decompile 창에서 변수를 클릭하면 Function Graph의 해당 블록도 하이라이트된다.

## 화면/코드에서 보이는 징후
반복문/분기가 복잡해서 Listing만으로는 전체 흐름이 잘 안 보이거나, IDA Graph View에 익숙한데 Ghidra에서 비슷한 기능을 못 찾을 때.

## 가장 먼저 할 것
분석하려는 함수 안에 커서를 두고 Window → Function Graph를 열어 전체 블록 구조부터 훑어본다.

## 단계별 절차
1. 함수 안에 커서 위치
2. Window → Function Graph(또는 툴바 아이콘)
3. Satellite View로 전체 구조 확인
4. 조건 분기의 초록/빨강 화살표를 따라가며 어느 쪽이 "성공" 경로인지 파악
5. 루프처럼 보이는 뒤로 가는 화살표(back edge)를 찾아 반복문 경계 확인
6. 필요하면 노드 안에서 직접 Rename/Comment로 표시

## 명령어/단축키
- Window → Function Graph
- 툴바의 레이아웃 선택 드롭다운
- 마우스 휠 확대·축소
- Satellite View(미니맵) 토글

## 출력 해석
하나의 노드에서 화살표가 두 개 나가면 조건 분기, 하나만 나가면 무조건 분기 또는 순차 진행이다. 화살표가 여러 노드에서 하나로 모이면(예: if/else 이후 합류) 그 지점이 분기 이후 로직이 다시 합쳐지는 지점이다.

## 흔한 실수
- 색상 의미(초록=true, 빨강=false)를 절대적으로 믿고 오해하는 것 — 정확한 조건은 결국 Listing의 실제 조건부 점프 명령을 확인해야 한다.
- 그래프가 복잡하다고 Listing 대조 없이 그래프만 보고 결론 내리는 것.
- 레이아웃이 겹쳐서 안 보이는데 재배치를 시도하지 않고 포기하는 것.

## 막혔을 때 다음 체크
- IDA Graph View와 직접 비교하고 싶으면 → REV-0150 IDA Graph View에서 분기 읽기
- 그래프의 각 분기가 내부적으로 어떤 P-code(CBRANCH)로 표현되는지 궁금하면 → REV-0745 Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)
- 함수 단위가 아니라 프로그램 전체 호출 구조를 보고 싶으면 → REV-0166 함수 Call Graph로 핵심 로직 좁히기

## 미니 예제
```text
if (input == 0x1337) {
    puts("correct");
} else {
    puts("wrong");
}

Function Graph 상에서:
- 비교 블록(CMP + 조건 분기) -> 초록 화살표 -> "correct" 블록
                             -> 빨강 화살표 -> "wrong" 블록
- 두 블록 모두 이후 return 블록으로 화살표가 합류
```

## 관련 글
- REV-0150 — IDA Graph View에서 분기 읽기
- REV-0745 — Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- REV-0158 — Ghidra Decompiler 창 읽기

## 출처/검증
Ghidra 공식 Help 문서(Function Graph) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서와 널리 통용되는 기본 색상/키바인딩을 기준으로 작성했다. 로컬 환경에서 색상 설정이 커스터마이즈되어 있다면 다를 수 있다(2026-09-09).
