---
id: REV-0693
title: "PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때"
slug: "rev-0693-pie-breakpoint-address-mismatch"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["PIE breakpoint 안맞음", "gdb break 주소 다름", "ASLR 주소 계산", "vmmap 베이스 주소", "info proc mappings"]
aliases: ["gdb break 주소가 실행할 때마다 달라짐", "ida 주소로 break 안걸림", "pie 브레이크포인트 실패"]
symptom_keywords: ["break *0x주소 했는데 안 멈춤", "어제는 되던 주소가 오늘은 안됨", "IDA에서 본 주소로 브레이크포인트 걸었는데 안 걸림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
PIE(Position Independent Executable) 바이너리는 실행할 때마다 로드 베이스 주소가 ASLR에 의해 무작위로 바뀌기 때문에, IDA에서 본 정적 오프셋이나 이전 실행에서 알아낸 절대 주소로 `break *0x주소`를 걸면 매번 다른(또는 아예 무효한) 위치가 되어 "브레이크포인트가 안 걸린다"는 증상이 나며, 해결책은 심볼 이름으로 걸거나 실행 후 베이스를 구해 오프셋을 더하는 것이다.

## 언제 검색해야 하나
- IDA에서 확인한 함수 주소(예: `0x1349`)로 `break *0x1349`를 걸었는데 `run` 후에도 전혀 멈추지 않을 때
- 어제는 `break *0x555555555169`가 잘 걸렸는데 오늘 같은 바이너리를 재실행했더니 안 걸릴 때
- `checksec` 결과에 `PIE enabled`가 나오는 바이너리를 GDB로 디버깅 중일 때
- raw 주소 기반 브레이크포인트가 실행 전/후 언제 걸어야 정확한지 헷갈릴 때

## 핵심 개념
`checksec`에서 `PIE enabled`로 나오는 바이너리는 ELF 타입이 `ET_DYN`이며, 고정 주소가 아니라 커널이 프로세스를 시작할 때마다(ASLR에 의해) 무작위로 고른 베이스 주소에 올라간다. IDA나 objdump에서 정적으로 보이는 주소는 이 베이스를 `0`으로 가정한 **상대 오프셋**일 뿐이다. 따라서 이전 실행에서 계산해둔 절대 주소를 다음 실행에 그대로 재사용하면, 베이스가 바뀌었기 때문에 그 주소는 이번엔 엉뚱한(혹은 아예 매핑 안 된) 위치일 확률이 높다. non-PIE(`ET_EXEC`) 바이너리는 항상 고정 베이스(보통 `0x400000`)에 로드되므로 이 문제가 생기지 않는다 — 오직 PIE 실행 파일 자신에서만 나타나는 증상이다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) break *0x1349
Breakpoint 1 at 0x1349
(gdb) run
[프로그램이 그냥 끝까지 실행되어 종료됨, 멈추지 않음]
```
또는 어제 저장해둔 `break *0x555555555169`가 오늘 실행에서는 전혀 다른 코드 위치에서 멈추거나 아예 안 멈춘다. `checksec` 결과에는 `PIE enabled`가 표시되어 있다.

## 가장 먼저 할 것
`checksec --file=./chall`로 PIE 여부부터 확인한다. PIE라면 raw 주소 브레이크포인트를 걸기 전에 심볼 이름으로 걸 수 있는지부터 검토한다.

## 단계별 절차
**1) 이름 있는 함수라면 그냥 심볼로 건다(가장 안전하고 빠른 해결책)**
```gdb
break main
break check_password
```
GDB는 `run`/`start`로 프로세스가 로드되는 순간 자동으로 그 심볼의 실제 런타임 주소를 계산해 브레이크포인트를 적용하므로, 실행 전에 걸어도 항상 정확하다.

**2) raw 오프셋이 꼭 필요하면 먼저 로드시키고 베이스를 구해서 더한다**
```gdb
start
info proc mappings
```
출력 맨 위쪽, 대상 바이너리 경로가 적힌 첫 줄의 시작 주소가 이번 실행의 베이스다.
```gdb
break *(0x555555554000 + 0x1349)
```
반드시 `start`/`run` **이후**에 계산해야 한다 — 실행 전에는 베이스가 아직 정해지지 않는다.

**3) 반복 분석 중이라면 ASLR을 고정해서 베이스를 매번 동일하게 유지**
```gdb
show disable-randomization
```
GDB는 기본적으로 이 값이 `on`이라, 같은 GDB 세션 안에서 여러 번 `run`해도 베이스가 항상 같다. GDB를 완전히 재시작하거나 밖에서 직접 실행하면 다시 무작위 베이스가 적용된다.

## 명령어/단축키
```gdb
break main
break FUNC
start
info proc mappings
break *(BASE + OFFSET)
show disable-randomization
```
```bash
checksec --file=./chall
```

## 출력 해석
`info proc mappings` 결과에서 대상 바이너리 자신의 경로가 적힌 첫 줄의 시작 주소가 이번 실행의 PIE 베이스다. `break *(0x555555554000 + 0x1349)` 실행 후 `Breakpoint 1 at 0x555555555349`처럼 계산된 절대 주소가 표시되면 계산이 맞게 반영된 것이다. 같은 세션에서 `run`을 반복해도 이 베이스가 항상 동일하면 GDB의 ASLR 비활성화 기본값 덕분이다.

## 흔한 실수
- 실행 전(`run`/`start` 전)에 raw 오프셋 그대로 `break *0x1349`를 거는 것 — 아직 그 주소에 코드가 로드되지 않았을 수 있다.
- 어제/이전 세션에서 계산해둔 절대 주소를 오늘 새 GDB 세션에서도 그대로 재사용하는 것.
- 이름 있는 함수인데도 굳이 raw 주소를 계산해서 거는 것 — `break 함수이름`이 항상 더 안전하다.
- PIE와 ASLR을 같은 개념으로 혼동하는 것 — PIE는 컴파일 옵션, ASLR은 커널이 실제로 무작위 배치하는 기능이다.

## 막혔을 때 다음 체크
- 이 문제를 훨씬 자세히 다룬 해결책 전체(Pwndbg `$rebase()`, `starti` 등)가 필요하면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기
- PIE 자체의 원리가 궁금하면 → REV-0103 PIE와 주소 계산
- ASLR이 정확히 무엇을 무작위화하는지 알고 싶다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 미니 예제
```gdb
$ gdb ./chall
(gdb) break main
Breakpoint 1 at 0x1189: file chall.c, line 10.
(gdb) run
Breakpoint 1, main (argc=1, argv=0x7fffffffe4d8) at chall.c:10
10          char buf[64];
(gdb) info proc mappings
      0x555555554000     0x555555555000     0x1000        0x0  r--p   /home/user/chall
(gdb) break *(0x555555554000 + 0x1349)
Breakpoint 2 at 0x555555555349
```
`break main`은 실행 전에 걸어도 정확히 동작했고, raw 오프셋은 `start`/`run` 이후 베이스를 구한 뒤에야 정확한 절대 주소로 계산할 수 있었다.

## 관련 글
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유

## 출처/검증
- PIE(`ET_DYN`)의 런타임 재배치와 정적 오프셋 개념: System V ABI ELF 명세(`e_type` 필드) 기준.
- `break`의 심볼 기준 런타임 주소 자동 계산, `start`, `info proc mappings`, `disable-randomization`: GDB 공식 문서("Breakpoints", "Starting your Program") 기준 (2026-09-09 검증).
