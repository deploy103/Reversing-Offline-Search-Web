---
id: REV-1030
title: "[Write-up] My Favorite Fruit"
slug: "rev-1030-writeup-my-favorite-fruit"
category: "writeup"
difficulty: "basic"
platform: [linux]
architecture: [x86]
format: [ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["dreamhack My Favorite Fruit", "드림핵 My Favorite Fruit", "PIE stripped 크랙미", "jnz jz 런타임 패치"]
aliases: ["My Favorite Fruit 못풀겠음", "마이 페이보릿 프루트 풀이", "과일 챗봇 리버싱"]
symptom_keywords: ["드림핵 My Favorite Fruit 어떻게 풀어야 할지 모르겠음", "strawberry만 입력하면 실패함", "if-else 과일 조건 리버싱"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
"My Favorite Fruit"는 챗봇처럼 좋아하는 과일 이름을 입력받는 PIE+stripped 바이너리로, `banana`/`mandarin`/`melon`/`erwin` 등은 정상적으로 통과하는데 `strawberry`만 실패하도록 설계되어 있어, 정적으로 분기 조건을 고치는 대신 디버거로 실행 중 조건 분기(`jnz`)를 패치해 강제로 성공 경로로 보내는 방식이 핵심이다.

## 언제 검색해야 하나
- 드림핵 "My Favorite Fruit"를 열었는데 PIE(위치 독립 실행 파일)이고 strip되어 있어서 IDA/Ghidra에서 함수 이름이 하나도 안 보일 때
- 여러 과일 이름 중 몇 개는 성공 문구가 나오는데 특정 과일(예: strawberry)만 계속 실패해서 원인을 모를 때
- 정적으로 값을 바꿀 수 없는 상황에서 x64dbg/GDB로 조건 분기 자체를 패치하는 방법이 필요할 때

## 핵심 개념
이 문제는 참고한 영문 write-up(Talal Ali Khan, Medium)에 따르면 사용자가 좋아하는 과일 이름을 입력하면 그에 맞는 반응을 보여주는 간단한 챗봇 형태의 프로그램이다. 바이너리는 PIE로 빌드되어 있어 실행할 때마다 로드 주소가 달라지고, strip되어 있어 함수 이름이 남아있지 않다. 그런데도 소스 로직 자체는 단순한 `if`/`else if` 연속 비교로 구성되어 있어, 디컴파일 결과를 읽는 것 자체는 어렵지 않다.

핵심 함수(참고 write-up에서 `sub_11E9`로 표시된 함수)는 여러 과일 이름을 인자로 받아 어떤 산술 연산을 수행한 뒤 결과를 반환하며, 이 반환값이 각 `if` 분기의 조건으로 쓰인다. `banana`, `mandarin`, `melon`, `erwin` 등을 입력하면 해당 분기 조건이 참이 되어 성공 문구가 나오지만, `strawberry`를 입력하면 이 함수의 결과값이 기대한 조건을 만족시키지 못해 분기 조건이 거짓으로 평가되고, 그 다음 분기(예: erwin 처리 블록)로 흘러가 버린다.

이런 상황에서 취할 수 있는 접근은 두 가지다.
1. `sub_11E9` 함수의 연산 로직을 완전히 분석해 `strawberry`가 왜 조건을 만족하지 못하는지 원인을 찾고, 함수가 기대하는 진짜 입력값을 역산한다.
2. 원인 분석 없이도, 문제가 되는 조건 분기(`jnz`/`jz`) 명령 자체를 디버거로 실행 중에 패치해서 강제로 성공 경로로 진입시킨다.

참고한 write-up은 2번 방식을 택했다. `strawberry`를 입력해 실행한 뒤, 문제의 조건 분기 명령에 브레이크포인트를 걸고, 그 지점에서 `jnz`를 `jz`로(또는 반대로) 바꿔 흐름을 성공 쪽으로 강제로 돌렸다. 이때 중요한 점은 **패치를 미리 정적으로 파일에 해두면 안 된다**는 것이다. PIE 바이너리에서 이 조건은 다른 과일 입력(예: erwin)에서는 정상적으로 다른 목적으로 쓰이기 때문에, 파일 자체를 고정적으로 고치면 다른 입력 경로가 깨진다. 그래서 "이번 실행에서, strawberry를 입력했을 때, 이 지점을 지나가는 순간에만" 패치해야 하며, 이는 정적 패치가 아니라 런타임 중 메모리 패치로만 가능하다.

## 화면/코드에서 보이는 징후
- `checksec`/Detect It Easy 등에서 `PIE: enabled`, `Stripped: yes`로 표시됨
- IDA Functions 창에 `sub_401XXX` 같은 이름 없는 함수만 나열됨
- 디컴파일 결과에 `if (strcmp(input, "banana") == 0) ... else if (...) ...` 형태의 연쇄 조건문이 보이고, 마지막에 어떤 함수의 반환값을 조건으로 쓰는 분기가 있음
- `strawberry`를 입력했을 때만 예상과 다른 분기(예: erwin 처리 블록)로 빠짐

## 가장 먼저 할 것
바이너리를 실행해서 여러 과일 이름을 하나씩 입력해보고, 어떤 입력이 성공/실패하는지 표로 정리한다. 그다음 IDA/Ghidra로 열어 `strcmp` 계열 호출을 xref로 따라가며 각 과일 이름 비교가 어느 조건 분기에 연결되는지 확인한다. 실패하는 입력(`strawberry`)이 어느 분기에서 갈라지는지 정확한 주소를 알아내는 것이 최우선이다.

## 단계별 절차
1. 바이너리를 실행하고 여러 과일 이름을 입력해 성공/실패 패턴을 확인한다.
2. IDA/Ghidra로 열어 `main`(또는 stripped라면 진입점부터) 근처의 `strcmp`/문자열 비교 연쇄를 찾는다.
3. `strawberry` 관련 비교 이후 호출되는 함수(참고 write-up 기준 `sub_11E9`)와 그 반환값을 조건으로 쓰는 분기 명령의 정확한 주소를 기록한다.
4. GDB 또는 x64dbg로 그 바이너리를 실행하되, PIE이므로 절대주소 대신 **베이스 주소 + 오프셋**으로 브레이크포인트를 건다.
5. `strawberry`를 입력해 그 브레이크포인트까지 도달시킨다.
6. 분기 직전 조건(플래그 레지스터, 비교 결과)을 확인하고, 조건 분기 명령(`jnz`)의 바이트를 그 자리에서 반대 조건(`jz`)으로 패치하거나, NOP으로 바꿔 무조건 성공 경로로 진입하게 만든다.
7. 패치 후 실행을 이어가 성공 문구가 출력되는지 확인한다.

## 명령어/단축키
```text
GDB(PIE 베이스 확인): 
  (gdb) start
  (gdb) info proc mappings   # 베이스 주소 확인
  (gdb) break *(베이스주소+오프셋)

x64dbg:
  조건 분기 명령에서 우클릭 → Binary → Edit
  또는 명령어 위에서 스페이스바로 어셈블 대체 입력(jnz → jz)
  F9(Run)으로 계속 실행
```
참고 write-up에서는 `jnz`를 `jz`로 패치하는 방식이 성공했고, `eax` 값을 0으로 바꿔 조건을 우회하려는 시도는 실패했다고 밝히고 있다 — 즉 조건 자체(분기 명령)를 바꾸는 것이 값 자체를 바꾸는 것보다 더 확실한 방법이었다는 뜻이다.

## 출력 해석
패치 후에도 실패 문구가 그대로 나온다면, 패치를 건 시점이 틀렸거나(너무 일찍 패치해서 다른 분기 로직에 영향을 준 경우) PIE 베이스 계산이 잘못되어 엉뚱한 주소를 패치한 경우일 수 있다. 반드시 실행 중(런타임)에, 정확한 순간에 패치했는지 다시 확인해야 한다.

## 흔한 실수
- PIE 바이너리인 것을 무시하고 IDA에서 본 정적 주소를 그대로 디버거에 입력해 브레이크포인트를 거는 것 — REV-0194에서 다루는 대로 반드시 로드 베이스를 더해야 한다.
- 패치를 파일에 영구적으로 저장해버리는 것 — 이 문제는 특정 입력(strawberry)에서만 우회가 필요하므로, 파일을 영구 패치하면 다른 과일 입력의 정상 동작이 깨질 수 있다. 런타임 메모리 패치로만 처리해야 한다.
- 조건 분기 대신 반환값(`eax`)을 강제로 바꾸려다 실패하는 것 — 참고 write-up에서도 이 방법은 통하지 않았다고 명시했다. 조건 분기 명령 자체를 바꾸는 편이 더 직접적이다.
- strip된 바이너리라고 분석을 포기하는 것 — 함수 이름이 없어도 문자열 xref와 호출 순서만으로 충분히 구조를 파악할 수 있다.

## 막혔을 때 다음 체크
- PIE 바이너리에서 브레이크포인트를 정확히 거는 방법이 헷갈리면 → REV-0194 PIE 바이너리 GDB 브레이크포인트 잡기
- x64dbg로 런타임에 바이트를 패치하는 구체적인 절차가 필요하면 → REV-0184 x64dbg CTF용 간단 패치와 저장
- 심볼이 없는 stripped 바이너리를 다루는 기본기가 부족하면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이
- 메모리 패치를 했는데 반영이 안 되는 것처럼 보이면 → REV-0844 메모리 값을 패치했는데 반영이 안 될 때

## 미니 예제
디컴파일 결과를 단순화하면 다음과 같은 구조로 추정된다(참고한 write-up 기준으로 재구성한 예시이며 실제 정확한 어셈블리 바이트는 아니다).
```c
if (!strcmp(input, "banana"))      goto success_banana;
else if (!strcmp(input, "strawberry")) {
    int r = sub_11E9(input);       // 특정 산술 연산
    if (r == EXPECTED)             // strawberry는 이 조건을 만족하지 못함
        goto success_strawberry;
    // 조건 실패 -> 다음 분기(erwin 처리 등)로 흘러감
}
else if (!strcmp(input, "erwin"))  goto success_erwin;
```
여기서 `if (r == EXPECTED)`에 대응하는 어셈블리의 `jnz`(조건 불일치 시 실패 경로로 분기)를 런타임에 `jz`로 바꾸면, `r`이 무엇이든 상관없이 `success_strawberry`로 진입하게 된다.

## 관련 글
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0184 — x64dbg CTF용 간단 패치와 저장
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0844 — 메모리 값을 패치했는데 반영이 안 될 때

## 출처/검증
- 문제 형태(과일 이름을 입력받는 챗봇형 프로그램, PIE + stripped), `strawberry`만 실패하는 현상, `sub_11E9` 함수와 조건 분기, `jnz`→`jz` 런타임 패치로 우회한 절차, `eax` 값 변경 시도는 실패했다는 내용: Talal Ali Khan, "Reverse Engineering CTF writeup: My Favorite Fruit — DreamHack"(Medium, 2025-10-04) 요약·재서술, WebSearch 및 WebFetch로 본문 확인(2026-09-10 검증). 원문 문장을 그대로 인용하지 않고 절차를 새로 서술했다.
- PIE 바이너리에서 디버거 브레이크포인트를 걸 때 베이스 주소를 더해야 한다는 일반 원칙: GDB/x64dbg 공식 문서 및 리버싱 일반 지식 기준.
