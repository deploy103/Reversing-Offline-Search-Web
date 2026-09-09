---
id: REV-0894
title: "시간 기반 시드(seed = time())를 역산하는 접근"
slug: "rev-0894-time-based-seed-recovery"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, Python]
keywords: ["srand(time(NULL))", "시간 기반 시드", "타임스탬프 브루트포스", "epoch", "unix time seed", "seed recovery"]
aliases: ["srand time null 문제", "시드가 시간이라 못 맞출 때", "타임스탬프로 시드 복원", "time() 기반 rand 공략"]
symptom_keywords: ["srand(time(NULL))이라는 코드가 보임", "실행할 때마다 결과가 다름", "시드가 초 단위 유닉스 타임인 것 같음", "파일 생성 시각으로 시드를 좁힐 수 있을 것 같음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`srand(time(NULL))`처럼 시드가 "현재 초 단위 유닉스 타임스탬프"로 결정되는 코드는 실행할 때마다 결과가 달라지는 것처럼 보이지만, 실제로는 **키 공간이 시간이라는 좁은 범위(대개 수십~수백 초)로 한정된 브루트포스 문제**로 바뀐 것뿐이다.

## 언제 검색해야 하나
- 디스어셈블리나 소스에서 `srand(time(NULL))`, `srand(time(0))`처럼 `time()`의 반환값을 그대로 `srand()`에 넘기는 코드를 발견했을 때
- 같은 바이너리를 여러 번 실행했을 때마다 결과(카드 순서, 좌표, 검증 상수 등)가 달라지는 걸 확인했지만, 짧은 시간 안에 재실행하면 값이 크게 벗어나지 않을 것 같다고 느껴질 때
- 문제 설명이나 파일 메타데이터(다운로드 시각, 서버 응답의 `Date` 헤더, 파일의 타임스탬프)로 "대략 언제 실행됐는지" 짐작할 단서가 있을 때
- REV-0893에서 다룬 `rand()`/`srand()` 재현 전략은 이미 확보했는데, 정확한 시드값 자체를 모르는 상황일 때

## 핵심 개념

### `time(NULL)`이 반환하는 값의 범위
`time(NULL)`(POSIX) 또는 `time(0)`은 1970년 1월 1일 UTC 자정(유닉스 epoch)부터 현재까지 경과한 **초** 단위 정수를 반환한다. 이 값은 32비트 부호 있는 정수 기준으로 약 21억까지 커질 수 있는 거대한 수처럼 보이지만, 실제로 CTF 문제를 풀 때는 **"언제쯤 이 프로그램이 실행됐는가"에 대한 대략적인 시간대를 알고 있다**는 전제가 성립하는 경우가 대부분이다. 예를 들어 문제 서버가 지금 이 순간 응답을 준다면, 그 응답이 생성된 시각은 지금으로부터 몇 초 이내다. 이렇게 **전체 32비트 공간이 아니라 "지금부터 앞뒤 몇 분"이라는 매우 좁은 창(window)**으로 탐색 범위가 줄어드는 것이 이 문제 유형의 핵심이다.

### 왜 이게 브루트포스 가능한 문제로 바뀌는가
REV-0219에서 다룬 "브루트포스가 가능한 입력 공간" 판단 기준을 그대로 적용하면 된다. 32비트 전체(약 43억 가지)를 다 시도하는 건 느리지만 현대 컴퓨터로도 충분히 감당 가능한 수준이고, 실행 시각을 어느 정도 좁힐 수 있다면(예: "지난 5분 이내에 실행됨" → 300가지 후보) 사실상 즉시 풀리는 문제가 된다. 전략은 다음과 같다.

1. **문제 서버/바이너리 실행 시각의 대략적인 범위를 확보**한다 — 서버 응답을 받은 시각, 파일 다운로드 시각, HTTP `Date` 헤더, 또는 로컬에서 직접 실행하는 경우라면 실행 직전/직후에 `time.time()`으로 확인.
2. 그 범위 안의 **모든 후보 초(second)마다** 시드로 넣어 `rand()` 결과를 재현(REV-0893의 방법 그대로)한다.
3. 재현한 결과가 실제 관찰한 값(암호문, 검증 상수, 화면 출력 등)과 일치하는 후보를 찾는다.

```python
import ctypes
import time

libc = ctypes.CDLL("libc.so.6")

def try_seed(seed, expected_first_value):
    libc.srand(seed)
    return libc.rand() == expected_first_value

now = int(time.time())
observed = 123456789   # 프로그램이 출력한 rand() 첫 값 (예시)

for delta in range(-120, 1):   # 실행 시점이 "지금으로부터 최대 120초 전"이라고 가정
    candidate = now + delta
    if try_seed(candidate, observed):
        print(f"시드 발견: {candidate} (delta={delta}s)")
        break
```

### 정밀도가 초 단위가 아닌 경우
일부 구현은 `time(NULL)` 대신 밀리초/마이크로초 단위 함수(`gettimeofday`, `clock()`, `GetTickCount`, `QueryPerformanceCounter`)를 시드로 쓰기도 한다. 이 경우 탐색 범위가 초 단위가 아니라 훨씬 미세한 단위로 넓어질 수 있어 순수 브루트포스가 비효율적일 수 있다. 이때는 다음을 함께 고려한다.

- **PID(프로세스 ID)와 결합된 시드**: `srand(time(NULL) ^ getpid())`처럼 PID를 섞는 경우, PID는 보통 범위가 좁으므로(리눅스 기준 최대 몇만~십만대) 시간 범위와 PID 범위를 곱한 만큼만 탐색하면 된다.
- **밀리초 단위 시드**: 탐색 폭이 1000배 늘어나지만, "정확히 몇 시 몇 분대에 실행했는가"를 좁힐 수 있다면(예: 자동화 스크립트로 실행 직후 곧바로 값을 관찰) 여전히 현실적인 범위 안에 들어온다.
- **여러 rand() 출력을 동시에 검증**: 시드 후보 하나당 `rand()`를 여러 번 호출해서 나온 값 전체가 관찰된 값들과 모두 일치하는지 검사하면, 우연히 첫 값만 일치하는 오탐(false positive)을 걸러낼 수 있다.

### 로컬에서 직접 실행할 수 있는 경우 — 가장 쉬운 우회
문제 바이너리를 로컬에서 그대로 실행할 수 있는 상황이라면, 시드를 역산할 필요조차 없다. GDB로 `time()` 함수 자체에 브레이크포인트를 걸어 반환값을 직접 확인하거나, 아예 `time()`의 반환값을 원하는 고정값으로 **패치/후킹**해서 원하는 시드가 강제로 쓰이게 만들 수 있다.

```bash
gdb ./chall
(gdb) break time
(gdb) run
(gdb) finish
# 반환값($eax/$rax)이 실제로 srand()에 들어갈 시드다 — 이 값을 그대로 기록
```
LD_PRELOAD로 `time()` 함수를 가로채 항상 원하는 값을 반환하게 만드는 것도 가능하다(REV-0650 참고).

```c
// fake_time.c — LD_PRELOAD로 time()을 가로채 고정값 반환
#include <time.h>
time_t time(time_t *t) {
    time_t fixed = 1700000000;   // 원하는 임의의 고정 시드
    if (t) *t = fixed;
    return fixed;
}
```
```bash
gcc -shared -fPIC -o fake_time.so fake_time.c
LD_PRELOAD=./fake_time.so ./chall
```
이렇게 하면 매 실행마다 시드가 고정되어, 재현성 있게 여러 번 테스트하며 로직을 분석할 수 있다.

## 화면/코드에서 보이는 징후
- `srand(time(NULL))`, `srand(time(0))`, 또는 `time` 함수 호출 결과가 `srand`의 인자로 바로 이어지는 코드
- 같은 바이너리를 반복 실행했을 때 결과가 매번 달라짐
- 실행 파일이나 문제 서버가 응답하는 타이밍에 대한 정보(HTTP 헤더의 `Date`, 파일 시스템 타임스탬프)를 얻을 수 있음
- `time()`뿐 아니라 `getpid()`, `clock()`, `GetTickCount()`가 시드 계산식에 함께 섞여 있는 경우

## 가장 먼저 할 것
시드 계산식에 `time()` 외에 다른 값(PID, 클럭 틱)이 섞여 있는지부터 확인한다. `time()` 단독이라면 초 단위 탐색 창을 얼마나 좁힐 수 있는지(문제 서버 응답 시각, 로컬 실행이면 직접 관찰)부터 확보한다.

## 단계별 절차
1. 시드 계산식을 정확히 파악 — `time(NULL)` 단독인지, PID/클럭과 XOR/덧셈으로 섞였는지 확인
2. 실행/응답 시각을 최대한 좁게 추정(서버 `Date` 헤더, 로컬 실행 직전/직후 `time.time()` 기록 등)
3. 좁힌 시간 창 전체를 대상으로 REV-0893의 방법(ctypes로 실제 libc 호출, 또는 정확한 재구현)을 이용해 시드 후보를 순회
4. 각 후보 시드로 재현한 `rand()` 결과와 실제 관찰값을 비교 — 여러 개의 출력값을 동시에 비교해 오탐 제거
5. 일치하는 시드를 찾으면 이후 필요한 모든 rand() 결과를 그대로 계산해 문제 해결
6. 로컬 실행이 가능하다면 GDB 브레이크포인트나 LD_PRELOAD 후킹으로 아예 시드를 고정시켜 반복 검증

## 명령어/단축키
```bash
# 실행 직전/직후 정확한 시각 기록(로컬 실행 시)
date +%s

# time() 호출 확인
gdb -q ./chall -ex "break time" -ex run -ex finish -ex continue
```
```python
# 시간 창 전체를 순회하는 브루트포스 템플릿
import ctypes, time
libc = ctypes.CDLL("libc.so.6")

def matches(seed, expected_values):
    libc.srand(seed)
    return all(libc.rand() == v for v in expected_values)

now = int(time.time())
for delta in range(-300, 1):
    if matches(now + delta, observed_values):
        print("seed:", now + delta)
        break
```

## 출력 해석
- 후보 하나가 여러 개의 관찰값과 동시에 정확히 일치하면 신뢰도가 매우 높은 정답이다.
- 탐색 범위 안에서 아무것도 안 맞으면, 시드 계산식에 `time()` 외의 요소(PID, 밀리초 단위)가 더 섞여 있을 가능성을 의심하고 탐색 차원을 하나 더 추가한다.
- 정확히 같은 시드인데도 값이 다르다면 libc 버전 차이(REV-0648)나 분석 환경 아키텍처 차이일 수 있다.

## 흔한 실수
- 탐색 창을 너무 좁게 잡아서(예: 정확히 지금 이 순간만 시도) 실제 실행 시각과의 오차(네트워크 지연, 문제 서버 큐잉 시간 등)를 고려하지 못해 정답을 놓치는 것.
- 첫 번째 `rand()` 출력값 하나만으로 시드를 확정해서, 우연히 일치하는 오탐 시드를 정답으로 잘못 채택하는 것 — 여러 출력값을 함께 검증해야 한다.
- 32비트 정수 오버플로/부호 문제를 무시하고 `time()` 반환값을 그대로 큰 정수로 다뤄 `srand()`에 넘길 때 값이 잘리는 것을 놓치는 것.
- 시드가 `time()`이 아니라 실제로는 밀리초 단위 함수인데 초 단위로만 탐색해서 후보를 못 찾는 것.

## 막혔을 때 다음 체크
- 시드를 확보한 뒤 실제 libc의 rand()를 어떻게 재현할지 기억이 안 나면 → REV-0893 rand()/srand() 시드 기반 문제 접근법
- 탐색해야 할 키 공간이 이 정도 크기에서 정말 브루트포스가 타당한지 재확인하려면 → REV-0219 Brute Force가 가능한 입력 공간 계산
- LD_PRELOAD로 라이브러리 함수를 후킹하는 구체적 방법이 기억나지 않으면 → REV-0650 LD_PRELOAD로 함수 후킹해서 관찰하기
- glibc 버전에 따라 rand() 결과가 달라지는 이유가 궁금하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법

## 미니 예제
어떤 문제 서버에 접속하면 다음과 같은 흐름의 바이너리가 실행된다고 하자.

```c
#include <time.h>
#include <stdlib.h>

int main(void) {
    srand(time(NULL));
    int challenge = rand() % 1000000;
    printf("Guess my number: ");
    // ... 사용자가 challenge를 맞히면 플래그 출력
}
```
서버에 접속해서 응답을 받은 시각을 `T`라고 기록했다면, `T` 전후 몇십 초 범위를 모두 시도해보는 것으로 충분하다.

```python
import ctypes, time, socket

libc = ctypes.CDLL("libc.so.6")

t0 = int(time.time())   # 접속 직전 기록한 시각

# 서버에 접속해서 "Guess my number:" 프롬프트를 받은 직후...
for delta in range(-10, 11):   # 네트워크 지연을 고려해 앞뒤로 넉넉히
    seed = t0 + delta
    libc.srand(seed)
    guess = libc.rand() % 1000000
    # guess를 서버에 전송해보고 정답이면 그대로 확정
    print(seed, guess)
```
정답으로 확인된 `guess`를 서버에 전송하면 시드를 정확히 몰라도, "실행 시각 근방"이라는 좁은 창만으로 문제를 풀 수 있다.

### 실행 가능한 전체 스크립트 — 숨겨진 시드를 실제로 몰라도 시간 창 브루트포스로 찾아내기

이번에는 "시드가 정확히 몇 초였는지 전혀 모른다"는 상황을 코드 안에서 그대로 재현해서, 시간 창 브루트포스가 실제로 정답을 찾아내는 과정을 끝까지 실행해본다. 이해를 돕기 위해 `hidden_seed`(공격자는 모른다고 가정하는 값)를 스크립트 안에 일부러 숨겨두고, 이후 코드는 그 값을 전혀 참조하지 않은 채로 순수하게 관찰된 `rand()` 출력값만으로 시드를 역추적한다.

```python
# -*- coding: utf-8 -*-
import ctypes   # 실제 시스템 glibc를 그대로 호출하기 위한 표준 도구

libc = ctypes.CDLL("libc.so.6")

# --- 0) "피해자 프로그램"을 흉내내는 부분 — 실전에서는 이 값을 공격자가 모른다 ---
now = 1893456000        # 예제를 재현 가능하게 만들기 위해 고정해둔 가상의 "현재 시각"(유닉스 타임)
hidden_seed = now - 47   # 실제 프로그램이 47초 전에 srand(time(NULL))을 호출했다고 가정

libc.srand(hidden_seed)                       # 피해자 프로그램의 시드 설정
observed_outputs = [libc.rand() for _ in range(3)]   # 프로그램이 화면에 출력한 rand() 값 3개
print("관찰된 출력값(공격자가 실제로 볼 수 있는 정보):", observed_outputs)

# --- 1) 여기서부터는 hidden_seed를 전혀 모른다고 가정하고 공격을 시작한다 ---
def try_seed(candidate_seed: int, expected_outputs: list) -> bool:
    """후보 시드로 rand()를 몇 번 호출해서, 관찰된 값들과 전부 일치하는지 검사."""
    libc.srand(candidate_seed)
    generated = [libc.rand() for _ in range(len(expected_outputs))]
    return generated == expected_outputs   # 값 하나가 아니라 여러 개를 모두 비교해 오탐 방지

found_seed = None
for delta in range(0, 121):        # "최대 120초 전에 실행됐다"고 가정하고 그 범위를 전부 시도
    candidate = now - delta
    if try_seed(candidate, observed_outputs):
        found_seed = candidate
        print(f"시드 발견! candidate={candidate} (지금으로부터 {delta}초 전)")
        break

print("복원한 시드:", found_seed)
print("실제 hidden_seed와 일치하는가?", found_seed == hidden_seed)   # 검증용 — 실전에서는 이 줄이 없다
```

이 스크립트를 그대로 실행하면 다음과 같은 결과가 나온다.

```text
관찰된 출력값(공격자가 실제로 볼 수 있는 정보): [581708673, 656406014, 667518886]
시드 발견! candidate=1893455953 (지금으로부터 47초 전)
복원한 시드: 1893455953
실제 hidden_seed와 일치하는가? True
```

공격자 입장에서 실제로 가진 정보는 `observed_outputs`(화면에 출력된 세 개의 숫자)와 "대략 120초 이내에 실행됐을 것"이라는 시간 창뿐이었는데, 그것만으로 121가지 후보를 전부 시도해 정확히 47초 전의 시드(`1893455953`)를 찾아냈다. 세 개의 출력값을 동시에 비교했기 때문에(`try_seed`에서 `expected_outputs` 전체를 검사) 우연히 한 값만 맞는 오탐 없이 정확한 시드 하나만 골라낼 수 있었다. 이 시드를 알았으니 이후 이 프로그램이 `rand()`를 몇 번을 더 호출하든 전부 미리 계산할 수 있다.

## 관련 글
- REV-0893 — rand()/srand() 시드 기반 문제 접근법
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0650 — LD_PRELOAD로 함수 후킹해서 관찰하기
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0891 — LCG(Linear Congruential Generator) 기반 난수 알아보기

## 출처/검증
- POSIX `time()` 함수가 1970-01-01 UTC 기준 경과 초를 반환한다는 정의: IEEE Std 1003.1(POSIX.1) `time()` 함수 사양 기준 (2026-09-09 검증).
- `srand(time(NULL))` 패턴이 예측 가능한 시드를 만들어 보안상 취약하다는 사실은 다수의 실제 사고 사례(예: 시간 기반 시드를 쓰는 랜섬웨어의 암호화 키 복구 가능성 분석)로 보고된 바 있음: 공개된 악성코드/CTF 분석 리포트(time()-seeded rand() 취약점 분석) 기준 (2026-09-09 검증).
- `LD_PRELOAD`를 이용한 라이브러리 함수 가로채기(후킹) 기법: `ld.so(8)` 공식 Linux man 페이지의 `LD_PRELOAD` 설명 기준 (2026-09-09 검증).
