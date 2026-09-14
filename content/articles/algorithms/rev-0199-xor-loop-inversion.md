---
id: REV-0199
title: "XOR 반복 변환 역산"
slug: "rev-0199-xor-loop-inversion"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["xor 루프", "xor 역산", "단일 바이트 xor", "반복 키 xor", "rolling xor", "xor 암호"]
aliases: ["xor 반복문", "xor 어떻게 품", "xor 복호화", "xor 역연산"]
symptom_keywords: ["xor 반복문", "xor로 뭘 하는지 모르겠음", "키가 반복되는 것 같음", "암호화된 문자열 xor"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`for` 루프 안에서 `xor al, key`가 반복되고 그 결과를 정답 배열과 비교하는 코드를 만나면, **XOR는 자기 자신의 역함수**이므로(`a ^ b = c`이면 `c ^ b = a`) 같은 키로 정답 배열을 다시 XOR하기만 하면 원래 입력(flag)이 그대로 나온다.

## 언제 검색해야 하나
- 루프 안에 `xor al, imm8` 또는 `xor al, byte ptr [key+ecx]`처럼 즉시값 또는 배열 원소로 XOR하는 코드가 있을 때
- 디컴파일 결과에 `input[i] ^ key`, `input[i] ^ key[i % keylen]` 형태의 수식이 보일 때
- "암호화된 것 같은데 복호화 함수가 안 보인다"는 상황 — 애초에 XOR은 암호화/복호화 함수가 동일하므로 별도 복호화 루틴 없이 같은 루프가 재사용되는 경우가 많다
- 전형적인 검색 질의 예시: `xor 반복문`

## 핵심 개념
XOR(배타적 논리합)의 수학적 성질 중 리버싱에서 가장 중요한 것은 **자기 역원(self-inverse)** 이라는 점이다.

```
a ^ b = c   이면   c ^ b = a   (항상 성립)
```

즉 "입력을 키로 XOR해서 정답과 같아야 한다"는 검증 로직이 있다면, **정답을 같은 키로 다시 XOR하면 입력(=flag)이 그대로 복원**된다. 덧셈/뺄셈이나 회전과 달리 방향을 뒤집을 필요조차 없다 — 연산 자체가 자기 자신의 역연산이다. 이 성질 때문에 XOR 변환은 리버싱 관점에서 "가장 빠르게 역산 가능한 패턴"이다.

키의 형태에 따라 세 가지 변형이 흔하다.

1. **단일 바이트 키(고정 XOR)**: 모든 바이트에 같은 값(예: `0x13`)을 XOR. 가장 단순.
2. **반복 키(rolling/repeating key XOR)**: `key[i % keylen]`처럼 짧은 키 배열을 순환시키며 XOR. 고전적인 "Vigenère 스타일" XOR.
3. **체인 XOR(누적형)**: 이전 평문 바이트 또는 이전 암호문 바이트를 다음 바이트의 키로 사용. CBC와 비슷한 발상으로, 역산 시 앞에서부터 순서대로 풀어야 한다(뒤 바이트를 풀려면 앞 바이트 값이 필요).

## 화면/코드에서 보이는 징후
**단일 바이트 키:**
```asm
loop1:
movzx   eax, byte ptr [rdi+rcx]
xor     al, 0x5A
cmp     al, byte ptr [rsi+rcx]
jne     fail
inc     ecx
cmp     ecx, len
jl      loop1
```
디컴파일: `if ((input[i] ^ 0x5A) != expected[i]) return 0;`

**반복 키:**
```c
for ( i = 0; i < len; ++i )
{
    if ( (input[i] ^ key[i % 4]) != expected[i] )
        return 0;
}
```

**체인 XOR:**
```c
prev = 0;
for ( i = 0; i < len; ++i )
{
    enc = input[i] ^ prev;
    if ( enc != expected[i] )
        return 0;
    prev = input[i];   // 또는 prev = enc (구현에 따라 다름)
}
```
이 형태는 `prev`라는 변수가 루프 밖에서 초기화되고 매 반복 갱신되는 것이 특징이다.

## 가장 먼저 할 것
`xor` 명령의 오퍼랜드가 **즉시값(고정 키)**인지, **배열 인덱싱(반복 키)**인지, **이전 반복의 변수(체인)**인지부터 구분한다. 그다음 `expected` 배열과 키를 정적으로 덤프해서 파이썬으로 역산한다.

## 단계별 절차
**1) 키 종류 판별**

- `xor al, 0x5A`처럼 명령어에 상수가 박혀 있으면 → 단일 바이트 키.
- `xor al, byte ptr [rbx+rdx]`이고 `rdx`가 `rcx % keylen`으로 계산되면 → 반복 키. `keylen`은 보통 `and edx, 3`(4로 나눈 나머지, 즉 keylen=4) 같은 마스크 연산으로 드러난다.
- `xor`의 두 번째 피연산자가 직전 반복에서 저장해둔 변수라면 → 체인 XOR.

**2) 필요한 값 모두 덤프**

IDA Hex View 또는 x64dbg 메모리 덤프로 `expected`(및 있다면 `key`) 배열을 파이썬 bytes로 옮긴다.

**3) 케이스별 역산**

단일 바이트 키:
```python
expected = bytes.fromhex("2f0a1a4a1a5a4a1a")
KEY = 0x5A
flag = bytes(b ^ KEY for b in expected)
print(flag)
```

반복 키:
```python
from itertools import cycle

expected = bytes.fromhex("...")
key = bytes.fromhex("deadbeef")   # 4바이트 키
flag = bytes(e ^ k for e, k in zip(expected, cycle(key)))
print(flag)
```

체인 XOR (앞에서부터 순서대로 복원해야 함):
```python
expected = bytes.fromhex("...")
flag = bytearray(len(expected))
prev = 0
for i, e in enumerate(expected):
    flag[i] = e ^ prev
    prev = flag[i]   # 원본 로직이 prev = input[i]였던 경우
print(bytes(flag))
```

**4) 결과 검증**

역산해서 나온 바이트가 전부 출력 가능한 아스키(0x20~0x7E)인지 확인한다. 아니라면 키 방향이나 XOR 대상을 잘못 짚은 것이니 2단계로 돌아가 재확인한다.

## 명령어/단축키
- IDA: `xor` 명령 위에서 `H`로 헥스/십진 토글, 오퍼랜드가 메모리면 더블클릭해서 배열 시작 위치 확인
- x64dbg: `bp` 걸고 루프 한 바퀴 돌 때마다 `al`, `[rsi+rcx]` 값을 Watch 창에 등록해 관찰
- Python: `itertools.cycle`, `bytes.fromhex`, `bytes([...])`

## 출력 해석
- 역산 결과가 `flag{`, `CTF{`, `FLAG{` 같은 접두어로 시작하면 성공 가능성이 매우 높다.
- 일부만 정상 아스키이고 나머지가 깨진다면, 반복 키의 길이(`keylen`)를 잘못 추정했을 가능성이 크다 — `and`/`cmp` 명령으로 나오는 나머지 연산의 실제 모듈러스 값을 다시 확인한다.
- 전체가 다 깨진다면 XOR 앞에 다른 변환(ADD/ROL 등)이 섞여 있을 수 있다 — REV-0198로 돌아가 `xor` 앞뒤에 다른 연산이 있는지 재확인.

## 흔한 실수
- 반복 키의 방향(`key[i % keylen]`인지 `key[keylen - 1 - (i % keylen)]`처럼 역순인지)을 확인하지 않고 무조건 정방향으로 가정하는 것.
- 체인 XOR에서 `prev`가 "원본 평문"인지 "암호문(expected)"인지 헷갈리는 것 — 둘 중 어느 것을 이전 값으로 쓰는지에 따라 역산 코드가 완전히 달라지므로 디컴파일 코드를 한 줄씩 다시 확인해야 한다.
- 8비트가 아니라 32비트 단위로 XOR하는 경우(`xor eax, key_dword`)를 1바이트 XOR로 착각해서 하위 1바이트만 역산하고 나머지 3바이트를 놓치는 것.
- XOR 키가 `0x00`인 특수 케이스(사실상 변환 없음)를 눈치채지 못하고 계속 "뭔가 이상한 값"이라고 헤매는 것 — 키 상수를 눈으로 직접 다시 확인한다.

## 막혔을 때 다음 체크
- XOR 앞뒤로 ADD/SUB가 섞여 있다면 → REV-0200과 함께 순서대로 역산(마지막에 적용된 연산부터 거꾸로 풀어야 함).
- 키가 32비트 이상이고 곱셈까지 함께 있다면 → REV-0207/REV-0208(FNV) 패턴일 수 있음.
- XOR 후 값이 `0xFF`로 마스킹되는 이유가 궁금하면 → REV-0203(AND 0xFF 마스크).
- 이 XOR 변환이 애초에 순수 비교인지 궁금하면 → REV-0198로 돌아가 전체 루프 구조 재확인.

## 미니 예제
**예제 1 — 단일 바이트 키**
바이너리에서 `expected = 2F 0A 1A 4A 1A 5A 4A 1A`, `xor al, 0x5A`를 확인했다면:
```python
expected = bytes.fromhex("2f0a1a4a1a5a4a1a")
flag = bytes(b ^ 0x5A for b in expected)
print(flag)  # b'uP@\x10@\x00\x10@' 같은 값이 나오면 키 추정이 틀린 것 -> 재확인 필요한 예시
```
(실전에서는 아스키로 깔끔하게 나오는 키를 찾을 때까지 값을 재검증한다. 위 예시는 계산 과정을 보여주기 위한 것으로, 실제 문제에서는 `expected`와 키가 서로 맞아떨어지는 실제 바이트를 사용한다.)

**예제 2 — 4바이트 반복 키**
```python
from itertools import cycle
expected = bytes.fromhex("1d0b1c56424e0413050b164e")
key = b"CTF!"
flag = bytes(e ^ k for e, k in zip(expected, cycle(key)))
print(flag)  # 정확한 키를 알고 있다면 사람이 읽을 수 있는 문자열이 나옴
```

**예제 3 — asm에서 keylen 유추**
```asm
mov     eax, ecx
xor     edx, edx
mov     ebx, 4
div     ebx           ; eax = i/4, edx = i%4  (여기서 4가 keylen)
movzx   esi, byte ptr [key+edx]
xor     al, sil
```
`div ebx`(ebx=4)로 나머지를 구하는 부분이 곧 `key[i % 4]`에 해당하는 코드.

**예제 4 — Ghidra에서 32비트 단위 XOR**
```c
for (i = 0; i < 8; i += 4)
{
    v = *(uint*)(input + i) ^ 0xDEADBEEF;
    if (v != *(uint*)(expected + i)) return 0;
}
```
```python
import struct
expected = bytes.fromhex("...")
KEY = 0xDEADBEEF
out = b""
for i in range(0, len(expected), 4):
    v = struct.unpack_from("<I", expected, i)[0]
    out += struct.pack("<I", v ^ KEY)
print(out)
```

**예제 5 — 처음부터 끝까지 실행되는 전체 스크립트 (단일 바이트 키 + 반복 키, 두 케이스 모두 검증)**

아래는 실제로 계산해서 값이 정확히 맞아떨어지는 것을 확인한 완결된 스크립트다. 두 가지 흔한 케이스(단일 바이트 키, 4바이트 반복 키)를 각각 역산하고, 결과가 `CTF{...}` 형태인지까지 자동으로 검사한다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0199 실전 스크립트: 단일 바이트 XOR와 반복 키 XOR를 실제로 검증된 값으로 역산한다.

from itertools import cycle

# ===== 케이스 1: 단일 바이트 키 =====
# 어셈블리에서 xor al, 0x5A 를 확인했고, expected(정답) 12바이트를 Hex View에서 복사했다.
expected1 = bytes.fromhex("190e1c2122352805313f2327")
KEY1 = 0x5A

# XOR의 자기 역원 성질(a^b=c 이면 c^b=a)을 그대로 이용해서 같은 키로 다시 XOR한다.
flag1 = bytes(b ^ KEY1 for b in expected1)
print("케이스1 복원 flag:", flag1.decode())
# 실행 결과: 케이스1 복원 flag: CTF{xor_key}

# ===== 케이스 2: 4바이트 반복 키 =====
# 어셈블리에서 xor al, byte ptr [key+edx] 를 확인했고, div ebx(ebx=4)로 keylen=4임을 알아냈다.
expected2 = bytes.fromhex("08673f5a395c154d144b165314581c5836")
key2 = b"K3y!"   # 4바이트 키를 Hex View에서 그대로 복사

# itertools.cycle로 key2를 반복시키면서 expected2와 자리마다 XOR한다.
flag2 = bytes(e ^ k for e, k in zip(expected2, cycle(key2)))
print("케이스2 복원 flag:", flag2.decode())
# 실행 결과: 케이스2 복원 flag: CTF{roll_xor_key}

# 두 케이스 모두 "CTF{ 로 시작하고 } 로 끝나는지"를 자동으로 검사해서 성공 여부를 판정한다.
for name, result in [("케이스1", flag1), ("케이스2", flag2)]:
    ok = result.startswith(b"CTF{") and result.endswith(b"}")
    print(name, "형식 검사:", "통과" if ok else "실패")
# 실행 결과: 케이스1 형식 검사: 통과
# 실행 결과: 케이스2 형식 검사: 통과
```

## 관련 글
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0200 — ADD SUB 상수 기반 문자 변환
- REV-0201 — Rotate ROL ROR 기반 변환
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ../assembly/rev-0057-xor.md — XOR 명령어

## 출처/검증
- XOR의 자기 역원 성질(`a^b^b=a`)은 불(Boolean) 대수의 기본 정리로, 모든 CPU 아키텍처 매뉴얼(Intel SDM XOR 명령 설명 포함)에서 동일하게 성립.
- 반복 키/체인 XOR 패턴은 CTF 리버싱 writeup에서 흔히 관찰되는 구현 방식을 일반화한 것(2026-09-08 확인).
