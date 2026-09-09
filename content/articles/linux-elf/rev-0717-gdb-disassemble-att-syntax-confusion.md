---
id: REV-0717
title: "GDB에서 disassemble 결과가 AT&T 문법이라 헷갈릴 때"
slug: "rev-0717-gdb-disassemble-att-syntax-confusion"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["AT&T syntax", "Intel syntax", "disassembly-flavor", "GDB 문법 변경", "objdump -M intel"]
aliases: ["gdb intel 문법으로 바꾸기", "AT&T 문법 읽는법", "gdb disassembly-flavor intel", "mov 순서 반대"]
symptom_keywords: ["gdb mov 순서가 이상함", "% 기호가 붙어서 헷갈림", "objdump 결과가 IDA랑 다름", "call 0x1234 <printf> 문법이 낯설음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB의 기본 역어셈블 출력이 IDA/Ghidra/x64dbg에서 흔히 보던 Intel 문법과 다른 **AT&T 문법**(`mov %rsp,%rbp`, `call 0x404e10 <printf>`)이라 헷갈리는 것이며, `.gdbinit`에 `set disassembly-flavor intel` 한 줄만 추가하면 이후 모든 세션에서 익숙한 Intel 문법(`mov rbp, rsp`)으로 영구히 바꿀 수 있다.

## 언제 검색해야 하나
- GDB `disassemble main`을 실행했더니 `mov %rsp,%rbp`처럼 레지스터 앞에 `%`가 붙고, IDA에서 봤던 순서와 피연산자가 반대로 나와서 당황스러울 때
- `sub $0x50,%rsp`, `lea 0x7d6cc(%rip),%rax` 같은 표기가 낯설어서 코드를 잘못 해석할 위험을 느낄 때
- Pwndbg를 설치했는데도 여전히 AT&T로 나오거나, 반대로 Pwndbg는 Intel인데 순정 GDB만 AT&T라서 둘을 오갈 때 헷갈릴 때

## 핵심 개념

### AT&T 문법과 Intel 문법의 핵심 차이 3가지
1. **피연산자 순서**: AT&T는 `연산 소스, 목적지`(source, destination) 순서, Intel은 `연산 목적지, 소스`(destination, source) 순서다. 예를 들어 "RAX에 RBX를 더한다"는 의미가 AT&T로는 `add %rbx, %rax`, Intel로는 `add rax, rbx`로 정반대 순서로 쓰인다.
2. **레지스터 표기**: AT&T는 레지스터 앞에 `%`를 붙인다(`%rax`, `%rdi`). Intel은 그냥 `rax`, `rdi`로 쓴다.
3. **즉시값(immediate) 표기**: AT&T는 상수 앞에 `$`를 붙인다(`$0x50`, `$0x1`). Intel은 그냥 `0x50`으로 쓴다.

### 메모리 참조 표기 차이
AT&T의 메모리 피연산자는 `disp(base, index, scale)` 형태로 쓴다. 예: `-0x8(%rbp)`는 "RBP - 8" 주소를 뜻하고, `0x8(%rax,%rcx,4)`는 "RAX + RCX*4 + 8" 주소를 뜻한다. Intel 문법에서는 이를 대괄호로 묶어 `[rbp-0x8]`, `[rax+rcx*4+0x8]`처럼 표기한다. IDA/Ghidra/x64dbg에 익숙한 사람이 GDB의 AT&T 출력을 처음 보면 대괄호가 없고 괄호 앞에 오프셋이 붙는 순서라 특히 헷갈려한다.

### 왜 GDB 기본값이 AT&T인가
`objdump`, `as`(GNU 어셈블러), `gdb` 모두 유닉스/GNU 툴체인 전통을 따라 기본 문법이 AT&T다. 반면 IDA, Ghidra, x64dbg, Visual Studio 등 윈도우/상용 툴 계열은 관례적으로 Intel 문법을 기본으로 쓴다. 리눅스 바이너리를 분석할 때 GDB/objdump는 AT&T, IDA/Ghidra는 Intel을 쓰는 상황이 흔해서 같은 코드를 두 표기법으로 번갈아 봐야 하는 경우가 자주 생긴다.

## 화면/코드에서 보이는 징후
```
(gdb) disassemble main
   0x0000000000401148 <+8>:    sub    $0x50,%rsp
   0x000000000040114c <+12>:   mov    %fs:0x28,%rax
   0x0000000000401157 <+27>:   lea    0x7d6cc(%rip),%rax        # 0x47f01b
   0x000000000040115e <+34>:   mov    %rax,%rdi
   0x0000000000401163 <+39>:   call   0x404e10 <printf>
```
이 출력을 IDA 스타일(Intel)로 옮기면 다음과 같다:
```
sub  rsp, 0x50
mov  rax, fs:0x28
lea  rax, [rip+0x7d6cc]
mov  rdi, rax
call printf
```
`mov %rax,%rdi`(AT&T, "RAX를 RDI로 복사")와 `mov rdi, rax`(Intel, 동일한 의미)가 겉보기엔 피연산자 순서가 정반대라 그대로 착각하고 읽으면 "RDI를 RAX로 복사한다"고 거꾸로 해석하는 실수가 나온다.

## 가장 먼저 할 것
`.gdbinit` 파일에 한 줄만 추가해서 아예 Intel 문법을 기본값으로 만든다:
```bash
echo "set disassembly-flavor intel" >> ~/.gdbinit
```
이후 새로 여는 모든 GDB 세션에서 `disassemble`, `x/i`, TUI 어셈블리 창이 전부 Intel 문법으로 출력된다.

## 단계별 절차

**1) 현재 세션에서 즉시 바꿔보기**
```
(gdb) set disassembly-flavor intel
(gdb) disassemble main
```
바로 이번 세션부터 Intel 문법으로 바뀐 것을 확인한다.

**2) 현재 설정값 확인**
```
(gdb) show disassembly-flavor
```
`The disassembly flavor is "intel".`처럼 현재 값이 출력된다. 기본값은 `"att"`다.

**3) 영구 설정으로 저장**
매번 손으로 치기 귀찮으므로 홈 디렉터리의 `~/.gdbinit`(없으면 새로 생성)에 추가한다:
```bash
echo "set disassembly-flavor intel" >> ~/.gdbinit
```
Pwndbg를 쓴다면 Pwndbg 자체 설정 파일(`~/.gdbinit.d/` 또는 Pwndbg가 관리하는 `.gdbinit`)에 같은 줄을 넣거나, Pwndbg 안에서 `set context-code-lines`처럼 Pwndbg 전용 옵션과 별개로 이 GDB 표준 옵션이 그대로 적용되는지 확인한다. Pwndbg는 최근 버전에서 기본적으로 Intel 스타일 컨텍스트를 보여주는 경우가 많지만, 순정 `disassemble` 명령 결과는 이 옵션을 따로 설정해야 하는 경우가 있다.

**4) objdump도 같이 맞추기**
GDB 밖에서 `objdump`로 훑어볼 때도 문법을 맞춰야 착각이 안 생긴다:
```bash
objdump -d -M intel ./chall | less
```
`-M intel` 옵션이 objdump의 Intel 문법 스위치다.

**5) 두 문법을 오가며 읽는 연습**
분석 자료(예: 블로그 라이트업, man page, CTF writeup)가 AT&T로 되어 있는 경우도 많으므로, 위 3가지 차이(피연산자 순서, `%`/`$` 접두사, 메모리 표기)만 기억해두면 문법을 몰라도 필요할 때 즉석에서 변환해서 읽을 수 있다.

## 명령어/단축키
```
(gdb) set disassembly-flavor intel
(gdb) show disassembly-flavor
(gdb) disassemble main
(gdb) disassemble /s main
```
```bash
echo "set disassembly-flavor intel" >> ~/.gdbinit
objdump -d -M intel ./chall
objdump -d ./chall              # 기본 AT&T
```

## 출력 해석
AT&T:
```
mov    -0x8(%rbp),%rax
add    $0x1,%rax
mov    %rax,-0x8(%rbp)
```
Intel(`set disassembly-flavor intel` 적용 후 동일 코드):
```
mov    rax, QWORD PTR [rbp-0x8]
add    rax, 0x1
mov    QWORD PTR [rbp-0x8], rax
```
두 출력은 완전히 동일한 코드를 의미한다: "RBP-8 위치의 8바이트 값을 RAX로 읽고, RAX에 1을 더한 뒤, 다시 RBP-8 위치에 저장한다"는 지역 변수 증가 패턴(`local_var++`에 해당)이다. Intel 쪽에 붙는 `QWORD PTR`는 메모리 접근 크기(8바이트)를 명시한 것으로, AT&T는 이런 크기를 보통 명령어 접미사(`movq`, `movl` 등)로 표시하며 GDB 출력에서는 종종 생략되기도 한다.

## 흔한 실수
- `mov %rax,%rdi`를 Intel 읽는 습관 그대로 "RDI를 RAX로 복사"라고 거꾸로 해석하는 것 — AT&T는 소스가 왼쪽, 목적지가 오른쪽이다.
- 문법을 Intel로 바꿔놓고도 예전 AT&T 캡처 화면이나 man page 예제를 그대로 최신 화면과 비교해서 헷갈리는 것 — 어느 문법으로 보고 있는지 항상 `show disassembly-flavor`로 재확인하는 습관을 들인다.
- `~/.gdbinit`에 설정을 추가했는데도 안 바뀐다며 재부팅부터 하는 것 — 대부분은 오타이거나, Pwndbg/PEDA 같은 플러그인이 `.gdbinit`을 덮어써서 그 뒤에 자기 설정을 넣어야 하는 순서 문제다. `~/.gdbinit` 맨 마지막 줄에 추가했는지 확인한다.
- 크기 접미사(AT&T의 `movq`/`movl`/`movb`)를 무시하고 항상 8바이트라고 착각하는 것 — 접미사는 각각 quad(8바이트)/long(4바이트)/byte(1바이트)를 의미하므로 실제 이동되는 데이터 크기를 결정한다.

## 막혔을 때 다음 체크
- GDB 명령어 전반을 한 번에 정리해서 보고 싶다면 → REV-0284 GDB 명령어 치트시트
- 정적 링킹된 stripped 바이너리라 이름조차 안 보이는 상황이라면 → REV-0716 statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때
- `disassemble` 자체 명령 사용법이 더 궁금하다면 → REV-0190 GDB disassemble와 현재 RIP 주변 보기
- SysV x64 호출 규약에서 레지스터가 인자로 어떻게 쓰이는지 먼저 정리하고 싶다면 → REV-0106 SysV AMD64 Calling Convention

## 미니 예제
```bash
$ cat ~/.gdbinit
set disassembly-flavor intel
$ gdb -q ./chall
(gdb) disassemble main
Dump of assembler code for function main:
   0x0000000000401148 <+8>:    sub    rsp, 0x50
   0x000000000040114c <+12>:   mov    rax, QWORD PTR fs:0x28
   0x0000000000401163 <+39>:   call   0x404e10 <printf>
End of assembler dump.
```
설정 한 줄로 이후 모든 세션에서 IDA/Ghidra와 동일한 문법으로 코드를 읽을 수 있게 되어, "이 코드는 IDA에서 본 것과 순서가 다른데 버그인가?"라는 불필요한 의심을 없앨 수 있다.

## 관련 글
- REV-0190 — GDB disassemble와 현재 RIP 주변 보기
- REV-0284 — GDB 명령어 치트시트
- REV-0106 — SysV AMD64 Calling Convention
- REV-0716 — statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때

## 출처/검증
- `set disassembly-flavor`, `show disassembly-flavor` 명령 동작: 본 환경 GDB 15.1에서 `help set disassembly-flavor` 및 실제 `disassemble` 출력 전/후 비교로 실측 검증 (2026-09-08).
- `objdump -M intel` 옵션: `objdump(1)` man page 기준.
- AT&T/Intel 문법 차이(피연산자 순서, 접두사, 메모리 표기): GNU 어셈블러(`as`) 매뉴얼의 "i386-Variations" 문법 설명 기준.
