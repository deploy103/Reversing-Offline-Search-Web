---
id: REV-0664
title: "objdump -d로 특정 함수만 디스어셈블하기"
slug: "rev-0664-objdump-disassemble-single-function"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [objdump]
keywords: ["objdump -d", "objdump --disassemble", "objdump 함수별 출력", "objdump -M intel", "objdump 특정 함수"]
aliases: ["objdump으로 함수 하나만 보는 법", "objdump 특정 심볼만 디스어셈블", "objdump AT&T Intel 문법 전환", "objdump 특정 주소 범위"]
symptom_keywords: ["objdump -d 결과가 너무 길어서 원하는 함수를 못 찾겠음", "objdump 결과가 AT&T 문법이라 읽기 힘듦", "objdump으로 main 함수만 보고 싶음", "objdump에서 특정 주소 범위만 뽑고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`objdump -d ./chall`은 바이너리 전체 함수를 디스어셈블해 화면을 뒤덮어버리지만, `--disassemble=심볼이름` 옵션이나 `grep`/`awk` 조합, 또는 `objdump -d`의 출력을 함수 경계(`<함수이름>:`)로 잘라내는 방법을 쓰면 원하는 함수 하나만 정확히 뽑아낼 수 있다.

## 언제 검색해야 하나
- `objdump -d ./chall`을 실행했더니 출력이 수천 줄이라 원하는 함수(`main`, `check_password` 등)를 찾기 힘들 때
- IDA/Ghidra 없이 터미널만으로 특정 함수 하나의 어셈블리만 빠르게 확인하고 싶을 때
- `objdump` 출력이 기본적으로 AT&T 문법이라 Intel 문법(IDA에서 보던 형식)으로 바꾸고 싶을 때
- 함수 이름을 모르고 주소 범위만 알고 있을 때, 그 범위만 디스어셈블하고 싶을 때

## 핵심 개념

### `--disassemble=SYMBOL` — 심볼 이름으로 직접 지정
binutils의 최신 `objdump`는 `-d`(전체 디스어셈블)와 별개로 특정 심볼 이름만 디스어셈블하는 옵션을 제공한다.

```bash
objdump -d --disassemble=main ./chall
```

이 옵션은 심볼 테이블(`.symtab` 또는 `.dynsym`)에 해당 이름이 존재해야 동작한다. 즉 **strip된 바이너리에서는 이름이 없으므로 이 옵션을 쓸 수 없다** — 이 경우 REV-0666(nm으로 정적 바이너리에서 심볼 찾기)이나 REV-0668(strip된 바이너리에서 시그니처 매칭) 같은 이름 복원 전략이 먼저 필요하다.

### 심볼 이름을 모를 때 — grep으로 함수 경계 잘라내기
`objdump -d` 출력은 각 함수 시작을 다음과 같은 형태로 표시한다.

```
0000000000401136 <check_password>:
```

이 패턴을 이용해 `awk`로 원하는 함수의 시작부터 다음 함수 시작 전까지만 잘라낼 수 있다.

```bash
objdump -d ./chall | awk '/<check_password>:/{flag=1} flag{print} /^$/{if(flag)exit}'
```

이 명령은 `<check_password>:`가 나오는 줄부터 출력을 시작하고, 그 다음에 나오는 빈 줄(objdump은 함수와 함수 사이를 빈 줄로 구분한다)을 만나면 출력을 멈춘다. 간단하게 `grep`으로 라인 번호만 찾고 `sed`로 범위를 뽑는 방법도 있다.

```bash
line=$(objdump -d ./chall | grep -n "<check_password>:" | cut -d: -f1)
objdump -d ./chall | sed -n "${line},+40p"
```
이 방법은 함수 길이를 모를 때 "우선 40줄만 보고 필요하면 더 늘린다"는 식으로 쓸 수 있어 실전에서 편하다.

### 주소 범위로 자르기 — `--start-address`/`--stop-address`
함수 이름 대신 주소 범위를 안다면(예: GDB `info functions`로 확인했거나, 다른 함수에서 `call` 대상 주소만 알 때) 다음처럼 범위를 직접 지정할 수 있다.

```bash
objdump -d --start-address=0x401136 --stop-address=0x4011a0 ./chall
```
이 방법은 심볼 테이블 유무와 무관하게 항상 동작하므로, strip된 바이너리에서 주소만 알고 있을 때 특히 유용하다.

### AT&T 문법 vs Intel 문법
`objdump`의 기본 출력은 AT&T 문법(`mov %rax, %rbx`처럼 소스가 왼쪽, 레지스터 앞에 `%`)이다. IDA/Ghidra에 익숙하다면 Intel 문법(`mov rbx, rax`처럼 목적지가 왼쪽)이 더 편할 수 있다. `-M intel` 옵션으로 전환한다.

```bash
objdump -d -M intel --disassemble=main ./chall
```

### 소스 코드와 나란히 보기 — `-S`(디버그 정보가 있을 때)
바이너리가 디버그 심볼(`-g`로 컴파일)을 포함하고 있다면 `-S` 옵션으로 원본 C 소스 줄과 어셈블리를 나란히 볼 수 있다.

```bash
objdump -d -S --disassemble=main ./chall
```
디버그 정보가 없으면 이 옵션은 그냥 무시되고 평범한 디스어셈블만 나온다(REV-0667 참고).

## 화면/코드에서 보이는 징후
- `objdump -d ./chall`을 스크롤해도 스크롤해도 함수가 계속 나와서 원하는 지점을 못 찾음
- 터미널 히스토리가 함수 하나 찾으려다 수천 줄로 뒤덮임
- 출력에 `mov %rax,%rbx`처럼 `%` 기호가 붙은 AT&T 문법이 낯설어서 읽기 힘듦

## 가장 먼저 할 것
`nm ./chall | grep -i 함수이름조각` 또는 `readelf -s ./chall | grep 함수이름조각`으로 정확한 심볼 이름과 존재 여부를 먼저 확인한다. 심볼이 있으면 `--disassemble=심볼이름`으로 바로 뽑고, 없으면(strip됨) 주소 기반(`--start-address`/`--stop-address`) 방법으로 전환한다.

## 단계별 절차
1. `nm ./chall | grep check` 등으로 원하는 함수의 정확한 심볼 이름 확인
2. 심볼이 있으면:
   ```bash
   objdump -d -M intel --disassemble=check_password ./chall
   ```
3. strip되어 심볼이 없으면, GDB로 실행 중 주소를 알아내거나(`info functions`, `disassemble` 명령) 다른 함수의 `call` 대상으로 주소를 특정
4. 주소 범위로 뽑기:
   ```bash
   objdump -d -M intel --start-address=0x401136 --stop-address=0x4011a0 ./chall
   ```
5. 결과가 너무 길면 `| head -60`으로 앞부분만 먼저 훑기
6. 디버그 정보가 있으면 `-S`로 소스와 함께 보기
7. 필요하면 결과를 파일로 저장해 IDA/Ghidra 결과와 비교: `objdump -d --disassemble=main ./chall > main.asm`

## 명령어/단축키
```bash
objdump -d ./chall                                  # 전체 디스어셈블(전체 함수)
objdump -d --disassemble=main ./chall               # 심볼 이름으로 특정 함수만
objdump -d -M intel --disassemble=main ./chall       # Intel 문법으로
objdump -d -S --disassemble=main ./chall             # 소스코드 병기(디버그 정보 있을 때)
objdump -d --start-address=0x401136 --stop-address=0x4011a0 ./chall   # 주소 범위 지정
objdump -T ./chall | grep FUNC                       # 동적 심볼에서 함수 이름 찾기
nm ./chall | grep FUNC                               # 정적 심볼 테이블에서 이름 찾기
```

## 출력 해석
```bash
$ objdump -d -M intel --disassemble=check_password ./chall

./chall:     file format elf64-x86-64


Disassembly of section .text:

0000000000401136 <check_password>:
  401136:	55                   	push   rbp
  401137:	48 89 e5             	mov    rbp,rsp
  40113a:	48 83 ec 20          	sub    rsp,0x20
  40113e:	48 89 7d e8          	mov    QWORD PTR [rbp-0x18],rdi
  401142:	c9                   	leave
  401143:	c3                   	ret
```
- 맨 앞 열(`401136:`)은 명령어의 가상 메모리 주소다.
- 그 다음 열(`55`, `48 89 e5` 등)은 실제 기계어 바이트(opcode)다. 바이트 개수가 명령어 길이다.
- 오른쪽이 사람이 읽는 어셈블리 명령이다. `-M intel`을 줬으므로 목적지가 왼쪽(`mov rbp,rsp`는 "rsp 값을 rbp로 복사")이다.
- `<check_password>:` 바로 아래부터가 함수 본문이고, 다음 함수 이름(`<...>:`)이 나오기 전까지가 이 함수의 전체 범위다. 즉 이 헤더 줄 자체가 "여기서 이 함수가 끝나고 다음 게 시작된다"는 경계 표시 역할을 한다.

## 흔한 실수
- `--disassemble=`에 함수 이름 대신 데코레이트된 이름(C++ 맹글링된 이름)을 몰라서 못 찾는 것 — C++ 바이너리라면 `nm -C` (demangle) 결과의 원래 이름이 아니라 맹글링된 실제 심볼 이름을 `--disassemble=`에 넣어야 할 때가 있다.
- strip된 바이너리에서 `--disassemble=main`처럼 이름 기반 옵션을 그대로 썼다가 "심볼을 찾을 수 없다"는 의미의 빈 출력을 받고 objdump가 고장났다고 오해하는 것 — 실제로는 심볼 테이블 자체가 없는 것이 원인이다.
- AT&T 문법과 Intel 문법을 섞어서 읽어 소스/목적지 방향을 반대로 해석하는 것(`mov src,dst`(AT&T) vs `mov dst,src`(Intel)) — 항상 어느 문법으로 보고 있는지 의식해야 한다.
- 함수 경계를 빈 줄 기준으로 자동 판단하는 `awk` 스크립트를 쓸 때, 함수 안에 빈 줄이 우연히 없다고 가정했다가 objdump 버전에 따라 출력 포맷이 미세하게 달라 경계를 놓치는 것 — 결과가 이상하면 항상 `<다음함수이름>:`가 나오는 지점까지 수동으로 다시 확인한다.

## 막혔을 때 다음 체크
- 심볼 이름 자체를 못 찾겠으면 → REV-0666 nm으로 정적 바이너리에서 원하는 심볼 찾기, REV-0091 readelf 기본 사용법
- strip되어 이름이 아예 없는 상황이면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- objdump 기초 옵션 자체가 헷갈리면 → REV-0092 objdump 기본 사용법
- 이 함수가 어떤 relocation(재배치) 대상을 참조하는지도 같이 보고 싶으면 → REV-0682 objdump로 relocation 엔트리 읽는 법
- 디스어셈블 대신 실행 중 실제 동작을 보고 싶으면 → REV-0642 GDB 명령어 심화 치트시트

## 미니 예제
```bash
$ nm ./chall | grep check
0000000000401136 T check_password

$ objdump -d -M intel --disassemble=check_password ./chall | tail -8
0000000000401136 <check_password>:
  401136:	55                   	push   rbp
  401137:	48 89 e5             	mov    rbp,rsp
  40113a:	48 83 ec 10          	sub    rsp,0x10
  40113e:	48 89 7d f8          	mov    QWORD PTR [rbp-0x8],rdi
  401142:	48 8b 45 f8          	mov    rax,QWORD PTR [rbp-0x8]
  401146:	48 8d 35 b7 0e 00 00 	lea    rsi,[rip+0xeb7]        # 402004 <_IO_stdin_used+0x4>
  40114d:	48 89 c7             	mov    rdi,rax
  401150:	e8 ab fe ff ff       	call   401000 <strcmp@plt>
```
`nm`으로 정확한 심볼 이름과 주소를 먼저 확인한 뒤, `--disassemble=check_password`로 그 함수만 뽑아내니 전체 디스어셈블 없이 바로 `strcmp@plt` 호출까지 확인할 수 있었다. `lea rsi,[rip+0xeb7]`가 `.rodata`의 문자열 리터럴을 가리키는 RIP 상대 주소 지정이라는 점도 이 짧은 출력만으로 바로 알 수 있다.

## 관련 글
- REV-0092 — objdump 기본 사용법
- REV-0666 — nm으로 정적 바이너리에서 원하는 심볼 찾기
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0682 — objdump로 relocation 엔트리 읽는 법
- REV-0091 — readelf 기본 사용법
- REV-0667 — ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기

## 출처/검증
- `objdump --disassemble=SYMBOL`, `--start-address`, `--stop-address`, `-M intel`, `-S` 옵션: GNU binutils `objdump(1)` 공식 매뉴얼 페이지 기준.
- AT&T 문법과 Intel 문법의 피연산자 순서 차이: GNU binutils 문서 및 x86 어셈블리 표준 표기 관례 기준.
- `objdump -d` 출력에서 함수 시작 표시(`<이름>:`)와 함수 간 빈 줄 구분 형식: 실제 binutils 출력 확인 (2026-09-09 검증).
