---
id: REV-0635
title: "libc 함수 사전: printf 계열 포맷 문자열 함수"
slug: "rev-0635-libc-printf-family"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, ltrace, objdump]
keywords: ["printf", "fprintf", "dprintf", "vprintf", "포맷 문자열", "va_list", "format string vulnerability", "%n"]
aliases: ["printf 함수 사전", "printf 시그니처", "포맷 문자열 취약점", "printf 가변 인자 전달 방식", "%n 취약점"]
symptom_keywords: ["printf에 사용자 입력을 그대로 넣는다", "포맷 문자열 취약점 %n %s", "printf 인자가 몇 개 전달되는지 모르겠다", "va_list가 뭔지 모르겠다", "printf 스택 릭"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`printf` 계열(`printf`, `fprintf`, `dprintf`, `vprintf` 등)은 포맷 문자열의 지정자(`%d`, `%s`, `%x`, `%n` 등) 개수만큼 뒤따르는 가변 인자를 소비하는데, **포맷 문자열 자체를 사용자가 제어할 수 있으면** 프로그램이 실제로 넘긴 인자보다 더 많은 `%x`/`%p`/`%n`을 요구해 스택/레지스터의 임의 값을 읽거나(정보 유출) 임의 주소에 값을 쓸(포맷 스트링 취약점) 수 있다.

## 언제 검색해야 하나
- `printf(buf)`처럼 **포맷 문자열 자리에 상수가 아니라 변수**(사용자 입력)가 그대로 들어가는 코드를 발견해 포맷 스트링 취약점 여부를 확인하고 싶을 때
- `call printf@plt` 직전 인자가 몇 개 세팅되는지 보고 포맷 문자열의 `%` 지정자 개수와 일치하는지 검증하고 싶을 때
- `%n` 지정자가 포함된 포맷 문자열을 만나 이게 왜 위험한지 이해하고 싶을 때

## 핵심 개념
```c
int printf(const char *format, ...);
int fprintf(FILE *stream, const char *format, ...);
int dprintf(int fd, const char *format, ...);
```
`printf`는 SysV x64 가변 인자 규약에 따라 `rdi=format`, 이후 정수/포인터 인자는 `rsi, rdx, rcx, r8, r9` 순서로, 그 이상은 스택에 쌓인다. 부동소수점 인자는 `xmm0~xmm7`을 따로 쓴다. `fprintf`는 `rdi=stream`, `rsi=format`으로 한 칸씩 밀리고, `dprintf`는 `rdi=fd`(파일 디스크립터, `write` 시스템콜로 직접 나가며 stdio 버퍼링 없음), `rsi=format`이다.

**포맷 지정자와 인자 소비**: `%d`, `%u`, `%x`는 정수 레지스터 하나, `%s`는 포인터(문자열 주소) 하나, `%p`는 포인터를 소비한다. `%n`은 특별한데, **그때까지 출력된 문자 개수를 지정된 주소(포인터 인자)에 정수로 써넣는다** — 즉 `%n`은 "읽는" 지정자가 아니라 "메모리에 쓰는" 지정자다.

**포맷 스트링 취약점의 원리**: `printf(user_input)`처럼 포맷 문자열 자체가 사용자 입력이면, 공격자는 `"%x.%x.%x.%x"` 같은 문자열을 입력해 실제로는 넘겨주지 않은 값들을 요구할 수 있다. `printf`는 포맷 문자열만 보고 그다음 인자 레지스터/스택을 순서대로 소비하므로, **호출자가 실제로 넘긴 인자 개수와 무관하게** 계속 다음 레지스터·스택 값을 읽어 스택 카나리, 저장된 리턴 주소, 다른 지역 변수 값 등을 그대로 유출시킬 수 있다. `%s`를 쓰면 그 값을 주소로 해석해 메모리 내용을 문자열로 읽어버리고, `%n`을 쓰면 그 주소에 값을 덮어써 GOT overwrite 같은 쓰기 공격까지 가능해진다.

**정상적인 사용**: `printf("%s", user_input)`처럼 포맷 문자열은 항상 고정된 문자열 리터럴이고 사용자 입력은 인자로만 전달되어야 안전하다.

## 화면/코드에서 보이는 징후
- `lea rdi, [스택버퍼 또는 입력변수]` 후 바로 `call printf@plt` — **두 번째 인자 없이 포맷 문자열 자리에만 값이 들어감**. 이 패턴이 가장 강력한 포맷 스트링 취약점 신호다.
- `mov esi, [값]` 등 인자 세팅이 포맷 문자열의 `%` 지정자 개수보다 뚜렷하게 적음
- 디컴파일러(IDA/Ghidra)에서 `printf(name);`처럼 인자가 하나뿐인 호출이 보임(정상 코드는 대개 `printf("%s", name);`)
- 문자열 안에 `%n`이 포함되어 있으면 즉시 최우선으로 의심

## 가장 먼저 할 것
`printf`(또는 계열 함수) 호출부에서 **포맷 문자열이 상수 리터럴인지, 아니면 변수(특히 사용자 입력에서 유래한 버퍼)인지**부터 확인한다. 상수가 아니라면 포맷 스트링 취약점 후보로 최우선 표시해둔다.

## 단계별 절차
1. `objdump -d ./chall | grep -B6 'call.*printf@plt'`로 인자 세팅 코드를 확인, `rdi`가 `.rodata`의 고정 주소인지 스택/힙 변수인지 구분.
2. 고정 주소가 아니면 IDA/Ghidra에서 `X`(xref)로 그 버퍼가 어디서 채워지는지(입력 함수) 추적한다 — `scanf`/`fgets`/`read`로 이어지면 사용자가 완전히 제어 가능한 포맷 문자열이다.
3. GDB에서 `break printf` 후 `x/s $rdi`로 실제 런타임 포맷 문자열 확인.
4. 실제 입력으로 `"%x.%x.%x.%x.%x.%x"`처럼 넣어보고 프로그램 출력에 스택 값(16진수)이 그대로 새는지 테스트.
5. `%p` 여러 개를 넣어 몇 번째 인자 위치가 자기가 입력한 문자열 자체(자기 참조, "직접 파라미터 접근"으로 `%7$p` 같은 표기 사용 가능)를 가리키는지 찾아내면 이후 `%n` 쓰기 공격의 오프셋 계산에 활용한다.

## 명령어/단축키
```bash
objdump -d ./chall | grep 'printf@plt\|fprintf@plt\|dprintf@plt'
ltrace -s 200 ./chall
```
GDB/Pwndbg: `break printf`, `x/s $rdi`, `x/8gx $rsp`(스택에 남아있는 잠재적 유출 대상 값 확인)

## 출력 해석
- 프로그램에 `%x %x %x %x`를 입력했을 때 스택 카나리처럼 보이는 값(하위 바이트가 `0x00`인 8바이트 패턴)이나 그럴듯한 코드 주소(`0x00005555...`, PIE 베이스 계산에 쓸 수 있음)가 출력되면 정보 유출이 실제로 동작한다는 뜻이다.
- `%n`을 포함한 입력을 넣었을 때 프로그램이 SIGSEGV로 죽으면, `%n`이 쓰려고 한 "주소"로 해석된 값이 유효하지 않은 메모리였다는 뜻 — 오프셋을 더 조정하면 원하는 주소에 도달할 수 있다는 신호이기도 하다.
- `dprintf`는 stdio 버�터링을 거치지 않고 바로 `write` 시스템콜로 나가므로, `strace`에서 `printf`/`fprintf`보다 훨씬 더 직접적으로 대응하는 `write` 호출을 볼 수 있다.

## 흔한 실수
- `printf(buf)`와 `printf("%s", buf)`가 "결과가 같으니 안전하다"고 착각하는 것 — `buf` 안에 `%`가 들어있지 않은 입력에 대해서만 우연히 같은 결과가 나올 뿐, `buf`에 `%x` 같은 문자가 포함되는 순간 완전히 다르게 동작한다.
- `%n`이 흔치 않다고 무시하는 것 — 최신 배포판/컴파일러는 `-D_FORTIFY_SOURCE`, `-Wformat-security` 등으로 이런 패턴을 컴파일 경고/런타임 차단하지만, CTF 문제 바이너리는 의도적으로 이 방어를 끄고 만들어지는 경우가 많다.
- 가변 인자 개수를 셀 때 `%%`(리터럴 `%` 문자 하나를 출력)를 지정자로 잘못 세는 것 — `%%`는 인자를 전혀 소비하지 않는다.

## 막혔을 때 다음 체크
- 포맷팅 결과를 메모리 버퍼에 쓰는 sprintf/snprintf가 궁금하면 → REV-0628.
- SysV 가변 인자 전달 규칙(정수/부동소수점 레지스터 구분)을 더 자세히 보려면 → REV-0106.
- 사용자 입력이 어디서 들어오는지부터 추적하려면 → REV-0109.

## 미니 예제
```c
char name[64];
fgets(name, sizeof(name), stdin);
printf(name);          // 취약: 포맷 문자열이 사용자 입력 그대로
```
입력으로 `%p %p %p %p %p %p`를 주면:
```
$ echo '%p %p %p %p %p %p' | ./chall
0x7ffee2a1b3c0 0x5583a1b3e260 0x7f8e4d2b7083 0x100000000 0x5583a1b3e1a0 (nil)
```
호출자가 실제로 넘긴 인자가 하나도 없는데도 `printf`가 스택/레지스터에 남아있던 값들을 순서대로 계속 읽어 출력하는 것을 볼 수 있다 — 이 중 코드 주소로 보이는 값(`0x5583...`)은 PIE 베이스 계산에, 스택 주소(`0x7ffe...`)는 스택 릭에 바로 활용 가능하다.

## 관련 글
- REV-0628 — libc 함수 사전: sprintf snprintf 계열
- REV-0106 — SysV AMD64 Calling Convention
- REV-0109 — scanf fgets read 입력 추적
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- `printf`/`fprintf`/`dprintf` 시그니처와 `%n`을 포함한 포맷 지정자 동작: ISO C 표준(C11 7.21.6.1) 및 Linux man-pages `printf(3)` 기준.
- 가변 인자 레지스터 전달 순서(정수 rdi 이후 rsi,rdx,rcx,r8,r9 / 부동소수점 xmm0-7): System V Application Binary Interface AMD64 psABI 문서 기준.
- 포맷 스트링 취약점의 원리(인자 개수 불일치로 인한 스택/레지스터 유출 및 `%n` 쓰기): 다수의 공개 바이너리 익스플로잇 교육 자료(예: exploit-db, CTF 포맷 스트링 공격 가이드) 기준 일반화된 서술.
