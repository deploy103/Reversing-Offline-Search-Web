---
id: REV-1098
title: "wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기"
slug: "rev-1098-wasm2wat-decompile"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: ["WASM"]
format: ["WASM"]
tools: [wabt]
keywords: ["wasm2wat", "wasm-decompile", "WASM 디스어셈블", "wabt", "WebAssembly Binary Toolkit"]
aliases: ["wasm 텍스트로 변환", "wasm 디스어셈블 방법", "wat 파일 만들기", ".wasm을 사람이 읽을 수 있게"]
symptom_keywords: ["wasm 파일을 못 읽음", "wasm이 바이너리라 열리지 않음", "wasm 파일에 문자열이 하나도 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`.wasm` 파일은 바이트코드로 압축된 바이너리 포맷이라 그냥 열어서는 읽을 수 없고, `wabt`(WebAssembly Binary Toolkit)의 `wasm2wat`으로 사람이 읽는 텍스트 형식(`.wat`)으로, `wasm-decompile`로 C와 비슷한 의사코드로 바꿔서 분석을 시작해야 한다.

## 언제 검색해야 하나
- CTF 문제 파일이 `.wasm` 확장자이거나 `file chall.wasm` 결과에 `WebAssembly (wasm) binary module`이 나올 때
- 웹 문제에서 브라우저가 JavaScript의 fetch API로 `.wasm` 파일을 받아와 실행하는 것을 발견했을 때
- `strings chall.wasm`을 돌려도 로직이 안 보이고 바이트 뭉치만 나올 때
- Ghidra/IDA에 그냥 로드했더니 인식이 안 되거나 의미 없는 바이트 나열로만 보일 때

## 핵심 개념

### WASM 바이너리 포맷과 텍스트 포맷의 관계
WebAssembly는 두 가지 표현 형식을 공식으로 정의한다. 브라우저가 로드하고 실행하는 것은 `.wasm` 바이너리 포맷이고, 사람이 읽고 쓰기 위한 것이 `.wat`(WebAssembly Text format)이다. 두 형식은 정보 손실 없이 서로 변환 가능하다(단, 원본 컴파일 소스의 변수명/주석 등은 디버그 정보가 없으면 복원되지 않는다).

### wabt(WebAssembly Binary Toolkit)
`wabt`는 WebAssembly 공식 조직(`WebAssembly` GitHub organization) 산하 프로젝트로, `.wasm`과 `.wat`를 상호 변환하고 검사하는 커맨드라인 도구 모음이다. 그중 리버싱에서 자주 쓰는 것은 다음과 같다.

- `wasm2wat`: 바이너리(`.wasm`) → 텍스트(`.wat`). `wat2wasm`의 반대 방향이다.
- `wasm-decompile`: 바이너리를 C와 비슷한(하지만 C 파일은 아닌) 읽기 쉬운 의사코드로 변환한다. `wasm2c`(실제 컴파일 가능한 C로 변환)와는 목적이 다르다 — `wasm-decompile`은 오직 가독성을 위한 것이다.
- `wasm-objdump`: `objdump`와 비슷하게 섹션별 정보를 요약해서 보여준다.
- `wasm-strip`: 디버그/이름 섹션을 제거한다(문제 출제자가 난독화 목적으로 미리 써두는 경우도 있음).
- `wasm-validate`: 바이너리가 스펙상 유효한지 검사한다.

### 왜 wat2wasm의 반대 방향부터 시작하는가
CTF에서 주어지는 파일은 항상 바이너리 `.wasm`이다. 사람이 로직을 읽으려면 먼저 `wasm2wat`으로 텍스트화하거나 `wasm-decompile`로 의사코드화해야 두 형식 모두 검토할 수 있다. 실무에서는 보통 두 도구를 같이 쓴다 — `.wat`은 실제 스택 기반 연산(`local.get`, `i32.add` 등)을 정확히 보여주고, `wasm-decompile` 결과는 제어 흐름과 변수 관계를 빠르게 파악하는 데 유리하다.

## 화면/코드에서 보이는 징후
- `file chall.wasm` → `WebAssembly (wasm) binary module`
- 파일 앞부분 매직 넘버가 `00 61 73 6D`(ASCII로 `\0asm`)로 시작
- 텍스트 에디터로 그냥 열면 대부분 출력 불가능한 바이트로 보임
- 브라우저 개발자도구 Network 탭에 `.wasm` 파일이 `application/wasm` MIME 타입으로 로드됨

## 가장 먼저 할 것
`wabt`를 설치(각 OS 패키지 매니저 또는 `npm install -g wabt`로 Node 없이도 `npx -p wabt`로 즉시 실행 가능)한 뒤, `wasm2wat`으로 전체를 텍스트화해서 함수 개수와 export된 함수 이름부터 확인한다. export 이름 중 `check`, `verify`, `validate`류가 있으면 그 함수부터 본다.

## 단계별 절차
1. `file chall.wasm`으로 정말 WASM 바이너리인지 확인
2. `wasm2wat chall.wasm -o chall.wat`로 텍스트 변환
3. `chall.wat`에서 `(export ...)` 목록을 찾아 어떤 함수가 JS/브라우저에서 호출되는지 확인
4. `wasm-decompile chall.wasm -o chall.dcmp`로 같은 파일을 의사코드로도 변환해 두고 비교하며 읽기
5. `wasm-objdump -x chall.wasm`로 섹션 요약(Import/Export/Function/Memory 등)을 먼저 훑어 전체 구조 파악
6. 이름 섹션이 strip되어 함수가 `$func0`, `$func1`처럼만 보이면 REV-1099(검증 로직 패턴)를 참고해 호출 관계로 역할을 추정

## 명령어/단축키
```bash
# wabt 설치 없이 바로 실행 (Node.js만 있으면 됨)
npx -p wabt wasm2wat chall.wasm -o chall.wat

# 로컬 설치 후
wasm2wat chall.wasm -o chall.wat
wasm2wat chall.wasm --no-debug-names -o chall_nodbg.wat   # 이름 자동생성, 디버그 이름 제외

# 의사코드(C와 유사, 컴파일 불가)로 변환
wasm-decompile chall.wasm -o chall.dcmp

# 섹션 요약만 빠르게 보기 (objdump 스타일)
wasm-objdump -x chall.wasm

# 반대 방향: 텍스트를 수정한 뒤 다시 바이너리로(패치용)
wat2wasm chall.wat -o chall_patched.wasm
```

## 출력 해석
`chall.wat`을 열면 다음과 같은 구조가 보인다.

```wat
(module
  (import "env" "memory" (memory 1))
  (func $check (export "check") (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add
    ...)
)
```

- `(export "check")`는 JS에서 `instance.exports.check(...)`로 호출된다는 뜻 — 이 이름이 웹 페이지의 JS 코드와 대조할 실마리다.
- `(param i32 i32)`는 함수가 정수 인자 2개를 받는다는 뜻이고, 스택 기반이라 `local.get 0`이 첫 번째 인자를 스택에 올리는 동작이다.
- `wasm-decompile` 출력은 `function check(a: int, b: int): int { ... }` 형태로 나와 훨씬 빠르게 읽히지만, WASM 명령어 하나하나의 정확한 의미(부호 있는/없는 나눗셈 등)를 볼 때는 `.wat`으로 다시 돌아가야 한다.

## 흔한 실수
- `.wasm`을 그냥 `strings`나 텍스트 에디터로 열어보고 "암호화됐다"고 오해하는 것 — 그냥 바이너리 포맷일 뿐이다.
- `wasm-decompile` 결과를 실제 C 소스처럼 생각해서 그대로 컴파일하려는 것 — 이 도구는 가독성용이지 `wasm2c`가 아니다.
- export 이름만 보고 함수 역할을 확신하는 것 — 이름이 `func_a`처럼 난독화되어 있으면 REV-1099의 패턴 분석이 필요하다.
- `wasm2wat`으로 만든 `.wat`을 수정한 뒤 `wat2wasm`으로 되돌리는 것을 잊고 원본 `.wasm`만 계속 들여다보며 패치 검증을 못 하는 것.

## 막혔을 때 다음 체크
- 함수 목록은 봤는데 어떤 함수가 입력 검증 로직인지 모르겠다면 → REV-1099 WASM에서 흔한 검증 로직 패턴 알아보기
- 정적으로 텍스트만 봐서는 흐름이 안 잡히면 → REV-1100 브라우저 개발자도구로 WASM 디버깅하기
- WASM 자체의 모듈/섹션 구조(Import/Function/Export/Code 섹션 등)가 먼저 헷갈리면 → REV-1097 WASM 바이너리 구조 기초(모듈/섹션)
- Ghidra에서 그래프 뷰로 직접 디스어셈블/디컴파일하고 싶다면, `nneonneo/ghidra-wasm-plugin` 확장을 설치해 Ghidra Extension으로 로드하는 방법도 있다(File → Install Extensions).

## 미니 예제
```bash
$ file chall.wasm
chall.wasm: WebAssembly (wasm) binary module version 0x1

$ npx -p wabt wasm2wat chall.wasm -o chall.wat
$ head -20 chall.wat
(module
  (type (;0;) (func (param i32 i32) (result i32)))
  (import "env" "memory" (memory (;0;) 1))
  (func $check (;0;) (type 0) (export "check") (param i32 i32) (result i32)
    local.get 1
    local.get 0
    i32.sub
    i32.const 0
    i32.eq)
```
이 예제에서 `check` 함수는 두 인자를 뺀 뒤 0과 같은지(`i32.eq`) 비교해서 결과를 돌려준다 — 즉 두 값이 같을 때 참을 반환하는 단순 비교 로직임을 텍스트만 보고 바로 파악할 수 있다.

## 관련 글
- REV-1097 — WASM 바이너리 구조 기초(모듈/섹션)
- REV-1099 — WASM에서 흔한 검증 로직 패턴 알아보기
- REV-1100 — 브라우저 개발자도구로 WASM 디버깅하기
- REV-0294 — readelf objdump nm strings 치트시트

## 출처/검증
- `wasm2wat`, `wasm-decompile`, `wasm-objdump`의 실제 커맨드라인 문법: WABT 공식 문서 wasm2wat (https://webassembly.github.io/wabt/doc/wasm2wat.1.html), WABT GitHub README (https://github.com/WebAssembly/wabt/blob/main/README.md) 기준 확인(2026-09-10).
- `npx -p wabt` 방식으로 설치 없이 실행 가능한 것: wabt npm 패키지 및 GitHub README 기준.
- Ghidra WASM 지원은 공식 내장 기능이 아니라 서드파티 확장(`nneonneo/ghidra-wasm-plugin`)으로 제공됨을 GitHub 저장소 기준으로 확인.
