---
id: REV-0651
title: "LD_LIBRARY_PATH와 라이브러리 탐색 순서"
slug: "rev-0651-ld-library-path-search-order"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, readelf, patchelf]
keywords: ["LD_LIBRARY_PATH", "RPATH", "RUNPATH", "ld.so.cache", "라이브러리 탐색 순서", "$ORIGIN"]
aliases: ["LD_LIBRARY_PATH란", "RPATH RUNPATH 차이", "라이브러리 못찾는 문제", "ld.so.cache란"]
symptom_keywords: ["error while loading shared libraries", "cannot open shared object file", "로컬 libc가 아니라 시스템 libc를 씀", "RPATH와 LD_LIBRARY_PATH 우선순위가 헷갈림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
동적 로더가 `libc.so.6` 같은 공유 라이브러리를 찾을 때는 `DT_RPATH`(RUNPATH가 없을 때만) → `LD_LIBRARY_PATH` 환경변수 → `DT_RUNPATH` → `/etc/ld.so.cache` → 기본 시스템 경로(`/lib`, `/usr/lib`) 순서로 검색하며, 이 순서를 모르면 CTF에서 "분명히 로컬 libc를 지정했는데 왜 시스템 libc가 로드되는지" 같은 문제에서 헤맨다.

## 언제 검색해야 하나
- `error while loading shared libraries: libc.so.6: cannot open shared object file`이 떴을 때
- `LD_LIBRARY_PATH=. ./chall`을 했는데도 여전히 시스템 `/lib/x86_64-linux-gnu/libc.so.6`이 로드될 때
- `readelf -d ./chall`에서 `RPATH`와 `RUNPATH`를 둘 다 봤는데 뭐가 더 우선인지 헷갈릴 때
- `patchelf --set-rpath`로 라이브러리 경로를 강제하고 싶은데 `$ORIGIN`이 뭔지 몰라서 막힐 때

## 핵심 개념

### 탐색 순서 — 정확한 우선순위
`man 8 ld.so`에 명시된 공식 순서는 다음과 같다(높은 우선순위부터).

1. **`DT_RPATH`** — 단, 같은 바이너리에 `DT_RUNPATH`가 존재하면 `DT_RPATH`는 완전히 무시된다(레거시).
2. **`LD_LIBRARY_PATH`** 환경변수에 나열된 디렉터리들(콜론으로 구분).
3. **`DT_RUNPATH`** — ELF `.dynamic` 섹션에 기록된 실행 파일 전용 검색 경로. RPATH의 후속 표준으로, 재귀적으로 로드되는 라이브러리에는 전파되지 않는다는 점이 RPATH와 다르다.
4. **`/etc/ld.so.cache`** — `ldconfig`가 시스템에 설치된 라이브러리들을 미리 스캔해 만들어둔 캐시 파일. 대부분의 일반 프로그램은 이 캐시를 통해 라이브러리를 찾는다.
5. **기본 트러스티드 경로** — `/lib`, `/usr/lib`(및 64비트 시스템의 `/lib64`, `/usr/lib64`) 등 로더에 하드코딩된 기본 경로.

핵심은 **`LD_LIBRARY_PATH`가 `DT_RUNPATH`보다 우선순위가 높다**는 점이다. 즉 바이너리에 `RUNPATH`가 박혀 있어도 `LD_LIBRARY_PATH`로 지정한 경로가 먼저 검색된다. 반면 `DT_RPATH`(RUNPATH 없을 때)는 `LD_LIBRARY_PATH`보다도 우선한다 — 그래서 RPATH가 박힌 오래된 바이너리는 환경변수로 라이브러리 경로를 못 바꾸는 경우가 있다.

### RPATH vs RUNPATH
둘 다 `readelf -d ./chall`로 확인 가능한 `.dynamic` 섹션의 태그다.

- `DT_RPATH`: 오래된 방식. 이 바이너리가 로드하는 모든 라이브러리, 그리고 그 라이브러리가 다시 로드하는 라이브러리에도 재귀적으로 적용된다.
- `DT_RUNPATH`: 최신 방식(기본 `ld`가 생성). 이 바이너리 자신에만 적용되고, 로드된 라이브러리가 또 다른 라이브러리를 찾을 때는 적용되지 않는다. 또한 `LD_LIBRARY_PATH`에 의해 오버라이드될 수 있다는 점이 보안상 더 예측 가능한 동작으로 여겨진다.

`gcc`로 링크할 때 `-Wl,-rpath,$ORIGIN`을 주면 기본적으로 RUNPATH가 만들어진다(구버전 바이너리 유틸리티나 `-Wl,--disable-new-dtags` 옵션을 쓰면 RPATH가 만들어질 수 있다).

### $ORIGIN 토큰
RPATH/RUNPATH 문자열 안에 `$ORIGIN`을 쓰면 로더가 이를 "현재 실행 중인 바이너리(또는 라이브러리)가 위치한 디렉터리"로 치환한다. 예를 들어 RUNPATH가 `$ORIGIN/lib`이면, `/home/user/chall`을 실행할 때 실제로는 `/home/user/lib`을 검색한다. 이는 배포 패키지를 어느 경로에 풀어도 상대 경로로 자기 라이브러리를 찾게 하는 표준적인 방법이다. `patchelf --set-rpath '$ORIGIN'`처럼 셸에서 `$`가 확장되지 않도록 작은따옴표로 감싸는 것이 중요하다.

### CTF에서 자주 쓰는 실전 패턴
CTF 배포 파일에 `libc.so.6`과 로더가 같이 온다면, 특정 libc로 강제 실행하는 방법은 두 가지다.

1. **환경변수 방식**(임시, 파일 수정 없음): `LD_LIBRARY_PATH=. ./ld-2.31.so ./chall` 또는 `env LD_LIBRARY_PATH=. ./chall`(단, 이 경우 바이너리의 INTERP가 시스템 로더를 가리키면 시스템 로더가 여전히 `libc.so.6` 이름을 찾을 때 `LD_LIBRARY_PATH`를 참고하므로 로컬 libc가 우선 로드될 수 있다).
2. **patchelf 방식**(영구, 파일 수정): `patchelf --set-interpreter ./ld-2.31.so --set-rpath '$ORIGIN' ./chall`로 인터프리터와 RUNPATH를 모두 로컬로 고정.

두 방식을 섞어 쓸 때 흔한 실수가, `LD_LIBRARY_PATH`를 지정했다고 안심했는데 실제로는 `RPATH`(RUNPATH 아님)가 이미 다른 경로를 가리키고 있어서 `LD_LIBRARY_PATH`가 무시되는 경우다 — RPATH가 LD_LIBRARY_PATH보다 우선순위가 높기 때문이다.

## 화면/코드에서 보이는 징후
- `./chall: error while loading shared libraries: libfoo.so: cannot open shared object file: No such file or directory`
- `readelf -d ./chall`에 `RPATH` 또는 `RUNPATH` 태그가 존재
- `LD_LIBRARY_PATH=. ./chall`을 했는데 `ldd ./chall`(같은 환경변수 하에서) 결과가 여전히 `/lib/x86_64-linux-gnu/libc.so.6`을 가리킴 → RPATH가 우선 적용되고 있다는 신호
- `strace`로 봤을 때 `openat(AT_FDCWD, "/etc/ld.so.cache", ...)` 호출이 보이면 캐시를 통해 시스템 라이브러리를 찾고 있다는 뜻

## 가장 먼저 할 것
`readelf -d ./chall | grep -E 'RPATH|RUNPATH'`로 바이너리에 하드코딩된 경로가 있는지부터 확인한다. 있다면 `LD_LIBRARY_PATH`만으로는 원하는 대로 안 될 수 있으니 `patchelf`로 직접 고치는 편이 확실하다.

## 단계별 절차
1. `readelf -d ./chall | grep -E 'RPATH|RUNPATH|NEEDED'`로 현재 상태 확인
2. RPATH가 있고 RUNPATH가 없다면 `LD_LIBRARY_PATH`가 무시될 수 있음을 인지
3. 로컬 libc를 강제하고 싶다면 `patchelf --set-rpath '$ORIGIN' --set-interpreter ./ld-2.31.so ./chall`
4. 패치 후 `readelf -d ./chall`로 RUNPATH가 제대로 박혔는지 재확인
5. `ldd ./chall`(신뢰 가능한 바이너리에 한해) 또는 `LD_TRACE_LOADED_OBJECTS=1 ./chall`로 실제 어떤 libc가 잡히는지 검증
6. GDB에서도 동일한 환경으로 디버깅해야 하므로 `gdb ./chall` 실행 전 환경변수/패치 상태를 동일하게 맞춘다

## 명령어/단축키
```bash
readelf -d ./chall | grep -E 'RPATH|RUNPATH|NEEDED'
LD_LIBRARY_PATH=. ./chall
patchelf --set-rpath '$ORIGIN' ./chall
patchelf --set-interpreter ./ld-2.31.so --set-rpath '$ORIGIN' ./chall
ldconfig -p | grep libc   # 시스템 캐시에 등록된 libc 목록
```

## 출력 해석
- `readelf -d` 결과에 `RUNPATH`만 있고 `RPATH`가 없다면 최신 링커로 빌드된 정상적인 경우이며, `LD_LIBRARY_PATH`로 오버라이드 가능하다.
- `RPATH`만 있다면 오래된 빌드 방식이며, 이 경로가 `LD_LIBRARY_PATH`보다 우선하므로 원하는 libc를 쓰려면 patchelf로 직접 고쳐야 한다.
- `error while loading shared libraries`는 대상 이름의 라이브러리를 전체 탐색 순서 어디에서도 못 찾았다는 뜻 — 경로 오타나 아키텍처 불일치(32비트 라이브러리를 64비트 경로에 넣는 등)를 의심한다.

## 흔한 실수
- `LD_LIBRARY_PATH`를 지정했는데도 시스템 libc가 로드되는 이유를 못 찾고 헤매는 것 — RPATH가 이미 다른 경로를 우선 지정하고 있을 가능성을 안 살펴본 것.
- `patchelf --set-rpath $ORIGIN`(따옴표 없이)를 실행해서 셸이 `$ORIGIN`을 빈 문자열로 확장해버리는 것 — 반드시 작은따옴표로 감싸야 한다.
- RUNPATH는 재귀적으로 전파되지 않는다는 점을 몰라서, A가 로드하는 B 라이브러리가 다시 C를 찾을 때 A의 RUNPATH가 적용될 거라고 오해하는 것.
- 32비트(x86) 바이너리에 64비트 libc 경로를 `LD_LIBRARY_PATH`로 지정해서 `wrong ELF class`류 오류를 만드는 것(REV-0675 multilib 참고).

## 막혔을 때 다음 체크
- 로더 자체를 직접 지정해서 실행하는 방법이 궁금하면 → REV-0649 ELF Interpreter(ld-linux.so)가 하는 일
- `LD_PRELOAD`로 함수를 후킹하는 방법과 이 환경변수가 어떻게 다른지 궁금하면 → REV-0650 LD_PRELOAD로 함수 후킹해서 관찰하기
- 정확한 glibc 버전을 알아내는 법이 먼저 필요하면 → REV-0648 glibc 버전별 함수 시그니처 차이 확인법
- 32비트 바이너리 실행 환경 자체가 안 갖춰져 있다면 → REV-0675 Linux에서 x86 32비트 바이너리 실행 환경 준비(multilib)

## 미니 예제
```bash
$ readelf -d ./chall | grep -E 'RPATH|RUNPATH'
 0x000000000000001d (RUNPATH)           Library runpath: [$ORIGIN]

$ LD_LIBRARY_PATH=. ./chall
(RUNPATH가 이미 $ORIGIN을 가리키므로 같은 디렉터리의 libc.so.6이 우선 로드됨)

$ patchelf --set-interpreter ./ld-2.31.so --set-rpath '$ORIGIN' ./chall
$ readelf -d ./chall | grep -E 'RPATH|RUNPATH'
 0x000000000000001d (RUNPATH)           Library runpath: [$ORIGIN]
```
`pwninit` 같은 도구가 내부적으로 하는 작업이 정확히 이것이다 — `patchelf`로 RUNPATH와 인터프리터를 로컬 디렉터리로 고정해서, 별도 환경변수 설정 없이 `./chall`만 실행해도 배포된 libc가 쓰이게 만든다.

## 관련 글
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일
- REV-0650 — LD_PRELOAD로 함수 후킹해서 관찰하기
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0675 — Linux에서 x86 32비트 바이너리 실행 환경 준비(multilib)
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- 라이브러리 탐색 순서(RPATH → LD_LIBRARY_PATH → RUNPATH → ld.so.cache → 기본 경로) 및 RPATH/RUNPATH 차이: `man 8 ld.so` 공식 매뉴얼(DESCRIPTION, "Rpath token expansion" 항목 포함) 기준.
- `$ORIGIN` 토큰 확장: `man 8 ld.so` 및 System V ABI 링커 확장 규칙 기준 (2026-09-08 검증).
