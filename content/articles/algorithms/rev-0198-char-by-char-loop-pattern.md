---
id: REV-0198
title: "문자별 for 루프 검증 패턴"
slug: "rev-0198-char-by-char-loop-pattern"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["for 루프 검증", "문자별 비교", "언롤된 strcmp", "입력 검증 루프", "byte by byte compare"]
aliases: ["strcmp 없는데 문자 비교함", "루프 안에 cmp jnz", "한 글자씩 비교", "언롤된 비교"]
symptom_keywords: ["루프 안에서 계속 cmp함", "strcmp가 안 보이는데 문자열 비교하는 것 같음", "for문 조건이 이상함", "인덱스로 배열 접근하면서 비교"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
라이브러리 함수 이름 없이 `for(i=0; i<len; i++) { ... input[i] ... }` 형태로 인덱스를 증가시키며 한 바이트씩 비교/변환하는 루프는 `strcmp`/`memcmp`가 **직접 손으로 구현되거나 컴파일러에 의해 인라인**된 것이며, 루프 본문에 변환 연산이 있는지 없는지에 따라 뒤의 REV-0199~0202 중 어떤 패턴을 함께 봐야 하는지가 갈린다.

## 언제 검색해야 하나
- Imports 탭에 `strcmp`/`memcmp`가 아예 없거나 있어도 호출되지 않는데, flag를 검증하는 것으로 보이는 함수가 있을 때
- 디스어셈블리에 반복문(루프 시작 라벨 + 조건부 점프로 되돌아가는 구조)이 있고, 그 안에서 배열 인덱스(`[rdi+rax]`, `[rsi+rcx]` 등)로 메모리에 접근하며 `cmp`를 수행할 때
- 디컴파일 결과가 `for` 또는 `while` 루프 안에 `if (input[i] != ...)` 형태로 나올 때
- "루프가 도는데 뭘 하는지 감이 안 잡힘"이라고 느껴질 때 (변환이 있는지부터 확인하면 됨)

## 핵심 개념
컴파일러 최적화(`-O2` 이상, 또는 릴리즈 빌드) 상태에서는 `strcmp`나 `memcmp` 같은 라이브러리 호출도 컴파일러가 직접 인라인해서 바이트/워드 단위 루프로 펼쳐버리는 경우가 많다. 또한 애초에 개발자(문제 출제자)가 `strcmp`를 안 쓰고 직접 `for`문으로 짠 검증 함수를 작성하는 경우도 매우 흔하다 — CTF 리버싱 문제의 절반 이상이 이 형태다.

이 패턴을 만나면 항상 두 가지를 구분해야 한다.

1. **순수 비교형**: `if (input[i] != expected[i]) return 0;` — 변환 없이 그냥 대응하는 바이트끼리 비교. 이건 `memcmp`를 손으로 푼 것과 동일하며, `expected[i]` 배열을 그대로 읽으면 끝난다.
2. **변환 후 비교형**: `if (transform(input[i]) != expected[i]) return 0;` — 각 문자에 XOR/ADD/SUB/ROL/ROR/SHIFT 같은 연산을 적용한 뒤 비교. 이 경우 `transform`을 알아내서 **역연산**을 해야 원래 문자를 구할 수 있다 (REV-0199~0202 참고).

또한 실패 처리 방식도 두 가지로 나뉜다.

- **조기 반환(short-circuit)**: 한 글자라도 틀리면 즉시 `return 0`으로 빠져나감. 이 구조는 타이밍 사이드채널 공격(각 글자가 맞을 때마다 비교 시간이 미세하게 길어짐)이 이론적으로 가능한 취약한 구조지만, CTF에서는 대부분 그냥 정적/동적 분석으로 값을 직접 읽는 게 더 빠르다.
- **전부 비교 후 판정**: 모든 글자를 다 비교한 다음 `and`나 카운터 누적으로 한 번에 성공/실패를 판정. 디버거로 한 글자씩 브레이크를 걸어도 중간에 끊기지 않으므로 오히려 전체 배열을 한 번에 덤프하는 쪽이 빠르다.

## 화면/코드에서 보이는 징후
**x64 디스어셈블리 (순수 비교형):**
```asm
xor     ecx, ecx              ; i = 0
loop_start:
movzx   eax, byte ptr [rdi+rcx]   ; input[i]
cmp     al, byte ptr [rsi+rcx]    ; expected[i]
jne     fail
inc     ecx
cmp     ecx, 20h               ; len == 32
jl      loop_start
```

**x64 디스어셈블리 (변환 후 비교형 — XOR 예시):**
```asm
loop_start:
movzx   eax, byte ptr [rdi+rcx]
xor     al, 0x13                  ; 변환: input[i] ^ 0x13
cmp     al, byte ptr [rsi+rcx]    ; expected[i]와 비교
jne     fail
inc     ecx
cmp     ecx, 20h
jl      loop_start
```

**IDA/Ghidra 디컴파일 (순수 비교형):**
```c
for ( i = 0; i < 32; ++i )
{
    if ( input[i] != expected[i] )
        return 0;
}
return 1;
```

**IDA/Ghidra 디컴파일 (변환 후 비교형):**
```c
for ( i = 0; i < 32; ++i )
{
    if ( (input[i] ^ 0x13) != expected[i] )
        return 0;
}
return 1;
```

**전부 비교 후 판정형:**
```c
int ok = 1;
for ( i = 0; i < 32; ++i )
    ok &= (input[i] == expected[i]);
return ok;
```
이 형태는 루프 안에 `jne`로 즉시 빠져나가는 분기가 없다는 게 특징이다 — `and`나 덧셈으로 결과를 누적하는 것만 보인다.

## 가장 먼저 할 것
루프 본문에서 `input[i]`를 읽어온 직후, **비교(`cmp`) 전에 다른 연산(`xor`, `add`, `sub`, `rol`, `ror`, `shl`, `shr`)이 끼어 있는지**부터 확인한다. 없으면 그냥 `expected` 배열을 읽으면 끝. 있으면 그 연산이 정확히 무엇인지 특정해서 REV-0199~0202로 넘어간다.

## 단계별 절차
**1) 루프 경계값(길이) 확인**

`cmp ecx, 0x20`처럼 루프 종료 조건에 쓰이는 상수가 곧 입력/flag의 길이다. 이걸 먼저 적어둔다.

**2) 인덱싱 베이스 두 개 식별**

루프 안에서 메모리를 읽는 베이스 레지스터가 보통 두 개 있다 — 하나는 사용자 입력(`rdi`/`rbp-0x20` 등), 하나는 정답/키 배열(`rsi`/전역 변수 주소). 둘 다 IDA에서 더블클릭해서 초기화 위치를 확인한다.

**3) 비교 직전 연산 유무 확인**

`cmp` 명령어 바로 위 1~3줄을 본다. `xor al, imm`이면 REV-0199, `add`/`sub`면 REV-0200, `rol`/`ror`면 REV-0201, `shl`/`shr`/`sar`면 REV-0202. 아무 연산도 없으면 그냥 REV-0197(memcmp)/REV-0196(strcmp)과 동일한 방식으로 `expected` 배열을 그대로 읽는다.

**4) 정답 배열 덤프**

정적으로는 IDA Hex View에서, 동적으로는 디버거에서 `expected` 배열의 시작 주소부터 `length`바이트를 덤프한다.

```python
# IDA Hex View에서 복사한 raw bytes
expected = bytes.fromhex("...")
length = 32
assert len(expected) == length
```

**5) 변환이 있으면 역산, 없으면 그대로 출력**

변환이 없다면:
```python
flag = expected.decode()
print(flag)
```
변환이 있다면 REV-0199~0202의 역연산 공식을 적용한다.

## 명령어/단축키
- IDA: 루프 시작 라벨에 커서를 놓고 `Ctrl+G`로 그래프 뷰 전환하면 loop back-edge가 시각적으로 보여서 루프 범위를 빠르게 파악 가능
- x64dbg: 루프 내부 `cmp` 명령어에 브레이크포인트를 걸고 F9로 여러 번 실행하며 `al`/`expected[i]` 값을 관찰(단, 조기 반환형이 아니라면 매 반복마다 멈추므로 조건부 브레이크포인트 `bp addr, "ecx==5"` 형태로 특정 인덱스만 확인하는 게 빠름)
- gdb: `watch *(char*)($rsi+$rcx)` 로 인덱스별 값 변화 관찰

## 출력 해석
- `jl`/`jb` 등으로 루프백하는 조건이 `ecx < length`이면 length가 곧 flag 길이. `jle`라면 `length+1`일 수 있으니 경계 조건(`<` vs `<=`)을 정확히 다시 읽는다.
- 루프 탈출 후 반환값이 `1`(성공)인지 `0`(실패)인지, 그리고 그 반환값이 상위 호출자에서 어떻게 쓰이는지("Correct" 출력과 연결되는지)까지 확인해야 진짜 검증 함수인지 확신할 수 있다.
- 변환 연산의 피연산자(`0x13` 같은 즉시값)가 매 반복 동일하면 "단일 키", 인덱스에 따라 달라지면(`key[i % keylen]`처럼 다른 배열을 참조) "반복 키" 구조이므로 REV-0199의 "반복 키 XOR" 절을 참고한다.

## 흔한 실수
- 루프 종료 조건에서 `<`와 `<=`를 헷갈려서 flag 길이를 하나 틀리게 잡는 것. 항상 실제로 몇 번 반복되는지 손으로 세어 확인한다.
- 비교 직전의 변환 연산을 놓치고 `expected` 배열을 그대로 flag라고 출력해버리는 것. 결과가 아스키로 안 읽히면 반드시 위로 1~3줄을 다시 살펴본다.
- 조기 반환형에서 첫 글자만 틀려도 함수 전체가 바로 끝난다는 걸 이용해서 "브루트포스 + 실행시간/분기 관찰"로 억지로 풀려다가, 사실은 그냥 `expected` 배열을 정적으로 읽으면 훨씬 빠르다는 걸 놓치는 것.
- 인덱스 변수(`ecx`, `rax` 등)가 두 개의 다른 목적(입력 인덱스, 정답 배열 인덱스)으로 각각 따로 증가하는 경우를 하나의 변수로 착각하는 것 — 두 배열의 정렬(offset)이 다를 수 있다.

## 막혔을 때 다음 체크
- 변환 연산이 `xor`라면 → REV-0199.
- 변환 연산이 `add`/`sub`라면 → REV-0200.
- 변환 연산이 `rol`/`ror`라면 → REV-0201.
- 변환 연산이 `shl`/`shr`/`sar`라면 → REV-0202.
- 변환 없이 그냥 비교인데 결과가 이상하다면 → REV-0196/REV-0197로 돌아가 `strcmp`/`memcmp`와 개념적으로 동일함을 재확인.

## 미니 예제
**예제 1 — 순수 비교, 길이 8**
```asm
xor ecx, ecx
loop1:
movzx eax, byte ptr [rdi+rcx]
cmp al, byte ptr [rsi+rcx]
jne fail
inc ecx
cmp ecx, 8
jl loop1
```
`rsi` 시작 주소의 8바이트를 그대로 읽으면 정답.

**예제 2 — 인덱스별 다른 키(반복 키 XOR)**
```c
for ( i = 0; i < 12; ++i )
{
    if ( (input[i] ^ key[i % 4]) != expected[i] )
        return 0;
}
```
`key`(4바이트)와 `expected`(12바이트)를 각각 덤프한 뒤:
```python
key = bytes.fromhex("deadbeef")
expected = bytes.fromhex("...")  # 12바이트
flag = bytes(e ^ key[i % len(key)] for i, e in enumerate(expected))
print(flag)
```

**예제 3 — 전부 비교 후 판정(and 누적)**
```c
int ok = 1;
for ( i = 0; i < 6; ++i )
    ok = ok & (input[i] == "Secret"[i]);
return ok;
```
문자열 리터럴 `"Secret"`이 코드/디컴파일 결과에 그대로 노출되어 있으므로 바로 읽으면 끝.

**예제 4 — 길이 경계값을 잘못 읽기 쉬운 경우**
```asm
cmp ecx, 0x10
jle loop1     ; i <= 16 이므로 실제로는 17번 반복(i=0..16)
```
`jl`이 아니라 `jle`이므로 flag 길이는 16이 아니라 17임에 주의.

## 관련 글
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0197 — memcmp 기반 Flag 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- REV-0200 — ADD SUB 상수 기반 문자 변환
- REV-0201 — Rotate ROL ROR 기반 변환
- REV-0202 — Shift SHL SHR SAR 기반 변환
- ../assembly/rev-0060-cmp.md — CMP 명령어
- ../assembly/rev-0068-jne-jnz.md — JNE/JNZ 조건 분기

## 출처/검증
- 컴파일러가 짧은 `strcmp`/`memcmp` 호출을 바이트 단위 루프로 인라인 전개하는 것은 GCC/Clang/MSVC의 일반적인 최적화 동작(각 컴파일러 최적화 문서 기준).
- 위 예제 코드는 CTF 스타일 검증 로직을 재현한 예시이며 특정 실제 문제의 정답이 아니다(2026-09-08 작성 시 확인).
