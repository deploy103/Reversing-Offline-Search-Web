---
id: REV-0781
title: "Ghidra Auto Analysis가 끝나지 않을 때"
slug: "rev-0781-ghidra-auto-analysis-never-finishes"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Auto Analysis 멈춤", "Ghidra 분석이 안 끝남", "Decompiler Switch Analysis 느림", "Ghidra 분석 취소", "Ghidra Task Monitor"]
aliases: ["Ghidra 분석 무한 로딩", "Ghidra Analyzing 창이 안 사라짐", "Ghidra 분석 진행바가 안 움직임"]
symptom_keywords: ["Ghidra 분석 진행바가 몇 시간째 그대로임", "Ghidra Analyzing... 이 안 끝남", "Ghidra가 멈춘 것처럼 보임", "Ghidra CPU 사용률만 계속 높음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra Auto Analysis가 오래 걸리는 것은 대부분 고장이 아니라 **Decompiler Switch Analysis/Decompiler Parameter ID처럼 디컴파일러를 내부적으로 반복 호출하는 무거운 Analyzer가 큰 바이너리 전체 함수를 돌고 있는 것**이며, 상태 바의 진행률과 작업 관리자의 CPU 사용률을 함께 확인해서 "정말 멈췄는지"와 "느리지만 진행 중인지"부터 구분해야 한다.

## 언제 검색해야 하나
- Analyze 버튼을 누른 뒤 진행률 표시줄이 몇 분째, 혹은 몇 시간째 그대로일 때
- 큰 바이너리(수십 MB 이상)나 정적 링킹 바이너리를 열었더니 분석이 끝날 기미가 안 보일 때
- 분석 중에 Ghidra 창 자체가 "응답 없음(Not Responding)"으로 표시될 때
- 취소(Cancel)를 눌러도 되는 건지, 누르면 지금까지 분석한 게 다 날아가는 건지 궁금할 때

## 핵심 개념
Ghidra의 Auto Analysis는 하나의 작업이 아니라 수십 개의 Analyzer가 우선순위 순서대로 실행되는 파이프라인이다(REV-0157 참고). 이 중 특히 시간이 오래 걸리는 것은 다음 두 가지다.

- **Decompiler Switch Analysis**: switch-case로 컴파일된 점프 테이블을 해석하기 위해 디컴파일러를 함수마다 내부적으로 호출한다.
- **Decompiler Parameter ID**: 함수 인자 개수/타입을 추정하기 위해 마찬가지로 디컴파일러를 호출한다.

두 Analyzer 모두 "함수 하나당 디컴파일 1회"이므로, 함수 개수가 수천 개를 넘는 큰 바이너리(특히 정적 링킹된 C++ 바이너리)에서는 이 두 단계에서만 수십 분~수 시간이 걸릴 수 있다. 이는 Ghidra가 멈춘 게 아니라 설계상 원래 느린 것이다. 반면 진짜로 멈춘(hang) 경우는 대개 다음 원인 중 하나다.

1. **극단적으로 큰 파일을 통째로 Import**: 펌웨어 이미지나 언패킹 전의 거대한 리소스 섹션까지 그대로 분석 대상에 포함시켜 함수 후보가 비정상적으로 많이 잡히는 경우.
2. **메모리 부족으로 인한 스와핑**: 힙이 부족해 JVM이 가비지 컬렉션과 디스크 스와핑을 반복하면서 CPU는 계속 도는데 실제 진행은 거의 없는 상태(REV-0786 참고).
3. **무한 루프에 가까운 재귀 분석**: 난독화되었거나 손상된 코드에서 함수 경계 추정이 계속 실패해 같은 영역을 반복 재분석하는 경우.

## 화면/코드에서 보이는 징후
- CodeBrowser 하단 상태 바에 "Analyzing <파일명>... Decompiler Switch Analysis" 같은 문구가 오래 고정되어 있다.
- 작업 관리자/`top`에서 `ghidra` 관련 Java 프로세스의 CPU 사용률이 여전히 100%에 가깝다.
- 진행률 표시줄(progress bar)이 퍼센트 없이 계속 움직이기만 하거나, 아주 느리게 조금씩 채워진다.

## 가장 먼저 할 것
분석을 그냥 기다리기 전에, 먼저 CPU 사용률이 실제로 움직이고 있는지(작업 관리자/`top`)와 상태 바의 Analyzer 이름이 시간이 지나며 바뀌는지부터 확인한다. CPU가 계속 돌고 있고 몇 분 간격으로라도 Analyzer 이름이 바뀐다면 "느리지만 진행 중"이므로 성급하게 취소하지 않는다.

## 단계별 절차

**1) 진행 중인지 멈췄는지부터 구분**

작업 관리자에서 Ghidra(Java) 프로세스의 CPU/메모리 사용량을 확인한다. CPU가 지속적으로 사용되고 있으면 계산 자체는 진행 중이다. CPU가 0%에 가깝게 떨어져 있다면 진짜로 멈췄거나 대기(deadlock) 상태일 가능성이 높다.

**2) 무거운 Analyzer를 끄고 재시작**

기다릴 수 없다면 지금 분석을 취소(하단 진행바 옆 취소 아이콘 또는 **Analysis → Auto Analyze '<파일명>'...** 재실행 시 나오는 대화상자)하고, Analysis Options에서 **Decompiler Switch Analysis**, **Decompiler Parameter ID**의 체크를 해제한 뒤 1차로 가볍게 다시 분석한다. 함수 목록/문자열/기본 XREF만으로도 초기 파악에는 충분한 경우가 많다.

**3) 필요한 함수만 나중에 개별 재분석**

1차 분석으로 관심 함수를 찾은 뒤, 그 함수 위에서만 **Decompile 창을 열어 F5 결과를 확인**하면 Parameter ID/Switch Analysis가 켜져 있지 않아도 개별 함수는 정상적으로 디컴파일된다. 전체를 다시 무겁게 돌릴 필요가 없는 경우가 많다.

**4) 분석 대상 범위 좁히기**

파일에 분석 불필요한 거대한 리소스/데이터 섹션이 포함되어 있다면, Program Trees에서 해당 메모리 블록을 선택하고 **Clear Code Bytes**로 코드 인식 대상에서 제외한 뒤 재분석하면 Analyzer가 처리할 범위 자체가 줄어든다.

**5) 메모리 부족이 의심되면 힙부터 늘리기**

CPU는 도는데 진행이 거의 없다면 메모리 부족(REV-0786)일 가능성이 크므로, Ghidra 실행 스크립트(`support/launch.properties` 또는 `ghidraRun`)의 `MAXMEM` 값을 늘린 뒤 다시 시도한다.

## 명령어/단축키
```text
Analysis → Auto Analyze '<파일명>'...   (분석 옵션 다시 열기/취소 후 재시작)
Analysis Options 창                     (개별 Analyzer 체크 해제)
Program Trees → 블록 선택 → Clear Code Bytes  (분석 범위 축소)
Window → Task Monitor 관련 진행 표시(상태 바)
```

## 출력 해석
- 상태 바에 표시되는 Analyzer 이름이 몇 분 간격으로 바뀌면 정상적으로 다음 단계로 넘어가고 있다는 뜻이다.
- 같은 Analyzer 이름이 아주 오래 고정되어 있고 CPU도 낮다면, 그 Analyzer가 걸린(hang) 상태일 가능성이 높다 — 취소 후 해당 Analyzer를 꺼서 재시도한다.
- 취소 후 다시 열어도 Symbol Tree에 함수/문자열이 이미 채워져 있다면, 취소 시점까지의 분석 결과는 대부분 보존된다는 뜻이므로 처음부터 다시 시작할 필요는 없다.

## 흔한 실수
- 첫 대화상자에서 무조건 기다리기만 하고, CPU 사용률조차 확인하지 않아 "멈춘 건지 느린 건지" 구분하지 못하는 것.
- 분석 중간에 강제 종료(kill)해서 프로젝트 파일이 일부만 반영된 상태로 남는 것 — 가능하면 UI의 취소 버튼으로 정상 중단하는 편이 안전하다.
- 정적 링킹된 대형 바이너리인데도 Decompiler Switch Analysis/Parameter ID를 켠 채로 매번 전체 재분석을 반복하는 것 — 필요한 함수만 개별로 확인하는 습관이 훨씬 빠르다.
- 메모리 부족이 원인인데 그냥 계속 기다리며 시간을 낭비하는 것 — REV-0786의 힙 설정부터 먼저 점검해야 한다.

## 막혔을 때 다음 체크
- 큰 바이너리에서 메모리 부족 증상(스와핑, OutOfMemory)이 의심되면 → REV-0786.
- 분석이 끝났는데도 특정 함수 디컴파일이 비어 보이면 → REV-0782.
- Auto Analysis 자체의 옵션/Analyzer 목록이 궁금하면 → REV-0157.
- 처음부터 프로젝트 Import 단계가 이상하면 → REV-0156.

## 미니 예제
30MB짜리 정적 링킹된 ELF 바이너리를 Import한 상황을 가정한다.

1. "Analyze?" 대화상자에서 Yes → 기본 옵션 그대로 진행.
2. 10분이 지나도 상태 바가 "Decompiler Switch Analysis"에 고정되어 있고, 작업 관리자에서 CPU가 100%로 계속 도는 것을 확인.
3. CPU가 실제로 돌고 있으므로 20분 더 기다려보되, 급하다면 진행바 옆 취소 아이콘으로 중단.
4. Analysis → Auto Analyze 재실행 → Decompiler Switch Analysis, Decompiler Parameter ID 체크 해제 → 다시 Analyze.
5. 2분 만에 1차 분석 완료. Symbol Tree에서 관심 함수(`check_password` 등)를 찾아 그 함수만 클릭해 Decompile 창으로 정상적으로 확인.

## 관련 글
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0786 — Ghidra가 큰 바이너리에서 메모리 부족으로 느려질 때
- REV-0782 — Ghidra에서 Decompile 결과가 비어있을 때
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import

## 출처/검증
- Decompiler Switch Analysis/Decompiler Parameter ID가 함수 단위로 디컴파일러를 내부 호출해 시간이 오래 걸린다는 동작 방식: Ghidra 공식 소스 저장소(NationalSecurityAgency/ghidra)의 Analyzer 구현 및 공식 Help 문서 기준.
- 분석 취소 시 그때까지의 결과가 프로젝트에 대부분 보존된다는 점과 Analysis Options에서 개별 Analyzer를 껐다 켤 수 있다는 점: Ghidra 공식 Help 문서(AutoAnalysisPlugin 토픽) 기준.
- 이 문서는 라이브 환경에서 대형 바이너리로 직접 재현 검증하지 않았으며, 공식 문서와 널리 알려진 사용 경험을 기준으로 작성되었다. 실제 소요 시간은 바이너리 크기/CPU/디스크 성능에 따라 크게 달라질 수 있다.
