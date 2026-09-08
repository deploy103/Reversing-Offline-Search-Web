---
id: REV-0393
title: "PADDB PADDW PADDD: SIMD 정수 덧셈"
slug: "rev-0393-paddb-paddw-paddd"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - paddb
  - PADDB
  - paddw
  - PADDW
  - paddd
  - PADDD
  - paddq
  - PADDQ
  - packed integer add
  - simd integer add
  - simd 정수 덧셈
  - xmm
  - XMM
  - SSE2
  - "paddd xmm0"
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - paddb 뭐임
  - paddw 뭐임
  - paddd 뭐임
  - paddb paddw paddd 차이
  - simd 정수 덧셈이 뭔지
symptom_keywords:
  - paddb paddw paddd 차이를 모르겠음
  - int 배열 덧셈이 paddd로 되어있음
  - b w d 접미사가 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`PADDB`/`PADDW`/`PADDD`는 128비트 XMM 레지스터를 각각 **8비트/16비트/32비트 정수 여러 개로 나눠**, 대응하는 원소끼리 병렬로 더하는 SSE2 정수 SIMD 명령이다.

## 언제 검색해야 하나
- `int`/`short`/`byte` 배열을 더하는 반복문이 자동 벡터화되어 `paddd`/`paddw`/`paddb`로 컴파일된 코드를 볼 때
- 체크섬, 해시, 픽셀 처리(이미지의 각 바이트를 더하는 필터 등) 코드에서 정수 SIMD 덧셈을 만났을 때
- `B`/`W`/`D`/`Q` 접미사가 각각 몇 비트짜리 원소를 의미하는지 헷갈릴 때

## 핵심 개념

### 접미사 B/W/D/Q — 원소 크기 구분
정수 SIMD 명령의 접미사는 128비트를 몇 비트 단위로 쪼개 병렬 처리하는지를 나타낸다:
- `B` (Byte, 8비트): 128비트 = 8비트 × 16개
- `W` (Word, 16비트): 128비트 = 16비트 × 8개
- `D` (Doubleword, 32비트): 128비트 = 32비트 × 4개
- `Q` (Quadword, 64비트): 128비트 = 64비트 × 2개

즉 `PADDB xmm0, xmm1`은 16개의 바이트를 각각 독립적으로 더하고, `PADDD xmm0, xmm1`은 4개의 32비트 정수를 각각 독립적으로 더한다. 이 규칙은 [PCMPEQB](rev-0394-pcmpeqb.md) 같은 다른 정수 SIMD 명령에도 동일하게 적용된다.

### Intel 문법
```
PADDB xmm_dest, xmm/m128_src   ; 8비트 x 16개 병렬 덧셈
PADDW xmm_dest, xmm/m128_src   ; 16비트 x 8개 병렬 덧셈
PADDD xmm_dest, xmm/m128_src   ; 32비트 x 4개 병렬 덧셈
PADDQ xmm_dest, xmm/m128_src   ; 64비트 x 2개 병렬 덧셈
```
`dest = dest + src`, 첫 오퍼랜드가 목적지다.

### 랩어라운드(wraparound) — 오버플로 처리 방식
`PADD*`는 **일반 정수 덧셈과 동일하게 오버플로 시 자리올림이 버려지고 값이 감싸돈다(wraparound)**. 예를 들어 `PADDB`에서 `0xFF + 0x01 = 0x00`(8비트 안에서 감김)이 된다. 이는 오버플로 시 값을 255/0으로 고정시키는 "포화 연산(saturating add, `PADDSB`/`PADDUSB` 등 별도 명령)"과 다르다는 점에 주의 — 본 문서가 다루는 `PADDB/W/D`는 포화되지 않는 일반 랩어라운드 버전이다.

### 플래그 변화
정수 SIMD 명령이지만 **EFLAGS(CF/OF/ZF 등)를 전혀 건드리지 않는다.** 오버플로가 나도 플래그로 알 수 없으므로, 오버플로 여부를 프로그램 로직에서 검사하려면 별도의 비교 명령이 필요하다.

### 신호 있음/없음 관점
`PADD*`는 부호 있는/없는 값 모두에 대해 동일한 비트 연산을 수행한다(2의 보수 덧셈은 signed/unsigned 상관없이 비트 패턴이 같다). 결과를 signed로 볼지 unsigned로 볼지는 그 값을 나중에 어떻게 다루는지(다른 SIMD 명령이나 스칼라 코드로 꺼내 쓸 때)에 달려 있다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- `int arr[4]` 같은 정수 배열을 더하는 반복문이 4개씩 묶여 `paddd`로 벡터화되는 것이 대표적이다.
- 이미지 픽셀(바이트 배열) 밝기 조정처럼 바이트 단위 대량 연산이 필요한 코드는 `paddb`로 벡터화되는 경우가 흔하다.
- 체크섬/해시 알고리즘 중 일부는 여러 워드를 한 번에 누적하기 위해 `paddw`/`paddd`를 쓴다.

### IDA/Ghidra 디컴파일
루프 형태로 남거나, 짧은 고정 크기(4/8/16개)라면 컴파일러 인트린식 호출(`_mm_add_epi32` 등)로 표현되는 경우가 있다. Ghidra는 명령을 그대로 남기고 오퍼랜드만 정리하는 경우도 많다.

### 수평 합산이 필요한 경우
"배열의 모든 원소를 하나의 총합으로 더하라"는 요구(예: `int total = 0; for (i) total += arr[i];`)는 `PADDD`만으로는 끝나지 않는다. `PADDD`로 4개씩 병렬 누적한 뒤에는, XMM 레지스터 안에 남은 4개의 부분합을 다시 하나로 합치는 **수평 합산(horizontal reduction)** 단계가 별도로 필요하다. 이 단계는 보통 `PSHUFD`(원소 재배열)로 값을 섞은 뒤 다시 `PADDD`를 하거나, `PHADDD`(수평 덧셈 전용 명령, 본 배치 범위 밖) 하나로 처리된다. 따라서 반복문에서 `paddd`만 보이고 최종 스칼라 값을 만드는 코드가 안 보인다면, 루프 뒤쪽에서 이 수평 합산 단계를 찾아봐야 한다.

### 부호 있는/없는 오버플로의 실제 위험
`PADDB`처럼 원소 크기가 작을수록(8비트) 랩어라운드가 발생하는 문턱값도 낮다(256 넘으면 바로 감김). CTF나 취약점 분석에서 이미지 픽셀 처리, 체크섬 계산 루틴에 정수 오버플로 버그가 숨어 있는지 확인할 때, `PADDB`가 쓰였다면 "8비트 범위(0~255)를 벗어나는 입력이 들어오면 조용히 감겨서 검증 로직을 우회할 수 있는가"를 우선적으로 검토할 가치가 있다.

## 화면/코드에서 보이는 징후
- `movdqa xmm0, [rsi]` → `paddd xmm0, [rdi]` → `movdqa [rsi], xmm0` — int[4] 배열 병렬 덧셈
- 이미지/버퍼 처리 루프에서 `paddb` 반복 — 픽셀 값 조정
- `paddw`/`paddd` 뒤에 결과를 다시 스칼라로 꺼내는(`movd`/`pextrw`) 코드 — 벡터 합산 후 최종 스칼라 값 추출

## 가장 먼저 할 것
1. 접미사(B/W/D/Q)로 원소 크기와 개수를 확인한다.
2. 오버플로가 실제로 문제가 되는 값 범위인지(랩어라운드 vs 포화가 필요한 도메인인지) 판단한다.
3. 결과가 이후 스칼라로 추출되는지, 계속 벡터로 쓰이는지 확인한다.

## 단계별 절차
**1) int[4] 배열 덧셈 인식**
```asm
movdqa xmm0, [rax]   ; a[0..3] (32비트 x 4)
paddd  xmm0, [rbx]    ; + b[0..3]
movdqa [rcx], xmm0    ; c[0..3] 저장
```
**2) 바이트 단위 픽셀 연산 인식**
```asm
movdqu xmm0, [rsi]
paddb  xmm0, xmm1     ; 16개 바이트 각각 밝기값 증가
movdqu [rsi], xmm0
```

## 명령어/단축키
- x64dbg/GDB의 XMM 레지스터 뷰를 정수(부호/무부호, 크기별) 형식으로 전환해 원소 각각을 확인 (GDB: `p $xmm0.v4_int32`, `p $xmm0.v16_int8`).

## 출력 해석
- `paddd` 결과에서 특정 원소가 예상보다 작게 나오면 32비트 랩어라운드(오버플로)를 의심한다.
- 원소별로 독립적이므로, 하나만 이상하면 그 위치에 해당하는 입력값만 따로 계산해 검증한다.

## 흔한 실수
- `PADDD`가 4개의 32비트 값을 하나로 합산(총합)한다고 착각하는 것 — 실제로는 **원소별(lane-wise) 독립 덧셈**이다. 전체를 하나의 스칼라 합으로 만들려면 이후 별도의 수평 합산(horizontal add, `PHADDD` 등) 명령이나 셔플+덧셈 조합이 필요하다.
- 오버플로 시 자동으로 255/최대값에 고정(포화)된다고 착각하는 것 — `PADDB/W/D`는 랩어라운드이며, 포화가 필요하면 `PADDSB`/`PADDUSB` 계열(본 배치 범위 밖) 명령이 별도로 쓰인다.
- 접미사 `D`(Doubleword, 32비트)를 `DQ`(128비트 전체)와 혼동하는 것 — `D` 하나만 붙으면 32비트, `DQ`가 붙으면 128비트다.

## 막혔을 때 다음 체크
- 결과가 예상과 다르면 → 접미사(B/W/D)를 다시 확인해 원소 크기를 재계산.
- 특정 원소만 이상하면 → 그 lane의 입력값을 스칼라로 다시 계산해 오버플로 여부 확인.
- 최종 하나의 합계를 기대했는데 4개 값이 나오면 → 이 명령은 원소별 덧셈일 뿐이며, 수평 합산은 별도 명령/셔플이 필요함을 상기.

## 미니 예제

**예제 1 — int[4] 배열 병렬 덧셈**
```c
int c[4];
for (int i = 0; i < 4; i++) c[i] = a[i] + b[i];
```
```asm
movdqa xmm0, [rax]
paddd  xmm0, [rbx]
movdqa [rcx], xmm0
```

**예제 2 — 바이트 배열(픽셀) 밝기 증가**
```c
for (int i = 0; i < 16; i++) pixel[i] = (uint8_t)(pixel[i] + delta[i]);
```
```asm
movdqu xmm0, [rsi]
paddb  xmm0, [rdi]
movdqu [rsi], xmm0
```

**예제 3 — 16비트 워드 배열 덧셈**
```asm
movdqa xmm0, [rax]   ; short[8]
paddw  xmm0, [rbx]
movdqa [rcx], xmm0
```

## 관련 글
- REV-0389 — MOVDQA와 MOVDQU: 정수 XMM 이동
- REV-0392 — PXOR: XMM 레지스터 초기화와 XOR
- REV-0394 — PCMPEQB: SIMD 바이트 비교 명령
- REV-0390 — ADDPS와 ADDSS: SIMD 병렬/단일 덧셈

## 출처/검증
- `PADDB`/`PADDW`/`PADDD`/`PADDQ` 명령어 동작과 랩어라운드 규칙: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PADDB/PADDW/PADDD—Add Packed Integers" 섹션 기준 (2026-09-08 검증).
- 포화 덧셈(PADDSB/PADDUSB)과의 구분: Intel SDM 동 섹션 및 "SSE2 Instructions" 개요 기준.
