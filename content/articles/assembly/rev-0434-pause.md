---
id: REV-0434
title: "PAUSE: 스핀락 힌트 명령"
slug: "rev-0434-pause"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - PAUSE
  - pause 명령어
  - spin-wait loop
  - 스핀락
  - spinlock
  - busy wait
  - _mm_pause
  - YieldProcessor
  - cpu_relax
  - REP NOP
  - F3 90
aliases:
  - pause가 뭔가요
  - pause 명령
  - 스핀락 어셈블리
  - _mm_pause가 뭐임
  - busy wait 어셈블리
symptom_keywords:
  - pause가 뭔지 모르겠음
  - 반복문 안에 pause만 있음
  - 무한루프처럼 보이는데 pause가 있음
  - 스레드가 계속 도는 것 같은데 왜인지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`PAUSE`는 오퍼랜드도 없고 어떤 레지스터·메모리·플래그도 바꾸지 않는 순수한 "힌트" 명령으로, 락을 기다리며 값을 반복 확인하는 스핀 대기(spin-wait) 루프 안에 넣으면 CPU 파이프라인 낭비와 전력 소모를 줄여주고 루프를 빠져나올 때의 성능 페널티를 완화해 준다.

## 언제 검색해야 하나
- 짧은 반복문 안에 `pause` 하나만 덩그러니 있고 다른 의미 있는 연산이 안 보여서 "이게 왜 무한루프처럼 도는지" 궁금할 때
- 멀티스레드 프로그램에서 `lock cmpxchg`나 `test`/`jnz` 재시도 루프 근처에 `pause`가 함께 있는 코드를 만났을 때
- 디버거로 특정 스레드를 멈춰보니 계속 같은 몇 줄만 맴돌고 있어서 이게 버그인지 정상 동작인지 판단해야 할 때

## 핵심 개념

### PAUSE가 실제로 하는 일
`PAUSE`는 CPU에게 "지금 이 자리는 스핀 대기 루프다"라고 알려주는 힌트일 뿐, 논리적으로는 사실상 아무것도 하지 않는다(NOP과 유사). 다만 내부적으로 세 가지 실질적 효과를 준다.
1. **파이프라인 최적화**: 스핀 루프는 같은 메모리 주소를 반복해서 읽는 짧은 명령들의 연속이라 CPU가 미리 여러 반복을 동시에 처리(비순차 실행, 메모리 순서 예측)하려다 실패해서 되돌리는 비용이 크다. `PAUSE`는 이런 과도한 추측 실행을 억제해서 루프를 더 효율적으로 반복하게 한다.
2. **탈출 페널티 감소**: 락이 풀려서 스핀 루프를 빠져나올 때, `PAUSE`가 없으면 CPU가 이미 진행 중이던 다른 반복들의 메모리 순서 위반을 감지하고 파이프라인을 대거 플러시하는 큰 지연이 생길 수 있다. `PAUSE`는 이 지연을 크게 줄여준다.
3. **하이퍼스레딩 코어 자원 양보**: 같은 물리 코어를 공유하는 다른 논리 코어(hyperthread)에게 실행 자원을 더 양보해서 시스템 전체 처리량을 개선한다.

### 오퍼랜드와 인코딩
```
PAUSE     ; 오퍼랜드 없음
```
바이트 인코딩은 `F3 90`이다. 흥미롭게도 이는 `REP` 프리픽스(`F3`) + `NOP`(`90`)와 정확히 같은 바이트열이다. `PAUSE`를 모르는(P4 이전) 구형 CPU는 이 바이트열을 그냥 `REP NOP`, 즉 실질적으로 `NOP`으로 해석해서 실행하기 때문에 하위 호환성이 보장된다.

### 플래그/스택/RIP 변화
플래그는 전혀 바뀌지 않는다. 스택에도 영향이 없다. `RIP`는 다음 명령으로 이동할 뿐, 레지스터나 메모리 상태도 전혀 바꾸지 않는다. `NOP`([REV-0074](./rev-0074-nop.md))과 마찬가지로 "아무 계산도 하지 않는" 명령이지만, `PAUSE`는 그 존재 이유(스핀 루프 최적화 힌트)가 명확히 다르다는 점이 핵심이다.

### 컴파일러/라이브러리가 만드는 전형적 패턴
- C/C++ 인트린식 `_mm_pause()` (또는 GCC `__builtin_ia32_pause()`)
- Windows API `YieldProcessor()` 매크로 내부 구현
- Linux 커널의 `cpu_relax()` 매크로(x86 한정)
- 스핀락 구현체의 대기 루프: `while (atomic_load(&lock)) { pause(); }`
- 락 없는(lock-free) 자료구조의 CAS 재시도 루프에서 실패가 계속될 때 재시도 사이에 삽입

### IDA/Ghidra 디컴파일에서 보이는 모습
`_mm_pause()` 인트린식 호출로 표시되거나, 인식되지 않으면 그냥 `pause`라는 명령 하나가 반복문 본문 안에 그대로 노출되어 보인다. 반복문 본문이 극단적으로 짧고(`test`/`jnz`/`pause` 몇 줄) 실질적인 계산이 없다는 것이 특징이다.

### 리버싱에서의 의미
`lock` 계열 명령([REV-0432](./rev-0432-lock-prefix.md))이나 단순 메모리 폴링(`test`/`cmp` 후 `jnz`로 되돌아가는 짧은 루프) 바로 안에 `pause`가 있다면, 이는 교과서적인 **스핀락(spinlock) 대기 루프**의 신호다. 이를 알아두면:
1. 디버거에서 특정 스레드가 이 루프에 멈춰 있는 것을 보고 "무한루프 버그"라고 오진하지 않을 수 있다 — 다른 스레드가 락을 풀어주기를 정상적으로 기다리는 중일 수 있다.
2. 데드락 분석 시, 어느 스레드가 어떤 락을 기다리는지 식별하는 출발점이 된다.
3. 단순 지연(delay) 루프 목적으로 남용되는 경우도 있어 항상 진짜 동기화 목적인지 문맥을 함께 봐야 한다.

## 화면/코드에서 보이는 징후
- 아주 짧은 루프: `spin: test dword ptr [lock_var], 1` → `jz acquired` → `pause` → `jmp spin`
- `lock cmpxchg` 실패 시 재시도 직전에 `pause`가 끼어 있는 CAS 루프
- 함수 이름이 `SpinLock`, `Wait`, `spin_wait` 등으로 붙어 있는 근처에서 발견됨

## 가장 먼저 할 것
1. `pause`를 감싸는 루프의 조건(`test`/`cmp` 대상 메모리)이 무엇인지 확인한다 — 그것이 바로 "기다리고 있는 락/플래그"다.
2. 이 루프에 진입하기 전 어떤 `lock` 계열 명령으로 락 획득을 시도했는지(REV-0432, REV-0431 참고) 위쪽 코드를 확인한다.

## 단계별 절차
**1) 스핀락 대기 루프 전체 구조 인식**
```asm
acquire:
mov  eax, 0
mov  ecx, 1
lock cmpxchg [lock_var], ecx    ; CAS로 락 획득 시도
jz   got_lock                    ; 성공하면 탈출
spin:
pause                            ; 실패했으니 잠깐 힌트를 주고
cmp  dword ptr [lock_var], 0    ; 락이 풀렸는지 가볍게 폴링(폴링 자체는 lock 없이 읽기만 함)
jne  spin                        ; 아직 잠겨 있으면 계속 대기
jmp  acquire                     ; 풀린 것 같으면 다시 CAS 시도
got_lock:
```
이렇게 "무거운 `lock cmpxchg`는 가끔만 시도하고, 그 사이에는 가벼운 읽기 폴링 + `pause`로 대기"하는 2단계 구조(test-and-test-and-set)가 실전 스핀락에서 흔히 보인다.

**2) 디버거로 관찰**
멀티스레드 디버깅 중 한 스레드가 이 루프에 머무르고 있다면, 다른 스레드에서 `lock_var`를 언제 0으로 되돌리는지(락 해제 지점) 찾아 그쪽에 브레이크포인트를 걸어 흐름을 맞춰본다.

## 명령어/단축키
- IDA: F5 디컴파일에서 `_mm_pause()`로 표시되는지 확인
- x64dbg/GDB: 멀티스레드 디버깅 시 스레드 목록 창(x64dbg: Threads 탭, GDB: `info threads`)에서 각 스레드가 어느 명령에 멈춰 있는지 확인해 스핀 대기 여부 판단

## 출력 해석
- `pause`는 실행해도 레지스터/메모리/플래그에 관찰 가능한 변화가 전혀 없다. 디버거에서 F7로 스텝해도 "아무 일도 안 일어난 것처럼" 보이는 게 정상이다.
- 이 루프에서 오래 머무른다는 것은 다른 스레드가 락을 오래 쥐고 있거나 데드락 상태라는 뜻일 수 있다.

## 흔한 실수
- `pause`를 단순 `NOP`과 완전히 같은 것으로 여겨서 왜 굳이 다른 니모닉을 썼는지 의아해하는 것 — 바이트는 하위호환을 위해 `REP NOP`과 같지만 최신 CPU에서의 실제 동작(파이프라인 최적화, 하이퍼스레드 자원 양보)은 `NOP`과 다르다.
- 스핀 루프를 보고 "버그로 무한루프에 빠졌다"고 성급히 결론짓는 것 — 정상적인 락 대기일 수 있으므로 락을 쥔 다른 스레드를 먼저 찾아야 한다.
- `pause`가 실제로 OS 스케줄러에게 실행을 양보(진짜 sleep)한다고 착각하는 것 — 그렇지 않다. 진짜 스케줄러 양보가 필요하면 프로그램은 별도로 `Sleep(0)`, `SwitchToThread()`, `sched_yield()` 같은 시스템 콜을 호출해야 한다. `pause`는 어디까지나 같은 코어 안에서의 하드웨어 힌트일 뿐이다.

## 막혔을 때 다음 체크
- 이 루프가 기다리는 락이 어떻게 걸리고 풀리는지 궁금하면 → [REV-0432 — LOCK 프리픽스](./rev-0432-lock-prefix.md), [REV-0431 — CMPXCHG](./rev-0431-cmpxchg.md)로 이동.
- `pause`와 비슷하게 생겼지만 다른 목적의 빈 명령이 궁금하면 → [REV-0074 — NOP](./rev-0074-nop.md)과 비교.
- 데드락처럼 보이는 상황을 진단하고 싶다면 → 모든 스레드의 대기 대상 락 변수를 나열해 서로 순환 대기 중인지 확인한다.

## 미니 예제
**예제 1 — 가장 단순한 스핀 대기**
```c
while (atomic_load(&flag) == 0) {
    _mm_pause();
}
```
```asm
spin:
cmp  dword ptr [flag], 0
je   spin_pause
jmp  done
spin_pause:
pause
jmp  spin
done:
```

**예제 2 — CAS 재시도 사이의 pause**
```asm
retry:
mov  eax, [expected]
lock cmpxchg [shared], ecx
jne  backoff
jmp  success
backoff:
pause
jmp  retry
```

**예제 3 — PAUSE의 바이트 표현(REP NOP과 동일)이 보이는 경우**
```
F3 90     ; 디스어셈블러/CPU 세대에 따라 "pause" 또는 "rep nop"으로 표시될 수 있음
```

## 관련 글
- REV-0432 — LOCK 프리픽스와 원자적 연산 개념
- REV-0431 — CMPXCHG: 비교 후 교환(원자적 연산 개념)
- REV-0074 — NOP: 아무것도 하지 않는 명령과 패치

## 출처/검증
- `PAUSE`의 정의, 인코딩(`F3 90`), 파이프라인/전력/하이퍼스레딩 관련 효과: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PAUSE—Spin Loop Hint" 섹션 기준 (2026-09-08 검증).
- 스핀락 구현에서의 `pause` 사용 관례(`YieldProcessor`, `cpu_relax`): Microsoft Learn 및 Linux 커널 소스의 스핀락 구현 관례 기준.
