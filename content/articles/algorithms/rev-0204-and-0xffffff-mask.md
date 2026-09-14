---
id: REV-0204
title: "AND 0xFFFFFF 24비트 마스크 이해"
slug: "rev-0204-and-0xffffff-mask"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["and 0xffffff", "24비트 마스크", "RGB 마스크", "상위 바이트 제거", "0xffffff"]
aliases: ["0xffffff 뭐임", "24비트가 뭐임", "and ffffff", "상위 1바이트만 지움"]
symptom_keywords: ["0xffffff가 보임", "24비트 마스크 왜 씀", "상위 바이트만 날아감", "RGB 색상값 같음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`and eax, 0xFFFFFF`는 32비트 값에서 **하위 24비트(3바이트)만 남기고 최상위 1바이트를 지우는 마스크**이며, RGB 색상값 추출, 24비트 필드/버전 정보 처리, 또는 해시 결과를 의도적으로 축소해서 브루트포스 가능한 크기로 줄이는 CTF 트릭에서 자주 나타난다. 이 상수(`0xFFFFFF`, 십진수 `16777215`)는 검색 중 자주 마주치는 대표적인 상수다.

## 언제 검색해야 하나
- 디스어셈블리에 `and eax, 0FFFFFFh` 또는 `and eax, 16777215`가 보일 때
- 색상값(픽셀, RGB) 처리 코드로 보이는 곳에서 상위 1바이트(알파 채널 등)를 제거하는 로직을 찾을 때
- 해시나 체크섬 결과가 32비트인데 최종 비교는 6자리 hex(24비트)로만 이루어질 때
- `16777619`(FNV prime, REV-0207/0208)와 `16777215`(0xFFFFFF, 24비트 마스크)를 혼동할 때 — 숫자가 비슷해 보이지만 완전히 다른 의미다

## 핵심 개념
`0xFFFFFF`는 16진수로 `F`가 6개, 즉 `1111_1111_1111_1111_1111_1111`(24개의 1)이다. 32비트 레지스터에서 이 값과 AND하면 최상위 8비트(1바이트)가 0으로 지워지고 나머지 24비트(3바이트)는 그대로 남는다.

**F 개수로 비트 폭 빠르게 판별하는 법 (REV-0026과 동일한 원리):**
| 마스크 | F 개수 | 유지되는 비트 | 유지되는 바이트 |
|---|---|---|---|
| `0xFF` | 2 | 8비트 | 1바이트 |
| `0xFFFF` | 4 | 16비트 | 2바이트 |
| `0xFFFFFF` | 6 | 24비트 | 3바이트 |
| `0xFFFFFFFF` | 8 | 32비트 | 4바이트 |

24비트 마스크가 특히 자주 등장하는 맥락:
1. **RGB 색상값**: `0xAARRGGBB` 형태의 32비트 픽셀값에서 알파(AA) 채널을 버리고 순수 색상(`0xRRGGBB`)만 남길 때.
2. **버전/매직 넘버 필드**: 32비트 중 상위 1바이트를 플래그나 타입 태그로 쓰고, 나머지 24비트를 실제 값(길이, 오프셋)으로 쓰는 커스텀 포맷.
3. **해시 공간을 의도적으로 축소**: 32비트 해시를 그대로 쓰면 브루트포스가 사실상 불가능(약 43억 가지)하지만, 문제 출제자가 `hash & 0xFFFFFF`로 24비트(약 1677만 가지)로 줄여서 "노트북으로 몇 분 안에 브루트포스 가능한" 난이도로 조정하는 경우가 있다.

## 화면/코드에서 보이는 징후
```asm
mov     eax, [pixel]
and     eax, 0FFFFFFh      ; 알파 채널 제거, RGB만 남김
cmp     eax, 0A1B2C3h
jne     wrong
```
```c
if ((color & 0xFFFFFF) != 0xA1B2C3)
    return 0;
```
해시 축소 예:
```c
unsigned int h = fnv1a_32(input);
if ((h & 0xFFFFFF) != 0x2C1A9F)   // 32비트 해시를 24비트로 축소해서 비교
    return 0;
```

## 가장 먼저 할 것
`0xFFFFFF`가 마스킹하는 원본 값이 어디서 왔는지(픽셀 데이터? 해시 계산 결과? 단순 필드?) 먼저 추적한다. 만약 해시 계산 직후에 이 마스크가 걸린다면, 해시 공간이 24비트로 줄어든 것이므로 브루트포스 난이도를 재평가해야 한다(2^24 ≈ 1,677만 — 파이썬으로도 초 단위~분 단위에 끝날 수 있는 크기).

## 단계별 절차
**1) 마스크 확인**: `0xFFFFFF` 또는 `16777215`인지 IDA에서 `H`로 진법 토글해서 정확히 확인.

**2) 원본 값의 출처 파악**: 그 위 코드가 픽셀/색상 처리인지, 해시 계산인지 확인.

**3) 파이썬으로 동일 마스킹 재현**
```python
value = 0xA1B2C3D4
masked = value & 0xFFFFFF
print(hex(masked))   # 0xb2c3d4
```

**4) 해시 축소 상황이면 브루트포스 가능성 검토**
```python
def fnv1a_32(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

target = 0x2C1A9F
import itertools, string
charset = string.ascii_lowercase + string.digits
for length in range(1, 5):
    for cand in itertools.product(charset, repeat=length):
        s = "".join(cand).encode()
        if (fnv1a_32(s) & 0xFFFFFF) == target:
            print("found:", s)
            break
```

## 명령어/단축키
- IDA: `H`(진법 토글)로 `0xFFFFFF`가 `16777215`인지, 혹은 `16777619`(FNV prime)와 헷갈리지 않았는지 재확인
- Python: `value & 0xFFFFFF`, `hex(value & 0xFFFFFF)`

## 출력 해석
- 마스킹 후 값이 6자리 hex(`0x000000`~`0xFFFFFF`)를 벗어나면 마스크 값 자체를 잘못 읽은 것.
- 해시 축소 브루트포스가 너무 오래 걸린다면 charset이나 length 범위를 문제 조건에 맞게 좁혀야 한다.

## 흔한 실수
- `0xFFFFFF`(24비트 마스크, 16777215)와 `16777619`(FNV prime, 0x01000193)를 숫자가 비슷하다고 혼동하는 것 — 하나는 AND 마스크이고 하나는 곱셈 상수로 용도 자체가 다르다.
- 24비트 마스크를 3바이트 정수로 다룰 때 엔디안(little-endian) 순서를 헷갈려서 바이트 나열 순서를 반대로 읽는 것.
- 상위 1바이트가 항상 `0x00`이라고 가정하고 원본 값을 그대로 마스킹 결과로 착각하는 것 — 원본 상위 바이트에 의미 있는 데이터(알파 채널, 플래그)가 있었을 수 있는데 이는 마스킹으로 영구히 사라지므로 복원 불가능하다는 점을 놓치는 것.

## 막혔을 때 다음 체크
- `F`가 2개(8비트)라면 → REV-0203.
- 이 마스크가 해시 계산 뒤에 있다면 → REV-0207/REV-0208(FNV), REV-0209(CRC)에서 원본 해시 알고리즘부터 특정.
- 마스킹 전 값이 음수로 보인다면 → REV-0206.

## 미니 예제

**예제 1 — 어셈블리에서 24비트 마스크 읽기**
```asm
mov  eax, [rbp-4]   ; eax = 0xDEADBEEF (예시)
and  eax, 0FFFFFFh  ; eax = 0x00ADBEEF  (상위 1바이트 0xDE가 잘려나감)
```
Python으로 그대로 재현:
```python
value = 0xDEADBEEF
masked = value & 0xFFFFFF
print(hex(masked))  # 0xadbeef
```

**예제 2 — RGB 색상값에서 알파 바이트 제거**
```python
argb = 0xFF3399CC        # 0xAA_RR_GG_BB 형태
rgb = argb & 0xFFFFFF     # 0x3399CC — 알파(0xFF)만 잘라냄
```

**예제 3 — 처음부터 끝까지 실행되는 전체 스크립트 (24비트로 축소된 해시를 실제로 브루트포스)**

32비트 해시(약 43억 가지)는 무식하게 다 돌려보기 어렵지만, 문제 출제자가 `& 0xFFFFFF`로 24비트(약 1677만 가지)로 줄여놨다면 짧은 입력에 한해 파이썬으로도 몇 초 안에 뚫을 수 있다. 아래 스크립트는 실제로 끝까지 실행해서 정답을 찾아내는 것까지 확인된 버전이다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0204 실전 스크립트: 32비트 해시를 24비트(0xFFFFFF)로 축소해둔 경우,
# 축소된 목표값을 실제로 브루트포스로 뚫어서 원문을 찾아낸다.

import itertools
import string

def fnv1a_32(data: bytes) -> int:
    # FNV-1a 32비트 해시를 그대로 재현한다 (REV-0207/0208 참고).
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

# 1) 바이너리에서 뽑은, 24비트로 축소된 목표값(and eax, 0FFFFFFh 뒤에 나온 비교 상수)이라고 가정한다.
target = 0x2505CA

# 2) 문제 조건상 입력이 소문자+숫자, 길이 1~2자리라고 가정하고 그 범위를 전부 시도한다.
#    (실제 문제에서는 flag 길이나 문자셋 힌트에 맞춰 charset과 length 범위를 조정해야 한다)
charset = string.ascii_lowercase + string.digits
found = None
for length in range(1, 3):
    for combo in itertools.product(charset, repeat=length):
        candidate = "".join(combo).encode()
        # 계산한 32비트 해시를 24비트로 마스킹한 뒤에 목표값과 비교한다 — 원본 코드와 똑같은 순서.
        if (fnv1a_32(candidate) & 0xFFFFFF) == target:
            found = candidate
            break
    if found:
        break

print("찾아낸 원문:", found)
# 실행 결과: 찾아낸 원문: b'ab'
if found is not None:
    print("검증:", hex(fnv1a_32(found) & 0xFFFFFF), "== 목표값", hex(target))
    # 실행 결과: 검증: 0x2505ca == 목표값 0x2505ca
```

## 관련 글
- REV-0203 — AND 0xFF 마스크 이해
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ./rev-0208-fnv-16777619.md — 16777619 상수가 보일 때 FNV 의심하기
- ../assembly/rev-0055-and.md — AND 명령어

## 출처/검증
- AND 마스킹 규칙은 Intel 64 and IA-32 Architectures Software Developer's Manual의 AND 명령 설명 기준.
- 24비트 RGB 픽셀 포맷(`0xRRGGBB`)은 일반적인 그래픽스 관례 기준(2026-09-08 확인).
