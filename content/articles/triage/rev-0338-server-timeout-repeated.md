---
id: REV-0338
title: "서버 문제에서 타임아웃이 계속 발생할 때"
slug: "rev-0338-server-timeout-repeated"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [nc, pwntools, socat]
keywords: ["타임아웃", "timeout", "연결이 끊김", "connection timed out", "alarm", "recvuntil 멈춤", "서버 응답 없음"]
aliases: ["원격 서버 타임아웃", "nc 연결이 자꾸 끊김", "pwntools timeout 에러", "서버가 응답을 안 함"]
symptom_keywords: ["nc로 접속하면 몇 초 뒤 연결이 끊김", "pwntools에서 EOFError나 timeout 예외가 계속 발생함", "recvuntil이 영원히 멈춰있음", "서버 접속 자체가 안 되고 connection timed out이 뜸"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
서버 문제에서 "타임아웃"은 사실 서로 다른 세 가지 문제 — ① 애초에 서버에 도달조차 못 하는 네트워크 레벨 타임아웃, ② 서버의 `alarm()` 기반 강제 종료 타이머, ③ 내 스크립트가 오지 않을 문자열을 기다리며 무한정 멈춰있는 로직 레벨 행(hang) — 를 뭉뚱그려 부르는 말이므로, 먼저 이 셋 중 어디에 해당하는지부터 구분해야 한다.

## 언제 검색해야 하나
- `nc host port`를 실행하자마자 또는 몇 초 뒤 `Connection timed out`이 뜨며 접속 자체가 안 될 때
- 접속은 됐는데 pwntools 스크립트가 `recvuntil`/`recvline`에서 멈춘 채로 몇 분째 진행이 없을 때
- 이전에는 잘 되던 스크립트가 갑자기 서버 쪽에서 자꾸 연결을 끊을 때
- CTF 문제 설명에 "이 문제는 N초 안에 풀어야 합니다" 같은 문구가 있어서 시간 제한 자체가 문제 로직의 일부일 때

## 핵심 개념

### 세 가지 서로 다른 "타임아웃"
1. **네트워크 레벨(연결 자체가 안 됨)** — TCP 연결(SYN)이 서버에 도달하지 못하거나 서버가 응답하지 않는 경우다. 방화벽, VPN 미접속, 문제 서버가 아직 안 켜졌거나 이미 내려간 경우, IP/포트를 잘못 입력한 경우가 원인이다. 이 경우 `nc`는 몇 초~몇십 초 뒤 `Connection timed out` 또는 `Connection refused`를 출력한다(둘은 다르다 — 아래 "출력 해석" 참고).
2. **서버 프로그램의 강제 종료 타이머(alarm)** — CTF pwn 서버는 한 접속이 자원을 무한정 점유하지 못하도록 `alarm(N)`(또는 `timeout N ./chall` 래퍼)으로 N초 뒤 프로세스를 강제 종료하는 경우가 매우 흔하다. 이 시간 안에 상호작용을 끝내지 못하면 서버가 연결을 강제로 닫는다. 이건 버그가 아니라 **의도된 보호 장치**이므로, 스크립트를 더 빠르게 만들거나 자동화해서 시간 안에 끝내야 한다.
3. **내 스크립트의 로직 레벨 행(hang)** — 서버는 정상 응답을 이미 보냈는데, 내 스크립트가 `recvuntil(b'어떤 문자열')`에서 그 문자열이 실제 서버 출력과 한 글자라도 다르거나(오타, 대소문자, 개행 문자 차이) 애초에 안 나올 문자열을 기다리고 있어서 영원히 멈춰있는 경우다. 이 경우 서버 쪽은 아무 문제가 없다 — 내 코드가 도착한 데이터를 못 알아보고 계속 기다리는 것뿐이다.

### 왜 구분이 중요한가
1번(네트워크)이면 서버/인프라 쪽 문제이거나 접속 정보 자체가 틀린 것이라 코드를 아무리 고쳐도 소용없다. 2번(alarm)이면 코드를 더 빠르게 만들거나 상호작용 순서를 최적화해야 한다. 3번(로직 행)이면 네트워크나 서버와는 무관하고, `recvuntil`에 넘긴 문자열 자체를 다시 검증해야 한다. 이 세 가지를 구분하지 못하면 "서버가 이상하다"고 단정하고 잘못된 방향으로 시간을 낭비하기 쉽다.

## 화면/코드에서 보이는 징후
- `nc: connect to host port [tcp/*] failed: Connection timed out` → 1번(네트워크) 가능성이 높음.
- `nc: connect to host port [tcp/*] failed: Connection refused` → 포트는 닫혀 있거나 서비스가 안 떠 있음(1번과 유사하지만 원인이 다름 — "출력 해석" 참고).
- 접속은 성공(프롬프트/배너까지 정상 수신)했는데 특정 시점에 서버가 갑자기 연결을 끊음(`EOFError` in pwntools) → 2번(alarm) 가능성.
- `p.recvuntil(b'...')`을 호출한 줄에서 스크립트가 몇 분째 멈춰 있고, `context.log_level='debug'`로도 그 뒤 아무 로그가 안 찍힘 → 3번(로직 행) 가능성. 이 경우 사실 서버가 보낸 데이터를 pwntools가 이미 받았지만, 기다리는 패턴이 그 안에 없어서 계속 기다리는 중일 수 있다.

## 가장 먼저 할 것
`context.log_level = 'debug'`로 pwntools 로그 레벨을 올리고 다시 실행한다. 이 한 줄만으로 실제로 소켓에 어떤 바이트가 오갔는지 전부 화면에 찍히므로, "서버가 아무것도 안 보냈다"(1·2번 쪽)와 "서버는 데이터를 보냈는데 내가 기다리는 문자열이 그 안에 없다"(3번)를 즉시 구분할 수 있다.

## 단계별 절차

**1) 네트워크 레벨부터 배제**
```bash
nc -vz chall.example.com 1337   # 포트가 열려있는지만 빠르게 확인
```
`succeeded` 나오면 네트워크는 정상. `timed out`/`refused`가 나오면 문제 서버 자체가 다운됐거나 방화벽/VPN 문제이니 CTF 운영진 공지나 네트워크 설정부터 확인한다.

**2) alarm 타이머 여부 확인**
문제 설명에 시간 제한 언급이 있는지, 또는 접속 후 몇 초 뒤 정확히 매번 같은 타이밍에 끊기는지 관찰한다. 정확히 일정한 시간(예: 항상 정확히 10초 뒤)에 끊긴다면 `alarm(10)`류의 서버 측 타이머가 거의 확실하다.
```python
from pwn import *
context.log_level = 'debug'

p = remote('chall.example.com', 1337)
p.sendline(b'...')
p.recvall(timeout=15)   # 실제로 몇 초 뒤 연결이 끊기는지 관찰
```

**3) 로직 레벨 행 여부 확인 — debug 로그로 실제 수신 데이터 확인**
```python
context.log_level = 'debug'
p = remote('chall.example.com', 1337)
data = p.recv(4096)      # recvuntil 대신 일단 통째로 받아서 눈으로 확인
print(repr(data))
```
`recv(4096)`으로 받은 원문을 그대로 출력해서, 내가 `recvuntil`에 넘기려던 문자열이 정확히 그 안에 (대소문자/공백/개행까지) 포함되어 있는지 직접 눈으로 대조한다.

**4) alarm 타이머가 원인이면 상호작용을 자동화/최적화**
- 수동으로 하나씩 타이핑하지 말고 스크립트로 모든 입력을 미리 계산해서 한 번에/빠르게 전송한다.
- 여러 번의 `recvuntil` + `sendline` 왕복이 필요하다면, 네트워크 왕복 지연(RTT)이 누적되어 시간 제한을 넘길 수 있으니 꼭 필요한 왕복만 남기고 나머지는 로컬에서 미리 계산한다.
- 브루트포스가 필요한 문제라면 "alarm 안에 몇 번 시도 가능한지" 계산부터 하고, 필요하면 재접속 반복 구조로 설계한다.

**5) 재시도 로직으로 감싸기(인프라 불안정 대응)**
```python
import time
for attempt in range(5):
    try:
        p = remote('chall.example.com', 1337, timeout=5)
        break
    except PwnlibException:
        time.sleep(2)
else:
    raise RuntimeError('서버에 계속 접속 실패')
```
대회 중 많은 참가자가 동시 접속하면 서버가 일시적으로 응답이 늦어질 수 있다. 짧은 대기 후 재시도하는 로직을 넣으면 이런 일시적 혼잡을 견딜 수 있다.

## 명령어/단축키
```bash
nc -vz host port                 # 포트 오픈 여부만 빠르게 확인
nc -w 5 host port                # 5초 타임아웃으로 접속 시도
```
```python
context.log_level = 'debug'      # 모든 송수신 바이트를 화면에 출력
p = remote('host', 1337, timeout=5)
p.recv(4096)                     # recvuntil 대신 원문 확인용
p.recvall(timeout=10)
```

## 출력 해석
- `Connection timed out`: 패킷이 서버까지 도달했는지조차 확인 안 됨(방화벽이 조용히 버리거나, 라우팅 문제, 서버가 아예 꺼져 있음).
- `Connection refused`: 서버 호스트까지는 도달했지만 그 포트를 듣고 있는 프로세스가 없음(서비스가 크래시했거나 아직 안 켜짐, 포트 번호를 잘못 입력함).
- pwntools `EOFError`: 서버가 정상적으로 연결을 닫았다는 뜻 — 소켓 자체는 문제없이 동작했고, 다만 그 시점에 종료됐다는 정보다. alarm 타이머 만료 또는 프로그램이 정상/비정상 종료(`exit`, crash)했을 가능성을 함께 봐야 한다.
- `recv(4096)`으로 뽑은 원문에 개행이 `\r\n`인데 `recvuntil(b'...\n')`으로 `\n`만 기다리고 있었다면, 이 자체는 매칭이 되어야 정상이지만(`\n`이 `\r\n`에 포함됨) 반대로 서버가 `\n` 없이 프롬프트를 내보내고 다음 입력을 기다리는 구조라면 영원히 안 온다 — 원문을 직접 보는 것이 가장 확실하다.

## 흔한 실수
- 알람 타이머(2번)로 끊긴 것을 네트워크 문제(1번)로 착각해서 계속 재접속만 반복하는 것.
- `recvuntil`이 멈춰 있는 것을 서버 문제로 단정하고 서버 상태를 의심하는 것 — 실제로는 기다리는 문자열 자체가 틀린 경우(3번)가 훨씬 흔하다.
- REV-0337(버퍼링으로 화면에 프롬프트가 안 보이는 경우)과 헷갈려서, 실제로는 정상 수신 중인데 "타임아웃 난 것 같다"고 오판하는 것 — `context.log_level='debug'`로 실제 수신 여부를 먼저 확인해야 구분된다.
- `remote()` 생성 자체에 `timeout`을 안 주고 기본값(무한 대기)으로 실행해서, 네트워크 문제가 있어도 스크립트가 영원히 멈춘 채로 원인 파악을 못 하는 것 — 항상 명시적 `timeout` 값을 주는 습관을 들인다.

## 막혔을 때 다음 체크
- 접속은 되는데 프롬프트가 안 보여서 타임아웃처럼 느껴진다면 → REV-0337(nc로 접속은 되는데 프롬프트가 안 보일 때)
- 시간 안에 풀었는데도 flag가 틀렸다고 나온다면 → REV-0339(Flag 형식은 맞는데 서버가 계속 오답 처리할 때)
- 로컬에서는 시간 내에 잘 풀리는데 서버에서만 자꾸 시간 초과가 난다면 → REV-0340(로컬에서는 성공하는데 서버에서는 실패할 때)

## 미니 예제
```python
from pwn import *
context.log_level = 'debug'

p = remote('chall.example.com', 1337, timeout=5)
data = p.recvuntil(b'password: ', timeout=10)
print(repr(data))
p.sendline(b'test123')
print(p.recvall(timeout=15))
```
`recvuntil(..., timeout=10)`처럼 각 수신 단계마다 명시적 타임아웃을 주면, 어느 단계에서 실제로 멈추는지 예외 메시지로 바로 알 수 있다. 타임아웃 없이 짜면 어느 줄에서 멈췄는지조차 알기 어렵다.

## 관련 글
- REV-0337 — nc로 접속은 되는데 프롬프트가 안 보일 때
- REV-0339 — Flag 형식은 맞는데 서버가 계속 오답 처리할 때
- REV-0340 — 로컬에서는 성공하는데 서버에서는 실패할 때

## 출처/검증
- `alarm()` 시스템콜을 이용한 프로세스 강제 종료 타이머: POSIX(IEEE Std 1003.1) `alarm` 함수 명세 기준.
- pwntools `remote`/`recv`/`recvuntil`/`recvall`의 `timeout` 파라미터와 `context.log_level` 동작: pwntools 공식 문서(docs.pwntools.com) 기준 (2026-09-09 확인).
- TCP `Connection timed out`과 `Connection refused`의 차이(패킷 미도달 대 포트 미청취): TCP/IP 일반 네트워킹 개념(RFC 793 TCP 명세 기준 동작 설명).
