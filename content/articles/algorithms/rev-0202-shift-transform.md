---
id: REV-0202
title: "Shift SHL SHR SAR 기반 변환"
slug: "rev-0202-shift-transform"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["shl", "shr", "sar", "shift 변환", "니블 분리", "nibble split", "djb2 해시", "hash*33"]
aliases: ["shl 반복문", "shr 역산 안됨", "shift는 왜 역산이 안됨", "니블 분리 조합"]
symptom_keywords: ["shl shr이 반복됨", "shift 역산이 이상함", "니블 나누는 것 같음", "hash<<5 패턴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`shl`(왼쪽 시프트), `shr`(부호 없는 오른쪽 시프트), `sar`(부호 있는 오른쪽 시프트)는 **밀려난 비트가 그냥 사라지는 연산**이라 단독으로는 완전히 역산할 수 없지만, 실전에서는 (1) 니블/바이트를 쪼갰다가 다시 합치는 "분리·조합" 용도이거나 (2) 곱셈을 대체하는 해시 누적식(`hash = (hash<<5) + hash + c` 같은 djb2류)으로 쓰이는 경우가 대부분이라, 그 맥락만 알아채면 여전히 파이썬으로 정확히 재현할 수 있다.

## 언제 검색해야 하나
- 루프 안에 `shl`/`shr`/`sar`가 반복되고, 그 결과가 `or`나 `add`와 결합되는 코드를 만났을 때
- 디컴파일 결과에 `(x << 4) | (y & 0xF)` 처럼 니블(4비트)을 합치는 식이 보일 때
- `hash = hash * 33 + c` 같은 해시 누적식이 곱셈(`imul`) 대신 `(hash << 5) + hash + c`로 최적화되어 있을 때
- "shift만 있고 or/add가 없는데 원래 값을 못 구하겠다"는 상황 — 이건 실제로 정보가 유실된 것일 수 있으니 그 가능성부터 먼저 인지해야 함

## 핵심 개념
Shift는 Rotate(REV-0201)와 근본적으로 다르다. Rotate는 밀려난 비트가 반대쪽으로 다시 들어오지만, Shift는 밀려난 비트가 그냥 버려지고 빈자리는 0(또는 SAR의 경우 부호 비트)으로 채워진다. 즉 **일반적으로 shift 하나만으로는 원래 값을 100% 복원할 수 없다** — 이건 XOR/ADD/SUB/ROL/ROR과 결정적으로 다른 점이므로 가장 먼저 인지해야 할 함정이다.

세 연산의 차이:
- **SHL(=SAL)**: 왼쪽으로 n비트 이동, 오른쪽 빈자리는 0으로 채움. `x << n`은 `x * 2^n`과 동일(오버플로 무시 시).
- **SHR**: 오른쪽으로 n비트 이동, 왼쪽 빈자리는 항상 0으로 채움(부호 없는 시프트). `unsigned` 값의 `x / 2^n`(내림)과 동일.
- **SAR**: 오른쪽으로 n비트 이동, 왼쪽 빈자리는 **원래 부호 비트로 채움**(부호 있는 시프트). `signed` 값의 `x / 2^n`(0 방향으로 내림, 단 음수는 -무한대 방향으로 내림하므로 정확히는 산술 시프트)과 동일. SHR과 SAR을 헷갈리면 음수 입력에서 결과가 완전히 달라지므로 반드시 구분해야 한다.

그럼에도 리버싱에서 shift가 검증 로직에 쓰일 때는 대개 아래 두 패턴 중 하나이고, 둘 다 실질적으로 역산 가능하다.

**패턴 A — 니블/바이트 분리·조합(완전히 역산 가능)**: 한 바이트를 상위 4비트와 하위 4비트로 나눠서 각각 다른 용도로 쓰거나, 두 바이트를 합쳐 하나의 워드로 만드는 경우. 분리와 결합이 쌍을 이루므로 원래 값 전체가 보존된다.

**패턴 B — 해시 누적식의 곱셈 최적화(알고리즘을 알면 그대로 재현 가능, 역산이 아니라 "동일 계산"의 문제)**: `hash * 33`을 컴파일러가 `(hash << 5) + hash`로 바꾼 것뿐이므로, 이건 해시 함수 자체를 파이썬으로 그대로 구현하면 되는 문제이지, "shift를 거꾸로 되돌리는" 문제가 아니다.

## 화면/코드에서 보이는 징후
**패턴 A: 니블 분리 (예: 바이트를 두 개의 hex 문자로 인코딩)**
```asm
movzx   eax, byte ptr [rdi+rcx]
mov     ebx, eax
shr     ebx, 4          ; 상위 니블
and     eax, 0x0F       ; 하위 니블
```
디컴파일:
```c
unsigned char hi = (b >> 4) & 0xF;
unsigned char lo = b & 0xF;
```
반대로 조합하는 코드:
```c
unsigned char b = (hi << 4) | lo;
```

**패턴 B: djb2류 해시 누적식**
```asm
lea     eax, [rax+rax*4]   ; eax = hash*5  (이런 조합도 흔함, *33은 두 단계로 쪼개질 수 있음)
shl     eax, 3             ; ... *8 -> 누적하면 *33 근처의 다양한 조합
```
가장 전형적인 djb2 형태:
```c
hash = ((hash << 5) + hash) + c;   // hash*33 + c 와 완전히 동일
```
IDA는 `hash << 5`를 그대로 `shl eax, 5`로 보여주고, `+hash`는 `add eax, ebx`(이전 hash 백업 레지스터)로 나타난다.

**SAR을 signed 나눗셈 대신 쓰는 경우:**
```asm
mov     eax, [value]
sar     eax, 2            ; value / 4 (부호 유지, signed)
```
비교 로직이라기보다 인덱스 계산이나 배열 접근에 쓰이는 경우가 많으므로, 이게 flag 변환의 일부인지 아니면 단순 배열 인덱싱인지 문맥을 구분해야 한다.

## 가장 먼저 할 것
shift 결과가 **다른 shift 결과와 `or`로 합쳐지는지**(니블/바이트 조합 → 완전 역산 가능), 아니면 **원래 값과 `add`로 합쳐지는지**(해시 누적식 → 알고리즘 자체를 재구현), 아니면 **아무것도 안 합쳐지고 그냥 버려지는지**(정보 손실 → 애초에 여러 입력이 같은 출력을 만들 수 있으므로 완전한 역산 불가, 다른 단서 필요)를 가장 먼저 구분한다.

## 단계별 절차
**1) 결합 연산자 확인**

`shl`/`shr` 직후 또는 근처에 `or`, `add`가 있는지 반드시 확인한다.

**2) 패턴 A(분리·조합)면 마스크와 시프트양을 그대로 파이썬에 옮김**

```python
def split_nibbles(b: int):
    hi = (b >> 4) & 0xF
    lo = b & 0xF
    return hi, lo

def join_nibbles(hi: int, lo: int) -> int:
    return ((hi & 0xF) << 4) | (lo & 0xF)

# 예: 니블을 각각 hex 문자로 저장한 경우 원복
def bytes_from_hexchars(hi_arr: bytes, lo_arr: bytes) -> bytes:
    return bytes(join_nibbles(h, l) for h, l in zip(hi_arr, lo_arr))
```

**3) 패턴 B(해시 누적식)면 shift를 되돌리지 말고 알고리즘 자체를 그대로 파이썬으로 구현**

```python
def djb2(data: bytes) -> int:
    h = 5381
    for c in data:
        h = ((h << 5) + h + c) & 0xFFFFFFFF   # h*33 + c
    return h
```
이 해시가 단방향이면(대부분 그렇다) "출력에서 입력을 역산"하는 게 아니라, 후보 입력들을 넣어보고 같은 해시가 나오는지 **정방향으로 검증**하는 방식으로 접근해야 한다.

**4) 패턴 C(순수 정보 손실)면 역산 불가능함을 인정하고 다른 단서를 찾음**

예: `x >> 4`만 하고 하위 4비트를 버린 뒤 그 결과만 비교에 쓴다면, 원래 값의 하위 4비트는 그 비교만으로는 절대 알 수 없다(0000~1111 중 어느 것이든 같은 결과를 만든다). 이 경우 다른 검증 조건(다른 비교 루프, 길이 제약 등)에서 하위 니블에 대한 추가 단서를 찾아야 한다.

## 명령어/단축키
- IDA: `shl`/`shr`/`sar` 명령의 즉시값 오퍼랜드에서 `H`(진법 토글), 데이터 폭(`al`/`ax`/`eax`/`rax`) 반드시 확인
- Ghidra: 디컴파일러가 shift+or 조합을 자동으로 니블/바이트 결합 표현으로 정리해줄 때가 많으므로, `<<`와 `>>`가 같은 변수에 대해 짝지어 나오는지 눈으로 스캔
- Python: `hi = (b >> 4) & 0xF`, `lo = b & 0xF`, `(hi << 4) | lo`

## 출력 해석
- 분리된 니블을 다시 합쳤을 때 원래 바이트 범위(0~255)를 벗어나면 마스크(`& 0xF`)를 빠뜨린 것.
- 해시 누적식을 파이썬으로 재현했는데 바이너리에서 뽑은 목표 해시값과 다르면, 초기값(`5381` 같은 상수)이나 최종 마스킹(`& 0xFFFFFFFF`)을 놓쳤을 가능성이 크다.
- SAR을 SHR로 착각하고 역산해서 음수 입력에서만 결과가 이상하다면, 부호 있는 시프트인지 다시 확인(부호 비트가 1인 값일 때만 차이가 드러나므로 양수 테스트 케이스만으론 안 걸릴 수 있다).

## 흔한 실수
- shift만 보고 무작정 "반대 방향 shift로 역산하면 되겠지"라고 생각하는 것 — Rotate(REV-0201)와 달리 Shift는 정보가 유실되므로 이 가정 자체가 틀렸다. 항상 `or`/`add`로 합쳐지는 짝이 있는지부터 확인해야 한다.
- `hash << 5`를 보고 "이건 못 되돌리는 shift다"라고 포기하는 것 — 사실 이건 곱셈(`*32`)의 최적화 표현일 뿐이므로, 애초에 "shift를 되돌리는" 문제가 아니라 "해시 알고리즘 자체를 그대로 재현"하는 문제임을 인지하지 못한 것.
- SHR과 SAR을 코드만 보고 구분하지 않고 둘 다 "그냥 오른쪽 시프트"로 뭉뚱그리는 것 — signed/unsigned 문맥에 따라 결과가 갈리므로 반드시 명령어 이름(`shr` vs `sar`)과 변수 타입을 함께 확인.
- 니블 조합 패턴에서 상위/하위가 바뀐 순서로 합치는 것(`(lo << 4) | hi`처럼 반대로) — 원본 코드에서 어느 쪽에 `shl 4`가 적용됐는지 정확히 다시 확인.

## 막혔을 때 다음 체크
- shift 결과가 rotate처럼 반대쪽으로 다시 들어오는 것 같다면 → REV-0201(그건 사실 rotate).
- shift와 XOR이 함께 있고 곱셈 상수까지 보인다면 → REV-0207/REV-0208(FNV)일 가능성.
- shift 결과가 256개짜리 테이블 인덱싱에 쓰인다면 → REV-0209(CRC, 테이블 기반 구현은 시프트로 다항식을 이동시키는 방식과 관련).
- 결과가 8비트를 넘어 잘리는 이유가 궁금하면 → REV-0203/REV-0204(AND 마스크).

## 미니 예제
**예제 1 — 바이트를 hex 문자 두 개로 인코딩한 뒤 검증**
```c
char hexchar_hi = "0123456789abcdef"[(input[i] >> 4) & 0xF];
char hexchar_lo = "0123456789abcdef"[input[i] & 0xF];
```
정답 배열이 `hexchar_hi`, `hexchar_lo`의 나열이라면, 파이썬으로는 그냥 `bytes.fromhex()`로 즉시 원복 가능:
```python
expected_hex_string = "48656c6c6f"   # 정답 배열에서 읽은 hex 문자들을 이어붙인 것
flag = bytes.fromhex(expected_hex_string)
print(flag)  # b'Hello'
```

**예제 2 — djb2 해시 재현**
```c
unsigned int hash = 5381;
for (i = 0; input[i]; i++)
    hash = ((hash << 5) + hash) + input[i];
```
```python
def djb2(s: bytes) -> int:
    h = 5381
    for c in s:
        h = ((h << 5) + h + c) & 0xFFFFFFFF
    return h

target = 0x1A2B3C4D  # 바이너리에서 뽑은 목표값
# 후보 입력을 넣어보고 djb2(candidate) == target 인지 정방향으로 검증
```

**예제 3 — SHR 정보 손실 케이스 (역산 불가 인지)**
```c
if ((input[i] >> 4) != (expected[i] & 0xF)) return 0;
```
이 조건은 `input[i]`의 하위 4비트에 대해서는 아무 정보도 주지 않는다 — 상위 니블만 맞으면 통과. 다른 검증 루프가 하위 니블을 커버하는지 반드시 별도로 찾아야 한다.

**예제 4 — SAR로 부호 있는 나눗셈 위장**
```asm
mov eax, [val]
cdq
sar eax, 3      ; signed val / 8 과 근접(단, 음수 처리 미세한 차이 존재)
```
이건 문자 변환이 아니라 인덱스나 카운터 계산일 가능성이 크므로, 이 값이 실제로 flag 바이트와 비교되는지 아니면 루프 제어에만 쓰이는지부터 구분한다.

**예제 5 — 처음부터 끝까지 실행되는 전체 스크립트 (니블 분리·조합 라운드트립 + djb2 정방향 재현)**

Shift는 정보가 유실될 수 있으므로, "역산 가능한 케이스(니블 분리·조합)"와 "역산이 아니라 알고리즘 재현이 필요한 케이스(djb2 해시)"를 구분해서 각각 실습한다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0202 실전 스크립트: 니블 분리/조합 라운드트립 + djb2 해시 정방향 재현을 함께 다룬다.

# ===== 패턴 A: 바이트를 상위/하위 니블로 쪼갠 뒤 다시 합치기 (완전히 역산 가능) =====
def split_nibbles(b: int):
    hi = (b >> 4) & 0xF   # 오른쪽으로 4비트 밀어서 상위 4비트만 하위 자리에 남김
    lo = b & 0xF          # 마스크로 하위 4비트만 남김
    return hi, lo

def join_nibbles(hi: int, lo: int) -> int:
    # 상위 니블을 다시 4비트 왼쪽으로 밀어 올리고, 하위 니블과 OR로 합쳐서 원래 바이트를 복원한다.
    return ((hi & 0xF) << 4) | (lo & 0xF)

original = b"Hi!"
for b in original:
    hi, lo = split_nibbles(b)
    restored = join_nibbles(hi, lo)
    assert restored == b        # 분리한 뒤 다시 합치면 항상 원래 바이트로 정확히 돌아와야 한다
print("니블 분리/조합 라운드트립 성공, 원본:", original)
# 실행 결과: 니블 분리/조합 라운드트립 성공, 원본: b'Hi!'

# ===== 패턴 B: djb2 해시(hash = (hash<<5)+hash+c)를 "역산"이 아니라 정방향으로 그대로 재현 =====
def djb2(data: bytes) -> int:
    h = 5381                                 # djb2의 표준 초기값
    for c in data:
        h = ((h << 5) + h + c) & 0xFFFFFFFF  # h*33 + c 와 완전히 동일한 계산(shift-add로 곱셈 대체)
    return h

target_hash = 0xF923099           # 바이너리에서 뽑은 목표 해시값(djb2(b"hello")의 실제 결과)
candidate = b"hello"               # 프로그램 로직을 보고 추정한 후보 입력
computed = djb2(candidate)
print("djb2(hello) =", hex(computed))
print("목표값과 일치?", computed == target_hash)
# 실행 결과: djb2(hello) = 0xf923099
# 실행 결과: 목표값과 일치? True
```

## 관련 글
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0201 — Rotate ROL ROR 기반 변환
- REV-0203 — AND 0xFF 마스크 이해
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ../assembly/rev-0061-shl-sal.md — SHL/SAL 명령어
- ../assembly/rev-0062-shr.md — SHR 명령어
- ../assembly/rev-0063-sar.md — SAR 명령어

## 출처/검증
- SHL/SHR/SAR의 정의와 부호 처리 차이는 Intel 64 and IA-32 Architectures Software Developer's Manual의 SHL/SHR/SAR 명령 설명 기준.
- djb2 해시 알고리즘(`hash*33+c`)은 Daniel J. Bernstein이 comp.lang.c 뉴스그룹에 공개한 알고리즘으로, 다수의 오픈소스 구현체(예: PHP, Perl 초기 해시 함수)에서 채택된 공개 알고리즘 기준(2026-09-08 확인).
