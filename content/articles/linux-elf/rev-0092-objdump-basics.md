---
id: REV-0092
title: "objdump 기본 사용법"
slug: "rev-0092-objdump-basics"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["objdump", "binutils"]
keywords: ["objdump", "objdump -d", "objdump -D", "AT&T 문법", "Intel 문법", "디스어셈블", "objdump -T"]
aliases: ["objdump 사용법", "objdump 옵션", "objdump 명령어", "objdump 치트시트", "objdump intel 문법"]
symptom_keywords: ["objdump 결과 att 문법이 낯설음", "objdump 옵션이 뭐가 있는지 모름", "objdump로 특정 함수만 보고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`objdump`는 ELF 파일을 디스어셈블(기계어 → 어셈블리 변환)하고, 심볼·재배치·헤더 정보를 함께 볼 수 있는 GNU binutils의 범용 바이너리 분석 도구로, IDA/Ghidra가 없는 환경에서 코드를 직접 읽어야 할 때 가장 먼저 손이 가는 명령어다.

## 언제 검색해야 하나
- 서버/CTF 환경에 IDA/Ghidra가 없어서 커맨드라인으로 디스어셈블리를 봐야 할 때
- 특정 함수 하나(`main`, `printf@plt` 등)의 어셈블리만 빠르게 확인하고 싶을 때
- `objdump` 결과가 기본적으로 AT&T 문법이라 IDA(Intel 문법)에 익숙한 사람이 헷갈릴 때
- import된 라이브러리 함수 목록을 스크립트로 뽑고 싶을 때

## 핵심 개념
`objdump`는 오브젝트 파일 포맷 전반(ELF, PE, Mach-O 등)을 다룰 수 있는 범용 도구다. 핵심 기능은 크게 세 가지다: (1) 디스어셈블(`-d`), (2) 헤더/심볼 정보 출력(`-f`, `-h`, `-t`, `-T`), (3) 특정 섹션의 raw 콘텐츠 덤프(`-s`). `readelf`가 ELF 구조체를 그대로 보여주는 데 집중한다면, `objdump`는 기계어 바이트를 실제 어셈블리 명령어로 변환해서 보여주는 데 특화되어 있다.

**AT&T 문법이 기본값**이라는 점이 IDA 사용자에게 가장 큰 함정이다. 기본 `objdump -d` 출력은 `mov %rax, %rbx`처럼 `%`레지스터 접두사, 소스→목적지 순서(IDA/Intel과 반대), 즉시값에 `$` 접두사를 쓴다. `-M intel` 옵션으로 IDA와 동일한 Intel 문법으로 바꿀 수 있다.

## 화면/코드에서 보이는 징후
IDA 없이 서버에 SSH로 접속해 바이너리만 있을 때, 또는 스크립트에서 특정 함수의 바이트 패턴을 자동으로 뽑아야 할 때 objdump가 등장한다.

## 가장 먼저 할 것
```bash
objdump -d -M intel ./chall | less
```
습관적으로 `-M intel`을 붙인다. IDA 출력과 형태가 비슷해져서 눈에 익은 문법으로 바로 읽을 수 있다.

## 단계별 절차 / 옵션 정리

### `-d` : 실행 가능한 섹션만 디스어셈블
```bash
objdump -d -M intel ./chall
```
출력 예:
```
0000000000001149 <main>:
    1149:	f3 0f 1e fa          	endbr64
    114d:	55                   	push   rbp
    114e:	48 89 e5             	mov    rbp,rsp
    1151:	48 83 ec 10          	sub    rsp,0x10
    1155:	bf 04 20 00 00       	mov    edi,0x2004
    115a:	e8 d1 fe ff ff       	call   1030 <puts@plt>
    115f:	b8 00 00 00 00       	mov    eax,0x0
    1164:	c9                   	leave
    1165:	c3                   	ret
```
왼쪽부터 주소, raw 기계어 바이트, 어셈블리 명령어(Intel 문법) 순서.

### `-D` : 모든 섹션 디스어셈블(비실행 섹션 포함)
```bash
objdump -D ./chall
```
`-d`는 실행 가능한(`X` 플래그) 섹션만 보여주고, `-D`는 데이터 섹션도 억지로 명령어처럼 디스어셈블해서 보여준다(데이터를 코드처럼 잘못 해석할 수 있으니 주의).

### 특정 함수만 보기
```bash
objdump -d -M intel ./chall --disassemble=main
```
또는 grep으로 필터:
```bash
objdump -d -M intel ./chall | grep -A20 '<main>:'
```

### `-T` : 동적 심볼 테이블(임포트 함수 목록)
```bash
objdump -T ./chall
```
출력 예:
```
0000000000000000      DF *UND*  0000000000000000  GLIBC_2.2.5 printf
0000000000000000      DF *UND*  0000000000000000  GLIBC_2.2.5 puts
0000000000004018 g    DO .bss   0000000000000004  GLIBC_2.2.5 stdout
```
`*UND*`는 이 바이너리 안에 정의되어 있지 않고 외부(libc 등)에서 가져와야 하는 심볼이라는 뜻 — 즉 이 프로그램이 어떤 라이브러리 함수를 쓰는지 한눈에 보인다.

### `-t` : 심볼 테이블(strip 안 됐을 때)
```bash
objdump -t ./chall
```

### `-f` : 파일 요약 헤더
```bash
objdump -f ./chall
```
출력 예:
```
architecture: i386:x86-64, flags 0x00000150:
HAS_SYMS, DYNAMIC, D_PAGED
start address 0x0000000000001060
```

### `-h` : 섹션 헤더 요약
```bash
objdump -h ./chall
```

### `-s -j <섹션>` : 특정 섹션 raw hex 덤프
```bash
objdump -s -j .rodata ./chall
```

### PLT 스텁만 필터링해서 보기
```bash
objdump -d -M intel ./chall | grep '@plt'
```
어떤 라이브러리 함수들이 이 바이너리에서 실제로 CALL되는지 빠르게 확인(REV-0100 참고).

## 명령어/단축키
자주 쓰는 조합만 빠르게 정리:
```bash
objdump -d -M intel ./chall           # 실행 섹션 디스어셈블 (Intel 문법)
objdump -d -M intel ./chall | grep -A20 '<main>:'   # main 함수만 잘라 보기
objdump -T ./chall                    # 동적 심볼 테이블
objdump -R ./chall                    # 재배치 정보 (GOT 엔트리 등)
objdump -s -j .rodata ./chall         # .rodata 섹션 원시 바이트 덤프
objdump -d -M intel ./chall | grep '@plt'   # PLT 스텁만 필터링
```

## 출력 해석
- 왼쪽 열 주소는 파일 오프셋이 아니라 **가상 주소**(ELF 헤더 REV-0089 참고)다. PIE 바이너리라면 이 주소에 실제 ASLR 베이스가 더해져야 런타임 주소가 된다.
- 중간의 raw 바이트 열(`f3 0f 1e fa` 등)은 그 명령어의 실제 기계어 인코딩 — 패치나 시그니처 작성 시 이 바이트를 직접 참고한다.
- `<main>:`처럼 꺾쇠괄호 안 이름은 심볼 테이블에서 가져온 것 — strip된 바이너리라면 이런 이름 대신 그냥 주소만 나온다.

## 흔한 실수
- 기본 출력이 AT&T 문법인 걸 모르고 "objdump가 이상하게 나온다"고 오해하는 것 — `-M intel`을 빼먹은 것뿐이다. AT&T는 `mov %rax, %rbx`(src, dst), Intel은 `mov rbx, rax`(dst, src)로 피연산자 순서 자체가 반대다.
- `-d`로 아무것도 안 나오는데 파일이 잘못됐다고 생각하는 것 — 정적 링킹이 아닌 순수 데이터 파일이거나, 실행 가능한 섹션이 없는 경우일 수 있다. `-h`로 섹션 플래그부터 확인한다.
- `-D`(전체 디스어셈블)로 데이터 섹션까지 억지로 명령어로 해석해서 나온 이상한 코드를 실제 실행되는 코드라고 착각하는 것 — `-d`가 실행 섹션만 보여주므로 더 안전하다.

## 막혔을 때 다음 체크
- ELF 구조 자체가 궁금하면 → [REV-0089 ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- 심볼 조회만 빠르게 하고 싶으면 → [REV-0093 nm으로 심볼 찾기](./rev-0093-nm-basics.md)
- PLT/GOT 스텁 코드 해석이 궁금하면 → [REV-0100 PLT와 GOT 기초](./rev-0100-plt-got.md)
- `_start`부터 코드를 읽고 싶으면 → [REV-0098 _start 함수 읽는 법](./rev-0098-start-function.md)

## 미니 예제
```bash
$ objdump -d -M intel chall | grep -A9 '<main>:'
0000000000001149 <main>:
    1149:	f3 0f 1e fa          	endbr64
    114d:	55                   	push   rbp
    114e:	48 89 e5             	mov    rbp,rsp
    1151:	48 83 ec 10          	sub    rsp,0x10
    1155:	bf 04 20 00 00       	mov    edi,0x2004
    115a:	e8 d1 fe ff ff       	call   1030 <puts@plt>
    115f:	b8 00 00 00 00       	mov    eax,0x0
    1164:	c9                   	leave
    1165:	c3                   	ret
```
`main`이 `puts@plt`를 한 번 호출하고 `0`을 반환하는 아주 단순한 "Hello World" 패턴임을 IDA 없이도 바로 읽을 수 있다.

## 관련 글
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0093 — nm으로 심볼 찾기](./rev-0093-nm-basics.md)
- [REV-0098 — _start 함수 읽는 법](./rev-0098-start-function.md)
- [REV-0100 — PLT와 GOT 기초](./rev-0100-plt-got.md)

## 출처/검증
- 옵션 목록/출력 형식: GNU binutils `objdump(1)` man page 기준 (2026-09-08 검증).
- AT&T vs Intel 문법 차이: GNU `as`(GAS) 문서 "AT&T Syntax versus Intel Syntax" 섹션 기준.
