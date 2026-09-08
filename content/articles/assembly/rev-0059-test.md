---
id: REV-0059
title: "TEST: 값을 바꾸지 않는 AND 비교"
slug: "rev-0059-test"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - test
  - TEST
  - Test
  - test 명령어
  - test instruction
  - "test eax, eax"
  - "test rax, rax"
  - test eax eax
  - null 체크
  - null check
  - zero check
  - 제로 체크
  - test vs cmp
  - test와 cmp 차이
  - test 명령이 뭔지
  - 비교만 하고 값 안바뀌는 연산
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - test 뭐임
  - test이 뭐죠
  - test 명령
  - TEST 명령어
  - 테스트 명령어
  - test eax eax 왜함
  - test와 cmp eax 0 차이
symptom_keywords:
  - test eax eax가 왜 나오는지 모르겠음
  - test rax rax가 왜 나오는지 모르겠음
  - cmp eax 0 대신 test를 쓰는 이유
  - null 체크 코드가 뭔지 모르겠음
  - if ptr == null 어셈블리
last_verified: "2026-09-08"
---

## 한 줄 요약
`TEST`는 두 오퍼랜드를 AND 연산하되 **결과를 어디에도 저장하지 않고 플래그만 세팅**하는 명령어이며, 특히 `test eax, eax`는 "eax가 0인가?"를 확인하는 컴파일러의 표준 null/zero 체크 관용구다.

## 언제 검색해야 하나
- `test eax, eax` 다음에 `jz`/`jnz`가 오는 코드를 만나서 이게 뭘 검사하는지 모를 때
- 함수 반환값 직후에 `test eax, eax`가 자주 나오는데 왜 `cmp eax, 0`을 안 쓰는지 궁금할 때
- 포인터가 NULL인지 검사하는 C 코드(`if (ptr == NULL)`)가 어셈블리로 어떻게 컴파일되는지 알고 싶을 때
- `test eax, 1`처럼 특정 비트 하나만 검사하는 코드를 분석할 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
TEST dest, src
```
- 내부적으로 `dest AND src`를 계산하지만, **그 결과를 dest(또는 어디에도)에 저장하지 않는다.** 오직 플래그만 갱신된다.
- `dest`는 레지스터/메모리, `src`는 레지스터/메모리/즉시값. 메모리-메모리 조합 불가.
- 예: `test eax, eax`, `test eax, 1`, `test byte ptr [rbp-1], 80h`.

### "값을 바꾸지 않는다"는 것의 정확한 의미
`AND`는 `dest = dest AND src`로 dest를 덮어쓰지만, `TEST`는 `dest AND src`를 계산만 하고 **dest를 원래 값 그대로 유지**한다. 즉 TEST는 "AND를 해보되 그 결과는 버리고, 결과에서 파생되는 플래그 정보만 취하는" 명령어다. 이 때문에 TEST는 원본 레지스터/메모리 값을 전혀 훼손하지 않으면서 "만약 AND를 했다면 어떤 상태였을까"를 미리 알아보는 용도로 쓰인다.

### 플래그 변화
`AND`와 완전히 동일한 플래그 규칙을 따른다 (내부적으로 AND를 계산하기 때문):
- **ZF**: `dest AND src`가 0이면 1
- **SF**: 결과의 최상위 비트가 1이면 1
- **PF**: 결과 하위 1바이트의 1비트 개수가 짝수면 1
- **CF = 0**, **OF = 0** (항상 무조건 클리어)
- **AF**: 정의되지 않음

### `test eax, eax` — 가장 중요한 패턴
`test eax, eax`는 `eax`를 자기 자신과 AND하는 것이므로 결과는 정확히 `eax`의 원래 값과 같다(자기 자신과 AND하면 값이 그대로 나옴). 따라서:
- `eax == 0` 이면 `ZF = 1`
- `eax != 0` 이면 `ZF = 0`
- `eax`의 최상위 비트(부호 비트)가 1이면(즉 `eax`가 음수로 해석될 수 있으면) `SF = 1`

즉 `test eax, eax`는 사실상 **"eax를 0과 비교한다"**와 같은 효과를 낸다. 뒤이어 `jz`(ZF=1이면 분기)를 쓰면 "eax가 0이면 분기", `jnz`(ZF=0이면 분기)를 쓰면 "eax가 0이 아니면 분기"가 된다.

### 왜 컴파일러는 `cmp eax, 0` 대신 `test eax, eax`를 쓰는가
둘 다 결과적으로 ZF를 "eax==0" 여부로 세팅한다는 점은 동일하지만, 컴파일러(GCC/Clang/MSVC 전부)는 압도적으로 `test eax, eax`를 선호한다. 이유:
1. **인코딩 크기**: `test eax, eax`는 2바이트(`85 C0`)인 반면 `cmp eax, 0`은 3바이트(`83 F8 00`, 8비트 즉시값을 부호 확장하는 형태 사용 시)다. `test`가 항상 더 짧거나 같다.
2. **즉시값 페치 불필요**: `test eax, eax`는 레지스터-레지스터 연산이라 즉시값을 디코딩할 필요가 없다. `cmp eax, 0`은 형식상 즉시값 0을 명령어 안에 담아야 한다.
3. **널리 인식되는 관용구**: 사람이 읽을 때도, 디스어셈블러가 패턴 인식을 할 때도 `test reg, reg`는 "제로 체크"라는 의미로 즉시 알아볼 수 있는 표준 관용구로 굳어져 있다.
4. **의미상 완전히 동등**: `TEST`는 CF/OF를 항상 0으로 만드는데, `CMP reg, 0`도 뺄셈 결과가 0이므로 CF=0(빌림 없음), OF=0(오버플로 없음)이 되어 이 경우에 한해 플래그 결과가 사실상 동일하다. 그래서 어느 쪽을 써도 이후의 모든 분기(`jz`, `jnz`, `jl`, `jg` 등)가 똑같이 동작한다.

핵심 정리: **레지스터를 상수 0과 비교할 때는 TEST와 CMP가 사실상 동등하고, 컴파일러는 더 작고 빠른 TEST를 선택한다.** 반대로 0이 아닌 다른 값과 비교하거나 `JA`/`JB` 같은 **unsigned** 비교가 필요하면 TEST로는 안 되고 반드시 [CMP](rev-0060-cmp.md)를 써야 한다(아래 "TEST vs CMP" 참고).

### TEST vs CMP — 근본적인 차이
| | `TEST dest, src` | `CMP dest, src` |
|---|---|---|
| 내부 연산 | `dest AND src` | `dest - src` |
| CF | 항상 0 | 뺄셈에서 빌림(borrow) 발생 여부 |
| OF | 항상 0 | 뺄셈에서 부호 있는 오버플로 여부 |
| 용도 | "이 비트가 켜져 있나?", "이 값이 0인가?" | "이 값이 저 값보다 큰가/작은가/같은가?" (임의의 두 값 비교) |
| unsigned 비교(JA/JB) | **불가능** (CF가 항상 0이라 크기 비교 정보가 없음) | 가능 |
| signed 비교(JG/JL) | 0과의 비교에서만 사실상 가능(OF가 항상 0이므로 SF만으로 판단) | 항상 가능 |

`TEST`는 진짜 뺄셈을 하지 않으므로 "A가 B보다 큰가"같은 **순서 비교**에는 근본적으로 쓸 수 없다. TEST는 오직 "특정 비트가 켜져 있는가"(`test eax, mask`) 또는 "값이 0인가/음수인가"(`test eax, eax`)를 확인하는 용도로만 쓰인다.

### 신호 있음/없음(signed/unsigned) 관점
`test eax, eax` 다음에는 signed 계열 분기(`jl`, `jg`, `jle`, `jge`)와 zero 계열 분기(`jz`, `jnz`)는 정상적으로 쓸 수 있다(TEST가 OF=0을 만들어주므로 `jl`은 사실상 SF만으로 판단되어 "음수인가"와 동일해진다). 하지만 unsigned 계열 분기(`ja`, `jb`, `jae`, `jbe`)는 TEST 뒤에 쓰면 **항상 CF=0을 기준으로 판단하므로 사실상 무의미하거나 잘못된 결과**를 낸다 — TEST 뒤에 unsigned 비교 분기가 오는 코드는 거의 없다.

### 스택/RSP/RIP 변화
없음.

## 화면/코드에서 보이는 징후
- `call some_func` 다음에 바로 `test eax, eax` — 함수 반환값(포인터 또는 정수)이 0/NULL인지 검사하는 극도로 흔한 패턴
- `test eax, eax` + `jz` — "0이면 분기" (예: `if (x == 0)`, `if (ptr == NULL)`)
- `test eax, eax` + `jnz` — "0이 아니면 분기" (예: `if (x != 0)`, `if (ptr != NULL)`)
- `test eax, 1` — 최하위 비트(홀짝, 또는 불리언 값) 검사
- `test al, al` — 바이트 크기 레지스터(보통 함수가 `bool`을 반환할 때, 반환값이 `AL`에 담김)에 대한 제로 체크

## 가장 먼저 할 것
1. 두 오퍼랜드가 완전히 같은 레지스터인지 확인 (같으면 "0인가?" 검사)
2. 다르면 어떤 비트마스크로 무슨 비트를 검사하는지 확인
3. 바로 뒤에 오는 조건부 분기(`jz`/`jnz`/`jl`/`jg` 등)를 확인해서 전체 조건문을 해석

## 단계별 절차

**1) NULL 체크 패턴 인식**
```asm
call malloc
test eax, eax
jz   alloc_failed
```
→ `if (ptr == NULL) goto alloc_failed;` (malloc 실패 검사)

**2) 반환값 0/1 (bool) 체크**
```asm
call IsValid
test al, al
jz   invalid
```
→ `if (!IsValid(...)) goto invalid;`

**3) 특정 비트 플래그 검사**
```asm
test eax, 8
jz   flag_off
```
→ `if (flags & 0x8) { ... }` (비트가 켜져 있으면 jz를 통과 — 주의: 켜져 있으면 ZF=0이라 jz는 분기 안 함)

**4) TEST로는 불가능한 unsigned 비교를 CMP로 바꿔서 읽는 훈련**
```asm
test eax, eax
ja   greater      ; 이런 조합은 사실상 등장하지 않음 - CF가 항상 0이라 무의미
```
이런 코드를 보면 원본 의도가 `cmp eax, something; ja ...` 였을 가능성을 의심해야 한다(디스어셈블러 오류이거나, 실제로는 다른 목적의 코드일 수 있음).

## 명령어/단축키
- IDA/Ghidra 의사코드에서 `test eax, eax` + `jz`는 자동으로 `if (v1 == 0)`으로, `jnz`는 `if (v1 != 0)`으로 정리된다 — 원본이 TEST였다는 사실은 소스 뷰에서만 확인 가능.
- x64dbg: 명령어 실행 후 플래그 창(ZF/SF/CF/OF)을 직접 관찰하며 TEST의 효과를 확인할 수 있다.

## 출력 해석
- Ghidra는 `test eax, eax` 다음 `jz` 블록을 `if (iVar1 == 0) { ... }`로, `jnz`는 `if (iVar1 != 0) { ... }`로 매우 정확하게 재구성한다.
- IDA F5도 동일하게 동작하며, 함수 반환값을 바로 `test`하는 패턴은 `if (!func())` 또는 `if (func())` 형태로 자연스럽게 보여준다.
- 디스어셈블리 원문에서 `test`가 보였다면, 이는 곧 "이 값 자체가 필요한 게 아니라 0 여부/비트 여부만 필요하다"는 컴파일러의 의도를 보여주는 신호다.

## 흔한 실수
- `test eax, eax`를 보고 "eax와 eax를 곱하거나 뭔가 계산하는 것"이라 오해하는 것 — 아무 계산도 저장되지 않는다. 오직 플래그만 갱신된다.
- `test`가 dest를 바꾼다고 착각해서 `test` 이후에도 `eax` 값이 달라졌을 거라 추적하는 것 — TEST는 절대 오퍼랜드를 수정하지 않는다.
- `test eax, eax` 뒤에 `ja`/`jb`(unsigned 비교)가 오는 걸 기대하는 것 — TEST는 CF를 항상 0으로 만들기 때문에 unsigned 순서 비교에는 애초에 쓰이지 않는다. 그런 비교가 필요하면 반드시 [CMP](rev-0060-cmp.md)가 쓰인다.
- `test eax, N`(N이 0이 아닌 상수)을 `cmp eax, N`(값이 N과 같은지)과 혼동하는 것 — `test eax, N`은 "eax와 N을 AND했을 때 결과가 0인가"(즉 N에 해당하는 비트가 전부 꺼져 있는가)를 묻는 것이지, "eax가 N과 같은가"를 묻는 게 절대 아니다.

## 막혔을 때 다음 체크
- `test eax, eax` 다음 분기가 이해 안 되면 → `jz`인지 `jnz`인지부터 정확히 구분 ([REV-0067](rev-0067-je-jz.md)/[REV-0068](rev-0068-jne-jnz.md) 참고).
- `test eax, N`에서 N이 0이 아니면 → N을 2진수로 풀어서 어떤 비트를 검사하는지 확인.
- 함수 호출 직후 `test`가 나오면 → 거의 항상 그 함수의 반환값(성공/실패, NULL 여부)을 검사하는 코드라고 가정하고 시작.

## 미니 예제

**예제 1 — 포인터 NULL 체크**
```c
void *p = malloc(size);
if (p == NULL) {
    return -1;
}
```
```asm
call malloc
test eax, eax
jnz  alloc_ok
mov  eax, -1
ret
alloc_ok:
```

**예제 2 — 정수 0 체크**
```c
if (count != 0) {
    process();
}
```
```asm
mov  eax, [count]
test eax, eax
jz   skip
call process
skip:
```

**예제 3 — bool 반환값 체크**
```c
if (!IsReady()) return;
```
```asm
call IsReady
test al, al
jnz  continue
ret
continue:
```

**예제 4 — 비트 플래그 검사**
```c
if (state & STATE_RUNNING) { ... }   // STATE_RUNNING = 0x2
```
```asm
mov  eax, [state]
test eax, 2
jz   not_running
; ... STATE_RUNNING이 켜져 있을 때 실행되는 코드
not_running:
```

## 관련 글
- [REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교](rev-0060-cmp.md)
- [REV-0055 — AND: 마스크와 비트 제거](rev-0055-and.md)
- [REV-0067 — JE와 JZ: ZF가 1일 때 분기](rev-0067-je-jz.md)
- [REV-0068 — JNE와 JNZ: ZF가 0일 때 분기](rev-0068-jne-jnz.md)
- [REV-0069 — JG JGE JL JLE: Signed 비교 분기](rev-0069-jg-jge-jl-jle.md)

## 출처/검증
- TEST 명령어의 오퍼랜드/플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "TEST—Logical Compare" 섹션 기준 (2026-09-08 검증).
- `test reg, reg`가 `cmp reg, 0`보다 짧고 컴파일러가 선호하는 이유(인코딩 크기): Agner Fog, "Optimizing subroutines in assembly language" 및 Intel SDM 명령어 인코딩(Opcode Map) 기준.
