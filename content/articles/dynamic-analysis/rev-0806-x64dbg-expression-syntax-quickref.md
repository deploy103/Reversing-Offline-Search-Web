---
id: REV-0806
title: "x64dbg 표현식(Expression) 문법 빠른 참조"
slug: "rev-0806-x64dbg-expression-syntax-quickref"
category: "dynamic-analysis"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["x64dbg expression", "x64dbg 표현식 문법", "mem.valid", "mod.base", "byte dword qword 함수", "x64dbg 함수 표현식", "x64dbg 연산자"]
aliases: ["x64dbg 표현식 사전", "x64dbg 문법 참조표", "x64dbg 함수 목록", "x64dbg expression functions"]
symptom_keywords: ["x64dbg 조건식이 원하는 대로 안 먹힘", "x64dbg에서 숫자가 이상하게 해석됨", "x64dbg mem.valid가 뭔지 모름", "x64dbg 표현식에 함수를 어떻게 쓰는지 모름", "x64dbg 메모리 값을 표현식으로 읽고 싶음"]
source_ids: ["SRC-X64DBG-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
x64dbg의 모든 입력창(Break condition, Go to, 명령줄, 워치 등)은 C와 비슷하지만 **숫자는 기본 16진수**, **메모리 접근은 `[ ]`**, **크기 지정 읽기는 `byte()`/`word()`/`dword()`/`qword()`**, 그리고 `mem.`/`mod.`/`src.`/`func.`/`ref.`/`dis.` 접두사가 붙은 전용 함수들로 구성된 하나의 통일된 "표현식 문법"을 공유한다.

## 언제 검색해야 하나
- Break condition, Log text, 명령줄 등 어디에 입력해도 되는 표현식 문법이 헷갈릴 때
- `mem.valid(EAX)` 같은 함수가 정확히 뭘 하는지 몰라서 조건식을 못 만들 때
- 10진수를 넣었는데 값이 다르게 평가돼서 원인을 모를 때
- 메모리 특정 위치에서 1/2/4/8바이트를 각각 읽는 표현식이 뭔지 찾을 때
- 모듈 베이스, RVA, 소스 라인 번호 등을 표현식으로 얻고 싶을 때

## 핵심 개념

### 숫자 리터럴
- 기본값은 **16진수**다. `100`은 0x100(십진수 256)이다.
- 10진수를 쓰려면 앞에 `.`을 붙인다. `.100`은 십진수 100이다.
- `0x` 접두사도 16진수로 인식된다.

### 레지스터와 메모리 역참조
- 레지스터는 이름 그대로 쓴다. `EAX`, `RAX`, `RSP`, `RIP` 등.
- 대괄호 `[ ]`는 "그 주소가 가리키는 메모리 값을 읽어라"는 뜻이다. `[rsp]`, `[rbp-8]`, `[rax+10]` 모두 가능하다.
- 기본 역참조 크기는 플랫폼 비트수(x86은 4바이트, x64는 8바이트)를 따른다. 특정 크기를 강제하려면 아래의 크기 지정 함수를 쓴다.

### 연산자
```text
+  -  *  /  %          산술 연산자
== != < > <= >=        비교 연산자 (참=1, 거짓=0)
&& ||                  논리 AND / OR
&  |  ^  ~             비트 AND / OR / XOR / NOT
<< >>                  시프트
```

### 크기 지정 메모리 읽기 함수
| 함수 | 읽는 크기 | 비고 |
|---|---|---|
| `byte(addr)` / `Byte(addr)` / `ReadByte(addr)` | 1바이트 | |
| `word(addr)` / `Word(addr)` | 2바이트 | |
| `dword(addr)` / `Dword(addr)` | 4바이트 | |
| `qword(addr)` / `Qword(addr)` | 8바이트 | x64 전용 |
| `ptr(addr)` / `Pointer(addr)` | 4/8바이트 | 현재 비트수에 맞는 포인터 크기 |

이 함수들은 주소가 유효하지 않으면 에러 대신 **0을 반환**하므로, `[addr]`로 직접 역참조했을 때 무효 주소에서 에러가 나는 상황(예: 조건부 브레이크포인트 평가 중)을 피하려면 이 함수들을 쓰는 것이 안전하다.

### mem. — 메모리 정보 함수
| 함수 | 의미 |
|---|---|
| `mem.valid(addr)` | addr이 유효한(매핑된) 메모리 주소인지 |
| `mem.base(addr)` | addr이 속한 메모리 페이지의 시작 주소 |
| `mem.size(addr)` | addr이 속한 메모리 페이지의 크기 |
| `mem.iscode(addr)` | addr이 실행 가능한 페이지에 있는지 |
| `mem.decodepointer(ptr)` | `DecodePointer` API와 동일한 디코딩(Vista 이상) |

### mod. — 모듈 정보 함수
| 함수 | 의미 |
|---|---|
| `mod.base(addr)` | addr이 속한 모듈의 베이스 주소 |
| `mod.main()` | 메인 모듈(디버기)의 베이스 주소 |
| `mod.rva(addr)` | addr의 RVA(모듈 베이스 기준 상대 주소) |
| `mod.offset(addr)` | addr의 파일 오프셋 |
| `mod.isexport(addr)` | addr이 모듈의 export 함수인지 |
| `mod.fromname(str)` | 문자열로 지정한 모듈의 베이스 주소, 못 찾으면 0 |
| `mod.party(addr)` | 0=사용자 모듈, 1=시스템 모듈 |

### src. / func. / ref. / dis. — 그 외 전용 함수
| 함수 | 의미 |
|---|---|
| `src.line(addr)` | addr에 대응하는 소스 라인 번호 |
| `func.start(addr)` / `func.end(addr)` | addr이 속한 함수의 시작/끝 주소 |
| `ref.count()` | 현재 References 뷰의 항목 수 |
| `ref.addr(index)` | References 뷰 index번째 항목의 주소 |
| `dis.len(addr)` | addr에 있는 명령어의 길이(바이트 수) |
| `dis.iscond(addr)` | addr의 명령어가 조건부 분기인지 |
| `dis.isbranch(addr)` | addr의 명령어가 분기(jcc/call 등)인지 |
| `tid()` | 현재 스레드 ID |
| `isdebuggerfocused()` / `isdebuggeefocused()` | x64dbg / 디버기 창이 포커스 상태인지 |

## 화면/코드에서 보이는 징후
이 문법은 화면 어딘가에 그대로 노출되는 것이 아니라, Break condition, Log text, 명령줄, "Go to Expression" 대화상자처럼 값을 직접 입력해야 하는 모든 창에서 요구된다. 잘못된 문법을 입력하면 x64dbg는 보통 표현식을 "항상 참(1)"으로 취급하거나 명령 실행에 실패한다.

## 가장 먼저 할 것
지금 만들려는 조건이 "값 비교"인지 "메모리 접근"인지 "함수 호출"인지부터 구분한다. 값 비교면 레지스터/숫자 리터럴과 비교 연산자만으로 충분하고, 메모리 상태를 확인해야 하면 `mem.*` 함수, 모듈/심볼 위치가 필요하면 `mod.*` 함수를 먼저 찾아본다.

## 단계별 절차

**1) 단순 값 비교**
```text
EAX == .100
```
EAX가 10진수 100일 때 참.

**2) 메모리 값 비교(크기 명시)**
```text
dword(rsp+8) == 0xdeadbeef
```

**3) 유효하지 않은 주소에서 에러 방지**
```text
mem.valid(rax) && dword(rax) == 1
```
`mem.valid`를 앞에 두어 rax가 유효할 때만 뒤의 `dword(rax)`를 평가하도록 한다(단축 평가).

**4) 특정 모듈 안에 있는지 확인**
```text
mod.base(cip) == mod.fromname("ntdll.dll")
```

**5) 특정 스레드에서만 참**
```text
tid() == 0x1a04
```

## 명령어/단축키
```text
[ADDR]                 메모리 역참조(기본 크기)
byte()/word()/dword()/qword()/ptr()   크기 지정 메모리 읽기
mem.valid/mem.base/mem.size/mem.iscode
mod.base/mod.main/mod.rva/mod.offset/mod.isexport/mod.fromname/mod.party
src.line
func.start/func.end
ref.count/ref.addr
dis.len/dis.iscond/dis.isbranch
tid()
isdebuggerfocused()/isdebuggeefocused()
```

## 출력 해석
표현식 평가 결과는 항상 하나의 정수 값(참/거짓 포함)이다. 대화상자나 명령줄에서 표현식이 받아들여지면 그 값이 그대로 사용되고, 문법 오류가 있으면 x64dbg가 "Invalid expression" 계열의 오류를 보여주거나 Break condition의 경우 조건을 항상 참으로 처리해 매번 멈추는 형태로 문제가 드러난다.

## 흔한 실수
- 10진수 값을 그대로 써서(`EAX==100`) 16진수 0x100(256)으로 해석되는 것 — 10진수는 반드시 `.100`처럼 마침표를 붙여야 한다.
- `[addr]`로 직접 역참조했다가 addr이 무효 주소일 때 표현식 평가 자체가 실패하는 것 — `mem.valid()`로 먼저 걸러주거나 `dword()` 계열 함수(무효 시 0 반환)를 쓰는 것이 안전하다.
- `mod.rva()`와 `mod.offset()`을 혼동하는 것 — RVA는 모듈이 메모리에 로드된 기준의 상대 주소이고, offset은 디스크 파일 기준 오프셋이라 값이 다를 수 있다.
- 크기 지정 함수 없이 `[addr]`만 쓰고 "왜 4바이트인지 8바이트인지 원하는 대로 안 나오지"라고 헷갈리는 것 — 원하는 크기를 항상 `byte`/`word`/`dword`/`qword`로 명시하는 습관이 안전하다.

## 막혔을 때 다음 체크
- 이 문법을 실제 Break condition에 어떻게 조합해서 쓰는지 레시피가 필요하면 → REV-0808 x64dbg 조건부 브레이크포인트 문법 참조.
- Edit breakpoint 대화상자를 여는 법 등 기초 사용법이 궁금하면 → REV-0183 x64dbg 조건부 Breakpoint 기초.
- GDB 쪽의 비슷한 표현식/포맷 문법이 궁금하면 → REV-0807 GDB 표현식/포맷 지정자(x/nfu) 빠른 참조.

## 미니 예제
```text
목표: rcx가 가리키는 문자열 버퍼의 첫 4바이트가 "flag"의 처음 4글자(0x67616c66, 리틀엔디언)와 같을 때만 참

표현식:
mem.valid(rcx) && dword(rcx) == 0x67616c66
```
`mem.valid(rcx)`가 먼저 rcx가 유효한 메모리인지 확인하고, 참일 때만 `dword(rcx)`로 4바이트를 읽어 비교한다. 순서를 반대로 하면 rcx가 무효할 때 `dword(rcx)`가 먼저 평가되어 문제가 생길 수 있다.

## 관련 글
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0808 — x64dbg 조건부 브레이크포인트 문법 참조
- REV-0807 — GDB 표현식/포맷 지정자(x/nfu) 빠른 참조
- REV-0178 — x64dbg Breakpoint 설정과 삭제

## 출처/검증
- 숫자 리터럴 기본 16진수/`.` 접두 10진수 표기, 레지스터/메모리 역참조 문법, 연산자 목록: x64dbg 공식 문서(help.x64dbg.com) Expressions 페이지 기준.
- `mem.*`, `mod.*`, `src.*`, `func.*`, `ref.*`, `dis.*`, `byte()`/`word()`/`dword()`/`qword()`/`ptr()`, `tid()`, `isdebuggerfocused()` 등 표현식 함수 목록과 설명: x64dbg 공식 문서 Expression Functions 페이지 기준 (2026-09-09 조사, 원문 확인).
