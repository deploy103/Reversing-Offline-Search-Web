---
id: REV-0217
title: "중첩 루프와 행렬 변환"
slug: "rev-0217-nested-loop-matrix-transform"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["matrix transform", "2D array", "행렬 변환", "row-major", "transpose", "rotate 90", "Hill cipher", "이중 루프"]
aliases: ["행렬 뒤집기", "그리드 변환", "2차원 배열 순회", "회전 변환"]
symptom_keywords: ["이중 루프 i j", "행렬 곱셈처럼 생김", "2차원 배열 인덱싱", "그리드 회전"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
입력을 `arr[row*WIDTH + col]` 같은 2차원 그리드로 다루고 이중 루프(`i`, `j`)로 순회하는 코드가 보이면, 이는 전치(transpose)/회전/행렬 곱셈 같은 **행렬 변환**이며, 데이터 이동만 하는지(전치·회전) 실제 산술 연산(`imul` 누적)까지 하는지를 먼저 구분해야 난이도가 갈린다.

## 언제 검색해야 하나
- 디스어셈블리에 `i`, `j` 두 개의 카운터를 쓰는 중첩 루프가 있고, 주소 계산에 `i*WIDTH + j` 같은 패턴이 보일 때
- 디컴파일 결과가 `arr[i][j]` 또는 `arr[i*4+j]` 형태로 렌더링될 때
- 플래그 길이가 정사각수(4, 9, 16, 25...)이거나 "가로×세로"로 나뉘는 것 같은 힌트가 있을 때
- [REV-0216](./rev-0216-array-shuffle-check.md)에서 다룬 1차원 셔플로는 설명이 안 되고, 2차원처럼 행/열 단위로 움직이는 것 같을 때

## 핵심 개념
행렬 변환은 [REV-0216](./rev-0216-array-shuffle-check.md)에서 다룬 1차원 순열의 2차원 버전이라고 볼 수 있다. 플래그나 입력을 `WIDTH × HEIGHT` 격자로 보고, 다음 중 하나(또는 조합)를 적용한다:

- **전치(transpose)**: `new[j][i] = old[i][j]` — 행과 열을 맞바꿈
- **90도 회전**: 시계/반시계 방향으로 격자를 통째로 돌림
- **행/열 교환**: 특정 행이나 열끼리 순서를 바꿈
- **행렬 곱셈(Hill cipher류)**: 진짜 선형대수 연산 — 각 출력 값이 입력 여러 개의 가중합으로 계산됨

컴파일러가 2차원 배열을 실제 메모리에 저장하는 방식은 보통 **row-major**다. 즉 `array[ROWS][COLS]`로 선언된 C 배열은 메모리상에서 `row0 전체, row1 전체, row2 전체 ...` 순서로 저장되고, `array[i][j]`의 실제 주소는 `base + (i*COLS + j) * element_size`로 계산된다. 어셈블리에서는 이게 `imul`(행 번호와 너비를 곱함) 다음에 `add`(열 번호를 더함)로 나타난다.

여기서 **가장 중요한 구분점**은 루프 안에 곱셈이 있느냐 없느냐다.
- 전치나 회전은 **값을 전혀 바꾸지 않고 위치만 옮긴다** — 곱셈은 오직 주소 계산(인덱스 계산)에만 등장하고, 데이터 값 자체에는 산술 연산이 없다.
- Hill cipher류의 진짜 행렬 곱셈은 **값 자체를 계산**하기 위해 `sum += matrix[i][k] * vector[k]`처럼 누적합 안에 곱셈이 들어간다. 이건 삼중 루프(`i`, `j`, `k`)로 나타나는 경우가 많다.

이 차이를 못 보고 회전을 행렬 곱셈으로, 또는 그 반대로 오인하면 완전히 잘못된 방향으로 시간을 쓰게 된다.

## 화면/코드에서 보이는 징후
- x64 Intel 문법으로 행 오프셋을 계산하는 전형적인 패턴 (너비가 4일 때):
  ```asm
  imul eax, [rbp+i], 4      ; row * WIDTH
  add  eax, [rbp+j]         ; + col
  ; 또는 곱셈 없이 shl로 대체되기도 함 (WIDTH가 2의 거듭제곱일 때)
  ```
- 더 간단히 `imul eax, edi, 4h` 후 `add eax, esi`처럼 레지스터 두 개로 표현되기도 함
- Ghidra/IDA 디컴파일: `arr[i*4+j]` (1차원 배열로 표현) 또는 IDA가 진짜 2차원 타입을 인식했다면 `arr[i][j]`
- 값 계산 없이 대입만 있으면 전치/회전, `imul` 결과가 다시 다른 변수에 누적(`+=`)되면 행렬 곱셈

## 가장 먼저 할 것
이중 루프를 발견하면, 먼저 루프가 **몇 겹**인지 센다. 2중 루프면 대부분 전치/회전/행 열 교환이고, **3중 루프**(`i`, `j`, `k`)에 누적 합과 곱셈이 함께 있으면 진짜 행렬 곱셈(Hill cipher류)이다. 이 판단 하나로 이후 작업량이 크게 달라지므로 가장 먼저 확인한다.

## 단계별 절차

**1) 그리드 크기(WIDTH, HEIGHT) 확정**

주소 계산에 쓰인 곱셈 상수(`imul ..., 4`라면 WIDTH=4)를 읽고, 전체 배열 길이를 이 값으로 나눠 HEIGHT를 구한다.

**2) 루프 깊이로 유형 분류**

2중 루프 + 곱셈이 인덱스 계산에만 등장 → 전치/회전류(3번으로). 3중 루프 + 곱셈이 값 누적에 등장 → 행렬 곱셈류(6번으로).

**3) 전치/회전 공식 확정 — 예제로 검증**

4×4 격자 `"ABCDEFGHIJKLMNOP"`를 다음처럼 배치했다고 하자:
```
row0: A B C D
row1: E F G H
row2: I J K L
row3: M N O P
```
시계방향 90도 회전 공식은 `new[j][N-1-i] = old[i][j]` (N=4)이다. 몇 칸만 손으로 검산해보면:
- `old[0][0]='A'` → `j=0, N-1-i=3` → `new[0][3]='A'`
- `old[3][0]='M'` → `j=0, N-1-i=0` → `new[0][0]='M'`

이렇게 전체를 계산하면 결과 격자는:
```
row0: M I E A
row1: N J F B
row2: O K G C
row3: P L H D
```
1차원으로 펼치면 `"MIEANJFBOKGCPLHD"`가 된다.

**4) 파이썬으로 순방향/역방향 구현**

```python
def rotate90_cw(grid, n):
    return [[grid[n-1-j][i] for j in range(n)] for i in range(n)]

def rotate90_ccw(grid, n):
    return [[grid[j][n-1-i] for j in range(n)] for i in range(n)]

grid = [list("ABCD"), list("EFGH"), list("IJKL"), list("MNOP")]
rotated = rotate90_cw(grid, 4)
print(["".join(r) for r in rotated])
# ['MIEA', 'NJFB', 'OKGC', 'PLHD']

restored = rotate90_ccw(rotated, 4)
assert restored == grid
```
시계방향 회전은 반시계방향 회전으로 되돌린다. 즉 바이너리가 시계방향 90도 회전을 적용했다면, 풀이 스크립트는 반시계방향 90도 회전(`rotate90_ccw`)을 적용하면 된다.

**5) 인덱싱 방향(row-major 확신) 검증**

디컴파일 코드만 보고 row-major라고 가정했다가 실제로는 반대(column-major처럼 보이게 최적화된 코드)일 수 있다. 확실히 하려면: 입력에 서로 다른 마커 바이트(`0, 1, 2, 3, ...`처럼 구분되는 값)를 채워 넣고, 디버거(x64dbg, GDB)로 루프를 한 바퀴씩 단계 실행(`Step Into`)하면서 **각 입력 인덱스가 정확히 어느 출력 위치로 가는지** 직접 관찰한다. 디컴파일러가 최적화된 코드에서 배열 차원을 잘못 추정하는 경우가 있으므로, 코드만 읽고 넘어가지 말고 실제 실행으로 한 번은 검증한다.

**6) 진짜 행렬 곱셈(Hill cipher류) — 작은 예제로 검증**

2×2 키 행렬 `K = [[3, 5], [1, 2]]`을 mod 26(전통적인 Hill cipher 크기, 실제 CTF에서는 mod 256을 바이트에 적용하는 경우가 많다)으로 평문 쌍 `(0, 1)`(문자 'A'=0, 'B'=1)에 적용하면:
```
c0 = (3*0 + 5*1) % 26 = 5   -> 'F'
c1 = (1*0 + 2*1) % 26 = 2   -> 'C'
```
어셈블리에서는 이게 삼중 루프(행 `i`, 열 `j`, 내적 인덱스 `k`)로 나타나고, 핵심 신호는 `sum += matrix[i][k] * vector[k]`처럼 **곱셈 결과가 누적 변수에 더해지는** 패턴이다. 단순 회전/전치는 절대 이렇게 값끼리 곱하지 않는다.

**7) 행렬 곱셈의 역변환 — 모듈러 역행렬**

Hill cipher류를 되돌리려면 키 행렬의 **모듈러 역행렬**(원소별 나눗셈이 아니라, adjugate 행렬 × 행렬식의 모듈러 역원)을 계산해야 한다. 이는 회전/전치보다 훨씬 어렵고, 모든 행렬이 역행렬을 가지는 것도 아니다(행렬식이 모듈러스와 서로소여야 함). 이 판단 기준은 [REV-0221 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md)에서 일반적인 틀로 다룬다.

## 명령어/단축키
```python
def rotate90_cw(grid, n):
    return [[grid[n-1-j][i] for j in range(n)] for i in range(n)]

def rotate90_ccw(grid, n):
    return [[grid[j][n-1-i] for j in range(n)] for i in range(n)]

def transpose(grid, n):
    return [[grid[j][i] for j in range(n)] for i in range(n)]
```
x64dbg/GDB: `Step Into`(`F7`/`si`)로 루프 한 바퀴씩 실행하며 실제 인덱싱 방향 관찰
IDA: 변수 타입을 `Y`로 지정해 배열 차원이 올바르게 표시되는지 확인

## 출력 해석
- 회전/전치 결과가 원래 격자와 동일한 문자 집합을 같은 개수로 가지면(위치만 바뀌었으면) 정상.
- 행렬 곱셈 결과 값이 `% N` 범위를 벗어나면 모듈러스를 빼먹은 것이니 다시 확인.
- 복원한 결과가 여전히 뒤섞여 있다면 회전 방향(시계 vs 반시계)이나 row-major/column-major 가정이 틀렸을 가능성이 크므로 5)번 절차로 돌아가 실제 실행으로 재확인한다.

## 흔한 실수
- row-major(`arr[i*W+j]`)와 column-major(`arr[j*H+i]`)를 혼동해서 전치된 채로 결과를 잘못 복원하는 경우 — 디컴파일 결과만 믿지 말고 5)번처럼 마커 바이트로 직접 검증한다.
- 회전 방향(시계 vs 반시계)을 반대로 적용해서 90도가 아니라 270도 회전한 것처럼 결과가 나오는 경우 — `rotate90_cw`를 적용해야 하는데 `rotate90_ccw`를 적용했거나 그 반대인 경우이니, 작은 예제로 먼저 검산해보고 방향을 확정한다.
- 단순 전치/회전인데 억지로 행렬식과 모듈러 역행렬까지 계산하려고 하는 경우 — 값 자체에 곱셈(누적합)이 있는지부터 확인하면 이런 헛수고를 피할 수 있다.
- Hill cipher류에서 모듈러스를 26(알파벳 크기)이라고 무작정 가정하는 경우 — 실제 CTF에서는 바이트 전체에 적용되는 mod 256 버전이 더 흔하므로, 코드에 있는 실제 마스크(`and eax, 0FFh`인지 `% 26`을 흉내내는 코드인지)를 반드시 확인한다.

## 막혔을 때 다음 체크
- 2차원이 아니라 1차원 순서 재배열이라면 → [REV-0216 배열 인덱스 재배열 Shuffle 검증](./rev-0216-array-shuffle-check.md).
- 이 행렬이 역변환 가능한지(행렬식이 모듈러스와 서로소인지) 판단하는 일반적인 기준이 필요하다면 → [REV-0221 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md).
- 추출한 변환 로직을 완성된 파이썬 솔브 스크립트로 정리하고 싶다면 → [REV-0222 검증 루틴을 Python으로 그대로 재현하기](./rev-0222-reimplement-in-python.md).

## 미니 예제
IDA에서 다음과 같은 디컴파일 결과를 봤다고 하자:
```c
void rotate_grid(char *out, char *in, int n)
{
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            out[j*n + (n-1-i)] = in[i*n + j];
}
```
값 계산 없이 대입만 하고 있고, 인덱스 계산에 곱셈(`j*n`)과 뺄셈(`n-1-i`)만 등장하므로 이는 데이터 이동만 하는 회전 변환이다. `out[j][n-1-i] = in[i][j]` 형태이므로 정확히 위에서 다룬 시계방향 90도 회전 공식과 같다. 파이썬으로 즉시 재현:
```python
def rotate_grid(data: str, n: int) -> str:
    grid = [list(data[i*n:(i+1)*n]) for i in range(n)]
    out = [[''] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            out[j][n-1-i] = grid[i][j]
    return "".join("".join(row) for row in out)

result = rotate_grid("ABCDEFGHIJKLMNOP", 4)
print(result)  # MIEANJFBOKGCPLHD
```
검증 루틴이 "회전된 격자가 목표 문자열과 같으면 Correct"라는 구조라면, 목표 문자열에 반대 방향 회전(`rotate90_ccw`)을 적용해 원래 입력을 즉시 복원할 수 있다.

**심화 예제 — 16글자 flag를 4×4 격자 회전에서 복원하는 완결된 스크립트**

이번에는 실제로 16글자짜리 flag 후보가 4×4 격자로 시계방향 90도 회전되어 저장된 상황을 가정하고, 처음부터 끝까지 실행되는 스크립트로 복원한다.

```python
def rotate90_cw(grid: list[list[str]], n: int) -> list[list[str]]:
    # ↑ n×n 격자를 시계방향으로 90도 회전시켜 새 격자를 돌려주는 함수.
    return [[grid[n - 1 - j][i] for j in range(n)] for i in range(n)]
    # ↑ 새 격자의 [i][j] 위치에는 원래 격자의 [n-1-j][i] 값을 가져다 놓는다.
    #   이 한 줄이 바로 "행과 열을 어떻게 맞바꾸는가"를 나타내는 회전 공식이다.

def rotate90_ccw(grid: list[list[str]], n: int) -> list[list[str]]:
    # ↑ 시계방향 회전을 정확히 되돌리는, 반시계방향 90도 회전 함수.
    return [[grid[j][n - 1 - i] for j in range(n)] for i in range(n)]
    # ↑ rotate90_cw와 정반대 방향으로 인덱스를 계산하므로, 두 함수를 순서대로
    #   적용하면 원래 격자로 정확히 돌아온다.

def str_to_grid(s: str, n: int) -> list[list[str]]:
    # ↑ 길이 n*n인 1차원 문자열을 n×n 2차원 격자(리스트의 리스트)로 바꿔주는 함수.
    return [list(s[i * n:(i + 1) * n]) for i in range(n)]
    # ↑ 문자열을 n글자씩 잘라서 한 행씩 만들고, 그 행들을 모아 격자를 완성한다.

def grid_to_str(grid: list[list[str]]) -> str:
    # ↑ 2차원 격자를 다시 1차원 문자열로 펼쳐주는 함수(str_to_grid의 반대).
    return "".join("".join(row) for row in grid)
    # ↑ 각 행(row)의 문자들을 먼저 이어붙이고, 그 행들을 다시 순서대로 이어붙인다.

if __name__ == "__main__":
    # ↑ 이 파일을 직접 실행할 때만 아래 블록을 수행한다.
    original_flag = "FLAG_ROTATE_GRID"
    # ↑ 검증용 원본 16글자 문자열(4×4 격자에 정확히 맞는 길이, 실전에서는 모르는 값).

    grid = str_to_grid(original_flag, 4)
    # ↑ 16글자 문자열을 4×4 격자로 바꾼다.

    rotated_grid = rotate90_cw(grid, 4)
    # ↑ 바이너리가 하는 것처럼(가정) 시계방향으로 90도 회전시킨다.
    rotated_str = grid_to_str(rotated_grid)
    # ↑ 회전된 격자를 다시 1차원 문자열로 펼친다 — 이게 바이너리가 저장/비교하는 값이다.
    print("회전된 결과:", rotated_str)
    # ↑ 회전된 문자열을 출력해서 확인한다.

    restored_grid = rotate90_ccw(rotated_grid, 4)
    # ↑ 반시계방향 90도 회전으로 원래 격자를 복원한다.
    restored_str = grid_to_str(restored_grid)
    # ↑ 복원된 격자를 다시 1차원 문자열로 펼친다.
    print("복원된 결과:", restored_str)
    # ↑ 복원된 문자열을 출력한다.

    assert restored_str == original_flag
    # ↑ 복원 결과가 원본과 정확히 같은지 스스로 검증한다.
    print("검증 성공: 시계방향 회전은 반시계방향 회전으로 정확히 되돌아온다.")
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 계산해서 검증한 값):
```
회전된 결과: GA_FRTRLIEOAD_TG
복원된 결과: FLAG_ROTATE_GRID
검증 성공: 시계방향 회전은 반시계방향 회전으로 정확히 되돌아온다.
```
즉 바이너리가 `"FLAG_ROTATE_GRID"`라는 16글자 문자열을 4×4 격자로 놓고 시계방향으로 90도 돌리면 `"GA_FRTRLIEOAD_TG"`라는, 전혀 알아볼 수 없는 문자열이 저장/비교된다. 실전에서는 이 `"GA_FRTRLIEOAD_TG"` 위치에 바이너리에서 실제로 뽑아낸 값을 넣고, `str_to_grid` → `rotate90_ccw` → `grid_to_str` 세 단계만 그대로 실행하면 즉시 원래 flag가 복원된다.

## 관련 글
- [REV-0216 — 배열 인덱스 재배열 Shuffle 검증](./rev-0216-array-shuffle-check.md)
- [REV-0215 — Lookup Table 기반 변환](./rev-0215-lookup-table-transform.md)
- [REV-0221 — 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md)
- [REV-0222 — 검증 루틴을 Python으로 그대로 재현하기](./rev-0222-reimplement-in-python.md)

## 출처/검증
- row-major 2차원 배열 메모리 레이아웃 및 주소 계산 공식: C 언어 표준(ISO/IEC 9899) 배열 레이아웃 규정 기준 (2026-09-08 검증).
- Hill cipher 행렬 곱셈 및 모듈러 역행렬을 통한 복호화 원리: 고전 암호학 표준 이론(Lester S. Hill, 1929) 기준 (2026-09-08 검증).
