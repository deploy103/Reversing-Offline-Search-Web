---
id: REV-1099
title: "WASM에서 흔한 검증 로직 패턴 알아보기"
slug: "rev-1099-wasm-validation-patterns"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: ["WASM"]
format: ["WASM"]
tools: [wabt]
keywords: ["wasm 검증 로직", "wasm 패턴", "i32.eq", "wasm crackme", "wasm flag check"]
aliases: ["wasm 크랙미 패턴", "wasm에서 flag 검증 찾기", "wasm 비교 로직 읽는 법"]
symptom_keywords: ["wat 파일은 열었는데 어디가 검증 로직인지 모르겠음", "wasm 함수 이름이 다 익명임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
WASM crackme는 대부분 스택 기반 산술/논리 연산(`i32.add`, `i32.xor`, `i32.eq` 등)을 반복해 입력을 변형한 뒤 `i32.eq`/`i32.eqz`로 최종 비교하는 짧은 함수 하나에 로직이 몰려 있으므로, `wasm2wat`으로 뽑은 텍스트에서 이 비교 연산자와 루프 구조부터 찾는 것이 가장 빠르다.

## 언제 검색해야 하나
- REV-1098로 `.wasm`을 `.wat`/의사코드로 변환했지만 함수가 여러 개이거나 이름이 `$func12`처럼 익명이라 어디서 시작해야 할지 모를 때
- JS 코드에서 `instance.exports.check(input)`처럼 결과값(boolean/i32)을 비교해 "Correct!"/"Wrong!"을 출력하는 지점은 찾았는데 `check` 내부 로직이 안 읽힐 때
- WASM 함수 안에 `loop`, `br_if`가 반복되는데 이게 for문인지 while문인지 헷갈릴 때

## 핵심 개념

### 스택 기반 실행 모델부터 이해하기
WASM은 레지스터가 아니라 스택 기반 가상 머신이다. `local.get 0`은 지역변수(대개 함수 인자) 0번을 스택에 push하고, `i32.add`는 스택 맨 위 두 값을 pop해서 더한 뒤 다시 push한다. x86의 `ADD EAX, EBX`처럼 레지스터를 직접 다루는 것과 달리, WASM 코드를 읽을 때는 "지금 스택에 뭐가 쌓여 있는가"를 순서대로 추적해야 한다.

### 패턴 1 — 문자별 XOR/덧셈 후 비교(간단한 인코딩 크랙미)
가장 흔한 패턴은 입력 문자열을 한 바이트씩 순회하며 고정 키와 XOR하거나 더한 뒤, 그 결과를 하드코딩된 배열과 비교하는 것이다. `.wat`에서는 `loop` 블록 안에 `i32.load8_u`(메모리에서 1바이트 읽기), `i32.xor` 또는 `i32.add`, 그리고 `i32.ne`(다르면 분기)가 반복되는 형태로 나타난다.

```wat
(loop $L
  local.get $i
  i32.load8_u        ;; 입력 문자열의 i번째 바이트
  i32.const 0x13
  i32.xor            ;; 0x13과 XOR
  local.get $i
  i32.const 1000      ;; 정답 배열 오프셋
  i32.add
  i32.load8_u
  i32.ne
  br_if $fail        ;; 다르면 실패 분기
  ...
)
```

### 패턴 2 — 단일 산술식 검증(체크섬/수식형)
입력을 정수로 파싱한 뒤 몇 개의 산술 연산(곱셈, 시프트, 모듈러)을 적용하고 특정 상수와 `i32.eq`로 비교하는 패턴. 코드 자체는 매우 짧지만 역연산(모듈러 역원 등)을 손으로 풀어야 할 수도 있다.

### 패턴 3 — 상태 머신/각 자리마다 다른 조건
`br_table`(WASM의 switch-case에 해당)을 이용해 입력 위치나 상태값에 따라 다른 분기로 점프하는 패턴. `br_table`이 보이면 여러 상태를 오가는 상태 머신형 검증일 가능성이 높다.

### 최종 판정 지점 찾기
어떤 패턴이든 결국 함수의 반환값은 `i32`(0/1로 boolean 취급) 하나로 수렴하는 경우가 많다. `.wat` 텍스트에서 함수 맨 끝의 마지막 연산자가 `i32.eq`, `i32.eqz`, `i32.and`(여러 조건을 AND로 합산) 중 하나인지 먼저 확인하면, 그 직전 스택에 쌓인 두 값이 "계산된 결과"와 "기대값"임을 알 수 있다.

## 화면/코드에서 보이는 징후
- `.wat`에 `loop`, `br_if`, `block`이 중첩되어 있고 함수 하나가 유난히 길다
- 함수 결과 타입이 `(result i32)`이고 반환 직전 마지막 명령이 `i32.eq` 계열
- `data` 섹션에 정답과 비교할 것으로 보이는 고정 바이트 배열이 있음
- JS 코드에서 `if (instance.exports.check(...) === 1) { alert("Correct") }` 같은 대조 로직이 보임

## 가장 먼저 할 것
`.wat`에서 `(export ...)`된 함수들의 시그니처(`param`/`result`)부터 훑어, 문자열이나 배열을 받고 `i32`(참/거짓) 하나를 돌려주는 함수를 최우선 후보로 지목한다. 그 함수 안에서 `loop`와 마지막 비교 연산자를 먼저 표시해두고 위에서 아래로 스택 값을 손으로 따라간다.

## 단계별 절차
1. `wasm2wat`으로 변환한 `.wat`에서 export 함수 시그니처 확인
2. 후보 함수 안의 `loop`/`block`/`br_if`/`br_table` 개수와 중첩 구조 파악 — 몇 겹인지 스케치
3. 함수 안에서 사용되는 상수(`i32.const`)를 전부 나열 — 키값, 배열 오프셋, 목표값 후보
4. `data` 섹션에서 해당 오프셋에 있는 실제 바이트를 확인(정답 또는 룩업 테이블일 가능성)
5. 마지막 비교 연산자 직전까지 스택에 쌓이는 값을 손으로(혹은 파이썬으로) 재현
6. 정적으로 막히면 REV-1100의 브라우저 디버거로 실제 실행 중 스택/로컬 변수 값을 찍어 검증

## 명령어/단축키
```bash
# loop/br_if 개수만 빠르게 세기
grep -c "loop" chall.wat
grep -c "br_if" chall.wat

# data 섹션(정답 배열 후보) 확인
wasm-objdump -s chall.wasm   # -s: 각 섹션의 raw 데이터 hex dump

# 특정 함수만 골라서 보고 싶으면 wasm-decompile 결과에서 함수명으로 검색
grep -n "function check" chall.dcmp
```

## 출력 해석
`wasm-objdump -s chall.wasm`의 `Data` 섹션 출력 예:
```
Data start=0x1000 (memory 0)
000010e0 4374 4621 7b73 3059 5f77 3170 5f6d 3374   CtF!{s0Y_w1p_m3t
```
이렇게 사람이 읽을 수 있는 문자열이 바로 보이면, WASM 코드의 XOR/비교 로직을 굳이 다 풀지 않아도 이 데이터가 정답 자체이거나 XOR 전 원문일 가능성이 크다. 반대로 랜덤해 보이는 바이트라면 인코딩된 정답이므로 코드의 변형 연산을 정확히 역산해야 한다.

## 흔한 실수
- `loop` 안의 `br_if` 조건을 반대로 읽는 것 — `br_if`는 "조건이 참이면 분기"이므로, 실패 분기인지 계속 진행 분기인지 라벨(`$fail`, `$continue` 등, 있다면)과 함께 확인해야 한다.
- 스택 순서를 착각해 `i32.sub`의 피연산자 순서(먼저 push된 값이 피감수인지 감수인지)를 반대로 계산하는 것.
- 익명 함수(`$func12`)라고 지레 포기하는 것 — export 시그니처와 상수만 봐도 역할을 상당 부분 추정할 수 있다.
- 짧은 함수라고 안일하게 보고 `br_table` 기반 상태 머신을 놓쳐 일부 분기 케이스를 빠뜨리는 것.

## 막혔을 때 다음 체크
- `.wat`/의사코드 자체를 만드는 방법이 기억 안 나면 → REV-1098 wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- 정적으로 손으로 계산하기엔 로직이 너무 복잡하면 → REV-1100 브라우저 개발자도구로 WASM 디버깅하기(실제 실행하며 값 관찰)
- 부호/오버플로우 판단이 헷갈리면 x86 쪽이지만 원리는 동일한 → REV-0088 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기
- WASM 모듈 구조(섹션 종류) 자체가 헷갈리면 → REV-1097 WASM 바이너리 구조 기초(모듈/섹션)

## 미니 예제
```wat
(func $check (export "check") (param $ptr i32) (param $len i32) (result i32)
  (local $i i32)
  (local.set $i (i32.const 0))
  (block $done
    (loop $L
      (br_if $done (i32.ge_u (local.get $i) (local.get $len)))
      (i32.ne
        (i32.xor
          (i32.load8_u (i32.add (local.get $ptr) (local.get $i)))
          (i32.const 0x2a))
        (i32.load8_u (i32.add (i32.const 4096) (local.get $i))))
      (br_if $done)          ;; 하나라도 다르면 즉시 실패 분기로
      (local.set $i (i32.add (local.get $i) (i32.const 1)))
      (br $L)))
  ...)
```
이 예제는 입력 문자열 각 바이트를 `0x2a`와 XOR한 값이 메모리 오프셋 `4096`부터 있는 정답 배열과 같은지 한 글자씩 비교하는 전형적인 패턴 1이다. 파이썬으로 `bytes(b ^ 0x2a for b in answer)`를 계산하면 바로 입력값을 복원할 수 있다.

## 관련 글
- REV-1098 — wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- REV-1100 — 브라우저 개발자도구로 WASM 디버깅하기
- REV-1097 — WASM 바이너리 구조 기초(모듈/섹션)
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## 출처/검증
- WASM 스택 기반 명령어 의미(`local.get`, `i32.add`, `i32.xor`, `br_if`, `br_table` 등)는 WebAssembly 공식 사양 및 WABT 문서의 명령어 목록 기준으로 확인(2026-09-10, WABT README (https://github.com/WebAssembly/wabt/blob/main/README.md) 및 wasm-decompile 관련 설명 참고).
- 실제 CTF WASM 문제에서 XOR+비교, 산술식 체크섬, 상태 머신형 검증이 자주 나타나는 경향은 공개된 다수의 WASM reversing CTF writeup(예: HackPack CTF 2023 WASM 문제 writeup 등)에서 반복 관찰됨.
