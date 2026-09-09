---
id: REV-0319
title: "리버싱과 Pwnable이 섞인 문제 구분하는 법"
slug: "rev-0319-reversing-vs-pwnable"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, pwntools, checksec]
keywords: ["리버싱 pwn 구분", "reversing vs pwnable", "하이브리드 문제", "checksec 리버싱", "백도어 함수", "buffer overflow 리버싱"]
aliases: ["리버싱인데 pwn 같음", "이거 리버싱 맞나 pwn 문제인가", "reversing pwnable hybrid", "리버싱 pwn 섞인 문제"]
symptom_keywords: ["nc로 접속하라는데 리버싱 문제라고 나옴", "libc.so가 같이 첨부됨", "checksec 결과가 왜 중요한지 모르겠음", "win 함수가 있는데 아무도 안 부름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
"리버싱" 카테고리로 분류된 문제라도 첨부파일에 `libc.so`가 딸려오거나, 원격 접속(`nc host port`)으로 상호작용하거나, 입력 함수와 버퍼 크기가 어긋나 있다면 실제로는 메모리 손상을 이용해 셸을 따야 하는 pwnable 문제이거나 두 요소가 섞인 하이브리드 문제이므로, 처음부터 "입력값을 맞혀서 flag를 얻는 문제"라고 단정하지 말고 목표 자체를 다시 확인해야 한다.

## 언제 검색해야 하나
- 문제 카테고리가 "reversing"인데 첨부파일에 `libc.so.6`, `ld-linux-x86-64.so.2` 같은 파일이 함께 들어있을 때
- 문제 설명에 `nc <host> <port>` 접속 방법이 나와서 로컬 실행이 아니라 원격 서버와 상호작용해야 할 때
- IDA/Ghidra Functions 창에 `win`, `get_shell`, `backdoor` 같은 이름의 함수가 있는데 어디서도 호출되지 않을 때
- `checksec` 결과(Canary/NX/PIE/RELRO)가 왜 중요한지 감이 안 잡히는데 문제 설명에서 그 값을 언급할 때
- 입력 함수(`gets`, `scanf("%s", buf)`, `read(0, buf, big_size)`)가 있는데 버퍼 크기와 읽는 크기가 맞지 않아 보일 때

## 핵심 개념

### 목표가 다르다
순수 리버싱 문제의 목표는 "프로그램이 내부적으로 기대하는 올바른 입력값을 복원하는 것"이다. 입력을 넣으면 프로그램이 `Correct!`를 출력하거나 flag를 그대로 뱉는다. 반면 pwnable 문제의 목표는 "프로그램의 메모리 손상 취약점을 이용해 임의 코드 실행 또는 셸 획득"이다. 정답 입력값이라는 개념 자체가 없고, 대신 스택/힙을 원하는 값으로 덮어써서 제어 흐름을 바꾼다. 두 목표는 접근 방식이 완전히 다르므로, 문제를 열자마자 어느 쪽인지 먼저 판단해야 헛수고를 줄인다.

### 하이브리드 문제가 흔한 이유
많은 대회가 "리버싱으로 로직을 이해한 뒤, 그 로직 안의 취약점을 pwn 기법으로 공격"하는 구성을 낸다. 예를 들어 커스텀 인코딩 로직을 리버싱으로 먼저 파악해야 어느 함수에 오버플로우가 있는지 알 수 있는 식이다. 이런 문제는 리버싱 위키의 정적 분석 절차(REV-0006, REV-0008)로 검증 로직까지는 도달할 수 있지만, 그 다음 단계(익스플로잇 작성)는 pwnable 영역이라 이 위키의 범위를 벗어난다는 것을 인지하고 있어야 한다.

### 징후로 미리 구분하기
아래 정보들이 하나라도 있으면 pwn 요소를 의심한다.
- `libc.so`, `ld.so`가 첨부됨 — 정확한 libc 버전에 맞춰 오프셋을 계산해야 하는 pwn 문제의 전형적 패턴
- 원격 서버 접속(`nc`) — 프로세스가 계속 살아있어야 하는 pwn 문제 구조
- `checksec` 결과를 문제 설명이나 Dockerfile에서 언급 — Canary/NX/PIE는 pwn 익스플로잇 난이도를 결정하는 값
- 버퍼 크기보다 큰 입력을 받는 함수 호출 — 스택 오버플로우 가능성
- 아무도 호출하지 않는 `win`류 함수 — ROP나 오버플로우로 반환 주소를 그 함수로 덮어쓰라는 신호

## 화면/코드에서 보이는 징후
- 첨부파일 목록에 실행 파일 외에 `libc.so.6`, `ld-linux.so.2`, `Dockerfile`이 함께 있음
- 문제 설명에 "쉘을 획득하세요", "flag.txt를 읽으세요" 같은 문구(정답 문자열을 맞히라는 문구가 아님)
- IDA Functions 창에 `system`, `execve`, `/bin/sh` 문자열이 있으나 정상적인 흐름에서는 호출되지 않음
- `gets(buf)`처럼 크기 제한이 없는 입력 함수 호출
- `checksec ./chall` 결과에 `Canary: No`, `PIE: No` 등 보호 기법이 꺼져 있어 공격이 쉬운 상태

## 가장 먼저 할 것
`checksec ./chall`을 실행해 보호 기법 상태를 확인하고, 첨부파일 목록에 `libc.so`가 있는지, 문제 설명에 원격 접속 주소가 있는지부터 확인한다. 이 셋 중 하나라도 해당되면 순수 리버싱이 아니라 pwn 요소가 섞였다고 가정하고 접근 계획을 다시 세운다.

## 단계별 절차
1. 첨부파일 전체 목록 확인 — 실행 파일 외에 `libc.so`, `ld.so`, `Dockerfile`이 있는지 본다
2. `checksec ./chall` 실행 — Canary/NX/PIE/RELRO 값을 기록한다(REV-0096, REV-0105)
3. 문제 설명 문장에서 목표 동사를 확인 — "복원하라/맞혀라"(리버싱) vs "셸을 따라/실행하라"(pwn)
4. IDA/Ghidra로 입력 함수(`gets`, `scanf`, `read`)를 찾아 버퍼 크기와 읽는 크기를 비교한다
5. Functions 창에서 `win`, `system`, `/bin/sh` 등 의심스러운 이름이 있는데 정상 흐름에서 호출 안 되는 함수가 있는지 확인한다
6. pwn 징후가 없으면 REV-0018 루틴대로 순수 리버싱 절차를 계속 진행한다
7. pwn 징후가 명확하면(오버플로우 + libc 첨부 + win 함수) 이 문제는 pwntools 기반 익스플로잇 작성이 필요한 영역임을 인지하고, 먼저 리버싱으로 검증 로직/취약점 위치까지만 명확히 정리한 뒤 별도의 pwn 학습 자료(REV-0300에서 준비한 pwntools 등)로 넘어간다

## 명령어/단축키
```bash
file ./chall
checksec --file=./chall
ls -la  # libc.so, Dockerfile 첨부 여부 확인
nc <host> <port>  # 원격 상호작용 방식 확인
```
IDA/Ghidra: Functions 창(Ctrl+P)에서 `system`, `win`, `execve` 검색 → X로 xref 확인해 아무도 호출 안 하는지 확인.

## 출력 해석
- `checksec` 결과에서 `Canary: No`, `NX: disabled`가 동시에 나오면 스택 기반 셸코드 실행이 가능한 고전적 pwn 세팅일 확률이 높다.
- `Canary: Yes`, `PIE: Yes`, `RELRO: Full`이 전부 켜져 있으면 pwn 난이도가 높아지므로, 문제가 실제로는 순수 리버싱(정답 계산)일 가능성도 같이 열어둔다 — 보호기법이 다 켜져 있다고 무조건 pwn은 아니다.
- `win` 함수가 있어도 xref가 하나라도 있으면(예: 디버그 메뉴 옵션) 백도어가 아니라 정상 기능일 수 있으니 xref 유무를 반드시 확인한다.

## 흔한 실수
- 첨부파일에 `libc.so`가 있는데도 이를 무시하고 로컬 libc로만 검증하다가 오프셋이 안 맞아 헤매는 것.
- `win` 함수를 발견하자마자 "이건 답이 아니다"라고 무시하는 것 — 오히려 그 함수가 pwn 익스플로잇의 최종 목표일 수 있다.
- 원격 접속(`nc`) 문제인데 로컬에 있는 바이너리만 계속 실행하며 정적 값으로 판단하려는 것 — 서버 환경이 다를 수 있다(REV-0711).
- 보호기법이 다 꺼져 있다고 무조건 pwn이라 단정하고 리버싱 로직 분석 자체를 건너뛰는 것 — 하이브리드 문제는 로직 이해가 선행되어야 취약점 위치도 보인다.

## 막혔을 때 다음 체크
- checksec 결과 자체를 어떻게 읽는지 모르겠다 → REV-0096 checksec 결과 읽는 법, REV-0105 Canary NX PIE RELRO 한 번에 이해
- 검증 로직까지는 찾았는데 그 다음이 pwn 영역인지 판단이 안 선다 → REV-0006 Flag 검증 함수 찾는 가장 흔한 경로
- crypto 요소까지 섞여 있어 더 헷갈린다 → REV-0320 리버싱과 Crypto가 섞인 문제 구분하는 법
- 전체적으로 시간이 너무 오래 걸린다 → REV-0015 막혔을 때 5분 체크리스트

## 미니 예제
```c
void vuln() {
    char buf[64];
    puts("Enter your answer:");
    gets(buf);  // 크기 제한 없음 -> 오버플로우 가능
    if (strcmp(buf, "correct_answer") == 0)
        puts("Correct!");
}

void win() {  // 어디서도 호출되지 않음
    system("/bin/sh");
}
```
이 예시는 겉보기에는 "정답 문자열을 맞히는" 리버싱 문제처럼 보이지만, `gets`가 크기 제한 없이 입력을 받고 `win` 함수가 존재하므로 실제로는 `buf`를 오버플로우시켜 반환 주소를 `win`으로 덮어쓰는 pwn 문제다. `strcmp` 비교값을 아무리 복원해도 정상적인 방법으로는 flag를 얻을 수 없다는 것이 핵심 징후다.

## 관련 글
- REV-0018 — 대회장에서 리버싱 문제 하나를 끝까지 추적하는 실전 루틴
- REV-0096 — checksec 결과 읽는 법
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0006 — Flag 검증 함수 찾는 가장 흔한 경로
- REV-0320 — 리버싱과 Crypto가 섞인 문제 구분하는 법
- REV-0711 — 서버 환경 glibc와 로컬 glibc가 달라 분석이 안 맞을 때

## 출처/검증
- checksec 출력 항목(Canary/NX/PIE/RELRO)과 그 의미: `pwntools` `checksec` 문서 및 본 위키 REV-0096/REV-0105 기준.
- 스택 오버플로우 후 반환 주소를 백도어 함수로 덮어쓰는 공격 패턴은 일반적인 CTF pwnable 문제 구성 방식으로, CTF 라이트업에서 반복적으로 확인되는 패턴 (2026-09-09 검증).
