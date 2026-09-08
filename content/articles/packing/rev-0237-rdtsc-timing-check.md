---
id: REV-0237
title: "RDTSC Time Check 안티디버깅"
slug: "rev-0237-rdtsc-timing-check"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, IDA]
keywords:
  - RDTSC timing check
  - 타이밍 안티디버깅
  - timing based anti-debug
  - rdtsc threshold
  - GetTickCount anti-debug
  - QueryPerformanceCounter anti-debug
  - timing trap
  - 실행 시간 비교 체크
  - 싱글스텝 탐지 패턴
aliases:
  - RDTSC 타이밍 체크가 뭐임
  - 시간 재서 디버거 탐지
  - GetTickCount 안티디버깅
  - 타이밍 트랩이 뭐임
symptom_keywords:
  - 디버거로 스텝하면 프로그램이 죽음
  - 시간을 두번 측정해서 빼는 코드가 있음
  - GetTickCount 호출이 반복됨
  - QueryPerformanceCounter 비교하는 코드가 있음
  - 브레이크포인트 걸면 타임아웃처럼 종료됨
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RDTSC` 명령어 자체의 사이클 단위 동작은 `../assembly/rev-0087-rdtsc.md`에서 다뤘고, 이 글은 그 위에서 실제 바이너리 안에서 타이밍 안티디버깅이 **어떤 API/패턴 조합으로, 어느 위치에** 나타나는지를 다룬다 — 핵심은 "특정 구간의 실행 시간을 두 번 재서 그 차이를 임계값(threshold)과 비교하고, 너무 오래 걸리면 디버거로 관찰당하고 있다고 판단"하는 하나의 공통 패턴이다.

## 언제 검색해야 하나
- 디버거로 한 줄씩 실행(Step)하거나 브레이크포인트에서 멈췄다 재개할 때 프로그램이 자꾸 다르게 동작하거나 종료될 때
- 코드에서 시간/카운터를 측정하는 함수(`RDTSC`, `GetTickCount`, `QueryPerformanceCounter`, `clock_gettime`)가 짧은 간격으로 두 번 호출되고 그 차이를 비교하는 패턴을 볼 때
- 패커 스텁이나 프로그램 시작 부분(entry point 근처)에서 정체를 알 수 없는 반복 루프와 시간 비교 코드를 볼 때
- "정상 실행은 되는데 한 줄씩 실행하면 안 된다"는 증상을 겪을 때

## 핵심 개념

### 타이밍 체크의 공통 원리
사람이 디버거에서 F7/F8(Step)을 누르거나, 브레이크포인트에 걸려 잠시 분석하다가 재개하는 과정은 CPU 입장에서 "굉장히 오랜 시간"이 걸리는 일이다(수 밀리초~수 초 단위, CPU 사이클로 치면 수백만~수십억 사이클). 반면 정상적으로 그냥 실행되는 코드 블록은 보통 수십~수천 사이클이면 끝난다. 이 차이를 이용해:
```
t1 = 현재 시간/사이클 측정
... 보호하려는 코드 블록 실행 ...
t2 = 현재 시간/사이클 측정
if (t2 - t1 > THRESHOLD) { 디버거 의심 }
```
이 패턴은 사용하는 측정 수단만 다를 뿐 원리는 항상 동일하다.

### 측정 수단별 변형
| 수단 | 특징 |
|---|---|
| `RDTSC`/`RDTSCP` | CPU 사이클 단위, 가장 정밀. 명령어 레벨(REV-0087)에서 직접 다룸 |
| `GetTickCount()`/`GetTickCount64()` (Windows API) | 시스템 부팅 이후 경과 밀리초. 정밀도는 낮지만 API라서 눈에 잘 띔 |
| `QueryPerformanceCounter()` (Windows API) | 고정밀 성능 카운터, 내부적으로 `RDTSC` 또는 HPET을 사용 |
| `clock_gettime(CLOCK_MONOTONIC, ...)` (Linux) | 단조 증가 시계, 나노초 단위 |
| `time(NULL)` | 초 단위라 정밀도가 매우 낮아 안티디버깅용으로는 드물게 쓰임 |

이 글이 다루는 것은 이 API/명령들의 **개별 동작이 아니라, 그것들이 "두 번 호출 후 비교"라는 패턴으로 함께 쓰였을 때 안티디버깅으로 작동하는 방식**이다.

### 어디에 나타나는가
1. **엔트리 포인트 근처**: 프로그램이 실제 `main`에 도달하기 전, 패커/프로텍터 스텁 코드가 실행되는 아주 초반부에서 흔히 발견된다. 이 지점은 사람이 처음 F9를 눌러 정상 실행할 때는 지나가지만, 엔트리 포인트에서부터 한 줄씩 분석을 시작하면 바로 걸린다.
2. **패커 스텁 내부**: UPX 같은 단순 패커는 보통 이런 체크가 없지만, VMProtect/Themida 계열 상용 프로텍터의 스텁 코드에는 압축 해제 루프 곳곳에 타이밍 체크가 산재해 있다.
3. **"트랩 체크"로 코드 전반에 흩어짐**: 정교한 보호에서는 하나의 큰 체크 함수가 아니라, 프로그램 곳곳(중요 함수 진입부, 라이선스 체크 근처 등)에 짧은 타이밍 체크가 여러 개 흩뿌려져 있어서 하나만 우회해도 다른 곳에서 다시 걸린다.

## 화면/코드에서 보이는 징후
- 코드에서 `rdtsc`(또는 `GetTickCount`/`QueryPerformanceCounter`) 호출이 짧은 간격을 두고 두 번 나온다.
- 두 번째 호출 직후 `sub`/뺄셈, 그다음 `cmp`(임계값)와 조건 분기가 바로 이어진다.
- IDA 디컴파일에서 `unsigned __int64 t1 = __rdtsc(); ... unsigned __int64 t2 = __rdtsc(); if (t2 - t1 > 0x...)` 형태로 깔끔하게 보이는 경우가 많다.
- 엔트리 포인트(`Entry point`로 이동, IDA `Ctrl+E`)부터 훑었을 때 진입 직후 몇 줄 안에 이런 패턴이 있다.
- 정상 실행 F9는 되는데, 처음부터 F7(Step Into)로 밟아나가면 특정 지점에서 갑자기 프로그램이 종료되거나 다른 메시지를 띄운다.

## 가장 먼저 할 것
1. Step 실행 중 문제가 생기면, 그 직전 몇 개 명령을 되짚어 `rdtsc`나 타이밍 API 호출이 있었는지 확인한다.
2. 없다면 엔트리 포인트로 이동(`Ctrl+E`)해 시작 부분부터 타이밍 체크가 있는지 스캔한다.
3. 발견하면 두 측정 사이의 "보호 대상 코드"가 무엇을 하는지, 그리고 비교 임계값이 얼마인지 적어둔다.

## 단계별 절차
1. `rdtsc` 텍스트 검색(IDA `Alt+T`) 또는 `GetTickCount`/`QueryPerformanceCounter` import xref로 후보 지점을 모두 찾는다.
2. 각 지점에서 "측정 시작 - 보호 코드 - 측정 끝 - 비교 - 분기" 다섯 단계를 순서대로 확인한다.
3. 비교에 쓰이는 임계값 상수를 기록해둔다 — 이 값이 클수록(즉 널널할수록) 일반적인 Step 실행도 통과할 가능성이 있다는 뜻이므로, 값 자체가 "이 체크가 얼마나 엄격한지"를 알려준다.
4. 실습으로 우회할 때는(자신의 크랙미에 한함) 비교/분기 명령을 무조건 "정상" 경로로 가도록 패치하거나, 두 번째 측정 값을 디버거에서 강제로 첫 번째 값과 비슷하게 맞춰 넣는다.
5. 여러 지점에 흩어져 있다면 하나씩 순서대로 처리하며, 매번 그 다음 지점까지 정상적으로 진행되는지 F9로 확인한다.

## 명령어/단축키
- IDA: `Ctrl+E`(엔트리 포인트로 이동), `Alt+T`(텍스트 검색, `rdtsc` 또는 API 이름), `X`(Xrefs to)
- x64dbg: 비교/분기 직전 주소에 `F2` 브레이크포인트, `F9` 실행, 레지스터 패널에서 경과값 확인 후 우클릭 → Assemble로 패치
- GDB/Pwndbg: `break *0x주소`, `info registers`, `set $eax = <값>`으로 경과값을 강제 조작

## 출력 해석
- 정상 실행 시 경과값이 임계값보다 훨씬 작다는 것을 로그/레지스터로 확인할 수 있다면, 그 위치가 진짜 타이밍 체크임을 확증한 것이다.
- 디버거로 관찰 중일 때 경과값이 임계값을 크게 초과한다면 정상적인 현상이며(체크가 의도대로 작동 중), 이후 분기가 어디로 가는지 확인해 "탐지됨" 처리를 특정해야 한다.

## 흔한 실수
- `RDTSC` 하나만 검색하고 `GetTickCount`/`QueryPerformanceCounter` 같은 API 기반 변형을 놓치는 것.
- 임계값을 한 번만 우회하고 나머지 트랩 체크가 코드 전반에 더 있다는 걸 확인하지 않는 것.
- 타이밍 체크와 단순 성능 측정/프로파일링 코드를 구분하지 않고 전부 안티디버깅으로 오판하는 것 — 결과가 조건 분기(특히 종료/오동작)로 바로 이어지는지가 핵심 구분 기준이다.
- 패커 스텁 안의 타이밍 체크를 실제 애플리케이션 로직의 일부로 착각해 시간을 낭비하는 것 — 엔트리 포인트 근처의 코드는 대개 스텁이며, `main`/`OEP(Original Entry Point)`에 도달하기 전까지는 패킹/보호 레이어라고 생각하고 접근하는 편이 낫다.

## 막혔을 때 다음 체크
- 어디서 걸리는지 감이 안 잡히면 → Step 대신 일단 F9로 끝까지 실행해보고, 정상 실행과 어떤 지점에서 갈라지는지 비교한다(REV-0241).
- `rdtsc` 검색으로도 안 나오면 → API 기반 타이밍 함수(`GetTickCount`, `QueryPerformanceCounter`, `clock_gettime`)의 import xref를 확인한다.
- 여러 체크가 겹쳐서 헷갈리면 → CPUID 기반 VM 탐지(REV-0238), 예외 기반 체크(REV-0239)도 같은 근처에 있는지 함께 확인한다.

## 미니 예제
**예제 1 — RDTSC 기반**
```c
unsigned __int64 t1 = __rdtsc();
do_protected_work();
unsigned __int64 t2 = __rdtsc();
if (t2 - t1 > 0x100000) {
    exit(1); // 디버거 의심
}
```

**예제 2 — Windows API 기반**
```c
DWORD t1 = GetTickCount();
do_protected_work();
DWORD t2 = GetTickCount();
if (t2 - t1 > 100) { // 100ms
    ExitProcess(1);
}
```

## 관련 글
- ../assembly/rev-0087-rdtsc.md
- REV-0238 — CPUID 기반 VM 탐지 기초
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0241 — 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환

## 출처/검증
- `RDTSC` 명령어 상세 동작: `../assembly/rev-0087-rdtsc.md`(Intel SDM 기준) 참고.
- `GetTickCount`/`QueryPerformanceCounter` API: Microsoft Learn 공식 문서(`sysinfoapi.h`, `profileapi.h`) 기준(2026-09-08 검증).
- 타이밍 기반 안티디버깅의 일반 패턴: 공개된 안티디버깅 기법 교육 자료 및 CTF 리버싱 writeup에서 공통적으로 다루는 표준 기법을 정리함.
