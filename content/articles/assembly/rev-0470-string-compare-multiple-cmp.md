---
id: REV-0470
title: "문자열 비교가 여러 CMP로 풀리는 최적화 패턴"
slug: "rev-0470-string-compare-multiple-cmp"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - string compare unroll
  - 문자열 비교 언롤
  - strcmp inline
  - memcmp inline
  - 정수로 변환된 문자열 비교
  - cmp dword ptr immediate string
  - 리틀 엔디안 문자열
  - little endian ascii
  - word compare optimization
aliases:
  - strcmp 함수 호출이 안 보임
  - cmp인데 이상한 hex 값
  - 큰 16진수가 문자열 같음
  - 문자열 비교가 인라인됨
symptom_keywords:
  - call strcmp가 없는데 문자열을 비교하는 것 같음
  - cmp 명령에 큰 hex immediate이 있음
  - 정답 문자열을 못 찾겠음
  - 문자열 비교가 여러 개의 cmp로 나눠져 있음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
길이가 컴파일 시점에 확정된 짧은 문자열 비교(`strcmp`, `memcmp`, `==`)는 함수 호출 없이 문자열을 4바이트/8바이트 단위 정수로 읽어서 `cmp` 명령 하나(또는 몇 개)로 직접 비교하도록 컴파일러가 풀어버리는 경우가 많으며, 이때 `cmp` 명령의 큰 16진수 즉시값이 사실 리틀 엔디안으로 뒤집힌 아스키 문자열이라는 점을 알아채는 게 핵심이다.

## 언제 검색해야 하나
- 문자열을 비교하는 것 같은데 Imports 탭에 `strcmp`/`memcmp` 호출이 안 보이거나, `call strcmp`가 있어도 그 앞뒤에 이상하게 큰 `cmp` 즉시값들이 추가로 있을 때
- `cmp dword ptr [rax], 12345678h`처럼 `cmp`에 사람이 읽기 애매한 큰 16진수 상수가 들어있을 때
- REV-0196(strcmp 기반 flag 검증 패턴)에서 배운 "call strcmp 뒤 test eax,eax" 패턴이 최적화된 빌드에서는 안 보여서 flag를 못 찾겠을 때
- CTF 바이너리가 `-O2`/`-O3`로 컴파일되어 있어서 익숙한 라이브러리 호출 패턴이 사라졌을 때

## 핵심 개념

### 왜 컴파일러가 문자열 비교를 CMP로 바꾸는가
`strcmp(s, "flag")`처럼 비교 대상 문자열 중 하나가 **컴파일 시점에 이미 알려진 리터럴**이면, 컴파일러는 함수 호출 오버헤드(스택 정렬, 인자 세팅, CALL/RET) 없이 그 자리에서 바로 비교하는 게 훨씬 빠르다는 걸 안다. 그래서 짧은 문자열(보통 몇 바이트~십수 바이트)에 대해서는 `strcmp`/`memcmp` 호출을 아예 인라인 전개해서, 비교할 바이트들을 **정수처럼 통째로 읽어 한 번에 비교**하는 코드로 바꿔버린다.

```c
if (strcmp(input, "flag") == 0) { ... }
```
`"flag"`는 4바이트(`'f','l','a','g'`) + 종료 널바이트 1개 = 5바이트다. 컴파일러는 이걸 4바이트 정수 하나로 로드해서 비교하고, 나머지 널바이트는 별도로 확인하거나, 아예 5바이트를 포함하는 더 큰 단위(8바이트 등)로 한 번에 비교하기도 한다.

### 리틀 엔디안과 16진수 읽는 법
x86/x64는 리틀 엔디안이므로, 메모리에 `'f','l','a','g'` 순서로 저장된 4바이트를 32비트 정수 하나로 읽으면 **바이트 순서가 뒤집혀서** 값이 만들어진다.
```
메모리: 66 6C 61 67   ('f'=0x66, 'l'=0x6C, 'a'=0x61, 'g'=0x67)
32비트 정수로 읽으면: 0x67616C66   (마지막 바이트가 최상위로 옴)
```
그래서 어셈블리에 `cmp eax, 67616C66h` 같은 게 보이면, 이 16진수를 1바이트씩(`67 61 6C 66`) 나눠서 **거꾸로** 읽으면 `66 6C 61 67` = `f l a g`가 된다. 즉 **가장 낮은 바이트(맨 오른쪽 2자리)부터 아스키로 변환**하면 원래 문자열이 나온다.

### 길이별 비교 전략
컴파일러/컴파일러 내장 함수(builtin `__builtin_strcmp`, `__builtin_memcmp`)는 비교할 길이에 따라 전략을 다르게 쓴다.
- **1~2바이트**: `cmp al, imm8` 또는 `cmp ax, imm16`
- **4바이트**: `cmp eax, imm32` (32비트 정수 하나로 통째 비교)
- **8바이트**: `cmp rax, imm64` 또는 `movabs`로 상수를 레지스터에 올린 뒤 `cmp reg, reg`
- **8바이트 초과**: 8바이트 단위로 여러 번 `cmp`를 반복하거나(체인), 남은 꼬리 바이트는 더 작은 단위로 따로 비교. 최신 컴파일러는 SSE/AVX 레지스터(XMM)로 16바이트씩 한 번에 비교하기도 한다(REV-0471 AVX/SSE 참고).

이렇게 되면 소스코드 한 줄(`strcmp(...)`)이 어셈블리에서는 **여러 개의 `cmp`와 그 사이의 짧은 분기**로 풀어져 나타나므로, 처음 보면 "이게 문자열 비교였다고?"라는 생각이 들 만큼 낯설어 보인다.

### memcmp와의 관계
`memcmp`도 길이가 컴파일 시점에 고정되어 있으면 같은 방식으로 정수 비교로 풀린다. `strcmp`와의 차이는 `strcmp`는 널 종료를 만나면 거기서 멈춰야 하지만, 짧은 리터럴 비교에서는 컴파일러가 "이 길이까지는 널이 없다는 걸 이미 알고 있으므로" 그냥 통째로 비교해버리는 경우가 많다는 점이다(자세한 `memcmp` 자체 패턴은 REV-0197 참고).

## 화면/코드에서 보이는 징후
```asm
; "flag" (4바이트 + NUL)를 4바이트 정수 비교 + 1바이트 NUL 비교로 처리
cmp     dword ptr [rdi], 67616C66h   ; "flag"의 첫 4바이트
jne     not_equal
cmp     byte ptr [rdi+4], 0          ; 종료 NUL 확인
jne     not_equal
; 여기 도달하면 "flag"와 완전히 일치
```
```asm
; 8바이트 문자열을 movabs + cmp reg,reg로 비교하는 예 ("password" 앞 8글자)
movabs  rax, 64726F7773736170h   ; "passwrd"가 아니라 실제로는 뒤집힌 8바이트
cmp     [rdi], rax
jne     not_equal
```
```asm
; call strcmp가 여전히 있지만 앞에 길이/첫 글자 사전 검사가 추가된 경우
movzx   eax, byte ptr [rdi]
cmp     al, 66h            ; 첫 글자가 'f'인지 먼저 빠르게 확인(짧은 회로)
jne     not_equal
call    strcmp
test    eax, eax
jne     not_equal
```

## 가장 먼저 할 것
1. `cmp`에 4바이트 이상의 큰 즉시값이 보이면, 그 값을 1바이트씩 나눠서 리틀 엔디안으로 뒤집어 아스키로 변환해본다.
2. 여러 개의 `cmp`가 연속으로 나오면서 각각 다른 메모리 오프셋(`[rdi]`, `[rdi+4]`, `[rdi+8]`...)을 비교한다면, 그 오프셋들을 순서대로 이어 붙여 하나의 문자열을 복원한다.
3. Python/계산기로 직접 변환하는 게 가장 빠르다 — 손으로 세는 것보다 오류가 적다.

## 단계별 절차
**1) 즉시값을 16진수 바이트로 쪼개기**
`cmp eax, 67616C66h`에서 `67616C66`을 2자리씩 끊는다: `67 61 6C 66`

**2) 순서를 뒤집는다(리틀 엔디안)**
`66 6C 61 67`

**3) 아스키로 변환**
`0x66='f', 0x6C='l', 0x61='a', 0x67='g'` → `flag`

**4) Python으로 한 번에 확인(권장)**
```python
>>> import struct
>>> struct.pack("<I", 0x67616C66).decode()
'flag'
>>> struct.pack("<Q", 0x64726F7773736170).decode()
'passwrd'
```
`<I`는 리틀 엔디안 4바이트(unsigned int), `<Q`는 리틀 엔디안 8바이트(unsigned long long)를 뜻한다. 여러 개의 `cmp` 오프셋이 있다면 각각 변환한 뒤 순서대로 이어 붙인다.

**5) 여러 조각을 이어 붙여 전체 문자열 복원**
```
cmp dword ptr [rdi],   67616C66h   -> "flag"
cmp word  ptr [rdi+4], 7B7Fh       -> 뒤집으면 "{" + 다음 바이트... (오프셋에 맞게 순서대로 이어 붙임)
```

## 명령어/단축키
- Python: `struct.pack("<I", value).decode()` / `struct.pack("<Q", value).decode()`
- x64dbg/IDA: 즉시값 위에서 마우스 오른쪽 → "10진수/16진수/문자로 표시" 전환 기능이 있는 경우 바로 아스키로 볼 수 있음(즉시값을 문자 상수로 렌더링하는 뷰 전환)
- IDA: 즉시 피연산자 위에서 `R`(문자 상수로 표시, "Char" 토글) 단축키로 바로 아스키 문자로 바꿔 볼 수 있음

## 출력 해석
- `cmp` 즉시값을 문자로 바꿨을 때 사람이 읽을 수 있는 문자열이 나오면, 그 부분이 정답(또는 정답의 일부)이다.
- 여러 `cmp`가 실패 시 모두 같은 `not_equal`/`fail` 라벨로 점프한다면, 이 `cmp`들은 모두 "AND로 연결된 하나의 전체 일치 조건"의 조각들이다 — 하나라도 실패하면 전체가 실패.
- NUL 바이트(`cmp byte ptr [...], 0`) 확인이 마지막에 붙어있다면 문자열 길이가 정확히 거기까지라는 뜻이다 — 그 뒤에 문자가 더 있으면 안 된다는 의미.

## 흔한 실수
- `cmp` 즉시값을 그냥 숫자로 보고 넘어가서 "이건 무슨 매직 넘버인가?" 하며 문자열 비교라는 걸 놓치는 것.
- 리틀 엔디안 뒤집기를 빼먹고 16진수를 그대로 아스키로 읽어서 뒤집힌(엉뚱한) 문자열을 정답이라고 착각하는 것.
- 여러 `cmp` 조각을 이어 붙일 때 오프셋 순서(`[rdi]`, `[rdi+4]`, `[rdi+8]`)를 무시하고 코드에 나온 순서 그대로(스케줄링으로 뒤섞였을 수 있음, REV-0468 참고) 이어 붙이는 것 — 반드시 **메모리 오프셋** 기준으로 정렬해야 한다.
- `strncmp`가 짧은 길이로 인라인된 경우와 완전한 `strcmp`/`memcmp` 인라인을 혼동해서, 실제로는 앞부분 몇 글자만 검사하는데 전체 정답이라고 오판하는 것.

## 막혔을 때 다음 체크
- `call strcmp`가 여전히 있는 일반적인 형태라면 → REV-0196(strcmp 기반 Flag 검증 패턴)으로 돌아가서 기본 패턴부터 확인한다.
- 문자별로 `cmp`가 루프 안에서 반복된다면(인라인 정수 비교가 아니라 진짜 루프) → REV-0198(문자별 for 루프 검증 패턴, CONTENT_PLAN 예정) 방향으로 접근한다.
- 비교 대상이 SSE/XMM 레지스터로 16바이트씩 처리된다면 → REV-0471(AVX가 보일 때 SSE와 다른 점)을 참고해 벡터 비교 명령을 해석한다.
- 상수가 암호화/변형된 것 같다면 → REV-0199~0202(XOR/ADD/Rotate/Shift 역산, CONTENT_PLAN 예정) 계열을 의심한다.

## 미니 예제
**예제 1 — 4바이트 정수 비교로 풀린 "flag" 검사**
```c
if (strcmp(input, "flag") == 0) puts("Correct!");
```
```asm
mov     eax, [rdi]
cmp     eax, 67616C66h      ; "flag"
jne     wrong
cmp     byte ptr [rdi+4], 0 ; NUL 종료 확인
jne     wrong
call    puts
```

**예제 2 — 8바이트 movabs 비교**
```c
if (memcmp(input, "S3cur3_1", 8) == 0) ok();
```
```asm
movabs  rax, 315F337275633353h   ; "S3cur3_1"을 8바이트로 리틀 엔디안 인코딩한 값
cmp     [rdi], rax
jne     wrong
call    ok
```

**예제 3 — 12바이트를 8+4로 나눠 비교**
```c
if (memcmp(input, "flag{is_this}", 13) == 0) ok();
```
```asm
movabs  rax, <"flag{is_"의 8바이트>
cmp     [rdi], rax
jne     wrong
mov     eax, <"this"의 4바이트>
cmp     [rdi+8], eax
jne     wrong
cmp     byte ptr [rdi+12], 7Dh   ; '}' 마지막 한 글자
jne     wrong
call    ok
```
Python으로 각 청크를 `struct.pack("<Q", ...)`, `struct.pack("<I", ...)`로 디코딩해서 순서대로(오프셋 0, 8, 12) 이어 붙이면 전체 문자열을 복원할 수 있다.

## 관련 글
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0454 — 나눗셈이 곱셈과 시프트로 최적화되는 패턴(Magic Number)
- REV-0471 — AVX 명령이 보일 때 SSE와 다른 점 개요
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `strcmp`/`memcmp` 리터럴 인라인 최적화: GCC 공식 문서(Built-in Functions, `__builtin_strcmp`/`__builtin_memcmp` 설명) 및 LLVM 최적화 패스(`InstCombine`, `SimplifyLibCalls`) 문서 기준.
- x86/x64가 리틀 엔디안임: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 1, "Byte Order" 섹션 기준.
- 위 어셈블리 예제는 x86-64 `-O2` 최적화 결과 경향을 단순화해 재구성한 예시다(2026-09-08 검증).
