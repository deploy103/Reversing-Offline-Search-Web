---
id: REV-0072
title: "RET: 함수 반환과 스택 변화"
slug: "rev-0072-ret"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - ret
  - RET
  - Ret
  - retn
  - RETN
  - retf
  - RETF
  - ret instruction
  - ret 명령어
  - "ret 0Ch"
  - "ret 4"
  - return address
  - 반환 주소
  - 리턴 주소
  - 함수 반환
  - 함수 리턴
  - stack cleanup
  - 스택 정리
  - stdcall ret
  - cdecl ret
aliases:
  - ret 뭐임
  - ret이 뭐죠
  - ret 명령
  - RET 명령어
  - 함수 끝나면
  - 함수 종료 명령어
  - 반환 명령어
symptom_keywords:
  - ret 다음에 왜 이상한 주소로 가는지 모르겠음
  - 스택 오버플로우로 ret 주소가 바뀜
  - ret 뒤에 숫자가 왜 있는지 모르겠음
  - 함수가 끝나면 어디로 돌아가는지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`RET`은 스택 맨 위에서 반환 주소를 [POP](./rev-0045-pop.md)해서 `RIP`(다음 실행할 명령의 주소)에 넣고, 그 주소로 실행을 이어가는 명령어다. [CALL](./rev-0071-call.md)이 스택에 PUSH한 반환 주소를 그대로 되찾아가는, CALL의 정확한 짝이다.

## 언제 검색해야 하나
- 함수 끝에서 `ret`만 덩그러니 있는데 어디로 돌아가는지 궁금할 때
- `ret 0Ch`, `ret 8`처럼 `ret` 뒤에 숫자가 붙는 이유를 알고 싶을 때
- 스택 버퍼 오버플로우로 반환 주소가 덮어써져서 `ret` 이후 프로그램이 엉뚱한 곳으로 튀는 취약점(Return Address Overwrite)을 분석할 때
- 함수 프롤로그의 PUSH 개수와 에필로그의 POP 개수, 그리고 RET까지 스택이 정확히 맞는지 검증하고 싶을 때
- ROP(Return-Oriented Programming) gadget을 찾을 때 — 각 가젯은 결국 RET으로 끝난다

## 핵심 개념

### RET의 정확한 동작
```
RET:
  1. RIP = [RSP]        ; 스택 최상단 값(반환 주소)을 읽어서 RIP에 로드
  2. RSP = RSP + 8        ; (x64 기준) 스택 포인터를 8만큼 증가
```
이건 정확히 `pop 임시값; jmp 임시값`과 같은 동작이다 — 다만 CPU가 이 두 단계를 하나의 명령어로 원자적으로 수행한다. [POP](./rev-0045-pop.md)과 완전히 같은 스택 규칙(먼저 읽고, 그 다음 RSP 증가)을 따르되, 목적지가 항상 RIP로 고정되어 있다는 점이 다르다.

### CALL과의 완벽한 대칭
```
CALL target:
  1. [RSP-8] = RIP (다음 명령 주소)   ; 반환 주소를 스택에 push
  2. RSP -= 8
  3. RIP = target

RET:
  1. RIP = [RSP]                        ; 반환 주소를 스택에서 pop
  2. RSP += 8
```
CALL이 "push 반환주소 + jmp target"이라면, RET은 정확히 "pop 반환주소 + jmp 반환주소"다. 이 대칭성 덕분에 함수는 자신을 호출한 위치로 정확히 돌아올 수 있다. **CALL이 스택에 쌓은 값을 RET이 그대로 꺼내 쓴다는 전제가 깨지면(스택이 중간에 변조되면) RET은 엉뚱한 주소로 튄다** — 이게 스택 버퍼 오버플로우 공격의 핵심 원리다.

### RET 이후 RSP는 CALL 실행 직전 값으로 정확히 돌아와야 한다
```
호출자 코드:
  ...                      ; RSP = 0x7ffee000
  call sub_401000          ; RSP -= 8 -> 0x7ffedff8 (반환주소 push)
  ...                      ; call 이후, 이 지점에서 RSP는 다시 0x7ffee000이어야 정상
```
함수 내부에서 PUSH/POP, `sub rsp, N`/`add rsp, N`이 아무리 복잡하게 얽혀도, **RET이 실행되는 순간 RSP는 CALL이 반환주소를 push하기 직전 값과 정확히 같아야 한다.** 이 균형이 깨지면(스택 언밸런스) 함수가 반환되는 순간 반환 주소가 아닌 엉뚱한 스택 데이터를 RIP로 읽어서 프로그램이 크래시하거나 예측 불가능한 곳으로 실행이 튄다. IDA는 이런 코드를 만나면 "positive sp value has been detected" 같은 경고를 낸다.

### `RET n` — 스택 정리까지 함께 수행 (RETN, imm16 오퍼랜드)
`ret` 뒤에 숫자가 붙은 형태(`ret 0Ch`, `ret 8`)는 반환 주소를 pop한 **직후 스택 포인터를 추가로 n바이트만큼 더 증가**시킨다.
```
RET n:
  1. RIP = [RSP]
  2. RSP += 8   (반환 주소 pop)
  3. RSP += n    (추가로 n바이트 스택 정리)
```
이건 **stdcall이나 Windows API처럼 "호출받은 함수(callee) 자신이 인자로 쓰인 스택 공간을 정리하는" 호출 규약**에서 나타난다. 반대로 cdecl(예: `printf`)처럼 "호출한 쪽(caller)이 스택을 정리하는" 규약에서는 함수 내부에 그냥 `ret`(오퍼랜드 없음)만 있고, 호출부에서 `call` 직후 `add esp, N`으로 정리한다. **`ret n`이 보이면 그 함수는 stdcall류(callee-cleanup) 규약으로 컴파일됐다는 강한 힌트**다. x64에서는 인자를 대부분 레지스터로 넘기기 때문에 `ret n` 형태 자체가 32비트(x86) 코드에서 훨씬 흔하다.
```asm
; stdcall 예시 (x86, 인자 2개 = 8바이트)
push  arg2
push  arg1
call  MessageBoxA_like_func
; 호출자는 스택 정리를 안 함 - 함수 내부의 ret 8이 대신 처리
...
MessageBoxA_like_func:
    push ebp
    mov  ebp, esp
    ...
    pop  ebp
    ret  8              ; 반환 주소 pop + 추가로 8바이트(인자 2개분) 스택 정리
```

### 플래그
`RET`은 **플래그를 전혀 바꾸지 않는다.**

### RET과 ROP(Return-Oriented Programming)
스택 버퍼 오버플로우로 반환 주소를 직접 제어할 수 있게 되면, 공격자는 그 자리에 임의 코드 대신 **이미 프로그램/라이브러리 안에 존재하는 짧은 명령어 조각(가젯, gadget)의 주소**를 넣는다. 각 가젯은 몇 개의 명령어 뒤에 `ret`으로 끝나는데, RET이 스택에서 "다음 반환 주소"를 또 pop해서 그 다음 가젯으로 점프하게 만든다 — 이런 식으로 가젯들을 스택에 체인으로 쌓아 임의의 로직을 실행하는 기법이 ROP다. DEP/NX(코드 실행 방지) 보호를 우회하는 대표적인 익스플로잇 기법이며, 이 사전의 다른 항목(스택 버퍼 오버플로우, ROP 체인 관련 글)에서 더 자세히 다룬다.

## 화면/코드에서 보이는 징후
- `ret` — 오퍼랜드 없음, 반환 주소만 pop해서 복귀 (cdecl/대부분의 x64 규약)
- `ret 8`, `ret 0Ch`, `ret 10h` — 반환과 동시에 스택 추가 정리 (stdcall류, x86에서 흔함)
- `retn` — 일부 디스어셈블러(IDA 등)에서 near return을 명시적으로 이렇게 표시하기도 함(far return인 `retf`와 구분)
- 함수 마지막 줄이 `pop rbp` 또는 [`leave`](./rev-0073-leave.md) 다음에 곧바로 `ret`
- 취약점 분석 중 `ret`이 스택 최상단의 조작된 값(비정상적으로 큰 주소, 셸코드 위치를 가리키는 주소 등)을 그대로 RIP에 로드하는 상황

## 가장 먼저 할 것
1. `ret`에 오퍼랜드가 있는지(`ret n`) 확인한다 — 있으면 stdcall류 규약을 의심한다.
2. RET 실행 직전 RSP가 가리키는 값이 정말 유효한 코드 주소(반환 주소)인지 확인한다.
3. 이 함수의 프롤로그(PUSH 횟수)와 에필로그(POP 횟수)를 세어서 RET 시점에 스택이 균형 잡혀 있는지 검증한다.

## 단계별 절차
**1) 기본 반환 추적**
```asm
sub_401000:
    push rbp
    mov  rbp, rsp
    ...
    pop  rbp
    ret                 ; [RSP]의 반환 주소로 복귀, RSP += 8
```
→ 함수 호출 시 CALL이 push한 주소로 정확히 돌아간다.

**2) `ret n` 형태 해석**
```asm
sub_401500:
    push ebp
    mov  ebp, esp
    ...
    pop  ebp
    ret  8               ; 반환 + 추가로 8바이트(인자 2개) 정리
```
→ 이 함수는 인자 2개(각 4바이트, x86 기준)를 스택으로 받았고, 함수 스스로 그 공간을 정리하는 stdcall류 규약이다.

**3) 스택 균형 검증**
```
CALL 실행 직전 RSP = X
함수 내부 PUSH 3번, POP 3번 (프롤로그/에필로그 균형)
RET 실행 -> RSP는 X로 정확히 복귀해야 정상
```
IDA 스택 뷰나 디버거에서 RET 실행 직후 RSP 값을 CALL 실행 직전 값과 비교해서 검증한다.

**4) 반환 주소 변조 여부 확인 (취약점 분석)**
```asm
lea rdi, [rbp-0x40]  ; 버퍼 주소
call gets              ; 크기 제한 없이 입력 -> 버퍼 오버플로우 가능
...
ret                     ; 만약 버퍼가 넘쳐서 반환 주소까지 덮어썼다면, 이 ret은 공격자가 넣은 주소로 실행을 넘긴다
```
→ `gets`, `strcpy` 등 크기 제한 없는 함수 다음에 `ret`이 있다면, 그 사이의 버퍼와 반환 주소 사이 거리(오프셋)를 계산하는 것이 스택 버퍼 오버플로우 분석의 핵심이다.

## 명령어/단축키
- IDA: 함수 끝의 `ret`에서 `Ctrl+F5`나 스택 뷰로 RSP 균형 확인, "positive sp value has been detected" 경고가 뜨면 함수 내 PUSH/POP/CALL 개수를 다시 센다
- x64dbg: `ret` 명령에 브레이크포인트를 걸고 `F9`로 실행 후 스택 창에서 `[RSP]` 값(반환될 주소)을 먼저 확인, `F7`(step into)로 실제로 그 주소로 점프하는지 관찰
- GDB/Pwndbg: `finish`(현재 함수가 끝날 때까지 실행하고 반환값까지 표시), `bt`(backtrace로 스택에 쌓인 반환 주소들을 한눈에 확인), pwndbg의 `stack`으로 RSP 주변 값 확인

## 출력 해석
- RET 실행 직후 RIP 값이 CALL 명령어 바로 다음 주소와 정확히 일치하면 정상 반환이다.
- GDB에서 `finish` 실행 시 `Run till exit from #0 ...` 뒤에 `Value returned is $1 = ...`가 나오면, 이게 함수의 반환값(RAX)이다.
- `ret` 실행 직전 `[RSP]`가 코드 영역이 아닌 이상한 값(예: 스택에 쌓인 사용자 입력 바이트 그대로)이면, 반환 주소가 변조됐다는 뜻이며 크래시나 익스플로잇으로 이어질 수 있다.

## 흔한 실수
- **RET이 그냥 "함수 끝"이라는 표시일 뿐 스택에서 실제로 값을 읽어온다는 걸 잊는 것** — RET은 반드시 `[RSP]`에서 반환 주소를 읽어야 동작한다. 그 값이 잘못되면 RET도 잘못된 곳으로 튄다.
- **`ret n`을 오타나 특이 케이스로 여기고 무시하는 것** — 이는 명확히 "이 함수는 callee-cleanup(stdcall류) 규약"이라는 중요한 정보다.
- **함수 안에서 PUSH/POP 균형이 안 맞아도 RET이 알아서 맞춰줄 거라 착각**하는 것 — RET은 그냥 `[RSP]`를 읽을 뿐이다. 균형이 안 맞으면 그 자리엔 반환 주소가 아닌 다른 값이 있을 수 있다.
- CALL과 RET을 별개로만 보고 "짝을 이룬다"는 사실을 놓쳐서, 함수 하나를 분석할 때 그 함수를 호출한 CALL 지점과 대응해서 생각하지 않는 것.
- 스택 버퍼 오버플로우 문제를 볼 때 "버퍼 크기"만 보고 "버퍼와 반환 주소 사이의 정확한 오프셋"을 계산하지 않는 것 — 이 오프셋을 정확히 알아야 반환 주소만 정밀하게 덮어쓸 수 있다.

## 막혔을 때 다음 체크
- RET 이후 어디로 갔는지 모르겠으면 → RET 실행 직전 `[RSP]` 값을 디버거에서 직접 확인한다.
- 스택 균형이 안 맞는 것 같으면 → 함수 안의 모든 PUSH(및 CALL — CALL도 내부적으로 8바이트 push)와 모든 POP(및 이 함수 자신의 RET)을 하나씩 센다.
- `ret n`의 n 값이 이해가 안 되면 → 그 함수가 스택으로 받는 인자의 총 바이트 수(x86 기준 인자 개수 × 4)와 비교해본다.
- ROP 관련 코드로 의심되면 → 반환 주소로 지정된 각 주소가 짧은 명령어 시퀀스 + `ret`으로 끝나는 "가젯"인지 확인한다.

## 미니 예제

**예제 1 — 기본 함수 반환**
```c
int add(int a, int b) {
    return a + b;
}
```
```asm
add:
    push rbp
    mov  rbp, rsp
    mov  eax, ecx      ; a (Windows x64 기준 1번째 인자)
    add  eax, edx       ; + b
    pop  rbp
    ret                  ; 반환값은 EAX, 반환 주소로 복귀
```

**예제 2 — stdcall류 `ret n`**
```c
// x86 stdcall 스타일 예시
int __stdcall Sum2(int a, int b) {
    return a + b;
}
```
```asm
_Sum2@8:
    push ebp
    mov  ebp, esp
    mov  eax, [ebp+8]   ; a
    add  eax, [ebp+0Ch]  ; + b
    pop  ebp
    ret  8                 ; 반환 + 인자 2개분(8바이트) 스택 정리
```

**예제 3 — CALL/RET 스택 균형**
```asm
caller:
    ; RSP = 0x1000 이라 가정
    call callee          ; RSP -= 8 -> 0xFF8, 반환주소 push
    ; call 이후 이 지점 도달 시 RSP는 다시 0x1000이어야 정상
    ...

callee:
    push rbp               ; RSP -= 8
    mov  rbp, rsp
    sub  rsp, 20h            ; 지역 변수 공간 (RSP -= 0x20)
    ...
    add  rsp, 20h            ; 지역 변수 공간 반납 (RSP += 0x20)
    pop  rbp                 ; RSP += 8
    ret                        ; 반환 주소 pop, RSP += 8 -> callee 진입 전 상태로 정확히 복귀
```

**예제 4 — 스택 버퍼 오버플로우로 인한 반환 주소 변조 (개념 예시)**
```c
void vuln(char *input) {
    char buf[16];
    strcpy(buf, input);   // 길이 제한 없음
}
```
```asm
vuln:
    push rbp
    mov  rbp, rsp
    sub  rsp, 20h           ; buf[16] + 정렬용 여유
    ...
    call strcpy               ; input이 16바이트보다 길면 buf 뒤의 저장된 rbp, 반환주소까지 덮어씀
    leave
    ret                        ; [RSP]가 이미 공격자가 덮어쓴 값 -> 임의 주소로 실행 흐름 이동
```

## 관련 글
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [LEAVE: 함수 에필로그와 스택 프레임](./rev-0073-leave.md)
- [PUSH: 스택에 값 넣기](./rev-0044-push.md)
- [POP: 스택에서 값 꺼내기](./rev-0045-pop.md)

## 출처/검증
- RET/RETN 명령어 동작(반환 주소 pop, RSP 증가, `ret n`의 추가 스택 정리): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "RET—Return from Procedure" 섹션 기준 (2026-09-08 검증).
- stdcall(callee-cleanup) vs cdecl(caller-cleanup) 스택 정리 책임 차이: Microsoft Learn 호출 규약 문서 기준.
- ROP(Return-Oriented Programming) 개념 및 RET 체이닝 기법: 일반 익스플로잇/취약점 분석 참고자료 기준.
