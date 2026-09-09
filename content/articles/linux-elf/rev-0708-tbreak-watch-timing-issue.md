---
id: REV-0708
title: "GDB에서 tbreak/watch가 예상과 다른 시점에 걸릴 때"
slug: "rev-0708-tbreak-watch-timing-issue"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords:
  - tbreak
  - watch
  - hardware watchpoint
  - software watchpoint
  - scope
  - watchpoint went out of scope
  - conditional breakpoint
  - PIE 주소
symptom_keywords:
  - tbreak가 예상한 함수에서 안 걸리고 다른 곳에서 멈춤
  - watch로 걸어둔 변수 감시가 한 번 걸리고 사라짐
  - watchpoint went out of scope 메시지가 뜸
  - watch 명령이 너무 느리거나 아예 안 멈춤
  - tbreak가 재귀 함수에서 한 번만 걸림
aliases:
  - tbreak 이상하게 걸림
  - watch 타이밍 이상함
  - 워치포인트 스코프 벗어남
  - 임시 브레이크포인트 헷갈림
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`tbreak`가 이상한 시점에 걸리는 것처럼 보이는 원인은 대개 "임시(temporary)"라는 이름 그대로 **딱 한 번 걸리고 자동으로 삭제되는 특성**을 잊고 두 번째 호출을 기다리는 경우이고, `watch`가 이상하게 걸리거나 사라지는 원인은 대개 **로컬 변수를 감시하다가 그 변수가 스코프를 벗어나면 GDB가 자동으로 워치포인트를 삭제**하기 때문이며, 두 경우 모두 정상 동작이다.

## 언제 검색해야 하나
- `tbreak vuln_func`로 걸어두고 다시 `continue`했는데 같은 함수를 또 호출하는데도 안 멈출 때
- `watch global_var`로 감시를 걸었는데 한 번 값이 바뀐 뒤로는 다시 안 멈추고 프로그램이 끝까지 실행될 때
- 콘솔에 `Watchpoint 2 deleted because the program has left the block in which its expression is valid.`라는 메시지가 뜨고 당황할 때
- `watch` 명령을 걸었더니 프로그램이 갑자기 엄청 느려질 때(하드웨어 워치포인트가 아니라 소프트웨어 워치포인트로 잡힌 경우)

## 핵심 개념

### tbreak는 "한 번만" 걸리는 임시 브레이크포인트
`tbreak <위치>`는 `break <위치>` 뒤에 `delete <번호>`를 자동으로 붙인 것과 동일하다. 즉 조건이 처음 만족되는 순간 딱 한 번 멈추고 나서 브레이크포인트 자체가 삭제된다. 재귀 함수나 반복 호출되는 함수에 `tbreak`를 걸어두고 "두 번째 호출에서도 멈추겠지"라고 기대하면, 실제로는 첫 호출 이후 바로 삭제되어 이후 호출에서는 전혀 멈추지 않는다. `info breakpoints`로 확인하면 그 브레이크포인트 번호 자체가 목록에서 사라져 있다.

```gdb
(gdb) tbreak vuln_func
Temporary breakpoint 1 at 0x401196
(gdb) continue
Temporary breakpoint 1, vuln_func () at chall.c:20
(gdb) info breakpoints
No breakpoints or watchpoints.
```

### watch는 하드웨어/소프트웨어 두 종류가 있고, 스코프에 묶인다
`watch <표현식>`은 해당 표현식의 **값이 바뀌는 순간** 멈춘다. 여기서 핵심은 두 가지다.

1. **감시 대상이 로컬 변수면 스코프에 종속된다.** GDB는 로컬(자동) 변수를 감시하는 워치포인트를, 그 변수가 선언된 블록(함수)을 벗어나는 순간 자동으로 삭제한다. 함수가 `return`하면 그 스택 프레임의 로컬 변수는 더 이상 존재하지 않기 때문에, GDB가 "watchpoint went out of scope"라는 안내와 함께 프로그램을 멈추고 워치포인트를 지운다. 이는 버그가 아니라 GDB의 설계된 동작이다.
2. **하드웨어 워치포인트 vs 소프트웨어 워치포인트.** GDB는 가능하면 CPU의 디버그 레지스터(x86의 `DR0`~`DR3`)를 이용한 **하드웨어 워치포인트**를 사용해 명령어 단위로 느려지지 않고 빠르게 감시한다. 그러나 CPU가 지원하는 하드웨어 워치포인트 슬롯은 보통 4개뿐이라, 이미 여러 개를 걸었거나 가상화/컨테이너 환경에서 디버그 레지스터 접근이 제한되면 GDB는 자동으로 **소프트웨어 워치포인트**로 전환한다. 소프트웨어 워치포인트는 매 명령어마다 싱글스텝하며 값을 비교하기 때문에 프로그램이 체감상 멈춘 것처럼 느껴질 정도로 느려진다.

### tbreak/watch를 함께 쓸 때 순서 혼동
`tbreak` 뒤에 `watch`를 걸 계획이었는데, `tbreak`가 걸리기 전에 `watch`를 먼저 걸어서 프로그램이 예상보다 훨씬 일찍(또는 늦게) 멈추는 경우도 흔하다. 워치포인트는 설정한 즉시부터 감시를 시작하므로, "이 함수 진입 이후부터만 감시하고 싶다"면 먼저 `tbreak`/`break`로 그 지점까지 이동한 뒤에 `watch`를 걸어야 한다.

## 화면/코드에서 보이는 징후
- `info breakpoints`에 걸어뒀던 `tbreak` 번호가 안 보임(이미 삭제됨)
- `Watchpoint 2 deleted because the program has left the block in which its expression is valid.` 메시지
- `continue` 이후 프로그램이 눈에 띄게 느려짐(소프트웨어 워치포인트로 전환된 신호)
- `Hardware watchpoint 2: var` 대신 그냥 `Watchpoint 2: var`로 표시됨(하드웨어 지원이 안 되거나 부족한 경우 소프트웨어로 폴백)

## 가장 먼저 할 것
1. `info breakpoints`로 지금 걸려 있는 브레이크포인트/워치포인트 목록과 각각의 상태(활성/삭제 여부, hit count)를 확인한다.
2. 두 번째 이상 호출에서도 멈추고 싶다면 `tbreak` 대신 `break`를 쓰고, 필요하면 조건(`break vuln_func if count == 2`)이나 `ignore <번호> <N>`으로 N번째 히트까지 건너뛴다.
3. 로컬 변수를 함수 밖에서도 계속 추적하고 싶다면, 전역 변수를 감시하거나 함수 진입 시점마다 `watch`를 다시 거는 방식으로 접근한다.

## 단계별 절차

**1) tbreak가 한 번만 걸린다는 것을 전제로 재귀/반복 함수 디버깅 전략 짜기**
```gdb
(gdb) break vuln_func
Breakpoint 1 at 0x401196
(gdb) continue
Breakpoint 1, vuln_func () at chall.c:20
(gdb) continue
Breakpoint 1, vuln_func () at chall.c:20    # 두 번째 호출에서도 멈춤
```
매번 멈추길 원하면 `tbreak` 대신 처음부터 `break`를 쓴다.

**2) N번째 호출에서만 멈추고 싶다면 ignore 사용**
```gdb
(gdb) break vuln_func
Breakpoint 1 at 0x401196
(gdb) ignore 1 4
Will ignore next 4 crossings of breakpoint 1.
(gdb) continue
```
브레이크포인트 1을 처음 4번은 무시하고, 5번째 히트에서 멈춘다.

**3) 워치포인트를 걸기 전에 스코프 확인**
```gdb
(gdb) break vuln_func
(gdb) continue
Breakpoint 1, vuln_func () at chall.c:20
(gdb) watch local_var
Hardware watchpoint 2: local_var
(gdb) continue
Hardware watchpoint 2: local_var
Old value = 0
New value = 65
vuln_func () at chall.c:25
(gdb) continue
Watchpoint 2 deleted because the program has left the block in which its expression is valid.
0x0000000000401220 in main () at chall.c:40
```
함수가 끝나면서 워치포인트가 자동 삭제되고 GDB가 그 시점에 멈춘 것 — 정상 동작이다. 계속 추적하려면 함수 진입 시점마다 다시 `watch`를 걸어야 한다.

**4) 전역/정적 변수는 스코프 제한 없이 끝까지 유지됨**
```gdb
(gdb) watch g_counter
Hardware watchpoint 3: g_counter
```
전역 변수는 프로그램 종료 전까지 계속 유효하므로, 함수를 넘나들며 반복 호출되어도 계속 감시된다.

**5) 하드웨어 워치포인트 개수 초과/미지원 확인**
```gdb
(gdb) watch a
Hardware watchpoint 4: a
(gdb) watch b
Hardware watchpoint 5: b
(gdb) watch c
Hardware watchpoint 6: c
(gdb) watch d
Hardware watchpoint 7: d
(gdb) watch e
Software watchpoint 8: e
```
CPU 디버그 레지스터가 보통 4개뿐이라 5번째부터는 소프트웨어 워치포인트로 자동 전환된다(느려짐의 원인). Docker/가상화 환경에서 디버그 레지스터 접근이 막혀 있으면 첫 번째부터 소프트웨어로 잡힐 수도 있다(REV-0715 참고).

## 명령어/단축키
```gdb
tbreak <위치>              # 한 번만 걸리는 브레이크포인트
break <위치>                # 반복해서 걸리는 일반 브레이크포인트
ignore <번호> <N>           # 다음 N번 히트를 무시
watch <표현식>               # 값이 바뀌면 멈춤(가능하면 하드웨어 워치포인트)
rwatch <표현식>              # 읽기 시 멈춤
awatch <표현식>              # 읽기/쓰기 모두 감시
info breakpoints            # 현재 브레이크포인트/워치포인트 상태 확인
delete <번호>                # 수동 삭제
```

## 출력 해석
- `Temporary breakpoint N, ...`으로 멈췄다면 그 브레이크포인트는 이미 삭제된 상태이며, `info breakpoints`에서 더는 보이지 않는 게 정상이다.
- `Watchpoint N deleted because the program has left the block in which its expression is valid.`는 로컬 변수 감시가 스코프를 벗어나 자동 정리된 것 — 에러가 아니다.
- `Hardware watchpoint`로 표시되면 CPU 디버그 레지스터를 사용 중이라 빠르다. `Watchpoint`(하드웨어 표기 없음)로 뜨면 소프트웨어 방식이라 실행 속도가 크게 느려질 수 있다.

## 흔한 실수
- `tbreak`를 반복 호출되는 함수에 걸어놓고 두 번째 호출에서 안 멈추는 것을 GDB 버그로 오해하는 것 — 설계된 정상 동작이다.
- 로컬 변수에 `watch`를 걸어두고 함수가 끝난 뒤에도 계속 감시되길 기대하는 것 — 전역/정적 변수가 아니면 스코프를 벗어나는 순간 자동 삭제된다.
- `watch` 여러 개를 걸어두고 프로그램이 갑자기 느려진 이유를 못 찾는 것 — 하드웨어 워치포인트 슬롯 초과로 소프트웨어 워치포인트로 전환됐을 가능성을 확인해야 한다(`info breakpoints`에서 타입 확인).
- `watch` 표현식에 함수 호출(`watch strlen(buf)`)을 넣어서 매번 그 함수를 실제로 실행하며 감시하는 바람에 프로그램 동작 자체가 오염되는 것 — 워치포인트 표현식은 가능한 한 순수한 변수/메모리 참조로 유지한다.

## 막혔을 때 다음 체크
- Docker 등 컨테이너 환경이라 하드웨어 워치포인트/브레이크포인트 자체가 이상하게 동작한다면 → REV-0715(Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때)
- PIE 바이너리라서 브레이크포인트 주소가 매번 달라지는 문제라면 → REV-0104(ASLR 때문에 실행할 때 주소가 바뀌는 이유), REV-0714(동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때)
- 레지스터를 직접 수정했는데 반영이 안 되는 것처럼 보인다면 → REV-0713(GDB에서 레지스터를 수정했는데 반영이 안 되는 것처럼 보일 때)

## 미니 예제
```gdb
(gdb) break main
(gdb) run
Breakpoint 1, main () at chall.c:10
(gdb) tbreak check_password
Temporary breakpoint 2 at 0x4011f0
(gdb) continue
Temporary breakpoint 2, check_password () at chall.c:30
(gdb) watch attempt_count
Hardware watchpoint 3: attempt_count
(gdb) continue
Hardware watchpoint 3: attempt_count
Old value = 0
New value = 1
check_password () at chall.c:35
(gdb) continue
Watchpoint 3 deleted because the program has left the block in which its expression is valid.
```
`attempt_count`가 `check_password` 안의 로컬 변수였기 때문에 함수가 끝나자 워치포인트가 자동으로 정리됐다. 전역 변수로 바꾸거나, 함수에 진입할 때마다 다시 `watch`를 걸어야 계속 추적할 수 있다.

## 관련 글
- REV-0713 — GDB에서 레지스터를 수정했는데 반영이 안 되는 것처럼 보일 때
- REV-0714 — 동적분석 중 ASLR 때문에 라이브러리 베이스 주소가 계속 바뀔 때
- REV-0715 — Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 출처/검증
- `tbreak`, `ignore`, `watch`/`rwatch`/`awatch` 동작: GDB 공식 문서(sourceware.org) "Breakpoints, Watchpoints" 챕터, "Setting Watchpoints" 섹션 기준.
- 로컬 변수 워치포인트가 스코프를 벗어나면 자동 삭제되는 동작(`deleted because the program has left the block`): GDB 공식 문서 "Set Watchpoints" 섹션 기준 (2026-09-08 확인).
- 하드웨어 워치포인트가 CPU 디버그 레지스터 개수(x86 기준 4개)를 초과하면 소프트웨어 워치포인트로 폴백되는 동작: GDB 공식 문서 및 x86 디버그 레지스터(DR0-DR3) 아키텍처 문서 기준.
