---
id: REV-0472
title: "함수 하나가 여러 진입점을 가진 것처럼 보이는 이유(ifunc/dispatch)"
slug: "rev-0472-ifunc-multiple-entry-points"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - ifunc
  - GNU indirect function
  - STT_GNU_IFUNC
  - CPU dispatch
  - CPU 디스패치
  - resolver function
  - 리졸버 함수
  - IRELATIVE
  - R_X86_64_IRELATIVE
  - runtime dispatch
  - 런타임 함수 선택
aliases:
  - memcpy가 이상한 함수를 부름
  - resolve_memcpy 뭐임
  - ifunc 뭐임
  - 함수가 실행할 때마다 다른 곳으로 감
symptom_keywords:
  - memcpy strlen 호출했는데 이상한 함수로 들어감
  - 첫 호출과 두 번째 호출이 다른 주소로 감
  - readelf에서 IRELATIVE가 보임
  - IDA에서 함수가 resolver로 표시됨
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
glibc의 `memcpy`, `strlen` 같은 고성능 함수는 프로그램 실행 초기에 CPU 기능(AVX2 지원 여부 등)을 검사하는 **리졸버(resolver) 함수**가 한 번 실행되어 그 CPU에 가장 빠른 구현체(SSE2 버전, AVX2 버전 등)의 주소를 직접 GOT에 박아 넣는 방식(GNU indirect function, IFUNC)을 쓰기 때문에, 같은 함수 이름인데도 실행 환경에 따라 실제로 호출되는 코드가 달라진다.

## 언제 검색해야 하나
- 디버거로 `call memcpy@plt`(또는 `strlen`, `memset`, `memcmp` 등 libc의 고성능 함수)를 Step Into 했는데 예상과 다르게 `__memcpy_avx_unaligned` 같은 낯선 이름의 함수나 `resolve_memcpy` 같은 함수로 들어갈 때
- 같은 함수를 처음 호출했을 때와 두 번째 호출했을 때 실행되는 코드 주소가 다를 때
- `readelf -r ./binary`로 relocation을 확인했는데 `R_X86_64_IRELATIVE` 타입이 여러 개 보일 때
- IDA/Ghidra에서 함수 하나가 `STT_GNU_IFUNC` 심볼 타입으로 표시되거나, 함수 옆에 "resolver"라는 설명이 붙어있을 때

## 핵심 개념

### CPU 디스패치가 왜 필요한가
`memcpy`(메모리 복사)나 `strlen`(문자열 길이) 같은 함수는 매우 자주 호출되므로 성능이 중요하다. 최신 CPU는 AVX2, AVX-512 같은 명령어 집합으로 한 번에 훨씬 많은 바이트를 처리할 수 있지만, 오래된 CPU는 이런 명령어를 지원하지 않는다. glibc(Linux의 C 표준 라이브러리)는 이 문제를 "**여러 버전의 구현을 미리 만들어두고, 프로그램이 실행되는 실제 CPU에 맞는 것을 골라 쓴다**"는 방식으로 해결한다. 이 매커니즘이 GNU IFUNC(Indirect Function)다.

### 동작 원리
1. 라이브러리(glibc) 안에는 `memcpy`의 여러 구현체가 있다 — 예를 들어 `__memcpy_sse2_unaligned`, `__memcpy_avx_unaligned`, `__memcpy_avx512_unaligned` 등.
2. `memcpy` 심볼은 일반 함수가 아니라 **리졸버(resolver) 함수**로 등록되어 있다. 이 리졸버는 함수가 아니라 "함수를 반환하는 함수"다 — 내부적으로 CPUID를 확인해서(REV-0086 CPUID 참고) 어떤 구현체가 가장 빠른지 판단하고, 그 구현체의 **주소**를 리턴한다.
3. 프로그램(또는 동적 링커 `ld.so`)이 시작될 때, 이 리졸버가 **딱 한 번** 실행되어 골라낸 실제 구현체 주소를 GOT(Global Offset Table)의 `memcpy` 슬롯에 직접 써넣는다.
4. 이후 프로그램 코드에서 `memcpy`를 호출하는 모든 지점은 PLT를 거쳐 이 GOT 슬롯을 읽는데, 이미 리졸버가 실제 주소로 채워놨기 때문에 매번 CPU 검사를 반복하지 않고 바로 최적화된 구현체로 점프한다.

### readelf/objdump에서 보이는 흔적
```bash
$ readelf -r ./binary | grep IRELATIVE
0000000000403ff8  0000000000000025 R_X86_64_IRELATIVE            403a10
```
`R_X86_64_IRELATIVE`는 "이 GOT 슬롯의 값은 고정 주소가 아니라, 리졸버 함수(`403a10`)를 실행한 **반환값**으로 채워야 한다"는 뜻의 특수한 재배치 타입이다. 일반 함수 재배치(`R_X86_64_JUMP_SLOT`)와 다르다는 점이 IFUNC의 핵심 특징이다.

`nm`/`objdump --syms`로 심볼 타입을 보면 `IFUNC`로 표시된다:
```bash
$ objdump -t /lib/x86_64-linux-gnu/libc.so.6 | grep 'memcpy$'
... IFUNC  memcpy
```

### 리버싱에서 왜 헷갈리는가
디버거로 `call memcpy@plt`에 Step Into(F7)를 하면:
- **정적 링킹 프로그램의 첫 실행**이거나 리졸버가 아직 안 돌았다면 리졸버 함수 내부로 들어가서 CPUID 체크 코드를 보게 되어 "왜 memcpy가 이런 이상한 코드를 하지?"라고 당황할 수 있다.
- 리졸버가 이미 실행된 이후(대부분의 경우, 동적 링커가 프로그램 시작 전에 처리)라면 곧바로 `__memcpy_avx2_unaligned` 같은 실제 최적화 구현체로 들어간다 — `memcpy`라는 이름을 보고 Step Into 했는데 전혀 다른 이름의 함수 안에 있어서 "내가 잘못 들어왔나?" 싶을 수 있다.

### Windows에는 동일한 메커니즘이 없다
IFUNC는 ELF(Linux) 전용 메커니즘이다. Windows PE에는 표준화된 동일 기능이 없지만, 고성능 라이브러리(Intel MKL, 일부 게임 엔진, 최적화된 코덱 등)는 유사한 아이디어를 **수작업으로** 구현하기도 한다 — 프로그램 시작 시 `CPUID`를 검사해서 함수 포인터 전역 변수를 적절한 구현체로 설정해두고, 이후 모든 호출을 그 함수 포인터를 통해(간접 호출로) 수행하는 패턴이다. 이런 경우 IDA에서 "함수 포인터 초기화 루틴"과 "그 포인터를 쓰는 간접 호출들"을 찾으면 사실상 같은 원리를 발견할 수 있다.

## 화면/코드에서 보이는 징후
```asm
; 리졸버 함수 자체 (단순화)
resolve_memcpy:
    call    __get_cpu_features   ; CPUID 기반 기능 검사
    test    eax, AVX2_BIT
    jz      use_sse2
    lea     rax, [rip+__memcpy_avx2_unaligned]
    ret
use_sse2:
    lea     rax, [rip+__memcpy_sse2_unaligned]
    ret
```
```bash
$ readelf -r ./binary | grep -i irelative
... R_X86_64_IRELATIVE ... <resolve_memcpy의 주소>
```
```text
(gdb) b memcpy
(gdb) run
Breakpoint 1, __memcpy_avx_unaligned () from /lib/x86_64-linux-gnu/libc.so.6
```
GDB에서 `memcpy`에 브레이크포인트를 걸었는데 실제로 멈춘 곳의 이름이 `__memcpy_avx_unaligned`처럼 다른 이름으로 표시되는 것이 IFUNC가 이미 리졸브된 상태에서의 정상적인 모습이다.

## 가장 먼저 할 것
1. 함수 이름이 `memcpy`, `memset`, `memcmp`, `strlen`, `strcmp` 등 libc의 고성능 함수이고 Step Into 결과가 이상하게 낯설다면, 먼저 "이게 IFUNC일 수 있다"고 의심한다.
2. `readelf -r`로 `IRELATIVE` 재배치가 있는지, `objdump -t`로 해당 심볼이 `IFUNC` 타입인지 확인한다.
3. 실제 로직(무슨 일을 하는가)은 리졸버가 아니라 **선택된 구현체 함수** 안에 있으므로, 리졸버 코드 자체를 분석 대상으로 삼지 말고 최종적으로 호출되는 구현체로 넘어간다.

## 단계별 절차
**1) IFUNC 여부 확인**
```bash
readelf -r ./binary | grep IRELATIVE
objdump -t ./binary | grep IFUNC
```

**2) 어떤 구현체가 선택됐는지 확인 (동적 분석)**
GDB로 실제 호출되는 함수 이름을 직접 확인하는 게 가장 확실하다.
```text
(gdb) b memcpy
(gdb) run
(gdb) bt          ; 백트레이스에 실제 진입한 구현체 이름이 보임
```

**3) 정적으로 리졸버 로직 확인 (선택)**
리졸버 함수 자체를 IDA/Ghidra로 열어서 어떤 CPUID 비트를 검사하는지 보면, 이 라이브러리가 지원하는 구현체 종류(SSE2/AVX/AVX2/AVX512)를 목록으로 파악할 수 있다.

**4) 실제 로직 분석은 선택된 구현체에서 진행**
리졸버가 아니라 `__memcpy_avx2_unaligned` 같은 실제 구현체를 F5로 디컴파일해서 분석을 이어간다.

## 명령어/단축키
- `readelf -r ./binary`, `readelf -d ./binary`(동적 섹션에서 `IRELATIVE` 관련 카운트 확인)
- `objdump -t ./binary`, `objdump -R ./binary`(동적 재배치 목록)
- GDB/Pwndbg: `b memcpy`, `run`, `bt`, `info symbol $pc`(현재 실행 중인 실제 함수 이름 확인)
- IDA: Imports/심볼 목록에서 `IFUNC` 타입 확인, 리졸버 함수 F5로 CPUID 분기 확인

## 출력 해석
- GDB에서 `memcpy`에 브레이크포인트를 걸었는데 멈춘 함수 이름이 `__memcpy_avx_unaligned`처럼 표시된다면, 이는 정상이며 IFUNC 리졸버가 이미 이 CPU에 맞는 구현체를 선택해뒀다는 뜻이다.
- `readelf -r`에서 `IRELATIVE` 항목의 개수가 많다면, 그 바이너리가 링크한 라이브러리(주로 glibc) 안에 CPU별 최적화 함수가 다수 포함되어 있다는 뜻이다 — 바이너리 자체의 로직과는 무관한 라이브러리 초기화 흔적이다.

## 흔한 실수
- 리졸버 함수의 CPUID 검사 로직을 프로그램의 "안티디버깅"이나 "핵심 로직"으로 오인하는 것 — 이는 순수하게 성능 최적화를 위한 라이브러리 초기화 코드다.
- 함수 이름이 `memcpy`인데 실제 실행되는 코드가 다른 이름(`__memcpy_avx2_unaligned`)이라고 해서 "후킹당했다"거나 "바이너리가 패치됐다"고 오판하는 것 — IFUNC의 정상 동작이다.
- REV-0466(함수 복제, constprop/isra/part)과 이 개념을 혼동하는 것 — 함수 복제는 **컴파일 시점**에 호출 상수에 따라 여러 버전을 만드는 것이고, IFUNC 디스패치는 **런타임에 CPU 기능**에 따라 이미 만들어진 여러 구현체 중 하나를 선택하는 것으로 완전히 다른 메커니즘이다.
- Windows PE 바이너리에서 IFUNC 관련 재배치 타입을 찾으려 하는 것 — ELF 전용 개념이므로 PE에는 존재하지 않는다.

## 막혔을 때 다음 체크
- 실제로 호출되는 구현체를 못 찾겠다면 → 정적 분석 대신 GDB로 브레이크포인트를 걸어 동적으로 확인하는 게 가장 빠르다.
- PLT/GOT 동작 자체가 헷갈린다면 → REV-0100(PLT와 GOT 기초)을 먼저 복습한다.
- CPUID 분기 로직을 더 이해하고 싶다면 → REV-0086(CPUID) 문서를 참고한다.
- 함수가 왜 여러 버전으로 보이는지 다른 이유가 의심되면 → REV-0466(Function Cloning)과 이 글의 차이를 다시 비교한다.

## 미니 예제
**예제 1 — GDB로 실제 구현체 확인**
```text
$ gdb ./a.out
(gdb) b memcpy
Breakpoint 1 at 0x...: memcpy
(gdb) run
...
Breakpoint 1, 0x00007ffff7... in __memcpy_avx_unaligned_erms ()
   from /lib/x86_64-linux-gnu/libc.so.6
```
`memcpy`에 건 브레이크포인트가 `__memcpy_avx_unaligned_erms`에서 멈췄다 — 이 시스템의 CPU가 AVX와 ERMS(Enhanced REP MOVSB/STOSB)를 지원해서 그 구현체가 선택됐다는 뜻이다.

**예제 2 — readelf로 IRELATIVE 재배치 확인**
```bash
$ readelf -r ./a.out | grep IRELATIVE | wc -l
23
```
glibc를 정적으로 일부 포함하거나 IFUNC를 쓰는 함수가 다수 링크된 바이너리에서는 이런 재배치가 여러 개 나타날 수 있다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0086 — CPUID: CPU 정보와 안티VM 단서
- REV-0466 — 함수가 여러 번 복제된 것처럼 보이는 이유(Function Cloning)
- REV-0447 — memset이 SIMD 명령으로 인라인되는 패턴
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- GNU Indirect Function(IFUNC) 메커니즘과 `STT_GNU_IFUNC` 심볼 타입: glibc 공식 문서 및 `elf(5)` man page, GNU Binutils 문서(`R_X86_64_IRELATIVE`) 기준.
- glibc의 CPU별 `memcpy`/`strlen` 다중 구현과 런타임 선택: glibc 소스 트리(`sysdeps/x86_64/multiarch/`) 및 공식 glibc 위키(CPU dispatch) 기준.
- 위 예제 출력은 일반적인 x86-64 Linux/glibc 환경의 전형적인 결과를 재구성한 예시다(2026-09-08 검증).
