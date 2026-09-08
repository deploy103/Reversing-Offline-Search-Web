---
id: REV-0261
title: "Python struct pack unpack"
slug: "rev-0261-python-struct"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python struct 모듈", "struct.pack", "struct.unpack", "struct 포맷 문자", "python 바이너리 구조체 파싱"]
aliases: ["파이썬 struct 사용법", "struct pack unpack 치트시트", "python 바이너리 필드 파싱"]
symptom_keywords: ["struct.error 발생", "unpack requires a buffer", "구조체 필드 파싱 어떻게", "C 구조체 파이썬으로 읽기"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
C의 `struct`처럼 여러 필드가 섞인 바이너리 데이터를 다룰 때는 `struct.pack`/`struct.unpack`에 포맷 문자열(`'<I'`, `'>H'` 등)만 넘기면 엔디안 변환과 타입 변환을 한 번에 처리할 수 있다.

## 언제 검색해야 하나
- PE/ELF 헤더처럼 여러 크기의 필드(1/2/4/8바이트)가 연속으로 붙어 있는 바이너리를 파싱해야 할 때
- CTF 문제 서버와 소켓 통신하면서 길이 필드, 시퀀스 번호 등을 정해진 바이트 수로 인코딩/디코딩해야 할 때
- `int.from_bytes`를 필드마다 반복해서 쓰는 게 번거로울 때 — `struct`는 한 번의 호출로 여러 필드를 동시에 풀 수 있다

## 핵심 개념
`struct` 모듈은 파이썬 값(정수, 실수, 바이트열)과 C 스타일 바이너리 표현 사이를 변환하는 표준 라이브러리다. 포맷 문자열은 크게 두 부분으로 이루어진다.

1. **바이트 순서 지시자(선두 1글자, 생략 가능)**
   - `<` : 리틀엔디안, 패딩 없음
   - `>` : 빅엔디안, 패딩 없음
   - `!` : 네트워크 바이트 순서(빅엔디안과 동일), 패딩 없음
   - `=` : 네이티브 바이트 순서, 패딩 없음
   - (지시자 생략 시) : 네이티브 바이트 순서 + 네이티브 정렬/패딩 적용 — CTF/리버싱에서는 거의 항상 원치 않는 동작이므로 **항상 `<` 또는 `>`를 명시하는 것이 안전**하다.

2. **타입 문자(반복 가능)**

| 문자 | C 타입 | 크기 | 부호 |
|---|---|---|---|
| `b` | signed char | 1 | 있음 |
| `B` | unsigned char | 1 | 없음 |
| `h` | short | 2 | 있음 |
| `H` | unsigned short | 2 | 없음 |
| `i` | int | 4 | 있음 |
| `I` | unsigned int | 4 | 없음 |
| `q` | long long | 8 | 있음 |
| `Q` | unsigned long long | 8 | 없음 |
| `f` | float | 4 | - |
| `d` | double | 8 | - |
| `s` | char[] (바이트열) | 앞에 숫자로 길이 지정 | - |

## 화면/코드에서 보이는 징후
Ghidra/IDA 디컴파일 결과에 `struct`나 `typedef struct { ... }` 형태로 필드가 정의되어 있고, 각 필드가 `DWORD`, `WORD`, `BYTE`, `QWORD` 같은 고정 크기 타입으로 선언된 코드를 만나면 `struct.pack`/`unpack`으로 그대로 옮겨 쓸 수 있는 신호다.

## 가장 먼저 할 것
필드들의 **순서, 크기, 부호 유무, 엔디안**을 표로 정리한다. 이 네 가지만 정확하면 포맷 문자열은 기계적으로 만들어진다.

## 단계별 절차
**1) 단일 값 pack/unpack**
```python
import struct

# 정수 -> 바이트
b = struct.pack('<I', 0x1337)          # b'\x37\x13\x00\x00'
b2 = struct.pack('>I', 0x1337)         # b'\x00\x00\x13\x37'

# 바이트 -> 정수 (unpack은 항상 튜플을 반환하므로 [0]으로 꺼냄)
val = struct.unpack('<I', b)[0]        # 0x1337
```

**2) 여러 필드를 한 번에**
```python
# C 구조체: struct Header { uint32_t magic; uint16_t ver; uint16_t flags; };
data = struct.pack('<IHH', 0xDEADBEEF, 1, 0x8000)
magic, ver, flags = struct.unpack('<IHH', data)
print(hex(magic), ver, hex(flags))
```

**3) 반복 개수와 문자열 필드**
```python
# 4바이트짜리 필드 3개를 한 번에
xs = struct.unpack('<3I', struct.pack('<3I', 1, 2, 3))   # (1, 2, 3)

# 고정 길이 바이트열 ('s' 앞의 숫자가 길이)
name = struct.pack('<8s', b'flag.txt')   # 8바이트, 부족하면 \x00으로 채움
print(name)                              # b'flag.txt'
```

**4) 파일에서 구조체 읽기 (calcsize로 크기 미리 계산)**
```python
fmt = '<IHH'
size = struct.calcsize(fmt)    # 8 (4+2+2, 패딩 없음)

with open("target.bin", "rb") as f:
    data = f.read(size)
magic, ver, flags = struct.unpack(fmt, data)
```

**5) 가변 길이 데이터를 반복 unpack (struct.iter_unpack)**
```python
# 4바이트 정수가 여러 개 연달아 있는 데이터를 순회
blob = struct.pack('<5I', 10, 20, 30, 40, 50)
for (val,) in struct.iter_unpack('<I', blob):
    print(val)
```

## 명령어/단축키
- `struct.calcsize(fmt)` : 포맷이 차지하는 바이트 수를 미리 계산해서 `f.read(size)`와 짝지어 쓰면 안전
- `struct.unpack_from(fmt, buffer, offset)` : 슬라이싱 없이 특정 오프셋부터 바로 unpack
- REPL에서 `import struct; help(struct)`로 전체 포맷 문자 표 확인 가능

## 출력 해석
- `struct.error: unpack requires a buffer of N bytes`가 뜨면 포맷 문자열이 요구하는 바이트 수와 실제로 넘긴 데이터 길이가 다르다는 뜻이다 — `struct.calcsize(fmt)`로 요구 크기를 확인하고 슬라이싱 범위를 다시 맞춘다.
- `unpack`은 필드가 하나여도 항상 튜플을 반환한다. `val = struct.unpack('<I', b)`처럼 `[0]`을 빼먹으면 `val`이 정수가 아니라 `(0x1337,)` 같은 튜플이 되어 이후 산술 연산에서 `TypeError`가 난다.
- 포맷 문자열에 엔디안 지시자가 없으면 네이티브 정렬(패딩)이 적용되어 `calcsize` 결과가 필드 크기 합과 다르게 나올 수 있다 — 리버싱에서는 항상 `<` 또는 `>`를 명시해 패딩을 없애는 것이 기본이다.

## 흔한 실수
- 엔디안 지시자를 빼먹고 기본(네이티브) 포맷을 쓰다가, 실행 환경에 따라 결과가 다르게 나오거나 패딩 때문에 `calcsize`가 예상보다 커지는 것.
- `'s'` 포맷 앞의 숫자를 반복 개수로 착각하는 것 — `'4s'`는 "4바이트 문자열 1개"이지 "1바이트 문자열 4개"(`'ssss'`와 다름)가 아니다.
- `pack`에 넘기는 값이 포맷이 표현할 수 있는 범위를 초과했는데(`I`인데 음수, `B`인데 300 이상) 이를 무시하고 넘기다가 `struct.error: argument out of range`를 만나는 것.
- 여러 필드를 언팩한 결과 튜플의 순서를 착각해서 엉뚱한 변수에 엉뚱한 값을 대입하는 것 — 구조체 정의 순서와 포맷 문자열 순서, 언패킹 변수 순서 세 가지가 항상 일치해야 한다.

## 막혔을 때 다음 체크
- 엔디안 지시자(`<`/`>`)의 의미 자체가 헷갈리면 → REV-0260 (Python으로 Little Endian 변환).
- 부호 있는/없는 포맷 문자(`i` vs `I`)를 헷갈려서 값이 음수/양수로 반대로 나오면 → REV-0259 (Signed Unsigned 변환).
- struct로 필드를 다 풀어냈는데 그 안에 XOR로 암호화된 값이 있다면 → REV-0262 (XOR 역산 템플릿).

## 미니 예제
CTF 문제 서버가 다음과 같은 4바이트 리틀엔디안 길이 + 가변 길이 페이로드 프로토콜을 쓴다고 하자.
```python
import struct

def send_msg(sock, payload: bytes):
    header = struct.pack('<I', len(payload))
    sock.sendall(header + payload)

def recv_msg(sock) -> bytes:
    header = sock.recv(4)
    (length,) = struct.unpack('<I', header)
    data = b""
    while len(data) < length:
        data += sock.recv(length - len(data))
    return data
```
이 패턴은 CTF pwn/rev 문제의 네트워크 프로토콜 클라이언트를 작성할 때 그대로 재사용할 수 있는 뼈대다.

## 관련 글
- REV-0258 — 리버싱용 Python 숫자 변환 치트시트
- REV-0259 — Python으로 Signed Unsigned 변환
- REV-0260 — Python으로 Little Endian 변환
- REV-0262 — Python XOR 역산 템플릿

## 출처/검증
- `struct` 모듈 포맷 문자 표와 동작은 Python 공식 문서(`struct — Interpret bytes as packed binary data`) 기준(2026-09-08 확인). 예제 코드는 모두 CPython 3.x 표준 라이브러리만으로 동작을 검증함.
