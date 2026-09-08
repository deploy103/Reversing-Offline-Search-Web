---
id: REV-0397
title: "BT: 비트 테스트"
slug: "rev-0397-bt"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - bt
  - BT
  - Bt
  - bt 명령어
  - bt instruction
  - bit test
  - 비트 테스트
  - "bt eax, 3"
  - "bt eax, ecx"
  - CF 비트
  - carry flag bit
  - 비트마스크 검사
  - bit flag check
  - 플래그 비트 검사
aliases:
  - bt 뭐임
  - bt가 뭐죠
  - BT 명령어
  - 비트 테스트 명령어
  - bt와 test 차이
  - bt test 차이점
symptom_keywords:
  - bt eax 3이 뭔지 모르겠음
  - CF에 비트값이 왜 들어가는지 모르겠음
  - 특정 비트만 검사하는 명령어를 모르겠음
  - test eax 8 대신 bt를 쓰는 이유
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BT`(Bit Test)는 지정한 비트 위치의 값을 **CF(Carry Flag)로 복사만 하고 오퍼랜드는 전혀 바꾸지 않는** 명령어다. "이 비트가 켜져 있나?"를 확인할 때 쓴다.

## 언제 검색해야 하나
- `bt eax, 3`, `bt dword ptr [rbx], ecx` 같은 코드를 만났는데 무슨 뜻인지 모를 때
- CF(캐리 플래그)가 산술 연산 없이 바뀌는 걸 디버거에서 보고 이상하다고 느낄 때
- `test eax, 8` 같은 비트마스크 검사와 `bt eax, 3`의 차이가 궁금할 때
- BTS/BTR/BTC와 BT의 관계가 헷갈릴 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BT r/m16, r16
BT r/m32, r32
BT r/m64, r64
BT r/m16/32/64, imm8
```
- 첫 번째 오퍼랜드(dest)는 검사할 값이 들어있는 레지스터 또는 메모리, 두 번째 오퍼랜드(src)는 **검사할 비트의 위치(bit index)**다.
- 비트 위치는 즉시값(`bt eax, 5`)일 수도 있고, 레지스터(`bt eax, ecx`)일 수도 있다.
- dest가 **레지스터**일 때는 비트 위치가 오퍼랜드 크기로 모듈로(mod) 연산된다 — 예를 들어 `bt eax, 40`이면 40 mod 32 = 8번 비트를 검사한다.
- dest가 **메모리**일 때는(레지스터로 비트 위치를 지정한 경우) CPU가 유효 주소를 비트 오프셋만큼 조정해서 메모리 전체를 마치 하나의 거대한 비트 배열처럼 다룰 수 있다. 실무 리버싱에서는 이 메모리 형태보다 레지스터 오퍼랜드가 훨씬 흔하다.

### 실제로 하는 일
`BT dest, n`은 `dest`의 `n`번째 비트(0부터 시작, LSB가 0번)를 읽어서 **CF에 그대로 복사**한다. `dest`는 어떤 방식으로도 수정되지 않는다.
```
CF = (dest >> n) & 1
```
이것이 전부다. AND/OR 같은 연산 결과를 저장하지 않는다는 점에서 [TEST](rev-0059-test.md)와 철학이 비슷하지만, TEST는 "값이 0인가"를 보는 반면 BT는 "특정 위치의 비트 하나가 1인가"를 직접 CF로 뽑아낸다는 점이 다르다.

### 플래그 변화
- **CF**: 지정된 비트의 원래 값으로 설정됨 (BT의 핵심 결과)
- **OF, SF, AF, PF, ZF**: 정의되지 않음(undefined) — 이후 코드가 이 플래그들을 참조해서는 안 된다.

BT 다음에는 보통 `JC`(CF=1이면 분기, JB와 동일 인코딩) 또는 `JNC`(CF=0이면 분기, JAE와 동일 인코딩)가 이어진다.

### 스택/RSP/RIP 변화
없음. dest를 수정하지 않는 순수 검사 명령이다.

### BT vs TEST — 언제 각각 쓰이나
`test eax, 8`(즉시값 8 = `1000b`)도 결국 3번 비트를 검사하는 것과 같은 효과(ZF로 결과 확인)를 낼 수 있지만, 차이가 있다.
- `TEST`는 결과를 **ZF**로 알려준다(0인지 아닌지).
- `BT`는 결과를 **CF**로 알려준다(그 비트가 1인지 0인지 직접).
- `BT`는 **비트 위치를 레지스터 값으로 동적으로 지정**할 수 있다(`bt eax, ecx`) — 이건 TEST/AND로는 불가능하다(TEST는 정적 비트마스크만 가능). 따라서 "검사할 비트 번호가 실행 중에 결정되는" 코드(예: 비트셋/플래그 배열에서 임의의 인덱스 비트를 검사)에서는 컴파일러가 BT를 선택한다.
- 컴파일러는 비트 번호가 컴파일 타임에 고정돼 있으면 대개 `TEST`(더 짧고 흔한 인코딩)를 쓰고, 비트 번호가 변수(런타임 값)일 때만 `BT`를 쓰는 경향이 있다.

## 화면/코드에서 보이는 징후
- `bt eax, 5` / `jc target` — "5번 비트가 켜져 있으면 분기"
- `bt eax, ecx` — 검사할 비트 번호 자체가 변수(ecx)인 동적 비트 검사
- `bt [rbx], eax` — 메모리를 비트 배열처럼 다루는 드문 형태(비트셋 라이브러리, `std::bitset::test()` 등에서 등장 가능)
- BT 직후 `jc`/`jnc`/`jb`/`jae` — CF 하나만으로 분기하는 조건문

## 가장 먼저 할 것
1. dest(어떤 값)와 검사 대상 비트 번호를 확인
2. 비트 번호가 상수인지, 레지스터(런타임 값)인지 확인
3. BT 직후 CF를 사용하는 분기(`jc`/`jnc`)를 찾아 조건문 의미를 해석

## 단계별 절차

**1) 고정 비트 번호 검사**
```asm
bt   eax, 4
jc   flag_set
```
→ `if (value & (1 << 4)) { ... }`

**2) 동적 비트 번호 검사**
```asm
mov  ecx, index      ; 검사할 비트 번호
bt   eax, ecx
jnc  not_set
```
→ `if (!(value & (1 << index))) { ... }`

## 명령어/단축키
- IDA/Ghidra 의사코드: `bt` + `jc` 조합은 대개 `(value >> n) & 1` 형태나 `(value & (1 << n)) != 0` 형태로 재구성된다.
- x64dbg/GDB: 명령 실행 후 CF 플래그 창(x64dbg는 플래그 표시줄, GDB는 `info registers eflags`)에서 CF 값을 직접 확인하면 BT의 결과를 바로 검증할 수 있다.

## 출력 해석
- BT 실행 직후 CF=1이면 해당 비트가 켜져 있던 것이고, CF=0이면 꺼져 있던 것이다.
- ZF/SF/OF 등 다른 플래그는 BT 실행 후 값이 남아있더라도 **신뢰할 수 없다** — 이전 명령의 잔여값일 수 있으므로 BT 다음에는 반드시 CF 기반 분기만 의미가 있다.

## 흔한 실수
- BT가 dest 값을 바꾼다고 착각하는 것 — BT는 절대 dest를 수정하지 않는다(비트를 설정/해제하려면 BTS/BTR/BTC를 써야 한다).
- BT 다음에 ZF 기반 분기(`jz`/`jnz`)를 기대하는 것 — BT는 ZF를 정의하지 않는다. 반드시 CF 기반 분기(`jc`/`jnc`, 또는 동일 인코딩인 `jb`/`jae`)를 찾아야 한다.
- 레지스터 dest에서 비트 번호가 오퍼랜드 크기로 모듈로 처리된다는 사실을 잊는 것 — `bt eax, 35`는 35 mod 32 = 3번 비트를 검사한다.
- `bt eax, ecx`처럼 비트 번호가 레지스터인 코드를 보고 "상수 비트 검사와 동일하다"고 넘겨짚는 것 — 이 경우 실제 검사 대상 비트는 실행 시점의 ecx 값에 따라 달라지므로 정적 분석만으로는 어떤 비트인지 알 수 없고 동적 분석(디버거로 ecx 값 확인)이 필요할 수 있다.

## 막혔을 때 다음 체크
- BT 다음 분기가 이해 안 되면 → CF를 쓰는 분기(`jc`/`jnc`/`jb`/`jae`)가 맞는지부터 확인 ([REV-0070](rev-0070-ja-jae-jb-jbe.md) 참고).
- 비트 번호가 레지스터라서 정적으로 특정이 안 되면 → 디버거로 브레이크포인트를 걸고 실제 레지스터 값을 확인.
- BT/BTS/BTR/BTC를 헷갈리면 → BT만 "읽기 전용"이고 나머지 셋은 각각 설정/해제/토글까지 수행한다는 점을 기억.

## 미니 예제

**예제 1 — 상수 비트 플래그 검사**
```c
if (flags & (1 << 4)) {
    do_something();
}
```
```asm
mov  eax, [flags]
bt   eax, 4
jnc  skip
call do_something
skip:
```

**예제 2 — 런타임 인덱스 비트 검사**
```c
int idx = get_index();
if (bitmap & (1 << idx)) {
    handle_set();
}
```
```asm
mov  eax, [bitmap]
mov  ecx, idx
bt   eax, ecx
jnc  not_handled
call handle_set
not_handled:
```

## 관련 글
- REV-0398 — BTS: 비트 설정하며 테스트
- REV-0399 — BTR: 비트 지우며 테스트
- REV-0400 — BTC: 비트 토글하며 테스트
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- BT 명령어의 오퍼랜드/플래그 동작: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BT—Bit Test" 섹션 기준 (2026-09-08 검증).
- 레지스터 dest에서 비트 위치가 오퍼랜드 크기로 모듈로 처리되는 동작: 위 SDM 문서의 Operation 의사코드 기준.
