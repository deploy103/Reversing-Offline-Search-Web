---
id: REV-0698
title: "ltrace가 정적 바이너리에서 아무것도 안 보여줄 때"
slug: "rev-0698-ltrace-static-binary-no-output"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [ltrace, strace, "readelf"]
keywords: ["ltrace static binary", "couldn't find .dynsym", "정적 링킹 ltrace 안됨", "ltrace no library calls"]
aliases: ["ltrace 출력 없음", "ltrace 아무것도 안 찍힘", "ltrace 정적 바이너리 실패", "Couldn't find .dynsym or .dynstr"]
symptom_keywords: ["ltrace 실행했는데 결과가 아무것도 안 나옴", "Couldn't find .dynsym or .dynstr 에러", "static binary ltrace 안됨", "ltrace가 프로그램만 실행시키고 트레이스를 안함"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ltrace ./chall`을 실행했는데 라이브러리 호출은 하나도 안 찍히고 프로그램 자체의 출력만 나오거나 `Couldn't find .dynsym or .dynstr in "..."` 에러가 뜨는 이유는, `ltrace`가 **동적 링킹의 PLT/GOT 후킹 메커니즘에 의존**하기 때문에 **정적으로 링킹된 바이너리**(`libc` 코드가 실행 파일 안에 그대로 박혀 있는 경우)에서는 원리상 아무것도 가로챌 수 없어서이며, 이런 경우엔 `ltrace` 대신 `strace`(시스템 콜 레벨)나 GDB 브레이크포인트로 접근해야 한다.

## 언제 검색해야 하나
- `ltrace ./chall`을 실행했더니 프로그램의 원래 출력만 보이고 `malloc(...)`, `strcpy(...)` 같은 라이브러리 호출 로그가 전혀 안 찍힐 때
- `Couldn't find .dynsym or .dynstr in "/proc/<PID>/exe"` 에러 메시지를 봤을 때
- `file ./chall` 결과에 `statically linked`라고 나오는데 왜 ltrace가 안 되는지 이유를 모를 때

## 핵심 개념

### ltrace는 PLT/GOT를 조작해서 라이브러리 호출을 가로챈다
`ltrace`와 `strace`는 둘 다 `ptrace(2)`를 쓰지만 가로채는 지점이 다르다. `strace`는 커널로 들어가는 **시스템 콜 진입점**을 가로채므로 바이너리가 정적이든 동적이든 항상 동작한다. 반면 `ltrace`는 **동적 링킹으로 호출되는 라이브러리 함수**를 가로채기 위해, 실행 파일의 `.dynsym`(동적 심볼 테이블)과 `.plt`/`.got.plt`(REV-0100 참고)를 찾아서 그 함수들이 실제로 호출되는 시점에 개입하는 방식으로 동작한다.

정적 링킹(`gcc -static`)된 바이너리는 `malloc`, `printf` 등 libc 함수의 **기계어 코드 전체가 실행 파일 안에 직접 복사**되어 들어간다. 즉 PLT를 거쳐 외부 라이브러리를 호출하는 구조 자체가 없다 — 함수 호출이 그냥 바이너리 내부의 `call` 명령 하나로 끝난다. `ltrace`가 후킹할 PLT 스텁도, 참조할 `.dynsym`도 없으므로 원리적으로 라이브러리 호출을 가로챌 방법이 없다.

### 왜 "아무것도 안 찍히는" 경우와 "에러가 뜨는" 경우가 갈리나
- 바이너리에 `.dynsym`/`.dynstr` 섹션 자체가 없으면(완전 정적 링킹 + 최소 구성) `ltrace`가 `Couldn't find .dynsym or .dynstr in "..."` 에러를 내고 아예 트레이싱을 포기한다.
- 일부 정적 바이너리는 `.dynsym`이 빈 채로 남아있거나 다른 목적의 심볼만 있어서 에러 없이 그냥 "라이브러리 호출 로그 0줄"로 조용히 지나가기도 한다.
- 두 경우 모두 **정적 링킹이 원인**이라는 결론은 같다.

## 화면/코드에서 보이는 징후
```text
$ ltrace ./chall
Couldn't find .dynsym or .dynstr in "/proc/12345/exe"
```
또는 에러 없이:
```text
$ ltrace ./chall
Enter password: test
Wrong password
+++ exited (status 1) +++
```
(라이브러리 호출 로그 없이 프로그램 출력만 그대로 찍힘)

## 가장 먼저 할 것
1. 바이너리가 진짜 정적 링킹인지부터 확인한다.
   ```bash
   file ./chall
   ```
   출력에 `statically linked`가 보이면 원인이 확정된다. `dynamically linked`인데도 이 증상이면 다른 원인(권한, ltrace 설치 문제 등)이므로 이 글의 범위를 벗어난다.
2. 정적 링킹이 확인되면 `ltrace`를 포기하고 **`strace`로 전환**하거나, 특정 함수 호출을 정말 보고 싶다면 GDB 브레이크포인트를 쓴다.

## 단계별 절차

**1) 정적 링킹 여부와 심볼 상태 확인**
```bash
file ./chall
readelf -d ./chall     # 동적 섹션이 없으면(.dynamic 없음) 완전 정적 링킹
readelf -S ./chall | grep dynsym
```
`readelf -d` 결과가 `There is no dynamic section in this file.`이면 완전히 정적으로 링킹된 것이 확정이다.

**2) syscall 레벨 관찰로 전환 (가장 실용적인 대안)**
```bash
strace ./chall
```
`ltrace`가 보여주려던 `malloc`, `read`, `write` 같은 함수는 결국 내부적으로 `brk`/`mmap`, `read`, `write` 시스템 콜을 호출하므로, `strace`로도 상당 부분 같은 정보를 얻을 수 있다(REV-0112, REV-0697 참고). 다만 `strlen`, `strcpy`처럼 시스템 콜을 아예 안 쓰는 순수 라이브러리 함수는 `strace`에도 안 잡힌다.

**3) 특정 라이브러리 함수 호출을 꼭 봐야 한다면 GDB로 직접 브레이크포인트**
정적 바이너리라도 함수가 strip되지 않았다면(정적 링킹 시 흔히 `.symtab`에 `malloc`, `strcpy` 같은 이름이 그대로 남는다) GDB로 이름으로 걸 수 있다.
```gdb
(gdb) break malloc
(gdb) break strcpy
(gdb) run
```
strip까지 되어 있어 이름도 없다면, 함수 시그니처(프롤로그 패턴)를 정적 분석 도구(Ghidra의 FunctionID, IDA의 FLIRT 시그니처)로 식별한 뒤 주소로 거는 수밖에 없다.

**4) 정말 함수 인자/리턴값 추적이 필요하면 GDB 스크립트로 ltrace 흉내**
```gdb
(gdb) break malloc
(gdb) commands
> printf "malloc(%d)\n", $rdi
> continue
> end
(gdb) run
```
`break`에 `commands`를 붙이면 그 지점을 지날 때마다 자동으로 인자를 출력하고 계속 진행하게 만들 수 있다 — 정적 바이너리에서 `ltrace`가 하던 일을 수동으로 재현하는 방법이다.

## 명령어/단축키
```bash
file ./chall
readelf -d ./chall
readelf -S ./chall | grep dynsym
strace ./chall
```
```gdb
break malloc
commands
printf "malloc(%d)\n", $rdi
continue
end
```

## 출력 해석
- `readelf -d ./chall` → `There is no dynamic section in this file.`은 완전 정적 링킹의 명확한 증거다.
- `file ./chall` → `ELF 64-bit LSB executable, ... statically linked, ... not stripped`처럼 `not stripped`가 함께 나오면 최소한 심볼 이름은 남아있어 GDB로 함수 이름 기반 접근이 가능하다는 뜻이다. `stripped`라면 이름 기반 접근도 불가능하다.
- `strace` 결과에서 `mmap(NULL, ..., PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, ...)`가 반복해서 보이면, 이는 정적 바이너리 내부의 `malloc` 구현이 힙을 확장하는 흔적이다 — `malloc` 자체 호출은 안 보여도 그 결과로 나타나는 syscall 패턴으로 간접 추론이 가능하다.

## 흔한 실수
- `ltrace`가 "설치가 잘못됐다"거나 "버전이 오래됐다"고 오해하고 재설치를 시도하는 것 — 원인은 도구 문제가 아니라 바이너리의 링킹 방식이다.
- `strace`로 바꾸면 되는데도 계속 `ltrace` 옵션(`-e`, `-S` 등)만 바꿔가며 재시도하는 것. `ltrace -S`는 시스템 콜까지 함께 보여주는 옵션이지만, 애초에 "라이브러리 함수 호출"을 가로채는 부분은 정적 바이너리에서 여전히 작동하지 않는다.
- CTF 문제에서 정적 바이너리를 일부러 준 이유(디버깅 방해, `libc` 버전 고정)를 무시하고 계속 동적 분석 도구로만 뚫으려 하는 것 — 정적 분석(Ghidra/IDA로 `malloc` 등 표준 라이브러리 함수 시그니처 인식)을 병행하는 게 더 빠를 때가 많다.

## 막혔을 때 다음 체크
- ltrace의 기본 사용법 자체가 처음이라면 → REV-0111 ltrace로 라이브러리 호출 빠르게 보기
- strace로 전환했는데 로그가 너무 많다면 → REV-0697 strace 결과가 너무 많아서 원하는 부분을 못 찾을 때
- 이 바이너리가 애초에 왜 정적 링킹됐는지, libc 버전 문제와 관련이 있는지 궁금하다면 → REV-0705 glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때
- GDB로 함수에 브레이크를 거는 세부 절차가 더 필요하다면 → REV-0696 동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때

## 미니 예제
```text
$ file ./chall
chall: ELF 64-bit LSB executable, x86-64, ... statically linked, for GNU/Linux 3.2.0, not stripped

$ ltrace ./chall
Couldn't find .dynsym or .dynstr in "/proc/9821/exe"

$ readelf -d ./chall
There is no dynamic section in this file.

$ strace -e trace=read,write ./chall
read(0, "test\n", 1024)                = 5
write(1, "Wrong password\n", 16)       = 16
```
`ltrace`는 `.dynsym`이 없어 바로 실패했지만, `readelf -d`로 정적 링킹임을 재확인한 뒤 `strace`로 바꾸자 최소한 입출력 흐름은 그대로 관찰할 수 있었다.

## 관련 글
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0697 — strace 결과가 너무 많아서 원하는 부분을 못 찾을 때
- REV-0696 — 동적 링킹된 함수에 브레이크포인트가 심볼 없이는 안 걸릴 때
- REV-0705 — glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때

## 출처/검증
- `ltrace`가 PLT/GOT 후킹 방식으로 동작하며 정적 링킹 바이너리를 트레이스할 수 없다는 점, `Couldn't find .dynsym or .dynstr` 에러 메시지는 ltrace 프로젝트(구 `ltrace.org`, 현재 gitlab.com/cespedes/ltrace) 문서 및 커뮤니티에 널리 보고된 표준 동작이다.
- `strace`는 syscall 레벨에서 동작하여 링킹 방식과 무관하게 항상 동작한다는 점은 `strace(1)`/`ptrace(2)` man page 기준이다.
- GDB의 `break`+`commands` 조합으로 함수 호출을 로깅하는 방법은 GDB 공식 문서 "Break Commands" 섹션에 기술되어 있다.
