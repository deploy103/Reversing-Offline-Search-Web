---
id: REV-0009
title: "main 함수가 안 보일 때 찾는 방법"
slug: "rev-0009-finding-main"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["main 찾기", "main 어디", "_libc_start_main", "WinMain", "entry point", "엔트리 포인트"]
aliases: ["메인함수 안보임", "main이 없음", "메인 어디감", "main 위치"]
symptom_keywords: ["main이 안 보임", "main 함수를 못 찾겠음", "함수가 하나도 없음", "entry만 있고 main이 없음"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA/Ghidra가 자동으로 `main`이라고 이름 붙여주지 않으면, **entry point(진입점)에서 시작해 `__libc_start_main`(Linux) 또는 `WinMain`/CRT 초기화 코드(Windows)를 거쳐 실제 로직 함수까지 따라 들어가면 된다.**

## 언제 검색해야 하나
- IDA/Ghidra로 바이너리를 열었는데 Functions 창에 `main`이라는 이름의 함수가 안 보일 때
- `start` 또는 `entry`라는 함수만 보이고 그 안이 낯선 초기화 코드로 가득할 때
- stripped 바이너리라서 함수 이름이 전부 `sub_401230`처럼 자동 생성된 이름일 때

## 핵심 개념
C/C++ 프로그램이 실제로 실행을 시작하는 지점(엔트리 포인트, Entry Point)은 우리가 작성한 `main`이 아니다. 컴파일러/링커가 붙여주는 **런타임 초기화 코드**가 먼저 실행되고, 그 코드가 스택 설정, 환경변수 세팅, 힙 초기화 등을 마친 뒤에야 `main`을 호출한다.

- **Linux (ELF, glibc 동적 링킹)**: 진입점은 `_start` → `__libc_start_main` 호출 → `__libc_start_main`이 인자로 받은 함수 포인터가 바로 우리의 `main`이다.
- **Windows (PE, MSVC)**: 진입점은 `mainCRTStartup`(콘솔) 또는 `WinMainCRTStartup`(GUI) → CRT(C Runtime) 초기화 → 그 안에서 사용자 `main`/`WinMain`을 호출한다.

symbol이 남아있는(strip되지 않은) 바이너리라면 IDA/Ghidra가 이 패턴을 인식해서 자동으로 `main`이라는 이름을 붙여주지만, 이름이 지워졌거나(strip) 자동 인식이 실패하면 우리가 직접 이 경로를 따라가야 한다.

## 화면/코드에서 보이는 징후
- Functions 창(Ctrl+P)에 `main`은 없고 `start`, `entry0`, `_start`만 있음
- entry 함수 안에 `__libc_start_main` 호출이 보이는데 인자가 여러 개(레지스터/스택에 실린 함수 포인터들)
- Windows에서 `mainCRTStartup` 안에 `__scrt_common_main_seh` 같은 낯선 함수 호출들이 이어짐

## 가장 먼저 할 것
IDA에서 **Ctrl+P**(또는 Ghidra의 Symbol Tree → Functions)를 눌러 함수 목록을 열고, `entry`, `start`, `main`으로 시작하는 이름이 있는지 먼저 확인한다. 없으면 Entry Point로 바로 이동한다(IDA는 처음 열었을 때 보통 entry에 커서가 가 있다).

## 단계별 절차

**Linux ELF (동적 링킹, glibc)**

1. IDA에서 `_start` 함수를 연다(Functions 창에서 더블클릭, 또는 `Alt+G`로 특정 주소로 이동해도 됨).
2. `_start`는 보통 매우 짧고, 레지스터를 세팅한 뒤 `__libc_start_main`을 CALL한다.
3. `__libc_start_main`의 첫 번째 인자(x64 SysV 기준 **RDI**)가 바로 사용자 `main`의 주소다. IDA 디스어셈블리에서 `__libc_start_main` CALL 바로 위쪽을 보면:
   ```asm
   lea rdi, main        ; 또는 mov rdi, offset sub_401136
   ...
   call __libc_start_main
   ```
4. `rdi`에 로드되는 함수(위 예시의 `sub_401136`)를 더블클릭해서 들어간다. 이 함수를 `main`으로 리네임(**N** 키)해 두면 이후 분석이 훨씬 편해진다.
5. 만약 IDA가 `__libc_start_main`을 자동 인식하지 못했다면(정적 링킹된 바이너리), Strings 창(Shift+F12)에서 `__libc_start_main` 근처 로직을 직접 찾거나, `_start` 안의 유일한 CALL 대상을 살펴본다 — 대부분 그 CALL의 인자 중 하나가 main이다.

**Windows PE (MSVC)**

1. Entry Point로 이동(IDA는 자동으로 여기서 시작하거나, Functions 창에서 `EntryPoint`/`start` 확인).
2. `mainCRTStartup` (콘솔 앱) 또는 `WinMainCRTStartup` (GUI 앱)으로 들어간다.
3. 이 함수 안에서 `__scrt_common_main_seh` 같은 CRT 내부 함수를 호출하고, 그 안에서 결국 사용자가 작성한 `main`/`WinMain`/`wmain`을 호출한다. IDA는 대개 이 마지막 호출을 자동으로 `main`이라는 이름으로 표시해준다.
4. 자동 인식이 안 되면, CRT 초기화 함수들을 하나씩 F5(디컴파일)로 열어보며 "우리가 작성했을 법한 코드"(입력받기, 비교하기 등)가 시작되는 지점을 찾는다. CRT 코드는 대부분 매우 규칙적이고 반복적이라 낯선 라이브러리 코드임을 금방 알아챌 수 있다.

**공통: 문자열로 거꾸로 찾기 (가장 실전적인 방법)**

가장 빠른 방법은 사실 entry부터 따라가는 게 아니라, **Shift+F12(Strings 창)** 에서 `Enter password`, `flag{` 같은 문자열을 찾고, 그 문자열을 더블클릭 → **X**(Xrefs)로 이 문자열을 사용하는 함수로 바로 점프하는 것이다. 그 함수, 또는 그 함수를 호출하는 상위 함수가 사실상의 "main"인 경우가 많다.

## 명령어/단축키
- IDA: `Ctrl+P` (함수 목록), `Shift+F12` (문자열), `X` (xref), `N` (이름 바꾸기), `G` (주소로 이동)
- Linux 커맨드라인으로 미리 확인: `nm ./chall | grep ' T main'` (symbol이 남아있다면 바로 주소를 알려줌)
- `objdump -d ./chall | grep '<main>:'`

## 출력 해석
- `__libc_start_main`은 원형이 대략 `int __libc_start_main(int (*main)(int,char**,char**), int argc, char **argv, ...)`이다. 즉 **첫 번째 인자가 진짜 main 함수 포인터**라는 사실만 기억하면 된다.
- IDA가 이미 이름을 안다면 Functions 창에 `main`이 굵게 표시되고, 더블클릭하면 바로 이동한다. 이 경우 위 과정을 반복할 필요가 없다.

## 흔한 실수
- `_start`를 보고 "여기가 진짜 시작이니 여기부터 한 줄씩 다 읽어야지"라며 CRT 초기화 코드를 전부 분석하려는 것 — 시간 낭비다. `__libc_start_main`의 인자 또는 CRT 마지막 호출만 찾으면 된다.
- 정적 링킹된 바이너리에서 `__libc_start_main`이라는 이름 자체가 안 보이는데 당황하는 것 — 이 경우 심볼이 없어도 함수 패턴(레지스터 세팅 후 큰 함수 하나를 호출)은 동일하다.
- Windows에서 `main` 대신 `wmain`(유니코드 버전)이나 `WinMain`(GUI)을 찾고 있다는 걸 모르는 것 — 콘솔/GUI 여부에 따라 이름이 다르다.

## 막혔을 때 다음 체크
- entry 자체가 이상하게 짧고 바로 알 수 없는 곳으로 점프한다면 → 패킹 의심 (REV-0224).
- 함수가 아예 하나도 안 보이고 전부 `sub_`로 시작한다면 → REV-0010(stripped 바이너리에서 시작점 잡기)로 이동.
- 문자열도 임포트도 거의 없다면 → REV-0002(파일 형식 재확인), 엔트로피 확인.

## 미니 예제
```asm
; _start (일부)
lea     rdx, [rsp+8]     ; argv
mov     rsi, rax         ; argc
lea     rdi, main        ; <- 이게 진짜 main
call    __libc_start_main
```
`lea rdi, main`을 더블클릭하면 IDA가 이미 `main`이라는 이름을 붙여놓은 걸 확인할 수 있다(심볼이 남아있는 경우). 이름이 `sub_401136`처럼 보인다면 그 함수를 더블클릭해서 들어간 뒤 **N** 키로 `main`으로 직접 리네임한다.

## 관련 글
- REV-0010 — stripped 바이너리에서 시작점 잡는 방법
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0099 — _libc_start_main이 무엇이고 main을 찾는 법 (예정)
- REV-0121 — Entry Point와 WinMain 찾기 (예정)

## 출처/검증
- glibc `__libc_start_main` 시그니처: glibc 공식 소스(`csu/libc-start.c`) 기준 (2026-09-08 검증).
- MSVC CRT 시작 흐름: Microsoft Learn "CRT initialization" 문서 기준 개념 설명.
