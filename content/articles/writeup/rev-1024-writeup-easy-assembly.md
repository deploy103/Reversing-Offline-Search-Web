---
id: REV-1024
title: "[Write-up] Easy Assembly"
slug: "rev-1024-writeup-easy-assembly"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["dreamhack Easy Assembly", "드림핵 Easy Assembly", "check_password 리버싱", "XOR 인덱스 검증"]
aliases: ["Easy Assembly 풀이", "이지 어셈블리", "dreamhack easy assembly flag"]
symptom_keywords: ["Easy Assembly에서 XOR 복호화했는데 이상한 문자가 나옴", "복호화한 값을 base64로 다시 인코딩해야 하는 문제"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`start()`가 조건을 확인한 뒤 `check_password()`를 호출해 암호화된 플래그(`enc_flag`)를 길이와 인덱스를 이용한 XOR 연산으로 검증하는 문제인데, XOR을 풀어서 나온 바이트를 그대로 플래그로 제출하면 틀리고 그 결과를 다시 base64로 인코딩해야 최종 플래그 형식이 완성되는 함정이 포함되어 있다.

## 언제 검색해야 하나
- Easy Assembly를 열었는데 `check_password` 안에서 `enc_flag[i] ^ len` 또는 `enc_flag[i] ^ i` 같은 연산이 반복되는 루프가 보일 때
- XOR을 풀어서 나온 바이트를 그대로 제출했는데 `DH{...}` 형태가 되지 않고 이상한 바이너리처럼 보일 때
- "Easy"라는 이름을 보고 단순 XOR만 풀면 끝일 거라 생각했는데 뭔가 한 단계가 더 있는 것 같을 때

## 핵심 개념

### 길이(length)와 인덱스(index)를 함께 쓰는 XOR 검증
`check_password`는 암호화된 플래그 데이터를 받아, 각 바이트를 입력 데이터의 전체 길이 값과 XOR하고, 다시 그 결과를 현재 반복 인덱스(0, 1, 2, ...)와 XOR하는 이중 XOR 구조로 되어 있는 것으로 분석되었다. 이런 구조는 단순히 "고정 키 하나로 XOR"하는 것보다 한 단계 더 있지만, XOR이 자기 역원 연산이라는 성질(REV-0057)은 그대로 적용된다. 길이 값과 인덱스 값을 정확히 알고 있다면 암호화 때와 똑같은 연산을 암호문에 다시 적용하는 것만으로 원문을 복원할 수 있다.

### "복호화 결과를 다시 인코딩해야 한다"는 함정
이 문제의 특이한 점은, XOR을 풀어서 나온 바이트열이 사람이 읽을 수 있는 `DH{...}` 플래그 문자열이 아니라는 것이다. 대신 그 결과를 base64로 인코딩해야 최종적으로 제출 가능한 플래그 문자열 형태가 완성된다. 즉 base64로 인코딩된 데이터를 "디코드해야 한다"는 일반적인 직관과 반대로, 이 문제는 XOR을 푼 결과를 오히려 "인코드"해야 하는 역방향 함정을 갖고 있다. 브론즈 티어에서 흔히 볼 수 있는 이런 방향성 함정은, 중간 결과가 사람이 읽을 수 있는 문자열이 아니어도 당황하지 말고 "이 데이터에 한 단계 더 인코딩/디코딩이 필요한가"를 항상 의심해야 한다는 교훈을 준다(REV-0212 참고).

## 화면/코드에서 보이는 징후
- `start()` 또는 `main()`에서 특정 조건(인자 개수, 파일 존재 등)을 확인한 뒤 `check_password(enc_flag, len)` 계열 함수를 호출
- `check_password` 내부에 `result[i] = enc_flag[i] ^ len ^ i` 형태의 루프
- XOR을 풀어서 얻은 바이트열을 출력해보면 `DH{`로 시작하지 않고 알아볼 수 없는 바이너리처럼 보임

## 가장 먼저 할 것
IDA로 `check_password`(또는 유사한 이름의 검증 함수)를 디컴파일해 XOR에 사용되는 두 값(길이, 인덱스)이 정확히 무엇인지 확인한다. 이 두 값의 정확한 정의(길이가 암호문 전체 길이인지 평문 길이인지, 인덱스가 0부터 시작하는지 1부터인지)를 확정하기 전에는 복호화 스크립트를 작성하지 않는다.

## 단계별 절차
1. IDA로 `start()`/`main()`을 확인해 `check_password`에 어떤 데이터(`enc_flag`)와 길이 값이 전달되는지 확인한다.
2. `check_password` 내부 루프를 분석해 XOR 연산의 정확한 순서(길이/인덱스는 XOR 교환법칙상 순서가 상관없지만, 인덱스가 0-based인지 1-based인지는 결과에 영향을 준다)를 확인한다.
3. `enc_flag` 배열의 실제 바이트 값을 IDA의 Hex View 또는 `.rodata` 덤프로 추출한다.
4. Python으로 같은 XOR 연산을 재현해 복호화를 시도한다.
5. 복호화 결과가 `DH{...}`로 바로 보이지 않으면, 그 결과를 base64로 인코딩해 본다.
6. base64 인코딩 결과가 `DH{...}` 형식이 되는지 확인하고 최종 플래그로 제출한다.

## 명령어/단축키
```python
import base64
enc_flag = bytes([...])  # IDA에서 추출한 바이트열
length = len(enc_flag)
decoded = bytes(b ^ length ^ i for i, b in enumerate(enc_flag))
flag_candidate = base64.b64encode(decoded)
print(flag_candidate)
```
IDA: `.rodata`에서 `enc_flag` 배열 우클릭 → Array로 변환 후 Hex View에서 바이트 복사.

## 출력 해석
XOR만 풀었을 때 결과가 사람이 읽을 수 없는 바이트라면, 그 결과를 최종 답이 아니라 "다음 단계에 넣을 입력"으로 취급해야 한다는 신호다. base64로 인코딩한 결과가 `DH{`로 시작하고 `}`로 끝나는 출력 가능한 ASCII 문자열이 되면 올바른 방향으로 온 것이다.

## 흔한 실수
- XOR 결과가 이상하게 나오면 "복호화 로직이 틀렸다"고 단정하고 XOR 연산 순서만 계속 바꿔보는 것 — 실제로는 XOR은 맞고 그 뒤에 인코딩 단계가 하나 더 필요한 경우일 수 있다.
- 인덱스를 0부터 시작하는지 1부터 시작하는지 확인하지 않고 임의로 가정하는 것.
- base64 결과를 다시 디코드하려고 시도하는 것 — 이 문제는 인코드가 정답 방향이다.

## 막혔을 때 다음 체크
- XOR 연산 자체가 헷갈리면 REV-0057 XOR: XOR 연산과 XOR reg reg 제로화를 본다.
- base64 인코딩/디코딩 결과가 어떻게 생겨야 정상인지 헷갈리면 REV-0212 Base64 인코딩 검증 패턴을 본다.
- 비슷하게 XOR 키/인덱스 기반 검증이 궁금하면 REV-1017 [Write-up] r-xor-t를 같이 참고한다.

## 미니 예제
```python
enc_flag = [0x1a, 0x2f, 0x33]  # 예시 값, 실제 값이 아님
length = len(enc_flag)
decoded = bytes(b ^ length ^ i for i, b in enumerate(enc_flag))
print(decoded)                    # 사람이 못 읽는 바이트일 수 있음
import base64
print(base64.b64encode(decoded))  # 이 결과가 DH{...} 형태가 되어야 함
```

## 관련 글
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0212 — Base64 인코딩 검증 패턴
- REV-1017 — [Write-up] r-xor-t

## 출처/검증
- 드림핵 워게임 Easy Assembly의 카테고리(reversing)·티어(Bronze 4)·풀이자 수(651명)는 dreamhack.io/wargame/challenges?tag=reversing 페이지 직접 조회로 확인됨(2026-09-10).
- `check_password`가 길이와 인덱스를 이용한 이중 XOR로 `enc_flag`를 검증하고, 복호화 결과를 base64로 인코딩해야 최종 플래그가 된다는 흐름은 medium.com/@denny00826 의 "[DREAMHACK] Easy Assembly" 글을 참고해 새 문장과 새 예시 값으로 재구성했다. 원문의 정확한 주소나 실제 enc_flag 바이트 값을 그대로 옮기지 않았다.
- 이 바이너리의 정확한 OS/아키텍처는 참고한 글에서 명시적으로 확인되지 않아, 프로젝트 기본 규칙에 따라 Windows PE x64로 표기했다. 실제로는 다른 드림핵 리버싱 브론즈 문제들처럼 Linux ELF일 가능성도 있으므로, 실제 파일을 받으면 `file` 명령으로 먼저 재확인해야 한다.
