---
id: REV-0564
title: "콘솔 프로그램과 GUI 프로그램 서브시스템 차이"
slug: "rev-0564-subsystem-console-gui"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", editbin]
keywords: ["Subsystem", "IMAGE_SUBSYSTEM_WINDOWS_CUI", "IMAGE_SUBSYSTEM_WINDOWS_GUI", "AllocConsole", "editbin /subsystem", "콘솔 숨기기"]
aliases: ["서브시스템이란", "콘솔 프로그램 gui 프로그램 차이", "콘솔창 안 뜨는 이유", "editbin subsystem windows"]
symptom_keywords: ["exe를 실행했는데 검은 창이 안 뜸", "악성코드가 콘솔창을 숨김", "printf 출력이 안 보임", "subsystem 필드값이 헷갈림"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`IMAGE_OPTIONAL_HEADER.Subsystem` 필드 하나(값 `2`=GUI, `3`=콘솔)가 "이 프로그램을 실행할 때 콘솔 창을 자동으로 붙일지 말지"를 결정하며, 코드 로직이 똑같아도 이 필드만 `editbin /subsystem:windows`로 바꿔치기하면 `printf`를 아무리 많이 써도 화면에 아무 창도 안 뜨게 만들 수 있어서, 악성코드가 콘솔 창을 숨기는 가장 흔하고 값싼 방법 중 하나로 쓰인다.

## 언제 검색해야 하나
- EXE를 더블클릭했는데 검은 콘솔 창이 뜨지 않아서, 콘솔 프로그램인 줄 알았는데 아무 반응이 없다고 느낄 때
- IDA/PE-bear에서 `Subsystem` 필드 값이 `2`인지 `3`인지 헷갈릴 때
- 악성코드가 콘솔 출력 없이 조용히 실행되는 이유를 서브시스템 관점에서 설명해야 할 때
- `editbin /subsystem:windows` 같은 명령으로 이미 빌드된 EXE의 콘솔 창 유무를 바꿀 수 있다는 걸 알고 싶을 때
- GUI 프로그램인데 디버깅용으로 콘솔 출력을 보고 싶어서 `AllocConsole`이 왜 필요한지 궁금할 때

## 핵심 개념

### Subsystem 필드가 결정하는 것
`IMAGE_OPTIONAL_HEADER.Subsystem`(REV-0116에서 다룬 Optional Header의 필드 중 하나)은 WORD 값이며, 대표적인 값은 다음과 같다.

| 값 | 상수 이름 | 의미 |
|---|---|---|
| 1 | `IMAGE_SUBSYSTEM_NATIVE` | 커널 드라이버 등 네이티브 서브시스템(REV-0562 참고) |
| 2 | `IMAGE_SUBSYSTEM_WINDOWS_GUI` | GUI 프로그램 — 실행 시 콘솔이 자동으로 붙지 않음 |
| 3 | `IMAGE_SUBSYSTEM_WINDOWS_CUI` | 콘솔 프로그램(Console User Interface) — 실행 시 콘솔이 자동으로 붙음 |

이 필드는 **Windows 로더가 프로세스를 시작할 때 콘솔 창을 자동으로 할당할지 결정하는 유일한 근거**다. 프로그램 코드가 `printf`를 쓰든 안 쓰든, `main`을 쓰든 `WinMain`을 쓰든 상관없이, 이 필드 값 자체가 콘솔 창 생성 여부를 결정한다.

### CRT 진입점과 Subsystem은 원래 짝을 이룬다
일반적으로 Visual Studio에서 프로젝트를 만들 때, "콘솔 앱" 템플릿은 `main`/`wmain`을 쓰고 링커가 자동으로 `Subsystem=CUI`를 설정하며, "Windows 데스크톱 앱" 템플릿은 `WinMain`/`wWinMain`(REV-0565 참고)을 쓰고 `Subsystem=GUI`를 설정한다. 하지만 이 둘은 **개념적으로 독립적**이다 — 즉 `WinMain`을 쓰면서 `Subsystem=CUI`로 링크하는 것도, `main`을 쓰면서 `Subsystem=GUI`로 링크하는 것도 기술적으로 가능하다. 다만 CRT 시작 함수(`mainCRTStartup` 계열은 `GetCommandLineA`만 호출, `WinMainCRTStartup` 계열은 추가로 `GetStartupInfo`, `GetModuleHandle`도 호출해 `WinMain`에 필요한 인자를 준비)가 다르므로, 링커의 `/ENTRY`, `/SUBSYSTEM` 옵션을 프로젝트 설정과 다르게 섞으면 빌드 시 명시적으로 지정해줘야 한다.

### 왜 악성코드가 이 필드를 악용하는가
콘솔 프로그램(`main`)으로 작성된 백도어/드로퍼라도, 링크할 때 `Subsystem=GUI`로 강제 설정하면 실행 시 **콘솔 창이 전혀 뜨지 않는다.** `printf`로 로그를 찍는 코드가 그대로 남아 있어도, 애초에 표준 출력이 연결된 콘솔 자체가 없으므로 그 출력은 어디에도 보이지 않고 조용히 사라진다(정확히는 실패하거나 무시된다). 이는 코드를 전혀 바꾸지 않고 **PE 헤더의 딱 2바이트(Subsystem 필드)**만 바꾸면 되는, 매우 값싼 은폐 기법이다.

```text
editbin /subsystem:windows sample.exe
```
위 명령 한 줄이면 이미 빌드된 콘솔 EXE를 GUI EXE로 즉시 바꿀 수 있다(둘 다 `main`을 그대로 쓸 수 있으며, CRT가 `GetStartupInfo` 실패 등에 관대하게 대처하도록 되어 있어 실행 자체는 대개 문제없이 이어진다).

### GUI 프로그램에서 콘솔을 보고 싶을 때: AllocConsole
반대로 GUI 프로그램이 디버깅/로그용으로 콘솔 창을 스스로 띄우고 싶다면 런타임에 직접 API를 호출해야 한다.
```c
AllocConsole();                                  // 새 콘솔 창 생성
freopen("CONOUT$", "w", stdout);                 // stdout을 새 콘솔에 연결
```
악성코드가 `AllocConsole` 호출 없이 `Subsystem=GUI`로만 빌드된 경우, 이 프로그램은 정말로 콘솔 출력을 아무 데도 보내지 않는 "조용한" 실행 파일이 된다.

## 화면/코드에서 보이는 징후
- PE-bear/CFF Explorer의 Optional Header 뷰에서 `Subsystem` 필드가 `IMAGE_SUBSYSTEM_WINDOWS_GUI (0x0002)`로 표시됨
- IDA에서 `main`류 함수(인자가 `argc`, `argv` 형태)가 있는데도 Subsystem이 GUI로 설정돼 있어 실행 시 창이 안 뜸
- Import Table에 `AllocConsole`, `freopen`/`_wfreopen`, `SetStdHandle`이 함께 있으면, 이 GUI 프로그램이 스스로 콘솔을 만들어 쓴다는 뜻
- `dumpbin /headers 파일.exe` 결과의 `OPTIONAL HEADER VALUES` 섹션에 `subsystem` 값이 표시됨

## 가장 먼저 할 것
실행 파일을 더블클릭했는데 아무 창도 안 뜬다고 해서 "아무것도 안 한다"고 단정하지 않는다. PE-bear나 `dumpbin /headers`로 Subsystem 필드부터 확인한다. GUI로 설정돼 있다면 콘솔 창이 안 뜨는 것이 정상이고, 실제 동작은 백그라운드에서 계속되고 있을 수 있다 — Process Explorer/Process Monitor 같은 도구로 프로세스가 실제로 살아있는지, 무슨 파일/레지스트리/네트워크 활동을 하는지 별도로 확인해야 한다.

## 단계별 절차

**1) Subsystem 필드 값 확인**
PE-bear, CFF Explorer, 또는 `dumpbin /headers`로 `2`(GUI)인지 `3`(CUI)인지 확인한다.

**2) 진입점 함수 시그니처와 비교**
IDA에서 실제 진입점(REV-0565 참고)이 `main`/`wmain` 형태(정수 `argc`, 문자열 배열 `argv`)인지, `WinMain`/`wWinMain` 형태(`HINSTANCE`, `HINSTANCE`, 문자열, `int`)인지 확인한다. Subsystem 값과 불일치하면(예: `main` 시그니처인데 Subsystem=GUI) 의도적으로 콘솔을 숨긴 것일 가능성을 의심한다.

**3) AllocConsole 등 자체 콘솔 생성 여부 확인**
Import Table에 `AllocConsole`이 있으면 이 프로그램이 필요할 때 스스로 창을 만들어 쓴다는 뜻이므로, 정상적인 GUI 설계일 수 있다.

**4) 필요하면 분석용으로 Subsystem을 임시로 바꿔서 관찰**
```text
editbin /subsystem:console 파일.exe
```
분석 목적으로 콘솔을 강제로 붙여서 `printf` 출력이 실제로 있는지 확인해볼 수 있다(원본 파일은 백업 후 진행).

**5) 동적 분석 도구로 실제 동작 확인**
콘솔이 안 떠도 프로세스는 살아있을 수 있으므로, Process Explorer로 프로세스 트리, Process Monitor로 파일/레지스트리/네트워크 활동을 확인한다.

## 명령어/단축키
```text
dumpbin /headers 파일.exe        OPTIONAL HEADER VALUES 섹션에서 subsystem 값 확인
editbin /subsystem:windows 파일.exe   Subsystem을 GUI로 강제 변경(콘솔 숨김)
editbin /subsystem:console 파일.exe   Subsystem을 CUI로 강제 변경(분석 시 콘솔 강제 표시)
PE-bear: Optional Header 뷰 → Subsystem 필드 직접 확인/수정
```

## 출력 해석
- `subsystem  Windows GUI` — 콘솔 자동 생성 없음. 표준 출력이 어딘가에 연결돼 있지 않으면 `printf` 결과는 보이지 않음
- `subsystem  Windows CUI` — 실행 시 콘솔 창이 자동으로 뜨고, `stdin`/`stdout`/`stderr`이 그 콘솔에 연결됨
- `editbin /subsystem:console`로 바꾼 뒤 다시 실행했을 때 갑자기 콘솔 출력이 쏟아진다면, 원래 GUI로 위장했지만 내부적으로는 콘솔 앱과 동일한 로직(`printf` 등)을 쓰고 있었다는 뜻

## 흔한 실수
- "콘솔 창이 안 뜬다 = 프로그램이 아무것도 안 한다"고 단정하는 것 — Subsystem=GUI인 프로그램은 창 없이도 정상적으로 백그라운드 동작을 계속할 수 있다.
- Subsystem 필드와 진입점 함수 시그니처(`main` vs `WinMain`)가 항상 일치해야 한다고 오해하는 것 — 링커 옵션으로 얼마든지 다르게 조합할 수 있다.
- `AllocConsole` 없이 GUI 서브시스템에서 `printf`를 호출하는 코드가 있으면 "이건 콘솔 프로그램이었을 것"이라고 무조건 단정하는 것 — Subsystem만 GUI로 바꿔치기됐을 가능성부터 의심해야 한다.
- `editbin /subsystem`으로 원본을 직접 덮어써서 원본 증거(포렌식/샘플 무결성)를 훼손하는 것 — 항상 사본에 대해 작업한다.

## 막혔을 때 다음 체크
- Optional Header 전반의 필드 구조가 헷갈리면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- `WinMain`/`wWinMain`/`DllMain`의 시그니처 차이가 궁금하면 → [REV-0565 WinMain wWinMain DllMain 진입점 차이](./rev-0565-winmain-wwinmain-dllmain.md)
- 커널 드라이버의 네이티브 서브시스템이 궁금하면 → [REV-0562 드라이버(.sys) 파일을 만났을 때 최소 대응](./rev-0562-driver-sys-basics.md)
- 진입점을 처음부터 다시 찾고 싶으면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)

## 미니 예제
`updater.exe`를 더블클릭했는데 아무 창도 뜨지 않았다고 하자.

```text
1) dumpbin /headers updater.exe 실행
   subsystem            2 (Windows GUI)

2) IDA로 진입점 확인:
   int __cdecl main(int argc, char** argv) { ... printf(...) ... }
   → main() 시그니처인데 Subsystem은 GUI. 의심스러운 불일치.

3) Import Table에 AllocConsole/freopen이 없음
   → 이 프로그램은 콘솔 출력을 볼 방법이 없도록 의도적으로 설계된 것으로 보임.

4) 분석용 사본에 editbin /subsystem:console updater_copy.exe 적용 후 재실행
   → 그제서야 콘솔 창이 뜨고 printf 로그가 보임, 숨겨져 있던 진단 메시지 확인 가능.
```

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0565 — WinMain wWinMain DllMain 진입점 차이
- REV-0562 — 드라이버(.sys) 파일을 만났을 때 최소 대응
- REV-0121 — Entry Point와 WinMain 찾기

## 출처/검증
- `IMAGE_OPTIONAL_HEADER.Subsystem` 필드와 `IMAGE_SUBSYSTEM_WINDOWS_GUI`/`_CUI`/`NATIVE` 상수 값: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- `editbin /SUBSYSTEM` 링커 도구 옵션과 콘솔 자동 생성 동작: Microsoft Learn "editbin.exe" 및 "/SUBSYSTEM (Specify Subsystem)" 공식 문서 기준.
- `AllocConsole`, `freopen`을 통한 GUI 프로그램의 수동 콘솔 생성 방법: Microsoft Learn "Console" API 공식 문서 기준.
