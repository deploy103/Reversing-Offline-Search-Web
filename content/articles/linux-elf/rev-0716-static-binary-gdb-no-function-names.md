---
id: REV-0716
title: "statically linked 바이너리라 GDB가 함수 이름을 안 보여줄 때"
slug: "rev-0716-static-binary-gdb-no-function-names"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["statically linked", "정적 링킹", "GDB 심볼", "symbol table", "stripped binary", "FLIRT"]
aliases: ["gdb static binary no symbols", "정적 바이너리 함수 이름 안보임", "gdb disassemble 주소만 나옴", "static stripped 분석"]
symptom_keywords: ["GDB에 함수 이름이 안뜸", "call 뒤에 주소만 있고 이름이 없음", "No symbol table is loaded static", "정적 바이너리 strip 확인법"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`file` 결과에 "statically linked"가 떴다고 해서 GDB가 자동으로 함수 이름을 못 보여주는 것이 아니라, 진짜 원인은 대부분 바이너리가 **동시에 strip까지 되어 있어서** `.symtab`(심볼 테이블) 자체가 사라졌기 때문이며, `readelf -S`로 `.symtab` 유무를 확인하고 없으면 GDB 자체 기능이 아니라 IDA/Ghidra의 FLIRT류 시그니처 매칭이나 libc 소스 대조로 함수를 식별해야 한다.

## 언제 검색해야 하나
- `file ./chall` 결과에 "statically linked"라고 나왔는데, GDB에서 `disassemble main`을 해도 `call 0x404e10` 처럼 이름 없이 주소만 나올 때
- `break printf` 같은 흔한 라이브러리 함수 이름으로 브레이크포인트를 걸었더니 `Function "printf" not defined`라고 나올 때
- "정적 링킹이라 원래 심볼이 없는 거다"라고 생각하고 포기하려는 상황

## 핵심 개념

### 정적 링킹과 심볼 유무는 별개다
정적 링킹(REV-0101)은 `printf`, `malloc`, `strcmp` 같은 libc 코드 전체를 컴파일 시점에 실행 파일 안에 복사해 넣는 것을 말한다. 이 자체는 심볼 테이블과 아무 상관이 없다. 실제로 `gcc -static`으로만 빌드하고 `strip`을 따로 하지 않으면, `nm ./chall`에 `printf`, `main`, `check` 같은 이름이 T(전역, 텍스트 섹션) 심볼로 그대로 남아 있고, GDB `disassemble main`에서도 `call 0x404e10 <printf>`처럼 이름이 정상적으로 붙는다. CTF 문제 바이너리에서 이름이 안 보이는 진짜 이유는 거의 항상 빌드 스크립트가 `-static`과 `strip`(또는 `-s` 링커 옵션)을 같이 적용했기 때문이다.

### strip이 지우는 것: .symtab, .strtab
`strip`은 ELF의 `.symtab`(심볼 이름-주소 매핑 테이블)과 `.strtab`(이름 문자열)을 제거한다. 동적 링킹 바이너리라면 `.dynsym`/`.dynstr`(REV-0100 PLT/GOT과 함께 쓰이는 동적 심볼)은 프로그램이 런타임에 라이브러리를 찾기 위해 반드시 필요하므로 보통 strip해도 남아있지만, 정적 링킹 바이너리는 애초에 동적 심볼 자체가 없다(외부 라이브러리를 안 부르니까). 그래서 "정적 + strip" 조합은 **이름 정보가 통째로 사라지는 최악의 조합**이 된다. GDB는 `.symtab`을 읽어서 이름을 붙이는 것뿐이라, 그 섹션이 아예 없으면 GDB 입장에서는 처음부터 이름을 알 방법이 없다 — GDB의 버그나 설정 문제가 아니다.

### 왜 정적 바이너리에서 유독 체감이 심한가
동적 링킹 바이너리는 strip 되어도 PLT(REV-0100)를 통해 호출하는 외부 함수 이름(`printf@plt` 등)이 `.dynsym`을 통해 남아 있는 경우가 많아 "그나마 라이브러리 호출 지점은 이름이 보이는" 경우가 흔하다. 반면 정적 바이너리는 `printf`부터 그 내부에서 쓰는 `vfprintf`, `_IO_*` 계열 헬퍼 함수까지 수백~수천 개의 libc 내부 함수가 전부 바이너리 안에 박혀 있는데, strip되면 이 전부가 이름 없이 `sub_XXXXXX`급 무명 코드 덩어리로 보인다. `file` 결과에 "statically linked, stripped"가 같이 뜨는 순간, 코드 크기는 커지고 정보는 사라지는 셈이라 초보자가 유독 막막함을 느끼는 지점이다.

## 화면/코드에서 보이는 징후
```
$ file chall
chall: ELF 64-bit LSB executable, x86-64, version 1 (GNU/Linux), statically linked, BuildID[sha1]=..., stripped
```
```
gdb-peda$ disassemble main
No symbol "main" in current context.
gdb-peda$ break main
Function "main" not defined.
```
```
gdb-peda$ info functions ^check$
All functions matching regular expression "^check$":
(아무것도 안 나옴)
```

## 가장 먼저 할 것
strip 여부를 직접 확인한다. `file` 출력 맨 끝에 `stripped`라고 명시되어 있거나, 다음 명령으로 `.symtab` 섹션이 있는지 본다:
```bash
readelf -S ./chall | grep symtab
```
아무것도 안 나오면 stripped가 맞고, `[NN] .symtab  SYMTAB  ...` 한 줄이 보이면 심볼이 남아 있는 것이므로 GDB 설정(예: `strip-debug` 없이 그냥 못 찾는 것)이나 오타 문제일 가능성을 먼저 의심한다.

## 단계별 절차

**1) strip 여부와 심볼 존재 재확인**
```bash
file ./chall
readelf -S ./chall | grep -E "symtab|dynsym"
nm ./chall 2>&1 | head
```
`nm: ./chall: no symbols`가 뜨면 확정적으로 strip된 것이다.

**2) entry point에서 시작해 __libc_start_main 패턴으로 main 위치 추정**
strip된 정적 바이너리라도 `_start`(REV-0098)는 항상 존재하는 진입점이라 `info file` 또는 `readelf -h`로 Entry point 주소를 알 수 있다.
```bash
readelf -h ./chall | grep Entry
gdb -q -batch -ex "break *<entry_point>" -ex run ./chall
```
`_start`에서 `__libc_start_main`(정적 바이너리에서는 흔히 `__libc_start_main` 호출부가 레지스터에 `main` 함수 포인터를 실어 넘기는 형태로 인라인되어 있다)에 진입하는 흐름을 몇 스텝 따라가면, RDI 레지스터에 실린 첫 번째 함수 포인터가 곧 `main`인 경우가 많다(SysV x64 관례상 첫 인자, REV-0106 calling convention 참고).

**3) IDA/Ghidra로 넘어가서 FLIRT/함수 ID 매칭 시도**
GDB 자체에는 라이브러리 함수 시그니처 매칭 기능이 없다. IDA의 FLIRT 시그니처나 Ghidra의 Function ID 데이터베이스는 컴파일된 libc/musl 함수의 바이트 패턴을 미리 학습해두고, strip된 정적 바이너리에서도 `printf`, `malloc`, `free` 같은 이름을 자동으로 복원해준다. CTF 정적 바이너리를 여러 개 다뤄야 한다면 GDB만으로 계속 씨름하지 말고 이 단계로 넘어가는 것이 훨씬 빠르다.

**4) glibc/musl 버전을 특정해서 소스와 대조**
```bash
strings ./chall | grep -iE "glibc|gnu c library|musl"
```
버전 문자열이 남아 있으면 해당 버전의 libc 소스를 받아 함수 프롤로그 패턴(스택 정렬, 레지스터 저장 순서)을 비교하며 수작업으로 매칭할 수 있다. musl로 빌드된 경우(REV-0712 참고 대상, musl은 함수가 더 단순하고 짧아 패턴 추정이 상대적으로 쉽다)도 있으니 `file`에 "musl" 문자열이 있는지도 같이 확인한다.

**5) 동작 기반으로 함수 역할만 추정**
이름 복원이 당장 어렵다면, `strace`(REV-0112)로 어떤 시스템 콜이 호출되는지, 어느 함수가 `write` 직전에 호출되는지 등 동작 패턴으로 "이 함수는 출력 담당이다"처럼 역할만 먼저 추정하고 임시 이름(GDB에서는 붙일 수 없지만 IDA/Ghidra에서는 REV-0147 rename)을 붙여 분석을 이어간다.

## 명령어/단축키
```bash
file ./chall
readelf -S ./chall | grep symtab
readelf -h ./chall | grep Entry
nm ./chall | head
strings ./chall | grep -iE "glibc|musl"
```
```
(gdb) info functions ^main$
(gdb) break *0x401905
(gdb) x/20i 0x401905
```

## 출력 해석
```
$ readelf -S chall | grep symtab
```
이 명령이 아무 줄도 출력하지 않으면 `.symtab` 섹션 헤더 자체가 파일에 없다는 뜻이고, GDB가 이름을 못 붙이는 것이 100% 정상 동작이라는 뜻이다. 반대로
```
[30] .symtab           SYMTAB           0000000000000000  000ac090
```
같은 줄이 보이는데도 GDB에서 이름이 안 보인다면, 심볼 자체는 있는데 GDB가 그 파일을 제대로 로드하지 못했거나(`file ./chall`을 GDB 안에서 다시 실행), 함수 이름 철자가 실제와 다른 것이니 `nm ./chall | grep -i <추정이름>`으로 정확한 이름을 다시 확인한다.

## 흔한 실수
- "정적 링킹이라서 원래 이름이 안 보이는 거다"라고 단정하고 strip 여부를 확인 안 하는 것 — 정적 링킹과 strip은 별개 개념이다.
- GDB에게 이름을 알려달라고 계속 옵션을 바꿔가며 시도하는 것 — `.symtab`이 없는 파일에서는 GDB 자체 설정으로 해결 불가능하며, IDA/Ghidra의 시그니처 매칭 기능으로 넘어가야 한다.
- 수백 개의 무명 함수를 하나하나 다 분석하려는 것 — `main`에서 시작해 실제로 호출되는 함수만 따라가고, `strace`/`ltrace`(단, ltrace는 정적 바이너리에서는 PLT가 없어 거의 못 씀, REV-0111 참고)로 범위를 먼저 좁힌다.
- musl 기반 정적 바이너리를 glibc 패턴으로 착각해서 함수 경계를 잘못 추정하는 것.

## 막혔을 때 다음 체크
- 정적 링킹 자체의 원리와 분석 전략을 더 보고 싶다면 → REV-0101 Dynamic Linking과 Import 함수 추적
- PLT/GOT이 왜 정적 바이너리에는 없는지 원리가 궁금하다면 → REV-0100 PLT와 GOT 기초
- `checksec`로 이 바이너리의 다른 보호 기법도 같이 확인하고 싶다면 → REV-0096 checksec 결과 읽는 법
- GDB 심볼 관련 다른 오류 메시지를 만났다면 → REV-0284 GDB 명령어 치트시트

## 미니 예제
```bash
$ gcc -static -O0 -o chall chall.c && strip -s chall
$ file chall
chall: ELF 64-bit LSB executable, x86-64, version 1 (GNU/Linux), statically linked, stripped
$ readelf -S chall | grep symtab
$ echo $?
1
```
`readelf -S`가 아무것도 못 찾고 종료 코드 1을 반환하는 순간, "GDB가 왜 이름을 안 보여주지?"라는 질문의 답은 이미 나온 것이다 — 파일에 이름 정보 자체가 없기 때문이다. 이후 분석은 GDB 옵션 조정이 아니라 IDA/Ghidra FLIRT 매칭이나 `_start` → `main` 진입점 추적으로 넘어가야 한다.

## 관련 글
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0100 — PLT와 GOT 기초
- REV-0096 — checksec 결과 읽는 법
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0717 — GDB에서 disassemble 결과가 AT&T 문법이라 헷갈릴 때

## 출처/검증
- `strip`이 제거하는 섹션(`.symtab`, `.strtab`)과 `.dynsym`이 남는 이유: `strip(1)`, `readelf(1)` man page 및 ELF 스펙(섹션 종류) 기준.
- 정적/strip 조합에서 실제 GDB 동작(이름 표시 여부, `No symbol table is loaded` 등 메시지): 본 환경에서 `gcc -static`으로 직접 빌드 후 strip 전/후 `nm`, `readelf -S`, `gdb disassemble`로 실측 검증 (2026-09-08).
- FLIRT/Function ID를 통한 strip된 정적 바이너리 함수 식별 관행: IDA/Ghidra 공식 문서 및 일반적인 리버싱 실무 기준.
