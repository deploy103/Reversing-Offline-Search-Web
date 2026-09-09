---
id: REV-0679
title: "IFUNC(Indirect Function)와 재배치 개념"
slug: "rev-0679-ifunc-indirect-function"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["IFUNC", "STT_GNU_IFUNC", "R_X86_64_IRELATIVE", "resolver", "ifunc resolver", "memcpy multiversioning", "indirect function"]
aliases: ["ifunc가 뭔가요", "irelative relocation 뜻", "memcpy 여러 버전 왜 있나", "gnu indirect function"]
symptom_keywords: ["gdb에서 memcpy에 breakpoint 걸었는데 다른 함수로 들어감", "readelf -r에 irelative라는 재배치가 보임", "objdump 심볼 타입이 ifunc라고 나옴", "disassemble했더니 resolver 함수가 하나 더 보임"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IFUNC(GNU Indirect Function)는 `memcpy`, `strlen` 같은 함수를 CPU가 지원하는 명령어 세트(AVX2, SSE4 등)에 맞춰 여러 버전으로 만들어두고, 프로그램 시작 시점에 "리졸버(resolver)" 함수를 한 번 호출해 그중 최적 구현의 주소를 골라 GOT에 박아 넣는 glibc 최적화 메커니즘이며, 이 선택 과정은 `R_X86_64_IRELATIVE`라는 특수한 재배치 타입으로 표현된다.

## 언제 검색해야 하나
- GDB에서 `memcpy`나 `strlen`에 브레이크포인트를 걸었는데 실제로는 `__memcpy_avx_unaligned` 같은 낯선 심볼로 진입할 때
- `readelf -r ./libc.so.6` 또는 `objdump -R`에서 심볼 이름 없이 `R_X86_64_IRELATIVE`만 찍힌 재배치 엔트리를 봤을 때
- `nm`이나 `readelf -s` 출력에서 심볼 타입이 `IFUNC`로 나오는 걸 봤을 때
- Ghidra/IDA가 `memcpy` 호출을 제대로 따라가지 못하고 이상한 주소로 점프하는 것처럼 보일 때(리졸버 처리 미흡으로 인한 디컴파일러 한계)

## 핵심 개념

### 왜 필요한가
glibc의 성능이 중요한 함수(`memcpy`, `memset`, `strlen`, `strcmp` 등)는 CPU 명령어 세트에 따라 여러 구현이 존재한다. 예를 들어 `memcpy`는 AVX2를 지원하는 CPU에서는 `__memcpy_avx_unaligned_erms`를, 구형 CPU에서는 `__memcpy_sse2_unaligned`를 쓰는 게 훨씬 빠르다. 하지만 라이브러리를 배포할 때는 어떤 CPU에서 실행될지 미리 알 수 없으므로, "컴파일 시점"이 아니라 "그 라이브러리가 실제로 로드되는 시점"에 CPU 기능을 검사해서 최적 구현을 고르고 싶다. IFUNC는 바로 이 요구를 만족시키는 메커니즘이다.

### 동작 원리
1. glibc 소스에서 `memcpy`는 `__attribute__((ifunc("resolver_name")))` 형태로 선언된다(또는 저수준 매크로로 동일 효과를 낸다).
2. 컴파일된 오브젝트에는 일반 함수 심볼이 아니라 **STT_GNU_IFUNC**라는 특수 심볼 타입으로 `memcpy`가 기록된다. 이 심볼은 함수 자체가 아니라 "리졸버(resolver) 함수"를 가리킨다.
3. 리졸버 함수는 인자 없이 호출되면 `__cpu_features`(HWCAP, `cpuid` 결과 캐시)를 검사해서, 실제로 써야 할 구현 함수의 **주소를 반환**한다. 예: `if (avx2_지원) return __memcpy_avx2; else return __memcpy_sse2;`
4. 동적 로더(공유 라이브러리로 로드되는 일반적인 경우)나 정적 바이너리 자체의 초기화 코드(정적 링크인 경우, `__libc_csu_irel`이 이 역할을 담당)는 프로그램이 `main`을 부르기 전에 이 리졸버를 **한 번 실제로 호출**해서 반환값(진짜 함수 주소)을 GOT에 써넣는다.
5. 이후 `memcpy(...)` 호출은 평소 PLT/GOT 호출과 동일하게 동작하지만, 그 GOT 슬롯에는 이미 CPU에 맞는 최적 구현의 주소가 들어있다.

### R_X86_64_IRELATIVE 재배치
이 "리졸버를 호출해서 나온 값을 GOT에 쓴다"는 동작을 표현하는 재배치 타입이 `R_X86_64_IRELATIVE`(x86 32비트는 `R_386_IRELATIVE`)다. 일반적인 재배치(`R_X86_64_JUMP_SLOT`, `R_X86_64_GLOB_DAT`)는 "이 심볼의 주소를 찾아서 그대로 슬롯에 써라"는 뜻이지만, `IRELATIVE`는 다르다.
- 연결된 **심볼이 없다**(심볼 인덱스가 0/`STN_UNDEF`) — `readelf -r`에서 이 줄만 심볼 이름 칸이 비어 있다.
- `Addend`(또는 `objdump -R`의 값 칸)에 들어있는 것은 데이터 주소가 아니라 **리졸버 함수의 주소**다.
- 로더는 이 재배치를 처리할 때 그 주소를 데이터로 쓰는 게 아니라 **인자 없이 함수처럼 호출**하고, 그 반환값을 최종적으로 GOT 슬롯에 쓴다.

정적으로 링크된 실행 파일에는 동적 로더가 없으므로, `__libc_csu_irel`(또는 유사한 초기화 루틴)이 `_start` 근처에서 `.rela.dyn`에 있는 `IRELATIVE` 엔트리들을 직접 순회하며 리졸버를 호출해준다. 이게 정적 바이너리에서도 IFUNC가 동작하는 이유다.

### 리버싱에서 왜 중요한가
- **디버깅 혼란 방지**: `memcpy`에 브레이크포인트를 걸었는데 `__memcpy_avx2_unaligned_erms` 같은 곳에서 멈추는 걸 보고 "심볼이 왜 다르지?"라고 당황할 수 있다. 이건 정상 동작이며, IFUNC 리졸버가 실제 구현을 골랐기 때문이다.
- **디컴파일러 한계 인지**: 정적 분석 도구는 "GOT 슬롯이 가리키는 함수"를 정적으로 계산할 수 없다(리졸버를 실제로 실행해봐야 알 수 있으므로). 그래서 IDA/Ghidra가 `memcpy` 호출을 리졸버 함수 자체로 잘못 표시하거나 xref가 끊겨 보이는 경우가 있는데, 이는 도구의 한계이지 바이너리가 난독화된 게 아니다.
- **libc 버전 판별 단서**: 어떤 IFUNC 구현이 선택됐는지는 실행 중인 CPU의 `AT_HWCAP`(REV-0677 참고)에 좌우되므로, 같은 libc라도 실행 환경에 따라 심볼 이름이 달라질 수 있다.

## 화면/코드에서 보이는 징후
- `readelf -s ./libc.so.6 | grep IFUNC`에서 `memcpy`, `strlen`, `strcmp` 등이 `IFUNC` 타입으로 표시된다.
- `readelf -r ./libc.so.6 | grep IRELATIVE`에서 심볼 이름 없이 주소만 있는 재배치 줄이 여러 개 보인다.
- GDB에서 `break memcpy` 후 `run`하면 실제로는 `__memcpy_avx_unaligned_erms+0x10` 같은 위치에서 멈춘다.
- `nm -D ./libc.so.6 | grep -i memcpy`에서 심볼 타입 열이 `i`(소문자, IFUNC를 뜻함)로 표시된다.

## 가장 먼저 할 것
`memcpy`, `strlen`류 함수에서 예상과 다른 심볼 이름이 보이면, 먼저 "이 심볼이 IFUNC인가?"를 `readelf -s`나 `nm`으로 확인한다. IFUNC라면 실제 실행되는 구현은 CPU에 따라 달라질 수 있다는 점을 받아들이고, 브레이크포인트는 원래 이름(`memcpy`)에 걸어도 GDB가 자동으로 실제 리졸브된 주소에서 멈춘다는 걸 활용한다.

## 단계별 절차

**1) IFUNC 심볼 확인**
```bash
readelf -s /lib/x86_64-linux-gnu/libc.so.6 | grep -i 'IFUNC' | head
```
출력 예:
```
   234: 0000000000098c30    45 IFUNC  GLOBAL DEFAULT   15 memcpy
   567: 00000000000a1200    30 IFUNC  GLOBAL DEFAULT   15 strlen
```

**2) IRELATIVE 재배치 확인**
```bash
readelf -r /lib/x86_64-linux-gnu/libc.so.6 | grep IRELATIVE | head
```
출력 예(심볼 이름이 없다는 점에 주목):
```
0000000000...  0000...0025  R_X86_64_IRELATIVE            98c50
```

**3) GDB로 실제 실행되는 구현 확인**
```gdb
gdb ./chall
break memcpy
run
bt
```
`bt`(백트레이스) 또는 `x/i $pc`로 실제 진입한 함수 이름이 `__memcpy_avx2_unaligned_erms` 등으로 나오는지 확인한다.

**4) CPU 기능과 대조**
```gdb
info auxv
```
`AT_HWCAP` 값을 확인하면 어떤 CPU 기능이 감지됐는지(그래서 리졸버가 어떤 구현을 골랐을지) 짐작할 수 있다.

**5) Pwndbg로 GOT 슬롯 확인**
```gdb
got
```
`memcpy` 슬롯이 리졸버 함수가 아니라 이미 `__memcpy_avx2...` 같은 실제 구현 주소로 채워져 있는 걸 볼 수 있다(정적 바이너리든 `main` 진입 이후든 이미 resolve가 끝난 상태이기 때문).

## 명령어/단축키
```bash
readelf -s ./libc.so.6 | grep IFUNC
readelf -r ./libc.so.6 | grep IRELATIVE
nm -D ./libc.so.6 | grep -i memcpy
objdump -R ./libc.so.6 | grep -i memcpy
```

## 출력 해석
- `readelf -s`에서 타입 칸이 `IFUNC`인 심볼은 "함수 자체"가 아니라 "리졸버"를 가리키는 심볼이다. 실행 시점에는 이 심볼 주소가 아니라 리졸버가 반환한 주소가 실제로 쓰인다.
- `readelf -r`의 `IRELATIVE` 줄에서 심볼 이름 칸이 비어 있는 건 정상이다 — 이 재배치는 심볼 룩업이 아니라 함수 호출로 처리되기 때문이다.
- GDB에서 `break memcpy`가 실제로는 리졸버가 고른 구체적인 구현부에서 멈추는 것은 버그가 아니라, GDB가 심볼 테이블을 통해 이미 resolve된 최종 주소를 인식하고 있다는 뜻이다.

## 흔한 실수
- IFUNC를 "난독화" 또는 "패커가 심어놓은 트릭"으로 오해하는 것 — 이는 glibc의 표준 성능 최적화 기법이며 대부분의 최신 리눅스 배포판 libc에 기본적으로 들어있다.
- `readelf -r`에서 `IRELATIVE` 재배치를 일반 데이터 재배치(`R_X86_64_RELATIVE`)와 혼동하는 것 — `RELATIVE`는 "베이스 주소 + addend"를 그대로 쓰지만, `IRELATIVE`는 addend 위치의 값을 함수로 호출한 결과를 쓴다는 점이 결정적으로 다르다.
- 정적 링크 바이너리에는 IFUNC가 없을 거라고 가정하는 것 — 정적 바이너리도 `__libc_csu_irel`류의 자체 초기화 루틴으로 IFUNC 리졸빙을 수행하므로 여전히 존재한다.
- 커스텀 디스어셈블러나 스크립트로 GOT를 그냥 "주소값 나열"로만 파싱하면서 IRELATIVE 슬롯의 의미(함수 호출 결과)를 놓치는 것.

## 막혔을 때 다음 체크
- PLT/GOT 기본 동작 자체가 헷갈린다면 → REV-0100 PLT와 GOT 기초
- Dynamic Linking 전반의 흐름이 궁금하다면 → REV-0101 Dynamic Linking과 Import 함수 추적
- 재배치 타입을 `objdump`로 더 폭넓게 읽는 법이 궁금하다면 → REV-0682 objdump로 relocation 엔트리 읽는 법
- CPU 기능 감지에 쓰이는 `AT_HWCAP`이 auxv의 어디에 있는지 궁금하다면 → REV-0677 ELF Auxiliary Vector(auxv) 개요

## 미니 예제
```c
// glibc 내부 개념을 단순화한 예시 (실제 glibc 코드는 매크로로 더 복잡함)
static void *resolve_memcpy(void) {
    if (__builtin_cpu_supports("avx2"))
        return memcpy_avx2;
    return memcpy_sse2;
}

void *memcpy(void *, const void *, size_t)
    __attribute__((ifunc("resolve_memcpy")));
```
```bash
$ readelf -s ./a.out | grep memcpy
    45: 0000000000001149    17 IFUNC  GLOBAL DEFAULT   14 memcpy
$ readelf -r ./a.out | grep IRELATIVE
000000004018  000000000025 R_X86_64_IRELATIVE                    1149
```
`Addend`/오프셋 칸의 `1149`가 바로 `resolve_memcpy` 함수의 주소이며, 로더는 프로그램 시작 시 이 주소를 함수처럼 호출해 그 반환값(`memcpy_avx2` 또는 `memcpy_sse2`의 주소)을 GOT 슬롯 `0x4018`에 채워 넣는다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0682 — objdump로 relocation 엔트리 읽는 법
- REV-0677 — ELF Auxiliary Vector(auxv) 개요

## 출처/검증
- IFUNC 메커니즘(STT_GNU_IFUNC, 리졸버 함수, CPU 기능별 함수 선택)과 `R_X86_64_IRELATIVE` 재배치의 의미: MaskRay "GNU indirect function" 기술 블로그 및 LLVM `R_*_IRELATIVE` 구현 리뷰(reviews.llvm.org D15235) 기준.
- `readelf -r`/`objdump -R`에서 IRELATIVE 항목이 심볼 이름 없이 addend 자리에 리졸버 주소를 담는 형식: 다수의 실측 readelf/objdump 출력 예시(공개 이슈 트래커, 기술 블로그) 기준.
- 정적 바이너리에서 `__libc_csu_irel`을 통한 IFUNC 처리: glibc `csu/libc-start.c` 및 관련 소스 구조 기준 (2026-09-08 검증).
