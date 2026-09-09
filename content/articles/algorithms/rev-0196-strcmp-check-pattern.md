---
id: REV-0196
title: "strcmp 기반 Flag 검증 패턴"
slug: "rev-0196-strcmp-check-pattern"
category: "algorithms"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, Python]
keywords: ["strcmp", "flag 검증", "문자열 비교", "call strcmp", "test eax eax", "Correct!"]
aliases: ["strcmp 어디서 걸림", "strcmp 뭐임", "정답 문자열 어디", "flag 비교 함수"]
symptom_keywords: ["strcmp 뒤에 test eax eax", "correct 문자열이 안 뜸", "정답이 어디 있는지 모르겠음", "함수 인자에 이상한 문자열이 있음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-CTF-WRITEUPS"]
last_verified: "2026-09-10"
---

## 한 줄 요약
`call strcmp` 직후 `test eax, eax` 또는 `cmp eax, 0`이 오고 그 결과로 분기하는 코드는 거의 항상 "입력 문자열이 정답 문자열과 같은지" 검사하는 부분이며, `strcmp`의 두 번째 인자(또는 비교 대상 문자열)를 그대로 읽으면 flag를 바로 얻을 수 있는 가장 쉬운 패턴이다.

## 언제 검색해야 하나
- IDA/Ghidra에서 `strcmp`가 임포트 목록(Imports 탭)에 있고, 그 함수를 호출하는 곳(xref)을 찾아가는 상황
- 디컴파일 코드에 `if ( strcmp(input, "...") == 0 )` 같은 줄이 보일 때
- 입력값을 받은 직후 표준 라이브러리 함수를 호출하고 반환값(EAX/RAX)으로 분기하는 코드를 만났을 때
- `x64dbg`나 `gdb`로 실행 중 "Correct" 또는 "Wrong" 문자열이 나오기 직전 어떤 함수가 호출됐는지 확인하고 싶을 때

## 핵심 개념
C 표준 라이브러리의 `strcmp(a, b)`는 두 널(NUL) 종료 문자열을 앞에서부터 한 바이트씩 비교해서, 같으면 `0`, 다르면 (첫 번째로 다른 바이트의 차이에 따라) 양수 또는 음수를 반환한다. CTF의 "input == flag" 검증 로직에서 가장 흔하게 쓰이는 함수이기도 하다. 왜냐하면 flag가 항상 출력 가능한 아스키 문자열이고 중간에 NUL 바이트가 없기 때문에, `strcmp`를 그대로 써도 안전하기 때문이다(중간에 `\0`이 들어가는 이진 데이터라면 `memcmp`를 쓰는데, 이건 REV-0197에서 다룬다).

컴파일러는 대개 이 비교를 다음 두 형태 중 하나로 만든다.

1. **라이브러리 호출형**: `call strcmp` 후 반환값(EAX/RAX)을 검사. 문자열이 길거나 최적화가 낮을 때 흔함.
2. **인라인 전개형**: 컴파일러가 `strcmp` 호출을 자체적으로 펼쳐서 `cmp`/`jne`를 문자별로 반복하는 루프나 완전 언롤(unroll)된 코드로 바꿔버림. 이 경우 겉보기엔 `strcmp`라는 이름이 아예 안 보이지만 본질은 동일하다(이 형태는 REV-0198 "문자별 for 루프 검증 패턴"에서 더 깊이 다룬다).

이 글은 (1) 라이브러리 호출형을 빠르게 알아보고, 비교 대상 문자열(=정답)을 즉시 뽑아내는 방법에 집중한다.

## 화면/코드에서 보이는 징후
**x64 리눅스(System V ABI) 디스어셈블리 예:**
```asm
lea     rdi, [rbp-0x20]      ; 첫 번째 인자: 사용자 입력 버퍼
lea     rsi, [rip+0x2e05]    ; 두 번째 인자: "CTF{sample_flag}" 문자열 주소
call    strcmp
test    eax, eax
jne     wrong                ; 0이 아니면(다르면) 오답 분기
```

**x64 윈도우(MS x64 ABI) 디스어셈블리 예:**
```asm
lea     rcx, [rbp+input]     ; 첫 번째 인자
lea     rdx, [flag_str]      ; 두 번째 인자
call    strcmp
test    eax, eax
jne     wrong_label
```

**IDA/Ghidra 디컴파일 예:**
```c
if ( strcmp(input, "CTF{sample_flag}") == 0 )
{
    puts("Correct!");
}
else
{
    puts("Wrong!");
}
```
Ghidra는 종종 `strcmp` 결과를 부호 비교로 그대로 남겨 `if (strcmp(local_28, "CTF{...}") == 0)` 형태로 매우 깔끔하게 보여준다. IDA도 F5(디컴파일)를 누르면 거의 동일하게 나온다.

## 가장 먼저 할 것
1. IDA에서 **Imports** 탭을 열고 `strcmp`를 찾는다.
2. `strcmp` 위에서 `X` (크로스 레퍼런스 보기)를 눌러 이 함수를 호출하는 모든 위치를 나열한다.
3. 호출 지점으로 이동해서 두 번째 인자(비교 대상 문자열)가 무엇인지 확인한다. 이게 정답 문자열이면 그대로 flag다.

## 단계별 절차
**1) 정적 분석(IDA/Ghidra)**

- `Shift+F12`(Strings 창)를 열어 `CTF{`, `flag{`, `FLAG{` 등으로 시작하는 문자열이 있는지 먼저 찾아본다. 있으면 바로 그 문자열이 정답일 가능성이 매우 높다.
- 문자열이 안 보이면(암호화/난독화된 경우), Imports에서 `strcmp`를 찾아 `X`로 xref를 추적한다.
- 호출 직전의 `lea rsi, [...]` 또는 `lea rdx, [...]`가 가리키는 주소를 더블클릭해서 실제 데이터를 확인한다.

**2) 동적 분석(x64dbg / gdb)**

x64dbg(Windows):
```text
bp strcmp
run
```
브레이크포인트가 걸리면 인자를 확인한다 (x64 fastcall: RCX=arg1, RDX=arg2).
```text
dq rcx L2      ; 첫 번째 인자(사용자 입력) 문자열 확인
dq rdx L2      ; 두 번째 인자(정답 문자열) 확인
```
또는 그냥 Registers 창에서 RDX를 우클릭 → "Follow in Dump"로 메모리를 보면 아스키 문자열이 그대로 보인다.

gdb/pwndbg(Linux, SysV ABI는 RDI=arg1, RSI=arg2):
```text
b strcmp
run
x/s $rdi
x/s $rsi
```

**3) 값 확인 후 종료**

`RSI`(또는 `RDX`)가 가리키는 문자열이 사람이 읽을 수 있는 flag 형태라면 그게 정답이다. 별도의 역산이 필요 없다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings), `X`(xref 보기), `N`(이름 바꾸기로 가독성 향상)
- x64dbg: `bp strcmp`, `dq rdx`(64비트), `dd edx`(32비트 프로세스에서 `dd`로 문자열 포인터 덤프)
- gdb: `b strcmp`, `x/s $rsi`, `info registers`
- 문자열이 안 보이면 `strings <binary> | grep -i flag` 를 먼저 시도(Linux) 또는 `Strings.exe`(Sysinternals, Windows)로 바이너리 전체를 훑는다.

## 출력 해석
- `test eax, eax` 뒤 `jne`가 오답 라벨로 가면 → **EAX==0이 정답 조건**이다. 즉 `strcmp`가 0을 반환해야 통과.
- 반대로 `je`가 오답 라벨로 가면 → 로직이 뒤집혀 보이는 것일 뿐 결론은 같다(EAX==0이면 정답, 다르면 실패라는 strcmp의 정의는 변하지 않는다). 분기 방향을 헷갈리지 말고 항상 "strcmp가 0을 반환하는가"를 기준으로 생각한다.
- 반환값이 0이 아니라 양수/음수인 값으로 추가 분기(`jg`, `jl`)를 하는 코드가 있다면, 이는 단순 일치 검사가 아니라 정렬(sort) 등 다른 목적일 수 있으니 문맥을 다시 확인한다.

## 흔한 실수
- `strcmp`가 아니라 `strncmp`(길이 제한 버전)인데 같은 패턴으로 착각하는 것. `strncmp`는 세 번째 인자(길이)가 있으므로 인자 개수와 레지스터(RCX/RDX/R8 또는 RDI/RSI/RDX)를 다시 확인해야 한다.
- 정적 문자열이 암호화되어 있어서(예: XOR로 난독화된 flag 문자열) `strcmp` 호출 직전에 복호화 루프가 먼저 실행되는 경우를 놓치는 것. 이땐 `lea`로 가리키는 주소의 데이터를 그대로 읽지 말고, 그 주소에 실제로 무엇이 쓰이는지(복호화 루프의 결과인지) 추적해야 한다.
- 컴파일러 최적화(`-O2` 이상)로 `strcmp` 호출이 완전히 인라인되어 함수 이름 자체가 사라진 경우를 "strcmp가 없다"고 오판하는 것. 이때는 REV-0198(문자별 for 루프 검증 패턴)을 참고해서 언롤된 형태를 알아봐야 한다.
- 두 인자의 순서를 헷갈려서 "입력값"과 "정답값" 중 어느 게 어느 레지스터인지 반대로 읽는 것. 함수 인자 자체는 대칭적이라(strcmp(a,b)와 strcmp(b,a)는 결과 부호만 다르고 0 여부는 같음) 실전에선 어느 쪽이 정답인지 그냥 "사람이 읽을 수 있는 문자열"인 쪽을 정답으로 보면 된다.

## 막혔을 때 다음 체크
- 비교 대상이 리터럴 문자열이 아니라 다른 버퍼라면 → 그 버퍼가 어떻게 채워지는지(REV-0199~0202의 변환 루프가 먼저 실행됐을 가능성)를 추적한다.
- `strcmp` 대신 `memcmp`가 보인다면 → REV-0197로 이동.
- 함수 이름 없이 `cmp`/`jne`가 문자 단위로 반복된다면 → REV-0198로 이동.
- 정답 문자열이 이상한 상수들과 함께 계산되는 형태라면 → REV-0199(XOR)/REV-0200(ADD·SUB)/REV-0201(Rotate)/REV-0202(Shift) 중 어떤 변환인지 확인.

## 미니 예제
**예제 1 — 가장 단순한 형태**
```c
// 디컴파일 결과
int check(char *input)
{
    if ( strcmp(input, "CTF{easy_strcmp}") == 0 )
        return 1;
    return 0;
}
```
바로 `CTF{easy_strcmp}`가 정답.

**예제 2 — 비교 순서가 반대인 경우**
```c
if ( strcmp("S3cur3_Flag_42", input) == 0 )
    puts("Correct!");
```
인자 순서만 바뀌었을 뿐 `strcmp`의 0 여부 판정은 동일하므로, 정답은 여전히 `S3cur3_Flag_42`.

**예제 3 — 길이 검사가 먼저 오는 경우**
```c
if ( strlen(input) == 20 && strcmp(input, real_flag) == 0 )
    puts("Correct!");
```
여기서 `real_flag`가 리터럴이 아니라 전역 변수라면, IDA에서 `real_flag`의 초기값(.data 섹션)을 확인하거나, 실행 중에 해당 주소를 덤프해서 값을 읽는다. `strlen` 체크는 부가 힌트로, flag 길이가 20자임을 미리 알려준다.

**예제 4 — x64dbg로 동적 확인**
바이너리를 x64dbg로 열고 `bp strcmp` 후 실행하면:
```text
RCX = 0x0000000000401234  ->  "myguess123"
RDX = 0x0000000000402050  ->  "CTF{dynamic_check_ok}"
```
RDX 쪽이 사람이 읽을 수 있는 flag 형태이므로 이것이 정답이다.

**예제 5 — 처음부터 끝까지 실행되는 전체 스크립트**

아래 스크립트는 "IDA Hex View나 x64dbg 메모리 덤프에서 바이트를 그대로 복사해온 상황"을 가정하고, 그 값을 파이썬으로 옮겨 flag를 즉시 복원한 다음, 로컬에서 직접 만든 `my_strcmp` 함수로 "이 값이 정말 정답인지"까지 재확인한다. 파이썬을 처음 써보는 사람도 그대로 복사해서 실행해보면 된다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# REV-0196 실전 스크립트: strcmp 비교 대상 문자열을 바로 읽어서 flag를 복원한다.

def my_strcmp(a: bytes, b: bytes) -> int:
    # C 표준 라이브러리의 strcmp와 똑같이 동작하도록 직접 만든 함수다.
    # 앞에서부터 한 바이트씩 비교하다가 다른 바이트가 나오면 그 차이를 반환하고,
    # 끝까지 같으면(둘 다 끝났으면) 0을 반환한다 -> "0이면 일치"라는 규칙은 그대로 유지된다.
    for x, y in zip(a, b):
        if x != y:
            return x - y          # 다른 바이트를 찾으면 그 차이를 바로 리턴
    return len(a) - len(b)        # 여기까지 왔으면 길이 차이로 판정(둘 다 같으면 0)

# 1) IDA Hex View(Alt+8)나 x64dbg의 "Follow in Dump"에서 RSI/RDX가 가리키는 주소를 보고
#    화면에 나온 raw byte들을 그대로 옮겨적은 문자열이라고 가정한다.
dumped_hex = "4354467b656173795f737472636d707d"  # 실제 문제에서는 여기에 덤프한 값을 넣는다

# 2) bytes.fromhex()는 "16진수 두 글자 = 1바이트"로 해석해서 파이썬 bytes로 바꿔준다.
answer = bytes.fromhex(dumped_hex)

# 3) C 문자열은 항상 끝에 NUL(0x00)이 붙으므로, 혹시 덤프에 그 뒤 쓰레기 값까지 포함됐다면
#    첫 번째 0x00에서 잘라내서 진짜 문자열 부분만 남긴다.
answer = answer.split(b"\x00")[0]

# 4) 사람이 읽을 수 있는 문자열(str)로 디코딩한다. 이게 곧 정답 flag다.
flag = answer.decode()
print("복원된 flag:", flag)
# 실행 결과: 복원된 flag: CTF{easy_strcmp}

# 5) 실전에서는 이 값을 진짜로 입력해도 되는지, 직접 만든 my_strcmp로 한 번 더 확인해볼 수 있다.
my_guess = b"CTF{easy_strcmp}"   # 이 자리에 실제로 입력창에 쳐볼 문자열을 넣는다
result = my_strcmp(my_guess, answer)
if result == 0:
    print("strcmp 결과 0 -> 일치! 이 값을 그대로 제출하면 된다.")
else:
    print("strcmp 결과", result, "-> 아직 불일치, 값을 다시 확인해야 한다.")
# 실행 결과: strcmp 결과 0 -> 일치! 이 값을 그대로 제출하면 된다.
```

## 관련 글
- REV-0197 — memcmp 기반 Flag 검증 패턴
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- ../assembly/rev-0071-call.md — CALL 명령어와 인자 전달 규칙

## 출처/검증
- `strcmp` 동작(0 반환 = 일치)은 C 표준 라이브러리 명세(ISO C `string.h`) 기준.
- System V AMD64 및 Microsoft x64 호출 규약(레지스터 인자 순서)은 각 ABI 공식 문서 기준.
- 위 예제 코드는 CTF 스타일 검증 로직을 재현한 예시이며 실제 특정 문제의 정답이 아니다(2026-09-08 작성 시 확인).
