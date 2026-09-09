---
id: REV-1028
title: "[Write-up] public"
slug: "rev-1028-writeup-public"
category: "writeup"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, "Detect It Easy"]
keywords: ["dreamhack public", "드림핵 public", "public 리버싱 문제"]
aliases: ["public 못풀겠음", "public 워게임 풀이"]
symptom_keywords: ["드림핵 public 어떻게 풀어야 할지 모르겠음", "public 문제 이름만으로 내용을 못 짐작함"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
드림핵 워게임 Bronze 1(리버싱 최저 난이도권)인 "public"은 공개된 상세 write-up을 찾지 못한 문제로, 이 글은 문제명이 짧고 일반적인 단어라 내용을 정확히 특정할 수 없다는 점을 먼저 솔직히 밝히고, Bronze 1 등급에서 일반적으로 나타나는 초급 크랙미 풀이 절차를 대신 정리한다.

## 언제 검색해야 하나
- 드림핵에서 "public"이라는 이름의 리버싱 문제를 열었는데 문제 설명이 짧고 이름에서 힌트를 얻기 어려울 때
- Bronze 1 등급인데도 어디서부터 시작해야 할지 감이 안 잡힐 때
- 다른 사람의 풀이를 찾으려 했지만 "public"이라는 이름이 너무 일반적인 단어라서 검색이 잘 안 될 때

## 핵심 개념
"dreamhack public 리버싱 write-up", "dreamhack public reversing writeup" 등 여러 조합으로 검색했지만, 이 문제를 구체적으로 다루는 블로그·velog·GitHub 자료를 찾지 못했다. "public"이라는 단어 자체가 프로그래밍 용어(접근 제어자, public 함수/클래스, public key 등)로도 매우 흔하게 쓰이기 때문에 검색 결과가 문제와 무관한 내용으로 뒤섞이는 경우가 많았다.

따라서 이 섹션은 **확인된 사실이 아니라 등급 기반 추정**이라는 점을 분명히 한다. 드림핵 워게임 리버싱 카테고리에서 Bronze 1은 사실상 입문 단계로, 대체로 다음과 같은 특징을 가진 문제가 많다.

- 파일 하나(PE 또는 ELF)를 받아서 실행하면 입력을 요구하고, 정답을 맞히면 플래그 형식 문자열이 출력되는 구조
- strip되지 않아 함수/변수 이름이 그대로 남아 있는 경우가 많음
- 비교 로직이 `strcmp`, `memcmp`, 또는 단순 문자별 비교 반복문 하나로 끝나는 경우가 많음
- 문자열이 평문으로 바이너리 안에 그대로 남아 있어서 `strings` 한 번으로 상당한 정보를 얻을 수 있는 경우가 많음

"public"이라는 이름에서 억지로 의미를 찾자면, C++/Java 클래스의 `public` 접근 제어자, 또는 "공개된 값"이라는 뜻에서 소스코드 일부가 그대로 공개되어 있거나(부분 소스 제공형 문제), 반대로 "누구나 볼 수 있게 평문으로 노출된 값"이 힌트로 주어지는 문제일 가능성을 생각해볼 수 있다. 이 또한 검증되지 않은 추정이다.

## 화면/코드에서 보이는 징후
- 실행 시 프롬프트가 나오고 입력을 요구하거나, 인자를 요구하거나, 아무 설명 없이 즉시 결과를 출력함
- `file`(Linux) 또는 Detect It Easy(Windows)로 확인했을 때 컴파일러/링킹 방식이 특별히 난해하지 않은, 표준적인 형태일 가능성이 높음(Bronze 등급 특성상 패킹/난독화가 거의 없을 것으로 추정)
- strip 여부에 따라 함수 이름이 남아있는지가 갈리므로 `nm`/IDA Functions 창을 먼저 확인

## 가장 먼저 할 것
바이너리를 받으면 가장 먼저 `file ./public`(Linux) 또는 Detect It Easy(Windows)로 포맷/아키텍처/링킹 방식을 확인한다. 곧바로 실행해서 어떤 입출력을 하는지 관찰하고, `strings ./public | less`로 평문 문자열을 훑어 플래그 포맷이나 힌트가 되는 문구가 있는지 찾는다. 이 세 가지만으로도 문제의 대략적인 유형(단순 비교형/알고리즘형/네트워크형)을 가늠할 수 있다.

## 단계별 절차
1. 파일 종류·아키텍처·링킹 방식 확인(`file`, Detect It Easy)
2. `strings`로 평문 문자열 전체 훑기 — 플래그 형식, 안내 문구, 디버그 심볼 흔적 등
3. 바이너리 직접 실행해서 입출력 동작 관찰
4. IDA/Ghidra로 `main`(또는 strip됐다면 `_start`부터 REV-0097~0099 방식으로) 진입점 찾기
5. `main`에서 호출되는 검증/비교 함수 특정
6. 비교 로직이 단순 상수 비교인지, 반복 연산인지, 외부 라이브러리 호출(암호화 등)인지 구분
7. 정적으로 안 풀리면 x64dbg/GDB로 비교 시점 값 확인(REV-0005 기준으로 정적/동적 전환 판단)

## 명령어/단축키
```bash
file ./public
strings ./public | less
./public            # 직접 실행해 입출력 관찰
nm ./public | grep ' T '   # strip 안 됐다면 함수 목록
```
Windows라면 Detect It Easy로 열어 컴파일러/링커 정보를 먼저 확인하고, IDA에서 `Shift+F12`(문자열), `Ctrl+P`(함수 목록)를 순서대로 확인한다.

## 출력 해석
`strings` 결과에 `Correct`, `Wrong`, `flag{`, `DH{` 같은 문구가 보이면 해당 문구를 출력하는 코드 위치를 xref로 거꾸로 추적해 비교 로직의 위치를 바로 특정할 수 있다. 아무 힌트도 안 보인다면 동적 실행으로 입출력 패턴을 먼저 관찰하는 쪽이 빠르다.

## 흔한 실수
- 문제 이름만 보고 특정 암호 기법(공개키/RSA 등)을 미리 확신하고 그 방향으로만 파고드는 것 — "public"이라는 이름은 확인된 정보가 아니라 추정의 대상일 뿐이다.
- Bronze 1이라고 방심해서 `strings`/실행 관찰 없이 바로 디스어셈블리부터 읽으려는 것 — 가장 쉬운 등급일수록 실행해보고 문자열만 봐도 상당 부분 풀리는 경우가 많다.
- 검색이 안 된다고 포기하는 것 — 실제 문제 파일을 손에 쥐고 있다면 이 글의 일반 절차만으로도 충분히 시작할 수 있다.

## 막혔을 때 다음 체크
- 처음 30초 동안 무엇부터 확인해야 하는지 다시 정리하고 싶으면 → REV-0001 first-30-seconds
- 검증 함수를 못 찾겠으면 → REV-0006 finding-check-function
- 정적/동적 분석 중 어느 쪽을 먼저 해야 할지 헷갈리면 → REV-0005 문제를 정적 분석부터 할지 동적 분석부터 할지 결정하는 법
- 문자열 기반으로 단서를 못 찾았다면 → REV-0008 trace-from-strings

## 미니 예제
검증되지 않은 추정이지만, Bronze 1 등급에서 흔한 구조를 예시로 들면 다음과 같다.
```c
char buf[64];
printf("Input: ");
scanf("%63s", buf);
if (strcmp(buf, "expected_value") == 0)
    printf("DH{...}\n");
else
    printf("Wrong\n");
```
이런 구조라면 `strings`에서 `expected_value`가 그대로 노출되어 있을 수도 있고, strip되어 있다면 `strcmp` 호출 직전에 브레이크포인트를 걸어 비교 대상 문자열을 읽으면 된다. 다시 강조하지만 이는 실제 "public" 문제의 코드가 아니라 등급 기반의 예시 코드다.

## 관련 글
- REV-0001 — 리버싱 문제 파일을 받았을 때 30초 트리아지
- REV-0006 — Flag 검증 함수 찾는 가장 흔한 경로
- REV-0005 — 문제를 정적 분석부터 할지 동적 분석부터 할지 결정하는 법
- REV-0008 — 성공/실패 문자열에서 역참조 따라가는 방법

## 출처/검증
- WebSearch로 "dreamhack public 리버싱 write-up", "dreamhack public reversing writeup", "드림핵 워게임 public 리버싱 문제풀이" 등을 검색했으나 이 문제를 구체적으로 다루는 공개 write-up을 찾지 못했다(2026-09-10 검증).
- 문제명(public), 티어(Bronze 1), 풀이자 수(519명)는 작업 지시에 포함된 드림핵 워게임 목록 조사 결과를 그대로 인용했다.
- 본문의 풀이 절차는 실제 "public" 문제의 검증된 분석이 아니라, 드림핵 워게임 Bronze 등급 리버싱 문제 전반에서 관찰되는 일반적 경향에 기반한 추정 가이드임을 명시한다.
