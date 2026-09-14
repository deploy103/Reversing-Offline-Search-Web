---
id: REV-0710
title: "GDB Python 스크립트가 오류로 안 돌아갈 때"
slug: "rev-0710-gdb-python-script-error"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords:
  - gdb python
  - gdb.execute
  - gdb.Breakpoint
  - python-interpreted
  - source 명령
  - Traceback most recent call last
  - gdb.error
  - GDB 파이썬 API
symptom_keywords:
  - gdb 안에서 python 스크립트 실행하면 Traceback 에러가 뜸
  - source script.py 했더니 ModuleNotFoundError
  - gdb.error No symbol table is loaded
  - python 명령어 자체가 gdb에서 안 먹힘
  - gdb에 파이썬 지원이 없다고 나옴
aliases:
  - gdb 파이썬 스크립트 오류
  - gdb python 안 됨
  - gdb.execute 에러
  - gdb Breakpoint 스크립트 실패
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB Python 스크립트가 실행되지 않는 원인은 거의 항상 다음 세 가지 중 하나다: (1) GDB 바이너리 자체가 Python 지원 없이 빌드되어 `python` 명령이 원천적으로 없거나, (2) 스크립트가 실행되는 시점에 아직 프로세스가 시작되지 않아 `gdb.execute`가 요구하는 프레임/레지스터/심볼 정보가 없어서 `gdb.error`가 발생하거나, (3) `source script.py`로 불러온 모듈이 시스템 Python과 GDB에 내장된 Python 인터프리터의 경로/버전이 달라 `ModuleNotFoundError`가 나는 경우이며, `gdb -q --batch -ex "python print(1)"`로 Python 지원 여부부터 확인하는 것이 첫 단계다.

## 언제 검색해야 하나
- GDB 안에서 `python`으로 시작하는 명령을 쳤는데 `Undefined command: "python"`이 뜰 때
- `source myscript.py`로 스크립트를 불러왔는데 `Traceback (most recent call last):`와 함께 에러가 출력될 때
- `gdb.Breakpoint`를 상속해서 만든 커스텀 브레이크포인트 클래스가 동작 안 하거나 `stop()` 메서드가 호출 안 될 때
- 스크립트 안에서 `import pwn`이나 다른 외부 패키지를 썼는데 `ModuleNotFoundError: No module named 'pwn'`이 뜰 때

## 핵심 개념

### GDB의 Python 지원은 빌드 옵션에 달려있다
GDB는 `--with-python` 옵션으로 빌드될 때만 Python 스크립팅을 지원한다. 대부분의 배포판 패키지(`apt install gdb`)는 Python 지원이 포함되어 있지만, 일부 최소 설치 이미지나 직접 소스 빌드한 GDB는 Python 없이 빌드될 수 있다. 이 경우 `python`, `pi`(python-interactive), `source *.py` 명령 자체가 존재하지 않는다.

```gdb
(gdb) python print("hello")
Undefined command: "python".  Try "help".
```

### GDB 내장 Python과 시스템 Python은 별개의 인터프리터다
GDB는 빌드 시점에 링크한 특정 libpython 버전을 내장해서 사용한다. 시스템에 `pip install`로 설치한 패키지(예: `pwntools`)는 시스템 기본 `python3`가 사용하는 `site-packages` 경로에 설치되는데, GDB가 내장한 Python 인터프리터의 `sys.path`가 그 경로를 포함하지 않으면 `import`가 실패한다. `gdb -q -ex "python import sys; print(sys.version)"`으로 GDB가 어떤 Python 버전을 쓰는지, `python import sys; print(sys.path)`로 어떤 경로를 뒤지는지 확인할 수 있다.

### gdb.execute/gdb.Breakpoint는 "실행 컨텍스트"를 요구한다
`gdb.execute("info registers")`나 `gdb.selected_frame()` 같은 API는 **현재 실행 중인 inferior(대상 프로세스)가 있고, 그 프레임 정보가 유효할 때만** 정상 동작한다. 프로세스가 아직 시작되지 않았거나(`run` 전) 이미 종료된 상태에서 이런 API를 호출하면 `gdb.error: No frame selected.`나 `gdb.error: No registers.` 같은 예외가 발생한다. 커스텀 `gdb.Breakpoint` 클래스의 `stop()` 메서드 안에서 레지스터를 읽는 코드를 짤 때 특히 자주 만나는 문제다.

### source 명령의 확장자 인식
`source script.py`처럼 `.py` 확장자면 GDB가 Python으로 해석하고, `.gdb` 확장자거나 확장자가 없으면 기존 GDB 스크립트 언어로 해석한다. `.py` 확장자를 빠뜨리고 `source script`처럼 쓰면 GDB 커맨드 언어로 잘못 해석되어 알 수 없는 명령 에러가 난다.

## 화면/코드에서 보이는 징후
- `Undefined command: "python".` — Python 미지원 GDB 빌드
- `Traceback (most recent call last): ... ModuleNotFoundError: No module named 'xxx'` — 경로/버전 불일치
- `gdb.error: No frame selected.` — 프로세스가 실행 중이 아닌데 프레임/레지스터 접근 시도
- `Python Exception <class 'gdb.error'>: No symbol "xxx" in current context.` — 아직 로드 안 된 심볼 참조

## 가장 먼저 할 것
1. `gdb -q --batch -ex "python print(1)"`로 Python 지원 여부부터 확인한다.
2. 에러 메시지의 `Traceback` 마지막 줄(가장 구체적인 예외 타입/메시지)을 정확히 읽는다 — GDB Python 에러도 일반 Python 예외와 동일한 형식으로 출력된다.
3. `gdb.execute`/`gdb.selected_frame()` 관련 에러라면, 그 코드가 실행되는 시점에 inferior가 실제로 실행 중이었는지(`run` 이후인지)부터 확인한다.

## 단계별 절차

**1) Python 지원 여부 확인**
```bash
$ gdb -q --batch -ex "python print(gdb.VERSION)"
14.1
```
버전이 정상 출력되면 Python 지원 O. `Undefined command`가 뜨면 Python 없이 빌드된 GDB다 — `apt install gdb`로 배포판 패키지를 다시 설치하거나, `--with-python`으로 다시 빌드해야 한다.

**2) GDB가 사용하는 Python 인터프리터와 경로 확인**
```gdb
(gdb) python import sys; print(sys.version)
3.11.6 (main, ...) [GCC ...]
(gdb) python import sys; print(sys.path)
['/usr/lib/python3.11', ..., '/usr/lib/python3/dist-packages']
```
`pip install --user pwntools`로 설치했다면 그 패키지가 설치된 경로(`~/.local/lib/python3.11/site-packages`)가 이 목록에 없을 수 있다. 없다면 스크립트 맨 앞에 다음을 추가한다.
```python
import sys, site
sys.path.append(site.getusersitepackages())
```

**3) source로 스크립트 불러올 때 확장자와 경로 확인**
```gdb
(gdb) source ./myscript.py
```
상대 경로는 GDB를 실행한 현재 작업 디렉터리 기준이다. 절대 경로를 쓰면 헷갈림을 줄일 수 있다. `~/.gdbinit`에 `source`를 넣어 자동 로드할 수도 있다.

**4) 실행 컨텍스트 에러(No frame selected 등) 대응**
```python
import gdb

class MyBreakpoint(gdb.Breakpoint):
    def stop(self):
        try:
            rax = gdb.selected_frame().read_register("rax")
            print(f"rax = {rax}")
        except gdb.error as e:
            print(f"[!] register read failed: {e}")
        return False  # 계속 실행

MyBreakpoint("vuln_func")
```
`stop()` 메서드는 브레이크포인트가 실제로 히트했을 때만 호출되므로 이 시점에는 프레임이 유효하다. 반대로 스크립트 최상단(모듈 로드 시점)에서 바로 `gdb.selected_frame()`을 호출하면 아직 `run` 전이라 실패한다 — 이런 호출은 반드시 `stop()`처럼 실제로 프로세스가 멈춘 시점의 콜백 안에 넣어야 한다.

**5) 에러 스택트레이스를 그대로 읽고 줄 번호 대조**
```
Traceback (most recent call last):
  File "myscript.py", line 12, in stop
    rax = gdb.selected_frame().read_register("rax")
gdb.error: No frame selected.
```
`line 12`가 실제 문제 지점이다. 일반 Python 디버깅과 동일하게 접근하면 된다.

**6) pwndbg와 함께 쓸 때의 주의**
pwndbg 자체가 방대한 Python 코드로 구현되어 있어, 커스텀 스크립트에서 pwndbg 내부 모듈을 import하려면 pwndbg의 `sys.path` 설정이 먼저 로드된 이후여야 한다. `~/.gdbinit`에서 pwndbg `source` 이후에 자신의 스크립트를 `source`하도록 순서를 맞춘다.

## 명령어/단축키
```bash
gdb -q --batch -ex "python print(gdb.VERSION)"   # Python 지원 여부 확인
```
```gdb
python import sys; print(sys.path)   # GDB 내장 파이썬 모듈 경로 확인
source ./script.py                    # 파이썬 스크립트 로드
pi                                    # python-interactive, REPL 진입
```

## 출력 해석
- `Undefined command: "python".` → GDB가 Python 없이 빌드됨. 패키지 재설치가 가장 빠른 해결책.
- `ModuleNotFoundError` → `sys.path`에 해당 패키지 경로가 없음. 경로 추가 또는 시스템 전역(`sudo pip install`) 설치로 해결.
- `gdb.error: No frame selected.` / `No registers.` → 프로세스가 실행 중이 아닌 시점에 프레임/레지스터를 읽으려 한 것. 콜백 위치를 점검.
- `Python Exception <class 'gdb.error'>: No symbol "xxx" in current context.` → 심볼이 아직 로드되지 않았거나(공유 라이브러리 로드 전) strip되어 없는 심볼을 참조한 것.

## 흔한 실수
- 시스템 `python3 script.py`로 먼저 테스트하고 잘 되니까 GDB 안에서도 그대로 될 거라 가정하는 것 — `gdb`, `import gdb` API는 시스템 Python 스크립트에서 쓸 수 없고, 반드시 GDB 안에서 `source`로 실행해야 `gdb` 모듈이 존재한다.
- `pip install`로 설치한 패키지가 GDB 내장 Python과 다른 버전/경로를 가리켜서 계속 `ModuleNotFoundError`가 나는데 원인을 못 찾는 것 — `python import sys; print(sys.path)`로 직접 확인하는 습관이 중요하다.
- 브레이크포인트 콜백 밖에서 레지스터/프레임 API를 호출해서 `No frame selected` 에러를 계속 만나는 것.
- 에러가 나면 무조건 스크립트를 처음부터 다시 쓰는 것 — Traceback의 마지막 줄(예외 타입과 메시지)과 줄 번호만 봐도 원인의 8할은 바로 드러난다.

## 막혔을 때 다음 체크
- GDB Python API로 무엇부터 시작해야 할지 개요가 필요하다면 → REV-0656(GDB Python 스크립팅 기초)
- Pwndbg 명령 자체가 이상하게 동작한다면 → REV-0709(Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때)
- 심볼 자체가 안 보여서 스크립트가 실패하는 것 같다면 → REV-0093(nm으로 심볼 찾기)

## 미니 예제
```gdb
(gdb) source hook.py
Traceback (most recent call last):
  File "hook.py", line 3, in <module>
    import pwn
ModuleNotFoundError: No module named 'pwn'
```
```gdb
(gdb) python import sys; print(sys.path)
['/usr/lib/python3.11', '/usr/lib/python3.11/lib-dynload']
```
```python
# hook.py 맨 위에 추가
import sys, site
sys.path.append(site.getusersitepackages())
import pwn
```
```gdb
(gdb) source hook.py
(gdb)
```
경로를 추가한 뒤 재실행하면 정상적으로 로드된다.

## 관련 글
- REV-0709 — Pwndbg에서 heap 명령이 이 glibc 버전에서 지원 안 된다고 할 때
- REV-0093 — nm으로 심볼 찾기
- REV-0713 — GDB에서 레지스터를 수정했는데 반영이 안 되는 것처럼 보일 때

## 출처/검증
- GDB Python API(`gdb.execute`, `gdb.Breakpoint`, `gdb.error`, `gdb.selected_frame`) 동작: GDB 공식 문서(sourceware.org) "Extending GDB" > "Python API" 챕터 기준.
- `--with-python` 빌드 옵션과 Python 미지원 시 `python` 명령 부재: GDB 공식 문서 "Python Support" 섹션 기준.
- `source` 명령의 확장자 기반 언어 판별(.py는 Python으로 해석): GDB 공식 문서 "Command Files" 섹션 기준 (2026-09-08 확인).
