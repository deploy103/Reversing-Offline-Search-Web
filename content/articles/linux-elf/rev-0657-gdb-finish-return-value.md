---
id: REV-0657
title: "GDB에서 함수 반환값을 finish로 확인하는 법"
slug: "rev-0657-gdb-finish-return-value"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["gdb finish", "run till exit", "value returned", "함수 반환값 확인", "rax 반환값"]
aliases: ["gdb finish 명령어", "finish 사용법", "함수 리턴값 gdb로 보기", "run till exit from"]
symptom_keywords: ["finish not meaningful in the outermost frame", "value returned has type unknown", "함수가 뭘 리턴하는지 모르겠음", "rax 값을 확인하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
GDB에서 어떤 함수 안에 들어가 있는 상태(브레이크포인트에 걸렸거나 `step`으로 진입한 상태)에서 `finish`를 치면, 그 함수가 끝날 때까지 자동으로 실행한 뒤 "Value returned is $1 = ..." 형태로 **리턴값을 바로 보여준다** — `strcmp`, `malloc`, 사용자 정의 함수 할 것 없이 "이 함수가 뭘 돌려주는지"를 한 번의 명령으로 확인하는 가장 빠른 방법이다.

## 언제 검색해야 하나
- `strcmp`나 `malloc` 같은 함수에 브레이크포인트를 걸어놓고, 이 함수가 이번 호출에서 정확히 어떤 값을 리턴하는지 바로 확인하고 싶을 때
- `finish`를 쳤는데 "finish not meaningful in the outermost frame" 같은 에러가 나서 원인을 알고 싶을 때
- 리턴값 타입이 안 나오고 "Value returned has type: <unknown return type>"라고 나올 때 실제 값을 어떻게 읽어야 하는지 궁금할 때

## 핵심 개념

### finish가 하는 일 — 현재 프레임의 return까지 실행
`finish`는 **현재 선택된 스택 프레임이 `ret`으로 리턴할 때까지** 프로그램을 계속 실행시키는 명령이다. 내부적으로는 그 프레임의 리턴 주소에 임시 브레이크포인트를 걸고 `continue`하는 것과 비슷하게 동작하지만, GDB가 자동으로 계산해서 걸어주기 때문에 사람이 직접 리턴 주소를 찾을 필요가 없다. 함수 안에서 `stepi`/`nexti`를 한 줄씩 눌러가며 리턴 지점까지 가는 대신, `finish` 한 번으로 "이 함수 끝까지 실행해서 나가라"를 표현할 수 있다.

### x86-64 SysV ABI에서 리턴값은 어디에 있는가
SysV AMD64 calling convention(REV-0106)에 따르면 정수/포인터 리턴값은 **RAX**(32비트 함수면 EAX)에 담긴다. 64비트를 초과하는 구조체는 RAX:RDX 페어나 숨겨진 포인터(hidden pointer, 첫 인자로 전달된 반환 버퍼 주소)를 쓰는 경우도 있고, 부동소수점 리턴값은 **XMM0**에 담긴다. `finish`가 "Value returned is ..."로 보여주는 값은 결국 이 규약에 따라 RAX(또는 XMM0)에서 읽어온 것을, 디버그 정보에 있는 함수 원형(prototype)을 참고해서 적절한 타입으로 해석한 것이다.

### 디버그 정보 유무에 따른 차이
- **디버그 정보(`-g`로 컴파일)가 있는 함수**: GDB가 함수의 실제 리턴 타입(`int`, `char *` 등)을 알고 있어서 `Value returned is $1 = 0`처럼 타입에 맞게 깔끔하게 보여준다.
- **디버그 정보가 없는 라이브러리 함수(`strcmp` 등, strip된 바이너리 포함)**: GDB가 원형을 모르면 기본적으로 `int`로 가정해서 RAX의 하위 32비트만 보여주거나, 아예 `Value returned has type: <unknown return type>. Cannot determine contents`라고 나올 수 있다. 이럴 때는 `finish` 직후 수동으로 `print $rax` 또는 `p/x $rax`를 쳐서 전체 64비트 값을 직접 읽어야 한다.

### "outermost frame" 에러의 의미
`finish`는 **현재 프레임을 호출한 상위 프레임(caller)이 있어야** 동작한다. `main`처럼 GDB가 더 이상 호출자를 추적할 수 없는 최상위 프레임(또는 `__libc_start_main` 이전, 콜스택이 끊긴 지점)에서 `finish`를 치면 `"finish" not meaningful in the outermost frame.` 에러가 난다. 이건 GDB가 어디로 리턴해야 할지 모른다는 뜻이므로, `finish` 전에 자신이 정말 호출된 함수 안에 있는지, `backtrace`(`bt`)로 콜스택이 정상적으로 잡히는지 먼저 확인해야 한다.

## 화면/코드에서 보이는 징후
소스에서 찾는 게 아니라 GDB 세션 중에 나타나는 상황이다. 어떤 함수(`strcmp`, `check_password` 등) 안에 브레이크포인트가 걸려서 멈춰 있고, 그 함수가 무엇을 리턴하는지에 따라 이후 분기(`test eax, eax` / `jz`/`jnz`)가 결정되는 코드가 보인다면 `finish`를 쓸 타이밍이다.

## 가장 먼저 할 것
먼저 관심 있는 함수에 브레이크포인트를 걸고 `run`으로 그 지점까지 도달한다:
```bash
(gdb) break check_password
(gdb) run
```
브레이크포인트에 걸려서 함수 진입부에 멈추면, 그 상태에서 바로 `finish`를 친다.

## 단계별 절차

**1) 함수 진입점에 브레이크포인트**
```
(gdb) break strcmp
(gdb) run
```

**2) finish 실행**
```
(gdb) finish
Run till exit from #0  0x00007ffff7c9d160 in strcmp () from /lib/x86_64-linux-gnu/libc.so.6
0x0000000000401235 in check_password ()
Value returned is $1 = 0
```

**3) 리턴값 타입이 안 잡힐 때 수동으로 RAX 읽기**
```
(gdb) finish
Run till exit from #0  0x... in strcmp ()
Value returned has type: <unknown return type>. Cannot determine contents
(gdb) print $rax
$2 = 0
(gdb) print/x $rax
$3 = 0x0
```

**4) 여러 번 반복 호출을 자동으로 보고 싶을 때**
`finish`는 한 번의 프레임 탈출만 처리하므로, 루프 안에서 여러 번 호출되는 함수라면 REV-0656의 `gdb.FinishBreakpoint`를 스크립트로 걸어 자동화하는 것이 더 편하다.

**5) 리턴 직후 값을 조건에 따라 이어서 관찰**
```
(gdb) finish
Value returned is $1 = 0
(gdb) if $1 == 0
 > print "동일한 문자열입니다"
 > end
```

## 명령어/단축키
```
(gdb) break strcmp
(gdb) run
(gdb) finish
(gdb) print $rax
(gdb) print/x $rax
(gdb) bt                 # 콜스택 확인 (finish 전에 caller가 있는지 점검)
(gdb) info frame         # 현재 프레임 정보 상세
```

## 출력 해석
```
(gdb) finish
Run till exit from #0  0x0000000000401146 in check_password (input=0x7fffffffe420 "test123") at chall.c:15
0x0000000000401278 in main () at chall.c:25
25          if (check_password(buf)) {
Value returned is $1 = 0
```
- `Run till exit from #0 ...`: 지금 있는 프레임(`#0`, `check_password`)에서 리턴할 때까지 실행한다는 안내.
- `0x0000000000401278 in main () at chall.c:25`: 리턴 직후 도착한 위치 — 호출자(`main`)의 `call` 다음 명령 주소다.
- `Value returned is $1 = 0`: `check_password`가 `int`를 리턴했고 값이 `0`이라는 뜻. `$1`은 GDB의 값 히스토리 번호로, 이후 `print $1`로 다시 참조할 수 있다.
- 다음 줄 `if (check_password(buf)) {`과 리턴값 `0`(= false)을 연결해서, 이번 실행에서는 이 조건이 거짓이 되어 실패 분기로 갈 것임을 코드 한 줄 안 읽고도 예측할 수 있다.

## 흔한 실수
- `finish`를 `main` 같은 최상위 프레임에서 치고 "왜 에러가 나지"라며 당황하는 것 — `bt`로 호출자가 있는지 먼저 확인한다.
- 리턴 타입이 `void`인 함수에 `finish`를 쓰고 값이 없다고 이상하게 여기는 것 — `void` 함수는 애초에 "Value returned"가 출력되지 않는 게 정상이다.
- strip된 바이너리에서 `Value returned` 줄 자체가 안 나오는데 리턴값이 없다고 착각하는 것 — 디버그 정보가 없으면 GDB가 타입을 몰라서 안 보여줄 뿐이니 `print $rax`로 직접 읽어야 한다.
- `finish` 도중에 그 함수 내부에 또 다른 브레이크포인트가 걸려 있으면 리턴까지 안 가고 그 브레이크포인트에서 먼저 멈춘다 — 이걸 "finish가 안 먹힌다"고 오해하지 말고, 어느 브레이크포인트에서 멈췄는지 `(gdb)` 프롬프트 위 메시지를 확인한다.
- 32비트 바이너리인데 `$rax` 대신 `$eax`를 안 쓰는 것 — 32비트 프로세스를 디버깅 중이면 리턴값은 `$eax`에 있다(REV-0022 레지스터 폭 차이 참고).

## 막혔을 때 다음 체크
- 같은 함수가 루프에서 여러 번 불려서 매번 수동으로 `finish`+`continue`를 반복하기 귀찮다면 → REV-0656 GDB Python 스크립팅 기초(gdb.FinishBreakpoint)
- 함수 진입 전에 인자부터 먼저 확인하고 싶다면 → REV-0175 CALL 직전 함수 인자 확인하는 법
- 리턴값과 레지스터의 관계, calling convention 자체가 헷갈린다면 → REV-0106 SysV AMD64 Calling Convention
- 원격 디버깅 세션에서도 finish가 똑같이 동작하는지 궁금하다면 → REV-0658 GDB 원격 디버깅(gdbserver) 기초

## 미니 예제
```bash
$ gdb -q ./chall
(gdb) break check_password
Breakpoint 1 at 0x401146
(gdb) run
Starting program: /home/user/chall
Enter password: test123

Breakpoint 1, 0x0000000000401146 in check_password (input=0x7fffffffe420 "test123") at chall.c:15
15      int check_password(char *input) {
(gdb) finish
Run till exit from #0  check_password (input=0x7fffffffe420 "test123") at chall.c:15
0x0000000000401278 in main () at chall.c:25
25          if (check_password(buf)) {
Value returned is $1 = 0
(gdb) print $1
$2 = 0
```
리턴값 `0`을 확인한 순간, 이 입력으로는 검증에 실패한다는 것을 소스나 어셈블리를 더 파고들지 않고도 알 수 있다.

## 관련 글
- REV-0656 — GDB Python 스크립팅 기초(gdb.Breakpoint 등)
- REV-0175 — CALL 직전 함수 인자 확인하는 법
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0106 — SysV AMD64 Calling Convention
- REV-0186 — GDB break와 address breakpoint

## 출처/검증
- `finish` 명령의 동작(현재 프레임 종료까지 실행, "Value returned" 출력): GDB 공식 매뉴얼 "Continuing and Stepping" 챕터 기준.
- x86-64 정수/포인터 리턴값이 RAX, 부동소수점 리턴값이 XMM0에 담기는 규약: System V AMD64 ABI 문서 기준 (2026-09-08 검증).
