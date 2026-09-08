---
id: REV-0006
title: "Flag 검증 함수 찾는 가장 흔한 경로"
slug: "rev-0006-finding-check-function"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: [검증 함수 찾기, flag 체크 함수, strcmp 위치 찾기, check 함수 찾는 법, 입력 비교 로직 찾기]
aliases: ["체크 함수 어디", "검증 로직 어디", "비교하는 곳 어디", "flag 확인하는 함수"]
symptom_keywords: ["검증 함수를 못 찾겠음", "어디서 비교하는지 모르겠음", "flag 체크하는 코드를 못 찾음", "함수가 너무 많아서 뭐가 검증 함수인지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
검증 함수는 거의 항상 **"성공/실패 문자열 xref" 또는 "strcmp/memcmp 계열 함수 xref" 또는 "입력 함수(scanf 등) 바로 다음 코드"** 세 갈래 중 하나로 도달하며, 이 세 갈래를 순서대로 시도하면 대부분의 크랙미에서 몇 분 안에 찾을 수 있다.

## 언제 검색해야 하나
- `main` 함수는 찾았는데, 실제로 입력을 검증하는 코드가 어디 있는지 못 찾을 때
- 함수가 수십~수백 개라서 어디부터 봐야 할지 모를 때
- `main` 안에 함수 호출이 여러 개 있는데 어떤 게 검증 로직인지 구분이 안 될 때

## 핵심 개념
CTF 크랙미의 절대다수는 구조가 비슷하다: **입력을 받는다 → (선택적으로 변형한다) → 정답과 비교한다 → 결과를 출력한다.** 이 중 "정답과 비교한다"에 해당하는 부분이 검증 함수(check function)다. 검증 함수를 찾는 문제는 결국 "코드를 처음부터 끝까지 읽지 않고 지름길로 그 지점에 도달하는 법"의 문제다.

지름길은 세 가지가 있고, 이 순서로 시도하는 게 성공률이 높다.

1. **결과 문자열에서 거꾸로 찾기**: "Correct!", "Wrong flag", "Access granted" 같은 문자열은 반드시 어떤 조건문의 두 갈래(참/거짓) 중 한쪽에서 출력된다. 그 문자열을 참조하는 코드 위치를 찾으면, 그 바로 위에 `if` 조건이 있고, 그 조건이 검증 함수 호출이거나 검증 로직 자체다.
2. **비교 함수 자체에서 찾기**: `strcmp`, `memcmp`, `strncmp` 같은 라이브러리 함수는 문자열/버퍼 비교에 쓰인다. 이 함수들을 호출하는 곳을 찾으면 바로 그 근처가 검증 로직이다. C++에서 `==` 연산자로 직접 비교하는 경우 어셈블리 레벨에서는 `cmp` 명령어가 반복되는 패턴으로 보인다.
3. **입력 함수 바로 다음을 순방향으로 추적**: `scanf`, `gets`, `fgets`, `read` 같은 함수로 입력을 받은 직후의 코드를 순서대로 따라간다. 이 방법은 앞의 두 가지가 실패했을 때(문자열이 암호화되어 있거나, strcmp를 안 쓰고 직접 바이트 비교 루프를 짠 경우)의 대안이다.

## 화면/코드에서 보이는 징후
- IDA Functions 창에 `sub_401500` 같은 이름 모를 함수가 `main`에서 호출되고, 그 리턴값이 바로 `if`문에 쓰인다 — 검증 함수일 확률이 높다.
- 디컴파일 코드에 `strcmp(input, "some_string")` 또는 `strcmp(v1, v2)`가 보인다 — 바로 그 자리가 검증 지점이다(단, 진짜 정답이 `"some_string"`처럼 평문으로 보이는 경우는 드물고, 대부분 변형된 값과 비교한다).
- `for`/`while` 반복문 안에서 배열 원소를 하나씩 비교하며 다르면 바로 실패 처리하는 패턴 — strcmp를 직접 구현한 형태다.

## 가장 먼저 할 것
IDA/Ghidra에서 **Shift+F12(Strings 창)** 를 열고 "Correct", "Wrong", "Success", "Fail", "flag", "정답", "틀렸습니다" 같은 단어를 검색한다(Ctrl+F로 문자열 창 안에서 검색). 문자열이 하나라도 나오면 그게 가장 빠른 길이다.

## 단계별 절차

**경로 A: 결과 문자열에서 역추적**

1. Shift+F12로 Strings 창을 열고 결과 메시지로 보이는 문자열을 찾는다.
2. 그 문자열을 더블클릭해서 `.rdata`/`.rodata`의 실제 위치로 이동한다.
3. **X** 키(Cross-references, xref)를 눌러 "이 문자열을 사용하는 코드 위치" 목록을 본다.
4. 목록에서 함수로 이동하면, 보통 그 주변에 `if (result == 0) { puts("Correct!"); } else { puts("Wrong!"); }` 형태의 분기가 보인다.
5. `result`가 어디서 계산됐는지 위로 거슬러 올라가면 검증 함수 호출(`result = check(input);`)이 나온다. 이게 진짜 검증 함수다.

이 방식이 [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md)에서 더 자세히 다루는 내용이다.

**경로 B: 비교 함수에서 역추적**

1. IDA Imports 탭(View → Open subviews → Imports) 또는 Ghidra Symbol Tree → Imports에서 `strcmp`, `strncmp`, `memcmp`를 찾는다.
2. 함수를 더블클릭 → **X**(xref)로 이 함수를 호출하는 위치들을 본다.
3. 호출 지점이 여러 개면, 그중 `main` 근처이거나 입력 변수(`scanf`로 받은 버퍼)를 인자로 쓰는 곳을 우선 확인한다.
4. `memcmp(input, key, 16)`처럼 길이가 고정된 비교가 보이면, `key` 버퍼(정답 후보)의 실제 값을 IDA에서 확인한다(변수를 클릭 → 데이터 정의 위치로 이동).

**경로 C: 입력 함수부터 순방향 추적**

경로 A, B가 둘 다 실패하면(문자열이 암호화되어 있거나, 자체 비교 로직을 짠 경우) 입력을 받는 지점부터 순서대로 코드를 읽는다. 이 방법은 [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)에서 자세히 다룬다. 요약하면:

1. Imports에서 `scanf`, `gets`, `fgets`, `read`, `cin` 관련 함수를 찾는다.
2. 그 호출 직후부터 F5 디컴파일 코드를 위에서 아래로 읽으며, 입력 변수가 어떤 함수에 전달되는지 따라간다.
3. 반복문이나 함수 호출이 나오면 그 안으로 들어가서(더블클릭) 무엇을 하는지 확인한다 — 대부분 몇 단계 안에 비교 로직에 도달한다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열), `Ctrl+F`(문자열 창 내 검색), `X`(xref), `F5`(디컴파일), `Ctrl+P`(함수 목록)
- Ghidra: `Window → Defined Strings`, 문자열 더블클릭 후 `Show References To`(단축키 없으면 우클릭 메뉴)
- 커맨드라인으로 미리 후보 좁히기(Linux): `objdump -d ./chall | grep -B5 "call.*strcmp"`

## 출력 해석
- xref 목록에 함수가 하나만 뜨면 바로 그 함수가 답이다.
- xref 목록에 여러 함수가 뜨면(예: 로깅 함수, 도움말 출력 함수 등에서도 비슷한 문자열을 씀) `main`에서 가장 가깝게 호출되는 것을 우선한다.
- `strcmp` 리턴값은 두 문자열이 같으면 0이다. 디컴파일 코드에서 `if (strcmp(...) == 0)`이 "같을 때" 분기, `if (strcmp(...))` 단독이면 "다를 때" 분기라는 걸 헷갈리지 않아야 한다.

## 흔한 실수
- xref 결과가 여러 개 나왔을 때 첫 번째 것만 보고 그게 검증 함수라고 단정하는 것 — 도움말/사용법 출력 함수일 수도 있다.
- `strcmp`의 인자 순서를 착각해서 어떤 게 사용자 입력이고 어떤 게 정답 후보인지 헷갈리는 것.
- 검증 로직이 함수로 분리되어 있지 않고 `main` 안에 인라인되어 있는 경우를 예상 못 하고 "검증 함수"라는 별도 함수만 찾으려는 것 — 컴파일러 최적화로 작은 함수는 인라인될 수 있다.
- 정답 문자열이 그대로 보인다고 바로 입력해보는 것 — XOR/인코딩된 값과 비교하는 경우가 많아 실제 정답이 아닐 수 있다.

## 막혔을 때 다음 체크
- 문자열이 하나도 안 보인다 → [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md)의 "문자열이 암호화된 경우" 참고, 또는 [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)로 전환
- `main` 자체를 못 찾았다 → [rev-0009-finding-main.md](./rev-0009-finding-main.md)
- 디컴파일이 이해가 안 된다 → [rev-0011-when-to-trust-asm.md](./rev-0011-when-to-trust-asm.md)
- 5분째 못 찾았다 → [rev-0015-five-minute-checklist.md](./rev-0015-five-minute-checklist.md)

## 미니 예제
```c
// main 안에서
int result = check_flag(input);
if (result == 1)
    puts("Correct!");
else
    puts("Wrong!");
```
`"Correct!"` 문자열을 xref로 찾아서 도착한 지점이 위 코드라면, `result`가 어디서 왔는지 보면 `check_flag(input)`라는 함수 호출이 바로 보인다. `check_flag`를 더블클릭해서 들어가면 그게 진짜 검증 함수다. `check_flag` 내부에서 다시 `strcmp`나 반복문이 있다면, 그 안으로 한 단계 더 들어가서 실제 비교 대상을 찾는다.

## 관련 글
- [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)
- [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md)
- [rev-0009-finding-main.md](./rev-0009-finding-main.md)
- [../assembly/rev-0071-call.md](../assembly/rev-0071-call.md)
- [rev-0013-record-constants-first.md](./rev-0013-record-constants-first.md)

## 출처/검증
- `strcmp`/`memcmp` 동작: POSIX/ISO C 표준 라이브러리 명세 기준 (2026-09-08 검증).
- IDA/Ghidra xref 기능: 각 공식 문서 기준.
