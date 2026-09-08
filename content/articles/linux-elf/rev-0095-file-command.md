---
id: REV-0095
title: "file 명령으로 ELF 정보 확인"
slug: "rev-0095-file-command"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["file"]
keywords: ["file 명령어", "libmagic", "file -i", "stripped 여부 확인", "PIE 여부 확인"]
aliases: ["file 사용법", "file 명령", "file 옵션", "파일 타입 확인"]
symptom_keywords: ["file 명령 결과 해석 안됨", "이 파일이 어떤 종류인지 모름", "pie인지 아닌지 빠르게 확인하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`file` 명령은 파일의 매직 넘버와 내부 구조를 읽어 "이 파일이 정확히 무엇인지"를 한 줄로 요약해주며, ELF 바이너리를 받았을 때 비트수·아키텍처·PIE 여부·strip 여부·동적 링킹 여부를 5초 안에 파악하는 가장 빠른 방법이다.

## 언제 검색해야 하나
- 분석 대상 바이너리를 처음 받아서 IDA/Ghidra 열기 전에 기본 정보부터 확인하고 싶을 때
- 확장자가 없거나 엉뚱한 파일이 실제로 ELF인지, 스크립트인지, 다른 포맷인지 확인하고 싶을 때
- 32비트인지 64비트인지, PIE인지, strip됐는지를 `readelf`보다 더 빠르게 한 줄로 확인하고 싶을 때

## 핵심 개념
`file`은 파일의 확장자를 전혀 신뢰하지 않는다. 대신 `libmagic` 데이터베이스를 이용해 파일 앞부분의 **매직 넘버**(ELF의 경우 `7F 45 4C 46`, REV-0089 참고)와 몇 가지 헤더 필드를 읽어서 사람이 이해하기 쉬운 한 줄 설명으로 바꿔준다. `readelf -h`가 정확하지만 여러 줄에 걸쳐 필드별로 나오는 반면, `file`은 그중 리버서가 가장 자주 필요로 하는 정보(비트수, 엔디안, 아키텍처, 실행 파일 종류, 동적 링킹 여부, interpreter 경로, strip 여부)를 압축해서 한 줄로 보여준다.

## 화면/코드에서 보이는 징후
CTF 문제 파일을 받았을 때 가장 먼저 실행하는 명령 중 하나. `chall`, `chall.bin`, 확장자 없는 파일을 받았을 때 특히 유용하다.

## 가장 먼저 할 것
```bash
file ./chall
```
단 한 줄로 이 바이너리에 대한 핵심 정보를 확보한다.

## 단계별 절차

**1) 기본 실행**
```bash
file ./chall
```
출력 예 (동적 링킹, PIE, strip 안 됨):
```
chall: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), \
dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, \
BuildID[sha1]=3a5f..., for GNU/Linux 3.2.0, not stripped
```

strip된 경우 마지막이 다르게 나온다:
```
chall: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), \
dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, \
BuildID[sha1]=..., for GNU/Linux 3.2.0, stripped
```

정적 링킹된 경우:
```
chall: ELF 64-bit LSB executable, x86-64, version 1 (GNU/Linux), \
statically linked, BuildID[sha1]=..., for GNU/Linux 3.2.0, not stripped
```
`pie executable`이 아니라 그냥 `executable`이라고 나오면 non-PIE(고정 주소 로드)라는 뜻.

**2) 여러 파일 한꺼번에 확인**
```bash
file ./*
```
디렉터리 안 모든 파일의 종류를 한 번에 파악(첨부 파일이 여러 개인 CTF 문제에서 유용).

**3) 심볼릭 링크를 따라가서 실제 파일 확인**
```bash
file -L ./chall
```

**4) MIME 타입으로만 간결하게 확인 (스크립팅용)**
```bash
file -i ./chall
# 출력: chall: application/x-pie-executable; charset=binary
```

**5) 압축/아카이브 안 파일까지 재귀적으로 확인**
```bash
file -z ./chall.gz
```

## 명령어/단축키
```bash
file ./chall            # 기본 사용
file -i ./chall          # MIME 타입 (스크립트에서 파싱하기 좋음)
file ./*                 # 여러 파일 한꺼번에
```

## 출력 해석
필드를 왼쪽부터 순서대로 읽으면 된다:
- `ELF 64-bit LSB` → 64비트, 리틀 엔디안(LSB)
- `pie executable` / `executable` / `shared object` → PIE 실행 파일 / non-PIE 실행 파일 / 공유 라이브러리(`.so`). 참고로 `.so` 파일도 내부적으로는 `pie executable`과 같은 `ET_DYN`이라, 확장자나 `interpreter` 유무로 실제 실행 파일인지 구분해야 한다.
- `x86-64` → 아키텍처
- `dynamically linked` / `statically linked` → 동적/정적 링킹 여부. 동적 링킹이면 `interpreter` 경로(동적 로더)가 같이 나온다.
- `interpreter /lib64/ld-linux-x86-64.so.2` → Program Header의 `PT_INTERP` 세그먼트 값(REV-0090 참고)을 그대로 보여준 것.
- `BuildID[sha1]=...` → 빌드마다 고유한 식별자(디버그 심볼 매칭 등에 사용, 리버싱에서는 크게 중요하지 않음).
- `not stripped` / `stripped` → 심볼 테이블(`.symtab`) 존재 여부. `not stripped`면 `nm`(REV-0093)으로 함수 이름을 바로 볼 수 있다는 뜻.

## 흔한 실수
- `file` 결과의 `not stripped`를 보고 "그러면 디버그 정보(소스 라인, 변수명)까지 다 있다"고 착각하는 것 — 이는 심볼 테이블(함수/전역변수 이름)만 있다는 뜻이지, DWARF 디버그 정보(줄 번호, 지역 변수 이름, 타입 정보)와는 다른 것이다. DWARF까지 있으려면 `-g` 옵션으로 컴파일된 디버그 빌드여야 한다.
- 확장자만 보고 파일 종류를 판단하는 것 — `chall.txt`가 실제로는 ELF 실행 파일일 수도 있다. `file`은 매직 넘버 기반이라 확장자에 속지 않는다.
- `shared object`라고 나오면 무조건 라이브러리라고 단정하는 것 — PIE 실행 파일도 `ET_DYN`이라 구버전 `file`에서는 `shared object`로 표시될 수 있다(최신 버전은 `pie executable`로 구분해서 표시). `interpreter`나 `.dynamic`의 유무로 실제 실행 가능한 파일인지 다시 확인하는 게 안전하다.

## 막혔을 때 다음 체크
- `file`이 알려준 정보를 더 깊이 파려면 → [REV-0089 ELF 헤더 읽는 법](./rev-0089-elf-header.md), [REV-0091 readelf 기본 사용법](./rev-0091-readelf-basics.md)
- `stripped`라고 나왔다면 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- 보호 기법(NX, RELRO, Canary, PIE)까지 종합적으로 확인하려면 → [REV-0096 checksec 결과 읽는 법](./rev-0096-checksec.md)

## 미니 예제
```bash
$ file chall
chall: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), \
dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, \
BuildID[sha1]=3a5f1e..., for GNU/Linux 3.2.0, not stripped
```
이 한 줄에서: 64비트, PIE(주소가 매 실행마다 바뀜), x86-64, 동적 링킹(libc를 따로 로드함), 심볼 안 지워짐(함수 이름 그대로 볼 수 있음)까지 전부 확인했다.

## 관련 글
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0091 — readelf 기본 사용법](./rev-0091-readelf-basics.md)
- [REV-0096 — checksec 결과 읽는 법](./rev-0096-checksec.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)

## 출처/검증
- `file` 명령 출력 필드 의미: `file(1)` man page 및 `libmagic` ELF 매직 규칙(`magic/Magdir/elf`) 기준 (2026-09-08 검증).
