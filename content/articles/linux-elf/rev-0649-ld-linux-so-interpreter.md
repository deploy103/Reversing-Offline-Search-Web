---
id: REV-0649
title: "ELF Interpreter(ld-linux.so)가 하는 일"
slug: "rev-0649-ld-linux-so-interpreter"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg, readelf, patchelf]
keywords: ["ld-linux", "ld.so", "PT_INTERP", "동적 로더", "인터프리터", "_dl_start", "patchelf --set-interpreter"]
aliases: ["ld-linux.so란", "인터프리터 세그먼트란", "동적 로더가 하는 일", "PT_INTERP란"]
symptom_keywords: ["INTERP 세그먼트가 뭔지 모르겠음", "특정 libc 버전으로 강제 실행하고 싶음", "ld.so를 직접 실행해도 되는지 궁금함", "no such file or directory인데 파일은 있음(인터프리터 문제)"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
동적 링킹된 ELF를 실행하면 커널은 프로그램 코드를 바로 실행하지 않고 ELF의 `PT_INTERP` 세그먼트에 적힌 경로(보통 `/lib64/ld-linux-x86-64.so.2`)의 프로그램, 즉 동적 로더를 먼저 실행시키며, 이 로더가 필요한 공유 라이브러리를 매핑하고 재배치를 끝낸 뒤에야 진짜 프로그램의 진입점으로 점프한다.

## 언제 검색해야 하나
- `readelf -l ./chall` 출력에서 `INTERP` 줄과 `Requesting program interpreter` 문구를 봤는데 정확히 무슨 역할인지 모를 때
- CTF에서 특정 버전의 libc를 강제로 쓰게 만들고 싶어서 `/lib64/ld-linux-x86-64.so.2 ./chall` 같은 명령을 봤는데 왜 되는지 궁금할 때
- 원격 서버에서 `No such file or directory` 에러가 나는데 파일은 분명히 있어서 원인이 인터프리터 경로 문제일 수 있다고 의심될 때
- `patchelf --set-interpreter`를 써야 하는 이유와 동작 원리를 이해하고 싶을 때

## 핵심 개념

### PT_INTERP 세그먼트
동적 링킹된 ELF의 Program Header 중에는 `PT_INTERP` 타입 엔트리가 있다. 이 세그먼트의 내용은 단순한 문자열 하나, 즉 실행 시 사용할 동적 로더의 절대 경로다. x86-64 리눅스 기본값은 `/lib64/ld-linux-x86-64.so.2`이고, x86(32비트)은 `/lib/ld-linux.so.2`, musl은 `/lib/ld-musl-x86_64.so.1`이다(REV-0647). 커널의 `execve()` 시스템 콜은 ELF 헤더를 파싱하다가 `PT_INTERP`를 발견하면, 원래 실행하려던 파일이 아니라 이 경로의 파일을 대신 로드하고 그 인터프리터의 진입점으로 제어를 넘긴다.

### ld.so 자신도 ELF다
`/lib64/ld-linux-x86-64.so.2`는 그 자체로 `ET_DYN` 타입의 공유 오브젝트이며, glibc 소스에서 `elf/rtld.c`의 `_dl_start` 함수가 실제 시작점이다. 커널이 인터프리터를 실행할 때는 원본 실행 파일의 정보(경로, 세그먼트 위치 등)를 보조 벡터(auxiliary vector, REV-0677)에 실어서 넘겨준다. `_dl_start`는 이 정보를 이용해 다음 작업을 순서대로 수행한다.

1. 자기 자신(`ld.so`)의 재배치를 먼저 처리한다(로더 스스로도 위치 독립 코드로 컴파일되어 있어야 하므로 셀프 부트스트랩이 필요하다).
2. 대상 실행 파일의 `.dynamic` 섹션을 읽어 `DT_NEEDED` 엔트리들, 즉 필요한 공유 라이브러리 목록을 확인한다(REV-0101).
3. `LD_LIBRARY_PATH`, `DT_RPATH`/`DT_RUNPATH`, `/etc/ld.so.cache` 순서로 각 라이브러리를 검색해 메모리에 매핑한다(REV-0651에서 정확한 순서를 다룸).
4. 실행 파일과 각 라이브러리의 재배치 테이블(`.rela.dyn`, `.rela.plt`)을 이용해 심볼을 연결한다. 이 과정 일부가 GOT를 채우는 작업이다(REV-0100).
5. TLS(Thread Local Storage) 세그먼트를 초기화한다(REV-0680).
6. IFUNC(Indirect Function) 재배치를 해석해 CPU 기능에 맞는 함수 구현을 선택한다(REV-0679).
7. 모든 준비가 끝나면 원래 실행 파일의 `e_entry`(보통 `_start`)로 점프한다.

즉 `./chall`을 실행하는 순간 실제로 먼저 실행되는 코드는 우리 프로그램이 아니라 `ld.so`이며, 우리 프로그램의 `_start`(REV-0098)는 이 모든 준비가 끝난 뒤에야 실행된다.

### ld.so를 직접 실행할 수 있다 — CTF의 핵심 활용법
`ld-linux-x86-64.so.2`는 실행 가능한 파일이므로, 대상 프로그램을 인자로 넘겨 직접 실행할 수 있다.

```bash
/lib64/ld-linux-x86-64.so.2 ./chall
```

이 방식이 중요한 이유는 **어떤 로더와 어떤 라이브러리를 쓸지 사용자가 직접 지정할 수 있기 때문**이다. CTF 배포 파일에 특정 버전의 `libc.so.6`과 그에 맞는 `ld-2.31.so`가 함께 온다면, 시스템 기본 로더 대신 그 로더를 지정해서 실행하면 문제 서버와 정확히 같은 libc 버전으로 로컬 재현이 가능하다.

```bash
./ld-2.31.so --library-path . ./chall
```

`--library-path` 옵션은 `LD_LIBRARY_PATH`처럼 라이브러리 검색 경로를 지정한다. 이렇게 하면 바이너리 자체는 수정하지 않고도 지정한 libc로 강제 실행할 수 있다. 비슷한 목적으로 바이너리의 `PT_INTERP` 자체를 영구히 바꿔버리는 `patchelf --set-interpreter ./ld-2.31.so --set-rpath . ./chall` 방법도 널리 쓰인다 — 이러면 `./chall`을 그냥 실행하기만 해도 지정한 로더가 쓰인다(pwntools의 `pwninit` 도구가 이 작업을 자동화해준다).

### ldd의 정체
`ldd ./chall`이 하는 일도 사실 이 로더를 활용한 것이다. `ldd`는 내부적으로 `LD_TRACE_LOADED_OBJECTS=1` 환경변수를 설정하고 대상 프로그램을 로더에게 넘겨 실행시킨다. 로더는 이 환경변수를 보면 실제로 프로그램을 실행하지 않고 라이브러리 매핑 목록만 출력하고 종료한다. 즉 `ldd`는 대상 바이너리를 아주 잠깐이나마 "실행"시키는 셈이라, 신뢰할 수 없는 바이너리에는 `ldd` 대신 `readelf -d`만 쓰는 것이 안전하다(REV-0101에서 언급).

## 화면/코드에서 보이는 징후
- `readelf -l ./chall` 출력에 `INTERP` 세그먼트와 `[Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]`
- GDB로 실행 시작 직후 `info sharedlibrary`를 치면 아직 아무 라이브러리도 안 보이다가, `_start` 이후 시점에는 `libc.so.6`, `ld-linux-x86-64.so.2` 모두 매핑된 상태로 보임
- `strace ./chall` 출력의 맨 앞부분에 `execve` 직후 `ld.so`가 여러 `openat`, `mmap` 호출로 라이브러리를 찾고 매핑하는 과정이 잔뜩 나옴(REV-0662)
- 잘못된 인터프리터 경로(`patchelf` 실수 등)로는 `bash: ./chall: No such file or directory`처럼 파일이 실제로 존재해도 커널이 인터프리터를 못 찾아 실행 자체가 거부됨

## 가장 먼저 할 것
`readelf -l ./chall | grep interpreter`로 이 바이너리가 요구하는 로더 경로를 확인한다. 특정 libc 버전으로 강제 실행해야 하는 상황이라면, 시스템 기본 로더를 건드리지 말고 원하는 버전의 `ld-X.Y.so`를 직접 실행 인자로 넘기는 방식(`./ld-X.Y.so --library-path . ./chall`)부터 시도한다.

## 단계별 절차
1. `readelf -l ./chall`로 `PT_INTERP` 경로 확인
2. CTF에서 배포된 libc가 있다면 대응되는 로더(`ld-2.xx.so`)도 함께 있는지 확인 — 없다면 해당 배포판의 `libc6` 패키지에서 추출하거나 `glibc-all-in-one` 같은 도구로 구한다
3. `chmod +x ld-2.xx.so`로 실행 권한 부여
4. `./ld-2.xx.so --library-path . ./chall`로 정확한 버전 조합 실행 테스트
5. GDB로 디버깅할 때도 같은 방식을 써야 한다: `gdb --args ./ld-2.xx.so --library-path . ./chall`
6. 매번 이렇게 실행하기 번거로우면 `patchelf --set-interpreter ./ld-2.xx.so --set-rpath . ./chall`로 바이너리 자체를 패치(원본은 백업 권장)
7. pwntools를 쓴다면 `ELF.patchelf()` 또는 `pwninit` 도구로 이 과정을 자동화 가능

## 명령어/단축키
```bash
readelf -l ./chall | grep -A1 INTERP
/lib64/ld-linux-x86-64.so.2 ./chall
./ld-2.31.so --library-path . ./chall
patchelf --set-interpreter ./ld-2.31.so --set-rpath . ./chall
LD_TRACE_LOADED_OBJECTS=1 ./chall   # ldd와 동일한 효과
```

## 출력 해석
- `readelf -l` 결과에서 `INTERP` 세그먼트의 `[Requesting program interpreter: ...]`는 이 값이 절대 경로 문자열 그대로 커널에 전달된다는 뜻이다. 경로가 시스템에 없으면 실행 자체가 실패한다.
- `./ld-2.31.so --library-path . ./chall` 실행 시 프로그램이 정상 동작하면, 그 디렉터리의 `libc.so.6`을 실제로 사용했다는 뜻이므로 오프셋 계산에 안심하고 그 libc를 기준으로 삼을 수 있다.
- `LD_TRACE_LOADED_OBJECTS=1 ./chall` 결과는 `ldd ./chall`과 완전히 동일하다 — `ldd`는 이 환경변수를 설정해주는 셸 스크립트일 뿐이다.

## 흔한 실수
- `patchelf --set-interpreter`만 하고 `--set-rpath`를 빼먹어서, 로더는 바뀌었는데 여전히 시스템 libc를 찾아가 오프셋이 안 맞는 것.
- 로더 파일에 실행 권한(`chmod +x`)을 안 줘서 `Permission denied`가 나는 것.
- GDB에서 `file ./chall`로만 열고 `run`을 눌러서 시스템 기본 로더로 실행돼버리는 것 — 특정 로더를 쓰려면 `gdb --args ./ld-2.xx.so --library-path . ./chall`처럼 로더를 직접 지정해야 한다.
- 신뢰할 수 없는 CTF 바이너리에 `ldd`를 그냥 실행해서 의도치 않게 페이로드가 실행되는 것 — `ldd`도 결국 로더를 통해 대상 코드를 실행하는 것과 유사한 경로를 타므로 주의가 필요하다.

## 막혔을 때 다음 체크
- 라이브러리 검색 순서(`LD_LIBRARY_PATH` vs `RPATH`/`RUNPATH`)를 더 정확히 알고 싶다면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- 커널이 로더에 넘겨주는 보조 벡터(auxv) 구조가 궁금하면 → REV-0677 ELF Auxiliary Vector(auxv) 개요
- 로더가 마지막에 점프하는 `_start`부터의 흐름이 궁금하면 → REV-0098 _start 함수 읽는 법
- 대상 libc 버전을 정확히 확인하는 법이 필요하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법
- GOT/PLT 재배치가 이 로더 작업의 어느 부분인지 궁금하면 → REV-0100 PLT와 GOT 기초

## 미니 예제
```bash
$ readelf -l ./chall | grep -A1 INTERP
  INTERP         0x0000000000000318 0x0000000000000318 0x0000000000000318
                 0x000000000000001c 0x000000000000001c  R      0x1
      [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]

$ ./ld-2.31.so --library-path . ./chall
(정상 실행되면 이 디렉터리의 libc.so.6을 사용했다는 뜻)

$ LD_TRACE_LOADED_OBJECTS=1 ./chall
linux-vdso.so.1 (0x00007ffd...)
libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f...)
/lib64/ld-linux-x86-64.so.2 (0x00007f...)
```
마지막 줄이 `ldd ./chall`을 실행했을 때와 완전히 동일한 출력이라는 점이 `ldd`의 정체를 잘 보여준다.

## 관련 글
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0098 — _start 함수 읽는 법
- REV-0100 — PLT와 GOT 기초
- REV-0677 — ELF Auxiliary Vector(auxv) 개요

## 출처/검증
- `PT_INTERP` 세그먼트와 커널 `execve` 처리 방식: System V ABI 및 Linux `man 8 ld.so`, ELF Specification 기준.
- `_dl_start`, `elf/rtld.c` 부트스트랩 절차: glibc 공식 소스 저장소 기준.
- `ld.so --library-path` 옵션 및 `LD_TRACE_LOADED_OBJECTS`(ldd 구현 원리): `man 8 ld.so` 공식 매뉴얼 기준 (2026-09-08 검증).
