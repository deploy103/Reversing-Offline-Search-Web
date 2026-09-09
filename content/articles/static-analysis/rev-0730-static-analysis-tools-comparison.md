---
id: REV-0730
title: "정적분석 도구별 기능 비교표(IDA/Ghidra/radare2/Cutter)"
slug: "rev-0730-static-analysis-tools-comparison"
category: "static-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, "radare2", "Cutter"]
keywords: ["IDA vs Ghidra", "정적분석 도구 비교", "radare2 vs Cutter", "무료 디컴파일러 비교", "리버싱 도구 선택"]
aliases: ["정적분석 툴 비교표", "IDA Ghidra radare2 차이", "무료 vs 유료 디스어셈블러", "CTF 정적분석 도구 뭐 쓸까"]
symptom_keywords: ["어떤 정적분석 도구를 써야 할지 모름", "IDA와 Ghidra 중 뭐가 나은지 궁금함", "무료 디컴파일러가 필요함", "오프라인 대회에 어떤 툴을 준비해야 할지 모름", "GUI 없이 커맨드라인으로 분석하고 싶음"]
source_ids: ["SRC-HEXRAYS-DOCS", "SRC-GHIDRA-DOCS", "SRC-RADARE2-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
CTF/오프라인 환경에서는 보통 **IDA(유료가 가장 강력하지만 IDA Free로도 기초 분석 가능) + Ghidra(완전 무료, 강력한 로컬 디컴파일러) + radare2/Cutter(커맨드라인/경량 GUI, 스크립팅에 강함)**를 상황에 맞게 조합해서 쓰는 것이 일반적이며, 이 문서는 이 네 가지 도구를 비용·디컴파일러·스크립팅·플랫폼·시그니처 기능 기준으로 한 표에 정리한다.

## 언제 검색해야 하나
- 처음 정적분석 환경을 꾸릴 때 어떤 도구부터 설치해야 할지 판단이 안 설 때
- 오프라인 대회 PC에 어떤 도구를 미리 준비해가야 할지 결정해야 할 때
- 특정 기능(예: FLIRT 같은 라이브러리 함수 자동 인식)이 다른 도구에도 있는지 궁금할 때
- 같은 바이너리를 다른 도구로도 열어봐야 하는데 그 도구의 특징을 빠르게 파악하고 싶을 때

## 핵심 개념
네 도구는 모두 "바이너리를 열어 함수/문자열/구조를 분석하고 가능하면 C 비슷한 코드로 보여준다"는 목표는 같지만, 라이선스 비용, 디컴파일러 성숙도, 스크립팅 편의성, 기본 제공 환경(GUI/CLI)에서 뚜렷한 차이가 있다. 하나만 골라 쓰기보다, IDA/Ghidra로 큰 그림을 보고 radare2로 빠른 커맨드라인 확인이나 자동화를 병행하는 식의 조합이 실전에서 흔하다.

## 화면/코드에서 보이는 징후
"이 도구에서는 안 되던 디컴파일이 다른 도구에서는 되더라", "이 도구는 무료인데 왜 이렇게 정교하지", "커맨드라인으로 서버에 SSH 접속해서 분석해야 하는데 GUI 도구를 못 쓴다" 같은 상황에서 도구 선택 기준이 필요해진다.

## 가장 먼저 할 것
아래 비교표에서 지금 상황(예산, 오프라인 여부, GUI 필요 여부)에 맞는 후보를 먼저 추린 뒤, 각 도구의 상세 사용법 문서(관련 글 참고)로 이동한다.

## 단계별 절차

**1) 예산/라이선스 확인**

상업적으로 IDA Pro 라이선스를 구매할 수 있는 환경인지, 아니면 완전 무료 도구만 써야 하는지부터 결정한다.

**2) 디컴파일러 필요 여부 확인**

어셈블리만으로 충분한 간단한 문제인지, C 비슷한 코드로 봐야 효율적인 복잡한 문제인지 판단한다.

**3) 자동화/스크립팅 필요 여부 확인**

동일 작업을 여러 바이너리에 반복해야 하거나 서버 환경(GUI 없음)에서 작업해야 한다면 radare2 계열이 유리하다.

**4) 병행 사용 계획**

큰 구조 파악은 GUI 도구(IDA/Ghidra/Cutter)로, 빠른 확인이나 자동화는 radare2 커맨드라인으로 병행하는 조합을 미리 계획해둔다.

## 명령어/단축키
아래 표가 이 문서의 핵심 참조 자료다.

| 항목 | IDA | Ghidra | radare2 | Cutter |
|---|---|---|---|---|
| 라이선스/비용 | 상용(IDA Pro), 기능 제한된 무료판(IDA Free) 존재 | 완전 무료, 오픈소스(NSA 공개) | 완전 무료, 오픈소스 | 완전 무료, 오픈소스 |
| 인터페이스 | GUI(데스크톱 앱) | GUI(Java 기반) | 커맨드라인(CLI), Visual/그래프 모드 내장 | GUI(radare2/rizin 엔진 기반) |
| 디컴파일러 | Hex-Rays(유료 애드온 또는 IDA Free 클라우드 버전) | 자체 내장 디컴파일러(무료, 로컬 실행) | 자체 pseudocode 기능은 제한적(주로 디스어셈블리 중심) | native pseudocode 또는 Ghidra 디컴파일러 플러그인 선택 가능 |
| 그래프 뷰 | Graph view(REV-0150) | Function Graph | Visual 그래프 모드(`VV`) | Graph 탭(마우스 기반) |
| 라이브러리 함수 자동 인식 | FLIRT(REV-0729) | FID(Function ID) 서비스 | zignatures(서명 기반 함수 인식) | radare2/rizin 엔진의 서명 기능 그대로 활용 |
| 구조체/타입 관리 | Structures/Enums/Local Types(REV-0721~0723) | Data Type Manager(REV-0724) | 명령 기반 타입 지정(`t` 계열 명령) | Data Type Manager와 유사한 GUI 패널 |
| 스크립팅/자동화 | IDC, IDAPython | Java, Jython/PyGhidra(REV-0725) | r2pipe(Python 등 여러 언어 바인딩), 자체 스크립트 | 내부적으로 radare2/rizin 명령 그대로 스크립팅 가능 |
| 플랫폼 | Windows/Linux/macOS | Windows/Linux/macOS(Java 런타임 필요) | Windows/Linux/macOS | Windows/Linux/macOS |
| 오프라인 사용 적합성 | 로컬 라이선스 있으면 완전 오프라인 가능(단, IDA Free 디컴파일러는 클라우드 의존 가능성) | 완전 오프라인 가능 | 완전 오프라인 가능 | 완전 오프라인 가능 |
| 대표 강점 | 성숙한 디컴파일러, 방대한 생태계, 안정적인 정적 분석 | 무료인데도 강력한 로컬 디컴파일러, 협업/버전 관리 기능 | 빠른 커맨드라인 워크플로, 강력한 자동화/스크립팅 | radare2 능력을 GUI로 접근 가능, 무료 GUI 대안 |

## 출력 해석
- "완전 무료"라고 해도 오프라인 대회 환경이라면 사전 설치/검증이 필수다 — 특히 Ghidra는 Java 런타임이 필요하므로 오프라인 PC에 JDK/JRE가 준비되어 있는지 미리 확인해야 한다.
- IDA Free의 디컴파일러가 클라우드 기반으로 제공되는 경우, 인터넷이 차단된 대회 환경에서는 F5가 아예 동작하지 않을 수 있다(REV-0146 참고) — 이 경우 사실상 Ghidra가 오프라인 무료 디컴파일러의 현실적 대안이 된다.
- 각 도구의 "라이브러리 함수 자동 인식" 기능(FLIRT/FID/zignatures)은 이름은 달라도 개념이 비슷하다 — 정적 링킹된 바이너리를 다룰 때 어떤 도구를 쓰든 이 기능부터 확인하는 습관이 유용하다.

## 흔한 실수
- "IDA가 무조건 더 좋다"고 단정하고 Ghidra를 아예 안 써보는 것 — 상황(예산, 오프라인 여부, 협업)에 따라 Ghidra가 더 적합할 수 있다.
- radare2를 "옛날 도구"로 치부하고 커맨드라인 자동화의 장점을 놓치는 것 — 대량의 바이너리를 배치 처리해야 할 때는 오히려 radare2/r2pipe 조합이 GUI 도구보다 빠르다.
- 한 도구에서 디컴파일이 이상하게 나오면 바로 포기하는 것 — 다른 도구로 같은 함수를 열어 교차 검증하면 어느 쪽이 실제 로직에 더 가까운지 판단하는 데 도움이 된다.
- Cutter를 radare2와 완전히 다른 도구로 착각해서 커맨드라인 학습을 아예 건너뛰는 것 — Cutter의 콘솔 창에는 radare2/rizin 명령을 그대로 쓸 수 있으므로 둘을 함께 배우는 편이 효율적이다.

## 막혔을 때 다음 체크
- IDA 기초 사용법이 필요하면 → REV-0142 IDA에 바이너리 처음 열었을 때 해야 할 것.
- Ghidra 기초 사용법이 필요하면 → REV-0156 Ghidra 프로젝트 생성과 바이너리 Import.
- radare2/Cutter 기초 사용법이 필요하면 → REV-0291 radare2 설치와 첫 명령, REV-0293 Cutter 설치와 기본 사용법.
- 라이브러리 함수 자동 인식 개념을 더 깊이 알고 싶다면 → REV-0729 FLIRT 시그니처 개념과 사용 빠른 참조.

## 미니 예제
```text
같은 strip된 정적 링킹 ELF 파일을 분석해야 하는 상황:
1. IDA(라이선스 있음) → 열자마자 FLIRT로 라이브러리 함수 다수 자동 인식 → F5로 주요 로직만 빠르게 확인
2. Ghidra(무료 환경) → Auto Analysis + FID로 유사하게 라이브러리 함수 인식 → Decompile 창에서 동일 로직 확인
3. radare2 → r2 -A ./chall; aaa; afl 로 즉시 함수 목록 확보, 스크립트로 문자열/임포트 일괄 추출
4. Cutter → radare2 엔진 그대로 사용하되, 마우스로 그래프/함수 목록을 훑으며 팀원에게 화면 공유로 설명
```
같은 바이너리라도 상황(라이선스, 협업, 자동화 필요성)에 따라 네 도구를 상호 보완적으로 쓸 수 있다.

## 관련 글
- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0291 — radare2 설치와 첫 명령
- REV-0293 — Cutter 설치와 기본 사용법
- REV-0729 — FLIRT 시그니처 개념과 사용 빠른 참조

## 출처/검증
- IDA/Hex-Rays의 라이선스 구조와 FLIRT 기능은 Hex-Rays 공식 문서 및 제품 페이지(hex-rays.com) 기준.
- Ghidra의 무료/오픈소스 라이선스, Data Type Manager, FID(Function ID) 관련 기능은 Ghidra 공식 문서(Ghidra Help, NationalSecurityAgency/ghidra 공식 저장소) 기준.
- radare2의 커맨드라인 구조, Visual/그래프 모드, zignatures 개념은 공식 문서 "The Radare2 Book"(book.rada.re) 기준.
- Cutter가 radare2/rizin 엔진을 그대로 사용한다는 점과 디컴파일러 플러그인 구조는 Cutter 공식 저장소(github.com/rizinorg/cutter) 기준.
- 네 도구 모두 버전에 따라 기능/UI가 계속 바뀌므로, 실제 선택 전 각 공식 웹사이트에서 최신 기능/라이선스 정책을 재확인할 것을 권장한다(2026-09-09 검증).
