---
id: REV-0229
title: "Import가 거의 없는 PE를 봤을 때"
slug: "rev-0229-few-imports"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "Detect It Easy", x64dbg]
keywords: ["import table 적음", "few imports", "LoadLibraryA GetProcAddress만 있음", "IAT 비어있음", "동적 import resolving", "manual import resolving", "static linking", "import 부족"]
aliases: ["import가 없다", "imports 창이 텅 빔", "kernel32만 있음", "import table이 이상함", "함수 몇 개 없는 PE"]
symptom_keywords: ["imports 창에 함수가 3개뿐", "loadlibrarya getprocaddress밖에 없음", "printf가 import에 안보임", "import table이 비정상적으로 작음", "static binary인지 packed인지 구분"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows PE의 Imports 창에 `LoadLibraryA`/`GetProcAddress`/`VirtualAlloc`/`VirtualProtect` 정도만 몇 개 보이고 원래 있어야 할 API들이 안 보인다면, 원인은 크게 세 가지(패킹, 정적 링크, 수동 API resolving)로 좁혀지며 각각 확인 방법이 다르다.

## 언제 검색해야 하나
- IDA Imports 창(View → Open Subviews → Imports)을 열었는데 함수가 5개 미만으로 너무 적을 때
- 프로그램이 분명 파일 입출력이나 문자열 처리를 하는데 그와 관련된 API가 import 목록에 하나도 안 보일 때
- `LoadLibraryA`, `GetProcAddress`만 눈에 띄게 반복적으로 보일 때
- REV-0224 패킹 체크리스트를 보다가 "import가 적은 이유"를 더 구체적으로 알고 싶을 때

## 핵심 개념
정상적인 Windows 실행 파일은 **IAT(Import Address Table)**라는 구조를 갖는다. 프로그램이 `MessageBoxA`, `CreateFileA`, `printf` 같은 외부 함수를 호출하려면, 링커가 컴파일 시점에 "이 프로그램은 `user32.dll`의 `MessageBoxA`, `kernel32.dll`의 `CreateFileA`를 쓴다"는 목록을 PE 헤더에 정리해두고, 실제 호출 코드는 `CALL [IAT의 특정 슬롯]` 형태로 그 목록의 주소를 통해 간접 호출한다. Windows 로더는 프로그램을 실행할 때 이 목록을 보고 각 DLL을 메모리에 로드한 뒤, 실제 함수 주소를 IAT 슬롯에 채워 넣는다. 그래서 IDA의 Imports 창은 이 정적으로 기록된 목록을 그대로 보여준다.

그런데 Imports 창이 거의 비어 있다면, 그 프로그램이 **API를 아예 안 쓴다는 뜻이 아니라 "정적으로 기록된 방식으로는" 안 쓴다는 뜻**일 가능성이 높다. 원인은 크게 세 가지다.

### 원인 1: 패킹 (가장 흔함)
패커는 원본 프로그램의 진짜 IAT를 감춘다. 대신 패킹된 파일의 IAT에는 압축 해제 스텁이 스스로 필요로 하는 최소한의 API, 즉 `LoadLibraryA`(DLL을 메모리에 로드)와 `GetProcAddress`(로드된 DLL에서 함수 주소를 이름으로 찾기), 그리고 종종 `VirtualAlloc`/`VirtualProtect`(압축 해제할 메모리 공간을 할당하고 실행 권한을 부여)만 남는다. 압축 해제가 끝난 뒤, 스텁은 원본이 실제로 필요로 하는 모든 API를 **런타임에 직접** `LoadLibraryA` + `GetProcAddress` 조합으로 찾아서 자기만의 IAT를 만들어 채워 넣는다. 이 과정은 파일에 정적으로 기록되지 않으므로 IDA가 볼 수 없다. 이것이 REV-0224/REV-0227에서 다루는 패킹의 핵심 특징 중 하나다.

### 원인 2: 정적 링크(static linking)
프로그램이 필요한 라이브러리 코드를 DLL 형태로 외부에서 가져오는 대신, 컴파일 시점에 실행 파일 안에 통째로 포함시키는 경우다(예: `/MT` 옵션으로 빌드된 Visual C++ 프로그램, Go나 Rust로 만든 정적 바이너리). 이 경우 `printf`, `malloc` 같은 함수들은 이미 실행 파일 내부에 기계어로 그대로 들어있어서 "import"할 필요가 없다. Imports 창에는 정말로 운영체제가 반드시 제공해야 하는 최소한의 커널 API(`kernel32.dll`의 몇 개 함수)만 남는다. 이 경우는 패킹과 달리 **함수 개수 자체는 매우 많다**(정적으로 포함된 라이브러리 코드가 그대로 디스어셈블되어 보이므로)는 점에서 구분할 수 있다.

### 원인 3: 수동 API resolving (난독화 목적)
악성코드나 안티 리버싱을 신경 쓴 프로그램은 패킹되지 않았더라도, import table을 아예 비워두고 코드 안에서 직접 `GetProcAddress` 계열 함수를 호출해 필요한 API 주소를 그때그때 찾아 쓰도록 작성되기도 한다. API 이름 문자열조차 코드에 직접 노출하지 않고 해시값으로 비교하는 경우도 흔하다(API 해싱). 이 경우는 패킹처럼 섹션이 이상하거나 엔트로피가 특별히 높지는 않지만, import가 이상하게 적다는 점은 동일하다.

## 화면/코드에서 보이는 징후
- IDA Imports 창에 `KERNEL32.dll`의 `LoadLibraryA`, `GetProcAddress`, `VirtualAlloc`, `VirtualProtect`, `ExitProcess` 정도만 보이고 5~10개를 넘지 않음
- 프로그램의 문자열(Strings 창)에는 분명 파일 경로, 에러 메시지, 네트워크 관련 문구가 있는데도 그와 관련된 API(`CreateFileA`, `WSAStartup` 등)가 import에 없음
- 디스어셈블리를 보면 `CALL GetProcAddress` 직후 그 반환값(레지스터)을 `CALL` 명령의 대상 레지스터로 바로 쓰는 패턴이 반복됨(런타임에 API 주소를 찾아 바로 호출하는 전형적인 코드)
- 함수 개수 자체는 매우 많은데(수백~수천 개) import는 적은 경우 → 정적 링크일 가능성
- 함수 개수도 적고(수 개) import도 적은 경우 → 패킹일 가능성이 훨씬 높음

## 가장 먼저 할 것
Imports 창과 Functions 창(Ctrl+P)을 함께 본다. **함수 개수가 몇 개 안 되면서 import도 적다면 패킹(REV-0224)을 먼저 의심**하고, **함수 개수는 매우 많은데 import만 적다면 정적 링크**를 먼저 의심한다. 이 두 가지를 구분하는 것이 다음에 할 일을 결정하는 핵심 분기점이다.

## 단계별 절차

**1) Functions 창과 Imports 창을 나란히 확인**

Ctrl+P로 Functions 창을 열어 함수 개수를 확인하고, Imports 창의 함수 개수와 비교한다.

**2) 함수가 적고 import도 적다면 → 패킹 의심**

REV-0224 체크리스트(섹션 이름, 엔트로피, entry point 코드)로 넘어가 패킹 여부를 확정한다.

**3) 함수는 많고 import만 적다면 → 정적 링크 의심**

Strings 창에서 컴파일러/런타임 관련 문구를 찾아본다. 예를 들어 `msvcrt`, `GCC:`, Go 바이너리 특유의 `runtime.` 접두사 함수 이름, Rust 바이너리의 `core::`, `std::` 심볼 등이 보이면 정적 링크된 실행 파일임을 뒷받침한다. 이 경우 패킹이 아니므로 바로 일반적인 정적 분석을 진행하면 된다.

**4) 코드에서 GetProcAddress 호출 패턴을 찾아본다**

IDA에서 `GetProcAddress`의 xref(교차 참조, Ctrl+X)를 확인해서 이 함수가 코드 여러 곳에서 반복 호출되는지 본다. 반복 호출되고 그 직후 함수 포인터를 호출하는 패턴이 많이 보이면, 수동 API resolving을 쓰는 코드임을 알 수 있다. 이 경우 동적 분석(디버거로 `GetProcAddress` 호출 시점에 브레이크포인트를 걸어 어떤 문자열이 인자로 들어가는지 확인)이 정적 분석보다 효율적이다.

**5) 결론에 따라 다음 문서로 이동**

패킹으로 확인되면 REV-0225(UPX 확인) 또는 REV-0227(수동 언패킹 개념)로, 정적 링크로 확인되면 일반 정적 분석 절차로, 수동 resolving으로 확인되면 동적 분석 절차로 넘어간다.

## 명령어/단축키
- IDA `Ctrl+P` : Functions window (함수 개수 확인)
- IDA `View → Open Subviews → Imports` : Import 목록 확인
- IDA `Ctrl+X` (함수 이름 위에서) : 해당 함수의 xref(누가 이 함수를 호출하는지) 확인
- IDA `Shift+F12` : Strings window (컴파일러/런타임 힌트 문자열 확인)

## 출력 해석
- Imports 창에 `KERNEL32.dll`만 있고 함수 5개 미만, Functions 창도 5개 미만 → 패킹 가능성 매우 높음.
- Imports 창은 적지만 Functions 창에 수백 개 이상 → 정적 링크 가능성 높음. 특히 함수 이름이 `sub_`가 아니라 `.text:00401000 _main`처럼 라이브러리 함수 이름이 FLIRT로 인식되어 있다면 정적 링크가 거의 확실하다.
- `GetProcAddress`의 xref가 코드 곳곳에 20개 이상 흩어져 있다 → 수동 resolving을 적극적으로 쓰는 코드. 패킹 스텁 한 곳에서만 몇 번 호출되는 것과는 패턴이 다르다(패킹은 스텁 안에서 한 번에 몰아서 처리, 수동 resolving은 코드 전반에 흩어져 필요할 때마다 호출).
- import된 함수 이름 문자열 자체가 안 보이고 숫자 해시만 코드에 있다면 → API 해싱 기법이 쓰인 것이다. 이 경우 문자열 검색으로는 어떤 API인지 알 수 없고, 해시 알고리즘을 역으로 분석하거나 동적 분석으로 확인해야 한다.

## 흔한 실수
- import가 적다고 무조건 패킹으로 단정하는 것. Functions 창의 함수 개수를 함께 보지 않으면 정적 링크된 정상 프로그램을 패킹으로 오판할 수 있다.
- `LoadLibraryA`/`GetProcAddress`가 보이는 것 자체를 이상하게 여기는 것. 이 두 API는 정상적인 프로그램(플러그인을 동적으로 로드하는 프로그램 등)도 흔히 쓰므로, 이 두 개만 보인다고 무조건 패킹은 아니다 — 다른 API가 완전히 없는지, 함수 개수가 비정상적으로 적은지를 함께 봐야 한다.
- API 해싱을 쓴 코드를 보고 "import가 하나도 없으니 분석 불가능"이라 포기하는 것. 동적 분석으로 `GetProcAddress` 호출 시점의 인자(문자열 또는 해시값)를 확인하면 결국 어떤 API인지 알아낼 수 있다.
- 정적 링크된 대형 바이너리(예: Go/Rust로 만든 실행 파일)를 함수가 너무 많다는 이유로 패킹으로 착각하는 것. 오히려 함수가 지나치게 많은 것은 패킹의 반대 신호에 가깝다.

## 막혔을 때 다음 체크
- Functions/Imports 모두 적다면 → REV-0224로 이동해 섹션 이름/엔트로피까지 종합 판단한다.
- 정적 링크로 확인됐다면 → 패킹 카테고리를 벗어나 일반 정적 분석(REV-0142 등)으로 넘어간다.
- `GetProcAddress` xref가 많고 문자열도 인코딩되어 안 보인다면 → 동적 분석 카테고리에서 API 호출 추적/브레이크포인트 관련 문서를 참고한다.
- 그래도 판단이 안 서면 → Detect It Easy로 컴파일러/링커 시그니처를 확인해 "Microsoft Visual C/C++", "Go compiler", "Rust" 같은 결과가 뜨는지 본다.

## 미니 예제
`tool.exe`의 IDA Imports 창에 다음 4개만 보인다고 하자.

```text
KERNEL32.dll!LoadLibraryA
KERNEL32.dll!GetProcAddress
KERNEL32.dll!VirtualAlloc
KERNEL32.dll!VirtualProtect
```

동시에 Functions 창(Ctrl+P)에는 함수가 딱 2개(`start`, `sub_401000`)뿐이다. 이 조합 — **import 4개 + 함수 2개** — 은 정적 링크로는 설명이 안 되고(정적 링크라면 함수가 훨씬 많아야 함), 전형적인 패킹 스텁의 모습과 정확히 일치한다. 다음 단계는 REV-0224 체크리스트로 섹션 이름과 엔트로피를 확인하고, REV-0225로 넘어가 UPX 여부를 검사하는 것이다.

반대로 `game.exe`의 Imports 창에도 비슷하게 몇 개 API만 보이지만, Functions 창에는 함수가 3,000개 이상 있고 그중 다수가 FLIRT로 `std::`, `boost::` 같은 이름이 붙어 있다면, 이는 패킹이 아니라 C++ 표준 라이브러리가 정적으로 링크된 정상 프로그램일 가능성이 훨씬 높다.

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0228 — Entropy가 높은 Section의 의미
- REV-0227 — 수동 언패킹 개념 OEP와 Dump

## 출처/검증
- IAT(Import Address Table)의 구조와 Windows 로더가 이를 채우는 방식, `LoadLibraryA`/`GetProcAddress`를 이용한 런타임 동적 함수 resolving 기법은 Microsoft PE 포맷 공식 문서(learn.microsoft.com/windows/win32/debug/pe-format) 설명을 기준으로 정리했다(2026-09-08 검증).
- 정적 링크와 패킹의 구분 기준(함수 개수 대 import 개수의 조합)은 다수의 공개 리버싱 교육 자료 및 실무 트리아지 관행을 정리한 일반적인 경험칙이며, 실제 판단은 항상 여러 지표를 종합해야 한다.
