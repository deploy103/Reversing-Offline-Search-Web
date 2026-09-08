---
id: REV-0190
title: "GDB disassemble와 현재 RIP 주변 보기"
slug: "rev-0190-gdb-disassemble"
category: "dynamic-analysis"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb disassemble", "gdb disas", "disas $rip", "gdb 디스어셈블", "gdb intel syntax", "x/i $rip"]
aliases: ["gdb 디스어셈블 명령어", "gdb disas 문법", "gdb 현재 명령어 확인", "gdb att intel 문법 변경"]
symptom_keywords: ["gdb 디스어셈블 문법 모름", "gdb에서 att 문법으로 나옴", "gdb disas 범위 지정법", "gdb rip 주변 코드 보고싶음", "gdb 함수 전체 디스어셈블"]
source_ids: ["SRC-GDB-DOCS", "SRC-PWNDBG-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`disassemble`(줄여서 `disas`)은 함수 전체나 지정한 주소 범위를 어셈블리 명령어 목록으로 보여주는 GDB 명령으로, `disas`만 치면 현재 `$rip`가 속한 함수 전체를, `disas $rip,+20`처럼 쓰면 현재 위치부터 20바이트 범위만 보여주며, 화살표(`=>`)로 지금 실행 중인 명령어 위치를 항상 표시해준다.

## 언제 검색해야 하나
- 지금 멈춰있는 함수 전체의 어셈블리 코드를 한눈에 보고 싶을 때
- 함수 전체를 다 보기엔 너무 길어서, 현재 위치 주변 몇십 바이트만 짧게 보고 싶을 때
- GDB가 보여주는 어셈블리 문법이 IDA/objdump와 다르게 생겨서(AT&T 문법) 혼란스러울 때
- `disas`로 본 코드에서 지금 실행 중인 명령어가 어디인지 못 찾겠을 때
- 함수 이름 없이 특정 주소 범위만 디스어셈블하고 싶을 때

## 핵심 개념

### 인자 없는 `disassemble` — 현재 함수 전체
그냥 `disas`를 치면 현재 `$rip`가 속한 함수 전체를 처음부터 끝까지 디스어셈블해서 보여준다. 함수가 아주 크지 않다면 가장 직관적인 방법이다.

### 함수 이름을 지정하기
```gdb
disas main
disas check_password
```
현재 멈춘 위치와 상관없이 원하는 함수를 지정해서 볼 수 있다. 실행 중이 아니어도(즉 `run`/`start` 전에도) 정적으로 디스어셈블이 가능하다 — 다만 이 경우 PIE 바이너리라면 표시되는 주소가 실제 런타임 주소가 아니라 링크 타임 기준 주소(대개 베이스 0으로 가정한 값)일 수 있다는 점을 기억해야 한다(REV-0194 참고).

### 범위를 직접 지정하기 — `START,END`와 `START,+LENGTH`
함수 전체가 너무 길 때는 범위를 좁혀서 볼 수 있다.
```gdb
disas 0x401234,0x401260      # 시작 주소부터 끝 주소까지
disas $rip,+20               # 현재 위치부터 20바이트만
disas $rip-10,$rip+10        # 현재 위치 앞뒤로
```
`+길이` 문법이 특히 실전에서 자주 쓰인다 — "지금부터 딱 몇 바이트만 빠르게 보고 싶다"는 상황에 정확히 맞는다.

### 지금 실행 중인 명령어 표시 — `=>` 화살표
`disassemble`은 함수 안에 `$rip`가 포함되어 있으면(즉 지금 그 함수 안에서 멈춰있으면) 그 줄 앞에 `=>` 화살표를 붙여서 표시해준다. 함수가 길어도 이 화살표만 찾으면 지금 어디에 있는지 바로 알 수 있다. `$rip`가 그 함수 안에 없다면(예: `disas main`을 다른 함수 안에서 멈춘 채 조회) 화살표 없이 그냥 코드만 보여준다.

### AT&T 문법 vs Intel 문법
GDB의 기본 어셈블리 출력은 **AT&T 문법**이다. 이는 IDA, Ghidra, objdump(기본 상태 기준)가 흔히 쓰는 **Intel 문법**과 표기 순서가 반대다.
- AT&T: `mov %rax, %rbx` — 오퍼랜드 순서가 "출발지, 목적지"
- Intel: `mov rbx, rax` — 오퍼랜드 순서가 "목적지, 출발지"

또한 AT&T는 레지스터에 `%`, 즉시값에 `$`를 붙이고 메모리 참조를 `-0x4(%rbp)`처럼 쓰는 반면, Intel은 `[rbp-0x4]`처럼 대괄호를 쓴다. IDA에 익숙한 사람이 GDB의 기본 출력을 보면 오퍼랜드 순서가 뒤바뀐 것처럼 느껴져 헷갈리기 쉽다. 다행히 GDB에서 손쉽게 전환할 수 있다.
```gdb
set disassembly-flavor intel
```
이 한 줄이면 이후 모든 `disas`, `x/i` 출력이 IDA와 동일한 Intel 문법(`mov rbx, rax`, `[rbp-0x4]`)으로 나온다. `~/.gdbinit`에 이 줄을 추가해두면 GDB를 켤 때마다 자동으로 적용된다. Pwndbg는 기본적으로 Intel 문법을 쓰도록 설정돼 있는 경우가 많다.

### 원본 바이트/소스 코드 함께 보기 — `/r`, `/s`, `/m`
`disassemble` 뒤에 슬래시 옵션을 붙이면 추가 정보를 함께 볼 수 있다.
```gdb
disas /r main     # 각 명령어의 raw 기계어 바이트도 함께 표시
disas /s main     # 소스 코드가 있다면 소스 줄과 섞어서 표시(최신 방식)
disas /m main     # 소스 줄 기준으로 정렬해서 표시(예전 방식, 최적화 코드에서 순서가 꼬일 수 있음)
```
`/r`은 패치할 바이트 오프셋을 확인하거나, 특정 명령어가 몇 바이트짜리인지 셀 때 유용하다. `/s`는 소스와 어셈블리를 대응시켜 이해할 때 좋다.

### `x/Ni $rip`와의 차이
REV-0189에서 다룬 `x/3i $rip`도 명령어를 디스어셈블해서 보여주지만, `disassemble`과의 차이는 다음과 같다.
- `x/Ni`: 정해진 개수만큼 명령어를 나열. 함수 경계 개념이 없다.
- `disassemble`: 기본적으로 함수 단위, 또는 명시한 주소 범위 단위로 보여주며, 현재 위치를 `=>`로 강조해준다.

빠르게 몇 줄만 보고 싶으면 `x/Ni $rip`, 함수 전체 흐름이나 정확한 범위를 보고 싶으면 `disassemble`을 쓰는 식으로 구분해서 쓰면 된다.

## 화면/코드에서 보이는 징후
- `disas`를 쳤는데 오퍼랜드 순서가 IDA와 반대로 보이는 것(AT&T 문법 기본값)
- `=>` 화살표가 붙은 줄이 지금 `$rip` 위치라는 것을 알고 있어야 브레이크포인트 이후 흐름을 따라가기 쉬움
- 함수가 너무 길어서 `disas`만 쳤을 때 화면이 넘쳐 위쪽 내용이 스크롤되어 사라짐(`disas $rip,+40`처럼 좁혀서 다시 볼 필요)

## 가장 먼저 할 것
GDB를 처음 쓴다면 가장 먼저 `set disassembly-flavor intel`부터 설정한다. IDA/Ghidra와 표기가 통일되어야 코드를 비교하며 분석하기가 훨씬 수월하다.

## 단계별 절차

**1) Intel 문법으로 전환(최초 1회, `.gdbinit`에 추가 권장)**
```gdb
set disassembly-flavor intel
```

**2) 현재 함수 전체 보기**
```gdb
disas
```

**3) 필요하면 특정 함수 지정**
```gdb
disas check_password
```

**4) 범위를 좁혀서 현재 위치 주변만 보기**
```gdb
disas $rip,+20
```

**5) 원본 바이트나 소스 줄까지 함께 보고 싶다면**
```gdb
disas /r $rip,+20
disas /s check_password
```

## 명령어/단축키
```gdb
set disassembly-flavor intel
disas
disas FUNC
disas START,END
disas $rip,+LEN
disas /r FUNC
disas /s FUNC
disas /m FUNC
```

## 출력 해석
```
Dump of assembler code for function check_password:
   0x0000555555555169 <+0>:	push   rbp
   0x000055555555516a <+1>:	mov    rbp,rsp
=> 0x000055555555516d <+4>:	sub    rsp,0x20
   0x0000555555555171 <+8>:	mov    QWORD PTR [rbp-0x18],rdi
   ...
End of assembler dump.
```
`<+0>`, `<+1>`, `<+4>`는 함수 시작으로부터의 바이트 오프셋이다. `=>`가 붙은 줄이 지금 실행하려는 명령어이며, 다음에 `stepi`를 치면 바로 이 명령어가 실행된다.

## 흔한 실수
- AT&T 문법인 줄 모르고 오퍼랜드 순서를 IDA처럼 읽어서 소스/목적지를 반대로 해석하는 것 — `set disassembly-flavor intel`로 미리 바꿔두면 이 문제 자체가 사라진다.
- `disas`로 함수 전체를 보다가 화면이 넘쳐서 `=>` 화살표를 놓치는 것 — 필요하면 `disas $rip,+30`처럼 범위를 좁혀서 다시 조회한다.
- 실행 전(정적 상태)에 PIE 바이너리를 `disas main`으로 봤을 때 나온 주소를 실제 런타임 주소로 착각하는 것(REV-0194 참고).
- `/m` 옵션이 최적화된 코드에서 소스 줄 순서와 실제 실행 순서가 다르게 보일 수 있다는 걸 모르고 흐름을 오해하는 것 — 최신 GDB에서는 `/s`가 더 정확하다.

## 막혔을 때 다음 체크
- 명령어를 한 개씩 실행하며 실제 흐름을 확인하고 싶다면 → REV-0187 GDB stepi nexti continue
- 특정 레지스터나 메모리 값과 대조해가며 보고 싶다면 → REV-0188 GDB info registers와 flags 확인, REV-0189 GDB x 명령으로 메모리 보기
- Pwndbg를 쓰면 `context` 한 번으로 디스어셈블+레지스터+스택을 자동으로 같이 보여준다 → REV-0193 Pwndbg context telescope vmmap

## 미니 예제
```gdb
(gdb) set disassembly-flavor intel
(gdb) disas $rip,+20
Dump of assembler code from 0x555555555185 to 0x555555555199:
=> 0x0000555555555185 <main+8>:	lea    rax,[rbp-0x50]
   0x0000555555555189 <main+12>:	mov    rdi,rax
   0x000055555555518c <main+15>:	call   0x555555555169 <check_password>
   0x0000555555555191 <main+20>:	test   eax,eax
   0x0000555555555193 <main+22>:	je     0x5555555551a5 <main+40>
End of assembler dump.
```
현재 위치(`=>`)부터 20바이트 범위만 짧게 확인하면서, 곧 `check_password`를 호출하고 그 리턴값을 `test`로 검사한 뒤 분기한다는 흐름을 한눈에 파악할 수 있다.

## 관련 글
- REV-0187 — GDB stepi nexti continue
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0193 — Pwndbg context telescope vmmap

## 출처/검증
- `disassemble` 명령 문법(`START,END`, `START,+LENGTH`, `/r`, `/s`, `/m` 옵션): GDB 공식 온라인 문서("Source and Machine Code") 기준.
- `set disassembly-flavor` 옵션과 AT&T/Intel 문법 차이: GDB 공식 문서 "Machine Code" 섹션 기준 (2026-09-08 검증).
