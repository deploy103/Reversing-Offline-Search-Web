---
id: REV-0076
title: "SETcc: 조건 결과를 0 또는 1로 만들기"
slug: "rev-0076-setcc"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - setcc
  - SETcc
  - sete
  - setz
  - setne
  - setnz
  - setg
  - setge
  - setl
  - setle
  - seta
  - setae
  - setb
  - setbe
  - sets
  - setns
  - set byte on condition
  - 조건 바이트 기록
  - 불리언 반환 어셈블리
  - boolean asm
  - xor eax eax sete al
  - SETcc 뭐임
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - set 명령어
  - SETcc가 뭐죠
  - sete al 뜻
  - 조건에 따라 0 1
symptom_keywords: []
last_verified: "2026-09-08"
---

## 한 줄 요약
`SETcc`는 "조건(cc)이 참이면 목적지 1바이트에 1을, 거짓이면 0을 써넣는다"는 명령어다. 분기(jump)도 아니고 데이터 이동(`CMOVcc`)도 아니라, 비교 결과 자체를 숫자 `0`/`1`로 "확정"시키는 명령이다.

## 언제 검색해야 하나
- 디스어셈블리에 `sete al`, `setg bl`, `seta cl` 같은 명령이 나오는데 무슨 뜻인지 모를 때
- `xor eax, eax` 다음에 `cmp`, 그다음 `sete al`이 연달아 나오는 패턴을 봤는데 왜 굳이 `xor`을 먼저 하는지 모를 때
- C 함수가 `return a == b;`처럼 불리언을 반환하는데 그 어셈블리에 `jcc`(분기)가 하나도 없어서 이상할 때
- "SETcc 뭐임", "sete al 뜻"처럼 처음 보는 명령어를 찾아볼 때

## 핵심 개념

### SETcc가 실제로 하는 일
`SETcc dst`는 (이전 명령이 세팅해둔) 플래그를 검사해서:
- 조건이 **참**이면 → `dst`(8비트)에 `1`을 기록
- 조건이 **거짓**이면 → `dst`에 `0`을 기록

`CMOVcc`와 결정적으로 다른 점: `CMOVcc`는 조건이 거짓이면 목적지를 안 건드리지만, `SETcc`는 조건이 거짓이어도 **반드시 0을 써넣는다** — 항상 결과가 확정된다.

### 이 cc 접미사 표는 Jcc/CMOVcc/SETcc 전부 공통
이 cc 접미사 표는 Jcc([JE/JZ](./rev-0067-je-jz.md), [JNE/JNZ](./rev-0068-jne-jnz.md), [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md), [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)), [CMOVcc](./rev-0075-cmovcc.md), SETcc에서 전부 동일하게 적용된다 — 명령어의 "동작"만 다르고 "어떤 플래그 조합을 테스트하는가"는 완전히 같은 규칙이다.

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

실제 mnemonic: `SETE`/`SETZ`, `SETNE`/`SETNZ`, `SETG`, `SETGE`, `SETL`, `SETLE`, `SETA`, `SETAE`, `SETB`, `SETBE`, `SETS`, `SETNS` 등 — 역시 `Jcc`/`CMOVcc`와 같은 접미사 규칙이다.

**signed vs unsigned 주의**: 같은 비트 패턴이 signed로는 음수, unsigned로는 아주 큰 양수로 해석될 수 있다(예: `0xFFFFFFFF`는 signed로 -1, unsigned로 4294967295). 그래서 `SETG`(signed greater)와 `SETA`(unsigned above)는 서로 다른 조건을 테스트하며, C에서 변수 타입이 `int`냐 `unsigned int`냐에 따라 컴파일러가 어느 쪽을 생성할지 갈린다. 상세 원리는 [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md), [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md) 참고.

### Intel 문법과 오퍼랜드
```
SETcc r/m8
```
목적지는 **오직 8비트 레지스터나 메모리 한 바이트**만 가능하다(`AL`, `BL`, `CL`, `byte ptr [rbx]` 등). 16/32/64비트 형태는 없다 — 애초에 결과가 0 아니면 1이라 1바이트면 충분하기 때문이다.

### 레지스터/메모리 효과 — 상위 바이트 주의
`sete al`은 `AL`(하위 1바이트)에만 0 또는 1을 쓴다. `RAX`/`EAX`의 나머지 상위 바이트는 **전혀 건드리지 않는다**(x86의 부분 레지스터 쓰기 특성). 그래서 `sete al` 뒤에 `eax`/`rax` 전체를 "0 아니면 1"인 값으로 쓰려면, 그 앞에 보통 `xor eax, eax`로 레지스터 전체를 미리 0으로 초기화해 둔다. `SETcc`가 보장하는 건 하위 바이트뿐이므로, 이 `xor + setcc` 조합은 매우 흔하고 알아볼 가치가 있는 관용구(idiom)다.

### 플래그
- **읽는 플래그**: cc 접미사가 요구하는 플래그 조합(위 표) — 보통 앞의 `CMP`/`TEST`가 세팅.
- **쓰는 플래그**: 없다.

### 스택/RIP 변화
`CMOVcc`와 마찬가지로 제어 흐름을 전혀 바꾸지 않는다. RIP는 항상 다음 명령으로 진행하고, 스택도 건드리지 않는다. 분기가 없는 한 줄짜리 명령이다.

### 컴파일러가 SETcc를 쓰는 이유와 대표 패턴
`SETcc`는 컴파일러가 C의 불리언 값 자체(비교 연산자의 "참/거짓 값")를 변수에 저장하거나 반환할 때 분기 없이 구현하는 표준 방법이다:

```c
int is_equal(int a, int b) {
    return a == b;
}
```
```asm
xor     eax, eax      ; eax 전체(상위 바이트 포함)를 0으로 초기화
cmp     edi, esi      ; a, b 비교
sete    al             ; a == b 이면 al = 1, 아니면 al = 0 (eax 상위는 이미 xor로 0)
ret
```

**핵심 구분 기준**: `SETcc`는 비교의 "참/거짓 값 자체"가 필요할 때(변수에 저장, 반환값 등), `Jcc`는 비교 결과로 "분기"가 필요할 때(`if` 조건) 쓰인다는 걸 기억해두면 어셈블리를 읽을 때 훨씬 빨리 의도를 파악할 수 있다.

또한 `SETcc`로 만든 0/1 값들을 이후 `AND`/`OR`/`TEST`로 조합하면, `a == b && c > d` 같은 복합 불리언 조건을 추가 분기 없이 계산할 수 있다 — 컴파일러가 이런 패턴도 자주 쓴다.

### IDA/Ghidra 디컴파일에서 보이는 모습
디컴파일러는 대개 `xor`+`cmp`+`setcc` 시퀀스를 원래의 불리언 식(`return a == b;`)으로 깔끔하게 되돌려 보여주고, 그 내부 메커니즘(부분 레지스터 초기화 등)은 숨긴다. 디스어셈블리 원문에서 이 세 줄을 볼 때는 "서로 무관한 세 개의 명령"이 아니라 "하나의 불리언 값을 계산하는 하나의 묶음"으로 읽는 습관을 들이는 게 좋다.

### 리버싱 관점에서의 의미
`xor reg,reg` → `cmp`/`test` → `setcc reg8` 시퀀스는 "이 함수가 불리언(참/거짓)을 계산/반환한다"는 매우 신뢰도 높은 지문(fingerprint)이다. 낯선 바이너리를 훑어볼 때 이 패턴만 보고도 디컴파일 없이 "검증 함수, 비교 함수(예: 커스텀 `strcmp`류, 라이선스/시리얼 검사 함수)"일 가능성을 빠르게 짚어낼 수 있다. 물론 `SETG`/`SETA` 같은 signed/unsigned 접미사 혼동 위험은 `Jcc`/`CMOVcc`와 동일하게 존재한다.

## 화면/코드에서 보이는 징후
- `sete al`, `setne al`, `setg bl`, `seta cl`, `setb dl` 등 8비트 레지스터/메모리 목적지
- 직전에 `xor reg, reg`(전체 레지스터 0 초기화) → `cmp`/`test` → `setcc reg8` 3단 콤보
- `SETcc` 뒤에 `and`/`or`/`test`로 다른 0/1 값과 결합되는 패턴(복합 불리언 조건)

## 가장 먼저 할 것
1. `SETcc` 앞의 `CMP`/`TEST`가 무엇을 비교하는지 확인한다.
2. cc 접미사를 표에서 찾아 정확히 어떤 플래그 조합을 테스트하는지 확인한다(signed/unsigned 구분 필수).
3. 그 앞에 `xor reg,reg`가 있는지 확인해서, 이후 코드가 8비트가 아니라 32/64비트 전체를 "0 또는 1" 값으로 쓰는지 판단한다.

## 단계별 절차

**1) xor + cmp + setcc 삼단 콤보 인식**
```asm
xor     eax, eax
cmp     edi, esi
sete    al
```
이 세 줄 전체를 "`eax = (edi == esi) ? 1 : 0`" 한 문장으로 읽는다.

**2) cc 접미사로 조건 확정**
`sete`는 E(ZF=1) 조건이므로 `edi == esi`일 때 1이다.

**3) 이후 코드에서 이 값의 쓰임 추적**
```asm
sete    al
test    al, al
jz      not_equal
```
→ `SETcc`로 만든 불리언 값을 다시 `TEST`+`Jcc`로 검사해서 분기하는 패턴 — 결과값을 잠깐 저장해뒀다가 나중에 분기에 쓰는 경우다.

**4) IDA/Ghidra 디컴파일과 대조**
디컴파일 결과가 `return a == b;`처럼 단순 불리언 식으로 나오면, 실제로는 `xor+cmp+setcc` 3줄이 그 뒤에 숨어 있다는 걸 기억한다.

## 명령어/단축키
- IDA: `SETcc` 명령 위에서 레지스터 창의 실행 전/후 값 비교, `F2`로 브레이크포인트.
- x64dbg: 명령 라인 우클릭 → "Toggle Breakpoint", 레지스터 패널에서 `AL`/`EAX` 값 비교(하위 바이트만 바뀌는지 확인).
- GDB/Pwndbg: `stepi`로 한 줄씩 실행하며 `p $al`, `p/x $eax`로 하위 바이트와 전체 레지스터 값을 따로 확인.

## 출력 해석
- `sete al` 실행 후 `al`이 `1`이면 직전 비교가 참이었다는 뜻, `0`이면 거짓.
- `eax` 상위 바이트에 이상한 값(0이 아닌 잔여값)이 남아 있다면 → 그 앞에 `xor eax,eax`가 없었거나 놓쳤을 가능성. `SETcc`는 하위 1바이트만 보장한다.

## 흔한 실수
- `SETcc`를 `Jcc`처럼 분기한다고 착각하는 것 — `SETcc`는 절대 분기하지 않고 바이트 하나만 기록한다.
- `xor eax,eax`가 왜 앞에 있는지 이해 못 하고 무시하는 것 — 이게 없으면 `eax` 상위 바이트에 이전 값이 남아있어 전체 레지스터를 "0/1 불리언"으로 쓸 수 없다는 걸 놓치면 값 추적이 틀어진다.
- `SETG`(signed)와 `SETA`(unsigned)를 같은 것으로 착각하는 것 — [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md), [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)의 signed/unsigned 함정과 동일하게 적용된다.

## 막혔을 때 다음 체크
- 레지스터 값에 이상한 상위 바이트가 남아있다면 → `xor reg,reg`가 있었는지 위쪽 코드를 다시 확인.
- cc 접미사 뜻이 헷갈리면 → 위 표를 다시 확인하고 signed/unsigned부터 구분.
- `SETcc` 결과가 바로 안 쓰이는 것 같다면 → 스택/다른 레지스터에 잠깐 저장됐다가 나중에 `TEST`+`Jcc`나 `AND`/`OR`로 결합돼 쓰이는지 아래쪽 코드를 계속 따라간다.

## 미니 예제

**예제 1 — is_equal(a, b)**
```c
int is_equal(int a, int b) { return a == b; }
```
```asm
xor     eax, eax
cmp     edi, esi
sete    al
ret
```

**예제 2 — signed 비교, SETG**
```c
int is_greater_signed(int a, int b) { return a > b; }
```
```asm
xor     eax, eax
cmp     edi, esi
setg    al             ; SF = OF 이고 ZF = 0 일 때 1
ret
```

**예제 3 — unsigned 비교, 같은 C 한 줄이 타입만 바뀌면 SETA**
```c
int is_greater_unsigned(unsigned int a, unsigned int b) { return a > b; }
```
```asm
xor     eax, eax
cmp     edi, esi
seta    al             ; CF = 0 이고 ZF = 0 일 때 1 (signed의 setg와 다른 명령)
ret
```

**예제 4 — 복합 불리언 (a == b && c > d)**
```c
int both(int a, int b, int c, int d) { return (a == b) && (c > d); }
```
```asm
xor     eax, eax
cmp     edi, esi
sete    al              ; al = (a == b)
xor     ecx, ecx
cmp     edx, r8d
setg    cl              ; cl = (c > d)
and     al, cl           ; 둘 다 참이어야 al = 1
```

## 관련 글
- [CMOVcc: 분기 없는 조건부 이동](./rev-0075-cmovcc.md) — 같은 cc 접미사, 분기 없이 값 자체를 옮김
- [JE/JZ: ZF가 1일 때 분기](./rev-0067-je-jz.md)
- [JNE/JNZ: ZF가 0일 때 분기](./rev-0068-jne-jnz.md)
- [JG/JGE/JL/JLE: Signed 비교 분기](./rev-0069-jg-jge-jl-jle.md)
- [JA/JAE/JB/JBE: Unsigned 비교 분기](./rev-0070-ja-jae-jb-jbe.md)
- [JMP: 무조건 분기](./rev-0066-jmp.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [FLAGS 레지스터 개요](./rev-0088-flags-overview.md)
- CMP: 값을 바꾸지 않는 SUB 비교 (예정)

## 출처/검증
- SETcc 동작 및 오퍼랜드 형식(8비트 전용): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "SETcc—Set Byte on Condition" 섹션 기준 (2026-09-08 검증).
- x86 부분 레지스터 쓰기(상위 바이트 미변경) 특성 및 xor+setcc 관용구: 일반 x86 어셈블리/컴파일러 코드 생성 통념(SRC-GENERAL-ASM) 기준.
