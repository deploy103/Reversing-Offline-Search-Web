---
id: REV-0296
title: "ltrace strace 치트시트"
slug: "rev-0296-ltrace-strace-cheatsheet"
category: "tools"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["ltrace", "strace"]
keywords: ["ltrace strace 치트시트", "ltrace strace 비교", "동적 분석 명령어 정리"]
aliases: ["ltrace strace 명령어 모음", "라이브러리 시스템콜 추적 치트시트"]
symptom_keywords: ["ltrace strace 어떤 걸 써야할지 모름", "ltrace strace 옵션을 자꾸 까먹음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ltrace`는 라이브러리 함수 호출(`strcmp`, `printf` 등)을, `strace`는 커널 시스템 콜(`open`, `read`, `execve` 등)을 실시간으로 보여주며, 둘 다 코드를 읽거나 브레이크포인트를 걸지 않고 프로그램 실행을 관찰하는 가장 빠른 첫 삽질이다.

## 언제 검색해야 하나
- 옵션 철자가 기억 안 나서 매번 `man`을 찾아보기 귀찮을 때
- 두 도구 중 어느 것을 먼저 돌려야 할지 헷갈릴 때

각 도구의 동작 원리, ptrace 기반 안티디버깅과의 상호작용, 출력 해석은 이 문서에서 반복하지 않는다. 아래 원본 문서를 참고할 것.
- [REV-0111 ltrace로 라이브러리 호출 빠르게 보기](../linux-elf/rev-0111-ltrace-basics.md)
- [REV-0112 strace로 시스템 콜에서 힌트 찾기](../linux-elf/rev-0112-strace-basics.md)

## 핵심 개념
`ltrace`/`strace` 둘 다 `ptrace(2)` 기반으로 대상 프로세스를 관찰만 할 뿐 코드를 고치지 않는다 — 그래서 "일단 뭔지 몰라도 실행부터 시켜보는" 첫 삽질용으로 가장 부담 없다.

## 가장 먼저 할 것
아래 "어느 것을 쓸까" 표에서 지금 궁금한 것에 맞는 도구를 고른다. 확신이 없으면 `ltrace`부터 돌려본다(정적 링킹이면 예외, 아래 참고).

## 단계별 절차 / 명령어/단축키
아래 도구별 절 참고. 순서를 모르겠다면 "조합 예시"부터 그대로 따라 하면 된다.

## 흔한 실수
정적 링킹 바이너리에 `ltrace`를 돌리고 "아무것도 안 나온다"며 도구가 고장났다고 오해하는 것 — 아래 "정적 링킹 바이너리라면" 절 참고.

## 어느 것을 쓸까
| 궁금한 것 | 도구 |
|---|---|
| `strcmp`에 어떤 문자열이 들어가는지, 정답 문자열 노출 | `ltrace` |
| 어떤 파일을 여는지(`flag.txt` 등), 네트워크/프로세스 동작 | `strace` |
| 정적 링킹 바이너리 | `strace`만 유효 (`ltrace`는 PLT가 없어 거의 무용지물) |
| `ptrace` 기반 안티디버깅 의심 | `strace -e trace=ptrace` |

## ltrace — 라이브러리 호출 (REV-0111)
```bash
ltrace ./chall                       # 기본 실행
ltrace -e 'strcmp+scanf' ./chall     # 특정 함수만 필터링
ltrace -s 200 ./chall                # 문자열 인자 길이 늘리기(잘림 방지)
ltrace -o trace.log ./chall          # 파일로 저장
ltrace -c ./chall                    # 호출 횟수/시간 요약
ltrace -f ./chall                    # 자식 프로세스까지 추적
```

## strace — 시스템 콜 (REV-0112)
```bash
strace ./chall                                  # 기본 실행
strace -e trace=open,openat,read,write ./chall   # 파일 입출력만 필터링
strace -e trace=execve,fork,clone,ptrace ./chall # 프로세스/안티디버깅 관련만
strace -f ./chall                                # 자식 프로세스까지 추적(fork 대응)
strace -tt ./chall                               # 타임스탬프 포함
strace -o trace.log -c ./chall                   # 저장 + 호출 요약 통계
```

## 설치 (둘 다 배포판 패키지로 충분)
```bash
sudo apt install ltrace strace
```
오프라인 대회 전에는 반드시 온라인 상태에서 미리 설치해 두어야 한다. 두 도구 모두 `ptrace(2)` 시스템 콜 기반으로 동작하므로, 컨테이너 환경에서는 `--cap-add=SYS_PTRACE` 같은 권한이 없으면 아예 동작하지 않을 수 있다는 점도 미리 확인해 둘 것.

## 막혔을 때 다음 체크
동작 원리나 ptrace 안티디버깅과의 상호작용이 더 궁금하면 REV-0111/REV-0112 원본 문서를 참고한다.

## 미니 예제 — 조합 예시(둘 다 빠르게 돌려보기)
```bash
ltrace -s 200 ./chall < <(echo test) 2>&1 | tail -20
strace -f -e trace=openat,read,write ./chall < <(echo test) 2>&1 | tail -20
```
`ltrace`로 비교 함수 인자에 정답 후보가 그대로 보이는지 먼저 확인하고, 안 보이면(값이 암호화/연산되어 있으면) `strace`로 파일 접근이나 프로세스 생성 패턴을 훑는 순서가 실전에서 자주 쓰인다.

## 정적 링킹 바이너리라면
`ltrace`는 PLT 후킹 방식이라 정적 링킹된 바이너리에는 사실상 무용지물이다. `file ./chall` 결과에 `statically linked`가 보이면 처음부터 `ltrace`는 건너뛰고 `strace`만으로 시스템 콜 레벨 분석을 시작하는 편이 시간을 아낀다.

## 관련 글
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0294 — readelf objdump nm strings 치트시트

## 출처/검증
- 모든 명령/옵션은 이 저장소의 REV-0111, REV-0112 원본 문서(각 도구 공식 man page 기준으로 이미 검증됨)에서 그대로 발췌한 것이며, 이 문서 자체에서 새로 검증한 내용은 없다.
