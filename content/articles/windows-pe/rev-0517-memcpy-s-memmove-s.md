---
id: REV-0517
title: "Windows CRT 메모리 함수 사전: memcpy_s memmove_s"
slug: "rev-0517-memcpy-s-memmove-s"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["memcpy_s", "memmove_s", "memcpy", "memmove", "memset", "버퍼 오버플로", "CRT"]
aliases: ["메모리 복사 함수", "memcpy 인자 순서", "memmove와 memcpy 차이"]
symptom_keywords: ["memcpy_s 인자가 몇 개인지 모르겠다", "memcpy와 memmove 차이를 모르겠다", "겹치는 메모리를 복사할 때 왜 함수가 다른지 모르겠다", "memcpy_s 4번째 인자가 뭔지 모르겠다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`memcpy`/`memcpy_s`/`memmove`/`memmove_s`는 문자열이 아니라 지정한 바이트 수만큼 원시 메모리를 그대로 복사하는 함수이며, 겹치는 영역을 안전하게 처리하는지(`memmove`) 여부와 대상 버퍼 크기를 검증하는지(`_s` 버전) 여부만 다르므로, 리버싱 시에는 세 번째 인자(복사할 바이트 수)와 소스/대상 버퍼 주소만 정확히 짚으면 대부분 분석이 끝난다.

## 언제 검색해야 하나
- 임포트 목록에서 `memcpy`, `memcpy_s`, `memmove`, `memmove_s`, `memset`을 발견해서 어떤 데이터가 어디로 복사되는지 추적해야 할 때
- `memcpy_s`가 인자를 4개 받는 이유(일반 `memcpy`는 3개)를 확인하고 싶을 때
- 스택 버퍼에 고정 크기 데이터가 복사되는 지점을 찾아 오버플로 취약점을 분석할 때
- `memcpy`와 `memmove`를 같은 것으로 착각해서 소스/대상 겹침 여부를 놓쳤을 때

## 핵심 개념
```c
void *memcpy(void *dest, const void *src, size_t count);
errno_t memcpy_s(void *dest, size_t destSize, const void *src, size_t count);
void *memmove(void *dest, const void *src, size_t count);
errno_t memmove_s(void *dest, size_t destSize, const void *src, size_t count);
void *memset(void *dest, int value, size_t count);
```

- `memcpy(dest, src, count)`: `src`부터 `count`바이트를 `dest`로 복사한다. `dest`와 `src`가 겹치면(overlap) 동작이 정의되지 않는다(undefined behavior) — 겹치는 경우 데이터가 깨질 수 있다.
- `memmove(dest, src, count)`: `memcpy`와 기능은 같지만 내부적으로 임시 버퍼나 방향을 조정해 `dest`와 `src`가 겹쳐도 항상 올바르게 동작한다. 같은 버퍼 내에서 앞/뒤로 데이터를 밀 때(예: 배열 중간에 원소 삽입) 사용한다.
- `memcpy_s`/`memmove_s`: 보안 강화 버전으로, 두 번째 인자 `destSize`(대상 버퍼의 실제 크기)를 받아 `count > destSize`이면 복사를 중단하고 `errno_t`(0이 아니면 오류 코드)를 반환한다. 인자 순서가 `dest, destSize, src, count` 순서임에 주의해야 한다(3번째가 아니라 4번째 인자가 복사 바이트 수).
- `memset(dest, value, count)`: `dest`부터 `count`바이트를 모두 `value`(하위 1바이트만 사용)로 채운다. 버퍼 초기화(0으로 채우기)나 스택 클리어에 흔히 쓰인다.

x64 호출 규약 기준으로 `memcpy(dest, src, count)`는 `RCX`=dest, `RDX`=src, `R8`=count 순서로 들어가며, `memcpy_s(dest, destSize, src, count)`는 `RCX`=dest, `RDX`=destSize, `R8`=src, `R9`=count 순서다. 인자 개수가 다르다는 점을 놓치면 `memcpy_s`의 3번째 인자를 `memcpy`처럼 count로 오인해 버퍼 크기(destSize)와 실제 소스 주소(src)를 뒤바꿔 읽는 실수를 하게 된다.

## 화면/코드에서 보이는 징후
- Hex-Rays 디컴파일에서 `memcpy(&local_buf, a1, v3)`처럼 세 인자가 나열되고, 세 번째 인자가 고정 상수(예: `0x100`)이면 고정 크기 버퍼 복사이므로 오버플로 여부를 점검할 대상
- `memcpy_s`가 보이는데 인자가 4개이고, 그중 두 번째와 네 번째가 비슷한 값(둘 다 버퍼 크기 관련)으로 보이는 경우
- 배열 삭제/삽입 로직 근처에서 `memmove`가 나타나는 경우(같은 버퍼 안에서 데이터를 앞뒤로 미는 패턴)
- 함수 시작부에서 `memset`으로 스택 버퍼를 0으로 초기화하는 코드(컴파일러가 자동 삽입하기도 함, `/RTC` 디버그 빌드에서 흔함)

## 가장 먼저 할 것
1. 함수 이름이 `memcpy`인지 `memcpy_s`인지부터 확인해서 인자가 3개인지 4개인지 헷갈리지 않는다.
2. 세 번째(또는 `_s` 버전의 네 번째) 인자인 "복사할 바이트 수"가 고정 상수인지 변수인지 확인한다. 변수라면 그 값이 사용자 입력에서 온 것인지 추적해 오버플로 가능성을 판단한다.
3. `dest` 버퍼가 스택 지역 변수인지 힙 버퍼인지 IDA의 스택 뷰(`Ctrl+K` 또는 함수 프레임 확인)로 확인한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `memcpy`/`memcpy_s`/`memmove` 를 찾아 `X`로 교차 참조를 나열한다.
- `F5`로 디컴파일해 세 번째(또는 네 번째) 인자가 상수인지, 변수라면 어디서 오는지(예: 사용자 입력 길이) 상위로 거슬러 올라간다.

**2) 동적 분석(x64dbg)**
- `bp memcpy_s`로 브레이크포인트를 건다.
- 진입 직후 `RCX`(dest), `RDX`(destSize), `R8`(src), `R9`(count)를 확인한다.
- `R8`(src)을 Follow in Dump 해서 실제로 복사되는 원본 데이터를 확인하고, `count`(`R9`)가 `destSize`(`RDX`)보다 크면 오버플로가 발생할 조건임을 바로 알 수 있다.

## 명령어/단축키
- x64dbg: `bp memcpy`, `bp memcpy_s`, `bp memmove`
- x64dbg 스택/레지스터 창에서 `RCX`/`RDX`/`R8`/`R9` 직접 확인, 우클릭 → "Follow in Dump"
- IDA: `X`(교차 참조), `F5`(디컴파일), `Ctrl+K`(스택 프레임 뷰)

## 출력 해석
- `memcpy`/`memmove`의 반환값은 `dest` 포인터 그대로(성공/실패 개념 없음).
- `memcpy_s`/`memmove_s`의 반환값(`errno_t`)이 `0`이면 성공, `0`이 아니면 오류(예: `ERANGE`는 count가 destSize를 초과한 경우)다. 반환값을 검사하지 않는 코드가 있다면 오류가 나도 그냥 넘어가는 취약한 경로일 수 있다.
- `count`(복사 바이트 수)가 `destSize`보다 큰 상태로 `memcpy_s`가 호출되면 함수 내부에서 대상 버퍼를 0으로 채우고 `errno_t`를 오류로 반환하는 동작을 하므로, 크래시 대신 "조용한 실패"가 나는 경우가 있다는 점도 함께 봐야 한다.

## 흔한 실수
- `memcpy`와 `strcpy`를 혼동해서 `memcpy`가 NUL을 만나면 멈춘다고 착각하는 것. `memcpy`는 지정한 바이트 수만큼 무조건 복사하며 NUL과 무관하다.
- `memcpy_s`의 인자 순서를 `dest, src, count`(일반 `memcpy` 순서)로 착각해서 2번째 인자(destSize)를 src로 오인하는 것.
- 겹치는 버퍼에 `memcpy`가 쓰인 코드를 보고 "정상 동작한다"고 가정하는 것. 실제로는 undefined behavior이므로 겹치는 경우라면 원래 `memmove`를 써야 했던 버그일 수 있다.
- `memset`으로 민감한 데이터(비밀번호 등)를 지우는 코드를 컴파일러가 최적화로 제거해버려 실제로는 메모리에 값이 남아있는 경우를 놓치는 것(`SecureZeroMemory` 같은 최적화 방지 함수와 구분해야 함).

## 막혔을 때 다음 체크
- 문자열이 아닌 순수 바이트 복사가 아니라 와이드 문자열 복사라면 → REV-0516(wcscpy wcscat 계열)을 본다.
- ANSI 문자열 복사 함수의 안전 버전 규약이 궁금하면 → REV-0515(strcpy_s sprintf_s)를 본다.
- 복사된 데이터가 힙 메모리와 관련 있다면 → REV-0510(HeapAlloc HeapFree)를 함께 본다.

## 미니 예제
x64dbg에서 `bp memcpy_s` 후 실행하니 다음처럼 멈췄다.

```text
RCX = 0x000000000021FA20   (dest, 스택 버퍼)
RDX = 0x0000000000000010   (destSize = 16)
R8  = 0x00000221A3B05000   (src)
R9  = 0x0000000000000010   (count = 16)
```

`count`(16)가 `destSize`(16)와 정확히 같으므로 정상적인 경계 내 복사이다. `R8`을 Follow in Dump 하면 실제 복사되는 16바이트(예: 사용자 입력 문자열)를 확인할 수 있다. 만약 `R9`가 `0x20`(32)처럼 `destSize`보다 크게 나온다면 오버플로 조건이 성립하는 것이므로, 취약점 분석 관점에서 이 호출을 중점적으로 파고들어야 한다.

## 관련 글
- REV-0516 — Windows CRT 문자열 함수 사전: wcscpy wcscat 계열(와이드 문자)
- REV-0515 — Windows CRT 문자열 함수 사전: strcpy_s sprintf_s
- REV-0510 — WinAPI 메모리 함수 사전: HeapAlloc HeapFree

## 출처/검증
- `memcpy`/`memcpy_s`/`memmove`/`memmove_s`/`memset`의 함수 시그니처, 인자 순서, `errno_t` 반환 동작은 Microsoft C 런타임 라이브러리(CRT) 공식 문서 기준이다.
- `memcpy`가 겹치는 메모리에서 undefined behavior라는 점과 `memmove`가 이를 안전하게 처리한다는 점은 C 표준 라이브러리 일반 사양 기준이다.
- 위 미니 예제의 주소와 값은 설명용으로 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
