---
id: REV-1017
title: "[Write-up] r-xor-t"
slug: "rev-1017-writeup-r-xor-t"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["dreamhack r-xor-t", "드림핵 r-xor-t", "r-xor-t 리버싱", "r-xor-t flag"]
aliases: ["r-xor-t 못풀겠음", "dreamhack r-xor-t flag", "r-xor-t 풀이"]
symptom_keywords: ["드림핵 r-xor-t 어떻게 풀어야 할지 모르겠음", "r-xor-t 문제에서 xor 키를 못 찾겠음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
이름에서 곧바로 XOR 연산 기반 검증임을 알 수 있는 브론즈 3 티어 문제로, 실제 공개 write-up을 찾지 못해 이 글은 문제명과 드림핵 브론즈 티어의 통상적인 출제 패턴에서 추정한 "XOR 키/인덱스 기반 문자열 비교" 접근법을 절차 중심으로 정리한 것이며 구체적 정답은 담고 있지 않다.

## 언제 검색해야 하나
- 드림핵 워게임에서 r-xor-t를 열었는데 디컴파일 결과에 xor 연산자가 반복적으로 등장할 때
- 함수 이름 자체가 문제 제목처럼 xor/t 조합으로 되어 있어 "t"가 tmp, transform, table 중 무엇을 뜻하는지 감이 안 잡힐 때
- IDA에서 루프 안에 `^=` 형태의 연산과 배열 인덱스 증가가 같이 보이는데 어떤 값과 xor 되는지 헷갈릴 때

## 핵심 개념
XOR 기반 검증 문제는 대체로 두 갈래로 나뉜다. 첫째는 "고정 키 XOR" 패턴으로, 입력 문자열의 각 바이트를 고정된 한 개(또는 반복되는 짧은) 키 값과 XOR한 결과가 바이너리에 미리 박혀 있는 배열과 일치하는지 비교한다. 둘째는 "인덱스 XOR" 패턴으로, 키 대신 루프 인덱스(`i`) 자신을 XOR 값으로 사용하거나 인덱스에 어떤 연산을 가한 값을 사용한다. 문제명 r-xor-t는 "reverse xor test/table" 등 여러 해석이 가능하지만 공식 설명이나 상세 write-up을 확인하지 못했으므로 이름만으로 로직을 확정할 수는 없다. 다만 XOR은 `A ^ B = C`이면 `C ^ B = A`, `C ^ A = B`가 항상 성립하는 자기 역원(self-inverse) 연산이라는 성질(REV-0057)은 이 문제뿐 아니라 모든 XOR 기반 검증에 공통으로 적용되는 핵심 무기다. 검증 함수가 어떤 두 값을 XOR해서 세 번째 값과 비교한다면, 그중 두 값만 알아도 나머지 하나를 역산할 수 있다.

## 화면/코드에서 보이는 징후
- 디컴파일된 검증 함수 내부에 `v[i] = input[i] ^ key[i]` 또는 `v[i] = input[i] ^ i` 형태의 반복문이 보임
- 비교 대상이 되는 상수 배열이 `.rodata` 또는 전역 변수에 하드코딩되어 있음
- 함수 리턴값이 0/1(또는 true/false)로만 나오고 그 값을 기준으로 "Correct"/"Wrong" 문자열을 출력

## 가장 먼저 할 것
디스어셈블러(IDA)로 진입점부터 따라가 flag 입력을 받는 지점과 그 값을 넘겨받는 검증 함수를 먼저 특정한다. 검증 함수 안에서 XOR 연산 피연산자 두 개가 무엇인지(고정 키인지, 인덱스인지, 다른 입력 바이트인지) 정확히 구분하는 것이 최우선이다. 이 구분이 끝나기 전에는 절대 브루트포스나 무작위 대입을 시도하지 않는다.

## 단계별 절차
1. IDA/x64dbg로 실행 파일을 열고 문자열 참조(String Xref)로 "flag", "Wrong", "Correct" 등의 출력 문자열을 찾아 호출 지점을 역추적한다.
2. 검증 함수를 찾으면 루프 구조를 살펴 `^` 연산이 어떤 두 오퍼랜드 사이에서 일어나는지 확인한다.
3. 비교 대상 상수 배열의 주소와 크기를 특정하고, x64dbg/IDA에서 해당 메모리를 덤프한다.
4. XOR의 자기 역원 성질을 이용해 `상수 배열 ^ 키(또는 인덱스)` 연산을 파이썬으로 재현하여 원래 입력 문자열을 역산한다.
5. 역산한 문자열을 실제 바이너리에 입력해 "Correct" 계열 메시지가 나오는지 검증한다.

## 명령어/단축키
IDA: Strings 창(Shift+F12)에서 출력 문자열 검색 후 더블클릭 → Ctrl+X로 Xref 확인.
x64dbg: 검증 함수 시작 주소에 F2로 브레이크포인트 설정 후 F9 실행, 레지스터 창에서 XOR 연산 직후 값 확인.
Python 검증 스크립트: `bytes(a ^ b for a, b in zip(const_array, key_or_index_stream))` 형태로 역산.

## 출력 해석
비교 함수의 반환값이 0이면 실패, 0이 아니면(또는 정확히 특정 상수와 같으면) 성공으로 처리하는 경우가 흔하다. 반환값 자체보다 반환값을 만드는 비교 루프의 종료 조건(루프가 끝까지 돌았는지, 중간에 break 했는지)을 확인하는 것이 더 중요한 정보다.

## 흔한 실수
- 문제 이름만 보고 "XOR 키가 한 글자일 것"이라고 단정하는 것 — 인덱스 기반이거나 키가 여러 바이트일 수 있다.
- 비교 대상 상수 배열을 바이트가 아니라 문자열로 착각해 오프셋을 하나 놓치는 것.
- 상세 write-up 없이 추정한 로직을 그대로 정답이라 믿고 더 이상 바이너리를 확인하지 않는 것.

## 막혔을 때 다음 체크
- XOR 연산 자체의 비트 단위 동작과 예시가 헷갈리면 REV-0057 XOR 연산과 XOR reg reg 제로화를 먼저 복습한다.
- XOR 키 길이를 추정하는 일반적인 팁이 필요하면 REV-0878 흔한 XOR 키 길이 탐지 팁 참조를 본다.
- 무차별 대입이 실제로 가능한 입력 공간인지 계산이 필요하면 REV-0219 Brute Force가 가능한 입력 공간 계산을 확인한다.

## 미니 예제
```c
// 추정되는 일반적인 XOR 검증 로직 예시(실제 r-xor-t 코드가 아님)
int check(char *input, int len) {
    unsigned char expected[] = { 0x0a, 0x1f, 0x3c /* ... */ };
    for (int i = 0; i < len; i++) {
        if ((input[i] ^ i) != expected[i]) return 0;
    }
    return 1;
}
```
이런 구조라면 `input[i] = expected[i] ^ i`로 즉시 역산할 수 있다. r-xor-t가 실제로 이 구조인지는 검증되지 않았으므로 참고용 예시로만 사용한다.

## 관련 글
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0878 — 흔한 XOR 키 길이 탐지 팁 참조
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-1023 — [Write-up] secret message
- REV-1024 — [Write-up] Easy Assembly

## 출처/검증
- 드림핵 워게임 카테고리(reversing)와 r-xor-t의 티어(Bronze 3)·풀이자 수(903명)는 dreamhack.io/wargame/challenges?tag=reversing 페이지 직접 조회로 확인됨(2026-09-10).
- WebSearch로 "dreamhack r-xor-t writeup", "드림핵 r-xor-t 풀이" 등을 검색했으나 이 문제를 구체적으로 다루는 블로그 글이나 write-up을 찾지 못했다. 위 절차와 예시는 XOR 기반 검증 문제 일반론에서 추정한 것이며 r-xor-t의 실제 로직으로 확정된 내용이 아니다.
- XOR 연산의 자기 역원 성질은 불 대수(Boolean algebra)의 표준 성질로, 별도 출처 없이도 수학적으로 항상 성립한다.
