---
id: REV-0331
title: "같은 입력인데 실행마다 다른 결과가 나올 때"
slug: "rev-0331-nondeterministic-output-same-input"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [GDB, x64dbg, strace]
keywords: ["실행마다 결과 다름", "비결정적 동작", "ASLR 영향", "uninitialized 변수", "rand 시드"]
aliases: ["돌릴 때마다 값이 다름", "결과가 랜덤함", "재현이 안 됨"]
symptom_keywords: ["같은 입력을 줬는데 결과가 매번 다름", "재현이 안 됨", "출력에 랜덤한 값이 섞여 나옴", "디버거에서는 되는데 맨몸 실행은 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
동일한 입력을 줬는데 실행할 때마다 결과가 달라진다면, 그 프로그램은 **주소값, 시간, 초기화 안 된 메모리, 스레드 스케줄링 중 하나에 의존해 값이 바뀌는 로직**을 갖고 있다는 뜻이며, 어느 값이 매번 바뀌는지부터 특정해야 한다.

## 언제 검색해야 하나
- 같은 입력 문자열을 줬는데 "Correct"와 "Wrong"이 실행마다 번갈아 나올 때
- 출력에 찍히는 숫자(주소, 해시값, 난수)가 실행할 때마다 달라질 때
- 디버거로 돌리면 항상 성공하는데 디버거 없이 돌리면 실패(혹은 그 반대)할 때
- 멀티스레드/멀티프로세스 프로그램에서 결과 순서나 값이 뒤바뀔 때

## 핵심 개념
"입력은 같은데 결과가 다르다"는 것은 프로그램 내부에 **입력이 아닌 다른 무언가**가 로직에 관여하고 있다는 뜻이다. 대표적인 원인은 다음과 같다.

1. **ASLR(Address Space Layout Randomization)** — 실행할 때마다 스택/힙/공유 라이브러리의 로드 주소가 바뀐다. 정상적인 프로그램이라면 이 주소 차이가 결과에 영향을 주면 안 되지만, 포인터 값 자체를 해시에 섞거나 주소를 시드로 쓰는 버그성/의도적 코드가 있으면 결과가 실행마다 달라진다.
2. **스택 카나리(Stack Canary)** — 카나리 값은 `AT_RANDOM`을 기반으로 실행마다 새로 생성된다(REV-0676 참고). 카나리 자체를 출력하거나 비교에 사용하는 코드가 있다면 매번 다른 값이 보인다.
3. **시드로 시간/PID를 쓰는 `rand()`** — `srand(time(NULL))`이나 `srand(getpid())`처럼 실행 시점에 따라 달라지는 값을 시드로 쓰면 `rand()` 결과가 매번 달라진다.
4. **초기화되지 않은 변수(uninitialized variable)** — 스택/힙에 남아있는 이전 값(garbage)을 그대로 읽어서 쓰는 코드가 있으면, 이전에 그 메모리 영역에 뭐가 있었는지에 따라 결과가 달라진다. 디버거로 실행하면 메모리가 0으로 초기화되어 있어 재현되고, 맨몸 실행에서는 안 되는 경우가 흔하다(그 반대도 가능).
5. **멀티스레드 경쟁 상태(race condition)** — 여러 스레드가 공유 변수에 동시에 접근하는 순서가 매번 달라져서 결과가 바뀐다.
6. **환경 의존 값** — 환경 변수, 현재 시각, 파일 시스템 상태(디렉토리 내 파일 개수 등)를 로직에 사용하는 경우.

## 화면/코드에서 보이는 징후
- 같은 입력에 대해 성공/실패가 실행마다 바뀜
- 출력되는 숫자가 매번 다르되, 자릿수나 형태(주소 같은 0x로 시작, 혹은 큰 정수)가 일정한 패턴을 보임
- `strace`에서 `gettimeofday`, `clock_gettime`, `getrandom` 같은 시스템 콜이 로직 중간에 호출됨

## 가장 먼저 할 것
같은 입력으로 여러 번 실행하며 **무엇이 바뀌는지** 먼저 정확히 특정한다(출력되는 숫자, 성공/실패 여부, 소요 시간 등). 그다음 ASLR을 꺼서 주소 관련 문제인지부터 배제한다.

## 단계별 절차

**1) ASLR을 꺼서 주소 문제인지 확인**
```bash
setarch $(uname -m) -R ./chall
# 또는 시스템 전체
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space
```
ASLR을 끈 상태에서도 결과가 계속 바뀐다면 원인은 주소가 아니다(REV-0104 ASLR 참고).

**2) rand/time 계열 함수 호출 확인**
```bash
ltrace -e 'rand+srand+time+clock+getpid' ./chall
```
`srand`에 어떤 값이 들어가는지 보면 시드가 시간/PID에 의존하는지 바로 알 수 있다.

**3) 초기화 안 된 변수 의심 시 valgrind로 확인**
```bash
valgrind --track-origins=yes ./chall
```
"Use of uninitialised value" 경고가 뜨면 정확히 어느 변수, 어느 코드 라인이 문제인지 알려준다.

**4) 멀티스레드라면 스레드 개수/순서 확인**
```bash
strace -f ./chall 2>&1 | grep clone
```
`clone` 호출이 여러 번 보이면 멀티스레드이며, 공유 자원 접근 순서가 매번 달라질 수 있다.

**5) 디버거 유무로 결과가 갈리는 경우 메모리 초기화 차이 의심**
디버거는 보통 새로 매핑된 페이지를 0으로 채워주는 반면, 맨몸 실행은 이전 프로세스가 쓰던 메모리 잔여값이 남아있을 수 있다. `gdb`에서 `run` 전에 `set environment MALLOC_PERTURB_=` 등을 조정하거나, 반대로 `MALLOC_PERTURB_=1` 환경 변수로 힙을 일부러 오염시켜서 재현성을 테스트해본다.

## 명령어/단축키
```bash
setarch $(uname -m) -R ./chall
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space
ltrace -e 'rand+srand+time+clock' ./chall
strace -f ./chall
valgrind --track-origins=yes ./chall
```

## 출력 해석
- `srand(1725850000)`처럼 인자가 큰 정수(유닉스 타임스탬프로 보이는 값)라면 시간 기반 시드다.
- valgrind의 `Conditional jump or move depends on uninitialised value(s)` 메시지는 어떤 조건 분기가 초기화 안 된 값에 의존한다는 뜻 — 그 조건이 성공/실패를 가르는 로직이라면 이게 원인이다.
- `clone(child_stack=...) = <pid>`가 여러 번 보이면 스레드가 생성된 것이며, 그 이후 출력 순서가 실행마다 바뀌는 건 스케줄링 때문일 수 있다.

## 흔한 실수
- ASLR을 끄지 않고 "왜 주소가 매번 다르지"라고만 생각하며 정작 로직에서 그 주소를 실제로 쓰는지는 확인하지 않는 것.
- `rand()`가 쓰인 걸 보고 바로 "이 문제는 못 푼다"고 포기하는 것 — 시드가 고정값이거나 예측 가능한 값(문제 시작 시각 등)이면 재현 가능한 경우가 많다.
- 디버거에서 결과가 재현되니 "디버거 결과가 진짜"라고 믿는 것 — 오히려 디버거가 메모리를 0으로 초기화해줘서 우연히 일관된 결과가 나오는 것일 수도 있다.
- valgrind 없이 초기화 안 된 변수 문제를 코드만 보고 찾으려다 시간을 낭비하는 것.

## 막혔을 때 다음 체크
- ASLR 자체 개념이 헷갈리면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유.
- 카나리 값이 매번 다른 것과 관련 있어 보이면 → REV-0676 AT_RANDOM과 스택 카나리 초기화 관계.
- GDB에서 레지스터/메모리 값이 실행마다 달라 보여서 혼란스럽다면 → REV-0718 GDB info registers 값이 화면마다 다르게 보여서 헷갈릴 때.
- 그래도 원인을 못 찾으면 → REV-0113 Core dump와 크래시 지점 분석 기초로 크래시성 비결정성인지 확인.

## 미니 예제
```bash
$ ./chall 1234
result: 0x7f3a2c001020 -> Wrong

$ ./chall 1234
result: 0x7f8e91a03020 -> Wrong

$ setarch $(uname -m) -R ./chall 1234
result: 0x7ffff7fc1020 -> Wrong
result: 0x7ffff7fc1020 -> Wrong   (여러 번 실행해도 항상 동일)
```
ASLR을 끄자 출력 주소가 고정됐다. 이는 프로그램이 힙/라이브러리 주소값 자체를 결과 계산에 사용하고 있다는 뜻이므로, 그 주소가 어디서 로직에 섞이는지(예: 포인터를 정수로 캐스팅해 XOR하는 코드) 디스어셈블리에서 추적해야 한다.

## 관련 글
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0676 — AT_RANDOM과 스택 카나리 초기화 관계
- REV-0718 — GDB info registers 값이 화면마다 다르게 보여서 헷갈릴 때
- REV-0113 — Core dump와 크래시 지점 분석 기초

## 출처/검증
- ASLR 랜덤화 범위와 `/proc/sys/kernel/randomize_va_space` 제어: Linux 커널 문서(`Documentation/admin-guide/sysctl/kernel.rst`) 기준 (2026-09-09 검증).
- `valgrind --track-origins=yes`의 초기화되지 않은 값 추적 기능: Valgrind 공식 매뉴얼 "Memcheck: a memory error detector" 기준.
