---
id: REV-0067
title: "JE와 JZ: ZF가 1일 때 분기"
slug: "rev-0067-je-jz"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - je
  - JE
  - jz
  - JZ
  - je jz
  - jump if equal
  - jump if zero
  - ZF
  - zero flag
  - 제로 플래그
  - 같으면 분기
  - 0이면 분기
  - cmp je
  - test jz
  - Jcc
  - jcc 조건 분기
  - 조건부 점프
  - 조건 분기
  - null 체크 어셈블리
  - 널 포인터 체크
aliases:
  - je란
  - jz란
  - je jz 차이
  - je와 jz 차이
  - je jz 같은거
  - jz가 뭐임
  - 제로플래그가 뭐임
symptom_keywords:
  - je jz 차이를 모르겠음
  - 왜 je와 jz가 둘 다 나오는지 모르겠음
  - cmp 다음에 je가 뭘 하는지 모르겠음
  - test eax eax 다음 jz가 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`JE`와 `JZ`는 **완전히 같은 명령어(같은 opcode)**다. "ZF(Zero Flag)가 1이면 분기하라"는 단 하나의 조건을 두 가지 이름으로 부를 뿐이며, `CMP` 뒤에서는 관례적으로 `JE`("같으면 점프"), 산술 연산 뒤에서는 관례적으로 `JZ`("0이면 점프")라고 부른다.

## 언제 검색해야 하나
- 디스어셈블리에 `je`가 나오는데 무슨 뜻인지 모를 때
- 어떤 곳은 `je`, 어떤 곳은 `jz`라고 나와서 둘이 다른 명령인지 헷갈릴 때 ("je jz 차이")
- `cmp eax, 10` 다음에 `je loc_401050`가 나왔을 때 이게 정확히 무슨 조건에서 점프하는지 알고 싶을 때
- `test eax, eax` 다음에 `jz`가 나왔는데 왜 `test`를 쓰는지, 무슨 값을 검사하는지 모를 때
- IDA 디컴파일 결과의 `if (a == b)`가 실제로 어셈블리에서 어떻게 생겼는지 확인하고 싶을 때

## 핵심 개념

### JE와 JZ는 같은 명령어다
x86/x64에는 **조건부 점프(Jcc, Jump if condition is met)**라는 명령어 계열이 있다. Jcc는 CPU 내부의 **플래그 레지스터(EFLAGS/RFLAGS)**에 저장된 비트들을 읽어서 조건이 참이면 점프하고, 거짓이면 다음 줄로 그냥 넘어간다.

`JE`(Jump if Equal)와 `JZ`(Jump if Zero)는 **opcode가 완전히 동일**하다(단거리 분기 0x74, 장거리 분기 0x0F 84). 어셈블러 입장에서는 두 이름이 그냥 같은 기계어를 만드는 동의어(alias)다. 왜 이름이 두 개일까?

- `CMP a, b` 바로 뒤에서는 "a와 b가 같으면 점프"라는 뜻이 더 자연스러우므로 `JE`라고 쓴다.
- `SUB`, `AND`, `DEC`, `TEST` 같은 산술/논리 연산 바로 뒤에서는 "결과가 0이면 점프"라는 뜻이 더 자연스러우므로 `JZ`라고 쓴다.

**둘 다 테스트하는 조건은 정확히 하나, `ZF = 1`이다.** IDA나 다른 디스어셈블러가 어느 이름을 골라 보여주는지는 순전히 관례/구현 선택의 문제이며, 동작에는 티끌만큼의 차이도 없다.

### 조건 코드(Jcc) 전체 표
이 표는 이후 `JNE`/`JNZ`([JNE/JNZ](./rev-0068-jne-jnz.md)), `JG`/`JL`([JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md)), `JA`/`JB`([JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)) 등 모든 Jcc 글에서 공통으로 참조되는 기준 표다. `Jcc`의 `cc`(condition code) 접미사가 실제로 어떤 플래그 조합을 검사하는지 정리하면 다음과 같다.

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

`JE`/`JZ`는 이 표에서 가장 위, 가장 단순한 줄이다 — 플래그 하나(`ZF`)만 보면 끝난다.

### Intel 문법과 오퍼랜드
```
JE  rel8    ; 짧은 상대 분기 (opcode 0x74), 대상이 현재 위치에서 -128~+127 바이트 이내
JE  rel32   ; 긴 상대 분기 (opcode 0x0F 84), 대상이 더 멀리 있을 때
JZ  rel8    ; JE와 완전히 동일한 opcode
JZ  rel32   ; JE와 완전히 동일한 opcode
```
오퍼랜드는 하나, 점프할 목표 주소를 가리키는 **상대 오프셋**이다. 어셈블리 소스에서는 `je loc_401050`처럼 레이블로 쓰지만, 실제 기계어에는 "현재 명령 다음 주소 기준으로 몇 바이트 이동"이라는 상대값이 인코딩되어 있다. 어셈블러가 rel8로 충분한지 rel32가 필요한지 자동으로 골라준다.

### 플래그: 읽기만 하고 쓰지 않는다
초보자가 가장 헷갈려하는 지점이다. **`Jcc`는 플래그를 "읽기"만 하지, 절대로 "쓰지" 않는다.**

- `JE`/`JZ`가 **읽는** 플래그: `ZF` 하나뿐이다. `CF`, `SF`, `OF`, `PF`, `AF`는 전혀 보지 않는다.
- `JE`/`JZ`가 **바꾸는** 플래그: 없다. 실행 후에도 `ZF`를 포함한 모든 플래그는 실행 전과 똑같이 유지된다.

플래그를 실제로 **쓰는(설정하는)** 명령은 `CMP`, `TEST`, `SUB`, `ADD`, `AND` 같은 산술/논리 명령이다. 즉 `cmp eax, ebx` / `je label` 두 줄에서, `ZF`를 계산해서 저장하는 일은 `cmp`가 다 하고, `je`는 그 결과를 그냥 읽어서 분기 여부만 결정한다. `Jcc`는 "플래그 소비자"이고 `CMP`/산술 명령은 "플래그 생산자"라고 구분해서 기억하면 편하다.

### 스택/RIP 변화
조건이 참(`ZF=1`)이면 `RIP`(다음 실행할 명령 주소)가 목표 레이블 주소로 바뀐다. 조건이 거짓이면 `RIP`는 그냥 다음 명령으로 정상적으로 진행한다. **스택(RSP)에는 아무 영향이 없다** — [CALL](./rev-0071-call.md)과 대조되는 점으로, `CALL`은 반환 주소를 스택에 push하지만 `Jcc`는 그런 흔적을 전혀 남기지 않는다. 그래서 `Jcc`로 이동한 곳에서 "돌아가는" 개념 자체가 없다.

### 컴파일러가 만드는 대표 패턴
**패턴 1 — 직접 대응**: `if (a == b) goto label;` 같은 명시적 goto나 단순 조건이 그대로 대응될 때
```c
if (a == b) {
    handle_equal();
}
```
```asm
cmp     eax, ebx
je      is_equal
jmp     after_if
is_equal:
call    handle_equal
after_if:
```
이 예시처럼 "조건이 참일 때 실행할 코드로 점프"하는 형태로 `je`가 직접 쓰이기도 한다.

**패턴 2 — 반전된 스킵 패턴(매우 흔함)**: 실제 컴파일러 출력에서는 아래처럼 **조건을 뒤집어서 몸통을 건너뛰는** 형태가 훨씬 흔하다.
```c
if (a == b) {
    do_something();
}
next_line();
```
```asm
cmp     eax, ebx
jne     skip_body      ; a != b (조건이 거짓)이면 몸통을 건너뜀
call    do_something    ; 몸통 (조건이 참일 때만 실행됨)
skip_body:
call    next_line
```
여기서는 `je`가 아니라 `jne`가 나온다는 점에 주의하자. "몸통을 실행하지 않고 건너뛰는" 조건(`a != b`)을 검사하는 게 더 효율적인 코드 흐름이기 때문이다. 이 반전 패턴은 [JNE/JNZ](./rev-0068-jne-jnz.md)에서 훨씬 자세히 다룬다 — 지금은 "`je`만 있는 게 아니라 `jne`로도 똑같은 `if (a==b)`가 나올 수 있다"는 것만 기억해두자.

**패턴 3 — NULL/0 체크 관용구**: `TEST reg, reg` 다음의 `JZ`는 "포인터가 NULL인가?" 또는 "반환값이 0인가?"를 검사하는 매우 흔한 관용구다.
```c
void *p = malloc(size);
if (p == NULL) {
    goto fail;
}
```
```asm
call    malloc
test    rax, rax     ; rax AND rax -> 결과가 0이면 ZF=1 (부호 검사가 아니라 순수 0 검사)
jz      fail          ; rax == 0 (malloc 실패)이면 fail로 분기
```
`TEST reg, reg`는 `reg`를 자기 자신과 `AND` 연산해서(값 자체는 바꾸지 않고) 결과의 플래그만 세팅한다. 결과가 0이면(즉 `reg`가 원래 0이었으면) `ZF=1`이 되므로, `test rax, rax` + `jz`는 "rax가 0인지" 검사하는 가장 흔한 x86 관용구다.

### IDA/Ghidra 디컴파일 화면에서 보이는 형태
IDA(F5)나 Ghidra 디컴파일러는 `cmp`+`je`/`jz` 쌍을 보면 대부분 자연스럽게 `if (a == b)` 또는 `if (v1 == 0)` 형태로 재구성해서 보여준다. 대부분은 정확하지만, 최적화가 심하거나 구조체 필드 타입 추론이 틀린 경우 디컴파일러가 보여주는 변수 이름/조건이 실제와 미묘하게 다를 수 있다.

디컴파일 결과의 `if` 조건이 이상하게 느껴진다면:
1. 해당 줄에서 **디스어셈블리 뷰**로 전환한다(IDA는 그래프뷰/텍스트뷰 전환 단축키 Space, 또는 하단 상태바의 디스어셈블리 창을 직접 확인).
2. `je`/`jz` 바로 위에 있는 `cmp` 또는 `test` 명령을 찾는다.
3. 그 명령의 두 오퍼랜드가 정확히 무엇인지 확인한다(레지스터? 상수? 메모리 오프셋?).
4. "`ZF=1`이면 두 오퍼랜드가 같다(또는 결과가 0이다)"는 원칙을 그대로 적용해서, 디컴파일러의 변수 이름을 신뢰하지 말고 실제 비교 대상을 직접 재해석한다.

이 과정은 디컴파일러가 구조체 필드나 타입을 잘못 추측해서 `if` 조건이 실제 의미와 어긋나 보일 때 특히 중요하다.

### 리버싱에서의 의미
문자열 비교/`memcmp` 스타일 루프가 끝난 직후에 나오는 `je`/`jz`는 크랙미(crackme)에서 전형적인 **"시리얼 번호 검사 통과 지점"**이다. 이런 지점은:
- 디버거로 `je`/`jz` 주소에 브레이크포인트를 걸고 그 시점의 플래그(`ZF`) 값을 확인하는 지점,
- 또는 (교육/CTF 목적의) 패치 대상으로 자주 지목되는 지점이다.

## 가장 먼저 할 것
디스어셈블리에서 `je`/`jz`를 만나면 다른 무엇보다 먼저 **바로 위 줄**부터 본다.
1. `je`/`jz` 바로 위에 있는 명령이 `cmp`인지 `test`/산술 명령(`sub`, `and`, `dec` 등)인지 확인한다 — 이게 "무엇을 0/같음으로 판단했는지"의 근거다.
2. 그 명령의 두 오퍼랜드(레지스터, 상수, 메모리)를 정확히 읽는다. `cmp eax, 10`이라면 "eax와 10", `test rax, rax`라면 "rax가 0인지"다.
3. `je`/`jz`가 점프하는 목표 주소와, 점프하지 않았을 때(fallthrough) 이어지는 코드를 둘 다 확인해서 어느 쪽이 "조건 성립 시 실행되는 코드"인지 파악한다.
4. 이 근처에 `jne`/`jnz`도 섞여 있는지 살펴본다 — 반전된 형태로 같은 비교가 다시 쓰이는 경우가 많다(예제 3 참고).

## 단계별 절차
IDA를 기준으로 실제로 손을 움직이는 순서:
1. **그래프뷰에서 `je`/`jz` 노드를 찾는다.** 화살표가 두 갈래로 갈라지는 지점(조건 분기 블록)이므로 눈에 잘 띈다.
2. **바로 위 블록의 마지막 명령**(대개 `cmp` 또는 `test`)에 커서를 놓고, 오퍼랜드에 쓰인 변수/레지스터 이름을 확인한다. 이름이 `var_10`처럼 스택 변수라면, 그 위에서 `var_10`에 마지막으로 쓰인 값을 거슬러 올라가 본다.
3. **F5로 디컴파일**해서 같은 지점의 `if` 문을 확인하고, 어셈블리에서 읽은 조건과 일치하는지 대조한다(디컴파일러가 조건을 반전/재구성했을 수 있으므로 대조가 중요하다).
4. 정적으로 값이 애매하면(런타임에 계산되는 값), `je`/`jz` 주소에 브레이크포인트를 걸고(`F2`) `F9`로 실행한 뒤, 레지스터 창에서 `ZF` 비트와 실제 비교 대상 레지스터 값을 직접 확인한다.
5. 두 갈래(점프 경로 / fallthrough 경로) 각각을 따라가서 그 안에서 무슨 문자열을 출력하거나 무슨 함수를 부르는지 보면("Correct!" vs "Wrong!" 등) 어느 쪽이 "성공 경로"인지 바로 판단할 수 있다.

## 명령어/단축키
- IDA: `Space`(그래프뷰/텍스트뷰 전환), `F5`(디컴파일), `F2`(브레이크포인트 설정/해제), `F9`(실행/계속), 분기 화살표를 클릭하면 해당 목표 블록으로 바로 이동
- x64dbg: 조건 분기 라인에서 `F2`(브레이크포인트), `F9`(실행), 우측 플래그 패널에서 `ZF` 값 실시간 확인, 분기 직전 `F7`(Step Into)로 한 줄씩 진행하며 `ZF`가 바뀌는 순간을 관찰
- GDB/Pwndbg: `break *0x<je주소>`, `info registers eflags`(플래그 전체 확인), `p/x $eflags`, Pwndbg는 `context` 명령으로 플래그 변화를 색으로 강조해서 보여줌

## 흔한 실수
- **JE/JZ를 signed/unsigned 비교(JG/JA 등)와 섞어서 생각하는 것.** JE/JZ는 오직 "같다/0이다"만 검사하며, 이 판단에는 부호(signed/unsigned) 해석이 전혀 개입하지 않는다 — 두 비트 패턴이 같은지 다른지는 부호를 어떻게 해석하든 결과가 항상 같기 때문이다. [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md)와 [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md)에서 다루는 signed/unsigned 함정이 JE/JZ에는 존재하지 않는다는 점에서 오히려 안심해도 좋다.
- **JE와 JZ가 다른 명령이라고 착각하는 것.** 같은 코드에서 어떤 곳은 `je`, 어떤 곳은 `jz`로 표시되는 걸 보고 "다른 종류의 비교인가?"라고 의심하는 초보자가 많다. 답은 "전혀 차이 없음" — 어셈블러/디스어셈블러가 직전 명령의 종류(비교냐 산술이냐)를 보고 관례적으로 이름을 고른 것뿐이다.
- **`Jcc`가 플래그를 설정한다고 착각하는 것.** `je` 자체는 플래그를 절대 바꾸지 않는다. 플래그는 그 앞의 `cmp`/`test`/산술 명령이 이미 설정해 둔 것을 `je`가 읽기만 한다.
- **`je`만 찾고 `jne`로 반전된 같은 조건을 놓치는 것.** `if (a == b)`가 소스에 있어도 실제 어셈블리에는 `jne`가 나올 수 있다(위 패턴 2). `je`가 안 보인다고 "이 코드에는 등호 비교가 없다"고 단정하지 말 것 — [JNE/JNZ](./rev-0068-jne-jnz.md) 참고.

## 막혔을 때 다음 체크
- `je`/`jz`가 뭘 검사하는지 모르겠다면 → 바로 위 명령이 `cmp`인지 `test`인지부터 다시 확인한다. 더 위로 거슬러 올라가야 할 수도 있다(컴파일러가 비교와 분기 사이에 다른 명령을 끼워 넣는 경우는 드물지만, 여러 조건이 `and`/`or`로 합쳐진 복합 `if`라면 `cmp`/`jcc` 쌍이 연달아 여러 번 나올 수 있다).
- 디컴파일러의 `if` 조건과 어셈블리가 다르게 느껴진다면 → 디스어셈블리 뷰(Space)로 돌아가 원문을 직접 재해석한다. 타입 추론이 틀려서 변수 이름이 오해를 유발하는 경우가 있다.
- 점프 목표/fallthrough 중 어느 쪽이 "성공"인지 헷갈리면 → 두 경로를 각각 끝까지 따라가서 어느 쪽이 성공 메시지 출력이나 정상 반환으로 이어지는지 실행해서 확인한다.
- 그래도 안 풀리면 → 이 지점에 브레이크포인트를 걸고 여러 다른 입력값으로 실행해보며 `ZF`와 분기 결과가 어떻게 달라지는지 직접 관찰한다.

## 미니 예제

**예제 1 — CMP + JE, 숫자 비교**
```asm
cmp     eax, 100
je      loc_401020    ; eax == 100 이면 분기
```
C: `if (eax == 100) goto loc_401020;`

**예제 2 — TEST + JZ, NULL 포인터 체크**
```asm
call    malloc
test    rax, rax
jz      alloc_failed   ; rax == 0 이면 (malloc 실패) 분기
```
C: `if (p == NULL) goto alloc_failed;`

**예제 3 — 문자열 비교 루프 끝의 JZ (시리얼 체크 패턴)**
```asm
loop_start:
    mov     al, [rsi]
    cmp     al, [rdi]
    jne     mismatch      ; 한 글자라도 다르면 실패로 분기
    inc     rsi
    inc     rdi
    test    al, al
    jnz     loop_start    ; 널 종료 문자가 아니면 계속 반복
    ; 여기까지 왔다는 것은 두 문자열이 끝까지 같았다는 뜻
    jmp     match_ok
mismatch:
    ; "Wrong password" 출력 등
match_ok:
    ; "Correct!" 출력 등
```
(이 예제에는 `jne`, `jnz`도 함께 등장한다 — 자세한 반전 조건 해석은 [JNE/JNZ](./rev-0068-jne-jnz.md) 참고.)

**예제 4 — 반전된 스킵 패턴 (JE 대신 JNE로 컴파일된 `if (a==b)`)**
```asm
cmp     dword ptr [rbp-4], 0
jne     skip_message   ; 조건(값==0)이 거짓이면 메시지 출력을 건너뜀
lea     rcx, [format_string]
call    printf
skip_message:
```
C: `if (counter == 0) { printf(...); }` — `je`가 아니라 `jne`가 나왔지만 여전히 같은 등호 비교임을 기억하자.

## 관련 글
- [JNE/JNZ](./rev-0068-jne-jnz.md) — JNE와 JNZ: ZF가 0일 때 분기 (JE/JZ의 정반대 조건)
- [JG/JGE/JL/JLE](./rev-0069-jg-jge-jl-jle.md) — JG JGE JL JLE: Signed 비교 분기
- [JA/JAE/JB/JBE](./rev-0070-ja-jae-jb-jbe.md) — JA JAE JB JBE: Unsigned 비교 분기
- [JMP](./rev-0066-jmp.md) — JMP: 무조건 분기
- [CMOVcc](./rev-0075-cmovcc.md) — CMOVcc: 분기 없는 조건부 이동
- [SETcc](./rev-0076-setcc.md) — SETcc: 조건 결과를 0 또는 1로 만들기
- [CALL](./rev-0071-call.md) — CALL: 함수 호출, 반환 주소, 인자 추적
- [FLAGS 개요](./rev-0088-flags-overview.md) — EFLAGS/RFLAGS 플래그 레지스터 개요
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- TEST 명령어 (예정)

## 출처/검증
- JE/JZ 명령어 동작과 opcode 동일성: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "Jcc—Jump if Condition Is Met" 섹션 기준 (2026-09-08 검증).
- Jcc 조건 코드 전체 표(ZF/CF/SF/OF/PF 조합): 위와 동일한 Intel SDM 섹션의 조건 코드 정의 표 기준.
- IDA 디컴파일러의 cmp/test → if 변환 동작: Hex-Rays 공식 디컴파일러 문서(Decompiler Interactive Operation) 기준 일반 동작 설명.
