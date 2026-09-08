---
id: REV-0391
title: "SUBPS와 MULPS: SIMD 뺄셈과 곱셈"
slug: "rev-0391-subps-mulps"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - subps
  - SUBPS
  - mulps
  - MULPS
  - subss
  - mulss
  - subps instruction
  - mulps instruction
  - subps 명령어
  - mulps 명령어
  - packed subtract
  - packed multiply
  - float 뺄셈
  - float 곱셈
  - xmm
  - XMM
  - SSE
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - subps 뭐임
  - mulps 뭐임
  - subps mulps 차이
  - float 곱셈 어셈블리
  - float 뺄셈 어셈블리
symptom_keywords:
  - subps mulps가 뭔지 모르겠음
  - float 곱셈이 imul 대신 mulps로 되어있음
  - simd 산술 명령이 뭔지 모르겠음
last_verified: "2026-09-08"
---

## 한 줄 요약
`SUBPS`와 `MULPS`는 각각 두 XMM 레지스터의 4개 single-precision float를 원소별로 병렬 **뺄셈**/**곱셈**하는 SSE 명령이며, 오퍼랜드 순서와 정밀도 규칙만 다를 뿐 [ADDPS](rev-0390-addps-addss.md)와 사용 패턴이 동일하다.

## 언제 검색해야 하나
- `float`/벡터 연산 코드에서 `subps`, `mulps`, 또는 스칼라 버전 `subss`/`mulss`가 나와서 정수 `SUB`/`IMUL`과 뭐가 다른지 궁금할 때
- 3D 그래픽, 물리 연산, 신호 처리 등 벡터 수학이 들어간 함수를 분석할 때
- 뺄셈에서 오퍼랜드 순서(어느 쪽에서 어느 쪽을 빼는지)를 착각해 결과 부호가 반대로 해석될 때

## 핵심 개념

### Intel 문법과 오퍼랜드 방향
```
SUBPS xmm_dest, xmm/m128_src   ; dest = dest - src  (4개 원소 병렬)
MULPS xmm_dest, xmm/m128_src   ; dest = dest * src  (4개 원소 병렬)
SUBSS xmm_dest, xmm/m32_src    ; dest[0] = dest[0] - src[0], 1~3번째는 유지
MULSS xmm_dest, xmm/m32_src    ; dest[0] = dest[0] * src[0], 1~3번째는 유지
```
`ADDPS`([REV-0390](rev-0390-addps-addss.md))와 마찬가지로 첫 번째 오퍼랜드가 목적지이자 좌항이다. **`SUBPS`는 뺄셈이므로 순서에 민감하다** — `subps xmm0, xmm1`은 `xmm0 = xmm0 - xmm1`이지 그 반대가 아니다. 이는 `SUB`(REV-0048)의 방향 규칙과 동일하다.

### 레지스터/메모리 효과
`PS`(4개 병렬)와 `SS`(1개, 나머지 보존) 구분은 [REV-0390](rev-0390-addps-addss.md)에서 설명한 것과 완전히 동일한 규칙을 따른다.

### 플래그 변화
정수 `SUB`/`IMUL`과 달리 EFLAGS(CF/OF/ZF/SF)를 세팅하지 않는다. 부동소수점 예외 상태는 MXCSR에 반영된다(REV-0390 참고).

### 신호 있음/없음 관점 — MULPS는 IMUL/MUL과 근본적으로 다르다
정수 곱셈은 부호 있는(`IMUL`)/부호 없는(`MUL`) 두 가지 버전이 필요하고 오버플로 시 상위 레지스터에 결과가 걸쳐진다. 반면 `MULPS`는 IEEE 754 부동소수점 곱셈 규칙을 그대로 따르며 signed/unsigned 구분 자체가 없다(부호는 값의 일부). 오버플로가 나면 예외 트랩 대신 `+Infinity`/`-Infinity` 값이 되거나 MXCSR의 Overflow 플래그가 세팅된다.

### 스택/RSP/RIP 변화
없음.

### 컴파일러 패턴
- 벡터/행렬 연산(예: `Vec4 operator*(Vec4 a, float s)`)이 `mulps`로 컴파일되는 것은 그래픽·게임 엔진류 바이너리에서 매우 흔한 패턴이다.
- `a - b` 형태의 float 뺄셈은 스칼라라면 `subss`, 배열이면 벡터화되어 `subps`로 나타난다.
- 곱셈 후 덧셈이 이어지는 `a*b+c` 패턴은 최신 CPU/컴파일러에서 FMA(Fused Multiply-Add, `VFMADD` 계열, AVX 확장)로 합쳐지기도 하지만, SSE만 대상으로 하는 코드에서는 `mulps` 다음 `addps`가 별도로 나온다.

### IDA/Ghidra 디컴파일
`subss`/`mulss`는 `fVar1 = fVar2 - fVar3;`, `fVar1 = fVar2 * fVar3;` 형태로 그대로 연산자로 복원된다. `subps`/`mulps`는 배열 루프거나 벡터 구조체(`Vec4`) 연산자 오버로드가 인라인된 경우가 많다.

## 화면/코드에서 보이는 징후
- `subss xmm0, xmm1` — 두 float의 차이 계산 (예: 거리, 델타 값)
- `mulps xmm0, xmm1` — 4개 float 벡터를 원소별로 곱함 (스케일링, 벡터 내적/외적의 일부)
- `mulss xmm0, xmm0` — 자기 자신을 곱함, 즉 **제곱**(`x * x`) 연산의 흔한 형태
- `mulps` 뒤 바로 `addps` — `a*b+c` 형태의 벡터 곱셈-누적(내적 계산 등)

## 가장 먼저 할 것
1. `PS`/`SS` 접미사로 병렬(4개)인지 스칼라(1개)인지 확인한다.
2. `SUBPS`라면 어느 오퍼랜드가 좌항(피감수)인지 순서를 정확히 읽는다.
3. `MULPS`/`MULSS`가 자기 자신을 곱하는 패턴(`mulss xmm0, xmm0`)이면 "제곱"으로 해석한다.

## 단계별 절차
**1) 스칼라 뺄셈 방향 확인**
```asm
movss xmm0, [rbp-4]   ; a
subss xmm0, [rbp-8]    ; xmm0 = a - b  (b를 빼는 것이지 그 반대가 아님)
```
**2) 제곱 패턴 인식**
```asm
movss xmm0, [rbp-4]
mulss xmm0, xmm0        ; xmm0 = a * a
```
**3) 벡터 곱셈-누적(내적류) 인식**
```asm
mulps xmm0, xmm1   ; a[0..3] * b[0..3]
addps xmm2, xmm0    ; 누적
```

## 명령어/단축키
- x64dbg/GDB의 XMM 레지스터 뷰로 `subps`/`mulps` 실행 전후 4개의 float 값 변화를 직접 비교 확인.
- IDA F5: 연산자(`+`, `-`, `*`)로 정리된 결과에서 원본이 packed인지 scalar인지 알고 싶으면 디스어셈블리(원문 어셈블리)를 병행 확인해야 한다(디컴파일 결과만으로는 PS/SS 구분이 사라지는 경우가 많음).

## 출력 해석
- `subps`/`mulps` 결과는 4개 원소 각각 독립적으로 계산된다 — 한 원소만 이상해 보이면 그 원소에 해당하는 입력값만 따로 확인한다.
- `mulss`/`subss`는 0번째 원소만 바뀌고 나머지는 보존되므로, XMM 전체 128비트를 봤을 때 1~3번째 값이 실행 전후 동일해야 정상이다.

## 흔한 실수
- `SUBPS`의 오퍼랜드 순서를 반대로 읽어서 부호가 뒤집힌 결과를 정상으로 착각하는 것 — `subps xmm0, xmm1`은 항상 `xmm0 - xmm1`이다.
- `mulps`/`mulss`가 정수 `IMUL`처럼 오버플로 시 상위 레지스터에 걸치는 결과를 만든다고 착각하는 것 — 부동소수점 곱셈은 결과가 그대로 같은 크기(32비트/64비트) 레지스터 슬롯에 들어가며, 넘치면 무한대나 반올림 손실로 처리된다.
- `mulss xmm0, xmm0`를 "값을 자기 자신에 복사하는 이상한 코드"로 오해하는 것 — 이는 표준적인 제곱 연산이다.

## 막혔을 때 다음 체크
- 뺄셈 결과 부호가 예상과 반대라면 → 오퍼랜드 순서(어느 게 dest/좌항인지)부터 다시 확인.
- 곱셈 결과가 이상하면 → PS(4개)인지 SS(1개)인지, 그리고 두 소스가 각각 어떤 값인지 XMM 레지스터 뷰에서 직접 확인.

## 미니 예제

**예제 1 — 스칼라 float 뺄셈**
```c
float delta(float a, float b) { return a - b; }
```
```asm
movss xmm0, xmm0   ; a (인자로 이미 xmm0)
subss xmm0, xmm1    ; xmm0 = a - b
ret
```

**예제 2 — 제곱 후 합산 (거리 제곱 계산의 일부)**
```c
float sq = dx * dx + dy * dy;
```
```asm
movss  xmm0, dx
mulss  xmm0, xmm0     ; dx*dx
movss  xmm1, dy
mulss  xmm1, xmm1     ; dy*dy
addss  xmm0, xmm1      ; 합산
```

**예제 3 — 벡터 스케일링 (Vec4 * scalar)**
```c
Vec4 scale(Vec4 v, float s) { return (Vec4){v.x*s, v.y*s, v.z*s, v.w*s}; }
```
```asm
movaps xmm2, xmm1      ; scalar s를 4칸 모두 복제했다고 가정 (shufps 등으로 준비)
mulps  xmm0, xmm2       ; v(4개) * s(4개 동일값)
```

**예제 4 — 벡터 뺄셈**
```asm
movaps xmm0, [rax]   ; a[0..3]
subps  xmm0, [rbx]    ; a - b (원소별)
movaps [rcx], xmm0    ; 결과 저장
```

## 관련 글
- REV-0390 — ADDPS와 ADDSS: SIMD 병렬/단일 덧셈
- REV-0386 — MOVAPS: 정렬된 XMM 레지스터 이동
- REV-0395 — CVTSI2SD와 CVTTSD2SI: 정수-실수 변환

## 출처/검증
- `SUBPS`/`MULPS`/`SUBSS`/`MULSS` 명령어 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "SUBPS—Subtract Packed Single-Precision Floating-Point Values" / "MULPS" 섹션 기준 (2026-09-08 검증).
- FMA(곱셈-누적 결합) 명령과의 관계: Intel SDM, "FMA Instruction Set" 개요 기준.
