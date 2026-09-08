---
id: REV-0448
title: "memcpy가 SIMD 명령으로 인라인되는 패턴"
slug: "rev-0448-memcpy-simd-pattern"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - memcpy
  - memmove
  - SIMD memcpy
  - MOVUPS 복사
  - MOVDQU 복사
  - REP MOVSB
  - ERMSB
  - 버퍼 복사 패턴
  - 구조체 복사 어셈블리
aliases:
  - memcpy가 안 보임
  - call memcpy 대신 이상한 xmm 코드
  - 구조체 대입이 movups로 바뀜
  - rep movsb가 뭔지 모르겠음
symptom_keywords:
  - movups가 두 번 나오는데 로드와 저장처럼 보임
  - rep movsb가 큰 버퍼를 복사하는 것 같음
  - memcpy 함수 이름이 안 보이는데 값이 그대로 옮겨짐
  - 구조체 대입 한 줄이 여러 mov로 펼쳐짐
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`memcpy(dst, src, len)`도 `memset`(REV-0447)과 마찬가지로 길이가 상수로 확정되면 함수 호출 없이 `MOVUPS/MOVDQU`로 소스를 로드해서 목적지에 그대로 저장하는 SIMD 페어(load+store) 반복, 또는 큰/가변 길이라면 `REP MOVSB`로 직접 펼쳐지며, 구조체 대입문(`*dst = *src;`)도 정확히 같은 패턴으로 컴파일된다.

## 언제 검색해야 하나
- `memcpy` 호출이 있어야 할 것 같은데 디스어셈블리에 `call memcpy`가 안 보이고 `movups xmm0, [rsi]` 다음 곧바로 `movups [rdi], xmm0` 같은 로드+저장 쌍이 반복될 때
- `rep movsb`/`rep movsd`/`rep movsq`가 큰 배열이나 구조체를 통째로 옮기는 것처럼 보일 때
- 구조체 대입(`struct_a = struct_b;`)이나 배열 복사 코드가 함수 호출 없이 여러 줄의 `MOV`/`MOVUPS`로 풀려 있을 때
- `memcpy`와 `memmove`의 차이(겹치는 영역 처리)가 어셈블리에서 어떻게 드러나는지 궁금할 때

## 핵심 개념

### 로드 + 스토어 쌍이 memcpy의 본질
`memcpy`가 하는 일은 결국 "소스의 N바이트를 읽어서(load) 목적지에 그대로 쓴다(store)"는 것뿐이다. 길이가 컴파일 시점에 확정되고 크지 않으면(대략 수십~수백 바이트 이하, 정확한 임계값은 컴파일러/타겟 CPU에 따라 다름), 컴파일러는 `call memcpy` 대신 SIMD 레지스터를 매개로 한 로드+스토어 쌍을 필요한 만큼 반복해서 그 자리에 박아 넣는다.
```asm
movups  xmm0, [rsi]        ; 소스에서 16바이트 로드
movups  [rdi], xmm0        ; 목적지에 16바이트 저장
movups  xmm0, [rsi+10h]    ; 다음 16바이트
movups  [rdi+10h], xmm0
```
정수 XMM 계열(`MOVDQA`/`MOVDQU`, REV-0389)이나 AVX가 켜진 빌드에서는 `VMOVDQU ymm0, [rsi]`로 32바이트씩 옮기기도 한다. 아주 작은 크기(1, 2, 4, 8바이트)라면 SIMD조차 필요 없이 그냥 정수 레지스터로 `mov rax, [rsi]` → `mov [rdi], rax` 한 쌍으로 끝난다 — 이 경우가 사실 가장 흔하다(작은 구조체 대입, `int`/`long` 필드 복사 등).

### 정렬(Alignment)에 따른 명령 선택
- 목적지/소스 주소가 모두 16바이트 정렬이 보장되면 `MOVAPS`/`MOVDQA`(정렬 필요, REV-0386/REV-0389)를 쓴다 — 정렬이 어긋난 주소에 쓰면 `#GP` 예외가 발생하므로, 컴파일러는 정렬을 100% 확신할 때만 이 명령을 고른다.
- 정렬을 보장할 수 없으면 `MOVUPS`/`MOVDQU`(비정렬, REV-0387)를 쓴다 — 느릴 수 있지만 항상 안전하다. 실무에서는 스택/힙 버퍼의 정렬을 컴파일러가 확신하기 어려운 경우가 많아 `MOVUPS/MOVDQU`가 더 자주 보인다.

### 큰 크기 또는 런타임 길이 — REP MOVSB
길이가 크거나 런타임에만 알 수 있으면(`memcpy(dst, src, n)`에서 `n`이 변수), SIMD 언롤 대신 문자열 명령 `REP MOVSB`(1바이트씩)/`REP MOVSD`(4바이트씩)/`REP MOVSQ`(8바이트씩)를 쓴다(REV-0080, REV-0081 참고).
```asm
mov     rsi, src
mov     rdi, dst
mov     rcx, n
rep movsb
```
최신 x86 CPU(Ivy Bridge 이후 Intel, 이후 세대 AMD)는 **ERMSB(Enhanced REP MOVSB)** 기능을 지원해서, 크기가 큰 경우 이 문자열 명령이 SIMD 언롤/수동 루프보다 오히려 빠르다. 그래서 `memcpy`의 실제 libc 구현체(glibc `memcpy`, Windows CRT `memcpy`)도 내부적으로 크기별 임계값에 따라 SIMD 루프와 `REP MOVSB`를 섞어 쓴다 — 컴파일러가 인라인할 때도 같은 전략을 쓰는 것으로 이해하면 된다.

### memcpy vs memmove — 방향과 겹침
`memcpy`는 소스/목적지 영역이 **겹치지 않는다고 가정**하고 항상 앞에서 뒤로(낮은 주소 → 높은 주소) 복사한다. 반면 `memmove`는 겹치는 영역도 안전하게 처리해야 하므로, 목적지가 소스보다 뒤에 있으면(즉 `dst > src`이고 겹치면) **뒤에서 앞으로** 복사한다. 이 방향 제어는 x86에서 방향 플래그(DF, EFLAGS의 한 비트)로 표현된다.
- `CLD`(Clear Direction Flag): DF=0, RSI/RDI가 매 반복 후 **증가** — 정방향 복사. `MOVSB` 등이 이 상태로 실행된다.
- `STD`(Set Direction Flag): DF=1, RSI/RDI가 매 반복 후 **감소** — 역방향 복사. `memmove`가 겹치는 뒤쪽 이동을 처리할 때 이 방식을 쓸 수 있다.

컴파일러가 인라인한 `memcpy`는 항상 정방향(단순 SIMD 로드+스토어 나열)이라 DF를 신경 쓸 필요가 거의 없지만, `memmove` 인라인이나 라이브러리 구현을 볼 때는 `std`/`cld` 명령이나 방향 판단 분기(목적지·소스 주소 비교 후 `jae`/`jb`로 정방향/역방향 루프를 고르는 코드)가 앞에 붙는지 확인해야 한다.

### 레지스터 효과와 플래그
- `MOVUPS`/`MOVUPD`/`MOVDQA`/`MOVDQU`는 **플래그를 변경하지 않는다.**
- `REP MOVSB/MOVSD/MOVSQ`도 EFLAGS(ZF, CF 등 산술 플래그)는 바꾸지 않지만, 매 반복마다 RCX(카운터)가 감소하고 RSI/RDI가 DF 방향에 따라 증가/감소한다는 점이 부수 효과다. `REP` 자체는 RCX가 0이 될 때까지 반복하는 접두사이며, 조건부 반복(`REPE`/`REPNE`)과 달리 ZF를 검사하지 않는다.
- signed/unsigned 구분은 `memcpy`에는 의미가 없다 — 바이트 단위 원시 복사이므로 데이터의 타입 해석과 무관하다.

## 화면/코드에서 보이는 징후
```asm
; 32바이트 고정 크기 복사 (SSE)
movups  xmm0, [rsi]
movups  [rdi], xmm0
movups  xmm0, [rsi+10h]
movups  [rdi+10h], xmm0
```
```asm
; 8바이트 이하의 작은 구조체 복사는 정수 레지스터로 끝남
mov     rax, [rsi]
mov     [rdi], rax
```
```asm
; 큰 크기, REP MOVSB (ERMSB)
lea     rsi, [rbp-400h]
lea     rdi, [rbp-800h]
mov     ecx, 400h
rep movsb
```
```asm
; memmove가 겹침을 확인 후 방향을 고르는 전형적인 분기
cmp     rdi, rsi
jae     copy_backward
; ... 정방향 복사 ...
jmp     done
copy_backward:
; ... 역방향 복사 (rdi/rsi를 끝에서부터, std 사용 또는 감소 인덱스) ...
done:
```

## 가장 먼저 할 것
1. 로드(`movups xmm, [src]`)와 스토어(`movups [dst], xmm`)가 짝을 이루는지 확인한다 — 소스 레지스터와 목적지 레지스터가 다르면 memcpy류(복사), 목적지 하나만 반복되면 memset류(REV-0447, 채우기)다.
2. 복사되는 총 길이를 계산한다(반복 오프셋 개수 × 16, 또는 `REP` 앞 카운터 값).
3. 소스/목적지 주소가 겹칠 가능성이 있는지 확인한다 — 겹친다면 `memmove` 의미론(겹침-안전 복사)이 필요했을 자리인데 단순 `memcpy` 패턴이 쓰였다면 버그 가능성을 의심한다.

## 단계별 절차

**1) 소스/목적지 레지스터 구분**

`movups xmm0, [X]` 줄의 `X`가 소스, `movups [Y], xmm0` 줄의 `Y`가 목적지다. 두 레지스터가 프로그램의 어떤 버퍼를 가리키는지(지역 배열, 함수 인자, 힙 포인터) 각각 위쪽에서 추적한다.

**2) 복사 길이 계산**

반복되는 `movups`/`mov` 쌍의 오프셋 최대값 + 오퍼랜드 크기가 곧 전체 길이다. `REP MOVSx` 형태면 `mov ecx, N`의 N이 (MOVSB 기준) 바이트 수 그 자체다.

**3) memcpy vs memmove 판별**

복사 직전에 `cmp dst, src` 후 대소 비교로 분기하는 코드가 있으면 겹침을 검사하는 `memmove` 스타일이다. 그런 분기 없이 바로 로드+스토어가 나열되면 컴파일러가 "겹치지 않는다"고 확신한 `memcpy`다.

**4) IDA/Ghidra 재인식 결과와 비교**

F5 디컴파일 결과가 `memcpy(dst, src, N)`으로 다시 요약되는지 확인한다. 재인식이 실패하면 XMM 로드/스토어가 그대로 나열되어 나오므로, 수동으로 "이 블록은 N바이트 복사"라고 주석을 남긴다.

## 명령어/단축키
- IDA: `F5`(디컴파일), `;`(코멘트), Xrefs to(`X`)로 이 코드가 어떤 필드 대입/함수 인자 준비인지 상위 함수에서 확인
- Ghidra: Decompile 창 자동 재인식 확인, Listing에서 `movups`/`movdqu` 연속 블록 강조
- x64dbg/GDB: 목적지 버퍼에 write 하드웨어 브레이크포인트를 걸어 실제로 복사되는 바이트 수와 값을 실행 중 확인

## 출력 해석
- IDA가 `memcpy(dest, src, size)`로 재인식하면, 실제로는 함수 호출이 아니라 SIMD/정수 로드-스토어 나열이 원본이었다는 것을 기억한다.
- `rep movsb`만 있고 `std`가 없으면 정방향(낮은 주소→높은 주소) 복사다. `std` 또는 역순 오프셋 접근(감소하는 인덱스)이 보이면 겹침을 고려한 역방향 복사(memmove 스타일)다.
- 소스와 목적지 버퍼 크기가 다르게 계산된다면(예: 목적지가 소스보다 작음) 오버플로우 버그 후보다.

## 흔한 실수
- `movups` 로드+스토어 쌍을 "암호화 라운드"나 "해시 믹싱"으로 오판하는 것 — 소스/목적지가 항상 같은 오프셋 간격(16바이트)으로 나란히 진행하고 중간에 XOR/ADD 같은 변형이 전혀 없다면 그냥 복사다.
- `rep movsb`를 보고 무조건 "느린 레거시 코드"라고 무시하는 것 — ERMSB를 지원하는 CPU에서는 컴파일러가 의도적으로 고른 빠른 경로일 수 있다.
- `memcpy`와 `memmove`를 어셈블리 레벨에서 구분하지 않고 아무 겹침 버퍼에나 단순 로드+스토어 패턴을 가정하는 것 — 겹치는 영역에 `memcpy` 의미론(정방향만 가정)을 썼다면 원본 소스 코드 자체의 버그일 수 있으니, 실제로 겹침 검사 분기가 있는지 반드시 먼저 확인한다.
- 구조체 대입(`a = b;`)이 함수 호출 없이 이런 SIMD 패턴으로 나오는 것을 보고 "이상하다"고 여기는 것 — 구조체/배열 값 복사는 C/C++에서 컴파일러가 내부적으로 `memcpy`와 동일하게 처리하는 것이 표준적인 동작이다.

## 막혔을 때 다음 체크
- 이게 `memcpy`가 아니라 `memset`일 수도 있다고 헷갈리면 → REV-0447로 이동해서 목적지만 반복되는지(스토어만 있고 로드가 없는지) 다시 확인.
- 복사 길이가 어디서 오는지 못 찾겠다면 → `REP` 앞의 `mov ecx, ...` 또는 SIMD 반복 오프셋 최댓값을 다시 센다.
- 정렬 관련 크래시(`MOVAPS`/`MOVDQA`에서 예외)가 의심되면 → 소스/목적지 주소가 실제로 16바이트 정렬인지, 혹은 컴파일러가 잘못 `MOVUPS` 대신 `MOVAPS`를 썼을 리는 없으므로 다른 원인(버퍼 오버플로우로 주소 자체가 깨졌을 가능성)을 의심한다.

## 미니 예제

**예제 1 — 고정 크기 구조체 복사**
```c
struct Point { int x, y; };
Point b = a;   // 8바이트
```
```asm
mov     rax, [rbp+a]
mov     [rbp+b], rax
```

**예제 2 — 32바이트 버퍼 복사, SIMD 언롤**
```c
memcpy(dst, src, 32);
```
```asm
movups  xmm0, [rsi]
movups  [rdi], xmm0
movups  xmm0, [rsi+10h]
movups  [rdi+10h], xmm0
```

**예제 3 — 가변 길이, REP MOVSB**
```c
void copy_n(char *dst, const char *src, size_t n) {
    memcpy(dst, src, n);
}
```
```asm
; SysV x64: rdi=dst, rsi=src, rdx=n
mov     rcx, rdx
rep movsb
```

**예제 4 — memmove 겹침 검사 분기**
```c
memmove(buf + 2, buf, 10);   // 목적지가 소스보다 뒤, 겹침
```
```asm
lea     rdi, [buf+2]
mov     rsi, buf
cmp     rdi, rsi
jb      forward_copy      ; dst < src면 정방향도 안전
; dst > src && 겹침 → 역방향 복사 필요
std                        ; 방향 플래그 설정 (뒤에서 앞으로)
...
cld                        ; 복사 후 관례적으로 원상 복구
```

## 관련 글
- REV-0447 — memset이 SIMD 명령으로 인라인되는 패턴
- REV-0449 — strlen이 인라인 최적화되는 패턴
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0081 — MOVS MOVSB MOVSW MOVSD MOVSQ
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `MOVUPS`/`MOVDQU`/`MOVAPS`/`MOVDQA`의 정렬 요구사항과 플래그 미변경: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2 각 명령어 항목 기준.
- `REP MOVSB` 및 Enhanced REP MOVSB(ERMSB) 동작: Intel SDM Volume 1 "String Operations" 및 Intel Optimization Reference Manual 기준.
- `memcpy`(겹치지 않음 가정)와 `memmove`(겹침 허용) 의미론 차이: ISO C 표준 라이브러리 명세(`string.h`) 기준.
- 방향 플래그(DF)와 `CLD`/`STD` 동작: Intel SDM Volume 1, EFLAGS 및 "CLD/STD" 명령어 항목 기준.
