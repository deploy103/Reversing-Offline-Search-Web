---
id: REV-0850
title: "워치포인트가 너무 자주 걸려서 못 쓸 때"
slug: "rev-0850-watchpoint-triggers-too-often"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB]
keywords: ["watch 너무 자주 걸림", "워치포인트 반복", "ignore count", "조건부 watch"]
aliases: ["watchpoint 스팸", "워치포인트가 매번 멈춤", "watch를 반복문에서 쓰기 힘듦"]
symptom_keywords: ["watch를 걸었더니 continue를 수백번 눌러야 한다", "루프 안에서 매번 워치포인트가 걸린다", "원하는 순간까지 못 기다리고 지침"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
루프나 자주 호출되는 함수 안의 변수/메모리에 `watch`를 걸면 매 반복마다 멈추게 되는데, 이럴 때는 워치포인트 자체를 포기하지 말고 **조건을 붙이거나(condition)**, **일정 횟수는 무시하거나(ignore)**, **감시 범위를 더 좁히거나**, **스크립트로 자동 continue**시키는 방식으로 "원하는 순간에만" 멈추도록 좁혀야 한다.

## 언제 검색해야 하나
- `watch` 하나를 걸었는데 루프를 돌 때마다(수십~수만 번) 멈춰서 `continue`를 계속 눌러야 할 때
- 배열/구조체 전체를 감시했더니 관련 없는 필드 변경까지 다 걸려서 정작 찾는 값의 변화를 못 찾을 때
- 워치포인트가 걸릴 때마다 매번 같은 정보(콜스택, 특정 값)만 확인하고 그냥 넘기고 싶을 때

## 핵심 개념

### 감시 범위가 너무 넓다
`watch g_counter` 하나만 걸어도 그 변수가 루프마다 증가한다면 매번 멈추는 게 정상이다. 이건 "너무 자주 걸리는 워치포인트"가 아니라 애초에 "그 변수 자체가 자주 바뀌는 변수"를 감시한 것이므로, 진짜 필요한 건 "특정 조건에서의 변화"인 경우가 많다.

### condition으로 걸러내기
워치포인트도 일반 브레이크포인트처럼 `condition` 명령을 붙일 수 있다. "값이 바뀌었을 때"가 아니라 "값이 특정 값으로 바뀌었을 때"만 멈추도록 좁힐 수 있다.

### ignore로 초반 N번 건너뛰기
루프의 앞쪽 반복은 관심 없고 100번째 반복부터 보고 싶다면, `ignore`로 처음 몇 번의 히트를 자동으로 무시하게 만들 수 있다.

### commands + continue로 자동 필터링
워치포인트가 걸릴 때마다 특정 조건이 아니면 자동으로 `continue`하도록 `commands` 블록을 짜면, 사실상 조건부 워치포인트처럼 동작하면서 더 복잡한 로직(여러 조건 조합, 카운터 누적)도 넣을 수 있다.

### 하드웨어 워치포인트 슬롯은 감시 "주소 범위"가 고정 크기다
`watch` 대상이 배열 전체처럼 넓은 범위면, 하드웨어 워치포인트가 감당 못 하는 크기라서 GDB가 여러 개로 쪼개거나 소프트웨어 워치포인트로 전환해 훨씬 느려지고, 그 범위 안 아무 바이트나 바뀌어도 걸려서 "너무 자주 걸린다"고 느끼게 된다. 감시 폭을 필요한 만큼(예: 4바이트 정수 하나)으로 좁혀야 한다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) watch loop_index
(gdb) continue
Hardware watchpoint 2: loop_index
Old value = 41
New value = 42
...
(gdb) continue
Hardware watchpoint 2: loop_index
Old value = 42
New value = 43
```
`continue`를 아무리 눌러도 매번 같은 워치포인트가 다시 걸리며 진행이 안 되는 상태.

## 가장 먼저 할 것
지금 감시 중인 값이 "원래 자주 바뀌는 값"인지, 아니면 "가끔 바뀌어야 하는데 감시 범위를 너무 넓게 잡아서" 자주 걸리는 것인지부터 구분한다. `info watchpoints`로 현재 걸린 워치포인트의 대상 표현식과 크기를 다시 확인한다.

## 단계별 절차

**1) 현재 워치포인트 확인**
```gdb
(gdb) info watchpoints
Num     Type           Disp Enb Address            What
2       hw watchpoint  keep y                      loop_index
```

**2) 조건 추가로 좁히기**
```gdb
(gdb) condition 2 loop_index == 100
```
이제부터는 `loop_index`가 100이 되는 순간에만 멈춘다.

**3) 초반 히트는 무시하기**
```gdb
(gdb) ignore 2 99
```
99번째까지는 자동으로 넘기고 100번째 히트에서 멈춘다. `condition`과 달리 "몇 번째"만 알고 정확한 값 조건이 없을 때 편하다.

**4) 자동 필터 + 로그만 남기기**
```gdb
(gdb) commands 2
> silent
> if loop_index % 1000 != 0
>   continue
> end
> printf "loop_index=%d\n", loop_index
> continue
> end
```
1000번째 반복마다 한 번씩만 로그를 찍고 자동으로 계속 진행한다.

**5) 감시 범위 좁히기**
구조체/배열 전체 대신 실제로 필요한 필드/원소 하나만 감시한다.
```gdb
(gdb) watch my_struct.status_flag
```
`watch my_struct`(구조체 전체)보다 훨씬 적게 걸린다.

**6) 그래도 너무 잦으면 소프트웨어 접근으로 전환**
루프 자체를 건너뛰고 싶다면 `until`로 현재 루프를 통째로 빠져나오게 한 뒤, 루프 밖에서 다시 조건을 판단한다.

## 명령어/단축키
```gdb
(gdb) info watchpoints
(gdb) condition N EXPR
(gdb) ignore N COUNT
(gdb) commands N ... end
(gdb) delete N
(gdb) until
```

## 출력 해석
- `Old value` / `New value`가 매번 1씩 증가하는 패턴이라면 루프 카운터류다 — 값이 특정 임계치에 도달하는 순간이 진짜 관심사인 경우가 많으니 `condition`으로 그 값을 지정한다.
- `ignore 2 99` 이후 `Will ignore next 99 crossings of breakpoint 2.` 메시지가 뜨면 정상 설정된 것.
- `commands` 블록 안에서 `silent`를 빼먹으면 매 히트마다 "Hardware watchpoint 2: ..." 헤더 메시지가 계속 출력되어 로그가 지저분해진다.

## 흔한 실수
- 조건 없이 자주 바뀌는 변수에 `watch`만 걸고 "왜 이렇게 자주 걸리지"라며 워치포인트 자체를 포기하는 것 — 대부분 `condition`/`ignore`로 해결된다.
- `commands` 블록에서 `continue`를 안 넣어서 조건이 안 맞을 때도 매번 사람이 직접 `continue`를 눌러야 하는 것.
- 배열/구조체 전체를 감시해서 관심 없는 필드 변경까지 다 걸리게 만드는 것.
- `ignore`로 넘긴 횟수와 실제 필요한 반복 횟수를 헷갈려서 한 번 차이로 원하는 지점을 지나쳐 버리는 것.

## 막혔을 때 다음 체크
- 반대로 워치포인트가 걸려야 하는데 전혀 안 걸린다면 → REV-0851 워치포인트가 걸려야 하는데 한 번도 안 걸릴 때.
- 워치포인트/조건부 브레이크포인트 기본 문법이 헷갈린다면 → REV-0191 GDB watchpoint 기초.
- `watch`/`catch`/`tbreak` 등 관련 심화 명령을 더 보고 싶다면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).

## 미니 예제
```gdb
(gdb) break main
(gdb) run
(gdb) watch attempt_count
Hardware watchpoint 2: attempt_count
(gdb) continue
Hardware watchpoint 2: attempt_count
Old value = 0
New value = 1
(gdb) continue
Hardware watchpoint 2: attempt_count
Old value = 1
New value = 2
# ... 계속 반복돼서 지침

(gdb) condition 2 attempt_count == 50
(gdb) continue
Hardware watchpoint 2: attempt_count

Old value = 49
New value = 50
check_attempts (n=50) at chall.c:30
```
조건 없이는 반복마다 멈췄지만, `condition 2 attempt_count == 50`을 걸자 50번째 순간에 딱 한 번만 멈췄다.

## 관련 글
- REV-0851 — 워치포인트가 걸려야 하는데 한 번도 안 걸릴 때
- REV-0191 — GDB watchpoint 기초
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)

## 출처/검증
- `watch`/`condition`/`ignore`/`commands` 명령 구문과 동작: GDB 공식 매뉴얼("Debugging with GDB") "Breakpoints, Watchpoints, and Catchpoints" 챕터 기준 (2026-09-09 검증).
