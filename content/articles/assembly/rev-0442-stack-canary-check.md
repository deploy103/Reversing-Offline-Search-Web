---
id: REV-0442
title: "스택 카나리(Stack Canary) 체크 시퀀스 분석"
slug: "rev-0442-stack-canary-check"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - stack canary
  - 스택 카나리
  - "fs:0x28"
  - "gs:0x28"
  - __stack_chk_fail
  - __stack_chk_guard
  - __security_cookie
  - __security_check_cookie
  - stack protector
  - stack smashing detected
  - GS 보호
  - fstack-protector
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
aliases:
  - 스택카나리가 뭐임
  - "fs:0x28이 뭐임"
  - stack_chk_fail이 뭐임
  - 카나리 체크 코드 분석
  - security_cookie가 뭐임
symptom_keywords:
  - "fs:0x28 mov 명령이 자꾸 나옴"
  - stack smashing detected가 뜸
  - __stack_chk_fail 함수가 호출됨
  - security_check_cookie가 호출됨
  - 카나리 값이 매번 다름
last_verified: "2026-09-08"
---

## 한 줄 요약
스택 카나리는 지역 버퍼와 저장된 반환 주소 사이에 심어둔 난수 값으로, 함수가 끝나기 직전 이 값이 그대로인지 확인해서 **버퍼 오버플로가 발생했는지**를 탐지하는 컴파일러 보호 기법이며, 실제 검증 로직과 무관한 "노이즈" 코드이므로 알아보고 넘어갈 줄 알아야 한다.

## 언제 검색해야 하나
- 함수 프롤로그에 `mov rax, fs:0x28`(Linux) 같은 낯선 세그먼트 레지스터 접근이 보일 때
- 함수 에필로그 직전에 `xor rax, fs:0x28` 다음 `je`/`jne`가 나오고, 그 분기 끝에 `call __stack_chk_fail`이 있을 때
- Windows 바이너리에서 `__security_cookie`, `__security_check_cookie` 심볼이 임포트/호출되는 것을 봤을 때
- 실행 중 "stack smashing detected"라는 메시지가 뜨고 프로그램이 죽는 이유를 조사할 때
- `checksec` 결과에서 "Canary found"가 나왔는데 실제 어셈블리에서 이게 어떻게 생겼는지 확인하고 싶을 때

## 핵심 개념

### 스택 카나리가 막으려는 것
클래식한 스택 버퍼 오버플로 공격은 지역 버퍼(예: `char buf[16]`)에 정해진 크기보다 많은 데이터를 써서, 버퍼 뒤에 있는 **저장된 RBP, 저장된 반환 주소**까지 덮어쓰는 방식이다. 반환 주소가 공격자가 원하는 값으로 바뀌면 `RET` 실행 시 임의의 코드로 실행 흐름이 넘어갈 수 있다.

스택 카나리는 이를 막기 위해, 컴파일러가 버퍼와 저장된 RBP/반환 주소 **사이**에 임의의 난수 값을 하나 심어둔다. 순차적으로 메모리를 덮어쓰는 일반적인 오버플로는 반환 주소에 도달하기 전에 반드시 이 카나리 값을 먼저 건드리게 되므로, 함수가 끝나기 직전에 카나리 값이 원래 값과 같은지 확인하면 오버플로 여부를 탐지할 수 있다. GCC/Clang은 `-fstack-protector`(또는 `-fstack-protector-all`/`-strong`) 옵션으로, MSVC는 `/GS`(기본 활성화)로 이 기능을 넣는다.

### Linux x64 (glibc, GCC/Clang) 패턴
프롤로그에서 TLS(Thread Local Storage) 영역의 고정 오프셋에서 카나리 기준값을 읽어 스택에 복사해둔다.
```asm
; 프롤로그
mov     rax, fs:0x28        ; TLS 기준 fs 세그먼트 + 0x28 위치의 카나리 값을 읽음
mov     [rbp-8], rax        ; 지역 버퍼 바로 위, 스택 프레임에 저장
xor     eax, eax            ; (레지스터 정리, 카나리 값 자체를 레지스터에 남기지 않으려는 관용구)
```
에필로그에서는 저장해둔 값과 현재 TLS의 값을 XOR로 비교한다.
```asm
; 에필로그
mov     rax, [rbp-8]
xor     rax, fs:0x28        ; 같으면 결과 0, 다르면 0이 아님
je      .ok                 ; ZF=1(같음)이면 정상 → 그냥 반환
call    __stack_chk_fail    ; 다르면(변조됨) 이 함수가 호출됨 → 메시지 출력 후 abort()
.ok:
leave
ret
```
32비트 Linux(glibc)에서는 위치가 `fs:0x28` 대신 `gs:0x14`다. 세그먼트(`fs`/`gs`)와 오프셋 숫자만 다를 뿐 로직 구조는 동일하다.

`__stack_chk_fail`이 호출되면 보통 "*** stack smashing detected ***: terminated" 메시지를 표준 에러에 출력하고 `abort()`를 호출해 프로세스를 즉시 종료시킨다. 이게 바로 오버플로가 있는 바이너리를 무심코 실행했을 때 보게 되는 그 메시지의 정체다.

### Windows x64 (MSVC /GS) 패턴
Windows는 TLS 세그먼트가 아니라 전역 변수 `__security_cookie`를 사용한다. 이 값은 프로세스 시작 시 `__security_init_cookie`가 시스템 엔트로피(주소, 시간 등)를 섞어 한 번 초기화한다.
```asm
; 프롤로그 (개략)
sub     rsp, 0x30
mov     rax, [__security_cookie]
xor     rax, rbp                 ; 스택 프레임 값과 섞어 함수마다 다른 값을 만듦(추가 엔트로피)
mov     [rbp+cookie_slot], rax
```
```asm
; 에필로그
mov     rcx, [rbp+cookie_slot]
xor     rcx, rbp
call    __security_check_cookie  ; RCX에 담긴 쿠키를 검사하는 헬퍼 함수
leave
ret
```
`__security_check_cookie` 내부에서 실제 비교가 이루어지며, 값이 다르면 `__report_gsfailure`를 호출해 프로세스를 빠르게 종료시킨다(fail-fast). 이 구조는 세그먼트 레지스터를 직접 쓰지 않는다는 점이 Linux glibc 방식과의 주요 차이다.

### 플래그와 레지스터 효과
`xor rax, fs:0x28`(또는 `xor rcx, rbp`)은 일반 `XOR`와 동일하게 `ZF`, `SF`, `PF`를 결과에 따라 세팅하고 `CF`, `OF`를 0으로 클리어한다(REV-0057 참고). 카나리 검사는 정확히 이 `ZF`(같으면 1)를 이용해 `je`/`jne`로 분기한다. RSP/RIP 자체는 이 비교 명령으로는 변하지 않고, 실패 시 호출되는 `__stack_chk_fail`/`__security_check_cookie`가 일반 `CALL`처럼 반환 주소를 push한 뒤 진입한다(REV-0071 참고).

### IDA/Ghidra 디컴파일에서 보이는 형태
Hex-Rays는 이 패턴을 인식해서 지역 변수 하나를 `canary` 또는 `v5`(주석 `[stack cookie]` 포함)로 표시하고, 아래와 같이 비교적 원본에 가깝게 보여준다.
```c
canary = *(_QWORD *)(fs_base + 0x28);
... // 사용자 로직
if ( canary != *(_QWORD *)(fs_base + 0x28) )
    __stack_chk_fail();
return result;
```
버전에 따라서는 이 검사 자체를 완전히 숨기고 사용자 로직만 보여주는 경우도 있다(IDA가 잘 인식했을 때). Ghidra도 유사하게 `local_XX` 변수와 `__stack_chk_fail` 호출로 표시한다. 어느 쪽이든, 이 카나리 관련 코드는 **원본 소스에 있던 로직이 아니라 컴파일러가 자동으로 삽입한 보호 코드**라는 것을 인식하고 무시해야 진짜 프로그램 로직에 집중할 수 있다.

### 리버싱 관점에서의 의미
1. **취약점 분석/exploit 개발**: 카나리가 있는 바이너리에서 스택 오버플로를 트리거하려면 카나리 값을 정확히 맞춰써야 크래시 없이 반환 주소까지 덮어쓸 수 있다. 카나리는 매 프로세스 실행마다 무작위로 바뀌므로(초기화 시점에 `/dev/urandom` 기반 엔트로피 이용), 공격자는 별도의 정보 유출(canary leak) 취약점으로 그 값을 먼저 알아내야 한다. 카나리의 **최하위 1바이트는 항상 0x00으로 고정**되어 있는데, 이는 `printf("%s", buf)`나 `strcpy` 같은 문자열 함수가 NUL 바이트에서 멈추기 때문에 카나리가 문자열 출력 버그로 통째로 새어나가는 것을 막기 위한 설계다.
2. **일반 리버싱**: 카나리 체크는 CTF의 "정답 검증" 로직과 아무 관련이 없는 순수한 방어 코드다. 초보자가 이 XOR 비교를 실제 flag 검증 로직으로 착각해서 분석 시간을 낭비하는 경우가 매우 흔하다.
3. **바이너리 보호 확인**: `checksec`(REV-0096)이나 `readelf -d`/IDA의 함수 목록에서 `__stack_chk_fail` 임포트 유무를 확인하면 정적으로도 카나리 보호 여부를 빠르게 판단할 수 있다(REV-0105 참고).

## 화면/코드에서 보이는 징후
- 프롤로그의 `mov rax, fs:0x28`(Linux) 또는 `mov rax, [__security_cookie]`(Windows)
- 에필로그의 `xor rax, fs:0x28` 또는 `xor rcx, rbp` 뒤에 `je`/`jne`
- `call __stack_chk_fail`(Linux) 또는 `call __security_check_cookie`(Windows)로 이어지는 분기
- 실행 시 출력되는 "*** stack smashing detected ***" 메시지

## 가장 먼저 할 것
1. `checksec`(REV-0096) 또는 IDA Imports 탭에서 `__stack_chk_fail`/`__security_check_cookie` 존재 여부를 먼저 확인한다.
2. 함수 프롤로그에서 `fs:0x28`/`__security_cookie` 접근을 찾아, 그 값이 어느 스택 슬롯(`[rbp-8]` 등)에 저장되는지 확인한다.
3. 이 슬롯이 실제 취약점 분석의 관심사(입력 버퍼)가 아니라 보호 코드임을 인지하고, 진짜 로직에 집중한다.

## 단계별 절차
1. 함수 프롤로그에서 `mov rax, fs:[0x28]`(x64) 또는 `mov eax, gs:[0x14]`(x86 계열의 유사 패턴)처럼 TLS에서 카나리 값을 읽어 스택에 저장하는 코드를 찾는다.
2. 함수 에필로그 직전에서 같은 위치를 다시 읽어 저장해둔 값과 `cmp`/`xor`로 비교하는 코드를 찾는다.
3. 비교가 다르면 호출되는 함수(보통 `__stack_chk_fail`)를 확인한다 — 이게 보이면 스택 오버플로 탐지 코드임을 확정한다.
4. CTF 실습 목적으로 이 체크를 우회해야 한다면, 카나리 값 자체를 유출하거나 덮어쓰지 않는 페이로드를 설계해야 한다는 점을 기록해둔다.

## 명령어/단축키
- IDA: Imports 탭에서 `__stack_chk_fail` 확인 → `X`로 xref를 찾으면 카나리 체크가 있는 모든 함수 목록이 나온다.
- x64dbg: `fs:[0x28]`을 Watch 창에 등록하면 카나리 기준값을 실시간으로 볼 수 있다.
- GDB/Pwndbg: `canary` 명령(pwndbg 확장)으로 현재 프로세스의 카나리 값을 바로 조회 가능. `p $fs_base` 로 TLS 베이스 주소 확인 후 `x/gx $fs_base+0x28`.

## 흔한 실수
- 카나리 XOR 비교를 실제 사용자 입력 검증(예: 비밀번호 체크) 로직으로 착각해서 그 값을 "정답"이라 여기고 분석하는 것.
- 카나리 값이 매 실행마다 랜덤하게 바뀐다는 것을 모르고, 한 번 디버거로 확인한 값을 다른 실행에서도 그대로 쓰려는 것 — ASLR/난수 시드가 그대로가 아니면 값이 달라진다.
- `fs:0x28`/`gs:0x28` 같은 세그먼트 레지스터 접근을 보고 "이건 그냥 일반 메모리 접근이다"라고 넘어가서 TLS 기반 카나리라는 걸 못 알아채는 것.
- Windows `/GS` 쿠키와 Linux 카나리를 완전히 동일한 메커니즘이라고 착각하는 것 — Windows는 세그먼트 레지스터가 아니라 전역 변수 `__security_cookie`와 `__security_check_cookie` 헬퍼 함수 호출 방식을 쓴다.
- 카나리 최하위 바이트가 항상 0x00이라는 사실을 모른 채, 문자열 출력 기반 정보 유출 공격을 설계할 때 이 제약을 놓치는 것.

## 막혔을 때 다음 체크
- 카나리와 별개로 다른 컴파일러 보호 기법(NX, PIE, RELRO)까지 한 번에 확인하고 싶으면 → REV-0105.
- 스택 프레임에서 카나리가 정확히 어느 위치에 저장되는지 구조가 헷갈리면 → REV-0031.
- 카나리 체크에 쓰이는 XOR 명령 자체의 플래그 규칙이 궁금하면 → REV-0057.
- `__stack_chk_fail` 호출 이후 프로그램이 왜 바로 종료되는지 더 알고 싶으면 → REV-0071(CALL)로 호출 구조를 다시 확인.

## 미니 예제

**예제 1 — Linux x64 (glibc) 전체 프롤로그+에필로그**
```asm
push    rbp
mov     rbp, rsp
sub     rsp, 0x30
mov     rax, fs:0x28
mov     [rbp-8], rax
xor     eax, eax
; ... buf에 데이터 읽어들이는 로직 (예: gets, read) ...
mov     rax, [rbp-8]
xor     rax, fs:0x28
je      .Lok
call    __stack_chk_fail
.Lok:
leave
ret
```

**예제 2 — Windows x64 (MSVC /GS) 개략형**
```asm
sub     rsp, 0x40
mov     rax, [__security_cookie]
xor     rax, rbp
mov     [rbp+0x20], rax
; ... 지역 버퍼 사용 로직 ...
mov     rcx, [rbp+0x20]
xor     rcx, rbp
call    __security_check_cookie
add     rsp, 0x40
ret
```

**예제 3 — 32비트 Linux 변형**
```asm
mov     eax, gs:0x14
mov     [ebp-4], eax
; ...
mov     eax, [ebp-4]
xor     eax, gs:0x14
je      .Lok
call    __stack_chk_fail
```

**예제 4 — checksec 출력과 대응**
```text
$ checksec ./vuln
Canary   : Found
```
"Canary: Found"가 뜨면 위와 같은 `fs:0x28`/`__stack_chk_fail` 패턴이 함수 안에 있다고 예상하고 찾아보면 된다.

## 관련 글
- REV-0441 — Switch문 점프 테이블(Jump Table) 완전 분석
- REV-0096 — checksec 결과 읽는 법
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0031 — 스택 프레임이 무엇인지
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화

## 출처/검증
- 스택 카나리/스택 프로텍터의 목적과 프롤로그·에필로그 삽입 방식(`-fstack-protector`): GCC 공식 문서 "Options That Control Optimization" 및 GNU libc `__stack_chk_fail` 구현 기준 (2026-09-08 검증).
- Linux x86-64 TLS 카나리 위치(`fs:0x28`)와 하위 바이트 0x00 설계: glibc `sysdeps` 스택 프로텍터 초기화 코드 및 다수의 공개 리버싱/exploit 문서 기준.
- Windows `/GS` 쿠키(`__security_cookie`, `__security_check_cookie`) 동작: Microsoft Learn "/GS (Buffer Security Check)" 공식 문서 기준.
