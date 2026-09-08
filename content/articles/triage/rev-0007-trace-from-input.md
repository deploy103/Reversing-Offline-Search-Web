---
id: REV-0007
title: "입력 함수부터 역추적하는 방법"
slug: "rev-0007-trace-from-input"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: [scanf 추적, 입력 변수 추적, gets 추적, 입력값 따라가기, 변수 흐름 추적, use-list]
aliases: ["입력받는 곳부터 추적", "scanf 다음부터 읽기", "입력값이 어디로 가는지 추적"]
symptom_keywords: ["입력값이 어디로 가는지 모르겠음", "scanf 다음에 뭘 봐야 할지 모르겠음", "변수가 어디서 쓰이는지 못 찾겠음", "문자열도 없고 strcmp도 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
결과 문자열도, `strcmp`도 못 찾겠으면 **입력을 받는 함수(scanf/gets/read/cin) 호출 직후로 가서, 입력이 저장된 변수를 IDA의 xref 또는 Ghidra의 "Uses" 기능으로 순방향 추적**하면 검증 로직에 도달한다.

## 언제 검색해야 하나
- [rev-0006-finding-check-function.md](./rev-0006-finding-check-function.md)의 문자열/strcmp 경로가 둘 다 막혔을 때(문자열이 암호화됐거나, strcmp 대신 자체 비교 루프를 쓴 경우)
- 입력을 어디서 받는지는 알겠는데 그 값이 이후에 어떻게 쓰이는지 놓치고 있을 때
- 함수가 너무 많아서 위에서 아래로 읽는 것 말고는 방법이 없어 보일 때

## 핵심 개념
문자열 xref나 strcmp xref로 검증 로직을 바로 찾는 게 이상적이지만, 다음과 같은 경우엔 그 방법이 안 먹힌다.
- 결과 메시지가 서버로 전송되거나 화면에 그래픽으로 그려져서 "문자열 상수"가 아예 없는 경우.
- 정답 비교를 `strcmp` 같은 라이브러리 함수 없이 `for` 루프 + `if (a[i] != b[i])`로 직접 짠 경우(디스어셈블리에는 반복되는 `cmp`/`jne` 패턴만 보임).
- 문자열이 XOR나 다른 방식으로 암호화되어 있어서 IDA Strings 창에 안 잡히는 경우.

이럴 때 유일하게 확실한 길은 **데이터 흐름을 순방향으로 추적**하는 것이다: "사용자가 입력한 값이 저장되는 변수/버퍼"를 기준으로, 그 변수가 다음에 어디서 읽히는지(read)를 계속 따라가면, 결국 그 값을 가지고 뭔가 판단하는 지점(비교, 분기)에 도달할 수밖에 없다 — 입력을 아예 안 쓰는 프로그램이 아닌 이상 반드시 어딘가에서 쓰인다.

이 방법은 시간이 조금 더 걸리지만 **가장 확실하다**. 문자열이나 strcmp에 의존하지 않기 때문에 난독화된 문제에서도 통한다.

## 화면/코드에서 보이는 징후
- `scanf("%d", &v1);` 또는 `scanf("%s", buf);` 뒤에 바로 결과 출력이 없고, 여러 함수 호출이 이어진다.
- 입력 버퍼(`buf`, `input`, `s1` 같은 이름 또는 `[rsp+20h]` 같은 스택 오프셋)가 다음 함수의 인자로 그대로 전달된다.
- 반복문 안에서 입력 버퍼의 각 바이트에 접근하는 인덱스 연산(`buf[i]`, `*(input + i)`)이 보인다.

## 가장 먼저 할 것
IDA Imports 탭에서 `scanf`(Windows는 `scanf`/`scanf_s`, Linux는 `__isoc99_scanf`로 표시될 수 있다) 또는 `gets`, `fgets`, `read`를 찾고, **X**(xref)로 호출 위치로 이동한다. 여러 곳에서 호출되면 `main` 근처, 또는 프로그램 시작 직후 위치를 우선한다.

## 단계별 절차

**1) 입력 함수 호출 지점 찾기**
- IDA Imports 탭 → `scanf` 계열 더블클릭 → `X`로 xref → 호출 위치로 이동.
- 없으면 Ctrl+P 함수 목록에서 `main`을 열고 위에서부터 훑으며 입력 관련 함수 호출을 찾는다.

**2) 입력이 저장되는 변수 확인**
F5로 디컴파일했을 때 다음과 같은 형태가 보일 것이다.
```c
char input[64];
scanf("%s", input);
```
여기서 `input`이 우리가 추적할 변수다. IDA 디컴파일 창에서 `input`을 클릭하면 노란색/회색으로 이 변수가 쓰이는 다른 위치들이 하이라이트된다 — 이게 가장 빠른 1차 확인 방법이다.

**3) 변수를 순방향으로 따라가기**
디컴파일 창에서 하이라이트된 다음 사용처로 이동한다(코드를 아래로 스크롤하며 하이라이트된 줄을 찾거나, 어셈블리 뷰에서는 해당 스택 오프셋을 담은 레지스터의 다음 사용을 찾는다).
- `input`이 그대로 다른 함수의 인자로 들어가면(`check(input)`) → 그 함수로 더블클릭해서 들어간다.
- `input`이 반복문 안에서 한 바이트씩 처리되면(`input[i]`) → 그 반복문이 무엇을 계산하는지 읽는다(합계? XOR? 변환?).
- `input`이 전역 변수에 복사되면 → 그 전역 변수를 다시 같은 방식으로 추적한다(전역 변수를 더블클릭하면 Ghidra/IDA가 이 변수의 모든 참조 위치를 보여준다).

**4) 어셈블리 레벨에서 추적해야 할 때**
디컴파일이 변수를 제대로 못 잡아서(최적화, 포인터 연산) 소스 레벨 추적이 끊기면, 어셈블리로 내려가서 레지스터를 추적한다. 예를 들어 `lea rax, [rbp-40h]`로 입력 버퍼의 주소를 `rax`에 로드했다면, 그 이후 코드에서 `rax`(또는 `rax`가 복사된 다른 레지스터)가 어떻게 쓰이는지 한 줄씩 따라간다. IDA에서는 레지스터 이름을 더블클릭하면 다음/이전 사용처로 이동하는 데 도움이 되는 하이라이트가 켜진다.

**5) 도착 지점 확인**
몇 단계 함수 호출을 따라가다 보면 결국 비교 연산(`cmp`, `test`) 뒤에 조건 분기(`je`/`jne`)가 나오는 지점, 또는 반복문이 끝난 뒤 최종 결과를 판단하는 지점에 도달한다. 여기가 실질적인 검증 로직이다.

## 명령어/단축키
- IDA: 디컴파일 창에서 변수 클릭(같은 변수 하이라이트), `X`(xref), `Ctrl+X`(디컴파일 창에서도 xref 가능한 버전 존재), `N`(변수/함수 리네임으로 추적 표시)
- Ghidra: 디컴파일 창에서 변수 우클릭 → `References → Show References to Address`
- GDB(동적으로 확인하고 싶을 때): `watch *(char*)input_addr` — 이 메모리 주소를 누가 읽거나 쓰면 멈춘다(하드웨어 워치포인트, 정확히는 write watchpoint가 기본이며 read는 `rwatch` 사용)

## 출력 해석
- 변수 하이라이트에서 사용처가 딱 1~2곳뿐이면 추적이 쉽다. 사용처가 10곳 넘게 흩어져 있으면 전역 변수이거나 여러 함수에서 공유하는 버퍼일 가능성이 높다 — 이럴 때는 `main`에서 호출 순서대로 함수를 따라가는 게 더 명확할 수 있다.
- `watch` 워치포인트가 걸리면 GDB가 "이 주소를 방금 어떤 명령어가 건드렸다"는 걸 알려준다. `bt`(backtrace)로 어떤 함수 안에서 발생했는지 바로 확인 가능.

## 흔한 실수
- 변수 하나만 따라가다가 그 값이 복사되어 다른 이름의 변수로 바뀌는 순간을 놓치는 것 — 복사/캐스팅되면 새 변수 이름도 계속 추적해야 한다.
- 포인터와 포인터가 가리키는 값을 혼동하는 것 — `input`(주소)과 `*input`(그 주소의 내용)은 다르다.
- 전역 변수 추적 시 프로그램 어디서든(다른 함수에서도) 값이 바뀔 수 있다는 걸 잊고 한 함수 안에서만 찾는 것.
- 이 방법이 오래 걸린다고 중간에 포기하고 다시 문자열 검색으로 돌아갔다가 또 포기하는 식으로 왔다갔다만 하는 것 — 한 방법을 정하면 최소 몇 분은 진득하게 따라가 본다.

## 막혔을 때 다음 체크
- 그래도 검증 로직을 못 찾겠다 → [rev-0015-five-minute-checklist.md](./rev-0015-five-minute-checklist.md)
- 안티디버깅 때문에 동적으로 확인이 안 된다 → [rev-0005-static-vs-dynamic.md](./rev-0005-static-vs-dynamic.md)
- 디컴파일이 신뢰가 안 간다 → [rev-0011-when-to-trust-asm.md](./rev-0011-when-to-trust-asm.md)
- 찾은 로직을 기록/정리하는 법 → [rev-0014-reversing-notes.md](./rev-0014-reversing-notes.md)

## 미니 예제
```c
int main() {
    char input[32];
    scanf("%s", input);
    int r = transform(input);
    if (r == 0x1A2B)
        puts("Correct!");
    else
        puts("Wrong!");
}
```
1. `scanf` xref로 이 코드에 도착.
2. `input`을 클릭 → 다음 사용처가 `transform(input)` 호출임을 확인.
3. `transform`으로 더블클릭해서 들어감 → 내부에서 각 바이트를 XOR하고 합산하는 반복문을 발견.
4. 반복문을 다 읽고 나오면 리턴값 `r`이 `main`으로 돌아와 `0x1A2B`와 비교됨을 확인 — 이제 `transform` 로직을 역산하면 `input`의 조건을 구할 수 있다.

## 관련 글
- [rev-0006-finding-check-function.md](./rev-0006-finding-check-function.md)
- [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md)
- [rev-0013-record-constants-first.md](./rev-0013-record-constants-first.md)
- [rev-0017-recover-logic-before-solver.md](./rev-0017-recover-logic-before-solver.md)

## 출처/검증
- 데이터 흐름 추적(use-def chain) 개념: 컴파일러/정적분석 일반 이론(데이터 흐름 분석) 기준 서술 (2026-09-08 검증).
- IDA/Ghidra 변수 하이라이트·xref 기능: 각 공식 문서 기준.
