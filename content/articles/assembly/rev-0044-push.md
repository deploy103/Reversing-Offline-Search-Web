---
id: REV-0044
title: "PUSH: 스택에 값 넣기"
slug: "rev-0044-push"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - push
  - PUSH
  - Push
  - push instruction
  - push 명령어
  - "push rbp"
  - "push rax"
  - "push eax"
  - "push 0"
  - "push offset"
  - "push qword ptr"
  - stack push
  - 스택 푸시
  - 스택에 넣기
  - 스택에 값 넣기
  - RSP 감소
  - ESP 감소
  - 스택 포인터
  - stack pointer
aliases:
  - push 뭐임
  - push가 뭐죠
  - push 명령
  - PUSH 명령어
  - 스택 넣기
  - 스택 쌓기
  - 스택에 저장
symptom_keywords:
  - 스택이 왜 아래로 자라는지 모르겠음
  - rsp가 왜 줄어드는지 모르겠음
  - push pop 짝이 안맞음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`PUSH src`는 스택 포인터(`RSP`/`ESP`)를 먼저 감소시킨 뒤, 그 새 위치에 `src` 값을 저장하는 명령어다. x64에서는 항상 8바이트 단위로 스택이 줄어든다. **스택은 낮은 주소 방향으로 자란다**는 것이 이 명령어를 이해하는 핵심이다.

## 언제 검색해야 하나
- `push rbp` 같은 코드가 함수 시작마다 반복돼서 왜 있는지 궁금할 때
- PUSH 이후 RSP 값이 어떻게 바뀌는지, 정확히 몇 바이트가 줄어드는지 헷갈릴 때
- 스택이 왜 "아래로(낮은 주소로) 자란다"고 하는지 이해가 안 될 때
- 함수 인자를 스택으로 넘기는 코드(`push` 여러 개 후 `call`)를 분석해야 할 때
- IDA가 "positive sp value has been detected" 경고를 냈는데 PUSH/POP 짝이 안 맞는 게 원인인지 확인하고 싶을 때

## 핵심 개념

### 스택은 왜 "아래로" 자라는가
스택 메모리 영역은 보통 **높은 주소에서 시작해서 낮은 주소 방향으로 채워진다.** 예를 들어 스레드 스택이 `0x7ffee1000000`에서 시작한다면, 값을 스택에 넣을수록(PUSH할수록) 사용 중인 메모리 영역은 `0x7ffee0fffff8`, `0x7ffee0fffff0`처럼 **더 작은 주소** 쪽으로 확장된다. 그래서 "스택에 넣는다(PUSH)"는 것은 곧 **RSP(스택 포인터)를 감소시키는 것**과 같은 뜻이다.

### PUSH의 정확한 동작 순서 (중요)
```
PUSH src:
  1. RSP = RSP - (오퍼랜드 크기)   ; 먼저 스택 포인터를 줄인다
  2. [RSP] = src                    ; 그 다음 그 새 주소에 값을 쓴다
```
x64에서 `PUSH r64`/`PUSH imm32`/`PUSH m64`는 항상 **8바이트** 단위로 동작한다(32비트 레지스터를 직접 PUSH하는 것은 x64에서 지원하지 않는다 — 즉 `push eax`는 x64에서 불가능하고, `push rax`만 가능하다). x86(32비트 모드)에서는 4바이트 단위다.

```asm
; 실행 전: RSP = 0x7ffee000
push rax
; 실행 후: RSP = 0x7ffedff8 (8만큼 감소), [0x7ffedff8] = RAX 값
```

**순서가 "감소 먼저, 쓰기 나중"이라는 걸 정확히 기억해야 한다** — 그래야 PUSH 직후 `[RSP]`가 정확히 방금 넣은 값을 가리킨다는 걸 이해할 수 있다.

### 오퍼랜드
- 레지스터: `push rax`, `push rbp`
- 메모리: `push qword ptr [rbx]`
- 즉시값: `push 0`, `push 10h` (x64에서는 부호 확장되어 8바이트로 스택에 저장됨)
- 세그먼트 레지스터(x86 레거시, x64에서는 CS/DS/ES/SS 일부 제한): 이 사전에서는 다루지 않음

### 플래그
`PUSH`는 **플래그를 전혀 바꾸지 않는다.** 값을 스택에 옮기는 것뿐, 산술 연산이 아니다. (예외: `PUSHF`는 플래그 레지스터 "자체"를 스택에 넣는 별개의 명령어이며, [PUSHF/POPF](./rev-0046-pushf-popf.md)에서 다룬다.)

### 스택은 그냥 "메모리"다 — 특별한 자료구조가 아니다
초보자가 자주 오해하는 부분: 스택은 마법 같은 별도의 저장 공간이 아니라, **RSP라는 레지스터가 가리키는 평범한 메모리 영역**일 뿐이다. PUSH/POP은 그 메모리에 정해진 규칙(RSP 증감 + 읽기/쓰기)으로 접근하는 명령어일 뿐이며, `[rsp]`, `[rsp+8]` 등으로 직접 메모리 접근하듯 읽는 것도 얼마든지 가능하다.

### 함수 프롤로그에서의 PUSH — 레지스터 백업
함수가 시작할 때 흔히 보이는 패턴:
```asm
push rbp          ; 이전 함수의 RBP 값을 스택에 백업
mov  rbp, rsp      ; 새 스택 프레임 기준점 설정
push rbx           ; 이 함수 안에서 RBX를 쓸 거라서 원래 값을 보존(콜리 세이브 레지스터)
push r12
```
Windows x64와 SysV x64 둘 다 RBX, RBP, RSP, R12~R15는 **콜리-세이브(callee-saved) 레지스터**로 규정한다 — 함수가 이 레지스터들을 쓰고 싶으면, 시작할 때 PUSH로 백업해두고 끝날 때 [POP](./rev-0045-pop.md)으로 복원해서, 호출자 입장에서는 이 레지스터 값이 함수 호출 전후로 변하지 않은 것처럼 보이게 해야 한다.

### 함수 인자를 스택으로 넘기는 패턴 (레거시 x86, cdecl/stdcall)
x64에서는 처음 몇 개 인자를 레지스터로 넘기지만([CALL](./rev-0071-call.md) 문서 참고), **32비트(x86) 코드**나 **레지스터를 초과하는 인자**의 경우 스택을 통해 넘긴다:
```asm
push 3        ; 3번째 인자 (오른쪽에서 왼쪽 순서로 push)
push 2        ; 2번째 인자
push 1        ; 1번째 인자
call some_func ; some_func(1, 2, 3)
```
인자를 오른쪽부터 왼쪽 순서로 PUSH하는 이유는, 스택에 쌓이고 나면 **1번째 인자가 가장 나중에 push되어 스택 최상단(가장 낮은 주소)에 위치**해야 함수 내부에서 `[rsp+4]`, `[rsp+8]`처럼 일정한 오프셋으로 순서대로 접근할 수 있기 때문이다.

## 화면/코드에서 보이는 징후
- `push rbp` — 함수 프롤로그, 이전 프레임 포인터 백업(가장 흔한 PUSH)
- `push rbx`, `push r12`~`r15` — 콜리-세이브 레지스터 백업
- `push 0`, `push 1` — 상수를 스택 인자로 전달(레거시 x86 호출 규약)
- `push qword ptr [rbp-0x10]` — 메모리 값을 스택에 직접 push
- `push rax` 뒤에 바로 `pop rcx` — 사실상 `mov rcx, rax`와 같은 효과지만 다른 목적(예: 코드 크기, 난독화)으로 쓰이기도 함

## 가장 먼저 할 것
1. 오퍼랜드 크기를 확인한다(x64에서는 사실상 항상 8바이트).
2. PUSH 실행 전 RSP 값을 기준으로, 실행 후 RSP가 정확히 8만큼 줄었는지 확인한다.
3. 이 PUSH가 레지스터 백업(프롤로그)인지, 인자 전달인지, 다른 목적(스택에 임시로 값 대피)인지 문맥으로 판단한다.

## 단계별 절차
**1) 프롤로그의 PUSH 인식**
```asm
sub_401000:
    push rbp          ; RSP -= 8, [RSP] = 이전 RBP
    mov  rbp, rsp       ; 새 프레임 기준점
```
→ 함수가 시작됐다는 신호. IDA는 이 지점을 "함수 시작"으로 자동 인식하는 데 이 패턴을 참고한다.

**2) RSP 변화 직접 추적**
```
실행 전: RSP = 0x7ffee050
push rax   -> RSP = 0x7ffee048
push rbx   -> RSP = 0x7ffee040
push rcx   -> RSP = 0x7ffee038
```
→ PUSH 3번이면 RSP는 정확히 24(=8×3) 감소해야 한다. 나중에 POP 3번으로 정확히 되돌아와야 균형이 맞는다.

**3) 스택 인자 전달 패턴 인식 (레거시 x86)**
```asm
push offset szFormat   ; 마지막 인자부터
push edx                 ; 그 다음 인자
push eax                 ; 첫 번째 인자
call _printf
add  esp, 0Ch             ; 호출 후 호출자가 직접 스택 정리(cdecl)
```
→ `add esp, 0Ch`(12 = 4바이트×3개)가 뒤따르면 cdecl 규약, 호출자가 인자 3개만큼 스택을 되돌리는 것.

## 명령어/단축키
- IDA: 스택 뷰(View → Open subviews → Stack view)에서 PUSH/POP에 따른 스택 프레임 변화를 시각적으로 확인, `F5`로 디컴파일하면 지역변수/인자로 정리되어 보임
- x64dbg: 하단 스택 창에서 RSP가 가리키는 위치와 그 아래 값들을 실시간으로 확인, PUSH 실행마다 스택 창이 한 줄씩 위로 갱신됨
- GDB/Pwndbg: `x/8gx $rsp`로 스택 최상단 8개 8바이트 값 확인, `stepi`로 한 줄씩 실행하며 `info registers rsp` 비교, pwndbg는 `stack` 커맨드로 스택을 보기 좋게 자동 표시

## 출력 해석
- PUSH 실행 후 스택 창/덤프에서 RSP가 가리키는 새 위치에 방금 넣은 값이 정확히 보이면 정상.
- RSP 값이 8의 배수가 아닌 이상한 값으로 바뀌었다면 스택이 깨진 것(오버플로우, 잘못된 오퍼랜드 크기 등)을 의심해야 한다.
- IDA에서 "positive sp value has been detected"(양수 SP 경고)가 뜨면, 코드 어딘가에서 PUSH보다 POP이 더 많이 실행되어(또는 그 반대) 스택 균형이 깨졌다는 뜻 — 함수 내 모든 PUSH/POP과 `call`(CALL도 내부적으로 push와 동일)을 세어봐야 한다.

## 흔한 실수
- **PUSH가 값을 쓴 다음 RSP를 줄인다고 순서를 반대로 착각**하는 것 — 실제로는 "RSP 먼저 감소, 그 다음 쓰기" 순서다.
- **x64에서 `push eax`(32비트 레지스터)가 된다고 착각**하는 것 — x64는 GPR PUSH를 8바이트(64비트) 단위로만 지원한다. 32비트 값을 push하려면 먼저 64비트 레지스터에 담아야 한다.
- **스택이 위로 자란다고(주소가 커지는 방향으로) 착각**하는 것 — 실제로는 아래로(주소가 작아지는 방향으로) 자란다. 이 방향을 반대로 알면 스택 프레임 그림 전체가 뒤집혀서 이해된다.
- **PUSH 개수와 POP 개수가 짝이 안 맞아도 괜찮다고 생각**하는 것 — 함수 안에서 PUSH/POP(및 CALL/RET)은 반드시 균형이 맞아야 정상적으로 함수가 반환된다. 안 맞으면 RET이 엉뚱한 주소로 튀는 심각한 버그(또는 의도적 스택 조작 트릭)가 된다.
- PUSH가 플래그를 바꾼다고 착각하는 것 — 바꾸지 않는다.

## 막혔을 때 다음 체크
- RSP 변화량이 예상과 다르면 → 오퍼랜드 크기가 정말 8바이트인지, 혹은 이 PUSH가 x86(32비트) 코드라서 4바이트인지 아키텍처를 재확인한다.
- 함수 전체에서 PUSH/POP 균형이 안 맞아 보이면 → CALL(내부적으로 반환 주소를 PUSH함)과 RET(POP)도 균형 계산에 포함시켰는지 확인한다.
- 스택 프레임 전체 구조가 헷갈리면 → [LEAVE](./rev-0073-leave.md)와 [RET](./rev-0072-ret.md) 문서에서 함수 에필로그 전체 흐름을 함께 확인한다.

## 미니 예제

**예제 1 — 함수 프롤로그의 레지스터 백업**
```c
void func(void) {
    // rbx, r12를 함수 내부에서 쓸 예정
    ...
}
```
```asm
func:
    push rbp        ; RSP -= 8
    mov  rbp, rsp
    push rbx         ; RSP -= 8  (콜리-세이브 백업)
    push r12          ; RSP -= 8  (콜리-세이브 백업)
```

**예제 2 — 지역 변수 값을 임시로 스택에 대피**
```asm
mov  eax, [rbp-0x4]
push rax              ; eax 값을 스택에 임시 저장
call some_func         ; some_func 내부에서 rax를 자유롭게 써도 됨
pop  rax               ; 스택에서 원래 값 복원
```

**예제 3 — 레거시 x86 cdecl 인자 전달**
```c
printf("%d + %d = %d", a, b, a+b);
```
```asm
mov  eax, [ebp-4]
add  eax, [ebp-8]
push eax                ; 4번째 인자 (a+b) - 오른쪽부터
push dword ptr [ebp-8]  ; 3번째 인자 (b)
push dword ptr [ebp-4]  ; 2번째 인자 (a)
push offset szFormat    ; 1번째 인자 (포맷 문자열)
call _printf
add  esp, 10h             ; 호출자가 스택 정리 (4개 * 4바이트)
```

## 관련 글
- [POP: 스택에서 값 꺼내기](./rev-0045-pop.md)
- [PUSHF와 POPF: 플래그 저장과 복원](./rev-0046-pushf-popf.md)
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [RET: 함수 반환과 스택 변화](./rev-0072-ret.md)
- [LEAVE: 함수 에필로그와 스택 프레임](./rev-0073-leave.md)

## 출처/검증
- PUSH 명령어 동작(RSP 감소 순서, x64에서 8바이트 고정): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "PUSH—Push Word, Doubleword, or Quadword Onto the Stack" 섹션 기준 (2026-09-08 검증).
- 콜리-세이브 레지스터(RBX, RBP, R12-R15) 규정: Microsoft Learn "x64 calling convention" 및 System V AMD64 ABI 공식 스펙 기준.
