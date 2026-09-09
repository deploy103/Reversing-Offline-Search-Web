---
id: REV-0747
title: "Ghidra Bookmarks로 분석 진행상황 표시하기"
slug: "rev-0747-ghidra-bookmarks-progress-tracking"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Bookmarks", "Ghidra Ctrl+B", "Ghidra 북마크", "Ghidra 분석 진행 표시", "Ghidra Bookmark Filter"]
aliases: ["Ghidra TODO 표시", "Ghidra 분석 메모 남기기", "Ghidra 위치 표시 기능"]
symptom_keywords: ["Ghidra에서 나중에 다시 볼 위치 표시하는 법", "Ghidra Ctrl+B가 뭔가", "Ghidra 북마크 목록 보는 법", "Ghidra 여백에 깃발 아이콘"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Bookmark는 코드/데이터를 전혀 바꾸지 않고 특정 주소에 카테고리(Note/Analysis/Error 등)와 짧은 설명만 남기는 표시 기능으로, `Ctrl+B`로 즉시 추가하고 Window → Bookmarks 창에서 필터링하며 CTF처럼 시간 제한이 있는 분석 진행 상황을 관리하기에 좋다.

## 언제 검색해야 하나
- 분석 도중 "여기 나중에 다시 봐야지" 하고 넘어갔다가 어디였는지 까먹는 일이 반복될 때
- Listing 여백에 보이는 작은 아이콘이 무엇인지 궁금할 때
- Ghidra Auto-Analysis가 스스로 의심스럽다고 표시한 지점을 모아서 보고 싶을 때
- 팀원과 분석 진행 상황을 오프라인 상태로 공유하고 싶을 때

## 핵심 개념

### Bookmark가 하는 일
Bookmark는 프로그램 안의 특정 주소에 "표시"만 남기는 가벼운 메타데이터로, 실제 코드/데이터를 바꾸지 않는다. CTF처럼 시간 제한이 있는 분석에서 "여기 나중에 다시 봐야 함", "여기 의심스러움", "여기 아직 분석 못함" 같은 진행 상황을 표시해두는 용도로 매우 유용하다.

### 추가하는 법
Bookmark를 남기고 싶은 주소(Listing이나 Decompile)에 커서를 놓고 `Ctrl+B`를 누르면 기본 카테고리(Note)로 즉시 추가된다. 더 세밀하게 카테고리/코멘트를 지정하려면 우클릭 → Bookmark → Add Bookmark 메뉴로 카테고리(Note, Analysis, Error, Info 등)와 텍스트를 직접 입력한다.

### Bookmarks 창에서 전체 목록 보기
Window → Bookmarks를 열면 지금까지 추가한 모든 북마크가 표(주소, 카테고리, 설명)로 정리되어 나온다. 이 표는 카테고리별로 필터링할 수 있고, 행을 더블클릭하면 해당 주소로 즉시 이동한다. CTF 문제 하나를 분석하며 "확인 필요" 카테고리로 열 몇 개를 표시해뒀다면, 이 창에서 그 목록만 걸러서 하나씩 처리하면 된다.

### Ghidra가 자동으로 남기는 Bookmark
분석 중 Auto-Analysis가 스스로 판단을 못 내린 지점에는 Error/Warning 카테고리의 Bookmark를 자동으로 남기기도 한다. 잘못된 명령어로 디스어셈블된 것으로 의심되는 지점, 참조를 못 찾은 지점 등이다. Bookmarks 창에서 Error 카테고리만 필터링하면 Ghidra 스스로 "여기 이상해 보인다"고 표시한 곳들을 빠르게 훑어볼 수 있다.

### CTF 워크플로우에서 활용
- Note 카테고리: 아직 분석 안 한 함수, 다음에 볼 곳
- Analysis 카테고리: 이미 분석해서 결론 낸 핵심 로직 위치(예: 플래그 검증 함수)
- Error 카테고리: Ghidra가 스스로 의심스럽다고 표시한 곳(디스어셈블리 오류 가능 지점)

이렇게 카테고리를 구분해 쓰면 팀원과 진행 상황을 오프라인 상태에서도(프로젝트 파일 공유만으로) 공유할 수 있다.

## 화면/코드에서 보이는 징후
분석 도중 넘어갔던 위치를 다시 찾지 못하거나, Listing 좌측 여백에 작은 깃발 모양 아이콘이 보이는데 무엇인지 모를 때.

## 가장 먼저 할 것
`Ctrl+B`로 지금 보고 있는 위치를 즉시 북마크하고, Window → Bookmarks를 열어 지금까지 쌓인 목록을 확인한다.

## 단계별 절차
1. 표시하고 싶은 주소에 커서 위치
2. `Ctrl+B`로 빠른 추가(기본 Note 카테고리), 또는 우클릭 → Bookmark → Add Bookmark로 카테고리/설명 직접 입력
3. Window → Bookmarks 창 열기
4. 카테고리 필터로 원하는 종류만 보기
5. 목록에서 더블클릭해 해당 주소로 이동, 분석 완료되면 해당 Bookmark 삭제(우클릭 → Delete) 또는 카테고리를 Analysis로 변경해 완료 표시

## 명령어/단축키
- `Ctrl+B`: 빠른 Bookmark 추가
- 우클릭 → Bookmark → Add Bookmark: 카테고리 지정
- Window → Bookmarks: 전체 목록
- Bookmarks 창에서 우클릭 → Delete

## 출력 해석
Listing 좌측 여백에 작은 깃발 모양 아이콘이 보이면 그 줄에 Bookmark가 있다는 뜻이며, 아이콘 색상/모양이 카테고리에 따라 달라진다(Error는 보통 눈에 띄는 색). Bookmarks 창의 행 수가 CTF 분석 진행률을 대략적으로 보여주는 지표가 되기도 한다.

## 흔한 실수
- Bookmark를 코드 자체를 바꾸는 기능(Patch, Comment)과 혼동하는 것 — Bookmark는 순수하게 "표시"일 뿐 코드/데이터 값에는 아무 영향이 없다.
- 카테고리 구분 없이 전부 기본 Note로만 쌓아서 나중에 필터링이 무의미해지는 것.
- 분석이 끝난 뒤에도 Bookmark를 정리하지 않아 목록이 무한정 늘어나는 것.

## 막혔을 때 다음 체크
- Bookmark 대신 실제 설명을 코드에 남기고 싶으면 → REV-0748 Ghidra Comments와 IDA Comments 비교
- 표시해둔 함수의 이름을 실제로 바꾸고 싶으면 → REV-0161 Ghidra Rename과 Data Type 수정
- 여러 함수 중 핵심 로직만 좁히고 싶으면 → REV-0166 함수 Call Graph로 핵심 로직 좁히기

## 미니 예제
```text
1. main 함수 안 이상한 XOR 루프 발견 -> 커서 위치 -> Ctrl+B (Note 카테고리로 추가됨)
2. 계속 분석 진행, 플래그 비교 함수 발견 -> 우클릭 -> Add Bookmark
   카테고리: Analysis, 설명: "flag 비교 함수, strcmp 결과 사용"
3. Window -> Bookmarks 열기 -> Category 필터를 Note로 설정
   -> 아직 처리 안 한 XOR 루프 위치만 걸러서 재확인
```

## 관련 글
- REV-0748 — Ghidra Comments와 IDA Comments 비교
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- REV-0278 — Ghidra 핵심 단축키 치트시트

## 출처/검증
Ghidra 공식 Help 문서(Bookmarks, Bookmark Manager) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서 및 기본 키바인딩을 기준으로 작성했다(2026-09-09).
