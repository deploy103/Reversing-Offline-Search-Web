---
id: REV-0142
title: "IDA에 바이너리 처음 열었을 때 해야 할 것"
slug: "rev-0142-ida-first-open"
category: "static-analysis"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: ["IDA 처음 사용법", "IDA 파일 열기", "auto analysis", "IDA 초기 화면", "IDA View-A", "IDA 데이터베이스 저장", "idb", "i64"]
aliases: ["IDA 첫 실행", "IDA 바이너리 로드", "IDA open file", "IDA 파일 불러오기"]
symptom_keywords: ["IDA 열었는데 뭐부터 해야 할지 모르겠음", "IDA 분석이 안 끝남", "IDA 화면에 뭐가 이렇게 많음", "IDA 저장 어떻게 함", "IDA 처음 켜니까 함수가 하나도 없음"]
source_ids: ["SRC-HEXRAYS-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA에 바이너리를 처음 열면 파일 형식/아키텍처 자동 인식과 **auto-analysis(자동 분석)**가 끝날 때까지 기다린 뒤, Functions 창(Ctrl+P)·Strings 창(Shift+F12)·Imports 창을 순서대로 훑어보는 것이 정석적인 초반 3분 루틴이다.

## 언제 검색해야 하나
- IDA를 처음 설치했거나 처음 실행해서 뭘 눌러야 할지 모를 때
- 바이너리를 드래그해서 넣었는데 화면에 코드가 잔뜩 뜨고 뭐부터 봐야 할지 막막할 때
- "분석이 끝난 건지 아닌지" 판단이 안 될 때
- 작업한 내용을 저장하는 방법을 모를 때

## 핵심 개념
IDA는 바이너리 파일을 열면 크게 세 단계를 거친다.

1. **파일 형식 인식** — 파일의 매직 바이트(magic bytes)를 보고 PE(Windows exe/dll), ELF(Linux 실행파일), Mach-O(macOS) 등 어떤 포맷인지, 그리고 32비트/64비트, x86/ARM 등 어떤 아키텍처인지 자동으로 판단한다. 이때 "Load file as" 대화상자가 뜨며, 후보가 여러 개면 목록으로 보여주고 사용자가 고를 수도 있다. 대부분은 IDA가 자동으로 고른 항목(맨 위)이 맞다.
2. **로더(loader) 적용** — 인식한 포맷에 맞는 로더가 섹션(.text, .data, .rdata/.rodata 등)을 IDA 데이터베이스 안에 배치하고, import table/export table을 읽어서 어떤 외부 함수(API)를 쓰는지 등록한다.
3. **auto-analysis(자동 분석)** — 엔트리 포인트부터 코드를 추적하면서 함수 경계를 찾고, 각 함수 내부를 디스어셈블하고, 알려진 라이브러리 함수를 FLIRT 시그니처로 식별해서 이름을 붙이는 과정. 바이너리가 크거나 함수가 많을수록 오래 걸리며, 화면 하단 상태바에 진행률이 표시된다.

이 세 단계 중 **자동 분석이 끝나기 전에는 함수 목록이나 xref 정보가 불완전**하다. 그래서 뭔가 조작하기 전에 반드시 분석이 끝나길 기다려야 한다.

## 화면/코드에서 보이는 징후
- 파일을 열자마자 "Load a new file" 대화상자가 뜨고, 포맷/프로세서 후보 목록과 "Processor type" 드롭다운이 보인다.
- 로딩 직후 화면 하단(상태 바, 화면 맨 아래 줄)에 "Please wait..." 또는 진행률/함수 개수 카운트가 계속 바뀌며 표시된다.
- 화면 하단 **Output window**(로그 창)에 로더 메시지, FLIRT 시그니처 적용 로그, 경고/에러 메시지가 스크롤되며 쌓인다.
- 분석이 끝나면 상태 바가 "AU: idle" 같은 대기 상태로 바뀌고, 더 이상 진행률이 움직이지 않는다.
- 기본적으로 열리는 화면은 **IDA View-A**라는 이름의 디스어셈블리 탭이며, 커서는 보통 프로그램의 **엔트리 포인트(entry point)** 주소에 위치한다.

## 가장 먼저 할 것
파일을 연 직후에는 아무것도 클릭하거나 수정하지 말고, 화면 하단 상태 바와 Output window를 보며 **자동 분석이 완전히 끝날 때까지 기다린다.** 작은 바이너리는 몇 초, 크거나 패킹된 바이너리는 수 분 이상 걸릴 수 있다. 분석 중에 이름 변경/타입 지정 등을 하면 나중에 재분석되면서 되돌아가거나 충돌할 수 있으므로 피한다.

## 단계별 절차

**1) 파일 열기**

`File → Open...` (또는 시작 화면에서 "Go" 버튼을 누른 뒤 파일 선택 다이얼로그, 혹은 실행 파일을 IDA 창에 그대로 드래그&드롭)로 대상 바이너리를 선택한다.

**2) 포맷/프로세서 확인 대화상자**

"Load a new file" 창이 뜨면 위쪽 목록에서 IDA가 자동으로 인식한 포맷(예: `Portable executable for AMD64 (PE)` 또는 `ELF64 for x86-64 (Executable)`)이 있는지 확인한다. 특수한 상황이 아니면 기본 선택값 그대로 **OK**를 누른다. 이 시점에 "Kernel options", "Processor options" 등은 초보 단계에서는 건드리지 않는다.

**3) 자동 분석 대기**

로딩이 끝나면 IDA는 즉시 auto-analysis를 시작한다. 상태 바의 진행 표시와 Output window의 로그가 멈추고 "AU: idle" 상태가 될 때까지 기다린다. 이 사이에는 다른 창을 열어 구경하는 것 정도는 괜찮지만, 이름 바꾸기·타입 지정 같은 편집 작업은 분석이 끝난 뒤에 하는 것이 안전하다.

**4) 초기 화면(IDA View-A) 확인**

분석이 끝나면 기본으로 열려 있는 **IDA View-A** 탭이 엔트리 포인트 주소의 디스어셈블리를 보여준다. 화면 왼쪽 여백의 파란 화살표나 상단 주소가 `start`, `_start`, `WinMain`, `entry` 같은 이름 근처인지 확인한다.

**5) 초반 3분 트리아지 루틴**

다음 순서로 훑어보면 이 바이너리의 성격(패킹 여부, 스트립 여부, 무슨 언어/컴파일러로 만들어졌는지)을 빠르게 감 잡을 수 있다.

- **Ctrl+P** (Functions window) — 함수 개수를 본다. 보통 크기의 바이너리인데 함수가 1~5개밖에 안 보이면 패킹/난독화를 의심해야 한다. 함수 이름이 대부분 `sub_XXXXXX` 형태로 자동 생성된 이름뿐이면 스트립된(strip) 바이너리라는 뜻이다.
- **Shift+F12** (Strings window) — 문자열 목록을 훑어서 에러 메시지, 포맷 문자열, "Wrong password" 같은 힌트가 있는지 확인한다.
- **Imports 창** (`View → Open Subviews → Imports`) — 어떤 Windows API/libc 함수를 가져다 쓰는지 보고, `IsDebuggerPresent`, `ptrace`, `ReadFile`, `strcmp` 같은 힌트성 함수가 있는지 확인한다.
- **엔트리 포인트 위치** — IDA View-A에서 시작 지점 코드가 익숙한 컴파일러 stub(`__security_init_cookie`, `__libc_start_main` 호출 등)인지, 아니면 알아볼 수 없는 이상한 코드(언패킹 스텁 등)인지 본다.

**6) 데이터베이스 저장**

분석 결과와 지금까지 한 모든 작업(이름 변경, 주석, 타입 지정 등)은 원본 실행 파일이 아니라 **IDA 데이터베이스 파일**(32비트는 `.idb`, 64비트는 `.i64`, 그리고 보조 파일 `.nam`, `.til`, `.id0`~`.id2` 등)에 저장된다. `Ctrl+S`로 저장하거나, `File → Save`를 누른다. 다른 이름/경로로 저장하려면 `Ctrl+Alt+S` 또는 `File → Save as...`를 사용한다. IDA를 종료할 때도 "Save database" 대화상자가 뜨는데, 여기서 저장 형식(패킹된 하나의 파일로 저장할지, unpacked 형태로 저장할지)을 고를 수 있다.

## 명령어/단축키
- `File → Open...` : 새 바이너리 열기
- 실행 파일을 IDA 창에 드래그&드롭 : 같은 효과
- `Ctrl+S` : 현재 데이터베이스 저장(같은 경로)
- `Ctrl+Alt+S` : 다른 이름/경로로 저장(Save as)
- `Ctrl+P` : Functions window 열기
- `Shift+F12` : Strings window 열기
- `View → Open Subviews → Imports` : Imports 창 열기
- `View → Open Subviews → Output window` : Output window(로그) 다시 열기(닫았을 경우)

## 출력 해석
- Output window에 `The initial autoanalysis has been finished.` 같은 문구가 뜨면 분석이 끝났다는 신호다(정확한 문구는 버전에 따라 다를 수 있으니, 문구 자체보다는 상태 바가 idle로 바뀌는지를 기준으로 판단하는 것이 더 안전하다).
- 로딩 시 `Load a new file`에서 후보가 하나뿐이면 IDA가 포맷을 확신했다는 뜻이고, 여러 개면 애매한 파일(예: raw binary, 특수 확장자)일 가능성이 있다.
- Imports 창이 거의 비어 있거나 몇 개뿐이면 정적 링크(static link)됐거나 패킹되어 원래의 import table이 감춰져 있다는 신호일 수 있다.
- Functions 창의 함수 개수가 비정상적으로 적으면(파일 크기에 비해) 패킹/암호화된 코드 영역이 있어서 IDA가 코드로 인식하지 못했다는 뜻일 수 있다.

## 흔한 실수
- 자동 분석이 끝나기 전에 이름을 바꾸거나 함수를 강제로 만들다가, 이후 재분석 과정에서 충돌하거나 변경이 덮어써지는 경우.
- Output window를 아예 닫아버리고 안 보다가, 로더가 남긴 중요한 경고(예: "unable to load debug info", 잘못된 섹션 정렬 경고 등)를 놓치는 경우.
- 처음부터 F5(디컴파일)만 눌러보고 Functions/Strings/Imports 창을 통한 전체 그림 파악을 건너뛰는 경우 — 이러면 어느 함수가 진짜 중요한지 감을 못 잡고 헤매게 된다.
- 작업하다가 저장을 안 하고 IDA를 강제 종료해서 지금까지의 이름/주석 작업을 날리는 경우. IDA 종료 시 뜨는 저장 대화상자를 무심코 "No"로 닫지 않도록 주의한다.
- 원본 실행 파일 자체를 수정하려는 시도 — IDA의 이름 변경/주석/타입 지정은 데이터베이스(.idb/.i64)에만 저장되고 원본 exe/elf 파일은 그대로다. 원본 바이트를 바꾸고 싶다면 패치 기능(Edit → Patch program)이나 별도 헥스 에디터가 필요하다.

## 막혔을 때 다음 체크
- 자동 분석이 몇 분째 멈춘 것처럼 안 끝난다면 → 파일이 매우 크거나(수십 MB), 패킹되어 코드가 반복 실행 스텁으로 가득할 수 있다. 상태 바 진행률이 아주 느리게라도 움직이는지 확인하고, 정말 멈췄다면 강제 종료 후 파일 크기/패킹 여부(Detect It Easy 등으로)를 먼저 점검한다.
- 함수 목록(Ctrl+P)에 `main`이나 익숙한 이름이 안 보인다면 → ../triage/rev-0009-finding-main.md 문서를 참고해서 엔트리 포인트에서부터 역추적한다.
- 파일 자체가 스트립되어 있어서 심볼이 하나도 없다면 → ../triage/rev-0010-stripped-entry-point.md 문서를 참고한다.
- 함수 개수가 비정상적으로 적어 패킹이 의심되면 → 정적 분석을 계속하기보다 Detect It Easy 등으로 패커를 먼저 식별하는 것이 시간을 아낀다.

## 미니 예제
64비트 Windows PE 파일 `sample.exe`를 처음 여는 흐름을 요약하면 다음과 같다.

```text
1. File → Open... → sample.exe 선택
2. "Load a new file" 창에서 "Portable executable for AMD64 (PE)" 확인 → OK
3. 상태 바에 진행률 표시 → Output window에 로그 스크롤 → 수 초~수십 초 대기
4. 상태 바가 "AU: idle"로 바뀜 → IDA View-A에 엔트리 포인트(start) 코드 표시
5. Ctrl+P로 함수 200여 개 확인, Shift+F12로 문자열 확인, Imports 창에서 kernel32.dll/user32.dll 함수 확인
6. Ctrl+S로 sample.idb(또는 .i64) 저장
```

## 관련 글
- REV-0143 — IDA Functions 창 사용법
- REV-0144 — IDA Strings 창과 Shift+F12
- ../triage/rev-0009-finding-main.md — main 함수가 안 보일 때 찾는 방법
- ../triage/rev-0010-stripped-entry-point.md — stripped 바이너리에서 시작점 잡는 방법

## 출처/검증
- IDA의 파일 로딩, auto-analysis, 데이터베이스(.idb/.i64) 저장 방식은 Hex-Rays 공식 문서(docs.hex-rays.com) 및 IDA 기본 UI 동작을 기준으로 정리했다(2026-09-08 검증).
- 정확한 대화상자 문구/메뉴 위치는 IDA 버전에 따라 약간 달라질 수 있으므로, 실제 설치된 버전에서 `File` 메뉴와 초기 로딩 대화상자를 직접 확인해서 재검증할 것을 권장한다.
