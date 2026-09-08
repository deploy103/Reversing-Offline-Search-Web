---
id: REV-0101
title: "Dynamic Linking과 Import 함수 추적"
slug: "rev-0101-dynamic-linking"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, readelf, objdump, ldd]
keywords: ["동적 링킹", "dynamic linking", "ld.so", "동적 로더", "NEEDED", "DT_NEEDED", "import 함수", "libc.so.6", "동적 심볼 테이블", ".dynsym", ".dynstr"]
aliases: ["dynamic linking이란", "동적 링킹이란", "ld.so란", "import 함수 목록", "라이브러리 함수 추적"]
symptom_keywords: ["함수 이름은 보이는데 코드가 없음", "libc 함수가 바이너리 안에 없음", "ldd가 not a dynamic executable이라고 나옴", "import 목록을 어디서 보는지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
동적 링킹(Dynamic Linking)된 ELF는 `printf`, `malloc` 같은 함수의 실제 코드를 파일 안에 담지 않고, 실행 시점에 `ld.so`(동적 로더)가 `libc.so.6` 등의 공유 라이브러리를 메모리에 매핑한 뒤 그 함수들과 이어붙이며, 이때 "어떤 함수를 가져다 쓸지"가 기록된 목록이 바로 import(동적 심볼) 목록이다.

## 언제 검색해야 하나
- IDA/Ghidra에서 함수 이름은 `strcpy`, `system`처럼 익숙한데 정작 코드 내용이 텅 비어 있고 `jmp` 한 줄뿐일 때
- `file ./chall` 결과에 `dynamically linked`라고 나오는데 이게 정확히 뭘 의미하는지 모를 때
- `ldd ./chall`을 실행했더니 어떤 라이브러리가 필요한지 목록이 나오는데, 이 정보를 리버싱에 어떻게 쓸지 모를 때
- 바이너리가 어떤 외부 함수를 쓰는지(import 목록) 한눈에 보고 싶을 때

## 핵심 개념

### 정적 링킹 vs 동적 링킹
정적 링킹(static linking)된 바이너리는 컴파일 시점에 `libc` 코드 전체(또는 사용하는 부분)를 실행 파일 안에 통째로 복사해 넣는다. 파일 크기가 커지지만 실행에 외부 라이브러리가 필요 없다. 반대로 동적 링킹된 바이너리는 자기 코드만 갖고 있고, `libc`, `libm`, `libpthread` 같은 공유 라이브러리(`.so`, shared object)는 실행할 때 커널과 `ld.so`가 메모리에 얹어준다. CTF 문제 대부분은 동적 링킹이지만, 배포 편의를 위해 정적 링킹된 바이너리도 종종 나온다. `file ./chall` 명령의 출력에 `dynamically linked` 또는 `statically linked`라고 바로 표시되므로 가장 먼저 확인하는 습관을 들이는 게 좋다.

### ld.so(동적 로더)의 역할
동적 링킹된 ELF를 실행하면 커널은 프로그램의 코드를 직접 실행하지 않고, ELF 헤더의 `INTERP` 세그먼트에 적힌 인터프리터(보통 `/lib64/ld-linux-x86-64.so.2`)를 먼저 실행시킨다. 이 `ld.so`가 진짜 로더 역할을 한다.

1. ELF의 `.dynamic` 섹션을 읽어서 이 바이너리가 필요로 하는 공유 라이브러리 목록(`DT_NEEDED` 엔트리들)을 확인한다.
2. `LD_LIBRARY_PATH`, `/etc/ld.so.cache`, 기본 경로(`/lib`, `/usr/lib` 등) 순서로 각 라이브러리 파일을 찾아 메모리에 매핑한다.
3. 실행 파일과 각 라이브러리의 재배치(relocation) 정보를 이용해 심볼(함수/전역변수)을 서로 연결한다. 이 연결 과정 일부가 REV-0100에서 다룬 GOT 채우기다.
4. 모든 준비가 끝나면 실행 파일의 진짜 진입점(`_start`)으로 점프한다.

즉 우리가 `./chall`을 실행하는 순간, 실제로는 `ld.so`가 먼저 실행되고, `ld.so`가 필요한 라이브러리를 다 붙인 뒤에야 우리 코드가 시작된다.

### 동적 심볼 테이블 — import 목록의 실체
ELF에는 두 종류의 심볼 테이블이 있을 수 있다.
- `.symtab` + `.strtab`: 디버깅/링크용 전체 심볼 테이블. `strip`으로 제거되는 경우가 많다.
- `.dynsym` + `.dynstr`: **동적 링킹에 반드시 필요한** 심볼 테이블. 여기에는 이 바이너리가 외부에서 가져다 쓰는 함수(import)와, 반대로 이 바이너리가 외부에 제공하는 함수(export)가 함께 들어있다. `.dynsym`은 `strip`으로도 지워지지 않는다 — 지우면 동적 링킹 자체가 깨지기 때문이다.

IDA/Ghidra의 "Imports" 창(IDA는 `Ctrl+I` 또는 View → Open subviews → Imports)에 뜨는 목록이 바로 이 `.dynsym`에서 "이 바이너리가 정의하지 않고 외부에서 가져오는" 심볼들을 추려낸 것이다. 이 목록만 훑어봐도 프로그램이 파일을 여는지(`open`, `fopen`), 네트워크를 쓰는지(`socket`, `connect`), 입력을 받는지(`scanf`, `read`, `fgets`), 프로세스를 실행하는지(`system`, `execve`) 같은 정보를 코드를 한 줄도 안 읽고 짐작할 수 있다. 리버싱을 시작할 때 가장 먼저 훑어봐야 할 목록이다.

### 정적 분석에서 import는 왜 코드가 비어 있나
REV-0100에서 설명했듯, import된 함수를 호출하는 코드는 실제로는 PLT 스텁을 호출하고, PLT는 GOT를 거쳐 런타임에 로드된 라이브러리의 진짜 주소로 점프한다. 정적 분석 도구(IDA, objdump)는 라이브러리를 로드하지 않으므로 GOT에 채워질 진짜 주소를 알 수 없고, 그래서 import 함수의 "본체"를 보여줄 수 없다. 진짜 함수 코드를 보고 싶다면 대상 라이브러리(`libc.so.6` 등)를 별도로 IDA에 로드하거나, 동적 분석(GDB)으로 실행 중에 확인해야 한다.

## 화면/코드에서 보이는 징후
- IDA Imports 창에 `printf`, `strcpy`, `system` 등 함수 이름과 라이브러리 이름(`libc.so.6`)이 줄줄이 나열됨
- 해당 함수로 더블클릭해 들어가면 코드가 몇 줄 없고 `jmp` 한 줄로 끝나는 PLT 스텁만 보임
- `ldd ./chall` 실행 시 `linux-vdso.so.1`, `libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6`, `/lib64/ld-linux-x86-64.so.2` 같은 줄이 출력됨
- 정적 링킹 바이너리는 `ldd`가 `not a dynamic executable`이라고 출력하고, IDA Imports 창도 거의 비어 있음

## 가장 먼저 할 것
새 바이너리를 받으면 분석 코드를 한 줄도 읽기 전에 다음 세 가지를 먼저 확인한다: (1) `file ./chall`로 정적/동적 링킹 여부, (2) `ldd ./chall`로 필요한 라이브러리와 그 버전(특히 libc 버전은 pwn에서 매우 중요), (3) import 함수 목록을 훑어 프로그램이 어떤 계열의 동작(입출력, 파일, 네트워크, 프로세스 실행, 문자열 비교)을 하는지 감을 잡는다. 이 세 가지만으로도 코드를 읽기 전에 이미 절반은 파악한 셈이다.

## 단계별 절차

**1) 정적/동적 링킹 확인**
```bash
file ./chall
```
출력에 `dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2`가 보이면 동적 링킹이다.

**2) 필요한 공유 라이브러리 확인**
```bash
ldd ./chall
```
출력 예:
```
linux-vdso.so.1 (0x00007ffd...)
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f...)
/lib64/ld-linux-x86-64.so.2 (0x00007f...)
```
`libc.so.6`이 가리키는 실제 경로가 이 바이너리가 실행 시 쓸 libc다. CTF에서는 문제 배포 파일에 특정 버전의 `libc.so.6`이 같이 들어오는 경우가 많은데, 그럴 때는 반드시 그 libc로 실행/디버깅해야 오프셋이 맞는다.

**3) DT_NEEDED 엔트리와 .dynamic 섹션 확인**
```bash
readelf -d ./chall
```
`NEEDED` 타입 줄들이 이 바이너리가 명시적으로 요구하는 라이브러리 이름이다.

**4) 동적 심볼(import) 목록 뽑기**
```bash
readelf --dyn-syms ./chall | grep UND
objdump -T ./chall
nm -D ./chall
```
`UND`(undefined)로 표시된 심볼이 "정의는 없고 외부에서 가져다 쓰는" 함수, 즉 import다.

**5) IDA/Ghidra에서 확인**
IDA는 `Ctrl+I` 또는 View → Open subviews → Imports로 목록을 연다. Ghidra는 Symbol Tree의 External 폴더에 같은 정보가 나온다.

**6) GDB로 런타임에 실제 로드된 라이브러리와 주소 확인**
```gdb
break main
run
info sharedlibrary
```
현재 프로세스에 매핑된 모든 공유 라이브러리와 그 시작/끝 주소가 나온다. `/proc/<pid>/maps`(또는 Pwndbg `vmmap`)로 봐도 같은 정보를 더 상세히 볼 수 있다.

## 명령어/단축키
```bash
file ./chall
ldd ./chall
readelf -d ./chall
readelf --dyn-syms ./chall
objdump -T ./chall
nm -D ./chall
```
GDB/Pwndbg: `info sharedlibrary`, `vmmap`, IDA: `Ctrl+I`(Imports)

## 출력 해석
- `readelf --dyn-syms` 결과에서 `UND`(undefined)는 import(외부에서 가져옴), 숫자 섹션 인덱스가 있으면 이 바이너리가 직접 정의(export)한 심볼이다.
- `objdump -T` 출력의 `DF *UND*` 표시도 마찬가지로 "정의되지 않음 = 외부 함수"라는 뜻이다.
- `ldd` 출력에서 라이브러리 경로 옆 괄호 안 주소는 ASLR 때문에 실행마다 달라진다(REV-0104 참고). `ldd`는 사실 대상 프로그램을 실제로 한 번 살짝 실행시켜서 얻은 값이므로, 신뢰할 수 없는 바이너리에는 `ldd` 대신 `readelf -d`나 `file`만 쓰는 것이 안전하다는 점도 알아두면 좋다.

## 흔한 실수
- import 함수 코드 자체를 IDA에서 끝까지 찾으려고 헤매는 것 — PLT 스텁만 있을 뿐이며 진짜 코드는 libc 안에 있다(REV-0100 참고).
- `strip`된 바이너리는 함수 이름이 다 사라졌다고 생각하는 것 — `.symtab`(사용자 정의 함수 이름)은 지워져도 `.dynsym`(import/export 이름)은 남아있는 경우가 많아 `printf`, `strcmp` 같은 라이브러리 함수 이름은 여전히 보인다.
- 로컬 libc 버전으로 무작정 디버깅하는 것 — CTF 배포 파일에 별도 libc가 포함돼 있으면 그 버전을 써야 오프셋과 동작이 문제 서버와 일치한다.

## 막혔을 때 다음 체크
- import 함수 호출이 실제로 어떤 코드로 이어지는지 구조를 더 알고 싶다면 → REV-0100 PLT와 GOT 기초
- `scanf`, `fgets`, `read` 같은 입력 함수를 어떻게 추적하는지 → REV-0109 scanf fgets read 입력 추적
- `strcmp`, `memcmp` 같은 비교 함수 추적 → REV-0110 strcmp strncmp memcmp 비교 추적
- 실행할 때마다 라이브러리 주소가 바뀌는 이유 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- import 호출을 코드 수정 없이 빠르게 다 보고 싶다면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기

## 미니 예제
```bash
$ file ./chall
chall: ELF 64-bit LSB pie executable, x86-64, ... dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, ...

$ ldd ./chall
linux-vdso.so.1 (0x00007ffd8b1fe000)
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f2a3d600000)
/lib64/ld-linux-x86-64.so.2 (0x00007f2a3d800000)

$ readelf --dyn-syms ./chall | grep UND | head -5
     3: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND __stack_chk_fail@GLIBC_2.4
     5: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND printf@GLIBC_2.2.5
     7: 0000000000000000     0 FUNC    GLOBAL DEFAULT  UND __isoc99_scanf@GLIBC_2.7
```
`__stack_chk_fail`이 보이면 스택 카나리가 켜져 있다는 뜻이고(REV-0105 참고), `__isoc99_scanf`가 보이면 `scanf`로 입력을 받는다는 뜻이다. 코드를 한 줄도 안 읽고도 이 정도 정보를 얻을 수 있다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0109 — scanf fgets read 입력 추적
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- 동적 링킹/`ld.so` 동작: System V Application Binary Interface, AMD64 Architecture Processor Supplement(동적 링킹 섹션) 기준.
- `.dynsym`/`.dynstr` 및 `DT_NEEDED` 구조: ELF Specification(TIS ELF Format) 기준.
- `readelf`, `objdump`, `nm`, `ldd` 사용법: GNU binutils 공식 매뉴얼 기준 (2026-09-08 검증).
