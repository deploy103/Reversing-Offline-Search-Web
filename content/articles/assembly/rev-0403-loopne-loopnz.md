---
id: REV-0403
title: "LOOPNE와 LOOPNZ: 조건부 반복 명령"
slug: "rev-0403-loopne-loopnz"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - loopne
  - LOOPNE
  - loopnz
  - LOOPNZ
  - loopne 명령어
  - loopnz 명령어
  - loop while not zero
  - loop while not equal
  - ECX ZF 반복
  - scasb loopne
  - cmps loopnz
  - 조건부 루프
aliases:
  - loopne 뭐임
  - loopnz가 뭐죠
  - LOOPNE 명령어
  - LOOPNZ 명령어
  - loopne loopnz 차이
symptom_keywords:
  - loopne label이 뭔지 모르겠음
  - loopnz label이 뭔지 모르겠음
  - 값을 찾을 때까지 반복하는 명령어를 모르겠음
  - scasb 다음에 loopne가 왜 나오는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`LOOPNE`/`LOOPNZ`(둘은 완전히 같은 명령의 다른 이름)는 [LOOP](rev-0401-loop.md)에 **ZF=0(다름/0이 아님)이라는 조건을 추가**해서, "카운터가 남아있고, 동시에 직전 비교 결과가 달랐을 때만" 반복하는 명령이다. [LOOPE/LOOPZ](rev-0402-loope-loopz.md)와 정확히 반대 조건이다.

## 언제 검색해야 하나
- `loopne label` 또는 `loopnz label` 코드를 만났는데 [LOOPE/LOOPZ](rev-0402-loope-loopz.md)와 뭐가 다른지 궁금할 때
- `scasb` 뒤에 `loopne`가 붙어서 "특정 값을 찾을 때까지 반복"하는 코드를 분석할 때(문자열에서 특정 문자를 찾는 `strchr` 유사 패턴)
- "카운터가 남아있는 동안"과 "값이 다른 동안"이라는 두 조건이 동시에 필요한 반복문을 어셈블리로 어떻게 표현하는지 알고 싶을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
LOOPNE rel8
LOOPNZ rel8      ; LOOPNE와 완전히 동일한 opcode - 니모닉만 다름
```
오퍼랜드는 [LOOP](rev-0401-loop.md)와 마찬가지로 rel8 하나뿐이다. `LOOPNE`(Loop while Not Equal)와 `LOOPNZ`(Loop while Not Zero)는 어셈블러 니모닉만 다를 뿐 기계어 opcode가 완전히 동일하다.

### 실제로 하는 일
```
(E/R)CX = (E/R)CX - 1
if ((E/R)CX != 0) AND (ZF == 0):
    jump to rel8
```
[LOOP](rev-0401-loop.md)와 동일하게 카운터를 먼저 감소시키지만, 분기 조건에 **ZF=0**이 추가로 걸린다. 즉 카운터가 남아있어도 ZF가 1(직전 비교가 "같음")이면 반복을 멈춘다.

### 플래그 변화
LOOPNE/LOOPNZ 자신은 EFLAGS를 **변경하지 않는다**. 분기 여부를 결정할 때 직전 명령이 세팅해 둔 ZF를 **읽기만** 한다. 따라서 이 명령 앞에는 반드시 ZF를 세팅하는 명령(`CMP`, `CMPS`, `SCAS`, `TEST` 등)이 있어야 의미가 있다.

### 스택/RSP/RIP 변화
RSP는 변하지 않는다. RIP는 조건 성립 시 목표로, 아니면 다음 명령으로 이동한다.

### 왜 이런 명령이 필요한가 — "찾을 때까지 반복" 패턴
LOOPNE/LOOPNZ의 가장 전형적인 용도는 [SCAS](rev-0084-scas.md)와 결합해 "버퍼 안에서 특정 값과 **일치하는** 위치를 찾을 때까지" 반복하는 것이다 — SCAS가 비교값과 **다르면(ZF=0)** LOOPNE가 계속 반복시키고, **같아지는 순간(ZF=1)** 멈춘다. 즉 "찾을 때까지 계속 진행"하는 탐색 루프에 자연스럽게 들어맞는다. 이는 C 표준 라이브러리의 `strchr`/`memchr`이 하는 일과 개념적으로 같으며, `REPNE`/`REPNZ` 접두사(예: `repne scasb`)가 SCAS 자체에 이 반복을 내장한 것과 목적이 동일하다([REP Prefix](rev-0080-rep-prefix.md) 참고).

### LOOPNE/LOOPNZ 종료 조건 정리
다음 중 **하나라도** 만족하면 반복이 멈춘다:
1. 카운터가 감소 후 0이 됨(끝까지 찾지 못함)
2. ZF=1(직전 비교가 "같음"이었음 — 원하는 값을 찾음)

루프를 빠져나온 후 **ECX 값을 확인**해서 어느 쪽으로 끝났는지 구분한다: ECX가 0이면 "끝까지 못 찾았다", ECX가 0보다 크면 "중간에 찾아서 멈췄다"는 뜻이다.

### LOOPE/LOOPZ와의 대칭 관계
| | 반복 조건 | 대표 용도 |
|---|---|---|
| `LOOPE`/`LOOPZ` ([REV-0402](rev-0402-loope-loopz.md)) | ZF=1 (같음) 이고 카운터 남음 | "같은 구간이 계속되는 동안" 진행 (버퍼 일치 비교) |
| `LOOPNE`/`LOOPNZ` (이 글) | ZF=0 (다름) 이고 카운터 남음 | "찾는 값이 나올 때까지" 진행 (버퍼 탐색) |

## 화면/코드에서 보이는 징후
- `scasb` 다음에 `loopne search_loop` — 버퍼에서 특정 바이트를 찾을 때까지 반복 스캔
- `cmpsb` 다음에 `loopnz diff_loop` — 두 버퍼가 다시 같아지는 지점을 찾을 때까지 반복
- 루프 종료 직후 `ECX`를 검사하는 코드 — "찾았는지" vs "끝까지 못 찾았는지" 판별 로직

## 가장 먼저 할 것
1. LOOPNE/LOOPNZ 직전에 ZF를 세팅하는 명령이 무엇인지 확인
2. 카운터(ECX/RCX) 초기값 확인 → 최대 탐색 범위
3. 루프 탈출 후 ECX 값을 확인하는 코드가 있는지 확인 → "찾음"과 "못 찾음" 구분 로직

## 단계별 절차

**1) 특정 바이트를 찾을 때까지 스캔**
```asm
mov   ecx, len
mov   al, 'X'          ; 찾을 문자
lea   rdi, [buf]
find_loop:
    scasb               ; [rdi]와 al 비교, rdi += 1, ZF 세팅
    loopne find_loop     ; 다르면(ZF=0) 계속, 카운터 소진돼도 멈춤
cmp   ecx, 0
jz    not_found          ; 끝까지 못 찾음
; ecx > 0 이면 rdi-1 위치에서 'X'를 찾은 것
```

**2) 두 버퍼가 다시 일치하는 지점 찾기**
```asm
mov   ecx, len
lea   rsi, [buf1]
lea   rdi, [buf2]
resync_loop:
    cmpsb
    loopnz resync_loop
; ecx > 0 이면 두 버퍼가 다시 같아진 지점을 찾은 것
```

## 명령어/단축키
- IDA/Ghidra 의사코드: LOOPNE/LOOPNZ 블록은 `while (ecx != 0 && ...)` 형태로 재구성되거나, `strchr`/`memchr` 유사 함수 호출로 컴파일러가 인라인 최적화해버려 원본 형태가 사라질 수 있다.
- x64dbg/GDB: 반복 중 ECX와 ZF, 그리고 RDI(SCAS의 현재 위치)를 함께 관찰하면 탐색 진행 상황을 정확히 볼 수 있다.

## 출력 해석
- 루프 종료 후 ECX == 0: 카운터가 다 소진될 때까지 원하는 값을 찾지 못했다.
- 루프 종료 후 ECX != 0: 중간에 ZF=1(일치)이 발생해서 조기 종료됐다 — 그 시점의 RDI가 "찾은 위치 바로 다음"을 가리킨다(SCASB가 비교 후 RDI를 자동으로 +1 하기 때문에, 실제 찾은 위치는 RDI-1이다).

## 흔한 실수
- LOOPNE가 비교 자체를 수행한다고 착각하는 것 — LOOPNE 자신은 비교하지 않는다. 오직 직전 SCAS/CMPS/CMP가 세팅한 ZF를 읽을 뿐이다.
- LOOPNE와 LOOPE([REV-0402](rev-0402-loope-loopz.md))를 헷갈리는 것 — 이름의 "N"(Not)이 조건을 반대로 만든다는 점을 기억: LOOPE는 "같은 동안", LOOPNE는 "다른 동안" 반복한다.
- 찾은 위치를 계산할 때 RDI가 SCASB 실행 후 이미 +1 되어 있다는 사실을 잊고 오프바이원 오류를 내는 것 — 실제 일치 위치는 항상 "현재 RDI - 1"이다.
- 루프 탈출 후 ECX 확인 코드를 놓치고 "무조건 찾았다"고 가정하는 것 — 끝까지 못 찾고 카운터 소진으로 종료된 경우와 반드시 구분해야 한다.

## 막혔을 때 다음 체크
- 찾은 위치가 하나 어긋나 보이면 → RDI가 SCASB에 의해 이미 자동 증가된 상태임을 감안해 -1 보정.
- 루프가 예상보다 일찍 끝나면 → 카운터가 예상보다 작게 초기화되지 않았는지 확인.
- LOOPNE 대신 REPNE 접두사 형태(`repne scasb`)가 나온다면 → [REP Prefix](rev-0080-rep-prefix.md) 문서를 참고 — 같은 목적이지만 문법이 다른 명령이다.

## 미니 예제

**예제 1 — 문자열에서 특정 문자 찾기 (strchr 유사)**
```c
char *find_char(char *s, int len, char target) {
    for (int i = 0; i < len; i++) {
        if (s[i] == target) return &s[i];
    }
    return NULL;
}
```
```asm
mov   ecx, len
mov   al, target
lea   rdi, [s]
scan:
    scasb
    loopne scan
cmp   ecx, 0
jz    not_found
lea   rax, [rdi - 1]   ; 찾은 위치 (rdi가 이미 +1 되어 있으므로 보정)
jmp   done
not_found:
xor   eax, eax
done:
```

## 관련 글
- REV-0401 — LOOP: 카운터 기반 반복 명령
- REV-0402 — LOOPE와 LOOPZ: 조건부 반복 명령
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기

## 출처/검증
- LOOPNE/LOOPNZ 명령어의 오퍼랜드/동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "LOOP/LOOPcc—Loop According to ECX Counter" 섹션 기준 (2026-09-08 검증). 해당 섹션은 LOOPNE와 LOOPNZ가 동일 opcode의 별칭임을 명시한다.
