---
id: REV-0892
title: "Mersenne Twister 흔적 알아보기"
slug: "rev-0892-mersenne-twister-fingerprints"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["Mersenne Twister", "메르센 트위스터", "MT19937", "0x9908b0df", "0x9d2c5680", "0xefc60000", "1812433253", "624 state", "tempering"]
aliases: ["MT19937이 뭐임", "메르센 트위스터 상수", "624개 배열 난수", "python random 모듈 알고리즘"]
symptom_keywords: ["624개짜리 정수 배열이 상태로 쓰임", "9908b0df 상수가 보임", "twist라는 이름의 함수가 있음", "출력 전에 시프트와 AND가 여러 번 연속으로 적용됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
난수 상태가 정수 하나가 아니라 **624개 워드짜리 배열**이고, 그 배열을 624번마다 한 번씩 통째로 갱신하는 `twist` 단계와 상수 `0x9908B0DF`가 보이며, 출력 직전에 시프트와 AND 마스킹이 여러 번 연쇄적으로 적용된다면 이건 LCG(REV-0891)가 아니라 **Mersenne Twister(MT19937)**다.

## 언제 검색해야 하나
- 난수 생성 함수 근처에서 크기 624(또는 그 배수, 32비트 워드 배열)의 전역/정적 배열을 발견했을 때
- 상수 `0x9908B0DF`, `0x9D2C5680`, `0xEFC60000`, `1812433253`(0x6C078965) 중 하나라도 코드에 리터럴로 등장할 때
- 출력을 만드는 함수가 상태 배열에서 값 하나를 꺼낸 뒤, `>>`, `<<`, `&`, `^`를 네 번 정도 연속으로 적용하는 짧은 후처리(tempering) 단계를 거칠 때
- Python으로 작성된 문제 파일에서 `random.getrandbits()`, `random.random()`, `random.randint()`를 호출하고 이 값들의 예측/역산이 문제의 핵심일 때 — 파이썬 표준 `random` 모듈이 내부적으로 MT19937을 그대로 사용하기 때문

## 핵심 개념

### Mersenne Twister는 왜 CTF에 자주 나오는가
Mersenne Twister(정확히는 그 32비트 버전인 MT19937)는 매우 긴 주기(`2^19937 - 1`, 메르센 소수에서 이름이 유래)와 우수한 통계적 성질 덕분에 C++11 `std::mt19937`, Python `random` 모듈, PHP의 (구버전) `mt_rand()`, 여러 게임 엔진의 기본 난수 생성기로 널리 채택되어 있다. LCG(REV-0891)보다 훨씬 널리 쓰이지만, **암호학적으로는 여전히 안전하지 않다** — 연속된 출력 624개만 관찰하면 내부 상태 전체를 복원해서 이후의 모든 출력을 정확히 예측할 수 있다는 것이 잘 알려진 약점이다. 이 성질이 "난수를 미리 맞혀라", "다음 카드/주사위를 예측하라" 류의 CTF 문제로 그대로 이어진다.

### 상태 배열과 초기화 — 시드에서 624개 워드 만들기
MT19937은 32비트 워드 624개(`n=624`)로 구성된 상태 배열을 시드로부터 채운다.

```c
#define N 624
uint32_t mt[N];
int mti = N + 1;

void mt_seed(uint32_t seed) {
    mt[0] = seed;
    for (int i = 1; i < N; i++) {
        // 1812433253 = 0x6C078965 — 초기화 전용 승수
        mt[i] = 1812433253u * (mt[i-1] ^ (mt[i-1] >> 30)) + i;
    }
    mti = N;
}
```
이 초기화 루프는 LCG와 언뜻 비슷해 보이지만(곱셈+덧셈), **이전 워드를 오른쪽으로 30비트 시프트한 뒤 XOR한 값을 곱한다**는 점, 그리고 **624번 반복해서 배열 전체를 채운다**는 점이 결정적으로 다르다. 곱셈 상수 `1812433253`(16진수 `0x6C078965`)은 이 초기화 단계에만 쓰이는 값으로, 이 숫자 하나만 봐도 MT19937 초기화 루틴임을 강하게 의심할 수 있다.

### twist 단계 — 624개를 한꺼번에 갱신
상태 배열을 다 소모하면(624개를 다 뽑으면), `twist`라 불리는 재생성 단계가 배열 전체를 다시 채운다. 이 단계의 핵심 상수가 `0x9908B0DF`다.

```c
#define M 397
#define MATRIX_A 0x9908b0dfu
#define UPPER_MASK 0x80000000u
#define LOWER_MASK 0x7fffffffu

void mt_twist(void) {
    for (int i = 0; i < N; i++) {
        uint32_t y = (mt[i] & UPPER_MASK) | (mt[(i+1) % N] & LOWER_MASK);
        mt[i] = mt[(i + M) % N] ^ (y >> 1);
        if (y & 1) {
            mt[i] ^= MATRIX_A;   // 0x9908B0DF — 최하위 비트가 1일 때만 적용
        }
    }
    mti = 0;
}
```
`i`번째와 `(i+1) % N`번째 워드를 섞고, `(i + 397) % N`번째(오프셋 `M=397`이 또 하나의 고유 상수) 워드와 XOR하는 구조가 twist 단계의 특징이다. `y & 1`(최하위 비트) 검사 후 조건부로 `0x9908B0DF`를 XOR하는 부분은 LCG의 "조건부 곱하기"(REV-0886의 square-and-multiply)와 겉모습이 비슷해 보일 수 있으나, 여기서는 지수 연산이 아니라 배열 전체를 순회하는 상태 갱신이라는 점이 다르다.

### tempering — 출력 직전의 비트 뒤섞기
상태 배열에서 값을 하나 꺼낼 때, 그 값을 그대로 반환하지 않고 4단계의 시프트+마스킹+XOR로 이루어진 tempering을 거친다.

```c
uint32_t mt_next(void) {
    if (mti >= N) mt_twist();

    uint32_t y = mt[mti++];
    y ^= (y >> 11);
    y ^= (y << 7)  & 0x9d2c5680u;
    y ^= (y << 15) & 0xefc60000u;
    y ^= (y >> 18);
    return y;
}
```
이 네 줄의 tempering 연산은 MT19937의 가장 확실한 지문이다. 시프트량(`11, 7, 15, 18`)과 마스크(`0x9D2C5680`, `0xEFC60000`)가 정확히 이 값으로 고정되어 있으므로, 디스어셈블리에서 시프트-AND-XOR가 정확히 이 순서와 상수로 네 번 연속 나타나면 MT19937로 100% 확정할 수 있다.

### 상태 복원(untempering)이 가능한 이유
tempering의 각 단계(`y ^= y >> k`, `y ^= (y << k) & mask`)는 전부 **가역 연산**이다. XOR와 시프트만으로 구성되어 있어서, 출력값 하나가 주어지면 역순으로 시프트-XOR를 되돌려 tempering 이전의 원본 상태 워드를 정확히 복원할 수 있다. 연속된 출력 624개를 모두 untemper하면 상태 배열 전체(`mt[0..623]`)를 완전히 복원하게 되고, 그 다음부터는 twist 단계까지 그대로 재현해 **미래의 모든 출력을 정확히 예측**할 수 있다. 이것이 "Python `random` 모듈 예측기", "MT19937 cracker" 같은 도구들의 기본 원리다.

```python
def untemper(y):
    y ^= y >> 18
    y ^= (y << 15) & 0xefc60000
    # y ^= (y << 7) & 0x9d2c5680 은 한 번의 역연산으로 안 풀려서
    # 비트를 나눠 여러 번 적용해야 하는 등 구현이 다소 까다롭다(공개된 참조 구현 사용 권장)
    y ^= y >> 11
    return y
```

## 화면/코드에서 보이는 징후
- 크기 624(또는 624의 배수, 64비트 버전은 312)인 `uint32_t`/`unsigned int` 배열
- 상수 `1812433253`(초기화), `0x9908B0DF`(twist), `0x9D2C5680`·`0xEFC60000`(tempering) 중 하나 이상
- 함수 이름이나 지역변수에 `mt`, `twist`, `temper`가 strip 안 된 채 남아있는 경우
- 시프트량 `11, 7, 15, 18`이 정확히 이 순서로 XOR 연산과 함께 연쇄적으로 등장
- 인덱스 `(i + 397) % 624` 형태의 오프셋 접근(twist 단계 특유의 패턴)

## 가장 먼저 할 것
상태가 624개짜리 배열인지부터 확인한다. 배열이 아니라 스칼라 변수 하나라면 LCG(REV-0891)로 재분류한다. 배열이 맞다면 tempering 단계의 네 줄(시프트 11/7/15/18, 마스크 0x9D2C5680/0xEFC60000)이 있는지 확인해 MT19937을 확정한다.

## 단계별 절차
1. 상태 배열의 크기(624 근처)와 자료형(32비트 정수)을 확인
2. 초기화 함수에서 `1812433253` 상수가 있는지 확인해 시드 → 상태 배열 변환 루틴을 특정
3. twist 함수에서 `0x9908B0DF`와 `(i + 397) % 624` 패턴을 확인
4. 출력 함수에서 4단계 tempering(시프트 11/7/15/18)을 확인해 MT19937로 최종 확정
5. Python 문제라면 애초에 `import random`이 그대로 있는지 확인 — 있다면 표준 라이브러리이므로 별도 구현 분석 없이 공개된 MT19937 크래커/역산 도구를 바로 적용 가능
6. 연속된 출력 624개(32비트 전체가 노출되는 경우) 확보 후 untemper로 상태 복원
7. 복원한 상태로 twist를 재현해 이후 출력을 예측하거나, 필요하면 이전 시드까지 역추적

## 명령어/단축키
```python
# 상수 지문으로 MT19937 여부를 빠르게 확인
KNOWN_MT_CONSTANTS = [0x9908b0df, 0x9d2c5680, 0xefc60000, 1812433253]

def looks_like_mt19937(constants_found: set) -> bool:
    return len(set(KNOWN_MT_CONSTANTS) & constants_found) >= 2
```
IDA: `Alt+B`로 `DF B0 08 99`(리틀엔디안 바이트 순서) 검색. Ghidra: Data Type Manager에서 배열을 `uint32_t[624]`로 캐스팅해 twist 루프와 대조.

## 출력 해석
- 상수 4개 중 2개 이상이 확인되면 MT19937로 확정해도 무방하다.
- tempering된 출력값만 보이고 twist 전 원본 상태에 접근할 수 없다면, untemper 절차를 반드시 거쳐야 상태를 복원할 수 있다 — 출력을 그대로 시드처럼 쓰면 안 된다.
- Python `random.getrandbits(32)`를 624번 연속으로 얻을 수 있는 상황이라면(예: 웹 서비스가 매 요청마다 난수를 노출), 공개된 MT19937 상태 복원 스크립트를 그대로 적용해 이후 모든 난수를 예측할 수 있다.

## 흔한 실수
- 상태 배열 크기(624)를 확인하지 않고 아무 배열이나 MT19937로 오인하는 것.
- tempering을 거치지 않은 원본 상태 워드와 실제 출력값을 혼동해서 예측 계산이 틀어지는 것.
- 32비트 버전과 64비트 버전(`std::mt19937_64`)의 상수를 혼동하는 것 — 64비트 버전은 `a = 0xB5026F5AA96619E9`, 상태 크기 312 등 완전히 다른 상수 집합을 쓴다.
- 출력이 32비트 전체가 아니라 일부만 노출되는 경우(`random.random()`처럼 여러 출력을 조합해 부동소수점을 만드는 경우)를 감안하지 않고 곧바로 32비트 정수로 untemper를 시도하는 것.

## 막혔을 때 다음 체크
- 상태가 배열이 아니라 스칼라 변수 하나라면 → REV-0891 LCG(Linear Congruential Generator) 기반 난수 알아보기
- `rand()`/`srand()` 조합 자체를 다루는 실전 접근법이 필요하면 → REV-0893 rand()/srand() 시드 기반 문제 접근법
- untemper에 쓰이는 XOR-시프트 역연산의 일반 원리가 헷갈리면 → REV-0199 XOR 반복 변환 역산
- 상수들을 표로 빠르게 참조하고 싶다면 → REV-0883 흔한 시드 기반 PRNG 상수 빠른 참조(LCG 계수 등)

## 미니 예제
Ghidra로 어떤 게임 바이너리의 `roll_dice` 함수를 디컴파일했더니 다음이 나왔다고 하자.

```c
uint32_t y = mt_state[index++];
y = y ^ (y >> 11);
y = y ^ ((y << 7) & 0x9d2c5680);
y = y ^ ((y << 15) & 0xefc60000);
y = y ^ (y >> 18);
return y % 6 + 1;   // 주사위 눈(1~6)으로 변환
```
시프트량과 마스크가 정확히 표준 tempering과 일치하므로 MT19937이 확정된다. 남은 작업은 `y % 6 + 1` 이전의 32비트 원본 출력(`y`)들을 624개 모아 상태를 복원하는 것뿐이다.

```python
# 공개된 MT19937 untemper/재구현 라이브러리(예: 'mt19937predictor')를 활용하면
# 624개의 원본 32비트 출력만으로 이후 모든 주사위 결과를 예측할 수 있다.
from mt19937predictor import MT19937Predictor

predictor = MT19937Predictor()
for y in collected_outputs:   # 실제로 관찰한 624개의 32비트 값
    predictor.setrandbits(y, 32)

next_y = predictor.getrandbits(32)
print(next_y % 6 + 1)   # 다음 주사위 결과 예측
```

### 실행 가능한 전체 스크립트 — 외부 라이브러리 없이 MT19937을 직접 구현해서 상태 복원까지

`mt19937predictor` 같은 외부 라이브러리를 설치할 수 없는 오프라인 환경일 수도 있으니, 이번에는 MT19937 자체를 순수 파이썬으로 직접 구현하고, tempering을 역으로 되돌리는 `untemper` 함수까지 직접 만들어서 상태 복원이 실제로 되는지 끝까지 검증해본다. 이 코드는 표준 MT19937 알고리즘(초기화, twist, temper)을 그대로 옮긴 것이라 어떤 환경에서도 추가 설치 없이 동작한다.

```python
# -*- coding: utf-8 -*-

# --- MT19937의 고정 파라미터 (본문에서 설명한 그 상수들 그대로) ---
N = 624                    # 상태 배열의 워드 개수
M = 397                    # twist 단계에서 쓰이는 오프셋
MATRIX_A = 0x9908b0df       # twist 단계의 핵심 상수
UPPER_MASK = 0x80000000     # 32비트 중 최상위 1비트만 남기는 마스크
LOWER_MASK = 0x7fffffff     # 32비트 중 하위 31비트만 남기는 마스크

class MT19937:
    """표준 MT19937 참조 구현을 그대로 옮긴 파이썬 클래스."""

    def __init__(self, seed: int):
        self.mt = [0] * N              # 상태 배열 624개짜리를 0으로 초기화
        self.mt[0] = seed & 0xFFFFFFFF  # 첫 워드는 시드값 그대로(32비트로 자름)
        for i in range(1, N):
            # 1812433253 = 0x6C078965, 초기화 전용 승수(본문에서 설명한 그 상수)
            prev = self.mt[i - 1]
            self.mt[i] = (1812433253 * (prev ^ (prev >> 30)) + i) & 0xFFFFFFFF
        self.mti = N   # 상태를 다 소모한 것으로 표시해서, 첫 next() 호출 때 바로 twist 되게 함

    def twist(self):
        """624개 상태 워드를 한꺼번에 갱신 (본문에서 설명한 twist 단계)."""
        for i in range(N):
            y = (self.mt[i] & UPPER_MASK) | (self.mt[(i + 1) % N] & LOWER_MASK)
            self.mt[i] = self.mt[(i + M) % N] ^ (y >> 1)
            if y & 1:                      # 최하위 비트가 1일 때만 조건부로 XOR
                self.mt[i] ^= MATRIX_A
        self.mti = 0

    def next(self) -> int:
        """상태 하나를 꺼내 tempering까지 거친 뒤 32비트 출력값을 반환."""
        if self.mti >= N:
            self.twist()                    # 624개를 다 썼으면 다시 채운다
        y = self.mt[self.mti]
        self.mti += 1
        y ^= (y >> 11)                      # tempering 1단계
        y ^= (y << 7) & 0x9d2c5680           # tempering 2단계
        y ^= (y << 15) & 0xefc60000          # tempering 3단계
        y ^= (y >> 18)                       # tempering 4단계
        return y & 0xFFFFFFFF

def temper(y: int) -> int:
    """next()의 tempering 부분만 따로 뽑아둔 함수 (아래 untemper와 짝을 이룬다)."""
    y ^= (y >> 11)
    y ^= (y << 7) & 0x9d2c5680
    y ^= (y << 15) & 0xefc60000
    y ^= (y >> 18)
    return y & 0xFFFFFFFF

def _undo_right_shift_xor(y: int, shift: int) -> int:
    """'y ^= (y >> shift)' 형태의 연산을 역으로 되돌린다."""
    result = y
    for _ in range(32 // shift + 1):        # 몇 번 반복하면 비트가 전부 안정적으로 맞춰진다
        result = y ^ (result >> shift)
    return result & 0xFFFFFFFF

def _undo_left_shift_mask_xor(y: int, shift: int, mask: int) -> int:
    """'y ^= (y << shift) & mask' 형태의 연산을 역으로 되돌린다."""
    result = y
    for _ in range(32 // shift + 1):
        result = y ^ ((result << shift) & mask)
    return result & 0xFFFFFFFF

def untemper(y: int) -> int:
    """temper()의 네 단계를 역순으로 정확히 되돌려 tempering 이전 원본 워드를 복원."""
    y = _undo_right_shift_xor(y, 18)                       # 4단계 되돌리기
    y = _undo_left_shift_mask_xor(y, 15, 0xefc60000)        # 3단계 되돌리기
    y = _undo_left_shift_mask_xor(y, 7, 0x9d2c5680)         # 2단계 되돌리기
    y = _undo_right_shift_xor(y, 11)                        # 1단계 되돌리기
    return y & 0xFFFFFFFF

# --- 1) untemper가 temper의 정확한 역함수인지 자체 검증 ---
import random as _sanity_rng
ok = True
for _ in range(1000):
    x = _sanity_rng.getrandbits(32)
    if untemper(temper(x)) != x:
        ok = False
        break
print("untemper가 temper의 역함수로 정확히 동작하는가?", ok)

# --- 2) 실제 시나리오: 시드를 모르는 채로 624개의 "관찰된 출력"만 확보했다고 가정 ---
victim = MT19937(seed=12345)             # 공격 대상이 실제로 쓰는 생성기 (시드는 모른다고 가정)
observed_outputs = [victim.next() for _ in range(624)]   # 624개의 32비트 출력을 그대로 관찰

# --- 3) 관찰한 출력들을 untemper로 되돌려 tempering 이전의 원본 상태 배열을 복원 ---
recovered_state = [untemper(v) for v in observed_outputs]

clone = MT19937(seed=0)      # 아무 시드로 객체만 만들고, 상태는 바로 덮어씌운다
clone.mt = recovered_state[:]   # 624개 상태를 복원한 값으로 통째로 교체
clone.mti = N                    # 상태를 다 썼다고 표시해서, 다음 next() 때 twist부터 정확히 재현

# --- 4) 원본과 복제본이 이후에도 정확히 같은 값을 내는지 비교 ---
real_future = [victim.next() for _ in range(5)]
predicted_future = [clone.next() for _ in range(5)]
print("실제 이후 출력  :", real_future)
print("예측한 이후 출력:", predicted_future)
print("완전히 일치하는가?", real_future == predicted_future)
```

이 스크립트를 그대로 실행하면 다음과 같은 결과가 나온다.

```text
untemper가 temper의 역함수로 정확히 동작하는가? True
실제 이후 출력  : [3957348375, 3514278914, 622445323, 785134127, 428957220]
예측한 이후 출력: [3957348375, 3514278914, 622445323, 785134127, 428957220]
완전히 일치하는가? True
```

시드(`12345`)를 전혀 몰랐어도, 연속된 624개의 32비트 출력만 관찰하면 내부 상태 배열 전체를 복원해서 그 이후의 모든 출력을 한 글자도 틀리지 않고 예측할 수 있다는 것을 코드로 직접 확인했다. 이것이 "624개만 모으면 MT19937이 뚫린다"는 말의 실체다. 실전 CTF에서는 `victim`이 실제 바이너리(또는 문제 서버)가 되고, `observed_outputs`는 여러 번의 요청/출력으로 직접 수집한 값이 된다.

## 관련 글
- REV-0891 — LCG(Linear Congruential Generator) 기반 난수 알아보기
- REV-0893 — rand()/srand() 시드 기반 문제 접근법
- REV-0199 — XOR 반복 변환 역산
- REV-0883 — 흔한 시드 기반 PRNG 상수 빠른 참조(LCG 계수 등)

## 출처/검증
- MT19937 파라미터(`w=32, n=624, m=397, r=31`, `a=0x9908B0DF`, tempering 상수 `u=11, s=7, b=0x9D2C5680, t=15, c=0xEFC60000, l=18`)와 초기화 승수 `1812433253`: Makoto Matsumoto, Takuji Nishimura, "Mersenne Twister: A 623-dimensionally equidistributed uniform pseudo-random number generator" (ACM TOMACS, 1998) 및 C++ 표준(`std::mersenne_twister_engine`, ISO/IEC 14882) 파라미터 정의 기준 (2026-09-09 검증).
- Python `random` 모듈이 내부적으로 MT19937을 사용한다는 사실: Python 공식 문서 `random` 모듈 설명("The pseudo-random generators of this module should not be used for security purposes... uses the Mersenne Twister as the core generator") 기준 (2026-09-09 검증).
- tempering 연산의 가역성과 상태 복원(untemper) 원리: MT19937 상태 복원 공개 구현체 및 Cryptopals Crypto Challenges Set 3(Challenge 22/23, MT19937 관련 챌린지) 기준 (2026-09-09 검증).
