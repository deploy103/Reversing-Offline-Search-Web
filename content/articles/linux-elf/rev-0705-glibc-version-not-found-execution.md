---
id: REV-0705
title: "glibc 버전이 안 맞아서 바이너리가 실행이 안 될 때"
slug: "rev-0705-glibc-version-not-found-execution"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [patchelf, pwninit, "ld.so"]
keywords: ["GLIBC_2.34 not found", "version not found", "glibc 버전 실행 오류", "patchelf --set-interpreter", "pwninit"]
aliases: ["libc.so.6 version not found", "GLIBC not found 오류", "바이너리가 아예 안 켜짐 glibc", "다른 glibc로 실행하기"]
symptom_keywords: ["/lib/x86_64-linux-gnu/libc.so.6: version GLIBC_2.34 not found 오류가 남", "바이너리를 실행하면 즉시 종료되며 glibc 관련 오류가 남", "CTF에서 받은 chall이 로컬에서 아예 실행이 안 됨", "libc가 없다는 오류로 바이너리 실행 자체가 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`./chall: /lib/x86_64-linux-gnu/libc.so.6: version 'GLIBC_2.34' not found`처럼 바이너리가 아예 실행조차 안 되는 오류는 그 바이너리가 컴파일된 서버의 glibc가 로컬 시스템의 glibc보다 최신이라서 필요한 심볼 버전을 못 찾는 것이며, 함께 배포된 `libc.so.6`과 `ld-linux.so`를 명시적으로 지정해서 실행하거나 `patchelf`로 인터프리터/RPATH를 그 libc로 고정하면 해결된다.

## 언제 검색해야 하나
- CTF 문제에서 `chall`, `libc.so.6`, `ld-linux-x86-64.so.2`를 함께 받았는데 `./chall`을 그냥 실행하면 `version 'GLIBC_2.xx' not found` 오류가 뜰 때
- 로컬 우분투/데비안 버전이 오래되어 최신 glibc로 컴파일된 CTF 바이너리가 실행 자체가 안 될 때
- `ldd ./chall` 결과에 `libc.so.6 => /lib/.../libc.so.6 (버전 안 맞음)` 경고가 보일 때
- 이미 실행은 되는데 익스플로잇 오프셋이 서버와 안 맞는 문제라면 이 글이 아니라 REV-0711을 봐야 하는 상황과 헷갈릴 때

## 핵심 개념

### 왜 이 오류가 나는가 — glibc의 심볼 버전 관리
glibc는 함수마다 `GLIBC_2.2.5`, `GLIBC_2.34`처럼 심볼 버전 태그를 붙여 관리한다(symbol versioning). 바이너리는 컴파일 당시 링크된 glibc 버전의 심볼을 참조하도록 새겨지는데, 런타임에 로드되는 `libc.so.6`이 그 심볼 버전을 갖고 있지 않으면(즉 로컬 glibc가 컴파일 서버 glibc보다 오래됐으면) 동적 로더(`ld.so`)가 `version 'GLIBC_2.34' not found`라며 실행 자체를 거부한다. glibc는 기본적으로 **하위 호환은 보장하지만 상위 호환은 보장하지 않는다** — 즉 새 glibc로 컴파일된 바이너리는 오래된 glibc에서 돌아가지 않는다.

### 해결 전략 — 함께 배포된 libc/ld를 그대로 사용
CTF 문제는 보통 서버와 동일한 `libc.so.6`, 그리고 그에 대응하는 `ld-linux-x86-64.so.2`(또는 `ld-2.xx.so`)를 함께 제공한다. 이 두 파일을 이용해 시스템 기본 로더 대신 그 로더로 직접 실행하면, 시스템 libc가 아니라 배포받은 libc를 사용하게 되어 버전 문제가 사라진다.

### patchelf로 인터프리터/RPATH 고정
매번 명령줄에서 `ld.so`를 지정하기 번거롭다면 `patchelf`로 바이너리 자체의 `INTERP`(ELF Interpreter, REV-0649)와 `RPATH`를 바꿔서, `./chall`을 그냥 실행해도 원하는 libc/ld 세트를 쓰도록 고정할 수 있다. `pwninit` 같은 도구는 이 과정(다운로드한 libc/ld 권한 설정, patchelf 적용, GDB script까지)을 자동화해준다.

## 화면/코드에서 보이는 징후
```
$ ./chall
./chall: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found (required by ./chall)
```
또는
```
$ ldd ./chall
	libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f...)
	/lib64/ld-linux-x86-64.so.2 (0x00007f...)
```
`ldd` 자체는 별문제 없어 보여도 실제 실행 시 위와 같은 버전 오류가 날 수 있다는 점에 주의한다.

## 가장 먼저 할 것
문제 폴더에 `libc.so.6`과 `ld-linux*.so*`(또는 이름이 다른 `ld-*.so`)가 함께 왔는지 확인한다. 있다면 시스템 로더 대신 그 로더로 직접 실행해본다.

## 단계별 절차
1. 배포된 파일 목록 확인 (`ls`) — `chall`, `libc.so.6`, `ld-2.xx.so` 등
2. `chmod +x ./ld-2.xx.so` (실행 비트 확인, REV-0702 참고)
3. 배포된 로더로 직접 실행: `./ld-2.xx.so --library-path . ./chall`
4. 매번 이렇게 실행하기 번거로우면 `patchelf`로 고정
   ```bash
   patchelf --set-interpreter ./ld-2.xx.so ./chall
   patchelf --set-rpath . ./chall
   ```
5. 이후 `./chall`만으로 정상 실행되는지 확인
6. `pwninit`이 설치되어 있다면 `pwninit` 한 번으로 위 과정 자동화 가능
7. 그래도 안 되면 배포된 libc 버전과 바이너리가 실제로 링크된 버전이 일치하는지 `strings ./libc.so.6 | grep "GNU C Library"`로 재확인

## 명령어/단축키
```bash
ldd ./chall
strings ./libc.so.6 | grep "GNU C Library"
./ld-2.xx.so --library-path . ./chall
patchelf --set-interpreter ./ld-2.xx.so ./chall
patchelf --set-rpath . ./chall
pwninit
```

## 출력 해석
`version 'GLIBC_2.34' not found (required by ./chall)`에서 `GLIBC_2.34`는 바이너리가 요구하는 최소 심볼 버전이다. 시스템 `libc.so.6`의 버전은 `strings /lib/x86_64-linux-gnu/libc.so.6 | grep "release version"`으로 확인할 수 있으며, 이 값이 요구 버전보다 낮으면 반드시 배포된 libc로 교체 실행해야 한다. `patchelf` 적용 후 `readelf -d ./chall | grep -E 'NEEDED|RPATH|RUNPATH'`로 실제 인터프리터/RPATH가 원하는 경로로 바뀌었는지 확인할 수 있다.

## 흔한 실수
- 시스템 glibc를 강제로 업그레이드하려다가 시스템 전체(다른 프로그램들이 의존하는 libc)를 망가뜨리는 것 — 시스템 libc는 절대 건드리지 말고 로컬 디렉터리 안의 사본만 사용해야 한다.
- 배포된 `ld-*.so`에 실행 비트가 없어서 "이 방법도 안 되네"라고 오해하는 것(REV-0702의 Permission denied 문제와 겹칠 수 있다).
- `patchelf` 적용 후 원본 바이너리를 덮어써서 되돌릴 수 없게 만드는 것 — 항상 원본을 백업해두고 사본에 적용한다.
- 이미 정상 실행되고 있는데 서버와 익스플로잇 결과(오프셋)가 안 맞는 상황을 이 글의 "실행 자체가 안 되는" 문제와 혼동하는 것 — 그 경우는 REV-0711을 봐야 한다.

## 막혔을 때 다음 체크
- 실행은 되는데 오프셋/one_gadget 결과가 서버와 안 맞는 문제라면 → REV-0711 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때.
- ELF Interpreter(`ld-linux.so`)가 정확히 무슨 역할을 하는지 궁금하면 → REV-0649 ELF Interpreter(ld-linux.so)가 하는 일.
- 애초에 정적 링킹으로 만들어서 이런 문제 자체를 피하고 싶다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법.

## 미니 예제
```bash
$ ./chall
./chall: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.34' not found (required by ./chall)
$ chmod +x ld-2.35.so
$ ./ld-2.35.so --library-path . ./chall
Welcome to the challenge!
$ patchelf --set-interpreter ./ld-2.35.so ./chall
$ patchelf --set-rpath . ./chall
$ ./chall
Welcome to the challenge!
```
배포된 로더로 직접 실행하면 바로 성공하고, `patchelf`로 고정한 뒤에는 `./chall`만으로도 동일하게 동작한다.

## 관련 글
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0702 — Permission denied로 바이너리 실행이 안 될 때

## 출처/검증
- glibc의 심볼 버전 관리(symbol versioning)와 하위 호환/상위 비호환 정책: GNU glibc 공식 문서("Library Interfaces" 및 ABI 관리 문서) 기준.
- 동적 로더를 직접 지정해 실행하는 `ld.so --library-path` 방식: `ld.so(8)` 공식 매뉴얼 기준.
- `patchelf`의 `--set-interpreter`/`--set-rpath` 옵션 동작: patchelf 공식 저장소(NixOS/patchelf) 문서 기준 (2026-09-09 검증).
