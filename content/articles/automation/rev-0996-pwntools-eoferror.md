---
id: REV-0996
title: "pwntools 프로세스 연결이 EOFError로 끊길 때"
slug: "rev-0996-pwntools-eoferror"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [pwntools, Python]
keywords: ["pwntools EOFError", "EOFError recv", "pwntools 프로세스 죽음", "tube closed", "pwntools 연결 끊김"]
aliases: ["pwntools EOFError 원인", "recvline EOFError", "pwntools 프로세스가 죽었다고 함", "EOFError: EOF while reading"]
symptom_keywords: ["pwntools에서 EOFError가 남", "recv 하다가 EOFError", "프로세스가 갑자기 죽어서 recv 실패", "pwntools 스크립트가 EOFError로 멈춤"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
pwntools의 `EOFError`는 "더 이상 읽을 데이터가 없다"는 뜻으로, 대상 프로세스가 이미 종료(정상 종료든 크래시든)되었는데 스크립트가 그 이후에도 `recv()`/`recvline()`/`recvuntil()`을 호출해서 발생하며, 대부분은 pwntools 자체 버그가 아니라 스크립트가 보낸 입력이 대상 프로그램을 실제로 죽였거나 예상한 프롬프트/구분자가 애초에 출력되지 않은 것이 원인이다.

## 언제 검색해야 하나
- `p.recvline()`이나 `p.recvuntil()`을 호출한 직후 `EOFError`가 발생하며 스크립트가 멈출 때
- 로컬에서 손으로 실행하면 멀쩡한 바이너리인데 pwntools로 자동화하면 중간에 죽는 것처럼 보일 때
- `sendline()`으로 어떤 값을 보낸 직후부터 `EOFError`가 나기 시작해서, 그 입력이 크래시를 유발했는지 확인하고 싶을 때
- 반복문으로 여러 후보값을 자동 테스트하는 스크립트가 특정 후보에서만 `EOFError`로 멈출 때

## 핵심 개념
pwntools의 `tube`(프로세스/소켓 연결을 추상화한 공통 인터페이스) 객체는 대상이 데이터를 더 보내지 않고 연결 자체를 닫으면(프로세스 종료, 소켓 close) 그 사실을 `EOFError` 예외로 알려준다. 이는 파이썬 파일 객체가 파일 끝(EOF)에 도달했을 때의 개념과 같다 — "읽을 게 더 있는데 못 읽는 것"이 아니라 "정말로 더 이상 아무것도 오지 않는다"는 확정적 신호다.

`EOFError`가 발생하는 전형적인 원인은 다음과 같다.

1. **대상 프로그램이 정상적으로 실행을 끝내고 종료**했는데, 스크립트는 그 이후에도 응답을 더 기다리며 `recv()`를 호출한 경우.
2. **스크립트가 보낸 입력이 대상 프로그램을 크래시시킨 경우**(버퍼 오버플로우, 잘못된 형식의 입력, `NULL` 역참조 유발 등). 크래시가 나면 프로세스가 즉시 종료되므로 그 이후 `recv` 계열 호출은 전부 `EOFError`가 난다.
3. **`recvuntil()`에 넘긴 구분자가 실제 프로그램 출력과 정확히 일치하지 않는 경우.** 이 경우 프로그램은 이미 출력을 다 하고 종료했는데, pwntools는 구분자를 못 찾아 계속 기다리다가 결국 EOF를 만나 예외를 던진다.
4. **잘못된 인자/경로로 대상을 실행해서 즉시 종료된 경우.** 예를 들어 32비트 전용 바이너리를 아키텍처가 안 맞는 환경에서 실행하면 즉시 죽는다.

즉 `EOFError`는 "무엇이 문제인가"를 직접 알려주지 않는 대신, "대상이 이미 죽었다"는 사실만 알려준다. 원인을 좁히려면 죽기 직전까지 어떤 데이터가 오갔는지를 직접 봐야 한다.

## 화면/코드에서 보이는 징후
```python
>>> p = process('./chall')
>>> p.recvuntil(b'password: ')
b'Enter password: '
>>> p.sendline(b'A' * 200)
>>> response = p.recvline()
Traceback (most recent call last):
  ...
EOFError
```
프로세스 종료 로그가 그 사이에 같이 출력되는 경우도 많다.
```text
[*] Process './chall' stopped with exit code -11 (SIGSEGV) (pid 12345)
```
`exit code -11`은 시그널 11(`SIGSEGV`, 세그멘테이션 폴트)로 죽었다는 뜻이며, 이는 방금 보낸 입력이 크래시를 유발했다는 강력한 단서다.

## 가장 먼저 할 것
스크립트 맨 위에 `context.log_level = 'debug'`를 추가해서 실제로 어떤 바이트가 오갔는지, 그리고 프로세스가 어떤 종료 코드로 죽었는지부터 확인한다. 이 한 줄만으로 원인의 대부분(정상 종료인지 크래시인지, 어느 시점에 끊겼는지)을 즉시 알 수 있다.

## 단계별 절차

**1) 디버그 로그로 실제 송수신 내역 확인**
```python
from pwn import *
context.log_level = 'debug'

p = process('./chall')
p.recvuntil(b'password: ')
p.sendline(b'A' * 200)
response = p.recvline()
```
디버그 모드에서는 `[DEBUG] Sent 0x...` / `[DEBUG] Received 0x...` 형태로 실제 바이트가 전부 로그로 찍히므로, 어느 시점 이후로 아무것도 안 오는지 눈으로 확인할 수 있다.

**2) 종료 코드로 크래시 여부 판단**
```python
p = process('./chall')
p.sendline(b'test')
try:
    p.recvline()
except EOFError:
    print('EOF, exit code:', p.poll())  # 음수면 시그널로 종료(예: -11 == SIGSEGV)
```
`p.poll()`은 프로세스가 이미 종료됐으면 종료 코드를, 아직 살아있으면 `None`을 반환한다. 리눅스에서 음수 값은 `-시그널번호`를 뜻한다(`-11`은 `SIGSEGV`, `-6`은 `SIGABRT`).

**3) recvuntil 구분자를 실제 출력과 정확히 대조**
```python
context.log_level = 'debug'
p = process('./chall')
# 여기서 구분자가 실제 프롬프트와 한 글자라도 다르면 EOF까지 계속 기다리다 예외가 난다
p.recvuntil(b'Enter password: ')  # 실제 출력이 'password:'(콜론 뒤 공백 없음)라면 여기서 이미 어긋남
```
디버그 로그에 찍힌 실제 수신 바이트를 그대로 복사해서 구분자로 써보는 것이 가장 확실하다.

**4) recvall로 죽기 직전까지 나온 모든 출력 한 번에 확인**
```python
p = process('./chall')
p.sendline(b'A' * 200)
leftover = p.recvall(timeout=2)  # EOF가 나도 예외 대신 지금까지 받은 데이터를 그대로 반환
print(leftover)
```
`recvall()`은 연결이 끊길 때까지 받은 모든 데이터를 모아서 반환하며, `EOFError`를 던지지 않고 조용히 끝난다는 점에서 디버깅용으로 유용하다.

**5) 프로세스가 즉시 죽는지 먼저 단독으로 확인**
```bash
./chall
# 손으로 몇 가지 입력을 넣어보며 실제로 정상 동작하는지, 특정 입력에서 죽는지 확인
echo $?  # 리눅스에서 마지막 실행 종료 코드 확인
```

## 명령어/단축키
- `context.log_level = 'debug'` : 모든 송수신 바이트와 프로세스 상태 로그 출력
- `p.poll()` : 프로세스 종료 여부/종료 코드 확인(음수면 시그널 번호)
- `p.recvall(timeout=n)` : EOF까지 받은 모든 데이터를 예외 없이 반환
- `p.recvrepeat(timeout=n)` : 지정 시간 동안 들어오는 데이터를 계속 모아 반환(EOF나 타임아웃에도 예외 없이 종료)
- `try/except EOFError:` : EOF를 정상적인 "프로세스 종료" 신호로 처리하고 싶을 때 감싸서 처리

## 출력 해석
- `EOFError` (그 자체) — 대상이 연결을 닫았고 더 받을 데이터가 없다는 뜻. 예외 시점 직전에 보낸 입력, 그리고 그 전에 기대했던 프롬프트를 실제로 받았는지부터 확인한다.
- `Process '...' stopped with exit code 0` — 정상 종료. 스크립트가 종료 이후에도 응답을 더 기다린 것이 원인이다.
- `Process '...' stopped with exit code -11 (SIGSEGV)` — 세그멘테이션 폴트로 죽었다는 뜻. 방금 보낸 입력이 오버플로우 등으로 크래시를 유발했을 가능성이 크다(취약점 자체를 찾는 과정에서는 오히려 이것이 목표 신호일 수도 있다).
- `Process '...' stopped with exit code -6 (SIGABRT)` — `abort()` 호출(스택 카나리 감지, `assert` 실패, 힙 손상 감지 등)로 죽었다는 뜻.

## 흔한 실수
- `recvuntil()`의 구분자 문자열이 실제 출력과 공백/대소문자 하나라도 달라서, 프로그램이 이미 종료됐는데도 pwntools는 계속 기다리다 결국 `EOFError`를 던지는 것을 "pwntools가 이상하다"고 오해하는 것.
- 크래시(`SIGSEGV`)로 죽은 것을 "스크립트 버그"로 착각해서 정작 취약점을 찾은 것을 놓치는 것.
- `try/except EOFError`로 예외를 조용히 삼키기만 하고, 왜 EOF가 났는지(정상 종료인지 크래시인지) 확인하지 않아 같은 문제를 반복해서 만나는 것.
- 32비트 전용 바이너리를 64비트 전용 환경(또는 그 반대)에서 실행해서 애초에 실행 자체가 실패하는데, 이를 로직 문제로 오해하는 것 — `file ./chall`로 아키텍처부터 확인해야 한다.

## 막혔을 때 다음 체크
- 같은 스크립트가 멈추는 게 아니라 계속 대기 상태로 걸려 있다면(EOF가 아니라 타임아웃 문제) → REV-0997 pwntools 타임아웃(TimeoutError)이 반복될 때.
- 송수신하는 바이트가 문자열 처리 중 깨진다면 → REV-0995 Python 문자열/바이트 인코딩 오류.
- 프로세스 실행/입력 기초부터 다시 확인하고 싶다면 → REV-0266 pwntools로 프로세스 실행하고 입력 보내기.

## 미니 예제
표준입력으로 문자열을 받아 20바이트 버퍼에 `strcpy`로 그대로 복사하는(오버플로우가 있는) 예시 프로그램을 pwntools로 테스트하는 상황이다.
```c
// chall.c
#include <stdio.h>
#include <string.h>
int main() {
    char buf[20];
    printf("input: ");
    char tmp[256];
    fgets(tmp, sizeof(tmp), stdin);
    strcpy(buf, tmp);  // 취약점: buf보다 긴 입력이 들어오면 오버플로우
    printf("you said: %s", buf);
    return 0;
}
```
```python
from pwn import *
context.log_level = 'debug'

p = process('./chall')
p.recvuntil(b'input: ')
p.sendline(b'A' * 100)   # 20바이트 버퍼를 훨씬 넘는 입력

try:
    response = p.recvline()
    print(response)
except EOFError:
    print('EOF! exit code:', p.poll())  # -11 (SIGSEGV) 이면 오버플로우로 크래시난 것
```
디버그 로그와 `p.poll()` 결과를 함께 보면, 100바이트 입력이 스택을 손상시켜 프로세스가 `SIGSEGV`로 죽었고, 그래서 이후 `recvline()`이 `EOFError`를 던졌다는 인과관계를 정확히 확인할 수 있다.

## 관련 글
- REV-0997 — pwntools 타임아웃(TimeoutError)이 반복될 때
- REV-0995 — Python 문자열/바이트 인코딩 오류(UnicodeDecodeError)가 날 때
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기

## 출처/검증
- pwntools `tube` 인터페이스(`recv`, `recvline`, `recvuntil`, `recvall`, `poll`, `EOFError` 발생 조건)는 pwntools 공식 문서(docs.pwntools.com)의 `pwnlib.tubes.tube` 레퍼런스를 기준으로 정리했다(2026-09-09 검증).
- 리눅스에서 음수 종료 코드가 시그널 번호를 뜻한다는 점은 POSIX `wait(2)`/`waitpid(2)` 매뉴얼 기준이다.
- 코드 예제는 `pip install pwntools` 환경의 표준 CPython 3 + 리눅스에서 재현 가능하다.
