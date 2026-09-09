---
id: REV-0919
title: "알고리즘 복원 결과를 원본과 바이트 단위로 비교 검증하기"
slug: "rev-0919-byte-level-diff-verification"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["ctypes 검증", "differential testing", "원본과 재구현 비교", "바이트 단위 diff", "fuzz 비교 검증", "재구현 정확성 검증"]
aliases: ["재구현이 맞는지 확실히 확인하는 법", "ctypes로 원본 함수 직접 호출", "differential fuzzing 리버싱", "원본 대조 검증"]
symptom_keywords: ["재구현한 코드가 맞는지 100% 확신이 안섬", "몇개 테스트는 통과했는데 불안함", "원본 함수를 직접 호출해서 비교하고 싶음", "무작위 입력으로 대량 검증하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
파이썬 재구현이 몇 개의 수동 테스트 케이스를 통과했다고 완전히 신뢰하지 말고, `ctypes`로 원본 바이너리의 실제 함수를 프로세스 안에서 직접 호출해 무작위 입력 수천~수만 개에 대해 재구현과 원본의 출력을 자동으로 비교(differential testing)하면, 사람이 일일이 생각해내기 어려운 엣지 케이스에서의 불일치까지 기계적으로 찾아낼 수 있다.

## 언제 검색해야 하나
- REV-0912(유닛 테스트)로 몇 개 케이스는 통과시켰지만, 재구현이 모든 입력에 대해 정말로 원본과 동일하게 동작하는지 더 확실히 확인하고 싶을 때
- 재구현한 알고리즘을 실제 익스플로잇/솔버 스크립트에 넣기 전에, 마지막으로 신뢰도를 최대한 끌어올리고 싶을 때
- 원본 바이너리를 매번 GDB로 수동 실행해 결과를 받아오는 게 번거로워서, 자동화된 대량 비교 방법이 필요할 때
- 재구현이 특정 입력 패턴(긴 문자열, 특수 바이트, 경계값)에서만 조용히 틀리는 게 아닌지 의심될 때

## 핵심 개념

### 왜 수동 테스트만으로는 부족한가
REV-0912의 유닛 테스트는 "사람이 생각해낸 케이스"에 대해서만 검증한다. 하지만 재구현 버그는 사람이 미처 떠올리지 못한 입력(예: 특정 바이트 조합에서만 발생하는 오버플로 경계, 부호 확장 실수)에서 숨어 있는 경우가 많다. 이를 보완하는 방법이 differential testing(차분 테스트)이다 — 무작위로 대량의 입력을 생성해서 "재구현 결과"와 "원본(정답 오라클) 결과"를 기계적으로 비교하고, 하나라도 다르면 그 즉시 실패 케이스로 잡아낸다.

### ctypes로 원본 함수를 직접 호출하기
Linux ELF나 Windows DLL이라면, 원본 바이너리의 검증 함수를 파이썬 프로세스 안으로 직접 로드해서 호출할 수 있다. 이렇게 하면 GDB로 매번 수동 실행할 필요 없이, 파이썬 루프 안에서 원본 함수를 수천~수만 번 빠르게 호출하며 재구현과 자동 비교할 수 있다.

```python
import ctypes

# Linux: 공유 라이브러리(.so)이거나, 실행 파일이라도 함수 심볼이 노출되어 있으면 로드 가능
lib = ctypes.CDLL("./libcheck.so")
lib.check.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.check.restype = ctypes.c_int

def original_check(data: bytes) -> int:
    return lib.check(data, len(data))
```

대상이 완전한 실행 파일(공유 라이브러리가 아님)이라면, 함수를 직접 `dlopen`하기 어려울 수 있다. 이 경우 다음 두 대안을 쓴다.

1. **함수만 추출해 별도 공유 라이브러리로 재컴파일**: 검증 함수와 그 함수가 의존하는 최소한의 코드/데이터만 추출해 독립된 `.so`/`.dll`로 다시 빌드한다. 원본과 100% 동일한 기계어 코드를 그대로 실행하므로 가장 신뢰도가 높다.
2. **GDB/pwntools로 실행 중인 프로세스의 함수를 원격 호출**: `gdb`의 `call` 명령이나 pwntools의 `process()` + `gdb.attach()` 조합으로, 실행 중인 프로세스 안의 함수를 호출하고 결과를 받아온다. 재컴파일이 번거로울 때 쓸 수 있는 대안이지만 매 호출마다 프로세스 통신 오버헤드가 있어 `ctypes` 직접 호출보다 느리다.

### 무작위 입력으로 대량 비교하기
원본 함수를 파이썬에서 빠르게 호출할 수 있게 되면, 다음처럼 무작위 입력을 대량 생성해 재구현과 자동으로 비교한다.

```python
import os
import random

def differential_test(reimplementation, original, num_trials=10000, max_len=16):
    mismatches = []
    for _ in range(num_trials):
        length = random.randint(0, max_len)
        data = os.urandom(length)
        r1 = reimplementation(data)
        r2 = original(data)
        if r1 != r2:
            mismatches.append((data, r1, r2))
            if len(mismatches) >= 20:  # 너무 많으면 앞부분만 수집하고 중단
                break
    return mismatches
```

수만 번 실행해서 불일치가 하나도 없으면 재구현의 신뢰도가 크게 올라간다. 불일치가 발견되면, 그 구체적인 입력을 GDB로 단독 실행하며 정확히 어느 지점에서 재구현과 원본이 갈리는지 추적한다.

### 무작위 입력만으로 부족한 경우 — 경계값을 명시적으로 섞기
완전 무작위 바이트는 통계적으로 극단적인 경계값(전부 0x00, 전부 0xFF, 길이 0, 길이 최대치)에 잘 도달하지 못한다. `differential_test`에 이런 경계값을 명시적으로 섞어 넣어야 REV-0912에서 강조한 경계값 커버리지를 실질적으로 확보할 수 있다.

```python
def edge_cases(max_len=16):
    yield b""
    yield b"\x00" * max_len
    yield b"\xff" * max_len
    yield b"A" * max_len
    yield bytes(range(min(256, max_len)))
```

### 어느 정도 테스트하면 충분한가
차분 테스트는 "버그가 없다는 증명"이 아니라 "버그를 발견할 확률을 높이는 것"이다. 실전에서는 무작위 케이스 수천~수만 개 + 명시적 경계값 케이스 전부를 통과하면 실용적으로 충분한 신뢰도로 간주하고 다음 단계(익스플로잇 작성, 최종 답 제출)로 넘어간다. CTF 시간 제약을 고려할 때 무한정 테스트 횟수를 늘리는 것보다, 통과가 확인되면 실전에서는 그 신뢰도로 진행하는 것이 합리적이다.

## 화면/코드에서 보이는 징후
- 재구현 코드에 대한 확신이 서지 않아 몇 번이고 손으로 같은 케이스를 재확인하고 있음
- 원본 바이너리가 Linux ELF의 `.so`이거나, 최소한 검증 함수 심볼이 strip되지 않고 남아있어 주소를 확인할 수 있음
- 이미 REV-0912로 몇 개 케이스는 통과했지만 "혹시 모를 반례"가 걱정되는 상황

## 가장 먼저 할 것
대상 함수가 공유 라이브러리(.so/.dll)인지, 아니면 실행 파일 안에 포함되어 있는지 확인한다. 공유 라이브러리라면 바로 `ctypes.CDLL()`로 로드를 시도하고, 실행 파일이라면 함수 주소와 호출 규약(인자 개수/타입)을 확인해 재컴파일 또는 GDB 원격 호출 방식 중 하나를 선택한다.

## 단계별 절차
1. 검증 함수의 정확한 이름/주소와 인자 타입, 반환 타입을 확정한다(strip 여부에 따라 REV-0646 방식으로 주소를 찾아야 할 수 있음).
2. `ctypes.CDLL()`로 원본 함수를 로드할 수 있는지 시도한다. 안 되면 함수만 추출해 재컴파일하거나 GDB 원격 호출로 대안을 마련한다.
3. `differential_test()`로 무작위 입력 최소 수천 개를 생성해 재구현과 원본을 자동 비교한다.
4. `edge_cases()`로 정의한 명시적 경계값도 모두 통과하는지 별도로 확인한다.
5. 불일치가 발견되면 그 구체적인 입력을 기록하고, GDB로 원본을 단독 실행하며 재구현과 갈리는 지점을 한 줄씩 추적한다.
6. 불일치 원인을 재구현 코드에 반영하고, 전체 차분 테스트를 다시 돌려 모든 케이스가 통과하는지 재확인한다.

## 명령어/단축키
```python
import ctypes, os, random

lib = ctypes.CDLL("./libcheck.so")
lib.check.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.check.restype = ctypes.c_int

def original_check(data: bytes) -> int:
    return lib.check(data, len(data))

def my_check(data: bytes) -> int:
    # 재구현한 파이썬 함수
    ...

def differential_test(num_trials=10000, max_len=16):
    fails = []
    for _ in range(num_trials):
        data = os.urandom(random.randint(0, max_len))
        if my_check(data) != original_check(data):
            fails.append(data)
    return fails

print(differential_test())
```

## 출력 해석
- `differential_test()`가 빈 리스트를 반환하면 수천 개 무작위 케이스에서 불일치가 없었다는 뜻으로, 실전에서 충분히 신뢰할 만한 재구현으로 간주할 수 있다.
- 불일치 리스트에 값이 있으면, 그 각각의 입력을 재현 가능한 최소 사례로 좁혀서(가능하면 더 짧은 길이로 줄여봐서) 디버깅한다.
- 특정 길이나 특정 바이트 패턴에서만 불일치가 몰린다면, 그 조건과 관련된 코드(길이 처리, 부호 확장, 배열 경계)를 재점검해야 한다.

## 흔한 실수
- 재구현 결과가 원본과 다른데도 "어차피 이 정도면 맞겠지"라며 넘어가는 것 — 단 하나의 불일치라도 재구현에 결함이 있다는 확실한 증거이므로 반드시 원인을 찾아야 한다.
- 무작위 입력만 테스트하고 명시적 경계값(전부 0x00, 전부 0xFF, 빈 입력)을 빼먹는 것 — 무작위 샘플링은 극단적인 경계값에 도달할 확률이 낮다.
- `ctypes` 함수의 `argtypes`/`restype`을 정확히 지정하지 않아서 잘못된 타입으로 호출되어 원본이 크래시하거나 엉뚱한 값을 반환하는 것 — 원본 함수의 실제 시그니처(인자 개수, 각 인자 크기)를 디스어셈블리로 재차 확인해야 한다.
- 대상이 stripped 바이너리인데 함수 이름으로 바로 로드하려는 것 — strip된 경우 REV-0646 방식으로 함수의 정확한 오프셋을 먼저 찾아 `ctypes`에서 오프셋 기반으로 호출해야 한다.

## 막혔을 때 다음 체크
- 재구현을 유닛 테스트로 먼저 정리하는 법이 궁금하면 → REV-0912 알고리즘 복원 결과를 유닛 테스트로 검증하는 법
- strip된 바이너리에서 함수 주소를 찾는 법이 기억 안 나면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- 다단계 파이프라인의 어느 단계가 문제인지 좁혀야 한다면 → REV-0911 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- ctypes 대신 GDB로 직접 함수를 호출하는 방법이 궁금하면 → REV-0657 GDB에서 함수 반환값을 finish로 확인하는 법

## 미니 예제
REV-0906의 다항식 해시 재구현을 원본 `.so`와 비교해보자.

```python
import ctypes, os, random

lib = ctypes.CDLL("./libpolyhash.so")
lib.poly_hash.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.poly_hash.restype = ctypes.c_uint32

def original_poly_hash(data: bytes) -> int:
    return lib.poly_hash(data, len(data))

def my_poly_hash(data: bytes, base=31, mod=2**32) -> int:
    h = 0
    for c in data:
        h = (h * base + c) % mod
    return h

mismatches = []
for _ in range(20000):
    data = os.urandom(random.randint(0, 32))
    if my_poly_hash(data) != original_poly_hash(data):
        mismatches.append(data)

for edge in (b"", b"\x00"*32, b"\xff"*32, b"A"*32):
    if my_poly_hash(edge) != original_poly_hash(edge):
        mismatches.append(edge)

print(f"{len(mismatches)} mismatches out of 20004 trials")
```

이 스크립트가 `0 mismatches`를 출력하면, 재구현이 base/mod 상수까지 정확히 맞고 부호 처리·오버플로 처리까지 원본과 완전히 동일하다는 강한 확신을 가질 수 있다.

### 완전한 예제 스크립트 — 진짜 컴파일된 라이브러리와 직접 비교하기
이번에는 "원본"을 흉내내기 위해 실제로 작은 C 코드를 컴파일해서 공유 라이브러리로 만들고, 그 라이브러리를 파이썬 `ctypes`로 직접 호출해 재구현과 비교하는 전체 과정을 처음부터 끝까지 보여준다. 리눅스 환경에 `gcc`가 설치되어 있다면 그대로 따라할 수 있다.

**1단계: "원본"이라고 가정할 C 코드를 작성하고 컴파일한다.**
```c
/* libcheck.c - 실제 크랙미의 검증 함수라고 가정한다 */
#include <stdint.h>

uint32_t poly_hash(const unsigned char *data, int len) {
    uint32_t h = 0;
    for (int i = 0; i < len; i++) {
        h = h * 31u + (uint32_t)data[i];
    }
    return h;
}
```
```bash
gcc -shared -fPIC -o libcheck.so libcheck.c   # 공유 라이브러리(.so)로 컴파일
```

**2단계: 파이썬에서 `ctypes`로 이 라이브러리를 직접 불러와 재구현과 비교한다.**
```python
import ctypes    # C로 만든 공유 라이브러리를 파이썬에서 직접 호출하기 위한 표준 라이브러리
import os        # 무작위 바이트를 만들기 위한 표준 라이브러리
import random    # 무작위 길이를 정하기 위한 표준 라이브러리

lib = ctypes.CDLL("./libcheck.so")                       # 컴파일한 .so 파일을 로드
lib.poly_hash.argtypes = [ctypes.c_char_p, ctypes.c_int]  # 함수의 인자 타입을 정확히 지정 (바이트 포인터, 정수)
lib.poly_hash.restype = ctypes.c_uint32                   # 반환 타입을 지정 (부호 없는 32비트 정수)


def original_poly_hash(data: bytes) -> int:
    """실제 '원본' 함수를 그대로 호출하는 래퍼 함수."""
    return lib.poly_hash(data, len(data))


def my_poly_hash(data: bytes, base: int = 31, mod: int = 2**32) -> int:
    """리버싱해서 만든 파이썬 재구현."""
    h = 0
    for c in data:
        h = (h * base + c) % mod
    return h


def differential_test(num_trials: int = 20000, max_len: int = 32):
    """무작위 입력을 num_trials번 생성해서 재구현과 원본의 결과가 다른 경우를 모두 모은다."""
    mismatches = []
    for _ in range(num_trials):
        length = random.randint(0, max_len)     # 0바이트부터 max_len바이트까지 무작위 길이
        data = os.urandom(length)                # 그 길이만큼 무작위 바이트 생성
        if my_poly_hash(data) != original_poly_hash(data):  # 재구현과 원본을 직접 비교
            mismatches.append(data)               # 다르면 그 입력을 기록해둔다
    return mismatches


mismatches = differential_test(num_trials=20000)

# 경계값(전부 0x00, 전부 0xFF, 빈 입력, 반복된 문자)도 별도로 검사한다
for edge in (b"", b"\x00" * 32, b"\xff" * 32, b"A" * 32):
    if my_poly_hash(edge) != original_poly_hash(edge):
        mismatches.append(edge)

print(f"{len(mismatches)} mismatches out of 20004 trials")
```

실제로 컴파일하고 실행한 결과:
```
0 mismatches out of 20004 trials
```
20004번의 시도(무작위 20000번 + 경계값 4번) 전부에서 재구현과 원본이 정확히 일치했다.

**3단계: 재구현에 일부러 버그를 넣으면 정말로 잡히는지 확인해보기.**
곱셈 상수를 `31`에서 `33`으로 실수로 잘못 옮겼다고 가정하고 같은 방식으로 비교해보자.

```python
def my_poly_hash_buggy(data: bytes, base: int = 33, mod: int = 2**32) -> int:
    h = 0
    for c in data:
        h = (h * base + c) % mod   # base가 31이어야 하는데 33으로 잘못 옮겨적었다
    return h

bug_count = 0
for _ in range(2000):
    data = os.urandom(random.randint(1, 32))
    if my_poly_hash_buggy(data) != original_poly_hash(data):
        bug_count += 1

print(f"buggy mismatches out of 2000: {bug_count}")
```
실제로 실행한 결과:
```
buggy mismatches out of 2000: 1942
```
2000번 중 1942번이나 불일치가 발견됐다 — 상수 하나만 잘못 옮겨도 거의 모든 무작위 입력에서 즉시 들통난다는 것을 실제 숫자로 확인한 것이다. 이것이 differential testing이 "재구현에 대한 막연한 확신"을 "숫자로 뒷받침된 확신"으로 바꿔주는 이유다.

## 관련 글
- REV-0912 — 알고리즘 복원 결과를 유닛 테스트로 검증하는 법
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0911 — 여러 알고리즘이 순차적으로 합성된 문제 풀어내기
- REV-0657 — GDB에서 함수 반환값을 finish로 확인하는 법
- REV-0906 — Polynomial Hash(다항식 해시) 패턴 알아보기

## 출처/검증
- Differential testing(차분 테스트)이 두 구현체의 출력을 대량의 무작위 입력으로 비교해 불일치를 찾아내는 소프트웨어 검증 기법이라는 정의: 소프트웨어 테스팅 표준 기법(differential testing/fuzzing 분야)의 일반 개념 기준.
- Python `ctypes`로 공유 라이브러리 함수를 로드하고 직접 호출하는 방법(`CDLL`, `argtypes`, `restype`): Python 공식 문서(`ctypes` 모듈) 기준 (2026-09-09 검증).
