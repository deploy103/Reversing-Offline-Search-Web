---
id: REV-0128
title: "Windows 문자열 ASCII와 UTF-16 찾기"
slug: "rev-0128-windows-string-encoding"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["UTF-16LE", "wide string", "와이드 문자열", "WCHAR", "LPWSTR", "IDA Unicode strings", "Shift+F12 필터", "x64dbg string references", "ASCII vs UTF-16"]
aliases: ["윈도우 문자열 인코딩", "와이드 스트링", "유니코드 문자열 찾기", "u\"...\" 표시", "PE 문자열 UTF-16"]
symptom_keywords: ["exe 문자열 검색했는데 아무것도 안 나옴", "strings 결과에 이상한 점(dot)들이 섞여 나옴", "IDA Strings 창에 문자열이 하나도 없음", "x64dbg에서 문자열이 깨져 보임", "L\"문자열\" 이 뭔지 모르겠음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows PE 바이너리는 리눅스 ELF와 달리 문자열이 1바이트 ASCII가 아니라 **문자당 2바이트인 UTF-16LE(와이드 문자열)**로 저장되는 경우가 매우 흔하기 때문에, 기본 설정의 `strings` 명령이나 IDA의 기본 문자열 필터로는 아무것도 안 잡히는 경우가 많고, Shift+F12 필터 옵션이나 `u"..."` 표시 방식을 알아야 이를 놓치지 않는다.

## 언제 검색해야 하나
- IDA Strings 창(Shift+F12)이나 `strings` 명령을 돌렸는데 화면에 보이는 문자열이 거의 없거나, 있어야 할 텍스트가 안 보일 때
- Hex Viewer로 파일을 열었을 때 문자열처럼 보이는데 글자마다 `00` 바이트가 하나씩 끼어 있어서 "점들이 섞여 있다"고 느껴질 때
- 소스코드에 `L"문자열"`, `TEXT("문자열")`, `WCHAR`, `LPWSTR`, `LPCWSTR` 같은 표기가 보이거나, 함수 이름이 `MessageBoxW`, `CreateFileW`처럼 끝에 `W`가 붙어있는 이유가 궁금할 때
- x64dbg에서 문자열 참조(String references)가 예상보다 훨씬 적게 나올 때
- Windows 프로그램과 리눅스 프로그램의 문자열 저장 방식이 왜 다른지 비교하고 싶을 때

## 핵심 개념

### ASCII/UTF-8 vs UTF-16LE
리눅스 ELF 바이너리는 대부분 문자열을 **1바이트 = 1문자**인 ASCII 또는 UTF-8로 저장한다. 예를 들어 `"Hello"`는 `48 65 6C 6C 6F`(5바이트)로 그대로 저장된다. `strings` 명령이나 IDA의 기본 문자열 필터는 이런 1바이트 문자열을 찾도록 기본 설정되어 있다.

반면 Windows API는 오래전부터 **UTF-16LE(2바이트 = 1문자, 리틀 엔디안)**을 네이티브 문자 인코딩으로 사용해왔다. 같은 `"Hello"`가 UTF-16LE로 저장되면 `48 00 65 00 6C 00 6C 00 6F 00`(10바이트)가 된다 — 각 문자 뒤에 `00` 바이트가 하나씩 끼어 있는 모습이다. Hex Viewer에서 문자열이 있어야 할 자리에 아스키 문자와 `.`(점, 즉 0x00을 표현할 수 없어서 표시되는 문자)가 번갈아 나오는 것처럼 보인다면 이게 바로 와이드 문자열이다.

### 왜 Windows는 UTF-16을 쓰는가
Windows NT 계열은 설계 초기부터 국제화(다국어 지원)를 염두에 두고 유니코드(당시 UCS-2, 이후 UTF-16으로 확장)를 시스템 내부 문자 인코딩으로 채택했다. 그래서 대부분의 Win32 API는 함수 이름 끝에 `A`(ANSI, 1바이트 코드페이지 기반)와 `W`(Wide, UTF-16) 두 버전이 함께 존재한다. 예를 들어:
- `MessageBoxA` / `MessageBoxW`
- `CreateFileA` / `CreateFileW`
- `GetProcAddress`는 함수 이름 자체는 항상 ANSI(`LPCSTR`)만 받지만, `LoadLibraryA`/`LoadLibraryW`는 둘 다 있다.

내부적으로 `A` 버전은 결국 문자열을 UTF-16으로 변환한 뒤 `W` 버전을 호출하는 얇은 래퍼(wrapper)인 경우가 대부분이다. 최신 Visual Studio 프로젝트는 기본적으로 유니코드(`UNICODE`, `_UNICODE` 매크로 정의)로 빌드되므로, 소스코드에서 그냥 `MessageBox(...)`나 `TEXT("문자열")`이라고 써도 실제로는 `MessageBoxW`가 호출되고 문자열은 UTF-16으로 저장된다.

### 소스코드에서 보이는 표기
- `L"문자열"` — 컴파일러에게 이 리터럴을 UTF-16(wide) 문자열로 저장하라고 지시하는 C/C++ 접두사.
- `TEXT("문자열")` 또는 `_T("문자열")` — `UNICODE` 매크로가 정의되어 있으면 `L"문자열"`로, 아니면 그냥 `"문자열"`로 치환되는 매크로. 유니코드/ANSI 양쪽 빌드를 모두 지원하려는 코드에서 흔히 쓰인다.
- `WCHAR`, `wchar_t` — UTF-16 코드 유닛 하나를 담는 타입(Windows에서는 2바이트).
- `LPWSTR`/`LPCWSTR` — wide 문자열(널 종료 `WCHAR*`)에 대한 포인터 타입.

### 리눅스 배경지식이 있는 사람이 특히 주의할 점
리눅스에서 `strings binary`만 치면 대부분의 문자열이 다 나오는 것에 익숙하다면, Windows PE에서 똑같이 했을 때 결과가 훨씬 빈약해 보여서 "이 프로그램엔 문자열이 별로 없나?"라고 착각하기 쉽다. 실제로는 문자열 대부분이 UTF-16으로 저장되어 있어서 1바이트 기준 스캔에 걸리지 않는 것뿐이다. 이 차이를 모르면 정적 분석 초반부터 중요한 힌트(에러 메시지, 정답 문자열 등)를 통째로 놓치게 된다.

## 화면/코드에서 보이는 징후
- Hex Viewer에서 `48 00 65 00 6C 00 6C 00 6F 00` 처럼 각 아스키 문자 바이트 사이에 `00`이 규칙적으로 끼어 있는 패턴.
- IDA의 기본 텍스트 뷰에서 와이드 문자열이 `L"Hello"` 또는 도구/버전에 따라 `u"Hello"`(유니코드 리터럴 표기)로 표시됨 — 일반 ASCII 문자열은 그냥 `"Hello"`로 표시되어 시각적으로 구분된다.
- IDA Strings 창(Shift+F12)에 문자열이 거의 없거나 예상보다 훨씬 적게 나오는데, 실제 파일 크기나 UI가 있는 프로그램인데도 문자열이 부족해 보임.
- x64dbg의 String references 창(우클릭 → Search for → All modules → String references)에서 나온 목록에 아스키 문자열만 보이고 UI 텍스트가 안 보임.
- Import 목록에 `MessageBoxW`, `CreateFileW`, `lstrlenW` 처럼 끝에 `W`가 붙은 함수가 많음 — 이는 그 프로그램이 유니코드(와이드) 빌드라는 강한 신호다.

## 가장 먼저 할 것
문자열 검색 결과가 빈약해 보이면 곧바로 "문자열이 없다"고 결론짓지 말고, 먼저 IDA Strings 창의 설정에서 UTF-16 필터가 켜져 있는지, 혹은 `strings` 계열 도구에 와이드 문자열 옵션이 있는지부터 확인한다.

## 단계별 절차

**1) IDA Strings 창에서 인코딩 필터 확인**

`Shift+F12`로 Strings 창을 연다. 창을 우클릭하고 `Setup...`(또는 `Strings window setup`)을 선택하면 어떤 인코딩(C-style ASCII, Unicode C-style 등)을 찾을지 체크박스로 고를 수 있다. 기본값에 따라 유니코드(UTF-16) 옵션이 꺼져 있을 수 있으니, `Unicode 16-bit`나 이에 해당하는 항목이 체크되어 있는지 확인하고 없으면 켠 뒤 창을 새로고침(우클릭 → Refresh)한다.

**2) IDA 디스어셈블리에서 와이드 문자열 리터럴 표시 확인**

`.rdata`/`.data` 섹션의 데이터를 보다가 문자로 보이는 바이트 나열이 있으면, 그 위치에서 `A`(Ascii로 변환) 또는 배열 재해석 단축키를 눌러보고, 자동으로 `L"..."` 혹은 `u"..."` 형태로 표시되는지 확인한다. IDA는 2바이트 간격으로 나열된 아스키 값 패턴을 감지하면 유니코드 문자열로 자동 인식하는 경우가 많다.

**3) Sysinternals Strings로 와이드 문자열까지 함께 추출**

명령줄에서 Sysinternals의 `strings.exe`(또는 GNU `strings`의 `-e l` 옵션)을 쓰면 ASCII와 UTF-16LE 문자열을 한 번에 뽑아낼 수 있다.
```text
strings.exe -n 4 sample.exe
```
GNU binutils의 `strings`(WSL 등)라면 인코딩을 명시해서 두 번 돌린다.
```bash
strings -a -e s sample.exe   # 1바이트(ASCII/Latin-1) 문자열
strings -a -e l sample.exe   # 리틀 엔디안 16비트(UTF-16LE) 문자열
```

**4) x64dbg에서 String references로 동적 확인**

디스어셈블리 창에서 우클릭 → `Search for` → `Current Module`(또는 `All Modules`) → `String references`를 선택하면, x64dbg가 코드에서 참조하는 문자열들을 ASCII/UTF-16 구분 없이 스캔해서 목록으로 보여준다.

**5) Import 목록으로 유니코드 빌드 여부 먼저 짐작하기**

PE-bear나 IDA Imports 창에서 `...W` 로 끝나는 함수가 대부분이면 이 프로그램은 유니코드(와이드) 빌드이므로, 문자열도 대부분 UTF-16일 것이라고 미리 예상하고 검색 전략을 세울 수 있다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창 열기), 창 우클릭 → `Setup...`(인코딩 필터 변경) → 우클릭 → `Refresh`
- IDA: 데이터 영역에서 `A`(Ascii 문자열로 변환/재해석)
- x64dbg: 디스어셈블리 우클릭 → `Search for` → `String references`
- Sysinternals Strings: `strings.exe -n 4 <파일>` (ASCII+유니코드 모두 탐지)
- GNU strings(WSL): `strings -e s <파일>`(ASCII), `strings -e l <파일>`(UTF-16LE)

## 출력 해석
- Hex Viewer에서 `xx 00 xx 00 ...` 패턴이 규칙적으로 이어지면 UTF-16LE 와이드 문자열이다. `00 xx 00 xx`(0이 먼저 오는 패턴)라면 빅 엔디안이거나 다른 정렬이므로 흔치 않은 경우다 — x86/x64 Windows는 거의 항상 리틀 엔디안 UTF-16LE다.
- IDA에서 문자열이 `L"..."`/`u"..."`로 표시되면 와이드 문자열, 그냥 `"..."`이면 1바이트(ASCII/UTF-8) 문자열이라는 뜻이다.
- `strings -e l` 결과에 의미 있는 텍스트가 쏟아지는데 `strings -e s`(1바이트) 결과는 빈약하다면, 이 바이너리는 문자열 대부분을 UTF-16으로 저장하는 유니코드 빌드다.
- Import에 `A` 버전 함수(`MessageBoxA` 등)만 있다면 ANSI 빌드일 가능성이 높으므로 문자열도 1바이트일 확률이 높다 — 다만 혼용되는 경우도 있으므로 둘 다 검색해보는 것이 안전하다.

## 흔한 실수
- `strings` 명령이나 IDA 기본 필터로 아무것도 안 나온다고 "이 파일엔 힌트가 없다"고 성급히 결론 내리는 것 — Windows PE에서는 UTF-16 검색을 반드시 별도로 해봐야 한다.
- Hex Viewer에서 `48 00 65 00`처럼 보이는 걸 그냥 "패딩이 섞인 이상한 데이터"로 넘겨버리고 문자열로 인식하지 못하는 것.
- `L"..."` 리터럴을 일반 문자열과 혼동해서, char 배열 크기 계산(바이트 수)을 문자 개수와 같다고 착각하는 것 — UTF-16 문자열은 문자 개수 × 2바이트(+ 널 종료 2바이트)만큼 메모리를 차지한다.
- ANSI(`A`)와 와이드(`W`) 버전 API가 인자로 받는 문자열 포인터의 실제 바이트 레이아웃이 다르다는 것을 잊고, 두 버전을 같은 방식으로 덤프해서 읽으려는 것.

## 막혔을 때 다음 체크
- 문자열을 찾았는데 그 문자열이 왜 이 위치에서 참조되는지 흐름을 추적하고 싶다면 → REV-0142 IDA에 바이너리 처음 열었을 때 해야 할 것(Xref 추적 관련)
- x64dbg로 직접 실행하며 문자열이 만들어지는 과정을 보고 싶다면 → REV-0127 x64dbg로 EXE 첫 분석 시작
- 문자열을 이용해 동적으로 API를 찾는 코드(`GetProcAddress`에 넘기는 함수 이름 문자열 등)를 만났다면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석

## 미니 예제
소스코드가 다음과 같다고 하자.
```c
#include <windows.h>
int WINAPI WinMain(HINSTANCE h, HINSTANCE p, LPSTR cmd, int show) {
    MessageBoxW(NULL, L"Access Denied", L"Error", MB_OK);
    return 0;
}
```
이 프로그램을 컴파일한 exe의 `.rdata` 섹션에는 다음과 같은 바이트가 들어있다(16진수, 일부 생략).
```text
41 00 63 00 63 00 65 00 73 00 73 00 20 00 44 00 65 00 6E 00 69 00 65 00 64 00 00 00
; A  .  c  .  c  .  e  .  s  .  s  .    .  D  .  e  .  n  .  i  .  e  .  d  . NUL
```
`strings -e s`로는 이 문자열이 전혀 안 잡히고, `strings -e l`이나 IDA Strings 창의 Unicode 필터로만 `Access Denied`가 보인다. IDA 디스어셈블리에서는 이 데이터가 `L"Access Denied"` 형태로 자동 표시되며, `call MessageBoxW` 직전 `lea rdx, [해당 주소]` 코드가 이 문자열을 인자로 넘기는 지점이다.

## 관련 글
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것
- REV-0125 — PE-bear로 헤더 분석하는 방법

## 출처/검증
- Win32 API의 `A`/`W` 함수 쌍과 UTF-16(와이드 문자) 사용 관례는 Microsoft 공식 문서(learn.microsoft.com, "Unicode and Character Sets", "Conventions for Function Prototypes") 기준.
- IDA Strings 창의 인코딩 필터(Setup) 및 유니코드 문자열 자동 인식 동작은 Hex-Rays 공식 문서(docs.hex-rays.com) 및 기본 UI 동작 기준.
- Sysinternals Strings 및 GNU binutils `strings -e` 옵션은 각 공식 문서(learn.microsoft.com/sysinternals, GNU binutils manual) 기준(2026-09-08 확인).
