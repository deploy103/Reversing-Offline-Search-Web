---
id: REV-0260
title: "Python으로 Little Endian 변환"
slug: "rev-0260-python-endianness"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python 엔디안 변환", "little endian python", "big endian python", "int.from_bytes", "int.to_bytes", "바이트 순서 변환"]
aliases: ["파이썬 엔디안", "리틀엔디안 빅엔디안 변환 코드", "바이트오더 파이썬"]
symptom_keywords: ["메모리 덤프 바이트 순서 이상함", "값이 거꾸로 읽힘", "hex dump 순서 반대"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
x86/x64는 기본적으로 리틀엔디안이므로 메모리 덤프에서 본 바이트 나열을 사람이 읽는 16진수 값으로 바꾸려면 바이트 순서를 뒤집어야 하며, Python에서는 `int.from_bytes(b, 'little')`과 `int.to_bytes(n, 'little')` 한 줄이면 충분하다.

## 언제 검색해야 하나
- 헥스 덤프에서 `78 56 34 12` 같은 바이트 나열을 보고 "이게 무슨 값이지?" 싶을 때(정답은 `0x12345678`)
- 네트워크 프로토콜이나 파일 포맷 스펙에서 필드가 빅엔디안(network byte order)으로 정의되어 있어 리틀엔디안 CPU와 반대로 다뤄야 할 때
- 직접 만든 XOR/체크섬 계산 결과를 다시 원본 바이너리와 같은 바이트 순서로 저장해야 할 때

## 핵심 개념
"엔디안"은 여러 바이트로 이루어진 정수를 메모리에 저장하는 순서를 말한다.

- **리틀엔디안(little endian)**: 최하위 바이트(LSB)가 가장 낮은 메모리 주소에 저장. x86/x64, ARM(기본 설정)이 이 방식을 쓴다.
- **빅엔디안(big endian)**: 최상위 바이트(MSB)가 가장 낮은 메모리 주소에 저장. 네트워크 프로토콜(TCP/IP 헤더 등)과 일부 파일 포맷, 구형 아키텍처(SPARC, 구형 PowerPC)가 이 방식을 쓴다.

값 `0x12345678`을 4바이트로 저장한다고 하면:
```
리틀엔디안 메모리 나열: 78 56 34 12
빅엔디안   메모리 나열: 12 34 56 78
```
디스어셈블러/디버거의 헥스 덤프 창은 **메모리에 저장된 그대로**의 순서(즉 리틀엔디안이면 뒤집힌 순서)를 보여주므로, 값을 계산하려면 항상 바이트 순서를 다시 맞춰야 한다.

## 화면/코드에서 보이는 징후
- x64dbg/IDA Hex View에서 `mov eax, dword ptr [rbx]`로 로드하는 4바이트가 `AA BB CC DD` 순서로 찍혀 있는데, 실제 `eax` 레지스터 값은 `0xDDCCBBAA`로 표시되는 상황.
- Wireshark나 소켓 덤프에서 포트 번호, 길이 필드 등이 `htons`/`ntohs`로 감싸져 있고 값이 예상과 다르게 나오는 경우 — 네트워크 바이트 순서는 빅엔디안이기 때문.
- PE/ELF 헤더의 매직 넘버나 필드 값이 스펙 문서와 반대로 보이는 경우.

## 가장 먼저 할 것
지금 다루는 값이 **리틀엔디안 메모리에서 읽은 것인지**, 아니면 **이미 사람이 계산한 정수인지**부터 구분한다. 전자라면 `int.from_bytes(..., 'little')`로 정수화, 후자를 다시 메모리 형태 바이트로 만들려면 `int.to_bytes(..., 'little')`을 쓴다.

## 단계별 절차
**1) 표준 라이브러리 방식 (권장)**
```python
data = bytes.fromhex("78563412")

# 바이트 -> 정수
val_le = int.from_bytes(data, 'little')   # 0x12345678
val_be = int.from_bytes(data, 'big')      # 0x78563412

print(hex(val_le), hex(val_be))

# 정수 -> 바이트
n = 0x12345678
b_le = n.to_bytes(4, 'little')   # b'\x78\x56\x34\x12'
b_be = n.to_bytes(4, 'big')      # b'\x12\x34\x56\x78'
```

**2) 부호 있는 값 다루기**
```python
n = -1
b = n.to_bytes(4, 'little', signed=True)   # b'\xff\xff\xff\xff'
back = int.from_bytes(b, 'little', signed=True)  # -1
```
`signed=True`를 빼먹으면 음수에서 `OverflowError: can't convert negative int to unsigned`가 발생한다.

**3) 수동으로 바이트 순서 뒤집기 (라이브러리 없이, 원리 이해용)**
```python
def bytes_to_int_le(b: bytes) -> int:
    result = 0
    for i, byte in enumerate(b):
        result |= byte << (8 * i)     # 낮은 인덱스가 낮은 자리
    return result

def int_to_bytes_le(n: int, size: int) -> bytes:
    return bytes((n >> (8 * i)) & 0xFF for i in range(size))

>>> bytes_to_int_le(bytes.fromhex("78563412"))
305419896      # == 0x12345678
>>> int_to_bytes_le(0x12345678, 4).hex()
'78563412'
```

**4) 단순히 바이트만 뒤집고 싶을 때**
```python
>>> data = bytes.fromhex("78563412")
>>> data[::-1].hex()      # 슬라이싱으로 순서 반전
'12345678'
>>> bytes(reversed(data)).hex()
'12345678'
```
`[::-1]`은 바이트 순서만 뒤집을 뿐 정수로 변환하지는 않는다는 점에 주의한다.

**5) 8바이트(QWORD)와 2바이트(WORD) 확장**
64비트 포인터나 시간값(`time_t`), 16비트 포트 번호처럼 크기가 다른 필드도 원리는 동일하다.
```python
>>> int.from_bytes(bytes.fromhex("0010000000000000"), 'little')   # 8바이트 QWORD
0x1000
>>> int.from_bytes(bytes.fromhex("1f90"), 'big')                  # 2바이트 포트 번호(예: 8080)
8080
```
필드 크기를 헷갈리지 않으려면 항상 "이 필드가 원본 C 구조체에서 몇 바이트짜리 타입이었는가"를 먼저 표로 정리해두는 습관이 중요하다 — `WORD`(2), `DWORD`(4), `QWORD`(8)라는 Windows API 관례 이름도 이런 목적으로 쓰인다.

## 명령어/단축키
- IDA Hex View: 주소 위 우클릭 → `Data` 타입을 `Dword`로 바꾸면 IDA가 자동으로 리틀엔디안 해석한 값을 옆에 보여줌
- x64dbg: 덤프 창에서 4바이트/8바이트 단위 보기(`Dword`/`Qword`)로 전환하면 자동으로 리틀엔디안으로 해석된 값 표시
- Python: `int.from_bytes`, `int.to_bytes`, `struct.pack("<I", n)` (REV-0261 참고)

## 출력 해석
- `int.from_bytes(b, 'little')`의 결과가 상식과 다르게 매우 큰 값이 나온다면, 인자로 넘긴 바이트 길이가 예상보다 길지 않은지(예: 8바이트인데 4바이트로 착각) 확인한다.
- 같은 바이트 4개를 `'little'`과 `'big'` 두 방식으로 각각 변환해 값을 비교해보면, 어느 쪽이 스펙과 맞는지 빠르게 판단할 수 있다 — 파일 포맷 매직 넘버(`b'PE\x00\x00'` 등)처럼 "정답"을 알고 있는 필드로 먼저 검증하는 것이 안전하다.

## 흔한 실수
- `data[::-1]`로 바이트만 뒤집어 놓고 정수로 변환하는 것을 잊어버려서, 그 결과를 그대로 다른 함수에 bytes로 넘기다가 타입 오류가 나는 것.
- 필드 크기(4바이트 vs 8바이트)를 착각해서 `int.from_bytes`에 잘못된 길이의 슬라이스를 넘기는 것 — 항상 오프셋과 크기를 먼저 확정한 뒤 `data[offset:offset+size]`로 정확히 잘라야 한다.
- 네트워크 프로토콜 필드(대부분 빅엔디안)를 습관적으로 `'little'`로 변환해서 완전히 다른 값을 얻는 것.
- `to_bytes()`에서 값이 지정한 바이트 크기를 초과하면 `OverflowError`가 나는데, 이걸 "버그"로 착각하고 예외 처리로 무시해버리는 것 — 사실은 필드 크기 추정이 잘못됐다는 신호다.

## 막혔을 때 다음 체크
- 여러 필드를 한 번에 파싱/조립해야 하면 → REV-0261 (struct pack/unpack)에서 `<`/`>` 포맷 문자로 훨씬 간결하게 처리 가능.
- 엔디안 변환 후 부호 해석까지 필요하면 → REV-0259 (Signed Unsigned 변환)와 함께 사용.
- 엔디안 개념 자체가 헷갈리면 → 기본 개념 정리 글에서 CPU 아키텍처별 기본값을 다시 확인.

## 미니 예제
PE 파일 헤더에서 `e_lfanew` 필드(NT 헤더 오프셋)를 오프셋 `0x3C`에서 4바이트 읽었다고 하자.
```python
with open("target.exe", "rb") as f:
    data = f.read()

offset = int.from_bytes(data[0x3C:0x40], 'little')
print(hex(offset))          # 보통 0x80 근처의 작은 값
print(data[offset:offset+4])  # b'PE\x00\x00' 이 나오면 정상적으로 NT 헤더 시작 지점을 찾은 것
```
이렇게 파일을 통째로 읽어 슬라이싱하고 `int.from_bytes`로 정수화하는 패턴은 PE/ELF 헤더 파싱 스크립트의 기본 골격이다.

같은 방식으로 ELF 헤더도 확인할 수 있다. ELF는 매직 넘버(`7F 45 4C 46`, 즉 `\x7fELF`)로 시작하고, 그 바로 다음 바이트(`EI_CLASS`)가 `1`이면 32비트, `2`면 64비트, 그다음 바이트(`EI_DATA`)가 `1`이면 리틀엔디안, `2`면 빅엔디안임을 스스로 선언한다.
```python
with open("target.elf", "rb") as f:
    data = f.read(16)

assert data[0:4] == b"\x7fELF"
ei_class = data[4]      # 1=32bit, 2=64bit
ei_data = data[5]       # 1=little, 2=big
endian = 'little' if ei_data == 1 else 'big'
print(f"class={ei_class}, endian={endian}")
```
이처럼 파일 포맷 스스로가 엔디안을 명시하는 필드를 갖고 있는 경우도 많으므로, 무작정 `'little'`을 가정하기 전에 헤더에 그런 필드가 있는지부터 확인하는 습관을 들이면 실수를 줄일 수 있다.

### 실전 예제 2 — 게임 세이브 파일의 정수 필드를 읽고, 값을 바꿔서 다시 쓰기
이번엔 PE/ELF 헤더가 아니라, 리버싱 실습에서 자주 만나는 "커스텀 세이브 파일" 형태를 다뤄본다. 파일 앞부분 12바이트에 체력(HP), 골드(Gold), 레벨(Level)이 각각 4바이트 리틀엔디안 정수로 저장되어 있다고 하자.

```python
# 세이브 파일의 앞 12바이트를 그대로 흉내낸 데이터
# HP=100(0x64), Gold=1000(0x3e8), Level=5 가 각각 4바이트 리틀엔디안으로 들어있다
# 12바이트를 4바이트씩 끊어서 보면: 64 00 00 00 | e8 03 00 00 | 05 00 00 00
data = bytes.fromhex("64000000e803000005000000")

# 1) 각 필드를 오프셋과 크기(4바이트씩)에 맞춰 잘라서 정수로 해석
hp = int.from_bytes(data[0:4], "little")      # 첫 4바이트 -> HP
gold = int.from_bytes(data[4:8], "little")    # 다음 4바이트 -> Gold
level = int.from_bytes(data[8:12], "little")  # 마지막 4바이트 -> Level

print("HP:", hp, "Gold:", gold, "Level:", level)   # HP: 100 Gold: 1000 Level: 5

# 2) Gold 값을 99999로 바꾸고, 다시 4바이트 리틀엔디안 바이트로 조립
new_gold_bytes = (99999).to_bytes(4, "little")     # 정수 -> 4바이트 리틀엔디안

# 3) 원본 데이터에서 Gold 필드(오프셋 4~8)만 새 값으로 교체해 새로운 세이브 데이터를 만든다
patched = data[0:4] + new_gold_bytes + data[8:12]
print("패치된 데이터(hex):", patched.hex())

# 4) 실제로 값이 반영됐는지 다시 읽어서 확인
check_gold = int.from_bytes(patched[4:8], "little")
print("패치 후 Gold 확인:", check_gold)   # 99999
```
이 패턴(오프셋과 크기를 정확히 잘라 `int.from_bytes`로 읽고, 값을 바꾼 뒤 `int.to_bytes`로 다시 조립해 원본 자리에 끼워 넣는 것)은 세이브 파일 에디터, 게임 치트, CTF의 파일 포맷 변조 문제에서 그대로 재사용할 수 있는 기본 골격이다.

## 관련 글
- REV-0258 — 리버싱용 Python 숫자 변환 치트시트
- REV-0259 — Python으로 Signed Unsigned 변환
- REV-0261 — Python struct pack unpack
- ../binary-basics/rev-0023-endianness.md

## 출처/검증
- 엔디안 정의와 x86/네트워크 바이트 순서 관례는 Intel SDM 및 RFC 1700(네트워크 바이트 순서 = 빅엔디안) 기준. `int.from_bytes`/`int.to_bytes` API는 Python 공식 문서(builtins int methods) 기준(2026-09-08 확인).
