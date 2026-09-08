---
id: REV-0111
title: "ltrace로 라이브러리 호출 빠르게 보기"
slug: "rev-0111-ltrace-basics"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [ltrace, GDB]
keywords: ["ltrace", "library call trace", "라이브러리 호출 추적", "동적 분석 도구"]
aliases: ["ltrace 사용법", "ltrace 명령어", "ltrace 출력 해석", "ltrace strace 차이"]
symptom_keywords: ["ltrace 설치 안됨", "ltrace 아무것도 안찍힘", "ltrace가 강제종료됨", "라이브러리 함수 호출을 빠르게 보고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ltrace ./chall`은 프로그램을 실행하면서 `strcmp`, `scanf`, `malloc` 같은 **라이브러리 함수 호출과 그 인자·반환값**을 실시간으로 화면에 출력해주는 도구로, 코드를 한 줄도 안 읽고 브레이크포인트도 안 걸고 어떤 함수가 어떤 인자로 몇 번 호출되는지 빠르게 훑을 때 가장 먼저 써볼 만한 명령이다.

## 언제 검색해야 하나
- GDB로 하나하나 브레이크포인트를 걸기 전에, 프로그램이 대략 어떤 라이브러리 함수들을 호출하는지 빠르게 훑어보고 싶을 때
- `strcmp`가 어떤 문자열들과 비교되는지, `scanf`가 몇 개의 입력을 받는지 등을 코드 분석 없이 바로 확인하고 싶을 때
- `ltrace`를 실행했더니 아무것도 안 찍히거나 바로 죽어서 원인이 궁금할 때

## 핵심 개념

### ltrace가 하는 일 — PLT 후킹
`ltrace`는 대상 프로그램이 호출하는 **동적 라이브러리 함수 호출**(PLT를 거치는 호출, REV-0100 참고)을 가로채서, 함수 이름, 전달된 인자, 반환값을 사람이 읽기 좋은 형태로 출력한다. 내부적으로는 `ptrace` 시스템 콜을 이용해 대상 프로세스를 제어하면서, PLT 엔트리 근처에 자체적으로 브레이크포인트류 후킹을 걸어 호출을 가로채는 방식으로 동작한다. GDB로 `strcmp`에 `break strcmp` 걸고 `run`, `x/s $rdi`, `x/s $rsi`, `continue`를 계속 반복하는 작업을, `ltrace`는 명령 한 줄로 자동화해준다고 이해하면 된다.

### ltrace vs strace — 레벨이 다르다
`ltrace`는 **라이브러리 함수 호출**(사용자 공간, libc/libm 등) 레벨을 보여주고, `strace`(REV-0112)는 **커널 시스템 콜**(`read`, `write`, `open`, `mmap` 등) 레벨을 보여준다. `printf("hello")` 한 줄은 `ltrace`에서는 `printf` 호출 하나로 보이지만, `strace`에서는 내부적으로 버퍼링을 거쳐 실제로 몇 번의 `write` 시스템 콜로 나가는지가 보인다. 두 도구는 상호 보완적이라 CTF에서 "일단 둘 다 한 번씩 돌려보고 시작하는" 것이 일반적인 습관이다.

### 설치
Debian/Ubuntu 계열:
```bash
sudo apt install ltrace
```

### 알려진 한계 — 특히 Full RELRO/PIE와의 상호작용
`ltrace`는 원래 lazy binding(REV-0100)이 진행되는 시점을 가로채는 방식으로 설계되어, 최신 glibc(특히 `.plt.sec` 도입, CET 관련 변경) 및 Full RELRO(REV-0102, 처음부터 GOT가 다 채워져 lazy binding 자체가 없음)가 결합된 환경에서는 일부 호출을 못 잡거나, 아예 실행이 실패하거나 매우 느려지는 경우가 보고되어 있다. `ltrace`가 오랫동안 활발히 유지보수되지 않았던 시기가 있어 최신 배포판에서 이런 호환성 문제가 특히 잘 나타난다. `ltrace`가 아무것도 안 찍히거나 이상하게 죽는다면, 이 도구 자체의 한계일 수 있으니 `strace`(REV-0112)나 GDB 수동 브레이크포인트로 넘어가는 것이 합리적이다.

### 정적 링킹 바이너리에는 거의 무용지물
`ltrace`는 PLT/GOT를 통한 동적 라이브러리 호출을 가로채는 도구이므로, 정적 링킹된 바이너리(REV-0101)에는 후킹할 PLT 자체가 없어 사실상 아무 정보도 못 준다. 이럴 때는 `strace`(시스템 콜은 정적/동적 무관하게 항상 커널을 거치므로 항상 관찰 가능)로 넘어가야 한다.

## 화면/코드에서 보이는 징후
이 도구는 코드에서 찾는 것이 아니라 터미널에서 직접 실행해서 관찰하는 도구다. 실행 결과 화면에 `함수이름(인자1, 인자2, ...) = 반환값` 형태의 줄이 계속 출력된다.

## 가장 먼저 할 것
바이너리를 받으면 아무 옵션 없이 그냥 한 번 돌려본다:
```bash
ltrace ./chall
```
출력이 잘 나오면 그대로 어떤 함수들이 호출되는지 훑고, 안 나오거나 죽으면 정적 링킹 여부(REV-0101)와 RELRO 상태(REV-0102)를 먼저 의심한다.

## 단계별 절차

**1) 기본 실행**
```bash
ltrace ./chall
```
프로그램이 입력을 요구하면 그대로 입력하면서 관찰한다.

**2) 특정 함수만 필터링**
```bash
ltrace -e 'strcmp+scanf+strncmp' ./chall
```
`-e` 뒤에 관심 있는 함수 이름을 `+`로 연결하면 그 함수 호출만 골라서 보여준다. 함수가 너무 많이 찍혀서 화면이 지저분할 때 유용하다.

**3) 문자열 인자 길이 늘려서 보기**
```bash
ltrace -s 200 ./chall
```
기본적으로 `ltrace`는 긴 문자열 인자를 일정 길이에서 잘라서 보여준다(`...`으로 표시). `-s <바이트수>`로 최대 출력 길이를 늘리면 긴 flag 문자열 등이 잘리지 않고 다 보인다.

**4) 파일로 저장해서 나중에 분석**
```bash
ltrace -o trace.log ./chall
```

**5) 호출 횟수/시간 요약**
```bash
ltrace -c ./chall
```
어떤 함수가 몇 번 호출됐고 시간을 얼마나 썼는지 요약 테이블을 프로그램 종료 후 보여준다. 반복 호출되는 함수(예: 루프 안에서 계속 불리는 비교 함수)를 찾을 때 유용하다.

**6) 자식 프로세스까지 추적(fork를 쓰는 프로그램)**
```bash
ltrace -f ./chall
```

## 명령어/단축키
```bash
ltrace ./chall
ltrace -e 'strcmp+scanf' ./chall
ltrace -s 200 ./chall
ltrace -o trace.log ./chall
ltrace -c ./chall
ltrace -f ./chall
```

## 출력 해석
실전 예시:
```
$ ltrace ./chall
__libc_start_main(0x4011f6, 1, 0x7ffd..., 0x401260 <unfinished ...>
printf("Enter password: ")                       = 18
__isoc99_scanf(0x402004, 0x7ffd...)               = 1
strcmp("test123", "s3cr3t_p4ss")                  = 1
puts("Wrong password.")                           = 17
+++ exited (status 0) +++
```
- 셋째 줄 `strcmp("test123", "s3cr3t_p4ss") = 1`에서 이미 입력값과 정답 후보 문자열이 **인자 그대로** 화면에 다 보인다 — 코드 한 줄 안 읽고 정답이 노출되는 대표적인 경우다.
- 반환값 `= 1`은 `strcmp`가 0이 아니므로(REV-0110 참고) "다름" 판정이라는 뜻이고, 실제로 다음 줄에서 `"Wrong password."`가 출력된 것과 일치한다.
- `__libc_start_main`과 `<unfinished ...>` 표시는 그 함수가 아직 리턴하지 않고 그 안에서 다른 함수(`main` 등)를 계속 호출 중이라는 뜻으로, 깊이가 있는 호출 구조를 나타낸다.

## 흔한 실수
- `ltrace`가 아무것도 안 찍히는데 무작정 재설치만 반복하는 것 — 정적 링킹 바이너리이거나 Full RELRO+최신 glibc 조합일 가능성부터 점검한다.
- `ltrace` 출력을 100% 신뢰하는 것 — 도구 자체의 오버헤드나 후킹 방식 때문에 타이밍에 민감한 안티디버깅 로직이 있는 프로그램은 `ltrace` 아래에서 평소와 다르게 동작할 수 있다(관찰 자체가 프로그램 동작에 영향을 주는 경우).
- 시스템 콜 정보가 필요한데 계속 `ltrace`만 붙잡고 있는 것 — 파일 열기, 소켓, `execve` 같은 것은 `strace`(REV-0112) 영역이다.
- `-s` 옵션 없이 긴 문자열이 `...`으로 잘려서 나온 걸 보고 "이게 전체 정답이다"라고 착각하는 것 — 반드시 `-s`로 길이를 늘려서 재확인한다.

## 막혔을 때 다음 체크
- 시스템 콜 레벨에서 더 깊이 보고 싶다면 → REV-0112 strace로 시스템 콜에서 힌트 찾기
- `strcmp`/`memcmp` 결과를 코드 관점에서 더 정확히 해석하고 싶다면 → REV-0110 strcmp strncmp memcmp 비교 추적
- PLT/GOT 구조 자체가 궁금하다면(ltrace가 무엇을 후킹하는지) → REV-0100 PLT와 GOT 기초

## 미니 예제
```bash
$ ltrace -s 64 ./chall < <(echo "test_input")
strlen("test_input")                                = 10
strcmp("test_input", "REAL_ANSWER_1234")             = 1
puts("Wrong flag!"
Wrong flag!
)                                                     = 12
+++ exited (status 0) +++
```
한 줄만 봐도 프로그램이 `strcmp`로 내 입력과 `"REAL_ANSWER_1234"`를 비교하고 있다는 게 바로 드러난다 — 이 문자열이 그대로 정답이거나, 정답을 만드는 데 필요한 핵심 상수다.

## 관련 글
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0109 — scanf fgets read 입력 추적
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- `ltrace` 옵션 및 동작(`-e`, `-s`, `-c`, `-f`, `-o`): `ltrace(1)` man page 기준.
- `ltrace`와 최신 glibc/Full RELRO 환경에서의 호환성 이슈: `ltrace` 프로젝트 공개 이슈 트래커 및 각 배포판 패키지 노트에서 보고된 알려진 한계 기준 (2026-09-08 검증).
