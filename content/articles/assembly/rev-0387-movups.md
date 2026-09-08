---
id: REV-0387
title: "MOVUPS: 비정렬 XMM 레지스터 이동"
slug: "rev-0387-movups"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - movups
  - MOVUPS
  - movups instruction
  - movups 명령어
  - unaligned move
  - 비정렬 이동
  - xmm
  - XMM
  - SSE
  - "movups xmm0"
  - packed single precision
  - memcpy simd
  - 정렬 안된 메모리
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - movups 뭐임
  - movups가 뭐죠
  - movups 명령
  - MOVUPS 명령어
  - movaps movups 차이
  - 정렬 안된 xmm 이동
symptom_keywords:
  - movups랑 movaps 차이를 모르겠음
  - memcpy가 movups로 되어있음
  - 정렬 안된 버퍼인데 크래시가 안남
  - simd memcpy 패턴
last_verified: "2026-09-08"
---

## 한 줄 요약
`MOVUPS`는 `MOVAPS`와 완전히 같은 데이터(128비트, 4개의 single-precision float)를 옮기지만, 메모리 오퍼랜드가 **16바이트 정렬이 안 되어 있어도 예외 없이 동작**하는 버전이다.

## 언제 검색해야 하나
- `movups`와 `movaps`가 코드 안에 섞여 있어서 왜 어떤 곳은 U(unaligned), 어떤 곳은 A(aligned)를 쓰는지 궁금할 때
- `memcpy`/`memmove` 구현이나 컴파일러가 생성한 복사 루프가 `movups`로 되어 있는 이유를 알고 싶을 때
- 임의의 크기/오프셋을 갖는 버퍼(정렬 보장이 없는 `malloc` 반환값 + 임의 오프셋 등)를 다루는 SIMD 코드를 분석할 때

## 핵심 개념

### Intel 문법과 MOVAPS와의 관계
```
MOVUPS xmm_dest, xmm/m128_src
MOVUPS xmm/m128_dest, xmm_src
```
`U`는 **Unaligned**를 의미한다. 옮기는 데이터의 종류(4개의 32비트 float, packed single-precision)와 크기(128비트)는 [MOVAPS](rev-0386-movaps.md)와 완전히 동일하다. 차이는 오직 **메모리 정렬 요구사항 하나뿐**이다:
- `MOVAPS`: 메모리 주소가 16바이트 경계가 아니면 #GP 예외 발생.
- `MOVUPS`: 정렬 여부와 무관하게 항상 정상 동작.

### 왜 항상 MOVUPS만 쓰지 않는가 — 성능 트레이드오프
"항상 안전한 MOVUPS만 쓰면 되지 않나?"라고 생각할 수 있지만, 리버싱 관점에서 알아둘 점은 구형 CPU에서는 `MOVUPS`가 정렬된 주소에 대해서도 `MOVAPS`보다 느릴 수 있었다는 점이다(최신 CPU에서는 정렬된 경우 사실상 성능 차이가 거의 없다). 그래서 컴파일러는 **주소가 정적으로 16바이트 정렬됨이 증명 가능한 경우에만 `MOVAPS`를 쓰고, 그렇지 않으면(런타임에 임의의 포인터가 들어올 수 있는 경우) 안전한 `MOVUPS`를 선택**한다. 즉 어떤 명령이 쓰였는지 자체가 "컴파일러가 이 메모리의 정렬 상태를 정적으로 확신했는가"를 알려주는 단서가 된다.

### 레지스터/메모리 효과, 플래그, 스택 변화
`MOVAPS`와 동일하다: 데이터는 그대로 복사(해석 없음), EFLAGS 변화 없음, 스택/RIP에 직접적 영향 없음.

### 컴파일러 패턴 — memcpy와 문자열 복사
현대 컴파일러의 `memcpy`/`memmove` 인라인 구현이나 libc 내부 구현은 크기가 큰 블록을 복사할 때 정렬을 보장할 수 없는 시작 주소에 대해 `movups`(또는 정수 버전인 [MOVDQU](rev-0389-movdqa-movdqu.md))를 반복 사용해 16바이트씩 복사한다. 즉 **C 코드에서 `memcpy(dst, src, n)`를 호출했을 뿐인데, 디스어셈블리에는 `movups` 루프가 나타나는 것이 매우 흔하다.**

### IDA/Ghidra 디컴파일
`MOVAPS`와 마찬가지로 대부분 구조체 대입이나 `memcpy` 호출로 정리된다. 벡터화된 `memcpy` 루프는 종종 원본 함수 이름 없이 인라인된 형태로만 보이므로, `movups`가 몰려 있는 루프를 보면 "이건 사실상 memcpy다"라고 해석하는 것이 실용적이다.

### 최신 CPU에서의 성능 차이 축소
초기 SSE 시절(Pentium III~초기 Core 시대)에는 `MOVUPS`가 정렬된 주소에 대해서도 `MOVAPS`보다 눈에 띄게 느렸지만, Nehalem(2008년경) 이후의 x86 CPU에서는 주소가 실제로 정렬되어 있기만 하면 두 명령의 실행 속도 차이가 거의 사라졌다. 그럼에도 컴파일러가 여전히 정렬을 증명할 수 있을 때 `MOVAPS`를 선호하는 이유는, `MOVAPS`가 "이 메모리는 정렬되어 있어야 한다"는 사실을 코드 자체에 문서화해 주는 효과도 있고, 정렬이 실제로 깨졌을 때 조용히 넘어가지 않고 크래시로 즉시 드러내 버그를 조기에 잡을 수 있기 때문이다. 즉 `MOVAPS`가 남아있는 코드를 보면 "이 지점의 메모리는 반드시 16바이트 정렬이어야 한다"는 하드웨어 수준의 assert로 이해해도 무방하다.

### x64dbg/GDB로 실습해보는 정렬 확인
의심되는 포인터가 있다면 디버거에서 `주소 AND 0xF`(x64dbg 계산기) 또는 `p $rax & 0xf`(GDB)를 실행해 결과가 0인지 바로 확인할 수 있다. 결과가 0이 아니면 `MOVAPS`로는 크래시가 나고 `MOVUPS`로는 정상 동작해야 한다 — 두 값을 비교해 두면 나중에 비슷한 크래시를 훨씬 빨리 진단할 수 있다.

## 화면/코드에서 보이는 징후
- `movups xmm0, [rsi]` / `movups [rdi], xmm0` 반복 — 정렬 미보장 블록 복사(memcpy류)
- 함수 인자로 받은 임의 포인터를 그대로 SIMD 소스로 쓰는 코드 — 거의 항상 `movups`
- 반대로 `movaps`만 쓰이면 컴파일러가 그 주소의 정렬을 정적으로 확신했다는 뜻

## 가장 먼저 할 것
1. 오퍼랜드 소스/목적지가 함수 인자(임의 포인터)에서 온 것인지, 컴파일러가 스택/전역에서 정렬을 보장한 지역 변수인지 확인한다.
2. 루프 형태라면 반복 카운트와 스텝(대개 16바이트씩)을 확인해 총 복사 크기를 역산한다.
3. 앞뒤에 산술 SIMD 명령이 없으면 순수 복사로 결론짓는다.

## 단계별 절차
**1) memcpy 루프 인식**
```asm
copy_loop:
    movups xmm0, [rsi+rcx]
    movups [rdi+rcx], xmm0
    add    rcx, 16
    cmp    rcx, rdx
    jl     copy_loop
```
→ `memcpy(rdi, rsi, rdx)`와 동일한 효과.

**2) MOVAPS와 MOVUPS 혼용 판단**
같은 함수 안에서 지역 변수(스택, 정렬 보장)는 `movaps`, 함수 인자로 받은 포인터는 `movups`로 처리되는 패턴을 찾으면 어떤 값이 "안전하다고 증명된" 데이터인지 구분할 수 있다.

## 명령어/단축키
- IDA/x64dbg/GDB의 XMM 레지스터 확인 방법은 [REV-0386 MOVAPS](rev-0386-movaps.md)와 동일하다.
- GDB/Pwndbg: `x/16xb $rsi`로 원본 메모리를 바이트 단위로 미리 확인해 정렬 여부(주소 하위 4비트가 0인지)를 직접 계산할 수 있다.

## 출력 해석
- 디버거에서 `movups` 실행 전후 XMM 레지스터 값이 소스 메모리와 정확히 일치하면 단순 로드/스토어임을 바로 확인 가능하다.
- 정렬이 실제로 안 맞아도 `movups`는 예외 없이 정상 진행되므로, 크래시가 안 난다고 해서 정렬된 데이터라고 오해하면 안 된다.

## 흔한 실수
- `movups`가 보이면 무조건 "정렬 문제를 피하려고 일부러 쓴 특별한 코드"라고 과대 해석하는 것 — 대부분은 컴파일러가 정렬을 보장할 수 없을 때 기본으로 선택하는 안전한 선택지일 뿐이다.
- `MOVAPS`와 `MOVUPS`가 "다른 데이터를 옮긴다"고 착각하는 것 — 옮기는 데이터의 의미와 크기는 완전히 동일하고, 오직 정렬 요구사항만 다르다.
- `movups` 루프를 보고 원본 C 함수 이름(`memcpy` 등)을 못 찾아서 당황하는 것 — 컴파일러가 인라인했을 가능성이 높으니 동작 패턴(16바이트씩 순차 복사)으로 판단한다.

## 막혔을 때 다음 체크
- 이 코드가 무슨 함수의 인라인인지 모르겠다면 → 반복 스텝이 16이고 산술 연산이 없는지 확인해 memcpy/memmove로 가정하고 분석을 진행.
- 정렬 문제로 크래시가 났는데 `movups`만 쓰였다면 → 크래시 원인은 다른 명령(`movaps`, `movdqa` 등)일 가능성을 다시 확인.

## 미니 예제

**예제 1 — memcpy의 SIMD 전개**
```c
memcpy(dst, src, 16);
```
```asm
movups xmm0, [rsi]   ; src (정렬 미보장)
movups [rdi], xmm0    ; dst
```

**예제 2 — 임의 오프셋을 갖는 구조체 필드 복사**
```c
struct Packed { char pad; float v[4]; } __attribute__((packed));
Vec4 out = p->v;  // p->v가 4바이트 오프셋이라 16정렬이 아님
```
```asm
movups xmm0, [rax+1]
movups [rcx], xmm0
```

**예제 3 — 큰 버퍼 복사 루프**
```asm
copy_loop:
    movups xmm0, [rsi+rcx]
    movups [rdi+rcx], xmm0
    add    rcx, 16
    cmp    rcx, size
    jb     copy_loop
```

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0388 — MOVAPD와 MOVUPD: Double Precision SIMD 이동

## 출처/검증
- `MOVUPS` 명령어 동작과 정렬 예외 없음: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A/2B, "MOVUPS—Move Unaligned Packed Single-Precision Floating-Point Values" 섹션 기준 (2026-09-08 검증).
- 정렬 여부에 따른 SIMD 이동 명령 선택 관행과 컴파일러의 memcpy 벡터화: Agner Fog, "Optimizing subroutines in assembly language" 기준.
