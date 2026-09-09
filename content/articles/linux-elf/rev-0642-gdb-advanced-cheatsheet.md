---
id: REV-0642
title: "GDB 명령어 심화 치트시트(watch/catch/tbreak)"
slug: "rev-0642-gdb-advanced-cheatsheet"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["watch", "rwatch", "awatch", "catch", "tbreak", "dprintf", "GDB 심화", "하드웨어 워치포인트"]
aliases: ["GDB watch 사용법", "GDB catch 사용법", "GDB tbreak", "GDB dprintf", "GDB 조건부 브레이크포인트"]
symptom_keywords: ["특정 변수가 언제 바뀌는지 모르겠음", "브레이크포인트를 한 번만 쓰고 싶음", "특정 syscall에서 멈추고 싶음", "출력만 찍고 멈추지 않는 브레이크포인트가 필요함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`break`만으로는 "이 주소에 도달하면 멈춰라"밖에 못 하지만, `watch`(값이 바뀌면 멈춤), `catch`(fork/exec/syscall 등 특정 이벤트에서 멈춤), `tbreak`(한 번만 멈추고 자동 삭제), `dprintf`(멈추지 않고 값만 찍음) 같은 GDB 명령을 조합하면 "언제 멈출지"를 훨씬 정교하게 지정할 수 있다.

## 언제 검색해야 하나
- 특정 전역 변수/메모리 값이 "언제, 어디서" 바뀌는지 코드를 눈으로 다 훑지 않고 찾고 싶을 때
- `fork`, `execve`, 특정 시스템 콜이 호출되는 순간에만 멈추고 싶을 때
- 반복문 안에서 브레이크포인트가 계속 걸려서 매번 `continue`를 치는 게 지겨울 때
- 멈추지 않고 그냥 로그만 찍으면서 프로그램을 계속 진행시키고 싶을 때

## 핵심 개념

### watch / rwatch / awatch — 하드웨어 워치포인트
```gdb
watch  EXPR   # EXPR에 쓰기(write)가 발생하면 멈춤
rwatch EXPR   # EXPR을 읽기(read)만 해도 멈춤
awatch EXPR   # 읽기 또는 쓰기 모두에 멈춤
```
CPU의 디버그 레지스터(x86의 `DR0`~`DR3`)를 이용한 **하드웨어 워치포인트**라서, 소프트웨어 방식(매 명령어마다 값을 비교)보다 훨씬 빠르다. `EXPR`은 변수 이름뿐 아니라 `*(int*)0x404060`처럼 메모리 주소 표현식도 가능하다. 단, x86 계열은 하드웨어 워치포인트 슬롯이 보통 4개뿐이라 동시에 너무 많이 걸 수는 없다.

### catch — 특정 이벤트에서 멈춤
```gdb
catch fork
catch vfork
catch exec
catch syscall            # 모든 syscall 진입/탈출 시 멈춤
catch syscall open       # open 시스템 콜만
catch signal SIGSEGV     # 특정 시그널 발생 시
catch throw               # C++ 예외 throw
```
`catch syscall`은 특정 시스템 콜 이름 또는 번호를 지정할 수 있어, 소스 없이도 "이 프로그램이 언제 파일을 여는지/네트워크 소켓을 만드는지" 같은 지점을 정확히 잡아낼 수 있다.

### tbreak — 임시(1회용) 브레이크포인트
```gdb
tbreak main
```
`break`와 동일하지만 **한 번 히트되면 자동으로 삭제**된다. 루프 안의 함수처럼 반복 호출되는 지점에서 딱 첫 진입만 보고 싶을 때, 매번 `delete` 안 해도 되어 편하다.

### until / advance — 반복문 넘기기
```gdb
until          # 현재 줄보다 큰 주소로 실행이 넘어갈 때까지 진행(루프 탈출용으로 자주 씀)
until *0x4012a0
advance main   # main에 도달할 때까지 실행(중간 브레이크포인트 없이)
```
`until`은 인자 없이 쓰면 "현재 실행 중인 루프를 한 바퀴 다 돌고 빠져나올 때까지" 자동으로 진행해주는 효과가 있어 `next`를 수십 번 누르는 것을 대체할 수 있다.

### dprintf — 멈추지 않는 브레이크포인트
```gdb
dprintf *0x401234, "count=%d\n", $eax
```
지정한 위치에 도달할 때마다 **멈추지 않고** `printf` 형식으로 값을 출력한 뒤 자동으로 계속 실행한다. 반복문 안에서 특정 값이 어떻게 변하는지 로그만 뽑고 싶을 때 `break` + `commands` + `continue` 조합보다 간결하다.

### condition / ignore — 브레이크포인트 조건화
```gdb
break *0x401234
condition 1 (eax == 0x1337)   # 브레이크포인트 1번에 조건 부여
ignore 1 5                     # 브레이크포인트 1번을 앞으로 5번은 무시하고 6번째부터 멈춤
```

### commands — 브레이크포인트에 자동 실행할 명령 묶기
```gdb
break *0x401234
commands
  print $rax
  continue
end
```
브레이크포인트에 걸릴 때마다 `print $rax` 하고 자동으로 `continue`하는 것을 자동화한다.

## 화면/코드에서 보이는 징후
이 명령들은 코드가 아니라 GDB 세션 안에서 직접 입력하는 것이다. 전역 변수가 예상치 못하게 바뀐다든지, 반복 호출되는 비교 함수를 브레이크포인트로 매번 멈추기 귀찮을 때 쓴다.

## 가장 먼저 할 것
값이 왜 바뀌는지 모르겠으면 우선 `watch`부터 걸어본다. 어떤 syscall/이벤트가 언제 발생하는지 궁금하면 `catch`부터 시도한다.

## 단계별 절차

**1) 특정 전역 변수가 바뀌는 지점 추적**
```gdb
break main
run
watch g_flag_check
continue
```
`g_flag_check`에 쓰기가 발생하는 순간 자동으로 멈추고, 그때의 콜스택(`bt`)을 보면 어느 함수가 그 값을 바꿨는지 바로 알 수 있다.

**2) 특정 syscall 호출 지점 찾기**
```gdb
catch syscall openat
run
```

**3) 루프 안 비교 함수에서 첫 진입만 보고 싶을 때**
```gdb
tbreak check_password
run
```

**4) 조건이 맞을 때만 멈추기**
```gdb
break strcmp
condition 1 ($rsi != 0 && strlen((char*)$rsi) > 5)
```

**5) 멈추지 않고 로그만 남기기**
```gdb
dprintf strcmp, "strcmp(\"%s\", \"%s\")\n", $rdi, $rsi
continue
```

## 명령어/단축키
```gdb
watch EXPR / rwatch EXPR / awatch EXPR
catch fork / catch exec / catch syscall [name] / catch signal SIG
tbreak LOCATION
until [LOCATION] / advance LOCATION
dprintf LOCATION,"fmt",args
condition N EXPR
ignore N COUNT
commands N ... end
info watchpoints
delete N
```

## 출력 해석
`watch` 히트 시 출력 예:
```
Hardware watchpoint 2: g_flag_check

Old value = 0
New value = 1
check_input (buf=0x7ffd...) at chall.c:42
42          return;
```
`Old value`/`New value`로 값이 어떻게 바뀌었는지, 그 아래 위치(`check_input` 함수, 42번째 줄)로 **누가** 바꿨는지 바로 확인된다.

## 흔한 실수
- 하드웨어 워치포인트 슬롯 부족(보통 4개)으로 `watch`를 너무 많이 걸어서 "No hardware watchpoints available" 에러를 만나는 것 — 필요한 것만 골라서 걸어야 한다.
- `watch` 대상이 스택/힙에 있는 지역 변수인데, 그 함수가 리턴해서 스코프를 벗어나면 GDB가 자동으로 그 워치포인트를 삭제한다는 사실을 모르고 "왜 갑자기 안 멈추지"라고 헷갈리는 것.
- `tbreak`를 반복문 안에서 걸고 "왜 두 번째 반복에서 안 멈추지"라고 당황하는 것 — 설계대로 1회만 동작하는 것이 정상이다.
- `catch syscall`이 정적 링킹 바이너리든 동적 링킹 바이너리든 항상 동작한다는 것을 모르고 `ltrace`가 안 통하는 상황에서도 `catch syscall`을 시도하지 않는 것.

## 막혔을 때 다음 체크
- fork/exec 관련 catch 활용 예시가 더 필요하면 → REV-0637 libc 함수 사전: fork exec 계열.
- Pwndbg가 제공하는 더 편한 heap/GOT 전용 명령이 궁금하면 → REV-0643 Pwndbg 명령어 심화 치트시트.
- 시스템 콜 이름/번호 목록이 필요하면 → REV-0645 시스템콜 번호 빠른 참조표(x86-64).

## 미니 예제
```gdb
(gdb) break main
(gdb) run
(gdb) watch is_authenticated
Hardware watchpoint 2: is_authenticated
(gdb) continue
Continuing.

Hardware watchpoint 2: is_authenticated

Old value = 0
New value = 1
verify_password (input=0x7ffd...) at chall.c:55
55          return 1;
(gdb) bt
#0  verify_password (input=0x7ffd...) at chall.c:55
#1  0x0000000000401278 in main () at chall.c:20
```
`is_authenticated`가 `verify_password` 함수의 55번째 줄에서 1로 바뀐 순간을 코드 전체를 읽지 않고도 정확히 찾아냈다.

## 관련 글
- REV-0637 — libc 함수 사전: fork exec 계열
- REV-0643 — Pwndbg 명령어 심화 치트시트(heap/got/plt)
- REV-0645 — 시스템콜 번호(syscall number) 빠른 참조표(x86-64)
- REV-0113 — Core dump와 크래시 지점 분석 기초

## 출처/검증
- `watch`/`rwatch`/`awatch`/`catch`/`tbreak`/`until`/`advance`/`dprintf`/`condition`/`ignore`/`commands` 명령 구문과 동작: GDB 공식 매뉴얼("Debugging with GDB") "Breakpoints, Watchpoints, and Catchpoints" 챕터 기준 (2026-09-08 검증).
- 하드웨어 워치포인트가 x86 디버그 레지스터(DR0-DR3)를 사용한다는 점: GDB 매뉴얼 "Setting Watchpoints" 섹션 및 x86 아키텍처 디버그 레지스터 문서 기준.
