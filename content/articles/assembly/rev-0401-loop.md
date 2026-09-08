---
id: REV-0401
title: "LOOP: 카운터 기반 반복 명령"
slug: "rev-0401-loop"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - loop
  - LOOP
  - Loop
  - loop 명령어
  - loop instruction
  - ECX 카운터
  - RCX 카운터
  - loop counter
  - "loop label"
  - dec jnz vs loop
  - 어셈블리 반복문
  - for문 어셈블리
aliases:
  - loop 뭐임
  - loop이 뭐죠
  - LOOP 명령어
  - 루프 명령어
  - loop과 dec jnz 차이
  - loop이 느린 이유
symptom_keywords:
  - loop label이 뭔지 모르겠음
  - ecx가 계속 줄어드는데 왜 그런지 모르겠음
  - for문이 loop 명령어로 컴파일 안되는 이유
  - loop 명령어가 코드에 안 보이는 이유
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LOOP`는 **ECX(또는 RCX/CX)를 1 감소시키고, 그 결과가 0이 아니면** 지정한 레이블로 분기하는 "카운터 기반 반복" 전용 명령어다. 사실상 `dec ecx; jnz label`을 한 명령으로 합친 것이지만, 플래그를 건드리지 않는다는 차이가 있다.

## 언제 검색해야 하나
- `loop loop_start` 같은 코드를 만났는데 무슨 조건으로 반복하는지 모를 때
- 카운터 레지스터가 ECX/RCX로 고정되어 있는 이유가 궁금할 때
- 최신 컴파일러가 생성한 코드에서는 `LOOP`가 거의 안 보이고 `dec`+`jnz` 조합만 보이는 이유가 궁금할 때(CTF 문제나 손으로 짠 셸코드/asm 예제에서는 여전히 자주 등장)

## 핵심 개념

### Intel 문법과 오퍼랜드
```
LOOP rel8
```
- 오퍼랜드는 **rel8(8비트 부호있는 상대 오프셋) 하나뿐**이다 — 즉 목적지 레이블은 현재 명령 위치 기준 -128 ~ +127 바이트 범위 안에만 있을 수 있다(짧은 뒤쪽 분기용).
- 카운터 레지스터는 오퍼랜드로 지정하지 않는다. 항상 고정: 64비트 모드에서는 RCX(주소 크기 접두사로 ECX 사용 가능), 32비트 모드에서는 ECX, 16비트 모드에서는 CX다.

### 실제로 하는 일
```
(E/R)CX = (E/R)CX - 1
if ((E/R)CX != 0) jump to rel8
```
카운터를 먼저 감소시키고, 그 결과가 0이 아니면 분기한다. **감소는 항상 일어나지만, 0이 되는 순간 더 이상 분기하지 않고 다음 명령으로 흘러간다.** 즉 카운터가 0이 아닌 동안 계속 반복되는 "N번 반복" 구조에 정확히 들어맞는다.

### 플래그 변화
**없음.** 이것이 LOOP의 가장 중요하고 헷갈리기 쉬운 특성이다. `DEC ECX`는 원래 ZF/SF/OF/AF/PF를 바꾸지만(CF는 안 바꿈), `LOOP`는 내부적으로 감소 연산을 해도 **EFLAGS를 전혀 건드리지 않는다.** 그래서 LOOP 앞뒤로 다른 조건 분기가 이미 세팅해 둔 플래그가 있다면, LOOP를 거쳐도 그 플래그 값은 그대로 보존된다.

### 스택/RSP/RIP 변화
RSP는 변하지 않는다(스택을 쓰지 않는다). RIP는 분기 성립 시 목표 레이블로, 성립하지 않으면 다음 명령으로 이동한다.

### 왜 최신 컴파일러는 LOOP를 잘 안 쓰는가
겉보기엔 `LOOP`가 `dec ecx; jnz label`(2개 명령)을 1개로 줄여주니 더 빨라 보이지만, 실제로는 **정반대**다. Pentium 이후 대부분의 x86/x64 CPU에서 `LOOP`는 내부적으로 여러 마이크로옵으로 분해되어 `dec`+`jnz` 조합보다 훨씬 느리게(수 사이클~십수 사이클) 처리된다. 이 때문에 GCC/Clang/MSVC 같은 현대 컴파일러는 반복문을 최적화할 때 `LOOP`를 사실상 전혀 생성하지 않고, 항상 `dec`+`jnz`나 다른 카운터 비교 방식을 쓴다. 그래서 실전 릴리즈 바이너리에서 LOOP를 보는 일은 드물고, 대신 다음과 같은 경우에 자주 등장한다:
- CTF/워게임에서 사람이 직접 어셈블리로 작성한 코드
- 매우 오래된 컴파일러가 만든 레거시 바이너리
- 교육용 예제, 셸코드 예제
- 인라인 어셈블리(`__asm` 블록)를 직접 쓴 코드

### 다른 카운터 기반 명령어와의 관계
`LOOP`는 [REP 접두사](rev-0080-rep-prefix.md)와 개념적으로 비슷하다 — 둘 다 ECX/RCX를 카운터로 써서 자동으로 감소시키며 반복한다는 공통점이 있다. 차이는 REP가 문자열 명령(MOVS/STOS/CMPS 등) 앞에 붙어 그 명령 자체를 반복시키는 반면, LOOP는 임의의 코드 블록 전체를 반복시키는 범용 분기 명령이라는 점이다. 조건부 버전인 `LOOPE`/`LOOPZ`([REV-0402](rev-0402-loope-loopz.md))와 `LOOPNE`/`LOOPNZ`([REV-0403](rev-0403-loopne-loopnz.md))는 여기에 ZF 조건까지 추가한 변형이다.

## 화면/코드에서 보이는 징후
- `loop loop_start` — 짧은 뒤쪽 분기, 근처에 `mov ecx, N`(반복 횟수 초기화)가 반드시 선행됨
- LOOP 대상 레이블이 LOOP 명령보다 항상 **앞쪽**(작은 주소)에 위치 — rel8 제약과 "반복" 의미상 자연스러운 패턴
- LOOP 직전/직후에 ECX/RCX를 다른 용도로 재사용하지 않음(카운터로 예약됨)

## 가장 먼저 할 것
1. LOOP 이전에 ECX/RCX가 몇으로 초기화됐는지 확인 → 반복 횟수 파악
2. LOOP가 감싸는 블록(레이블부터 LOOP까지) 범위 확인 → 매 반복마다 실행되는 코드 파악
3. 블록 안에서 ECX/RCX를 건드리는 다른 명령이 있는지 확인(있다면 반복 횟수 계산이 더 복잡해짐)

## 단계별 절차

**1) 기본 카운터 반복 인식**
```asm
mov   ecx, 10
sum_loop:
    add   eax, [rsi]
    add   rsi, 4
    loop  sum_loop
```
→ `for (int i = 0; i < 10; i++) { sum += arr[i]; }` 형태의 배열 합산으로 해석.

**2) 반복 횟수를 정적으로 알 수 없는 경우**
```asm
mov   ecx, [count]   ; 변수에서 로드
proc_loop:
    ...
    loop  proc_loop
```
→ 반복 횟수가 런타임 값에 의존. `count`가 어디서 오는지(함수 인자, 배열 길이 등) 추가로 추적 필요.

## 명령어/단축키
- IDA/Ghidra 의사코드: LOOP 블록은 대개 표준 `for`/`while` 루프로 깔끔하게 재구성된다.
- GDB/Pwndbg: `info registers rcx`로 카운터 값을 실행 중 직접 확인 가능. `watch $rcx`로 카운터 변화를 추적할 수도 있다.

## 출력 해석
- ECX/RCX가 0이 되는 순간 LOOP가 분기하지 않고 다음 줄로 넘어간다 — 이것이 "반복 종료"의 신호다.
- 디버거에서 ECX가 예상보다 빨리 0이 됐다면, 루프 본문 안에서 ECX를 다른 용도로 잘못 재사용했을 가능성을 의심한다.

## 흔한 실수
- LOOP가 플래그(ZF 등)를 바꾼다고 착각하는 것 — LOOP는 EFLAGS를 전혀 변경하지 않는다. `dec ecx; jnz`는 ZF를 바꾸지만 LOOP는 바꾸지 않는다는 차이를 꼭 기억해야 한다.
- 카운터 레지스터를 임의로 선택할 수 있다고 착각하는 것 — LOOP는 항상 ECX/RCX(또는 CX)만 사용한다. 다른 레지스터를 카운터로 쓰고 싶다면 LOOP를 쓸 수 없고 직접 `dec reg; jnz`를 써야 한다.
- 반복 횟수를 "0번"과 "1번" 경계에서 헷갈리는 것 — LOOP는 먼저 감소시킨 후 검사하므로, ECX가 진입 시점에 이미 0이면 감소 후 0xFFFFFFFF(언더플로)가 되어 **약 42억 번(32비트 기준) 반복**하는 심각한 버그가 발생할 수 있다. 이는 `while(count--)` 류 C 코드를 짤 때도 흔한 오프바이원 버그의 어셈블리 버전이다.
- 최신 릴리즈 바이너리를 분석하면서 LOOP 명령어만 찾아 반복문을 식별하려는 것 — 실제로는 `dec`+`jnz`나 `cmp`+`jl` 조합이 훨씬 흔하므로 이들도 반복문 패턴으로 인식해야 한다.

## 막혔을 때 다음 체크
- LOOP가 예상과 다르게 도는 것 같다면 → EFLAGS가 아니라 ECX 값 자체를 디버거에서 직접 확인.
- 반복 횟수가 이상하게 크다면 → 진입 시점 ECX가 0이었을 가능성(언더플로) 의심.
- 코드에 LOOP가 안 보이는데 반복문이 있어야 할 것 같다면 → `dec`+`jnz`, `cmp`+`jl`/`jle` 패턴을 대신 찾아본다.

## 미니 예제

**예제 1 — 단순 합산 루프**
```c
int sum = 0;
for (int i = 0; i < 10; i++) {
    sum += arr[i];
}
```
```asm
xor   eax, eax
mov   ecx, 10
lea   rsi, [arr]
sum_loop:
    add   eax, [rsi]
    add   rsi, 4
    loop  sum_loop
```

**예제 2 — ECX 언더플로 버그 예시**
```asm
mov   ecx, 0
bad_loop:
    ; ecx가 0에서 시작 -> loop 진입 시 감소되어 0xFFFFFFFF가 됨 -> 사실상 무한에 가까운 반복
    loop  bad_loop
```

## 관련 글
- REV-0402 — LOOPE와 LOOPZ: 조건부 반복 명령
- REV-0403 — LOOPNE와 LOOPNZ: 조건부 반복 명령
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기
- REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의

## 출처/검증
- LOOP 명령어의 오퍼랜드/동작/플래그 미변경: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LOOP/LOOPcc—Loop According to ECX Counter" 섹션 기준 (2026-09-08 검증).
- LOOP가 dec+jnz보다 느려 현대 컴파일러가 회피하는 경향: Agner Fog, "Optimizing subroutines in assembly language" 및 Intel/AMD 최적화 매뉴얼의 명령어 지연시간(latency) 표 기준.
