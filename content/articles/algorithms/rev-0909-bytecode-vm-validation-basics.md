---
id: REV-0909
title: "가상머신(bytecode VM) 기반 검증 로직 초급 알아보기"
slug: "rev-0909-bytecode-vm-validation-basics"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["bytecode VM", "가상머신 크랙미", "opcode dispatch", "custom VM", "VM 기반 검증", "인터프리터 루프", "opcode 배열"]
aliases: ["VM 크랙미란", "바이트코드 인터프리터 리버싱", "opcode dispatch loop", "커스텀 가상머신 초급"]
symptom_keywords: ["코드 안에 opcode 배열이 하드코딩되어 있음", "while문 하나가 프로그램 전체 로직인 것처럼 보임", "switch case가 opcode 번호별로 나뉨", "pc라는 변수가 계속 증가하며 opcode를 읽음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Bytecode VM 기반 검증은 프로그램 로직 자체를 x86 명령어가 아니라 개발자가 만든 커스텀 "opcode 배열"로 인코딩해 놓고, 바이너리 안의 작은 인터프리터 루프(`pc`를 증가시키며 opcode를 읽어 switch/점프 테이블로 분기하는 `while` 하나)가 이 배열을 실행하는 구조이며, 실제 검증 로직은 x86 디스어셈블리가 아니라 이 opcode 배열 안에 숨어 있으므로 인터프리터의 각 opcode 핸들러부터 표로 정리해야 한다.

## 언제 검색해야 하나
- 함수 하나가 유난히 짧고 단순한데(레지스터 몇 개, `while(1)` 루프 하나, `switch` 하나) 이 함수가 프로그램의 핵심 검증 로직 전체를 담당하고 있다고 알려져 있을 때(문제 설명, 또는 다른 함수에서 이 함수만 호출)
- `.rodata`나 전역 배열에 의미를 알 수 없는 바이트 나열(`unsigned char bytecode[] = {0x01, 0x05, 0x02, ...}`)이 있고, 이 배열이 그 루프 함수에 인자로 전달될 때
- 디스어셈블리 자체는 짧은데 실행하면 아주 복잡한 동작을 하는 것처럼 보일 때("의문의 인터프리터"가 있다는 신호)
- `pc`, `ip`, `program_counter` 같은 이름의 변수가 루프마다 증가하면서 배열 인덱스로 쓰일 때

## 핵심 개념

### VM 크랙미가 왜 강력한 난독화인가
일반 크랙미는 x86 명령어 자체가 곧 검증 로직이라서, IDA/Ghidra가 바로 디컴파일해준다. 반면 VM 기반 크랙미는 검증 로직을 커스텀 바이트코드로 인코딩하고, x86 코드에는 이 바이트코드를 "해석(interpret)"하는 범용 인터프리터 하나만 존재한다. 즉 IDA가 보여주는 디컴파일 결과는 "인터프리터가 어떻게 동작하는가"일 뿐이고, "무엇을 검증하는가"는 데이터로 취급되는 바이트코드 배열 안에 있다. 이 때문에 x86 디스어셈블리만 봐서는 실제 검증 로직이 거의 안 보인다 — 인터프리터 자체를 먼저 이해해야 데이터(바이트코드)를 해석할 수 있다.

### 인터프리터 루프의 전형적인 골격
아무리 복잡한 VM이라도 인터프리터의 핵심 골격은 거의 항상 다음과 같다.

```c
uint8_t stack[256];
int sp = 0;              // stack pointer
int pc = 0;              // program counter
int regs[8] = {0};       // 레지스터 역할 배열(있을 수도, 없을 수도)

while (pc < bytecode_len) {
    uint8_t op = bytecode[pc++];
    switch (op) {
        case 0x01: /* PUSH_IMM */
            stack[sp++] = bytecode[pc++];
            break;
        case 0x02: /* ADD */
            stack[sp-2] = stack[sp-2] + stack[sp-1];
            sp--;
            break;
        case 0x03: /* XOR_KEY */
            stack[sp-1] ^= key[pc % key_len];
            break;
        case 0x04: /* CMP_INPUT */
            stack[sp-1] = (stack[sp-1] == input[input_idx++]);
            break;
        case 0xFF: /* HALT */
            return stack[0];
        default:
            return 0;  // unknown opcode = fail
    }
}
```

이 구조의 핵심 요소는 다음과 같이 항상 정해져 있다.

- **`pc`(program counter)**: 다음에 실행할 바이트코드 위치. 루프마다 최소 1씩 증가.
- **`stack` 또는 `regs`**: 연산 결과를 저장하는 공간. 스택 기반 VM(대부분의 간단한 커스텀 VM)과 레지스터 기반 VM(더 정교한 경우) 두 계열이 있다.
- **opcode dispatch**: `switch(op)` 또는 함수 포인터 배열(`handlers[op](...)`)로 분기. 함수 포인터 배열 형태면 `.rodata`에 코드 주소들이 나열된 테이블이 하나 더 있다는 신호다.
- **종료 조건**: 특정 opcode(`HALT`, `RET` 등)를 만나거나 `pc`가 바이트코드 길이를 넘으면 종료하고, 마지막 스택 값이나 특정 플래그로 성공/실패를 판정.

### 초급 단계에서 목표로 삼을 것
VM 리버싱은 깊게 들어가면 자동 디스어셈블러 제작(opcode마다 오퍼랜드 길이를 파싱하는 완전한 디스어셈블러)까지 갈 수 있지만, 초급 단계의 현실적인 목표는 다음 두 가지면 충분하다.

1. **opcode 표 만들기**: `switch`의 각 `case` 번호와 그 안에서 하는 일(스택에서 몇 개를 꺼내 어떤 연산을 하고 몇 개를 넣는지)을 표로 정리한다.
2. **바이트코드를 파이썬 인터프리터로 그대로 재현하기**: x86 인터프리터의 동작을 파이썬 함수로 옮기고, 실제 바이트코드 배열을 그 파이썬 인터프리터에 넣어 같은 결과가 나오는지 확인한다. 이 단계가 되면 이후에는 파이썬 레벨에서 바이트코드를 자유롭게 분석(어떤 입력이 성공하는지 시뮬레이션, 필요하면 Z3에 넘기기)할 수 있다.

### 실행 흐름을 눈으로 보는 가장 쉬운 방법 — 동적 디버깅
정적으로 opcode 표를 만드는 게 막막하면, GDB/x64dbg로 인터프리터 루프에 브레이크포인트를 걸고 `pc`와 `op` 값을 매 반복마다 출력하는 것이 가장 빠르다. 실제 입력 하나를 넣고 몇 번 반복 실행해보면 "이 opcode 다음엔 항상 이런 패턴"이라는 감이 정적 분석보다 훨씬 빨리 잡힌다.

## 화면/코드에서 보이는 징후
- 함수 하나에 `while` 또는 `for(;;)` 루프 하나와 그 안에 큰 `switch`문 하나만 있음
- `.rodata`에 의미 불명의 바이트 배열이 있고 이 배열의 길이가 꽤 김(수십~수백 바이트)
- 스택처럼 쓰이는 지역 배열이 있고 `sp++`, `sp--`처럼 증감되는 인덱스 변수가 있음
- 함수 포인터 배열(코드 주소가 나열된 테이블)이 있고 `op` 값으로 이 배열을 인덱싱해 `call`하는 코드

## 가장 먼저 할 것
문제 설명이나 다른 함수의 호출 관계를 보고 "이 함수가 VM 인터프리터"라는 심증을 굳힌 뒤, 바이트코드 배열의 시작 주소와 길이를 먼저 확정한다. 그다음 인터프리터 함수의 `switch`문에서 나오는 모든 `case` 번호를 빠짐없이 나열해 opcode 개수를 센다.

## 단계별 절차
1. 바이트코드 배열을 IDA/Ghidra Hex View로 통째로 덤프해 파이썬 `bytes` 객체로 옮긴다.
2. 인터프리터의 `switch(op)` 각 `case`를 하나씩 읽으며 "opcode 번호 → 하는 일(스택 입출력, 레지스터 변경, pc 이동)"을 표로 정리한다. 오퍼랜드가 있는 opcode(예: `PUSH_IMM`처럼 바이트코드에서 추가로 값을 읽는 경우)는 `pc`가 몇 바이트 더 소비되는지도 반드시 기록한다.
3. 정리한 표를 그대로 파이썬 함수로 옮겨 미니 인터프리터를 작성한다.
4. 알려진 입력(테스트용으로 아무 문자열)을 이 파이썬 인터프리터에 넣어 실행하고, 실제 바이너리를 GDB로 같은 입력으로 실행했을 때와 중간 상태(스택 값, pc 진행)가 일치하는지 비교한다.
5. 파이썬 인터프리터가 검증되면, 이후에는 바이트코드 자체를 분석해 어떤 입력이 성공하는지 판단한다(단순 비교면 값 추출, 복잡한 조건이면 Z3에 제약식으로 넘기는 것도 고려, REV-0917).

## 명령어/단축키
```python
def run_vm(bytecode: bytes, user_input: bytes) -> bool:
    stack = []
    pc = 0
    input_idx = 0
    while pc < len(bytecode):
        op = bytecode[pc]; pc += 1
        if op == 0x01:              # PUSH_IMM
            stack.append(bytecode[pc]); pc += 1
        elif op == 0x02:            # ADD
            b = stack.pop(); a = stack.pop(); stack.append((a + b) & 0xFF)
        elif op == 0x03:            # XOR_INPUT
            v = stack.pop()
            stack.append(v ^ user_input[input_idx]); input_idx += 1
        elif op == 0x04:            # CMP_TOP_ZERO
            stack.append(1 if stack.pop() == 0 else 0)
        elif op == 0xFF:            # HALT
            return bool(stack[-1])
        else:
            return False
    return False
```
GDB: 인터프리터 루프 안 `switch` 분기 직전 주소에 `break *0x<addr>` 걸고 `commands`로 `printf "pc=%d op=%d\n", $rax, $rbx` 같은 자동 출력을 등록하면 opcode 실행 순서를 통째로 로그로 뽑을 수 있다.

## 출력 해석
- 파이썬 인터프리터 실행 결과가 실제 바이너리 실행 결과(성공/실패)와 매 테스트 케이스마다 일치하면 opcode 표가 정확하다는 뜻이다.
- 특정 opcode에서만 결과가 어긋난다면 그 opcode의 오퍼랜드 소비 바이트 수를 잘못 세었을 가능성이 크다 — `pc`가 한 바이트라도 어긋나면 그 뒤 모든 해석이 밀려서 완전히 틀어진다.
- `default` 분기(알 수 없는 opcode)에 자주 걸린다면 opcode 표에서 빠뜨린 case가 있다는 뜻이니 `switch`문을 다시 훑어야 한다.

## 흔한 실수
- 오퍼랜드가 있는 opcode(추가로 바이트를 더 읽는 것)와 없는 opcode를 구분하지 않고 무조건 `pc += 1`만 하는 것 — 이러면 오퍼랜드 바이트를 다음 opcode로 잘못 해석하게 되어 이후 전체가 어긋난다.
- VM이라는 걸 알아채지 못하고 이 루프 하나를 x86 수준에서 명령어 단위로 스텝하며 몇 시간을 소모하는 것 — 함수가 유난히 짧고 반복적인데 동작이 복잡하면 먼저 "이거 VM 아닐까"부터 의심해야 한다.
- 함수 포인터 배열 방식의 dispatch를 보고도 이를 알아채지 못해 opcode 핸들러 목록을 다 못 찾는 것 — `call [handlers + op*8]` 같은 간접 호출이 보이면 `handlers` 배열 자체를 덤프해서 각 opcode가 가리키는 코드 주소를 모두 찾아야 한다.
- 첫 테스트에서 결과가 맞았다고 바로 신뢰하는 것 — opcode 표에 실수가 있어도 우연히 한 케이스는 맞을 수 있으므로, 최소 3~5개의 서로 다른 입력으로 교차 검증해야 한다.

## 막혔을 때 다음 체크
- 이 VM 뒤에 상태 기계나 해시 비교가 추가로 이어진다면 → REV-0908 State Machine(상태 기계) 기반 검증 로직 알아보기, REV-0911 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- 파이썬으로 재현한 인터프리터를 실제 바이너리와 정확히 교차 검증하는 절차가 궁금하면 → REV-0919, REV-0912
- 재구성한 opcode 로직이 너무 복잡해서 손으로 입력을 못 찾겠다면 → REV-0917 Z3로 풀기 전에 손으로 먼저 검증 로직 축소하기, REV-0271 angr 심볼릭 실행 기초
- 이런 VM을 처음부터 자동으로 에뮬레이션하고 싶다면 → REV-0273 Unicorn으로 작은 검증 함수 에뮬레이션

## 미니 예제
바이트코드 `01 05 01 03 02 04 FF`가 있고, 위의 미니 인터프리터로 해석한다고 하자.

```python
bytecode = bytes([0x01, 0x05, 0x01, 0x03, 0x02, 0x04, 0xFF])
# 01 05 -> PUSH_IMM 5        : stack=[5]
# 01 03 -> PUSH_IMM 3        : stack=[5,3]
# 02    -> ADD               : stack=[8]
# 04    -> CMP_TOP_ZERO      : stack=[0]  (8은 0이 아니므로 결과 0)
# FF    -> HALT, return bool(stack[-1]) == False

print(run_vm(bytecode, b""))  # False
```

이 바이트코드는 입력과 무관하게 항상 실패하도록 만들어진 예시다. 실전에서는 `XOR_INPUT`처럼 사용자 입력을 소비하는 opcode가 섞여 들어가면서 최종 스택 값이 입력에 따라 달라지고, 그 최종 값이 특정 조건(0이 아님, 또는 특정 상수와 일치)을 만족해야 `HALT`에서 성공을 리턴하는 구조로 확장된다. opcode 표를 정확히 만들었다면, 이런 조건을 만족하는 입력을 Z3 제약식(REV-0268, REV-0269)으로 넘겨 자동으로 풀어낼 수도 있다.

## 관련 글
- REV-0908 — State Machine(상태 기계) 기반 검증 로직 알아보기
- REV-0911 — 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- REV-0271 — angr 심볼릭 실행 기초
- REV-0273 — Unicorn으로 작은 검증 함수 에뮬레이션
- REV-0268 — Z3 BitVec 기초
- REV-0917 — Z3로 풀기 전에 손으로 먼저 검증 로직 축소하기

## 출처/검증
- 스택 기반/레지스터 기반 가상머신 인터프리터의 opcode dispatch 골격(`pc` 증가, switch/함수 포인터 분기, 스택 push/pop): 프로그래밍 언어 구현론(바이트코드 인터프리터 설계) 및 CTF 리버싱 커뮤니티에서 통용되는 VM 크랙미 분석 기법 기준.
- 커스텀 VM이 정적 디스어셈블 기반 분석을 어렵게 만드는 이유(로직이 데이터로 인코딩됨): 코드 난독화 일반 기법 중 하나로 널리 알려진 개념 (2026-09-09 검증).
