---
id: REV-1097
title: "WASM 바이너리 구조 기초(모듈/섹션)"
slug: "rev-1097-wasm-module-section-basics"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: ["WASM"]
tools: [wabt, "Chrome DevTools"]
keywords: ["WASM 바이너리 구조", "WebAssembly 모듈", "wasm 섹션", "0asm 매직 넘버"]
aliases: ["wasm 파일 구조가 뭔지 모름", "WebAssembly 섹션 종류"]
symptom_keywords: [".wasm 파일을 헥스로 열었는데 뭐가 뭔지 모르겠음", "wasm 파일에 섹션이 몇 개인지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
모든 WebAssembly 바이너리(`.wasm`)는 4바이트 매직 넘버 `\0asm`과 4바이트 버전(현재 `1`) 뒤에, 각각 고유한 섹션 ID(0~11)를 가진 Type/Import/Function/Table/Memory/Global/Export/Start/Element/Code/Data 섹션들이 정해진 순서로 이어지는 형태이며, 각 섹션은 "ID 1바이트 + 크기(가변길이 정수) + 내용"으로 인코딩된다.

## 언제 검색해야 하나
- CTF 문제로 `.wasm` 파일 하나가 주어졌는데 이걸 어떻게 열어야 할지, 안에 뭐가 들어있는지 감이 안 잡힐 때
- `.wasm` 파일을 헥스 에디터로 열었는데 맨 앞 8바이트가 뭔지 궁금할 때
- `wasm2wat` 등으로 텍스트 변환하기 전에, 원본 바이너리 구조 자체를 먼저 이해하고 싶을 때(REV-1098에서 실제 변환 도구를 다룬다)
- 브라우저에서 로드되는 `.wasm` 모듈의 함수/메모리/전역 변수 구조를 파악해야 할 때

## 핵심 개념

### 프리앰블(preamble) — 매직 넘버와 버전
WebAssembly Core Specification("Modules")에 따르면 모든 모듈 인코딩은 4바이트 매직 넘버 문자열 `\0asm`으로 시작하고, 바로 이어서 4바이트 버전 필드가 온다(현재 WebAssembly 바이너리 포맷 버전은 1). 즉 파일의 첫 8바이트는 항상 다음과 같다.

```
00 61 73 6D   ; '\0' 'a' 's' 'm' 매직 넘버
01 00 00 00   ; 버전 1 (리틀엔디언 32비트)
```

이 8바이트가 없거나 다르면 유효한 wasm 모듈이 아니다.

### 섹션의 일반 구조
프리앰블 뒤에는 섹션들이 순서대로 이어진다. 커스텀 섹션(ID 0)은 시퀀스 어디에나 여러 번 나타날 수 있지만, 그 외의 섹션은 각각 최대 한 번만, 그리고 정해진 순서로만 나타날 수 있다(순서를 어기면 잘못된 모듈로 취급된다). 모든 섹션은 다음과 같이 인코딩된다.

```
<section id: 1바이트> <section size: u32(가변길이)> <실제 섹션 내용>
```

섹션 크기는 디코딩 자체에는 필수가 아니지만(커스텀 섹션 제외), 도구가 특정 섹션을 건너뛰며 순회할 때 유용하게 쓰인다. 크기가 실제 내용 길이와 다르면 모듈은 malformed(잘못된 형식)로 간주된다.

### 표준 섹션 ID 목록(0~11)
WebAssembly Core Specification 기준으로 섹션 ID와 이름은 다음과 같다.

| ID | 이름 | 내용 |
|----|------|------|
| 0 | Custom | 디버그 정보 등 임의 메타데이터, 실행 의미에 영향 없음 |
| 1 | Type | 함수 시그니처(매개변수/리턴 타입) 목록 |
| 2 | Import | 외부에서 가져오는 함수/테이블/메모리/전역 변수 |
| 3 | Function | 각 함수가 어떤 Type 인덱스를 쓰는지 목록 |
| 4 | Table | 간접 호출(call_indirect) 등에 쓰이는 테이블 정의 |
| 5 | Memory | 선형 메모리(linear memory) 정의 |
| 6 | Global | 전역 변수 정의 |
| 7 | Export | 외부에 공개하는 함수/테이블/메모리/전역 변수 |
| 8 | Start | 모듈 로드 시 자동 실행되는 시작 함수 인덱스(선택적) |
| 9 | Element | 테이블 초기화 데이터 |
| 10 | Code | 실제 함수 본문(로컬 변수 선언 + 명령어 시퀀스) |
| 11 | Data | 메모리 초기화 데이터 |

### Function 섹션과 Code 섹션의 관계
Function 섹션(ID 3)은 각 함수가 어떤 시그니처(Type 섹션의 몇 번 항목)를 쓰는지 순서대로 나열만 하고, 실제 함수 몸체(로컬 변수 + 명령어)는 Code 섹션(ID 10)에 별도로 저장된다. 스펙은 이 두 섹션에서 만들어지는 벡터의 길이가 반드시 일치해야 한다고 규정한다 — 즉 Function 섹션에 함수가 5개 나열되어 있다면 Code 섹션에도 정확히 5개의 함수 본문이 있어야 한다. 이 두 섹션을 인덱스로 짝지어야 "N번째 함수의 시그니처가 무엇이고 실제 코드가 어디 있는지"를 알 수 있다.

### Type 섹션 인코딩 예시
Type 섹션은 함수 시그니처의 벡터를 담으며, 각 함수 타입은 `0x60`(함수 타입을 나타내는 고정 바이트) 뒤에 매개변수 타입 목록과 리턴 타입 목록이 이어지는 형태로 인코딩된다(`functype ::= 0x60 vec(valtype) vec(valtype)`). 이 `0x60`은 wasm 바이너리를 헥스로 열었을 때 Type 섹션을 찾는 좋은 단서가 된다.

## 화면/코드에서 보이는 징후
- 파일 첫 8바이트가 `00 61 73 6D 01 00 00 00`
- 그 뒤로 `01`(Type), `02`(Import), `03`(Function), `07`(Export), `0A`(Code) 같은 한 바이트 ID들이 반복해서 나타남
- 각 섹션 ID 바로 뒤에 가변 길이 정수(LEB128)로 인코딩된 크기 값이 따라옴
- Code 섹션(ID 10) 부분이 파일에서 가장 큰 비중을 차지

## 가장 먼저 할 것
파일을 헥스 에디터나 `xxd`로 열어 첫 8바이트가 `00 61 73 6D 01 00 00 00`인지 확인해 유효한 wasm 모듈인지부터 검증한다. 그다음은 원본 바이트를 직접 파싱하기보다, `wasm2wat`(REV-1098, 예정)으로 텍스트 형식(WAT)으로 변환해서 사람이 읽기 쉬운 형태로 먼저 훑어보는 것이 실전에서 훨씬 빠르다.

## 단계별 절차
1. `xxd chall.wasm | head -1`로 매직 넘버/버전 확인
2. 섹션을 순서대로 훑으며 각 섹션의 ID 바이트를 기록(직접 파싱하거나, 툴 출력으로 대체)
3. Import 섹션(ID 2)을 확인해 외부에서 어떤 함수/메모리를 가져오는지(예: JS 쪽에서 제공하는 함수) 파악
4. Export 섹션(ID 7)을 확인해 이 모듈이 외부(JS)에 어떤 함수/메모리를 공개하는지 파악
5. Start 섹션(ID 8)이 있으면 모듈 로드 시 자동 실행되는 함수가 있다는 뜻이므로 그 함수부터 우선 분석
6. Function/Code 섹션(ID 3, 10)을 인덱스로 짝지어 각 함수의 시그니처와 실제 본문을 매칭
7. 이후 실제 텍스트/디스어셈블 분석은 REV-1098의 `wasm2wat`/`wasm-decompile` 절차로 넘어간다

## 명령어/단축키
```bash
xxd chall.wasm | head -2
wasm-objdump -h chall.wasm      # 섹션 헤더 목록만 빠르게 확인 (wabt 도구)
wasm-objdump -x chall.wasm      # 상세 정보(Import/Export/타입 등)
```

## 출력 해석
- `wasm-objdump -h` 결과에 나오는 섹션 이름과 크기(offset, size)를 보면 파일 전체에서 각 섹션이 차지하는 비중을 알 수 있다 — 보통 Code 섹션이 압도적으로 크다.
- Import 섹션에 `env` 같은 모듈 이름과 함께 여러 함수가 나열되어 있으면, 이 wasm 모듈이 호스트(JS) 환경이 제공하는 함수에 의존한다는 뜻이다.
- Export 섹션에 `main`이나 특정 이름의 함수가 보이면 그것이 JS 쪽에서 호출하는 진입점일 가능성이 높다.

## 흔한 실수
- 매직 넘버/버전 확인 없이 바로 파싱을 시도하다가, 실제로는 gzip 압축되었거나 손상된 파일임을 뒤늦게 알아채는 것.
- 섹션 크기 필드가 고정 4바이트라고 착각하는 것 — 실제로는 LEB128 가변 길이 정수이므로 바이트 수가 섹션마다 다를 수 있다.
- Function 섹션과 Code 섹션을 별개로 보고 인덱스로 짝지어 봐야 한다는 것을 놓쳐서, 함수 시그니처와 실제 본문을 서로 다른 함수의 것으로 혼동하는 것.
- 커스텀 섹션(ID 0)에 있는 디버그용 이름 정보(예: `name` 섹션)를 무시하고 넘어가는 것 — 이 안에 원래 함수 이름이 남아있는 경우가 많아 분석에 큰 도움이 된다.

## 막혔을 때 다음 체크
- 원본 바이너리를 직접 읽지 않고 사람이 읽기 쉬운 텍스트로 바꾸고 싶으면 → REV-1098 wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- 변환한 텍스트에서 흔한 검증/체크 로직 패턴을 알아보고 싶으면 → REV-1099 WASM에서 흔한 검증 로직 패턴 알아보기
- 브라우저에서 동적으로 디버깅하고 싶으면 → REV-1100 브라우저 개발자도구로 WASM 디버깅하기

## 미니 예제
```
$ xxd chall.wasm | head -1
00000000: 0061 736d 0100 0000 0186 8080 8000 0260  .asm...........

$ wasm-objdump -h chall.wasm
chall.wasm:     file format wasm 0x1

Sections:

     Type start=0x0000000a end=0x00000014 (size=0x0000000a) count: 3
   Import start=0x00000016 end=0x00000030 (size=0x0000001a) count: 2
 Function start=0x00000032 end=0x00000036 (size=0x00000004) count: 3
   Export start=0x00000040 end=0x00000050 (size=0x00000010) count: 1
     Code start=0x00000052 end=0x000000d0 (size=0x0000007e) count: 3
```
첫 8바이트로 유효한 wasm 파일임을 확인했고, `wasm-objdump -h`로 Type/Import/Function/Export/Code 섹션이 순서대로 존재하며 각각 몇 개의 항목을 담고 있는지 한눈에 파악할 수 있다.

## 관련 글
- REV-1098 — wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- REV-1099 — WASM에서 흔한 검증 로직 패턴 알아보기
- REV-1100 — 브라우저 개발자도구로 WASM 디버깅하기

## 출처/검증
- 모듈 프리앰블(4바이트 매직 넘버 `\0asm` + 4바이트 버전 1)과 섹션 시퀀스 규칙(커스텀 섹션은 임의 위치 반복 가능, 나머지는 최대 1회·순서 고정): WebAssembly Core Specification 공식 문서("Modules" 챕터, webassembly.github.io) 기준.
- 섹션 일반 인코딩(`<id> <u32 size> <content>`)과 크기 필드가 커스텀 섹션 외에는 디코딩 필수는 아니라는 점, Type 섹션의 `0x60` 함수 타입 마커: 동일 WebAssembly Core Specification 기준.
- 섹션 ID 0~11 전체 목록(Custom/Type/Import/Function/Table/Memory/Global/Export/Start/Element/Code/Data)과 Function/Code 섹션 벡터 길이 일치 규칙: WebAssembly Core Specification 및 커뮤니티 정리 자료(KodeKloud "Understanding the WebAssembly Binary Format") 기준 (2026-09-10 검증).
