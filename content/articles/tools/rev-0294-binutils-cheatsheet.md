---
id: REV-0294
title: "readelf objdump nm strings 치트시트"
slug: "rev-0294-binutils-cheatsheet"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["readelf", "objdump", "nm", "strings", "binutils"]
keywords: ["binutils 치트시트", "readelf objdump nm strings", "binutils 명령어 정리", "ELF 커맨드라인 분석"]
aliases: ["binutils 명령어 모음", "readelf objdump nm strings 비교", "리눅스 바이너리 분석 치트시트"]
symptom_keywords: ["readelf objdump nm strings 어떤 걸 써야할지 모름", "binutils 명령어를 자꾸 까먹음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`readelf`, `objdump`, `nm`, `strings`는 각각 ELF 구조/디스어셈블리/심볼/문자열이라는 서로 다른 관심사를 담당하는 GNU binutils 도구이며, 이 문서는 네 도구의 최다빈출 명령만 모은 빠른 조회용 표다.

## 언제 검색해야 하나
- 네 도구 중 어떤 걸 써야 할지 헷갈릴 때
- 옵션 철자가 기억 안 나서 매번 `man`을 찾아보기 귀찮을 때

각 도구의 출력 형식 해석, 흔한 실수, 상세 예제는 이 문서에서 반복하지 않는다. 아래 원본 문서를 참고할 것.
- [REV-0091 readelf 기본 사용법](../linux-elf/rev-0091-readelf-basics.md)
- [REV-0092 objdump 기본 사용법](../linux-elf/rev-0092-objdump-basics.md)
- [REV-0093 nm으로 심볼 찾기](../linux-elf/rev-0093-nm-basics.md)
- [REV-0094 strings로 빠르게 단서 찾기](../linux-elf/rev-0094-strings-basics.md)

## 핵심 개념
네 도구 모두 GNU binutils 소속이며 컴파일된 ELF를 "다른 각도"로 읽는다 — 구조(readelf)/코드(objdump)/이름표(nm)/텍스트(strings). 하나로 부족하면 나머지를 조합해서 쓰는 것이 정상이다.

## 가장 먼저 할 것
아래 "무엇을 볼 때 어떤 도구인가" 표에서 지금 알고 싶은 정보에 해당하는 줄만 찾아 그 명령을 그대로 복붙한다.

## 단계별 절차 / 명령어/단축키
아래 도구별 절 참고. 순서를 모르겠다면 "조합 예시 — 30초 트리아지"부터 그대로 따라 하면 된다.

## 무엇을 볼 때 어떤 도구인가
| 알고 싶은 것 | 도구 |
|---|---|
| ELF 헤더/세그먼트/섹션 구조 | `readelf` |
| 실제 디스어셈블리(기계어 → 어셈블리) | `objdump` |
| 함수/변수 이름과 주소 한 줄 요약 | `nm` |
| 하드코딩된 텍스트(암호, flag 형식 등) | `strings` |

## readelf — ELF 구조 (REV-0091)
```bash
readelf -h ./chall          # ELF 헤더 (엔트리포인트, 타입, 아키텍처)
readelf -S ./chall          # 섹션 헤더 테이블
readelf -l ./chall          # 프로그램 헤더(세그먼트) 테이블
readelf -s ./chall          # 심볼 테이블
readelf -d ./chall          # 동적 섹션 (NEEDED 라이브러리 등)
readelf -x .rodata ./chall  # 특정 섹션 헥스 덤프
readelf -aW ./chall | less  # 전부 + 넓게 출력 + 페이저
```

## objdump — 디스어셈블리 (REV-0092)
```bash
objdump -d -M intel ./chall                       # 실행 섹션 디스어셈블 (Intel 문법)
objdump -d -M intel ./chall | grep -A20 '<main>:'  # main 함수만 잘라 보기
objdump -T ./chall                                 # 동적 심볼 테이블
objdump -R ./chall                                 # 재배치 정보 (GOT 엔트리 등)
objdump -s -j .rodata ./chall                      # .rodata 섹션 원시 바이트 덤프
```

## nm — 심볼 (REV-0093)
```bash
nm ./chall              # 심볼 테이블 (.symtab, strip되면 실패)
nm -D ./chall           # 동적 심볼 (.dynsym, strip돼도 대부분 남음)
nm -n ./chall           # 주소순 정렬
nm -C ./chall           # C++ 이름 demangle
nm --size-sort ./chall  # 크기순 정렬(핵심 로직 함수 추정에 유용)
```

## strings — 문자열 (REV-0094)
```bash
strings ./chall                # 기본(4바이트 이상 ASCII)
strings -n 6 ./chall           # 최소 길이 조정
strings -t x ./chall           # 16진수 오프셋 포함
strings ./chall | grep -i flag # 키워드 필터
```

## 막혔을 때 다음 체크
표에 없는 옵션이 필요하면 각 도구의 원본 문서(REV-0091~REV-0094)로 가서 더 깊은 설명과 출력 해석을 참고한다.

## 미니 예제 — 조합 예시(30초 트리아지)
```bash
file ./chall
readelf -h ./chall | grep Type      # PIE 여부
nm ./chall | grep ' T main'         # strip 여부 + main 주소
strings ./chall | grep -iE 'flag|password'
objdump -d -M intel ./chall | grep -A20 '<main>:'
```
이 다섯 줄이면 IDA를 열기 전에 "PIE인지, strip됐는지, main이 어디인지, 눈에 띄는 문자열이 있는지, main의 첫 흐름이 뭔지"를 모두 확인할 수 있다.

## 관련 글
- REV-0091 — readelf 기본 사용법
- REV-0092 — objdump 기본 사용법
- REV-0093 — nm으로 심볼 찾기
- REV-0094 — strings로 빠르게 단서 찾기
- REV-0295 — checksec 설치와 사용법

## 출처/검증
- 모든 명령/옵션은 이 저장소의 REV-0091~REV-0094 원본 문서(GNU binutils 공식 man page 기준으로 이미 검증됨)에서 그대로 발췌한 것이며, 이 문서 자체에서 새로 검증한 내용은 없다.
