---
id: REV-0402
title: "LOOPE와 LOOPZ: 조건부 반복 명령"
slug: "rev-0402-loope-loopz"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - loope
  - LOOPE
  - loopz
  - LOOPZ
  - loope 명령어
  - loopz 명령어
  - loop while zero
  - loop while equal
  - ECX ZF 반복
  - cmps loope
  - scas loopz
  - 조건부 루프
aliases:
  - loope 뭐임
  - loopz가 뭐죠
  - LOOPE 명령어
  - LOOPZ 명령어
  - loope loopz 차이
symptom_keywords:
  - loope label이 뭔지 모르겠음
  - loopz label이 뭔지 모르겠음
  - loop인데 zf도 확인하는 이유를 모르겠음
  - cmps 다음에 loope가 왜 나오는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LOOPE`/`LOOPZ`(둘은 완전히 같은 명령의 다른 이름)는 [LOOP](rev-0401-loop.md)에 **ZF=1(같음/0)이라는 조건을 추가**해서, "카운터가 남아있고, 동시에 직전 비교 결과가 같았을(0이었을) 때만" 반복하는 명령이다.

## 언제 검색해야 하나
- `loope label` 또는 `loopz label` 코드를 만났는데 [LOOP](rev-0401-loop.md)와 뭐가 다른지 궁금할 때
- `cmpsb`/`scasb` 같은 문자열 비교 명령 뒤에 `loope`가 붙어 있어서 무슨 반복 조건인지 헷갈릴 때
- "카운터가 남아있는 동안"과 "값이 같은 동안"이라는 두 조건이 동시에 필요한 반복문을 어셈블리로 어떻게 표현하는지 알고 싶을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
LOOPE  rel8
LOOPZ  rel8      ; LOOPE와 완전히 동일한 opcode - 니모닉만 다름
```
오퍼랜드는 [LOOP](rev-0401-loop.md)와 마찬가지로 rel8(짧은 뒤쪽 상대 분기) 하나뿐이다. `LOOPE`(Loop while Equal)와 `LOOPZ`(Loop while Zero)는 **어셈블러 니모닉만 다를 뿐 기계어 opcode가 완전히 동일**하다 — CMP/TEST 결과 "같음"과 "0"이 같은 ZF=1로 표현되기 때문에 두 이름이 공존한다.

### 실제로 하는 일
```
(E/R)CX = (E/R)CX - 1
if ((E/R)CX != 0) AND (ZF == 1):
    jump to rel8
```
[LOOP](rev-0401-loop.md)와 동일하게 카운터를 먼저 감소시키지만, 분기 조건에 **ZF=1**이 추가로 걸린다. 즉 카운터가 남아있어도 ZF가 0(직전 비교가 "다름")이면 반복을 멈춘다.

### 플래그 변화
LOOPE/LOOPZ 자신은 EFLAGS를 **변경하지 않는다**([LOOP](rev-0401-loop.md)와 동일). 다만 **읽기는 한다** — 분기 여부를 결정할 때 직전 명령이 세팅해 둔 ZF를 참조한다. 따라서 LOOPE/LOOPZ 앞에는 반드시 ZF를 세팅하는 명령(`CMP`, `CMPS`, `SCAS`, `TEST` 등)이 있어야 의미가 있다.

### 스택/RSP/RIP 변화
RSP는 변하지 않는다. RIP는 조건 성립 시 목표로, 아니면 다음 명령으로 이동한다.

### 왜 이런 명령이 필요한가 — "같은 동안 계속" 패턴
LOOPE/LOOPZ는 전형적으로 [CMPS](rev-0085-cmps.md)나 [SCAS](rev-0084-scas.md) 같은 문자열 비교 명령 바로 뒤에 붙어서, "두 배열이 같은 부분이 계속되는 동안, 그리고 카운터가 남아있는 동안" 반복 비교를 이어가는 데 쓰인다. 이는 사실 [REP 접두사](rev-0080-rep-prefix.md) 중 `REPE`/`REPZ`(예: `repe cmpsb`)가 하는 일과 거의 같은 목적이지만, `REPE CMPSB`는 CMPS 자체에 반복을 내장한 한 명령인 반면, `LOOPE`는 임의의 코드 블록(비교 명령 + 다른 처리 코드)을 통째로 반복시킬 수 있다는 점에서 더 범용적이다.

전형적인 용도: 정렬된 배열에서 같은 값이 연속되는 구간의 길이를 세거나, 두 버퍼가 어디까지 일치하는지 手동으로 순회하며 확인하는 손으로 짠 루프.

### LOOPE/LOOPZ 종료 조건 정리
다음 중 **하나라도** 만족하면 반복이 멈춘다:
1. 카운터가 감소 후 0이 됨(더 이상 반복할 대상이 없음)
2. ZF=0(직전 비교가 "다름"이었음 — 더 이상 "같은 구간"이 아님)

이 두 조건 중 어느 쪽 때문에 루프가 끝났는지는 **루프를 빠져나온 직후 ECX 값을 확인**해서 구분한다: ECX가 0이면 "끝까지 다 같았다", ECX가 0이 아니면 "중간에 달라서 멈췄다"는 뜻이다.

## 화면/코드에서 보이는 징후
- `cmpsb` 다음에 `loope compare_loop` — 두 버퍼를 바이트 단위로 비교하며 같은 동안 계속 진행
- `scasb` 다음에 `loopz scan_loop` — 특정 값이 연속되는 구간 탐색
- 루프 종료 직후 `ECX`를 검사하는 코드 — "끝까지 같았는지" vs "중간에 달랐는지" 구분 로직

## 가장 먼저 할 것
1. LOOPE/LOOPZ 직전에 ZF를 세팅하는 명령(CMP/CMPS/SCAS/TEST)이 무엇인지 확인
2. 카운터(ECX/RCX) 초기값 확인 → 최대 반복 횟수
3. 루프 탈출 후 ECX 값을 확인하는 코드가 있는지 확인 → 탈출 이유(카운터 소진 vs 불일치) 판별 로직

## 단계별 절차

**1) 문자열 비교 반복 패턴**
```asm
mov   ecx, 20
lea   rsi, [buf1]
lea   rdi, [buf2]
cmp_loop:
    cmpsb              ; [rsi]와 [rdi] 비교, rsi/rdi 각각 +1, ZF 세팅
    loope cmp_loop      ; 같았고(ZF=1) 카운터도 남았으면 계속
; 루프 탈출 후
cmp   ecx, 0
jz    fully_equal       ; 20바이트 전부 같았음
; ecx != 0 이면 중간에 달라서 멈춘 것
```

**2) "같은 값 연속 개수" 세기**
```asm
mov   ecx, len
mov   al, target_val
lea   rdi, [buf]
scan_loop:
    scasb
    loopz scan_loop
; ecx가 초기값보다 얼마나 줄었는지로 연속 개수 계산
```

## 명령어/단축키
- IDA/Ghidra 의사코드: LOOPE/LOOPZ 블록은 대개 `while (ecx != 0 && ...)` 형태의 복합 조건 루프로 재구성되거나, 문자열 비교 함수 호출(`memcmp` 유사)로 컴파일러가 아예 인라인 최적화해버려 원본 형태가 사라질 수 있다.
- x64dbg/GDB: 루프를 한 번씩 스텝 실행하며 ECX와 ZF를 함께 관찰하면 두 조건이 어떻게 상호작용하는지 명확히 보인다.

## 출력 해석
- 루프 종료 후 ECX == 0: 카운터가 다 소진될 때까지 계속 같았다(전부 일치).
- 루프 종료 후 ECX != 0: 중간에 ZF=0(불일치)이 발생해서 조기 종료됐다 — 그 시점의 RSI/RDI(또는 RDI, SCAS의 경우)가 "처음���로 달랐던 위치"를 가리킨다.

## 흔한 실수
- LOOPE/LOOPZ가 그 자체로 비교를 수행한다고 착각하는 것 — LOOPE/LOOPZ 자신은 비교를 하지 않는다. 오직 **직전 명령이 세팅한 ZF**를 읽을 뿐이다. 비교는 반드시 CMP/CMPS/SCAS/TEST 등 앞선 명령이 담당한다.
- LOOPE와 LOOPNE([REV-0403](rev-0403-loopne-loopnz.md))를 헷갈리는 것 — LOOPE는 "같은 동안(ZF=1)", LOOPNE는 "다른 동안(ZF=0)" 반복한다. 정반대 조건이다.
- 루프 탈출 이유를 확인하지 않고 넘어가는 것 — ECX가 0인지 아닌지 확인해야 "끝까지 같았다"와 "중간에 달랐다"를 구분할 수 있는데, 이 확인 코드를 놓치면 로직을 잘못 해석하기 쉽다.
- LOOPE/LOOPZ도 [LOOP](rev-0401-loop.md)와 마찬가지로 EFLAGS를 변경하지 않는다는 점을 잊고, 루프 안에서 ZF가 명령마다 새로 갱신된다고 착각하는 것 — ZF는 오직 CMPS/SCAS/CMP 등이 실행될 때만 갱신되고, LOOPE 자체는 읽기만 한다.

## 막혔을 때 다음 체크
- 루프가 예상보다 일찍 끝나면 → 직전 비교 명령이 ZF를 어떻게 세팅했는지, 데이터가 정말 그 지점에서 달랐는지 확인.
- ECX 최종값을 확인하는 코드가 안 보이면 → 컴파일러가 반복 결과를 다른 방식(RSI/RDI 최종 위치 비교 등)으로 판단하고 있을 수 있으니 주변 코드를 넓게 살펴본다.
- LOOPE 대신 REPE 접두사 형태(`repe cmpsb`)가 나온다면 → [REP Prefix](rev-0080-rep-prefix.md) 문서를 참고 — 같은 목적이지만 문법이 다른 명령이다.

## 미니 예제

**예제 1 — 두 버퍼의 일치 여부 확인**
```c
int i;
for (i = 0; i < 20; i++) {
    if (buf1[i] != buf2[i]) break;
}
bool fully_equal = (i == 20);
```
```asm
mov   ecx, 20
lea   rsi, [buf1]
lea   rdi, [buf2]
loop_top:
    cmpsb
    loope loop_top
cmp   ecx, 0
sete  fully_equal
```

**예제 2 — 연속된 같은 문자 개수 세기**
```c
int count = 0;
while (count < max && str[count] == target) count++;
```
```asm
mov   ecx, max
lea   rdi, [str]
mov   al, target
count_loop:
    scasb
    loopz count_loop
; max - ecx == count
```

## 관련 글
- REV-0401 — LOOP: 카운터 기반 반복 명령
- REV-0403 — LOOPNE와 LOOPNZ: 조건부 반복 명령
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0067 — JE와 JZ: ZF가 1일 때 분기

## 출처/검증
- LOOPE/LOOPZ 명령어의 오퍼랜드/동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LOOP/LOOPcc—Loop According to ECX Counter" 섹션 기준 (2026-09-08 검증). 해당 섹션은 LOOPE와 LOOPZ가 동일 opcode의 별칭임을 명시한다.
