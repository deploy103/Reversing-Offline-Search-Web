---
id: REV-0010
title: "stripped 바이너리에서 시작점 잡는 방법"
slug: "rev-0010-stripped-entry-point"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, readelf]
keywords: ["stripped", "strip", "심볼 없음", "entry point", "시작점 잡기"]
aliases: ["스트립됨", "심볼이 다 사라짐", "함수 이름이 다 sub_", "stripped 바이너리"]
symptom_keywords: ["함수 이름이 전부 sub_로 시작함", "심볼이 없음", "이름이 하나도 없음"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
stripped 바이너리는 함수 **이름**만 없을 뿐 함수 **경계와 진입점 구조는 그대로** 남아있으므로, ELF 헤더의 Entry Point 주소부터 시작해 IDA/Ghidra의 자동 함수 탐지와 호출 패턴을 근거로 `main`을 역추적하면 된다.

## 언제 검색해야 하나
- IDA/Ghidra의 Functions 창에 `main`, `printf` 같은 이름이 하나도 없고 전부 `sub_401230`, `FUN_00401230` 형태일 때
- `nm ./chall` 실행 시 `no symbols`라고 나올 때
- 문제 설명에 "stripped binary"라고 명시되어 있을 때

## 핵심 개념
"strip"이란 컴파일된 바이너리에서 **심볼 테이블(함수/변수 이름 정보)** 을 제거하는 작업이다(`strip ./binary` 명령으로 수행). 심볼 테이블은 디버깅과 분석 편의를 위한 부가 정보일 뿐, **실행에는 필요 없다.** 그래서 배포용 바이너리는 흔히 strip되어 있다.

중요한 점: **strip해도 코드 자체와 실행 흐름은 전혀 바뀌지 않는다.** 다음은 그대로 남아있다:
- ELF Header의 `e_entry` 필드 (진입점 주소) — 이건 심볼이 아니라 헤더의 고정 필드라서 strip으로 지워지지 않는다.
- 함수 호출(CALL) 관계, 즉 콜 그래프 구조.
- PE의 경우 `AddressOfEntryPoint` 필드(Optional Header)도 마찬가지로 남는다.

즉 strip은 "이름표"를 뗀 것이지 "건물"을 부순 게 아니다. IDA/Ghidra는 이름이 없어도 코드 패턴(함수 프롤로그 `push rbp; mov rbp, rsp` 등)을 분석해서 함수 경계를 자동으로 찾아내고 `sub_XXXXXX`라는 임시 이름을 붙여준다.

## 화면/코드에서 보이는 징후
- Functions 창의 모든 항목이 `sub_` 또는 `FUN_`으로 시작
- `nm ./chall` → `nm: no symbols`
- `file ./chall` 결과에 `not stripped` 대신 `stripped`라고 표시됨 (최근 `file` 버전 기준)

## 가장 먼저 할 것
IDA/Ghidra에 로드했을 때 커서가 자동으로 위치하는 **Entry Point**를 확인한다. IDA는 파일을 열면 기본적으로 entry 주소에서 시작한다. 여기서부터 REV-0009와 동일한 방식(`__libc_start_main` 인자 추적 / CRT 초기화 추적)으로 main을 찾는다.

## 단계별 절차

**1) 헤더에서 진입점 주소를 먼저 확인 (도구 없이도 가능)**

Linux:
```bash
readelf -h ./chall | grep Entry
```
출력 예:
```
  Entry point address:               0x1060
```

Windows PE (PE-bear 또는 objdump):
```bash
objdump -f ./chall.exe | grep start
```

**2) IDA/Ghidra에서 해당 주소로 이동**

IDA에서 **G** 키(Jump to address) → 위에서 확인한 주소 입력. 자동으로 이미 그 함수 안에 있는 경우가 많다(IDA가 처음 로드 시 entry로 이동해주기 때문).

**3) 함수 경계 자동 인식 확인**

strip되어도 IDA/Ghidra는 대부분 함수 프롤로그 패턴(`push rbp` / `sub rsp, N` / `endbr64`)을 인식해서 함수 단위로 잘라준다. Functions 창(Ctrl+P)에 `sub_` 이름의 함수가 여러 개 나열되어 있다면 자동 탐지가 정상 동작 중인 것이다.

**4) main 후보 찾기 (REV-0009와 동일한 로직)**
- Linux: entry(`sub_1060` 등) 안에서 유일하게 큰 CALL 대상(`__libc_start_main`에 해당하는 함수, 심볼 없어도 라이브러리 코드 특유의 복잡한 패턴으로 구분 가능)을 찾고, 그 직전에 레지스터(RDI)에 로드되는 함수 주소를 따라간다.
- Windows: CRT 시작 루틴 특유의 반복적인 초기화 코드를 눈에 익히고, 그 끝에서 사용자 코드로 보이는 함수(문자열 참조, scanf류 호출이 있는 함수)로 진입한다.

**5) 문자열 기반 역추적을 병행 (가장 빠른 지름길)**

strip된 바이너리라도 문자열 자체는 지워지지 않는다(strip은 심볼 테이블만 지운다). Shift+F12로 문자열을 보고, `flag`, `correct`, `wrong` 등을 찾아 Xref(X)로 참조 함수로 바로 이동하면, entry부터 한 단계씩 내려가는 것보다 훨씬 빠르게 핵심 함수에 도달할 수 있다.

**6) 리네임으로 흔적 남기기**

main으로 추정되는 함수를 찾으면 바로 **N**으로 `main`이라고 리네임해 둔다. 이후 이 함수를 호출/참조하는 다른 곳에서도 이름이 바뀐 채로 보여서 분석이 누적된다.

## 명령어/단축키
```bash
readelf -h ./chall | grep Entry
nm ./chall            # "no symbols" 확인용
file ./chall          # stripped 여부 표시
```
IDA: `G`(주소 이동), `Ctrl+P`(함수 목록), `Shift+F12`(문자열), `X`(xref), `N`(리네임)

## 출력 해석
- `nm: ./chall: no symbols`는 심볼 테이블이 완전히 제거되었다는 뜻. 함수는 여전히 존재하지만 이름 정보가 없을 뿐이다.
- IDA에서 함수가 `sub_401136`으로 보여도 인자 개수, 호출 관계, 참조하는 문자열은 전부 정확하다 — 이름만 없을 뿐 분석 자체에는 지장이 없다.

## 흔한 실수
- "stripped니까 분석이 불가능하다"고 오해하는 것 — 이름만 없을 뿐 구조 분석은 100% 가능하다.
- entry point를 못 찾아서 파일 전체를 처음부터 스크롤하며 찾으려는 것 — 헤더에 정확한 주소가 명시되어 있으니 그걸 이용한다.
- 정적 링킹된 stripped 바이너리에서 `__libc_start_main`류 함수까지 전부 이름이 없어서 라이브러리 코드와 사용자 코드를 구분 못 하는 것 — 이럴 땐 IDA의 FLIRT 시그니처(자동 라이브러리 함수 인식) 결과를 참고하거나, 문자열 기반 역추적을 우선한다.

## 막혔을 때 다음 체크
- FLIRT가 라이브러리 함수를 인식하지 못해 구분이 안 되면 → 문자열 기반 역추적(REV-0008 참고)으로 전환.
- entry point 자체가 정상적인 CRT 패턴이 아니라 이상한 곳으로 바로 점프한다면 → 패킹 의심(REV-0224).
- 그래도 안 되면 동적 분석으로 전환: 디버거로 실행 후 `scanf`/`read` 같은 표준 함수 CALL에 브레이크포인트를 걸어 역방향으로 호출자를 추적한다.

## 미니 예제
```bash
$ file chall
chall: ELF 64-bit LSB pie executable, x86-64, ..., stripped

$ nm chall
nm: chall: no symbols

$ readelf -h chall | grep Entry
  Entry point address:               0x1060
```
IDA에서 `G` → `1060` 입력(PIE라서 실제 로드 주소는 다를 수 있지만 IDA 내부에서는 이 상대 주소를 그대로 쓴다) → entry 함수 진입 → 그 안의 유일한 CALL을 따라 들어가 `main` 후보를 찾는다.

## 관련 글
- REV-0009 — main 함수가 안 보일 때 찾는 방법
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이 (예정)
- REV-0154 — IDA에서 함수 경계가 잘못 잡혔을 때 (예정)

## 출처/검증
- `strip(1)`, `nm(1)`, `readelf(1)` GNU binutils man page 기준 (2026-09-08 검증).
- IDA FLIRT 시그니처 개념: Hex-Rays 공식 문서 "Fast Library Identification and Recognition Technology" 설명 기준.
