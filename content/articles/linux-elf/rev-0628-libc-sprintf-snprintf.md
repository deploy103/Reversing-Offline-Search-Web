---
id: REV-0628
title: "libc 함수 사전: sprintf snprintf 계열"
slug: "rev-0628-libc-sprintf-snprintf"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["sprintf", "snprintf", "포맷 문자열", "va_list", "버퍼 오버플로우", "%n"]
aliases: ["sprintf snprintf 함수 사전", "sprintf 시그니처", "snprintf 시그니처", "sprintf 버퍼 오버플로우", "sprintf snprintf 차이"]
symptom_keywords: ["sprintf 사용 시 버퍼 크기 제한이 없다", "snprintf 반환값이 버퍼에 쓴 것보다 크다", "sprintf 스택 오버플로우 원인", "포맷 문자열에 사용자 입력이 그대로 들어간다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`sprintf(char *str, const char *format, ...)`는 `printf`처럼 포맷팅된 문자열을 화면이 아니라 메모리 버퍼 `str`에 쓰는 함수이고, **버퍼 크기 제한이 없어** 포맷 결과가 길면 그대로 버퍼 오버플로우가 나며, `snprintf(char *str, size_t size, ...)`는 `size`바이트(널 종료 포함)를 넘지 않도록 제한하는 안전한 버전이다.

## 언제 검색해야 하나
- 디스어셈블리에서 `call sprintf@plt`가 보이는데 인자가 몇 개인지, 몇 번째가 버퍼고 몇 번째가 포맷 문자열인지 헷갈릴 때
- `sprintf`로 스택 버퍼에 쓰다가 스택 카나리/리턴 주소가 깨지는 취약점을 의심할 때
- `snprintf`의 반환값이 실제로 쓰인 바이트 수와 다르게 나와서(잘림 발생 시) 원인을 찾고 싶을 때

## 핵심 개념
```c
int sprintf(char *str, const char *format, ...);
int snprintf(char *str, size_t size, const char *format, ...);
```
두 함수 모두 `printf` 계열(REV-0635)과 동일한 포맷 지정자(`%d`, `%s`, `%x`, `%p` 등)를 사용하지만, 출력 대상이 `stdout`이 아니라 `str`이 가리키는 메모리라는 점만 다르다.

**인자 순서(SysV x64)**: `sprintf`는 `rdi=str`, `rsi=format`, 이후 가변 인자가 `rdx, rcx, r8, r9, 스택` 순서로 이어진다. `snprintf`는 `rdi=str`, `rsi=size`, `rdx=format`, 이후 가변 인자가 `rcx, r8, r9, 스택` 순서로 밀린다 — **`size` 인자 하나가 끼어들어 나머지 인자 레지스터가 한 칸씩 밀린다**는 점이 두 함수를 구분하는 핵심 단서다.

**`sprintf`의 위험성**: 몇 바이트가 쓰일지는 포맷 문자열과 인자 값에 따라 런타임에 결정된다. 예를 들어 `sprintf(buf, "%s", user_input)`에서 `buf`가 `char buf[16]`인데 `user_input`이 100바이트짜리 문자열이면, `sprintf`는 아무 제약 없이 100바이트를 그대로 써서 스택/힙 오버플로우를 일으킨다. `strcpy`(REV-0629)와 마찬가지로 "길이 제한이 없는" 대표적인 위험 함수다.

**`snprintf`의 반환값**: `size`만큼만 실제로 쓰지만, **반환값은 잘림이 없었다면 썼을 전체 길이**(널 종료 제외)다. 즉 반환값이 `size` 이상이면 출력이 잘렸다는 뜻이다. 이 특성 덕분에 `int need = snprintf(NULL, 0, fmt, ...);`처럼 첫 호출로 필요한 버퍼 크기를 먼저 계산하고, 그 크기만큼 `malloc`한 뒤 두 번째 `snprintf`로 실제 값을 채우는 패턴이 자주 쓰인다.

## 화면/코드에서 보이는 징후
- `lea rdi, [buf]` 이후 `lea rsi, [format_string]` (sprintf) 또는 `mov esi, <size>` 후 `lea rdx, [format_string]` (snprintf)
- 스택 버퍼(`[rbp-0x??]`)를 목적지로 잡는 `sprintf` 호출은 스택 오버플로우 후보로 항상 표시해둘 만하다
- 반환값(`eax`)을 이후 문자열 길이로 재사용하는 코드가 있으면 `snprintf`의 "필요 길이 계산" 패턴일 가능성

## 가장 먼저 할 것
호출된 함수가 `sprintf`인지 `snprintf`인지부터 확인한다. `sprintf`라면 목적지 버퍼의 선언 크기(스택 프레임 상 다른 변수와의 거리, 또는 malloc 크기)를 먼저 확인해 오버플로우 가능성을 계산한다.

## 단계별 절차
1. `objdump -d ./chall | grep -B8 'call.*sprintf@plt\|call.*snprintf@plt'`로 인자 세팅 코드 확인.
2. GDB에서 `break sprintf`(또는 `break snprintf`) 후 `x/s $rdi`로 목적지 버퍼 주소, `x/s $rsi`(sprintf) 또는 `x/s $rdx`(snprintf)로 포맷 문자열을 읽는다.
3. `finish` 후 `print $rax`로 실제 쓰인(또는 쓰였을) 문자열 길이 확인.
4. `snprintf`라면 `print $rsi`(size 인자)와 반환값을 비교해 잘림 여부 판단.
5. 목적지 버퍼가 스택이면 `info frame`으로 그 버퍼와 저장된 리턴 주소 사이 거리를 계산해 오버플로우로 리턴 주소까지 덮을 수 있는지 확인.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'sprintf@plt\|snprintf@plt'
ltrace -s 200 ./chall     # 문자열 인자를 200자까지 잘리지 않고 표시
```
GDB/Pwndbg: `break sprintf`, `break snprintf`, `x/s $rdi`, `x/s $rsi`, `x/s $rdx`, `print $rax`

## 출력 해석
- `sprintf` 반환값(`eax`)은 널 종료 문자를 제외하고 실제로 쓴 바이트 수다.
- `snprintf` 반환값이 두 번째 인자(`size`)보다 **크거나 같으면** 출력이 잘렸다는 뜻 — 이 경우 버퍼 안의 실제 문자열은 `size-1`바이트에서 끊기고 널로 종료된다.
- `ltrace` 출력에서 `sprintf(buf, "%s", "AAAA...(긴 문자열)") = 200` 처럼 반환값이 목적지 버퍼 크기를 훨씬 넘으면 오버플로우가 실제로 발생했다는 강한 증거다.

## 흔한 실수
- `snprintf`도 `size`를 초과해서 쓸 수 있다고 착각하는 것 — `snprintf`는 절대 `size`바이트(널 포함)를 넘겨 쓰지 않는다. 넘치는 부분은 버퍼에 안 쓰이고 버려질 뿐, 반환값에는 "썼어야 할 길이"로 반영된다.
- `sprintf`의 반환값을 실제 쓰인 바이트 수가 아니라 항상 성공/실패 코드(0/음수)라고 생각하는 것 — `printf` 계열은 전부 "쓴 문자 개수"를 반환하지, 성공 여부를 0/1로 반환하지 않는다.
- `snprintf(buf, sizeof(buf), ...)`처럼 안전하게 쓰인 코드를 보고도 여전히 오버플로우를 의심하는 것 — `sizeof(buf)`가 정확한 배열 크기와 일치하는 정적 배열이라면 이 패턴은 안전하다(단, `buf`가 포인터인데 `sizeof(buf)`를 잘못 써서 포인터 크기(8)가 들어간 경우는 예외).

## 막혔을 때 다음 체크
- 포맷 문자열 자체의 위험성(`%n`, `%s` 임의 읽기)이 궁금하면 → REV-0635.
- 길이 제한 없는 문자열 복사 함수 계열이 궁금하면 → REV-0629.
- 라이브러리 호출 인자를 빠르게 로그로 보고 싶으면 → REV-0111(ltrace).

## 미니 예제
```c
char buf[16];
sprintf(buf, "%s", long_user_input);   // long_user_input이 16바이트보다 길면 오버플로우
```
```gdb
(gdb) break sprintf
(gdb) run
(gdb) x/s $rdi
0x7fffffffe410: ""
(gdb) x/s $rsi
0x402004: "%s"
(gdb) finish
Value returned is $1 = 40
```
반환값 `40`이 `buf`의 선언 크기(16)보다 크므로 이 호출로 스택 버퍼 오버플로우가 발생했음을 알 수 있다.

## 관련 글
- REV-0635 — libc 함수 사전: printf 계열 포맷 문자열 함수
- REV-0629 — libc 함수 사전: strcpy strncpy strcat strncat
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0106 — SysV AMD64 Calling Convention

## 출처/검증
- `sprintf`/`snprintf` 시그니처, 반환값 규칙(잘림 시 필요 길이 반환): ISO C 표준(C11 7.21.6.5, 7.21.6.6) 및 Linux man-pages `printf(3)` 기준.
- 인자 레지스터 배치(SysV x64 가변 인자 전달): System V Application Binary Interface AMD64 psABI 문서 기준.
