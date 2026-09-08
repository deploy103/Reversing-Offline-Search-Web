---
id: REV-0406
title: "BSWAP: 바이트 순서 반전"
slug: "rev-0406-bswap"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - bswap
  - BSWAP
  - Bswap
  - bswap 명령어
  - bswap instruction
  - byte swap
  - 바이트 스왑
  - 바이트 순서 반전
  - endian swap
  - endianness conversion
  - 엔디안 변환
  - big endian little endian
  - htonl
  - ntohl
  - htons
  - ntohs
  - "bswap eax"
  - "bswap rax"
  - network byte order
  - 네트워크 바이트 순서
aliases:
  - bswap 뭐임
  - bswap이 뭐죠
  - bswap 명령
  - BSWAP 명령어
  - 바이트스왑 명령어
  - 엔디안 뒤집기 명령어
symptom_keywords:
  - 리틀 엔디안 빅 엔디안 변환 코드
  - htonl ntohl이 어셈블리에서 어떻게 보이는지
  - 해시 함수에 bswap이 왜 나오는지
  - 파일 포맷 길이 필드가 이상하게 보일 때
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`BSWAP`(Byte Swap)은 32비트 또는 64비트 레지스터 안의 바이트 순서를 통째로 뒤집는 명령어로, 리틀 엔디안과 빅 엔디안 표현을 서로 변환할 때(네트워크 프로토콜, 특정 파일 포맷, 일부 해시 알고리즘) 사용된다.

## 언제 검색해야 하나
- `bswap eax`, `bswap rax` 같은 코드를 만났는데 이게 곱셈/시프트와 무슨 관계인지 헷갈릴 때
- 네트워크 패킷 파싱 코드에서 `htonl`/`ntohl` 호출이 어셈블리 레벨에서 어떻게 보이는지 궁금할 때
- SHA류 해시 함수나 PNG/ZIP 같은 파일 포맷 파서 코드에서 정체불명의 바이트 재배열 명령을 만났을 때
- 상수 값이 파일에서 읽은 값과 바이트 순서가 반대로 보여서 헷갈릴 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
BSWAP r32
BSWAP r64   (REX.W 접두사 필요, x64)
```
- 오퍼랜드는 반드시 **레지스터** 하나뿐이다 — 메모리 오퍼랜드는 지원하지 않는다.
- 16비트 오퍼랜드(`BSWAP ax`)는 정의되어 있지 않다(결과가 구현에 따라 다르며 보통 레지스터가 0이 되어버리므로 실전에서 절대 쓰지 않는다). 16비트 바이트 스왑이 필요하면 `xchg al, ah` 또는 `rol ax, 8`을 대신 쓴다.

### 실제로 하는 일 — 바이트 위치를 완전히 반전
32비트 레지스터라면 4개 바이트의 순서를 정확히 거꾸로 뒤집는다(바이트0↔바이트3, 바이트1↔바이트2). 64비트라면 8개 바이트를 거꾸로 뒤집는다(바이트0↔바이트7, 바이트1↔바이트6, 바이트2↔바이트5, 바이트3↔바이트4).
```
eax = 0x12 34 56 78   (메모리 관점 바이트: 78 56 34 12, 리틀엔디안)
bswap eax
eax = 0x78 56 34 12
```
[ROL](rev-0064-rol.md)로 8비트씩 회전하는 것과 결과가 비슷해 보일 수 있지만, `ROL eax, 8`은 4바이트를 한 칸씩 순환시킬 뿐 완전히 반전시키지 않는다는 점에서 다르다. BSWAP은 "정확히 거울처럼 뒤집기"이고, ROL/ROR은 "회전"이다.

### 플래그 변화
**어떤 플래그도 바꾸지 않는다.** CF, ZF, SF, OF, PF, AF 모두 영향받지 않는다.

### signed/unsigned 관점
바이트 순서 반전은 값을 순수한 바이트 배열로 다루는 연산이라 signed/unsigned 구분이 의미 없다. 부호 비트가 어느 바이트에 있었든 그 바이트 자체가 통째로 옮겨질 뿐이다.

### 스택/RSP/RIP 변화
없음. 레지스터 안에서만 일어나는 연산이다.

### 왜 필요한가 — 엔디안 문제
x86/x64는 **리틀 엔디안**(최하위 바이트가 낮은 메모리 주소에 저장)이다. 하지만 다음과 같은 상황에서는 값을 **빅 엔디안**(네트워크 바이트 순서)으로 다뤄야 한다:
- **네트워크 프로토콜**: TCP/IP 헤더의 포트 번호, 길이 필드 등은 관례적으로 빅 엔디안으로 정의된다. C의 `htonl()`/`ntohl()`(32비트), `htons()`/`ntohs()`(16비트) 함수가 이 변환을 담당하며, x86/x64에서는 내부적으로 `BSWAP`(32/64비트) 또는 `XCHG al, ah`/`ROL ax, 8`(16비트)로 컴파일되는 경우가 많다.
- **해시 알고리즘**: SHA-1/SHA-256 같은 표준은 메시지를 빅 엔디안 32/64비트 워드로 처리하도록 정의되어 있다. 리틀 엔디안 CPU에서 이를 구현하면 데이터를 읽은 직후 `bswap`으로 바이트 순서를 맞추는 코드가 라운드 함수 앞에 반복적으로 나타난다.
- **일부 파일 포맷**: PNG의 청크 길이 필드, 자바 클래스 파일, 일부 바이너리 프로토콜은 빅 엔디안 정수를 쓴다.

### 컴파일러 패턴
- MSVC: `_byteswap_ulong(x)`(32비트), `_byteswap_uint64(x)`(64비트) 내장 함수
- GCC/Clang: `__builtin_bswap32(x)`, `__builtin_bswap64(x)`
- `htonl`/`ntohl` 매크로/함수도 x86 리눅스/윈도우에서 최종적으로 `bswap`으로 귀결되는 경우가 흔하다(단, 인라인 함수 최적화 여부에 따라 실제 함수 호출로 남을 수도 있다).

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays(IDA) 디컴파일러는 `bswap`을 `__ROL4__`/`__ROL8__` 조합이 아니라 대개 `_byteswap_ulong(x)` 또는 `__builtin_bswap32(x)` 형태로 정리해서 보여준다. 만약 그런 이름 없이 순수 어셈블리만 본다면, "4/8바이트가 완전히 거꾸로 뒤집힌다"는 사실 자체로 엔디안 변환임을 알아챌 수 있어야 한다.

### 리버싱 의미
`BSWAP`을 발견하면 다음을 의심할 수 있다:
1. 네트워크 코드(소켓 프로그래밍, 패킷 파싱/생성) — 특히 `recv`/`send` 근처
2. 해시/체크섬 계산(SHA류) — 루프 안에서 데이터를 읽자마자 반복적으로 나타남
3. 파일 포맷 파서 — 특정 필드를 읽은 직후 값이 상식과 다르게 보이면 빅 엔디안 필드일 가능성

## 화면/코드에서 보이는 징후
- `bswap eax` — 32비트 레지스터 바이트 순서 반전
- `bswap rax` — 64비트 레지스터 바이트 순서 반전
- 값을 메모리에서 읽자마자(`mov`) 곧바로 `bswap`이 따라오는 패턴 — 파일/네트워크에서 읽은 빅 엔디안 값을 리틀 엔디안으로 변환
- 해시 함수 라운드 루프 안에서 데이터 로드 직후 반복되는 `bswap`

## 가장 먼저 할 것
1. `bswap` 앞뒤로 어디서 값을 읽고(`mov`, `recv`, 파일 읽기) 어디에 쓰는지 확인한다.
2. 소켓 관련 API(`recv`, `send`, `htonl`, `ntohl`) 근처인지, 해시 루프 안인지 먼저 구분한다.
3. 반전 전/후 값을 16진수로 적어 비교해보면 실제로 바이트가 거꾸로 뒤집혔는지 눈으로 확인할 수 있다.

## 단계별 절차

**1) 단순 반전 확인**
```asm
mov  eax, [rdi]     ; 파일/네트워크에서 읽은 원시 값 (빅 엔디안일 수 있음)
bswap eax             ; 리틀 엔디안 CPU가 이해할 수 있는 순서로 변환
```

**2) htonl 스타일 패턴 인식**
```asm
mov  eax, [len]
bswap eax
mov  [packet_header], eax   ; 네트워크로 보낼 패킷의 길이 필드 세팅
```

**3) 해시 루프에서의 반복 패턴**
```asm
hash_round:
    mov  eax, [data+rcx*4]
    bswap eax                  ; SHA류가 요구하는 빅 엔디안 워드로 변환
    ; ... 라운드 함수 계산 ...
    add  rcx, 1
    cmp  rcx, 16
    jl   hash_round
```
루프 인덱스가 16(SHA-256 메시지 스케줄 워드 개수)이면 SHA-256 구현을 강하게 의심할 수 있다.

## 명령어/단축키
- x64dbg/IDA 디버거: `bswap` 실행 전후 레지스터 창에서 값을 16진수로 비교하면 바이트가 뒤집힌 것을 바로 확인 가능
- Python으로 재현: `int.from_bytes(x.to_bytes(4,'little'), 'big')` 또는 `struct.pack('>I', x)` vs `struct.pack('<I', x)`

## 출력 해석
- `bswap` 실행 전 `eax = 0x12345678`이었다면 실행 후 `eax = 0x78563412`가 정상이다. 이렇게 정확히 바이트 4개가 거울처럼 뒤집힌 결과가 나오면 BSWAP이 제대로 동작한 것이다.
- IDA 디컴파일에서 `_byteswap_ulong(v1)` 같은 호출이 보이면 소스에서 명시적으로 엔디안 변환을 했다는 뜻이므로, 그 값이 이후 네트워크/파일 I/O에 쓰이는지 따라가 본다.

## 흔한 실수
- `BSWAP`을 `ROL`/`ROR` 8비트 회전과 같은 것으로 착각하는 것 — 회전은 바이트를 한 칸씩 순환시킬 뿐이고, BSWAP은 전체를 거울처럼 완전히 반전시킨다는 점이 다르다.
- 16비트 레지스터에 `bswap`을 쓰려는 것 — 정의되지 않은 동작이라 실전 코드에는 절대 나오지 않으며, 16비트 바이트 스왑은 `xchg al, ah` 등으로 처리된다.
- BSWAP이 플래그를 바꾼다고 착각하는 것 — 어떤 플래그도 영향받지 않는다.
- 값이 "이상하게 크거나 이상한 순서"로 보이면 무조건 버그라고 단정하는 것 — 실제로는 빅 엔디안 필드를 아직 변환하지 않고 읽은 것일 수 있으니, BSWAP 호출 유무를 먼저 확인한다.

## 막혔을 때 다음 체크
- 어떤 값이 파일/네트워크에서 읽은 것과 바이트 순서가 반대로 보이면 → 그 값이 사용되기 전에 `bswap`을 거치는지 코드를 앞뒤로 살펴본다.
- 해시 함수처럼 보이는 루프에서 반복되는 `bswap`이 있다면 → 루프 반복 횟수와 라운드 상수를 SHA-1(80라운드, 워드 16개 확장)/SHA-256(64라운드, 워드 16개 확장) 스펙과 대조해본다.
- `htonl`/`ntohl` 호출이 인라인되어 사라졌다면 → 대신 `bswap` 명령어 자체를 검색해서 네트워크 관련 코드 위치를 찾는다.

## 미니 예제

**예제 1 — 기본 32비트 반전**
```c
uint32_t y = __builtin_bswap32(x);
```
```asm
mov   eax, [x]
bswap eax
mov   [y], eax
```

**예제 2 — htonl 스타일 (네트워크 전송 전 변환)**
```c
uint32_t net_len = htonl(len);
```
```asm
mov   eax, [len]
bswap eax
mov   [net_len], eax
```

**예제 3 — 64비트 반전**
```c
uint64_t y = __builtin_bswap64(x);
```
```asm
mov   rax, [x]
bswap rax
mov   [y], rax
```

**예제 4 — 해시 계산 중 데이터 로드 직후 변환**
```c
uint32_t w = __builtin_bswap32(*(uint32_t*)(data + i*4));
```
```asm
mov   eax, [rsi+rcx*4]
bswap eax
mov   [w], eax
```

## 관련 글
- REV-0064 — ROL: 왼쪽 Rotate
- REV-0065 — ROR: 오른쪽 Rotate
- REV-0039 — MOV: 값 복사와 레지스터 메모리 이동
- REV-0043 — XCHG: 두 값 교환

## 출처/검증
- BSWAP 명령어 오퍼랜드/동작/플래그 미변경: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "BSWAP—Byte Swap" 섹션 기준 (2026-09-08 검증).
- htonl/ntohl 등 네트워크 바이트 순서 변환 함수와 엔디안 개념: POSIX `<arpa/inet.h>` 표준 문서 기준.
- SHA 계열 해시가 빅 엔디안 워드를 사용하는 규격: FIPS 180-4 (Secure Hash Standard) 공식 스펙 기준.
