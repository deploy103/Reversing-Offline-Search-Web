---
id: REV-0696
title: "동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때"
slug: "rev-0696-breakpoint-symbol-missing-dynamic"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, "objdump"]
keywords: ["break malloc", "Function not defined", "pending breakpoint", "PLT 브레이크포인트", "stripped 바이너리 브레이크포인트", "GDB break symbol"]
aliases: ["gdb break 안됨", "함수 이름으로 브레이크 안 걸림", "malloc에 브레이크 안 걸림", "stripped 함수 브레이크포인트"]
symptom_keywords: ["Function \"malloc\" not defined 뜸", "break foo 했는데 No symbol table is loaded", "라이브러리 함수에 breakpoint가 안 걸림", "stripped 바이너리에서 함수 이름으로 break 불가"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB에서 `break malloc`처럼 이름으로 브레이크포인트를 걸었는데 `Function "malloc" not defined.`가 뜨는 이유는 대부분 **그 함수의 심볼이 아직 GDB에 로드되지 않았기 때문**이며, 실행 전(libc 미로드) 상태라면 `set breakpoint pending on` 또는 프롬프트에서 `y`로 pending 처리하면 되고, 바이너리 자체가 strip되어 심볼이 아예 없다면 이름 대신 **PLT 스텁 주소**나 정적 분석으로 찾은 **raw 주소**에 `break *0x...`로 걸어야 한다.

## 언제 검색해야 하나
- `gdb ./chall` 실행 후 `break malloc`, `break printf` 같은 명령을 쳤는데 `Function "malloc" not defined.`가 뜰 때
- strip된 바이너리에서 함수 이름 자체가 안 보여서 어디에 브레이크포인트를 걸어야 할지 막막할 때
- PIE 바이너리에서 정적 분석으로 찾은 주소에 브레이크포인트를 걸었는데 실행할 때마다 다른 곳에서 멈추거나 아예 안 걸릴 때

## 핵심 개념

### GDB는 "지금 알고 있는 심볼"에만 이름으로 브레이크를 걸 수 있다
GDB가 `break 함수이름`을 처리하려면 그 이름이 어느 주소에 대응하는지 알아야 한다. 이 정보는 크게 두 군데서 온다.

1. **디버그 정보(DWARF)** — `gcc -g`로 컴파일된 바이너리라면 함수 이름과 주소, 소스 라인이 모두 들어있다.
2. **심볼 테이블(`.symtab`/`.dynsym`)** — 디버그 정보가 없어도 심볼 테이블에 이름이 남아있으면 GDB가 최소 심볼(minimal symbol)로 인식한다.

문제는 **동적 링킹된 라이브러리 함수(`malloc`, `printf`, `strcpy` 등)의 실제 코드는 실행 파일 안에 없다**는 점이다. 실행 파일에는 그 함수를 가리키는 PLT 스텁과 `.dynsym`에 이름만 있을 뿐, 진짜 함수 본체는 `libc.so.6`가 메모리에 로드된 뒤에야 존재한다(REV-0100, REV-0101 참고). GDB를 막 실행한 직후(`run`을 아직 안 한 상태)에는 아직 어떤 공유 라이브러리도 메모리에 매핑되지 않았으므로, GDB는 `malloc`이라는 이름이 나중에 libc의 어느 주소에 자리 잡을지 아직 모른다. 이때 `break malloc`을 치면 `Function "malloc" not defined.`가 뜨는 것이다.

### strip된 바이너리는 이름 자체가 없다
CTF 문제 바이너리는 흔히 `strip` 처리되어 `.symtab`이 제거된다(`.dynsym`은 동적 링킹에 필요하므로 보통 남아있다). 이 경우 `main`이나 사용자 정의 함수처럼 **바이너리 자신이 정의한 함수**는 이름이 아예 사라져서 `break main`도 실패한다. 반면 `malloc`, `printf`처럼 **외부에서 가져다 쓰는(import) 함수**는 `.dynsym`에 이름이 남아있는 경우가 많아 `break malloc`은 되는데 `break vuln_func`는 안 되는 비대칭이 자주 발생한다.

## 화면/코드에서 보이는 징후
```text
(gdb) break malloc
Function "malloc" not defined.
Make breakpoint pending on future shared library load? (y or [n])
```
또는 pending 질문 없이 바로:
```text
(gdb) break vuln_func
Function "vuln_func" not defined.
```

## 가장 먼저 할 것
1. 프롬프트에 `Make breakpoint pending on future shared library load? (y or [n])`이 떴다면 **`y`를 입력**한다. libc가 로드되는 순간 자동으로 실제 주소에 브레이크포인트가 걸린다.
2. 그런 프롬프트조차 안 뜨고 바로 `not defined`만 나왔다면(주로 사용자 정의 함수가 strip된 경우), 심볼이 아예 없는 것이므로 이름 대신 **주소**로 걸어야 한다.

## 단계별 절차

### 케이스 A: 라이브러리 함수(malloc, printf 등)에 브레이크포인트가 안 걸릴 때
1. 매번 `y`를 누르기 귀찮다면 아예 처음부터 pending을 기본값으로 켠다.
   ```gdb
   (gdb) set breakpoint pending on
   (gdb) break malloc
   Breakpoint 1 (malloc) pending.
   ```
2. `run`으로 실행하면 동적 링커(`ld.so`)가 libc를 매핑하는 시점에 pending 브레이크포인트가 실제 주소로 확정되며 정상 동작한다.
3. libc가 로드된 뒤에 다시 걸고 싶다면, 프로그램을 한 번 `run`으로 끝까지 실행하거나 `start`로 `main`까지만 진행한 뒤(이때는 libc가 이미 로드됨) `break malloc`을 치면 pending 없이 바로 걸린다.

### 케이스 B: PLT 스텁 주소로 직접 거는 방법 (동적 링킹 이전 시점부터 잡고 싶을 때)
동적 링킹된 함수를 프로그램 실행 아주 초반부터(예: `_start` 직후) 잡고 싶다면, PLT 스텁은 실행 파일 자신의 코드 영역이라 처음부터 항상 매핑되어 있으므로 그 주소에 걸면 pending 없이도 확실하다.
```bash
objdump -d -j .plt ./chall | grep -A1 "malloc@plt"
```
출력에서 `malloc@plt`의 주소(예: `0x401030`)를 확인한 뒤:
```gdb
(gdb) break *0x401030
```
PIE 바이너리라면 이 주소는 링크 타임 오프셋이므로, 실행 후 실제 주소는 `로드 베이스 + 오프셋`이 된다. `info proc mappings`나 Pwndbg의 `vmmap`으로 로드 베이스를 확인한 뒤 더해서 걸거나, GDB가 알아서 오프셋 처리를 하도록 심볼 이름 대신 `break *malloc@plt`처럼 표기하면 GDB가 자동으로 계산해준다(단, 이 표기가 항상 모든 GDB 버전에서 지원되는 것은 아니므로 안 되면 직접 계산한다).

### 케이스 C: strip된 사용자 정의 함수에 이름으로 브레이크가 안 걸릴 때
1. 정적 분석(Ghidra, IDA, `objdump -d`)으로 함수의 **파일 오프셋 기준 주소**를 먼저 찾는다.
2. Non-PIE 바이너리라면(`checksec`으로 확인, REV-0096) 정적 분석 주소를 그대로 사용한다.
   ```gdb
   (gdb) break *0x401196
   ```
3. PIE 바이너리라면 ASLR을 끄고 재현 가능하게 만드는 편이 훨씬 편하다.
   ```gdb
   (gdb) set disable-randomization on
   (gdb) break *0x1196
   ```
   ASLR을 끄면 로드 베이스가 항상 `0x555555554000`(64비트 기본값) 등 고정값이 되므로, 정적 분석에서 본 오프셋을 그대로 베이스에 더한 절대 주소에 걸면 된다. Pwndbg를 쓰면 `pie break 0x1196`처럼 오프셋 기준으로 바로 거는 헬퍼 명령도 있다(Pwndbg 버전에 따라 지원 여부 확인).

## 명령어/단축키
```gdb
set breakpoint pending on
break malloc
break *0x401030
break *malloc@plt
set disable-randomization on
info proc mappings
```
```bash
objdump -d -j .plt ./chall
readelf -r ./chall   # .rela.plt에서 함수별 GOT 엔트리 확인
```

## 출력 해석
- `Breakpoint 1 (malloc) pending.`은 브레이크포인트가 걸린 게 **아니라 예약된** 상태라는 뜻이다. `info breakpoints`로 확인하면 `<PENDING>` 표시가 남아있고, 실제로 라이브러리가 로드되면 이 표시가 사라지고 정상 브레이크포인트로 바뀐다.
- `break *0x401030`처럼 주소로 걸면 함수 이름 없이 `Breakpoint 1 at 0x401030`만 뜬다 — 정상이며, 심볼이 없어서 이름을 못 보여주는 것뿐이다.
- PIE 바이너리에서 ASLR을 끄지 않고 정적 분석 주소 그대로 걸면 실행할 때마다 다른 곳에서 멈추거나 아예 안 멈춘다. 이 증상이 보이면 `set disable-randomization on`을 빼먹은 것이다.

## 흔한 실수
- `Function not defined` 메시지를 보고 "이 함수는 존재하지 않는다"고 오해하는 것. 실제로는 존재하지만 GDB가 아직 그 위치를 모를 뿐이다.
- pending 프롬프트에서 매번 `n`을 눌러버려서 브레이크포인트가 아예 무시되는 것.
- PIE 바이너리에서 정적 분석 주소를 로드 베이스 보정 없이 그대로 `break *0x...`에 쓰는 것.
- strip된 함수를 이름으로 걸려고 반복 시도하는 것 — strip된 함수는애초에 이름 정보가 없으므로 주소 기반 접근으로 전환해야 한다.

## 막혔을 때 다음 체크
- PLT/GOT 구조 자체가 헷갈린다면 → REV-0100 PLT와 GOT 기초
- 동적 링킹 전체 흐름이 궁금하다면 → REV-0101 Dynamic Linking과 Import 함수 추적
- PIE에서 왜 주소가 매번 바뀌는지 원리가 궁금하다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- 아예 정적 링킹된 바이너리라 이런 pending 이슈 자체가 다르게 나타난다면 → REV-0698 ltrace가 정적 바이너리에서 아무것도 안 보여줄 때
- 브레이크포인트는 걸었는데 그 지점에서 왜 죽는지 원인을 못 찾겠다면 → REV-0703 Segmentation fault가 나는데 원인 위치를 못 찾을 때

## 미니 예제
```text
$ gdb -q ./chall
(gdb) set breakpoint pending on
(gdb) break malloc
Breakpoint 1 (malloc) pending.
(gdb) run
Starting program: /home/user/chall

Breakpoint 1, 0x00007ffff7e1c150 in malloc () from /lib/x86_64-linux-gnu/libc.so.6
(gdb) bt
#0  0x00007ffff7e1c150 in malloc () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x0000555555555216 in vuln_func ()
#2  0x000055555555529e in main ()
```
`set breakpoint pending on`을 미리 켜두었기 때문에 `run` 직후 libc가 로드되자마자 `malloc`에서 정상적으로 멈췄다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0096 — checksec 결과 읽는 법
- REV-0698 — ltrace가 정적 바이너리에서 아무것도 안 보여줄 때
- REV-0703 — Segmentation fault가 나는데 원인 위치를 못 찾을 때

## 출처/검증
- GDB의 pending breakpoint 동작(`set breakpoint pending`, `Make breakpoint pending on future shared library load?` 프롬프트)은 GDB 공식 온라인 문서(sourceware.org, "Set Breaks") 및 "Break Conditions" 섹션에 기술된 표준 동작이다.
- PLT/GOT를 통한 동적 함수 호출 구조와 라이브러리가 실행 초반에는 매핑되어 있지 않다는 사실은 System V ABI(x86-64 psABI)의 동적 링킹 절차 설명에 기반한다.
- `set disable-randomization on`은 GDB가 `personality(ADDR_NO_RANDOMIZE)`를 사용해 자식 프로세스의 ASLR을 끄는 기능으로, GDB 공식 문서 "Starting your Program" 섹션에 문서화되어 있다.
- 정확한 프롬프트 문구와 Pwndbg의 PIE 오프셋 브레이크 헬퍼 이름은 GDB/Pwndbg 버전에 따라 달라질 수 있어, 실제 사용 중인 버전에서 `help break`, Pwndbg의 `pie` 명령 도움말로 재확인을 권장한다.
