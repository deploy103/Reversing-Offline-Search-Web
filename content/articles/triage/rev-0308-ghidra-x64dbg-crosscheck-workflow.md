---
id: REV-0308
title: "Ghidra로 분석하고 x64dbg로 크로스체크하는 워크플로"
slug: "rev-0308-ghidra-x64dbg-crosscheck-workflow"
category: "triage"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [Ghidra, x64dbg]
keywords: [Ghidra x64dbg 조합, 무료 도구 리버싱 조합, Ghidra 디컴파일 검증, Windows 무료 리버싱 워크플로, IDA 없이 분석]
aliases: ["Ghidra랑 x64dbg 같이 쓰기", "IDA 없이 Ghidra x64dbg만으로", "무료 툴로 정적동적 조합", "Ghidra 결과 실행으로 확인"]
symptom_keywords: ["IDA가 없어서 Ghidra로만 분석 중인데 검증을 어떻게 하는지 모름", "Ghidra 디컴파일과 x64dbg 어셈블리가 다르게 보임", "Ghidra 함수 이름이 x64dbg에 안 나타남", "무료 도구만으로 Windows 바이너리를 검증하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
IDA 라이선스가 없는 환경에서 Windows PE를 분석할 때는 **Ghidra의 무료 디컴파일러로 구조와 로직 가설을 세우고, x64dbg로 실제 실행값을 크로스체크**하는 조합이 IDA+x64dbg 조합의 완전한 대체 워크플로가 되며, 두 도구 사이의 디컴파일 스타일 차이와 주소 표기 차이만 신경 쓰면 된다.

## 언제 검색해야 하나
- IDA Free의 기능 제한(64비트 디컴파일 미지원 등) 때문에 Ghidra를 메인 정적 분석 도구로 쓰고 있을 때
- Ghidra의 디컴파일 결과(의사코드)가 실제 실행에서도 맞는지 x64dbg로 확인하고 싶을 때
- Ghidra와 x64dbg에서 같은 함수를 가리키는 주소 표기 방식이 달라 혼란스러울 때

## 핵심 개념
Ghidra와 x64dbg는 각각 무료로 배포되는 정적/동적 분석 도구로, IDA+x64dbg 조합과 목적은 동일하지만 세부 사용법에 차이가 있다.

- **디컴파일 스타일 차이**: Ghidra의 디컴파일러(Decompiler)는 IDA의 Hex-Rays와 다른 표기 관습을 쓴다. 예를 들어 부호 없는 비교에 `(uint)` 캐스팅을 자주 명시적으로 붙이고, 지역변수 이름이 `local_1c`, `uVar1`처럼 IDA의 `v1`, `a1`과 다른 패턴으로 자동 생성된다. 논리는 같지만 처음 보면 낯설 수 있다.
- **주소 표기 방식**: Ghidra는 함수 목록(Symbol Tree)에서 파일 기준 가상 주소(예: `0x140015a30`)를 그대로 보여준다. x64dbg는 모듈 기준 상대 주소(`chall.exe+15A30`)로 이동할 수 있으므로, Ghidra 주소에서 이미지 베이스(PE 옵션 헤더의 `ImageBase`, 기본 `0x140000000`)를 뺀 값을 x64dbg 주소창에 입력하면 된다 — 이 계산 방식은 REV-0306(IDA+x64dbg)과 완전히 동일하다.
- **심볼 동기화가 안 되는 점은 동일**: Ghidra에서 함수를 리네임해도 x64dbg는 그 이름을 모른다(디버그 심볼 파일 `.pdb`가 따로 있지 않은 한). 따라서 오프셋 기반 이동이 필수다.

이 조합을 선택하는 실전 이유는 대부분 "IDA Pro 라이선스가 없다"이다. Ghidra는 완전 무료이고 64비트 디컴파일도 제한 없이 지원하므로, 정적 분석 단계는 Ghidra만으로 충분히 진행 가능하다. x64dbg 역시 완전 무료이므로, 이 조합은 비용 없이 IDA+x64dbg와 동등한 정적+동적 워크플로를 구성할 수 있다는 것이 핵심 장점이다.

## 화면/코드에서 보이는 징후
- Ghidra Decompile 창에 `local_28`, `uVar2` 같은 변수명과 `(uint)`, `(undefined4)` 같은 캐스팅이 자주 보인다.
- Ghidra의 Symbol Tree에서 확인한 주소가 x64dbg 주소창에 그대로 입력했을 때 엉뚱한 곳으로 이동하거나 "Invalid address"가 뜬다.
- x64dbg의 디스어셈블리 창에 나오는 함수 이름이 전부 `sub_140015A30` 식으로 남아 있어 Ghidra에서 붙인 이름과 대조가 안 된다.

## 가장 먼저 할 것
Ghidra에서 CodeBrowser를 열고 Window → Bytes 또는 프로그램 정보(Analysis → Program Information 또는 헤더 View)를 확인해서 이미지 베이스 값을 정확히 확인한다. 대부분 PE64는 `0x140000000`이지만, 반드시 실제 값을 확인하고 시작한다.

## 단계별 절차

**1) Ghidra로 정적 분석 및 가설 수립**
Ghidra CodeBrowser에서 Window → Defined Strings로 결과 문자열을 찾고, 문자열을 더블클릭 후 References(우클릭 → Show References To)로 xref를 역추적한다. 해당 함수를 클릭해 Decompile 창에서 의사코드를 읽고 검증 로직 가설을 세운다.

**2) 함수 주소를 오프셋으로 환산**
Ghidra Symbol Tree에서 함수 주소(예: `0x140015a30`)를 확인하고, 이미지 베이스(`0x140000000`)를 빼서 오프셋(`0x15a30`)을 계산한다.

**3) x64dbg로 실행 후 동일 위치로 이동**
```
x64dbg 주소창: chall.exe+15A30
```
`Ctrl+G`로 주소 이동 대화상자를 열고 위 형식으로 입력하면 ASLR과 무관하게 정확히 Ghidra에서 본 것과 같은 코드로 이동한다.

**4) 명령어 일치 여부로 오프셋 계산 검증**
이동한 위치의 어셈블리 명령어(니모닉과 오퍼랜드)가 Ghidra의 Listing 창(디스어셈블리 뷰, 디컴파일 창 옆에 있는 원본 어셈블리)과 정확히 같은지 확인한다. 다르면 이미지 베이스 값을 잘못 읽었을 가능성이 높으므로 1단계로 돌아가 헤더 정보를 재확인한다.

**5) 브레이크포인트와 실행으로 값 검증**
x64dbg에서 F2로 브레이크포인트, F9로 실행, 도달하면 레지스터 창/Dump 창에서 실제 값을 확인해 Ghidra 가설과 대조한다.

**6) 결과를 Ghidra에 다시 반영**
확인된 값이나 함수 역할을 Ghidra에서 주석(단축키 `;`, Annotate 메뉴)으로 남기고, 변수/함수 이름을 우클릭 → Rename으로 정리한다. 이렇게 정리해두면 Ghidra 프로젝트 파일 하나만으로 나중에 다시 분석을 이어갈 수 있다.

## 명령어/단축키
Ghidra: Window → Defined Strings(문자열 목록), 우클릭 → Show References To(xref), Decompile 창 자동 표시, `;`(주석), Rename(우클릭 메뉴).
x64dbg: Ctrl+G(`모듈명+오프셋` 주소 이동), F2(브레이크포인트), F9(실행), F7(스텝 인투), F8(스텝 오버), 레지스터 창/Dump 창.

## 출력 해석
- x64dbg에서 `모듈명+오프셋`으로 이동한 위치의 명령어가 Ghidra Listing과 완전히 일치하면 오프셋 계산이 정확하다는 뜻이다.
- Ghidra 의사코드의 `(uint)` 캐스팅은 단순히 부호 없는 비교/연산임을 명시하는 표기이므로, 논리 자체가 바뀐 건 아니라는 점을 기억한다 — IDA였다면 같은 코드가 캐스팅 없이 표시됐을 수 있다.
- x64dbg 레지스터 값이 Ghidra 가설과 일치하면 검증 성공, 다르면 해당 값이 어디서 오는지 스텝 인투(F7)로 더 위쪽까지 따라 올라가야 한다.

## 흔한 실수
- Ghidra 이미지 베이스를 확인하지 않고 그냥 `0x140000000`이라고 가정했다가, 실제로는 다른 베이스로 컴파일된 파일이라 오프셋 계산이 전부 틀리는 것.
- Ghidra 디컴파일 결과의 `(uint)`, `(undefined4)` 같은 표기를 이상하게 여겨 로직을 잘못 해석하는 것 — 단순 타입 표기 관습 차이일 뿐이다.
- x64dbg에서 값 확인 후 Ghidra에 기록하지 않아, 나중에 같은 함수를 다시 열었을 때 처음부터 재분석하는 것.
- Ghidra Listing(원본 어셈블리) 창을 안 보고 Decompile 창만 보다가, 디컴파일러가 잘못 추론한 부분(드물지만 발생 가능)을 걸러내지 못하는 것.

## 막혔을 때 다음 체크
- 이미지 베이스/오프셋 계산 자체가 처음이라 헷갈린다 → REV-0306 IDA로 정적분석 후 x64dbg로 검증하는 워크플로(같은 계산 방식, IDA 기준 설명)
- Linux ELF라 x64dbg 대신 GDB를 써야 한다 → REV-0307 Ghidra와 GDB를 같이 쓰는 워크플로
- Ghidra 디컴파일 결과 자체가 이상해서 못 믿겠다 → REV-0011 디컴파일 코드가 이상할 때 어셈블리로 돌아가는 기준

## 미니 예제
`quiz.exe`(64비트 PE)를 Ghidra와 x64dbg로 분석한다.

1. Ghidra Defined Strings에서 `Correct Answer!` 발견 → References To 확인 → `FUN_140012a10`에서 참조.
2. Decompile 창에서 `if (uVar1 == 0x2A) { print_correct(); }` 확인. 함수 시작 주소는 Listing에서 `140012a10`.
3. 프로그램 정보에서 이미지 베이스 `0x140000000` 확인 → 오프셋 `0x12a10` 계산.
4. x64dbg에서 `quiz.exe` 실행, `Ctrl+G` → `quiz.exe+12A10` 입력 → Ghidra Listing과 동일한 `cmp eax, 2Ah` 명령어 확인.
5. F2 브레이크포인트, F9 실행, 임의 답 입력 → 브레이크 도달 → `EAX` 값이 `0x1F` 확인 → 예상값 `0x2A`와 다름을 확인, 정답이 아니었음을 실행으로 재검증.
6. Ghidra로 돌아가 `FUN_140012a10`을 `check_answer`로 리네임하고 `; 0x2A와 비교, EAX가 사용자 응답 해시로 추정`이라는 주석을 남긴 뒤 다음 분석(해시 함수 역추적)으로 이동.

## 관련 글
- REV-0306 — IDA로 정적분석 후 x64dbg로 검증하는 워크플로
- REV-0307 — Ghidra와 GDB를 같이 쓰는 워크플로
- REV-0011 — 디컴파일 코드가 이상할 때 어셈블리로 돌아가는 기준

## 출처/검증
- Ghidra Decompiler 표기 관습(`local_`, `uVar`, `(uint)` 캐스팅 등) 및 Defined Strings/References To 기능: Ghidra 공식 문서(Ghidra Help) 기준.
- x64dbg `모듈명+오프셋` 주소 이동 및 단축키: x64dbg 공식 문서(help.x64dbg.com) 기준.
- PE `ImageBase` 옵션 헤더 필드: Microsoft PE/COFF 공식 스펙 기준 (2026-09-09 검증).
