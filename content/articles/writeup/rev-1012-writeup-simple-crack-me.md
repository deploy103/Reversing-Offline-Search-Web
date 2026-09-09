---
id: REV-1012
title: "[Write-up] Simple Crack Me"
slug: "rev-1012-writeup-simple-crack-me"
category: "writeup"
difficulty: "basic"
platform: [linux]
architecture: [x64]
format: [ELF]
tools: [Ghidra, GDB]
keywords: ["dreamhack Simple Crack Me", "드림핵 Simple Crack Me", "Simple Crack Me 풀이"]
aliases: ["Simple Crack Me 못풀겠음", "dreamhack simple crack me flag", "심플 크랙미"]
symptom_keywords: ["드림핵 Simple Crack Me 어떻게 풀어야 할지 모르겠음", "Simple Crack Me 입력 길이 오류가 남"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Simple Crack Me는 이름 그대로 가장 기초적인 크랙미 형태의 드림핵 문제로, 후속작인 Simple Crack Me 2가 ELF 바이너리에 길이 검사와 XOR/INC/DEC 조합 변환을 사용하는 것으로 확인된 점을 볼 때, 원작인 이 문제는 그보다 더 단순한 한두 단계짜리 입력 검증(길이 확인 후 고정 비교값과 대조)으로 구성되어 있을 가능성이 높다는 점을 전제로 접근해야 한다.

## 언제 검색해야 하나
- "Simple Crack Me"라는 제목만 보고 아주 쉬운 문제라고 예상했는데 실제로는 Ghidra 디컴파일 결과가 낯설어서 어디부터 봐야 할지 모를 때
- Simple Crack Me 2를 먼저 검색하다가 원작인 Simple Crack Me도 같이 풀어야 하는 상황일 때
- 리눅스 ELF 크랙미를 처음 접해서 `strcmp`/`memcmp` 기반 검증인지 변환 기반 검증인지부터 구분해야 할 때

## 핵심 개념
이 write-up을 작성하며 조사한 결과, "Simple Crack Me"(속편이 아닌 원작) 자체를 상세히 다룬 한국어 공개 풀이 글은 찾지 못했다. 다만 같은 제작자·같은 계열로 보이는 후속 문제 "Simple Crack Me 2"에 대한 공개 풀이(REV-1013 참고)에서는 파일이 리눅스 ELF이고, 입력 길이가 정확히 맞아야 통과되는 길이 검사(`GetStrLen` 형태의 함수)가 먼저 있고, 그 다음 XOR와 증가(INC)/감소(DEC) 연산이 여러 차례 반복 적용된 뒤 `memcmp`로 최종 비교하는 구조라는 것이 확인됐다. "Simple Crack Me 2"라는 이름 자체가 "더 발전된 버전"을 뜻하므로, 원작인 "Simple Crack Me"는 이 다단계 변환 없이 길이 검사와 직접 비교(또는 XOR 한 단계 정도) 수준의 더 단순한 로직일 것으로 추정된다. 이 추정은 확정된 사실이 아니라 이름 규칙과 후속작 구조로부터의 유추임을 분명히 밝힌다.

크랙미 계열 문제에서 검증 로직을 파악하는 일반적 순서는 동일하다. 먼저 실행해서 어떤 오답 메시지가 나오는지 확인하고("입력 길이가 틀렸습니다" 같은 메시지가 있으면 길이 검사가 선행된다는 뜻), 그 메시지를 Ghidra의 Defined Strings에서 찾아 참조하는 함수로 거슬러 올라간 뒤, 그 함수 안에서 비교 연산자가 `strcmp`인지 `memcmp`인지, 아니면 바이트 단위 반복 비교인지를 구분하는 것이 핵심이다.

## 화면/코드에서 보이는 징후
- 실행 파일이 리눅스 ELF 형식이며 Windows/macOS에서 바로 실행되지 않음(가상머신이나 리눅스 환경 필요)
- 임의 문자열 입력 시 "wrong" 또는 길이 관련 오류 메시지가 출력됨
- Ghidra 디컴파일 결과에 `FUN_00401xxx` 형태의 이름 없는 함수와, 그 안에 `strlen`/`scanf` 호출이 먼저 나오고 뒤이어 비교 로직이 이어지는 구조

## 가장 먼저 할 것
Ghidra의 Defined Strings 창(Window → Defined Strings)에서 오답/정답 관련 문자열을 먼저 찾고, 더블클릭해서 그 문자열을 참조하는 함수로 이동한다. 그 함수의 시작부에서 입력을 받는 방식(고정 길이 버퍼인지, `scanf`의 포맷 문자열이 무엇인지)을 먼저 확인해야 뒤에 나오는 비교 로직을 정확히 해석할 수 있다.

## 단계별 절차
1. `file ./chall`로 ELF 여부와 32/64비트를 확인한다.
2. 리눅스 환경(또는 우분투 VM)에서 실제로 실행해 오답 메시지 문구를 확인한다.
3. Ghidra로 열어 Auto Analyze를 마친 뒤 Defined Strings에서 오답 메시지를 찾아 참조 함수로 이동한다.
4. 해당 함수를 디컴파일해서 입력 길이 검사가 있는지, 있다면 요구 길이가 몇 바이트인지 확인한다.
5. 길이 검사를 통과한 뒤 이어지는 비교 로직이 `strcmp`/`memcmp` 직접 비교인지, 변환 후 비교인지 구분한다.
6. 직접 비교라면 비교 대상 문자열/배열을 그대로 읽어 정답으로 사용한다. 변환이 있다면 각 연산을 역순으로 역연산하는 스크립트를 작성한다(REV-0199, REV-0200 참고).
7. 복원한 값을 다시 실행 파일에 입력해 정답 메시지가 나오는지 확인한다.

## 명령어/단축키
```bash
file ./chall
chmod +x ./chall
./chall
```
Ghidra: Window → Defined Strings, 문자열 더블클릭 후 우클릭 → References → Show References to Address로 참조 함수를 찾는다.

## 출력 해석
길이 검사를 통과하지 못하면 보통 "wrong" 계열 메시지보다 먼저 길이 관련 안내가 뜨는 경우가 많다(후속작인 Simple Crack Me 2에서 실제로 "your input length is wrong"이라는 메시지가 확인됨). 이 메시지가 뜬다면 아직 변환/비교 로직에 도달하기 전 단계이므로, 먼저 요구되는 정확한 입력 길이를 맞추는 것이 우선이다.

## 흔한 실수
- 길이 검사를 무시하고 아무 길이의 문자열이나 넣어보며 시간을 낭비하는 것 — 길이 오류 메시지가 뜬다면 반드시 정확한 길이부터 맞춰야 한다.
- Simple Crack Me 2의 다단계 XOR/INC/DEC 변환 구조를 원작에도 그대로 있다고 가정하고 지나치게 복잡한 역연산 스크립트를 먼저 작성하는 것 — 원작은 더 단순할 가능성이 높으므로 먼저 Ghidra 디컴파일 결과로 실제 연산 개수를 확인해야 한다.
- 리눅스 ELF 바이너리를 Windows에서 그냥 더블클릭해 실행되지 않는다고 "파일이 깨졌다"고 오해하는 것.

## 막혔을 때 다음 체크
- 다음 단계인 후속 문제의 실제 검증 구조가 궁금하면 → REV-1013 [Write-up] Simple Crack Me 2
- 길이 검사부터 역추적하는 절차가 헷갈리면 → REV-0218 길이 검증부터 역추적하는 법
- XOR 반복 변환을 역산하는 방법이 필요하면 → REV-0199 XOR 반복 변환 역산
- strcmp/memcmp 검증 패턴 자체가 궁금하면 → REV-0196 strcmp 기반 Flag 검증 패턴, REV-0197 memcmp 기반 Flag 검증 패턴

## 미니 예제
크랙미 계열에서 가장 흔한 최소 형태는 다음과 같다. 실제 Simple Crack Me의 정확한 코드는 아니며, 위 절차를 적용할 때 우선적으로 확인해야 할 최소 골격을 보여주는 예시다.
```c
int check(char *input) {
    if (strlen(input) != N) {
        puts("your input length is wrong");
        return 0;
    }
    return strcmp(input, "hidden_answer") == 0;
}
```
이 골격에서 `N`과 `"hidden_answer"`에 해당하는 실제 값을 Ghidra 디컴파일 결과와 문자열 창에서 직접 찾아내는 것이 이 문제의 실제 풀이다.

## 관련 글
- REV-1013 — [Write-up] Simple Crack Me 2
- REV-0218 — 길이 검증부터 역추적하는 법
- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0197 — memcmp 기반 Flag 검증 패턴
- REV-0199 — XOR 반복 변환 역산

## 출처/검증
- "Simple Crack Me" 원작 자체를 다룬 상세 한국어 공개 write-up은 2026-09-10 기준 조사에서 찾지 못했다. 이 문서의 "핵심 개념"과 "미니 예제"는 후속작 "Simple Crack Me 2"의 공개 풀이(velog "[드림핵] Simple Crack Me 2 풀이", https://velog.io/@hamham/드림핵-Simple-Crack-Me-2-풀이)에서 확인된 구조와 크랙미 문제의 일반적 관례로부터 유추한 것이며, 원작의 정확한 정답이나 상수를 확정적으로 서술하지 않았다.
- ELF 형식이라는 점, 길이 검사 메시지("your input length is wrong")가 존재한다는 점은 후속작 기준으로 확인된 사실이며, 원작에도 동일하게 적용되는지는 추정임을 다시 밝힌다.
