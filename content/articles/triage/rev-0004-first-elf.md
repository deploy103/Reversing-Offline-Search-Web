---
id: REV-0004
title: "처음 보는 ELF 문제 접근 순서"
slug: "rev-0004-first-elf"
category: "triage"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [file, readelf, checksec, GDB, Pwndbg, IDA, Ghidra, ltrace, strace]
keywords: [ELF 분석 순서, 리눅스 리버싱 시작, checksec 사용법, readelf 사용법, 정적 링킹 확인, PIE 확인]
aliases: ["elf 문제 어떻게 풀어", "리눅스 문제 처음 접근", "elf 파일 뭐부터", "chall 파일 분석"]
symptom_keywords: ["elf 파일 뭐부터 봐야 할지 모르겠음", "리눅스 문제 처음 봄", "chall 실행이 안 됨", "권한이 없다고 나옴", "심볼이 하나도 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
확장자 없는 ELF 문제는 **file → checksec → readelf(동적/정적 링킹, 심볼) → strings → ltrace/strace(동적 훑기)** 순서로 5분 안에 훑고 나서 IDA/Ghidra/GDB 중 어디로 갈지 정한다.

## 언제 검색해야 하나
- CTF에서 확장자 없는 파일(`chall`, `pwn1`, `rev_easy` 등)을 받았고 실행조차 안 될 때
- `Permission denied`가 뜨거나 `readelf`, `file` 명령이 뭘 하는지 몰라서 시작을 못 할 때
- 정적 링킹된 큰 바이너리라서 함수가 수천 개 보여서 어디부터 봐야 할지 막막할 때

## 핵심 개념
Windows와 달리 Linux ELF 문제는 대부분 **명령줄에서 바로 조작 가능**하다는 게 최대 장점이다. GUI 도구를 켤 필요 없이 `file`, `readelf`, `strings`, `ltrace` 같은 표준 도구만으로 상당한 정보를 얻을 수 있다. 리눅스 ELF 분석의 핵심 축은 세 가지다.

1. **링킹 방식** — 동적 링킹(dynamically linked)이면 `libc`에 있는 함수(`strcmp`, `printf` 등)를 그대로 임포트해서 쓰므로 IDA/Ghidra가 이름을 잘 알아본다. 정적 링킹(statically linked)이면 `libc` 전체가 바이너리 안에 박혀 있어서 함수가 수천 개로 보이고, 어떤 게 우리가 짠 코드고 어떤 게 libc 내부 코드인지 구분이 안 된다.
2. **PIE 여부** — PIE(Position Independent Executable)면 실행할 때마다 로드 주소가 바뀐다. GDB로 디버깅할 때 "IDA에서 본 주소"와 "GDB에서 실제로 찍힌 주소"가 다른 이유가 바로 이것이다.
3. **strip 여부** — 심볼이 지워졌으면(stripped) 함수 이름이 전부 `sub_XXXX`로 나온다.

이 세 가지를 실행 파일을 열기도 전에 `file` 한 줄로 대부분 파악할 수 있다.

## 화면/코드에서 보이는 징후
- 실행하려는데 `bash: ./chall: Permission denied`가 뜬다 → 실행 권한이 없는 것뿐이다(리버싱 문제 아님).
- `readelf -d`에 아무것도 안 뜬다 → 정적 링킹.
- IDA/Ghidra에서 함수가 3000개 넘게 보인다 → 정적 링킹된 libc 포함 바이너리.
- Functions 목록에 `main`, `printf` 같은 이름이 아예 없고 전부 `sub_`로 시작 → stripped.

## 가장 먼저 할 것
디스어셈블러를 켜기 전에 터미널에서 아래 네 줄을 순서대로 친다.
```bash
chmod +x ./chall
file ./chall
checksec --file=./chall
readelf -d ./chall
```

## 단계별 절차

**1) 실행 권한 부여 및 형식 확인**
```bash
chmod +x ./chall
file ./chall
```
출력 예시:
```
chall: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0, not stripped
```
한 줄에 다음 정보가 다 있다: 64비트, PIE(주소 바뀜), x86-64, **동적 링킹**, **not stripped**(심볼 남아있음 — 좋은 소식, `main`을 IDA가 자동으로 찾아줄 것이다).

**2) 보호 기법 확인**
```bash
checksec --file=./chall
```
출력에 `Canary`, `NX`, `PIE`, `RELRO` 값이 나온다. 순수 리버싱(크랙미) 문제라면 이 정보는 크게 중요하지 않지만, `NX disabled`나 `Canary: No`처럼 나오면 pwn 요소가 섞인 문제일 수도 있다는 신호다.

**3) 동적/정적 링킹 확인**
```bash
readelf -d ./chall | grep NEEDED
```
`NEEDED libc.so.6`처럼 나오면 동적 링킹 — 정상적인 경우다. 아무 출력도 없으면 정적 링킹이다. 정적 링킹이면:
```bash
readelf -h ./chall   # 헤더 확인
nm ./chall 2>/dev/null | grep ' T main'   # 심볼이 남아있으면 main 주소를 바로 알려줌
```
정적 링킹에서 심볼까지 지워졌다면(strip + static) IDA/Ghidra의 FLIRT 시그니처(라이브러리 함수 자동 인식 기능)에 의존해야 한다. 이때는 진입점부터 `__libc_start_main` 호출 인자를 따라가는 [rev-0009-finding-main.md](./rev-0009-finding-main.md) 절차가 특히 중요해진다.

**4) 문자열 훑기**
```bash
strings -n 6 ./chall | grep -i -E "correct|wrong|flag|password|usage"
```
힌트가 될 문자열을 미리 찾아둔다.

**5) 동적으로 가볍게 훑기 (선택)**

바로 실행해봐도 안전한 문제라면(악성코드가 아닌 CTF 문제라는 전제하에):
```bash
ltrace ./chall
```
`ltrace`는 이 프로그램이 호출하는 라이브러리 함수(`printf`, `strcmp`, `scanf` 등)를 실시간으로 인자와 함께 보여준다. 예를 들어 `strcmp("abc", "flag_value")`처럼 인자가 그대로 찍히면, 정적 분석 없이도 비교 대상 문자열을 바로 알아낼 수 있는 경우도 있다(단, 최적화나 인라인 비교면 안 보일 수 있다).
```bash
strace ./chall
```
`strace`는 시스템 콜(`read`, `write`, `open` 등) 레벨을 보여준다. 입력을 어떻게 받는지, 파일을 여는지 등을 확인할 때 쓴다.

**6) 방향 결정**

- `not stripped` + 동적 링킹 + 문자열에 힌트 있음 → IDA/Ghidra로 바로 정적 분석, `main` 자동 인식됨.
- stripped 또는 함수가 수천 개(정적 링킹) → [rev-0010-stripped-entry-point.md](./rev-0010-stripped-entry-point.md)로.
- `ltrace`에서 비교 문자열이 바로 노출됨 → 굳이 IDA 안 열어도 풀릴 수도 있다.

## 명령어/단축키
```bash
chmod +x ./chall
file ./chall
checksec --file=./chall
readelf -h ./chall
readelf -d ./chall
nm ./chall | grep ' T '
strings -n 6 ./chall
ltrace ./chall
strace ./chall
objdump -d ./chall | less
```

## 출력 해석
- `file` 결과의 `pie executable`은 "GDB에서 주소가 IDA랑 다르게 보일 수 있다"는 의미다. GDB에서는 `info proc mappings` 또는 pwndbg의 `vmmap`으로 실제 로드 베이스를 확인하고 오프셋을 계산해야 한다.
- `not stripped`는 좋은 소식이다 — 함수/변수 이름이 컴파일 당시 이름 그대로 남아있어서 분석이 훨씬 빠르다.
- `readelf -d`에 `NEEDED libc.so.6`만 있고 버전 표기가 없다면, 로컬 시스템의 libc와 CTF 서버의 libc가 다를 수 있으니 문제에 첨부된 `libc.so.6`이 따로 있는지 확인해야 한다(pwn 성격이 섞인 문제일 때 특히 중요).

## 흔한 실수
- `./chall`을 실행하기 전에 `chmod +x`를 안 해서 "실행이 안 된다"고 착각하는 것.
- 정적 링킹된 바이너리에서 IDA가 찾아준 함수 수천 개를 전부 하나씩 열어보려는 것 — libc 내부 함수는 무시하고 우리가 만든 로직만 찾으면 된다. 보통 `main` 근처, 또는 문자열을 참조하는 함수만 보면 충분하다.
- PIE인 걸 모르고 IDA 주소를 GDB `break *0x401234`에 그대로 써서 브레이크포인트가 안 걸리는 것 — PIE 바이너리는 로드 베이스 오프셋을 더해야 한다.
- `ltrace`/`strace` 결과만 보고 로직을 다 이해했다고 착각하는 것 — 실제 비교 로직(XOR, 복잡한 알고리즘)은 라이브러리 호출 레벨에서는 안 보인다.

## 막혔을 때 다음 체크
- 함수 이름이 하나도 안 남아있다 → [rev-0010-stripped-entry-point.md](./rev-0010-stripped-entry-point.md)
- `main`을 못 찾겠다 → [rev-0009-finding-main.md](./rev-0009-finding-main.md)
- 정적 분석으로 뚫을지 동적으로 뚫을지 애매하다 → [rev-0005-static-vs-dynamic.md](./rev-0005-static-vs-dynamic.md)
- 5분째 진전이 없다 → [rev-0015-five-minute-checklist.md](./rev-0015-five-minute-checklist.md)

## 미니 예제
```bash
$ chmod +x chall
$ file chall
chall: ELF 64-bit LSB pie executable, x86-64, ... dynamically linked, ... not stripped

$ checksec --file=chall
[*] '/home/user/chall'
    Arch:     amd64-64-little
    RELRO:    Full RELRO
    Stack:    Canary found
    NX:       NX enabled
    PIE:      PIE enabled

$ strings -n 6 chall | grep -i correct
Correct! flag is printed above.
```
이 정보만으로 "64비트 PIE 바이너리, 심볼 살아있음, `Correct!` 문자열 존재"라는 그림이 그려진다. 다음 할 일은 IDA/Ghidra로 열어서 `Correct!` 문자열의 xref를 따라가는 것이다([rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md) 참고).

## 관련 글
- [rev-0001-first-30-seconds.md](./rev-0001-first-30-seconds.md)
- [rev-0003-first-exe.md](./rev-0003-first-exe.md)
- [rev-0005-static-vs-dynamic.md](./rev-0005-static-vs-dynamic.md)
- [rev-0009-finding-main.md](./rev-0009-finding-main.md)
- [rev-0010-stripped-entry-point.md](./rev-0010-stripped-entry-point.md)
- [rev-0008-trace-from-strings.md](./rev-0008-trace-from-strings.md)

## 출처/검증
- `file(1)`, `readelf(1)`, `nm(1)`, `ltrace(1)`, `strace(1)` — GNU binutils/util-linux 공식 man page 기준 (2026-09-08 검증).
- checksec-tool(slimm609/checksec.sh) 공식 GitHub 사용법 기준.
