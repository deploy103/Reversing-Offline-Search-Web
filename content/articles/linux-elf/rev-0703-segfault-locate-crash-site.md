---
id: REV-0703
title: "Segmentation fault가 나는데 원인 위치를 못 찾을 때"
slug: "rev-0703-segfault-locate-crash-site"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, dmesg]
keywords: ["Segmentation fault", "SIGSEGV", "세그폴트 원인 찾기", "catch signal", "크래시 위치 특정"]
aliases: ["세그폴트 어디서 나는지 모르겠음", "Segmentation fault 위치 찾기", "SIGSEGV 원인 분석", "gdb로 세그폴트 잡기"]
symptom_keywords: ["Segmentation fault (core dumped)만 뜨고 어디서 났는지 모름", "gdb 없이 실행하면 세그폴트만 나고 정보가 없음", "세그폴트가 나는데 어느 함수인지 특정이 안 됨", "strip된 바이너리라 크래시 위치 이름이 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
그냥 `./chall`을 실행해서 나오는 `Segmentation fault (core dumped)`라는 한 줄만으로는 어디서 죽었는지 알 수 없으므로, GDB로 직접 실행해 `catch signal SIGSEGV` 또는 `run`으로 크래시 순간을 붙잡고 `bt`(백트레이스)와 `x/i $pc`로 죽은 정확한 명령어와 호출 스택을 확인하는 절차가 필요하다.

## 언제 검색해야 하나
- 터미널에 `Segmentation fault (core dumped)`만 뜨고 어떤 함수, 어떤 줄에서 죽었는지 전혀 모를 때
- GDB로 실행했을 때도 그냥 멈추기만 하고 어디를 봐야 할지 막막할 때
- strip된 바이너리라서 크래시 지점의 함수 이름이 안 보이고 주소만 나올 때
- REV-0704에서 core dump 생성 자체는 됐는데, 그 안에서 실제로 원인 위치를 어떻게 읽어야 할지 모를 때

## 핵심 개념

### 왜 기본 실행만으로는 정보가 없나
셸이 보여주는 `Segmentation fault (core dumped)`는 커널이 프로세스에 `SIGSEGV`를 보냈고 기본 동작(core dump 생성 후 종료)이 일어났다는 뜻일 뿐, 셸 자체는 어떤 주소·어떤 함수에서 문제가 생겼는지 알려주지 않는다. 이 정보를 얻으려면 디버거로 그 순간을 직접 붙잡아야 한다.

### GDB로 크래시 순간을 붙잡는 두 가지 방법
1. **그냥 `run`**: GDB 안에서 `run`으로 실행하면, 프로그램이 `SIGSEGV`를 받는 순간 GDB가 자동으로 그 지점에서 실행을 멈추고 프롬프트를 돌려준다. 별도 설정 없이 기본 동작이다.
2. **`catch signal SIGSEGV`**: 여러 종류의 시그널을 처리하는 핸들러가 등록된 프로그램이거나, 정확히 어느 시점에 시그널이 전달되는지 명시적으로 잡고 싶을 때 사용한다.

멈춘 직후 확인할 것은 세 가지다 — 어떤 명령어에서 죽었는지(`$pc`/`$rip`), 그 명령어가 어떤 메모리를 건드리려 했는지(레지스터 값), 그리고 그 지점까지 어떤 함수들을 거쳐왔는지(콜스택)다.

### 백트레이스(bt)로 콜스택 확인
`bt`(backtrace)는 크래시 지점부터 `main`까지 호출된 함수들을 순서대로 보여준다. 심볼이 남아있는 바이너리라면 함수 이름과 인자까지 보이고, strip된 바이너리라면 주소만 나오는데 이 경우에도 "몇 단계를 거쳐 왔는지"와 "어느 주소 범위인지"는 여전히 유용한 단서다.

### 잘못된 메모리 접근의 흔한 패턴
`x/i $pc`로 죽은 명령어를 보면 대개 `mov`, `movzx` 계열처럼 메모리를 읽거나 쓰는 명령어다. 그 명령어의 피연산자 레지스터(`info registers`로 값 확인) 값이 `0x0`에 가깝거나(널 포인터 역참조), 말이 안 되게 크거나 이상한 패턴(`0x4141414141414141` 등 버퍼 오버플로우로 덮인 값)이면 그것이 바로 원인 단서다.

## 화면/코드에서 보이는 징후
```
$ ./chall
Segmentation fault (core dumped)
```
아무 정보 없이 이 한 줄만 뜨는 것이 전형적인 증상이다.

## 가장 먼저 할 것
`gdb ./chall`로 실행한 뒤 `run`(필요하면 인자 포함 `run <args>`)으로 그대로 재현한다. GDB가 자동으로 멈추면 바로 `bt`와 `info registers`, `x/i $pc`부터 확인한다.

## 단계별 절차
1. `gdb ./chall` 실행 후 `run`(입력이 필요하면 `run < input.txt`)
2. 크래시로 멈추면 우선 `bt`로 콜스택 확인
3. `info registers`로 각 레지스터 값 확인, 특히 `$rip` 근처와 접근하려던 주소로 추정되는 레지스터
4. `x/i $pc`로 죽은 명령어 자체를 디스어셈블해서 확인
5. `x/i $pc`에서 참조하는 레지스터가 널(0)이면 널 포인터 역참조, `0x4141...` 같은 패턴이면 버퍼 오버플로우로 덮인 값 의심
6. strip되어 함수 이름이 안 보이면 `bt`에 나온 주소를 `objdump -d ./chall`에서 검색해 함수 경계 확인, 또는 REV-0668의 시그니처 매칭 기법 적용
7. 원인이 애매하면 `main` 등에 `break`를 걸고 `next`/`step`으로 한 줄씩 따라가며 어느 시점부터 값이 이상해지는지 좁힌다(REV-0642의 `watch` 활용)

## 명령어/단축키
```gdb
gdb ./chall
run
run < input.txt
bt
bt full
info registers
x/i $pc
x/20xg $rsp
watch VAR
```

## 출력 해석
```
Program received signal SIGSEGV, Segmentation fault.
0x0000000000401235 in copy_data (dst=0x0, src=0x7ffd1234) at chall.c:30
30          *dst = *src;
```
`0x0000000000401235`는 죽은 명령어 주소, `copy_data`는 그 명령어가 속한 함수(심볼이 있을 때), `dst=0x0`은 널 포인터가 인자로 들어왔다는 뜻이다. 이 한 줄만으로도 "널 포인터 역참조가 `copy_data` 함수 30번째 줄에서 발생했다"는 원인을 바로 특정할 수 있다.

## 흔한 실수
- GDB 없이 셸에서 `Segmentation fault`만 보고 원인을 추측으로 때려 맞추려는 것 — 반드시 GDB로 재현해서 확인해야 한다.
- `bt` 결과에서 가장 위(크래시 지점)가 아니라 `main`부터 거꾸로 읽으며 헷갈리는 것 — `bt`는 위에서부터 크래시에 가장 가까운 프레임 순이다.
- 입력값에 따라 크래시 여부가 달라지는데 GDB 안에서 재현 조건(파일 리다이렉션, 인자)을 빠뜨려서 크래시 자체가 재현이 안 되는 것.
- core dump 설정 문제(REV-0704)와 이 문제(GDB로 직접 원인 위치 찾기)를 혼동해서, core dump가 아예 안 생기는 상황에서 core 파일부터 찾으려 하는 것.

## 막혔을 때 다음 체크
- core dump 자체가 생성되지 않아서 사후 분석용 파일이 없다면 → REV-0704 Core dump가 생성되지 않을 때 설정 확인하기.
- 종료 코드만으로 대략적인 원인(시그널 종류)을 먼저 좁히고 싶다면 → REV-0661 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기.
- SIGSEGV 자체의 의미와 다른 시그널과의 차이가 궁금하면 → REV-0671 Linux 시그널(SIGSEGV 등)과 리버싱에서의 의미.
- GDB에서 특정 변수가 바뀌는 시점을 추적하고 싶다면 → REV-0642 GDB 명령어 심화 치트시트(watch/catch/tbreak).

## 미니 예제
```gdb
(gdb) run
Starting program: /home/user/chall

Program received signal SIGSEGV, Segmentation fault.
0x0000000000401235 in copy_data (dst=0x0, src=0x7ffd1234) at chall.c:30
30          *dst = *src;
(gdb) bt
#0  copy_data (dst=0x0, src=0x7ffd1234) at chall.c:30
#1  0x0000000000401290 in main () at chall.c:12
(gdb) info registers rdi rsi
rdi            0x0                 0
rsi            0x7ffd1234          2147627572
```
`bt` 한 번으로 `main`이 `copy_data`를 호출했고 그 안에서 죽었다는 흐름이 드러나고, `rdi`(첫 번째 인자, `dst`)가 `0`이라는 것으로 널 포인터 전달이 원인임을 확정할 수 있다.

## 관련 글
- REV-0704 — Core dump가 생성되지 않을 때 설정 확인하기
- REV-0661 — 리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기
- REV-0671 — Linux 시그널(SIGSEGV 등)과 리버싱에서의 의미
- REV-0642 — GDB 명령어 심화 치트시트(watch/catch/tbreak)
- REV-0113 — Core dump와 크래시 지점 분석 기초

## 출처/검증
- GDB가 `SIGSEGV` 수신 시 자동으로 실행을 멈추는 기본 동작과 `catch signal`, `bt`, `info registers`, `x/i` 명령: GDB 공식 매뉴얼("Debugging with GDB") "Signals"/"Backtrace"/"Registers" 챕터 기준 (2026-09-09 검증).
- 널 포인터 역참조 및 버퍼 오버플로우로 인한 SIGSEGV 발생 패턴: 일반적인 x86-64 메모리 손상 취약점 분석 관행 기준.
