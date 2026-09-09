---
id: REV-0686
title: "GDB에서 No symbol table is loaded 오류가 뜰 때"
slug: "rev-0686-gdb-no-symbol-table-is-loaded"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["No symbol table is loaded", "gdb file command", "gdb 심볼 테이블 없음", "gdb break 안됨", "gdb list 안됨"]
aliases: ["gdb no symbol table", "gdb symbol table is loaded 오류", "gdb use the file command"]
symptom_keywords: ["gdb에서 break main 했더니 No symbol table is loaded가 뜸", "gdb list 했더니 No symbol table is loaded", "gdb 실행하자마자 아무 파일도 안 물려있음", "gdb Use the file command 메시지"]
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`No symbol table is loaded.  Use the "file" command.`은 GDB에 **아직 분석 대상 실행 파일 자체가 물려있지 않은 상태**에서 `break`, `list`, `info line` 같은 심볼 기반 명령을 쳤을 때 나오는 안내 메시지이며, 해결책은 GDB를 켤 때 `gdb ./chall`처럼 바이너리를 인자로 주거나 이미 켜진 GDB 안에서 `file ./chall`로 직접 로드하는 것이다.

## 언제 검색해야 하나
- 터미널에 그냥 `gdb`만 치고 들어간 뒤 `break main`을 입력했는데 `No symbol table is loaded.  Use the "file" command.`가 뜰 때
- `list main`이나 `info line main`을 쳤는데 같은 메시지가 뜰 때
- GDB 스크립트(`-x script.gdb`)나 `.gdbinit`에서 `break` 명령이 실행 파일 로드보다 먼저 실행되어 같은 오류가 스크롤되어 지나갈 때
- 이 메시지가 "바이너리가 stripped라서 나는 오류"인지 "애초에 파일을 안 물려서 나는 오류"인지 구분이 안 갈 때

## 핵심 개념

### 이 메시지는 "심볼이 없다"가 아니라 "물린 파일 자체가 없다"는 뜻
GDB는 세션을 시작할 때 디버깅 대상 실행 파일(objfile)을 지정받지 않으면 내부적으로 아무 심볼 테이블도 갖고 있지 않은 빈 상태로 대기한다. 이 상태에서 함수 이름이나 소스 라인을 참조하는 명령(`break FUNC`, `list`, `info line`)을 쓰면, GDB는 "찾아볼 심볼 테이블 자체가 없다. `file` 명령으로 로드해라"라고 정확히 안내해준다. 이는 **바이너리가 stripped(심볼 제거됨)인 경우**(→ REV-0689 참고)와는 다른 상황이다. stripped 바이너리는 일단 파일이 로드는 됐지만 그 안에 찾는 심볼이 없는 경우이고, 이 문서의 상황은 애초에 아무 파일도 로드되지 않은 경우다.

### 어떤 상황에서 "파일 없이" GDB가 켜지는가
- 터미널에서 그냥 `gdb`만 입력하고 실행 파일 경로를 인자로 주지 않은 경우
- `gdb -p <PID>`로 이미 실행 중인 프로세스에 attach는 했지만, 어떤 이유로 GDB가 해당 프로세스의 실행 파일을 자동으로 못 찾은 경우(권한 문제, 컨테이너 안 PID 등)
- `.gdbinit` 스크립트나 `-x` 옵션으로 넘긴 명령 파일 맨 위에 `break main` 같은 줄이 있는데, 정작 그 스크립트를 실행 파일 지정 없이(`gdb -x script.gdb`, 대상 없이) 돌린 경우
- core 파일만 열고(`gdb core`) 원본 실행 파일은 같이 지정하지 않은 경우

## 화면/코드에서 보이는 징후
```text
(gdb) break main
No symbol table is loaded.  Use the "file" command.
(gdb) list
No symbol table is loaded.  Use the "file" command.
```
- GDB 프롬프트가 뜬 직후, 어떤 심볼 기반 명령을 쳐도 같은 문구가 반복됨
- `info files`를 쳤을 때 `No executable file now.`처럼 실행 파일이 아예 없다고 나옴

## 가장 먼저 할 것
`info files`를 쳐서 지금 GDB에 실행 파일이 물려있는지부터 확인한다. `No executable file now.`가 나오면 파일이 전혀 로드되지 않은 상태이므로, `file ./chall`로 바로 로드한다.

## 단계별 절차

**1) 현재 상태 확인**
```gdb
(gdb) info files
```

**2) 파일이 없다면 file 명령으로 로드**
```gdb
(gdb) file ./chall
Reading symbols from ./chall...
```
경로가 상대 경로라면 GDB를 실행한 셸의 현재 디렉터리 기준이라는 점에 주의한다(바이너리가 있는 디렉터리로 먼저 `cd`하거나 절대 경로를 쓴다).

**3) 애초에 GDB를 켤 때 같이 지정하는 편이 더 안전**
```bash
gdb ./chall
gdb -q ./chall
gdb --args ./chall arg1 arg2
```
`--args`를 쓰면 프로그램 인자까지 함께 지정한 뒤 `run`만 치면 된다.

**4) attach 상황이라면 file을 먼저, attach를 나중에**
```gdb
(gdb) file ./chall
(gdb) attach 1234
```
`gdb -p 1234`만으로 시작했는데 심볼이 하나도 안 잡히는 것 같다면, `file` 명령으로 그 PID에 해당하는 실행 파일 경로(`/proc/1234/exe`를 `ls -l`로 확인)를 명시적으로 지정해준다.

**5) 그래도 안 된다면 stripped 여부 확인**
```bash
file ./chall
readelf -S ./chall | grep -i symtab
```
`file` 로드는 성공했는데 여전히 `break FUNC`에서 비슷한 문제가 나면, 이번엔 다른 오류(`Function "FUNC" not defined.`)일 가능성이 높다 — REV-0689를 참고한다.

## 명령어/단축키
```bash
gdb ./chall
gdb -q ./chall
gdb --args ./chall arg1
```
```gdb
info files
file ./chall
file ./chall core
```
```bash
file ./chall           # 셸의 file 명령: ELF인지, stripped인지 확인
readelf -S ./chall | grep -i symtab
```

## 출력 해석
- `Reading symbols from ./chall...` (버전에 따라 뒤에 `(no debugging symbols found)`가 붙을 수 있음) — 파일이 정상적으로 로드됐다는 뜻. `(no debugging symbols found)`는 DWARF 소스 라인 정보가 없다는 뜻이지, `.symtab`(함수 이름)까지 없다는 뜻은 아니다. `break FUNC`는 `.symtab`만 있어도 대체로 동작한다.
- `info files`에서 실행 파일 경로와 `Entry point:` 주소가 출력되면 정상적으로 물려있는 상태다.
- `readelf -S ./chall | grep -i symtab`에서 아무 것도 안 나오면 `.symtab`이 제거된(stripped) 바이너리라는 뜻이다.

## 흔한 실수
- 이 메시지를 "바이너리가 stripped됐다"는 뜻으로 오해하고 곧바로 IDA/Ghidra로 넘어가는 것 — 사실은 단순히 `file` 명령을 안 쳐서 나는 경우가 훨씬 많다.
- 상대 경로로 `file chall`을 쳤는데 GDB의 현재 디렉터리가 바이너리 위치와 달라서 `chall: No such file or directory.`가 또 뜨는 것 — 이 경우는 REV-0688을 참고한다.
- `.gdbinit`에 `break main`을 무조건 먼저 써두고, 정작 `gdb`를 파일 인자 없이 켜서 매번 이 오류를 보는 것 — `.gdbinit`에는 파일별로 다른 심볼 기반 명령을 넣기보다 `file` 로드 이후에만 의미 있는 명령을 넣거나, `gdb ./chall -x script.gdb` 형태로 항상 파일과 함께 실행하는 습관을 들인다.

## 막혔을 때 다음 체크
- stripped 바이너리에서 함수 이름으로 브레이크포인트가 안 걸릴 때 → REV-0689 GDB에서 breakpoint를 걸었는데 Function not defined라고 할 때
- 파일 경로 자체가 있는데도 GDB가 못 찾는다고 할 때 → REV-0688 GDB에서 No such file or directory 오류가 뜰 때
- core 파일과 함께 여는 절차가 궁금하면 → REV-0113 Core dump와 크래시 지점 분석 기초
- stripped와 심볼 있는 바이너리의 차이 자체가 궁금하면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 미니 예제
```bash
$ gdb
GNU gdb (Ubuntu 12.1-0ubuntu1~22.04) 12.1
(gdb) break main
No symbol table is loaded.  Use the "file" command.
(gdb) file ./chall
Reading symbols from ./chall...
(gdb) break main
Breakpoint 1 at 0x1189: file chall.c, line 10.
(gdb) run
Breakpoint 1, main (argc=1, argv=0x7fffffffe4d8) at chall.c:10
10          char buf[64];
```
`file ./chall`을 실행하고 나서야 `break main`이 정상적으로 주소를 계산해 브레이크포인트를 걸었다.

## 관련 글
- REV-0689 — GDB에서 breakpoint를 걸었는데 Function not defined라고 할 때
- REV-0688 — GDB에서 No such file or directory 오류가 뜰 때
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 출처/검증
- `No symbol table is loaded.  Use the "file" command.` 메시지와 `file` 명령의 역할: GDB 공식 온라인 문서("Commands to Specify Files", "Specifying a Debugging Target") 기준.
- `.symtab`과 DWARF 디버그 정보(`-g`)의 차이: readelf/DWARF 일반 지식 및 GDB 문서 "Debugging Information in Separate Files" 기준 (2026-09-08 검증).
