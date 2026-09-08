---
id: REV-0259
title: "Python으로 Signed Unsigned 변환"
slug: "rev-0259-python-signed-unsigned"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python signed unsigned", "2의 보수 파이썬", "python 부호 변환", "to_signed", "to_unsigned", "python 음수 변환"]
aliases: ["파이썬 부호 있는 정수 변환", "2의 보수 변환 코드", "signed int python 구현"]
symptom_keywords: ["디버거에서 음수인데 파이썬은 양수", "int overflow signed python", "부호 확장 안 됨", "eax 값이 음수로 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Python 정수는 크기 제한이 없어 "부호"라는 개념이 CPU 레지스터와 다르게 동작하므로, C의 `int8_t`/`int16_t`/`int32_t`/`int64_t`와 똑같이 동작시키려면 비트 폭을 명시한 `to_signed(x, bits)` / `to_unsigned(x, bits)` 변환 함수를 직접 만들어 써야 한다.

## 언제 검색해야 하나
- 디버거의 레지스터 창에는 음수(예: `EAX = FFFFFFFF`가 `-1`로 표시)로 나오는데, Python으로 같은 값을 계산하면 항상 양수 4294967295로만 나올 때
- IDA/Ghidra 디컴파일 결과에 `int` 타입 변수가 음수 비교(`if (v < 0)`)를 쓰는데 그 값을 파이썬으로 재현해야 할 때
- `IMUL`, `IDIV`, `SAR`처럼 부호를 신경 쓰는 명령과 `MUL`, `DIV`, `SHR`처럼 부호를 신경 쓰지 않는 명령의 결과 차이를 코드로 확인하고 싶을 때

## 핵심 개념
CPU는 부호 있는 정수를 저장할 별도의 공간이 없다. 대신 **2의 보수(two's complement)** 표현을 쓴다 — 최상위 비트(MSB)가 1이면 그 비트 패턴을 "음수"로 해석할 뿐, 메모리에 저장된 비트 자체는 부호 없는 정수와 동일하다. 즉 32비트에서 `0xFFFFFFFF`라는 같은 비트 패턴이 부호 없는 관점에서는 `4294967295`, 부호 있는 관점에서는 `-1`이다.

Python의 `int`는 이런 "고정 비트 폭" 개념이 없는 임의 정밀도 정수이므로, `0xFFFFFFFF`를 그대로 쓰면 항상 4294967295로 취급된다. 따라서 부호 있는 값처럼 다루려면 **비트 폭을 정하고, 그 폭 기준으로 최상위 비트를 검사해서 필요하면 2^bits를 빼주는** 변환을 직접 해야 한다. 변환 공식은 다음과 같다.

- 부호 없는 → 부호 있는: `x >= 2**(bits-1)`이면 `x -= 2**bits`
- 부호 있는 → 부호 없는: `x < 0`이면 `x += 2**bits` (그 다음 `& mask`로 폭 안에 가두면 안전)

## 화면/코드에서 보이는 징후
- x64dbg/OllyDbg의 레지스터 창에서 부호 있는 10진수 표시(`-1`)와 16진수 표시(`FFFFFFFF`)를 오갈 수 있는 컨텍스트 메뉴가 있는데, Python으로 직접 계산하다 보면 이 변환을 놓쳐서 부호가 다른 값으로 조건 분기 결과가 어긋나는 경우가 흔하다.
- Ghidra 디컴파일에서 `int`(부호 있음)와 `uint`(부호 없음) 타입이 섞여 있고, 같은 비트 패턴인데 조건문 결과가 다르게 나오는 코드.
- `IDIV`/`SAR` 뒤에 나오는 결과가 예상과 반대 부호로 나오는 상황.

## 가장 먼저 할 것
문제가 되는 값의 **비트 폭**(8/16/32/64)부터 정확히 파악한다. `al`이면 8비트, `ax`면 16비트, `eax`면 32비트, `rax`면 64비트다. 폭을 잘못 잡으면 변환 결과가 완전히 다르게 나온다.

## 단계별 절차
**1) 변환 함수 정의 (한 번만 작성해서 재사용)**
```python
def to_signed(x: int, bits: int) -> int:
    """부호 없는 값(또는 임의의 정수) x를 bits비트 2의 보수 signed 값으로 해석"""
    mask = (1 << bits) - 1
    x &= mask                      # 우선 해당 비트 폭 안으로 자름
    if x >= (1 << (bits - 1)):     # 최상위 비트가 1이면 음수
        x -= (1 << bits)
    return x


def to_unsigned(x: int, bits: int) -> int:
    """부호 있는 값 x를 bits비트 unsigned 표현(0 이상 값)으로 변환"""
    return x & ((1 << bits) - 1)
```

**2) 폭별 헬퍼(선택 사항, 가독성용)**
```python
def s8(x):  return to_signed(x, 8)
def s16(x): return to_signed(x, 16)
def s32(x): return to_signed(x, 32)
def s64(x): return to_signed(x, 64)

def u8(x):  return to_unsigned(x, 8)
def u16(x): return to_unsigned(x, 16)
def u32(x): return to_unsigned(x, 32)
def u64(x): return to_unsigned(x, 64)
```

**3) 실제 값에 적용**
```python
>>> to_signed(0xFFFFFFFF, 32)
-1
>>> to_signed(0x80000000, 32)
-2147483648
>>> to_signed(0x7FFFFFFF, 32)
2147483647
>>> to_unsigned(-1, 32)
4294967295
>>> to_unsigned(-1, 8)
255
```

**4) 부호 있는 나눗셈/곱셈 재현**
IDIV, IMUL은 부호를 유지한 채 계산한다. Python `//`는 음수에 대해 "0 방향 버림"이 아니라 "음의 무한대 방향 버림"이므로 그대로 쓰면 C의 결과와 달라질 수 있다.
```python
import math

def c_div(a: int, b: int) -> int:
    """C/IDIV 스타일 0-방향 버림 나눗셈"""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q

>>> c_div(-7, 2)
-3
>>> (-7) // 2      # Python 기본 연산자는 -4 (음의 무한대 방향)
-4
```

## 명령어/단축키
- x64dbg 레지스터 창에서 값 위 우클릭 → "Signed" 표시로 전환해 부호 있는 10진수를 바로 확인 가능
- IDA에서 `Alt+M`(구조체/타입 뷰) 대신, 변수 타입을 `int`↔`unsigned int`로 바꿔보며(`Y` 키) 디컴파일 결과 변화 관찰
- Python REPL에서 위 함수들을 파일(`convert.py`)로 저장해두고 `from convert import *`로 매번 재사용

## 출력 해석
- `to_signed` 결과가 음수인데 원래 알고리즘이 부호 없는 비교(`unsigned` 타입)를 쓰는 코드였다면, 애초에 부호 변환을 적용하면 안 되는 값이다 — 디컴파일된 변수의 선언 타입을 먼저 확인해야 한다.
- 8/16비트 값은 `movzx`(부호 확장 없이 0으로 채움)로 로드됐는지 `movsx`(부호 확장, MSB를 그대로 반복 채움)로 로드됐는지에 따라 상위 비트 해석이 달라진다. `movsx`로 로드된 값이라면 이미 CPU가 부호 확장을 마쳤으므로 `to_signed`를 다시 적용하면 이중 변환 오류가 난다.

## 흔한 실수
- 비트 폭을 항상 32로 고정해버려서 `al`/`ax` 같은 8/16비트 레지스터 값을 잘못 해석하는 것.
- `to_unsigned` 없이 음수를 그대로 `hex()`에 넣어 `-0x...` 같은 형태를 만들고, 이걸 다시 바이트로 변환할 때 `to_bytes()`가 `OverflowError`를 던지는 것 — 반드시 `to_unsigned`로 먼저 양수화하거나 `int.to_bytes(..., signed=True)`를 명시해야 한다.
- C 나눗셈과 Python `//` 연산자의 버림 방향 차이를 모르고 그대로 써서 음수 나눗셈 결과가 1 어긋나는 것.

## 막혔을 때 다음 체크
- 바이트를 정수로/정수를 바이트로 직접 다루는 법이 필요하면 → REV-0261 (struct pack/unpack, `int.to_bytes(signed=True)` 포함).
- 부호 있는 값을 32비트 안에서 계속 연산해야 하면 → REV-0264 (32비트 Overflow 재현)와 함께 사용.
- 두 보수 개념 자체(왜 이런 표현을 쓰는지)가 헷갈리면 → 이론 설명이 정리된 기본 개념 글을 먼저 본다.

## 미니 예제
Ghidra에서 다음과 같은 디컴파일 결과를 봤다고 하자.
```c
int check(int v) {
    return (v ^ 0x7F) - 100 < 0;
}
```
`v = 0xA3`(부호 없이 읽으면 163)일 때 이 조건이 참인지 파이썬으로 그대로 재현하면:
```python
def check(v_raw, bits=32):
    v = to_signed(v_raw, bits)
    result = to_signed((v ^ 0x7F) - 100, bits)
    return result < 0

print(check(0xA3))   # v를 부호 있는 int로 해석해서 그대로 대입
```
이처럼 원본 코드의 변수 타입(`int`)을 그대로 존중해 `to_signed`를 적용한 뒤 연산하면, 디버거에서 관찰한 값과 Python 계산 결과가 항상 일치한다.

## 관련 글
- REV-0258 — 리버싱용 Python 숫자 변환 치트시트
- REV-0261 — Python struct pack unpack
- REV-0264 — Python 32비트 Overflow 재현
- ../binary-basics/rev-0024-twos-complement.md
- ../binary-basics/rev-0025-signed-unsigned.md

## 출처/검증
- 2의 보수 표현과 부호 확장 규칙은 Intel 64 and IA-32 Architectures Software Developer's Manual의 정수 표현 섹션과 모든 C 언어 표준의 정수 표현 정의를 따름(2026-09-08 확인). Python 임의 정밀도 정수 동작은 CPython 공식 문서 기준.
