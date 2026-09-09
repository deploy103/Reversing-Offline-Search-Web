---
id: REV-1037
title: "[Write-up] ezmix"
slug: "rev-1037-writeup-ezmix"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["dreamhack ezmix", "드림핵 ezmix", "ezmix 리버싱"]
aliases: ["ezmix 풀이", "ezmix 못풀겠음"]
symptom_keywords: ["드림핵 ezmix 어떻게 풀어야 할지 모르겠음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
"ezmix"(Bronze 1)라는 이름은 드림핵 CTF Season 7 Round #4(Div2)에도 등장하지만 그곳에서는 pwnable(시스템 해킹) 카테고리 문제로 확인되어, 드림핵 워게임의 리버싱 카테고리 "ezmix"(Bronze 1)와 동일한 문제인지는 확정할 수 없다. 이름이 "easy mix"의 축약형으로 보이는 만큼, mix-compare(REV-1036)와 유사하게 여러 비교/변환 연산이 섞였지만 그중에서도 상대적으로 쉬운(ez) 축에 속하는 문제로 추정하고 접근하는 것이 합리적이다.

## 언제 검색해야 하나
- "ezmix"를 검색했는데 같은 이름의 다른 대회(pwnable 카테고리) 문제 정보만 나와서 헷갈릴 때
- 리버싱 워게임 문제인데 이름 때문에 pwnable 문제로 착각하고 스택/힙 취약점을 찾다가 시간을 낭비했을 때
- Bronze 1 최하위 난이도인데도 XOR, 비트 시프트, 문자열 뒤섞기(mix) 같은 연산이 여러 개 겹쳐 있어 손으로 역산하기 번거로울 때

## 핵심 개념
검색을 통해 확인한 사실은 "ezmix"라는 이름이 드림핵 CTF Season 7 Round #4(Div2) 대회에 pwnable 카테고리 문제(코인 20, Official Writeup 존재)로 등장한다는 것이다. 이 저장소가 다루는 대상은 드림핵 워게임의 리버싱 카테고리 "ezmix"(Bronze 1)이므로, 두 문제가 이름만 같은 서로 다른 문제일 가능성이 있다는 점을 먼저 분명히 해둔다. 드림핵은 워게임 문제를 CTF 라운드에 재활용하는 경우가 흔하지만, 카테고리가 다르게 표기된 이상 이 둘을 같은 문제로 단정할 근거는 부족하다.

이름 "ezmix"에서 유추할 수 있는 것은 두 가지다.

- "ez"(easy)는 mix-compare 계열 문제들 중에서도 상대적으로 쉬운 버전임을 암시한다.
- "mix"는 REV-1036에서 다룬 것과 같이 여러 연산(비교, XOR, 뒤섞기)이 함께 쓰였다는 것을 암시한다.

리버싱 카테고리라는 점을 감안하면, pwnable 문제와 달리 스택 오버플로우나 메모리 손상을 노리는 것이 아니라 정적/동적 분석으로 알고리즘 자체를 파악해 올바른 입력값을 계산해내는 유형일 가능성이 높다. Bronze 1이므로 연산 종류가 많아도 각각은 단순한 산술/비트 연산(XOR, ADD, 시프트)일 것으로 추정된다.

## 화면/코드에서 보이는 징후
- 입력 문자열을 받은 뒤 여러 개의 연산(XOR, ADD, 자리 바꾸기)을 순서대로 적용하는 짧은 함수가 보임
- 연산 결과를 미리 정해진 배열/문자열과 최종 비교하는 한 줄의 `cmp` 또는 `memcmp`가 마지막에 존재
- pwnable 카테고리에서 흔히 보이는 `gets`/버퍼오버플로우 패턴이 아니라, 입력 길이를 명확히 제한하는 `scanf("%Ns", ...)` 형태의 안전한 입력 처리가 보임(리버싱 문제이므로 메모리 손상을 유도하지 않는 구조일 가능성)

## 가장 먼저 할 것
바이너리가 pwnable 스타일(취약한 입력 함수, 스택 배치)인지 순수 리버싱 스타일(안전한 입력 + 알고리즘 검증)인지부터 코드를 훑어 구분한다. 리버싱 문제로 확인되면 REV-1036과 같은 방식으로 비교/연산 지점을 모두 나열한다.

## 단계별 절차
1. `checksec`/Detect It Easy로 보호 기법과 입력 함수의 안전성 확인 → pwnable류가 아님을 확인
2. IDA/Ghidra에서 입력값에 적용되는 연산(XOR, ADD, 시프트, 자리 교환)을 순서대로 나열
3. 최종 비교 대상 값(하드코딩된 배열/문자열)을 확인
4. 적용된 연산의 역연산을 순서를 거꾸로 적용해 원래 입력값을 계산(예: XOR은 자기 역연산, ADD는 SUB로, 자리교환은 다시 교환)
5. 계산한 입력값을 실제 바이너리에 넣어 검증

## 명령어/단축키
```text
IDA: F5(Ghidra 스타일 디컴파일이 필요하면 Ghidra 사용), Ctrl+X(xref)
Python: 역연산 스크립트 작성 시 pwntools 없이도 순수 파이썬 for 루프로 충분
```

## 출력 해석
연산이 여러 개 이어져 있다면 마지막 비교에서 실패했을 때 어느 단계까지 값이 맞았는지 파악하기 어렵다. 이런 경우 x64dbg로 각 연산 단계 직후 값을 메모리/레지스터에서 직접 읽어 손으로 계산한 역연산 결과와 한 단계씩 대조하는 것이 안전하다.

## 흔한 실수
- 이름이 같은 pwnable 카테고리의 다른 "ezmix" 문제 정보를 그대로 리버싱 워게임 문제에 적용해 완전히 다른 접근(힙/스택 공격)을 시도하는 것
- 연산 순서를 거꾸로 되짚을 때 XOR/ADD/시프트 각각의 정확한 역연산을 헷갈려 잘못된 입력을 계산하는 것
- Bronze 1이라고 방심해 연산이 하나뿐일 거라 예단하고 뒤에 이어지는 추가 연산을 놓치는 것

## 막혔을 때 다음 체크
- XOR류 역산이 헷갈리면 → REV-0199 XOR 반복 변환 역산
- 비교/검증 패턴 전반이 궁금하면 → REV-0196 strcmp 기반 Flag 검증 패턴, REV-0197 memcmp 기반 Flag 검증 패턴
- 이름이 비슷한 mix-compare와 어떤 차이가 있는지 궁금하면 → REV-1036 [Write-up] mix-compare

## 미니 예제
```python
# 여러 연산이 순서대로 적용된 경우의 역산 스크립트 예시(구조 일반화, 실제 상수 아님)
target = bytes.fromhex("...")
result = bytearray(target)
for i in range(len(result) - 1, -1, -1):
    result[i] ^= 0x5A         # XOR의 역연산은 같은 XOR
    result[i] = (result[i] - 3) & 0xFF  # ADD 3의 역연산은 SUB 3
print(bytes(result))
```
이 스크립트는 "여러 연산이 섞인(mix) 검증"이라는 이름에서 유추한 일반적 역산 방식을 보여주는 예시이며, 실제 "ezmix" 바이너리의 정확한 상수나 순서를 나타낸 것이 아니다.

## 관련 글
- REV-0199 — XOR 반복 변환 역산
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0197 — memcmp 기반 Flag 검증 패턴
- REV-1036 — [Write-up] mix-compare

## 출처/검증
- WebSearch로 "dreamhack ezmix writeup 리버싱"을 검색한 결과, 드림핵 CTF Season 7 Round #4(Div2)에 "ezmix"라는 이름의 pwnable 카테고리 문제가 존재함을 확인했으나 이것이 워게임의 리버싱 카테고리 "ezmix"(Bronze 1)와 동일 문제인지는 확인하지 못했다(2026-09-10 검증).
- 워게임 쪽 "ezmix"에 대한 공개 write-up은 검색 결과에서 발견되지 않았다.
- 본문의 연산 구조 추정은 문제명과 카테고리(리버싱)에서 착안한 가설이며 실제 바이너리 분석 결과가 아니다.
