---
id: REV-1095
title: "Rust 이름 맹글링(v0 mangling) 해석하기"
slug: "rev-1095-rust-v0-name-mangling"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB]
keywords: ["Rust v0 mangling", "Rust 이름 맹글링", "_R 심볼", "rustfilt"]
aliases: ["Rust 심볼이 _R로 시작함", "Rust 함수 이름 해석하는 법"]
symptom_keywords: ["함수 이름이 _R로 시작해서 못 읽음", "Rust 제네릭 함수 심볼이 복잡함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Rust는 RFC 2603으로 표준화된 v0 맹글링 스킴에서 심볼 이름 앞에 `_R` 접두사를 붙이고 경로/제네릭 타입 정보를 역으로 디코딩 가능한 형태로 압축 인코딩하므로, `_R`로 시작하는 이름을 보면 legacy(해시 접미사 방식)와 구분되는 v0 스킴임을 알고 rustfilt 등으로 디맹글링해서 읽어야 한다.

## 언제 검색해야 하나
- 심볼 테이블에서 함수 이름이 `_R`로 시작하고 그 뒤로 숫자와 알파벳이 섞인 암호 같은 문자열이 이어질 때
- 같은 프로그램인데 어떤 심볼은 `_ZN...17h<해시>E` 형태(legacy)이고 어떤 심볼은 `_R...` 형태(v0)로 섞여 있어 혼란스러울 때
- 제네릭 함수(`fn foo<T>(...)`)가 여러 타입으로 인스턴스화되어 비슷하지만 조금씩 다른 이름의 함수가 여러 개 보일 때
- IDA/Ghidra가 Rust 심볼을 자동으로 예쁘게 안 보여줘서 원래 함수/타입 이름을 수동으로 복원해야 할 때

## 핵심 개념

### 왜 새 맹글링 스킴이 필요했나
기존(legacy) Rust 맹글링은 시간이 지나며 컴파일러 내부 구현에 강하게 의존하는 형태로 커져서 일관성이 없었다. RFC 2603("Rust Symbol Mangling (v0)")은 이를 대체하기 위해 다음을 목표로 설계된 새 스킴을 제안했다: 바이너리에 들어갈 수 있는 모든 것에 대해 모호하지 않은 문자열 인코딩을 제공하고, 제네릭 매개변수 정보를 가역적으로(reversible) 인코딩하며, 다형 함수(polymorphic function)의 구체적인 인스턴스임을 디맹글된 결과만으로도 쉽게 식별 가능하게 만드는 것이다.

### _R 접두사
공식 rustc 문서(v0 Symbol Format)에 따르면, v0로 맹글링된 심볼은 항상 두 글자 `_R`로 시작한다. 이는 이 심볼이 Rust 심볼임을 나타내는 접두사이며, 그 뒤에 선택적으로 인코딩 버전을 나타내는 십진수가 붙을 수 있지만 현재 버전에서는 이 숫자가 실제로 쓰이지 않아 항상 생략된다. 즉 실전에서 보는 v0 심볼은 거의 항상 `_R` 바로 뒤에 본문 인코딩이 이어진다.

### 인코딩 문자 제한과 백레퍼런스 압축
v0 스킴은 심볼 이름에 영문 대소문자, 숫자, 밑줄(`A-Z`, `a-z`, `0-9`, `_`)만 쓰도록 제한한다. 이는 플랫폼에 따라 특수 문자가 예약된 의미를 가질 수 있는 문제를 피하기 위함이다. 또한 컴파일러는 심볼을 만들면서 경로의 모든 접두사, 모든 비기본(non-basic) 타입, 타입 레벨 상수의 위치를 추적해, 나중에 같은 항목이 다시 나오면 축약된 역참조(백레퍼런스)로 대체한다 — C++ Itanium ABI 맹글링의 압축 방식과 비슷한 개념이다.

### legacy 스킴과의 차이 — 해시 접미사 유무
legacy(예전) Rust 맹글링은 심볼 이름 끝에 짧은 해시값이 접미사로 붙는 특징이 있었다(예: `...17h2a1b3c4d5e6f7089E`). v0 스킴은 이런 임의 해시 접미사에 의존하지 않고 구조 자체를 완전히 인코딩하는 방식으로 설계되었다. 두 스킴은 `-C symbol-mangling-version` 컴파일러 플래그(`legacy` 또는 `v0`)로 선택할 수 있었으며, 최근 Rust 릴리스에서는 v0가 stable 기본값으로 전환되어(2026년 7월 Rust 1.97) 이제 기본적으로 v0 심볼을 훨씬 자주 보게 된다.

### 왜 기존 C++ 디맹글러를 그대로 안 썼나
RFC 논의 과정에서 기존 C++ 스타일 맹글링을 재사용하는 방안도 검토되었지만, 실제 이득이 크지 않다고 판단되었다 — C++ 도구로 디맹글해도 Rust 문법으로 나오지 않을 것이고, GDB/LLDB/binutils/valgrind 등 이미 여러 도구가 Rust 전용 처리 로직을 갖고 있었기 때문이다. 따라서 실전에서는 `rustfilt` 같은 Rust 전용 디맹글러, 또는 Rust 심볼 처리를 지원하는 최신 `c++filt`/`nm --demangle`을 사용해야 한다.

## 화면/코드에서 보이는 징후
- 심볼이 `_RNvC...`, `_RNvNtCs...` 처럼 `_R` 뒤에 `N`(경로 시작), `v`/`t`(값/타입 네임스페이스) 등 규칙적인 문자 조합으로 시작
- 같은 제네릭 함수가 타입 인자만 다르게 여러 번 반복 정의되어, 심볼 이름 뒷부분만 조금씩 다름
- IDA/Ghidra Functions 창에서 심볼 이름이 너무 길어 한 줄에 다 안 보이고 잘림

## 가장 먼저 할 것
심볼이 `_R`로 시작하는지 확인해 v0 스킴인지 legacy(해시 접미사) 스킴인지부터 구분한다. 그다음 `rustfilt` 또는 Rust 심볼을 지원하는 최신 `c++filt`로 일괄 디맹글해 읽기 쉬운 형태로 바꾼 뒤 분석을 시작한다.

## 단계별 절차
1. `nm ./chall | grep '^\S* [Tt] _R'`로 v0 스킴 심볼만 먼저 추출
2. `rustfilt`가 설치되어 있으면 `nm ./chall | rustfilt`로 전체 심볼을 한 번에 디맹글
3. `rustfilt`가 없으면 최신 `c++filt`(Rust 심볼 지원 버전)로 `c++filt _R...` 형태 시도
4. 디맹글된 이름에서 크레이트/모듈 경로(`::`로 구분된 부분)를 확인해 어떤 패키지 소속인지 파악
5. 제네릭 인스턴스가 여러 개면 디맹글된 이름의 타입 인자 부분(`<T>`에 해당하는 부분)만 비교해 실제로 몇 가지 타입으로 호출되는지 정리
6. IDA/Ghidra에서는 디맹글된 이름을 함수 이름에 그대로 반영(Rename)해 이후 분석에서 원본 이름을 계속 볼 수 있게 한다

## 명령어/단축키
```bash
nm ./chall | grep '^\S* [Tt] _R'
nm ./chall | rustfilt
c++filt '_RNvC7mycrate4main'
```

## 출력 해석
- 디맹글 결과가 `mycrate::main`처럼 깔끔한 `크레이트이름::경로`로 나오면 정상적으로 v0 심볼이 해석된 것이다.
- 디맹글 결과에 `<T>`나 `impl` 같은 표기가 붙어 있으면 이는 제네릭 함수나 트레이트 구현체의 구체적인 인스턴스라는 뜻이다.
- 백레퍼런스 압축 때문에 raw 심볼 문자열만 봐서는 반복 구조를 알아채기 어려우므로, 항상 디맹글 도구의 출력으로 판단해야 한다.

## 흔한 실수
- `_R` 접두사를 못 알아보고 legacy 스킴 전용 디맹글러(구버전 `c++filt`)만 시도해 실패하는 것 — v0와 legacy는 서로 다른 인코딩이라 전용 도구/버전이 필요하다.
- raw 맹글링된 문자열을 사람이 직접 손으로 해석하려 드는 것 — 백레퍼런스 압축 규칙이 있어 수작업 해석은 비효율적이고 오류가 나기 쉽다.
- 제네릭 함수의 여러 인스턴스를 전부 별개의 무관한 함수로 취급해서 같은 로직을 여러 번 분석하는 것 — 디맹글된 이름을 비교하면 같은 함수의 타입별 인스턴스임을 알 수 있다.
- v0가 최근 stable 기본값이 되었다고 해서 모든 Rust 바이너리가 v0라고 단정하는 것 — 오래된 rustc로 빌드했거나 `-C symbol-mangling-version=legacy`를 명시한 바이너리는 여전히 legacy 스킴을 쓴다.

## 막혔을 때 다음 체크
- 애초에 이 바이너리가 Rust인지 확신이 안 서면 → REV-1093 Rust 바이너리 식별하는 법
- 디맹글한 이름에서 소스 파일/줄 정보까지 더 구체적으로 얻고 싶으면 → REV-1094 Rust panic 메시지에서 소스 정보 추출하기
- C++ 맹글링과 비교해서 개념을 더 명확히 하고 싶으면 → REV-0763 C++ 이름 맹글링(Name Mangling) 해석하기

## 미니 예제
```
$ nm ./chall | grep '^\S* [Tt] _R' | head -3
0000000000401120 T _RNvC7mycrate10check_flag
0000000000401200 T _RNvMs_C7mycrate5VaultNtB4_5check
0000000000401300 T _RINvC7mycrate5parseNtNtCs1a2b3c4d5e6_4core3fmt6ResultE

$ nm ./chall | rustfilt | head -3
0000000000401120 T mycrate::check_flag
0000000000401200 T <mycrate::Vault>::check
0000000000401300 T mycrate::parse::<core::fmt::Result>
```
`rustfilt`를 거치자 `_R`로 시작하던 암호 같은 이름이 `mycrate::check_flag`, `<mycrate::Vault>::check`처럼 원래 Rust 코드의 모듈/트레이트/제네릭 구조를 그대로 드러내는 이름으로 바뀐다.

## 관련 글
- REV-1093 — Rust 바이너리 식별하는 법
- REV-1094 — Rust panic 메시지에서 소스 정보 추출하기
- REV-0763 — C++ 이름 맹글링(Name Mangling) 해석하기

## 출처/검증
- v0 맹글링 스킴의 목표(모호하지 않은 인코딩, 제네릭 정보의 가역적 인코딩, 다형 함수 인스턴스 식별 용이성): rust-lang RFC 2603 "Rust Symbol Mangling (v0)" 공식 문서 기준.
- `_R` 접두사와 버전 숫자 생략, 문자 집합 제한(A-Z, a-z, 0-9, `_`), 백레퍼런스(substitution) 압축 방식: rustc 공식 문서 "v0 Symbol Format"(doc.rust-lang.org/rustc/symbol-mangling/v0.html) 기준.
- legacy 스킴의 해시 접미사 특징과 `-C symbol-mangling-version` 플래그로 legacy/v0 선택 가능했던 이력, 그리고 v0가 최근 stable 기본값으로 전환된 시점: rust-lang/rust PR #57967, Issue #60705(RFC 2603 트래킹 이슈), 2026년 Rust 1.97 릴리스 관련 보도 기준 (2026-09-10 검증).
