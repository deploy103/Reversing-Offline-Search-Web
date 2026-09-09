---
id: REV-1093
title: "Rust 바이너리 식별하는 법"
slug: "rev-1093-rust-binary-identification"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, "Detect It Easy"]
keywords: ["Rust 바이너리 식별", "Rust 리버싱", "rustc 문자열", "cargo 리버싱"]
aliases: ["이 바이너리가 Rust인지 확인하는 법", "Rust로 만든 실행파일 특징"]
symptom_keywords: ["함수 이름이 이상하게 길고 해시가 붙어있음", "panicked at 라는 문자열이 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Rust 바이너리는 `.rodata`에 남는 표준 라이브러리 소스 경로(`library/std/src/...`, `library/core/src/panicking.rs`)와 `core::panicking::panic` 같은 해시 접미사 붙은 심볼, 그리고 `rustc`/크레이트 버전 문자열이라는 세 가지 특징적인 흔적으로 대부분 식별할 수 있다.

## 언제 검색해야 하나
- `file`/checksec으로는 그냥 "ELF 64-bit"나 "PE32+"로만 나오고 컴파일러 정보가 없어서 어떤 언어로 짜였는지 감이 안 잡힐 때
- Detect It Easy(DIE)로 열었는데 컴파일러가 명확히 안 뜨고 GCC/MSVC로만 애매하게 잡힐 때
- 함수 이름이 `_ZN4core9panicking5panic17h...E` 처럼 길고 끝에 16진수 해시가 붙어 있어서 C++ 맹글링과는 다르게 보일 때
- `strings` 결과에 `panicked at`, `Cargo.toml`, `library/std/src` 같은 문자열이 섞여 있을 때

## 핵심 개념

### .rodata에 남는 표준 라이브러리 경로
Rust 툴체인이 배포하는 표준 라이브러리(`std`, `core`)는 미리 컴파일된 바이너리 형태로 제공되는데, 이 사전 컴파일 과정에서 만들어진 패닉 위치 메타데이터(소스 파일 경로, 줄/열 번호)가 그대로 남아 있다. 그래서 사용자가 직접 작성한 코드가 하나도 패닉을 안 일으켜도, 표준 라이브러리 어딘가에서 패닉이 날 수 있는 코드 경로가 있다면 `library/std/src/...` 또는 `library/core/src/panicking.rs` 같은 경로 문자열이 바이너리에 박혀 있다. `strings ./chall | grep "\.rs"` 로 손쉽게 확인 가능하다.

### 해시 접미사가 붙은 심볼 이름
Rust는 자체 이름 맹글링 스킴을 쓰며, 레거시 스킴에서는 심볼 이름 마지막에 해시값이 접미사로 붙는 특징이 있다(v0 스킴은 형식이 다르며 REV-1095에서 별도로 다룬다). `core::panicking::panic`, `rust_begin_unwind`, `_ZN...17h<16진수>E` 같은 이름이 심볼 테이블에 보인다면 이는 강력한 Rust 지문이다. 특히 `panic`/`panicking` 관련 심볼은 거의 모든 Rust 바이너리에 존재한다(패닉 핸들러 자체가 표준 라이브러리 필수 구성요소이기 때문).

### rustc/크레이트 버전 및 의존성 이름
Rust 바이너리는 컴파일에 사용된 `rustc` 버전 문자열이나, `Cargo.toml`에 선언된 의존성 크레이트 이름/버전이 문자열로 남아있는 경우가 많다. 이 정보는 어떤 rustc 버전으로 컴파일됐는지, 어떤 서드파티 라이브러리(예: `serde`, `tokio`)를 쓰는지 파악하는 데도 쓰인다.

### 문자열이 널 종료되지 않는다는 주의점
Rust 문자열도 Go와 비슷하게 포인터+길이 쌍으로 표현되며 널 종료가 아니다. 그래서 Ghidra 같은 도구가 문자열 하나를 자동 인식할 때 실제 경계보다 길게 잡아 다음 문자열까지 겹쳐 보여줄 수 있다. 이 경우 Ghidra에서 해당 위치의 문자열을 "Clear Code Bytes"로 지우고 정확한 길이만큼 수동으로 다시 정의해야 한다.

### 식별을 어렵게 만드는 빌드 옵션
`Cargo.toml`의 `[profile.release]`에 `panic = "abort"`를 지정하면 언와인딩 관련 테이블과 문자열 상당수가 줄어들고, 나이틀리 전용 플래그 `RUSTFLAGS="-Zlocation-detail=none"`(그리고 `-Z build-std`로 표준 라이브러리 자체를 이 옵션으로 다시 빌드)를 쓰면 패닉 위치의 소스 파일명이 아예 사라진다. 이런 빌드에서는 경로 문자열만으로 식별하기 어려워지므로, 심볼 해시 패턴이나 rustc 버전 문자열 등 다른 단서를 함께 확인해야 한다.

## 화면/코드에서 보이는 징후
- `strings ./chall | grep "\.rs"` 결과에 `library/std/src/...`, `library/core/src/panicking.rs`, 혹은 사용자 프로젝트 경로(`src/main.rs`)가 여러 줄 나옴
- 심볼 테이블에 `core::panicking::panic`, `rust_begin_unwind`, `_ZN...h[0-9a-f]{16}E` 형태의 이름이 존재
- `strings` 결과에 `panicked at`라는 고정 문구가 보임
- Ghidra에서 특정 문자열을 열었더니 다음 문자열과 이어 붙은 것처럼 보임(널 미종료 특성)

## 가장 먼저 할 것
`strings ./chall | grep -E "\.rs$|panicked at|library/(std|core)/src"` 한 줄로 대부분의 경우 바로 확인 가능하다. 결과가 없다면 `panic = "abort"`나 위치 정보 스트리핑 빌드일 수 있으므로, 심볼 테이블에서 해시 접미사 패턴이나 `_R`로 시작하는 v0 맹글링 심볼(REV-1095)을 추가로 확인한다.

## 단계별 절차
1. `file ./chall`과 Detect It Easy(REV-0287, REV-0126)로 1차 스캔 — 컴파일러가 명확히 안 잡히면 다음 단계로
2. `strings ./chall | grep -E "\.rs$"`로 소스 경로 문자열 확인
3. `strings ./chall | grep -i "panicked at"`로 패닉 메시지 포맷 확인
4. `nm ./chall 2>/dev/null | grep -iE "panicking|rust_begin_unwind"`로 심볼 확인(strip 안 된 경우)
5. 위 세 개가 전부 안 나오면 `nm ./chall | grep '^_R'` 또는 `_ZN.*17h[0-9a-f]\{16\}E` 패턴으로 v0/레거시 맹글링 심볼 검색
6. `strings ./chall | grep -iE "rustc [0-9]"`로 컴파일러 버전 문자열 탐색
7. 그래도 확신이 안 서면 알려진 크레이트 이름(`serde`, `tokio`, `anyhow` 등)이 문자열에 있는지 확인

## 명령어/단축키
```bash
strings ./chall | grep -E "\.rs$"
strings ./chall | grep -i "panicked at"
nm ./chall | grep -iE "panicking|rust_begin_unwind"
nm ./chall | grep '^_R'
strings ./chall | grep -iE "rustc [0-9]"
```

## 출력 해석
- `library/std/src/...` 경로가 나오면 표준 라이브러리 자체가 패닉 위치 정보를 갖고 있다는 뜻이므로, 사용자 코드가 패닉을 안 써도 뜰 수 있다 — 이것만으로 Rust라고 확정할 수 있다.
- 사용자 프로젝트 경로(`src/main.rs`, `src/lib.rs` 등)가 나오면 이는 실제 컴파일한 사람의 로컬 경로 일부가 그대로 남은 것이라, 프로젝트 구조(멀티 크레이트 워크스페이스 여부 등)까지 추측할 단서가 된다.
- 아무 `.rs` 문자열도 안 나오는데 `_R` 또는 해시 접미사 심볼만 있다면, `-Zlocation-detail=none`류 빌드로 위치 정보만 제거된 경우일 가능성이 높다.

## 흔한 실수
- `.rs` 경로 문자열이 하나도 안 보인다고 바로 "Rust가 아니다"라고 단정하는 것 — `panic = "abort"`나 위치 정보 제거 빌드에서는 문자열이 거의 없을 수 있다.
- Ghidra의 자동 문자열 인식 결과를 그대로 믿고 문자열 경계가 겹쳐 보이는 것을 못 알아채는 것(널 미종료 특성).
- C++ 이름 맹글링(REV-0763)과 Rust 레거시 맹글링을 혼동해서 `_ZN`으로 시작한다고 무조건 C++이라 단정하는 것 — Rust 레거시 맹글링도 Itanium ABI 스타일을 일부 차용해 `_ZN`으로 시작할 수 있다.
- 크레이트 이름 문자열만 보고 어떤 라이브러리를 쓰는지 성급히 결론짓고, 실제 사용 여부(단순 의존성 vs 실제 호출)를 검증하지 않는 것.

## 막혔을 때 다음 체크
- panic 메시지에서 더 구체적인 소스 위치(파일/줄/열)를 뽑아내고 싶으면 → REV-1094 Rust panic 메시지에서 소스 정보 추출하기
- 심볼 이름이 왜 그런 형태인지, v0 맹글링 규칙을 정확히 알고 싶으면 → REV-1095 Rust 이름 맹글링(v0 mangling) 해석하기
- 어셈블리에서 `match`/분기가 이상하게 짧게 나오면(니치 최적화) → REV-1096 Rust의 Option/Result 패턴이 어셈블리에서 보이는 방식
- Detect It Easy 자체 사용법이 헷갈리면 → REV-0287 Detect It Easy 설치와 사용법

## 미니 예제
```
$ strings ./chall | grep -E "\.rs$" | head -5
/rustc/9c2ca8a2c11f349850be2c3e7c8e0a4a2eaf8c48/library/core/src/panicking.rs
src/main.rs
src/checker.rs

$ strings ./chall | grep -i "panicked at"
panicked at

$ nm ./chall | grep panicking
0000000000123abc T _ZN4core9panicking9panic_fmt17h2a1b3c4d5e6f7089E
```
표준 라이브러리 경로(`library/core/src/panicking.rs`)와 사용자 경로(`src/main.rs`, `src/checker.rs`)가 함께 나왔고, 해시 접미사가 붙은 `panic_fmt` 심볼도 확인되어 이 바이너리는 Rust로 컴파일된 것이 확실하다.

## 관련 글
- REV-1094 — Rust panic 메시지에서 소스 정보 추출하기
- REV-1095 — Rust 이름 맹글링(v0 mangling) 해석하기
- REV-1096 — Rust의 Option/Result 패턴이 어셈블리에서 보이는 방식
- REV-0287 — Detect It Easy 설치와 사용법
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0763 — C++ 이름 맹글링(Name Mangling) 해석하기

## 출처/검증
- Rust 바이너리의 표준 라이브러리 패닉 위치 문자열(`library/std/src`, `library/core/src/panicking.rs`)이 사전 컴파일된 표준 라이브러리에서 유래한다는 점, 및 널 미종료 문자열로 인한 Ghidra 자동 인식 문제: cxiao.net "Using panic metadata to recover source code information from Rust binaries" 기준.
- `panic = "abort"` 및 `RUSTFLAGS="-Zlocation-detail=none"`로 패닉 위치 메타데이터를 제거하는 빌드 옵션: 동일 cxiao.net 자료 및 Rust 공식 The Book(panic 관련 챕터) 기준.
- 레거시 Rust 심볼 맹글링의 해시 접미사 특징: Rust 컴파일러 데몽글러 구현(perf `demangle-rust.h` 등 여러 도구의 공통 처리 방식) 기준 (2026-09-10 검증).
