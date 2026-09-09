---
id: REV-0660
title: "Pwndbg search로 메모리에서 패턴 찾기"
slug: "rev-0660-pwndbg-search-memory-pattern"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["pwndbg search", "메모리 패턴 검색", "search -t string", "search -p pointer", "힙 주소 찾기"]
aliases: ["pwndbg search 명령어", "gdb 메모리에서 문자열 찾기", "search writable", "search 옵션"]
symptom_keywords: ["메모리 어디에 이 값이 있는지 모르겠음", "이 포인터가 가리키는 값을 다시 참조하는 곳을 찾고 싶음", "flag 문자열이 메모리 어디 있는지 찾고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Pwndbg의 `search` 명령은 프로세스의 전체(또는 지정한) 메모리 영역을 스캔해서 특정 문자열/바이트열/정수/포인터 값이 있는 모든 주소를 찾아주는 기능으로, "이 값이 메모리 어디에 있는지", "이 주소를 가리키는 포인터가 어디에 있는지"를 손으로 `x/` 덤프를 뒤지지 않고 바로 알아낼 때 쓴다.

## 언제 검색해야 하나
- 입력한 문자열이나 알고 있는 flag 조각이 메모리 어딘가에 그대로 남아있는지 확인하고 싶을 때
- 특정 힙 청크 주소나 함수 주소를 "누가 가리키고 있는지"(포인터 레퍼런스, 일종의 메모리 내 xref) 찾고 싶을 때
- UAF/더블프리 문제에서 해제된 청크의 값을 덮어쓴 뒤, 그 값이 실제로 다른 곳에서도 참조되는지 확인하고 싶을 때
- `checksec`으로 canary 값을 스택에서 직접 찾아보거나, libc 주소가 유출된 후 그 값이 스택/힙 어디에 저장돼 있는지 찾고 싶을 때

## 핵심 개념

### search가 하는 일
`search`는 지정한 값을 바이트 패턴으로 변환한 뒤, 프로세스의 매핑된 메모리 영역(`vmmap`에 나오는 범위들)을 순회하며 그 패턴이 나타나는 모든 주소를 출력한다. GDB 기본 명령에는 이런 전체 메모리 스캔 기능이 없어서(`find` 명령이 있긴 하지만 범위를 직접 지정해야 하고 출력이 덜 정리되어 있다), Pwndbg의 `search`가 사실상 "메모리용 grep" 역할을 한다.

### 타입 지정 — 검색 패턴을 어떻게 해석할지
기본적으로 `search`는 인자를 문자열로 취급하려 시도하지만, `-t`(`--type`) 옵션으로 명시적으로 지정할 수 있다:
- `string` — 널 종료 문자열로 검색 (기본값에 가까움)
- `byte`, `word`, `dword`, `qword` — 각각 1/2/4/8바이트 정수로 검색
- `pointer` — 현재 아키텍처의 포인터 크기(x64면 8바이트)로 취급해서 검색. "이 주소를 참조하는 포인터가 어디 있는지" 찾을 때 핵심.
- `bytes` — 직접 지정한 raw 바이트 시퀀스

### 자주 쓰는 필터 옵션
- `-s "문자열"` — 문자열 검색을 명시적으로 표시
- `-x` — 값을 16진수로 해석
- `-w` / `--writable` — 쓰기 가능한 페이지(스택, 힙, `.data`/`.bss`)로만 범위를 좁혀서 스캔 속도를 올리고 노이즈를 줄인다
- `-n <개수>` — 결과 개수 제한

## 화면/코드에서 보이는 징후
소스 코드가 아니라 GDB+Pwndbg 세션 안에서 필요한 상황이다. "이 값이 어디서 왔는지", "이 주소를 누가 들고 있는지" 궁금해지는 시점 — 대표적으로 힙 익스플로잇 중 fake chunk를 만들 위치를 찾거나, 리크한 libc 주소를 스택에서 재확인할 때 이 명령이 필요하다.

## 가장 먼저 할 것
찾고 싶은 값이 정확히 무엇인지부터 정한다(문자열인지, 정수/주소인지). 문자열이면 그대로:
```
pwndbg> search "flag{"
```
주소/포인터를 찾는 것이라면 타입을 명시한다:
```
pwndbg> search -t pointer 0x555555559260
```

## 단계별 절차

**1) 문자열 검색**
```
pwndbg> search "s3cr3t_p4ss"
```

**2) 쓰기 가능한 영역으로만 좁혀서 검색 (스택/힙/bss 위주)**
```
pwndbg> search -w "s3cr3t_p4ss"
```

**3) 정수/주소 값 검색**
```
pwndbg> search -t dword 0x1337
pwndbg> search -t qword 0x00007ffff7dd0000
```

**4) 포인터 검색 — 이 주소를 가리키는 곳 찾기**
힙 청크 `0x55d4a1b2c260`을 다른 어떤 포인터가 가리키고 있는지 알고 싶을 때:
```
pwndbg> search -t pointer 0x55d4a1b2c260
```

**5) raw 바이트 시퀀스 검색**
```
pwndbg> search -t bytes 4142434445
```

**6) 찾은 주소를 telescope/xinfo로 더 파보기**
`search`로 후보 주소들이 나오면, 각 주소가 어떤 세그먼트에 속하는지, 주변에 뭐가 있는지 이어서 확인한다:
```
pwndbg> xinfo <주소>
pwndbg> telescope <주소>
```

## 명령어/단축키
```
pwndbg> search "문자열"
pwndbg> search -w "문자열"                 # 쓰기 가능 영역만
pwndbg> search -t dword 0x1337
pwndbg> search -t qword 0x7ffff7dd0000
pwndbg> search -t pointer <주소>            # 이 주소를 가리키는 포인터 찾기
pwndbg> search -t bytes 4142434445          # raw 바이트열
pwndbg> search -n 5 "flag"                  # 결과 5개로 제한
pwndbg> xinfo <주소>                        # 주소가 속한 매핑 정보
pwndbg> telescope <주소>                    # 주소 이후 메모리 연쇄 참조 보기
```

## 출력 해석
```
pwndbg> search "s3cr3t_p4ss"
Searching for value: 's3cr3t_p4ss'
libc-2.31.so     0x7ffff7f9e8b8 's3cr3t_p4ss'
[stack]          0x7ffffffde420 's3cr3t_p4ss'
```
- 첫 번째 결과 `libc-2.31.so 0x7ffff7f9e8b8`: 이 문자열이 바이너리 자체가 아니라 libc 영역에도 있다면, 우연히 겹치는 바이트 패턴이거나 libc 내부 문자열일 수 있으니 문맥을 다시 확인해야 한다.
- 두 번째 결과 `[stack] 0x7ffffffde420`: 스택에 이 문자열이 그대로 있다는 뜻 — 방금 `scanf`/`gets`로 입력받은 값이 저장된 지역 버퍼일 가능성이 높다. `x/s 0x7ffffffde420`로 주변까지 확인하면 어떤 변수인지 유추할 수 있다.
- 각 줄 맨 앞의 `libc-2.31.so`, `[stack]`은 Pwndbg가 `vmmap` 정보를 이용해 그 주소가 어느 매핑에 속하는지 자동으로 붙여주는 라벨이다 — 바이너리 자체(`chall`), 힙(`[heap]`), 공유 라이브러리 이름 등으로 나온다.

```
pwndbg> search -t pointer 0x55d4a1b2c260
[heap]           0x55d4a1b2c4a0 —▸ 0x55d4a1b2c260 ◂— ...
```
`0x55d4a1b2c4a0` 위치의 8바이트 값이 정확히 `0x55d4a1b2c260`이라는 뜻 — 즉 힙 안의 다른 청크(또는 tcache 리스트)가 이 청크를 `fd` 포인터로 가리키고 있다는 걸 알 수 있다.

## 흔한 실수
- 문자열 검색 시 널 종료를 기대했는데 실제로는 부분 문자열이 다른 문자열 중간에 우연히 포함되어 너무 많은 결과가 나오는 것 — `-n`으로 개수를 제한하거나 더 긴/고유한 부분 문자열로 검색 범위를 좁힌다.
- 정수 검색 시 타입(`dword`/`qword`)을 지정하지 않아서 원하는 크기로 안 맞춰져 결과가 하나도 안 나오는 것 — 64비트 주소는 반드시 `-t qword`나 `-t pointer`로 검색해야 한다.
- 전체 메모리를 매번 검색해서 느린 것 — 스택/힙만 관심 있다면 `-w`로 쓰기 가능 영역만 검색해 속도를 크게 줄인다.
- 검색 결과 주소를 절대 주소로 기억해뒀다가 다음 실행(ASLR로 베이스가 바뀜)에도 그대로 쓰는 것 — PIE/ASLR 환경(REV-0103, REV-0104)에서는 매 실행마다 베이스가 바뀌므로, 절대 주소가 아니라 "베이스로부터의 오프셋"으로 기억해야 한다.

## 막혔을 때 다음 체크
- 찾은 청크 주소를 힙 전체 구조 관점에서 다시 확인하고 싶다면 → REV-0659 Pwndbg에서 힙 상태를 시각화해서 보는 법
- ASLR 때문에 절대 주소가 매번 바뀌는 이유가 궁금하다면 → REV-0104 ASLR 때문에 실행할 때 주소가 바뀌는 이유
- Pwndbg의 다른 메모리 확인 명령(`telescope`, `vmmap`)이 궁금하다면 → REV-0193 Pwndbg context telescope vmmap
- 기본 GDB `x` 명령과 무엇이 다른지 궁금하다면 → REV-0189 GDB x 명령으로 메모리 보기

## 미니 예제
```
pwndbg> search -w "REAL_ANSWER"
[stack]          0x7ffffffde3f0 'REAL_ANSWER_1234'
pwndbg> x/s 0x7ffffffde3f0
0x7ffffffde3f0: "REAL_ANSWER_1234"
```
스택 어딘가에 있는 정답 후보 문자열의 정확한 위치를 `search`로 먼저 찾고, `x/s`로 전체 내용을 재확인하는 전형적인 조합이다.

## 관련 글
- REV-0659 — Pwndbg에서 힙 상태를 시각화해서 보는 법
- REV-0193 — Pwndbg context telescope vmmap
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0286 — Pwndbg 명령어 치트시트

## 출처/검증
- `search` 명령의 옵션(`-t`, `-w`, `-s`, `-n`)과 타입(`string`, `byte`/`word`/`dword`/`qword`, `pointer`, `bytes`): Pwndbg 공식 GitHub 저장소 명령 문서 기준 (2026-09-08 검증).
