---
id: REV-0185
title: "GDB 실행 run start args 사용법"
slug: "rev-0185-gdb-run-start-args"
category: "dynamic-analysis"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb run", "gdb start", "gdb args", "set args", "starti", "gdb 실행 인자", "gdb 진입점"]
aliases: ["gdb 실행하는법", "gdb run 명령어", "gdb start 명령어", "gdb 인자 전달", "gdb 프로그램 시작"]
symptom_keywords: ["gdb에서 프로그램이 안 켜짐", "gdb run 했는데 바로 끝남", "gdb에 인자 넣는법 모름", "gdb main에서 바로 멈추고 싶음", "gdb 실행하자마자 멈추는법"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB에서 프로그램을 동적으로 분석하려면 먼저 `gdb ./chall`로 바이너리를 로드한 뒤, 그냥 끝까지 돌리는 `run`, `main` 진입 직전에 자동으로 멈추는 `start`, 명령줄 인자를 넘기는 `set args`/`run arg1 arg2`, 아예 첫 명령어에서 멈추는 `starti` 중 상황에 맞는 시작 방법을 골라야 한다.

## 언제 검색해야 하나
- `gdb ./chall`까지는 켰는데 그다음 뭘 입력해야 프로그램이 실제로 돌기 시작하는지 모를 때
- `run`을 눌렀더니 프로그램이 끝까지 실행되고 그냥 종료 메시지만 뜰 때(브레이크포인트를 안 걸어서)
- 대상 프로그램이 `./chall input.txt` 처럼 명령줄 인자를 받아야 하는데, GDB 안에서 어떻게 인자를 넘기는지 모를 때
- `main`이 실행되기 직전, 또는 라이브러리가 로드되기 직전처럼 아주 이른 시점에서 멈추고 싶은데 어떤 명령을 써야 할지 모를 때
- PIE 바이너리의 진짜 로드 베이스 주소를 보고 싶어서 `main`보다도 더 앞선 시점(엔트리 포인트)에서 멈추고 싶을 때

## 핵심 개념

### GDB에 바이너리를 로드하는 것과 "실행"은 다른 단계다
`gdb ./chall`(또는 실행 중 `file ./chall`)을 입력하면 GDB는 바이너리를 **읽어서 심볼 테이블과 디스어셈블리 정보를 파싱**할 뿐, 아직 프로세스를 만들지 않는다. 이 상태에서 `info registers`나 `x/10i $rip`을 치면 "프로세스가 없다"는 취지의 에러가 난다. 실제로 프로세스를 fork/exec해서 메모리에 올리는 건 `run`이나 `start` 같은 명령이 담당한다. 이 구분을 모르면 "왜 레지스터가 안 보이지?"라는 흔한 초보 질문이 나온다.

### `run` — 그냥 끝까지 돌린다
`run`(줄여서 `r`)은 프로그램을 실행시키고, 브레이크포인트가 없으면 **끝까지** 실행한 뒤 종료 코드와 함께 GDB 프롬프트로 돌아온다. 분석 없이 그냥 프로그램이 어떻게 동작하는지 한 번 보고 싶을 때, 또는 미리 `break`로 원하는 지점을 걸어둔 뒤 그 지점까지 빠르게 진행시키고 싶을 때 쓴다. 브레이크포인트가 하나도 없는 상태에서 `run`을 치면 그냥 프로그램이 자연 종료될 때까지 GDB가 관여하지 않으므로, "run 했더니 그냥 끝나버렸어요"라는 증상은 대부분 **브레이크포인트를 안 걸었다**는 뜻이다.

### `start` — main 진입 직전에 자동으로 멈춘다
`start`는 내부적으로 `main` 함수에 **임시 브레이크포인트(tbreak)**를 걸고 `run`을 실행하는 것과 같다. 즉:
```gdb
tbreak main
run
```
을 한 번에 해주는 단축 명령이다. `main`에서 멈춘 뒤에는 그 임시 브레이크포인트가 자동으로 삭제되므로, 이후 프로그램을 몇 번을 다시 `run`해도 `start`처럼 다시 걸리진 않고 그냥 끝까지 실행된다(원한다면 `main`에 `break`를 따로 걸어두면 된다). `start`는 실전에서 가장 많이 쓰이는 진입 명령이다 — 라이브러리와 동적 링커의 초기화가 이미 끝났고, PIE 바이너리라면 로드 베이스도 이미 확정된 상태이기 때문에, 이 시점부터는 `info proc mappings`로 정확한 런타임 주소를 조회할 수 있다.

### `starti` — 그보다도 더 앞선 진입점(엔트리 포인트)에서 멈춘다
`starti`는 `main`보다도 훨씬 이른 시점, ELF의 `e_entry`가 가리키는 **진짜 프로그램 시작 지점**(보통 `_start`)에서 멈춘다. `main`이 호출되기 전에 스택 초기화, `argc`/`argv` 설정, 동적 링커의 라이브러리 로딩 과정을 명령어 단위로 지켜보고 싶을 때 사용한다. 초보자가 당장 필요한 경우는 많지 않지만, "동적 링킹이 정확히 언제 일어나는지" 또는 "PIE 베이스가 결정되는 순간을 최대한 앞에서 잡고 싶을 때" 유용하다.

### 명령줄 인자 넘기기: `set args`와 `run` 뒤에 바로 쓰는 방법
GDB 밖에서 `./chall hello 123`처럼 인자를 주며 실행하던 프로그램이라면, GDB 안에서도 똑같이 인자를 넘겨야 프로그램이 정상 동작한다. 두 가지 방법이 있다.
```gdb
set args hello 123
run
```
또는 한 줄로:
```gdb
run hello 123
```
`run` 뒤에 인자를 직접 쓰면 그 인자가 그대로 `set args`처럼 저장되어, 이후 다시 `run`만 쳐도 같은 인자가 재사용된다. 표준 입력으로 데이터를 넣어야 하는 프로그램이라면(`./chall < input.txt`) 리다이렉션도 그대로 쓸 수 있다:
```gdb
run < input.txt
```
파일 경로, 환경변수를 다르게 주고 싶다면 `set environment VAR=value`, 실행 시 작업 디렉터리를 바꾸고 싶다면 `cd /path`도 GDB 안에서 지원한다.

### GDB를 실행할 때부터 인자를 함께 넘기는 방법
매번 `set args`를 치기 귀찮다면 셸에서 GDB를 켤 때 `--args` 옵션으로 한 번에 지정할 수 있다:
```bash
gdb --args ./chall hello 123
```
이렇게 하면 GDB 안에서 그냥 `run`만 쳐도 `hello 123` 인자가 자동으로 붙는다. CTF에서 exploit 스크립트와 함께 자동화할 때 특히 편리한 방식이다.

### 여러 번 실행하기: 재시작과 상태 초기화
브레이크포인트에서 멈춘 뒤 다시 처음부터 실행하고 싶다면 `kill`로 현재 프로세스를 종료하고 다시 `run`(또는 `start`)을 치면 된다. GDB는 종료되지 않은 프로세스에서 `run`을 다시 치면 "다시 시작할까요?(y/n)"라고 물어본다.

## 화면/코드에서 보이는 징후
- `gdb ./chall` 직후 `(gdb)` 프롬프트만 뜨고 아직 아무 레지스터도 없는 상태
- `run`을 쳤는데 아무 브레이크포인트도 안 걸려 있어서 `[Inferior 1 (process 12345) exited normally]` 메시지와 함께 그냥 끝나버림
- `Missing separate debuginfos` 경고(디버그 심볼이 없다는 뜻, 분석에는 큰 지장 없음)
- `start` 실행 시 `Temporary breakpoint 1, 0x0000... in main ()`처럼 `main`에서 멈췄다는 메시지
- 프로그램이 인자를 요구하는데 안 줘서 `Usage: ./chall <file>`처럼 사용법 메시지만 찍고 바로 종료되는 경우

## 가장 먼저 할 것
분석 목적이 "일단 `main` 시작부터 천천히 보고 싶다"라면 그냥 `gdb ./chall` 후 `start`를 치는 것이 가장 빠른 시작이다. 프로그램이 명령줄 인자나 표준입력을 요구한다면 `start` 전에 `set args ...`부터 설정해둔다.

## 단계별 절차

**1) GDB로 바이너리 로드**
```bash
gdb ./chall
```
또는 인자까지 한 번에:
```bash
gdb --args ./chall input.txt
```

**2) (필요하면) 인자/표준입력 설정**
```gdb
set args input.txt
```

**3) 진입 방식 선택**
```gdb
start        # main 직전에서 멈춤 (가장 흔한 선택)
```
또는
```gdb
run          # 브레이크포인트 없이 끝까지 실행
```
또는
```gdb
starti       # 엔트리 포인트(_start)에서 멈춤
```

**4) 멈춘 뒤 상태 확인**
```gdb
info registers
bt
```

**5) 이후 진행**
`break`로 원하는 지점에 브레이크포인트를 추가로 걸고 `continue`로 이어서 진행한다(REV-0186, REV-0187 참고).

## 명령어/단축키
```gdb
gdb ./chall
gdb --args ./chall arg1 arg2
run
run arg1 arg2
run < input.txt
set args arg1 arg2
start
starti
kill
```

## 출력 해석
- `start` 직후 뜨는 `Temporary breakpoint 1, 0x0000555555555185 in main ()`에서 `0x0000555555555185`는 PIE 베이스가 이미 반영된 **실제 런타임 주소**다. 이 값을 그대로 이후 분석에 활용할 수 있다.
- `run`만으로 종료됐을 때 나오는 `[Inferior 1 (process N) exited normally]`은 브레이크포인트 없이 프로그램이 정상 종료했다는 뜻이다. `exited with code 01`처럼 코드가 붙으면 비정상 종료(0이 아닌 반환값)다.
- `starti` 직후에는 아직 라이브러리가 매핑되지 않았을 수 있어 `info proc mappings`가 실행 파일 자신만 보여줄 수 있다. 라이브러리까지 보고 싶다면 `start`를 쓰는 게 낫다.

## 흔한 실수
- 인자를 요구하는 프로그램에 `set args` 없이 그냥 `run`을 쳐서 "Usage" 메시지만 보고 왜 코드가 안 보이는지 헤매는 것.
- 브레이크포인트를 하나도 안 걸고 `run`을 쳐서 프로그램이 끝까지 실행돼버린 뒤 "GDB가 멈추질 않아요"라고 착각하는 것 — GDB는 아무것도 안 시키면 그냥 정상 실행만 시켜준다.
- `start`가 `main`에 건 임시 브레이크포인트를 영구 브레이크포인트로 착각하는 것 — `start` 이후 다시 `run`을 하면 `main`에서 자동으로 멈추지 않는다. 계속 `main`에서 멈추고 싶다면 `break main`을 별도로 걸어야 한다.
- `gdb --args`를 쓰지 않고 `gdb ./chall arg1 arg2`처럼 인자를 그냥 뒤에 붙여서 GDB 자체가 이상하게 파싱하는 것.

## 막혔을 때 다음 체크
- 특정 함수나 주소에 정확히 멈추고 싶다면 → REV-0186 GDB break와 address breakpoint
- 멈춘 뒤 한 줄씩 실행하고 싶다면 → REV-0187 GDB stepi nexti continue
- PIE 바이너리라 주소가 매번 바뀌어서 브레이크포인트가 안 걸린다면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기

## 미니 예제
```bash
$ gdb --args ./chall secret.txt
GNU gdb (Ubuntu 12.1) ...
Reading symbols from ./chall...
(gdb) start
Temporary breakpoint 1 at 0x1189: file chall.c, line 10.
Starting program: /home/user/chall secret.txt
Temporary breakpoint 1, main (argc=2, argv=0x7fffffffe4d8) at chall.c:10
10          char buf[64];
(gdb) info registers rip
rip            0x555555555189      0x555555555189 <main+8>
```
`argc=2, argv=0x7fffffffe4d8`가 보이는 것으로 `secret.txt` 인자가 제대로 전달됐음을 확인할 수 있다.

## 관련 글
- REV-0186 — GDB break와 address breakpoint
- REV-0187 — GDB stepi nexti continue
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기

## 출처/검증
- `run`, `start`, `starti`, `set args`, `--args` 옵션: GDB 공식 온라인 문서("Starting your Program", "Arguments") 기준.
- `tbreak main` + `run` 조합이 `start`와 동일하다는 설명: GDB 공식 문서의 `start` 명령 설명 기준 (2026-09-08 검증).
