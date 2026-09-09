---
id: REV-1070
title: "컴파일러가 인라인한 memcpy/memset이 어셈블리에서 보이는 패턴"
slug: "rev-1070-inlined-memcpy-memset-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["memcpy 인라인 어셈블리", "memset 인라인 어셈블리", "inlined memcpy assembly pattern", "REP MOVSB STOSB 최적화"]
aliases: ["memcpy가 CALL 없이 보임", "memset이 함수 호출 없이 보임", "구조체 복사 인라인"]
symptom_keywords: ["memcpy 호출인데 CALL memcpy가 안 보임", "memset인데 함수 호출 없이 mov만 나옴"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`memcpy`/`memset`의 복사·채우기 크기가 컴파일 시점에 고정된 작은 값이면 컴파일러는 함수를 호출(`CALL memcpy`)하지 않고 그 크기에 딱 맞는 `mov`(또는 `REP MOVSB`/`REP STOSB`) 명령을 코드에 직접 박아 넣는데, 이를 "인라인(inline)"이라고 하며 라이브러리 호출의 오버헤드(스택 정리, 인자 전달)를 없앤 결과다.

## 언제 검색해야 하나
- 소스에 `memcpy(dst, src, N)`이나 `memset(buf, 0, N)`이 분명히 있는데 디스어셈블리에 `CALL memcpy`/`CALL memset`이 안 보일 때
- 구조체 대입(`*a = *b;`)이나 배열 초기화(`int arr[4] = {0};`)를 했는데 함수 호출 없이 갑자기 `mov`가 여러 줄 나열되어 있을 때
- 짧은 `mov`/`movdqu` 나열이 반복적으로 나와서 이게 무슨 의도인지 못 알아볼 때
- `REP MOVSB`, `REP STOSB` 명령을 보고 이게 `memcpy`/`memset`과 어떤 관계인지 헷갈릴 때

## 핵심 개념
`memcpy(dst, src, n)`은 "src에서 n바이트를 dst로 복사"하고, `memset(buf, c, n)`은 "buf의 n바이트를 모두 c로 채운다"는 뜻이다. 컴파일러가 `n`이 **상수이고 충분히 작다**는 것을 컴파일 시점에 알면, 함수 호출 없이 그 크기만큼의 `mov`/레지스터 이동으로 직접 풀어 쓴다. 이렇게 하면 `CALL`/`RET`, 인자를 레지스터에 옮기는 준비 코드가 전부 사라지고 실행 속도도 빨라진다.

이 최적화는 구조체 대입, 배열 초기화, 작은 버퍼 복사·초기화 어디서나 자동으로 일어난다 — 프로그래머가 `memcpy`를 직접 호출하지 않아도 컴파일러가 이런 대입을 알아서 `memcpy`와 동등한 코드로 바꾸고, 그 코드를 다시 인라인하는 경우가 흔하다.

크기가 커지면(수십~수백 바이트 이상) 컴파일러는 대신 `REP MOVSB`/`REP STOSB`(REV-0080, REV-0081, REV-0082) 같은 반복 문자열 명령이나 SIMD(`movdqu` 등)로 묶어서 처리하기도 하고, 크기가 아주 크거나 런타임에만 정해지는 경우에는 결국 진짜 `CALL memcpy`/`CALL memset`으로 남는다. 즉 **크기가 작고 컴파일 시점에 고정 → 인라인, 크기가 크거나 가변적 → 라이브러리 호출 또는 REP 명령**이라는 스펙트럼이 있다.

## 화면/코드에서 보이는 징후
- 함수 호출 없이 `mov` 여러 줄이 연속으로 나열되고, 각 줄의 목적지 오프셋이 4/8씩 순서대로 증가함 — 작은 고정 크기 복사
- `mov dword [rax], 0`, `mov dword [rax+4], 0` 처럼 0을 대입하는 `mov`가 연속으로 나열 — 작은 고정 크기 채우기(memset 0)
- `rep movsb`/`rep stosb` 앞에 `mov rcx, N`(반복 횟수), `mov rdi, dst`, `mov rsi, src`(또는 `al`에 채울 값) 준비 코드 — 중간 크기 복사/채우기
- `movups`/`movdqu` 같은 SIMD 명령으로 16바이트씩 한 번에 복사 — 컴파일러/최적화 옵션에 따라 등장
- 진짜 `CALL memcpy`/`CALL memset`이 남아있다면 크기가 런타임 변수이거나 너무 커서 인라인하지 않은 경우

## 가장 먼저 할 것
연속된 `mov`(또는 `movdqu`)들이 목적지 주소가 순서대로 증가하는 패턴인지 확인한다. 그렇다면 이는 어떤 복사/초기화 작업이 인라인된 것이며, 총 몇 바이트를 다루는지(마지막 오프셋 + 크기)로 원본 `memcpy`/`memset`의 `n` 값을 역산할 수 있다.

## 단계별 절차
1. 함수 호출이 없는데 `mov`가 연속으로 여러 줄 나오는 구간을 찾는다.
2. 각 `mov`의 목적지 오프셋이 이전 줄보다 정확히 그 줄의 크기(4바이트, 8바이트 등)만큼 증가하는지 확인한다 — 순서대로 증가하면 복사/채우기의 흔적이다.
3. 소스가 되는 값이 매번 다른 메모리(`[rsi+N]`)에서 오면 `memcpy`(복사), 매번 같은 상수(주로 0)면 `memset`(채우기)으로 구분한다.
4. 마지막 오프셋에 그 줄의 크기를 더해 전체 복사/채우기 크기(원본 `n`)를 계산한다.
5. `REP MOVSB`/`REP STOSB`가 보이면 그 직전의 `RCX`(반복 횟수), `RSI`/`RDI`(원본/목적지), `AL`(채울 값, STOS의 경우) 설정 코드를 확인해 같은 정보를 얻는다.

## 명령어/단축키
- IDA: 연속된 `mov`를 선택 후 `Analysis`가 자동으로 구조체 대입/배열 초기화로 pseudocode에서 합쳐서 보여주는 경우가 많음(컴파일러 최적화 인식 기능)
- Ghidra: `Decompile` 창에서 인라인된 복사가 `*(int *)dst = *(int *)src;` 여러 줄 또는 `memset`/`memcpy` 호출로 재구성되어 보이기도 함(패턴 인식 기능)
- GDB: `x/8xb dst`로 복사/채우기 이후 실제 목적지 메모리 내용을 바이트 단위로 확인
- x64dbg: 메모리 덤프 창을 목적지 주소에 맞춰 두고 각 `mov` 실행 후 값이 채워지는 것을 실시간으로 관찰

## 출력 해석
```c
struct Vec3 { int x, y, z; };

void copy_vec3(struct Vec3 *dst, struct Vec3 *src) {
    memcpy(dst, src, sizeof(struct Vec3));  /* 12바이트, 상수 크기 */
}

void zero_buf(int *buf) {
    memset(buf, 0, 16);   /* 16바이트, 상수 크기 */
}
```

```asm
; copy_vec3, rdi = dst, rsi = src   (12바이트라서 8+4로 나눠 복사)
copy_vec3:
    mov     rax, [rsi]        ; src의 앞 8바이트(x, y) 읽기
    mov     [rdi], rax        ; dst의 앞 8바이트에 쓰기
    mov     eax, [rsi+8]      ; src의 나머지 4바이트(z) 읽기
    mov     [rdi+8], eax      ; dst의 나머지 4바이트에 쓰기
    ret                       ; *** CALL memcpy 없음: 8+4바이트로 직접 인라인 ***

; zero_buf, rdi = buf   (16바이트를 8+8로 나눠 0으로 채움)
zero_buf:
    mov     qword [rdi], 0     ; buf[0..7] = 0
    mov     qword [rdi+8], 0   ; buf[8..15] = 0
    ret                        ; *** CALL memset 없음: 0을 직접 두 번 씀 ***
```

`copy_vec3`은 12바이트를 "8바이트 한 번 + 4바이트 한 번"으로 나눠 복사한다 — 레지스터가 8바이트 단위로 움직이는 게 가장 효율적이기 때문에 크기를 이렇게 쪼갠다. `zero_buf`는 16바이트를 0으로 채우는데 `mov qword [...], 0`을 두 번 쓰는 것으로 끝난다. 둘 다 함수 호출이 전혀 없고, 원본 코드의 `memcpy`/`memset` 호출은 흔적도 없이 사라졌지만 **동작은 완전히 동일**하다.

## 흔한 실수
- 연속된 `mov`를 각각 독립된 대입 연산으로 오해하고, 사실은 하나의 `memcpy`/`memset` 호출이 쪼개진 것임을 놓치는 것.
- `mov qword [...], 0`이 반복되는 것을 보고 "많은 지역변수를 각각 초기화하는 코드"로 착각하는 것 — 실제로는 하나의 버퍼를 한 번에 0으로 채우는 `memset(..., 0, ...)`일 수 있다.
- `REP MOVSB`/`REP STOSB`를 보고 "이건 문자열 명령이니 문자열 처리다"라고 단정하는 것 — 임의의 바이트 복사/채우기(구조체, 배열 등)에도 똑같이 쓰인다.
- 인라인된 코드에서 원본 `n`(복사/채우기 크기)을 계산할 때 오프셋을 잘못 더해 실제 크기보다 크거나 작게 추정하는 것 — 마지막 `mov`의 오프셋 + 그 `mov`가 다루는 바이트 수를 정확히 더해야 한다.

## 막혔을 때 다음 체크
- 구조체 필드 오프셋 계산 자체가 헷갈리면 → REV-1061 중첩 구조체 접근이 어셈블리에서 보이는 패턴, REV-0035 구조체 접근이 어셈블리로 변하는 방식
- REP 계열 명령의 기본 동작이 궁금하면 → REV-0080 REP Prefix와 반복 문자열 명령, REV-0081 MOVS 계열, REV-0082 STOS 계열
- 진짜 라이브러리 호출(`CALL memcpy`)이 남아있는 경우의 인자 전달 규칙이 궁금하면 → REV-0071 CALL: 함수 호출, 반환 주소, 인자 추적
- 함수 인라인 일반론(memcpy/memset뿐 아니라 모든 함수에 적용되는 인라인 개념)이 궁금하면 → REV-0357 함수 인라인이 코드 흐름에 미치는 영향, REV-1079(예정) 매크로/인라인 함수가 CALL 없이 전개되는 패턴

## 미니 예제
크기가 커지면 같은 `memcpy`가 `REP MOVSB`로 바뀌는 예(개념 예시, 크기가 런타임 변수인 경우):
```asm
; memcpy(dst, src, n)  n이 변수일 때
mov     rcx, n      ; 반복 횟수 = n
mov     rsi, src    ; 원본 시작
mov     rdi, dst    ; 목적지 시작
rep     movsb        ; rcx번 반복하며 [rsi]->[rdi] 복사, 매 반복마다 rsi/rdi 자동 +1
```
크기가 상수라 인라인된 `mov` 나열과, 크기가 변수라 `REP MOVSB`로 처리된 코드는 결과는 같지만 겉모습이 완전히 다르다. 어느 쪽이든 "함수 호출 없이 메모리 복사/채우기가 일어난다"는 공통점으로 `memcpy`/`memset`의 흔적임을 알아챌 수 있다.

## 관련 글
- REV-1061 — 중첩 구조체 접근이 어셈블리에서 보이는 패턴
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0081 — MOVS MOVSB MOVSW MOVSD MOVSQ
- REV-0082 — STOS STOSB STOSD STOSQ
- REV-0357 — 함수 인라인이 코드 흐름에 미치는 영향
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `memcpy`/`memset`의 표준 동작(바이트 단위 복사/채우기)과 크기가 컴파일 시점 상수일 때 컴파일러가 이를 인라인할 수 있다는 최적화 규칙: ISO C 표준 라이브러리(`<string.h>`) 및 GCC 공식 문서(builtin memcpy/memset 최적화 설명) 기준.
- gcc/clang이 작은 고정 크기 `memcpy`/`memset`을 함수 호출 없이 `mov` 나열로, 중간 크기는 `REP MOVSB`/`STOSB`로 대체하는 패턴은 x86-64 리눅스/윈도우 환경에서 반복 확인되는 표준 최적화 패턴이다(2026-09-10 검증).
