---
id: REV-0110
title: "strcmp strncmp memcmp 비교 추적"
slug: "rev-0110-comparison-functions"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, ltrace]
keywords: ["strcmp", "strncmp", "memcmp", "문자열 비교", "패스워드 비교", "flag 비교", "return 0"]
aliases: ["strcmp 추적", "비밀번호 비교 찾기", "flag 비교 로직 찾기", "memcmp 인자"]
symptom_keywords: ["정답 문자열이 어디 있는지 모르겠음", "strcmp 결과를 어떻게 읽는지 모르겠음", "비교 로직을 못찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
"입력한 값이 맞는지 틀린지" 판별하는 CTF 리버싱 문제 대부분은 결국 `strcmp`/`strncmp`/`memcmp` 호출(또는 이를 흉내낸 수동 반복문) 한 지점으로 귀결되며, 이 함수들의 **두 번째 인자(RSI)** 에 정답/비교 대상 문자열이 들어있는 경우가 많아 그 인자를 GDB로 들여다보는 것이 가장 빠른 "정답 찾기" 방법이다.

## 언제 검색해야 하나
- "비밀번호를 맞히면 통과" 류의 CTF 리버싱 문제에서 정답 문자열이 어디 저장돼 있는지, 비교 로직이 어디인지 찾고 싶을 때
- 디스어셈블리에서 `call strcmp`, `call memcmp` 다음에 `test eax, eax` 또는 `cmp eax, 0`이 나오는 패턴을 봤는데 이걸 어떻게 해석해야 할지 모를 때
- `strings ./chall`로 찾은 후보 문자열이 실제 정답인지, 아니면 다른 용도(에러 메시지 등)인지 헷갈릴 때

## 핵심 개념

### 세 함수의 시그니처와 반환값 의미
| 함수 | 시그니처 | 비교 범위 | 반환값 |
|---|---|---|---|
| `strcmp` | `int strcmp(const char *s1, const char *s2)` | NUL 바이트가 나올 때까지 전체 | `0`=완전히 같음, 음수/양수=다름(사전순 비교) |
| `strncmp` | `int strncmp(const char *s1, const char *s2, size_t n)` | 최대 `n`바이트 또는 NUL까지 | `strcmp`과 동일한 규칙 |
| `memcmp` | `int memcmp(const void *s1, const void *s2, size_t n)` | 정확히 `n`바이트(NUL 무시, 바이너리 비교) | 같으면 `0`, 다르면 음수/양수 |

세 함수 모두 SysV AMD64 규약(REV-0106)에 따라 `RDI=s1`, `RSI=s2`, (`strncmp`/`memcmp`라면) `RDX=n`으로 인자를 받고, 결과는 `EAX`에 담긴다. **"같다"는 결과가 `0`이라는 점**이 초보자가 가장 헷갈리는 부분이다 — 조건문에서 `if (strcmp(input, answer) == 0)`처럼 "0이면 성공" 로직이 흔하다.

### 어느 쪽이 사용자 입력이고 어느 쪽이 정답인가
관례상 `s1`(`RDI`, 첫 번째 인자)에 사용자 입력을, `s2`(`RSI`, 두 번째 인자)에 하드코딩된 정답/비교 대상을 넣는 코드가 많지만, **컴파일러나 프로그래머에 따라 순서가 반대일 수도 있다.** `strcmp`의 결과는 순서를 바꿔도 부호만 반대일 뿐 "같다/다르다" 판정 자체는 동일하므로, 순서가 바뀌어도 로직에는 영향이 없다. 따라서 실전에서는 두 인자를 모두 GDB로 확인해서, 둘 중 어느 쪽이 프로그램 시작부터 고정된 값(`.rodata` 섹션의 문자열, 즉 바이너리에 이미 박혀있는 값)이고 어느 쪽이 방금 사용자가 입력한 값(스택/힙 버퍼)인지로 구분하는 것이 정확하다.

### 정답 문자열을 정적으로 먼저 찾는 법
`strcmp`/`strncmp`로 비교되는 하드코딩된 문자열은 대개 `.rodata`(읽기 전용 데이터) 섹션에 있고, `strings ./chall`로도 바로 보인다. 하지만 여러 후보 문자열이 있을 때 어떤 것이 진짜 비교 대상인지 정적으로 판단하기 어렵다면, `call strcmp` 직전에 `lea rsi, [rip+0x...]`(RIP 상대 주소로 `.rodata`의 문자열을 가리키는 코드) 패턴을 찾아 그 주소가 가리키는 문자열을 확인하는 방법이 가장 확실하다.

### memcmp가 쓰이는 이유 — 문자열 검색 회피
프로그래머(또는 CTF 문제 제작자)가 `strings`나 `grep`으로 정답이 쉽게 노출되는 것을 피하고 싶을 때, 정답 문자열을 평문으로 두지 않고 바이트 배열로 흩어 놓거나 XOR로 인코딩해둔 뒤 `memcmp`로 비교하는 경우가 흔하다. 이런 경우 `.rodata`를 `strings`로 훑어도 정답이 그대로 안 보이고, `memcmp` 호출부에서 두 번째 인자가 가리키는 바이트들을 직접 덤프해서 디코딩 로직(XOR 키 등)을 역으로 따라가야 한다.

### 바이트 단위 수동 비교(strcmp 흉내)로 문자열 검색을 피하는 경우
가장 흔한 CTF 안티-치트 패턴 중 하나는 `strcmp`를 아예 안 쓰고, `for` 루프를 돌면서 `cmp byte ptr [rdi+i], byte ptr [rsi+i]` 형태로 한 바이트씩 직접 비교하는 코드다. 이렇게 하면 import 목록(REV-0101)에 `strcmp`가 아예 안 나타나서 "비교 함수가 없다"고 착각하기 쉽다. 이런 경우는 루프 안에서 `cmp`/`jne` 패턴이 반복되는 것을 찾아야 한다 — REV-0110이 이 문서에서 다루는 범위를 넘어가지만, "정답 문자열이 안 보이면 반복문 안의 바이트 비교를 의심하라"는 원칙만은 기억해두자.

### strncmp/memcmp의 길이(n) 인자가 알려주는 것
`strncmp(input, "flag{", 5)`처럼 `n`이 정답 전체 길이보다 짧다면, "정답의 앞부분(접두사)만 확인하는" 로직이라는 뜻이다. 이런 패턴은 여러 단계로 나뉜 비교(각 부분마다 다른 `strncmp` 호출)로 이어지는 경우가 많아, `n` 값을 확인하는 것만으로도 전체 정답의 구조(길이, 몇 조각으로 나뉘어 검증되는지)를 짐작할 수 있다.

## 화면/코드에서 보이는 징후
- `call strcmp` 또는 `call strcmp@plt` 바로 다음에 `test eax, eax`(또는 `cmp eax, 0`) → `jne`/`jnz`(다르면 실패 경로로 분기) 패턴
- `call memcmp` 직전에 `mov edx, N`(고정 길이 리터럴)이 보임 — 이 `N`이 비교 대상의 바이트 길이
- `.rodata` 섹션에 `flag{`, `Correct!`, `Wrong password` 같은 문자열이 함께 존재 — `strings` 실행 시 바로 눈에 띔

## 가장 먼저 할 것
`strings ./chall | grep -i 'flag\|correct\|wrong\|password'` 같은 명령으로 후보 문자열을 먼저 훑는다. 후보가 나오면 IDA에서 그 문자열의 Xref를 따라가 어떤 함수, 어떤 비교 호출 직전에 쓰이는지 확인한다. 후보가 하나도 안 나온다면 `memcmp`/수동 바이트 비교 인코딩을 의심하고 동적 분석(GDB)으로 넘어간다.

## 단계별 절차

**1) 후보 문자열 정적 검색**
```bash
strings ./chall | grep -iE 'flag|correct|wrong|password|success'
```

**2) 비교 함수 호출부 찾기**
```bash
objdump -d ./chall | grep -B15 'call.*strcmp@plt'
```

**3) GDB로 두 인자를 모두 확인**
```gdb
break *0x<call주소>
run
x/s $rdi
x/s $rsi
```
`strncmp`/`memcmp`라면 길이도 함께 확인:
```gdb
p/x $rdx
```

**4) 반환값과 분기 조건 확인**
```gdb
finish
p $eax
```
`$eax`가 `0`이면 두 인자가 같다는 뜻이다. 이후 코드가 `test eax,eax; jne fail`이라면, `eax==0`일 때(즉 같을 때) `jne`가 분기하지 않고 정상 경로(성공)로 이어진다는 뜻이다.

**5) memcmp/수동 비교로 인코딩된 경우 바이트 덤프**
```gdb
x/16xb $rsi
```
16진수 바이트 나열을 직접 보고, 필요하면 파이썬 등으로 XOR/인코딩을 역산한다(이 단계는 알고리즘 분석 영역이므로 상황에 따라 다르다).

## 명령어/단축키
```bash
strings ./chall | grep -iE 'flag|correct|wrong|password'
objdump -d ./chall | grep -B15 'call.*strcmp@plt'
```
GDB: `x/s $rdi`, `x/s $rsi`, `p/x $rdx`, `finish`, `p $eax`, `x/16xb $rsi`

## 출력 해석
- `x/s $rsi`가 사람이 읽을 수 있는 평문 문자열이면 인코딩 없이 그대로 비교하는 문제다.
- `x/16xb $rsi`가 사람이 읽을 수 없는 바이트 나열이면, 이 값 자체가 정답이 아니라 인코딩된 형태이거나 이미 사용자 입력을 가공한 중간 버퍼일 수 있다 — 어느 쪽 버퍼인지(`.rodata` 고정값 vs 런타임 계산값) 주소 범위로 구분한다(`.rodata`는 실행 파일 매핑 영역, 스택/힙 버퍼는 다른 범위).
- `finish` 이후 `$eax`가 `0`이 아니면 두 값이 다르다는 뜻이며, 부호(양수/음수)는 사전순으로 어느 쪽이 더 큰지를 나타내지만 "같다/다르다" 판정에서는 대개 무시된다.

## 흔한 실수
- `strcmp` 반환값 `0`을 "실패"로 착각하는 것 — C 관례에서 `0`은 대개 "같다/성공"을 뜻하지만, 이 관례가 헷갈려 부호를 반대로 해석하는 실수가 잦다. 반드시 실제 분기 코드(`jne`가 실패로 가는지 성공으로 가는지)까지 같이 확인한다.
- `strcmp`만 찾다가 `memcmp`나 수동 바이트 비교 루프를 놓치는 것 — import 목록에 `strcmp`가 없다고 비교 로직이 없다고 단정하면 안 된다.
- `s1`, `s2` 중 아무 쪽이나 정답이라고 가정하는 것 — 반드시 GDB로 두 인자 모두 확인해서 어느 쪽이 고정값(`.rodata`)이고 어느 쪽이 사용자 입력인지 구분해야 한다.
- 정답이 한 번의 `strcmp`로 끝날 거라 가정하는 것 — `strncmp`로 여러 조각을 나눠 검증하거나, `strcmp` 여러 번을 조합하는 문제도 흔하다.

## 막혔을 때 다음 체크
- 사용자 입력이 어디서 들어와서 이 비교 지점까지 오는지 앞 단계를 보고 싶다면 → REV-0109 scanf fgets read 입력 추적
- 호출 규약 자체가 헷갈린다면 → REV-0106 SysV AMD64 Calling Convention
- 코드 수정 없이 `strcmp` 호출과 인자를 빠르게 다 보고 싶다면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기

## 미니 예제
```bash
$ strings ./chall | grep -i flag
flag{th1s_1s_n0t_th3_r3al_fl4g}
Correct!
Wrong password.
```
```gdb
(gdb) break *0x401203
(gdb) run
input: test123
(gdb) x/s $rdi
0x7fffffffe4a0: "test123"
(gdb) x/s $rsi
0x402010: "flag{th1s_1s_n0t_th3_r3al_fl4g}"
(gdb) finish
(gdb) p $eax
$1 = -3
```
`$eax`가 `0`이 아니므로("-3", 즉 다름) 비교 실패, 방금 입력한 `test123`이 정답이 아님을 확인했다. 정답 후보 문자열(`.rodata`에서 나온 `flag{...}`)을 그대로 입력하면 `$eax`가 `0`이 되는지 재확인해보는 것이 다음 단계다.

## 관련 글
- REV-0109 — scanf fgets read 입력 추적
- REV-0106 — SysV AMD64 Calling Convention
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기

## 출처/검증
- `strcmp`/`strncmp`/`memcmp` 함수 시그니처 및 반환값 규칙: ISO C 표준 라이브러리(`<string.h>`) 명세 및 Linux man-pages(`strcmp(3)`, `strncmp(3)`, `memcmp(3)`) 기준 (2026-09-08 검증).
