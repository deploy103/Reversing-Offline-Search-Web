---
id: REV-0293
title: "Cutter 설치와 기본 사용법"
slug: "rev-0293-cutter-install-usage"
category: "tools"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: ["Cutter", "radare2", "rizin"]
keywords: ["Cutter 설치", "Cutter 사용법", "radare2 GUI", "Cutter 디컴파일러", "Cutter 함수 목록"]
aliases: ["Cutter 튜토리얼", "radare2 GUI 프론트엔드", "Cutter 시작하기"]
symptom_keywords: ["Cutter 설치가 안됨", "Cutter 화면 구성을 모름", "radare2 GUI 버전을 찾음"]
source_ids: ["SRC-RADARE2-DOCS", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Cutter는 radare2(현재는 rizin 포크 기반)의 분석 엔진을 그대로 사용하면서 함수 목록, 디스어셈블리, 그래프, 디컴파일러를 마우스로 클릭하며 볼 수 있게 만든 무료 오픈소스 GUI 프론트엔드다.

## 언제 검색해야 하나
- radare2 명령어를 외우기 전에 먼저 눈으로 구조를 훑어보고 싶을 때
- IDA Free/Ghidra와 비슷한 느낌의 무료 GUI 디스어셈블러가 필요할 때
- radare2로 커맨드라인 분석을 하다가, 특정 함수만 그래프나 디컴파일된 형태로 빠르게 확인하고 싶을 때

## 핵심 개념
Cutter는 radare2 프로젝트에서 시작되어 현재는 radare2의 후속/포크 프로젝트인 **rizin**을 분석 엔진으로 사용하는 GUI다. 즉 Cutter 자체는 디스어셈블 로직을 새로 구현한 것이 아니라, [REV-0291](./rev-0291-radare2-install-first-command.md)/[REV-0292](./rev-0292-radare2-commands-cheatsheet.md)에서 다룬 `aaa`, `afl`, `pdf` 같은 명령어들이 내부적으로 그대로 실행되고, 그 결과를 창과 패널로 보여주는 것이다. 그래서 Cutter의 하단에는 실제 rizin/radare2 콘솔 명령을 직접 입력할 수 있는 콘솔 창이 항상 남아 있다 — GUI로 못 찾는 기능은 그 콘솔에 원래 명령어를 그대로 치면 된다.

Cutter는 자체 디컴파일러가 없는 대신, 여러 디컴파일러 플러그인(`decompiler`)을 선택해 붙일 수 있다. 대표적으로:
- **native**(rizin 자체 내장 pseudocode 생성기, 별도 설치 불필요)
- **Ghidra 디컴파일러 플러그인**(Ghidra의 디컴파일 엔진을 그대로 가져와 붙이는 방식, 더 정교한 pseudocode 제공)

오프라인 대회 환경이라면 대회 전에 원하는 디컴파일러 플러그인까지 미리 설치해서 검증해 두어야 한다.

## 화면/코드에서 보이는 징후
Cutter를 켜는 건 특정 코드 패턴을 봤을 때가 아니라, "커맨드라인 radare2보다 지금은 화면으로 구조를 훑어보는 게 더 빠르겠다"고 판단했을 때다. 함수가 많고 서로 호출 관계가 복잡한 바이너리일수록 GUI의 함수 목록/그래프가 유리하다.

## 가장 먼저 할 것
설치 후 Cutter를 실행하고, 시작 화면에서 분석할 파일을 선택한다. "Auto analysis" 옵션 창이 뜨면 기본값(대략 `aaa`에 대응하는 수준)을 그대로 두고 진행한다.

## 단계별 절차

### 1) 설치 — Windows
공식 GitHub 릴리스(`https://github.com/rizinorg/cutter/releases`)에서 Windows용 `Cutter-vX.X.X-Windows-x86_64.zip` 또는 설치 프로그램(installer)을 받는다. 압축形 배포판은 압축만 풀면 바로 실행되는 포터블 형태라 오프라인 대회용 USB/외장 SSD에 폴더째 복사해 가기 좋다.

### 2) 설치 — Linux
공식 릴리스에서 `.AppImage` 파일을 받아 실행 권한만 주면 별도 설치 없이 바로 실행된다.
```bash
chmod +x Cutter-vX.X.X-Linux-x86_64.AppImage
./Cutter-vX.X.X-Linux-x86_64.AppImage
```
일부 배포판은 저장소 패키지(`sudo apt install cutter` 등)로도 제공하지만, 버전이 오래된 경우가 많아 AppImage를 권장한다.

### 3) 첫 실행 — 파일 열기와 자동 분석
1. Cutter 실행 후 "Open File"로 대상 바이너리를 선택한다.
2. 분석 옵션 창에서 architecture/bits가 올바르게 자동 감지되었는지 확인하고 "OK"를 눌러 자동 분석을 시작한다.
3. 분석이 끝나면 좌측에 **Functions** 패널이 채워진다.

### 4) 기본 화면 구성
- **Functions 패널**(좌측): `afl`과 동일한 함수 목록. 함수를 더블클릭하면 해당 함수로 이동.
- **Disassembly 뷰**(중앙): `pdf`와 동일한 정보를 줄 단위로 보여줌.
- **Graph 뷰**: radare2 Visual 그래프 모드(`VV`)와 동일한 정보를 마우스로 확대/축소하며 볼 수 있음.
- **Decompiler 패널**(우측 또는 탭): 선택한 디컴파일러 플러그인으로 생성한 pseudo-C 코드.
- **Hexdump 뷰**: `px`와 동일한 raw 바이트 보기.
- **하단 콘솔**: radare2/rizin 명령을 직접 입력하는 창. GUI에 없는 기능은 여기서 원래 명령어로 해결한다.

### 5) 문자열/임포트 확인
상단 메뉴 또는 좌측 패널에서 **Strings**(`iz`에 대응), **Imports**(`ii`에 대응) 탭을 클릭하면 커맨드라인 명령을 몰라도 클릭만으로 같은 정보를 볼 수 있다.

## 명령어/단축키
| 동작 | 방법 |
|---|---|
| 함수로 이동 | Functions 패널에서 더블클릭, 또는 `Ctrl+G` 후 함수명/주소 입력 |
| 그래프 뷰 전환 | 상단 탭에서 "Graph" 클릭 |
| 디컴파일러 코드 보기 | 상단 탭에서 "Decompiler" 클릭 (없으면 Edit → Preferences에서 플러그인 활성화) |
| 원본 콘솔 명령 실행 | 하단 콘솔에 radare2 명령(예: `iz`, `afl`) 직접 입력 |
| 주소로 이동 | `Ctrl+G` |
| 이름 바꾸기(rename) | 함수/변수 우클릭 → Rename, 또는 `N` |

## 출력 해석
Decompiler 패널에 나오는 pseudo-C 코드는 IDA의 F5나 Ghidra의 Decompile 결과와 비슷하지만, 사용하는 디컴파일러 엔진(native/Ghidra 플러그인)에 따라 변수명, 표현식 형태, 최적화 정도가 달라질 수 있다. 한 디컴파일러 결과가 이상하게 보이면 다른 디컴파일러 플러그인으로 전환해서 비교해보는 것도 방법이다.

## Cutter를 언제 쓰고 radare2 커맨드라인을 언제 쓸까
실전에서는 둘을 상황에 따라 오간다. 함수가 몇 개 안 되는 작은 바이너리나 서버 SSH 세션처럼 GUI를 띄우기 번거로운 환경에서는 커맨드라인 radare2([REV-0291](./rev-0291-radare2-install-first-command.md))가 더 빠르다. 반대로 함수 수가 수십~수백 개인 큰 바이너리에서 호출 관계를 눈으로 훑거나, 여러 함수를 오가며 이름을 붙이고(rename) 주석을 다는 작업이 많다면 Cutter의 클릭 기반 탐색과 그래프 뷰가 훨씬 효율적이다. 콘솔 창이 항상 열려 있으므로 "GUI로 훑다가 특정 명령 하나만 커맨드라인으로 실행"하는 혼합 사용도 자연스럽다.

## 흔한 실수
- Cutter를 radare2와 "별개의 도구"로 착각해서 두 도구의 명령어 체계가 다를 거라 예상하는 것 — 내부 엔진이 사실상 같으므로, 콘솔 창에 [REV-0292](./rev-0292-radare2-commands-cheatsheet.md)의 명령어를 그대로 입력해도 동작한다.
- 디컴파일러 플러그인을 하나도 설치/활성화하지 않고 "Decompiler 탭이 비어있다"고 당황하는 것 — Edit → Preferences → Plugins에서 활성화 여부를 확인해야 한다.
- 오프라인 대회 당일에 처음 AppImage/zip을 풀어보는 것 — 반드시 사전에 실행까지 검증해서 의존 라이브러리 누락 등의 문제를 미리 걸러내야 한다.

## 막혔을 때 다음 체크
- Cutter 콘솔에 칠 명령어가 기억 안 나면 → [REV-0292 radare2 명령어 치트시트](./rev-0292-radare2-commands-cheatsheet.md)
- 커맨드라인만으로 충분한 경우의 첫 세션 흐름은 → [REV-0291 radare2 설치와 첫 명령](./rev-0291-radare2-install-first-command.md)
- 보호 기법(RELRO/Canary/NX/PIE)까지 같이 확인하고 싶으면 → [REV-0096 checksec 결과 읽는 법](../linux-elf/rev-0096-checksec.md)

## 미니 예제
Cutter로 `chall`을 열고 Functions 패널에서 `main`을 더블클릭하면 중앙 Disassembly 뷰가 `main` 코드로 이동한다. 이어서 상단 "Graph" 탭을 누르면 같은 함수가 조건 분기 블록 단위의 박스와 화살표로 다시 그려진다 — `cmp`/`jne` 뒤에 갈라지는 두 갈래 흐름을 코드 한 줄씩 읽지 않고 그림으로 먼저 파악할 수 있다.

## 관련 글
- REV-0291 — radare2 설치와 첫 명령
- REV-0292 — radare2 명령어 치트시트
- REV-0096 — checksec 결과 읽는 법

## 출처/검증
- Cutter가 rizin(구 radare2 포크)을 분석 엔진으로 사용한다는 관계, 배포 형태(Windows zip/installer, Linux AppImage), 디컴파일러 플러그인 구조: Cutter 공식 GitHub 저장소(`https://github.com/rizinorg/cutter`) 및 공식 웹사이트 소개 문서 기준.
- 화면 패널 이름(Functions/Graph/Decompiler/Hexdump)과 단축키는 Cutter 공식 문서 기준이며, 버전마다 메뉴 위치가 조금씩 바뀔 수 있어 실제 실행 화면과 대조 검증은 하지 못했다. 설치 직후 Help 메뉴에서 현재 버전의 최신 안내를 다시 확인할 것을 권장한다.
