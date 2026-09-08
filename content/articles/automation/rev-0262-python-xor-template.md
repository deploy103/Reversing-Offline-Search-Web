---
id: REV-0262
title: "Python XOR 역산 템플릿"
slug: "rev-0262-python-xor-template"
category: "automation"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Python]
keywords: ["python xor 역산", "xor_bytes 함수", "repeating key xor python", "python 반복 키 xor", "xor 복호화 코드"]
aliases: ["파이썬 xor 함수", "xor bytes 템플릿", "rolling xor 파이썬 구현"]
symptom_keywords: ["xor 복호화 코드 어떻게 짜지", "반복 키 xor 파이썬으로 풀기", "flag xor 되어있음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
XOR은 자기 자신의 역함수이므로(`a ^ b ^ b = a`) 재사용 가능한 `xor_bytes(data, key)` 함수 하나만 만들어두면 고정 키, 반복 키(rolling key) XOR을 모두 같은 코드로 암호화/복호화할 수 있다.

## 언제 검색해야 하나
- 바이너리 안에서 `for` 루프로 입력 바이트를 키와 XOR한 뒤 정답 배열과 비교하는 패턴을 발견했을 때
- 암호화된 문자열(예: 설정 파일, 난독화된 API 이름)이 XOR로 인코딩되어 있다고 의심될 때
- 키 길이를 모를 때 여러 길이를 자동으로 시도해보는 스크립트가 필요할 때

## 핵심 개념
XOR의 핵심 성질은 자기 역원(self-inverse)이다.
```
a ^ b = c   이면   c ^ b = a
```
즉 "암호화"와 "복호화"가 완전히 같은 연산이다 — 같은 키로 다시 XOR하면 원래 값이 그대로 나온다. 이 성질 덕분에 XOR 기반 변환은 별도의 역함수를 만들 필요 없이, **같은 함수를 암호화에도 복호화에도 그대로 재사용**할 수 있다.

키 형태는 크게 두 가지다.
- **고정 키(single-byte 또는 고정 길이 키 1개)**: 모든 바이트에 동일한 키(바이트 하나 또는 정해진 길이의 키)를 반복 적용.
- **반복 키(repeating/rolling key)**: 키 길이가 데이터보다 짧아서 `key[i % len(key)]`처럼 순환시키며 적용. 고전적인 Vigenère 암호와 원리가 같다.

## 화면/코드에서 보이는 징후
```c
for (i = 0; i < len; i++) {
    out[i] = data[i] ^ key[i % keylen];
}
```
디스어셈블리에서는 `xor al, byte ptr [key + edx]` 형태로 나타나고, `edx`가 나눗셈/나머지 연산(`and edx, mask` 또는 `div`)으로 만들어진 인덱스라면 반복 키 XOR일 가능성이 높다. 자세한 어셈블리 패턴은 REV-0199에서 다룬다.

## 가장 먼저 할 것
암호화된(또는 비교 대상인) 바이트 배열과 키를 정확히 덤프한다. 키가 몇 바이트인지 모른다면 뒤의 "키 길이 추정" 절차를 먼저 수행한다.

## 단계별 절차
**1) 재사용 가능한 xor_bytes 함수**
```python
from itertools import cycle

def xor_bytes(data: bytes, key: bytes) -> bytes:
    """data와 key를 반복 키 XOR로 결합한다.
    key가 1바이트든, data보다 짧은 여러 바이트든 모두 동작한다."""
    return bytes(d ^ k for d, k in zip(data, cycle(key)))
```
`key`가 1바이트(`bytes([0x5A])`)여도, 4바이트(`b"CTF!"`)여도 동일하게 동작한다 — `cycle()`이 키를 필요한 만큼 반복해준다.

**2) 고정 키(단일 바이트) 사용 예**
```python
expected = bytes.fromhex("3c363b3d2122352827")
flag = xor_bytes(expected, bytes([0x5A]))
print(flag)   # b'flag{xor}'
```

**3) 반복 키 사용 예**
```python
expected = bytes.fromhex("25382746382c29531c65357e262e3b")
key = b"CTF!"
flag = xor_bytes(expected, key)
print(flag)
```

**4) 키를 모를 때 — 단일 바이트 키 전수 브루트포스**
알려진 부분 문자열(예: `flag{`)이 있다면 XOR 성질을 이용해 키를 역산할 수 있다.
```python
expected = bytes.fromhex("...")
known_prefix = b"flag{"

for i in range(len(expected) - len(known_prefix) + 1):
    # expected[i:i+len(known_prefix)]가 known_prefix가 되게 하는 키 후보 계산
    candidate_key = xor_bytes(expected[i:i+len(known_prefix)], known_prefix)
    print(i, candidate_key)
```
실제로는 키가 위치와 무관하게 고정이어야 하므로, `i=0`에서 얻은 후보 키로 전체를 복호화해 아스키 여부를 확인하는 식으로 좁혀간다.

**5) 키 길이를 모를 때 — 아스키 비율로 자동 탐색**
```python
def printable_ratio(b: bytes) -> float:
    return sum(0x20 <= c < 0x7F for c in b) / max(len(b), 1)

expected = bytes.fromhex("...")
best = (0.0, None, None)
for keylen in range(1, 17):
    for key_guess in range(256):
        key = bytes([key_guess]) * keylen   # 간단화: 단일 값 반복 (실전에선 바이트별 빈도분석 권장)
        result = xor_bytes(expected, key)
        ratio = printable_ratio(result)
        if ratio > best[0]:
            best = (ratio, keylen, key)
# best로 대략적인 키 길이 후보를 좁힌 뒤 정밀 탐색으로 넘어감
```
실전에서는 위 코드보다 "각 위치(`i % keylen`)별로 가장 자주 나오는 XOR 결과가 공백(`0x20`)이나 알려진 문자가 되는 키 바이트를 고르는" 빈도 분석이 더 정확하지만, 짧은 CTF 플래그에는 위 방식만으로도 충분히 실용적이다.

## 명령어/단축키
- IDA/Ghidra에서 XOR 명령을 찾으려면 `Search > Text`(또는 `Alt+T`)로 `xor`를 검색
- x64dbg: 커맨드바에 `find 00, "xor"` 또는 그래프 뷰에서 `xor` 관련 블록만 하이라이트
- Python: `itertools.cycle`, `bytes.fromhex`, 리스트 컴프리헨션

## 출력 해석
- 복호화 결과가 `flag{`, `CTF{` 같은 접두어로 깔끔하게 시작하면 키/방향 추정이 맞았다는 강한 신호다.
- 앞부분만 맞고 뒷부분이 깨진다면 반복 키 길이를 잘못 추정했을 가능성이 높다 — 키 길이를 늘리거나 줄여가며 다시 시도한다.
- 전부 깨진 값이 나온다면 XOR 앞뒤에 다른 변환(ADD/ROL 등)이 섞여 있을 수 있다.

## 흔한 실수
- `zip(data, cycle(key))`에서 `data`가 `key`보다 짧을 때는 문제없지만, 반대로 `cycle`을 안 쓰고 그냥 `key`만 `zip`하면 긴 데이터의 뒷부분이 잘려나가는 것 — 반드시 `cycle(key)`처럼 무한 반복자로 감싸야 한다.
- 반복 키의 방향을 착각하는 것 — `key[i % keylen]`이 정방향인지, 코드에 따라 `key[keylen - 1 - i % keylen]`처럼 역순인지 디스어셈블리를 다시 확인해야 한다.
- 체인 XOR(이전 바이트를 다음 키로 쓰는 CBC 스타일)을 반복 키 XOR로 착각해서 `xor_bytes`를 그대로 적용하는 것 — 이 경우는 REV-0199에서 다루는 별도의 순차 복원 로직이 필요하다.
- 8비트가 아니라 32비트 단위(`xor eax, key_dword`)로 XOR하는 코드를 1바이트 함수로 처리해 하위 바이트만 맞고 나머지가 틀리는 것 — 이럴 땐 REV-0261의 `struct.pack('<I', ...)`로 4바이트씩 묶어 XOR해야 한다.

## 막혔을 때 다음 체크
- 어셈블리에서 XOR 패턴이 단일 키/반복 키/체인 중 무엇인지 구분하는 방법이 더 필요하면 → REV-0199 (XOR 반복 변환 역산)에서 어셈블리 예제와 함께 상세히 다룬다.
- 32비트/64비트 단위로 묶어서 XOR해야 하면 → REV-0261 (struct pack/unpack)과 조합.
- XOR 앞뒤에 ROL/ROR가 섞여 있으면 → REV-0263 (Rotate 함수 템플릿)과 순서를 맞춰 함께 역산.

## 미니 예제
바이너리에서 다음 값을 확인했다고 하자: `expected = 1D 0B 1C 56 42 4E 04 13 05 0B 16 4E`, 키는 4바이트 `"CTF!"`.
```python
from itertools import cycle

def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(d ^ k for d, k in zip(data, cycle(key)))

expected = bytes.fromhex("25382746382c29531c65357e262e3b")
key = b"CTF!"
flag = xor_bytes(expected, key)
print(flag)   # 사람이 읽을 수 있는 문자열이 나오면 성공
```
같은 `xor_bytes` 함수로 반대로 `xor_bytes(flag, key)`를 하면 다시 `expected`가 나온다 — 암호화/복호화가 완전히 대칭이라는 것을 직접 확인할 수 있다.

## 관련 글
- REV-0261 — Python struct pack unpack
- REV-0263 — Python Rotate 함수 템플릿
- REV-0264 — Python 32비트 Overflow 재현
- ../algorithms/rev-0199-xor-loop-inversion.md

## 출처/검증
- XOR의 자기 역원 성질은 불(Boolean) 대수의 기본 정리이며 모든 CPU 아키텍처 매뉴얼에서 동일하게 성립. `itertools.cycle`은 Python 공식 문서(itertools 모듈) 기준(2026-09-08 확인).
