---
id: REV-0337
title: "nc로 접속은 되는데 프롬프트가 안 보일 때"
slug: "rev-0337-nc-connected-no-prompt"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [nc, ncat, socat, pwntools]
keywords: ["nc 프롬프트 안 보임", "netcat 접속 후 아무것도 안 나옴", "stdout 버퍼링", "fully buffered", "line buffered", "fflush"]
aliases: ["nc 접속했는데 화면이 비어있음", "netcat 화면에 아무것도 안 뜸", "서버 배너가 안 보임", "nc host port 하니까 멈춤"]
symptom_keywords: ["nc host port로 접속했는데 아무 출력도 없음", "타이핑해도 반응이 없다가 엔터 치면 갑자기 다 출력됨", "분명 접속은 됐는데 프롬프트나 배너가 안 보임", "로컬에서 실행하면 프롬프트가 보이는데 nc로는 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`nc host port`로 접속했는데 화면이 비어 있다가 아무 키나 입력하고 엔터를 치는 순간 그동안 쌓여 있던 배너/프롬프트가 한꺼번에 쏟아진다면, 이건 연결 문제가 아니라 서버 프로그램이 표준출력을 **터미널이 아닌 파이프/소켓으로 인식해 완전 버퍼링(fully buffered) 모드로 동작하기 때문**인 경우가 대부분이다.

## 언제 검색해야 하나
- `nc chall.example.com 1337`을 실행했는데 커서만 깜빡이고 아무 텍스트도 안 보일 때
- 아무 입력이나 쳐서 엔터를 눌렀더니 갑자기 배너, 메뉴, 프롬프트가 한꺼번에 출력될 때
- 로컬에서 `./chall`을 직접 실행하면 프롬프트가 바로 보이는데, 똑같은 바이너리를 nc/서버로 접속했을 때만 안 보일 때
- pwntools `remote()`로 붙었는데 `recvline()`이 계속 멈춰 있어서(hang) "연결이 안 된 건가?" 헷갈릴 때

## 핵심 개념

### stdout은 상황에 따라 버퍼링 방식이 다르다
C 표준 라이브러리(`stdio`)는 `stdout`을 어디에 연결하느냐에 따라 자동으로 버퍼링 모드를 다르게 정한다.
- **터미널(tty)에 연결됨** → line buffered: 줄바꿈(`\n`)이 나올 때마다 즉시 화면에 출력(flush)된다.
- **파일, 파이프, 소켓에 연결됨** → fully buffered: 보통 4KB(BUFSIZ) 정도가 쌓이거나, `fflush()`가 명시적으로 호출되거나, 프로그램이 종료될 때만 한꺼번에 flush된다.

`nc`로 접속한 원격 셸/서비스의 관점에서 서버 프로그램의 `stdout`은 **소켓**에 연결된 것이다. 즉 터미널이 아니다. 그래서 서버 프로그램이 `printf("Enter password: ")`만 호출하고 `fflush(stdout)`을 호출하지 않았다면, 그 문자열은 커널로 전송되지 않고 프로그램 내부 버퍼 안에 머물러 있는다. 사용자가 아무 값이나 입력해서 서버가 `scanf`/`read` 호출을 마치고 다음 `printf`를 호출하는 시점, 혹은 프로그램이 종료(`exit`)해서 stdio가 남은 버퍼를 자동으로 flush하는 시점에야 그동안 쌓여있던 모든 텍스트가 한꺼번에 소켓으로 전송된다. 이때 클라이언트 화면에는 배너와 프롬프트가 "갑자기" 전부 나타나는 것처럼 보인다.

이것은 **버그가 아니라 정상적인 C 표준 동작**이다. 다만 CTF 문제를 만든 사람이 `setvbuf(stdout, NULL, _IONBF, 0)`(버퍼링 끔) 또는 각 `printf` 뒤에 `fflush(stdout)`을 넣지 않으면 이런 증상이 그대로 참가자에게 노출된다.

### 왜 로컬 실행에서는 이 문제가 안 보이는가
로컬 터미널에서 `./chall`을 직접 실행하면 `stdout`이 터미널(tty)에 연결되므로 line buffered로 동작해서 `\n`마다 즉시 출력된다. 그래서 개발자/출제자 본인도 로컬 테스트에서는 버퍼링 문제를 전혀 눈치채지 못하는 경우가 흔하다. 서버에 배포되어 소켓으로 서비스될 때만 fully buffered로 바뀌면서 처음으로 증상이 드러난다.

### nc/터미널 자체의 문제일 수도 있다
드물지만 다음도 원인이 될 수 있다.
- 사용 중인 `nc`가 오래된 버전이거나 Windows용 포팅판이라 줄바꿈(CRLF vs LF) 처리가 달라 출력이 안 보이는 것처럼 보이는 경우.
- 방화벽/프록시가 소켓은 열어주지만 데이터는 지연 전송(버퍼링)하는 중간 장비를 거치는 경우.
- TLS로 감싸진 포트인데 평문 `nc`로 접속해서 핸드셰이크가 실패했지만 연결 자체는 유지되는 것처럼 보이는 경우 — 이 경우 `ncat --ssl host port`로 재시도해야 한다.

## 화면/코드에서 보이는 징후
- `nc host port` 실행 직후 화면이 완전히 비어 있음(프롬프트, 배너 전부 없음)
- 아무 문자나 입력 후 엔터 → 배너 + 프롬프트 + 방금 입력값 처리 결과까지 한꺼번에 출력됨
- pwntools `context.log_level = 'debug'`로 보면 `recv`가 아무 것도 못 받다가, 이쪽에서 `send`를 호출한 직후 서버로부터 대량의 데이터가 한 번에 도착하는 로그가 찍힘
- 로컬 `./chall` 직접 실행은 정상, `socat TCP-LISTEN:1337,fork EXEC:./chall` 등으로 소켓을 흉내내면 로컬에서도 같은 증상 재현됨

## 가장 먼저 할 것
로컬에서 같은 증상을 재현해본다. `socat tcp-listen:4444,reuseaddr,fork exec:./chall &`로 로컬에 리스너를 띄우고 `nc 127.0.0.1 4444`로 접속했을 때도 똑같이 화면이 비어 있다면, 서버/네트워크 문제가 아니라 **바이너리 자체의 stdout 버퍼링 문제**라는 게 확정된다. 이 경우 접속이 실패한 게 아니므로 당황할 필요 없이, 그냥 정해진 입력을 순서대로 보내면 정상적으로 상호작용할 수 있다.

## 단계별 절차

**1) 로컬에서 소켓 환경으로 증상 재현**
```bash
socat tcp-listen:4444,reuseaddr,fork exec:./chall &
nc 127.0.0.1 4444
```
소켓을 통했을 때만 화면이 비면 버퍼링 문제로 확정.

**2) strace로 실제 write() 호출 시점 확인**
```bash
strace -f -e trace=read,write ./chall < /dev/null
```
`write(1, "Enter password: ", 17)`이 호출되는 시점과 그 사이 `read()` 호출이 오는 순서를 보면, 프로그램이 실제로 언제 데이터를 커널에 넘기는지 알 수 있다. 소켓으로 서비스될 때는 이 `write()` 자체가 지연되거나 나중에 합쳐져서 나가는 게 아니라, **애초에 `write()` 호출 자체가 늦게 일어난다**(stdio가 자체 버퍼에 쌓아두고 있다가 나중에 한 번에 `write()`).

**3) 증상을 확인했다면, 화면에 아무것도 안 보여도 정해진 입력을 그대로 진행**
프롬프트가 안 보인다고 접속이 끊긴 게 아니다. 문제 설명이나 바이너리 정적 분석(`strings`, IDA/Ghidra)으로 미리 파악해 둔 입력 순서대로 그냥 입력을 계속 보낸다. 서버가 종료되거나 버퍼가 가득 차는 시점에 밀려있던 출력이 한꺼번에 나타난다.

**4) pwntools로 자동화할 때는 화면에 안 보여도 recv 계열로 파싱**
```python
from pwn import *

p = remote('chall.example.com', 1337)
p.recvuntil(b'password: ')   # 화면에 안 보였어도 버퍼 안에는 도착해 있을 수 있음
p.sendline(b'test123')
print(p.recvall(timeout=3))
```
`recvuntil`/`recvline`은 사람 눈에 보이는 화면 출력과 무관하게, 소켓에 실제로 도착한 바이트를 기준으로 동작한다. 즉 화면(터미널로 nc 실행 시)에 안 보이는 것과, pwntools가 데이터를 못 받는 것은 별개다.

**5) 로컬 재현 바이너리로 버퍼링을 강제로 끄고 확인(선택)**
```bash
stdbuf -o0 -e0 ./chall
```
`stdbuf -o0`으로 표준출력 버퍼링을 끄면 소켓 환경에서도 line buffered처럼 즉시 flush되는지 실험적으로 확인할 수 있다. 단, 이건 로컬 재현용 진단 도구일 뿐 서버 바이너리 자체를 바꿀 수는 없다.

## 명령어/단축키
```bash
nc host port                          # 기본 접속
ncat --ssl host port                  # TLS로 감싸진 포트일 때
socat tcp-listen:4444,reuseaddr,fork exec:./chall   # 로컬 소켓 환경 재현
strace -f -e trace=read,write ./chall # 버퍼링 타이밍 확인
stdbuf -o0 -e0 ./chall                # 로컬 재현 시 버퍼링 강제 해제(진단용)
```
```python
p = remote('host', 1337)
p.recvuntil(b'...')
p.sendline(b'...')
p.interactive()
```

## 출력 해석
- 아무 입력 없이도 화면이 비어 있던 상태에서 입력 한 번에 배너+프롬프트+응답이 통째로 나오면 fully buffered 버퍼링 문제가 100% 확정이다.
- `strace` 결과에서 여러 개의 `printf`에 대응하는 `write()` 호출들이 실제로는 하나의 큰 `write()`로 합쳐져서 나타나거나, 예상보다 훨씬 늦게(예: `exit_group` 직전에) 나타나면 버퍼링이 원인이다.
- pwntools `recvuntil`이 타임아웃 없이 정상적으로 리턴됐다면 화면에 안 보였어도 실제로는 데이터가 도착한 것이다 — 이 경우는 걱정할 게 없다.

## 흔한 실수
- 프롬프트가 안 보인다고 접속이 끊겼다고 판단해서 `nc`를 계속 재접속하며 시간을 낭비하는 것.
- pwntools로 `p.recv()`를 호출했을 때 화면에 아무것도 안 나온다고 해서 코드가 잘못됐다고 판단하는 것 — 실제로는 정상 동작 중이며, `recvuntil`로 원하는 지점까지 기다리면 된다.
- 로컬 `./chall` 실행이 정상적으로 프롬프트를 보여준다고 해서 "버퍼링 문제가 아니다"라고 단정하는 것 — 로컬 직접 실행은 tty라서 line buffered로 동작하므로 증상이 재현되지 않는 게 당연하다. 반드시 `socat`/파이프로 재현해야 한다.
- REV-0338(타임아웃)과 혼동해서, 사실은 정상적으로 데이터를 받고 있는데 "타임아웃이 난 것 같다"고 착각하고 재시도하는 것.

## 막혔을 때 다음 체크
- 재현까지 했는데도 nc 자체가 계속 멈춰 있고 pwntools로도 아무것도 못 받는다면 → REV-0338(서버 문제에서 타임아웃이 계속 발생할 때)
- 원하는 입력을 다 보냈는데 서버가 계속 틀렸다고 한다면 → REV-0339(Flag 형식은 맞는데 서버가 계속 오답 처리할 때)
- 로컬에서는 잘 되던 익스플로잇/입력이 서버에서만 안 먹힌다면 → REV-0340(로컬에서는 성공하는데 서버에서는 실패할 때)
- 서버 프로그램의 입력 처리 함수 자체를 더 알아보고 싶다면 → REV-0109(입력 함수 정리)

## 미니 예제
```bash
$ nc chall.example.com 1337
                              # <- 여기서 몇 초간 화면이 완전히 비어 있음
test                          # <- 아무 값이나 입력하고 엔터
=== Welcome to xor_lock ===   # <- 엔터 치자마자 배너, 프롬프트, 응답이 한꺼번에 출력됨
Enter password: Wrong!
```
이 예시에서 `Enter password: ` 프롬프트는 사실 접속 직후 서버 프로그램이 이미 호출한 `printf`였지만, `fflush` 없이 stdio 버퍼 안에 머물러 있다가 사용자가 `test\n`을 보내 서버가 `scanf`/`read`를 마치고 다음 처리(`Wrong!` 출력 및 종료 전 최종 flush)를 하는 순간에야 전부 함께 소켓으로 전송된 것이다.

## 관련 글
- REV-0338 — 서버 문제에서 타임아웃이 계속 발생할 때
- REV-0339 — Flag 형식은 맞는데 서버가 계속 오답 처리할 때
- REV-0340 — 로컬에서는 성공하는데 서버에서는 실패할 때
- REV-0109 — scanf fgets read 입력 추적

## 출처/검증
- C 표준 stdio의 버퍼링 모드(fully buffered/line buffered/unbuffered)와 tty 여부에 따른 자동 선택: ISO C 표준(C11) 7.21.3 "Files" 및 glibc 공식 매뉴얼(GNU C Library Manual) "Stream Buffering" 섹션 기준 (2026-09-09 검증).
- `setvbuf`/`fflush` 동작: glibc 공식 매뉴얼 기준.
- pwntools `remote`/`recvuntil`/`recvall` 동작: pwntools 공식 문서(docs.pwntools.com) 기준.
