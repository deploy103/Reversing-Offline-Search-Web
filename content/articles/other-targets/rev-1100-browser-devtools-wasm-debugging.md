---
id: REV-1100
title: "브라우저 개발자도구로 WASM 디버깅하기"
slug: "rev-1100-browser-devtools-wasm-debugging"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: ["WASM"]
format: ["WASM"]
tools: [wabt]
keywords: ["Chrome DevTools WASM", "wasm 디버깅", "wasm 브레이크포인트", "DWARF wasm", "브라우저 wasm debugger"]
aliases: ["크롬 개발자도구로 wasm 디버깅", "wasm 실행 중 값 확인", "wasm breakpoint 거는 법"]
symptom_keywords: ["wasm 코드를 정적으로만 봐서는 값이 안 나옴", "wasm이 실행되는 순간 값을 보고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Chrome/Firefox 개발자도구의 Sources 탭은 `.wasm` 모듈을 자동으로 WAT(WebAssembly Text) 형식으로 디스어셈블해 보여주고, JS 코드처럼 그 위에 줄 단위 브레이크포인트를 걸어 스택/로컬 변수 값을 실시간으로 관찰할 수 있어, REV-1099의 정적 분석만으로 막힌 검증 로직을 실행하며 확인할 때 가장 확실한 방법이다.

## 언제 검색해야 하나
- REV-1098/1099로 `.wat`을 읽었지만 반복 연산이 몇 바퀴 도는지, 특정 시점의 로컬 변수 값이 무엇인지 손으로 계산하기 번거로울 때
- WASM이 웹 페이지 안에서 JS와 상호작용하며 동작해서, 정적 파일만 봐서는 호출 순서/타이밍을 알 수 없을 때
- "input을 넣었을 때 실제로 어떤 값이 비교되는지" 직접 눈으로 확인하고 싶을 때

## 핵심 개념

### 브라우저가 WASM을 자동으로 디스어셈블해준다
Chrome DevTools는 오래전부터(2019년 개선판 기준) `.wasm` 모듈을 로드하면 Sources 패널에 자동으로 사람이 읽을 수 있는 디스어셈블 텍스트(WAT과 유사한 형식)를 표시해왔다. 별도로 `wasm2wat`을 돌리지 않아도 브라우저 안에서 바로 코드를 볼 수 있고, 여기에 JS 코드처럼 줄 번호 옆을 클릭해 브레이크포인트를 걸 수 있다.

### DWARF 디버그 정보가 있으면 원본 소스로도 디버깅 가능
C/C++/Rust로 작성된 뒤 Emscripten 등으로 컴파일된 WASM에 `-g` 옵션으로 DWARF 디버그 정보가 포함되어 있으면, Chrome DevTools는 컴파일된 WASM 대신 원본 C/C++/Rust 소스 코드 자체를 Sources 탭에 보여주고, 그 소스 줄에 브레이크포인트를 걸 수 있다. 이를 위해서는 별도로 "C/C++ DevTools Support (DWARF)" 확장을 설치해야 하는 경우가 많다. 다만 CTF에서 배포되는 문제 파일은 최적화·strip된 릴리스 빌드가 많아 DWARF 정보가 빠져 있는 경우가 흔하고, 이때는 자동 디스어셈블된 WAT 형식으로 디버깅하게 된다.

### 디스어셈블 뷰에서 할 수 있는 것
DWARF가 없어도 Chrome DevTools의 디스어셈블 텍스트 뷰에서 다음이 모두 가능하다.
- 특정 명령어 줄에 브레이크포인트 설정
- Step Into/Over/Out으로 한 명령어씩 실행
- Scope 패널에서 현재 함수의 로컬 변수(local) 값 확인
- Call Stack 패널에서 호출 스택 확인
- Console에서 값 조회

### Firefox도 유사한 기능 제공
Firefox 개발자도구 역시 Debugger 패널에서 `.wasm` 모듈을 텍스트 형식으로 보여주고 브레이크포인트를 지원한다. CTF 환경에서는 Chrome/Chromium 계열이 더 널리 쓰이므로 이 글은 Chrome 기준으로 설명한다.

## 화면/코드에서 보이는 징후
- 브라우저 개발자도구 Sources 탭 좌측 파일 트리에 `wasm://...` 형태의 항목이 나타남
- 클릭하면 JS 코드 대신 `(module ... (func $check ...))` 형태의 텍스트가 보임(디스어셈블 뷰)
- 우클릭 또는 줄 번호 클릭으로 빨간 점(브레이크포인트) 표시 가능
- 브레이크포인트에 걸리면 우측 패널에 Scope > Locals, Call Stack이 표시됨

## 가장 먼저 할 것
문제 페이지를 Chrome에서 열고 `F12`(개발자도구)를 누른 뒤 Sources 탭에서 좌측 파일 트리를 펼쳐 `.wasm` 관련 항목을 찾는다. 없다면 Network 탭에서 `.wasm` 요청을 확인해 로드 자체가 되는지부터 점검한다.

## 단계별 절차
1. 문제 웹페이지를 Chrome에서 열고 개발자도구(`F12` 또는 `Ctrl+Shift+I`)를 연다
2. Sources 탭 좌측 트리에서 `.wasm` 관련 파일(도메인 아래 `wasm://` 또는 스크립트 트리 안)을 찾아 클릭
3. 디스어셈블된 텍스트가 보이면 REV-1099에서 지목한 후보 함수(예: `check`)를 찾아 스크롤
4. 비교 연산(`i32.eq` 계열) 직전 줄 번호를 클릭해 브레이크포인트 설정
5. 페이지에서 실제로 입력값을 넣고 "확인" 버튼 등을 눌러 실행을 트리거
6. 브레이크포인트에 멈추면 우측 Scope 패널에서 로컬 변수 값을 확인하고, Step Over(`F10`)로 한 줄씩 진행하며 값 변화를 관찰
7. Console 패널에서 현재 스코프의 변수를 직접 조회하거나 표현식을 평가해볼 수도 있음

## 명령어/단축키
| 동작 | 단축키(Chrome, Windows/Linux 기준) |
|---|---|
| 개발자도구 열기 | `F12` 또는 `Ctrl+Shift+I` |
| 브레이크포인트에서 재개 | `F8` |
| Step Over | `F10` |
| Step Into | `F11` |
| Step Out | `Shift+F11` |
| 조건부 브레이크포인트 | 줄 번호 우클릭 → Add conditional breakpoint |

## 출력 해석
브레이크포인트에 멈췄을 때 Scope 패널의 `Locals`에는 현재 함수의 지역변수(WASM `local`)들이 `$0`, `$1` 또는 소스 정보가 있으면 원래 이름으로 표시된다. Call Stack에는 JS에서 `instance.exports.check(...)`를 호출한 지점까지의 전체 호출 흐름이 나오므로, WASM 함수가 어떤 JS 이벤트(버튼 클릭 핸들러 등)에서 어떤 인자로 호출됐는지 역추적할 수 있다.

## 흔한 실수
- 개발자도구를 페이지 로드 이후에 열어서 초기 브레이크포인트를 놓치는 것 — 필요하다면 새로고침(`Ctrl+R`) 후 다시 트리거해야 한다.
- 최적화된 릴리스 빌드에 DWARF가 없는데 "소스 코드가 안 보인다"고 당황하는 것 — 디스어셈블 텍스트 뷰만으로도 브레이크포인트/스텝 실행은 충분히 가능하다.
- Step Into를 남발해 WASM 런타임 내부(메모리 관리 등)까지 깊이 들어가 버려서 원래 보려던 함수를 놓치는 것 — Step Over 위주로 진행하다가 필요한 함수에서만 Step Into 하는 것이 효율적이다.
- 콘솔에서 값을 볼 때 WASM의 `i32`/`i64` 값과 JS 숫자 타입 간 차이(64비트 정수는 BigInt로 표시)를 혼동하는 것.

## 막혔을 때 다음 체크
- WASM 텍스트 자체를 미리 오프라인에서 훑어보고 싶다면 → REV-1098 wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- 어떤 함수가 검증 로직인지부터 감이 안 잡히면 → REV-1099 WASM에서 흔한 검증 로직 패턴 알아보기
- WASM이 아니라 페이지의 일반 JS 로직 자체를 디버깅해야 한다면 이 글의 범위 밖 — 일반 JS 브레이크포인트 디버깅으로 접근

## 미니 예제
Sources 탭에서 디스어셈블 뷰는 대략 다음처럼 보인다(실제 Chrome 표시 형식은 버전에 따라 약간 다를 수 있음).
```
$check (param $ptr i32) (param $len i32) (result i32)
  001: local.get $ptr
  002: local.get 0
  003: i32.add
  004: i32.load8_u
  ...
  012: i32.eq          ← 여기에 브레이크포인트
  013: return
```
012번 줄에 브레이크포인트를 걸고 Step Over 없이 바로 재개하면, 멈춘 시점의 Scope 패널에서 스택 맨 위 두 값(비교 직전 값)을 확인할 수 있어 REV-1099에서 손으로 계산하던 것을 실행 결과로 바로 검증할 수 있다.

## 관련 글
- REV-1098 — wasm2wat/wasm-decompile로 WASM을 텍스트로 바꾸기
- REV-1099 — WASM에서 흔한 검증 로직 패턴 알아보기
- REV-1097 — WASM 바이너리 구조 기초(모듈/섹션)

## 출처/검증
- Chrome DevTools가 `.wasm`을 자동으로 디스어셈블 텍스트로 보여주고 브레이크포인트/스텝 실행을 지원하는 기능: Chrome for Developers 공식 문서 - Debug C/C++ WebAssembly (https://developer.chrome.com/docs/devtools/wasm), Improved WebAssembly debugging in Chrome DevTools (2019) (https://developer.chrome.com/blog/wasm-debugging-2019) 기준 확인(2026-09-10).
- DWARF 기반 원본 소스 디버깅(Emscripten/Clang `-g` 옵션, C/C++ DevTools Support 확장 필요)은 위 Chrome for Developers 공식 문서 기준.
