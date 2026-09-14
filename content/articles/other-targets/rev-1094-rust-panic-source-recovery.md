---
id: REV-1094
title: "Rust panic 메시지에서 소스 정보 추출하기"
slug: "rev-1094-rust-panic-source-recovery"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB]
keywords: ["Rust panic 위치 정보", "Rust core::panic::Location", "Rust 소스 경로 복구"]
aliases: ["Rust 바이너리에서 소스 파일 이름 찾기", "panicked at src/main.rs 의미"]
symptom_keywords: ["panicked at라는 문자열이 실제 소스 파일 경로와 함께 있음", "Rust 바이너리에서 함수가 어느 파일 코드인지 구분하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Rust 프로그램이 기본 패닉 동작(언와인딩)으로 컴파일되면, 패닉이 실행될 수 있는 코드마다 `core::panic::Location` 구조체(소스 파일 경로 포인터+길이, 줄 번호, 열 번호)가 정적으로 바이너리에 박혀 있어서, 런타임에 실제로 패닉을 일으키지 않고도 정적 분석만으로 소스 파일/줄/열 정보를 그대로 복구할 수 있다.

## 언제 검색해야 하나
- `strings ./chall`에서 `panicked at`라는 고정 문구를 발견했고, 이 메시지가 실제로 어떤 소스 위치와 연결되는지 알고 싶을 때
- Rust 바이너리에서 어떤 함수가 사용자 코드(`src/...`)이고 어떤 함수가 표준 라이브러리/서드파티 크레이트 코드인지 구분하고 싶을 때
- 릴리스 빌드라 디버그 심볼이 없는데도 특정 함수가 원래 소스에서 몇 번째 줄이었는지 실마리가 필요할 때
- 배열 인덱스 초과, `unwrap()` 실패 등 CTF 문제에서 의도적으로 패닉을 유도하는 취약점을 찾을 때

## 핵심 개념

### 패닉 메시지의 표준 형태
Rust 공식 문서(The Rust Programming Language, 9장)에 따르면 패닉이 발생하면 다음과 같은 형태로 출력된다.

```
thread 'main' panicked at src/main.rs:2:5:
crash and burn
```

`src/main.rs:2:5`는 2번째 줄, 5번째 열(컬럼)에서 패닉이 발생했다는 뜻이다. 패닉을 일으킨 코드가 자신이 작성한 함수가 아니라 자신이 호출한 다른 코드(다른 크레이트, 표준 라이브러리) 안에 있다면, 보고되는 파일/줄 번호는 그 다른 코드의 위치이지 호출한 쪽의 위치가 아니다.

### 이 정보가 정적으로 어떻게 저장되는가
이 위치 정보는 `core::panic::Location`이라는 구조체로 컴파일 타임에 이미 결정되어 바이너리에 내장된다. 대략적으로 소스 파일 경로 문자열을 가리키는 포인터(+길이), 그리고 줄/열 번호(정수)로 구성되며, `panic!` 매크로가 호출될 수 있는 모든 지점마다 이런 `Location` 값이 하나씩 데이터 섹션에 만들어진다. 이 값은 프로그램을 실제로 실행하지 않아도 디스어셈블리/데이터 섹션에서 정적으로 읽어낼 수 있다는 점이 리버싱 관점에서 중요하다 — 즉 "패닉을 실제로 발생시켜야만 위치를 알 수 있는 것"이 아니라, 바이너리 안에 이미 답이 적혀 있다.

### 표준 라이브러리와 사용자 코드를 구분하는 용도
표준 라이브러리(`std`, `core`)도 사전 컴파일 시점에 만들어진 자신의 `Location` 정보를 그대로 갖고 있으므로, 발견한 경로 문자열이 `library/std/src/...`나 `library/core/src/...`로 시작하면 이는 표준 라이브러리 내부 코드이고, 그 외의 상대 경로(`src/main.rs`, `src/utils.rs` 등)라면 사용자(또는 서드파티 크레이트)가 작성한 코드다. `strings`로 뽑은 `.rs` 경로들을 이렇게 분류하면 분석 우선순위를 사용자 코드 쪽으로 좁힐 수 있다.

### 이 정보가 사라지는 경우
- `Cargo.toml`의 `[profile.release] panic = "abort"`로 설정하면 언와인딩 관련 코드가 사라지면서 패닉 관련 문자열/구조가 크게 줄어든다(단, `Location` 자체는 abort 시에도 메시지 출력을 위해 일부 남을 수 있어 완전히 사라진다고 단정하지 않는다).
- 나이틀리 전용 플래그 `RUSTFLAGS="-Zlocation-detail=none"`을 표준 라이브러리까지(`-Z build-std`) 적용해 빌드하면 소스 파일명 자체가 바이너리에서 완전히 빠진다. 이 경우 정적으로 파일명을 복구할 방법이 없어진다.
- 릴리스 빌드에서도 이 즉시 패닉 위치(`Location`)와 별개로, 함수 호출 스택 전체를 보여주는 백트레이스는 디버그 정보가 없으면 함수 이름만 나오고 줄 번호는 안 나올 수 있다 — 이는 패닉 발생 지점 자체의 위치 정보와는 다른 이야기다.

## 화면/코드에서 보이는 징후
- `.rodata`에 `src/main.rs`, `library/core/src/panicking.rs` 같은 문자열이 있고, 그 근처(또는 xref로 연결된 곳)에 작은 정수 두 개(줄, 열)가 나란히 저장됨
- 디스어셈블리에서 `unwrap`/인덱싱/정수 오버플로 체크 실패 분기 직전에 이 파일 경로 문자열 주소를 로드하는 코드가 있음
- 함수 이름에 `core::panicking::panic`, `core::panicking::panic_bounds_check`, `core::option::unwrap_failed` 등이 보임(인덱스 초과, `unwrap()` 실패 등 패닉 종류별로 다른 헬퍼 함수가 호출됨)

## 가장 먼저 할 것
`strings ./chall | grep "\.rs$"`로 모든 소스 경로 문자열을 먼저 뽑고, `library/` 접두사가 붙은 것과 그렇지 않은 것으로 분류한다. `library/`가 아닌 경로들이 실제 프로그램 고유 코드이므로, 그 문자열들을 xref로 따라가 어떤 함수에서 참조되는지부터 확인한다.

## 단계별 절차
1. `strings ./chall | grep "\.rs$"`로 모든 `.rs` 경로 문자열 수집
2. `library/std/`, `library/core/`, `library/alloc/`로 시작하는 것은 표준 라이브러리로 분류해 제외
3. 남은 사용자/크레이트 경로 문자열의 주소를 확인(`objdump -s -j .rodata` 또는 IDA/Ghidra에서 주소 확인)
4. 그 주소를 참조하는 코드를 xref로 찾아 해당 함수로 이동
5. 문자열 근처(구조체 레이아웃상 앞이나 뒤)에 있는 두 개의 작은 정수 필드를 줄/열 번호 후보로 확인 — 값이 상식적인 범위(1~수백)인지로 검증
6. 이 정보를 바탕으로 "이 함수는 원본 소스의 몇 번째 줄 근처에서 왔다"는 대략적인 지도(map)를 만들어 분석 우선순위를 정한다
7. `core::panicking::panic_bounds_check` 등 특정 패닉 헬퍼가 호출되는 지점은 배열 인덱스 초과 등 구체적인 취약점 후보로 별도 표시

## 명령어/단축키
```bash
strings ./chall | grep -E "\.rs$"
strings ./chall | grep -v "^library/"
objdump -s -j .rodata ./chall | grep -B2 -A2 "src/main"
```
IDA/Ghidra: 문자열 주소에서 `Ctrl+X`/References로 xref 확인, 구조체 뷰로 `Location`처럼 보이는 (포인터, 길이, i32, i32) 4필드 레이아웃을 수동으로 정의해두면 이후 같은 패턴이 반복될 때 빠르게 알아볼 수 있다.

## 출력 해석
- 사용자 경로 문자열이 여러 개의 서로 다른 함수에서 참조된다면, 그 파일 하나에 여러 함수가 정의돼 있었다는 뜻이므로 이 함수들을 같은 소스 파일 그룹으로 묶어 분석할 수 있다.
- 줄 번호 값이 비정상적으로 크거나(수만 이상) 이상한 값이면 그건 줄/열 필드가 아니라 다른 필드를 잘못 짚은 것일 수 있다.
- `panic_bounds_check` 호출이 있다는 것은 그 근처에 배열/슬라이스 인덱싱 코드가 있다는 뜻이므로, CTF에서 인덱스 조작 취약점을 찾을 때 우선 확인 지점이 된다.

## 흔한 실수
- 패닉 메시지의 파일/줄 번호가 항상 "내가 실행한 지점"이라고 오해하는 것 — 실제로는 패닉이 일어난 코드(호출된 라이브러리 내부일 수 있음)의 위치다.
- `library/`로 시작하는 표준 라이브러리 경로까지 전부 사용자 코드로 착각해 분석 범위를 불필요하게 넓히는 것.
- `panic = "abort"`나 `-Zlocation-detail=none` 빌드에서 이 방법이 항상 통할 거라 기대하는 것 — 상황에 따라 파일명 정보가 아예 없을 수 있다.
- `Location` 구조체의 필드 순서/타입을 추측 없이 임의로 가정해서 줄/열 번호를 잘못 읽는 것 — 값이 상식적인 범위인지 항상 교차 검증해야 한다.

## 막혔을 때 다음 체크
- 애초에 이 바이너리가 Rust인지 확신이 안 서면 → REV-1093 Rust 바이너리 식별하는 법
- 함수 이름 자체가 해시 접미사나 `_R` 형태로 복잡해서 못 읽겠으면 → REV-1095 Rust 이름 맹글링(v0 mangling) 해석하기
- 문자열이 널 종료가 아니라서 경계가 헷갈리면 → REV-1090 Go 바이너리의 문자열 구조(길이+포인터) 읽는 법 (구조 자체는 언어가 달라도 "길이+포인터" 개념이 유사해 참고 가능)
- 일반적인 문자열 단서 찾기 기법을 다시 보고 싶으면 → REV-0094 strings로 빠르게 단서 찾기

## 미니 예제
```
$ strings ./chall | grep "\.rs$"
library/core/src/panicking.rs
library/core/src/option.rs
src/main.rs
src/vault.rs

$ strings ./chall | grep -v "^library/"
src/main.rs
src/vault.rs
```
`library/`로 시작하는 두 줄은 표준 라이브러리 내부(패닉/Option unwrap 관련) 코드이고, `src/main.rs`와 `src/vault.rs`는 실제 CTF 문제 제작자가 작성한 파일이다. 이 두 사용자 파일 문자열의 xref를 따라가면 문제의 핵심 로직이 있는 함수로 바로 접근할 수 있다.

## 관련 글
- REV-1093 — Rust 바이너리 식별하는 법
- REV-1095 — Rust 이름 맹글링(v0 mangling) 해석하기
- REV-1096 — Rust의 Option/Result 패턴이 어셈블리에서 보이는 방식
- REV-0094 — strings로 빠르게 단서 찾기

## 출처/검증
- 패닉 메시지 형식(`thread 'main' panicked at src/main.rs:2:5: crash and burn`)과 호출된 코드 위치가 보고된다는 설명: Rust 공식 The Rust Programming Language Book 9장(Unrecoverable Errors with panic!) 기준.
- `core::panic::Location`(소스 경로+줄+열) 정보가 표준 라이브러리 사전 컴파일 시점에 만들어져 정적으로 바이너리에 남고, 실행 없이 정적 분석만으로 복구 가능하다는 점, 그리고 `panic = "abort"`/`-Zlocation-detail=none`으로 이를 제거할 수 있다는 점: cxiao.net "Using panic metadata to recover source code information from Rust binaries" 기준 (2026-09-10 검증).
