---
id: REV-0207
title: "FNV-1과 FNV-1a 해시 패턴"
slug: "rev-0207-fnv1-fnv1a"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["FNV", "FNV-1", "FNV-1a", "해시 루프 구조", "곱셈 최적화", "shift-add 곱셈"]
aliases: ["fnv 구조", "곱셈이 shift add로 바뀜", "fnv 64비트", "fnv 커스텀 변형"]
symptom_keywords: ["xor랑 곱셈이 번갈아 나옴", "imul이 안 보이는데 곱셈같음", "hash 함수 이름을 모르겠음", "64비트 해시 상수가 이상함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
FNV(Fowler–Noll–Vo) 해시는 "**초기화 → (XOR, 곱셈)을 정해진 순서로 반복 → 결과 반환**"이라는 매우 단순한 루프 구조를 가지며, 이 구조 자체(비트 폭 무관, 상수를 몰라도 알아볼 수 있는 "모양")를 인식하는 것이 핵심이다 — 특히 최적화된 바이너리에서는 `imul`이 아예 안 보이고 `shl`+`add` 조합으로 곱셈이 풀려 있는 경우가 많은데, 이 글은 그 변형까지 포함해서 FNV류를 알아보는 법을 다룬다. 특정 상수(`16777619`)만으로 빠르게 확정하는 방법은 `./rev-0208-fnv-16777619.md`에서 집중적으로 다룬다.

## 언제 검색해야 하나
- 루프 안에서 `xor`와 `imul`(또는 `imul` 없이 `shl`+`add` 조합)이 함께, 정해진 순서로 반복될 때
- FNV 특유의 초기값(`0x811C9DC5`, `0xCBF29CE484222325` 등)이나 곱셈 상수(`0x01000193`, `0x100000001B3`)가 보이지 않는데도 구조가 FNV와 똑같아서 "커스텀 변형 해시"인지 의심될 때
- 32비트가 아니라 64비트 해시 계산 루프를 만났을 때
- `imul`이 안 보이는데 곱셈 같은 연산(해시 누적)이 있는 것 같다고 느껴질 때

## 핵심 개념
**FNV의 일반 구조 (비트 폭과 무관)**
```
hash = offset_basis
for each byte b in data:
    (FNV-1)  hash = (hash * prime) ^ b
    (FNV-1a) hash = (hash ^ b) * prime
return hash
```
이 구조에서 특징적인 것은 "**한 바이트당 정확히 곱셈 한 번, XOR 한 번**"이 반복된다는 점이다. 다른 다항식 해시(예: `hash = hash*31 + b`처럼 덧셈을 쓰는 djb2/Java String.hashCode 계열)와 구분되는 지점이 바로 이 XOR의 존재다.

**비트 폭별 상수(참고용 — REV-0208에 32비트 상수는 더 자세히 있음)**

| 비트 폭 | offset basis | FNV prime |
|---|---|---|
| 32비트 | `0x811C9DC5` | `0x01000193` |
| 64비트 | `0xCBF29CE484222325` | `0x100000001B3` |

64비트 prime(`0x100000001B3`)은 41비트 정수라서 `imul r64, r64, imm32`로 즉시값을 바로 인코딩할 수 없는 경우가 있고, 그러면 컴파일러는 이 상수를 별도 레지스터에 `mov`로 올려둔 뒤 `imul reg, reg`(레지스터-레지스터 곱셈)로 처리한다. 즉시값이 명령어에 안 보인다고 곱셈이 아니라고 오판하지 않도록 주의.

**곱셈이 imul 없이 shift+add로 최적화되는 경우 (매우 중요한 인식 포인트)**

32비트 FNV prime `16777619`를 이진수로 분해하면:
```
16777619 = 16777216 + 403
         = 2^24 + 256 + 128 + 16 + 2 + 1
         = 2^24 + 2^8 + 2^7 + 2^4 + 2^1 + 2^0
```
컴파일러(특히 크기/속도 최적화가 강한 빌드)는 `imul` 대신 이 비트 분해를 이용해서 시프트와 덧셈의 조합으로 곱셈을 대체하기도 한다:
```c
hash = (hash << 24) + (hash << 8) + (hash << 7) + (hash << 4) + (hash << 1) + hash;
```
이 형태는 겉보기엔 곱셈이 전혀 안 보이지만, `hash`를 여러 번 다른 크기로 시프트한 뒤 전부 더하는 패턴이 보이면 "곱셈이 shift-add로 풀린 것"임을 의심하고, 각 시프트양을 모아서 `2^a + 2^b + ...` 형태로 재구성해보면 원래 곱셈 상수를 역으로 계산할 수 있다.
```python
shifts = [24, 8, 7, 4, 1, 0]   # 코드에서 관찰한 시프트 양들(자기 자신, shift 0 포함)
constant = sum(1 << s for s in shifts)
print(constant)   # 16777619 -> FNV prime 확정
```

## 화면/코드에서 보이는 징후
**표준 imul 형태 (REV-0208과 동일, 여기서는 구조 확인용으로 재수록):**
```c
h ^= (unsigned char)s[i];
h *= 16777619;      // FNV-1a
```

**64비트 레지스터-레지스터 곱셈:**
```asm
movabs  rdx, 100000001B3h
loop1:
movzx   eax, byte ptr [rdi+rcx]
xor     rax, [hash]
mov     [hash], rax
mov     rax, [hash]
imul    rax, rdx        ; 즉시값이 아니라 레지스터로 곱셈
mov     [hash], rax
```

**shift-add로 풀린 32비트 곱셈:**
```asm
mov     eax, [hash]
mov     ecx, eax
shl     ecx, 24
mov     edx, eax
shl     edx, 8
add     ecx, edx
mov     edx, eax
shl     edx, 7
add     ecx, edx
mov     edx, eax
shl     edx, 4
add     ecx, edx
add     eax, eax        ; << 1
add     ecx, eax
add     ecx, [hash]     ; << 0 (자기 자신)
mov     [hash], ecx
```
이 뭉텅이 전체가 `hash *= 16777619` 한 줄과 완전히 동일하다.

**"FNV 비슷한데 상수가 다른" 커스텀 변형:**
```c
h ^= s[i];
h *= 0x1000197;   // FNV prime(0x1000193)과 한 글자 다름 -> 표준이 아니라 변형
```
구조(XOR 후 곱셈)는 FNV-1a와 동일하지만 상수가 다르면, 이건 표준 FNV가 아니라 "FNV에서 영감을 받은 커스텀 해시"다. 이 경우 알고리즘 이름에 의존하지 말고, 관찰한 실제 상수(초기값과 곱셈값)를 그대로 파이썬에 옮겨서 일반화된 함수로 재현하면 된다.

## 가장 먼저 할 것
루프 안에서 "바이트당 XOR 1회 + 곱셈 1회"라는 뼈대가 보이는지 확인한다. 곱셈이 `imul`로 안 보이면 시프트+덧셈 뭉텅이가 하나의 곱셈으로 뭉쳐질 수 있는지(시프트양들의 `2^n` 합이 그럴듯한 상수가 되는지) 계산해본다.

## 단계별 절차
**1) XOR/곱셈 순서로 FNV-1 vs FNV-1a 판별** (REV-0208 3단계와 동일한 방법)

**2) 곱셈 상수 확정** — `imul` 즉시값을 직접 읽거나, shift-add 뭉텅이라면 시프트양을 모아 `2^n`의 합으로 재구성

**3) 일반화된 파이썬 함수로 재현 (표준이든 커스텀 변형이든 동일하게 적용 가능)**
```python
def generic_fnv(data: bytes, offset_basis: int, prime: int, bits: int = 32, variant: str = "1a") -> int:
    mask = (1 << bits) - 1
    h = offset_basis
    for b in data:
        if variant == "1a":
            h = (h ^ b) & mask
            h = (h * prime) & mask
        else:  # "1"
            h = (h * prime) & mask
            h = (h ^ b) & mask
    return h

# 표준 32비트 FNV-1a
print(hex(generic_fnv(b"hello", 0x811C9DC5, 0x01000193, 32, "1a")))

# 표준 64비트 FNV-1a
print(hex(generic_fnv(b"hello", 0xCBF29CE484222325, 0x100000001B3, 64, "1a")))

# 관찰한 상수가 다른 커스텀 변형(예시)
print(hex(generic_fnv(b"hello", 0x811C9DC5, 0x01000197, 32, "1a")))
```

**4) 목표 해시값과 대조** — 바이너리에서 뽑은 비교 상수와 파이썬 계산 결과가 일치하는지 확인. 안 맞으면 variant("1" vs "1a")를 바꿔보거나 bits(32 vs 64)를 재확인.

## 명령어/단축키
- IDA: 여러 개의 `shl`+`add`가 같은 원본 값(`eax` 등)에서 파생되는지 확인할 때는 `\`(레지스터 하이라이트) 또는 클릭으로 같은 레지스터 사용처를 색칠해서 눈으로 추적
- Python: 위 `generic_fnv()` 헬퍼를 상수만 바꿔가며 재사용

## 출력 해석
- shift 값들을 `2^n`으로 합산한 결과가 정확히 `16777619`나 `1099511628211`(64비트 prime의 10진수)이면 표준 FNV 확정.
- 합산 결과가 이 값들과 다르면 커스텀 변형이므로, 그 값 그대로를 prime으로 써서 `generic_fnv()`에 대입하면 된다 — 이름이 FNV가 아니어도 구조만 같으면 똑같이 다룰 수 있다.

## 흔한 실수
- `imul`이 안 보인다고 곱셈이 없다고 단정하고 "이건 FNV가 아니다"라고 넘어가는 것 — shift-add 최적화 가능성을 항상 의심해야 한다.
- 64비트 FNV인데 32비트 마스크(`& 0xFFFFFFFF`)를 그대로 써버려서 결과가 안 맞는 것 — bits 파라미터를 반드시 데이터 폭에 맞게 지정.
- "FNV와 구조가 비슷하니 상수도 표준일 것"이라고 가정하고 표준 상수만 시도하다가, 실제로는 커스텀 변형이라 계속 값이 안 맞아서 시간을 낭비하는 것 — 코드에서 직접 관찰한 상수를 우선 신뢰해야 한다.

## 막혔을 때 다음 체크
- 특정 상수(`16777619`, `0x811C9DC5`)로 바로 FNV를 확정하고 싶다면 → `./rev-0208-fnv-16777619.md`.
- XOR이 없고 덧셈만 반복된다면(곱셈+덧셈, XOR 없음) → 이건 FNV가 아니라 djb2/다항식 해시(REV-0202, REV-0205 참고).
- 256개짜리 테이블을 참조하는 구조라면 → REV-0209(CRC, FNV와 달리 룩업 테이블 기반).
- 해시값 자체를 브루트포스해야 하는 상황이라면 → 입력 공간과 charset을 좁혀 파이썬으로 전수조사.

## 미니 예제
**예제 1 — 표준 32비트 FNV-1a (imul 형태)**
```c
unsigned int h = 0x811C9DC5;
for (i = 0; i < len; i++) { h ^= s[i]; h *= 16777619; }
```
`generic_fnv(data, 0x811C9DC5, 16777619, 32, "1a")`로 즉시 재현.

**예제 2 — shift-add로 풀린 곱셈 역추적**
코드에서 `<<24`, `<<8`, `<<7`, `<<4`, `<<1`, 그리고 시프트 없는 자기 자신(`<<0`)이 전부 더해지는 것을 확인했다면:
```python
shifts = [24, 8, 7, 4, 1, 0]
prime = sum(1 << s for s in shifts)
print(prime)  # 16777619
```
표준 FNV prime과 일치하므로 표준 FNV-1a로 확정.

**예제 3 — 64비트 FNV, 레지스터 곱셈**
```asm
movabs rdx, 100000001B3h
imul   rax, rdx
```
`generic_fnv(data, 0xCBF29CE484222325, 0x100000001B3, 64, "1a")`.

**예제 4 — 상수가 살짝 다른 커스텀 변형**
```c
h ^= s[i];
h *= 0x01000199;   // 표준 0x01000193과 마지막 바이트만 다름
```
구조는 FNV-1a와 동일하므로, 이 관찰된 상수를 그대로 prime에 넣어서 재현하면 된다 — "이게 진짜 FNV냐 아니냐"를 고민할 필요 없이 그대로 계산하면 끝.

**예제 5 — 처음부터 끝까지 실행되는 전체 스크립트 (32비트/64비트/shift-add 변형까지 한 번에)**

`generic_fnv()` 하나로 표준 32비트, 표준 64비트, 그리고 "shift-add로 풀려서 곱셈 상수가 안 보이는 경우"까지 전부 처리하는 실전 스크립트다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0207 실전 스크립트: FNV-1/1a를 32비트/64비트, 표준/커스텀 변형까지 한 함수로 전부 재현한다.

def generic_fnv(data: bytes, offset_basis: int, prime: int, bits: int = 32, variant: str = "1a") -> int:
    mask = (1 << bits) - 1          # bits폭에 맞는 마스크(오버플로를 그대로 재현하기 위함)
    h = offset_basis                # 초기값(offset basis)에서 시작
    for b in data:
        if variant == "1a":
            h = (h ^ b) & mask      # FNV-1a: XOR을 먼저 한다
            h = (h * prime) & mask  # 그다음 곱셈을 한다
        else:
            h = (h * prime) & mask  # FNV-1: 곱셈을 먼저 한다
            h = (h ^ b) & mask      # 그다음 XOR을 한다
    return h

# 1) 표준 32비트 FNV-1a
result_1a_32 = generic_fnv(b"hello", 0x811C9DC5, 0x01000193, 32, "1a")
print("FNV-1a 32bit hello:", hex(result_1a_32))
# 실행 결과: FNV-1a 32bit hello: 0x4f9f2cab

# 2) 표준 32비트 FNV-1 (XOR과 곱셈의 순서만 반대)
result_1_32 = generic_fnv(b"hello", 0x811C9DC5, 0x01000193, 32, "1")
print("FNV-1 32bit hello:", hex(result_1_32))
# 실행 결과: FNV-1 32bit hello: 0xb6fa7167

# 3) 표준 64비트 FNV-1a (bits=64로 지정해야 마스크가 올바르게 적용된다)
result_1a_64 = generic_fnv(b"hello", 0xCBF29CE484222325, 0x100000001B3, 64, "1a")
print("FNV-1a 64bit hello:", hex(result_1a_64))
# 실행 결과: FNV-1a 64bit hello: 0xa430d84680aabd0b

# 4) 코드에서 shl 24 / shl 8 / shl 7 / shl 4 / shl 1 / (시프트 없는 자기 자신)이 전부 add로
#    더해지는 것을 직접 관찰했다고 가정하고, 그 시프트양들로 원래 곱셈 상수를 역으로 재구성한다.
shifts = [24, 8, 7, 4, 1, 0]
reconstructed_prime = sum(1 << s for s in shifts)
print("shift-add로 복원한 곱셈 상수:", reconstructed_prime)
# 실행 결과: shift-add로 복원한 곱셈 상수: 16777619  -> 표준 FNV prime과 정확히 일치
```

## 관련 글
- ./rev-0208-fnv-16777619.md — 16777619 상수가 보일 때 FNV 의심하기
- REV-0202 — Shift SHL SHR SAR 기반 변환
- REV-0205 — Modulo와 오버플로를 이용한 검증
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- ../assembly/rev-0057-xor.md — XOR 명령어
- ../assembly/rev-0061-shl-sal.md — SHL/SAL 명령어

## 출처/검증
- FNV 해시 공식 스펙 및 32/64비트 상수: Fowler/Noll/Vo, "The FNV Non-Cryptographic Hash Algorithm"(IETF Draft, isthe.com/chongo/tech/comp/fnv/ 기준 공개 자료).
- 정수 상수 곱셈을 shift/add 시퀀스로 대체하는 컴파일러 최적화(strength reduction)는 GCC/LLVM 최적화 문서 및 Hacker's Delight(Warren)의 표준 기법 기준(2026-09-08 확인).
