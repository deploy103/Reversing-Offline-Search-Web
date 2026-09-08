---
id: REV-0103
title: "PIE와 주소 계산"
slug: "rev-0103-pie"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, Pwndbg, checksec, readelf]
keywords: ["PIE", "Position Independent Executable", "ET_DYN", "ET_EXEC", "base address", "이미지 베이스", "pie breakpoint", "주소 오프셋 계산"]
aliases: ["pie란", "pie 바이너리", "pie breakpoint", "pie 브레이크포인트", "pie 주소 계산", "no-pie"]
symptom_keywords: ["break *0x주소가 안 걸림", "breakpoint가 안 걸림", "실행할 때마다 함수 주소가 바뀜", "gdb에서 break 주소를 넣었는데 반응이 없음", "ida 주소랑 gdb 주소가 다름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
PIE(Position Independent Executable)는 실행 파일 자체도 공유 라이브러리처럼 "어느 주소에 올려도 동작하도록" 만들어진 바이너리이며, 그 결과 IDA에서 보는 주소는 실행 시 실제 메모리 주소가 아니라 **베이스 주소로부터의 오프셋**일 뿐이므로, PIE 바이너리를 디버깅할 때는 반드시 "런타임 베이스 주소 + 오프셋"을 계산해서 브레이크포인트를 걸어야 한다.

## 언제 검색해야 하나
- IDA에서 `main` 함수 주소가 `0x1234`처럼 작게 나오는데, GDB에서 그 주소에 `break *0x1234`를 걸었더니 아무 반응이 없거나("pie breakpoint가 안 걸림") 프로그램이 그냥 끝까지 실행돼버릴 때
- 같은 바이너리를 실행할 때마다 GDB `info proc mappings`나 `vmmap`에 찍히는 코드 시작 주소가 계속 바뀌는 걸 봤을 때
- `checksec` 결과 `PIE: PIE enabled`가 무슨 의미인지, `PIE: No PIE`와 뭐가 다른지 궁금할 때
- IDA가 보여주는 주소와 GDB가 보여주는 주소가 서로 다른데 이게 오류가 아니라 정상인지 궁금할 때

## 핵심 개념

### PIE가 없던 시절: 고정 베이스 주소
전통적인 리눅스 실행 파일(`ET_EXEC` 타입)은 항상 같은 가상 주소, 보통 `0x400000`부터 로드되도록 컴파일됐다. 즉 컴파일 시점에 "이 프로그램은 항상 `0x400000`에서 시작한다"고 못박아 두면, 코드 안의 모든 `call`, `jmp`, 전역 변수 접근이 절대 주소(absolute address)로 그냥 박혀 있어도 문제가 없었다. IDA로 열어봐도 `0x400000`대 주소가 그대로 실제 실행 주소였다.

### PIE: 실행 파일도 공유 라이브러리처럼
PIE 바이너리는 ELF 타입이 `ET_DYN`(공유 오브젝트와 같은 타입)이다. 이 바이너리는 "특정 고정 주소에서만 실행 가능"하지 않고, **로더가 아무 주소에나 올려도 동작**하도록 컴파일된다. 이렇게 하는 이유는 순전히 보안 때문이다 — 실행 파일 자체의 주소를 예측 불가능하게(ASLR과 결합해서) 만들어, 공격자가 코드 안의 특정 가젯(gadget)이나 함수 주소를 미리 알고 공격하는 것을 어렵게 만든다. 요즘 대부분의 리눅스 배포판(Ubuntu, Debian 등)은 `gcc`로 컴파일할 때 기본값이 PIE이며, 일부러 `gcc -no-pie`를 줘야 옛날 방식(`ET_EXEC`, non-PIE)으로 컴파일된다.

### IDA/objdump가 보여주는 주소의 정체
PIE 바이너리를 IDA로 열면 기본적으로 **로드 베이스를 `0`으로 가정**하고 주소를 매긴다(IDA는 흔히 `0x0` 또는 매우 낮은 값에서 시작). 그래서 `main`이 `0x1349`처럼 보이는데, 이건 "이 바이너리가 메모리 어디에 로드되든, main은 로드 시작점으로부터 `0x1349`만큼 떨어진 곳에 있다"는 **상대 오프셋**이다. 실제 실행 중 `main`의 진짜 메모리 주소는:

```
실제 주소 = 런타임 베이스 주소 + IDA에서 본 오프셋
```

이 계산을 못 하면 GDB에서 IDA가 알려준 주소 그대로 `break *0x1349`를 걸었을 때, 그 주소는 대개 프로세스 메모리 안에서 매핑조차 안 된 영역이라 브레이크포인트가 걸리지 않거나("pie breakpoint" 문제), 걸리더라도 전혀 엉뚱한 코드에서 멈춘다.

### 런타임 베이스 주소는 어떻게 정해지나
PIE 바이너리의 런타임 베이스 주소는 커널의 ASLR(REV-0104 참고)에 의해 **프로세스가 시작될 때마다 무작위로** 정해진다(ASLR이 꺼져 있다면 항상 같은 고정값이 된다 — 보통 `0x555555554000` 부근). 이 베이스 주소는 실행 전에는 절대 알 수 없고, 오직 프로세스가 이미 로드된 **실행 중**에만 확인할 수 있다.

### GDB/Pwndbg에서 PIE 베이스를 다루는 법
GDB는 기본적으로 PIE를 인식하고 도와준다. 심볼 이름(`main`, `printf` 등)으로 브레이크포인트를 걸면 GDB가 알아서 실제 로드 주소를 계산해준다:
```gdb
break main
```
이 방법이 가장 안전하고 실수가 적다. 반면 IDA에서 얻은 raw 오프셋 주소로 걸고 싶다면, 프로세스를 일단 실행시켜(`start` 또는 `run` 후 잠깐 멈추게 하거나) 베이스 주소를 먼저 구해야 한다:
```gdb
start
info proc mappings
```
또는 Pwndbg를 쓰면 더 간단하다:
```gdb
start
piebase
```
Pwndbg의 `piebase`(또는 오래된 버전에서 `pie` 관련 명령)는 현재 프로세스의 PIE 베이스 주소를 바로 알려준다. 이 값을 IDA 오프셋에 더해서 `break *(베이스+오프셋)`으로 걸면 된다. Pwndbg는 더 나아가서 `break` 명령 자체를 확장해 오프셋 표현을 직접 지원하기도 한다(버전에 따라 `b *$rebase(0x1349)` 형태의 헬퍼를 제공). 정확한 문법은 설치된 Pwndbg 버전의 `help`로 확인하는 것이 안전하다.

### "pie breakpoint가 안 걸린다" 문제의 진짜 원인
이 증상은 초보자가 가장 많이 겪는 문제 중 하나다. 원인은 거의 항상 다음 중 하나다.
1. **아직 실행 전(`run`을 하기 전)에 raw 주소로 브레이크포인트를 걸었다.** PIE 바이너리는 실행 전에는 아직 어느 주소에 로드될지 모르므로, 로드되지 않은 주소(오프셋 값 그대로)에 브레이크포인트를 걸면 그 주소에는 아무 코드도 없다.
2. **베이스 주소를 더하지 않고 IDA 오프셋을 그대로 썼다.** 위에서 설명한 "실제 주소 = 베이스 + 오프셋" 계산을 빠뜨린 경우다.
3. **ASLR 때문에 실행마다 베이스가 바뀌어서, 이전 실행에서 계산해둔 주소가 이번 실행에는 안 맞는 경우.** 디버깅 중에는 ASLR을 꺼두는 것이 정신 건강에 좋다(REV-0104 참고).

해결책은 간단하다 — **가능하면 심볼 이름으로 브레이크포인트를 걸고(`break main`, `break *main+0x20`), 주소를 직접 쓸 때는 반드시 프로세스가 이미 로드된 뒤(`start` 이후)에 베이스를 구해서 더한다.**

### non-PIE와의 차이 요약
| 항목 | non-PIE (`ET_EXEC`) | PIE (`ET_DYN`) |
|---|---|---|
| IDA가 보여주는 주소 | 실제 실행 주소와 동일 | 베이스 기준 오프셋 |
| 베이스 주소 | 항상 고정(보통 `0x400000`) | 매 실행마다 ASLR로 무작위(꺼져 있으면 고정) |
| `break *0x401234` | 그대로 동작 | 대부분 실패("pie breakpoint" 문제) |
| checksec 표시 | `PIE: No PIE (0x...)` | `PIE: PIE enabled` |

## 화면/코드에서 보이는 징후
- `checksec` 출력에 `PIE enabled`가 표시됨
- `file ./chall` 결과가 `ELF 64-bit LSB pie executable`(non-PIE는 `LSB executable`)
- IDA에서 함수 주소가 `0x1000`~`0x4000`대의 작은 값으로 시작함(non-PIE는 보통 `0x400000`대)
- GDB에서 같은 바이너리를 여러 번 실행하면 `info proc mappings` 결과의 코드 베이스 주소가 매번 다름
- IDA 오프셋 그대로 `break *0x....`를 걸었을 때 `Breakpoint 1 at 0x....`는 뜨지만 `run` 후 실제로 멈추지 않고 프로그램이 끝나버림

## 가장 먼저 할 것
`checksec ./chall`로 PIE 여부부터 확인한다. PIE가 켜져 있다면 지금부터 다루는 모든 주소는 "오프셋"이라고 마음속으로 라벨을 붙이고, GDB에서는 되도록 raw 주소 대신 심볼(`break main`, `break printf`) 또는 심볼 기준 상대 주소(`break *main+0x20`)로 작업한다.

## 단계별 절차

**1) PIE 여부 확인**
```bash
checksec --file=./chall
file ./chall
```

**2) IDA/objdump에서 관심 있는 함수의 오프셋 확인**
IDA 상태 표시줄이나 함수 목록에서 주소를 확인한다. 예: `check_password` 함수가 `0x1349`.

**3) GDB에서 프로세스를 일단 로드**
```gdb
gdb ./chall
start
```
`start`는 `main`의 시작 부분에 임시 브레이크포인트를 걸고 실행해, 라이브러리와 PIE 베이스가 이미 매핑된 상태로 멈춘다.

**4) 베이스 주소 확인**
```gdb
info proc mappings
```
출력 맨 위쪽, `./chall` 자신의 실행 파일 경로가 적힌 첫 줄의 시작 주소가 베이스다(예: `0x0000555555554000`).

Pwndbg 사용 시:
```gdb
piebase
```

**5) 실제 주소 계산 후 브레이크포인트**
```gdb
break *(0x0000555555554000 + 0x1349)
```
또는 Pwndbg의 `$rebase` 표현식을 지원하는 버전이라면:
```gdb
break *$rebase(0x1349)
```

**6) 훨씬 더 쉬운 대안: 심볼 이름 사용**
```gdb
break check_password
break *check_password+0x20
```
GDB는 디버깅 심볼이나 동적 심볼이 있으면 PIE 베이스를 알아서 계산해 넣어준다. 대부분의 상황에서 이 방법이 가장 안전하다.

**7) ASLR을 꺼서 매 실행 주소를 고정**
```gdb
set disable-randomization on
```
GDB는 기본적으로 이미 이 옵션이 켜져 있어(즉 ASLR을 끄고 실행) 매번 같은 베이스로 실행되지만, 명시적으로 확인해두면 좋다. 자세한 내용은 REV-0104 참고.

## 명령어/단축키
```bash
checksec --file=./chall
file ./chall
```
GDB/Pwndbg: `start`, `info proc mappings`, `vmmap`, `piebase`, `break main`, `break *(base+offset)`, `set disable-randomization on`

## 출력 해석
- `info proc mappings`의 첫 몇 줄 중 `./chall` 실행 파일 경로가 적힌 라인의 시작 주소 = PIE 베이스.
- `vmmap`(Pwndbg) 결과에서 실행 파일 이름 옆에 `r-xp`(읽기+실행) 권한이 붙은 구간이 코드 세그먼트다.
- non-PIE 바이너리에서는 `info proc mappings`에 찍히는 코드 시작 주소가 IDA에서 본 주소와 그대로 일치한다 — 이때는 베이스를 더할 필요가 없다.

## 흔한 실수
- 실행 전(`run`/`start` 하기 전)에 IDA 오프셋으로 바로 `break *0x1349`를 거는 것 — 그 시점엔 아직 파일이 그 주소에 로드되지 않았을 수 있고, 대개 GDB가 "그 주소에 실행 파일이 없다"는 취지의 경고를 내거나 원하는 곳에서 멈추지 않는다.
- 베이스 주소를 한 번 구해놓고 다음 실행에서도 같은 값을 재사용하는 것 — ASLR이 켜져 있으면 실행마다 베이스가 바뀐다.
- PIE와 ASLR을 같은 것으로 생각하는 것 — PIE는 "바이너리를 재배치 가능하게 컴파일하는 옵션"이고 ASLR은 "그 재배치 가능한 것들을 실제로 무작위 주소에 배치하는 커널 기능"이다. PIE가 꺼져 있으면 ASLR이 켜져 있어도 실행 파일 자체의 코드 주소는 바뀌지 않는다(스택/힙/라이브러리 주소만 바뀐다).
- IDA의 `Debugger` 메뉴로 직접 붙여서 디버깅할 때 오프셋을 잘못 계산해 엉뚱한 함수에 브레이크포인트가 걸리는 것 — IDA도 디버거로 attach하면 자동으로 재베이스(rebase)를 해주므로, 정적 분석 뷰의 오프셋을 손으로 계산하는 대신 디버거 뷰의 주소를 그대로 쓰는 것이 안전하다.

## 막혔을 때 다음 체크
- 실행마다 주소가 바뀌는 원리 자체(ASLR)를 더 자세히 알고 싶다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- PIE를 포함한 다른 보호 기법까지 한 번에 정리하고 싶다면 → REV-0105 Canary NX PIE RELRO 한 번에 이해
- GOT/PLT의 주소도 PIE 베이스에 영향을 받는지 궁금하다면 → REV-0100 PLT와 GOT 기초

## 미니 예제
```bash
$ checksec --file=./chall
RELRO           STACK CANARY      NX            PIE
Partial RELRO   Canary found      NX enabled    PIE enabled
```
```gdb
$ gdb ./chall
(gdb) start
Temporary breakpoint 1, 0x0000555555555185 in main ()
(gdb) info proc mappings
      0x555555554000     0x555555555000     0x1000        0x0  r--p   /home/user/chall
      0x555555555000     0x555555556000     0x1000     0x1000  r-xp   /home/user/chall
      ...
```
IDA에서 `main`이 `0x1185`로 보였다면, 베이스 `0x555555554000` + 오프셋 `0x1185` = `0x555555555185`, 실제로 GDB가 멈춘 주소(`0x0000555555555185`)와 정확히 일치한다.

## 관련 글
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0100 — PLT와 GOT 기초

## 출처/검증
- PIE(`ET_DYN` 실행 파일)와 재배치 가능 실행 개념: System V ABI ELF 명세(`e_type` 필드 `ET_DYN`) 기준.
- GDB의 PIE/ASLR 처리(`disable-randomization`, `start` 동작): GDB 공식 온라인 문서(Starting your Program, `set disable-randomization`) 기준.
- Pwndbg `piebase`/`vmmap` 명령: Pwndbg 공식 문서/명령어 목록 기준 (2026-09-08 검증).
