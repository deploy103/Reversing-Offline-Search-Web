---
id: REV-0191
title: "GDB watchpoint 기초"
slug: "rev-0191-gdb-watchpoint"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb watch", "gdb watchpoint", "rwatch", "awatch", "hardware watchpoint", "gdb 값 변경 감지"]
aliases: ["gdb 워치포인트", "gdb watch 명령어", "gdb 값 바뀌는지점 찾기", "gdb 메모리 변경 감지", "gdb rwatch awatch"]
symptom_keywords: ["특정 변수가 언제 바뀌는지 모르겠음", "gdb watch가 안 걸림", "메모리 값이 어디서 바뀌는지 찾고싶음", "gdb에서 값이 읽히는 순간 찾기", "브레이크포인트로는 못 찾는 버그"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`watch`(워치포인트)는 특정 메모리 주소나 변수의 **값이 바뀌는 순간** 자동으로 프로그램을 멈추는 GDB 기능으로, 언제 어느 코드가 그 값을 변경하는지 모를 때 "어느 지점에 브레이크포인트를 걸어야 할지" 미리 알 필요 없이 값 자체를 감시해서 원인 코드를 역으로 찾아낼 수 있다.

## 언제 검색해야 하나
- 특정 전역 변수나 스택 변수(예: 점수, 플래그, 카운터)가 프로그램 어딘가에서 예상과 다르게 바뀌는데, 어느 코드가 그걸 바꾸는지 모를 때
- 함수가 너무 많아서 일일이 `break`를 걸고 `continue`를 반복하기 비효율적일 때
- 어떤 값을 "쓰는" 게 아니라 "읽는" 순간을 잡고 싶을 때(예: 특정 시크릿 값이 언제 처음 참조되는지)
- 스택 버퍼 오버플로우로 인해 카나리(canary) 값이나 리턴 주소가 덮어써지는 정확한 순간을 잡고 싶을 때
- `watch`를 걸었는데 "Hardware watchpoints not supported" 같은 에러가 뜨거나 예상과 다르게 동작할 때

## 핵심 개념

### 워치포인트 세 가지: `watch`, `rwatch`, `awatch`
GDB는 감시 방향에 따라 세 가지 명령을 제공한다.
- `watch EXPR`: 그 표현식(주소/변수)에 **쓰기(write)**가 일어날 때 멈춘다. 가장 많이 쓰인다.
- `rwatch EXPR`: **읽기(read)**가 일어날 때 멈춘다. "이 값이 언제 처음 사용(참조)되는지" 찾을 때 쓴다.
- `awatch EXPR`: 읽기 또는 쓰기(access) 어느 쪽이든 발생하면 멈춘다.

### 대상 지정: 변수 이름 vs 주소
디버그 심볼이 있다면 변수 이름을 그대로 쓸 수 있다.
```gdb
watch global_score
```
심볼이 없거나 임의의 메모리 주소를 감시하고 싶다면, **타입 캐스팅과 함께 역참조**해서 지정해야 한다.
```gdb
watch *(int*)0x601040
watch *0x601040          # 타입을 생략하면 GDB가 기본 int로 추정(버전에 따라 다를 수 있음)
```
타입 캐스팅(`(int*)`, `(long*)`, `(char*)`)을 붙이는 이유는 GDB가 그 크기만큼의 메모리를 감시 범위로 잡기 때문이다 — `int`(4바이트)로 캐스팅했다면 그 4바이트 어디든 바뀌면 멈추고, `char`(1바이트)로 하면 딱 그 1바이트만 감시한다. 스택 지역 변수는 `&buf`처럼 주소를 얻어서 지정할 수도 있다.

### 하드웨어 워치포인트 vs 소프트웨어 워치포인트
GDB의 워치포인트는 가능하면 **CPU의 디버그 레지스터(DR0~DR3 등)를 활용한 하드웨어 워치포인트**로 동작한다. 이 방식은 CPU가 직접 감시하므로 매 명령어마다 GDB가 개입할 필요가 없어 매우 빠르다. 다만 x86-64 CPU는 하드웨어 워치포인트를 **보통 4개까지만** 동시에 지원하므로, 너무 많은 워치포인트를 걸면 일부는 자동으로 느린 소프트웨어 워치포인트(모든 명령어를 하나씩 실행하며 매번 값을 확인 — 극단적으로 느림)로 전환되거나 에러가 날 수 있다. `info watchpoints`로 현재 워치포인트가 하드웨어인지 확인할 수 있다.

### 스코프가 있는 지역 변수 워치포인트
지역 변수를 감시하다가 그 변수가 속한 함수가 리턴해버리면, GDB는 "그 변수는 더 이상 존재하지 않는다"고 판단해서 워치포인트를 자동으로 삭제하고 알려준다.
```
Watchpoint 2 deleted because the program has left the block in
which its expression is valid.
```
이건 정상 동작이다. 함수를 벗어나도 계속 감시하고 싶다면 지역 변수가 아니라 전역 변수나 고정 주소를 감시 대상으로 삼아야 한다.

### 실전 활용: "어디서 이 값을 바꾸는지 모를 때"
예를 들어 스택 카나리 값이 오버플로우로 덮어써지는 정확한 명령어를 찾고 싶다면:
```gdb
break main
run
p &canary_value          # 또는 x/gx $rbp-0x8 등으로 카나리 위치 확인
watch *(long*)($rbp-0x8)
continue
```
이후 `continue`를 치면, 그 값이 실제로 바뀌는 순간(정상적인 함수 흐름이든, 버퍼 오버플로우로 인한 비정상적 덮어쓰기든) GDB가 자동으로 멈추고 이전 값과 새 값을 보여준다. 어느 함수, 어느 명령어에서 이 일이 일어났는지 `bt`, `x/i $rip`로 바로 확인할 수 있다.

### `continue`와 함께 반복 사용
워치포인트도 일반 브레이크포인트처럼 `delete`, `disable`, `info watchpoints`로 관리한다. 한 번 멈춘 뒤 그 값이 앞으로도 계속 바뀔 걸 예상하고 계속 지켜보고 싶다면 그냥 `continue`를 반복하면 된다 — 바뀔 때마다 매번 멈춰준다.

### 워치포인트와 브레이크포인트를 함께 쓰는 조합 전략
실전에서는 두 기능을 같이 쓰는 경우가 많다. 예를 들어 "이 함수에 들어온 뒤부터만 이 변수를 감시하고 싶다"면, 먼저 `break 함수이름`으로 그 함수 진입 지점에서 멈춘 뒤, 그 안에서 `watch 변수`를 걸고 다시 `continue`한다. 함수에 들어오기 전부터 워치포인트를 걸어두면, 관심 없는 다른 코드 경로에서의 변경까지 전부 잡혀서 오히려 분석이 번거로워질 수 있다. 반대로 특정 시점 이후로 감시 범위를 좁히고 싶을 때는 브레이크포인트로 먼저 진입 지점을 확보하는 습관이 유용하다.

### Pwndbg에서의 워치포인트
Pwndbg가 로드된 상태에서도 `watch`, `rwatch`, `awatch`는 순정 GDB 명령 그대로 동작한다. 다만 Pwndbg의 `context` 화면이 자동으로 함께 뜨기 때문에, 값이 바뀌어 멈추는 순간 레지스터/스택/디스어셈블리까지 한 번에 확인할 수 있어 원인 코드를 훨씬 빠르게 특정할 수 있다.

## 화면/코드에서 보이는 징후
- `watch` 실행 시 `Hardware watchpoint 2: *(long*)0x601040`처럼 워치포인트 번호와 대상이 표시됨
- 값이 바뀌는 순간 `Hardware watchpoint 2: *(long*)0x601040` 아래에 `Old value = ...`, `New value = ...`가 함께 출력됨
- 지역 변수를 감시하다가 함수를 벗어나면 `Watchpoint N deleted because the program has left the block...` 메시지
- 워치포인트가 너무 많거나 환경 제약이 있으면 `Hardware watchpoints not supported.`처럼 에러가 뜨고 소프트웨어 워치포인트로 자동 전환되거나 실패

## 가장 먼저 할 것
감시하고 싶은 값의 정확한 메모리 주소와 크기(몇 바이트인지)부터 확인한다. 전역 변수라면 이름 그대로, 스택 값이라면 `x/gx`나 `p &변수`로 주소를 먼저 확인한 뒤 워치포인트를 건다.

## 단계별 절차

**1) 감시 대상 주소/변수 확인**
```gdb
p &global_score
```
또는
```gdb
x/gx $rbp-0x8
```

**2) 워치포인트 설정**
```gdb
watch global_score
```
또는
```gdb
watch *(long*)($rbp-0x8)
```

**3) 실행 재개**
```gdb
continue
```

**4) 멈춘 지점 분석**
```gdb
bt
x/i $rip
```

**5) 필요하면 반복**
계속 `continue`를 눌러 이후에도 값이 바뀔 때마다 확인한다.

**6) 다 썼으면 정리**
```gdb
info watchpoints
delete 2
```

## 명령어/단축키
```gdb
watch EXPR
rwatch EXPR
awatch EXPR
watch *(int*)0xADDR
info watchpoints
delete N
continue
```

## 출력 해석
```
Hardware watchpoint 2: *(long*)0x601040

Old value = 100
New value = 0
0x0000555555555201 in update_score () at chall.c:30
30          score = 0;
```
`Old value`/`New value`로 값이 어떻게 바뀌었는지 즉시 확인할 수 있고, 그 아래 위치(`update_score` 함수, 30번째 줄)가 바로 그 값을 바꾼 코드다. 여기서 바로 `bt`를 치면 이 함수를 누가 호출했는지까지 거슬러 올라갈 수 있다.

## 흔한 실수
- `watch` 대상의 타입 크기를 잘못 지정해서(예: 실제로는 8바이트 값인데 `int*`로 캐스팅) 값의 절반만 감시되거나, 관련 없는 인접 메모리 변경에 걸리는 것.
- 지역 변수를 감시하다가 함수가 끝나면서 워치포인트가 자동 삭제된 걸 모르고 "왜 더 이상 안 멈추지?"라고 헤매는 것.
- 워치포인트를 너무 많이 걸어서 하드웨어 슬롯을 초과해 일부가 소프트웨어 워치포인트로 전환되고, 실행 속도가 급격히 느려지는 걸 못 알아채는 것.
- `break`와 `watch`의 용도를 혼동하는 것 — "이 코드 라인에서 멈추고 싶다"는 `break`, "이 값이 바뀌는 순간을 찾고 싶은데 어느 코드인지 모른다"는 `watch`가 적합하다.

## 막혔을 때 다음 체크
- 애초에 브레이크포인트 개념 자체가 궁금하다면 → REV-0169 Breakpoint가 무엇이고 어디에 걸어야 하는가
- 특정 함수/주소에 정확히 멈추는 법 → REV-0186 GDB break와 address breakpoint
- 멈춘 뒤 스택 전체를 보고 싶다면 → REV-0193 Pwndbg context telescope vmmap

## 미니 예제
```gdb
(gdb) break main
(gdb) run
(gdb) watch *(int*)0x601040
Hardware watchpoint 2: *(int*)0x601040
(gdb) continue
Continuing.

Hardware watchpoint 2: *(int*)0x601040

Old value = 0
New value = 1337
0x0000555555555211 in set_flag () at chall.c:18
18          flag_value = 1337;
```
전역 주소 `0x601040`의 값이 `0`에서 `1337`로 바뀌는 순간, `set_flag` 함수의 18번째 줄에서 자동으로 멈춘 것을 확인할 수 있다.

## 관련 글
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0186 — GDB break와 address breakpoint
- REV-0193 — Pwndbg context telescope vmmap

## 출처/검증
- `watch`, `rwatch`, `awatch`, `info watchpoints`, 하드웨어/소프트웨어 워치포인트 동작 차이: GDB 공식 온라인 문서("Setting Watchpoints") 기준.
- x86 디버그 레지스터 기반 하드웨어 워치포인트 개수 제한(일반적으로 4개): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 3B (Debug Registers 챕터) 기준 (2026-09-08 검증).
