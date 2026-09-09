---
id: REV-1039
title: "[Write-up] Happy New Year!"
slug: "rev-1039-writeup-happy-new-year"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["dreamhack Happy New Year", "드림핵 Happy New Year", "Happy New Year 리버싱"]
aliases: ["Happy New Year 풀이", "Happy New Year 못풀겠음"]
symptom_keywords: ["드림핵 Happy New Year 어떻게 풀어야 할지 모르겠음", "Happy New Year 실행해도 아무 반응 없음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
"Happy New Year!"(Bronze 4)의 공개 write-up은 찾지 못했다. 이름이 새해(연도가 바뀌는 시점)를 직접 가리키는 만큼, 시스템의 현재 날짜/시간을 읽어 특정 시점(1월 1일 등)과 비교하는 조건으로 플래그를 내보내는 문제일 가능성을 열어두고, 실제 시간을 기다리지 않고 그 조건을 역으로 찾아내는 전략으로 접근하는 것이 합리적이다.

## 언제 검색해야 하나
- "Happy New Year!"를 실행했는데 아무 반응이 없거나 "아직 새해가 아닙니다" 같은 문구만 나오고 더 진행이 안 될 때
- 문제 이름이 날짜와 관련된 것 같은데 바이너리 안에서 날짜 API를 어디서 찾아야 할지 감이 안 잡힐 때
- 실제로 1월 1일이 될 때까지 기다려야 하는 문제인지, 아니면 그 조건을 우회할 수 있는 문제인지 판단이 필요할 때

## 핵심 개념
검색 결과 "Happy New Year"라는 제목의 드림핵 리버싱 문제를 직접 다루는 write-up은 확인되지 않았다. 다만 이 이름은 명확하게 "새해가 되는 시점"이라는 시간적 조건을 암시하므로, CTF에서 흔히 쓰이는 "시간 기반 조건 검사" 패턴을 참고해 접근하는 것이 타당하다.

시간을 소재로 한 리버싱 문제는 보통 다음 중 하나의 형태를 갖는다.

- Windows API `GetLocalTime`/`GetSystemTime`을 호출해 연/월/일을 읽고, 그 값이 원하는 날짜(예: 1월 1일)와 일치할 때만 플래그 관련 함수를 호출한다. 이 경우 실제로 컴퓨터의 시스템 날짜를 새해로 바꾸거나, 디버거에서 API의 반환값을 조작해 조건을 강제로 만족시키는 방법이 가장 빠르다.
- `time(NULL)`로 얻은 유닉스 타임스탬프를 `srand()`의 시드로 사용해 그 시점에만 나올 수 있는 특정 난수를 요구하는 형태일 수도 있다. 이 경우는 시드 자체를 역산하는 문제이지 날짜를 실제로 기다리는 문제가 아니다(REV-0894 참고).
- 단순히 "새해 복 많이 받으세요" 같은 문구를 출력하는 장식적인 이름일 뿐, 실제 검증 로직은 시간과 무관한 일반적인 문자열 비교일 수도 있다. Bronze 4는 최하위 난이도이므로 이 가능성도 배제할 수 없다.

세 가지 가능성 모두 검증되지 않았으므로, 실제 분석 시에는 바이너리에서 시간 관련 API의 import 여부를 먼저 확인해 어떤 경우에 해당하는지 판단해야 한다.

## 화면/코드에서 보이는 징후
- Import 목록에 `GetLocalTime`, `GetSystemTime`, `time`, `srand`, `rand` 등이 있는지
- 실행 시 날짜/시간과 관련된 안내 문구(예: "아직 1월 1일이 아닙니다")가 출력되는지
- 조건 분기 직전에 연도/월/일 값을 비교하는 `cmp` 인스트럭션이 상수(1, 12, 31 등)와 함께 등장하는지

## 가장 먼저 할 것
Import 창에서 시간 관련 API(`GetLocalTime`, `time`, `srand`)가 있는지부터 확인한다. 있다면 그 API를 호출하는 지점의 xref를 따라가 어떤 값을 비교하는지 본다. 없다면 이름과 무관한 일반 문자열 비교 문제일 가능성을 열어두고 REV-0196/REV-0197 방식으로 접근한다.

## 단계별 절차
1. Import 목록에서 시간 관련 API 유무 확인
2. 있다면 해당 API 호출 직후의 비교 조건(연/월/일 값) 확인
3. 조건이 "현재 날짜 == 1월 1일"류라면, x64dbg로 API 반환값을 담는 메모리를 직접 원하는 값으로 덮어써서 조건 통과
4. 조건이 `srand(time(NULL))` 형태라면 REV-0894, REV-0893 방식으로 시드 자체를 알아내는 전략으로 전환
5. 조건과 무관하게 단순 비교라면 REV-0196/REV-0197로 회귀해 표준적인 문자열 검증 우회 시도

## 명령어/단축키
```text
IDA: Imports 탭에서 GetLocalTime/GetSystemTime/time 검색
x64dbg: API 반환 직후 SYSTEMTIME 구조체 메모리를 Ctrl+G로 이동 → 값 직접 수정 → F9
```

## 출력 해석
`GetLocalTime`은 `SYSTEMTIME` 구조체(연, 월, 요일, 일, 시, 분, 초, 밀리초 순서의 WORD 배열)를 채워 넣는다. 이 구조체의 첫 두 WORD(연, 월)만 바꿔도 "새해가 되었다"는 조건을 통과시킬 수 있는 경우가 많으므로, 조건이 이 구조체의 특정 필드만 검사하는지 먼저 확인하면 효율적이다.

## 흔한 실수
- 실제로 시스템 시계를 1월 1일로 바꾸는 것을 시도하다가 다른 프로그램/OS 동작에 영향을 주는 것 — 디버거로 반환값만 조작하는 편이 더 안전함
- 이름만 보고 무조건 시간 기반 문제라고 확신했다가 실제로는 무관한 단순 비교 문제였을 경우를 대비하지 않는 것
- `srand(time(NULL))` 패턴과 단순 `GetLocalTime` 비교 패턴을 구분하지 않고 같은 방식으로 접근하는 것

## 막혔을 때 다음 체크
- 시드가 시간 기반일 가능성이 있다면 → REV-0894 시간 기반 시드(seed = time())를 역산하는 접근, REV-0893 rand()/srand() 시드 기반 문제 접근법
- 이름과 무관하게 단순 비교였을 경우를 대비하려면 → REV-0196 strcmp 기반 Flag 검증 패턴
- Import된 API 이름만으로 로직을 추정하는 법이 궁금하면 → REV-0761 Import된 CRT 함수 이름으로 원본 로직 추정하기

## 미니 예제
```c
// 이름에서 유추한 가상의 구조(실제 코드 아님)
SYSTEMTIME st;
GetLocalTime(&st);
if (st.wMonth == 1 && st.wDay == 1) {
    print_flag();
} else {
    puts("아직 새해가 아닙니다.");
}
```
이 예제는 "Happy New Year!"라는 이름에서 착안한 가상의 시간 검사 구조이며, 실제 바이너리의 코드가 확인된 것은 아니다.

## 관련 글
- REV-0894 — 시간 기반 시드(seed = time())를 역산하는 접근
- REV-0893 — rand()/srand() 시드 기반 문제 접근법
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0761 — Import된 CRT 함수 이름으로 원본 로직 추정하기
- REV-1038 — [Write-up] Summer Fan
- REV-1042 — [Write-up] my rand

## 출처/검증
- WebSearch로 "dreamhack Happy New Year writeup reversing wargame"을 검색했으나 이 문제를 직접 다루는 공개 write-up을 찾지 못했다(2026-09-10 검증).
- 본문의 날짜/시간 API 기반 로직 추정은 문제명에서 착안한 가설이며 실제 바이너리 분석 결과가 아님을 명시한다.
- Windows `SYSTEMTIME` 구조체 필드 순서 및 `GetLocalTime` 동작은 일반적으로 알려진 Win32 API 동작 방식을 참고했다.
