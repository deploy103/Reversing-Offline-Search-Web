---
id: REV-0629
title: "libc 함수 사전: strcpy strncpy strcat strncat"
slug: "rev-0629-libc-strcpy-strncpy-strcat-strncat"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["strcpy", "strncpy", "strcat", "strncat", "버퍼 오버플로우", "널 종료", "off-by-one"]
aliases: ["strcpy strncpy strcat strncat 함수 사전", "strcpy 시그니처", "strncpy 널 종료 문제", "strcat 버퍼 오버플로우", "문자열 복사 함수 비교"]
symptom_keywords: ["strcpy로 인한 스택 오버플로우", "strncpy가 널 종료를 안 한다", "strcat 대상 버퍼가 넘친다", "strncat n 값이 헷갈린다", "문자열 복사 함수 중 뭐가 안전한지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strcpy`/`strcat`은 목적지 버퍼 크기를 전혀 확인하지 않아 CTF 스택 오버플로우의 대표 원인이고, `strncpy`/`strncat`은 길이 제한(`n`)을 받지만 **`strncpy`는 소스가 `n` 이상이면 널 종료를 보장하지 않는다**는 함정이 있어 "안전한 함수"라고 무조건 믿으면 안 된다.

## 언제 검색해야 하나
- `call strcpy@plt`가 보이고 목적지가 고정 크기 스택 버퍼인데 소스 길이가 사용자 입력이라 오버플로우 여부를 확인하고 싶을 때
- `strncpy`를 썼는데도 이후 코드에서 이상한 길이의 문자열이 출력될 때(널 종료 누락 의심)
- `strcat`으로 문자열을 이어붙이는데 목적지 버퍼에 이미 얼마나 차 있는지 계산해야 할 때

## 핵심 개념
```c
char *strcpy(char *dest, const char *src);
char *strncpy(char *dest, const char *src, size_t n);
char *strcat(char *dest, const char *src);
char *strncat(char *dest, const char *src, size_t n);
```
네 함수 모두 **반환값은 `dest` 포인터 그대로**다(체이닝 목적, 성공/실패 판단용이 아님).

**strcpy**: `src`의 널 종료(`\0`)까지 통째로 `dest`에 복사한다. `dest`의 크기를 전혀 알지 못하므로 `src`가 `dest`보다 길면 그만큼 뒤쪽 메모리(스택이면 저장된 레지스터·카나리·리턴 주소, 힙이면 다음 청크 헤더)를 덮어쓴다.

**strncpy**: 최대 `n`바이트까지만 복사한다. 그런데 동작이 두 갈래로 갈린다:
- `src`가 `n`바이트보다 **짧으면** 나머지를 `\0`으로 채운다(`dest` 전체가 항상 `n`바이트만큼 초기화됨).
- `src`가 `n`바이트보다 **길거나 같으면** 정확히 `n`바이트만 복사하고 **널 종료를 붙이지 않는다.** 이 경우 `dest`는 널로 끝나지 않는 문자열이 되어, 이후 `strlen(dest)`나 `printf("%s", dest)`를 호출하면 버퍼 뒤 메모리까지 읽어버리는 out-of-bounds read가 발생할 수 있다.

**strcat**: `dest`의 기존 널 종료 위치를 찾은 뒤 그 위치부터 `src`를 이어 붙인다. `strcpy`와 마찬가지로 `dest`의 남은 공간을 전혀 확인하지 않는다 — 오히려 `dest`에 이미 데이터가 있는 상태에서 추가로 덮어쓰므로 오버플로우 위치를 계산할 때 기존 문자열 길이까지 더해야 한다.

**strncat**: `n`은 "복사할 `src`의 최대 바이트 수"이며, **널 종료 문자는 `n`에 포함되지 않는다.** 즉 `strncat(dest, src, n)`은 최악의 경우 `dest`에 `n+1`바이트(데이터 `n` + 널 1)를 추가로 쓸 수 있다. `strncpy`의 `n`(전체 버퍼 크기 개념)과 의미가 다르다는 점이 흔한 혼동 포인트다.

## 화면/코드에서 보이는 징후
- `lea rdi, [rbp-0x??]` (목적지, 스택 버퍼) 이후 `lea rsi, [입력버퍼]` 후 `call strcpy@plt`
- `mov edx, N` 처럼 세 번째 인자에 상수가 들어가면 `strncpy`/`strncat`
- `strncpy` 호출 뒤 별도로 `mov byte ptr [dest+n-1], 0`을 수동으로 추가하는 코드가 있으면, 개발자가 널 종료 누락 문제를 알고 방어한 것

## 가장 먼저 할 것
어느 함수인지(인자 개수 2개=strcpy/strcat, 3개=strncpy/strncat) 먼저 구분하고, 목적지 버퍼의 실제 크기(스택 프레임 오프셋 차이 또는 `sizeof`로 알 수 있는 배열 크기)를 소스 길이와 비교한다.

## 단계별 절차
1. `objdump -d ./chall | grep -B6 'call.*strn\?cpy@plt\|call.*strn\?cat@plt'`로 인자 세팅 확인.
2. GDB에서 `break strcpy`(또는 대상 함수) 후 `x/s $rdi`(dest), `x/s $rsi`(src) 확인.
3. `strncpy`/`strncat`이면 `print $rdx`로 `n` 값 확인.
4. `finish` 후 `x/s $rdi`(dest 재확인)로 실제 복사된 결과와 널 종료 여부(`x/32xb $rdi`로 원시 바이트까지)를 확인.
5. `info frame`으로 dest 버퍼와 저장된 canary/리턴 주소 사이 거리를 계산해 오버플로우 가능성 판단.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'strcpy@plt\|strncpy@plt\|strcat@plt\|strncat@plt'
ltrace -s 200 ./chall
```
GDB/Pwndbg: `break strcpy`, `break strncpy`, `x/s $rdi`, `x/s $rsi`, `x/32xb $rdi`, `print $rdx`

## 출력 해석
- `x/32xb $rdi` 실행 후 복사된 데이터 바로 뒤에 `0x00`이 없다면(다른 데이터가 바로 이어짐) `strncpy`의 널 미종료 케이스에 해당한다.
- `ltrace`에서 `strcpy(dest, "AAAA...(긴 문자열)")` 형태로 소스 길이가 눈에 띄게 길게 로그되면 오버플로우 재현 입력을 그대로 참고할 수 있다.
- `strcat` 호출 전후로 `x/s $rdi`를 두 번 찍어 길이 차이를 재면 실제로 몇 바이트가 추가됐는지 확인 가능하다.

## 흔한 실수
- `strncpy`를 쓰면 무조건 안전하다고 믿는 것 — 널 종료를 보장하지 않는 케이스를 놓치면 여전히 정보 유출(out-of-bounds read) 취약점이 될 수 있다.
- `strncat`의 `n`을 목적지 버퍼의 **남은 공간**이 아니라 **버퍼 전체 크기**로 잘못 계산하는 것 — `strncat`은 `dest`에 이미 있는 데이터 길이를 고려하지 않고 그 뒤에 최대 `n`바이트를 추가로 붙인다.
- `strcpy`/`strcat` 호출을 보고 바로 "이건 취약점이다"라고 단정하는 것 — 목적지가 충분히 큰 고정 배열이고 소스 길이가 프로그램 로직상 항상 제한되어 있다면 실제로는 안전할 수 있다. 반드시 실제 크기 비교를 해봐야 한다.

## 막혔을 때 다음 체크
- 포맷 문자열 기반 복사(sprintf류)가 궁금하면 → REV-0628.
- 문자열 비교 함수(strcmp/strncmp/memcmp)가 궁금하면 → REV-0110.
- 문자열 탐색 함수(strchr/strstr/strtok)가 궁금하면 → REV-0630.
- 스택 오버플로우로 이어지는 입력 함수 자체가 궁금하면 → REV-0109.

## 미니 예제
```c
char dest[8];
strncpy(dest, "ABCDEFGHIJ", 8);  // 정확히 8바이트 복사, 널 종료 없음!
printf("%s\n", dest);            // dest 뒤 스택 메모리까지 이어서 출력될 수 있음
```
```gdb
(gdb) break strncpy
(gdb) run
(gdb) x/s $rsi
0x402004: "ABCDEFGHIJ"
(gdb) print $rdx
$1 = 8
(gdb) finish
(gdb) x/9xb $rdi
0x7fffffffe408: 0x41 0x42 0x43 0x44 0x45 0x46 0x47 0x48 0x?? 
```
9번째 바이트(`dest[8]`, 배열 범위 밖)가 `0x00`이 아니라 임의 값이면 널 종료가 안 된 상태임을 직접 확인한 것이다.

## 관련 글
- REV-0628 — libc 함수 사전: sprintf snprintf 계열
- REV-0630 — libc 함수 사전: strchr strstr strtok
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0109 — scanf fgets read 입력 추적

## 출처/검증
- `strcpy`/`strncpy`/`strcat`/`strncat` 시그니처와 널 종료 규칙: ISO C 표준(C11 7.24.2.3, 7.24.2.4, 7.24.3.1, 7.24.3.2) 및 Linux man-pages `strcpy(3)`, `strncpy(3)`, `strcat(3)`, `strncat(3)` 기준.
- `strncpy` 널 미종료 함정은 다수의 공식 보안 코딩 가이드(CERT C, `strncpy(3)` man 페이지 CAVEATS 섹션)에서 공통적으로 지적하는 내용.
