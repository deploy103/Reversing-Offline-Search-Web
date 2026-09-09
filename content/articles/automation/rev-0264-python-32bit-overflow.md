---
id: REV-0264
title: "Python 32비트 Overflow 재현"
slug: "rev-0264-python-32bit-overflow"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python 32비트 오버플로우", "python 정수 마스킹", "0xFFFFFFFF 마스크", "python C 정수 재현", "wraparound python"]
aliases: ["파이썬 오버플로우 재현", "32비트 정수 랩어라운드 파이썬", "python int overflow simulate"]
symptom_keywords: ["파이썬 계산값이 C보다 훨씬 큼", "eax 값 파이썬으로 안 맞음", "곱셈 결과가 이상하게 큼"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Python `int`는 크기 제한 없이 커지지만 C의 `int`/`uint32_t`는 32비트를 넘으면 값이 잘려나가므로(wraparound), C와 똑같은 결과를 얻으려면 **모든 산술 연산 직후마다** `& 0xFFFFFFFF`로 마스킹해야 한다.

## 언제 검색해야 하나
- 바이너리의 해시/체크섬 계산 루프를 Python으로 그대로 옮겨 적었는데 결과가 디버거에서 본 값과 전혀 다르게 나올 때
- `EAX`가 곱셈이나 덧셈을 반복하는 루프를 도는데, Python으로 같은 루프를 돌리면 값이 눈덩이처럼 커져서 자릿수 자체가 다를 때
- CRC, FNV 해시, 커스텀 시리얼 검증 알고리즘처럼 32비트 레지스터 연산이 핵심인 알고리즘을 재현할 때

## 핵심 개념
C에서 `int`, `unsigned int`, `uint32_t` 같은 32비트 타입은 값이 `0`~`0xFFFFFFFF`(또는 부호 있는 범위) 사이에서만 존재할 수 있다. 이 범위를 넘어서는 연산 결과는 상위 비트가 잘려나가고 하위 32비트만 남는다 — 이것이 "오버플로/wraparound"다. CPU도 `EAX` 같은 32비트 레지스터에 결과를 저장할 때 자동으로 하위 32비트만 남긴다(캐리/오버플로 플래그는 별도로 세팅될 뿐 레지스터 값 자체는 잘림).

Python의 `int`는 이런 제한이 전혀 없는 임의 정밀도 정수다. `2**32 * 2**32`를 계산해도 오류 없이 정확한 큰 수를 반환한다. 이것이 편리하기도 하지만, **C 코드를 그대로 옮겨 적을 때는 함정**이 된다 — Python은 "잘라내는" 동작을 저절로 해주지 않기 때문에, 명시적으로 마스킹하지 않으면 완전히 다른(훨씬 큰) 값이 계속 누적된다.

규칙은 단순하다. **곱셈, 덧셈, 뺄셈, 왼쪽 시프트 등 결과가 커질 수 있는 연산을 수행한 직후에는 항상 `& 0xFFFFFFFF`(32비트 기준)를 붙인다.**

## 화면/코드에서 보이는 징후
```c
uint32_t hash = 0x811C9DC5;
for (int i = 0; i < len; i++) {
    hash ^= data[i];
    hash *= 0x01000193;   // 곱하면 32비트를 넘을 수 있지만 uint32_t라 자동으로 잘림
}
```
이런 루프를 Python으로 그대로 옮기면서 `hash *= 0x01000193`만 적고 마스킹을 빼먹으면, 반복할수록 `hash`가 수백 자리 숫자로 불어나버려 최종값이 C와 전혀 다르게 나온다.

## 가장 먼저 할 것
원본 C/디스어셈블리 코드에서 다루는 변수의 **정확한 비트 폭**(`uint32_t`인지 `uint64_t`인지, `EAX`인지 `RAX`인지)을 확정한다. 32비트 레지스터에 결과를 쓰는 명령(`mov eax, ...`, `imul eax, ...`)은 상위 32비트를 자동으로 0으로 만든다는 x86-64 규칙도 함께 기억해둔다.

## 단계별 절차
**1) 틀린 예시로 문제를 먼저 확인**
```python
# 마스킹을 빼먹은 잘못된 버전
def fnv1a_wrong(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h *= 0x01000193
    return h

print(hex(fnv1a_wrong(b"hello")))
# 결과: 매우 큰 수 (32비트를 훌쩍 넘는 자릿수) — C의 uint32_t 결과와 다름
```

**2) 올바른 버전 — 매 연산 후 마스킹**
```python
MASK32 = 0xFFFFFFFF

def fnv1a_correct(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & MASK32   # 곱셈 직후 즉시 마스킹
    return h

print(hex(fnv1a_correct(b"hello")))
# 결과: 0xa430d84 같은 정상적인 32비트 값
```

**3) 재사용 가능한 헬퍼 함수로 정리**
```python
MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF

def add32(a: int, b: int) -> int: return (a + b) & MASK32
def sub32(a: int, b: int) -> int: return (a - b) & MASK32
def mul32(a: int, b: int) -> int: return (a * b) & MASK32
def shl32(a: int, n: int) -> int: return (a << n) & MASK32
# 오른쪽 시프트는 자연히 32비트 안에 들어오므로 별도 마스킹이 필수는 아니지만
# 습관적으로 붙여도 무해하다.
def shr32(a: int, n: int) -> int: return (a & MASK32) >> n
```
이 함수들을 쓰면 C 코드의 각 줄을 거의 1:1로 옮길 수 있다.
```c
// C
hash = hash * 33 + c;
```
```python
# Python
hash = add32(mul32(hash, 33), c)
```

**4) 부호 있는 결과가 필요할 때 (REV-0259와 연계)**
```python
def to_signed32(x: int) -> int:
    x &= MASK32
    return x - (1 << 32) if x >= (1 << 31) else x

result = mul32(0x7FFFFFFF, 3)
print(hex(result), to_signed32(result))
```

## 명령어/단축키
- 디버거(x64dbg/IDA)에서 `EAX`/`EDX` 등 32비트 레지스터의 연산 직후 값을 하나하나 캡처해 Python 결과와 대조하며 어느 단계에서 마스킹이 빠졌는지 이분 탐색하듯 좁혀나간다.
- Python REPL에서 `hex(value)`의 자릿수가 8자리(`0x` 제외)를 넘어가면 곧바로 마스킹 누락을 의심한다.

## 출력 해석
- Python 계산값의 16진수 표현이 8자리(32비트)를 초과하면 100% 마스킹 누락이다. 즉시 해당 연산 뒤에 `& 0xFFFFFFFF`를 추가한다.
- 자릿수는 맞는데 값 자체가 다르다면 마스킹 위치가 아니라 연산 순서나 초기값, 상수를 잘못 옮겨 적었을 가능성이 크다 — C 코드와 한 줄씩 다시 대조한다.
- 64비트 레지스터(`RAX` 등)를 다루는 코드라면 마스크를 `0xFFFFFFFFFFFFFFFF`로 바꿔야 하며, 32비트 마스크를 그대로 쓰면 상위 32비트가 잘못 잘려나간다.

## 흔한 실수
- 루프 안의 여러 연산 중 곱셈에만 마스킹을 걸고 덧셈/시프트에는 빼먹는 것 — 모든 연산 각각이 잠재적 오버플로 지점이므로 하나도 빠짐없이 확인해야 한다.
- 최종 반환값에만 마스킹을 걸고 루프 중간값은 그대로 두는 것 — 중간값이 이미 틀리면 다음 반복의 입력도 틀려지므로 누적 오차가 발생한다. 반드시 **매 스텝마다** 마스킹해야 한다.
- 32비트 코드인데 64비트 마스크(`0xFFFFFFFFFFFFFFFF`)를 쓰거나 그 반대로 착각하는 것.
- `x86` 32비트 레지스터 연산 시 자동으로 상위 비트가 0이 되는 x86-64 규칙(`mov eax, ...`는 `rax`의 상위 32비트를 0으로 클리어)과, `AL`/`AX`처럼 8/16비트 서브 레지스터에 쓸 때는 상위 비트가 보존되는 규칙을 혼동하는 것 — 이 경우는 마스크 크기(`0xFF`, `0xFFFF`)를 정확히 그 레지스터 폭에 맞춰야 한다.

## 마스킹을 잊으면 벌어지는 일 — 대조 예제
아래는 "왜 잊으면 틀리는지"를 보여주는 대조 예제다.
```python
MASK32 = 0xFFFFFFFF

def bad_checksum(data: bytes) -> int:
    s = 0
    for b in data:
        s = s * 31 + b          # 마스킹 없음 -> WRONG
    return s

def good_checksum(data: bytes) -> int:
    s = 0
    for b in data:
        s = (s * 31 + b) & MASK32   # 매 반복마다 마스킹 -> C와 동일
    return s

data = b"A" * 20
print(hex(bad_checksum(data)))    # 자릿수가 8자리를 훨씬 초과하는 거대한 수
print(hex(good_checksum(data)))   # 정확히 8자리 이하의 32비트 값, C의 uint32_t 결과와 일치
```
`bad_checksum`은 Python에서는 "에러 없이 실행되어 그럴듯한 숫자"를 내놓기 때문에, 검증 로직과 비교할 때까지 문제를 못 느끼는 경우가 많다는 점이 특히 위험하다.

## 실전 예시: 여러 연산이 섞인 시리얼 체크섬 역재현
실전 CTF의 검증 로직은 곱셈이나 덧셈 하나만 반복하는 것이 아니라 **시프트, XOR, 곱셈을 한 반복문 안에서 여러 번 섞어서** 쓰는 경우가 많다. 아래 C 코드는 그런 상황을 흉내 낸, 앞의 djb2 예제보다 한 단계 더 복잡한 예시다.

```c
// 원본 C: 왼쪽 4비트 시프트 + 오른쪽에서 넘친 4비트를 다시 XOR로 섞은 뒤 매직 상수를 곱하는 32비트 해시
uint32_t compute(const char *s, int len) {
    uint32_t h = 0;
    for (int i = 0; i < len; i++) {
        h = (h << 4) ^ (h >> 28) ^ (uint32_t)(unsigned char)s[i];
        h = h * 0x9E3779B9u;   // 황금비 기반 홀수 매직 상수, 32비트 자동 랩어라운드
    }
    return h;
}
```

이 함수는 한 번 반복할 때마다 **연산이 다섯 개**(왼쪽 시프트, 오른쪽 시프트, XOR 두 번, 곱셈 한 번)나 이어져 있다. 이럴 때 "한 줄 전체를 계산한 다음 맨 끝에만 마스킹"하면 틀린다 — 특히 `h << 4`는 그 자체로 이미 32비트를 넘어설 수 있는 연산이므로, **그 시프트 결과만 따로 떼어서 즉시 마스킹**해야 다음 XOR에 넘어갈 값이 정확해진다.

```python
MASK32 = 0xFFFFFFFF

def compute(s: bytes) -> int:
    h = 0
    for c in s:
        # 1) 왼쪽 시프트는 32비트를 초과할 수 있으므로 시프트 직후 바로 마스킹한다
        left = (h << 4) & MASK32
        # 2) 오른쪽 시프트는 이미 32비트 범위 안에 들어오지만, 습관적으로 마스킹을 붙여도 무해하다
        right = (h >> 28) & MASK32
        # 3) XOR는 자릿수를 키우지 않는 연산이라 여기서는 추가 마스킹이 필요 없다
        h = left ^ right ^ c
        # 4) 곱셈은 32비트를 크게 초과할 수 있는 연산이므로 곱한 직후 다시 마스킹한다
        h = (h * 0x9E3779B9) & MASK32
    return h

# 예시 입력 "KEY01"에 대해 위 규칙대로 정확히 마스킹하며 계산한 값
print(hex(compute(b"KEY01")))   # 0x2fc4f1e1
```

이 코드를 실제로 실행하면 `0x2fc4f1e1`이 그대로 나온다(직접 CPython 3에서 재현 검증됨). 만약 3번째 줄(`h = left ^ right ^ c`)까지는 맞게 옮겼는데 4번째 줄의 곱셈 뒤에 마스킹을 빼먹으면, `h`가 반복될수록 눈덩이처럼 커져서 최종 자릿수 자체가 8자리(32비트)를 넘어가 버린다 — 이 자릿수 초과가 곧 "마스킹을 어디선가 빼먹었다"는 가장 확실한 신호라는 점은 앞서 "출력 해석"에서 다룬 규칙과 동일하다. 요컨대 규칙은 항상 같다: **연산이 몇 개가 이어지든, "커질 수 있는" 연산(덧셈/뺄셈/곱셈/왼쪽 시프트) 각각의 결과를 그 즉시 떼어서 마스킹**하면, 아무리 복잡하게 섞인 해시 함수도 C와 동일하게 재현할 수 있다.

## 막혔을 때 다음 체크
- 부호 있는 값으로 해석해야 하는 경우 → REV-0259 (Signed Unsigned 변환)와 함께 `to_signed32` 적용.
- 회전(ROL/ROR)까지 섞인 해시라면 → REV-0263 (Rotate 함수 템플릿)의 회전 함수와 마스킹을 함께 적용.
- 최종 결과를 바이트로 다시 묶어야 하면 → REV-0261 (struct pack/unpack)로 `<I` 포맷 사용.

## 미니 예제
간단한 커스텀 체크섬 검증을 재현해보자. C 코드가 다음과 같다고 하자.
```c
uint32_t calc(const char *s, int len) {
    uint32_t h = 5381;
    for (int i = 0; i < len; i++) {
        h = ((h << 5) + h) + s[i];   // h*33 + c (djb2 스타일)
    }
    return h;
}
```
Python으로 정확히 재현:
```python
MASK32 = 0xFFFFFFFF

def calc(s: bytes) -> int:
    h = 5381
    for c in s:
        h = (((h << 5) & MASK32) + h + c) & MASK32
    return h

print(hex(calc(b"flag_candidate")))
```
`(h << 5)`에 먼저 마스킹을 걸고, 그 다음 덧셈 결과 전체에도 다시 마스킹을 거는 이중 마스킹이 안전하다 — 시프트만으로도 32비트를 초과할 수 있기 때문이다.

## 관련 글
- REV-0259 — Python으로 Signed Unsigned 변환
- REV-0261 — Python struct pack unpack
- REV-0263 — Python Rotate 함수 템플릿
- REV-0258 — 리버싱용 Python 숫자 변환 치트시트

## 출처/검증
- 32비트 정수 오버플로/wraparound 동작은 C 표준(부호 없는 정수 연산은 모듈러 산술로 정의됨, ISO/IEC 9899)과 Intel SDM의 32비트 레지스터 쓰기 규칙 기준(2026-09-08 확인). Python `int`의 임의 정밀도 특성은 Python 공식 문서 기준.
