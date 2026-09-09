---
id: REV-0720
title: "GDB에서 특정 라이브러리 함수 스텝 진입이 계속 반복될 때"
slug: "rev-0720-gdb-step-repeats-in-library-function"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["GDB step 반복", "step-mode", "skip command", "step vs next", "라이브러리 함수 디버그 정보 없음"]
aliases: ["gdb step 무한루프", "gdb s 계속 눌러도 안빠져나옴", "gdb 라이브러리 함수 안에 갇힘", "gdb skip 라이브러리"]
symptom_keywords: ["step 눌러도 계속 같은 함수 안에 머무름", "gdb s 명령이 라이브러리 내부만 계속 돎", "printf 안에서 안빠져나옴", "gdb step-mode 라이브러리 반복"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`step`(소스 라인 단위 스텝 인)을 디버그 정보가 없는 라이브러리 함수(`printf`, `strlen` 등) 안에서 계속 누르면 GDB가 매번 명령어 단위로 한 줄씩만 진행하며 그 함수 내부를 벗어나지 못하는 것처럼 보이는데, 이는 `set step-mode on`이 켜져 있거나 애초에 `step` 대신 함수를 통째로 건너뛰는 `next`를 썼어야 하는 상황이며, `finish`로 강제로 빠져나오거나 `skip` 명령으로 그 함수를 아예 스텝 대상에서 제외하면 즉시 해결된다.

## 언제 검색해야 하나
- `main`을 스텝으로 따라가다가 `printf`, `strlen`, `memcpy` 같은 라이브러리 함수 호출문에서 `step`(GDB `s` 또는 Pwndbg에서도 동일)을 눌렀는데, 소스 라인이 안 넘어가고 알 수 없는 어셈블리 명령어들 사이를 계속 오갈 때
- `step`을 수십 번 눌러도 라이브러리 함수 밖으로 못 나오고 체감상 "무한 반복"처럼 느껴질 때
- `next`와 `step`의 차이를 몰라서 라이브러리 내부까지 다 스텝으로 밟으려다 막힐 때

## 핵심 개념

### step과 next의 근본적인 차이
GDB의 `step`(`s`)은 **소스 라인 단위로 한 줄 실행**하되, 그 줄이 함수 호출을 포함하면 그 함수 **내부로 들어간다**(Step Into, REV-0170 참고). `next`(`n`)는 마찬가지로 한 줄 실행하지만 함수 호출을 만나면 **그 함수를 통째로 실행해버리고 리턴 후 다음 줄로 넘어간다**(Step Over). 디스어셈블리 단위로 이 둘에 대응하는 것이 `stepi`(`si`)/`nexti`(`ni`)다(REV-0187).

### 라이브러리 함수 안에서 step이 "반복"처럼 보이는 진짜 이유 — step-mode
GDB에는 `step-mode`라는 옵션이 있다:
```
(gdb) help set step-mode
Set mode of the step operation.
When set, doing a step over a function without debug line information
will stop at the first instruction of that function. Otherwise, the
function is skipped and the step command stops at a different source line.
```
기본값은 off다. off일 때는 `step`이 디버그 라인 정보가 없는 함수(strip되지 않은 바이너리라도 libc는 보통 별도 디버그 심볼이 없어 "라인 정보 없음" 상태다)를 만나면 **그 함수를 통째로 실행하고 건너뛴다** — 즉 원래는 `next`처럼 동작해줘야 정상이다. 그런데 `step-mode`가 **on**으로 설정되어 있으면, GDB는 라인 정보가 없는 함수라도 억지로 명령어 단위로 계속 멈춰 세우기 때문에, `printf` 내부의 `vfprintf`, `_IO_*` 계열 헬퍼 함수들을 명령어 단위로 하나하나 다 밟게 되어 사용자 입장에서는 "몇 번을 눌러도 라이브러리 안에서 못 빠져나온다"는 체감을 준다. Pwndbg나 일부 `.gdbinit` 스크립트, GEF 등이 편의를 위해 이 옵션을 on으로 바꿔두는 경우가 있어, 자신이 설정한 적 없는데도 이 증상을 겪을 수 있다.

### step-mode가 off여도 반복처럼 느껴지는 경우
`step-mode`가 off라도, 애초에 함수 호출이 아니라 **루프문** 안에서 `step`을 계속 누르고 있으면 같은 소스 라인/같은 함수를 계속 왔다갔다 하는 것이 정상 동작이다. 예를 들어 `strlen`처럼 SIMD 루프로 구현된 libc 함수를 명령어 단위(`stepi`)로 밟으면 같은 루프 본문 명령어들을 문자열 길이만큼 반복해서 통과하게 되므로, 이것도 "안 끝나는" 것처럼 보일 수 있다 — 실제로는 정상적으로 진행 중이지만 반복 횟수가 많아 체감상 멈춘 것 같은 경우다.

## 화면/코드에서 보이는 징후
```
(gdb) step
0x00000000004a3d21 in __vfprintf_internal ()
(gdb) step
0x00000000004a3d2f in __vfprintf_internal ()
(gdb) step
0x00000000004a3d3a in __vfprintf_internal ()
```
소스 파일/라인 번호(`chall.c:12` 같은 표시) 없이 `함수이름+오프셋` 형태의 주소만 계속 나오면서, 아무리 `step`을 눌러도 원래 보고 있던 `main` 코드로 안 돌아오는 것이 전형적인 증상이다.

## 가장 먼저 할 것
지금 당장 그 함수 안에서 빠져나오고 싶다면 `finish`를 쓴다:
```
(gdb) finish
Run till exit from #0  __vfprintf_internal ()
main () at chall.c:12
12          if (check(buf) == 0) {
```
`finish`는 "현재 함수가 리턴할 때까지 실행"하는 명령이라, 라이브러리 함수 내부 몇 단계 안에 들어가 있어도 즉시 호출한 지점(정확히는 그 함수를 호출한 프레임)까지 빠져나올 수 있다.

## 단계별 절차

**1) step-mode 상태 확인**
```
(gdb) show step-mode
```
`Mode of the step operation is on.`이라고 나오면 원인이 이것이다.

**2) step-mode를 꺼서 근본적으로 해결**
```
(gdb) set step-mode off
```
이후 `step`은 라인 정보 없는 라이브러리 함수를 다시 자동으로 건너뛴다.

**3) 지금 갇힌 상태에서 즉시 빠져나오기**
```
(gdb) finish
```
여러 단계 중첩되어 있다면(`printf` → `vfprintf` → `_IO_vfprintf` 등) `finish`를 필요한 만큼 반복해서 상위 프레임까지 올라온다. `bt`(backtrace)로 지금 몇 단계나 들어와 있는지 먼저 확인하면 몇 번 `finish`해야 할지 가늠할 수 있다.

**4) 애초에 다음부터는 그 함수를 스텝 대상에서 제외 — skip 명령**
```
(gdb) skip function printf
(gdb) skip -rfunction ^__.*
```
`skip`은 지정한 함수(또는 정규식에 매칭하는 함수들)를 이후 `step`이 아예 통과하지 않도록 등록한다. libc 내부 헬퍼 함수들이 보통 `_`나 `__`로 시작하는 점을 이용해, 두 번째 예시처럼 정규식으로 libc 내부 함수 전체를 한 번에 스킵 대상으로 등록하는 것도 실전에서 자주 쓰는 방법이다. 등록된 목록은 `info skip`으로 확인하고, `skip delete <번호>`로 해제할 수 있다.

**5) 원래 의도가 "라인 단위로 내 코드만 보고 싶다"는 것이었다면 next를 사용**
애초에 라이브러리 함수 내부까지 들여다볼 필요가 없다면, 그 호출 줄에서는 `step` 대신 `next`를 쓰는 것이 근본적인 해법이다. `next`는 함수 호출을 만나면 무조건 통째로 실행하고 다음 줄로 넘어가므로 라이브러리 내부에 들어갈 일 자체가 없다.

## 명령어/단축키
```
(gdb) show step-mode
(gdb) set step-mode off
(gdb) finish
(gdb) bt
(gdb) skip function printf
(gdb) skip -rfunction ^__.*
(gdb) info skip
(gdb) skip delete 1
(gdb) next
```

## 출력 해석
```
(gdb) bt
#0  0x00000000004a3d3a in __vfprintf_internal ()
#1  0x000000000049f012 in printf ()
#2  0x0000000000401163 in main () at chall.c:10
```
`bt`(backtrace)로 지금 몇 단계나 라이브러리 내부에 들어와 있는지 정확히 확인할 수 있다. 이 예시라면 `main`(#2)에서 `printf`(#1)를 호출했고, `printf` 내부에서 다시 `__vfprintf_internal`(#0)까지 들어와 있는 상태이므로, `finish`를 두 번 실행해야 `main`으로 돌아온다.

## 흔한 실수
- `step-mode`가 켜진 줄 모르고 `step`을 계속 눌러가며 "GDB가 고장났다"고 오해하는 것 — `show step-mode`로 먼저 확인한다.
- 라이브러리 함수 내부에서 `finish` 대신 계속 `step`/`stepi`만 눌러서 수동으로 빠져나오려는 것 — 몇 단계나 들어와 있는지 모르는 상태에서는 `finish`가 훨씬 빠르고 정확하다.
- `skip`으로 함수를 등록해놓고 나중에 그 함수 내부를 정말 봐야 하는 상황이 왔을 때 `skip`이 걸려 있다는 사실을 잊는 것 — `info skip`으로 현재 등록된 스킵 목록을 주기적으로 확인한다.
- 애초에 관심 없는 라이브러리 호출 줄에서도 습관적으로 `step`을 눌러 매번 이 문제를 반복하는 것 — 내 코드만 볼 때는 기본을 `next`로, 정말 함수 내부를 봐야 할 때만 `step`을 쓰는 습관을 들인다.

## 막혔을 때 다음 체크
- Step Into와 Step Over의 개념 차이를 먼저 정리하고 싶다면 → REV-0170 Step Into와 Step Over 차이
- 함수를 빠져나와 리턴값을 바로 확인하는 법이 궁금하다면 → REV-0171 Run Until Return과 함수 빠져나오기
- 명령어 단위 스텝(`stepi`/`nexti`)과의 차이가 궁금하다면 → REV-0187 GDB stepi nexti continue
- 애초에 라이브러리 함수 이름 자체가 안 보이는 정적/strip 바이너리라면 → REV-0716 statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때

## 미니 예제
```
(gdb) show step-mode
Mode of the step operation is on.
(gdb) set step-mode off
(gdb) break main
(gdb) run
(gdb) next
10          printf("Enter password: ");
(gdb) next
11          fgets(buf, sizeof(buf), stdin);
```
`step-mode`를 끄고 `printf`/`fgets` 호출 줄에서 `step` 대신 `next`를 쓰면, 라이브러리 내부로 들어가지 않고 곧바로 다음 소스 라인으로 넘어간다. 정말 `printf` 내부 동작이 궁금할 때만 그 줄에서 `step`을 쓰고, 갇혔다 싶으면 즉시 `finish`로 빠져나오면 된다.

## 관련 글
- REV-0170 — Step Into와 Step Over 차이
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0187 — GDB stepi nexti continue
- REV-0716 — statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때
- REV-0717 — GDB에서 disassemble 결과가 AT&T 문법이라 헷갈릴 때

## 출처/검증
- `step-mode` 옵션 정의 및 기본값, `skip`/`finish` 명령 동작: 본 환경 GDB 15.1 `help set step-mode`, `help skip` 실측 및 GDB 공식 매뉴얼(`Continuing and Stepping`, `Skipping Over Functions and Files` 챕터) 기준.
- `step`/`next`의 소스 라인 vs 명령어 단위 차이: GDB 공식 매뉴얼 기준.
