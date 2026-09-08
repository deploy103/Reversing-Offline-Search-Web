---
id: REV-0405
title: "ENTER: 스택 프레임 생성 명령"
slug: "rev-0405-enter"
category: "assembly"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - enter
  - ENTER
  - enter 명령어
  - enter instruction
  - stack frame
  - 스택 프레임 생성
  - "enter 0x20, 0"
  - enter leave 짝
  - nested procedure
  - 중첩 프로시저
  - Pascal calling convention
aliases:
  - enter 뭐임
  - enter가 뭐죠
  - ENTER 명령어
  - 스택 프레임 명령어
  - enter와 push rbp 차이
symptom_keywords:
  - enter 0x20 0이 뭔지 모르겠음
  - enter 명령어가 왜 안 보이는지 모르겠음
  - push rbp mov rbp rsp 대신 enter를 쓰는 경우가 궁금함
  - 스택 프레임을 한 번에 만드는 명령어를 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ENTER size, nestlevel`은 **`PUSH RBP; MOV RBP, RSP; SUB RSP, size`를 한 명령으로 합쳐** 함수의 스택 프레임(지역 변수 공간)을 한 번에 만들어주는 명령이다. [LEAVE](rev-0073-leave.md)와 정확히 짝을 이루는 프롤로그 전용 명령이다.

## 언제 검색해야 하나
- `enter 0x20, 0` 같은 코드를 함수 시작부에서 만났는데 `push rbp`/`mov rbp, rsp` 조합과 뭐가 다른지 궁금할 때
- 컴파일러가 생성한 최적화 코드에는 이 명령이 거의 안 보이는데 특정 바이너리에서만 보여서 의아할 때
- [LEAVE](rev-0073-leave.md)와 짝을 이루는 프롤로그 명령이 무엇인지 찾고 있을 때

## 핵심 개념

### Intel 문법과 오퍼랜드
```
ENTER imm16, imm8
```
- **첫 번째 오퍼랜드(imm16)**: 지역 변수를 위해 스택에서 추가로 확보할 바이트 수(size).
- **두 번째 오퍼랜드(nestlevel, imm8)**: 중첩 프로시저 레벨(0~31). 실무 C/C++ 코드에서는 **거의 항상 0**이다.

### 실제로 하는 일 (nestlevel = 0인 일반적인 경우)
```
PUSH (E/R)BP          ; 이전 프레임 포인터 저장, RSP -= 8(64비트 기준)
MOV  (E/R)BP, (E/R)SP ; 새 프레임 포인터 설정
SUB  (E/R)SP, size     ; size 바이트만큼 지역 변수 공간 확보
```
정확히 [PUSH](rev-0044-push.md)/[MOV](rev-0039-mov.md)/[SUB](rev-0048-sub.md) 세 명령을 순서대로 실행한 것과 동일한 결과를 만든다. nestlevel이 0보다 크면(레거시 Pascal/Algol류 언어의 중첩 함수 지원용으로) 추가로 이전 프레임 포인터들을 복사하는 동작이 들어가지만, 이는 C 계열 언어 컴파일러가 사실상 전혀 쓰지 않는 기능이다.

### 플래그 변화
없음.

### 스택/RSP/RIP 변화
- RSP는 `8(RBP 저장) + size(지역 변수)` 만큼 감소한다(64비트 기준, RBP push가 8바이트).
- RBP는 새 프레임의 기준점(이 함수 안에서 지역 변수/저장된 레지스터를 가리키는 고정 기준)으로 설정된다.
- RIP는 다음 명령으로 정상 진행(분기 없음).

### 왜 컴파일러가 ENTER를 잘 안 쓰는가
[LOOP](rev-0401-loop.md)와 마찬가지 이유다 — `ENTER`는 겉보기엔 세 개 명령을 한 개로 합쳐 코드 크기를 줄여주는 것 같지만, 실제 실행 사이클 수는 `push rbp; mov rbp, rsp; sub rsp, size`를 따로 쓰는 것보다 **더 느리다.** 이 때문에 GCC/Clang/MSVC를 포함한 모든 현대 컴파일러는 최적화 여부와 무관하게 `ENTER`를 사실상 절대 생성하지 않고, 항상 풀어쓴 세 개 명령을 사용한다. 그래서 실전 릴리즈 바이너리에서 `ENTER`를 보는 일은 드물며, 다음과 같은 경우에 나타난다:
- 사람이 직접 손으로 작성한 어셈블리 코드(교육용, CTF, 셸코드)
- 매우 오래된/단순한 컴파일러(구형 Pascal, Turbo C 등) 산출물
- 디버그 옵션(`/Od` 등)에서도 실제로는 잘 쓰이지 않지만, 컴파일러 실험/특수 툴체인 산출물에서 가끔 등장

### ENTER와 LEAVE의 관계
`ENTER`가 프롤로그(함수 시작, 프레임 생성)를 담당한다면, [LEAVE](rev-0073-leave.md)는 정확히 반대인 에필로그(함수 종료, 프레임 해제)를 담당한다:
```
LEAVE  등가:  MOV RSP, RBP ;  POP RBP
```
LEAVE는 오퍼랜드가 없고 항상 "현재 RBP 기준으로 스택을 되돌리고 이전 RBP를 복원"하는 단순한 동작만 하므로, ENTER만큼 컴파일러가 기피하지 않는다 — 실제로 `push rbp; mov rbp, rsp; sub rsp, N` 프롤로그와 `LEAVE; RET` 에필로그가 섞여 있는 코드(프롤로그는 풀어쓰고 에필로그만 LEAVE 한 줄로 쓰는)가 흔하다. 즉 **ENTER는 드물어도 LEAVE는 흔하다**는 비대칭이 존재한다.

## 화면/코드에서 보이는 징후
- 함수 맨 첫 줄이 `enter 0x30, 0` — 스택 프레임 생성, 0x30(48)바이트 지역 변수 공간 확보
- nestlevel(두 번째 오퍼랜드)이 항상 0인 경우가 절대다수 — 0이 아니면 매우 이례적인 코드(레거시 언어 산출물)로 의심
- 함수 맨 끝에서 `enter`의 짝인 [LEAVE](rev-0073-leave.md) + `ret`

## 가장 먼저 할 것
1. 첫 번째 오퍼랜드(size)를 확인 → 이 함수가 스택에 확보하는 지역 변수 공간 크기
2. 두 번째 오퍼랜드(nestlevel)가 0인지 확인 → 0이 아니면 특수한 툴체인/레거시 코드 의심
3. 함수 끝에 [LEAVE](rev-0073-leave.md)가 있는지 확인 → 표준 프롤로그/에필로그 짝 여부

## 단계별 절차

**1) 일반적인 ENTER 프롤로그 해석**
```asm
func_start:
    enter 0x20, 0      ; RBP 저장 + RBP=RSP + RSP -= 0x20 (32바이트 지역변수)
    ; ... 함수 본문, [rbp-4], [rbp-8] 등으로 지역 변수 접근 ...
    leave                ; RSP=RBP, RBP 복원
    ret
```
→ 표준 `push rbp; mov rbp, rsp; sub rsp, 0x20` 프롤로그와 완전히 동일한 의미로 읽으면 된다.

**2) 풀어쓴 형태와 비교**
```asm
; ENTER 0x20, 0 과 완전히 동일:
push  rbp
mov   rbp, rsp
sub   rsp, 0x20
```
두 형태 모두 IDA/Ghidra에서는 동일하게 지역 변수 프레임으로 인식되어 `[rbp-4]` 등이 지역 변수로 자동 표시된다.

## 명령어/단축키
- IDA/Ghidra 의사코드: ENTER 프롤로그와 풀어쓴 프롤로그 모두 동일하게 지역 변수 스택 프레임으로 인식되어 `int local_4;` 같은 형태로 정리된다.
- x64dbg/GDB: `enter` 실행 직후 RBP/RSP 값을 확인하면 새 프레임 기준점이 어디로 잡혔는지 바로 검증 가능.

## 출력 해석
- ENTER 실행 직후 `RBP`는 "이 함수의 지역 변수 기준 주소"가 되고, `RSP`는 `RBP - size`가 된다.
- `[RBP - N]` 형태의 메모리 접근은 모두 이 함수의 지역 변수, `[RBP + N]`(N ≥ 0x10, 64비트 기준)은 저장된 레지스터/반환주소를 지나 호출자가 스택에 남긴 인자 영역을 가리킨다.

## 흔한 실수
- ENTER가 [LOOP](rev-0401-loop.md)처럼 반복 명령이라고 착각하는 것 — ENTER는 반복과 무관한 **일회성 스택 프레임 생성 명령**이다.
- nestlevel(두 번째 오퍼랜드)을 반복 횟수나 다른 의미로 오해하는 것 — 이는 오직 레거시 중첩 프로시저 지원을 위한 값이며, 사실상 항상 0이다.
- ENTER를 보고 항상 최적화되지 않은 디버그 빌드라고 단정하는 것 — 실제로는 최적화 여부보다 "이 코드가 어떤 컴파일러/툴체인으로 만들어졌는가"가 더 중요한 판단 기준이다. 대부분의 현대 컴파일러는 디버그 빌드에서도 ENTER를 쓰지 않는다.
- ENTER의 size가 지역 변수 개수라고 착각하는 것 — size는 **바이트 수**이며, 여러 지역 변수의 크기 합(+정렬 패딩)이다.

## 막혔을 때 다음 체크
- ENTER의 size 값이 이상하게 크면 → 큰 지역 배열/버퍼가 스택에 있을 가능성을 의심하고 함수 본문에서 `[rbp-큰오프셋]` 접근을 찾아본다.
- ENTER는 있는데 LEAVE가 안 보이면 → 함수가 여러 반환 지점을 갖고 있고, 그중 일부는 `mov rsp, rbp; pop rbp; ret`로 풀어썼을 수 있으니 모든 `ret` 직전을 확인.
- ENTER가 왜 이 바이너리에만 나오는지 궁금하면 → 컴파일러/컴파일 옵션이 특이한(구형 Pascal 계열, 특정 학습용 컴파일러 등) 바이너리일 가능성을 소스/문자열에서 추가로 확인.

## 미니 예제

**예제 1 — 지역 변수가 있는 단순 함수**
```c
int add_locals(int a, int b) {
    int sum = a + b;
    return sum;
}
```
```asm
add_locals:
    enter 0x10, 0
    mov   [rbp-4], ecx    ; a (Windows x64 기준 첫 인자)
    mov   [rbp-8], edx    ; b
    mov   eax, [rbp-4]
    add   eax, [rbp-8]
    mov   [rbp-0xc], eax  ; sum
    mov   eax, [rbp-0xc]
    leave
    ret
```

**예제 2 — 풀어쓴 형태와의 완전 동치 비교**
```asm
; 아래 두 코드는 실행 결과가 완전히 동일함
enter 0x18, 0

push  rbp
mov   rbp, rsp
sub   rsp, 0x18
```

## 관련 글
- REV-0073 — LEAVE: 함수 에필로그와 스택 프레임
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기
- REV-0401 — LOOP: 카운터 기반 반복 명령
- REV-0072 — RET: 함수 반환과 스택 변화

## 출처/검증
- ENTER 명령어의 오퍼랜드/동작(nestlevel 포함): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "ENTER—Make Stack Frame for Procedure Parameters" 섹션 기준 (2026-09-08 검증).
- ENTER가 풀어쓴 프롤로그보다 느려 현대 컴파일러가 회피하는 경향: Agner Fog, "Optimizing subroutines in assembly language" 명령어 지연시간 분석 기준.
