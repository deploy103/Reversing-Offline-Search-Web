---
id: REV-0667
title: "ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기"
slug: "rev-0667-debug-info-symbols-utilization"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf, objdump]
keywords: ["DWARF", ".debug_info", "디버그 심볼", "debug symbols", "objdump --dwarf", "소스 라인 정보"]
aliases: ["디버그 정보 있는 바이너리 분석", "DWARF 디버그 정보 읽기", ".debug_info 활용법", "readelf debug-dump"]
symptom_keywords: ["GDB에서 소스 코드 라인이 보임", "file 명령에 with debug_info 표시됨", "readelf -S에 .debug로 시작하는 섹션이 많음", "디버그 정보를 어떻게 써야 할지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`-g` 옵션으로 컴파일되고 `strip`되지 않은 ELF는 `.debug_info`, `.debug_line` 등 DWARF 디버그 섹션에 원본 소스 파일 이름, 변수 이름, 함수 이름과 정확한 줄 번호까지 남아있어서, 이런 바이너리를 만나면 GDB에서 소스 라인 단위로 바로 디버깅할 수 있는 사실상 "치트키" 상황이다.

## 언제 검색해야 하나
- `file ./chall` 결과에 `with debug_info, not stripped`라는 문구가 보일 때
- GDB로 `run`을 했더니 갑자기 어셈블리가 아니라 C 소스 코드 줄이 화면에 나와서 당황스러울 때
- `readelf -S ./chall` 결과에 `.debug_info`, `.debug_line`, `.debug_str` 같은 섹션이 여러 개 보일 때, 이걸 어떻게 활용해야 할지 모를 때

## 핵심 개념

### DWARF란 무엇인가
DWARF는 컴파일러(GCC/Clang)가 디버거를 위해 만들어 넣는 디버그 정보 포맷으로, ELF 안에 다음과 같은 섹션들로 저장된다.
- `.debug_info`: 타입, 변수, 함수에 대한 핵심 디버그 정보(DIE, Debugging Information Entry 트리)
- `.debug_abbrev`: `.debug_info`를 압축해서 표현하기 위한 약어 테이블
- `.debug_line`: 기계어 주소 ↔ 소스 파일명:줄번호 매핑 테이블(라인 넘버 프로그램)
- `.debug_str`: `.debug_info`에서 참조하는 문자열들(함수 이름, 변수 이름, 파일 경로 등)
- `.debug_ranges` / `.debug_rnglists`, `.debug_loc` / `.debug_loclists`: 코드 범위, 변수가 어느 레지스터/스택 위치에 있는지에 대한 정보

이 정보는 `.symtab`(REV-0666)보다 훨씬 풍부해서, 단순히 "이 주소가 `main`이다" 수준이 아니라 "이 주소는 `chall.c`의 42번째 줄에 해당하고, 이 시점에 지역 변수 `buf`는 `rbp-0x40`에 있다"까지 알려준다.

### 왜 CTF 문제에 디버그 정보가 남아있나
문제 출제자가 GCC로 컴파일할 때 실수로 `-g`를 빼먹지 않았거나, 디버깅 편의를 위해 일부러 남겨두는 경우, 또는 `strip` 단계를 생략한 경우다. 상용 소프트웨어와 달리 CTF 바이너리는 이런 실수가 종종 있으며, 있으면 반드시 활용해야 하는 큰 이점이다.

## 화면/코드에서 보이는 징후
```
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), dynamically linked,
interpreter /lib64/ld-linux-x86-64.so.2, ... with debug_info, not stripped
```
`with debug_info`라는 문구가 결정적인 신호다. `readelf -S ./chall | grep debug`로도 확인 가능하며, `.debug_info`, `.debug_line` 등이 나오면 확실하다.

## 가장 먼저 할 것
```bash
file ./chall
```
`with debug_info`가 보이면, 바로 GDB로 실행해서 소스 레벨 디버깅이 되는지 확인한다.
```bash
gdb ./chall
(gdb) list main
```
소스 코드가 그대로 출력되면(원본 `.c` 파일이 배포에 포함되어 있거나 GDB가 경로를 찾을 수 있는 경우) 소스와 함께 분석할 수 있고, 소스 파일 자체는 없어도 DWARF 정보만으로 `break`, `next`, `step`, 변수 이름 조회는 가능하다.

## 단계별 절차

**1) 디버그 섹션 존재 확인**
```bash
readelf -S ./chall | grep debug
```

**2) 컴파일에 쓰인 소스 파일 이름과 컴파일러 정보 확인**
```bash
readelf --debug-dump=info ./chall | head -40
```
출력 초반에 `DW_AT_producer` (예: `GNU C17 11.4.0 -g`), `DW_AT_name` (원본 `.c` 파일 이름), `DW_AT_comp_dir` (컴파일 당시 디렉터리 경로)가 나온다. 이것만으로도 출제자의 빌드 환경을 유추할 수 있다.

**3) 주소 ↔ 소스 줄 매핑 확인**
```bash
objdump --dwarf=decodedline ./chall | less
```
또는
```bash
readelf --debug-dump=decodedline ./chall | less
```
어떤 기계어 주소가 소스 코드 몇 번째 줄에 해당하는지 표를 볼 수 있다. `addr2line`도 같은 정보를 뽑는 전용 도구다.
```bash
addr2line -e ./chall -f -C 0x401256
```

**4) GDB에서 함수/변수 목록 확인**
```bash
gdb ./chall
(gdb) info functions
(gdb) info variables
(gdb) info line main
(gdb) break main
(gdb) run
(gdb) next
(gdb) print buf
(gdb) print password
```
디버그 정보가 있으면 `print 변수이름`으로 지역 변수 값을 이름 그대로 조회할 수 있다 — `x/s $rbp-0x40` 같은 오프셋 계산 없이 바로 값이 보인다.

**5) GDB TUI로 소스와 어셈블리 동시에 보기**
```bash
(gdb) layout src
(gdb) layout split
```
원본 소스 파일이 실제로 존재하면 `layout src`로 소스 코드 창을 띄운 채 `next`/`step`으로 따라갈 수 있다.

## 명령어/단축키
```bash
readelf -S ./chall | grep debug
readelf --debug-dump=info ./chall
readelf --debug-dump=decodedline ./chall
objdump --dwarf=decodedline ./chall
addr2line -e ./chall -f -C 0x401256
gdb ./chall
  (gdb) list main
  (gdb) info functions
  (gdb) break main
  (gdb) next / step
  (gdb) print <변수명>
  (gdb) layout src
```

## 출력 해석
```
$ addr2line -e ./chall -f -C 0x401256
check_password
/home/build/chall/chall.c:27
```
첫 줄은 그 주소가 속한 함수 이름(`-f`), 둘째 줄은 원본 소스 파일 경로와 줄 번호다. 이 한 줄만으로 IDA/Ghidra의 무명 `sub_401256` 대신 정확한 함수 이름과 소스 위치를 바로 얻을 수 있다.

```
(gdb) info line check_password
Line 27 of "chall.c" starts at address 0x401256 <check_password> and ends at 0x40125d <check_password+7>.
```
GDB가 특정 소스 줄과 어셈블리 주소 구간을 직접 매핑해서 보여준다.

## 흔한 실수
- 디버그 정보가 있다는 걸 확인하고도 여전히 IDA/Ghidra에서 `sub_` 이름만 보고 분석하는 것 — Ghidra는 DWARF를 상당 부분 자동으로 임포트해 함수/변수 이름을 채워주고, IDA도 ELF 로더가 DWARF를 읽어 이름을 붙여준다. 디버그 정보가 있는데 이름이 안 보인다면 로더 설정이나 임포트 옵션을 다시 확인해야 한다.
- `.debug_info`가 있다고 소스 코드 원본 파일까지 같이 배포된 것으로 착각하는 것 — DWARF는 파일 이름과 줄 번호를 알려줄 뿐, 실제 `.c` 파일 내용은 원본 파일이 로컬에 있어야 GDB `list`로 볼 수 있다. 파일이 없으면 GDB는 `27	in chall.c` 처럼 줄 번호만 보여주고 실제 코드 내용은 못 보여준다.
- 디버그 정보만 믿고 `.debug_info`가 없는(strip된) 라이브러리 부분까지 소스 레벨로 보일 거라 기대하는 것 — 정적 링킹된 glibc 부분은 별도로 디버그 정보가 없는 경우가 대부분이라 여전히 어셈블리로 봐야 한다.

## 막혔을 때 다음 체크
- `.debug_info`가 아예 없다면 → REV-0666 nm으로 정적 바이너리에서 원하는 심볼 찾기, REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념
- 디버그 정보로 얻은 함수 이름을 GDB 브레이크포인트에 바로 쓰고 싶다면 → REV-0186 GDB break와 address breakpoint
- 전체 심볼 구조를 다시 짚고 싶다면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이
- GDB 기본 명령이 헷갈린다면 → REV-0284 GDB 명령어 치트시트

## 미니 예제
```bash
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, ... with debug_info, not stripped

$ gdb -q ./chall
Reading symbols from ./chall...
(gdb) break check_password
Breakpoint 1 at 0x401260: file chall.c, line 29.
(gdb) run
Starting program: /home/user/chall
Enter password: test

Breakpoint 1, check_password (input=0x7ffd1234 "test") at chall.c:29
29          if (strcmp(input, secret) == 0) {
(gdb) print secret
$1 = 0x402008 "s3cr3t_flag_value"
```
브레이크포인트가 함수 이름과 파일:줄 번호로 바로 걸리고, `print secret`으로 지역 변수 값이 이름 그대로 즉시 노출된다 — 디버그 정보가 남아있을 때 리버싱이 얼마나 빨라지는지 보여주는 전형적인 예다.

## 관련 글
- REV-0666 — nm으로 정적 바이너리에서 원하는 심볼 찾기
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0186 — GDB break와 address breakpoint
- REV-0284 — GDB 명령어 치트시트
- REV-0091 — readelf 기본 사용법

## 출처/검증
- DWARF 섹션 구조(`.debug_info`, `.debug_line`, `.debug_str` 등) 및 `DW_AT_*` 속성: DWARF Debugging Information Format 공식 스펙(DWARF Standards Committee) 기준.
- `readelf --debug-dump`, `objdump --dwarf`, `addr2line` 옵션: GNU Binutils 공식 man page 기준 (2026-09-08 검증).
