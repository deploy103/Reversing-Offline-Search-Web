---
id: REV-0676
title: "AT_RANDOM과 스택 카나리 초기화 관계"
slug: "rev-0676-at-random-stack-canary"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["AT_RANDOM", "스택 카나리", "stack_chk_guard", "auxv", "TCB", "fs:0x28", "__stack_chk_fail", "_dl_setup_stack_chk_guard"]
aliases: ["at_random이 뭔가요", "스택 카나리 초기값은 어디서 오나", "canary 랜덤값 생성 원리", "fs:0x28 카나리"]
symptom_keywords: ["gdb에서 auxv 읽는 법을 모르겠음", "카나리 값이 프로그램마다 왜 다른지 모르겠음", "카나리 마지막 바이트가 항상 00인 이유를 모르겠음", "fs 세그먼트 레지스터로 카나리를 읽는 코드가 이해 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
스택 카나리(`__stack_chk_guard`) 값은 프로그램이 실행될 때마다 커널이 스택에 심어주는 16바이트 난수인 `AT_RANDOM`에서 나오며, glibc가 이 중 8바이트를 잘라 최상위 바이트를 0으로 만든 뒤 스레드 제어 블록(TCB)에 저장해 매 함수 호출마다 `fs` 세그먼트를 통해 검증한다.

## 언제 검색해야 하나
- GDB에서 `p/x $fs_base` 또는 `x/2gx $fs_base+0x28`로 카나리를 직접 읽어보고 싶을 때
- 같은 바이너리를 재실행할 때마다 카나리 값이 달라지는데, 그 값이 어디서 나오는지 원리가 궁금할 때
- 디스어셈블리에서 `mov rax, fs:0x28` 같은 코드를 보고 이게 무슨 뜻인지 모를 때
- 카나리 leak 익스플로잇을 짜다가 "카나리의 최하위 바이트는 항상 0x00"이라는 규칙의 근거를 확인하고 싶을 때
- `LD_SHOW_AUXV=1`로 실행했을 때 `AT_RANDOM` 항목을 보고 이게 카나리와 무슨 관계인지 궁금할 때

## 핵심 개념

### AT_RANDOM이란
리눅스 커널은 ELF 바이너리를 실행할 때(`execve` 처리 중, `fs/binfmt_elf.c`의 `create_elf_tables`) 스택 최상단 근처에 커널이 직접 생성한 16바이트 난수를 심어두고, 이 메모리 주소를 auxiliary vector(auxv, REV-0677 참고)의 `AT_RANDOM`(타입 번호 25) 엔트리에 담아 프로그램에 전달한다. 이 16바이트는 `/dev/urandom`과 같은 커널 난수 생성기에서 뽑히며, 프로세스마다(즉 실행할 때마다) 새로 생성된다.

이 16바이트는 원래 두 가지 용도로 쓰인다.
1. glibc가 스택 카나리(`__stack_chk_guard`) 값을 만드는 재료로 쓴다.
2. glibc가 포인터 암호화(pointer guard, `PTR_MANGLE`/`PTR_DEMANGLE`에 쓰이는 `__pointer_chk_guard`) 값을 만드는 재료로도 쓴다.

### 카나리 값이 만들어지는 과정
정적 실행 파일이든 동적 실행 파일이든, 프로그램이 `_start` → `__libc_start_main`(glibc 2.34 이후에는 `__libc_start_main`이 `_start`에 인라인되어 사라졌지만 역할은 동일하게 초기화 코드가 수행) 경로를 거치는 동안 `security_init()`이라는 내부 함수가 호출된다. 이 함수 안에서 다음과 같은 일이 일어난다(glibc `csu/libc-start.c`, `sysdeps/generic/dl-osinfo.h` 기준 로직).

1. 동적 로더(또는 정적 바이너리의 자체 초기화 코드)가 auxv를 스캔해 `AT_RANDOM` 엔트리의 값(포인터)을 `_dl_random`이라는 전역 변수에 저장한다.
2. `_dl_setup_stack_chk_guard(_dl_random)` 함수가 이 포인터가 가리키는 16바이트 중 앞의 8바이트(64비트 기준, `sizeof(uintptr_t)`만큼)를 `memcpy`로 복사한다.
3. 복사한 8바이트 정수의 **최상위 바이트(리틀엔디언 기준으로는 메모리상 가장 마지막 바이트)를 강제로 0x00으로 덮어쓴다.**
4. 이렇게 만들어진 값을 `__stack_chk_guard`(전역 변수 위치가 아니라 TCB 내부, x86-64에서는 `fs:0x28`)에 저장한다.
5. `AT_RANDOM`을 구하지 못하는 예외적 환경(아주 오래된 커널 등)이면, 대신 `{0, 랜덤하지 않은 고정 패턴, '\n', 0xff}` 형태의 폴백 값을 쓴다 — 이 경우는 사실상 카나리가 무력화된 것과 같으므로 최신 커널/glibc 조합에서는 거의 볼 일이 없다.

이 "최상위 바이트를 0으로 만든다"는 규칙이 실무에서 자주 언급되는 **"카나리는 항상 널 바이트로 시작한다"**는 특성의 정체다. 스택은 높은 주소에서 낮은 주소로 자라고, 버퍼 오버플로우는 낮은 주소(버퍼)에서 높은 주소(카나리, 저장된 RBP, 리턴 주소) 방향으로 덮어쓰기 때문에, 버퍼 바로 위에 위치한 카나리의 첫 바이트가 항상 0x00이라는 사실은 `strcpy`/`gets`류의 문자열 함수 오버플로우가 카나리를 "우연히" 건드리지 못하게 막는 효과를 낸다 — 널 바이트를 만나면 문자열 함수가 복사를 멈추기 때문이다. 반대로 이 성질은 카나리를 한 바이트씩 brute-force하는 공격(포크 서버 환경에서 카나리의 첫 바이트가 항상 0x00이라는 걸 알고 나머지 7바이트만 추측)에도 그대로 이용된다.

### TCB와 fs:0x28
x86-64 리눅스에서 스레드별 데이터(TCB, Thread Control Block)는 `fs` 세그먼트 레지스터가 가리키는 영역에 있다(REV-0680 TLS 세그먼트 참고). glibc의 TCB 구조체(`tcbhead_t`) 안에는 `stack_guard`라는 필드가 있고, 이 필드의 오프셋이 바로 `0x28`이다. 그래서 컴파일러(gcc `-fstack-protector`)가 생성하는 함수 프롤로그/에필로그 코드는 전역 변수를 참조하는 대신 항상 `fs:0x28`을 직접 읽는다.

```asm
; 프롤로그: 카나리를 스택에 복사
mov    rax, fs:0x28
mov    [rbp-0x8], rax
xor    eax, eax          ; 카나리 값 자체는 레지스터에 남기지 않음

; 에필로그: 검증
mov    rax, [rbp-0x8]
xor    rax, fs:0x28
je     ok
call   __stack_chk_fail
ok:
leave
ret
```
`fs:0x28`을 직접 참조하기 때문에 카나리 값은 전역 심볼로 존재하지 않고, GOT 조작이나 데이터 세그먼트 덮어쓰기로는 건드릴 수 없다 — TCB 자체를 덮어써야 한다는 뜻이다. 32비트 x86 리눅스에서는 `fs` 대신 `gs` 세그먼트를 사용해 같은 역할을 한다(`mov eax, gs:0x14`가 전형적인 패턴).

## 화면/코드에서 보이는 징후
- 디스어셈블리 함수 프롤로그에 `mov rax, fs:0x28`(x64) 또는 `mov eax, gs:0x14`(x86)가 보이면 스택 프로텍터가 켜진 함수다.
- GDB에서 `info auxv` 실행 시 `AT_RANDOM  0x7fffffffe1c9` 같은 항목이 보인다.
- 같은 바이너리를 여러 번 실행했을 때 `p $rbp-0x8`(또는 카나리 저장 위치)에서 읽히는 값이 매번 다르다.
- 카나리 값을 16진수로 덤프하면 특정 1바이트(리틀엔디언 메모리 배치에서 버퍼에 가장 가까운 바이트)가 항상 `00`으로 고정되어 있다.

## 가장 먼저 할 것
`checksec`으로 `Canary found`가 뜬 바이너리를 분석할 때는, 카나리를 "그냥 랜덤 상수"로 취급하지 말고 이 값이 `AT_RANDOM` → glibc 초기화 → TCB(`fs:0x28`) 경로로 매 실행마다 새로 만들어진다는 점을 먼저 확인한다. GDB에서 `info auxv`로 `AT_RANDOM` 주소를 확인하고, 그 주소를 직접 덤프해서 카나리 값과 어떻게 연결되는지 눈으로 확인하면 이후 leak/브루트포스 전략을 세우기 훨씬 쉬워진다.

## 단계별 절차

**1) auxv에서 AT_RANDOM 주소 확인**
```gdb
gdb ./chall
break main
run
info auxv
```
출력 예:
```
33   AT_SYSINFO_EHDR      System-supplied DSO's ELF header  0x7ffff7fc9000
25   AT_RANDOM            Address of 16 random bytes        0x7fffffffe1c9
...
```

**2) 그 16바이트를 직접 덤프**
```gdb
x/16bx 0x7fffffffe1c9
```

**3) 실제 카나리 값(TCB의 fs:0x28)과 비교**
```gdb
p/x $fs_base
x/gx $fs_base+0x28
```
`AT_RANDOM`이 가리키는 16바이트 중 앞 8바이트를 최상위 바이트만 0으로 바꾼 값이 `fs_base+0x28`에 그대로 들어있는 것을 확인할 수 있다.

**4) 함수 스택 프레임에 복사된 카나리 확인**
```gdb
disassemble main
```
프롤로그에서 `mov rax,fs:0x28` 다음에 어느 스택 오프셋(`[rbp-0x8]` 등)에 저장하는지 확인하고, 그 위치를 `x/gx $rbp-8`로 조회하면 같은 값이 보인다.

**5) Pwndbg로 더 빠르게 확인**
```gdb
canary
```
Pwndbg는 `canary` 명령 한 번으로 현재 프로세스의 카나리 값과 저장 위치를 바로 보여준다.

## 명령어/단축키
```gdb
info auxv
x/16bx <AT_RANDOM 주소>
p/x $fs_base
x/gx $fs_base+0x28
canary          ; Pwndbg 전용
```
```bash
LD_SHOW_AUXV=1 ./chall     # 실행 전 auxv를 텍스트로 덤프
cat /proc/<pid>/auxv | xxd  # 실행 중인 프로세스의 auxv 원본 바이트 확인
```

## 출력 해석
- `info auxv`의 `AT_RANDOM` 줄 오른쪽 주소는 "16바이트 난수가 저장된 스택 위의 위치"이지 카나리 값 자체가 아니다. 반드시 그 주소를 다시 덤프해야 실제 바이트를 볼 수 있다.
- `x/gx $fs_base+0x28`로 읽은 8바이트 값이 곧 `__stack_chk_guard`이며, 스택 프레임에 저장된 카나리와 동일해야 정상이다. 값이 다르면 이미 스택 프레임이 오염되었거나 다른 스레드를 보고 있는 것이다.
- 카나리 값을 리틀엔디언 그대로 화면에 출력하면(`p/x`) 마지막 표시 자리(가장 낮은 주소, 즉 메모리에 저장될 때 버퍼와 인접한 바이트)가 `00`으로 끝나는 패턴을 볼 수 있다. 예를 들어 `0x7a3c91de00000000`처럼 나온다면 이는 정수로 볼 때 최상위 바이트가 0인 것이고, 메모리에는 `00 00 00 00 de 91 3c 7a` 순서로 저장되어 버퍼 쪽 첫 바이트가 널이 된다.

## 흔한 실수
- 카나리를 "컴파일 시점에 고정된 상수"로 착각하는 것 — 실제로는 실행할 때마다 커널이 새로 뽑은 난수에서 파생되므로, 정적 분석만으로는 값을 알 수 없고 반드시 leak을 통해서만 알아낼 수 있다.
- `AT_RANDOM` 주소에 담긴 16바이트를 그대로 카나리라고 착각하는 것 — 실제 카나리는 그중 앞 8바이트를 가공(최상위 바이트를 0으로)한 값이다. 나머지 8바이트는 포인터 가드(`__pointer_chk_guard`, `PTR_MANGLE`)를 만드는 데 쓰인다.
- 32비트 바이너리에서 `fs` 세그먼트를 찾으려 하는 것 — x86(32비트)에서는 `gs`가 TLS/TCB 세그먼트다.
- 카나리와 ASLR을 혼동하는 것 — 둘 다 `AT_RANDOM`처럼 커널 난수에 의존하지만, ASLR은 매핑 베이스 주소를 무작위화하는 것이고 카나리는 스택 오버플로우로 리턴 주소를 덮기 전에 감지하기 위한 값이다. 서로 독립적인 보호 기법이다.

## 막혔을 때 다음 체크
- auxv 전체 구조와 다른 `AT_*` 항목들이 궁금하다면 → REV-0677 ELF Auxiliary Vector 개요
- `fs:0x28`이 왜 TCB에 있는지, TLS 세그먼트 구조 자체가 궁금하다면 → REV-0680 Thread Local Storage가 ELF에서 구현되는 방식
- 카나리를 포함한 다른 보호 기법(NX, PIE, RELRO)까지 한 번에 정리하고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해
- `_start`부터 `main`까지 초기화 흐름 전체가 궁금하다면 → REV-0097 ELF Entry Point에서 main까지, REV-0099 __libc_start_main이 무엇이고 main을 찾는 법

## 미니 예제
```c
#include <stdio.h>
#include <string.h>

void vuln(void) {
    char buf[16];
    gets(buf);   // 카나리로 보호되는 취약한 함수
}

int main(void) {
    vuln();
    return 0;
}
```
```bash
$ gcc -fstack-protector-all -o demo demo.c
$ gdb ./demo
(gdb) disassemble vuln
...
   0x0000...11c9 <+0>:  push   rbp
   0x0000...11ca <+1>:  mov    rbp,rsp
   0x0000...11cd <+4>:  sub    rsp,0x20
   0x0000...11d1 <+8>:  mov    rax,QWORD PTR fs:0x28
   0x0000...11da <+17>: mov    QWORD PTR [rbp-0x8],rax
...
(gdb) info auxv
25   AT_RANDOM  Address of 16 random bytes  0x7fffffffdf29
(gdb) x/16bx 0x7fffffffdf29
0x7fffffffdf29: 0xf3 0x0a 0x2c ... (16바이트)
(gdb) x/gx $fs_base+0x28
0x7ffff7fbd728: 0x00e5b1a3f30a2cf3
```
`AT_RANDOM`이 가리키는 16바이트 중 앞 8바이트(`f3 0a 2c ... a3`를 리틀엔디언 정수로 읽은 값)에서 최상위 바이트만 `00`으로 바뀐 값이 그대로 카나리로 쓰이는 것을 볼 수 있다.

## 관련 글
- REV-0677 — ELF Auxiliary Vector(auxv) 개요
- REV-0680 — Thread Local Storage가 ELF에서 구현되는 방식(TLS 세그먼트)
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법

## 출처/검증
- `_dl_setup_stack_chk_guard`, `AT_RANDOM` 기반 카나리 생성 로직(최상위 바이트를 0으로 마스킹): glibc `sysdeps/generic/dl-osinfo.h` / `sysdeps/unix/sysv/linux/dl-osinfo.h` 소스 및 관련 논의(sourceware.org libc-alpha/libc-hacker 메일링 리스트, Jakub Jelinek의 stack protector 패치) 기준.
- `AT_RANDOM` auxv 타입 번호(25) 및 커널의 16바이트 난수 제공: Linux 커널 `fs/binfmt_elf.c`의 `create_elf_tables` 동작 및 `LD_SHOW_AUXV=1` 실측 기준.
- x86-64에서 TCB `stack_guard` 필드가 `fs:0x28`에 위치하는 것: glibc `tcbhead_t` 구조체(`sysdeps/x86_64/nptl/tls.h`) 및 `-fstack-protector` 컴파일 결과물 디스어셈블리 실측 기준 (2026-09-08 검증).
