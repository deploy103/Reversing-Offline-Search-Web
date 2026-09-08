---
id: REV-0485
title: "TEST 명령의 의미를 몰라서 분기 조건을 못 찾을 때"
slug: "rev-0485-test-instruction-meaning"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - test instruction meaning
  - test 명령어 의미
  - test eax eax
  - test al al
  - test 비트마스크
  - test bit check
  - TEST vs CMP
  - test 값 안 바뀜
  - implicit AND
  - 비트 검사
aliases:
  - test eax eax가 뭐임
  - test 명령이 뭐하는 거임
  - test랑 cmp 차이
  - test 뒤 분기가 이해 안 됨
symptom_keywords:
  - test 명령 뒤 분기 조건을 모르겠음
  - test eax eax 의미를 모르겠음
  - test 값이 왜 안 바뀌는지 모름
  - test로 특정 비트 검사하는 걸 모름
  - test와 cmp 차이를 모름
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`TEST a, b`는 `a AND b`를 계산해서 그 결과로 **플래그만 세팅**하고 `a`와 `b` 자체는 전혀 바꾸지 않는 명령어이며, 가장 흔한 형태인 `test eax, eax`는 "EAX가 0인지 아닌지"를 검사하는 관용구이고 `test eax, 특정값`은 "특정 비트가 켜져 있는지" 검사하는 비트마스크 관용구라는 것만 알면 분기 조건을 바로 읽을 수 있다.

## 언제 검색해야 하나
- `test eax, eax` 바로 뒤에 `jz`/`jnz`가 오는데 이게 무슨 조건인지 감이 안 잡힐 때
- `test eax, 4` 처럼 오퍼랜드가 상수인 `TEST`를 만나서 "4랑 뭘 비교하는 거지?"라고 헷갈릴 때
- `TEST`와 `CMP`가 둘 다 "값을 안 바꾸고 플래그만 세팅한다"고 배웠는데 정확히 뭐가 다른지 모를 때
- CALL 직후 `test eax, eax`가 반복적으로 나오는 이유(반환값 검사 패턴)를 모를 때

## 핵심 개념

### TEST가 실제로 하는 일
`TEST dest, src`는 내부적으로 `dest AND src`를 계산하지만, **그 결과를 dest에 저장하지 않고 버린다.** 대신 그 계산 결과를 바탕으로 플래그만 세팅한다.
```
연산: temp = dest AND src   (temp는 버려짐, dest/src 값 그대로 유지)
ZF = (temp == 0) ? 1 : 0
SF = temp의 최상위 비트
PF = temp 하위 바이트의 패리티
CF = 0 (항상 클리어)
OF = 0 (항상 클리어)
```
즉 `TEST`는 "AND는 계산하되 그 결과는 저장하지 않고, 결과가 0인지/음수인지만 알고 싶다"는 명령어다(REV-0059 참고). `CMP`가 "빼기는 계산하되 저장 안 함"인 것과 정확히 같은 구조로, `AND` 버전이 `TEST`, `SUB` 버전이 `CMP`다.

### 가장 흔한 형태: `test reg, reg` (자기 자신과 AND) — "0인지 검사"
```asm
test  eax, eax
jz    is_zero      ; EAX가 0이면 점프
jnz   not_zero     ; EAX가 0이 아니면 점프
```
어떤 값이든 **자기 자신과 AND하면 결과는 원래 값과 같다**(`x AND x = x`). 그래서 `test eax, eax`는 사실상 "EAX 값 자체가 0인가?"를 검사하는 것과 동일하다. `cmp eax, 0`을 쓰는 것과 논리적으로 결과가 같지만, `test eax, eax`가 인코딩이 더 짧고(즉치값 0을 따로 넣을 필요 없음) 더 널리 쓰이는 관용구다.

이 패턴은 함수 호출 직후 반환값을 검사할 때 압도적으로 많이 등장한다(REV-0071 참고).
```asm
call    strcmp
test    eax, eax
jnz     not_equal    ; strcmp가 0이 아니면(다르면) 분기
```

### 두 번째로 흔한 형태: `test reg, 상수` — "특정 비트가 켜져 있는지 검사"
```asm
test  eax, 1        ; EAX의 최하위 비트(bit 0)만 검사 -> 홀짝 판단
jz    is_even
jnz   is_odd
```
`상수` 부분이 검사하고 싶은 비트 위치에만 1이 있는 **비트마스크**다. `AND` 결과가 0이 아니려면 그 비트 위치에 원래 값도 1이어야 하므로, `test eax, mask`는 "mask로 표시된 비트들 중 하나라도 켜져 있는가?"를 검사하는 셈이다.
```asm
test  eax, 4         ; bit 2(값 4 = 0b100)가 켜져 있는지 검사
jnz   flag_bit2_set
```
플래그(권한 비트, 옵션 플래그 등)를 다루는 코드에서 이 패턴이 매우 흔하다.

### TEST와 CMP의 차이 정리
```
TEST dest, src  ->  내부적으로 dest AND src 계산, 결과 버림, 플래그만 세팅
CMP  dest, src  ->  내부적으로 dest SUB src 계산, 결과 버림, 플래그만 세팅
```
용도가 다르다: `CMP`는 "두 값의 크기 관계(같다/크다/작다)"를 알고 싶을 때, `TEST`는 "0인지 아닌지" 또는 "특정 비트가 켜져 있는지"를 알고 싶을 때 쓴다. `TEST eax, eax`를 `CMP eax, eax`로 착각하면 안 된다 — `CMP eax, eax`는 항상 같으므로 무의미하지만(자기 자신과의 크기 비교는 항상 "같다"), `TEST eax, eax`는 값이 0인지 아닌지를 의미있게 검사한다.

## 화면/코드에서 보이는 징후
- `call 함수` 바로 뒤에 `test eax, eax` — 반환값(포인터 NULL 체크, 성공/실패 코드 0 체크)을 검사하는 매우 흔한 패턴
- `test al, al` — 1바이트(bool, char) 반환값이나 상태값을 검사
- `test eax, 상수` — 상수가 2의 거듭제곱(1, 2, 4, 8, ...)이면 특정 비트 하나를 검사하는 것
- `test eax, 상수` — 상수가 여러 비트가 켜진 값(예: 0x0C = 0b1100)이면 그 비트들 중 하나라도 켜져 있는지 검사

## 가장 먼저 할 것
1. `TEST`의 두 오퍼랜드가 같은 레지스터인지, 다른 레지스터/상수인지 구분한다.
2. 같은 레지스터라면 "0인지 아닌지" 검사로 즉시 해석한다.
3. 상수가 있다면 그 상수를 2진수로 펼쳐서 어떤 비트 위치를 검사하는지 확인한다.

## 단계별 절차
**1) 오퍼랜드 유형 파악**

`test eax, eax`(같은 레지스터) 인지 `test eax, 4`(상수) 인지, `test eax, ecx`(다른 레지스터, 흔치 않지만 존재) 인지 구분한다.

**2) 값이 0인지 검사하는 경우 — 뒤따르는 Jcc로 조건 완성**

바로 뒤 `jz`(0이면 점프) / `jnz`(0이 아니면 점프)와 결합해서 "EAX == 0이면 X" 또는 "EAX != 0이면 Y" 문장으로 정리한다.

**3) 비트마스크 검사인 경우 — 상수를 2진수로 변환**

`test eax, 4`라면 `4 = 0b100`이므로 "bit 2가 켜져 있는가"로 해석한다. 파이썬으로 `bin(4)`를 찍어보면 바로 확인된다.

**4) 함수 반환값 검사 문맥인지 확인**

바로 위에 `call`이 있다면 이건 REV-0071에서 다룬 "반환값을 즉시 검사하는" 매우 흔한 패턴이므로, 그 함수가 무엇을 반환하는 함수인지(포인터? 에러코드? bool?) 확인하면 검사 의도가 분명해진다.

## 명령어/단축키
- IDA: F5 디컴파일에서 `test eax, eax; jz L`은 보통 `if (v1 == 0)` 또는 `if (!v1)`으로, `test eax, 4; jnz L`은 `if (v1 & 4)`로 자동 정리되어 나온다 — 헷갈리면 디컴파일 결과와 대조하는 게 가장 빠르다.
- x64dbg/GDB: `TEST` 실행 직후 플래그 레지스터(ZF 등)를 확인해서 직접 계산과 일치하는지 검증
- Python: `bin(mask)`로 비트마스크 상수를 2진수로 즉시 변환해서 확인

## 출력 해석
- `test eax, eax` 이후 `ZF=1`이면 EAX가 0이었다는 뜻이고, `ZF=0`이면 0이 아니었다는 뜻이다.
- `test eax, mask` 이후 `ZF=1`이면 mask로 표시된 비트들이 EAX에서 전부 꺼져 있었다는 뜻이고, `ZF=0`이면 그중 하나 이상이 켜져 있었다는 뜻이다.
- `TEST` 실행 후에도 EAX/원본 오퍼랜드 값 자체는 실행 전과 완전히 동일해야 한다 — 값이 바뀌었다면 다른 명령어를 TEST로 착각한 것이다.

## 흔한 실수
- `test eax, eax`를 보고 "EAX 값이 바뀌었나?"라고 값 변화를 찾으려 하는 것 — `TEST`는 절대 오퍼랜드를 바꾸지 않는다.
- `test eax, 상수`의 상수를 "비교할 값"으로 오해해서 `cmp eax, 상수`와 똑같이 해석하는 것 — `TEST`의 상수는 크기 비교 대상이 아니라 **비트마스크**다.
- `TEST`와 `CMP`를 아무 차이 없는 동의어로 생각하는 것 — 내부 연산(AND vs SUB)이 다르므로 세팅되는 플래그의 "의미"도 다르게 해석해야 한다.
- 반환값이 없는(void) 함수 호출 뒤에 우연히 `test eax, eax`가 있는 걸 보고 "이 함수도 반환값을 검사하는구나"라고 착각하는 것 — 이 경우는 그냥 다른 목적으로 EAX를 재사용하는 코드일 수 있으니 문맥을 함께 봐야 한다.

## 막혔을 때 다음 체크
- TEST 명령어 자체의 문법과 인코딩을 더 자세히 보고 싶으면 → REV-0059(TEST: 값을 바꾸지 않는 AND 비교)
- TEST 뒤에 오는 Jcc 조건 방향이 헷갈리면 → REV-0481(Jcc 조건을 반대로 착각해서 로직을 잘못 해석했을 때)
- CMP와의 차이를 더 명확히 하고 싶으면 → REV-0060(CMP: 값을 바꾸지 않는 SUB 비교)
- 반환값 검사 패턴 전체 흐름(CALL과 함께)을 다시 보고 싶으면 → REV-0071(CALL: 함수 호출, 반환 주소, 인자 추적)

## 미니 예제
**예제 1 — 함수 반환값(포인터) NULL 체크**
```c
void *p = malloc(size);
if (p == NULL) {
    return -1;
}
```
```asm
call    malloc
test    rax, rax     ; rax(반환된 포인터)가 0(NULL)인지 검사
jz      alloc_failed
```

**예제 2 — 비트 플래그 검사**
```c
if (flags & 0x08) {  // bit 3이 켜져 있으면
    do_something();
}
```
```asm
test  eax, 8          ; 0b1000, bit 3 검사
jz    skip             ; 꺼져 있으면 건너뜀
call  do_something
skip:
```

**예제 3 — TEST와 CMP를 나란히 비교**
```asm
; "EAX가 0인가?" - TEST 사용
test  eax, eax
jz    is_zero

; "EAX가 10인가?" - 이건 TEST로 못함, CMP 사용
cmp   eax, 10
je    is_ten
```
0인지 검사할 땐 TEST, 특정 값과 같은지/크기를 비교할 땐 CMP — 이 구분이 핵심이다.

## 관련 글
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0481 — Jcc 조건을 반대로 착각해서 로직을 잘못 해석했을 때
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화

## 출처/검증
- TEST의 내부 연산(AND, 결과 미저장, 플래그만 세팅)과 세팅되는 플래그 목록: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "TEST—Logical Compare" 섹션 기준.
- `test reg, reg`가 0 검사 관용구로 쓰이는 컴파일러 코드 생성 관행: GCC/LLVM 코드 생성 관련 일반 최적화 문서 기준(2026-09-08 확인).
