---
id: REV-0753
title: "Cutter에서 Ghidra 디컴파일러 연동 확인하기"
slug: "rev-0753-cutter-ghidra-decompiler-integration"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Cutter, Ghidra, radare2]
keywords: ["Cutter Ghidra 플러그인", "Cutter decompiler 설정", "Cutter native vs Ghidra 디컴파일러", "Cutter Ghidra 연동 확인법"]
aliases: ["Cutter에 Ghidra 붙이기", "Cutter Ghidra 디컴파일러 활성화", "Cutter 디컴파일러 탭이 비어있음"]
symptom_keywords: ["Cutter Decompiler 탭이 비어있음", "Cutter에서 Ghidra 디컴파일이 안됨", "Cutter native pseudocode가 이상함", "Cutter Ghidra 플러그인 설치법을 모름"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-RADARE2-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Cutter는 기본적으로 rizin/radare2 내장 native 디컴파일러만으로도 동작하지만, Ghidra 디컴파일러 엔진을 플러그인으로 별도 연동하면 더 정교한 타입 추론과 변수명 pseudocode를 얻을 수 있으므로, 연동이 실제로 활성화됐는지는 코드를 열기 전에 반드시 눈으로 확인해야 한다.

## 언제 검색해야 하나
- Cutter의 Decompiler 탭이 비어 있거나, 상단 탭에 "Ghidra"라는 선택지가 아예 보이지 않을 때
- native 디컴파일러가 생성한 pseudocode가 너무 단순하거나 변수 타입이 전부 `undefined4`처럼 뭉뚱그려져 있어, Ghidra 수준의 타입 추론이 필요한데 어떻게 붙여야 할지 모를 때
- 오프라인 CTF 대회 전에 Cutter+Ghidra 디컴파일러 조합이 실제로 정상 동작하는지 미리 검증해두고 싶을 때

## 핵심 개념
Cutter는 자체 디컴파일 엔진을 새로 만들지 않고, 여러 디컴파일러를 **플러그인 형태**로 선택해 붙이는 구조다(REV-0293). 대표적으로 두 가지가 있다.

- **native**: rizin에 내장된 pseudocode 생성기. 별도 설치가 필요 없어 Cutter를 처음 실행하면 기본으로 활성화되어 있는 경우가 많다. 속도는 빠르지만 타입 추론 수준은 Ghidra만큼 정교하지 않을 수 있다.
- **Ghidra 디컴파일러 플러그인**: Ghidra 프로젝트의 디컴파일 엔진(`decompile` 백엔드)을 그대로 Cutter 안에서 호출하는 플러그인이다. Ghidra를 따로 설치해 실행할 필요 없이, Cutter 안에서 같은 디컴파일 품질(구조체 추론, 더 자연스러운 변수명 등)을 얻을 수 있다는 것이 장점이다.

이 플러그인은 Cutter 배포판에 기본 포함되어 바로 켤 수 있는 경우도 있고, 별도의 플러그인 관리자를 통해 추가 설치해야 하는 경우도 있다 — 배포 형태(Windows zip/installer, Linux AppImage, 배포판 패키지)에 따라 다르므로, 대회 전 반드시 한 번은 직접 열어서 확인해야 한다. 연동이 안 된 상태에서 "Ghidra 탭"만 찾다가 시간을 낭비하는 일이 실제로 자주 발생한다.

두 디컴파일러는 결과가 다를 수 있다. 같은 함수를 native로 봤을 때 이상하게 보이는 표현식이 Ghidra 플러그인으로 전환하면 훨씬 읽기 쉬운 형태로 바뀌는 경우가 흔하다. 반대의 경우도 있을 수 있으므로, 하나가 이상해 보이면 곧바로 다른 하나로 바꿔 비교하는 습관이 중요하다(REV-0754에서 다루는 교차검증의 축소판).

## 화면/코드에서 보이는 징후
- Cutter 상단(또는 Decompiler 패널 안)의 디컴파일러 선택 드롭다운에 "Ghidra"라는 항목 자체가 없다.
- Decompiler 패널을 열었는데 아무 내용도 나오지 않거나, 오류 메시지만 표시된다.
- native pseudocode에서 변수/리턴 타입이 전부 `undefined`, `undefined4` 같은 모호한 타입으로만 나와 구조체나 포인터 관계를 파악하기 어렵다.

## 가장 먼저 할 것
파일을 열기 전에 먼저 Cutter의 **Edit → Preferences → Plugins**(또는 이에 대응하는 메뉴)를 열어, Ghidra 디컴파일러 플러그인이 목록에 있고 체크(활성화) 상태인지부터 확인한다.

## 단계별 절차
1. Cutter를 실행하고 아무 바이너리나 열어 자동 분석까지 마친다.
2. 상단 메뉴에서 Edit → Preferences(또는 Cutter Preferences)로 들어가 Plugins 섹션을 연다.
3. 목록에서 Ghidra 관련 플러그인(예: `Native Ghidra decompiler` 또는 이와 유사한 이름)이 보이는지, 체크박스가 활성화되어 있는지 확인한다.
4. 보이지 않는다면 사용 중인 Cutter 배포판이 Ghidra 플러그인을 포함한 버전인지 공식 릴리스 페이지에서 다시 확인한다(일부 경량 배포판은 기본 제외되어 있을 수 있다).
5. 활성화되어 있다면 Decompiler 패널 상단의 드롭다운(또는 탭)에서 "native"와 "Ghidra"를 각각 선택해 같은 함수의 pseudocode를 번갈아 비교해본다.
6. 대회 당일 이전에 이 과정을 미리 한 번 끝까지 검증해, 오프라인 환경에서 실제로 Ghidra 플러그인이 로드되는지 확인해둔다(인터넷 연결 없이도 로컬 플러그인만으로 동작해야 한다).
7. 문제가 있다면 native 디컴파일러만으로도 REV-0158/REV-0161 수준의 수동 분석(Rename/Retype)으로 충분히 대체 가능하다는 점을 대비책으로 기억해둔다.

## 명령어/단축키
| 동작 | 방법 |
|---|---|
| 플러그인 목록/활성화 확인 | Edit → Preferences → Plugins |
| 디컴파일러 전환 | Decompiler 패널 상단 드롭다운에서 native/Ghidra 선택 |
| 콘솔로 직접 확인 | 하단 콘솔에서 `pdf`/`pdg` 계열 radare2/rizin 명령 직접 실행(플러그인 설치 여부에 따라 사용 가능한 명령이 다름) |

## 출력 해석
- native와 Ghidra 두 결과가 크게 다르지 않다면 둘 다 신뢰도가 높다고 볼 수 있다.
- 한쪽에서만 나타나는 이상한 표현식(예: 부호 없는 캐스팅이 과도하게 들어간 산술식)은 그 디컴파일러의 타입 추론 한계일 가능성이 있으므로, 다른 디컴파일러 결과와 대조해 어느 쪽이 더 실제 어셈블리와 일치하는지 REV-0162(Hex View 검증) 방식으로 확인한다.
- Ghidra 플러그인 로딩에 실패하면 보통 Decompiler 패널에 오류 메시지나 빈 화면이 뜨고, 드롭다운에 항목 자체가 나타나지 않는다 — 이는 코드 문제가 아니라 플러그인 설치/활성화 문제다.

## 흔한 실수
- Ghidra 디컴파일러 플러그인이 곧 "Ghidra를 따로 설치해서 열어야 한다"는 뜻이라고 오해하는 것 — 플러그인은 Cutter 안에서 엔진만 재사용하는 것이며 별도의 Ghidra GUI 실행이 필요 없다.
- 대회 당일에 처음으로 플러그인 활성화 여부를 확인하는 것 — 오프라인 환경에서는 인터넷으로 추가 다운로드를 받을 수 없으므로 사전 검증이 필수다.
- 두 디컴파일러 결과가 다르게 나왔을 때 무조건 Ghidra 쪽을 더 신뢰하는 것 — 상황에 따라 native 결과가 더 명확할 수도 있으므로, 항상 실제 디스어셈블리와 대조해서 판단해야 한다.
- Decompiler 탭이 비었는데 "Cutter가 고장났다"고 판단하고 재설치만 반복하는 것 — 먼저 Plugins 설정에서 활성화 여부부터 확인해야 한다.

## 막혔을 때 다음 체크
- Cutter 자체의 화면 구성/설치가 처음이라면 → REV-0293 Cutter 설치와 기본 사용법
- 여러 도구의 디컴파일 결과를 비교하는 방법론 자체가 궁금하다면 → REV-0754 여러 정적분석 도구 결과를 교차검증하는 이유와 방법
- native 디컴파일 결과만으로 변수명을 정리하고 싶다면 → REV-0161 Ghidra Rename과 Data Type 수정(Cutter에서도 개념은 동일하게 적용된다)
- 콘솔 명령 자체가 궁금하다면 → REV-0292 radare2 명령어 치트시트

## 미니 예제
Cutter로 strip된 `chall`을 열고 Decompiler 패널 드롭다운에서 처음엔 "native"가 선택되어 있어 `check_password` 함수가 `undefined4 sym.check_password(undefined4 param_1)`처럼 모호하게 나온다고 하자. 드롭다운을 "Ghidra"로 전환하면 같은 함수가 `int check_password(char *input)`처럼 포인터 타입이 명확히 드러난 형태로 다시 표시될 수 있다. 이 차이를 확인하는 것만으로 두 엔진이 실제로 각각 정상 동작하고 있다는 것을 검증할 수 있다.

## 관련 글
- REV-0293 — Cutter 설치와 기본 사용법
- REV-0292 — radare2 명령어 치트시트
- REV-0754 — 여러 정적분석 도구 결과를 교차검증하는 이유와 방법
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0161 — Ghidra Rename과 Data Type 수정

## 출처/검증
- Cutter가 native(rizin 내장) 디컴파일러와 Ghidra 디컴파일러 플러그인을 선택적으로 지원한다는 구조: Cutter 공식 GitHub 저장소(`https://github.com/rizinorg/cutter`) 및 공식 웹사이트의 기능 소개 문서 기준.
- 플러그인 활성화 메뉴 위치(Edit → Preferences → Plugins)는 Cutter 공식 문서 기준이며, 버전에 따라 메뉴 명칭/위치가 달라질 수 있다.
- 이 문서는 실제 Cutter 화면을 캡처해 재검증하지는 않았으며, 공식 저장소 설명과 커뮤니티에 널리 알려진 사용 패턴을 기준으로 작성했다. 사용 전 자신의 Cutter 버전에서 Plugins 목록을 직접 확인할 것을 권장한다(2026-09-09 검증).
