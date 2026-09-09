---
id: REV-0997
title: "pwntools 타임아웃(TimeoutError)이 반복될 때"
slug: "rev-0997-pwntools-timeouterror"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [pwntools, Python]
keywords: ["pwntools timeout", "recvuntil 무한대기", "pwntools 멈춤", "PwnlibException timeout", "pwntools 버퍼링"]
aliases: ["pwntools 타임아웃 원인", "recvuntil이 안 끝남", "pwntools 스크립트가 멈춰있음", "pwntools hang"]
symptom_keywords: ["pwntools에서 계속 대기만 함", "recvuntil이 끝나지 않음", "스크립트가 멈춘 것처럼 보임", "pwntools TimeoutError가 반복됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
pwntools에서 `recv` 계열 호출이 지정된 시간(기본은 무한 대기) 동안 응답을 못 받아 멈추거나 `TimeoutError`를 반환하는 것은, 대부분 프로그램이 실제로 안 죽었는데도 stdout 버퍼링 때문에 기대한 시점에 데이터를 내보내지 않거나, `recvuntil()`의 구분자가 실제 출력과 일치하지 않아 pwntools가 계속 더 받으려고 기다리기 때문이다.

## 언제 검색해야 하나
- 스크립트를 실행했더니 아무 에러도 안 나고 그냥 멈춘 것처럼 화면이 정지할 때
- `recv(timeout=N)`처럼 타임아웃을 명시했는데 매번 `TimeoutError` 또는 빈 데이터가 반환될 때
- 프로그램을 손으로 터미널에서 실행하면 출력이 바로바로 나오는데, pwntools로 돌리면 출력이 한참 뒤에 몰아서 나오거나 아예 안 나올 때
- 반복 실행 스크립트가 특정 반복에서만 멈춰서 자동화가 끝까지 안 도는데 원인을 모를 때

## 핵심 개념
pwntools의 `recv()`/`recvline()`/`recvuntil()`은 기본적으로 "필요한 만큼 데이터가 올 때까지 계속 기다리는" 블로킹(blocking) 함수다. `timeout` 인자를 안 주면 사실상 무한정 기다리기 때문에, 대상이 그 데이터를 영영 안 보내는 상황에서는 스크립트가 멈춘 것처럼 보인다. 타임아웃이 반복되는 원인은 크게 세 갈래로 나뉜다.

1. **stdout 버퍼링 차이** — C의 표준 라이브러리는 출력 대상이 터미널(tty)인지 파이프(pipe)인지에 따라 버퍼링 방식을 자동으로 바꾼다. 터미널로 직접 출력할 때는 보통 **줄 단위 버퍼링**(개행마다 즉시 출력)이지만, 파이프로 연결되면(즉 pwntools의 `process()`가 대상을 실행하는 방식이 정확히 이것이다) **완전 버퍼링**(내부 버퍼가 다 찰 때까지, 혹은 프로그램이 종료될 때까지 출력을 미룸)으로 바뀐다. 그래서 사람이 터미널에서 실행하면 즉시 보이던 프롬프트가, pwntools로 실행하면 한참 뒤(또는 프로그램 종료 시점)까지 안 나올 수 있다. 이는 pwntools의 문제가 아니라 **대상 프로그램이 `setvbuf`로 버퍼링을 끄지 않은 것**이 원인이다.
2. **구분자 불일치** — `recvuntil(b'구분자')`에 넘긴 바이트열이 실제 프로그램 출력과 정확히 일치하지 않으면(공백 하나, 대소문자 하나만 달라도) pwntools는 그 구분자가 나타날 때까지 영원히 기다린다.
3. **프로그램이 실제로 다른 입력을 더 기다리는 중** — 스크립트가 어떤 입력을 빠뜨렸거나 순서를 잘못 짜서, 대상 프로그램이 실제로는 응답을 준비해놓고 있지만 그전 단계에서 다른 값을 더 기다리고 있는 상태.

## 화면/코드에서 보이는 징후
```python
>>> p = process('./chall')
>>> p.recvuntil(b'password: ')
# 화면이 그대로 멈춰서 프롬프트로 안 돌아옴 (Ctrl+C로 강제 종료해야 함)
```
타임아웃을 명시했을 때는 예외 형태로 나타난다.
```python
>>> data = p.recv(timeout=3)
>>> print(data)
b''
```
빈 바이트열(`b''`)이 반환되는 것도 흔한 신호로, "타임아웃 동안 아무것도 못 받았다"는 뜻이다(EOF와 달리 예외를 던지지 않고 빈 값만 돌려주는 경우도 있다).

## 가장 먼저 할 것
`context.log_level = 'debug'`를 켜고 다시 실행해서, 실제로 어떤 데이터가 오갔는지(혹은 정말 아무것도 안 왔는지) 확인한다. 아무것도 안 왔다면 버퍼링 문제를 의심하고, 뭔가 왔는데 구분자를 못 찾는 것 같다면 구분자 철자를 재확인한다.

## 단계별 절차

**1) 디버그 로그로 실제 상황 확인**
```python
from pwn import *
context.log_level = 'debug'

p = process('./chall')
p.recvuntil(b'password: ', timeout=5)
```
로그에 아무 `[DEBUG] Received` 줄도 안 뜬다면 프로그램이 아직 아무것도 출력하지 않은 것이고, 이는 버퍼링 문제일 가능성이 크다.

**2) stdbuf로 대상 프로그램의 버퍼링을 강제로 끄기(리눅스)**
```python
from pwn import *

# 소스를 직접 못 고칠 때, 실행 자체를 stdbuf로 감싸서 라인 버퍼링을 강제
p = process(['stdbuf', '-o0', './chall'])
p.recvuntil(b'password: ')
```
`stdbuf -o0`는 표준출력 버퍼링을 아예 끄도록(unbuffered) 강제하는 리눅스 유틸리티로, 소스 수정 없이도 파이프 환경에서의 버퍼링 문제를 우회할 수 있다.

**3) 소스를 고칠 수 있다면 setvbuf로 버퍼링 자체를 끄기**
```c
#include <stdio.h>
int main() {
    setvbuf(stdout, NULL, _IONBF, 0);  // 표준출력 버퍼링 끄기
    // ... 이후 로직
}
```
CTF 문제 바이너리 자체를 수정할 수 없는 경우가 대부분이므로, 이 방법은 주로 자기가 직접 작성한 테스트용 바이너리를 디버깅할 때 쓴다.

**4) recvuntil 대신 짧은 timeout으로 recv를 반복하며 실제 출력 확인**
```python
from pwn import *
p = process('./chall')

import time
time.sleep(0.5)
data = p.recv(timeout=2)
print(repr(data))  # 실제로 뭐가 왔는지 정확히 확인 (repr로 공백/개행까지 눈에 보이게)
```
`repr()`로 감싸서 출력하면 공백(` `), 탭, 개행(`\n`) 같은 눈에 안 보이는 문자까지 정확히 드러나므로, `recvuntil()` 구분자를 정확히 맞추는 데 큰 도움이 된다.

**5) 타임아웃을 명시해서 무한 대기 대신 빠르게 실패시키기**
```python
try:
    data = p.recvuntil(b'password: ', timeout=3)
except PwnlibException:
    print('3초 안에 구분자를 못 찾음 - 구분자나 버퍼링 문제 의심')
    print(repr(p.recv(timeout=1)))  # 지금까지 온 데이터라도 확인
```
개발/디버깅 단계에서는 항상 짧은 `timeout`을 명시해서, 무한정 멈춰 있는 대신 빠르게 실패하고 원인을 확인하는 루프를 만드는 것이 효율적이다.

## 명령어/단축키
- `p.recv(timeout=N)` / `p.recvline(timeout=N)` / `p.recvuntil(b'sep', timeout=N)` : N초 안에 못 받으면 타임아웃 처리
- `context.log_level = 'debug'` : 실제 송수신 바이트 전부 로그로 확인
- `stdbuf -o0 명령` : 리눅스에서 대상 프로그램의 stdout 버퍼링을 강제로 끄고 실행
- `repr(data)` : 수신 데이터의 공백/개행/제어문자를 눈에 보이게 출력
- `p.can_recv(timeout=N)` : 예외를 던지지 않고 "N초 안에 받을 데이터가 있는지"만 불리언으로 확인

## 출력 해석
- `b''`(빈 바이트열) 반환 — 지정한 시간 동안 아무 데이터도 못 받았다는 뜻. 프로그램이 아직 출력을 안 했거나(버퍼링), 이미 다른 이유로 멈춰 있는 상태다.
- 디버그 로그에 `[DEBUG] Sent`는 찍히는데 그 뒤로 `[DEBUG] Received`가 한참 없다 — 프로그램이 입력을 받고도 응답을 만들지 못하고 있거나(내부적으로 다른 입력을 더 기다림), 응답은 만들었지만 버퍼에 갇혀서 안 나오고 있는 상태다.
- `stdbuf -o0`로 감쌌더니 즉시 데이터가 오기 시작한다 — 버퍼링이 원인이었다는 것이 확정된 것이다.

## 흔한 실수
- 터미널에서 손으로 실행했을 때 잘 되는 걸 보고 "프로그램은 정상"이라고만 결론짓고, 파이프 환경에서의 버퍼링 차이 가능성을 아예 고려하지 않는 것.
- `recvuntil()` 구분자에 개행(`\n`)이나 공백을 빠뜨려서 프로그램은 정상 출력했는데도 구분자 매칭에 실패해 계속 기다리는 것.
- 개발 중에도 `timeout`을 안 주고 계속 무한 대기 상태로 디버깅해서, 원인 파악에 오히려 시간을 더 쓰는 것 — 디버깅 단계에서는 짧은 타임아웃을 습관적으로 걸어야 한다.
- 여러 단계의 입출력 순서(프로그램이 A를 물어보고, 그다음 B를 물어보는 구조)를 스크립트에서 반대로 짜서, 프로그램이 실제로는 다른 입력을 기다리고 있는 상태를 "먹통이 됐다"고 오해하는 것.

## 막혔을 때 다음 체크
- 타임아웃이 아니라 프로세스가 아예 죽어서 생기는 문제라면 → REV-0996 pwntools 프로세스 연결이 EOFError로 끊길 때.
- 수신 데이터를 다루다 인코딩 오류가 겹친다면 → REV-0995 Python 문자열/바이트 인코딩 오류.
- 기본적인 `process`/`sendline`/`recvline` 개념부터 다시 확인하려면 → REV-0266 pwntools로 프로세스 실행하고 입력 보내기.

## 미니 예제
버퍼링 때문에 pwntools에서 응답이 안 오는 것처럼 보이는 상황을 재현한다.
```c
// chall.c (버퍼링 켜진 상태, 의도적으로 setvbuf 없음)
#include <stdio.h>
int main() {
    printf("password: ");  // 개행이 없어서 파이프 환경에서는 버퍼에 남아있을 수 있음
    char buf[64];
    scanf("%63s", buf);
    printf("you said: %s\n", buf);
    return 0;
}
```
```python
from pwn import *
context.log_level = 'debug'

p = process('./chall')
# 개행이 없는 프롬프트라도 대부분의 libc 구현은 fflush 없이도 특정 시점에 내보내지만,
# 만약 안 나온다면 stdbuf로 감싸서 확인한다
data = p.recv(timeout=2)
print(repr(data))

if data == b'':
    print('버퍼링 의심 -> stdbuf로 재시도')
    p2 = process(['stdbuf', '-o0', './chall'])
    print(repr(p2.recv(timeout=2)))
```
이렇게 `stdbuf`로 감싼 버전과 안 감싼 버전의 결과를 비교하면, 문제가 pwntools 자체가 아니라 대상 프로그램의 출력 버퍼링 방식이었다는 것을 직접 확인할 수 있다.

### 에러를 재현하는 잘못된 코드 vs 고쳐서 정상 동작하는 코드
이번에는 버퍼링이 아니라 **`recvuntil()` 구분자 불일치**로 타임아웃이 나는 상황을 재현한다. C 바이너리를 컴파일하지 않아도 되도록 파이썬 자신을 대상 프로세스로 사용하며, `pip install pwntools`만 되어 있으면 리눅스에서 그대로 실행된다. 무한정 멈추지 않도록 `timeout` 값을 짧게 줘서 안전하게 실패하도록 만든다.

**잘못된 코드 — 실제 출력과 정확히 다른 구분자를 기다려서 타임아웃 발생**
```python
from pwn import *

# 대상 프로세스: "Password:"를 콜론 뒤 공백 없이, 개행도 없이 출력한 뒤 입력을 기다림
target_script = (
    "import time\n"
    "print('Password:', end='', flush=True)\n"   # 콜론 뒤 공백 없음, 줄바꿈도 없음
    "time.sleep(0.2)\n"
    "input()\n"
    "print('done', flush=True)\n"
)

p = process(['python3', '-c', target_script])

# *** 잘못된 부분: 실제 출력에는 없는 "콜론 뒤 공백"이 들어간 구분자를 기다림 ***
try:
    data = p.recvuntil(b'Password: ', timeout=2)   # 실제 출력은 'Password:'(공백 없음)라 절대 못 찾음
    print('구분자 찾음:', data)
except PwnlibException as e:
    print('타임아웃 발생:', e)   # 2초 안에 구분자를 못 찾아서 실패
```

**고친 코드 — 구분자를 실제 출력과 정확히 맞추거나, 먼저 원본 바이트를 눈으로 확인**
```python
from pwn import *

target_script = (
    "import time\n"
    "print('Password:', end='', flush=True)\n"
    "time.sleep(0.2)\n"
    "input()\n"
    "print('done', flush=True)\n"
)

p = process(['python3', '-c', target_script])

# 고친 방법 1: 실제 출력과 정확히 같은 구분자로 수정(콜론 뒤 공백 제거)
data = p.recvuntil(b'Password:', timeout=2)
print('받은 데이터:', repr(data))

# 고친 방법 2: 구분자를 정확히 모를 때는 recv(timeout=N)으로 실제 바이트를 먼저 확인
p2 = process(['python3', '-c', target_script])
raw = p2.recv(timeout=1)
print('실제로 온 원본 바이트:', repr(raw))   # repr로 보면 공백/개행 유무를 정확히 알 수 있다
```
`repr()`로 실제 수신 바이트를 먼저 확인한 뒤 그 값을 그대로 `recvuntil()` 구분자로 옮기는 습관을 들이면, 이런 종류의 타임아웃을 크게 줄일 수 있다.

## 관련 글
- REV-0996 — pwntools 프로세스 연결이 EOFError로 끊길 때
- REV-0995 — Python 문자열/바이트 인코딩 오류(UnicodeDecodeError)가 날 때
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기

## 출처/검증
- pwntools `tube.recv`/`recvline`/`recvuntil`의 `timeout` 인자와 블로킹 동작은 pwntools 공식 문서(docs.pwntools.com)의 `pwnlib.tubes.tube` 레퍼런스를 기준으로 정리했다(2026-09-09 검증).
- 표준 C 라이브러리가 출력 대상이 tty인지 파이프인지에 따라 완전 버퍼링/줄 버퍼링을 자동 선택한다는 동작은 POSIX `setvbuf(3)` 매뉴얼 및 glibc 문서 기준이다.
- `stdbuf` 유틸리티가 `LD_PRELOAD` 기반으로 자식 프로세스의 표준 스트림 버퍼링 모드를 강제 조정한다는 점은 GNU coreutils 공식 매뉴얼 기준이다.
- 코드 예제는 `pip install pwntools` 환경의 표준 CPython 3 + 리눅스에서 재현 가능하다.
