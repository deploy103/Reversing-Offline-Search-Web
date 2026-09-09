---
id: REV-0893
title: "rand()/srand() 시드 기반 문제 접근법"
slug: "rev-0893-rand-srand-seed-approach"
category: "algorithms"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg, Python, ltrace]
keywords: ["rand", "srand", "시드", "seed", "libc 식별", "PRNG 재현", "ctypes", "ltrace rand"]
aliases: ["rand srand 문제 푸는 법", "시드만 알면 되는 문제", "libc rand 재현", "난수 예측 실전"]
symptom_keywords: ["srand 호출 뒤에 rand를 여러 번 부름", "시드값이 화면에 출력되거나 파일에 남음", "어떤 libc를 쓰는지 몰라서 난수를 재현 못함", "rand 결과로 문제의 정답이 결정됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`srand(seed)`로 초기화한 뒤 `rand()`를 반복 호출해 문제의 정답이나 동작을 결정하는 바이너리를 만나면, 알고리즘을 직접 재구현하기 전에 **먼저 어떤 C 런타임(glibc/musl/MSVC)의 `rand()`인지부터 특정**해야 한다 — 런타임마다 내부 알고리즘이 완전히 다르기 때문이다.

## 언제 검색해야 하나
- 코드에서 `srand(...)` 호출 직후 `rand()`를 여러 번 호출해서 나온 값들로 배열 섞기, 카드 뽑기, 좌표 생성, 검증 상수 계산 등을 하는 패턴을 만났을 때
- "시드를 알아내라" 또는 "시드가 주어졌으니 이후 결과를 예측하라" 류의 문제 설명이 있을 때
- Import 목록에 `rand`, `srand`(POSIX/CRT) 심볼이 있고, 직접 구현한 PRNG(REV-0891, REV-0892)가 아니라 표준 라이브러리 함수를 그대로 호출하는 경우
- `strace`/`ltrace`로 실행을 관찰했더니 `time(NULL)` 뒤에 곧바로 `srand()`가 호출되는 것을 봤을 때(REV-0894로 이어지는 상황)

## 핵심 개념

### 왜 "런타임 식별"이 가장 먼저인가
`rand()`라는 이름은 표준화되어 있지만(C 표준은 "의사난수를 반환한다"는 동작만 규정할 뿐 알고리즘은 규정하지 않음), 실제 내부 알고리즘은 컴파일 대상 플랫폼마다 완전히 다르다.

- **glibc(리눅스 기본)**: 기본적으로 지연 피보나치형 덧셈 생성기(`TYPE_3`)를 쓴다. 상태는 31개 워드 배열이고, `r[i] = (r[i-3] + r[i-31]) mod 2^32`로 갱신되며 최종 출력은 `r[i+344] >> 1`(최하위 비트를 버려 31비트 값을 얻음)이다. **단순 LCG가 아니다.**
- **musl(Alpine 등 경량 리눅스 배포판)**: `rand_r()`는 `1103515245*x + 12345` 형태의 고전 LCG를 쓰지만, `rand()`/`random()` 자체는 이 LCG와 지연 피보나치 방식을 조합한 자체 구현을 쓴다. glibc와 동일하지 않으니 반드시 별도로 확인해야 한다.
- **MSVC(Windows CRT)**: `holdrand = holdrand * 214013 + 2531011`, 반환값은 `(holdrand >> 16) & 0x7fff` — REV-0891에서 다룬 순수 LCG.

즉 같은 "시드 42로 `rand()`를 5번 호출"이라는 시나리오라도 **바이너리가 어떤 libc/CRT에 링크되어 있느냐에 따라 나오는 값이 완전히 다르다.** 알고리즘을 재구현하기 전에 파일이 정적/동적 링크인지, 어떤 libc 버전인지(REV-0646, REV-0647 참고)부터 확인하는 게 순서다.

### 실전 접근 전략 — 재구현 vs 그대로 실행
직접 알고리즘을 재구현하는 것보다 훨씬 안전하고 빠른 방법이 있다 — **같은 libc/CRT를 그대로 호출**해서 값을 얻는 것이다.

**전략 1: ctypes로 시스템 libc의 rand()를 직접 호출(리눅스/glibc)**
```python
import ctypes

libc = ctypes.CDLL("libc.so.6")
libc.srand(42)
values = [libc.rand() for _ in range(5)]
print(values)   # 실제 glibc가 생성한 값과 100% 동일
```
이 방법은 glibc의 복잡한 내부 알고리즘을 몰라도 되고, **분석 환경이 챌린지와 같은 glibc 버전을 쓰는 한 100% 정확한 값을 얻는다**는 게 가장 큰 장점이다. 단, 분석 환경의 glibc 버전이 챌린지 배포 환경과 다르면 값이 달라질 수 있으므로, 가능하면 챌린지가 배포된 Docker 이미지/서버 환경에서 실행해 값을 뽑는 것이 가장 안전하다.

**전략 2: 알고리즘 자체를 파이썬으로 재구현**
분석 환경에 접근할 수 없거나(문제가 소스 코드만 주어진 경우 등) 오프라인 재현이 필요하면 알고리즘을 직접 옮긴다.

```python
# glibc 스타일 지연 피보나치 재구현 (TYPE_3, 상태 31 워드)
class GlibcRandom:
    def __init__(self, seed):
        r = [0] * 344
        r[0] = seed if seed != 0 else 1
        for i in range(1, 31):
            # word_size=32, hi/lo 곱셈은 int32 오버플로 규칙을 그대로 따른다
            r[i] = (16807 * r[i-1]) % 2147483647
            if r[i] < 0:
                r[i] += 2147483647
        for i in range(31, 34):
            r[i] = r[i - 31]
        for i in range(34, 344):
            r[i] = (r[i - 3] + r[i - 31]) & 0xFFFFFFFF
        self.r = r
        self.idx = 344

    def next(self):
        val = (self.r[self.idx - 3] + self.r[self.idx - 31]) & 0xFFFFFFFF
        self.r.append(val)
        self.idx += 1
        return val >> 1   # 최하위 비트를 버려 31비트 출력

g = GlibcRandom(42)
print([g.next() for _ in range(5)])
```
(위 시드 초기화 단계는 glibc의 실제 초기화 규칙을 단순화해 보여주는 것으로, 정확한 재현이 필요하면 공개된 `python-glibc-random` 류의 검증된 구현체를 쓰는 것을 권장한다.)

**전략 3: 바이너리 자체를 그대로 실행해서 관찰**
가장 확실한 방법은 바이너리를 직접 실행하면서 GDB/x64dbg로 `rand()` 반환값을 매 호출마다 덤프하는 것이다. `rand`(또는 그 심볼)에 브레이크포인트를 걸고 `finish` 명령으로 반환값을 확인하면, 알고리즘을 전혀 몰라도 실제 값을 그대로 얻을 수 있다.

```bash
gdb ./chall
(gdb) break rand
(gdb) run
(gdb) finish     # rand()의 반환값이 $eax/$rax에 담겨 표시됨
```

### 시드가 고정 상수인 경우와 그렇지 않은 경우
- **시드가 코드에 하드코딩된 상수**라면 문제는 사실상 끝난 것이다 — 그 시드로 위 세 전략 중 하나를 적용하면 이후 모든 `rand()` 출력을 그대로 재현할 수 있다.
- **시드가 `time(NULL)`처럼 실행 시점에 결정**된다면, 시드 자체를 좁혀야 한다 — REV-0894에서 이 상황을 구체적으로 다룬다.
- **시드가 사용자 입력에서 유도**된다면(예: 입력 문자열의 해시를 시드로 사용), 그 유도 과정을 먼저 리버싱해서 정확한 시드 계산식을 파이썬으로 옮겨야 한다.

## 화면/코드에서 보이는 징후
- Import 목록에 `srand`, `rand`(POSIX/CRT) 심볼이 그대로 있음(정적 링크면 REV-0646 참고해 시그니처로 확인)
- `srand()` 호출 인자가 상수이거나, `time()`의 반환값을 그대로 받음
- `rand()`의 반환값이 `% N` 형태로 특정 범위로 축소되어 배열 인덱스, 카드 값, 좌표 등으로 쓰임
- 여러 번의 `rand()` 결과가 순서대로 배열에 채워지고, 그 배열이 셔플이나 검증 로직에 쓰임

## 가장 먼저 할 것
바이너리가 동적 링크인지 정적 링크인지, 그리고 리눅스(glibc/musl)인지 Windows(MSVC)인지부터 확인한다(`file`, `checksec`, REV-0646/REV-0647 참고). 그 다음 시드가 상수인지 런타임 값인지 확인한다. 상수라면 ctypes/GDB로 바로 값을 뽑고, 런타임 값(특히 `time()`)이라면 REV-0894로 넘어간다.

## 단계별 절차
1. `file`, `ldd`, `checksec`으로 타깃 플랫폼과 libc 종류 확인
2. `srand()` 호출부에서 시드 값의 출처(상수/입력/시간)를 확인
3. 가능하면 분석 환경(챌린지와 같은 OS/libc 버전)에서 ctypes로 직접 `srand`+`rand` 호출해 실제 값 확보(전략 1)
4. 환경이 다르거나 재현이 어려우면 GDB/x64dbg로 실제 바이너리 실행 중 `rand()` 반환값을 직접 관찰(전략 3)
5. 오프라인 완전 재현이 꼭 필요하면 해당 libc의 공개 알고리즘을 파이썬으로 이식(전략 2, 검증된 구현체 사용 권장)
6. 확보한 난수열을 문제 로직(카드 순서, 좌표, 비교 상수 등)에 대입해 실제 정답 재현
7. `rand() % N` 같은 축소 연산이 있다면 그 나머지 연산까지 동일하게 적용해 최종 값 검증

## 명령어/단축키
```bash
# libc 종류/버전 확인
file ./chall
ldd ./chall
strings ./chall | grep -i "GNU C Library"

# 실행 중 rand() 반환값 직접 관찰
ltrace -e rand+srand ./chall
gdb -q ./chall -ex "break rand" -ex run -ex finish
```
```python
# ctypes로 같은 libc 그대로 호출(리눅스)
import ctypes
libc = ctypes.CDLL("libc.so.6")
libc.srand(1234)
print([libc.rand() for _ in range(3)])
```

## 출력 해석
- ctypes로 얻은 값이 바이너리 실행 결과와 일치하면 분석 환경과 챌린지 환경의 libc가 같다는 뜻이므로 이후 예측도 신뢰할 수 있다.
- 값이 다르다면 glibc 버전 차이(REV-0648 참고)나 아키텍처 차이(32/64비트) 가능성이 있으니, 챌린지가 배포된 정확한 환경(Docker 이미지 등)에서 다시 시도한다.
- `ltrace`가 `rand`/`srand`를 아예 잡아내지 못한다면 정적 링크(REV-0646)이거나 `ltrace`가 차단된 환경일 수 있으니 GDB 브레이크포인트 방식으로 전환한다.

## 흔한 실수
- glibc 환경인데 MSVC의 LCG 상수(REV-0891)로 재구현해서 값이 전혀 안 맞는 것 — 반드시 플랫폼부터 확인해야 한다.
- 분석 환경(WSL, 다른 배포판 등)의 glibc 버전이 챌린지 배포 서버와 달라서 같은 시드인데 다른 값이 나오는 것을 인지하지 못하는 것.
- `rand() % N`에서 나머지 연산을 빠뜨리고 원본 `rand()` 값을 그대로 비교해 결과가 안 맞는 것.
- 정적 링크 바이너리인데 동적 심볼을 찾다가 시간을 낭비하는 것(REV-0646의 정적 링킹 분석 전략을 먼저 적용해야 함).

## 막혔을 때 다음 체크
- 알고리즘 내부 구조(글리빅 지연 피보나치, MSVC LCG)를 더 자세히 알고 싶으면 → REV-0891 LCG(Linear Congruential Generator) 기반 난수 알아보기
- 배열 기반 상태를 가진 Mersenne Twister와 헷갈린다면 → REV-0892 Mersenne Twister 흔적 알아보기
- 시드가 `time(NULL)`에서 오는 경우의 구체적 공략법이 필요하면 → REV-0894 시간 기반 시드(seed = time())를 역산하는 접근
- 정적 링킹된 바이너리에서 `rand`/`srand` 심볼을 못 찾겠다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- glibc/musl 차이가 헷갈리면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향

## 미니 예제
어떤 카드 게임 CTF 바이너리를 리버싱했더니 다음과 같은 흐름이 나왔다고 하자.

```c
srand(1337);
int deck[52];
for (int i = 0; i < 52; i++) deck[i] = i;
for (int i = 51; i > 0; i--) {
    int j = rand() % (i + 1);
    int tmp = deck[i]; deck[i] = deck[j]; deck[j] = tmp;   // Fisher-Yates 셔플
}
// deck[0]이 플레이어의 첫 패
```
`file ./chall` 결과 동적 링크 ELF, `ldd` 결과 일반 glibc임을 확인했다면, 분석 환경이 같은 glibc 계열이라는 전제 하에 다음처럼 그대로 재현할 수 있다.

```python
import ctypes
libc = ctypes.CDLL("libc.so.6")
libc.srand(1337)

deck = list(range(52))
for i in range(51, 0, -1):
    j = libc.rand() % (i + 1)
    deck[i], deck[j] = deck[j], deck[i]

print(deck[0])   # 플레이어가 받을 첫 패를 실행 전에 미리 계산
```
이 값이 실제 바이너리 실행 결과와 일치하면, 시드(`1337`)와 셔플 로직만으로 결과 전체를 미리 알아낸 것이다.

## 관련 글
- REV-0891 — LCG(Linear Congruential Generator) 기반 난수 알아보기
- REV-0892 — Mersenne Twister 흔적 알아보기
- REV-0894 — 시간 기반 시드(seed = time())를 역산하는 접근
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향

## 출처/검증
- glibc `random()`/`rand()`의 기본 알고리즘(TYPE_3 지연 피보나치, `r[i] = r[i-3] + r[i-31] mod 2^32`, 출력은 `>> 1`)과 이것이 단순 LCG가 아니라는 점: `random(3)` 공식 Linux man 페이지 및 Peter Selinger(Dalhousie University)의 GLIBC PRNG 분석 기준 (2026-09-09 검증).
- musl libc `rand()`/`rand_r()`가 별도의 LCG+지연 피보나치 조합 구현이며 glibc와 동일하지 않다는 점: musl 공식 저장소 `src/prng/rand.c`, `src/prng/rand_r.c` 소스 기준 (2026-09-09 검증).
- Python `ctypes.CDLL`로 시스템 `libc.so.6`을 로드해 `rand`/`srand`를 직접 호출하는 기법: Python 공식 `ctypes` 문서(외부 공유 라이브러리 함수 호출) 기준 (2026-09-09 검증).
