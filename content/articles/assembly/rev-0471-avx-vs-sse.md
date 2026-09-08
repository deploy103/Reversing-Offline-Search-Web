---
id: REV-0471
title: "AVX 명령이 보일 때 SSE와 다른 점 개요"
slug: "rev-0471-avx-vs-sse"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - AVX
  - AVX2
  - AVX-512
  - SSE
  - VEX prefix
  - EVEX prefix
  - YMM
  - ZMM
  - XMM
  - vmovaps
  - vaddps
  - vectorization
  - 자동 벡터화
  - SIMD
aliases:
  - v로 시작하는 명령어
  - vmovaps 뭐임
  - ymm 레지스터
  - AVX SSE 차이
symptom_keywords:
  - v로 시작하는 명령어가 잔뜩 보임
  - ymm zmm 레지스터가 나옴
  - 명령어에 오퍼랜드가 3개 있음
  - SIMD 코드를 분석해야 함
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
AVX는 SSE의 확장판으로, 명령어 앞에 `v`가 붙고(`vmovaps`, `vaddps`) VEX/EVEX 프리픽스를 사용하며, 128비트 XMM 대신 256비트 YMM(AVX2)이나 512비트 ZMM(AVX-512) 레지스터로 **더 많은 데이터를 한 번에** 처리하고, `dst, src1, src2` 형태의 **3-오퍼랜드(non-destructive) 문법**을 쓴다는 점이 SSE와 가장 큰 차이다.

## 언제 검색해야 하나
- 디스어셈블리에 `vmovaps`, `vaddps`, `vpxor`, `vfmadd231ps` 처럼 `v`로 시작하는 명령어가 잔뜩 보일 때
- 레지스터 이름이 `ymm0`, `ymm1`처럼 낯설게 보일 때(REV-0386에서 다룬 `xmm`보다 큰 레지스터)
- `-O3 -mavx2` 등으로 컴파일된 바이너리를 열었더니 단순 루프가 알아보기 힘든 SIMD 코드로 바뀌어 있을 때
- 명령어 오퍼랜드가 SSE와 달리 3개(`vaddps ymm0, ymm1, ymm2`)로 되어 있어서 뭐가 목적지고 뭐가 원본인지 헷갈릴 때

## 핵심 개념

### AVX는 SSE의 "더 넓고, 더 깔끔한" 후속판
SSE(Streaming SIMD Extensions)는 128비트 XMM 레지스터 8~16개로 여러 데이터를 한 번에 처리(SIMD, Single Instruction Multiple Data)하는 명령어 집합이다(REV-0386 MOVAPS 참고). AVX(Advanced Vector Extensions)는 이를 확장해서:
- 레지스터 폭을 128비트(XMM) → **256비트(YMM)**, AVX-512에서는 **512비트(ZMM)** 까지 넓혔다. 예를 들어 32비트 float라면 SSE는 한 번에 4개, AVX2는 8개, AVX-512는 16개를 동시에 처리할 수 있다.
- 인코딩을 VEX(Vector Extension) 프리픽스로 바꾸고, AVX-512는 EVEX 프리픽스를 쓴다. 이 프리픽스 덕분에 명령어에 **세 번째 오퍼랜드**를 넣을 수 있게 됐다.

### 3-오퍼랜드(non-destructive) 문법의 의미
SSE는 오퍼랜드가 2개뿐이라 항상 목적지가 원본 중 하나를 덮어쓴다(destructive).
```asm
; SSE - xmm0이 파괴되어(overwrite) 결과가 됨
addps   xmm0, xmm1        ; xmm0 = xmm0 + xmm1  (원래 xmm0 값은 사라짐)
```
AVX는 오퍼랜드가 3개까지 가능해서 원본 값을 보존하면서 결과를 별도 레지스터에 쓸 수 있다(non-destructive).
```asm
; AVX - ymm1, ymm2는 그대로 남고 ymm0에만 결과가 들어감
vaddps  ymm0, ymm1, ymm2  ; ymm0 = ymm1 + ymm2   (ymm1, ymm2 둘 다 보존됨)
```
이는 컴파일러 입장에서 불필요한 `mov`(복사) 명령을 줄여주는 실질적인 이점이 있다 — SSE에서는 `xmm1`을 보존하려면 미리 다른 레지스터로 복사해둬야 했지만 AVX는 그럴 필요가 없다.

### VEX 인코딩과 "AVX-SSE 전환 페널티"
VEX로 인코딩된 명령어는 상위 비트(YMM의 상위 128비트)를 실행 시 명시적으로 처리(제로화 등)하기 때문에, 레거시 SSE 명령어와 VEX 인코딩 AVX 명령어를 뒤섞어 쓸 때 발생하던 "AVX/SSE 전환 페널티(transition penalty)"라는 성능 문제를 근본적으로 피할 수 있다. 컴파일러가 `-mavx`를 켜면 SSE 명령어까지도 VEX로 인코딩된 형태(`vmovaps xmm0, xmm1`처럼 `v`가 붙지만 128비트인 경우)로 바꿔서 생성하는 것도 이 때문이다.

### 리버싱에서 가장 중요한 태도: "이건 벡터화된 스칼라 로직일 뿐"
AVX/AVX2로 자동 벡터화(auto-vectorization)된 코드를 처음 보면 명령어가 낯설고 복잡해 보이지만, 본질은 **원래 스칼라(1개씩 처리하던) 알고리즘을 한 번에 4개/8개씩 처리하도록 데이터를 묶은 것**뿐이다. 예를 들어 `for (i=0;i<n;i++) arr[i] *= 2;`라는 단순 루프가 `-O3 -mavx2`에서는 한 번의 반복에서 8개의 `int`를 동시에 처리하는 `vpmulld`/`vpaddd` 코드로 바뀔 수 있다. 분석할 때는 "이 명령이 8개 레인(lane)에 대해 스칼라 버전과 동일한 연산을 병렬로 수행한다"고 생각하면 로직 자체는 어렵지 않게 이해할 수 있다.

### AVX-512와 마스크 레지스터(참고)
AVX-512(EVEX 프리픽스)는 512비트 ZMM 레지스터 외에도 `k0~k7` 마스크 레지스터를 도입해서, 벡터의 일부 레인만 선택적으로 연산/저장할 수 있게 했다(예: 배열 길이가 8의 배수가 아닐 때 남는 원소만 마스킹). CTF/일반 리버싱 바이너리에서는 AVX-512가 SSE/AVX2만큼 흔하지는 않지만, 최신 서버용 바이너리나 고성능 라이브러리(암호화, 압축)에서는 종종 등장한다.

## 화면/코드에서 보이는 징후
```asm
; SSE (128비트, 2-오퍼랜드, xmm0 파괴)
movaps  xmm0, [rdi]
addps   xmm0, xmm1
movaps  [rdi], xmm0
```
```asm
; AVX2 (256비트, 3-오퍼랜드, ymm 보존)
vmovdqa ymm0, [rdi]
vpaddd  ymm0, ymm0, [rsi]     ; 32비트 정수 8개를 동시에 덧셈
vmovdqa [rdi], ymm0
```
```asm
; AVX-512 (512비트, 마스크 레지스터 사용)
vmovdqa32 zmm0 {k1}, [rdi]    ; k1 마스크에 따라 선택적으로 로드
vpaddd    zmm0, zmm0, zmm1
```

## 가장 먼저 할 것
1. 명령어 앞에 `v`가 붙어있는지, 레지스터가 `xmm`/`ymm`/`zmm` 중 무엇인지 확인해서 SSE/AVX2/AVX-512 중 어떤 세대인지 파악한다.
2. 오퍼랜드가 3개(`vaddps dst, src1, src2`)면 `dst = src1 op src2`로 읽는다 — SSE의 2-오퍼랜드(`dst = dst op src`)와 규칙이 다르다는 점을 유념한다.
3. 낯선 명령이면 "이게 스칼라로는 무슨 연산이었을까"를 먼저 생각한다 — 대개 `+`, `-`, `*`, 비교, 셔플/재배열 중 하나의 벡터 버전이다.

## 단계별 절차
**1) 명령어를 스칼라 등가물로 환원해서 읽기**
`vpaddd ymm0, ymm1, ymm2`를 볼 때 "32비트 정수 8개를 각각 더하는 `for` 루프 한 스텝"이라고 머릿속에서 변환한다. `vaddps`(단정도 float 덧셈), `vmulps`(곱셈), `vpxor`(XOR), `vpcmpeqd`(정수 비교) 등도 마찬가지 방식으로 접근한다.

**2) 벡터 폭에 맞춰 루프 스텝 계산**
32비트 원소를 다루는 `ymm`(256비트)이면 한 번의 반복에서 8개 원소를 처리한다는 뜻이므로, 원래 스칼라 루프의 인덱스 증가값(`i++`)이 벡터화된 코드에서는 `i += 8`로 바뀐 것과 같다.

**3) IDA/Ghidra 디컴파일로 벡터 연산을 스칼라 C처럼 재구성된 결과 참고**
Hex-Rays와 최신 Ghidra는 일부 SIMD 패턴을 배열 연산이나 loop-vectorized 형태의 pseudo-C로 정리해서 보여주기도 한다(완벽하지 않을 수 있으니 원본 어셈블리와 교차 확인).

## 명령어/단축키
- IDA/Ghidra: 레지스터 뷰(Regs 창)에서 `ymm`/`zmm` 값을 16진수 바이트 배열로 확인 가능
- x64dbg: SIMD 레지스터 탭에서 `ymm0` 등을 byte/word/dword/float 단위로 다양하게 표시 전환 가능
- GDB/Pwndbg: `info registers ymm0` 또는 `p $ymm0.v8_int32`(gdb 버전에 따라 문법 차이 있음)로 벡터 레지스터를 원소 단위로 확인

## 출력 해석
- `vmovdqa`(정렬된 정수 이동), `vmovaps`/`vmovapd`(정렬된 float/double 이동)에서 접미사 `a`는 정렬(aligned) 메모리를 요구한다는 뜻이며, 정렬이 안 맞으면 예외가 발생한다. 정렬 요구가 없는 버전은 `u`(unaligned, `vmovdqu`, `vmovups`)다.
- `vp`로 시작하면 정수(packed integer) 연산, `v`만 있고 `p`가 없으면 대개 float 계열(`ps`=packed single, `pd`=packed double) 연산이다.
- 3-오퍼랜드에서 첫 번째가 항상 목적지(destination)다: `vaddps dst, src1, src2` → `dst = src1 + src2`.

## 흔한 실수
- AVX 코드를 보고 SSE와 완전히 다른 새로운 알고리즘이라고 지레 겁먹는 것 — 대부분 같은 스칼라 로직의 벡터화일 뿐이다.
- 3-오퍼랜드 문법에서 SSE 습관대로 "첫 번째 오퍼랜드가 파괴되면서 동시에 입력으로도 쓰인다"고 착각하는 것 — AVX는 목적지와 원본이 분리되어 있어 원본이 보존된다.
- 정렬 접미사(`a` vs `u`)를 무시하고 아무 메모리 주소나 넣어도 될 거라고 가정하는 것 — 정렬 안 된 메모리에 `vmovaps`를 쓰면 `#GP` 예외가 발생한다.
- AVX-512 마스크 레지스터(`{k1}`)를 그냥 무시하고 모든 레인이 항상 처리된다고 가정하는 것 — 마스크된 레인은 연산에서 제외되거나 0으로 채워질 수 있다.

## 막혔을 때 다음 체크
- 이 코드가 어떤 스칼라 루프에서 왔는지 감이 안 잡히면 → REV-0457/REV-0458(루프 형태 구분)로 원래 루프 구조부터 파악한 뒤 벡터화 이전 모습을 상상해본다.
- `-O0`으로 다시 컴파일한 결과와 비교하고 싶다면 → REV-0464(-O0과 -O2 비교) 절차를 그대로 적용한다(단, `-O0`은 AVX를 거의 안 씀).
- MOVAPS/MOVUPS 자체의 세부 동작이 궁금하다면 → REV-0386(MOVAPS)을 먼저 참고한다.

## 미니 예제
**예제 1 — 단순 벡터 덧셈 루프**
```c
void add_arrays(int *a, int *b, int *out, int n) {
    for (int i = 0; i < n; i++) out[i] = a[i] + b[i];
}
```
```asm
loop_top:
    vmovdqu ymm0, [rdi+rax*4]    ; a[i..i+7] 로드 (8개 int)
    vpaddd  ymm0, ymm0, [rsi+rax*4]  ; + b[i..i+7]
    vmovdqu [rdx+rax*4], ymm0    ; out[i..i+7]에 저장
    add     rax, 8               ; i += 8  (스칼라라면 i++ 였을 부분)
    cmp     rax, r8
    jl      loop_top
```

**예제 2 — SSE와 AVX의 같은 연산 비교**
```asm
; SSE
movaps  xmm0, [rdi]
mulps   xmm0, xmm1        ; xmm0 = xmm0 * xmm1 (xmm0 파괴)
```
```asm
; AVX 동일 연산
vmovaps xmm0, [rdi]
vmulps  xmm2, xmm0, xmm1  ; xmm2 = xmm0 * xmm1 (xmm0, xmm1 모두 보존)
```

## 관련 글
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0470 — 문자열 비교가 여러 CMP로 풀리는 최적화 패턴
- REV-0474 — 명령어 프리픽스(REX, 66h, F2h/F3h)가 붙는 이유 개요
- REV-0447 — memset이 SIMD 명령으로 인라인되는 패턴
- REV-0448 — memcpy가 SIMD 명령으로 인라인되는 패턴

## 출처/검증
- AVX/AVX2/AVX-512 명령어 인코딩(VEX/EVEX)과 3-오퍼랜드 문법: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A/2C, "Instruction Set Reference" 및 Chapter "AVX, AVX2, AVX-512" 개요 기준.
- AVX-SSE 전환 페널티: Intel Optimization Reference Manual, "Mixing AVX and SSE Code" 섹션 기준.
- 위 어셈블리 예제는 GCC/Clang `-O3 -mavx2` 벡터화 결과 경향을 단순화해 재구성한 예시다(2026-09-08 검증).
