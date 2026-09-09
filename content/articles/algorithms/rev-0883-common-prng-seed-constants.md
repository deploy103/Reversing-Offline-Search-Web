---
id: REV-0883
title: "흔한 시드 기반 PRNG 상수 빠른 참조(LCG 계수 등)"
slug: "rev-0883-common-prng-seed-constants"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["LCG", "선형합동생성기", "1103515245", "22695477", "214013", "2531011", "0x5DEECE66D", "Mersenne Twister", "0x9908B0DF"]
aliases: ["lcg 상수", "rand 곱셈 상수", "선형합동 생성기 계수", "prng 매직넘버"]
symptom_keywords: ["seed * 상수 + 상수 형태의 코드가 있음", "1103515245가 보임", "214013이 보임", "난수처럼 보이는데 재현 가능함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`seed = seed * A + C` 형태의 곱셈-덧셈 반복 코드를 만나면 이는 **선형 합동 생성기(LCG, Linear Congruential Generator)** 기반의 의사난수(pseudo-random) 생성기이며, 곱셈 상수 `A`와 증분 `C`의 정확한 값을 알면 어떤 표준 라이브러리의 `rand()`인지 즉시 식별하고 시드만 알아내면 이후 모든 "난수"를 정확히 예측할 수 있다.

## 언제 검색해야 하나
- 디컴파일 코드에 `seed = seed * 상수1 + 상수2` 형태가 반복 호출될 때
- "랜덤"으로 보이는 값인데 매번 프로그램을 재시작해도 시드가 같으면 같은 순서로 나올 때(암호학적으로 안전하지 않은 PRNG를 쓴다는 신호)
- `srand(time(NULL))`처럼 시드가 현재 시간에서 유도되는 것을 봤고, 그 시간 값만 알아내면 이후 값을 모두 예측할 수 있어 보일 때
- Import에 `rand`, `srand`, `random`, `java.util.Random`, `Math.random` 계열이 보일 때

## 핵심 개념
LCG는 `X(n+1) = (A * X(n) + C) mod M` 공식을 반복 적용해서 다음 값을 만든다. `A`(곱셈), `C`(증분), `M`(모듈러스)이 구현마다 고정되어 있어, 이 세 값만 알면 시드 하나로 전체 수열을 완벽히 재현할 수 있다 — **암호학적으로 안전하지 않다는 뜻**이며, CTF에서 "난수처럼 보이지만 사실 예측 가능한" 문제의 핵심 트릭으로 자주 쓰인다.

**대표적인 LCG 상수 조합**
| A (곱셈) | C (증분) | M (모듈러스) | 사용처 |
|---|---|---|---|
| `1103515245` | `12345` | `2^31` 또는 `2^32` | ANSI C 예시 구현, 여러 오래된 BSD `rand()`, Borland Delphi 계열 |
| `1664525` | `1013904223` | `2^32` | Numerical Recipes(교재) 예시 LCG, 일부 Borland C/C++ |
| `22695477` | `1` | `2^32` | glibc(GCC)에서 실제로 쓰는 계수 — 널리 알려진 "1103515245/12345"와는 다름 |
| `214013` | `2531011` | `2^31`(상위 15비트만 반환) | Microsoft Visual C++ 런타임의 `rand()` |
| `0x5DEECE66D` (25214903917) | `0xB` (11) | `2^48` | Java `java.util.Random` (48비트 LCG) |
| `6364136223846793005` | `1` | `2^64` | 구형 VAX/glibc `random()` 계열, POSIX `drand48`과 유사 계열(Knuth 추천값) |

**Microsoft Visual C++ `rand()`의 정확한 동작**
```c
static long holdrand = 1L;
int rand(void) {
    holdrand = holdrand * 214013L + 2531011L;
    return (holdrand >> 16) & 0x7fff;   // 하위 16비트를 버리고 상위 15비트만 반환
}
```
하위 비트일수록 주기가 짧고 예측하기 쉬워서(최하위 비트는 주기 2), 상위 비트만 골라 반환하는 것이 이 구현의 특징이다. 기본 시드가 `1`이면 첫 번째 `rand()` 호출 결과가 항상 `41`이라는 점도 유명한 지문이다.

**Java `java.util.Random`의 정확한 동작**
```java
seed = (seed ^ 0x5DEECE66DL) & ((1L << 48) - 1);   // 시드 설정 시 스크램블
// next(bits):
seed = (seed * 0x5DEECE66DL + 0xB) & ((1L << 48) - 1);
return (int)(seed >>> (48 - bits));
```
48비트 상태만 쓰기 때문에 몇 개의 출력값만 관찰하면 내부 시드를 완전히 역산할 수 있는 것으로 잘 알려져 있다.

**Mersenne Twister(MT19937) — LCG는 아니지만 자주 혼동됨**

Python `random`, PHP `mt_rand`, 여러 게임 엔진이 쓰는 MT19937은 LCG가 아니라 훨씬 복잡한 상태(624개의 32비트 워드)를 갖는 생성기다. 대표 상수로 `0x9908B0DF`(twist 연산의 매직 벡터 A)가 있으며, 이 값이 보이면 LCG가 아니라 Mersenne Twister임을 바로 알 수 있다. 이 생성기도 암호학적으로 안전하지 않아서, 연속된 624개의 32비트 출력을 관찰하면 내부 상태 전체를 복원해 이후 값을 전부 예측할 수 있다는 점이 잘 알려져 있다.

## 화면/코드에서 보이는 징후
```asm
imul    eax, [seed], 214013h
add     eax, 2531011h
mov     [seed], eax
shr     eax, 16
and     eax, 7FFFh          ; MSVC rand()의 전형적인 패턴
```
```c
state = state * 1103515245 + 12345;
return (unsigned)(state / 65536) % 32768;   // ANSI C 스타일
```

## 가장 먼저 할 것
곱셈 상수(`A`)를 정확히 읽고 위 표와 대조한다. 어떤 라이브러리의 `rand()`인지 확정되면, 시드를 어디서 가져오는지(하드코딩? `time(NULL)`? 사용자 입력?) 추적한다.

## 단계별 절차
**1) 곱셈/증분 상수 확인** — `imul`/`mul` 뒤의 즉시값과 `add` 뒤의 즉시값을 정확히 읽는다.

**2) 표와 대조해서 알고리즘 확정**

**3) 시드 출처 추적** — `srand(time(NULL))`이면 프로그램 실행 시각(초 단위)이 시드이므로, 대략적인 실행 시간대를 알면 몇 초~몇 분 범위의 시드만 브루트포스하면 된다.

**4) Python으로 동일 LCG 재구현**
```python
def msvc_rand_sequence(seed: int, n: int) -> list:
    out = []
    state = seed & 0xFFFFFFFF
    for _ in range(n):
        state = (state * 214013 + 2531011) & 0xFFFFFFFF
        out.append((state >> 16) & 0x7FFF)
    return out

print(msvc_rand_sequence(1, 3))   # [41, ...] 시드 1일 때 첫 값이 41임을 확인
```

**5) 시드 범위가 좁으면 브루트포스로 시드 자체를 복원**
```python
target_sequence = [41, 18467, 6334]   # 바이너리가 실제로 만든 값들(관찰값)
for seed_candidate in range(0, 100000):
    if msvc_rand_sequence(seed_candidate, 3) == target_sequence:
        print("seed =", seed_candidate)
        break
```

## 명령어/단축키
- IDA/Ghidra: `Alt+T`로 `214013`, `1103515245`, `22695477`, `1664525` 등 곱셈 상수 검색
- Python: `ctypes` 없이도 `& 0xFFFFFFFF`로 32비트 오버플로를 그대로 재현 가능

## 출력 해석
- 재구현한 시퀀스가 바이너리 관찰값과 정확히 일치하면 알고리즘과 시드가 모두 확정된 것이다.
- 값이 안 맞으면 모듈러스(`2^31` vs `2^32`)나 반환 시 시프트/마스크(`>>16 & 0x7FFF` 여부)를 놓쳤을 가능성이 크다.
- Mersenne Twister라면 단순 LCG 재현으로는 절대 안 맞으므로, 상수가 `0x9908B0DF`인지 다시 확인해서 완전히 다른 구현(624워드 상태)으로 접근해야 한다.

## 흔한 실수
- "1103515245/12345"가 모든 시스템의 표준이라고 착각하는 것 — 실제 glibc는 `22695477`을 쓰고, MSVC는 `214013`을 쓰는 등 라이브러리마다 다르다.
- 반환값 계산 시 시프트/마스크(`>>16`, `&0x7FFF`)를 빼먹고 전체 32비트 값을 그대로 "난수"라고 착각하는 것.
- LCG와 Mersenne Twister를 같은 취약점(몇 개 값으로 전체 예측 가능)을 공유한다고 뭉뚱그려 이해하고, 필요한 관찰 값의 개수(LCG는 1~2개, MT19937은 624개)를 착각하는 것.
- 시드가 `time(NULL)`에서 온다는 걸 확인하고도, 서버/문제 배포 환경의 대략적인 실행 시각 범위를 좁히지 않고 전체 32비트 시간 범위를 브루트포스하려다 시간을 낭비하는 것.

## 막혔을 때 다음 체크
- 시드 브루트포스 자체가 현실적으로 가능한 범위인지 판단하려면 → REV-0219 — Brute Force가 가능한 입력 공간 계산.
- 이 PRNG의 출력이 해시/체크섬과 함께 쓰이는 구조라면 → REV-0876 — 해시 함수 매직 상수 빠른 참조(MD5/SHA1/SHA256 초기값), REV-0877 — CRC 다항식 상수 빠른 참조표와 구분해서 확인.
- 전체 판별 흐름이 필요하면 → REV-0885 — 알고리즘 유형별 판별 체크리스트.

## 미니 예제
바이너리에서 다음 디스어셈블리를 봤다:
```asm
mov     eax, [holdrand]
imul    eax, eax, 214013h
add     eax, 2531011h
mov     [holdrand], eax
sar     eax, 16
and     eax, 7FFFh
```
곱셈 상수 `0x214013`(=214013)과 증분 `0x2531011`(=2531011)이 표와 정확히 일치하므로 MSVC `rand()`로 확정된다. `holdrand`의 초기값(시드)이 프로그램 시작 시 어디서 대입되는지(`srand` 호출 인자)를 추적하면, 위 5)번 절차의 브루트포스 스니펫으로 실제 시드를 복원해 이후 모든 "난수" 호출 결과를 미리 계산할 수 있다.

## 관련 글
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0876 — 해시 함수 매직 상수 빠른 참조(MD5/SHA1/SHA256 초기값)
- REV-0877 — CRC 다항식 상수 빠른 참조표
- REV-0885 — 알고리즘 유형별 판별 체크리스트

## 출처/검증
- ANSI C 계열(1103515245/12345), glibc 실제 계수(22695477/1), Numerical Recipes(1664525/1013904223), VAX/구형 glibc(6364136223846793005/1): 공개된 LCG 파라미터 비교 자료 및 각 처리계의 소스코드/문서 기준 (2026-09-09 검증).
- Microsoft Visual C++ `rand()` 구현(214013/2531011, 시드 1일 때 첫 출력 41): Microsoft C 런타임 소스코드에서 공개적으로 알려진 구현(`crt/src/rand.c` 계열) 기준 (2026-09-09 검증).
- Java `java.util.Random`(0x5DEECE66D/0xB, 48비트 상태): OpenJDK `java.util.Random` 공식 소스코드 기준 (2026-09-09 검증).
- Mersenne Twister(MT19937) 매직 벡터 `0x9908B0DF` 및 624워드 상태 크기: Matsumoto & Nishimura의 MT19937 원논문 및 참조 구현 기준.
