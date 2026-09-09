---
id: REV-1064
title: "구조체 배열 순회가 어셈블리에서 보이는 패턴"
slug: "rev-1064-struct-array-traversal-asm-pattern"
category: "c-analysis"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["구조체 배열 순회 어셈블리", "struct array traversal assembly pattern", "IMUL 구조체 크기", "구조체 배열 인덱싱"]
aliases: ["구조체 배열 for문 어셈블리", "구조체 크기 곱셈 오프셋", "array of struct asm"]
symptom_keywords: ["구조체 배열 순회에서 IMUL이 왜 나오는지 모름", "구조체 크기가 이상한 수로 곱해짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-10"
---

## 한 줄 요약
구조체 배열 `arr[i]`에 접근할 때 구조체 크기가 1/2/4/8바이트가 아니면(예: 12바이트) 하드웨어 스케일 인덱스를 못 쓰기 때문에 `IMUL`로 인덱스에 구조체 크기를 직접 곱한 뒤 더하는 코드가 명시적으로 나타난다.

## 언제 검색해야 하나
- `for` 루프 안에서 `imul rax, rcx, 12`처럼 낯선 상수를 곱하는 명령이 반복해서 나올 때
- 구조체 배열을 순회하는 루프인데 왜 `LEA` 스케일(`*4`, `*8`)이 아니라 `IMUL`이 쓰였는지 궁금할 때
- `sizeof(struct)`을 몰라서 IMUL에 곱해진 상수로 구조체 크기를 역산해야 할 때
- IDA/Ghidra가 배열을 `int` 배열이 아니라 구조체 배열로 인식하지 못해서 오프셋이 뒤죽박죽으로 보일 때

## 핵심 개념
REV-1063에서 봤듯 x86-64는 메모리 오퍼랜드에서 인덱스 레지스터에 1/2/4/8배의 스케일만 하드웨어로 지원한다. 구조체 크기가 이 네 값 중 하나가 아니면(패딩 때문에 12바이트, 20바이트 등이 흔함) 컴파일러는 별도의 곱셈 명령(`IMUL`)으로 "인덱스 × 구조체 크기"를 먼저 계산한 뒤, 그 결과를 배열 시작 주소에 더하는 `LEA`나 `ADD`를 이어붙인다.

```c
struct Item { int id; int value; char tag; };  /* 4+4+1 = 9바이트인데 int 정렬로 12바이트 패딩 */
```
이 구조체는 `sizeof(struct Item) == 12`가 된다(REV-0344 정렬/패딩 참고). 배열 `arr[i].value`에 접근하려면 `i * 12 + 4`(4는 `value`의 구조체 내 오프셋)를 계산해야 하고, 12는 스케일 인덱스로 못 쓰는 값이므로 `IMUL rax, rcx, 12`가 코드에 명시적으로 나타난다.

반대로 구조체 크기가 우연히 8이나 4로 딱 맞는 경우(예: `int` 두 개만 있는 8바이트 구조체)는 REV-1063처럼 `LEA [base+idx*8]`로 압축되어 IMUL이 안 보일 수 있다. **IMUL이 보이면 구조체(또는 배열 원소) 크기가 2의 거듭제곱이 아니라는 강력한 힌트**다.

## 화면/코드에서 보이는 징후
- 루프 안에서 `imul rax, rcx, N` (N이 12, 16, 20, 24 등 흔한 구조체 크기)
- 그 결과에 배열 베이스 주소를 더하는 `add rax, [rbp-8]` 또는 `lea rax, [rax+rdx]`
- 최종 필드 접근에서 작은 오프셋이 추가로 붙음: `mov eax, [rax+4]` (필드 오프셋)
- Ghidra pseudocode에서 `arr[i].value`로 깨끗하게 복원되지 못하고 `*(int *)((char *)arr + i * 12 + 4)`처럼 바이트 연산으로 풀려 보이는 경우가 흔함

## 가장 먼저 할 것
`IMUL`에 곱해지는 상수를 먼저 확인한다. 이 값이 곧 `sizeof(구조체)`다. 그다음 그 결과에 최종적으로 더해지는 작은 오프셋(0, 4, 8 등)을 보면 어느 필드에 접근하는지 알 수 있다. IDA에서는 이 구조체 크기로 `Structures` 창에 새 구조체를 만들어 필드를 채워 넣고, 배열 변수에 `struct Item[]` 타입을 지정하면 pseudocode가 `arr[i].value` 형태로 정리된다.

## 단계별 절차
1. 루프의 인덱스 변수가 어느 레지스터인지 확인한다(보통 `ecx`나 `edx`).
2. `imul reg, idx_reg, N` 형태의 곱셈을 찾고 `N`을 기록한다 — 이것이 구조체(원소) 크기다.
3. 곱셈 결과가 배열 시작 주소와 더해지는 지점(`add`, `lea`)을 찾아 "배열 원소의 시작 주소"가 어디서 만들어지는지 확인한다.
4. 그 주소에 추가로 붙는 작은 오프셋(`[rax+0]`, `[rax+4]`, `[rax+8]`)을 각각 필드로 매핑한다 — 오프셋 0부터 N-1(패딩 포함)까지 필드들이 순서대로 배치되어 있다고 가정하고 역산한다.
5. GDB에서 `p sizeof(struct Item)`(디버그 정보가 있으면) 또는 `p arr[1] - arr[0]`으로 실제 구조체 크기를 검증한다.

## 명령어/단축키
- IDA: `Shift+F9`(Structures 창) → `Insert` → 필드 크기 합이 `IMUL` 상수와 같은 구조체를 정의
- Ghidra: `Data Type Manager` → 새 구조체 생성 → 배열 변수에 `구조체[]` 타입 지정
- GDB: `p &arr[1] - &arr[0]` (원소 간 실제 바이트 거리 확인), `ptype struct Item` (디버그 정보 있을 때 정확한 크기/오프셋)
- x64dbg: 곱셈 명령 실행 후 레지스터 값으로 실제 계산된 오프셋 확인

## 출력 해석
```c
struct Item { int id; int value; char tag; };  /* sizeof == 12 (패딩 포함) */

int get_value(struct Item *arr, int i) {
    return arr[i].value;
}
```

```asm
; get_value, rdi = arr, esi = i
get_value:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-8], rdi     ; arr
    mov     [rbp-12], esi    ; i
    mov     eax, [rbp-12]    ; eax = i
    movsxd  rdx, eax         ; rdx = (long)i  (부호 확장, int -> long)
    imul    rax, rdx, 12     ; rax = i * 12   (12 = sizeof(struct Item))
    add     rax, [rbp-8]     ; rax = arr + i*12  (arr[i]의 시작 주소)
    mov     eax, [rax+4]     ; eax = arr[i].value  (value의 구조체 내 오프셋 = 4)
    leave
    ret
```

`imul rax, rdx, 12`가 이 함수의 핵심이다. 12라는 상수는 스케일 인덱스(1/2/4/8)에 속하지 않으므로 반드시 별도의 곱셈 명령으로 나타난다. 이후 `[rax+4]`는 `struct Item`의 두 번째 필드(`value`, `id` 다음 4바이트 위치)에 대응한다. `movsxd`는 32비트 인덱스를 64비트 주소 계산에 쓰기 위한 부호 확장으로, 배열 인덱싱에서 거의 항상 함께 등장한다(REV-0041 MOVSX/MOVSXD 참고).

## 흔한 실수
- `IMUL`의 곱셈 상수를 "그냥 어떤 계산값"으로 넘기고 구조체 크기라는 것을 놓치는 것.
- 구조체 크기가 8이나 4로 딱 맞아서 `LEA` 스케일로 압축된 경우와, 12/20 등이라 `IMUL`이 명시된 경우를 같은 패턴으로 오해하는 것 — 전자는 REV-1063, 후자는 이 글의 패턴이다.
- 필드 오프셋(예: `+4`)만 보고 그 필드가 몇 번째 필드인지 패딩을 고려하지 않고 단순히 "4바이트씩 나누기"로 계산하는 것 — 구조체 안에 `char`, `short` 등이 섞이면 패딩 때문에 균등하게 안 나뉜다(REV-0344).
- `movsxd`(부호 확장) 단계를 무시하고 인덱스 레지스터 크기가 왜 32비트에서 64비트로 바뀌는지 신경 안 쓰는 것 — 음수 인덱스가 있을 경우 부호 확장 여부가 실제 접근 주소를 완전히 바꾼다.

## 막혔을 때 다음 체크
- 일반 포인터 산술과 스케일 인덱스 압축이 헷갈리면 → REV-1063 포인터 산술이 어셈블리에서 보이는 패턴
- 구조체 자체의 필드 오프셋 계산 원리가 궁금하면 → REV-1061 중첩 구조체 접근이 어셈블리에서 보이는 패턴, REV-0035 구조체 접근이 어셈블리로 변하는 방식
- 왜 구조체 크기가 필드 합과 다르게 나오는지(패딩)는 → REV-0344 구조체 정렬/패딩이 미치는 영향
- 2차원 배열과의 차이가 궁금하면 → REV-1059 2차원 배열 인덱싱이 어셈블리에서 보이는 패턴, REV-0350 다차원 배열이 어셈블리로 어떻게 변하는지

## 미니 예제
IMUL 상수만 보고 구조체를 역추정하는 연습:
```
imul rax, rdx, 8   ->  구조체 크기 8바이트 후보: {int, int} 또는 {포인터 하나}
imul rax, rdx, 16  ->  구조체 크기 16바이트 후보: {long, long}, {포인터, 포인터}, {double, int, 패딩}
imul rax, rdx, 24  ->  구조체 크기 24바이트 후보: {char*, long, int+패딩} 등
```
정확한 필드 구성은 이후 각 필드 오프셋(`[rax+0]`, `[rax+8]`, `[rax+16]`)에서 읽는 크기(`mov`면 4/8바이트, `movzx`면 1/2바이트)를 함께 봐야 확정할 수 있다.

## 관련 글
- REV-1063 — 포인터 산술이 어셈블리에서 보이는 패턴
- REV-1061 — 중첩 구조체 접근이 어셈블리에서 보이는 패턴
- REV-0344 — 정렬(Alignment)과 패딩이 구조체에 미치는 영향
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해
- REV-0350 — 다차원 배열이 어셈블리로 어떻게 변하는지

## 출처/검증
- x86-64 스케일 인덱스가 1/2/4/8만 하드웨어로 지원되는 제약: Intel 64 and IA-32 Architectures Software Developer's Manual 기준.
- 구조체 크기가 2의 거듭제곱이 아닐 때 컴파일러가 `IMUL`로 명시적 곱셈을 삽입하는 패턴: gcc/clang `-O0` x86-64 리눅스/윈도우 환경에서 반복 확인되는 표준 패턴(2026-09-10 검증).
