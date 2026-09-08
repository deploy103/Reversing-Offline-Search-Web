---
id: REV-0194
title: "PIE 바이너리 GDB 브레이크포인트 잡기"
slug: "rev-0194-gdb-pie-breakpoints"
category: "dynamic-analysis"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pie breakpoint", "gdb pie 브레이크포인트", "pie break", "런타임 베이스 주소", "gdb rebase", "load_base offset"]
aliases: ["pie 브레이크포인트 안걸림", "gdb pie 주소 계산", "pie break 명령어", "gdb 브레이크포인트 랜덤", "pie 바이너리 디버깅"]
symptom_keywords: ["pie breakpoint가 안 걸림", "gdb break 주소가 실행할때마다 다름", "이전에 걸었던 주소가 이번엔 안 맞음", "ida 주소로 break했는데 안 걸림", "pie 바이너리 gdb 디버깅 안됨"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PIE(Position Independent Executable) 바이너리는 실행할 때마다 로드 베이스 주소가 (ASLR에 의해) 무작위로 바뀌므로, 이전 실행에서 알아낸 raw 주소로 `break *0x주소`를 걸면 이번 실행에서는 전혀 다른(또는 매핑조차 안 된) 위치가 되어 "pie breakpoint가 안 걸린다"는 증상이 나며, 해결책은 심볼 이름으로 걸거나(`break main`), 실행 후 `vmmap`/`info proc mappings`로 이번 실행의 베이스를 구해 `베이스+오프셋`을 계산하거나, `starti`/`start`로 먼저 로드시킨 뒤 브레이크포인트를 거는 것이다.

## 언제 검색해야 하나
- IDA에서 확인한 함수 주소(예: `0x1349`)로 GDB에서 `break *0x1349`를 걸었는데, `run` 후에도 전혀 멈추지 않을 때
- 어제는 `break *0x555555555169`가 잘 걸렸는데, 오늘 같은 바이너리를 다시 실행했더니 같은 명령이 안 먹힐 때
- "pie breakpoint"라는 표현을 CTF 라이트업이나 스택오버플로우에서 보고 정확히 뭘 뜻하는지 찾고 있을 때
- GDB 안에서 아직 실행 전(run 이전)에 raw 주소로 브레이크포인트를 걸어야 하는지, 실행 후에 걸어야 하는지 헷갈릴 때
- gef나 다른 GDB 확장의 `pie break`, `pie run` 같은 명령을 보고 pwndbg에서는 어떻게 하는지 궁금할 때

## 핵심 개념

### 문제의 근원: PIE는 매 실행마다 다른 주소에 로드된다
`checksec`으로 확인했을 때 `PIE enabled`가 뜨는 바이너리는 ELF 타입이 `ET_DYN`이며, 고정된 주소가 아니라 **커널이 프로세스를 시작할 때마다(ASLR에 의해) 무작위로 고른 베이스 주소**에 올라간다(자세한 원리는 REV-0103 PIE와 주소 계산, REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유 참고). IDA나 objdump로 정적 분석할 때 보이는 주소는 이 베이스를 `0`으로 가정한 **상대 오프셋**일 뿐이다. 그래서 "이전 실행에서 GDB가 `0x555555555169`에서 멈췄다"는 사실을 기억해뒀다가 다음 실행에서 `break *0x555555555169`를 그대로 다시 걸면, 이번 실행의 베이스가 달라졌기 때문에 그 주소는 이번엔 아무 코드도 없는 엉뚱한 위치일 확률이 높다.

### "안 걸린다"의 세 가지 구체적 증상
1. **아예 반응이 없다**: `break *0x1349`처럼 실행 전에 오프셋 그대로 걸었을 때. 이 주소는 아직 아무것도 매핑되지 않은, 혹은 프로세스와 무관한 주소로 취급되어 GDB가 브레이크포인트를 "pending" 상태로 두거나 걸리지 않는다.
2. **걸리긴 했는데 전혀 다른 곳에서 멈춘다(혹은 아예 안 멈춘다)**: 이전 실행에서 계산해둔 `베이스+오프셋` 값을 이번 실행에 그대로 재사용했을 때. ASLR 때문에 베이스가 달라져서 그 주소가 이번엔 의미 없는 위치가 됐다.
3. **`run`으로 그냥 끝까지 실행돼버린다**: 브레이크포인트 자체가 무효화된 상태로 계속 프로그램이 진행된 경우다.

### 해결책 1 — 가장 안전한 방법: 심볼 이름으로 걸기
```gdb
break main
break check_password
break *check_password+37
```
GDB는 심볼 테이블을 알고 있으므로, `run`이나 `start`로 프로세스가 로드되는 순간 **자동으로 그 심볼의 실제 런타임 주소를 계산**해서 브레이크포인트를 적용한다. 실행 전에 미리 걸어놔도, 실행 후에 걸어도 항상 정확하게 동작한다. 이름 있는 함수를 대상으로 할 때는 무조건 이 방법을 최우선으로 쓴다.

### 해결책 2 — raw 주소가 꼭 필요할 때: 먼저 로드시키고 베이스를 구한 뒤 계산
심볼이 없는 임의의 주소(디버그 심볼이 제거된 바이너리의 특정 명령어 등)에 걸어야 한다면, **프로세스가 이미 메모리에 로드된 뒤에** 베이스 주소를 구해서 오프셋을 더해야 한다.
```gdb
start
info proc mappings
```
출력 맨 위쪽, 대상 바이너리 자신의 경로가 적힌 첫 줄의 시작 주소가 이번 실행의 베이스다. Pwndbg를 쓰면 더 간단하다.
```
pwndbg> start
pwndbg> vmmap
```
`vmmap` 결과의 맨 위 줄이 바로 실행 파일의 베이스 주소다. 이 값을 IDA에서 확인한 오프셋에 더해서 건다.
```gdb
break *(0x555555554000 + 0x1349)
```
반드시 **`start`나 `run` 뒤에** 이 계산을 해야 한다 — 실행 전에는 아직 베이스가 정해지지 않아 계산할 값 자체가 없다.

### 해결책 3 — `starti`로 최대한 이른 시점에 멈춰서 베이스부터 확보
`main`보다도 이른 시점(엔트리 포인트)에서 베이스를 미리 알아두고 싶다면 `starti`를 쓴다. 엔트리 포인트에서 멈추면 이미 실행 파일 자신은 메모리에 로드된 상태이므로 `vmmap`/`info proc mappings`로 베이스를 즉시 얻을 수 있다(단, 아직 동적 링커가 라이브러리를 전부 로드하기 전일 수 있다).
```gdb
starti
info proc mappings
```

### 해결책 4 — ASLR을 꺼서 베이스를 고정시키기
분석 중에는 매번 베이스가 바뀌는 것 자체가 번거로우므로, ASLR을 꺼서 항상 같은 베이스로 실행되게 만드는 방법도 실무에서 많이 쓴다. GDB는 기본적으로 **디버깅 대상의 ASLR을 이미 꺼둔 상태(`disable-randomization on`)**로 실행하므로, GDB 안에서 여러 번 `run`을 해도 베이스가 항상 동일하게 나온다.
```gdb
show disable-randomization
```
이게 `on`이라면 GDB 세션 안에서는 안심하고 이전에 구한 `베이스+오프셋` 값을 재사용할 수 있다(단, GDB를 완전히 종료하고 새로 켜거나 GDB 밖에서 직접 실행하면 다시 무작위 베이스가 적용된다). 시스템 전체 ASLR을 끄고 싶다면 `setarch $(uname -m) -R ./chall`로 GDB 밖에서 직접 실행하는 방법도 있다(REV-0104 참고).

### 해결책 5 — Pwndbg/GEF류 헬퍼: `$rebase()`와 `pie break`
일부 Pwndbg 버전은 `$rebase(오프셋)`이라는 GDB 편의 함수(convenience function)를 제공해, 매번 베이스를 직접 더하지 않고 오프셋만 넘기면 자동으로 현재 로드 베이스를 더해준다.
```gdb
break *$rebase(0x1349)
```
GEF(GDB Enhanced Features, Pwndbg와는 다른 별도의 GDB 확장)에는 이 용도로 특화된 `pie break 0x1349`, `pie run`, `pie info` 같은 전용 명령어가 있어서 PIE 오프셋을 그대로 넘기면 자동으로 현재 실행의 베이스를 반영해준다. Pwndbg를 쓴다면 `$rebase()` 함수나 `vmmap`으로 베이스를 구해 직접 더하는 방식이 표준적인 접근이며, 설치된 버전에 어떤 헬퍼가 있는지는 `pwndbg`(명령 목록)나 `help`로 확인하는 것이 가장 정확하다.

### non-PIE와 비교하면 왜 이 문제가 PIE에서만 생기는지 명확해진다
non-PIE(`ET_EXEC`, `checksec`에서 `No PIE`) 바이너리는 항상 고정된 베이스(보통 `0x400000`)에 로드되므로, IDA에서 본 주소를 그대로 `break *0x401234`로 걸어도 매번 정확히 맞는다. "pie breakpoint" 문제는 오직 실행 파일 자신이 재배치 가능한(PIE) 경우에만 발생하며, 라이브러리(`libc` 등)는 애초에 항상 공유 라이브러리이므로 PIE 여부와 무관하게 원래부터 이 문제를 안고 있었다 — `printf`에 raw 주소로 브레이크포인트를 걸 수 없는 것도 같은 이유다.

## 화면/코드에서 보이는 징후
- `break *0x1349`처럼 4~5자리의 작은 raw 주소를 걸었는데 `run` 후 프로그램이 그냥 끝까지 실행되고 멈추지 않음
- 어제 저장해둔 `break *0x555555555169` 명령이 오늘 실행에서는 전혀 다른 코드 위치에서 멈추거나 아예 안 멈춤
- `checksec` 결과에 `PIE enabled`가 표시되어 있음
- `info proc mappings`/`vmmap`을 실행할 때마다 실행 파일 자신의 베이스 주소가 다르게 나옴(ASLR이 켜진 셸에서 직접 실행한 경우)

## 가장 먼저 할 것
가능하면 무조건 심볼 이름으로 건다(`break main`, `break 함수이름`). 심볼이 없는 주소가 꼭 필요할 때만 `start` 이후 `vmmap`/`info proc mappings`로 베이스를 구해서 더하는 절차를 밟는다.

## 단계별 절차

**1) PIE 여부 확인**
```bash
checksec --file=./chall
```

**2) 이름 있는 함수라면 그냥 심볼로 건다**
```gdb
gdb ./chall
break main
break check_password
run
```

**3) raw 오프셋 주소가 꼭 필요하다면 먼저 로드**
```gdb
start
```

**4) 이번 실행의 베이스 확인**
```gdb
info proc mappings
```
또는 Pwndbg:
```
vmmap
```

**5) 베이스 + 오프셋으로 브레이크포인트**
```gdb
break *(0x555555554000 + 0x1349)
```
또는 Pwndbg의 `$rebase` 헬퍼가 있다면:
```gdb
break *$rebase(0x1349)
```

**6) 반복 분석 시 ASLR을 꺼서 베이스를 고정**
```gdb
show disable-randomization
```
GDB 기본값이 `on`이므로 같은 GDB 세션 안에서는 별도 조치 없이도 베이스가 유지된다.

## 명령어/단축키
```bash
checksec --file=./chall
```
```gdb
break main
break FUNC
break *FUNC+OFFSET
start
starti
info proc mappings
vmmap
break *(BASE + OFFSET)
break *$rebase(OFFSET)
show disable-randomization
set disable-randomization on
```

## 출력 해석
- `info proc mappings` 첫 몇 줄 중 대상 바이너리 경로가 적힌 라인의 시작 주소 = 이번 실행의 PIE 베이스.
- `vmmap` 맨 위쪽 줄의 시작 주소도 동일한 정보를 색깔과 함께 보여준다.
- `break *(0x555555554000 + 0x1349)` 실행 후 `Breakpoint 1 at 0x555555555349`처럼 계산된 절대 주소가 그대로 표시되면 계산이 맞게 들어간 것이다.
- 같은 GDB 세션에서 여러 번 `run`을 반복해도 `info proc mappings`의 베이스가 항상 동일하다면, GDB의 `disable-randomization on` 기본값 덕분에 ASLR이 꺼진 상태로 실행되고 있다는 뜻이다.

## 흔한 실수
- 실행 전(run/start 하기 전)에 raw 오프셋 그대로 `break *0x1349`를 거는 것 — 아직 그 주소에 코드가 로드되지 않았을 수 있다.
- 어제/이전 세션에서 계산해둔 `베이스+오프셋` 절대 주소를 오늘 새 GDB 세션에서도 그대로 재사용하는 것 — GDB를 재시작하면 새로운 무작위 베이스가 적용될 수 있다.
- 심볼이 있는 함수인데도 굳이 raw 주소로 계산해서 거는 것 — 계산 실수 여지를 만들 뿐, `break 함수이름`이 항상 더 안전하고 빠르다.
- PIE와 ASLR을 같은 개념으로 혼동해서, "PIE를 끄면 ASLR도 꺼진다"거나 그 반대로 착각하는 것 — PIE는 컴파일 옵션(재배치 가능하게 만듦), ASLR은 커널이 그것을 실제로 무작위 배치하는 기능이다. 자세한 차이는 REV-0103, REV-0104 참고.
- IDA의 정적 분석 뷰 주소와 GDB로 attach한 디버거 뷰 주소를 섞어서 계산하는 것 — IDA도 디버거로 붙이면 자동으로 재베이스된 주소를 보여주므로, 디버거 뷰의 주소를 그대로 쓰는 편이 계산 실수를 줄인다.

## 막혔을 때 다음 체크
- PIE 자체의 원리(왜 오프셋으로 보이는지, ET_DYN이 뭔지)를 더 알고 싶다면 → REV-0103 PIE와 주소 계산
- ASLR이 정확히 무엇을 무작위화하는지, 어떻게 끄는지 알고 싶다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- 일반적인 브레이크포인트 문법 자체가 헷갈린다면 → REV-0186 GDB break와 address breakpoint
- Pwndbg의 `vmmap`을 더 자세히 알고 싶다면 → REV-0193 Pwndbg context telescope vmmap
- 브레이크포인트의 근본 원리(INT3 등)가 궁금하다면 → REV-0169 Breakpoint가 무엇이고 어디에 걸어야 하는가

## 미니 예제
```bash
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Partial RELRO   Canary found      NX enabled    PIE enabled
```
```gdb
$ gdb ./chall
(gdb) break main
Breakpoint 1 at 0x1189: file chall.c, line 10.
(gdb) run
Breakpoint 1, main (argc=1, argv=0x7fffffffe4d8) at chall.c:10
10          char buf[64];
(gdb) info proc mappings
      0x555555554000     0x555555555000     0x1000        0x0  r--p   /home/user/chall
      0x555555555000     0x555555556000     0x1000     0x1000  r-xp   /home/user/chall
(gdb) break *(0x555555554000 + 0x1349)
Breakpoint 2 at 0x555555555349
```
`break main`은 실행 전에 걸어도 그대로 정확히 동작했고, raw 오프셋(`0x1349`)은 `start`/`run` 이후 베이스(`0x555555554000`)를 구한 뒤에야 정확한 절대 주소(`0x555555555349`)로 계산할 수 있었다.

## 관련 글
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0186 — GDB break와 address breakpoint
- REV-0193 — Pwndbg context telescope vmmap
- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가

## 출처/검증
- PIE(`ET_DYN`)의 런타임 재배치와 정적 오프셋 개념: System V ABI ELF 명세(`e_type` 필드) 기준.
- `break`가 심볼 기준으로 런타임 주소를 자동 계산하는 동작, `start`/`starti`, `info proc mappings`, `disable-randomization`: GDB 공식 온라인 문서("Breakpoints", "Starting your Program") 기준.
- Pwndbg `vmmap`, `$rebase()` 헬퍼: Pwndbg 공식 문서(pwndbg.re) 기준. GEF의 `pie break`/`pie run` 전용 명령: GEF 공식 문서(GEF-CTF 사용자 가이드) 기준 (2026-09-08 검증).
