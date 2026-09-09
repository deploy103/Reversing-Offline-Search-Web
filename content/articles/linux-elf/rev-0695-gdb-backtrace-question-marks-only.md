---
id: REV-0695
title: "GDB backtrace가 ??로만 나와서 콜스택을 못 볼 때"
slug: "rev-0695-gdb-backtrace-question-marks-only"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB]
keywords: ["gdb backtrace ??", "in ?? ()", "No symbol table info available", "gdb 콜스택 함수이름 안보임", "stripped binary backtrace"]
aliases: ["gdb bt ?? ()만 나옴", "백트레이스에 함수이름 없음", "gdb 콜스택 주소만 보임"]
symptom_keywords: ["bt 했더니 전부 in ?? ()로만 나옴", "함수 이름 없이 주소만 나열됨", "strip된 바이너리라 콜스택을 못 읽겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-GDB-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`bt` 결과의 각 프레임이 `#N  0x... in ?? ()`처럼 함수 이름 없이 주소만 나온다면, 그 코드 영역에 대응하는 심볼 테이블 정보가 GDB에 없기 때문이며, 대부분 바이너리/공유 라이브러리가 strip되었거나 아직 로드되지 않은 상태에서 백트레이스를 시도했을 때 나타나는 정상적인(그러나 불편한) 동작이다.

## 언제 검색해야 하나
- `bt` 결과 프레임마다 함수명 대신 `in ?? ()`만 반복해서 나올 때
- strip된(`file` 결과에 `stripped`로 표시되는) 바이너리나 정적 링크된 실행 파일을 디버깅 중일 때
- 공유 라이브러리(`libc` 등) 안에서 크래시가 나서 `bt`를 찍었는데 라이브러리 쪽 프레임만 `??`로 보일 때
- 라이브러리가 아직 로드되기 전(예: `_start` 근처)에 브레이크포인트를 걸어 `bt`를 찍었을 때

## 핵심 개념
GDB가 각 스택 프레임에 함수 이름을 붙일 수 있는 것은, 그 프레임의 반환 주소가 어떤 함수의 어느 심볼에 속하는지를 알려주는 **심볼 테이블**(ELF의 `.symtab`/`.dynsym`, 또는 컴파일러가 남긴 디버그 정보)이 있기 때문이다. 이 정보가 없으면 GDB는 그 주소가 몇 번째 함수인지 전혀 알 수 없어 그냥 `?? ()`로만 표시한다. 이런 상황이 나오는 대표적 이유는 세 가지다.
1. **바이너리 자체가 strip됨**: `strip ./chall`로 심볼 테이블이 제거된 실행 파일은 자신의 함수들에 대해 GDB가 이름을 붙일 수 없다.
2. **공유 라이브러리가 아직 GDB에 인식되지 않음**: 동적 링킹된 프로그램은 `libc.so.6` 등이 런타임에 로드되는데, 로드되기 전(예: 진입점 직후)에는 GDB가 그 주소 범위에 어떤 라이브러리가 있는지 아직 모른다.
3. **`.debug_info` 없이 `.dynsym`/`.symtab`만 참조 가능한 라이브러리에서, 그마저도 strip된 배포용 `libc`를 쓰는 경우**: 배포판 기본 `libc.so.6`은 보통 strip되어 있어 개별 내부 함수 이름(`__vfprintf_internal` 등)까지는 안 나오고, exported 심볼(`printf` 등)만 나오거나 그마저도 안 나올 수 있다.

## 화면/코드에서 보이는 징후
```gdb
(gdb) bt
#0  0x00007ffff7a52d2e in ?? ()
#1  0x00007ffff7a3ee40 in ?? ()
#2  0x0000000000401136 in ?? ()
#3  0x0000000000000000 in ?? ()
```
심한 경우 자신이 만든 코드 부분(`main`, 사용자 정의 함수)까지도 전부 `?? ()`로만 보여서, 어느 함수에서 크래시가 났는지조차 짐작이 안 되는 상황이 된다.

## 가장 먼저 할 것
`file ./chall`로 strip 여부를 확인하고, `info sharedlibrary`로 현재 GDB가 인식한 공유 라이브러리 목록과 심볼 로드 상태를 확인한다.

## 단계별 절차
1. `file ./chall`로 `not stripped`/`stripped` 여부 확인
2. strip 안 됐는데도 `??`가 나온다면 `info sharedlibrary`로 해당 주소 범위의 라이브러리가 제대로 매핑/심볼 로드됐는지 확인
3. 라이브러리 심볼이 안 보이면 배포판의 디버그 심볼 패키지를 설치 — Ubuntu/Debian 계열은 `libc6-dbg` 패키지, 또는 `debuginfod`(최신 GDB가 자동으로 원격 심볼 서버에서 디버그 정보를 내려받는 기능)가 활성화되어 있는지 확인
   ```bash
   sudo apt install libc6-dbg
   ```
4. 자신이 만든 바이너리가 strip됐다면, strip 안 된 사본으로 다시 컴파일하거나(`gcc -g`) 원본 오브젝트가 있으면 `symbol-file`로 심볼만 별도로 로드
   ```gdb
   symbol-file ./chall_with_symbols
   ```
5. strip된 배포용 바이너리를 그대로 분석해야 한다면, 함수 이름 대신 주소 기준으로 `x/10i $pc`, `info proc mappings`를 조합해 어느 모듈(바이너리 자신 vs 특정 `.so`) 소속인지부터 구분
6. 라이브러리가 아직 로드되기 전 시점이라 `??`가 나온 것이라면, `run`을 조금 더 진행시키거나(`continue`) 라이브러리 로드 이후 시점에서 다시 `bt`

## 명령어/단축키
```bash
file ./chall
sudo apt install libc6-dbg
```
```gdb
bt
info sharedlibrary
symbol-file ./chall_with_symbols
x/10i $pc
info proc mappings
```

## 출력 해석
`info sharedlibrary` 결과에서 어떤 라이브러리 줄에 `Syms Read`가 `No`로 표시되면, 그 라이브러리에 속한 주소는 backtrace에서 `??`로 나올 수밖에 없다. `libc6-dbg` 설치 후 다시 확인하면 해당 줄이 `Yes`로 바뀌고, 이후 `bt`에서 `printf`, `__libc_start_main` 같은 이름이 정상적으로 표시된다. 자신이 만든 바이너리 부분이 `??`로 나오는 경우는 대부분 `file` 결과가 `stripped`인 경우이며, 이때는 라이브러리 문제가 아니라 실행 파일 자체의 심볼 부재가 원인이다.

## 흔한 실수
- `libc`가 strip된 배포판 기본 패키지라는 걸 모르고, `libc6-dbg` 없이 계속 라이브러리 쪽 콜스택만 노려보는 것.
- strip된 실행 파일에서 `??`가 나오는 걸 GDB 설정 문제로 오해해서 애꿎은 GDB 설정을 계속 고치는 것 — 원인은 바이너리 자체에 있다.
- 라이브러리가 로드되기 전 이른 시점(엔트리 포인트 부근)에서 `bt`를 찍고 "라이브러리 심볼이 아예 없다"고 단정하는 것 — 조금 더 실행을 진행시키면 정상적으로 심볼이 붙는 경우가 많다.
- `symbol-file`로 심볼만 별도로 로드할 때 실제 실행 중인 바이너리와 다른 버전의 심볼 파일을 로드해서, 주소는 맞는데 함수 이름/줄 번호가 실제와 다르게 나오는 것을 눈치채지 못하는 것.

## 막혔을 때 다음 체크
- 백트레이스 자체가 `corrupt stack`으로 중단된다면 → REV-0694 GDB에서 스택 프레임이 corrupted stack frame이라고 나올 때
- 정적 링킹된 strip 바이너리에서 심볼을 아예 못 찾는 근본적인 상황이라면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- ELF에 디버그 정보(`.debug_info`)가 남아있는 경우 활용법이 궁금하면 → REV-0667 ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기

## 미니 예제
```gdb
(gdb) bt
#0  0x00007ffff7a52d2e in ?? ()
#1  0x00007ffff7a3ee40 in ?? ()

(gdb) info sharedlibrary
From                To                  Syms Read   Shared Object Library
0x00007ffff7fce090  0x00007ffff7fef7ff  Yes         /lib64/ld-linux-x86-64.so.2
0x00007ffff7a1c000  0x00007ffff7c00000  No          /lib/x86_64-linux-gnu/libc.so.6
```
`libc.so.6`의 `Syms Read`가 `No`인 것을 확인하고 `libc6-dbg`를 설치한 뒤:
```gdb
(gdb) bt
#0  0x00007ffff7a52d2e in __GI___libc_write (fd=1, buf=..., nbytes=13) at ../sysdeps/unix/sysv/linux/write.c:26
#1  0x00007ffff7a3ee40 in _IO_file_write () from /lib/x86_64-linux-gnu/libc.so.6
```
같은 위치의 프레임이 함수 이름과 소스 줄 번호까지 포함해서 정상적으로 표시됐다.

## 관련 글
- REV-0694 — GDB에서 스택 프레임이 corrupted stack frame이라고 나올 때
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0667 — ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기

## 출처/검증
- GDB의 심볼 테이블 기반 프레임 이름 표시 및 `info sharedlibrary`, `symbol-file` 동작: GDB 공식 문서("Symbols", "Shared Libraries") 기준.
- 배포판 `libc6-dbg` 패키지 및 `debuginfod`를 통한 디버그 심볼 확보 방식: Debian/Ubuntu 공식 패키지 문서 및 GDB `debuginfod` 지원 문서 기준 (2026-09-09 검증).
