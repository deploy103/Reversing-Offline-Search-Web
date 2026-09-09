---
id: REV-0656
title: "GDB Python 스크립팅 기초(gdb.Breakpoint 등)"
slug: "rev-0656-gdb-python-scripting-basics"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb python", "gdb.Breakpoint", "gdb 스크립팅", "gdb.execute", "gdb.parse_and_eval", "자동화 브레이크포인트"]
aliases: ["gdb 파이썬 API", "gdb 파이썬 스크립트", "gdb-python", "gdb 자동화"]
symptom_keywords: ["같은 브레이크포인트를 계속 continue만 치고 있음", "루프 안에서 값을 자동으로 기록하고 싶음", "gdb 명령을 매번 수동으로 반복 입력 중"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB는 Python 인터프리터가 내장되어 있어서, `gdb.Breakpoint`를 상속한 클래스의 `stop()` 메서드로 "이 지점에 멈출 때마다 자동으로 값을 읽고, 조건에 안 맞으면 다시 실행을 이어가라"는 로직을 짤 수 있고, 이걸로 수동 `continue` 반복을 없애고 루프/브루트포스성 분석을 자동화할 수 있다.

## 언제 검색해야 하나
- `break strcmp` 같은 브레이크포인트가 루프 안에서 수백 번 걸려서 `continue`를 수백 번 쳐야 하는 상황일 때
- 특정 함수가 호출될 때마다 인자 값을 자동으로 기록/출력하고, 조건이 맞을 때만 진짜로 멈추게 하고 싶을 때
- GDB `.gdbinit`이나 CTF 문제에서 `.py` 확장자의 GDB 스크립트를 보고 이게 뭘 하는 건지 읽어야 할 때

## 핵심 개념

### GDB에 Python이 내장돼 있다
현대 GDB(Ubuntu/Debian 기본 패키지 포함 대부분의 배포판)는 `--with-python` 옵션으로 빌드되어 Python 인터프리터를 내장하고 있다. GDB 프롬프트에서 바로 확인할 수 있다:
```
(gdb) python print("hello from gdb python")
hello from gdb python
```
한 줄짜리 명령은 `python <코드>`(별칭 `py`)로 실행하고, 여러 줄을 대화형으로 입력하려면 `python` 또는 `pi`(python-interactive)만 치고 엔터를 누른 뒤 코드를 여러 줄 입력하다가 `end`로 마무리한다.

### gdb 모듈 — GDB를 제어하는 Python API
GDB는 자체 `gdb` 모듈을 Python 쪽에 노출한다. 대표적인 것들:
- `gdb.execute("break main", to_string=True)` — 일반 GDB 명령을 문자열로 실행. `to_string=True`면 출력이 화면 대신 문자열로 반환된다.
- `gdb.parse_and_eval("$rdi")` — GDB 표현식을 평가해서 `gdb.Value` 객체로 반환. 레지스터, 변수, 역참조(`*(int*)$rsp`) 모두 가능하다.
- `gdb.selected_frame()` — 현재 선택된 스택 프레임 객체를 반환. `.read_var("변수명")`으로 지역 변수도 읽을 수 있다.
- `gdb.Breakpoint` — 브레이크포인트를 클래스로 감싸서 동작을 커스터마이즈하는 핵심 클래스.
- `gdb.FinishBreakpoint` — 현재 프레임이 리턴할 때 자동으로 멈추는 특수 브레이크포인트(REV-0657의 `finish` 명령을 스크립트로 자동화한 버전). `return_value` 속성으로 리턴값을 읽는다.

### gdb.Breakpoint와 stop() — 핵심 패턴
`gdb.Breakpoint`를 상속해서 `stop()` 메서드를 오버라이드하면, 그 브레이크포인트에 걸릴 때마다 이 메서드가 호출된다. **`stop()`이 `True`를 반환하면 GDB가 실제로 멈추고, `False`를 반환하면 자동으로 실행을 계속 이어간다.** 이게 "수동으로 continue를 반복하지 않아도 되는" 핵심 메커니즘이다.

```python
import gdb

class CountingBreak(gdb.Breakpoint):
    def __init__(self, location):
        super().__init__(location)
        self.hit_count = 0

    def stop(self):
        self.hit_count += 1
        arg1 = gdb.parse_and_eval("$rdi")
        arg2 = gdb.parse_and_eval("$rsi")
        print(f"[{self.hit_count}] strcmp(0x{int(arg1):x}, 0x{int(arg2):x})")
        return False  # 멈추지 않고 자동으로 계속 진행

CountingBreak("strcmp")
```
이 스크립트를 `trace_strcmp.py`로 저장하고 `gdb -q -x trace_strcmp.py ./chall` 로 실행하면, `strcmp`가 호출될 때마다 인자가 자동으로 출력되면서 프로그램이 끊기지 않고 계속 실행된다.

### 이벤트 훅 — gdb.events
브레이크포인트를 굳이 걸지 않아도 전역 이벤트에 콜백을 등록할 수 있다.
```python
def on_exit(event):
    print(f"exit code = {event.exit_code}")

gdb.events.exited.connect(on_exit)
```
`gdb.events.stop`(어떤 이유로든 정지할 때), `gdb.events.exited`(프로세스 종료), `gdb.events.new_objfile`(공유 라이브러리 로드) 등이 자주 쓰인다.

### 스크립트 로딩 방법
- `source script.py` — GDB 프롬프트에서 직접 로드. 확장자가 `.py`면 Python으로, `.gdb`면 기존 GDB 명령 스크립트로 자동 인식한다.
- `gdb -x script.py ./chall` — 실행과 동시에 스크립트 로드.
- `.gdbinit`/`gdbinit.d` 안에서 `source ~/my_script.py`로 항상 자동 로드되게 설정 가능. Pwndbg, GEF, peda 같은 도구들도 결국 이 방식으로 GDB에 Python 스크립트를 얹은 것이다.

## 화면/코드에서 보이는 징후
CTF 문제 저장소나 write-up에 `solve.py`가 아니라 `.gdbinit` 파일 안에 `python`으로 시작하는 블록이나, 별도의 `*.py` 파일을 `gdb -x`로 로드하라는 안내가 있다면 GDB Python 스크립팅을 활용하는 것이다. 코드 안에 `class ... (gdb.Breakpoint):`, `def stop(self):`, `gdb.execute(...)` 패턴이 보이면 이 문서의 내용이 바로 적용된다.

## 가장 먼저 할 것
GDB에 Python이 제대로 빌드되어 있는지부터 확인한다:
```bash
gdb -q -ex "python print(gdb.VERSION)" -ex quit
```
오류 없이 버전 문자열이 출력되면 Python 지원이 켜져 있는 것이다. 이후 위 `CountingBreak` 예제를 그대로 파일로 저장해 실행해보면서 감을 잡는 것이 가장 빠르다.

## 단계별 절차

**1) 목표 함수와 읽고 싶은 값 정하기**
예: `scanf` 호출마다 두 번째 인자(버퍼 주소)를 기록하고 싶다고 하자.

**2) 클래스 작성**
```python
import gdb

class ScanfWatch(gdb.Breakpoint):
    def stop(self):
        buf = gdb.parse_and_eval("$rsi")
        print(f"scanf buffer = {buf}")
        return False

ScanfWatch("scanf")
```

**3) 조건부로 진짜 멈추게 하기**
특정 조건일 때만 실제로 정지하고 싶으면 `return True`를 조건 안에 넣는다:
```python
class StrcmpBreak(gdb.Breakpoint):
    def stop(self):
        arg1 = gdb.parse_and_eval("(char*)$rdi").string()
        if arg1.startswith("A"):
            print(f"A로 시작하는 입력 발견: {arg1}")
            return True  # 이번엔 진짜로 멈춘다
        return False

StrcmpBreak("strcmp")
```

**4) 실행**
```bash
gdb -q -x script.py ./chall
(gdb) run
```

**5) 종료 시 통계 출력하기**
`gdb.events.exited`를 연결해서 마지막에 호출 횟수 요약을 찍을 수 있다.
```python
bp = ScanfWatch("scanf")
def summary(event):
    print(f"총 scanf 호출 횟수 관련 정보는 별도 카운터로 추적")
gdb.events.exited.connect(summary)
```

## 명령어/단축키
```bash
gdb -q -x script.py ./chall          # 스크립트와 함께 실행
(gdb) source script.py               # 실행 중 스크립트 로드
(gdb) python print("hi")             # 한 줄 파이썬 실행
(gdb) pi                             # 대화형 파이썬 REPL 진입 (python-interactive)
(gdb) python-interactive             # pi의 전체 이름
```

## 출력 해석
```
$ gdb -q -x trace_strcmp.py ./chall
Breakpoint 1 at 0x401040
Starting program: /home/user/chall
[1] strcmp(0x7ffd12340a10, 0x402004)
[2] strcmp(0x7ffd12340a10, 0x402010)
Wrong password.
[Inferior 1 (process 12345) exited with code 01]
```
`[1]`, `[2]` 접두어는 우리가 만든 `CountingBreak.stop()` 안의 `self.hit_count`가 매 호출마다 증가하며 출력된 것이다. 프로그램이 멈추지 않고 끝까지 실행되어 `[Inferior ... exited]`까지 자동으로 도달한 것이 핵심 — `stop()`이 계속 `False`를 반환했기 때문에 사람이 `continue`를 한 번도 안 눌러도 됐다.

## 흔한 실수
- `stop()`에서 `return` 문 자체를 빠뜨리는 것 — 파이썬에서 값 없는 `return`이나 함수 끝까지 실행되면 `None`을 반환하는데, GDB는 이를 `False`(멈추지 않음)로 취급하지 않고 예외를 던지거나 예측 못한 동작을 할 수 있다. 항상 `True`/`False`를 명시적으로 반환한다.
- `gdb.parse_and_eval`의 결과인 `gdb.Value`를 그냘 `print()`에 넣고 정수 연산을 시도하다 타입 에러가 나는 것 — 정수로 쓰려면 `int(value)`로 변환해야 한다.
- 브레이크포인트 위치 문자열(`"strcmp"`, `"*0x401136"`)에 오타가 있으면 `gdb.Breakpoint` 생성 시 조용히 실패하거나 "Function \"xxx\" not defined" 에러가 난다 — `info breakpoints`로 실제 등록됐는지 확인한다.
- PIE 바이너리에서 심볼 이름 대신 고정 주소로 브레이크포인트를 걸면 ASLR 때문에 실행마다 주소가 달라져 브레이크포인트가 엉뚱한 곳에 걸린다(REV-0103, REV-0194 참고) — 가능하면 심볼 이름이나 `break *(0x555555554000 + offset)` 같은 base 상대 표현을 쓴다.

## 막혔을 때 다음 체크
- 리턴값만 자동으로 확인하고 싶다면 수동 `finish`보다 `gdb.FinishBreakpoint`가 더 편하다 → REV-0657 GDB finish로 반환값 확인하기
- 원격 프로세스를 디버깅하면서 같은 스크립트를 쓰고 싶다면 → REV-0658 GDB 원격 디버깅(gdbserver) 기초
- Pwndbg/GEF 자체가 이런 Python 스크립팅으로 만들어진 확장이라는 걸 알고 싶다면 → REV-0192 Pwndbg 설치와 실행, REV-0286 Pwndbg 명령어 치트시트
- 기본 브레이크포인트 문법 자체가 헷갈린다면 → REV-0186 GDB break와 address breakpoint

## 미니 예제
`strcmp` 인자를 자동 기록하면서, 특정 접두사가 나올 때만 멈추는 완전한 스크립트:
```python
import gdb

class SmartBreak(gdb.Breakpoint):
    def __init__(self):
        super().__init__("strcmp")
        self.count = 0

    def stop(self):
        self.count += 1
        try:
            s1 = gdb.parse_and_eval("(char*)$rdi").string()
        except Exception:
            s1 = "<읽기 실패>"
        print(f"[{self.count}] strcmp arg1 = {s1!r}")
        if s1.startswith("flag"):
            print(">>> flag 관련 문자열 비교 발견, 여기서 멈춤")
            return True
        return False

SmartBreak()
gdb.execute("run")
```
```bash
$ gdb -q -x smart.py ./chall
[1] strcmp arg1 = 'test'
[2] strcmp arg1 = 'flag{fake_prefix}'
>>> flag 관련 문자열 비교 발견, 여기서 멈춤

Breakpoint 1, 0x0000555555555169 in strcmp ()
```

## 관련 글
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-0658 — GDB 원격 디버깅(gdbserver) 기초
- REV-0186 — GDB break와 address breakpoint
- REV-0284 — GDB 명령어 치트시트
- REV-0192 — Pwndbg 설치와 실행

## 출처/검증
- `gdb.Breakpoint`, `gdb.FinishBreakpoint`, `gdb.events`, `gdb.parse_and_eval`, `python`/`pi` 명령: GDB 공식 매뉴얼 "Python API" 챕터(`gdb.org` 온라인 문서) 기준.
- `stop()` 반환값에 따른 자동 재개 동작: GDB Python API `Breakpoint.stop()` 문서 설명 기준 (2026-09-08 검증).
