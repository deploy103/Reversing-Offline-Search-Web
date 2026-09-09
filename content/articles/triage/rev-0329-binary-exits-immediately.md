---
id: REV-0329
title: "실행하자마자 바로 종료되는 바이너리 원인 좁히기"
slug: "rev-0329-binary-exits-immediately"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg, strace, ltrace]
keywords: ["바로 종료", "즉시 종료", "실행하자마자 꺼짐", "exit code", "안티디버깅 종료"]
aliases: ["실행이 바로 끝남", "창이 뜨자마자 닫힘", "프로그램이 아무것도 안 하고 종료됨"]
symptom_keywords: ["실행하면 바로 종료됨", "프롬프트도 안 뜨고 꺼짐", "터미널이 바로 닫힘", "exit code가 0이 아님"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
바이너리를 실행하자마자 바로 종료되는 원인은 크게 "정상적인 조기 종료 로직"(인자 누락, 사용법 출력), "환경 문제"(라이브러리/아키텍처 불일치), "안티디버깅에 의한 자폭" 세 갈래로 나뉘며, `echo $?`(exit code)와 `strace`/`ltrace`로 마지막 몇 줄만 봐도 어느 쪽인지 대부분 구분된다.

## 언제 검색해야 하나
- 더블클릭하거나 터미널에서 실행했는데 콘솔 창이 뜨자마자 사라지거나, 프롬프트가 바로 돌아올 때
- 입력을 받을 틈도 없이 프로그램이 끝나버릴 때
- `./chall`을 실행했는데 아무 출력도 없이 셸 프롬프트만 다시 나타날 때
- 디버거로 열면 실행되는데 그냥 실행하면 바로 꺼지는 것 같을 때(이 경우는 REV-0240 계열과도 겹치므로 안티디버깅부터 의심)

## 핵심 개념
"바로 종료"는 원인별로 완전히 다른 처리가 필요하다.

1. **정상적인 조기 종료(사용법 체크)** — `argc`가 예상과 다르면 `printf("usage: %s <arg>\n"); return 1;`처럼 바로 끝나도록 짜여있는 프로그램이 많다. CTF 문제도 인자나 파일 경로를 요구하는 경우가 흔하다.
2. **환경 불일치로 인한 즉시 크래시** — 필요한 공유 라이브러리가 없거나(`error while loading shared libraries`), 32비트 바이너리를 64비트 전용 환경에서 실행하거나, glibc 버전이 안 맞으면 실행 자체가 실패하며 매우 짧게 종료된다.
3. **런타임 자체 검사에 의한 조기 종료** — `ptrace(PTRACE_TRACEME, ...)` 결과 확인, `IsDebuggerPresent`, `/proc/self/status`의 `TracerPid` 값 확인 등으로 디버거가 붙어있는지 체크하고, 붙어있으면 `exit()`를 호출하도록 만든 안티디버깅 로직.
4. **의도된 크래시(버그/취약점 유발용)** — 스택 카나리 훼손 감지, 세그폴트를 유도하는 조건 등으로 즉시 죽는 경우.
5. **버퍼링 때문에 "출력이 안 보였을 뿐" 착각** — 실제로는 몇 초 걸리는데 출력이 flush 안 돼서 아무것도 안 보이다가 프로그램이 끝나는 순간 한꺼번에 나오는 경우도 있다(이건 REV-0330과 겹치는 영역이므로 먼저 `echo $?`로 실제 종료까지 걸린 시간과 exit code를 확인).

## 화면/코드에서 보이는 징후
- 터미널에서 실행 직후 바로 `$` 프롬프트로 돌아옴
- Windows에서 cmd 창이 아주 잠깐 나타났다가 닫힘
- `echo $?`로 확인한 종료 코드가 `1`, `127`, 혹은 `139`(세그폴트, 128+11) 등 0이 아닌 값

## 가장 먼저 할 것
셸에서 직접 실행하고 바로 `echo $?`로 종료 코드를 확인한다(Windows는 `echo %errorlevel%`). 종료 코드만 봐도 "정상 종료(0 또는 1로 usage 출력)"인지 "크래시(비정상 시그널)"인지 절반은 구분된다.

## 단계별 절차

**1) 종료 코드부터 확인**
```bash
./chall
echo $?
```
- `0` 또는 `1`이면 프로그램이 정상적으로 리턴하며 끝난 것 — 인자/입력 요구사항 문제일 가능성이 높다.
- `130`대 이상이면 시그널로 죽은 것(예: `139` = 128+11 = `SIGSEGV`, `134` = 128+6 = `SIGABRT`).

**2) 인자 없이 실행했는지 확인**
```bash
./chall --help
./chall arg1 arg2
```
문제 설명에 "인자로 flag 후보를 준다"는 힌트가 있는지 REV-0012(문제 설명과 첨부파일에서 힌트 뽑는 방법)를 참고해 확인한다.

**3) 라이브러리/아키텍처 문제 확인**
```bash
ldd ./chall
file ./chall
```
`ldd`가 `not found` 항목을 보여주면 라이브러리 문제다. `file`로 32/64비트, 아키텍처가 현재 시스템과 맞는지 확인한다.

**4) strace로 마지막 syscall 확인**
```bash
strace -f ./chall 2>&1 | tail -30
```
`exit_group(1)` 직전에 어떤 syscall이 있었는지 본다. `ptrace(PTRACE_TRACEME, ...)` 호출 후 곧바로 `exit_group`이 보이면 안티디버깅 자폭 패턴이다.

**5) 디버거에서 signal/exit 지점 잡기**
```gdb
catch syscall exit_group
run
bt
```
`exit_group` 호출 직전의 콜스택을 보면 어느 함수가 종료를 결정했는지 알 수 있다. 만약 `catch syscall ptrace`도 걸어서 `ptrace` 호출 직후 조건 분기를 확인하면 안티디버깅 로직인지 바로 확인된다.

**6) 디버거로는 정상 동작하는데 맨몸 실행만 죽는다면**
이는 거의 확실히 안티디버깅이 아니라 "디버거가 특정 환경 변수/타이밍을 바꿔서 우연히 통과"하는 경우일 수 있으니, `strace ./chall`(디버거 없이)과 `strace gdb -batch -ex run ./chall`(디버거로) 결과를 나란히 비교(diff)해 어디서 갈라지는지 찾는다.

## 명령어/단축키
```bash
echo $?                      # 직전 명령 종료 코드
ldd ./chall                  # 공유 라이브러리 확인
file ./chall                 # 아키텍처/비트 확인
strace -f ./chall            # 시스템 콜 추적
ltrace ./chall                # 라이브러리 함수 호출 추적
```
GDB: `catch syscall exit_group`, `catch syscall ptrace`, `run`, `bt`

## 출력 해석
- `error while loading shared libraries: libfoo.so.1: cannot open shared object file` → 라이브러리 누락, 환경 문제이지 로직 문제가 아니다.
- `exit_group(1)` 직전에 `ptrace(PTRACE_TRACEME, 0, NULL, NULL) = -1 EPERM` 이 보이면, 이미 디버거가 붙어 `ptrace`가 실패했고 그걸 감지해 종료한 것 — 대표적인 자기 자신에 대한 `PTRACE_TRACEME` 안티디버깅.
- `Segmentation fault (core dumped)`가 뜨면 종료 코드 139, 이건 안티디버깅이 아니라 실제 크래시일 가능성이 높다.

## 흔한 실수
- 인자 없이 실행해보고 "버그다"라고 단정하는 것 — 먼저 `--help`나 문제에 주어진 사용법을 확인해야 한다.
- 종료 코드를 확인하지 않고 무작정 디스어셈블리부터 뒤지는 것 — `echo $?` 한 줄이면 크래시인지 정상 종료인지 바로 갈린다.
- 디버거를 붙였더니 멀쩡히 동작해서 "문제 없네"라고 넘어가는 것 — 오히려 디버거 유무로 동작이 달라진다는 것 자체가 안티디버깅의 강력한 증거다.
- `strace`/`ltrace`가 정적 링킹 바이너리에서 라이브러리 호출을 못 보여줄 때 "도구가 고장났다"고 오해하는 것(REV-0698 참고).

## 막혔을 때 다음 체크
- 디버거 유무로 동작이 달라진다면 → REV-0240 디버거에서 갑자기 종료될 때 체크리스트.
- `ptrace` 기반 자폭이 확인되면 → REV-0234 ptrace PTRACE_TRACEME 안티디버깅.
- `strace`가 정적 바이너리에서 아무것도 안 보여준다면 → REV-0698 ltrace가 정적 바이너리에서 아무것도 안 보여줄 때.
- 라이브러리 문제라면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향.

## 미니 예제
```bash
$ ./chall
$ echo $?
1

$ strace ./chall
execve("./chall", ["./chall"], 0x7ffd...) = 0
...
write(1, "usage: ./chall <password>\n", 27) = 27
exit_group(1)                           = ?
+++ exited with 1 +++
```
`write`로 usage 메시지를 찍고 `exit_group(1)`로 끝난 것이 보이므로, 이건 버그도 안티디버깅도 아니라 단순히 인자를 안 줘서 생긴 정상 종료다. 인자를 채워서 다시 실행하면 된다.

## 관련 글
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0698 — ltrace가 정적 바이너리에서 아무것도 안 보여줄 때
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향

## 출처/검증
- 종료 코드와 시그널 번호의 관계(128+N): POSIX 셸 종료 상태 규약(Bash 매뉴얼 "Exit Status") 기준 (2026-09-09 검증).
- `strace`/`ltrace` 사용법과 출력 형식: strace(1), ltrace(1) man page 기준.
- `PTRACE_TRACEME` 기반 셀프 안티디버깅 원리: Linux `ptrace(2)` man page 기준.
