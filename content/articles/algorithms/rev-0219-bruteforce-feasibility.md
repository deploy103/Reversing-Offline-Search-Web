---
id: REV-0219
title: "Brute Force가 가능한 입력 공간 계산"
slug: "rev-0219-bruteforce-feasibility"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["brute force", "keyspace", "input space", "charset", "attempts per second", "2^40", "무차별 대입", "입력 공간", "탐색 공간"]
aliases: ["브루트포스 가능한지", "무차별 대입 가능한지", "이거 그냥 다 돌려볼까", "키스페이스 계산"]
symptom_keywords: ["다 돌려보면 되는거 아님", "브루트포스 며칠걸림", "얼마나 걸릴지 모르겠음", "그냥 다 해볼까 고민", "경우의 수가 너무 많음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
브루트포스가 "가능한지"는 감이 아니라 계산으로 결정한다. **탐색 공간 크기 = 문자셋 크기^미지 바이트 수**, **소요 시간 = 탐색 공간 ÷ 초당 시도 횟수**라는 두 공식만 정확히 적용하면, 리버싱을 계속할지 그냥 다 돌려볼지 5분 안에 판단할 수 있다.

## 언제 검색해야 하나
- [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md)에서 미지 바이트 수를 확정한 뒤, "이 정도면 그냥 브루트포스 돌려도 되나?"를 판단해야 할 때
- 알고리즘이 너무 복잡해서 역산(REV-0221)이 막막할 때, 브루트포스가 대안이 될 수 있는지 확인하고 싶을 때
- 브루트포스 스크립트를 이미 돌리고 있는데 언제 끝날지 감이 안 잡힐 때
- "2^32", "2^40" 같은 숫자를 보고 이게 실현 가능한 크기인지 직관이 안 설 때

## 핵심 개념
탐색 공간(키스페이스)은 다음 공식으로 계산한다:

```
keyspace = charset_size ^ unknown_length
time_sec = keyspace / attempts_per_second
```

여기서 두 변수를 현실적으로 잡는 게 핵심이다.

**1) `attempts_per_second`(초당 시도 횟수) 기준값**
- 순수 파이썬 루프로 후보마다 체크 함수를 호출: 체크 로직이 어느 정도 복잡하면 인터프리터 오버헤드 때문에 **초당 10^5 ~ 10^6회** 정도가 현실적이다. 아주 가벼운 체크(단순 XOR 비교 수준)라면 낙관적으로 10^6/s를 상한으로 잡는다.
- 최적화된 C/C++ 브루트포서, 또는 파이썬에서 `ctypes`로 바이너리의 실제 체크 함수를 직접 호출하는 방식: 체크 비용에 따라 **초당 10^7 ~ 10^9회**. 흔히 10^8/s를 현실적인 중간값으로, 아주 가벼운 연산(XOR+비교 1회 수준)이면 10^9/s를 낙관적 상한으로 잡는다.
- GPU 가속 해시 크래킹(hashcat류)은 타깃이 MD5/SHA1 같은 표준 해시이고 GPU가 있을 때만 의미가 있으며 **10^10 ~ 10^11/s**까지도 나온다. 하지만 CTF의 커스텀 알고리즘은 대부분 GPU로 이식하기 어려우므로 이 수치를 과신하지 않는다.
- CTF의 현실적인 시간 예산은 대체로 "수 분 ~ 수 시간"이다. 하루를 넘어가는 계산이 나온다면 브루트포스가 아니라 알고리즘 자체를 역산/이해하는 방향이 맞을 가능성이 높다.

**2) `charset_size`(문자셋 크기)와 `unknown_length`(미지 길이)**

이 두 값은 [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md)에서 설명한 게이트 인벤토리로 최대한 좁혀야 한다. 문자셋을 좁히거나(예: 인쇄 가능 아스키 95종 → hex 문자만 16종) 길이를 줄이면(접두사/접미사 제거) 지수와 밑이 동시에 작아져서 실현 가능성이 극적으로 바뀐다.

## 화면/코드에서 보이는 징후
- 디컴파일 결과에서 반복되는 `for(i=0;i<len;i++)` 루프가 있고, 각 바이트가 독립적이지 않고 이전 결과에 의존하는 복잡한 연산(암호화 라운드, 해시 믹싱 등)을 수행 — "역산이 어려워 보이니 브루트포스를 검토해야 하나?" 판단이 필요한 신호.
- 목표 비교값(`target` 상수 배열)이 32비트/64비트 몇 개로 짧게 주어짐 — 이 경우 실제 미지 정보량이 생각보다 작을 수 있으니 다시 계산해야 함.

## 가장 먼저 할 것
Python 인터프리터에서 `charset_size ** unknown_length`를 직접 계산해서 정확한 정수값을 얻는다(파이썬은 임의 정밀도 정수를 지원하므로 근사 없이 정확하다). 그 다음 실제 체크 함수를 몇천 번 호출해서 초당 몇 번 처리되는지 벤치마크한 뒤, 두 값을 나눠서 예상 소요 시간을 얻는다.

## 단계별 절차

**1) 탐색 공간 정확히 계산하기**

예: 문자셋 62종(영소문자+영대문자+숫자), 미지 길이 6.

```python
charset = 26 + 26 + 10  # 62
length = 6
keyspace = charset ** length
print(keyspace)  # 56800235584
```

손으로 검산: `62^2 = 3844`, `62^3 = 3844 * 62 = 238328`, `62^6 = 238328^2 = 56,800,235,584` (≈5.68×10^10).

**2) 실제 체크 함수 속도 벤치마크**

```python
import time

N = 10000
start = time.perf_counter()
for _ in range(N):
    check_candidate(b"AAAAAA")  # 실제 검증 로직(재구현본 또는 ctypes 호출)
elapsed = time.perf_counter() - start
rate = N / elapsed
print(f"{rate:.0f} candidates/sec")
```

**3) 소요 시간 계산**

```python
seconds = keyspace / rate
print(seconds, seconds / 60, seconds / 3600)
```

**4) 판단**

수 분~수 시간이면 그냥 돌린다. 하루 이상 걸리면 문자셋/길이를 더 좁힐 방법이 있는지([rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md), [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md)) 먼저 찾고, 그래도 안 되면 [rev-0220-meet-in-the-middle.md](./rev-0220-meet-in-the-middle.md)나 REV-0221(역산 가능성 판단)로 넘어간다.

## 명령어/단축키
재사용 가능한 판단 함수:

```python
def feasibility(charset_size, length, rate_per_sec, budget_sec=3600):
    keyspace = charset_size ** length
    seconds = keyspace / rate_per_sec
    return keyspace, seconds, seconds <= budget_sec

ks, secs, ok = feasibility(62, 6, 1e8)
print(ks, secs, ok)   # 56800235584 568.00235584 True
```

## 출력 해석

**예제 1 — 실현 가능한 경우**: 문자셋 62(영소문자+영대문자+숫자), 미지 길이 6.

```
keyspace = 62^6 = 56,800,235,584  (약 5.68×10^10)
```

- 최적화 C, 10^8/s 가정: `56,800,235,584 / 100,000,000 ≈ 568.0초 ≈ 9.47분` → **명확히 실현 가능**.
- 순수 파이썬, 10^6/s 가정: `56,800,235,584 / 1,000,000 ≈ 56,800초 ≈ 946.7분 ≈ 15.78시간` → **경계선/사실상 비현실적**. 이 경우 검증 로직을 C로 옮기거나 `ctypes`로 바이너리의 실제 체크 함수를 직접 호출해서 속도를 올려야 한다.

**예제 2 — "2^40이면 되나?" 판단**

```
2^40 = 1,099,511,627,776  (약 1.1×10^12)
```

- 10^9/s(거의 트리비얼한 체크, 최적화된 C 루프나 SIMD/멀티스레드) 가정: `1,099,511,627,776 / 1,000,000,000 ≈ 1,099.5초 ≈ 18.3분` → **실현 가능**, 단 실제로 10^9/s를 뽑아낼 수 있어야 한다는 전제가 붙는다.
- 10^6/s(순수 파이썬) 가정: `1,099,511,627,776 / 1,000,000 ≈ 1,099,511.6초 ≈ 12.7일` → **비현실적**. 최적화하거나 [rev-0220-meet-in-the-middle.md](./rev-0220-meet-in-the-middle.md), REV-0221(역산 가능성 판단)로 넘어가야 한다.

**결론**: 2^40은 순전히 초당 시도 속도에 따라 실현 가능/불가능이 갈리는 진짜 경계선 사례다. 브루트포스 여부를 판단할 때는 항상 비관적 추정(순수 파이썬)과 낙관적 추정(최적화 C/ctypes) 둘 다 계산해서 폭을 파악해야 한다.

**예제 3 — 명백히 불가능한 경우 (대조용)**: 문자셋 95(인쇄 가능 아스키 전체), 미지 길이 16(접두사/접미사로 좁히지 않은 전형적인 flag 본문 크기).

```
log10(95) ≈ 1.977724
log10(95^16) = 16 × 1.977724 ≈ 31.644
95^16 ≈ 4.4×10^31
```

아주 낙관적으로 10^12/s(사실상 커스텀 알고리즘에는 비현실적인 GPU 클러스터급 속도)를 가정해도:

```
4.4×10^31 / 10^12 ≈ 4.4×10^19초
```

우주의 나이(약 138억 년 ≈ 4.35×10^17초)보다도 100배 이상 긴 시간이다. **브루트포스는 완전히 잘못된 접근**이며, 알고리즘의 구조(역산, known-plaintext 활용, 혹은 검증 로직 자체의 결함)를 찾아야 한다.

**narrowing의 위력**: 같은 95^16(불가능)이라도, 게이트 인벤토리와 known-plaintext 분석으로 길이를 8로 줄이고 문자셋도 hex(16종)로 좁혔다면:

```
16^8 = 4,294,967,296 (정확히 2^32)
```

10^8/s 가정 시 `4,294,967,296 / 100,000,000 ≈ 42.9초` → **순식간에 실현 가능**. 이게 [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md)와 [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md)의 narrowing 기법이 왜 중요한지 보여주는 극적인 사례다.

## 흔한 실수
- 키스페이스 계산은 정확히 했지만 **실제 체크 함수의 비용**을 곱하는 걸 잊는 것. 만약 체크 로직 내부에 bcrypt/PBKDF2처럼 반복 횟수가 많은 느린 KDF가 들어있다면 실효 속도가 초당 100~10,000회 수준까지 떨어질 수 있고, "작아 보이는" 10^8 크기의 키스페이스도 며칠씩 걸릴 수 있다. 계산에 들어가기 전에 `time.perf_counter()`로 실제 체크 함수를 1만 번쯤 돌려서 진짜 속도를 재야 한다.
- 근사값(예: "약 10^12")만 믿고 정확한 정수 계산을 생략하는 것 — 파이썬은 큰 정수도 정확히 다루므로 `charset ** length`를 직접 찍어보는 게 훨씬 안전하다.
- 문자셋 크기를 실제보다 넓게 잡는 것(예: 실제로는 소문자+숫자만 가능한데 대문자까지 포함) — 게이트 인벤토리에서 문자셋 제약을 놓치지 않았는지 재확인한다.
- "일단 돌려보고 판단하자"며 계산 없이 무작정 실행해서 몇 시간을 낭비하는 것 — 계산은 1분도 안 걸리니 반드시 먼저 한다.

## 막혔을 때 다음 체크
- 문자셋/길이를 더 좁힐 방법이 있는지 → [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md), [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md)
- 탐색 공간이 두 독립적인 절반으로 나뉘는 구조라면 → [rev-0220-meet-in-the-middle.md](./rev-0220-meet-in-the-middle.md)
- 브루트포스 자체가 답이 아니고 알고리즘을 거꾸로 계산해야 한다면 → REV-0221(역연산 가능한 알고리즘 판단법, 예정)
- FNV처럼 원래 단방향(역산 불가능)인 해시라서 브루트포스/충돌 탐색만이 답인 경우 → [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md)

## 미니 예제
어떤 문제의 체크 함수를 게이트 인벤토리로 분석했더니 flag 본문이 순수 소문자 8바이트로 좁혀졌다고 하자.

```python
def feasibility(charset_size, length, rate_per_sec, budget_sec=3600):
    keyspace = charset_size ** length
    seconds = keyspace / rate_per_sec
    return keyspace, seconds, seconds <= budget_sec

# 소문자 26종, 길이 8
ks, secs, ok = feasibility(26, 8, 1e8)
print(ks)          # 208827064576  (약 2.09×10^11)
print(secs)        # 2088.27064576 초 ≈ 34.8분
print(ok)          # True (기본 예산 3600초=1시간 안에 끝남)
```

2088초는 기본 예산으로 잡은 3600초(1시간) 안에 들어오므로 `ok`는 `True`가 나온다. 이렇게 함수 하나로 여러 가정(문자셋, 길이, 속도, 예산)을 바꿔가며 즉시 판단할 수 있다는 게 이 계산법의 핵심 가치다.

**심화 예제 — 판단 계산부터 실제 브루트포스 실행까지 이어지는 완결된 스크립트**

이번에는 계산만 하는 게 아니라, 실제로 작은 키스페이스를 브루트포스로 완전히 뒤져서 정답을 찾아내는 전체 과정을 보여준다. 파이썬을 몰라도 따라올 수 있도록 한 줄씩 설명한다.

```python
import zlib
# ↑ 체크 로직을 흉내 내기 위해 CRC-32 계산 함수가 담긴 zlib 모듈을 불러온다.
import itertools
# ↑ 모든 후보 조합을 순서대로 만들어주는 product() 함수가 담긴 itertools 모듈을 불러온다.
import time
# ↑ 실제 걸린 시간을 재기 위한 time 모듈을 불러온다.

def feasibility(charset_size: int, length: int, rate_per_sec: float, budget_sec: float = 3600) -> tuple:
    # ↑ 문자셋 크기, 미지 길이, 초당 시도 속도, 시간 예산을 받아서
    #   (탐색 공간, 예상 소요 시간, 예산 안에 끝나는지 여부)를 돌려주는 함수.
    keyspace = charset_size ** length
    # ↑ 탐색해야 할 전체 후보 개수를 계산한다.
    seconds = keyspace / rate_per_sec
    # ↑ 후보 개수를 초당 속도로 나눠서 예상 소요 시간을 구한다.
    return keyspace, seconds, seconds <= budget_sec
    # ↑ 세 값을 튜플로 묶어서 돌려준다. 마지막 값은 예산 안에 끝나면 True.

if __name__ == "__main__":
    # ↑ 이 파일을 직접 실행할 때만 아래 블록을 수행한다.

    CHARSET = "abcdefghijklmnopqrstuvwxyz"
    # ↑ 이번 예제에서 미지 바이트가 취할 수 있는 문자 종류(소문자 26개)로 좁혔다고 가정.
    LENGTH = 3
    # ↑ 게이트 인벤토리(REV-0218)로 좁힌 결과, 미지 바이트가 3개뿐이라고 가정.
    SECRET = b"ctf"
    # ↑ 검증용으로 우리가 미리 알고 있는 정답(실전에서는 모르는 값).
    TARGET = zlib.crc32(SECRET)
    # ↑ 바이너리가 비교하는 목표값. 실전에서는 이 값을 디버거로 직접 확인해서 넣는다.

    ks, secs, ok = feasibility(len(CHARSET), LENGTH, rate_per_sec=1_000_000)
    # ↑ 소문자 26종, 길이 3, 파이썬 순수 루프 기준(초당 100만 회)으로 실현 가능성을 미리 계산.
    print(f"탐색 공간: {ks}개, 예상 소요 시간: {secs:.6f}초, 실현 가능: {ok}")
    # ↑ 계산 결과를 미리 출력해서, 브루트포스를 실행하기 전에 감을 잡는다.

    start = time.perf_counter()
    # ↑ 실제 브루트포스를 시작하기 직전의 시각을 기록한다.
    found = None
    # ↑ 정답을 찾으면 여기에 저장할 변수. 아직 못 찾았으므로 None으로 시작.
    tries = 0
    # ↑ 지금까지 몇 번 시도했는지 세는 변수.

    for combo in itertools.product(CHARSET, repeat=LENGTH):
        # ↑ CHARSET에서 LENGTH개를 뽑는 모든 순서 있는 조합을 하나씩 만들어낸다.
        #   예: ('a','a','a'), ('a','a','b'), ... 알파벳 순서대로 전부.
        tries += 1
        # ↑ 시도 횟수를 하나 늘린다.
        candidate = "".join(combo).encode()
        # ↑ 문자 튜플을 하나의 문자열로 합친 뒤, 바이트로 인코딩한다.
        if zlib.crc32(candidate) == TARGET:
            # ↑ 후보의 CRC32 값이 목표값과 정확히 같으면
            found = candidate
            # ↑ 이 후보를 정답으로 기록한다.
            break
            # ↑ 정답을 찾았으므로 더 이상 반복하지 않고 즉시 멈춘다.

    elapsed = time.perf_counter() - start
    # ↑ 브루트포스를 마친 시각에서 시작 시각을 빼서 실제 걸린 시간을 구한다.

    print(f"찾은 정답: {found}")
    # ↑ 실제로 찾아낸 정답 후보를 출력한다.
    print(f"실제 시도 횟수: {tries}회, 실제 걸린 시간: {elapsed:.6f}초")
    # ↑ 실제로 몇 번 시도했고 얼마나 걸렸는지 출력해서, 미리 계산한 예상치와 비교해본다.
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 실행해서 검증한 값, 실행 환경에 따라 걸린 시간은 조금씩 달라질 수 있다):
```
탐색 공간: 17576개, 예상 소요 시간: 0.017576초, 실현 가능: True
찾은 정답: b'ctf'
실제 시도 횟수: 1852회, 실제 걸린 시간: 0.000556초
```
`26**3 = 17,576`개의 전체 후보 중에서, 알파벳 순서로 하나씩 시도하다가 정확히 1,852번째 시도에서 `b"ctf"`를 찾아내고 즉시 멈춘다(`c`, `t`, `f`가 알파벳의 앞쪽에 있어서 상대적으로 빨리 발견된 것이다). 미리 계산한 예상 소요 시간(약 0.018초)과 실제 걸린 시간(약 0.0006초)이 같은 자릿수 안에 있다는 것도 확인할 수 있다 — 이렇게 "미리 계산 → 실제 실행 → 비교" 흐름을 스크립트 하나로 만들어두면, 훨씬 큰 키스페이스를 실행하기 전에 시간을 낭비하지 않고 미리 판단할 수 있다.

## 관련 글
- [rev-0218-length-check-backtrace.md](./rev-0218-length-check-backtrace.md) — 길이 검증부터 역추적하는 법
- [rev-0220-meet-in-the-middle.md](./rev-0220-meet-in-the-middle.md) — Meet-in-the-middle를 고려할 상황
- [rev-0223-known-plaintext-narrowing.md](./rev-0223-known-plaintext-narrowing.md) — Known plaintext와 Flag 형식으로 조건 줄이기
- [rev-0208-fnv-16777619.md](./rev-0208-fnv-16777619.md) — 단방향 해시라서 브루트포스가 유일한 선택지가 되는 예시
- REV-0221 — 역연산 가능한 알고리즘 판단법

## 출처/검증
- 초당 시도 횟수 기준값(파이썬 vs C vs GPU): 일반적인 CTF/보안 커뮤니티에서 통용되는 브루트포스 성능 경험칙을 정리 (2026-09-08 기준).
- 모든 수치 계산은 본문에 기재된 그대로 Python으로 직접 검산됨(예: `62**6`, `2**40`, `16**8`).
