---
id: REV-0940
title: "PECompact 패커 기초 알아보기"
slug: "rev-0940-pecompact-packer-basics"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, DIE, PE-bear]
keywords: ["PECompact", "PECompact 언패킹", "PEC2", "pec 패커란", "PECompact stub", "PECompact 시그니처"]
aliases: ["pecompact이 뭐임", "PEC 패킹 확인법", "pecompact 언패킹 방법", "PECompact2 분석"]
symptom_keywords: ["DIE에서 PECompact이라고 뜸", "섹션 이름이 PEC2", "pecompact 패킹된 exe 분석", "pecompact 플러그인 anti-debug"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
PECompact은 자체 압축 스텁 위에 서드파티 플러그인(안티 디버깅, 안티 덤프 등)을 얹을 수 있는 상용 Windows 실행 압축기로, ASPack보다 스텁이 더 다양하게 변형될 수 있어 같은 이름의 패커라도 샘플마다 난이도 차이가 크다.

## 언제 검색해야 하나
- DIE 스캔 결과에 `PECompact`, `PEC2` 같은 이름이 나올 때
- 섹션 이름이 `PEC2`, `pec1`처럼 보일 때
- x64dbg로 붙였는데 ASPack보다 스텁이 길고 중간에 예상치 못한 예외(SEH)가 발생할 때
- "PECompact 언패킹"을 검색했는데 플러그인 종류에 따라 방법이 다르다는 이야기를 보고 개념부터 정리하고 싶을 때

## 핵심 개념
PECompact(줄여서 PEC)은 실행 파일 압축이라는 기본 기능은 ASPack, UPX와 같지만, 두 가지 특징 때문에 실전 난이도가 들쭉날쭉하다.

### 1) 플러그인 아키텍처
PECompact은 패커 자체에 "플러그인" 개념이 있어서, 압축 스텁 안에 안티 디버깅 체크, 안티 덤프 트릭, CRC 무결성 검사 같은 추가 모듈을 끼워 넣을 수 있다. 즉 같은 "PECompact으로 패킹된 파일"이라도:
- 플러그인 없이 순수 압축만 된 파일은 ASPack만큼 쉽게 OEP를 찾을 수 있고,
- 안티 디버깅 플러그인이 들어간 파일은 디버거를 붙이는 것 자체가 막히거나 SEH(구조적 예외 처리) 기반으로 실행 흐름이 꼬여서 훨씬 오래 걸린다.

그래서 "PECompact이다"라는 식별 결과만으로 난이도를 예단하면 안 되고, 실제로 디버거에 붙여서 어떤 반응이 오는지 먼저 관찰해야 한다.

### 2) SEH 기반 안티 디버깅과의 결합
PECompact이 쓰이는 일부 샘플은 압축 해제 루프 자체를 예외 처리기(exception handler) 안에서 진행한다. 정상적으로 실행되면 의도적으로 예외를 발생시키고 자체 핸들러가 이를 처리하면서 다음 압축 해제 단계로 넘어가는데, 디버거가 붙어 있으면 이 예외를 디버거가 먼저 가로채서 스텁이 오작동하거나 멈춰버리는 경우가 있다. 이는 REV-0239(예외 기반 안티 디버깅)에서 다루는 일반적인 기법이 패커 스텁 안에 결합된 형태다.

### OEP 탐색 전략
플러그인이 없는 단순한 PECompact 샘플이라면 ASPack과 똑같은 전략(REV-0944)이 통한다 — `pushad`/`popad` 짝을 찾고 마지막 `jmp`를 추적. 하지만 SEH가 섞여 있다면, x64dbg의 "예외 발생 시 디버거에 전달"/"애플리케이션에 우선 전달" 옵션을 조정해가며 실행해야 스텁이 정상적으로 흘러간다. x64dbg의 Options → Exceptions 설정에서 특정 예외 코드를 애플리케이션이 먼저 처리하도록 넘겨주는 식으로 대응한다.

## 화면/코드에서 보이는 징후
- DIE에 `PECompact 2.xx -> Jeremy Collake` 같은 시그니처 표시
- 섹션 이름이 `PEC2`, 혹은 컴파일러 설정에 따라 임의 이름
- x64dbg로 실행 중 `Exception 계열` 팝업이 반복해서 뜨거나, "Pass exception to application"을 눌러야 진행되는 상황
- 스텁 코드 안에 `int 3`(0xCC) 또는 의도적으로 잘못된 메모리 접근을 유발하는 명령이 섞여 있음

## 가장 먼저 할 것
DIE로 버전을 확인한 뒤, 원본을 백업하고 x64dbg로 붙여서 처음 몇 초 동안 예외 팝업이 뜨는지 관찰한다. 예외가 전혀 없다면 REV-0939/REV-0944와 같은 방식(pushad/popad, jmp OEP)으로 그대로 진행한다. 예외가 반복된다면 SEH 기반 안티 디버깅이 결합된 변형으로 간주하고, 예외 처리 옵션부터 조정한다.

## 단계별 절차
1. DIE로 `PECompact` 버전 식별
2. 원본 백업
3. x64dbg로 열고 `Options → Exceptions`에서 "Ignore custom exceptions" 유사 설정을 확인, 필요 시 특정 예외를 애플리케이션에 우선 전달하도록 설정
4. `Shift+F9`(예외를 애플리케이션에 전달하며 계속 실행) 또는 `F9`로 실행하며 예외 발생 지점을 관찰
5. `pushad`/`popad` 패턴 또는 반복되는 예외 핸들러 등록/해제 패턴을 단서로 스텁 종료 지점 추정
6. OEP 후보에서 정지, 코드 스타일 확인
7. Scylla로 덤프 + IAT 복구(REV-0945)

## 명령어/단축키
- x64dbg: `Shift+F9`(예외를 프로그램에 전달하며 실행), `Ctrl+F9`(현재 함수 끝까지 실행)
- x64dbg 설정: `Options → Preferences` / `Options → Exceptions`
- DIE: `File → Open` 후 상단 패커 배너 확인

## 출력 해석
- x64dbg 상태 표시줄에 `Access violation` 또는 특정 예외 코드가 반복해서 뜨는데 `Shift+F9`로 넘기면 계속 실행이 이어진다면, 이는 스텁이 의도적으로 발생시키는 SEH 트릭일 가능성이 크다.
- 예외 없이 매끄럽게 진행되고 `pushad`/`popad`가 한 번씩만 보인다면 플러그인 없는 단순 압축 버전이다.

## 흔한 실수
- PECompact을 항상 ASPack만큼 쉬운 패커로 취급하는 것 — 플러그인 유무에 따라 난이도 차이가 크다는 점을 무시하면 시간을 낭비한다.
- 예외 팝업이 뜨자마자 "디버거가 감지당했다"고 단정하고 안티 디버깅 우회 코드부터 패치하려는 것. 먼저 `Shift+F9`로 예외를 프로그램에 넘겨보고 정상 진행되는지 확인하는 것이 순서다.
- 첫 예외에서 바로 프로세스를 종료시키고 "언패킹 불가"로 결론짓는 것. x64dbg 예외 전달 옵션을 조정하면 해결되는 경우가 많다.

## 막혔을 때 다음 체크
- 예외가 계속 반복되어 진행이 안 된다면 → REV-0239 예외 기반 안티 디버깅 개념부터 복습
- OEP는 찾았는데 덤프 후 실행이 안 된다면 → REV-0945 IAT 복구 개념
- 아예 다른 상용 프로텍터로 의심된다면 → REV-0942 상용 프로텍터를 만났을 때 현실적인 대응
- CTF 맥락에서 시간이 너무 오래 걸린다면 → REV-0953 패킹/난독화 여부를 실전에서 5분 안에 판단하는 절차로 돌아가 우선순위 재검토

## 미니 예제
```text
entry:
  pushad
  ; 압축 해제 준비
  push handler_addr
  push fs:[0]
  mov fs:[0], esp      ; SEH 체인에 자체 핸들러 등록
  mov eax, [0]         ; 의도적으로 잘못된 접근 -> 예외 발생
  ; 예외 핸들러(handler_addr)가 실행 흐름을 이어받아 다음 단계 진행
  ...
  popad
  jmp OEP
```
x64dbg에서 이 흐름을 만나면 `Shift+F9`로 예외를 애플리케이션에 넘겨 계속 진행시키고, `popad` 다음 `jmp` 대상을 OEP 후보로 표시한다.

## 관련 글
- REV-0939 — ASPack 패커 기초 알아보기
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0944 — 패킹된 바이너리에서 OEP를 수동으로 추적하는 절차 심화
- REV-0945 — 언패킹 후 IAT를 복구하는 개념(Import Reconstruction)

## 출처/검증
- PECompact의 플러그인 아키텍처와 SEH 기반 압축 해제 흐름은 공개된 리버싱 교육 자료 및 언패킹 튜토리얼에서 공통적으로 다루는 설명을 기준으로 정리했다.
- x64dbg의 예외 전달 옵션(`Options → Exceptions`, `Shift+F9`)은 x64dbg 공식 문서(help.x64dbg.com)를 기준으로 확인했다(2026-09-09 검증).
- 특정 PECompact 버전/플러그인 조합의 정확한 동작은 샘플마다 달라질 수 있어 실제 분석 시 재검증이 필요하다.
