---
id: REV-0877
title: "CRC 다항식 상수 빠른 참조표"
slug: "rev-0877-crc-polynomial-constants"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["CRC32", "CRC16", "CRC-CCITT", "0xEDB88320", "0x04C11DB7", "0x82F63B78", "0xA001", "0x1021", "polynomial", "CRC8"]
aliases: ["crc 다항식 표", "crc32 상수 목록", "crc16 상수", "crc 종류별 다항식"]
symptom_keywords: ["다항식 상수가 여러 개 나와서 헷갈림", "crc32인지 crc16인지 구분이 안됨", "0xa001이 보임", "0x1021이 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
CRC는 비트 폭(8/16/32)과 반사(reflected) 여부에 따라 쓰이는 다항식 상수가 여러 종류로 갈리므로, 코드에 등장하는 정확한 상수값(`0xEDB88320`, `0x04C11DB7`, `0x82F63B78`, `0xA001`, `0x1021` 등)만 보고도 어떤 CRC 변형인지 표로 즉시 식별할 수 있다.

## 언제 검색해야 하나
- REV-0877(본 문서)를 찾기 전에 이미 CRC 계열임은 확인했지만(REV-0209 참고), 정확히 어떤 CRC 변형인지(CRC-32 vs CRC-32C vs CRC-16) 구분이 안 될 때
- 여러 개의 낯선 16비트/32비트 다항식 상수가 코드에 등장해서 어느 것이 표준 CRC인지 헷갈릴 때
- `zlib.crc32`로 계산한 값과 바이너리의 결과가 계속 다르게 나와서 다른 변형(CRC-32C 등)을 의심할 때

## 핵심 개념
CRC는 "반사형(reflected)"과 "정방향(normal)" 두 가지 비트 순서 표현이 있고, 같은 알고리즘이라도 표현 방식에 따라 다항식 상수가 다르게 보인다. 아래는 리버싱에서 실제로 마주치는 대표적인 CRC 상수 목록이다.

**32비트 CRC**
| 상수(hex) | 방향 | 알고리즘 | 비고 |
|---|---|---|---|
| `0xEDB88320` | 반사형 | CRC-32(ISO-HDLC) | zlib/PKZIP/PNG/이더넷 표준. 가장 흔함 |
| `0x04C11DB7` | 정방향 | CRC-32(ISO-HDLC) | 위와 동일 알고리즘, 비트 순서만 반대 |
| `0x82F63B78` | 반사형 | CRC-32C(Castagnoli) | SSE4.2 `CRC32` 명령어, iSCSI/ext4 |
| `0x1EDC6F41` | 정방향 | CRC-32C(Castagnoli) | 위의 정방향 표현 |
| `0x77073096` | - | CRC-32 표준 테이블의 인덱스 1 값 | 테이블 지문(fingerprint)으로 사용 |

**16비트 CRC**
| 상수(hex) | 알고리즘 | 비고 |
|---|---|---|
| `0xA001` | CRC-16/ARC (CRC-16/Modbus 계열) | 반사형, 다항식 `0x8005`의 반사 표현 |
| `0x8005` | CRC-16/IBM 계열 | 정방향 표현 |
| `0x1021` | CRC-16/CCITT-FALSE, CRC-16/XMODEM | 통신/펌웨어에서 흔함 |
| `0x8408` | CRC-16/CCITT 반사형 | `0x1021`의 반사 표현 |

**8비트 CRC**
| 상수(hex) | 알고리즘 | 비고 |
|---|---|---|
| `0x07` | CRC-8(표준) | 정방향, ATM HEC 등에서 사용 |
| `0x31` | CRC-8/MAXIM (1-Wire) | Dallas/Maxim 1-Wire 장치 |

**초기값/최종 XOR도 함께 확인해야 하는 이유**: 다항식이 같아도 초기값(`init`)과 최종 XOR(`xorout`)이 다르면 결과값이 완전히 달라진다. 표준 CRC-32(zlib)는 `init=0xFFFFFFFF`, `xorout=0xFFFFFFFF`를 쓰지만, CRC-32/BZIP2나 CRC-32/MPEG-2처럼 초기값·최종XOR·비트순서 조합이 다른 변형도 있으므로, 다항식 상수 하나만 맞다고 무조건 zlib과 같은 결과가 나오는 건 아니다.

## 화면/코드에서 보이는 징후
```asm
xor     eax, 0EDB88320h     ; CRC-32 반사형
```
```c
crc = (crc >> 1) ^ (0xA001 & -(crc & 1));   // CRC-16 반사형 비트루프
```
```text
crc32     eax, edx           ; SSE4.2 하드웨어 명령어 → CRC-32C(0x82F63B78) 확정
```

## 가장 먼저 할 것
코드에서 발견한 다항식 상수를 위 표와 정확히 대조한다. 표에 없는 낯선 값이면, 온라인 CRC 카탈로그(예: `reveng` 프로젝트의 CRC 카탈로그) 기준의 변형(CRC-32/BZIP2, CRC-32/JAMCRC 등)일 수 있으니 초기값·최종XOR·반사 여부까지 함께 기록해둔다.

## 단계별 절차
**1) 다항식 상수 정확히 읽기** — IDA에서 `H`로 진법 토글해서 오타 없이 확인.

**2) 비트 폭 확인** — 상수가 8/16/32비트 중 어디에 속하는지(레지스터 크기, 마스크 `& 0xFF`/`& 0xFFFF`/`& 0xFFFFFFFF`) 확인.

**3) 위 표와 대조** — 정확히 일치하는 알고리즘 이름을 찾는다.

**4) Python으로 검증**
```python
import zlib
print(hex(zlib.crc32(b"123456789")))       # 0xcbf43926, 표준 CRC-32 테스트 벡터

def crc16_arc(data: bytes) -> int:
    crc = 0x0000
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return crc

print(hex(crc16_arc(b"123456789")))  # 0xbb3d, CRC-16/ARC 테스트 벡터와 대조
```

**5) SSE4.2 CRC32 명령어인 경우** — 이건 반드시 CRC-32C(Castagnoli)이며 zlib의 표준 CRC-32와 다른 알고리즘이므로 `zlib.crc32`가 아니라 `crc32c` 계열 라이브러리로 검증해야 한다.

## 명령어/단축키
- IDA: `H`(진법 토글), `Alt+T`(텍스트 검색으로 다항식 상수 검색)
- Linux: `objdump -d binary | grep -i "crc32"`
- Python: `zlib.crc32(data)`, `import crc8/crcmod` 같은 서드파티 라이브러리로 CRC-8/16 변형 계산

## 출력 해석
- 계산값이 zlib과 안 맞는데 다항식은 `0xEDB88320`이 맞다면, 초기값이나 최종 XOR이 표준(`0xFFFFFFFF`)이 아닌 변형(CRC-32/BZIP2는 `xorout=0`, CRC-32/MPEG-2는 반사되지 않음)일 가능성이 크다.
- CRC-16 계열은 초기값이 `0x0000`이 아니라 `0xFFFF`인 변형(CRC-16/CCITT-FALSE)도 흔하니 결과가 안 맞으면 초기값부터 바꿔서 재시도.

## 흔한 실수
- 다항식 상수 하나만 일치하면 무조건 zlib과 같은 CRC-32라고 단정하는 것 — 초기값/최종XOR/비트순서까지 모두 같아야 동일한 결과가 나온다.
- CRC-32와 CRC-32C를 다항식 숫자만 비슷해 보인다고 혼동하는 것(`0xEDB88320` vs `0x82F63B78`) — 완전히 다른 알고리즘이며 SSE4.2 `crc32` 명령어는 항상 CRC-32C다.
- CRC-16 계열에서 반사형(`0xA001`)과 정방향(`0x8005`) 상수를 같은 알고리즘의 다른 표현이 아니라 서로 다른 알고리즘으로 착각하는 것.

## 막혔을 때 다음 체크
- CRC의 테이블 기반/비트 단위 구현 자체를 식별하는 기초는 → REV-0209 — CRC 계열 알고리즘 흔적 찾기.
- 곱셈 상수 위주의 해시(FNV)와 헷갈리면 → REV-0208 — 16777619 상수가 보일 때 FNV 의심하기.
- 암호학적 해시(MD5/SHA류) 상수와 헷갈리면 → REV-0876 — 해시 함수 매직 상수 빠른 참조(MD5/SHA1/SHA256 초기값).

## 미니 예제
바이너리에서 다음 즉시값을 발견했다:
```asm
mov     eax, 8408h
```
위 표에서 `0x8408`은 CRC-16/CCITT의 반사형 표현이다. Python으로 재현:
```python
def crc16_ccitt_reflected(data: bytes, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF
```
계산 결과를 바이너리의 비교 상수와 대조해서 초기값(`0xFFFF` 또는 `0x0000`)을 조정하며 일치시킨다.

## 관련 글
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- REV-0208 — 16777619 상수가 보일 때 FNV 의심하기
- REV-0876 — 해시 함수 매직 상수 빠른 참조(MD5/SHA1/SHA256 초기값)
- REV-0885 — 알고리즘 유형별 판별 체크리스트

## 출처/검증
- CRC-32(0xEDB88320/0x04C11DB7) 및 테이블 인덱스 1 값(0x77073096): zlib 공식 소스코드(`crc32.c`) 및 ISO 3309 / ITU-T V.42 표준 기준 (2026-09-09 검증).
- CRC-32C(0x82F63B78/0x1EDC6F41, Castagnoli): RFC 3720(iSCSI) 및 Intel SDM SSE4.2 CRC32 명령어 설명 기준.
- CRC-16/ARC(0xA001/0x8005), CRC-16/CCITT(0x1021/0x8408), CRC-8 계열: Anycrc/CRC RevEng 공개 CRC 카탈로그("A catalogue of parametrised CRC algorithms") 기준 표준 테스트 벡터와 대조 (2026-09-09 검증).
