---
id: REV-0661
title: "리눅스 프로세스 종료 코드(Exit Code)로 크래시 원인 좁히기"
slug: "rev-0661-linux-exit-code-crash-narrowing"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["exit code", "종료 코드", "128+signal", "WIFEXITED", "WEXITSTATUS", "WTERMSIG", "echo $?"]
aliases: ["리눅스 종료 코드 확인", "시그널로 죽은 프로세스 exit code", "bash exit status 139", "segfault exit code 확인"]
symptom_keywords: ["exit code 139", "exit code 134", "exit code 132", "Segmentation fault core dumped", "echo $? 로 원인 찾고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
쉘에서 프로그램 실행 직후 `echo $?`로 보이는 종료 코드가 128보다 크면(예: 139, 134, 132) `128 + 시그널 번호`이며, 그 시그널 번호(139→11=SIGSEGV, 134→6=SIGABRT, 132→4=SIGILL, 136→8=SIGFPE)만 알아도 코드를 한 줄도 안 읽고 "널 포인터 역참조인지, abort()가 호출됐는지, 잘못된 명령어를 실행했는지, 0으로 나눴는지"를 즉시 좁힐 수 있다.

## 언제 검색해야 하나
- 퍼징이나 무작위 입력 테스트 중 특정 입력에서만 프로그램이 비정상 종료됐는데, 왜 죽었는지 로그 없이 빠르게 1차 분류하고 싶을 때
- `./chall; echo $?`로 확인한 숫자(예: 139)가 무슨 뜻인지 모를 때
- 스크립트로 자동화된 크래시 탐지(exit code만으로 "크래시 후보"를 걸러내는 방식)를 만들고 싶을 때

## 핵심 개념

### 정상 종료와 시그널 종료의 exit code 차이
프로세스가 `exit(n)`이나 `return n`(main에서)으로 **정상 종료**하면, 쉘에서 보는 종료 코드는 `n & 0xFF`(0~255 범위)다.

프로세스가 처리되지 않은 **시그널로 강제 종료**되면, bash 등 대부분의 쉘은 `128 + 시그널번호`를 종료 코드로 보고한다. 이건 커널이 직접 정하는 규칙이 아니라 쉘의 관례지만, bash/zsh/dash 모두 이 관례를 따르므로 사실상 표준처럼 쓰인다.

### 자주 보는 값과 의미
| exit code | 128+N | 시그널 | 의미 |
|---|---|---|---|
| 132 | 128+4 | SIGILL | 잘못된 명령어 실행(illegal instruction) — 손상된 코드, 잘못된 함수 포인터 호출 등 |
| 133 | 128+5 | SIGTRAP | 트랩/브레이크포인트성 시그널, `int3` 등 |
| 134 | 128+6 | SIGABRT | `abort()` 호출 — 스택 카나리 감지(`__stack_chk_fail`), `assert()` 실패, glibc의 malloc/free 무결성 검사 실패(double free, heap corruption 등) |
| 135 | 128+7 | SIGBUS | 버스 에러 — 정렬 안 된 메모리 접근, 매핑되지 않은 파일 영역 접근 등 |
| 136 | 128+8 | SIGFPE | 부동소수점 예외 — 대표적으로 **정수 나눗셈에서 0으로 나누기**(`idiv`) |
| 137 | 128+9 | SIGKILL | 강제 종료(`kill -9`), OOM killer에 의해 죽은 경우도 포함 |
| 139 | 128+11 | SIGSEGV | 세그멘테이션 폴트 — 매핑 안 된 주소 접근, 널 포인터 역참조, 스택 오버플로우로 인한 잘못된 접근 등 리버싱에서 가장 자주 보는 크래시 |

### 왜 이게 "가장 먼저 할 것"이 되는가
GDB로 core dump나 실시간 크래시를 분석하기 전에, exit code 하나만 확인해도 **어느 카테고리의 버그인지**(메모리 접근 오류 vs 무결성 검사 실패 vs 산술 오류)를 미리 좁힐 수 있다. 특히 자동화된 fuzzing/brute-force 스크립트에서는 매번 GDB를 붙이는 대신 `subprocess`로 실행하고 반환 코드만 확인해서 "이 입력이 크래시를 유발했는지"를 빠르게 스크리닝하는 데 이 값이 직접 쓰인다.

### C에서 wait 계열 함수와의 관계
부모 프로세스가 `wait()`/`waitpid()`로 자식의 종료 상태를 받을 때는 매크로로 해석해야 한다:
```c
int status;
waitpid(pid, &status, 0);
if (WIFEXITED(status)) {
    printf("정상 종료, code = %d\n", WEXITSTATUS(status));
} else if (WIFSIGNALED(status)) {
    printf("시그널로 종료, signal = %d\n", WTERMSIG(status));
}
```
쉘이 보여주는 `128+N` 규칙은 이 `WTERMSIG(status)` 값을 쉘이 사람이 보기 좋게 인코딩한 것이다. pwntools의 `process` 객체를 쓸 때도 `p.wait()` 후 `p.poll()`이 음수를 반환하면 그 절댓값이 시그널 번호를 의미한다(REV-0266 참고).

## 화면/코드에서 보이는 징후
터미널에서 프로그램 실행 후 쉘이 직접 출력하는 메시지에서 확인된다:
```
Segmentation fault (core dumped)
```
이 메시지가 뜬 직후 `echo $?`를 치면 `139`이 나온다. `Aborted (core dumped)`가 뜨면 `echo $?`는 `134`다. 메시지 없이 그냥 프로세스가 사라지고 `$?`만 이상한 값일 때도 이 표를 참고해서 원인을 좁힌다.

## 가장 먼저 할 것
프로그램을 실행한 직후 바로 종료 코드를 확인하는 습관을 들인다:
```bash
./chall
echo $?
```
128보다 크면 위 표에서 시그널을 확인하고, core dump 설정(REV-0113)이 되어 있다면 바로 core 파일을 GDB로 열어 정확한 크래시 지점을 확인한다.

## 단계별 절차

**1) 실행 후 즉시 종료 코드 확인**
```bash
./chall < input.txt
echo "exit code: $?"
```

**2) 128 초과 여부로 1차 분류**
- 128 이하: 정상 종료 경로. 프로그램 로직상 의도된 실패(예: "Wrong password" 후 `return 1`)일 가능성이 높다.
- 128 초과: 시그널에 의한 비정상 종료. 위 표에서 시그널 번호(`code - 128`)를 확인한다.

**3) 시그널별로 다음 액션 결정**
- SIGSEGV(139) → GDB로 core dump 열거나 재실행 후 크래시 지점의 faulting 주소 확인(REV-0113)
- SIGABRT(134) → 스택 카나리 검사 실패인지, glibc 힙 무결성 검사(`malloc(): invalid pointer` 등) 실패인지 stderr 메시지 확인
- SIGFPE(136) → 코드에서 나눗셈(`idiv`) 근처를 확인, 0으로 나누는 입력을 의심(REV-0053)
- SIGILL(132) → 함수 포인터가 잘못된 주소를 가리키거나, 손상된 코드 영역을 실행했을 가능성

**4) 커널 로그로 교차 확인 (SIGSEGV/SIGBUS)**
```bash
dmesg | tail -20
```
`chall[12345]: segfault at 0 ip 0000000000401146 sp 00007ffd... error 4`처럼 폴트 주소(`at 0`)와 명령어 포인터(`ip`)가 나온다. `at 0`은 널 포인터 역참조를 강하게 시사한다.

**5) 자동화 스크립트에서 exit code로 크래시 후보 스크리닝**
```python
import subprocess
for candidate in test_inputs:
    p = subprocess.run(["./chall"], input=candidate, capture_output=True)
    if p.returncode < 0:  # 음수 = -시그널번호 (Python subprocess 관례)
        print(f"크래시 후보: {candidate!r}, signal={-p.returncode}")
```

## 명령어/단축키
```bash
./chall; echo $?
echo $?                        # 직전 명령 종료 코드
dmesg | tail -20               # 커널이 기록한 segfault 정보
ulimit -c unlimited            # core dump 활성화 (REV-0113과 연계)
```
```c
WIFEXITED(status)
WEXITSTATUS(status)
WIFSIGNALED(status)
WTERMSIG(status)
```

## 출력 해석
```bash
$ ./chall
Segmentation fault (core dumped)
$ echo $?
139
```
`139 - 128 = 11` → SIGSEGV. `(core dumped)`가 붙어 있으므로 `ulimit -c unlimited`가 설정돼 있었다면 `core` 파일이 생성됐을 것이다(REV-0113에서 core dump를 GDB로 여는 절차 참고).

```bash
$ ./chall
Aborted (core dumped)
$ echo $?
134
```
`134 - 128 = 6` → SIGABRT. glibc 힙 오류 메시지(`free(): invalid pointer` 등)나 스택 카나리 실패 메시지(`*** stack smashing detected ***`)가 stderr에 함께 출력됐는지 다시 확인해야 정확한 원인을 알 수 있다 — SIGABRT는 원인이 여러 갈래이므로 exit code만으로는 "abort가 호출됐다"까지만 알 수 있다.

## 흔한 실수
- exit code `1`이나 `0`처럼 128 이하인 값을 시그널로 착각하는 것 — 128 이하는 프로그램이 명시적으로 `exit(n)`/`return n`한 정상 종료 경로다.
- SIGABRT(134)를 보고 무조건 스택 카나리 문제라고 단정하는 것 — malloc/free 무결성 검사 실패, `assert()` 실패 등 원인이 다양하므로 stderr 메시지를 반드시 같이 봐야 한다.
- 파이프라인(`prog1 | prog2`)에서 `echo $?`가 마지막 명령(`prog2`)의 종료 코드만 보여준다는 걸 잊고 `prog1`이 크래시 났는데 못 알아채는 것 — bash에서는 `${PIPESTATUS[@]}` 배열로 파이프라인 전체의 종료 코드를 확인해야 한다.
- Python `subprocess.run().returncode`가 시그널로 죽었을 때 **음수**로 나온다는 걸 모르고 `if returncode != 0`으로만 정상/비정상만 판별하고 시그널 종류를 놓치는 것.

## 막혔을 때 다음 체크
- SIGSEGV/SIGABRT의 정확한 크래시 지점(명령어 주소, 레지스터 상태)을 보고 싶다면 → REV-0113 Core dump와 크래시 지점 분석 기초
- 시스템 콜 수준에서 시그널이 어떻게 전달되는지 더 자세히 보고 싶다면 → REV-0662 strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기(strace는 `--- SIGSEGV {...} ---` 형태로 시그널도 함께 보여준다)
- pwntools로 이 판별을 자동화하고 싶다면 → REV-0266 pwntools process 기초

## 미니 예제
```bash
$ printf 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' | ./vuln
Segmentation fault (core dumped)
$ echo $?
139
$ dmesg | tail -1
[12345.678] vuln[9821]: segfault at 4141414141414141 ip 0000000000401234 sp 00007ffd12340000 error 4 in vuln[401000+1000]
```
`segfault at 4141414141414141`은 `A`(0x41) 바이트로 덮인 주소로 리턴하려다 실패했다는 뜻 — 스택 버퍼 오버플로우로 리턴 주소를 덮어썼다는 강력한 신호이며, exit code 139만 보고도 "메모리 손상 계열"이라는 큰 방향을 코드 분석 전에 잡을 수 있다.

## 관련 글
- REV-0113 — Core dump와 크래시 지점 분석 기초
- REV-0662 — strace 결과를 파일/네트워크 시스템콜로 필터링해서 노이즈 줄이기
- REV-0053 — IDIV: Signed 나눗셈
- REV-0442 — 스택 카나리(Stack Canary) 체크 시퀀스 분석

## 출처/검증
- 쉘의 `128+시그널번호` exit code 관례: bash 매뉴얼 "EXIT STATUS" 절 및 POSIX 쉘 관례 기준.
- 시그널 번호(SIGILL=4, SIGTRAP=5, SIGABRT=6, SIGBUS=7, SIGFPE=8, SIGKILL=9, SIGSEGV=11)와 `WIFEXITED`/`WEXITSTATUS`/`WIFSIGNALED`/`WTERMSIG` 매크로: `signal(7)` 및 `wait(2)` man page 기준.
- Python `subprocess.run().returncode`가 시그널 종료 시 음수(`-시그널번호`)로 반환되는 동작: Python 공식 문서 `subprocess` 모듈 기준 (2026-09-08 검증).
