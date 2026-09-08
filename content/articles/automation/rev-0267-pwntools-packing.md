---
id: REV-0267
title: "pwntools p32 p64 u32 u64"
slug: "rev-0267-pwntools-packing"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, pwntools]
keywords: ["p32", "p64", "u32", "u64", "pwntools 패킹", "little endian", "struct.pack", "바이트 순서", "정수 바이트열 변환"]
aliases: ["pwntools pack unpack", "정수 바이트 변환 함수", "p32 u32 차이", "엔디안 변환 pwntools"]
symptom_keywords: ["p32 u32 차이 모르겠음", "주소를 바이트열로 어떻게 바꿈", "little endian 헷갈림", "struct pack 대신 pwntools", "pwntools 패킹 함수 정리"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`pwntools`의 `p32`/`p64`(pack)와 `u32`/`u64`(unpack)는 파이썬 정수와 32/64비트 바이트열을 서로 변환해주는 헬퍼 함수로, 기본적으로 x86/x64에서 흔한 **리틀 엔디안(little-endian)** 순서를 쓰기 때문에 `sendline()`에 주소나 정수를 실어 보낼 때 `struct.pack`을 직접 쓰지 않아도 되게 해준다.

## 언제 검색해야 하나
- 리버싱한 바이너리에 4바이트/8바이트짜리 정수 값(주소, 매직 넘버, 체크섬 등)을 바이트열로 만들어 보내야 할 때
- 라이트업 코드에서 `p32(addr)`나 `u64(data)` 같은 함수를 봤는데 무슨 뜻인지 모를 때
- 리틀 엔디안/빅 엔디안 순서가 헷갈려서 값이 이상하게 들어가는 것 같을 때
- `struct.pack('<I', x)`를 매번 쓰는 게 번거로워서 더 짧은 방법을 찾을 때

## 핵심 개념
CPU가 메모리에 여러 바이트짜리 정수를 저장하는 방식에는 크게 두 가지가 있다. **리틀 엔디안**은 최하위 바이트(LSB)를 가장 낮은 주소에 저장하고, **빅 엔디안**은 최상위 바이트(MSB)를 가장 낮은 주소에 저장한다. x86과 x64는 리틀 엔디안을 쓰므로, 정수 `0x12345678`은 메모리에 `78 56 34 12` 순서로 저장된다. 리버싱 중에 헥스 덤프나 스택 값을 볼 때 "숫자가 거꾸로 보인다"고 느끼는 이유가 바로 이것이다.

`pwntools`는 이 변환을 함수 네 개로 캡슐화했다.

- **`p32(n)`** — 파이썬 정수 `n`을 4바이트(32비트) 바이트열로 "패킹(packing)"한다. 기본 엔디안은 리틀 엔디안이다.
- **`p64(n)`** — 파이썬 정수 `n`을 8바이트(64비트) 바이트열로 패킹한다.
- **`u32(data)`** — 4바이트 바이트열 `data`를 파이썬 정수로 "언패킹(unpacking)"한다.
- **`u64(data)`** — 8바이트 바이트열 `data`를 파이썬 정수로 언패킹한다.

이 네 함수는 사실 파이썬 표준 라이브러리 `struct` 모듈의 `struct.pack('<I', n)` / `struct.unpack('<I', data)[0]`을 짧게 감싼 것에 가깝다. 다만 pwntools 버전은 이름이 짧고, `context.arch`/`context.endian` 전역 설정과 연동되어 있어 아키텍처를 한 번만 지정하면 이후 코드 전체에서 일관되게 동작한다는 장점이 있다.

리버싱 자동화에서 이 함수들이 왜 중요한가 하면, 바이너리에 값을 넣을 때 사람이 읽는 형태(파이썬 정수 `4276993775`)와 프로그램이 메모리에서 실제로 기대하는 바이트 순서가 다르기 때문이다. `scanf("%d")`처럼 텍스트로 숫자를 읽는 함수라면 문자열로 `sendline(b'42')`를 보내면 되지만, `read()`나 `fread()`로 raw 바이트를 그대로 구조체에 채워 넣는 함수, 혹은 리버싱해서 알아낸 4바이트 매직 값(예: 파일 헤더 서명)을 그대로 재현해야 하는 경우에는 `p32`/`p64`로 정확한 바이트 순서를 맞춰 보내야 검증을 통과한다.

## 화면/코드에서 보이는 징후
- `p.sendline(p32(0x1337))`처럼 `sendline()` 인자로 정수가 아니라 `p32(...)`로 감싼 결과가 들어간다.
- 리버싱 중 IDA/Ghidra에서 본 4바이트 상수(`cmp eax, 0xDEADBEEF` 같은)를 코드로 재현할 때 `p32(0xDEADBEEF)`가 등장한다.
- 함수 주소나 스택 카나리 같은 8바이트 값을 다룰 때는 `p64`/`u64`가 쓰인다.
- 서버에서 받은 응답을 정수로 해석할 때 `leaked = u64(p.recv(8))`처럼 `recv()` 결과를 바로 `u32`/`u64`에 넘긴다.
- 코드 어딘가에 `context.arch = 'amd64'` 또는 `context.arch = 'i386'`을 설정해서 이후 `pack()`/`unpack()`(범용 함수)의 기본 크기를 맞추는 경우도 있다.

## 가장 먼저 할 것
대상 프로그램이 값을 어떤 방식으로 읽는지부터 확인한다. 소스코드나 디스어셈블리에서 `scanf`, `atoi` 계열이면 텍스트(문자열)로 보내야 하고, `read`/`fread`/구조체 통째로 읽는 코드라면 `p32`/`p64`로 만든 raw 바이트를 보내야 한다. 이 구분을 먼저 하지 않으면 값을 아무리 정확히 계산해도 형식이 달라 검증에 실패한다.

## 단계별 절차

**1) 기본 패킹/언패킹 사용**

```python
from pwn import *

# 정수 -> 4바이트 리틀 엔디안 바이트열
data = p32(0x1337)
print(data)          # b'7\x13\x00\x00'

# 정수 -> 8바이트 리틀 엔디안 바이트열
data64 = p64(0xdeadbeefcafebabe)
print(data64)         # b'\xbe\xba\xfe\xca\xef\xbe\xad\xde'

# 바이트열 -> 정수
n = u32(b'7\x13\x00\x00')
print(hex(n))          # 0x1337

n64 = u64(b'\xbe\xba\xfe\xca\xef\xbe\xad\xde')
print(hex(n64))         # 0xdeadbeefcafebabe
```

**2) 실제 송수신에 결합하기**

```python
from pwn import *

p = process('./chall')

# 리버싱으로 알아낸 4바이트 매직 값을 그대로 재현해서 전송
magic = 0xCAFEBABE
p.send(p32(magic))

# 서버가 8바이트 주소 값을 흘려주는(leak) 경우, 그대로 정수로 변환
leaked_bytes = p.recv(8)
leaked_addr = u64(leaked_bytes)
print('leaked address:', hex(leaked_addr))

p.close()
```

**3) 빅 엔디안이 필요한 특수 케이스**

네트워크 프로토콜이나 일부 임베디드/특수 아키텍처 문제는 빅 엔디안을 쓴다. 이때는 `endian` 인자를 명시하거나 `context.endian`을 바꾼다.

```python
from pwn import *

# 이 호출 하나만 빅 엔디안으로
data_be = p32(0x1337, endian='big')
print(data_be)  # b'\x00\x00\x13\x37'

# 이후 코드 전체를 빅 엔디안 기본값으로
context.endian = 'big'
print(p32(0x1337))  # b'\x00\x00\x13\x37'
```

**4) `struct`와 비교**

`pwntools` 없이 표준 라이브러리만으로 같은 일을 하면 다음과 같다. 두 코드는 동일한 결과를 낸다.

```python
import struct
data = struct.pack('<I', 0x1337)   # p32(0x1337)와 동일
n = struct.unpack('<I', data)[0]   # u32(data)와 동일
```

## 명령어/단축키
- `p8(n)` / `p16(n)` / `p32(n)` / `p64(n)` : 1/2/4/8바이트 리틀 엔디안 패킹(기본값)
- `u8(data)` / `u16(data)` / `u32(data)` / `u64(data)` : 대응하는 언패킹
- `p32(n, endian='big')` : 특정 호출만 빅 엔디안으로 변경
- `context.endian = 'big'` / `context.arch = 'amd64'` : 전역 기본값 설정
- `pack(n, word_size=32)` : 범용 패킹 함수(크기를 인자로 지정)

## 출력 해석
- `p32(x)` 결과가 `b'\x00\x00\x00\x00'`처럼 전부 0이면 `x`가 0이거나, `x`에 넣은 변수가 의도한 값으로 계산되지 않았을 가능성이 크다 — `hex(x)`로 원래 정수를 먼저 확인한다.
- `u32()`/`u64()`에 넘긴 바이트열의 길이가 4/8이 아니면 `error: unpack requires a buffer of N bytes` 같은 예외가 발생한다. `recv()`로 받은 바이트 수가 기대와 다를 수 있으니 `len(data)`를 먼저 찍어본다.
- `p32(n)`에 32비트로 표현 안 되는 큰 정수(예: `2**32` 이상)를 넣으면 `error: number too large` 같은 예외가 난다 — 이 경우 `p64`가 필요한 값을 `p32`에 잘못 넣은 건 아닌지 확인한다.
- 값이 "거꾸로" 들어간 것처럼 보이면 대부분 엔디안 문제다 — 리틀 엔디안 결과를 손으로 읽을 때는 바이트 순서를 뒤집어서 읽어야 원래 정수가 보인다는 점을 기억한다.

## 흔한 실수
- 4바이트 값에 `p64`를 쓰거나 8바이트 값에 `p32`를 써서 크기가 안 맞는 데이터를 보내는 경우 — 대상 프로그램의 구조체 필드 크기를 정확히 확인해야 한다.
- 엔디안을 신경 안 쓰고 헥스 덤프에서 본 바이트 순서를 그대로 파이썬 정수 리터럴로 옮겨 적어서 값이 뒤집히는 경우 — 헥스 덤프에서 `78 56 34 12`로 보였다면 실제 정수는 `0x12345678`이지 `0x78563412`가 아니다(리틀 엔디안이라면).
- `u32()`/`u64()` 대신 `int.from_bytes(data, 'little')`를 섞어 쓰다가 엔디안 인자를 빼먹어 기본값(빅 엔디안)으로 해석해버리는 경우 — 파이썬 표준 `int.from_bytes`의 기본 동작과 pwntools의 기본 동작(리틀 엔디안)이 다르다는 점에 주의해야 한다.
- `p32`가 반환하는 것은 바이트열이지 문자열이 아닌데, 이를 `str()`로 감싸거나 문자열과 `+` 연산해서 타입 에러를 내는 경우.

## 막혔을 때 다음 체크
- 값이 계속 이상하게 전달된다면 → `context.log_level = 'debug'`로 실제 전송 바이트를 눈으로 확인하고, 기대한 바이트 순서와 비교한다.
- 프로세스 실행/입출력 자체가 익숙하지 않다면 → REV-0266 문서에서 `process()`/`sendline()`/`recvline()` 기본기를 먼저 확인한다.
- 검증 로직에서 8비트/32비트 오버플로우가 섞여 있어서 패킹한 값이 예상과 다르게 검증되는 것 같다면 → REV-0270 문서에서 Z3로 비트 폭을 정확히 모델링하는 방법을 참고한다.
- 오프라인 환경에서 `pip install pwntools`가 막혀 있다면 → 툴킷 카테고리(`../tools/`, 추후 작성)에서 오프라인 설치 절차를 참고한다.

## 미니 예제
4바이트 매직 값 `0xCAFEBABE`를 검사하는 아주 단순한 대상 프로그램을 가정한다.

```c
// magic.c
#include <stdio.h>
#include <unistd.h>
int main() {
    unsigned int magic;
    read(0, &magic, 4);  // raw 4바이트를 그대로 읽음
    if (magic == 0xCAFEBABE) printf("Correct!\n");
    else printf("Wrong\n");
    return 0;
}
```

```python
# solve.py
from pwn import *

p = process('./magic')
p.send(p32(0xCAFEBABE))   # 문자열이 아니라 raw 4바이트를 그대로 전송
print(p.recvline())        # b'Correct!\n'
p.close()
```

이 예제는 `scanf`가 아니라 `read()`로 raw 바이트를 읽는 프로그램이므로, 텍스트 `b'3405691582'`를 보내면 실패하고 반드시 `p32()`로 패킹한 4바이트를 보내야 통과한다는 점이 핵심이다.

## 관련 글
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기
- REV-0270 — Z3에서 8비트 32비트 Overflow 다루기
- REV-0272 — Capstone으로 디스어셈블 자동화

## 출처/검증
- `pwntools` 공식 문서(docs.pwntools.com)의 `pwnlib.util.packing` 모듈(`p8/p16/p32/p64`, `u8/u16/u32/u64`)을 기준으로 정리했다(2026-09-08 검증).
- x86/x64가 리틀 엔디안을 사용한다는 사실은 Intel/AMD 아키텍처 매뉴얼의 일반적인 서술과 일치한다.
- `pwntools`는 서드파티 패키지이므로 `pip install pwntools`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제는 `pip install pwntools` 환경의 표준 CPython 3에서 그대로 재현 가능하다.
