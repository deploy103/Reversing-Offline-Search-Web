---
id: REV-0263
title: "Python Rotate 함수 템플릿"
slug: "rev-0263-python-rotate-template"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python rol ror 구현", "python rotate left right", "비트 회전 파이썬", "rol32 ror32 python", "python 비트 마스킹 회전"]
aliases: ["파이썬 rol ror 함수", "비트 로테이트 코드", "rotate left right python 템플릿"]
symptom_keywords: ["rol ror 어떻게 역산", "비트 회전 파이썬으로 구현", "회전 명령어 역산 코드"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Python에는 `<<`/`>>` 시프트만 있고 CPU의 ROL/ROR 같은 회전 연산은 없으므로, `((x << n) | (x >> (bits - n))) & mask` 형태로 비트 폭을 명시한 회전 함수를 직접 만들어야 하며, 왼쪽 회전과 오른쪽 회전은 서로의 역함수라는 점을 이용해 역산한다.

## 언제 검색해야 하나
- 디스어셈블리에 `rol`/`ror` 명령이 보이고, 그 결과를 검증 로직과 비교하는 코드를 역산해야 할 때
- 해시 함수(MD5, SHA류, 커스텀 체크섬)의 내부에서 회전 연산이 반복적으로 쓰이는 것을 볼 때
- Python으로 회전을 구현했는데 비트 폭 마스킹을 빼먹어서 값이 예상보다 훨씬 커지는 버그를 만났을 때

## 핵심 개념
비트 회전(rotate)은 시프트(shift)와 달리 **밀려나는 비트가 사라지지 않고 반대쪽 끝으로 다시 들어온다**. 예를 들어 8비트 값 `10110001`을 왼쪽으로 2비트 회전(ROL)하면 `11000110`이 된다 — 왼쪽으로 밀려난 최상위 2비트(`10`)가 사라지지 않고 오른쪽 끝에 다시 붙는다.

Python 정수는 고정 비트 폭이 없으므로 `x << n`만 하면 비트가 그냥 계속 왼쪽으로 늘어날 뿐 "반대쪽으로 넘어오는" 동작이 자동으로 일어나지 않는다. 따라서 회전을 구현하려면 **비트 폭(bits)을 명시하고, 두 방향의 시프트 결과를 OR로 합친 뒤 mask로 잘라내는** 방식을 써야 한다.

```
ROL(x, n, bits) = ((x << n) | (x >> (bits - n))) & mask
ROR(x, n, bits) = ((x >> n) | (x << (bits - n))) & mask
```
여기서 `mask = (1 << bits) - 1`이다.

가장 중요한 성질: **ROL의 역연산은 같은 크기만큼의 ROR이고, 그 반대도 성립한다.** 즉 코드에서 `rol eax, 5`를 봤다면, 그 결과를 원래 값으로 되돌리려면 파이썬에서 `ror(x, 5, 32)`를 적용하면 된다.

## 화면/코드에서 보이는 징후
```asm
mov     eax, dword ptr [rdi]
rol     eax, 7
xor     eax, ebx
```
디컴파일 결과에서는 `_rotl(x, 7)`, `_rotr(x, 7)` (MSVC intrinsic) 또는 `(x << 7) | (x >> 25)` 처럼 시프트 두 개가 OR로 묶인 형태로 나타나기도 한다 — 이 패턴을 보면 실제로는 32비트 회전을 컴파일러가 시프트 조합으로 풀어쓴 것임을 알아챌 수 있다(우변의 `25`는 `32 - 7`).

## 가장 먼저 할 것
회전 대상 레지스터의 **비트 폭**(`al`=8, `ax`=16, `eax`=32, `rax`=64)과 **회전량(n)**, **방향(ROL/ROR)**을 정확히 확인한다. 방향과 비트 폭이 틀리면 역산 결과가 완전히 다른 값이 된다.

## 단계별 절차
**1) 범용 회전 함수 정의**
```python
def rol(x: int, n: int, bits: int = 32) -> int:
    """x를 bits 비트 폭에서 왼쪽으로 n비트 회전"""
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x << n) | (x >> (bits - n))) & mask


def ror(x: int, n: int, bits: int = 32) -> int:
    """x를 bits 비트 폭에서 오른쪽으로 n비트 회전"""
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x >> n) | (x << (bits - n))) & mask
```
`n %= bits`를 넣어두면 `n`이 비트 폭보다 크거나 0일 때(예: `n=32, bits=32`)도 `x >> (bits - n)`이 `x >> 0`이 되어 자기 자신과 OR되는 사고를 방지할 수 있다.

**2) 동작 확인**
```python
>>> hex(rol(0xB1, 2, 8))
'0xc6'          # 10110001 -> 11000110
>>> ror(rol(0xB1, 2, 8), 2, 8) == 0xB1
True            # ROL 다음 같은 양만큼 ROR하면 원래 값으로 복귀
```

**3) 어셈블리의 rol/ror를 그대로 역산**
`rol eax, 7` 다음 그 값을 정답과 비교하는 코드를 만났다면, 정답을 반대 방향(ROR)으로 같은 양만큼 돌리면 원본 입력이 나온다.
```python
expected = 0xC3A5F001
original = ror(expected, 7, 32)
print(hex(original))
```

**4) 여러 바이트에 걸쳐 반복 적용 (해시류 패턴)**
```python
data = [0x11, 0x22, 0x33, 0x44]
rotated = [rol(b, 3, 8) for b in data]
restored = [ror(b, 3, 8) for b in rotated]
assert restored == data
```

**5) 32비트 곱셈/덧셈과 함께 쓰이는 경우 (해시 함수 스타일)**
```python
def mix(x: int) -> int:
    x = (x * 0x9E3779B1) & 0xFFFFFFFF   # 32비트 마스킹 필수 (REV-0264 참고)
    x = rol(x, 13, 32)
    return x
```
곱셈/덧셈 뒤에 반드시 `& 0xFFFFFFFF`로 마스킹해야 회전 함수에 넘기는 `x`가 올바른 32비트 범위 안에 있게 된다.

## 명령어/단축키
- IDA: `rol`/`ror` 명령 위에서 `?`(계산기) 또는 직접 오퍼랜드 값을 확인. MSVC 컴파일 결과에서는 `_rotl`/`_rotr`/`_rotl64`/`_rotr64` 함수 호출로 보일 수 있음
- x64dbg: 레지스터 값 변경 전/후를 Watch로 비교하며 회전량(즉시값 오퍼랜드)을 그대로 기록
- Python: 위 `rol`/`ror` 함수를 별도 파일(`rotate.py`)로 저장해 재사용

## 출력 해석
- `rol`로 암호화된 값을 역산할 때 방향을 반대로(즉 `rol`을 다시 `rol`로) 적용하면 전혀 다른 값이 나온다 — 반드시 반대 방향 함수를 써야 한다.
- 결과가 예상 범위를 벗어난 큰 수로 나온다면 `bits` 인자를 실제 레지스터 폭과 다르게 넣은 것이다. `eax`인데 `bits=64`로 착각하는 실수가 흔하다.

## 흔한 실수
- Python `x << n`만 쓰고 반대편에서 넘어오는 비트(`x >> (bits - n)`)를 OR로 합치지 않아서, 사실상 회전이 아니라 그냥 시프트가 되어버리는 것.
- 회전 후 `& mask`를 빼먹어서 비트 폭을 초과한 값이 그대로 다음 연산에 전달되는 것 — Python 정수가 무한히 커질 수 있다는 특성 때문에 조용히 틀린 값으로 계속 진행되어 디버깅이 어려워진다.
- `n`이 음수이거나 `bits`보다 큰 경우를 처리하지 않아서 `x >> (bits - n)`에서 음수 시프트 오류(`ValueError: negative shift count`)가 나는 것 — `n %= bits`로 항상 정규화해야 한다.
- ROL과 ROR을 반대로 구현해놓고 역산 방향도 반대로 적용해서, 두 번 잘못 계산했는데 우연히 얼추 맞는 것처럼 보이는(사실은 완전히 틀린) 값을 만드는 것 — 항상 `rol(ror(x, n, bits), n, bits) == x` 같은 자체 검증 코드를 먼저 돌려본다.

## 막혔을 때 다음 체크
- 회전 앞뒤로 XOR이 섞여 있으면 → REV-0262 (XOR 역산 템플릿)와 순서를 정확히 맞춰(마지막에 적용된 연산부터 거꾸로) 함께 역산.
- 곱셈/덧셈까지 섞인 해시 패턴이면 → REV-0264 (32비트 Overflow 재현)에서 마스킹 규칙을 반드시 함께 적용.
- 어셈블리에서 ROL/ROR 명령 자체의 오퍼랜드 해석이 헷갈리면 → 관련 알고리즘 패턴 글에서 상세 예제 확인.

## 미니 예제
`check(x) = rol(x, 5, 32) ^ 0xCAFEBABE`가 `0x9F3C21A0`과 같아야 통과하는 검증 함수를 역산해보자.
```python
def rol(x, n, bits=32):
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x << n) | (x >> (bits - n))) & mask

def ror(x, n, bits=32):
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x >> n) | (x << (bits - n))) & mask

target = 0x9F3C21A0
after_xor_removed = target ^ 0xCAFEBABE   # XOR은 자기 역원이므로 그대로 다시 XOR
original = ror(after_xor_removed, 5, 32)  # rol의 역은 같은 양만큼의 ror
print(hex(original))
```
이렇게 "마지막에 적용된 연산부터 역순으로" 하나씩 풀어나가는 것이 회전+XOR 조합 검증 로직을 역산하는 표준 절차다.

### 실전 예제 2 — 회전과 "덧셈"이 함께 섞인 검증 로직 역산하기
이번엔 XOR 대신 **덧셈**이 회전과 함께 쓰이는 경우를 다뤄본다. `check2(x) = rol(x, 11, 32) + 0xDEADBEEF (mod 2^32)`가 목표값 `0x12345678`이 되어야 통과하는 검증 함수라고 하자. 덧셈의 역연산은 뺄셈이라는 점만 빼면, 역산 절차는 앞의 예제와 동일하다.

```python
def rol(x: int, n: int, bits: int = 32) -> int:
    # x를 bits 비트 폭에서 왼쪽으로 n비트 회전
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x << n) | (x >> (bits - n))) & mask


def ror(x: int, n: int, bits: int = 32) -> int:
    # x를 bits 비트 폭에서 오른쪽으로 n비트 회전 (rol의 역연산)
    mask = (1 << bits) - 1
    x &= mask
    n %= bits
    return ((x >> n) | (x << (bits - n))) & mask


MASK32 = 0xFFFFFFFF


def check2(x: int) -> int:
    # 원본 검증 로직: 32비트 왼쪽 회전 11비트 후, 상수를 더하고 32비트로 마스킹
    return (rol(x, 11, 32) + 0xDEADBEEF) & MASK32


target = 0x12345678   # 검증을 통과하려면 check2(x)가 반드시 이 값이 되어야 한다

# 1) 마지막에 적용된 연산(덧셈)부터 역순으로 되돌린다 -> 덧셈의 역연산은 뺄셈
step1 = (target - 0xDEADBEEF) & MASK32    # 뺄셈 후 다시 32비트로 마스킹(음수 방지)
print("덧셈을 되돌린 중간값:", hex(step1))

# 2) 그 앞에 적용된 연산(rol 11비트)을 되돌린다 -> rol의 역연산은 같은 양만큼의 ror
original = ror(step1, 11, 32)
print("역산으로 복구한 원본 x:", hex(original))   # 0xf12670d2

# 3) 검증: 복구한 x를 다시 정방향(check2)으로 계산해서 target과 정확히 같은지 확인
recomputed = check2(original)
print("정방향으로 재계산한 값:", hex(recomputed))   # 0x12345678
assert recomputed == target, "역산이 잘못됐다면 여기서 AssertionError가 발생한다"
print("역산 성공: 정방향 재계산 값이 target과 정확히 일치함")
```
회전 앞뒤에 XOR가 아니라 덧셈이 오더라도 원칙은 똑같다 — **마지막에 적용된 연산의 역연산을 먼저 적용하고, 그 앞의 연산을 순서대로 거슬러 올라가면** 된다. 여기서는 "덧셈 -> 뺄셈", "rol(11) -> ror(11)" 순으로 두 단계를 거꾸로 밟아 `0xf12670d2`라는 원본 값을 정확히 복구했고, 이 값을 다시 정방향으로 계산하면 정확히 `target`(`0x12345678`)이 나온다는 것으로 역산이 맞았음을 검증했다.

## 관련 글
- REV-0262 — Python XOR 역산 템플릿
- REV-0264 — Python 32비트 Overflow 재현
- REV-0258 — 리버싱용 Python 숫자 변환 치트시트
- ../algorithms/rev-0201-rotate-transform.md

## 출처/검증
- ROL/ROR 명령의 정의와 비트 이동 방식은 Intel 64 and IA-32 Architectures Software Developer's Manual의 ROL/ROR 명령 설명 기준(2026-09-08 확인). Python 비트 연산자(`<<`, `>>`, `|`, `&`) 동작은 Python 공식 언어 레퍼런스 기준.
