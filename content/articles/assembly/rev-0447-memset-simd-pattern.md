---
id: REV-0447
title: "memset이 SIMD 명령으로 인라인되는 패턴"
slug: "rev-0447-memset-simd-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - memset
  - SIMD memset
  - XMM 초기화
  - PXOR 제로화
  - MOVAPS 반복 저장
  - REP STOSB
  - 버퍼 초기화 패턴
  - zero fill
  - 배열 0으로 채우기
aliases:
  - memset이 안 보임
  - 배열 초기화 코드가 이상함
  - call memset 대신 이상한 xmm 코드
  - 버퍼 제로화 어셈블리
symptom_keywords:
  - pxor xmm0 xmm0 다음에 movaps가 반복됨
  - rep stosd가 배열 초기화처럼 보임
  - memset 함수 이름이 안 보이는데 값이 다 0으로 채워짐
  - 작은 버퍼인데 call 없이 바로 값이 채워짐
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`memset(buf, val, len)`는 컴파일 시점에 `len`(과 종종 `val`)이 상수로 확정되면 함수 호출 없이 `PXOR`/`MOVAPS`/`MOVUPS` 같은 SIMD 명령이나 `REP STOSB/STOSD/STOSQ`로 직접 펼쳐지는 경우가 매우 흔하며, 이런 코드는 겉보기에 `memset`이라는 이름이 전혀 안 보여도 "버퍼를 특정 값으로 채우는" 로직으로 알아봐야 한다.

## 언제 검색해야 하나
- 소스나 디컴파일에 `memset(...)` 호출이 있어야 할 것 같은데 실제 디스어셈블리에는 `call memset`이 안 보이고 대신 `pxor xmm0, xmm0` 다음에 `movaps [rax], xmm0`가 반복될 때
- `rep stosb` 또는 `rep stosd` 명령이 배열/구조체를 초기화하는 것처럼 보일 때
- 지역 배열을 선언하자마자(`char buf[64] = {0};`) 이상한 XMM 코드 블록이 바로 뒤따를 때
- IDA/Ghidra 디컴파일 결과에 `memset(v1, 0, 0x40)`처럼 자동으로 다시 인식되어 나오는데, 실제 어셈블리와 왜 다르게 보이는지 이해하고 싶을 때

## 핵심 개념

### 왜 컴파일러가 memset 호출을 없애버리는가
`memset`은 함수 호출 오버헤드(REV-0071의 `CALL` — 인자 세팅, 스택 정렬, 반환 주소 push/pop)가 있다. 크기(`len`)가 컴파일 시점 상수이고 그 값이 크지 않으면, 컴파일러는 이 호출을 없애고 **그 자리에 직접 채우는 명령을 삽입(inline)**하는 것이 훨씬 빠르다고 판단한다. 이것은 REV-0449(strlen 인라인)와 REV-0448(memcpy SIMD 인라인)에서도 똑같이 나타나는 컴파일러 최적화의 큰 흐름 중 하나로, 표준 라이브러리의 "잘 알려진 함수"를 컴파일러가 직접 이해하고 있다는 뜻에서 이를 **빌트인 함수 인식(builtin recognition)** 이라고 부른다(GCC/Clang은 `-fbuiltin`, MSVC는 인트린식 인식으로 이 최적화를 수행한다).

### 값이 0일 때 — 가장 흔한 경우
버퍼를 0으로 채우는 코드(`memset(buf, 0, N)`, 또는 `= {0}` 초기화)가 압도적으로 많기 때문에 컴파일러는 이 경우를 특히 잘 최적화한다.
1. **제로 레지스터 준비**: `pxor xmm0, xmm0` — XMM 레지스터를 자기 자신과 XOR해서 0으로 만든다(REV-0392, 정수 레지스터의 `xor eax, eax`와 같은 관용구, REV-0057 참고). SSE2 이상에서 표준적으로 쓰이는 "레지스터 제로화" 트릭이다.
2. **16바이트씩 반복 저장**: `movaps [rdi], xmm0` / `movaps [rdi+16], xmm0` ... 정렬이 보장되면 `MOVAPS`(정렬, REV-0386), 보장 안 되면 `MOVUPS`(비정렬, REV-0387)를 쓴다. AVX가 활성화된 빌드라면 32바이트(YMM) 단위 `VMOVDQU`로 두 배씩 채우기도 한다.
3. **꼬리 처리**: 전체 길이가 16의 배수가 아니면 마지막에 남는 바이트를 `MOV`(1/2/4/8바이트) 명령 몇 개로 따로 채운다. 예를 들어 20바이트를 채운다면 16바이트를 XMM으로, 나머지 4바이트를 `mov dword ptr [rdi+16], 0`으로 처리한다.

### 값이 0이 아닐 때 — 값 복제(broadcast) 필요
`memset(buf, 'A', 32)`처럼 0이 아닌 1바이트 값을 채울 때는, 그 1바이트 값을 레지스터 전체에 **복제(broadcast)** 하는 과정이 먼저 필요하다.
- 정수 레지스터에서: `movzx eax, byte_value` 후 `imul eax, 0x01010101`(1바이트를 4바이트에 반복) 같은 트릭을 쓰거나, `mov al, val` → `mov ah, al` → `shl eax, 16` → `or eax, ...` 식으로 비트 조작해서 채운다.
- XMM 레지스터로: 8/16바이트 단위로 채워야 하면 `movd xmm0, eax`(정수 → XMM) 후 `pshufd xmm0, xmm0, 0`(4바이트 패턴을 16바이트 전체에 복제)로 XMM 레지스터 전체를 같은 패턴으로 채운 뒤, 앞서 설명한 `movaps`/`movups` 반복 저장으로 넘어간다.

### 큰 크기 또는 크기를 모를 때 — REP STOS
길이가 크거나(수백 바이트 이상) 컴파일 시점에 확정되지 않으면, SIMD 언롤 대신 문자열 명령 `REP STOSB`(1바이트씩) / `REP STOSD`(4바이트씩) / `REP STOSQ`(8바이트씩, x64)를 쓴다(REV-0080 REP 접두사, REV-0082 STOS 참고).
```asm
xor     eax, eax        ; 채울 값 (0)
mov     ecx, 100h       ; 반복 횟수(=바이트 수, STOSB 기준)
lea     rdi, [rbp-0x110] ; 목적지 버퍼
rep     stosb
```
최신 x86 CPU는 "Enhanced REP MOVSB/STOSB"(ERMSB) 기능을 지원해서, 이 문자열 명령이 예전만큼 느리지 않고 오히려 큰 버퍼에서는 SIMD 언롤보다 빠를 수 있다 — 그래서 컴파일러가 크기 임계값을 넘으면 SIMD 대신 `REP STOS`를 선택하는 것이다.

### 레지스터/메모리 효과와 플래그
- `PXOR`, `MOVAPS`, `MOVUPS`는 **플래그를 변경하지 않는다.** 정수 `XOR`(REV-0057)과 달리 SIMD 버전은 EFLAGS에 영향이 없다.
- `REP STOSB/STOSD/STOSQ`도 EFLAGS 플래그를 바꾸지 않지만, 방향 플래그(DF, `CLD`/`STD`로 설정)에 따라 RDI가 증가(`CLD`, 일반적) 또는 감소(`STD`, 드묾)한다. `REP` 계열은 실행할 때마다 RCX를 1씩 감소시키고 RCX가 0이 될 때까지 반복하며, RDI는 매 반복마다 오퍼랜드 크기만큼 증가/감소한다.
- 값이 부호 있는(signed) 타입이냐 없는(unsigned) 타입이냐는 `memset`에는 의미가 없다 — `memset`은 항상 `int` 인자의 **하위 1바이트**만 사용해서 채우기 때문에, `memset(buf, -1, N)`과 `memset(buf, 0xFF, N)`은 완전히 동일한 결과(모든 바이트가 `0xFF`)를 만든다는 점이 시그니처 상의 중요한 특징이다.

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays(IDA)와 Ghidra 모두 이런 SIMD 언롤 패턴을 다시 `memset(dest, 0, size)` 형태로 **재인식(pattern re-fold)** 해주는 경우가 많다 — 완전히 자동은 아니지만 흔한 크기(16, 32, 64바이트)에서는 잘 동작한다. 재인식이 안 되면 디컴파일 결과에 XMM 대입이 그대로 여러 줄 나열되므로, 사람이 "이건 memset이다"라고 직접 판단해야 한다.

## 화면/코드에서 보이는 징후
```asm
; 0으로 채우기, 32바이트, SSE
pxor    xmm0, xmm0
movaps  [rdi], xmm0
movaps  [rdi+10h], xmm0
```
```asm
; 값 'A'(0x41)로 채우기, 16바이트
movzx   eax, 41h
imul    eax, eax, 1010101h
movd    xmm0, eax
pshufd  xmm0, xmm0, 0
movups  [rdi], xmm0
```
```asm
; 큰 크기, REP STOSB
xor     eax, eax
mov     ecx, 400h
rep stosb
```
```asm
; 작은 고정 크기(8바이트 이하)는 그냥 MOV 하나로 끝나기도 함
mov     qword ptr [rbp-8], 0   ; memset(buf, 0, 8)과 동일한 효과
```

## 가장 먼저 할 것
1. `pxor`/`movaps`/`movups` 또는 `rep stosX` 블록을 발견하면, 목적지 레지스터(RDI, RAX, RCX 등)가 어떤 버퍼(지역 배열, 구조체, 힙 포인터)를 가리키는지 위쪽에서 확인한다.
2. 채워지는 값이 0인지 아닌지 확인한다(제로 레지스터를 만드는 `pxor`/`xor`가 있는지, 아니면 특정 상수를 복제하는지).
3. 채워지는 총 길이를 계산한다 — `movaps`가 몇 번 반복되는지 세거나(16바이트 × 횟수), `REP` 앞의 카운터 레지스터(RCX/ECX) 값을 확인한다.

## 단계별 절차

**1) 목적지와 길이 확인**

디스어셈블리에서 반복되는 `movaps [reg+offset], xmm0` 줄들의 offset을 보고 총 길이를 계산한다(예: `[rdi]`, `[rdi+0x10]`, `[rdi+0x20]` 세 번이면 48바이트). `REP STOS` 계열이면 `mov ecx, N` 줄의 N이 곧 길이(STOSB 기준) 또는 길이/4(STOSD), 길이/8(STOSQ)이다.

**2) 채워지는 값 확인**

`pxor xmm0, xmm0`나 `xor eax, eax`가 있으면 값은 0이다. `movzx`/`imul .., 0x01010101` 또는 `pshufd` 조합이 있으면 특정 1바이트 값이 반복 복제된 것이니, 그 원본 1바이트 값을 역추적한다.

**3) IDA/Ghidra 디컴파일과 대조**

F5(IDA)나 Ghidra 디컴파일 결과를 보고 `memset(...)`으로 이미 재인식됐는지 확인한다. 재인식이 안 됐다면 직접 "이 XMM 블록은 buf를 0으로 32바이트 채우는 memset과 동일하다"고 주석을 남긴다(IDA `;` 키로 커멘트 추가).

**4) 취약점 관점에서 재검토**

버퍼 크기와 채우는 길이가 일치하는지 확인한다. 길이 계산에 부호 있는 값이 잘못 쓰이거나(음수 길이를 `size_t`로 캐스팅해서 거대한 값이 되는 등), 스택 버퍼보다 큰 길이를 채우는 경우는 스택 오버플로우로 이어질 수 있다.

## 명령어/단축키
- IDA: `F5`(디컴파일, memset 재인식 확인), 명령 위에서 `;`(코멘트 달기), Regular expression 검색(`Alt+T`)으로 `pxor` 패턴 전체 찾기
- Ghidra: Decompile 창에서 자동 인식 결과 확인, Listing에서 `Search → For Instruction Patterns`로 SIMD 명령 블록 찾기
- x64dbg/GDB: 목적지 버퍼에 메모리 브레이크포인트(하드웨어 write breakpoint)를 걸어서 실제로 어떤 값이 얼마나 채워지는지 실행 중 확인 (`ba w` in x64dbg, `watch` in GDB)

## 출력 해석
- IDA가 `memset(v5, 0, 0x40)`처럼 재인식해서 보여주면, 이는 어셈블리의 PXOR/MOVAPS 시퀀스를 표준 라이브러리 호출 형태로 요약한 것 — 원래 `call memset`이 있었던 게 아니라 컴파일러가 인라인한 것이라는 사실을 잊지 않는다.
- `movaps`가 아니라 `movups`가 쓰였다면, 컴파일러가 이 버퍼의 정렬(alignment)을 16바이트로 보장할 수 없다고 판단했다는 뜻 — 스택 정렬이나 구조체 패딩을 다시 볼 단서가 될 수 있다.
- `rep stosb` 앞에 `cld` 명령이 있으면 방향 플래그를 "증가"로 명시적으로 설정한 것 — 표준적인 정방향 채우기다.

## 흔한 실수
- `pxor`/`movaps` 블록을 보고 "SIMD 연산 로직(암호화, 해시 등)"이라고 오판하는 것 — 목적지가 단순 반복 오프셋(`+0, +10h, +20h`)이고 항상 같은 XMM 레지스터를 쓴다면 그냥 초기화(memset)일 가능성이 매우 높다.
- `rep stosb`를 보고 무조건 "문자열 복사"라고 착각하는 것 — `STOS`는 **채우기(fill)**, `MOVS`는 **복사(copy)** 다. 이 둘은 목적지/소스 개수가 다르므로(STOS는 목적지만, MOVS는 목적지+소스) 명령어 이름을 정확히 구분해야 한다(REV-0448, REV-0082 참고).
- `memset(buf, 1, N)`이 `buf`를 정수 1로 채운다고 착각하는 것 — `memset`은 항상 **바이트 단위**로 채우므로 값은 1바이트(`0x01`)만 반복된다. 4바이트 정수 배열을 1로 초기화하고 싶다면 `memset`이 아니라 반복문이나 `std::fill`을 써야 하며, 이 차이를 모르고 작성된 실제 버그 코드도 흔하다.
- SIMD 언롤 길이 계산 시 `movaps` 반복 횟수를 잘못 세어 실제 버퍼 크기를 오판하는 것 — offset 값을 하나씩 정확히 확인해야 한다.

## 막혔을 때 다음 체크
- 값 복제(broadcast) 로직이 복잡해서 원래 1바이트 값을 못 찾겠다면 → `pshufd`/`imul ..., 0x01010101` 직전에 `movzx`/`mov`로 로드되는 원본 값을 찾는다.
- 이게 `memset`이 아니라 `memcpy`/`memmove`가 아닌지 헷갈리면 → 소스 레지스터(RSI 등)가 별도로 존재하는지 확인 — 있으면 REV-0448(memcpy SIMD 인라인 패턴)로 이동.
- 정렬 관련 크래시(`MOVAPS`에서 GP fault)가 의심되면 → 목적지 주소가 16바이트 정렬인지 계산해보고, 정렬이 깨졌다면 원래 소스에서 왜 그런지(구조체 패킹, 커스텀 얼로케이터 등) 확인.

## 미니 예제

**예제 1 — 스택 버퍼 0 초기화**
```c
char buf[32];
memset(buf, 0, sizeof(buf));
```
```asm
pxor    xmm0, xmm0
movaps  [rbp-20h], xmm0
movaps  [rbp-10h], xmm0
```

**예제 2 — 구조체 필드 값 채우기**
```c
memset(&header, 0xFF, sizeof(header));   // sizeof(header) == 8
```
```asm
mov     rax, 0FFFFFFFFFFFFFFFFh
mov     [rbp+header], rax
```
8바이트 이하로 작을 때는 컴파일러가 SIMD조차 쓰지 않고 그냥 한 번의 정수 `MOV`로 끝내버리는 경우가 매우 흔하다.

**예제 3 — 큰 버퍼, REP STOSD**
```c
int arr[256];
memset(arr, 0, sizeof(arr));   // 1024바이트
```
```asm
xor     eax, eax
lea     rdi, [rbp-400h]
mov     ecx, 100h        ; 256개(4바이트 단위이므로 STOSD 기준 256)
rep stosd
```

**예제 4 — 1바이트 값 채우기 후 IDA 재인식**
```c
memset(name, ' ', 20);
```
디컴파일 결과가 원본 코드와 거의 동일하게 `memset(name, 0x20, 20);`으로 재인식되어 나오는 경우가 많다 — 이때는 그냥 IDA를 믿고 넘어가도 된다.

## 관련 글
- REV-0448 — memcpy가 SIMD 명령으로 인라인되는 패턴
- REV-0449 — strlen이 인라인 최적화되는 패턴
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0082 — STOS STOSB STOSD STOSQ
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화

## 출처/검증
- `PXOR`/`MOVAPS`/`MOVUPS`가 EFLAGS를 변경하지 않는다는 내용: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 각 명령어 항목(Operation/Flags Affected) 기준.
- `REP STOSB/STOSD/STOSQ` 동작과 Enhanced REP MOVSB/STOSB(ERMSB): Intel SDM Volume 1, "String Operations"/"Fast-Strings" 관련 절 및 Intel Optimization Reference Manual 기준.
- `memset`이 값 인자의 하위 1바이트만 사용해서 채운다는 규격: ISO C 표준 라이브러리 명세(`string.h`, `memset`) 기준.
- 컴파일러의 memset 빌트인 인식(`-fbuiltin` 등)은 GCC/Clang 공식 문서의 빌트인 함수 최적화 설명 기준.
