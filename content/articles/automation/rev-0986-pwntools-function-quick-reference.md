---
id: REV-0986
title: "pwntools 함수 빠른 참조(p32/p64/u32/u64/process/remote)"
slug: "rev-0986-pwntools-function-quick-reference"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [pwntools, Python]
keywords: ["pwntools 함수표", "process remote 정리", "sendline recvuntil 정리", "pwntools 치트시트", "context 설정"]
aliases: ["pwntools 치트시트", "pwntools 함수 목록", "pwn 라이브러리 빠른 참조", "pwntools API 정리"]
symptom_keywords: ["pwntools 함수 이름을 까먹음", "process remote 차이 헷갈림", "recv 계열 함수 정리 필요", "context 설정법을 매번 찾아봄"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
REV-0266(프로세스 실행)과 REV-0267(패킹)에서 다룬 pwntools 핵심 기능을 실전에서 바로 찾아 쓸 수 있도록, 프로세스/원격 연결, 송수신, 패킹/언패킹, 로깅/설정까지 한 페이지 표로 정리한 빠른 참조 문서다.

## 언제 검색해야 하나
- 스크립트를 짜다가 `recvuntil`과 `recvline`의 정확한 차이가 기억 안 날 때
- `process()`를 `remote()`로 바꿀 때 인자 형태가 헷갈릴 때
- `p32`/`u32`와 `pack`/`unpack`의 차이, ELF/context 관련 헬퍼 이름이 기억 안 날 때
- 디버깅용 로그 레벨 설정 문법을 매번 검색하기 귀찮을 때

## 핵심 개념
pwntools의 API는 크게 네 그룹으로 나뉜다. **튜브(tube) 생성**(`process`, `remote`, `ssh` 등 — 실제로 무엇에 연결할지), **송수신**(`send*`/`recv*` — 튜브 종류와 무관하게 동일한 인터페이스), **패킹/언패킹**(`p32`/`u64` 등 — 정수와 바이트열 변환), **환경 설정/로깅**(`context`, `log_level` — 아키텍처나 출력 상세도 조정)이다. 이 네 그룹의 이름과 역할만 확실히 구분해두면 실전 스크립트 작성 속도가 크게 빨라진다.

## 화면/코드에서 보이는 징후
`from pwn import *` 한 줄로 아래 표의 모든 함수/클래스가 한 번에 임포트되어, 별도 모듈 접두사 없이 바로 호출된다.

## 가장 먼저 할 것
지금 다루는 대상이 로컬 바이너리인지 원격 서버인지부터 확인한다. 로컬이면 `process()`, 원격(host:port로 접속하는 CTF 서버)이면 `remote()`를 쓰며, 이후 송수신 코드는 완전히 동일하게 재사용된다.

## 단계별 절차
1. 튜브를 연다: `p = process(...)` 또는 `p = remote(host, port)`.
2. 필요하면 `p.recvuntil(...)`로 불필요한 프롬프트를 먼저 읽어치운다.
3. `p.sendline(...)`으로 입력을 보낸다. raw 바이트가 필요하면 `p32`/`p64`로 미리 패킹한다.
4. `p.recv*()`로 응답을 받아 파싱한다. 정수로 해석해야 하면 `u32`/`u64`를 쓴다.
5. 다 끝나면 `p.close()`로 정리하거나, 사람이 이어받아야 하면 `p.interactive()`.

## 명령어/단축키

### 튜브 생성
```python
p = process('./chall')                 # 로컬 바이너리 실행
p = process(['./chall', 'arg1'])       # 인자와 함께 실행
p = remote('ctf.example.com', 1337)    # 원격 서버 접속
```

### 송신
```python
p.send(data)          # 그대로 전송
p.sendline(data)       # 끝에 개행(\n) 추가해서 전송
p.sendafter(delim, data)     # delim이 나올 때까지 기다린 뒤 전송
p.sendlineafter(delim, data) # 위와 동일 + 개행 추가
```

### 수신
```python
p.recv(n)              # 최대 n바이트 수신
p.recvline()            # 개행까지 한 줄 수신
p.recvuntil(delim)      # delim이 나올 때까지 누적 수신(delim 포함)
p.recvall()             # 프로세스 종료까지 전부 수신
p.recvregex(pattern)     # 정규식에 매치될 때까지 수신
```

### 패킹/언패킹
```python
p8(n) / p16(n) / p32(n) / p64(n)        # 정수 → 바이트열(리틀 엔디안 기본)
u8(d) / u16(d) / u32(d) / u64(d)        # 바이트열 → 정수
pack(n, word_size=32, endian='little')   # 범용 패킹
unpack(d, word_size=32)                   # 범용 언패킹
```

### 설정/로깅
```python
context.arch = 'amd64'        # 'i386', 'arm' 등
context.os = 'linux'
context.endian = 'big'         # 기본은 little
context.log_level = 'debug'    # 송수신 바이트를 전부 로그로 출력
```

### 종료/전환
```python
p.close()             # 연결 종료
p.interactive()        # 사람이 직접 조작하는 모드로 전환
```

## 출력 해석
- `recvuntil(delim)`은 결과에 `delim` 자체를 **포함**해서 반환한다. 이후 파싱 시 이 delim까지 포함된 것을 감안해야 한다.
- `recvline()`은 개행 문자까지 포함해서 반환하므로, 순수 텍스트만 비교하려면 `.strip()`이 필요할 수 있다.
- `context.log_level = 'debug'`를 켜면 실제로 오간 바이트가 `[DEBUG] Sent 0x9 bytes:` 형태로 전부 출력되어, 값이 어디서 어긋나는지 눈으로 바로 확인할 수 있다.

## 흔한 실수
- `send`와 `sendline`을 혼용해서 개행 유무 때문에 대상 프로그램이 입력을 못 읽는 것.
- `recvuntil`의 delim이 실제 출력과 한 글자라도 다르면 무한 대기에 빠지는 것을 모르고 계속 같은 코드를 재실행하는 것.
- `process()`로 짠 스크립트를 대회 서버 제출 직전에 `remote()`로 바꾸는 걸 깜빡하는 것.
- `p32`/`p64` 크기를 헷갈려서 4바이트 자리에 8바이트 값을 넣는 것.

## 막혔을 때 다음 체크
- 프로세스 실행/송수신 개념 자체가 헷갈리면 → REV-0266 pwntools로 프로세스 실행하고 입력 보내기
- 패킹/엔디안 개념을 더 자세히 알고 싶다면 → REV-0267 pwntools p32 p64 u32 u64
- 찾은 입력값을 Z3/angr로 자동 계산해서 바로 여기에 넣고 싶다면 → REV-0268 Z3 BitVec 기초, REV-0271 angr 심볼릭 실행 기초

## 미니 예제
로컬 바이너리와 원격 서버 둘 다에 동일하게 쓸 수 있는 스크립트 구조 예시다.

```python
from pwn import *

context.log_level = 'debug'

LOCAL = True
if LOCAL:
    p = process('./chall')
else:
    p = remote('ctf.example.com', 1337)

p.recvuntil(b'guess: ')
p.sendline(p32(1337))
result = p.recvline()
print(result)
p.close()
```

`LOCAL` 플래그 하나만 바꾸면 로컬 테스트와 원격 제출용 스크립트를 완전히 동일한 코드로 재사용할 수 있다.

## 관련 글
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기
- REV-0267 — pwntools p32 p64 u32 u64
- REV-0268 — Z3 BitVec 기초

## 출처/검증
- pwntools 공식 문서(docs.pwntools.com)의 `pwnlib.tubes`(process/remote/send/recv 계열), `pwnlib.util.packing`(p32/u32 등), `pwnlib.context` API를 기준으로 정리했다(2026-09-09 검증).
- `pwntools`는 서드파티 패키지이므로 `pip install pwntools`가 필요하며, 오프라인 설치 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
