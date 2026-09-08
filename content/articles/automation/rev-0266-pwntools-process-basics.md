---
id: REV-0266
title: "pwntools로 프로세스 실행하고 입력 보내기"
slug: "rev-0266-pwntools-process-basics"
category: "automation"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python, pwntools]
keywords: ["pwntools", "process()", "sendline", "recvline", "interactive()", "CTF 자동화", "pwn 스크립트", "exploit 스크립트", "리눅스 바이너리 실행"]
aliases: ["pwn 라이브러리", "python pwn", "from pwn import *", "pwntools 프로세스 실행"]
symptom_keywords: ["pwntools 어떻게 씀", "process 실행하고 입력 어떻게 보냄", "sendline recvline 차이", "pwn 스크립트 처음", "인터랙티브 모드 어떻게 씀"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`pwntools`는 CTF/리버싱에서 로컬 바이너리를 반복 실행하며 입력을 자동으로 넣고 출력을 파싱하는 작업을 몇 줄로 끝내주는 파이썬 라이브러리로, `process()`로 대상을 실행하고 `sendline()`/`recvline()`으로 표준입출력을 주고받다가 `interactive()`로 사람이 직접 조작하는 모드로 넘어갈 수 있다.

## 언제 검색해야 하나
- 손으로 터미널에 매번 값을 입력하며 바이너리를 테스트하는 게 너무 느려서 스크립트로 자동화하고 싶을 때
- CTF 문제 바이너리를 브루트포스나 반복 실행으로 풀어야 하는데 파이썬으로 어떻게 프로세스를 다뤄야 할지 모를 때
- `pwn` 모듈을 import하는 라이트업(writeup) 코드를 봤는데 `process`, `sendline`, `recvline`, `interactive` 같은 함수의 의미를 모를 때
- 리버싱으로 찾은 검증 로직을 실제 실행 파일에 자동으로 넣어서 정답인지 확인하고 싶을 때

## 핵심 개념
`pwntools`는 원래 익스플로잇 개발(pwn)을 위한 라이브러리지만, 리버싱에서도 "바이너리를 실행하고 입력을 넣고 출력을 읽는" 반복 작업을 자동화하는 용도로 매우 자주 쓰인다. 핵심은 세 가지 객체/함수다.

1. **`process()`** — 로컬 실행 파일을 서브프로세스로 띄우고, 그 프로세스의 표준입력(stdin)/표준출력(stdout)/표준에러(stderr)에 연결된 파이프를 돌려준다. 반환값(보통 변수 `p`)은 "튜브(tube)"라는 공통 인터페이스를 갖는데, 이 인터페이스는 `process()`뿐 아니라 `remote()`(TCP 소켓 연결)에도 똑같이 적용된다. 즉 로컬에서 스크립트를 다 만들고 나중에 `remote('host', port)`로 한 줄만 바꾸면 원격 서버 문제에도 그대로 쓸 수 있다.
2. **송신 함수** — `p.send(data)`는 바이트를 그대로 보내고, `p.sendline(data)`는 끝에 개행문자(`\n`)를 자동으로 붙여서 보낸다. C의 `scanf("%s")`나 `fgets()`처럼 줄 단위로 입력을 읽는 프로그램에는 거의 항상 `sendline()`을 쓴다.
3. **수신 함수** — `p.recv(n)`은 최대 n바이트를 읽고, `p.recvline()`은 개행문자가 나올 때까지 한 줄을 읽으며, `p.recvuntil(b'구분자')`는 지정한 바이트열이 나올 때까지 누적해서 읽는다. 프로그램이 "Enter password: " 같은 프롬프트를 출력한 뒤 입력을 기다리는 구조라면, 먼저 `recvuntil(b': ')`로 프롬프트를 다 읽어치운 다음 `sendline()`으로 답을 보내는 순서가 정석이다.

여기에 더해 `p.interactive()`는 지금까지 자동화된 송수신을 잠깐 멈추고, 터미널을 프로세스에 직접 연결해서 사람이 손으로 입력/관찰할 수 있게 해준다. 자동화 스크립트로 여기까지 진행시켜 놓고, 마지막 셸이나 인터랙티브 메뉴만 손으로 조작하고 싶을 때 유용하다.

`pwntools`는 서드파티 패키지이므로 `pip install pwntools`로 먼저 설치해야 동작한다. 이 프로젝트는 오프라인 대회 환경을 기본 전제로 하므로, 인터넷이 없는 PC에서 미리 wheel 파일을 받아 설치하는 절차는 툴킷 카테고리(`../tools/` 아래, 추후 작성될 오프라인 패키지 준비 문서)에서 별도로 다룬다. 지금 이 문서는 이미 설치가 끝났다는 전제로 사용법만 다룬다.

## 화면/코드에서 보이는 징후
- 라이트업 코드 맨 위에 `from pwn import *`라는 줄이 있다 — pwntools의 거의 모든 것(process, remote, p32, p64, log 등)을 한 번에 가져오는 관용적인 표현이다.
- `p = process('./chall')`처럼 상대경로로 바이너리를 실행하는 코드가 보인다.
- `p.sendline(b'...')`에서 문자열 앞에 `b`가 붙어 바이트열(bytes)로 되어 있다 — 파이썬 3에서 pwntools는 네트워크/프로세스 입출력을 문자열이 아니라 바이트열로 다루는 것이 기본이다.
- 스크립트 실행 시 터미널에 `[+] Starting local process './chall': pid 12345` 같은 로그가 출력된다.
- 스크립트 끝부분에 `p.interactive()` 호출이 있고, 그 이후로는 사람이 직접 셸처럼 입력하는 모습이 보인다.

## 가장 먼저 할 것
대상 바이너리가 실제로 실행 가능한지(`chmod +x`, 아키텍처가 현재 시스템과 맞는지) 터미널에서 직접 한 번 실행해서 확인한다. pwntools 스크립트가 이상하게 멈추거나 에러가 나는 원인의 상당수는 pwntools 문제가 아니라 바이너리 자체가 실행 권한이 없거나, 32비트 바이너리를 64비트 전용 환경에서 돌리려는 경우다. 그다음 `python3 -c "import pwn"`으로 pwntools가 설치되어 있는지 확인한다.

## 단계별 절차

**1) 설치 확인**

```bash
pip install pwntools
python3 -c "import pwn; print(pwn.__version__)"
```

**2) 기본 스크립트 뼈대 작성**

```python
from pwn import *

# 대상 바이너리를 로컬 프로세스로 실행
p = process('./chall')

# 프로그램이 먼저 프롬프트를 출력하는 경우, 그 부분을 다 읽어치운다
p.recvuntil(b'password: ')

# 값을 보낸다 (개행 자동 추가)
p.sendline(b'test1234')

# 프로그램의 응답 한 줄을 받는다
response = p.recvline()
print(response)

p.close()
```

**3) 반복 실행으로 자동 테스트**

바이너리가 매번 랜덤 시드나 여러 후보값을 검증해야 한다면, `process()`를 반복문 안에서 새로 호출해 매 시도마다 새 프로세스를 띄운다.

```python
from pwn import *

candidates = [b'abc123', b'letmein', b'flag_guess']

for c in candidates:
    p = process('./chall')
    p.recvuntil(b'password: ')
    p.sendline(c)
    result = p.recvline()
    if b'Correct' in result:
        print('found:', c)
        p.close()
        break
    p.close()
```

**4) 마지막 단계만 손으로 조작하기**

자동화로 여기까지는 다 맞췄는데 그 뒤 메뉴/셸은 직접 눌러보고 싶다면:

```python
from pwn import *

p = process('./chall')
p.recvuntil(b'password: ')
p.sendline(b'found_password')
p.interactive()  # 이후 터미널이 프로세스에 그대로 연결됨
```

`interactive()` 모드에서 빠져나오려면 보통 `Ctrl+C` 또는 `Ctrl+D`를 누른다.

## 명령어/단축키
- `process('./chall')` : 로컬 바이너리 실행, 튜브 객체 반환
- `process(['./chall', 'arg1'])` : 인자를 함께 넘기며 실행
- `p.send(data)` / `p.sendline(data)` : 바이트열 전송(개행 없음/있음)
- `p.recv(n)` / `p.recvline()` / `p.recvuntil(b'sep')` / `p.recvall()` : 수신
- `p.interactive()` : 사람이 직접 조작하는 모드로 전환
- `p.close()` : 프로세스/파이프 정리
- `context.log_level = 'debug'` : 송수신 바이트를 전부 로그로 출력(디버깅용)

## 출력 해석
- `[+] Starting local process './chall': pid 12345` — 프로세스가 정상적으로 실행됐고 PID가 12345라는 뜻. 이 로그가 안 뜨고 바로 에러가 나면 경로나 실행 권한 문제다.
- `EOFError` 예외 — 프로그램이 예상보다 일찍 종료되어(크래시나 정상 종료) 더 이상 읽을 데이터가 없을 때 발생한다. `recvline()`을 호출했는데 프로그램이 이미 죽어 있으면 이 예외가 뜬다.
- `[*] Process './chall' stopped with exit code 0 (pid 12345)` — 프로세스가 종료됐을 때 뜨는 로그. exit code가 0이 아니면 비정상 종료(크래시, assert 실패 등)를 의심한다.
- `recvuntil()`이 계속 멈춰 있다(타임아웃 없이 대기) — 지정한 구분자 바이트열이 프로그램 출력에 실제로 나타나지 않는다는 뜻. 프롬프트 문자열의 공백이나 개행 유무를 오타 없이 정확히 맞췄는지 확인해야 한다.

## 흔한 실수
- `sendline()`에 문자열(`'test'`)을 그대로 넣고 바이트열(`b'test'`)로 안 바꿔서 `TypeError`가 나는 경우 — 파이썬 3 pwntools는 기본적으로 bytes를 요구한다.
- `recvuntil()`에 넘기는 구분자가 실제 프로그램 출력과 한 글자라도(공백, 콜론 위치 등) 다르면 무한 대기에 빠진다.
- 프로세스를 여러 번 새로 만들면서 이전 `p.close()`를 안 해서 좀비 프로세스가 쌓이는 경우.
- `process()`로 실행한 로컬 테스트 스크립트를 원격 서버용으로 바꿀 때 `remote('host', port)`로 교체하는 걸 잊어서 계속 로컬만 테스트하는 경우.
- 프로그램이 버퍼링 때문에 출력을 즉시 내보내지 않아서(stdout이 파이프로 연결되면 라인버퍼링이 풀버퍼링으로 바뀌는 C 표준 동작) `recv()`가 기대한 시점에 데이터를 못 받는 경우 — 이는 pwntools 문제가 아니라 대상 프로그램이 `setvbuf`로 버퍼링을 끄지 않았을 때 흔히 발생한다.

## 막혔을 때 다음 체크
- 계속 멈춰 있다면 → `context.log_level = 'debug'`를 스크립트 맨 위에 추가해서 실제로 어떤 바이트가 오가는지 눈으로 확인한다.
- 바이트열을 어떻게 조립해야 할지 막막하면 → REV-0267 문서에서 `p32`/`p64`/`u32`/`u64`로 정수를 바이트열로 변환하는 방법을 참고한다.
- 검증 로직 자체를 자동으로 풀고 싶다면 → Z3 계열 문서(REV-0268~REV-0270)로 넘어가서 조건을 만족하는 입력값을 수학적으로 구한 뒤, 이 문서의 `sendline()`으로 그 값을 실제 바이너리에 넣어 확인하는 조합이 일반적인 CTF 자동화 흐름이다.
- 오프라인 환경에서 `pip install`이 안 된다면 → 이 프로젝트의 툴킷 문서(추후 `../tools/` 카테고리에 작성 예정)에서 다루는 오프라인 wheel 준비 절차를 참고한다.

## 미니 예제
아래는 표준입력으로 숫자를 하나 받아서 42면 "Correct!"를, 아니면 "Wrong"을 출력하는 아주 단순한 C 프로그램을 pwntools로 자동 테스트하는 전체 흐름이다.

```c
// chall.c (참고용 대상 프로그램)
#include <stdio.h>
int main() {
    int guess;
    printf("guess: ");
    scanf("%d", &guess);
    if (guess == 42) printf("Correct!\n");
    else printf("Wrong\n");
    return 0;
}
```

```python
# solve.py
from pwn import *

p = process('./chall')
p.recvuntil(b'guess: ')
p.sendline(b'42')
line = p.recvline()
print(line)  # b'Correct!\n'
p.close()
```

`python3 solve.py`로 실행하면 사람이 손으로 `42`를 입력하는 과정을 자동화해서 곧바로 `Correct!`를 확인할 수 있다.

## 관련 글
- REV-0267 — pwntools p32 p64 u32 u64
- REV-0268 — Z3 BitVec 기초
- REV-0271 — angr 심볼릭 실행 기초

## 출처/검증
- `pwntools` 공식 문서(docs.pwntools.com)의 `process`, `tube`(send/recv/interactive) API를 기준으로 정리했다(2026-09-08 검증).
- `pwntools`는 서드파티 패키지이므로 사용 전 `pip install pwntools`가 필요하다. 이 리포지토리는 오프라인 환경을 전제로 하므로, 인터넷이 없는 대회 PC에서의 오프라인 패키지 준비 절차는 툴킷 카테고리(`../tools/`)에 추후 작성될 문서에서 다룬다.
- 코드 예제는 pwntools 표준 API만 사용했으며 표준 CPython 3 + `pip install pwntools` 환경에서 직접 재현 가능하다.
