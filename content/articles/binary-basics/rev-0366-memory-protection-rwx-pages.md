---
id: REV-0366
title: "메모리 보호 비트(RWX)와 페이지 개념 기초"
slug: "rev-0366-memory-protection-rwx-pages"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, Pwndbg, IDA]
keywords: ["메모리 보호", "memory protection", "RWX", "read write execute", "페이지", "page", "NX bit", "DEP", "mprotect", "VirtualProtect"]
aliases: ["rwx가 뭐임", "페이지가 뭔지 모르겠음", "실행 권한이 뭔지", "왜 데이터영역에서 실행하면 크래시남", "NX가 뭐임"]
symptom_keywords: ["셸코드를 스택에 넣었는데 실행이 안됨", "vmmap에서 권한 표시가 rwx로 안보임", "왜 특정 메모리 접근에서 크래시남", "checksec에서 NX enabled라고 나옴", "mprotect나 VirtualProtect 호출이 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
운영체제는 메모리를 고정 크기 블록인 "페이지"(보통 4KB) 단위로 관리하며, 각 페이지마다 읽기(Read)/쓰기(Write)/실행(Execute) 권한을 개별적으로 지정할 수 있어서, 코드 영역은 보통 실행 가능하지만 쓰기는 불가능하고, 데이터/스택/힙 영역은 쓰기는 가능하지만 실행은 불가능하게(NX, No-eXecute) 막아놓는 것이 현대 시스템의 기본 방어 방식이다.

## 언제 검색해야 하나
- GDB/Pwndbg의 `vmmap`이나 x64dbg의 Memory Map에서 각 메모리 영역 옆에 `r-x`, `rw-`, `r--` 같은 세 글자 권한 표시가 나오는데 무슨 뜻인지 모를 때
- 스택이나 힙에 셸코드를 직접 써넣고 실행하려 했는데 세그폴트가 날 때 ("스택은 실행 안 되는 거 아니었나?"가 궁금할 때)
- `checksec` 결과에 `NX enabled` / `NX disabled`가 나오는데 이게 실제로 뭘 의미하는지 모를 때
- 코드에서 `mprotect()`(Linux) 또는 `VirtualProtect()`(Windows) 호출이 보이는데 왜 굳이 메모리 권한을 바꾸는지 궁금할 때
- 패커/언패킹된 바이너리 분석 중 압축 해제한 코드를 실행하기 직전에 메모리 권한을 바꾸는 코드가 보일 때

## 핵심 개념

### 페이지란 무엇인가
운영체제는 프로세스에게 메모리를 1바이트씩 개별 관리해주지 않는다. 대신 **페이지(page)**라는 고정 크기 블록(x86/x64에서 표준은 4096바이트 = 4KB) 단위로 묶어서 관리한다. 프로세스가 사용하는 모든 가상 메모리 주소는 어떤 페이지에 속해 있고, 그 페이지 전체가 하나의 속성 세트(권한, 매핑된 실제 물리 메모리 위치 등)를 공유한다. 즉 한 페이지 안의 일부 바이트만 실행 가능하고 나머지는 실행 불가능하게 만드는 것은 불가능하다 — 권한은 항상 페이지 전체 단위로 적용된다.

### R/W/X 세 가지 권한
각 페이지는 세 가지 독립적인 권한 비트를 가진다.
- **R(Read, 읽기)**: 이 페이지의 데이터를 읽을 수 있다.
- **W(Write, 쓰기)**: 이 페이지에 값을 쓸 수 있다.
- **X(Execute, 실행)**: 이 페이지에 있는 바이트를 CPU가 명령어로 해석해 실행할 수 있다.

이 세 비트의 조합으로 흔히 보는 표시가 만들어진다.
- `r-x`: 읽기+실행 가능, 쓰기 불가 — 전형적인 **코드 영역(.text)**. 실행은 되지만 프로그램 스스로 자기 코드를 덮어쓸 수는 없다.
- `rw-`: 읽기+쓰기 가능, 실행 불가 — 전형적인 **데이터 영역(.data, .bss), 힙, 스택**. 값은 자유롭게 바꿀 수 있지만 여기 있는 바이트를 코드로 실행하려 하면 막힌다.
- `r--`: 읽기만 가능 — 상수 데이터 영역(`.rodata`) 등.
- `rwx`: 세 권한이 모두 열려있는 경우 — 정상적인 프로그램에서는 드물고, 만약 있다면 보안상 취약한 신호로 취급된다(코드 인젝션/셸코드 실행 공격에 취약).

### 왜 데이터 영역은 실행이 막혀 있는가 — NX/DEP
과거(1990년대~2000년대 초)에는 스택, 힙 같은 데이터 영역도 실행 권한이 열려 있는 경우가 흔했다. 공격자들은 이 점을 악용해 버퍼 오버플로로 스택에 셸코드를 써넣고 그 스택 주소로 실행 흐름을 돌리는 공격을 즐겨 썼다. 이를 막기 위해 CPU와 OS는 **NX bit(No-eXecute bit, AMD 명칭)** 또는 **XD bit(eXecute Disable, Intel 명칭)**라는 하드웨어 기능을 페이지 테이블에 추가했고, OS는 이를 활용해 데이터 영역 페이지에는 실행 권한을 아예 부여하지 않는 정책을 기본값으로 만들었다. 이 방어 기법을 Windows에서는 **DEP(Data Execution Prevention)**, Linux/리버싱 커뮤니티에서는 그냥 **NX**라고 부른다. CTF pwn 문제에서 `checksec` 결과의 `NX enabled`가 바로 이 보호가 켜져 있다는 뜻이며, 켜져 있으면 스택/힙에 셸코드를 넣어도 곧바로 실행할 수 없어 ROP(Return-Oriented Programming) 같은 우회 기법이 필요해진다.

### 코드 영역이 쓰기 금지인 이유
반대로 `.text`(코드) 영역은 보통 `r-x`로, 쓰기가 막혀 있다. 이는 실행 중인 프로그램이 (버그나 공격으로) 자기 자신의 코드를 실수로 덮어쓰는 것을 막고, 여러 프로세스가 같은 실행 파일을 실행할 때 코드 페이지를 안전하게 공유(REV-0029, REV-0030 참고)할 수 있게 해준다. 코드를 실행 중에 바꾸고 싶다면(JIT 컴파일러, 자체 복호화 패커 등) 권한을 명시적으로 바꾸는 절차가 필요하다.

### 권한을 런타임에 바꾸는 API
프로그램이 스스로 메모리 권한을 바꿔야 하는 경우(대표적으로 JIT 엔진, 실행 파일 압축(패킹) 도구가 압축 해제 후 코드를 실행하는 경우)를 위해 OS는 전용 API를 제공한다.
- Linux: `mprotect(addr, len, PROT_READ|PROT_WRITE|PROT_EXEC)`
- Windows: `VirtualProtect(lpAddress, dwSize, flNewProtect, lpflOldProtect)`

리버싱 중에 이런 함수 호출이 보이면, "이 코드는 곧 어떤 메모리 영역을 실행 가능하게 바꾸고 그 위치로 점프하려는 것"이라고 의심해야 한다. UPX 같은 실행 파일 압축 도구로 패킹된 바이너리를 언패킹할 때(REV-0037 관련), 압축 해제 루프가 끝난 직후 이런 권한 변경 API 호출이나 직접적인 페이지 테이블 조작이 나오는 것이 전형적인 패턴이다.

## 화면/코드에서 보이는 징후
- GDB/Pwndbg `vmmap` 출력에 각 메모리 영역마다 `r-x`, `rw-`, `r--` 표시
- x64dbg Memory Map 탭의 Protection 열에 `PAGE_EXECUTE_READ`, `PAGE_READWRITE`, `PAGE_EXECUTE_READWRITE` 같은 Windows 상수 표시
- `checksec` 출력의 `NX enabled` / `NX disabled` 항목
- 디스어셈블리에 `mprotect`, `VirtualProtect`, `VirtualAlloc(..., PAGE_EXECUTE_READWRITE)` 호출이 보이고 직후 그 메모리로 점프하는 코드

## 가장 먼저 할 것
셸코드/직접 작성한 페이로드가 특정 메모리 영역에서 실행되지 않는다면, 가장 먼저 GDB의 `vmmap`(Pwndbg) 또는 x64dbg의 Memory Map으로 그 주소가 속한 페이지의 권한을 확인한다. 실행(`x`) 비트가 없다면 그 자체가 원인이다.

## 단계별 절차
1. GDB+Pwndbg: `vmmap` 실행 후, 문제가 되는 주소가 어느 행에 속하는지 확인한다.
2. 해당 행의 권한 컬럼(`r-x`, `rw-` 등)을 확인해 실행(`x`) 권한이 있는지 본다.
3. 없다면, `checksec`으로 바이너리 전체의 NX 설정을 확인한다(NX enabled면 스택/힙 실행이 기본 차단됨).
4. NX가 켜져 있고 셸코드를 그 위치에서 바로 실행해야 하는 상황이라면, `mprotect`를 호출해 권한을 바꾸는 ROP 체인(ret2mprotect 계열 기법)이 필요한지 검토한다.
5. 바이너리 자체 코드에서 `mprotect`/`VirtualProtect` 호출이 보이면, 그 호출의 인자(대상 주소, 크기, 새 권한 플래그)를 먼저 확인해 어떤 영역을 어떤 권한으로 바꾸려는지 파악한다.

## 명령어/단축키
```
(gdb) vmmap                 # Pwndbg: 전체 메모리 맵과 권한 표시
(gdb) vmmap 0x555555558000  # 특정 주소가 속한 페이지만 확인
$ checksec --file=./chall   # NX, PIE, Canary 등 보호 기법 확인
```
Windows: `VirtualProtect` 원형
```c
BOOL VirtualProtect(
  LPVOID lpAddress, SIZE_T dwSize,
  DWORD  flNewProtect, PDWORD lpflOldProtect
);
```
Linux: `mprotect` 원형
```c
int mprotect(void *addr, size_t len, int prot);
// prot: PROT_NONE, PROT_READ, PROT_WRITE, PROT_EXEC (OR 조합)
```

## 출력 해석
- `vmmap`에서 스택 영역(`[stack]`)이 `rw-`로만 보인다면 NX가 정상적으로 켜져 있는 것 — 스택에 셸코드를 넣어도 직접 실행은 막힌다.
- 어떤 힙 페이지가 예외적으로 `rwx`로 보인다면, 프로그램이 명시적으로 `mprotect`/`VirtualProtect`를 호출해 실행 권한을 열어둔 상태라는 뜻이며, 그 위치가 코드 인젝션의 목표 지점일 가능성이 있다.
- `checksec`에서 `NX disabled`가 나온다면 매우 오래되었거나 의도적으로 보호를 끈 실습용 바이너리일 가능성이 높다 — 이 경우 스택 셸코드 실행이 그대로 통한다.

## 흔한 실수
- "실행 파일이니까 모든 메모리가 실행 가능하다"고 착각하는 것 — 실행 권한은 코드가 실제로 위치한 페이지에만 부여되고, 나머지(데이터/스택/힙)는 기본적으로 실행이 막혀 있다.
- 페이지 권한이 바이트 단위로 세밀하게 적용된다고 오해하는 것 — 권한은 항상 페이지(보통 4KB) 전체 단위로만 적용된다.
- NX가 켜져 있다고 해서 셸코드 실행이 "완전히 불가능"하다고 단정하는 것 — ROP나 `mprotect`/`VirtualProtect` 호출을 우회 경로로 이용해 결국 실행 가능한 페이지를 만들어낼 수 있다.
- `rwx` 표시를 보고 무조건 "이건 악성/공격 코드"라고 단정하는 것 — JIT 컴파일러, 일부 정상적인 언패킹 루틴도 합법적으로 `rwx` 페이지를 잠깐 사용할 수 있다.

## 막혔을 때 다음 체크
- 코드/데이터가 프로세스 메모리에서 어떤 영역(Section/Segment)으로 나뉘어 배치되는지 전체 그림이 필요하면 → REV-0029 메모리 Section과 Segment 차이, REV-0030 Code Data BSS Stack Heap 기초
- 패킹된 바이너리가 압축 해제 후 실행 권한을 바꾸는 패턴을 더 깊이 보고 싶으면 → 패킹/언패킹 관련 항목(안티디버깅/패킹 카테고리) 참고
- 스택에 셸코드를 못 넣는 상황에서 다음 단계(ROP)로 넘어가야 한다면 → 스택 프레임(REV-0031)과 반환 주소 구조부터 다시 확인
- NX/DEP, ASLR, 스택 카나리 등 보호 기법 전반을 한 번에 정리하고 싶다면 `checksec` 각 항목별 관련 글을 참고

## 미니 예제
Pwndbg에서 실제로 확인할 수 있는 `vmmap` 출력 예시(단순화):
```
$ gdb ./chall
(gdb) vmmap
LEGEND: STACK | HEAP | CODE | DATA | RWX | RODATA
0x555555554000  0x555555555000  r--p   /path/chall     ; RODATA/헤더
0x555555555000  0x555555556000  r-xp   /path/chall     ; .text, 실행 가능, 쓰기 불가
0x555555556000  0x555555557000  rw-p   /path/chall     ; .data/.bss
0x7ffff7dd0000  0x7ffff7ff0000  rw-p   [heap]           ; 힙, 실행 불가
0x7ffffffde000  0x7ffffffff000  rw-p   [stack]          ; 스택, 실행 불가
```
이 상태에서 스택에 셸코드를 넣고 그 주소로 반환 주소를 덮어써도, 스택 페이지가 `rw-`(실행 비트 없음)이므로 `#GP` 예외로 즉시 크래시난다. 이것이 바로 NX/DEP가 정상 동작하는 모습이다.

## 관련 글
- REV-0029 — 메모리 Section과 Segment 차이
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0031 — 스택 프레임이 무엇인지
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유

## 출처/검증
- 페이지 단위 메모리 관리 및 R/W/X 보호 비트: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 3A, "Paging" 챕터 기준 (2026-09-09 검증).
- NX bit(AMD)/XD bit(Intel), Windows DEP: Microsoft 공식 문서(Data Execution Prevention) 및 AMD64 Architecture Programmer's Manual 기준.
- `mprotect`(POSIX), `VirtualProtect`(Win32 API): POSIX 표준 문서 및 Microsoft Win32 API 공식 문서 기준.
