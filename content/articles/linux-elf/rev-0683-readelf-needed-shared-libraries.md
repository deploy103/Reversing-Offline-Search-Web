---
id: REV-0683
title: "readelf -d로 필요한 공유 라이브러리 목록 확인하기"
slug: "rev-0683-readelf-needed-shared-libraries"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, ldd]
keywords: ["readelf -d", "NEEDED", ".dynamic", "DT_NEEDED", "필요한 공유 라이브러리", "readelf dynamic section"]
aliases: ["readelf -d 사용법", "NEEDED 항목이 뭔지", "이 바이너리가 필요로 하는 so 목록", "ldd 대신 readelf로 라이브러리 확인"]
symptom_keywords: ["ldd 실행이 불안하거나 위험하다고 들었음", "readelf -d 결과에 NEEDED가 여러 줄 나옴", "이 바이너리가 정확히 어떤 so 파일들을 로드하는지 알고 싶음", "RPATH RUNPATH가 뭔지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`readelf -d ./chall`은 ELF의 `.dynamic` 섹션을 읽어 이 바이너리가 실행 시점에 로드해야 하는 공유 라이브러리 목록(`NEEDED` 태그)과 그 탐색 경로 힌트(`RPATH`/`RUNPATH`)를 정적으로(프로그램을 실행하지 않고) 안전하게 보여주며, 이는 `ldd`가 실제로 프로그램을 실행시켜 정보를 얻는 것과 다른, 더 안전한 대안이 된다.

## 언제 검색해야 하나
- 이 바이너리가 정확히 어떤 공유 라이브러리(`.so`)들에 의존하는지 실행하지 않고 확인하고 싶을 때
- `ldd`로 신뢰할 수 없는 바이너리를 검사하는 것이 찜찜할 때(신뢰 안 된 바이너리에 대해 `ldd`를 직접 실행하는 것은 상황에 따라 그 바이너리의 코드가 실제로 로드/실행되게 만들 수 있어 권장되지 않는다)
- `readelf -d` 출력에 `NEEDED`, `RPATH`, `RUNPATH`, `SONAME` 같은 태그가 나오는데 각각 뭘 뜻하는지 모를 때
- 정적 링킹인지 동적 링킹인지, 그리고 동적 링킹이라면 몇 개의 라이브러리를 로드하는지 빠르게 세어보고 싶을 때

## 핵심 개념

### `.dynamic` 섹션 — 동적 링킹에 필요한 모든 메타데이터의 모음
동적 링킹된 ELF는 `.dynamic`이라는 특수 섹션(동시에 `PT_DYNAMIC` 프로그램 헤더로도 노출됨)을 갖는데, 여기에는 동적 로더가 이 바이너리를 실행하기 위해 알아야 할 정보가 태그(tag)-값(value) 쌍으로 나열되어 있다. `.dynsym`, `.dynstr`, `.rela.plt` 같은 다른 섹션들의 위치, GOT/PLT 관련 정보, 그리고 지금 다룰 필요한 라이브러리 목록까지 전부 여기 담긴다. `readelf -d`는 이 태그들을 사람이 읽기 좋은 형태로 번역해서 보여주는 명령이다. 각 태그 이름의 전체 목록과 의미는 REV-0641에서 더 폭넓게 다룬다.

### `DT_NEEDED` — "이 라이브러리가 있어야 실행된다"
`.dynamic` 섹션에서 `Tag`가 `(NEEDED)`로 표시되는 항목이 바로 이 바이너리가 로드 시점에 반드시 필요로 하는 공유 라이브러리 이름이다. 하나의 실행 파일이 여러 라이브러리에 의존할 수 있으므로 `NEEDED` 항목은 여러 줄일 수 있다.

```bash
readelf -d ./chall | grep NEEDED
```

여기 나오는 값은 보통 `libc.so.6`처럼 **파일 이름만**(경로 없이) 나온다. 실제로 그 파일을 어느 디렉터리에서 찾을지는 동적 로더가 별도의 탐색 규칙(REV-0651의 `LD_LIBRARY_PATH` 탐색 순서)에 따라 결정한다.

### `SONAME` — 라이브러리가 스스로를 부르는 이름
공유 라이브러리 자체(`libfoo.so.1.2.3` 같은 실제 파일)의 `.dynamic`을 보면 `Tag`가 `(SONAME)`인 항목이 있다. 이는 "다른 바이너리가 나를 참조할 때 써야 할 논리적 이름"이다. 예를 들어 실제 파일명은 `libc-2.31.so`인데 `SONAME`은 `libc.so.6`으로 설정되어 있을 수 있다. 다른 실행 파일의 `NEEDED` 항목에는 실제 파일명이 아니라 이 `SONAME` 값이 들어간다 — 그래서 배포판이 패치 버전을 올려 실제 파일명이 바뀌어도(`libc-2.31.so` → `libc-2.35.so`), 심볼릭 링크로 `SONAME`(`libc.so.6`)만 최신 파일을 가리키게 해두면 기존 실행 파일들이 재컴파일 없이 새 라이브러리를 그대로 찾아 쓸 수 있다.

### `RPATH`/`RUNPATH` — 라이브러리를 찾을 경로 힌트
일부 바이너리는 표준 경로(`/lib`, `/usr/lib` 등) 외에 특정 디렉터리를 추가로 뒤지도록 `.dynamic`에 경로 힌트를 담고 있다.
- `RPATH`(구식): 링크 시점에 `-rpath` 옵션으로 지정된 경로. `LD_LIBRARY_PATH` 환경변수보다 우선순위가 높다.
- `RUNPATH`(RPATH의 개선판): `LD_LIBRARY_PATH`보다 우선순위가 낮다. 최신 링커는 기본적으로 `RUNPATH`를 사용한다.

CTF 문제에서 특정 디렉터리의 `libc.so.6`을 강제로 쓰게 하려고(원격 서버 환경과 동일한 glibc를 로컬에서 재현하기 위해) `patchelf --set-rpath`로 이 값을 직접 조작하는 경우가 흔하다.

### `readelf -d`와 `ldd`의 차이 — 정적 분석 vs 실제 실행
`ldd`는 내부적으로 동적 로더가 실제로 해당 바이너리를 로드하는 것과 유사한 절차를 거쳐 라이브러리 경로를 알아낸다(구현 방식에 따라 실행 파일을 실제로 실행시키는 경우가 있다). 신뢰할 수 없는 바이너리(예: 출처가 불분명한 CTF 바이너리, 멀웨어 샘플)에 대해 `ldd`를 직접 쓰는 것은 상황에 따라 해당 코드가 실행될 수 있어 안전하지 않다는 경고가 여러 문서에서 반복적으로 언급된다. 반면 `readelf -d`는 파일을 파싱만 할 뿐 실행하지 않으므로, 라이브러리 의존성만 확인하고 싶다면 훨씬 안전한 선택이다. 실제 실행 시 경로가 정확히 어떻게 해석되는지까지 보고 싶다면 `ldd` 대신 격리된 환경(컨테이너, VM)에서 확인하는 것이 안전하다.

## 화면/코드에서 보이는 징후
- `readelf -d ./chall` 출력에 `Tag`, `Type`, `Name/Value` 형태의 표가 나오고 그중 일부 줄이 `(NEEDED)`로 시작함
- `file ./chall`에 `dynamically linked`라고 나오는데 `readelf -d`에 `NEEDED` 항목이 하나도 없다면 static-PIE(REV-0681)일 가능성
- `readelf -d`에 `There is no dynamic section in this file` 메시지가 나오면 완전 정적 링킹(REV-0646)

## 가장 먼저 할 것
`readelf -d ./chall | grep -E "NEEDED|RPATH|RUNPATH|SONAME"`을 실행해 필요한 라이브러리 목록과 경로 힌트를 한 번에 뽑아본다. 아무것도 안 나오면 정적 링킹 여부(`file`, `readelf -h`의 `Type`)부터 재확인한다.

## 단계별 절차
1. `file ./chall`로 동적/정적 링킹 1차 확인
2. `readelf -d ./chall`로 `.dynamic` 섹션 전체 출력
3. 필요한 라이브러리만 추리기:
   ```bash
   readelf -d ./chall | grep NEEDED
   ```
4. 경로 힌트(`RPATH`/`RUNPATH`) 확인해 표준 경로 외에 특정 디렉터리를 우선 탐색하는지 확인
5. 실제로 그 라이브러리들이 시스템 어디에 있는지, 어느 버전이 실제로 매핑될지 확인하고 싶다면(신뢰 가능한 바이너리에 한해) `ldd ./chall` 실행
6. 원격 서버와 동일한 libc를 강제로 쓰게 하고 싶다면 `patchelf --set-interpreter`, `patchelf --set-rpath`로 인터프리터(REV-0649)와 `RUNPATH`를 함께 조정
7. 공유 라이브러리(`.so`) 파일 자체를 분석 중이라면 그 파일의 `SONAME`도 함께 확인해 다른 바이너리가 이 라이브러리를 어떤 이름으로 참조할지 예측(REV-0652 참고)

## 명령어/단축키
```bash
readelf -d ./chall                              # .dynamic 섹션 전체
readelf -d ./chall | grep NEEDED                # 필요한 라이브러리만
readelf -d ./chall | grep -E "RPATH|RUNPATH"    # 경로 힌트만
readelf -d ./libfoo.so | grep SONAME            # 라이브러리 자신의 논리적 이름
ldd ./chall                                     # (신뢰 가능한 바이너리에 한해) 실제 실행 시 로드될 경로까지 확인
patchelf --set-rpath /path/to/libs ./chall      # RUNPATH를 원하는 경로로 변경
```

## 출력 해석
```
$ readelf -d ./chall

Dynamic section at offset 0x2dc8 contains 24 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000c (INIT)               0x1000
 0x000000000000001d (RUNPATH)            Library runpath: [/opt/glibc-2.31/lib]
 0x0000000000000000 (NULL)               0x0
```
- `(NEEDED) Shared library: [libc.so.6]`은 이 실행 파일이 실행되려면 `libc.so.6`이라는 이름의 공유 라이브러리가 반드시 로드되어야 한다는 뜻이다. 대괄호 안이 실제로 찾아야 할 라이브러리의 논리적 이름(`SONAME`)이다.
- `(RUNPATH) Library runpath: [/opt/glibc-2.31/lib]`는 동적 로더가 `libc.so.6`을 찾을 때 표준 경로보다 먼저(또는 함께) `/opt/glibc-2.31/lib` 디렉터리를 뒤지라는 힌트다. CTF 문제에서 특정 glibc 버전을 강제로 쓰게 하려고 `patchelf`로 이 값을 심어두는 경우가 매우 흔하다.
- `(NULL)`은 `.dynamic` 섹션의 끝을 표시하는 종료 마커다.

## 흔한 실수
- `NEEDED` 항목에 나온 이름(`libc.so.6`)을 실제 파일 경로라고 착각하는 것 — 이는 논리적 이름(`SONAME`)일 뿐이고, 실제 파일이 어디 있는지는 탐색 경로 규칙에 따라 별도로 결정된다.
- `RPATH`/`RUNPATH`가 없는 바이너리를 보고 "라이브러리를 못 찾을 것"이라고 오해하는 것 — 대부분의 바이너리는 이 태그가 없어도 표준 시스템 경로(`/lib`, `/usr/lib` 등)에서 정상적으로 라이브러리를 찾는다. 이 태그들은 표준 경로 외의 위치를 추가로 지정하고 싶을 때만 쓰인다.
- 출처가 불분명한 바이너리에 아무 생각 없이 `ldd`를 돌려서 확인하는 것 — 신뢰 안 된 바이너리라면 `readelf -d`(파싱만 함)로 먼저 확인하고, 실제 실행이 필요한 검사는 격리된 환경에서 하는 것이 안전하다.
- static-PIE 바이너리에서 `.dynamic` 섹션이 존재한다는 것만 보고 "동적 링킹이니 `NEEDED`도 있겠지"라고 넘겨짚는 것 — static-PIE는 재배치 처리를 위한 최소한의 `.dynamic`만 가질 뿐 `NEEDED` 항목은 없는 것이 정상이다(REV-0646, REV-0681 참고).
- `RPATH`와 `RUNPATH`를 같은 것으로 여겨 우선순위(`RPATH` > `LD_LIBRARY_PATH` > `RUNPATH`)를 혼동하는 것.

## 막혔을 때 다음 체크
- `.dynamic` 섹션의 다른 태그(`DT_*`) 전체 목록이 궁금하면 → REV-0641 ELF Dynamic Section 태그(DT_*) 빠른 참조
- 실제 라이브러리 탐색 순서(어떤 경로를 어떤 우선순위로 뒤지는지)가 궁금하면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- 동적 로더 자체가 하는 일이 궁금하면 → REV-0649 ELF Interpreter(ld-linux.so)가 하는 일
- 정적 링킹/static-PIE와의 구분이 헷갈리면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법, REV-0681 Position Independent Executable과 Position Independent Code 차이
- 필요한 라이브러리를 찾을 수 없어서 에러가 나는 상황이면 → REV-0706 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때
- 공유 라이브러리 자체를 분석 대상으로 삼는 법이 궁금하면 → REV-0652 공유 라이브러리(.so) 자체를 분석 대상으로 다루기

## 미니 예제
```bash
$ file ./chall
chall: ELF 64-bit LSB pie executable, x86-64, ..., dynamically linked, ...

$ readelf -d ./chall | grep -E "NEEDED|RUNPATH"
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000001d (RUNPATH)            Library runpath: [/home/user/chall/libs]

$ ls /home/user/chall/libs
libc.so.6  ld-linux-x86-64.so.2
```
`readelf -d`만으로 이 바이너리가 `libc.so.6` 하나에 의존하고, 그 라이브러리를 표준 시스템 경로가 아니라 `/home/user/chall/libs`라는 문제 전용 디렉터리에서 먼저 찾도록 `RUNPATH`가 설정되어 있다는 것을 실행 없이 확인했다. 실제로 그 디렉터리를 열어보니 문제 출제자가 원격 서버와 동일한 버전의 `libc.so.6`을 함께 배포해둔 전형적인 CTF pwn 문제 구성임을 알 수 있다.

## 관련 글
- REV-0641 — ELF Dynamic Section 태그(DT_*) 빠른 참조
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0649 — ELF Interpreter(ld-linux.so)가 하는 일
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0681 — Position Independent Executable과 Position Independent Code 차이
- REV-0652 — 공유 라이브러리(.so) 자체를 분석 대상으로 다루기

## 출처/검증
- `.dynamic` 섹션과 `DT_NEEDED`/`DT_SONAME`/`DT_RPATH`/`DT_RUNPATH` 태그의 의미: System V ABI "Dynamic Section" 챕터 및 `ld.so(8)` 매뉴얼 페이지 기준.
- `RPATH`/`RUNPATH`/`LD_LIBRARY_PATH` 우선순위 규칙: `ld.so(8)` 공식 매뉴얼 페이지의 라이브러리 탐색 순서 설명 기준.
- 신뢰할 수 없는 바이너리에 대한 `ldd` 실행 위험성: `ldd(1)` 공식 매뉴얼 페이지의 보안 경고(NOTES 섹션) 기준.
- `patchelf --set-rpath`/`--set-interpreter` 사용법: patchelf 공식 문서 기준 (2026-09-09 검증).
