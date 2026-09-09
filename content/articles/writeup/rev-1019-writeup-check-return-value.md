---
id: REV-1019
title: "[Write-up] Check Return Value"
slug: "rev-1019-writeup-check-return-value"
category: "writeup"
difficulty: "basic"
platform: [linux]
architecture: [x64]
format: [ELF]
tools: [IDA, GDB, pwndbg]
keywords: ["dreamhack Check Return Value", "드림핵 Check Return Value", "함수 반환값 확인", "RAX 리버싱"]
aliases: ["Check Return Value 풀이", "체크 리턴 밸류", "dreamhack check return value flag"]
symptom_keywords: ["Check Return Value에서 rax를 못찾겠음", "함수 리턴값이 어디 저장되는지 모르겠음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
이름 그대로 "함수의 반환값을 확인하라"는 것이 핵심 힌트인 브론즈 4 문제로, 이 문제만을 다룬 상세 write-up은 찾지 못했지만 같은 시리즈로 보이는 Check Function Argument(REV-1018)의 분석 패턴과 GDB의 finish 명령으로 반환값을 확인하는 일반적인 방법을 근거로 접근법을 정리했다.

## 언제 검색해야 하나
- 드림핵에서 "Check Return Value"를 열었는데 검증 함수가 뭔가를 리턴하고 그 값으로 성공/실패를 가르는 것 같은데 그 값이 어디 저장되는지 모를 때
- IDA 디컴파일 결과에서 `return v;` 같은 코드가 보이지만 그 v가 실제로 어떤 레지스터/스택 위치에 대응하는지 헷갈릴 때
- GDB에서 함수 안으로 들어갔다가 반환되는 순간의 값을 놓쳐서 다시 처음부터 실행해야 하는 상황

## 핵심 개념

### x86-64에서 반환값이 저장되는 위치
System V AMD64 호출 규약에서 정수/포인터형 함수의 반환값은 관례적으로 RAX 레지스터에 담긴다. 함수가 `ret`으로 복귀하는 순간, 호출자는 RAX를 읽어서 그 값을 사용한다. 리버싱에서 "이 함수가 성공/실패를 어떻게 판단하는가"를 알고 싶을 때 가장 먼저 확인해야 하는 것이 바로 이 반환 순간의 RAX 값이다.

### GDB finish로 반환값 가로채기
함수 안으로 스텝인(step into)해서 한 줄씩 따라가는 것은 느리고, 반환되는 순간을 놓치기 쉽다. GDB의 `finish` 명령은 "현재 함수가 끝날 때까지 실행하고, 반환된 직후에 멈춰서 반환값을 보여주는" 기능을 한다(REV-0657). 검증 함수 시작 지점에 브레이크포인트를 걸고 `finish`를 실행하면 "Value returned is $1 = ..." 형태로 반환값을 바로 확인할 수 있어, 이 문제처럼 반환값 자체가 핵심 힌트인 경우 가장 효율적인 방법이 된다.

### 이 문제와 Check Function Argument의 관계
같은 드림핵 브론즈 계열에 "Check Function Argument"(REV-1018)와 "Check Return Value"가 나란히 존재하는 것으로 보아, 두 문제는 "함수의 입력(인자)을 볼 줄 아는가"와 "함수의 출력(반환값)을 볼 줄 아는가"를 각각 연습시키는 짝 문제로 설계되었을 가능성이 높다. 즉 Check Function Argument에서 익힌 pwndbg 기반 레지스터 관찰 습관을 그대로 반환값 관찰에 적용하면 되는 문제로 추정된다.

## 화면/코드에서 보이는 징후
- 디컴파일 결과에 조건문이나 최종 비교 없이 특정 함수의 리턴값을 그대로 되돌리는 짧은 wrapper 함수가 보임
- main 또는 상위 함수가 검증 함수 호출 직후 반환값을 바로 `if`문에 사용
- 정적 분석만으로는 반환값이 계산되는 과정이 불명확하거나 인라인/최적화로 뭉개져 있음

## 가장 먼저 할 것
IDA로 main과 검증 함수의 관계를 파악해 "어느 함수의 반환값이 성공/실패를 가르는가"를 먼저 특정한다. 그 함수의 시작 주소에 GDB 브레이크포인트를 걸고 `finish`로 반환값을 직접 관찰하는 것이 정적 분석보다 훨씬 빠르다.

## 단계별 절차
1. IDA에서 main 흐름을 따라가 최종 성공/실패 분기가 어느 함수의 반환값에 의존하는지 확인한다.
2. 그 함수의 시작 주소에 `break`를 걸고 GDB(pwndbg)로 실행한다.
3. 함수 진입 후 `finish`를 입력해 함수가 끝나는 순간 반환값을 확인한다.
4. 다양한 입력값으로 반환값이 어떻게 바뀌는지 반복 실험해 "어떤 입력이 어떤 반환값을 만드는가"의 관계를 파악한다.
5. 관계가 명확해지면 목표 반환값(성공 조건)을 만드는 입력을 역산하거나, 필요하다면 조건 분기 자체를 패치하는 방법(REV-0072 참고)도 검토한다.

## 명령어/단축키
```bash
gdb ./chall
(gdb) break check_value   # 또는 break *주소
(gdb) run
(gdb) finish
Run till exit from #0 check_value (...)
0x0000... in main ()
Value returned is $1 = 1
```

## 출력 해석
`Value returned is $1 = ...` 뒤에 나오는 값이 바로 RAX에 담긴 반환값이다. 이 값이 0/1 같은 불리언이면 상위 함수의 조건문과 직접 연결되고, 특정 정수나 포인터라면 그 값 자체가 다음 단계(예: 문자열 비교, 인덱스 계산)에 쓰이는 재료일 수 있으므로 곧바로 다음 함수 호출까지 추적해야 한다.

## 흔한 실수
- 함수 안에서 `step`/`next`만 반복하다가 반환되는 순간을 놓치는 것 — `finish`를 쓰면 한 번에 해결된다.
- 반환형이 `bool`이 아니라 더 큰 정수/구조체 포인터인데 무조건 0/1로만 해석하려는 것.
- 이 글이 다루는 "wargame Check Return Value"와 드림핵 자체 Ghidra 스크립팅 강의 안에 있는 동명의 실습 문제를 혼동하는 것 — 둘은 이름이 같지만 서로 다른 콘텐츠일 가능성이 있다.

## 막혔을 때 다음 체크
- `finish`의 정확한 동작과 옵션이 기억 안 나면 REV-0657 GDB에서 함수 반환값을 finish로 확인하는 법을 본다.
- RET 명령이 스택/RIP를 어떻게 바꾸는지 원리부터 다시 보고 싶다면 REV-0072 RET: 함수 반환과 스택 변화를 본다.
- 이 문제의 짝으로 보이는 인자 확인 문제는 REV-1018 [Write-up] Check Function Argument를 먼저 풀어보는 것이 도움이 된다.

## 미니 예제
```
(gdb) break *0x4015a0
(gdb) run
(gdb) finish
Value returned is $1 = 0
```
반환값이 0이면 실패, 다른 특정 값(예: 1 또는 문자열 길이)이면 성공으로 이어지는 구조가 흔하다. 실제 이 문제의 정확한 주소와 반환값 의미는 검증되지 않았으므로 예시로만 참고한다.

## 관련 글
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-1018 — [Write-up] Check Function Argument

## 출처/검증
- 드림핵 워게임 Check Return Value의 카테고리(reversing)·티어(Bronze 4)·풀이자 수(833명)는 dreamhack.io/wargame/challenges?tag=reversing 페이지 직접 조회로 확인됨(2026-09-10).
- WebSearch로 이 워게임 문제만을 다룬 상세 write-up은 찾지 못했다. 검색 중 발견된 동명의 "Check Return Value"는 dreamhack.io의 "Ghidra - Scripting" 학습 코스 안에 있는 실습 문제로, Tier 1 Medium/50코인으로 소개되어 있었으나 이것이 이 글에서 다루는 Bronze 4 워게임 문제와 동일한지는 확인하지 못했다. 이 글의 절차는 GDB finish의 표준 동작과 짝 문제인 Check Function Argument의 분석 흐름에서 유추한 일반적 접근법이며, 이 문제의 실제 로직으로 확정된 내용은 아니다.
