---
id: REV-0699
title: "checksec 결과가 예상과 달라서 보호기법 판단이 헷갈릴 때"
slug: "rev-0699-checksec-unexpected-result"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [checksec, "readelf", GDB, Pwndbg]
keywords: ["checksec Partial RELRO", "checksec No canary found", "checksec PIE enabled", "checksec 오탐", "checksec.sh vs pwntools checksec"]
aliases: ["checksec 결과 안 믿김", "checksec 틀린 것 같음", "checksec canary 오판", "checksec RELRO 헷갈림"]
symptom_keywords: ["checksec에서 No canary found인데 실제로는 카나리가 있는 것 같음", "Partial RELRO와 Full RELRO 차이가 헷갈림", "checksec 결과가 도구마다 다르게 나옴", ".so 파일인데 PIE enabled로 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`checksec`은 심볼 이름과 ELF 헤더/세그먼트 몇 가지 플래그만 보고 판단하는 **휴리스틱 도구**라서, strip된 바이너리에서 카나리가 실제로 있어도 `No canary found`로 나오거나, `GNU_RELRO` 세그먼트만 있고 `BIND_NOW`가 없으면 기대와 달리 `Partial RELRO`로만 표시되는 등 오탐이 흔하며, 진짜 보호기법 여부는 `readelf -d`(동적 태그)와 `readelf -l`(세그먼트) 원본 값, 그리고 디스어셈블리에서 직접 확인해야 확실하다.

## 언제 검색해야 하나
- `checksec`이 `No canary found`라고 했는데 디스어셈블리를 보니 `fs:0x28`을 읽는 스택 카나리 코드가 분명히 있을 때
- `Partial RELRO`라고 나왔는데 왜 `Full RELRO`가 아닌지, 익스플로잇 가능성에 어떤 차이가 있는지 헷갈릴 때
- 공유 라이브러리(`.so`) 파일을 `checksec`으로 돌렸더니 `PIE enabled`로 나와서 실행 파일처럼 착각할 때
- `checksec.sh`와 `pwn checksec`(pwntools) 결과가 서로 다르게 나올 때

## 핵심 개념

### checksec은 "증거"를 보는 것이지 "코드"를 실행해보는 게 아니다
`checksec`(원조 `checksec.sh`, 또는 pwntools의 `pwn checksec`)은 바이너리를 실제로 실행하거나 디컴파일하지 않는다. 대신 다음과 같은 **간접 증거**만 빠르게 확인한다.

- **Stack Canary**: `.dynsym`에 `__stack_chk_fail`이라는 심볼 이름이 있는지 검사한다. 이름이 있으면 "있음", 없으면 "없음"으로 판정한다.
- **NX**: Program Header에서 `GNU_STACK` 세그먼트의 `PF_X`(실행 가능) 플래그가 꺼져 있는지 확인한다(REV-0090, REV-0105 참고).
- **PIE**: ELF 헤더의 `e_type`이 `ET_DYN`인지 확인한다.
- **RELRO**: `GNU_RELRO` Program Header가 있는지, 그리고 `.dynamic` 섹션에 `DT_BIND_NOW`(또는 `DT_FLAGS`/`DT_FLAGS_1`의 `BIND_NOW` 비트)가 있는지를 함께 본다.

이 방식은 대부분의 정상 컴파일된 바이너리에서는 잘 맞지만, **심볼이 제거되었거나(strip)**, **바이너리 종류가 실행 파일이 아니라 라이브러리(.so)이거나**, **의도적으로 조작된 CTF 바이너리**에서는 실제 보호기법 존재 여부와 checksec 판정이 어긋날 수 있다.

### `__stack_chk_fail` 심볼이 없으면 카나리를 못 찾는다
`gcc -fstack-protector`로 컴파일된 바이너리는 함수 프롤로그에서 `fs:0x28`(TLS 영역의 카나리 값)을 스택에 복사하고, 에필로그에서 검증한 뒤 실패하면 `__stack_chk_fail`을 호출한다(REV-0105). `checksec`은 바로 이 `__stack_chk_fail` 심볼의 **이름**을 찾는다. 그런데 바이너리가 정적 링킹되어 있고 `strip`까지 되어 있으면, 카나리 검사 코드 자체(`fs:0x28` 읽기/비교/`call`)는 여전히 존재하지만 그 `call` 대상 함수의 이름표가 사라져서 checksec이 "이름을 못 찾았으니 카나리 없음"으로 잘못 판정한다.

### Partial RELRO vs Full RELRO는 "두 가지 조건"의 AND다
RELRO(REV-0102)는 두 단계로 나뉜다.
1. `GNU_RELRO` Program Header 존재 → 링크 시점에 알 수 있는 데이터 섹션(`.init_array`, `.got` 등)을 `mprotect`로 읽기 전용화하도록 준비됨(컴파일 옵션 `-Wl,-z,relro`).
2. `DT_BIND_NOW`(또는 동일 효과의 `DT_FLAGS_1`의 `DF_1_NOW`) 존재 → 프로그램 시작 시 **모든** GOT 엔트리를 즉시 미리 resolve(컴파일 옵션 `-Wl,-z,now`).

**둘 다** 있어야 `Full RELRO`다. 1번만 있고 2번이 없으면 `Partial RELRO`로 표시되며, 이 경우 아직 resolve되지 않은 `.got.plt` 엔트리는 실행 중에도 여전히 쓰기 가능한 상태로 남아있어 GOT 오버라이트 공격이 부분적으로 가능하다. "RELRO가 있으니 안전하다"고 단순화해서 판단하면 안 되는 이유다.

### `.so` 파일에 PIE enabled가 뜨는 건 오류가 아니다
공유 라이브러리는 어차피 어느 주소에든 로드될 수 있어야 하므로 항상 `ET_DYN`으로 컴파일된다. `checksec`은 `ET_DYN`만 보고 "PIE"라고 표시하므로, `.so` 파일을 checksec으로 돌리면 항상 `PIE enabled`가 뜬다 — 이건 그 라이브러리가 특별히 PIE 보호기법을 켰다는 뜻이 아니라 "공유 라이브러리는 원래 다 이렇다"는 것뿐이다. 반대로 `gcc -static-pie`로 만든 정적 PIE 실행 파일도 `ET_DYN`이라 checksec은 "동적 링킹된 PIE"와 구분 없이 표시할 수 있다.

## 화면/코드에서 보이는 징후
```text
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Partial RELRO   No canary found   NX enabled    PIE enabled
```
그런데 디스어셈블리(`objdump -d ./chall`)에는:
```asm
mov    rax, fs:0x28
mov    [rbp-0x8], rax
...
mov    rax, [rbp-0x8]
sub    rax, fs:0x28
je     <ok>
call   0x401040   ; __stack_chk_fail 호출인데 이름이 안 보임
```
분명히 카나리 검사 코드가 있다.

## 가장 먼저 할 것
1. checksec 결과 중 의심스러운 항목을 **직접 원본 데이터로 재확인**한다 — 아래 절차의 항목별 명령을 그대로 실행해본다.
2. `file ./chall`로 strip 여부(`not stripped` / 표시 없으면 stripped 가능성)와 정적/동적 링킹 여부를 먼저 확인해 어떤 항목이 오탐일 가능성이 있는지 좁힌다.

## 단계별 절차

**1) 카나리 직접 확인 (심볼 없이)**
```bash
objdump -d ./chall | grep -B2 "fs:0x28"
```
`mov rax, fs:0x28` 패턴이 함수 프롤로그/에필로그에 보이면 카나리가 실제로 켜져 있는 것이다(REV-0105). checksec의 `No canary found`는 이름표만 없을 뿐 검사 로직은 있다는 뜻이다.

**2) RELRO 세부 확인**
```bash
readelf -l ./chall | grep -A1 GNU_RELRO
readelf -d ./chall | grep -i "BIND_NOW\|FLAGS"
```
`GNU_RELRO` 세그먼트는 있는데 `BIND_NOW`/`FLAGS_1: NOW`가 안 보이면 정확히 Partial RELRO가 맞다. 둘 다 있으면 Full RELRO다.

**3) PIE/실행 파일 종류 확인**
```bash
readelf -h ./chall | grep Type
```
`Type: DYN (Position-Independent Executable file)`이면 PIE, `EXEC (Executable file)`이면 Non-PIE다. 다만 `.so` 파일은 `DYN (Shared object file)`로 표시되어 이름부터 구분이 가능하다.

**4) NX 확인**
```bash
readelf -l ./chall | grep -A1 GNU_STACK
```
`RWE`(또는 `RW E`)처럼 실행(`E`) 플래그가 있으면 스택이 실행 가능(NX 꺼짐), `RW`만 있으면 NX 활성화 상태다.

**5) 서로 다른 checksec 버전 비교**
```bash
checksec --file=./chall           # 원조 checksec.sh 계열
python3 -c "from pwn import *; print(ELF('./chall'))"   # pwntools의 자체 ELF 파싱 결과
```
pwntools의 `ELF()` 로드 시 자동으로 출력되는 보호기법 정보는 pwntools가 직접 ELF를 파싱한 결과라서, `objdump`/`readelf`의 텍스트 출력을 파싱하는 구버전 `checksec.sh`보다 binutils 버전 차이에 덜 취약하다. 두 결과가 다르면 `readelf` 원본값을 기준으로 삼는다.

## 명령어/단축키
```bash
checksec --file=./chall
readelf -h ./chall
readelf -l ./chall
readelf -d ./chall
objdump -d ./chall | grep "fs:0x28"
python3 -c "from pwn import *; print(ELF('./chall'))"
```

## 출력 해석
- `readelf -d` 결과에서 `0x000000000000001e (FLAGS)  BIND_NOW` 또는 `0x000000006ffffffb (FLAGS_1) Flags: NOW`가 보이면 즉시 resolve(Full RELRO 조건 2번 충족)를 의미한다.
- `readelf -l`의 `GNU_STACK` 줄에서 `Flags: RW` = NX 활성화, `Flags: RWE` = NX 비활성화(스택에서 코드 실행 가능, 매우 오래된/특수 빌드에서만 흔함).
- checksec이 `Canary: No`인데 `fs:0x28` 코드가 있다면, 심볼 스트립이 원인이지 컴파일 옵션(`-fstack-protector`) 자체가 꺼진 게 아니다 — 두 가지는 다른 문제이므로 혼동하지 않는다.

## 흔한 실수
- checksec 결과 하나만 보고 exploit 전략을 확정하는 것 — 특히 strip된 CTF 바이너리에서는 항상 `readelf`/디스어셈블리로 교차 검증해야 한다.
- Partial RELRO를 "RELRO가 켜져 있으니 GOT는 절대 못 건드린다"고 오해하는 것 — Partial RELRO에서는 아직 resolve 안 된 GOT 엔트리가 여전히 쓰기 가능하다.
- `.so` 파일에 뜬 `PIE enabled`를 보고 "이 라이브러리가 특별히 보안 강화되었다"고 오해하는 것 — 공유 라이브러리는 원래 다 `ET_DYN`이다.
- 서로 다른 checksec 구현체(bash 스크립트 vs pwntools) 결과가 다를 때 어느 쪽이 맞는지 확인하지 않고 아무 쪽이나 믿는 것.

## 막혔을 때 다음 체크
- checksec의 기본 사용법과 정상 출력 형식이 헷갈린다면 → REV-0096 checksec 결과 읽는 법
- Canary/NX/PIE/RELRO 각각의 원리를 다시 보고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해
- RELRO 자체의 의미와 exploit 관점에서의 중요성을 더 깊이 알고 싶다면 → REV-0102 RELRO가 리버싱에 의미하는 것
- PIE에서 실제 주소를 계산하는 법이 궁금하다면 → REV-0103 PIE와 주소 계산
- Program Header/Section Header 구조 자체가 헷갈린다면 → REV-0090 ELF Program Header와 Section Header 차이

## 미니 예제
```text
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Partial RELRO   No canary found   NX enabled    PIE enabled

$ readelf -d ./chall | grep -i flags
0x000000006ffffffb (FLAGS_1)           Flags: NOW

$ objdump -d ./chall | grep -B1 "fs:0x28" | head -4
  1189:	64 48 8b 04 25 28 00 	mov    rax,QWORD PTR fs:0x28
  1190:	00 00 
```
`readelf -d`에서 `FLAGS_1: NOW`가 실제로 보였다면 checksec의 `Partial RELRO` 표기가 이상하다는 신호이므로 `GNU_RELRO` 세그먼트 존재 여부도 함께 재확인해야 하고(둘 다 있어야 Full), `fs:0x28` 코드가 있는데도 `No canary found`가 떴다면 strip으로 인한 오탐임을 확정할 수 있다.

## 관련 글
- REV-0096 — checksec 결과 읽는 법
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0103 — PIE와 주소 계산
- REV-0090 — ELF Program Header와 Section Header 차이

## 출처/검증
- checksec의 판정 방식(`__stack_chk_fail` 심볼 존재 여부로 카나리 판정, `GNU_RELRO`+`BIND_NOW` 조합으로 RELRO 등급 판정, `ET_DYN`으로 PIE 판정)은 checksec.sh 및 pwntools `ELF.checksec()` 구현에서 공개적으로 알려진 휴리스틱을 요약한 것이다.
- RELRO의 두 단계 구조(`-z relro`, `-z now`)는 GNU ld(binutils) 링커 옵션 문서(`ld(1)`)에 기술되어 있다.
- `GNU_STACK` 세그먼트의 실행 플래그로 NX를 판정하는 방식은 ELF Program Header 사양(System V ABI) 기준이다.
- checksec.sh와 pwntools checksec 구현 간의 세부 차이는 각 도구의 공개 소스 코드에 기반하며, 정확한 버전별 동작은 실제 설치된 버전에서 `--help`/소스를 재확인하는 것을 권장한다.
