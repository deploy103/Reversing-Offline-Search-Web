---
id: REV-0075
title: "CMOVcc: 분기 없는 조건부 이동"
slug: "rev-0075-cmovcc"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - cmovcc
  - CMOVcc
  - cmove
  - cmovz
  - cmovne
  - cmovnz
  - cmovg
  - cmovge
  - cmovl
  - cmovle
  - cmova
  - cmovae
  - cmovb
  - cmovbe
  - cmovs
  - cmovns
  - conditional move
  - 조건부 이동
  - 분기 없는 조건문
  - branchless
  - branch-free
  - branchless code
  - 삼항 연산자 어셈블리
  - ternary asm
  - CMOVcc 뭐임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - cmov 명령어
  - CMOVcc가 뭐죠
  - cmov이 뭐임
  - 조건부 이동 명령어
  - 분기 없는 이동
symptom_keywords: []
last_verified: "2026-09-08"
---

## 한 줄 요약
`CMOVcc`는 "조건(cc)이 참이면 src를 dst로 옮기고, 거짓이면 dst를 그대로 둔다"는 명령어다. `Jcc`처럼 조건에 따라 실행 흐름이 갈라지는 게 아니라, **분기 자체가 아예 없이** 한 줄로 끝난다 — 그래서 "branchless(분기 없는)" 코드라고 부른다.

## 언제 검색해야 하나
- 디스어셈블리에 `cmovg`, `cmovle`, `cmova` 같은 명령이 나오는데 `Jcc`와 뭐가 다른지 모를 때
- IDA 디컴파일에서는 `if`/삼항 연산자(`? :`)로 보이는 코드인데, 실제 어셈블리에는 분기(jump)가 하나도 없어서 당황스러울 때
- `max()`, `min()`, `abs()` 스타일 함수를 디버깅하다가 예상한 `jg`/`jl` 브레이크포인트가 절대 안 걸릴 때
- "CMOVcc 뭐임", "cmov이 뭐임"처럼 처음 보는 명령어를 찾아볼 때

## 핵심 개념

### CMOVcc가 실제로 하는 일
`CMOVcc dst, src`는 (이전 명령이 세팅해둔) 플래그를 검사해서:
- 조건이 **참**이면 → `src`의 값을 `dst`에 복사 (`MOV`와 동일하게 동작)
- 조건이 **거짓**이면 → `dst`를 **완전히 그대로 둔다** (아무것도 안 씀)

중요한 점은, CPU는 조건이 참이든 거짓이든 **매번 src와 dst를 둘 다 읽고 실행 자체는 항상 한다** — 다만 "쓸 것이냐 말 것이냐"만 조건에 달려 있다. RIP가 갈라지는 지점(분기)이 아예 존재하지 않기 때문에 분기 예측(branch prediction)이 틀릴 일도 없다.

### 이 cc 접미사 표는 Jcc/CMOVcc/SETcc 전부 공통
이 cc 접미사 표는 Jcc([JE/JZ](./rev-0067-je-jz.md), [JNE/JNZ](./rev-0068-jne-jnz.md), [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md), [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)), CMOVcc, [SETcc](./rev-0076-setcc.md)에서 전부 동일하게 적용된다 — 명령어의 "동작"(분기냐, 이동이냐, 0/1 기록이냐)만 다르고 "어떤 플래그 조합을 테스트하는가"는 완전히 같은 규칙이다.

| 접미사 | 테스트하는 플래그 조건 | 의미 |
|---|---|---|
| E / Z | ZF = 1 | equal / zero |
| NE / NZ | ZF = 0 | not equal / not zero |
| G / NLE | ZF = 0 AND SF = OF | signed greater |
| GE / NL | SF = OF | signed greater or equal |
| L / NGE | SF ≠ OF | signed less |
| LE / NG | ZF = 1 OR SF ≠ OF | signed less or equal |
| A / NBE | CF = 0 AND ZF = 0 | unsigned above |
| AE / NB / NC | CF = 0 | unsigned above or equal |
| B / NAE / C | CF = 1 | unsigned below |
| BE / NA | CF = 1 OR ZF = 1 | unsigned below or equal |
| S | SF = 1 | sign(negative) |
| NS | SF = 0 | not sign |
| O | OF = 1 | overflow |
| NO | OF = 0 | no overflow |
| P / PE | PF = 1 | parity even |
| NP / PO | PF = 0 | parity odd |

실제 mnemonic: `CMOVE`/`CMOVZ`, `CMOVNE`/`CMOVNZ`, `CMOVG`, `CMOVGE`, `CMOVL`, `CMOVLE`, `CMOVA`, `CMOVAE`, `CMOVB`, `CMOVBE`, `CMOVS`, `CMOVNS` 등 — `J` 대신 `CMOV`가 붙을 뿐, 접미사 규칙은 `Jcc`와 완전히 같다.

**signed vs unsigned 주의**: 같은 비트 패턴이라도 signed로 볼 때와 unsigned로 볼 때 비교 결과가 정반대로 나올 수 있다(예: `0xFFFFFFFF`는 signed로 -1, unsigned로 4294967295). 따라서 `CMOVG`(signed greater)와 `CMOVA`(unsigned above)는 완전히 다른 조건을 테스트하며 서로 바꿔 쓰면 안 된다. 이 signed/unsigned 함정의 상세한 원리는 [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md)와 [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)에서 다룬다.

### Intel 문법과 오퍼랜드
```
CMOVcc r16, r/m16
CMOVcc r32, r/m32
CMOVcc r64, r/m64
```
`MOV`와 마찬가지로 `CMOVcc dst, src` 순서다(왼쪽이 목적지, 오른쪽이 소스). **주의**: dst는 반드시 **레지스터**여야 한다(메모리로는 못 씀). src는 레지스터 또는 메모리 모두 가능하다. 그리고 **8비트 형태(`CMOVE al, bl`처럼)는 존재하지 않는다** — 16/32/64비트만 지원한다.

### 레지스터/메모리 효과
- 조건 참: dst가 src 값으로 완전히 덮어써진다(다른 부작용 없음).
- 조건 거짓: dst는 CMOVcc 실행 전 값 그대로 남는다. 메모리는 dst가 아니므로 CMOVcc가 메모리를 쓰는 일은 없다(읽는 것은 가능).

### 플래그
- **읽는 플래그**: cc 접미사가 요구하는 플래그 조합(위 표 참고) — 보통 그 앞의 `CMP`나 `TEST` 등이 세팅해 둔 값이다.
- **쓰는 플래그**: 없다. `CMOVcc`는 어떤 플래그도 바꾸지 않는다. `Jcc`와 마찬가지로 "플래그를 소비만 하고 만들지는 않는" 명령이다.

### 스택/RIP 변화 — 이 글에서 가장 중요한 포인트
`CMOVcc`는 **제어 흐름을 전혀 바꾸지 않는다.** RIP는 조건과 무관하게 항상 다음 명령으로 그냥 진행한다. 스택도 건드리지 않는다. `Jcc`는 조건에 따라 RIP가 다른 곳으로 튈 수 있지만, `CMOVcc`는 "갈림길" 자체가 없다 — 실행되는 명령의 순서는 코드에 적힌 그대로 한 줄씩 흘러간다. 조건에 따라 달라지는 건 오직 "레지스터에 값을 쓰느냐 마느냐"뿐이다. 이 때문에 분기 예측이 틀려서 파이프라인을 통째로 비우는(flush) 일이 원천적으로 생기지 않는다.

### 컴파일러가 CMOVcc를 쓰는 이유와 대표 패턴
최적화 컴파일러(`gcc -O2` 등)는 아래처럼 짧고 예측하기 어려운(데이터에 따라 랜덤한) 조건문을 `Jcc` 분기 대신 `CMOVcc`로 바꿔치기하는 경우가 많다:

```c
int max(int a, int b) {
    return (a > b) ? a : b;
}
```
```asm
mov     eax, edi      ; eax = a  (일단 결과를 a라고 가정)
cmp     edi, esi      ; a와 b 비교
cmovle  eax, esi      ; a <= b 이면 eax를 b로 덮어씀 (a > b 이면 eax는 그대로 a)
ret
```
읽는 법: "결과를 일단 a로 가정해두고, `a <= b`라서 그 가정이 틀렸다면 b로 고쳐 쓴다." 어디에도 점프가 없다.

**왜 컴파일러가 이렇게 하나**: 최신 CPU는 분기 예측이 틀리면 이미 미리 실행해둔(speculative execution) 명령들을 전부 버리고 파이프라인을 다시 채워야 하는 큰 페널티를 문다. `max(a,b)`처럼 어느 쪽이 클지 데이터마다 랜덤이라 예측하기 어려운 짧은 조건문은, 차라리 두 값을 다 계산해두고 `CMOVcc`로 하나만 골라 쓰는 게(= "낭비되는 일"을 조금 하더라도) 분기 예측 실패 페널티보다 평균적으로 더 빠를 수 있다. 그래서 최적화 컴파일러는 이런 짧고 부작용 없는 삼항 연산자/`min`/`max`/`abs` 패턴을 즐겨 `CMOVcc`로 바꾼다.

### IDA/Ghidra 디컴파일에서 보이는 모습
디컴파일러는 대개 `CMOVcc`를 다시 삼항식(`dst = cond ? src : dst`)이나 인라인 `if`로 재구성해서 보여준다. 원래 실행 흐름에 분기가 없었다는 사실 자체는 디컴파일된 C 유사 코드만 봐서는 드러나지 않는다 — 이는 **디스어셈블리 원문을 보는 게 디컴파일 결과보다 오히려 더 정확한 몇 안 되는 경우** 중 하나다.

실전에서 자주 겪는 함정: 디컴파일 결과가 `if (a > b) x = a; else x = b;`처럼 보여서 "분기가 있겠지"라 생각하고 그 지점에 브레이크포인트를 걸었는데, 실제 바이너리에는 `CMOVcc` 한 줄만 있어서 브레이크포인트가 절대 안 걸리는 경우다. `if`/`else`처럼 보이는 코드에 실제 조건부 점프(`jg`, `jle` 등)가 안 보인다면, `CMOVcc`로 컴파일됐을 가능성을 의심하고 그 명령 자체에 브레이크포인트를 걸어야 한다.

### 리버싱 관점에서의 의미
- `CMOVcc`는 의도적인 난독화가 아니라 **정상적인 컴파일러 최적화**다. 하지만 결과적으로 "분기 지점에 브레이크포인트를 걸어 조건을 확인한다"는 표준 분석 방식을 무력화시킨다는 점에서 안티 분석 기법과 비슷한 효과를 낸다.
- 반대로, `CMOVcc`는 절대 분기 예측 실패가 없기 때문에 실행 시간이 입력값에 따라 달라지지 않는다(constant-time). 그래서 암호학 코드(비밀번호/키 비교, 상수 시간 비교 함수 등)에서는 **타이밍 사이드채널 공격을 막으려고 일부러** `Jcc` 대신 `CMOVcc`를 사용하는 경우가 있다. 크립토 관련 코드에서 `CMOVcc`가 자주 보인다면 "의도적인 상수 시간 구현"일 가능성을 염두에 두자.

## 화면/코드에서 보이는 징후
- `cmovg`, `cmovle`, `cmova`, `cmovb`, `cmove`, `cmovne` 등 — cc 접미사가 `Jcc`와 동일한 이름 규칙
- 직전에 `cmp`나 `test`가 있고, 그 다음 줄에 곧바로 `mov` + `cmovcc` 쌍이 오는 패턴
- 디컴파일러가 삼항 연산자(`? :`)나 `if`/`else` 한 줄짜리로 보여주는데, 정작 어셈블리에는 `jcc` 계열 명령이 하나도 없는 경우

## 가장 먼저 할 것
1. `CMOVcc` 앞의 `CMP`/`TEST`가 무엇을 비교하는지 확인한다.
2. cc 접미사를 표에서 찾아 정확히 어떤 플래그 조합을 테스트하는지 확인한다(signed/unsigned 구분 필수).
3. dst 레지스터의 "조건 전 값"과 src 값이 각각 무엇인지 확인해서, 조건이 참/거짓일 때 최종 값이 뭐가 되는지 두 경우 모두 계산해본다.

## 단계별 절차

**1) 앞의 비교 찾기**
```asm
cmp     edi, esi
cmovle  eax, esi
```
`cmp edi, esi`가 `edi - esi`를 계산해 플래그를 세팅한다. `cmovle`는 LE(signed less or equal) 조건, 즉 `ZF=1 OR SF≠OF`를 테스트한다.

**2) dst의 "이전 값"과 src 값 확인**
`cmovle eax, esi`가 실행되기 직전 `eax`에 이미 들어있던 값(보통 앞줄의 `mov eax, edi`로 세팅된 값)을 확인하고, 조건이 거짓이면 `eax`는 그 값을 그대로 유지한다는 걸 기억한다.

**3) 조건 참/거짓 각각의 결과를 손으로 계산**
`edi=5, esi=3`이라면 `5 <= 3`은 거짓이므로 `cmovle`는 실행되지 않고 `eax`는 `edi`(=5)로 남는다 → `max(5,3)=5`.

**4) IDA/Ghidra 디컴파일과 대조**
디컴파일 결과가 삼항식으로 나오면, 그게 실제로는 `CMOVcc` 한 줄이라는 걸 인지하고 분기로 착각해 브레이크포인트를 걸지 않는다.

## 명령어/단축키
- IDA: 명령어 위에서 `?`(Value 계산)나 레지스터 창에서 실행 전/후 값을 비교. `CMOVcc` 자체에 브레이크포인트를 걸 때는 `F2`.
- x64dbg: 명령어 라인 우클릭 → "Toggle Breakpoint", 레지스터 패널에서 실행 전/후 값을 직접 비교.
- GDB/Pwndbg: `stepi`로 한 줄씩 실행하며 `info registers eax`(또는 `p $eax`)로 CMOVcc 실행 전후 값을 비교.

## 출력 해석
- 디버거에서 `cmovle eax, esi`를 실행했는데 `eax` 값이 안 바뀌었다면 → 조건이 거짓이었다는 뜻(정상 동작, 버그 아님).
- IDA 디컴파일에 `if`/삼항식이 보이는데 실제 디스어셈블리에 대응하는 `jcc`가 없다면 → `CMOVcc`로 컴파일된 것.

## 흔한 실수
- `CMOVcc`가 분기라고 착각해서 "분기 안 타는 지점"에 브레이크포인트를 걸고 하염없이 기다리는 것 — 애초에 분기가 없으므로 절대 안 걸린다.
- `CMOVG`(signed)와 `CMOVA`(unsigned)를 같은 것으로 착각하는 것 — 완전히 다른 플래그 조합을 테스트한다. 자세한 원리는 [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md), [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md) 참고.
- 조건이 거짓일 때 `CMOVcc`가 "아예 아무 일도 안 했다"고 생각하는 것 — 정확히는 "dst를 이전 값 그대로 유지한다"는 뜻이며, 그 이전 값이 무엇인지 추적하고 있어야 레지스터 값 변화를 제대로 읽을 수 있다.

## 막혔을 때 다음 체크
- 디컴파일에서 분기처럼 보이는 코드에 브레이크포인트가 안 걸린다면 → 어셈블리 원문에서 `jcc` 대신 `cmovcc`가 쓰였는지 확인.
- cc 접미사 뜻이 헷갈리면 → 위 표를 다시 확인하고, signed 문제인지 unsigned 문제인지부터 구분.
- dst 값이 예상과 다르면 → CMOVcc 직전 dst에 이미 들어있던 값을 놓쳤을 가능성이 크다. 그 위의 `mov`/`lea` 등을 다시 확인.

## 미니 예제

**예제 1 — max(a, b)**
```c
int max(int a, int b) { return (a > b) ? a : b; }
```
```asm
mov     eax, edi
cmp     edi, esi
cmovle  eax, esi     ; a <= b 이면 b로 교체
ret
```

**예제 2 — min(a, b)**
```c
int min(int a, int b) { return (a < b) ? a : b; }
```
```asm
mov     eax, edi
cmp     edi, esi
cmovge  eax, esi     ; a >= b 이면 b로 교체
ret
```

**예제 3 — 일반 삼항 연산자**
```c
int x = cond ? a : b;
```
```asm
mov     eax, ebx      ; eax = b (기본값)
test    ecx, ecx      ; cond 검사 (0인지 아닌지)
cmovnz  eax, edx       ; cond != 0 이면 eax = a
```

**예제 4 — 0 이하이면 0으로 클램프 (CMOVS)**
```c
int clamp_nonneg(int x) { return (x < 0) ? 0 : x; }
```
```asm
mov     eax, edi
test    edi, edi
cmovs   eax, ecx      ; SF=1(음수)이면 eax = ecx(0으로 미리 세팅해둔 레지스터)
```

## 관련 글
- [SETcc: 조건 결과를 0 또는 1로 만들기](./rev-0076-setcc.md) — 같은 cc 접미사, 분기 없이 0/1 바이트를 기록
- [JE/JZ: ZF가 1일 때 분기](./rev-0067-je-jz.md)
- [JNE/JNZ: ZF가 0일 때 분기](./rev-0068-jne-jnz.md)
- [JG/JGE/JL/JLE: Signed 비교 분기](./rev-0069-jg-jge-jl-jle.md)
- [JA/JAE/JB/JBE: Unsigned 비교 분기](./rev-0070-ja-jae-jb-jbe.md)
- [JMP: 무조건 분기](./rev-0066-jmp.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [FLAGS 레지스터 개요](./rev-0088-flags-overview.md)
- CMP: 값을 바꾸지 않는 SUB 비교 (예정)

## 출처/검증
- CMOVcc 동작 및 오퍼랜드 형식: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CMOVcc—Conditional Move" 섹션 기준 (2026-09-08 검증).
- 분기 예측/파이프라인 플러시로 인한 분기 비용과 컴파일러의 branchless 최적화 배경: 일반 컴퓨터 구조/컴파일러 최적화 통념(SRC-GENERAL-ASM) 기준.
