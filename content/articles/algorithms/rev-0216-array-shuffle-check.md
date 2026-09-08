---
id: REV-0216
title: "배열 인덱스 재배열 Shuffle 검증"
slug: "rev-0216-array-shuffle-check"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["permutation", "shuffle", "순열", "인덱스 재배열", "scatter", "gather", "order array", "위치 이동"]
aliases: ["셔플 검증", "순서 뒤섞기", "인덱스 배열", "위치 재배열"]
symptom_keywords: ["값은 맞는데 순서가 이상함", "이중 인덱싱이 보임", "글자가 섞여 있음", "위치가 바뀐 것 같음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
입력 바이트의 **값 자체는 바뀌지 않고 위치만 뒤섞이는** 코드(`out[order[i]] = in[i]` 또는 `out[i] = in[order[i]]`)를 만나면, 이는 고정 순열(permutation) 배열에 의한 셔플이며, scatter 형태인지 gather 형태인지부터 정확히 구분해야 올바른 역변환을 만들 수 있다.

## 언제 검색해야 하나
- 디컴파일 결과에 값 변환(XOR, 덧셈, 테이블 치환)이 전혀 없는데 출력 문자열의 문자 구성은 입력과 똑같고 순서만 다를 때
- 루프 안에서 배열을 **이중으로 인덱싱**하는 코드(`idx = order[i]; out[idx] = in[i];` 같은 패턴)를 봤을 때
- "값은 다 맞는 것 같은데 순서가 이상하다"는 감이 들 때
- [REV-0214](./rev-0214-custom-alphabet-substitution.md)나 [REV-0215](./rev-0215-lookup-table-transform.md)를 적용해봤는데 값 자체는 이미 입력과 동일해서 뭔가 이상하다고 느껴질 때

## 핵심 개념
셔플(순열) 패턴은 값 치환과 완전히 다른 문제다. 값 치환은 "바이트 3의 값이 뭘로 바뀌는가"를 묻지만, 셔플은 "바이트 3이 어느 위치로 이동하는가"를 묻는다. 이 둘은 독립적으로 존재할 수도, 함께 쓰일 수도 있다.

셔플은 보통 **고정된 순서(permutation) 배열** `order`를 하나 가지고 있고, 이를 적용하는 방식은 크게 두 가지다.

**Scatter(흩뿌리기) 형태**: `out[order[i]] = in[i]` — "입력의 `i`번째 바이트를 `order[i]`번째 자리로 보낸다."

**Gather(모으기) 형태**: `out[i] = in[order[i]]` — "출력의 `i`번째 자리는 입력의 `order[i]`번째 바이트에서 가져온다."

이 두 형태는 서로 **정확히 반대의 관계**이며, 같은 `order` 배열을 쓰더라도 scatter로 만들어진 결과를 되돌리는 방법과 gather로 만들어진 결과를 되돌리는 방법이 다르다. 이걸 헷갈리면 복원한 결과가 완전히 엉뚱하게 나오므로, **바이너리가 둘 중 어느 형태를 쓰는지부터 코드를 보고 정확히 판단하는 것이 이 패턴 전체의 핵심**이다.

## 화면/코드에서 보이는 징후
루프 카운터 `i`가 순서 배열(`order`, `perm`, `idx` 등으로 이름 붙었을 수도, 이름 없는 `unk_...`일 수도 있음)을 인덱싱해서 두 번째 인덱스 값을 얻고, 그 값으로 다시 입력/출력 배열을 인덱싱하는 **이중 참조**가 핵심 신호다.

```asm
movzx eax, byte [rdi+rcx]     ; order[i]를 로드 (rdi=order, rcx=i)
movzx edx, byte [rsi+rax]     ; 그 값을 인덱스로 써서 input[order[i]]를 로드
```

이때 루프 카운터 `rcx`(즉 `i`) 자신이 입력/출력 배열을 직접 인덱싱하는 게 아니라, `order[i]`를 거쳐서 간접적으로 인덱싱한다는 점이 값 치환 패턴과 다른 결정적 차이다.

IDA/Ghidra 디컴파일에서는 각각 다음처럼 보인다:
```c
for (i = 0; i < 16; i++)
    out[order[i]] = in[i];      // scatter: in[i]가 order[i] 자리로 감
```
```c
for (i = 0; i < 16; i++)
    out[i] = in[order[i]];      // gather: out[i]는 order[i] 자리에서 옴
```
차이는 **`order[i]`가 왼쪽(대입 대상)에 있는지, 오른쪽(값을 가져오는 곳)에 있는지**뿐이다. 이 위치를 정확히 읽는 것이 전체 절차의 출발점이다.

## 가장 먼저 할 것
디스어셈블리나 디컴파일에서 셔플 루프를 찾으면, 가장 먼저 **`order[i]`가 대입식의 좌변(scatter)인지 우변(gather)인지**부터 확인한다. 이걸 착각하면 이후 모든 역변환 계산이 틀어지므로, 코드를 여러 번 다시 읽어서라도 확실히 하는 것이 시간을 아끼는 길이다.

## 단계별 절차

**1) order 배열 추출**

xref를 따라가서 순서 배열의 시작 주소와 길이를 확인하고, [REV-0215](./rev-0215-lookup-table-transform.md)에서 설명한 방법(IDA `Edit → Export data`, IDAPython 콘솔, Ghidra `Copy Special`)으로 바이트를 그대로 뽑는다.

**2) scatter인지 gather인지 판정**

디컴파일된 대입문에서 `order[i]`가 좌변 인덱스인지 우변 인덱스인지 확인한다. 애매하면 디버거(x64dbg, gdb)로 실제 실행 중 루프 한 바퀴만 단계 실행(`Step Into`, `si`)해서 어느 배열의 어느 위치에 값이 쓰이는지 직접 관찰한다.

**3) Scatter 형태 예제로 검증**

8개짜리 순서 배열 `order = [3, 1, 4, 0, 6, 2, 7, 5]`가 입력 `b"ABCDEFGH"`에 scatter 형태(`out[order[i]] = in[i]`)로 적용된다고 하자. 하나씩 손으로 추적하면:
- `out[order[0]] = out[3] = in[0] = 'A'`
- `out[order[1]] = out[1] = in[1] = 'B'`
- `out[order[2]] = out[4] = in[2] = 'C'`
- `out[order[3]] = out[0] = in[3] = 'D'`
- `out[order[4]] = out[6] = in[4] = 'E'`
- `out[order[5]] = out[2] = in[5] = 'F'`
- `out[order[6]] = out[7] = in[6] = 'G'`
- `out[order[7]] = out[5] = in[7] = 'H'`

각 자리를 인덱스 순서(0~7)로 정리하면 `out[0]='D', out[1]='B', out[2]='F', out[3]='A', out[4]='C', out[5]='H', out[6]='E', out[7]='G'`이므로 최종 결과는 `"DBFACHEG"`이다.

**4) Scatter의 역변환**

scatter 공식 `out[order[i]] = in[i]`을 그대로 뒤집으면 `in[i] = out[order[i]]`가 된다. **같은 `order` 배열을 그대로, 인덱싱 방향만 바꿔서 쓰면 된다** — 별도의 역배열을 만들 필요가 없다.
```python
order = [3, 1, 4, 0, 6, 2, 7, 5]
scrambled = b"DBFACHEG"   # 바이너리가 만들어낸 결과
original = bytes(scrambled[order[i]] for i in range(len(order)))
print(original)  # b"ABCDEFGH"
```
`order[0]=3`이므로 `scrambled[3]='A'`가 `original[0]`이 되고, `order[1]=1`이므로 `scrambled[1]='B'`가 `original[1]`이 된다 — 정확히 원래 입력이 복원된다.

**5) Gather 형태라면 명시적 역배열이 필요**

만약 반대로 바이너리가 gather 형태(`out[i] = in[order[i]]`)를 쓴다면, 같은 `order`를 그대로 재사용해서는 안 되고 **명시적으로 역순열을 만들어야** 한다:
```python
def invert_permutation(order):
    inv = [0] * len(order)
    for i, p in enumerate(order):
        inv[p] = i
    return inv

order = [3, 1, 4, 0, 6, 2, 7, 5]
inv = invert_permutation(order)
scrambled = b"..."  # gather로 만들어진 결과
original = bytes(scrambled[inv[i]] for i in range(len(inv)))
```
gather 공식은 `out[i] = in[order[i]]`이므로 `in[k] = out[i]` (단, `order[i] = k`)가 되고, 이는 `i = inv[k]`이므로 `in[k] = out[inv[k]]`가 된다. 즉 gather를 되돌릴 때는 `order`가 아니라 `inv`를 인덱스로 써야 한다.

## 명령어/단축키
```python
def invert_permutation(order):
    inv = [0] * len(order)
    for i, p in enumerate(order):
        inv[p] = i
    return inv
```
x64dbg: `F7`(Step Into)로 루프 한 바퀴씩 실행하며 레지스터/메모리 창에서 실제 대입 대상 관찰
IDA: xref(`Ctrl+X`)로 순서 배열을 참조하는 모든 위치 확인

## 출력 해석
- scatter 역변환(`scrambled[order[i]]`) 결과가 사람이 읽을 수 있는 문자열로 나오면 성공.
- gather인데 scatter 방식(또는 그 반대)으로 되돌렸다면, 결과가 원래 입력과 다르게 뒤섞인 채로 나온다 — 이 경우 반드시 3)번으로 돌아가 scatter/gather 판정을 다시 확인한다.
- 복원 결과의 문자 구성(멀티셋)은 원래 스크램블된 문자열과 동일해야 정상이다. 문자 종류 자체가 달라졌다면 셔플이 아니라 값 변환(REV-0214, REV-0215)이 섞여 있는 것이다.

## 흔한 실수
- `order` 배열을 자기 자신의 역배열이라고 착각해서 scatter 결과에 gather 방식을 적용(또는 그 반대)하는 경우 — 오직 스왑 같은 대합(involution) 순열(`[1,0,3,2]`처럼 두 번 적용하면 원래로 돌아오는 특수한 경우)에서만 `order`가 자기 자신의 역이 된다. 일반적인 순열에서는 반드시 scatter/gather를 구분해서 처리해야 한다.
- 순서 배열의 값 범위가 0-based인지 1-based인지 확인하지 않고 그대로 파이썬 인덱스로 사용하는 경우 — C 코드가 1부터 세는 관례를 쓴 경우 모든 인덱스에서 1을 빼야 한다.
- gather의 역변환을 만들 때 `invert_permutation` 없이 그냥 `order`를 다시 적용해서 "왜 복원이 안 되지"라고 헤매는 경우.
- 이중 인덱싱을 발견하지 못하고 "이거 그냥 단순 값 변환이네"라고 REV-0214/0215만 적용했다가 값은 맞는데 순서가 이상한 결과를 얻는 경우 — 디스어셈블리에서 `order`/`perm` 역할을 하는 배열을 한 번 더 찾아본다.

## 막혔을 때 다음 체크
- 2차원 격자(행/열) 형태로 위치가 재배열되는 것 같다면 → [REV-0217 중첩 루프와 행렬 변환](./rev-0217-nested-loop-matrix-transform.md)에서 2D 일반화 버전 확인.
- 이 순열이 정말 항상 역변환 가능한지(bijective) 궁금하다면 → [REV-0221 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md)에서, 값 치환과 달리 순열은 정의상 항상 전단사(bijection)이므로 항상 역변환이 존재한다는 점을 확인.
- 순서 배열 자체를 못 찾겠다면 → [REV-0215 Lookup Table 기반 변환](./rev-0215-lookup-table-transform.md)의 테이블 추출 절차부터 다시 따라간다.

## 미니 예제
IDA에서 다음과 같은 디컴파일 결과를 봤다고 하자:
```c
unsigned char order[8] = {3, 1, 4, 0, 6, 2, 7, 5};

void shuffle(unsigned char *out, unsigned char *in, int n)
{
    for (int i = 0; i < n; i++)
        out[order[i]] = in[i];   // order[i]가 좌변 -> scatter
}
```
`order[i]`가 대입식의 왼쪽(`out[...]`)에 있으므로 scatter 형태다. 파이썬으로 순방향과 역방향을 모두 재현하면:
```python
order = [3, 1, 4, 0, 6, 2, 7, 5]

def shuffle_scatter(data, order):
    out = bytearray(len(data))
    for i, v in enumerate(data):
        out[order[i]] = v
    return bytes(out)

def unshuffle_scatter(data, order):
    return bytes(data[order[i]] for i in range(len(order)))

original = b"ABCDEFGH"
scrambled = shuffle_scatter(original, order)
print(scrambled)                          # b"DBFACHEG"
restored = unshuffle_scatter(scrambled, order)
print(restored)                           # b"ABCDEFGH"
assert restored == original
```
검증 루틴이 "셔플된 입력이 목표 문자열과 같으면 Correct"라는 구조라면, 목표 문자열에 `unshuffle_scatter`를 적용해 원래 입력을 즉시 복원할 수 있다.

## 관련 글
- [REV-0215 — Lookup Table 기반 변환](./rev-0215-lookup-table-transform.md)
- [REV-0217 — 중첩 루프와 행렬 변환](./rev-0217-nested-loop-matrix-transform.md)
- [REV-0221 — 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md)
- [REV-0222 — 검증 루틴을 Python으로 그대로 재현하기](./rev-0222-reimplement-in-python.md)

## 출처/검증
- 순열(permutation)의 scatter/gather 형태와 역순열 구성 방법: 이산수학 표준 이론(순열의 역원은 항상 존재한다는 대칭군 성질) 및 CTF 리버싱 writeup에서 반복 관찰되는 구현 패턴 기준 (2026-09-08 검증).
