---
id: REV-0008
title: "성공/실패 문자열에서 역참조 따라가는 방법"
slug: "rev-0008-trace-from-strings"
category: "triage"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: [문자열 xref, 문자열 역참조, X 키 사용법, Strings 창 사용법, 성공 문자열 추적, 실패 문자열 추적]
aliases: ["문자열에서 거꾸로 찾기", "xref 따라가기", "X키로 찾기", "문자열 참조 찾기"]
symptom_keywords: ["문자열은 찾았는데 어디서 쓰이는지 모르겠음", "xref가 뭔지 모르겠음", "X 키 눌러도 아무것도 안 뜸", "문자열 더블클릭해도 안 됨"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA/Ghidra에서 결과 문자열을 찾은 뒤 그 문자열 위에서 **X 키(Cross-references)** 를 누르면 "이 문자열을 사용하는 코드 위치" 목록이 뜨고, 그 위치로 이동하면 검증 로직의 분기 지점에 바로 도달한다.

## 언제 검색해야 하나
- Strings 창에서 "Correct!", "Wrong password" 같은 결과 문자열은 찾았는데 그다음에 뭘 눌러야 할지 모를 때
- `X`를 눌렀는데 아무것도 안 뜨거나, 에러가 나서 당황할 때
- xref 결과가 여러 개 나와서 어떤 걸 봐야 할지 모를 때

## 핵심 개념
xref(cross-reference, 상호 참조)는 "이 주소/데이터를 누가 참조하는가"를 IDA/Ghidra가 자동으로 계산해서 보여주는 기능이다. 문자열은 메모리상의 데이터일 뿐이고, 코드 어딘가에서 그 문자열의 **주소를 레지스터/스택에 로드해서 `printf`나 `puts` 같은 함수에 넘기는 명령어**가 반드시 존재한다(그렇지 않으면 그 문자열은 애초에 실행 중 출력될 수 없다). xref는 바로 그 "주소를 로드하는 명령어"들을 찾아서 보여주는 것이다.

이 기법이 강력한 이유는, 프로그램 전체를 위에서 아래로 읽지 않고 **"결과가 나오는 지점" → "그 결과를 만든 조건" → "그 조건을 계산한 로직"** 순서로 거꾸로(reverse) 거슬러 올라갈 수 있기 때문이다. 이게 "리버스" 엔지니어링이라는 이름에 잘 어울리는 접근이다: 끝에서부터 원인을 추적한다.

x64/x86 어셈블리에서 문자열은 보통 다음과 같이 참조된다.
```asm
lea rax, aCorrect      ; "Correct!" 문자열의 주소를 rax에 로드 (x64)
mov rcx, rax
call puts
```
또는 32비트/구형 코드에서는
```asm
push offset aCorrect
call printf
```
IDA는 이런 패턴을 자동 인식해서 `aCorrect`처럼 문자열 내용 기반의 이름을 붙여주고, xref 목록에 이 `lea`/`push` 명령어의 위치를 보여준다.

## 화면/코드에서 보이는 징후
- Strings 창(Shift+F12)에서 항목을 더블클릭하면 `.rdata`(Windows) 또는 `.rodata`(Linux) 섹션의 해당 주소로 IDA View가 이동한다.
- 그 위치에 `aCorrectFlag db 'Correct! Here is your flag', 0`처럼 데이터 정의가 보인다.
- `X`를 눌렀을 때 아무 반응이 없다면, 커서가 데이터 라인이 아니라 그 옆 빈 공간이나 다른 곳에 있을 가능성이 높다 — 문자열이 정의된 줄 자체에 커서를 정확히 놓아야 한다.

## 가장 먼저 할 것
Shift+F12로 Strings 창을 열고, 결과 메시지로 의심되는 문자열(`Correct`, `Wrong`, `Success`, `Fail`, `Access granted`, `flag`, 한글 문제면 `정답`, `틀렸습니다`, `축하합니다` 등)을 Ctrl+F로 검색한다.

## 단계별 절차

**1) Strings 창에서 후보 찾기**
- IDA: `Shift+F12` → 목록이 뜨면 `Ctrl+F`로 키워드 검색(대소문자 구분 없이 부분 일치).
- Ghidra: `Window → Defined Strings` (또는 `Search → For Strings`로 먼저 문자열을 스캔해야 할 수도 있다) → 필터 박스에 키워드 입력.

**2) 문자열 위치로 이동**
목록에서 항목을 더블클릭하면 해당 데이터가 정의된 주소로 뷰가 이동한다.

**3) xref 실행**
- IDA: 그 데이터 라인에 커서를 놓고 **X** 키(또는 상단 메뉴 View → Cross references to). "xref to..." 창이 뜨고 이 데이터를 참조하는 명령어 주소 목록이 나온다.
- Ghidra: 문자열 라인을 우클릭 → `References → Show References to Address`, 또는 단축키로 목록 하단에 References 패널이 이미 떠 있을 수도 있다.

**4) 목록에서 적절한 참조 선택**
- 참조가 1개뿐이면 바로 더블클릭해서 그 코드 위치로 이동.
- 참조가 여러 개면, 함수 이름이 `main`에 가깝거나 이름이 `check`/`verify`/`validate`처럼 보이는 것을 우선 확인한다.

**5) 도착한 코드에서 위로 거슬러 올라가기**
문자열을 출력하는 코드(`call puts` 등) 주변에서 시작해, 이 코드 블록으로 들어오는 조건 분기(`je`, `jne`, `jz`, `jnz`)를 찾는다. IDA 그래프 뷰(Space bar로 텍스트뷰/그래프뷰 전환)를 쓰면 어떤 분기 조건에서 이 블록으로 들어오는지 화살표로 시각적으로 바로 보인다.

**6) 조건의 근원 찾기**
그 분기 조건 직전의 `cmp`/`test` 명령어가 무엇을 비교하는지 확인한다. 비교 대상이 함수 리턴값이면 그 함수(진짜 검증 함수)로 더 들어간다. 비교 대상이 이미 계산된 지역 변수면, 그 변수가 어디서 계산됐는지 위로 계속 거슬러 올라간다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창), `Ctrl+F`(창 내 검색), `X`(xref to), `Space`(그래프뷰 ↔ 텍스트뷰 전환), `Esc`(이전 위치로 돌아가기 — 여러 번 이동했을 때 매우 유용)
- Ghidra: `Window → Defined Strings`, 우클릭 `References → Show References to Address`, `Ctrl+Alt+←`(이전 위치로)

## 출력 해석
- xref 목록의 각 줄은 `Up`(코드) 또는 `Down`(다른 데이터)으로 구분된다. 우리가 찾는 건 대부분 `Up`(코드에서의 참조)이다.
- 목록에 함수 이름과 오프셋이 같이 나온다(`sub_401500+1A`). `+1A`는 그 함수 시작부터 0x1A바이트 떨어진 위치라는 뜻 — 함수 시작이 아니라 중간이라는 걸 알 수 있다.
- Esc로 원래 있던 위치로 돌아갈 수 있다는 걸 기억해두면, 여러 갈래를 탐색하다가 원점으로 복귀하기 편하다.

## 흔한 실수
- 문자열이 정의된 줄이 아니라 그 문자열을 감싼 구조체나 배열의 시작 주소에 커서를 놓고 X를 눌러서 원하는 결과가 안 나오는 것.
- xref 목록에 나온 첫 번째 결과만 보고 이동했는데 그게 `main`이 아니라 사용법 출력 함수(`usage()`)여서 헛수고하는 것 — 항상 함수 이름과 주변 코드를 먼저 훑어 타당한지 확인한다.
- 그래프뷰에서 화살표 방향을 반대로 읽어서(어디서 들어오는 분기인지) 조건을 거꾸로 해석하는 것.
- 문자열이 통째로 하나의 상수가 아니라 여러 조각을 이어붙여 만들어지는 경우(스택에 바이트 단위로 채워 넣는 경우)를 못 알아채는 것 — 이때는 Strings 창에 아예 안 뜬다. 이 경우 [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)의 입력 추적 방식으로 전환한다.

## 막혔을 때 다음 체크
- Strings 창에 원하는 문자열이 아예 없다 → 암호화/조립형 문자열일 수 있음, [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)로 전환
- xref가 하나도 안 뜬다 → 문자열이 실제로는 사용되지 않는 죽은 데이터이거나, 커서 위치가 잘못됐을 수 있음. 몇 바이트 앞/뒤 줄에서 다시 시도.
- 도착한 함수가 이해가 안 된다 → [rev-0011-when-to-trust-asm.md](./rev-0011-when-to-trust-asm.md)
- 5분째 못 찾았다 → [rev-0015-five-minute-checklist.md](./rev-0015-five-minute-checklist.md)

## 미니 예제
[rev-0001-first-30-seconds.md](./rev-0001-first-30-seconds.md)의 예제를 이어서 보면:
```
$ strings -n 6 crackme | grep -i -E "correct|wrong"
Correct! Here is your flag:
Wrong password, try again.
```
1. IDA에서 Shift+F12 → `Correct` 검색 → `aCorrectHereIs` 항목 더블클릭.
2. 데이터 정의 줄에서 `X` → xref 목록에 `sub_401220+45` 하나만 뜸.
3. 더블클릭해서 이동 → 그 줄 바로 위에 `test eax, eax` / `jnz short loc_401260`이 보임.
4. `eax`가 어디서 왔는지 위로 스크롤 → `call check_password` 호출을 발견 → `check_password`가 진짜 검증 함수.

## 관련 글
- [rev-0001-first-30-seconds.md](./rev-0001-first-30-seconds.md)
- [rev-0006-finding-check-function.md](./rev-0006-finding-check-function.md)
- [rev-0007-trace-from-input.md](./rev-0007-trace-from-input.md)
- [rev-0009-finding-main.md](./rev-0009-finding-main.md)

## 출처/검증
- IDA Pro Cross-reference 기능: Hex-Rays 공식 문서(IDA Help) 기준.
- Ghidra References 기능: Ghidra 공식 문서(ghidra_docs) 기준 (2026-09-08 검증).
