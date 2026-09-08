---
id: REV-0068
title: "JNE와 JNZ: ZF가 0일 때 분기"
slug: "rev-0068-jne-jnz"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - jne
  - JNE
  - jnz
  - JNZ
  - jne jnz
  - jump if not equal
  - jump if not zero
  - ZF
  - zero flag
  - 제로 플래그
  - 다르면 분기
  - 0이 아니면 분기
  - cmp jne
  - test jnz
  - Jcc
  - jcc 조건 분기
  - 조건부 점프
  - 조건 분기
  - 반전 조건 분기
  - 카운트 루프 jnz
  - dec jnz
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - jne란
  - jnz란
  - jne jnz 차이
  - jne와 jnz 차이
  - jne jnz 같은거
  - jnz가 뭐임
  - if a==b 인데 왜 jne가 나옴
symptom_keywords:
  - jne jnz 차이를 모르겠음
  - if a==b 조건인데 어셈블리에 jne가 나와서 헷갈림
  - dec jnz 루프가 뭔지 모르겠음
  - jne fail 패턴이 뭔지 모르겠음
---

## 한 줄 요약
`JNE`와 `JNZ`도 `JE`/`JZ`와 마찬가지로 **완전히 같은 명령어(같은 opcode)**이며, "ZF(Zero Flag)가 0이면 분기하라" — 즉 `JE`/`JZ`의 정반대 조건을 검사한다. 그리고 이 글에서 가장 중요한 포인트는, 소스코드의 `if (a == b) { ... }`가 실제로는 `je`가 아니라 **`jne`로 컴파일되는 경우가 압도적으로 많다**는 것이다.

## 언제 검색해야 하나
- 디스어셈블리에 `jne`가 나오는데 무슨 뜻인지 모를 때
- 소스에 `if (a == b)`라고 되어 있는 것 같은데 어셈블리에는 `jne`가 나와서 "왜 부정 조건이 나오지?"라고 헷갈릴 때
- `dec ecx` 다음에 `jnz loop_start`가 나오는 카운트 루프를 만났을 때
- 시리얼/패스워드 비교 루프에서 `jne fail`이 반복되는 코드를 볼 때, 이걸 패치해서 우회하는 원리가 궁금할 때
- IDA/Ghidra 디컴파일 결과와 실제 raw 디스어셈블리의 조건이 반대로 보여서 헷갈릴 때

## 핵심 개념

### JNE와 JNZ는 같은 명령어다
`JNE`(Jump if Not Equal)와 `JNZ`(Jump if Not Zero)는 [JE/JZ](./rev-0067-je-jz.md)와 정확히 같은 관계다 — **opcode가 완전히 동일**하다(단거리 분기 0x75, 장거리 분기 0x0F 85). 검사하는 조건은 단 하나, `ZF = 0`이다. `CMP` 뒤에서는 "다르면 점프"라는 뜻으로 `JNE`, 산술/논리 연산 뒤에서는 "결과가 0이 아니면 점프"라는 뜻으로 `JNZ`라고 부르는 것도 관례일 뿐 동작은 완전히 같다.

### 조건 코드(Jcc) 전체 표
이 표는 [JE/JZ](./rev-0067-je-jz.md)에서도 동일하게 제공되는 Jcc 조건 코드 기준 표다. `JNE`/`JNZ`는 `JE`/`JZ`의 정확한 논리 부정(`ZF=0`)이라는 점을 이 표에서 바로 확인할 수 있다.

| 접미사 | 다른 표기 | 테스트하는 플래그 조건 | 의미 |
|---|---|---|---|
| E / Z | — | ZF = 1 | equal / zero |
| NE / NZ | — | ZF = 0 | not equal / not zero |
| G / NLE | — | ZF = 0 AND SF = OF | signed greater |
| GE / NL | — | SF = OF | signed greater or equal |
| L / NGE | — | SF ≠ OF | signed less |
| LE / NG | — | ZF = 1 OR SF ≠ OF | signed less or equal |
| A / NBE | — | CF = 0 AND ZF = 0 | unsigned above |
| AE / NB / NC | — | CF = 0 | unsigned above or equal |
| B / NAE / C | — | CF = 1 | unsigned below |
| BE / NA | — | CF = 1 OR ZF = 1 | unsigned below or equal |
| S | — | SF = 1 | sign(negative) |
| NS | — | SF = 0 | not sign |
| O | — | OF = 1 | overflow |
| NO | — | OF = 0 | no overflow |
| P / PE | — | PF = 1 | parity even |
| NP / PO | — | PF = 0 | parity odd |

### Intel 문법과 오퍼랜드
```
JNE  rel8    ; 짧은 상대 분기 (opcode 0x75)
JNE  rel32   ; 긴 상대 분기 (opcode 0x0F 85)
JNZ  rel8    ; JNE와 완전히 동일한 opcode
JNZ  rel32   ; JNE와 완전히 동일한 opcode
```
오퍼랜드는 목표 레이블을 가리키는 상대 오프셋 하나뿐이다.

### 플래그: 읽기만 하고 쓰지 않는다
`JNE`/`JNZ`가 **읽는** 플래그는 `ZF` 하나뿐이며, `CF`/`SF`/`OF`/`PF`/`AF`는 전혀 보지 않는다. 실행 후에도 어떤 플래그도 바꾸지 않는다. `ZF`는 언제나 그 앞의 `CMP`/`TEST`/산술 명령이 이미 계산해 둔 값이고, `JNE`/`JNZ`는 그 값을 읽어 "0인가 아닌가"만 판단한다.

### 스택/RIP 변화
조건이 참(`ZF=0`)이면 `RIP`가 목표 주소로 바뀐다. 거짓이면 다음 명령으로 그냥 진행한다. 스택(RSP)에는 아무 영향이 없다 — [CALL](./rev-0071-call.md)처럼 반환 주소를 push하는 일은 없다.

### 가장 중요한 포인트: 반전된 스킵 패턴
초보자가 어셈블리와 C 소스를 머릿속에서 왔다갔다 번역할 때 가장 많이 걸려 넘어지는 지점이 바로 이것이다.

```c
if (a == b) {
    do_something();
}
next_line();
```
이 코드는 컴파일러에 의해 보통 아래처럼 번역된다:
```asm
cmp     eax, ebx
jne     skip_body      ; 조건 FALSE (a != b) -> if 몸통을 건너뜀
call    do_something
skip_body:
call    next_line
```

**왜 `je`가 아니라 `jne`가 나올까?** 컴파일러는 "조건이 참일 때 실행할 코드"를 코드 순서상 바로 뒤에 배치하고, "조건이 거짓일 때는 그 블록을 건너뛰어야" 하므로, **조건을 뒤집어서(negate) "거짓이면 건너뛰어라"는 분기를 만드는 쪽이 자연스럽다.** 즉 소스의 `==`가 어셈블리에서는 `jne`(부정 조건)로 나타나는 것이 오히려 표준적인 컴파일 패턴이다.

**절대 잊지 말아야 할 규칙**: 디스어셈블리에서 `jne`/`jnz`를 봤다고 해서 소스가 `!=` 비교라고 단정하지 말 것. `if (a == b) { ... }` 패턴에서 `jne`가 압도적으로 자주 나온다. 실제로 소스의 연산자를 알아내려면, `jne`가 가리키는 목표(건너뛰는 곳)와 건너뛰지 않았을 때 실행되는 코드(몸통) 중 어느 쪽이 "조건이 참일 때 실행되어야 하는 코드"인지를 문맥으로 판단해야 한다.

### 대조 예시: 반전되지 않고 그대로 대응되는 경우
모든 `jne`/`jnz`가 반전된 것은 아니다. `while (x != 0) { ... }` 같은 루프는 소스의 `!=` 조건이 그대로 `jne`/`jnz`로 나타난다.
```c
while (x != 0) {
    x = process(x);
}
```
```asm
loop_check:
    test    eax, eax
    jz      loop_end       ; x == 0 이면 루프 종료 (반전됨: 반복 조건은 x!=0)
    call    process
    jmp     loop_check
loop_end:
```
여기서는 오히려 `jz`(반전)가 쓰였다는 점에 주목하자 — "반복 조건(`x != 0`)이 거짓이면(`x==0`) 루프를 빠져나가라"는 스킵 패턴이 루프에도 똑같이 적용된 것이다. 반면 아래처럼 **루프 뒤쪽(back-edge)** 에서 "계속 반복할지" 판단하는 형태는 `jnz`가 소스의 `!=` 조건과 그대로 대응된다:
```asm
loop_body:
    call    process
    dec     ecx
    jnz     loop_body      ; ecx != 0 이면 (아직 남았으면) 반복
```
이 경우는 반전이 아니라 "카운터가 0이 아닌 동안 계속 반복"이라는 조건이 `jnz`에 그대로 직결된다. **결론**: `jne`/`jnz`가 반전된 스킵 패턴인지, 소스 조건과 직접 대응되는 것인지는 그 분기가 어디로 가는지(몸통을 건너뛰는가, 루프를 계속하는가)를 보고 판단해야 한다.

### TEST + JNZ 관용구, 카운트 루프
`TEST reg, reg` 다음의 `JNZ`는 "값이 0이 아닌가?" 또는 "특정 비트가 켜져 있는가?"를 검사하는 관용구다.
```asm
test    eax, eax
jnz     nonzero_case   ; eax != 0 이면 분기
```
또한 `DEC`/`JNZ` 조합은 가장 고전적인 **카운트 루프(counted loop)** 패턴이다:
```asm
mov     ecx, 10
loop_top:
    ; ... 반복할 코드 ...
    dec     ecx
    jnz     loop_top    ; ecx가 0이 될 때까지 반복
```
이 패턴은 사실상 x86의 오래된 전용 루프 명령 `LOOP`(내부적으로 ECX를 감소시키고 0이 아니면 분기)가 하는 일을 `DEC`+`JNZ`로 직접 풀어쓴 것과 같다. 최신 컴파일러는 `LOOP` 명령 자체보다 이 `DEC`+`JNZ` 조합을 더 자주 생성하며, 손으로 짠 어셈블리나 최적화가 약한 코드에서 흔히 보인다.

### IDA/Ghidra 디컴파일 화면에서 보이는 형태
디컴파일러(F5)는 `cmp`+`jne`/`jnz` 쌍을 보면 대부분 사람이 읽기 편한 `if`/`else` 구조로 **다시 뒤집어서(un-invert)** 보여준다 — 즉 raw 어셈블리에는 `jne skip_body`가 있어도, 디컴파일러는 이를 `if (a == b) { ... }`처럼 자연스러운 형태로 재구성해준다는 뜻이다. 이 재구성은 대체로 정확하다.

문제는 **raw 디스어셈블리(어셈블리 원문)를 직접 읽을 때**다. 이때는 위의 반전을 스스로 머릿속에서 되돌려야 한다. 순서는 다음과 같다:
1. `jne`/`jnz` 바로 위에 있는 `cmp`/`test` 명령을 찾고 두 오퍼랜드를 확인한다.
2. `jne`는 "두 오퍼랜드가 **다를 때(같지 않을 때)**" 분기(점프)한다는 것을 기억한다.
3. 점프하지 않고 **그대로 다음 줄로 떨어지는 경로(fallthrough)**가 바로 "두 오퍼랜드가 **같은** 경우"의 경로다.
4. 각 경로(점프한 곳 / 떨어진 곳)가 각각 어떤 코드로 이어지는지 따라가서, 어느 쪽이 원래 C의 `if` 몸통이고 어느 쪽이 `else`(또는 몸통 없음)인지 재구성한다.

### 리버싱에서의 의미
`JNZ` 기반 카운트 루프와 `JNE` 기반 "비교 실패 시 분기" 패턴은 CTF 크랙미에서 극도로 흔하다. 대표적으로 시리얼/패스워드 검사 루프는 다음과 같은 형태를 띤다:
```asm
check_loop:
    mov     al, [rsi + rcx]
    cmp     al, [rdi + rcx]
    jne     fail          ; 한 글자라도 다르면 즉시 실패로 분기
    inc     rcx
    cmp     rcx, len
    jne     check_loop
    jmp     success
fail:
    ; "Wrong!" 출력
success:
    ; "Correct!" 출력
```
이런 코드에서 **`jne fail`을 `je fail`로 바꾸거나 NOP으로 지워버리는 것**은 (교육/CTF 맥락에서) "체크 패치(patching the check)"라고 불리는 매우 고전적이고 흔한 크랙미 우회 기법이다. 다만 이는 검사 로직 자체를 무력화하는 것일 뿐 원래 정답 시리얼을 알아내는 것과는 다르며, 실제 CTF 라이트업에서 "일단 분기 하나만 패치해서 통과시켜본다"는 형태로 자주 등장한다.

## 가장 먼저 할 것
`jne`/`jnz`를 봤다면 가장 먼저 확인할 것은 **"이게 반전된 스킵 패턴인지, 아니면 조건과 직결된 것인지"**다.
1. 바로 위의 `cmp`/`test`가 무엇을 비교하는지 읽는다.
2. `jne`/`jnz`가 점프하는 곳으로 먼저 가본다 — 거기가 `fail:`, `wrong:`, 루프의 맨 위(back-edge) 중 어디인지 본다.
3. 점프하지 않고 fallthrough로 이어지는 코드가 "정상/성공 처리"처럼 보이는지 확인한다.
4. 위 두 가지 정황으로 "몸통을 건너뛰는 패턴(반전)"인지 "카운터/조건이 그대로 이어지는 패턴"인지 판단한다 — 판단 기준은 본문의 "가장 중요한 포인트" 절 참고.

## 단계별 절차
1. **IDA 그래프뷰에서 `jne`/`jnz` 노드를 찾는다.** 두 갈래로 갈라지는 지점이다.
2. **바로 위 블록**에서 `cmp`/`test` 명령과 오퍼랜드를 확인한다.
3. **점프 목표 블록**을 클릭해서 이동해보고, 그 안에 `fail`/`wrong`/에러 처리 코드가 있는지, 아니면 루프 상단으로 돌아가는지 확인한다.
4. **fallthrough 블록**도 확인해서 "몸통(성공/정상 처리)"인지 판단한다.
5. **F5로 디컴파일**해서 IDA가 재구성한 `if`문과 비교한다 — 디컴파일러는 이미 반전을 풀어서 자연스러운 형태로 보여주므로, raw 어셈블리 해석이 맞는지 검증하는 용도로 쓴다.
6. 판단이 애매하면 브레이크포인트(`F2`)를 걸고 `F9`로 실행해 실제 `ZF` 값과 어느 경로로 가는지 직접 관찰한다.

## 명령어/단축키
- IDA: `Space`(그래프뷰/텍스트뷰 전환), `F5`(디컴파일), `F2`(브레이크포인트), `F9`(실행), 분기 화살표 클릭으로 목표 블록 이동
- x64dbg: `F2`(브레이크포인트), `F9`(실행/계속), `F7`(Step Into)로 한 줄씩 진행하며 우측 플래그 패널의 `ZF` 관찰, "Wrong!" 문자열 등을 Strings 탭에서 찾아 그 문자열을 참조하는 코드로 역추적(우클릭 → Follow)
- GDB/Pwndbg: `break *0x<jne주소>`, `info registers eflags`, `x/5i $rip`(현재 위치 주변 명령 5개 미리보기로 분기 목표까지 한눈에 확인)

## 흔한 실수
- **signed/unsigned 착각.** JNE/JNZ도 JE/JZ와 마찬가지로 "같다/다르다"만 검사하므로 부호 해석에 영향을 받지 않는다. [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md)와 [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)에서 다루는 signed/unsigned 함정은 여기엔 없다.
- **가장 흔하고 치명적인 실수 — 반전 조건을 놓치는 것.** `jne`/`jnz`가 보인다고 소스가 `!=`라고 바로 단정하는 것. 위에서 다뤘듯 `if (a == b) { ... }`가 `jne`로 컴파일되는 경우가 압도적으로 많다. 분기가 "몸통을 건너뛰는" 것인지 "몸통으로 들어가는" 것인지 반드시 흐름을 따라가서 확인해야 한다.
- **JNE와 JNZ를 다른 명령으로 착각하는 것.** [JE/JZ](./rev-0067-je-jz.md)와 마찬가지로 완전히 같은 opcode의 다른 이름일 뿐이다.
- **Jcc가 플래그를 설정한다고 착각하는 것.** `jne` 자체는 어떤 플래그도 바꾸지 않는다.

## 막혔을 때 다음 체크
- 반전인지 아닌지 계속 헷갈리면 → 점프 목표 블록과 fallthrough 블록 각각에 어떤 문자열/함수 호출이 있는지 먼저 본다. "Wrong"/"fail"류 문자열이 있는 쪽이 대개 실패 경로다.
- 디컴파일러의 `if` 조건과 원문이 안 맞는 것 같으면 → 디스어셈블리 뷰로 돌아가 `cmp`/`test`의 실제 오퍼랜드를 재확인한다.
- 루프인지 단순 if인지 헷갈리면 → 점프 목표가 지금 보고 있는 블록보다 **앞쪽(더 낮은 주소)**인지 확인한다 — 앞쪽으로 되돌아가면 루프의 back-edge일 가능성이 높다.
- 그래도 판단이 안 서면 → 브레이크포인트를 걸고 여러 입력값으로 실제 실행 경로를 관찰한다.

## 미니 예제

**예제 1 — 반전된 스킵 패턴 (if (a==b) 의 표준 컴파일 형태)**
```asm
cmp     eax, ebx
jne     skip_body      ; a != b (조건 FALSE) -> 몸통 건너뜀
call    do_something
skip_body:
call    next_line
```
C: `if (a == b) { do_something(); } next_line();`

**예제 2 — 카운트 루프 (DEC + JNZ)**
```asm
mov     ecx, 5
sum_loop:
    add     eax, ecx
    dec     ecx
    jnz     sum_loop    ; ecx != 0 이면 반복
```
C: `for (int i = 5; i > 0; i--) { sum += i; }`

**예제 3 — 바이트 비교 루프 + JNE fail (시리얼 체크 패턴)**
```asm
cmp     byte ptr [rsi], 0x41
jne     fail
cmp     byte ptr [rsi+1], 0x42
jne     fail
; ... 계속 비교 ...
jmp     success
fail:
    call    print_wrong
success:
    call    print_correct
```
C: `if (buf[0] != 'A' || buf[1] != 'B' || ...) { print_wrong(); } else { print_correct(); }`

**예제 4 — TEST + JNZ, 0이 아닌지 검사**
```asm
test    eax, eax
jnz     has_value      ; eax != 0 이면 분기
call    handle_zero
jmp     done
has_value:
call    handle_nonzero
done:
```
C: `if (x != 0) { handle_nonzero(); } else { handle_zero(); }`

## 관련 글
- [JE/JZ](./rev-0067-je-jz.md) — JE와 JZ: ZF가 1일 때 분기 (JNE/JNZ의 정반대 조건)
- [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md) — Signed 비교 분기
- [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md) — Unsigned 비교 분기
- [JMP](./rev-0066-jmp.md) — 무조건 분기
- [CMOVcc](./rev-0075-cmovcc.md) — 분기 없는 조건부 이동
- [SETcc](./rev-0076-setcc.md) — 조건 결과를 0 또는 1로 만들기
- [CALL](./rev-0071-call.md) — 함수 호출, 반환 주소, 인자 추적
- [FLAGS 개요](./rev-0088-flags-overview.md) — EFLAGS/RFLAGS 플래그 레지스터 개요
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교 (예정)
- LOOP 명령어 (예정)

## 출처/검증
- JNE/JNZ 명령어 동작과 opcode 동일성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션 기준 (2026-09-08 검증).
- Jcc 조건 코드 전체 표(ZF/CF/SF/OF/PF 조합): 위와 동일한 Intel SDM 섹션의 조건 코드 정의 표 기준.
- 디컴파일러의 조건 반전/재구성 동작: Hex-Rays 공식 디컴파일러 문서(Decompiler Interactive Operation) 기준 일반 동작 설명.
