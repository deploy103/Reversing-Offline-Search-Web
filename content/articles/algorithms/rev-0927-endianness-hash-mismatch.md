---
id: REV-0927
title: "엔디안을 잘못 적용해서 해시 값이 안 맞을 때"
slug: "rev-0927-endianness-hash-mismatch"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, GDB]
keywords: ["해시 엔디안 실수", "4바이트 청크 패킹", "little endian word", "byte order 해시", "테스트 입력 반복문자"]
aliases: ["해시 재구현 엔디안 실수", "청크 엔디안 틀림", "hex(h) 순서가 안 맞음", "워드 조립 순서"]
symptom_keywords: ["같은 문자 반복 입력은 맞는데 다른 문자는 틀림", "4바이트씩 묶어서 처리하는 해시가 안 맞음", "struct pack 순서가 헷갈림", "청크 단위 해시 결과가 다름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
입력을 4바이트(또는 8바이트) 단위로 묶어서 처리하는 해시/체크섬을 재구현했는데 값이 안 맞는다면, 십중팔구 그 청크를 하나의 정수 워드로 조립할 때 **바이트 순서(리틀 엔디안 vs 빅 엔디안)를 반대로 적용**한 것이며, 같은 바이트가 반복되는 테스트 입력(`"AAAA"`)으로는 이 버그가 절대 드러나지 않고 서로 다른 바이트로 구성된 입력(`"ABCD"`)으로 테스트해야만 드러난다는 점이 핵심 함정이다.

## 언제 검색해야 하나
- 입력을 1바이트씩이 아니라 4바이트/8바이트씩 묶어서 처리하는 해시·체크섬 함수를 재구현했는데 결과가 원본과 다를 때
- `struct.unpack`이나 직접 시프트 조합으로 여러 바이트를 하나의 정수로 합치는 코드가 있을 때
- 테스트 입력을 같은 문자 반복(`"AAAA"`, `"1111"`)으로만 썼는데 실제 목표 입력에서는 결과가 다를 때
- 최종 해시값을 바이트 배열로 바꿔서 원본 프로그램의 출력과 비교하는 단계에서 순서가 안 맞을 때

## 핵심 개념
x86/x64는 리틀 엔디안이므로, 원본 C 코드가 `*(uint32_t*)(buf + i*4)`처럼 **메모리를 4바이트 정수로 직접 캐스팅해서 읽으면**, 그 결과는 항상 "메모리상 낮은 주소의 바이트가 정수의 최하위 바이트가 되는" 리틀 엔디안 해석이 자동으로 적용된다. 이를 파이썬으로 옮길 때 `struct.unpack(">I", chunk)`(빅 엔디안)를 쓰거나, 수동으로 `(b[0]<<24)|(b[1]<<16)|(b[2]<<8)|b[3]`(빅 엔디안 방식 조립)을 쓰면 원본과 정반대의 워드 값이 만들어진다.

**이 버그가 테스트에서 숨는 이유**: 만약 테스트 입력이 `"AAAA"`(4바이트 모두 `0x41`)처럼 **같은 바이트가 반복**되면, 리틀 엔디안으로 조립하든 빅 엔디안으로 조립하든 결과 워드는 항상 `0x41414141`로 완전히 동일하다. 즉 이런 입력으로는 엔디안 버그가 있어도 절대 발견할 수 없다. 서로 다른 바이트로 구성된 입력(`"ABCD"` = `0x41 0x42 0x43 0x44`)을 넣어야만 리틀 엔디안 조립 결과(`0x44434241`)와 빅 엔디안 조립 결과(`0x41424344`)가 다르다는 게 드러난다.

**출력 쪽 엔디안도 별개로 확인해야 한다**: 입력을 정확히 리틀 엔디안으로 조립했더라도, 최종 해시값(32비트 정수)을 파일에 쓰거나 바이트 배열로 만들어 원본 프로그램의 출력과 비교하는 단계에서 또 다른 엔디안 선택이 필요하다. 이 두 지점(입력 청크 조립, 출력 직렬화)은 서로 독립적으로 틀릴 수 있으므로 각각 따로 확인해야 한다.

## 화면/코드에서 보이는 징후
```c
// 원본 C: 메모리를 직접 캐스팅해서 4바이트씩 읽음 -> x86에서는 항상 리틀 엔디안
uint32_t word = *(uint32_t*)(data + i * 4);
hash ^= word;
```
```python
# 흔한 실수: 빅 엔디안으로 조립
word = struct.unpack(">I", chunk)[0]     # 틀림
# 또는
word = (chunk[0]<<24)|(chunk[1]<<16)|(chunk[2]<<8)|chunk[3]   # 틀림(빅 엔디안 방식)
```
- 디컴파일 결과에서 4바이트를 한 번에 읽는 캐스팅(`*(DWORD*)`, `*(uint32_t*)`)이 보이는데 파이썬 쪽은 바이트를 하나씩 루프 돌며 시프트로 조립하고 있고, 그 시프트 방향이 원본과 반대인 경우

## 가장 먼저 할 것
같은 바이트가 반복되지 않는 테스트 입력(`"ABCD"`, `b"\x01\x02\x03\x04"` 등)으로 청크 조립 함수만 따로 떼어 실행해서, 리틀 엔디안 결과와 빅 엔디안 결과 중 무엇이 실제 바이너리(디버거로 확인한 `eax` 등)와 일치하는지 직접 비교한다.

## 단계별 절차

**1) 청크 조립 함수를 독립적으로 테스트**
```python
import struct

chunk = b"\x01\x02\x03\x04"
print(hex(struct.unpack("<I", chunk)[0]))   # 0x04030201 (리틀 엔디안)
print(hex(struct.unpack(">I", chunk)[0]))   # 0x01020304 (빅 엔디안)
```

**2) 디버거로 원본이 실제로 만드는 워드값 확인**
```gdb
break hash_loop
run
x/1xw $rdi      # 첫 4바이트를 워드로 읽어 GDB가 보여주는 값 확인
```
GDB의 `x/xw`는 대상 아키텍처(x86/x64, 리틀 엔디안)에 맞게 이미 올바른 정수로 보여주므로, 이 값과 파이썬 조립 결과를 직접 비교한다.

**3) 일치하는 조립 방식으로 전체 재구현**
```python
def bytes_to_words_le(data: bytes):
    return [struct.unpack("<I", data[i:i+4])[0] for i in range(0, len(data), 4)]
```

**4) 출력 직렬화도 별도로 확인**

최종 해시 정수를 원본 프로그램이 어떤 순서로 바이트로 풀어서 출력/비교하는지 확인한다(예: `printf("%08x")`는 그냥 정수를 그대로 hex로 찍는 것이라 엔디안과 무관하지만, `fwrite(&hash, 4, 1, f)`처럼 메모리를 그대로 파일에 쓰면 리틀 엔디안 바이트 순서로 저장된다).
```python
final_bytes_le = struct.pack("<I", h)   # fwrite(&hash, ...)와 동일한 순서
final_hex_str = "%08x" % h              # printf("%08x", hash)와 동일(엔디안 무관)
```

## 명령어/단축키
```python
struct.unpack("<I", b)[0]   # 4바이트 -> 리틀 엔디안 정수
struct.unpack(">I", b)[0]   # 4바이트 -> 빅 엔디안 정수
struct.pack("<I", n)        # 정수 -> 리틀 엔디안 4바이트
int.from_bytes(b, "little") # struct 없이도 동일하게 처리 가능
```
```gdb
x/4xb $rdi     # 바이트 4개를 그대로(순서 그대로) 출력
x/1xw $rdi     # 같은 4바이트를 아키텍처 엔디안에 맞춰 워드로 해석해서 출력
```

## 출력 해석
- `"ABCD"`처럼 서로 다른 바이트로 만든 테스트에서 리틀 엔디안 결과와 빅 엔디안 결과가 다르게 나오고, 그중 하나만 GDB의 `x/xw` 값과 일치한다 — 일치하는 쪽이 정답 방식이다.
- `"AAAA"`류 반복 문자 테스트에서는 두 방식이 항상 같은 값을 내므로, 이 테스트만으로 "맞다"고 판단하면 안 된다.

## 흔한 실수
- 테스트를 항상 같은 문자 반복 문자열(`"AAAA"`, `"1111"`, `"aaaa"`)로만 하고 "잘 되네"라고 넘어가는 것 — 엔디안 버그를 포함해 바이트 순서에 관련된 버그 전반을 숨기는 최악의 테스트 습관이다.
- `struct.unpack`의 포맷 문자에서 `<`/`>`를 빼먹고 시스템 기본값(`@`, 대부분 리틀 엔디안이지만 정렬 규칙이 다를 수 있음)에 의존하는 것 — 항상 명시적으로 `<` 또는 `>`를 쓴다.
- 입력 청크 조립은 맞게 고쳤는데 출력 직렬화 단계의 엔디안은 확인하지 않아서 여전히 최종 비교에서 실패하는 것 — 입력과 출력은 별개로 점검해야 한다.
- 수동으로 시프트 조합(`b[0]<<24 | ...`)을 짤 때 어느 바이트가 최상위인지 매번 헷갈리는 것 — 가능하면 직접 시프트를 짜지 말고 `struct.unpack`/`int.from_bytes`로 엔디안을 명시적으로 선언하는 편이 실수를 줄인다.

## 막혔을 때 다음 체크
- 엔디안 개념 자체가 헷갈린다면 → REV-0023 Little Endian과 Big Endian
- 파일 헥스 덤프의 매직 넘버/상수가 안 맞는 문제라면(이건 해시 계산이 아니라 파일 포맷 문제) → REV-0384 리틀 엔디안 값을 잘못 읽어서 상수 매칭이 안 될 때
- 엔디안 자체가 아니라 32비트 오버플로우 마스킹이 의심된다면 → REV-0926 정수 오버플로를 빼먹어서 계산이 계속 안 맞을 때
- 여전히 어디서 갈라지는지 못 찾겠다면 → REV-0921 알고리즘을 복원했는데 출력이 원본과 안 맞을 때

## 미니 예제
4바이트씩 묶어서 XOR-누산하는 간단한 체크섬을 재구현한다고 하자. 원본은 `*(uint32_t*)`로 메모리를 직접 읽는다(리틀 엔디안).
```python
import struct

def checksum_wrong(data: bytes) -> int:
    h = 0
    for i in range(0, len(data), 4):
        chunk = data[i:i+4].ljust(4, b"\x00")
        word = struct.unpack(">I", chunk)[0]   # 버그: 빅 엔디안으로 조립
        h ^= word
    return h

def checksum_right(data: bytes) -> int:
    h = 0
    for i in range(0, len(data), 4):
        chunk = data[i:i+4].ljust(4, b"\x00")
        word = struct.unpack("<I", chunk)[0]   # 원본과 동일: 리틀 엔디안
        h ^= word
    return h

print(hex(checksum_wrong(b"AAAA")), hex(checksum_right(b"AAAA")))
# 0x41414141 0x41414141  -> 같은 바이트 반복이라 두 방식이 우연히 일치! 버그가 안 보임

print(hex(checksum_wrong(b"ABCD")), hex(checksum_right(b"ABCD")))
# 0x41424344 0x44434241  -> 서로 다른 값! 여기서 비로소 버그가 드러남
```
`"AAAA"`로만 테스트했다면 이 엔디안 버그를 영원히 못 찾았을 것이다. 서로 다른 바이트로 구성된 `"ABCD"`를 넣고서야 두 구현이 다른 값을 낸다는 게 드러나고, GDB로 확인한 실제 워드 값과 대조해서 `checksum_right`(리틀 엔디안)가 정답임을 확정할 수 있다.

### 추가 예제 — XOR가 아니라 "덧셈"으로 워드를 누적하는 체크섬
XOR 기반 체크섬은 엔디안이 틀려도 우연히 값이 맞아떨어지는 경우가 있다(비트 위치만 뒤섞일 뿐 XOR 자체는 순서에 덜 민감하기 때문). 덧셈으로 누적하는 체크섬에서는 엔디안 버그가 훨씬 더 확실하게 드러난다.

```python
import struct  # 바이트 <-> 정수 변환에 사용


def wordsum_wrong(data: bytes) -> int:
    """[틀린 코드] 4바이트 청크를 빅 엔디안으로 잘못 조립해서 더한다."""
    total = 0                                  # 누산값 초기화
    for i in range(0, len(data), 4):           # 4바이트씩 건너뛰며 순회
        chunk = data[i:i + 4]                   # 이번 4바이트를 잘라낸다
        word = struct.unpack(">I", chunk)[0]     # 버그: '>'는 빅 엔디안
        total = (total + word) & 0xFFFFFFFF      # 32비트로 마스킹하며 누적
    return total


def wordsum_right(data: bytes) -> int:
    """[고친 코드] 4바이트 청크를 리틀 엔디안(x86 기본)으로 조립해서 더한다."""
    total = 0
    for i in range(0, len(data), 4):
        chunk = data[i:i + 4]
        word = struct.unpack("<I", chunk)[0]     # 원본과 동일: '<'는 리틀 엔디안
        total = (total + word) & 0xFFFFFFFF
    return total


# 서로 다른 바이트로 구성된 8바이트(2개의 워드) 테스트 데이터
data = bytes.fromhex("0102030405060708")

print("틀린 코드 결과:", hex(wordsum_wrong(data)))   # 0x6080a0c
print("고친 코드 결과:", hex(wordsum_right(data)))   # 0xc0a0806
print("같은 값인가?:", wordsum_wrong(data) == wordsum_right(data))   # False

# 반복 문자로만 테스트하면 이 버그가 숨는다는 것도 함께 확인
rep = b"\x11\x11\x11\x11\x22\x22\x22\x22"
print("반복 문자 입력, 틀린 코드:", hex(wordsum_wrong(rep)))
print("반복 문자 입력, 고친 코드:", hex(wordsum_right(rep)))
print("반복 문자에서는 같은 값인가?:", wordsum_wrong(rep) == wordsum_right(rep))   # True (버그가 숨음!)
```
서로 다른 바이트(`0102030405060708`)를 넣으면 `wordsum_wrong`(`0x6080a0c`)과 `wordsum_right`(`0xc0a0806`)가 완전히 다른 값을 내지만, 반복 문자(`\x11\x11\x11\x11\x22\x22\x22\x22`)를 넣으면 두 함수가 똑같이 `0x33333333`을 반환한다 — 이 두 번째 실행 결과가 바로 "반복 문자 테스트만으로는 엔디안 버그를 절대 찾을 수 없다"는 것을 코드로 직접 증명해준다.

## 관련 글
- REV-0023 — Little Endian과 Big Endian
- REV-0384 — 리틀 엔디안 값을 잘못 읽어서 상수 매칭이 안 될 때
- REV-0926 — 정수 오버플로를 빼먹어서 계산이 계속 안 맞을 때
- REV-0921 — 알고리즘을 복원했는데 출력이 원본과 안 맞을 때

## 출처/검증
- x86/x64가 리틀 엔디안이며 다중 바이트 메모리 캐스팅(`*(uint32_t*)`)이 리틀 엔디안으로 해석된다는 사양: Intel 64 and IA-32 Architectures Software Developer's Manual, Vol.1 "Byte Order" 섹션 기준 (2026-09-09 검증).
- Python `struct` 모듈의 `<`/`>` 포맷 문자와 엔디안 지정: Python 공식 문서(`struct` 모듈) 기준.
