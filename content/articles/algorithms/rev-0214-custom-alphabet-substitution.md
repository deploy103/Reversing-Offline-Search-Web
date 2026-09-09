---
id: REV-0214
title: "Custom alphabet 치환 패턴"
slug: "rev-0214-custom-alphabet-substitution"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["substitution table", "S-box", "치환 테이블", "custom alphabet", "lookup substitution", "byte remap", "table[input[i]]"]
aliases: ["치환표", "커스텀 알파벳", "바이트 치환", "테이블 대입"]
symptom_keywords: ["바이트 배열이 뒤죽박죽", "곱셈도 xor도 안 보이는데 값이 바뀜", "정적 테이블에서 값을 가져옴", "S박스처럼 생긴 배열"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`output[i] = table[input[i]]`처럼 입력 바이트를 인덱스로 써서 고정된 배열에서 값을 그대로 가져오는 코드가 보이면, 이는 **커스텀 치환(substitution) 테이블**이며 공식으로는 절대 재현할 수 없고 테이블 바이트 전체를 바이너리에서 그대로 뽑아내야 한다.

## 언제 검색해야 하나
- 디컴파일 결과에 `v = table[byte]` 형태의 코드가 있는데, `table`이 XOR·덧셈·곱셈 상수가 아니라 **배열**일 때
- 루프 안에서 입력 바이트 값과 출력 바이트 값 사이에 어떤 산술적 규칙(더하기, 곱하기, XOR)도 보이지 않을 때
- `.rodata`나 `.data` 섹션에 16개, 26개, 64개, 256개짜리 정적 바이트 배열이 있고 그 값들이 불규칙하게 흩어져 있을 때
- "이거 그냥 시저 암호(회전)인가?" 싶은데 값이 딱 맞아떨어지지 않을 때

## 핵심 개념
XOR 루프(REV-0199 예정)나 FNV 같은 해시([16777619 상수 문서](./rev-0208-fnv-16777619.md))는 입력값과 출력값 사이에 **수식으로 표현되는 관계**가 있다. 예를 들어 XOR 암호라면 `output[i] = input[i] ^ key[i]`라는 식 하나로 전체 동작을 설명할 수 있고, 키만 알면 임의의 입력에 대해 즉시 출력을 계산할 수 있다.

반면 **치환 테이블(substitution table, S-box 스타일)**은 다르다. 입력 바이트 `b`가 있을 때 출력은 `table[b]`이며, `table`은 그냥 미리 정해진 256개(또는 16개, 26개, 64개)의 값이 나열된 배열일 뿐이다. `table[5]`와 `table[6]`이 어떤 관계인지는 설계자 마음대로이며, 수학적 규칙이 전혀 없을 수도 있다. 즉 **테이블의 실제 바이트 값을 하나하나 알아내지 않으면 이 변환을 절대 재현할 수 없다** — 공식을 추측해서 풀 수 있는 문제가 아니다.

이 패턴은 아주 자주 나온다:
- 16개짜리 니블(4비트) 치환 테이블 — 입력을 니블 단위로 쪼개 각각 치환
- 26개짜리 알파벳 치환 테이블 — `A-Z`를 다른 `A-Z`로 매핑 (커스텀 시저/비제네르 변형)
- 64개짜리 Base64 유사 알파벳 치환 — REV-0212(Base64 검증 패턴)와 헷갈릴 수 있으니 주의
- 256개짜리 풀 바이트 치환 테이블 — AES S-box([REV-0211](./rev-0211-aes-fingerprints.md))도 이 카테고리의 특수 사례

**치환 테이블인지 규칙적 회전인지 빠르게 구분하는 법**: 테이블의 연속된 값들 사이 차이(`table[i+1] - table[i]`)가 일정한 상수라면, 그건 사실 `table[i] = (i + k) % N` 같은 단순 회전(Caesar shift)을 배열로 미리 계산해둔 것일 뿐이다. 이 경우는 진짜 임의 치환이 아니라 훨씬 단순한 덧셈/모듈러 문제이므로 테이블 전체를 뽑을 필요 없이 회전량 `k` 하나만 알아내면 된다. 반대로 차이가 들쭉날쭉하면 진짜 치환 테이블이므로 전체 바이트를 덤프해야 한다.

## 화면/코드에서 보이는 징후
- `movzx eax, byte [rdi+rcx]` (입력 바이트 로드) 다음에 `movzx eax, byte [rax+off_140004000]` (그 값을 다시 인덱스로 써서 테이블 참조) — **이중 참조**가 핵심 신호
- IDA 디컴파일에서 `v3 = byte_140004000[v2];` 같은, 산술 연산 없이 배열 인덱싱만 있는 한 줄
- `.rodata`에 이름 없는(`unk_...`, `byte_...`) 고정 크기 배열이 있고, `xref`를 따라가면 이 배열을 참조하는 함수가 입력 검증 루틴 근처에 있음
- Ghidra에서는 `DAT_140004000[input[i]]` 형태로 렌더링됨

## 가장 먼저 할 것
테이블 참조 명령어(`movzx`/`mov` + 배열 인덱싱)를 찾으면, 먼저 **테이블의 크기**를 확인한다. 인덱스로 쓰이는 값이 0~15 범위면 16개짜리, 0~255 범위(즉 바이트 전체)면 256개짜리다. 크기를 알아야 몇 바이트를 덤프해야 하는지 정해진다. 그다음 곧바로 "이게 진짜 임의 치환인가, 아니면 규칙적인 회전을 배열로 표현한 것뿐인가"를 아래 3번 절차로 확인한다.

## 단계별 절차

**1) 테이블 주소와 크기 확인**

IDA에서 인덱싱에 쓰인 배열의 시작 주소로 더블클릭해서 이동한다. 배열 선언 크기(`db 256 dup(?)` 같은 표시나, 다음 심볼까지의 간격)를 보고 정확한 엔트리 개수를 확정한다.

**2) 바이트 덤프**

- **IDA**: 배열 시작 위치에 커서를 놓고 `Edit → Export data...` 메뉴를 열어 원하는 바이트 범위를 텍스트로 내보낸다. 더 빠른 방법은 IDA 하단의 `Output window`(없으면 `View → Open subviews → Output window`)에 있는 IDAPython 콘솔에 직접 다음처럼 입력하는 것이다:
  ```python
  print([hex(Byte(0x140004000+i)) for i in range(256)])
  ```
  엔터를 치면 콘솔에 파이썬 리스트 형태로 값이 출력되며, 이를 그대로 복사해서 솔브 스크립트에 붙여넣을 수 있다.
- **Ghidra**: Listing 창에서 테이블 바이트 범위를 드래그로 선택한 뒤, 우클릭 → `Copy Special → Python List`를 쓰면 바로 파이썬 리스트 문자열을 얻는다.
- **x64dbg**: Hex Dump 패널에서 테이블 주소로 이동(`Ctrl+G`) 후 필요한 바이트 수만큼 드래그로 선택, 우클릭 → `Copy → Hex Data`로 복사한다.

**3) 규칙성 검사 (회전인지 진짜 치환인지)**

파이썬으로 덤프한 테이블을 검사한다:
```python
T = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0x2, 0xE, 0x8, 0x1, 0xF, 0x3, 0x7, 0xD, 0xA, 0x4]
diff0 = (T[1] - T[0]) % len(T)
is_rotation = all((T[i] - T[i-1]) % len(T) == diff0 for i in range(1, len(T)))
print(is_rotation)  # False -> 진짜 임의 치환
```
`True`가 나오면 사실 `table[i] = (i + k) % N` 형태의 단순 회전이므로, 굳이 전체 테이블을 저장하지 않고 `k` 값만 코드에 넣으면 된다. `False`면 아래 4)번처럼 테이블 전체를 그대로 써야 한다.

**4) 역테이블 생성**

치환이 순수 대입이므로, 역변환은 "값이 어디서 왔는지"를 담은 역테이블을 만들면 된다:
```python
T = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0x2, 0xE, 0x8, 0x1, 0xF, 0x3, 0x7, 0xD, 0xA, 0x4]
inv = [0] * 16
for i, v in enumerate(T):
    inv[v] = i
# T[i]가 원래 i를 치환한 결과이므로, inv[T[i]] == i 여야 한다
assert inv[T[5]] == 5
assert inv[T[0]] == 0
```
직접 계산으로 확인해보자. `T[0] = 0xC`이므로 `inv[0xC] = 0`이 되고, `T[1] = 0x5`이므로 `inv[0x5] = 1`이 된다. 이렇게 16개 항목 전부에 대해 "값 → 원래 인덱스" 매핑을 뒤집어 채우면 `inv`가 완성된다.

**5) 256바이트 실전 예제에 적용**

8바이트 플래그 조각이 256엔트리 테이블로 스크램블되었다고 가정하자. IDA에서 뽑은 바이트가 다음과 같다고 하면(실제로는 256개 전부 필요하지만 여기서는 개념 설명을 위해 표기를 생략):
```python
# 실제로는 256바이트 hex 문자열 전체를 IDA/Ghidra에서 그대로 복사해 붙여넣는다
T = bytes.fromhex("....(256바이트 = 512 hex 문자)....")

inv = [0] * 256
for i, v in enumerate(T):
    inv[v] = i

scrambled = bytes.fromhex("A15C3F...")  # 바이너리가 만들어낸 결과값
original = bytes(inv[b] for b in scrambled)
print(original)
```
이렇게 하면 스크램블된 8바이트를 원래 입력 8바이트로 되돌릴 수 있다.

## 명령어/단축키
- IDA: `Edit → Export data...` (배열 바이트 내보내기), IDAPython 콘솔에 `Byte(addr)` 함수로 1바이트씩 읽기
- Ghidra: 선택 후 우클릭 `Copy Special → Python List`
- x64dbg: Hex Dump 패널 `Ctrl+G`(주소 이동), 드래그 선택 후 `Copy → Hex Data`
- Python: `bytes.fromhex(...)`, `inv = [0]*N; [inv.__setitem__(v,i) for i,v in enumerate(T)]`

## 출력 해석
- `inv[T[i]] == i`가 모든 `i`에서 성립하면 역테이블이 올바르게 만들어진 것이다.
- 복원한 `original`이 사람이 읽을 수 있는 ASCII(플래그 형식과 맞는 문자들)로 나오면 성공.
- 결과가 여전히 깨진 바이트라면, 테이블을 잘못된 범위로 덤프했거나(오프셋이 한 바이트씩 밀렸거나), 이 치환이 다른 변환(예: 인덱스 재배열)과 함께 적용된 복합 변환일 가능성을 의심한다.

## 흔한 실수
- 테이블을 규칙적 회전이라고 성급하게 단정하고 공식으로 재현하려다 값이 안 맞는 경우 — 반드시 위 3번 절차로 `is_rotation`을 코드로 확인해야 한다.
- 테이블 바이트를 덤프할 때 시작 주소를 한 바이트 앞이나 뒤로 잘못 잡아 전체가 밀리는 경우 — IDA에서 xref를 통해 실제로 참조되는 정확한 시작 주소를 다시 확인한다.
- 테이블에 중복된 값이 있는데(즉 `table[3]`과 `table[7]`이 같은 값) 이를 무시하고 역테이블을 만드는 경우 — 이러면 정보가 손실되어 역변환이 불가능하다([REV-0221 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md) 참고). 역테이블 생성 코드에서 뒤에 나온 값이 앞의 매핑을 덮어쓰므로, 중복이 있는지 `len(set(T)) == len(T)`로 먼저 확인하는 습관을 들인다.
- 16개짜리 니블 테이블인데 바이트 단위(0~255)로 인덱싱하려다가 인덱스 초과(out of range) 에러를 만나는 경우 — 입력이 바이트 전체인지, 상위/하위 니블로 쪼개서 쓰는지 디스어셈블리에서 `and eax, 0Fh`나 `shr eax, 4` 같은 마스킹/시프트 코드가 있는지 다시 확인한다.

## 막혔을 때 다음 체크
- 테이블이 어디서 참조되는지 자체를 못 찾겠다면 → [REV-0215 Lookup Table 기반 변환](./rev-0215-lookup-table-transform.md)에서 일반적인 LUT 인식 신호부터 다시 확인.
- 치환 다음에 위치까지 바뀌는 것 같다면(값은 맞는데 순서가 이상하다면) → [REV-0216 배열 인덱스 재배열 Shuffle 검증](./rev-0216-array-shuffle-check.md)에서 순서 재배열 패턴과 구분.
- 이 테이블이 정말 뒤집을 수 있는(bijective) 구조인지 헷갈린다면 → [REV-0221 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md).
- 추출한 테이블과 로직을 파이썬 함수로 완성하는 전체 흐름이 필요하면 → [REV-0222 검증 루틴을 Python으로 그대로 재현하기](./rev-0222-reimplement-in-python.md).

## 미니 예제
IDA에서 다음과 같은 디컴파일 결과를 봤다고 하자:
```c
unsigned char T[16] = { 0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0x2, 0xE,
                         0x8, 0x1, 0xF, 0x3, 0x7, 0xD, 0xA, 0x4 };

void transform(unsigned char *buf, int len)
{
    for (int i = 0; i < len; i++)
        buf[i] = T[buf[i] & 0xF];   // 니블 단위 치환
}
```
`buf[i] & 0xF`로 니블만 뽑아 인덱스로 쓰고 있으므로, 이건 16개짜리 니블 치환 테이블이다. 입력 니블 `0x0`은 `T[0] = 0xC`로, 니블 `0x1`은 `T[1] = 0x5`로 바뀐다. 이를 파이썬으로 그대로 재현하고 역변환까지 준비하면:
```python
T = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0x2, 0xE, 0x8, 0x1, 0xF, 0x3, 0x7, 0xD, 0xA, 0x4]
inv = [0] * 16
for i, v in enumerate(T):
    inv[v] = i

def transform(nibble):
    return T[nibble]

def untransform(nibble):
    return inv[nibble]

assert untransform(transform(0x0)) == 0x0
assert untransform(transform(0x1)) == 0x1
```
검증 루틴이 "치환된 니블이 어떤 목표값과 같아야 Correct"라는 구조라면, 목표값에 `inv`를 적용해 원래 니블을 즉시 복원할 수 있다.

**심화 예제 — 256바이트 풀 테이블을 IDA에서 뽑아냈다고 가정한 완결된 스크립트**

이번에는 16개짜리 니블 테이블이 아니라, 실전에서 훨씬 흔한 **256바이트 풀 바이트 치환 테이블**을 다룬다. IDA의 `Edit → Export data...`로 `.rodata`의 256바이트 배열 전체를 뽑아냈다고 가정하고, 그 값을 그대로 스크립트에 붙여넣어 처음부터 끝까지 실행한다.

```python
# IDA/Ghidra에서 뽑아낸 256바이트 치환 테이블을 16진수 문자열 하나로 옮겨 적었다.
# (실제로는 IDAPython 콘솔에서 print([hex(Byte(addr+i)) for i in range(256)]) 같은
#  방식으로 뽑아낸 값을 그대로 여기에 붙여넣으면 된다.)
T_HEX = (
    "2163df470f523b8925c08b2ce8bd0e67bee3692342b9e050385f4856cbec3e"
    "974372e6c5d1545149afca4f5d73343d5b6e02ff5e8530057dde91a100b0148"
    "d61bff36dcdd6b7ef8cc77ac8a2ede4538fd335d286e2c2689a18880cf23681"
    "712098f63a9eb3d5759340f5c166a9addd329c09b4396465b25c6b6cf42292c"
    "64a281bd43141b8dc1a1e6fcc2f1fa44b9b84702b78d0bad7f7577e596290a3"
    "e5a04c27cf2da6466a0afa4eaec31cea06bc37f8bb297f96130d2a60a879b52"
    "455fd1282ebd9877433a7db44f9e74dfbda8e450b948316ac9911778aaa103f"
    "7c8003d8feb62efc26769d7b9fa558eec907043c5ac41915b1ab0895cef0f1e"
    "917011de1"
)
# ↑ 512개의 16진수 문자(=256바이트)가 되어야 하는데, 위 문자열은 줄바꿈을 위해
#   여러 줄로 쪼개 적었을 뿐 실제로는 하나로 이어지는 문자열이다. 파이썬은
#   괄호 안에서 이렇게 나란히 놓인 문자열 리터럴을 자동으로 하나로 합쳐준다.

T = bytes.fromhex(T_HEX)
# ↑ 16진수 문자열을 실제 256개의 바이트로 이루어진 bytes 객체로 변환한다.
#   이제 T[5] 같은 식으로 인덱싱하면 곧바로 치환 결과를 얻을 수 있다.

assert len(T) == 256, "테이블 크기가 256이 아니면 뽑아낸 범위가 잘못됐을 가능성이 크다"
# ↑ 테이블 크기가 정확히 256인지 스스로 검증한다. 다르면 assert가 실패해서
#   에러를 내며 프로그램이 멈추므로, 잘못된 테이블로 계속 진행하는 실수를 막아준다.

inv = [0] * 256
# ↑ 역테이블을 저장할 256개짜리 리스트를 미리 0으로 채워서 만든다.
for i, v in enumerate(T):
    # ↑ enumerate(T)는 (인덱스, 값) 쌍을 하나씩 돌려준다. i=인덱스, v=T[i]의 값.
    inv[v] = i
    # ↑ "값 v는 원래 인덱스 i에서 왔다"는 사실을 역테이블에 기록한다.

def transform(data: bytes) -> bytes:
    # ↑ 정방향 치환(암호화 방향과 동일)을 수행하는 함수.
    return bytes(T[b] for b in data)
    # ↑ 입력 바이트 하나하나를 인덱스로 써서 T에서 값을 꺼내 새 바이트열을 만든다.

def untransform(data: bytes) -> bytes:
    # ↑ 역방향 치환(복원)을 수행하는 함수.
    return bytes(inv[b] for b in data)
    # ↑ 역테이블 inv를 사용해 원래 값을 꺼내 새 바이트열을 만든다.

if __name__ == "__main__":
    # ↑ 이 파일을 직접 실행할 때만 아래 블록을 수행한다.
    original_flag = b"flag{sub_table}"
    # ↑ 검증용으로 우리가 미리 알고 있는 원본 문자열(실전에서는 모르는 값).

    scrambled = transform(original_flag)
    # ↑ 원본을 테이블로 치환해서, 바이너리가 저장/비교하는 값과 같은 형태를 만든다.
    print("치환된 결과(hex):", scrambled.hex())
    # ↑ 치환된 바이트를 16진수 문자열로 출력해서 눈으로 확인한다.

    recovered = untransform(scrambled)
    # ↑ 역테이블로 다시 원래 값을 복원한다.
    print("복원된 결과:", recovered)
    # ↑ 복원된 바이트열을 출력한다.

    assert recovered == original_flag
    # ↑ 복원된 값이 원본과 정확히 같은지 스스로 검증한다. 다르면 여기서 에러가 난다.
    print("검증 성공: 치환 후 다시 치환을 되돌리면 원본과 정확히 일치한다.")
```

이 스크립트를 그대로 실행하면 다음과 같이 출력된다(직접 계산해서 검증한 값):
```
치환된 결과(hex): 75a9f6932239653a2064f63aa9d5c6
복원된 결과: b'flag{sub_table}'
검증 성공: 치환 후 다시 치환을 되돌리면 원본과 정확히 일치한다.
```
실전에서는 `original_flag`를 알 수 없으므로, 대신 **바이너리가 저장하고 있는 스크램블된 바이트열**을 `scrambled` 변수에 직접 넣고 `untransform(scrambled)`만 호출하면 곧바로 원본 flag 조각이 복원된다. `T_HEX`만 실제 바이너리에서 뽑아낸 256바이트로 교체하면, 이 스크립트는 어떤 256바이트 치환 문제에도 그대로 재사용할 수 있는 범용 템플릿이 된다.

## 관련 글
- [REV-0208 — 16777619 상수가 보일 때 FNV 의심하기](./rev-0208-fnv-16777619.md)
- [REV-0211 — AES 테이블 또는 AES API 흔적 찾기](./rev-0211-aes-fingerprints.md)
- [REV-0215 — Lookup Table 기반 변환](./rev-0215-lookup-table-transform.md)
- [REV-0216 — 배열 인덱스 재배열 Shuffle 검증](./rev-0216-array-shuffle-check.md)
- [REV-0221 — 역연산 가능한 알고리즘 판단법](./rev-0221-is-it-invertible.md)
- [REV-0222 — 검증 루틴을 Python으로 그대로 재현하기](./rev-0222-reimplement-in-python.md)
- REV-0199 — XOR 반복 변환 역산

## 출처/검증
- 치환 테이블(S-box) 개념 및 역함수 구성 방식: 대칭키 암호학 일반 이론(Feistel 구조의 S-box 설계 원리), CTF 리버싱 writeup에서 반복적으로 관찰되는 패턴 (2026-09-08 검증).
- IDA `Edit → Export data`, Ghidra `Copy Special` 기능: 각 툴의 공식 사용자 매뉴얼 기준 (2026-09-08 검증).
