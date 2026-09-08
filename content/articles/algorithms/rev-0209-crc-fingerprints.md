---
id: REV-0209
title: "CRC 계열 알고리즘 흔적 찾기"
slug: "rev-0209-crc-fingerprints"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["CRC32", "CRC16", "0xEDB88320", "0x04C11DB7", "crc 테이블", "polynomial", "zlib crc32"]
aliases: ["crc32 알아보는 법", "체크섬 테이블 256개", "crc 다항식 상수", "crc 어디서 씀"]
symptom_keywords: ["256개짜리 상수 테이블이 있음", "0xedb88320이 보임", "crc32 함수를 임포트함", "체크섬 알고리즘 이름을 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이너리 안에 정확히 **256개의 4바이트(또는 2바이트) 상수로 이루어진 정적 테이블**이 있고, 그 테이블의 인덱스 1번 값이 `0x77073096`(CRC-32) 같은 특징적인 값이거나, 코드에 `0xEDB88320`/`0x04C11DB7` 같은 다항식 상수가 보이면 이는 거의 확실히 **CRC(순환 중복 검사) 계열 체크섬**이며, 표준 CRC라면 소스코드 없이도 Python `zlib`/`binascii` 모듈로 즉시 재현할 수 있다.

## 언제 검색해야 하나
- `.rodata`/`.data` 섹션에 1024바이트(256×4바이트)짜리 정적 배열이 있는데 값들이 규칙성 없이 무작위로 보일 때
- 함수 안에 `0xEDB88320`, `0x04C11DB7`, `0x82F63B78` 같은 낯선 32비트 상수가 있을 때
- Imports 탭에 `crc32`(zlib), `RtlComputeCrc32`(Windows API) 같은 함수가 있을 때
- 8회 반복되는 내부 루프(비트 단위 처리, `shr`/`sar` + 조건부 XOR)가 바깥쪽 바이트 루프를 감싸고 있는 "테이블 없는" 구현을 만났을 때

## 핵심 개념
CRC는 원래 데이터 전송 오류를 검출하기 위해 설계된 체크섬으로, 데이터를 하나의 큰 이진수로 보고 미리 정해진 **다항식(polynomial)으로 나눈 나머지**를 결과로 삼는다(GF(2) 상의 다항식 나눗셈). 구현 방식은 크게 두 가지가 있다.

**1) 테이블 기반(table-driven) 구현 — 실무에서 압도적으로 많이 쓰임**

미리 256개의 값을 계산해둔 룩업 테이블을 만들어, 바이트당 한 번의 테이블 조회와 XOR·시프트만으로 CRC를 갱신한다. 표준 CRC-32(반사형, 다항식 `0xEDB88320`)의 테이블에서 인덱스 1번 값은 **항상 `0x77073096`** 이다 — 이는 zlib을 포함한 거의 모든 표준 CRC-32 구현에서 동일하게 나타나는 매우 강력한 지문(fingerprint)이다.

```c
uint32_t crc = 0xFFFFFFFF;         // 초기값 (많은 CRC-32 변형이 공통으로 사용)
for (i = 0; i < len; i++)
    crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
crc ^= 0xFFFFFFFF;                 // 최종 XOR (비트 반전으로 마무리)
```
이 정확한 형태(`crc = table[(crc^byte)&0xFF] ^ (crc>>8)`)와 시작/끝의 `0xFFFFFFFF` XOR이 표준 CRC-32(ISO-HDLC, zlib/PKZIP/이더넷 등에서 쓰는 그 CRC-32)의 전형적인 모습이다.

**2) 테이블 없는(bit-by-bit) 구현 — 느리지만 테이블이 안 보일 때**

테이블을 미리 만들지 않고, 바이트마다 8번의 비트 단위 루프를 돌며 최상위(또는 최하위) 비트를 확인해서 다항식을 XOR한다.
```c
crc ^= data[i];
for (j = 0; j < 8; j++)
    crc = (crc & 1) ? (crc >> 1) ^ 0xEDB88320 : (crc >> 1);
```
정적 테이블이 안 보여도, "바깥 루프(바이트) 안에 정확히 8번 도는 안쪽 루프(비트)가 있고, 그 안에서 다항식 상수와 조건부 XOR을 한다"는 구조만 보이면 CRC임을 알 수 있다.

**대표적인 CRC 다항식 상수 (모두 32비트 반사형/정방향 기준)**

| 상수(hex) | 의미 |
|---|---|
| `0xEDB88320` | CRC-32(반사형, zlib/PKZIP/이더넷/PNG에서 쓰는 표준 CRC-32) 다항식 |
| `0x04C11DB7` | CRC-32(정방향) 다항식 — 반사형의 비트 순서를 뒤집은 것과 동일 알고리즘 |
| `0x82F63B78` | CRC-32C(Castagnoli, SSE4.2 `crc32` 명령어, iSCSI/ext4 등에서 사용) 다항식 |
| `0x77073096` | 표준 CRC-32 테이블의 인덱스 1 값 (테이블만 보고도 알아볼 수 있는 지문) |
| `0xA001` | CRC-16(ARC/Modbus 계열, 반사형) 다항식 |
| `0x1021` | CRC-16(CCITT) 다항식 |

## 화면/코드에서 보이는 징후
**테이블 기반 CRC-32 (가장 흔한 형태):**
```asm
loop1:
movzx   eax, byte ptr [rsi+rcx]
xor     eax, [crc]
and     eax, 0FFh
mov     eax, [table+rax*4]
mov     edx, [crc]
shr     edx, 8
xor     eax, edx
mov     [crc], eax
inc     rcx
cmp     rcx, len
jl      loop1
```
디컴파일:
```c
for (i = 0; i < len; i++)
    crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
```

**비트 단위 구현(테이블 없음):**
```asm
xor     eax, [data_byte]
mov     ecx, 8
bit_loop:
test    eax, 1
jz      no_xor
shr     eax, 1
xor     eax, 0EDB88320h
jmp     next_bit
no_xor:
shr     eax, 1
next_bit:
dec     ecx
jnz     bit_loop
```

**Import를 통한 확정(가장 빠른 케이스):**
```text
Imports: crc32 (zlib.dll / libz.so.1)
```
이 경우 계산 로직을 볼 필요도 없이 표준 zlib CRC-32라고 100% 확정할 수 있다.

## 가장 먼저 할 것
Imports 탭에서 `crc32`가 임포트되어 있는지 먼저 확인한다(zlib 정적/동적 링크). 없다면 `.rodata`에서 1024바이트짜리 상수 배열을 찾고, 그 배열의 두 번째 원소(인덱스 1)가 `0x77073096`인지 확인한다. 일치하면 표준 CRC-32로 100% 확정.

## 단계별 절차
**1) Imports 확인** — `crc32`, `RtlComputeCrc32`, `boost::crc32` 등.

**2) 테이블 지문 대조**
```python
# IDA Hex View에서 테이블 시작 주소 + 4바이트(인덱스 1) 읽은 값
table_index_1 = 0x77073096
if table_index_1 == 0x77073096:
    print("표준 CRC-32(0xEDB88320 다항식) 확정")
```

**3) 다항식 상수 직접 확인** — 테이블이 없다면 코드에서 `0xEDB88320`/`0x04C11DB7`/`0x82F63B78` 등을 직접 검색.

**4) Python으로 재현 (표준 CRC-32라면 직접 구현할 필요조차 없음)**
```python
import zlib

def crc32_of(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF

print(hex(crc32_of(b"123456789")))  # 0xcbf43926 (표준 CRC-32 공인 테스트 벡터)
```

**5) 커스텀 다항식이거나 zlib이 없는 환경이면 직접 구현**
```python
def crc32_manual(data: bytes, poly: int = 0xEDB88320, init: int = 0xFFFFFFFF, final_xor: int = 0xFFFFFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ poly if (crc & 1) else (crc >> 1)
    return crc ^ final_xor

print(hex(crc32_manual(b"123456789")))  # 0xcbf43926, zlib.crc32와 동일해야 함
```

**6) 검증 로직과 대조** — 계산한 CRC가 바이너리의 비교 상수와 일치하는지 확인한다. CRC 자체는 단방향(원문 복원 불가)이므로, "값을 아는 원문이 정말 flag인지" 검증하는 용도로만 쓰거나, flag 길이/문자셋이 짧다면 브루트포스로 접근한다.

## 명령어/단축키
- IDA: 테이블처럼 보이는 데이터 블록을 선택하고 `A`(아스키) 대신 `D`→`Alt+Q`류로 dword 배열로 재해석, 이후 `Array`(단축키는 버전에 따라 다름)로 256개짜리 배열임을 명시
- Python: `zlib.crc32(data)`, `binascii.crc32(data)`(동일 결과), `zlib.crc32(data, prev_crc)`로 누적 CRC도 재현 가능

## 출력 해석
- 계산한 CRC가 바이너리의 비교 상수와 일치하면 알고리즘 확정 완료.
- 표준 다항식(`0xEDB88320`)인데 결과가 zlib과 안 맞는다면, 초기값(`init`)이나 최종 XOR(`final_xor`)이 표준(`0xFFFFFFFF`)이 아닌 커스텀 값일 수 있다 — 코드에서 `crc = 0xFFFFFFFF`(초기화)와 `crc ^= 0xFFFFFFFF`(최종 XOR) 부분을 asm에서 다시 찾아 정확한 값을 대입한다.
- 테이블 크기가 256이 아니라 16이면 니블(4비트) 단위 CRC 구현일 수 있으니 별도로 접근(테이블당 니블 하나씩 처리, 8회가 아니라 2×length회 반복).

## 흔한 실수
- CRC를 FNV(REV-0207/0208)와 혼동하는 것 — CRC는 보통 256개짜리 테이블이나 8회 비트루프가 있는 반면, FNV는 테이블 없이 단순 곱셈+XOR 한 번씩만 반복하는 짧은 루프다. 상수 자릿수도 다르다(CRC는 `0xEDB88320`류, FNV는 `16777619`류).
- CRC가 암호학적으로 안전한 해시라고 착각해서 "원문을 복원할 수 없으니 포기"하는 것 — 맞는 말이지만, 애초에 CTF에서 CRC를 쓰는 이유는 대부분 "체크섬 검증"이 목적이지 비밀을 숨기려는 게 아니므로, CRC 자체보다 그 앞뒤의 다른 로직(길이 제약, 문자셋 제한)에서 답을 찾아야 하는 경우가 많다.
- 초기값/최종 XOR을 표준값(`0xFFFFFFFF`)으로 무조건 가정해서, 커스텀 초기값을 쓰는 변형 CRC에서 결과가 안 맞는데도 원인을 못 찾는 것.
- CRC-32와 CRC-32C(Castagnoli, SSE4.2 하드웨어 명령어로 계산되는 변형)를 다항식만 보고 구분하지 못하는 것 — `crc32` x86 명령어(SSE4.2)가 직접 쓰였다면 이는 `0x82F63B78` 다항식(Castagnoli)이지 zlib의 표준 CRC-32(`0xEDB88320`)가 아니다.

## 막혔을 때 다음 체크
- 상수가 `16777619`나 `0x811C9DC5`처럼 보인다면 → REV-0207/REV-0208(FNV로 혼동하지 않도록 재확인).
- 나머지 연산/모듈러스 기반 체크섬처럼 보인다면 → REV-0205(CRC도 본질적으로 다항식 나눗셈의 나머지이므로 개념적으로 연결됨).
- 결과가 24비트로 잘려서 비교된다면 → REV-0204(24비트 마스크로 해시 공간을 축소하는 트릭).
- SSE4.2 `crc32` 명령어 자체를 처음 본다면 → Intel SDM의 CRC32 명령어 설명을 별도로 확인(하드웨어 가속 CRC32C).

## 미니 예제
**예제 1 — zlib 임포트로 즉시 확정**
Imports 탭에 `crc32`가 있고, 인자로 `(0, buffer, length)`가 전달되는 걸 확인했다면:
```python
import zlib
print(hex(zlib.crc32(b"test_input")))
```
바이너리의 목표값과 바로 대조.

**예제 2 — 테이블 지문으로 확정**
IDA Hex View에서 테이블 시작 주소+4바이트를 읽었더니 `96 30 07 77`(리틀엔디안 → `0x77073096`)이었다면 표준 CRC-32 확정.

**예제 3 — 비트 단위 구현, 다항식만으로 확정**
```asm
xor eax, 0EDB88320h
```
이 즉시값 하나만으로도 표준 CRC-32(반사형)임을 바로 알 수 있다.

**예제 4 — 커스텀 초기값 CRC**
```c
unsigned int crc = 0x12345678;   // 표준 0xFFFFFFFF가 아님
for (...) crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8);
// 최종 XOR 없음
```
```python
def crc32_custom(data: bytes) -> int:
    table = [ ... ]  # 바이너리에서 덤프한 256개 테이블
    crc = 0x12345678
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc & 0xFFFFFFFF
```

## 관련 글
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- ./rev-0208-fnv-16777619.md — 16777619 상수가 보일 때 FNV 의심하기
- REV-0205 — Modulo와 오버플로를 이용한 검증
- ../assembly/rev-0062-shr.md — SHR 명령어
- ../assembly/rev-0057-xor.md — XOR 명령어

## 출처/검증
- CRC-32(0xEDB88320 반사형 다항식) 및 테이블 인덱스 1 값(0x77073096)은 zlib 공식 소스코드(`crc32.c`)와 ISO 3309 / ITU-T V.42 CRC-32 표준 정의 기준.
- CRC-32C(Castagnoli, 0x82F63B78)는 RFC 3720(iSCSI) 및 Intel SDM의 SSE4.2 `CRC32` 명령어 설명 기준.
- Python `zlib.crc32()`의 표준 CRC-32 테스트 벡터(`"123456789"` → `0xCBF43926`)는 공개적으로 널리 검증된 CRC-32 참조값 기준(2026-09-08 확인).
