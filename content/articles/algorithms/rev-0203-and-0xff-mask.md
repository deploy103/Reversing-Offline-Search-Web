---
id: REV-0203
title: "AND 0xFF 마스크 이해"
slug: "rev-0203-and-0xff-mask"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["and 0xff", "하위 바이트 마스크", "byte 캐스팅", "체크섬 마스크", "부호 확장 방지"]
aliases: ["and 0xff 왜함", "and ff 뭐임", "하위 바이트만 남김", "체크섬 wraparound"]
symptom_keywords: ["and eax 0xff가 계속 나옴", "왜 하위 바이트만 씀", "체크섬이 256 넘으면 이상해짐", "and로 값이 작아짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`and eax, 0xFF`(또는 `and al, 0xFF`, `movzx`)는 32비트/64비트 레지스터에서 **하위 8비트(0~255 범위)만 남기고 나머지 상위 비트를 전부 0으로 지우는 마스킹**이며, 체크섬 누적이나 부호 확장을 막고 "1바이트 값"으로 강제 변환할 때 CTF 검증 루프에서 매우 자주 등장한다.

## 언제 검색해야 하나
- 덧셈/곱셈/XOR 루프가 끝난 직후 `and eax, 0xFF` 또는 `and eax, 0FFh`가 보일 때
- 디컴파일 결과에 `(unsigned char)`, `& 0xFF`, `(uint8_t)` 캐스팅이 보일 때
- 값이 8비트 범위를 넘어서 계속 커지는데, 비교 대상은 항상 0~255 사이인 이유가 궁금할 때
- 대표 검색 질의 예시: `and 왜함`

## 핵심 개념
`AND` 연산은 두 비트가 모두 1일 때만 1이 되는 논리곱이다. 어떤 값 `x`에 `0xFF`(이진수로 `1111_1111`)를 AND하면, 하위 8비트는 원래 값 그대로 남고 그 위의 모든 비트는 강제로 0이 된다. 이것이 "마스크(mask)"라는 이름의 유래다 — 원하는 부분만 남기고 나머지를 가려버린다는 뜻.

이 마스크가 CTF 검증 루프에서 등장하는 대표적인 이유 세 가지:

1. **체크섬/해시 누적 값을 8비트로 강제 축소**: `sum += input[i]` 같은 누적을 여러 번 반복하면 `sum`이 8비트 범위를 훌쩍 넘어갈 수 있는데, 최종 비교는 1바이트짜리 체크섬과 하기 위해 `sum & 0xFF`로 잘라낸다.
2. **부호 확장(sign extension) 방지**: `char`를 `int`로 옮길 때 부호 있는 값이면 상위 비트가 1로 채워질 수 있는데(`movsx`), `& 0xFF`를 걸면 항상 0~255 범위의 부호 없는 값으로 강제된다. 이건 `movzx`(zero-extend)와 사실상 같은 효과를 낸다.
3. **바이트 연산의 자연스러운 wraparound을 명시적으로 재현**: REV-0200(ADD/SUB)에서 8비트 레지스터 연산이 자동으로 wrap된다고 설명했는데, 만약 32비트 레지스터로 같은 계산을 했다면 컴파일러/개발자가 `& 0xFF`를 명시적으로 붙여서 8비트 wraparound를 흉내 낸다.

## 화면/코드에서 보이는 징후
```asm
mov     eax, [sum]
add     eax, ecx
and     eax, 0FFh        ; 체크섬을 항상 0~255 범위로 유지
mov     [sum], eax
```
```c
checksum = (checksum + input[i]) & 0xFF;
```
또는 캐스팅으로 표현:
```c
unsigned char v = (unsigned char)(sum + input[i]);
```
IDA/Ghidra는 `& 0xFF`와 `(unsigned char)` 캐스팅을 사실상 동일한 의미로 서로 바꿔서 보여주기도 한다.

## 가장 먼저 할 것
`and`의 대상이 되는 레지스터가 원래 몇 비트 연산의 결과였는지(덧셈 누적? 곱셈? XOR?) 위쪽 코드를 먼저 확인한다. `& 0xFF`는 그 자체로는 변환이 아니라 "범위를 8비트로 강제 고정"하는 것뿐이므로, 실제 변환 로직은 그 앞의 연산에 있다.

## 단계별 절차
**1) 마스킹 대상 확인**: `and eax, 0xFF`가 어떤 값에 적용되는지(누적 합, 곱셈 결과, XOR 결과) 확인.

**2) 파이썬 재현 시 항상 동일 위치에 `& 0xFF` 삽입**
```python
checksum = 0
for b in data:
    checksum = (checksum + b) & 0xFF
```
파이썬 정수는 크기 제한이 없으므로, C/asm에서 자동으로 일어나는 8비트 wrap을 **직접 마스킹으로 재현하지 않으면 값이 절대 일치하지 않는다.**

**3) 체크섬 검증이라면 "원하는 결과를 만드는 자유도"를 활용**
체크섬 검증은 REV-0205(Modulo)와 밀접하다 — 마지막 한 바이트를 자유롭게 고를 수 있다면, 목표 체크섬에 맞춰 역산으로 그 바이트를 결정할 수 있다.
```python
target = 0x7A
partial_sum = sum(known_prefix_bytes) & 0xFF
last_byte = (target - partial_sum) & 0xFF
```

## 명령어/단축키
- IDA: `and` 명령의 즉시값 위에서 `H`(진법 토글)로 `0xFF`인지 `255`인지 즉시 확인
- Python: `x & 0xFF`, `x & 0xFFFF`(16비트), 항상 연산 직후에 마스킹

## 출력 해석
- 마스킹 후 값이 0~255 범위를 벗어나면 파이썬 코드에서 `& 0xFF`를 빠뜨린 것.
- 마스킹이 누적 연산 "매 반복마다" 걸리는지, 아니면 "루프가 다 끝난 후 딱 한 번"만 걸리는지에 따라 결과가 달라질 수 있으므로 asm에서 `and` 명령의 정확한 위치(루프 안/밖)를 확인해야 한다.

## 흔한 실수
- `& 0xFF`를 16비트 마스크(`& 0xFFFF`)나 24비트 마스크(REV-0204)와 혼동하는 것 — `F`의 개수를 세면 된다: `FF`=8비트, `FFFF`=16비트, `FFFFFF`=24비트, `FFFFFFFF`=32비트.
- 마스킹이 매 반복 적용되는지 최종 결과에만 적용되는지 구분하지 않고 파이썬 루프 바깥에서 한 번만 마스킹해버리는 것 — 결과가 크게 달라질 수 있다.
- `and eax, 0xFF`를 보고 무조건 "체크섬"이라고 단정하는 것 — 단순히 `char`로 캐스팅하려는 목적일 수도 있으므로 문맥(비교 대상이 배열인지 단일 값인지)을 함께 봐야 한다.

## 막혔을 때 다음 체크
- `FF`가 6개(`FFFFFF`)라면 → REV-0204(24비트 마스크).
- 마스킹된 값이 나머지 연산(modulo)의 결과처럼 보인다면 → REV-0205.
- 마스킹 전 값이 음수로 표시된다면 → REV-0206(음수 상수를 unsigned hex로 다시 읽기).

## 미니 예제
**예제 1 — 체크섬 마지막 바이트 역산**
```python
data_prefix = b"CTF{part"
target_checksum = 0x42
partial = sum(data_prefix) & 0xFF
missing = (target_checksum - partial) & 0xFF
print(hex(missing))
```

**예제 2 — 부호 확장 방지 확인**
```c
int v = (unsigned char)signed_char_value;   // & 0xFF와 동일 효과
```
`signed_char_value`가 `-1`(0xFF)이어도 `v`는 `-1`이 아니라 `255`가 된다 — `movzx` 계열과 동일한 의도.

**예제 3 — 처음부터 끝까지 실행되는 전체 스크립트 (체크섬 방정식 역산 + 최종 재검증까지)**

체크섬의 마지막 한 바이트가 자유도(내가 원하는 값을 골라도 되는 자리)라면, 나머지 부분의 체크섬을 미리 계산해두고 목표 체크섬에 맞는 마지막 바이트를 방정식으로 바로 구할 수 있다. 아래 스크립트는 값을 구한 뒤 실제로 다시 합쳐서 체크섬이 맞는지까지 재검증한다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0203 실전 스크립트: 체크섬(sum & 0xFF)의 마지막 자유 바이트를 방정식으로 역산한다.

data_prefix = b"CTF{part"     # 이미 알고 있는 flag의 앞부분(디스어셈블리/문자열에서 확인)
target_checksum = 0x42        # 바이너리에서 "이 값과 같아야 통과"라고 확인한 체크섬 목표값

# 1) 알고 있는 부분의 체크섬을 먼저 구하고, and eax, 0xFF와 동일하게 8비트로 마스킹한다.
partial = sum(data_prefix) & 0xFF
print("알고 있는 부분의 체크섬:", hex(partial))
# 실행 결과: 알고 있는 부분의 체크섬: 0xf

# 2) (partial + missing) & 0xFF == target_checksum 이 성립하도록 missing을 방정식으로 구한다.
#    뺄셈 후 다시 & 0xFF를 붙여서, 결과가 음수가 나오는 경우까지 0~255 범위로 자동 보정한다.
missing = (target_checksum - partial) & 0xFF
print("복원한 마지막 바이트:", hex(missing), repr(chr(missing)))
# 실행 결과: 복원한 마지막 바이트: 0x33 '3'

# 3) 구한 값이 정말 맞는지, 실제로 이어붙여서 체크섬을 처음부터 다시 계산해 재검증한다.
full_data = data_prefix + bytes([missing])
final_checksum = sum(full_data) & 0xFF
print("완성된 데이터:", full_data)
print("최종 체크섬:", hex(final_checksum), "목표와 일치?", final_checksum == target_checksum)
# 실행 결과: 완성된 데이터: b'CTF{part3'
# 실행 결과: 최종 체크섬: 0x42 목표와 일치? True
```

## 관련 글
- REV-0200 — ADD SUB 상수 기반 문자 변환
- REV-0204 — AND 0xFFFFFF 24비트 마스크 이해
- REV-0205 — Modulo와 오버플로를 이용한 검증
- REV-0206 — 음수 상수를 Unsigned Hex로 다시 읽기
- ../assembly/rev-0055-and.md — AND 명령어

## 출처/검증
- AND 마스킹과 비트 폭 절단 규칙은 Intel 64 and IA-32 Architectures Software Developer's Manual의 AND 명령 설명 및 C 언어 정수 승격/캐스팅 규칙(ISO C) 기준(2026-09-08 확인).
