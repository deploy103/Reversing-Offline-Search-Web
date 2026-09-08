---
id: REV-0621
title: "WinDbg/x64dbg 심볼 로드가 안 되어 함수명이 안 보일 때"
slug: "rev-0621-symbol-load-fails-no-function-names"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [WinDbg, x64dbg]
keywords: ["심볼", "PDB", "_NT_SYMBOL_PATH", "심볼 서버", "Symbols 탭", "오프라인 심볼"]
aliases: ["심볼 로드 실패", "함수명이 sub_로만 나옴", "PDB 못 찾음", "심볼 서버 접속 안됨"]
symptom_keywords: ["시스템 DLL 함수명이 안 보인다", "ntdll 함수가 주소로만 나온다", "심볼을 다운로드할 수 없다", "PDB 파일이 없다는 오류가 뜬다", "오프라인 환경에서 심볼이 안 잡힌다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`ntdll.dll`/`kernel32.dll` 같은 시스템 DLL의 함수명이 WinDbg/x64dbg에서 주소로만 보인다면, 대부분 **인터넷이 연결되지 않아 Microsoft 공개 심볼 서버에서 PDB를 받아오지 못한 것**이다. 오프라인 대회 PC에서는 이게 정상이며 사실 큰 문제가 되지 않는다. 시스템 DLL의 함수 이름은 PDB 없이도 **Export Table**만으로 대부분 확인 가능하고, 분석 대상 바이너리 자체에는 애초에 PDB가 딸려오지 않는 경우가 대부분이므로 `sub_401000`류 이름이 뜨는 것은 정상이다.

## 언제 검색해야 하나
- WinDbg에서 `kb`(콜 스택)나 `u`(역어셈블)를 실행했는데 함수 이름 없이 `ntdll!0x7ffabc123456` 같은 주소만 나올 때
- x64dbg Symbols 탭에서 시스템 DLL 옆에 노란 경고 아이콘이나 "심볼 없음" 표시가 뜰 때
- WinDbg 실행 시 `*** ERROR: Symbol file could not be found` 또는 `SYMSRV: ... 0x80070002 (파일을 찾을 수 없습니다)` 메시지가 뜰 때
- 인터넷이 안 되는 대회 PC에서 디버깅할 때 함수 이름이 하나도 안 뜨는 것을 보고 "디버거가 고장났다"고 오해할 때

## 핵심 개념
심볼(디버그 심볼, PDB)은 함수 이름, 지역 변수 이름, 소스 라인 정보를 담은 별도 파일로, 컴파일된 바이너리 자체에는 (특별히 넣지 않는 한) 포함되지 않는다. Microsoft는 Windows 시스템 DLL의 공개 심볼을 **심볼 서버**(`https://msdl.microsoft.com/download/symbols`)를 통해 온라인으로 배포한다. WinDbg/x64dbg는 기본적으로 이 서버에 접속해서 필요한 PDB를 다운로드하고 로컬 캐시에 저장한 뒤 함수 이름을 보여준다.

여기서 두 가지를 구분해야 한다.

1. **시스템 DLL(`ntdll`, `kernel32`, `user32` 등)의 심볼**: 이건 Microsoft가 제공하는 공개 심볼이며, 인터넷 연결과 심볼 서버 접근이 필요하다. 오프라인 환경에서는 이게 없어서 함수 이름이 안 보이는 게 정상이다. 단, 이 DLL들은 모두 자신의 함수를 **Export Table**로 공개하고 있으므로(REV-0120 참고), 심볼이 없어도 Export Table 이름만으로 `CreateFileW` 같은 이름은 이미 정확히 보인다. 즉 API 이름 자체는 심볼 없이도 항상 보이고, 심볼이 있어야만 보이는 것은 그 DLL **내부** 비공개 함수들(`RtlpXxx` 같은 내부 헬퍼)뿐이다.
2. **대상 바이너리(문제로 주어진 EXE) 자체의 심볼**: CTF/워게임 바이너리는 대부분 `/DEBUG` 옵션 없이 릴리스 빌드되거나, PDB가 의도적으로 제거되어 배포된다. 이 경우 IDA/x64dbg가 `sub_401000`, `loc_402010`처럼 자동 생성한 이름을 붙이는 것은 정상이며, 이건 심볼 "로드 실패"가 아니라 애초에 PDB가 존재하지 않는 것이다.

## 화면/코드에서 보이는 징후
- WinDbg 시작 로그에 `DBGHELP: ntdll.dll - export symbols` 처럼 "export symbols"라고 명시되어 있으면, PDB가 아니라 Export Table만으로 대체 로드했다는 뜻이다.
- x64dbg Symbols 탭에서 시스템 DLL 옆에 노란 아이콘, 사용자 바이너리 옆에는 원래부터 심볼 표시가 없음(에러가 아님)
- WinDbg에서 `.symfix`나 `.reload` 실행 시 타임아웃이나 네트워크 오류 메시지가 뜸
- IDA에서 함수 이름이 `sub_`/`loc_`/`nullsub_`으로 시작하는 것은 심볼 문제가 아니라 애초에 이름 정보가 없다는 뜻(디컴파일/휴리스틱 분석 결과일 뿐)

## 가장 먼저 할 것
지금 이름이 안 보이는 대상이 "시스템 DLL"인지 "분석 대상 바이너리"인지부터 구분한다. 분석 대상 바이너리라면 PDB가 원래 없는 것이 정상이니 심볼 문제를 해결하려 시간 쓸 필요가 없다. 시스템 DLL이라면 아래 절차로 오프라인 대응을 한다.

## 단계별 절차
1. **오프라인이면 심볼 다운로드를 기대하지 않는다**: 대회 PC는 보통 인터넷이 없으므로 처음부터 온라인 심볼 서버 접근을 시도하지 않는 것이 시간 낭비를 줄인다.
2. **Export Table로 충분한지 확인**: WinDbg의 `x ntdll!*CreateFile*`처럼 와일드카드 검색을 해보면, PDB가 없어도 Export Table 기반 이름이 뜨는지 확인할 수 있다. 대부분의 공개 Win32 API 이름은 이것으로 해결된다.
3. **로컬 심볼 캐시 활용(사전 준비된 경우)**: 대회 전에 인터넷이 되는 환경에서 미리 심볼을 캐시해뒀다면, `_NT_SYMBOL_PATH` 환경변수를 로컬 캐시 경로로 지정한다.
   ```text
   set _NT_SYMBOL_PATH=srv*C:\symbols
   ```
   대회 PC로 그 `C:\symbols` 폴더를 통째로 복사해가면 인터넷 없이도 미리 받아둔 심볼을 그대로 쓸 수 있다.
4. **x64dbg에서 심볼 경로 설정**: Options → Preferences → Symbols(또는 Misc) 탭에서 Symbol Store 경로를 로컬 캐시 폴더로 지정하고, "심볼 다운로드" 관련 옵션은 오프라인이면 꺼둔다.
5. **분석 대상 바이너리는 export/import 이름 위주로 분석**: 자체 PDB가 없는 것이 확정되면, 함수 이름을 직접 리네임하며 분석을 진행하는 것이 정상적인 워크플로다. IDA의 `sub_` 이름을 `N`(리네임)으로 직접 의미 있는 이름으로 바꿔가며 진행한다.
6. **`.reload`/`lm` 명령으로 현재 로드 상태 점검(WinDbg)**: `lm`을 입력하면 각 모듈의 심볼 상태가 `pdb symbols`, `export symbols`, `deferred` 등으로 표시된다. `export symbols`면 이미 최선의 상태(오프라인에서 얻을 수 있는 최대치)에 도달한 것이다.

## 명령어/단축키
- WinDbg: `.symfix`(심볼 경로를 기본 서버로 재설정, 온라인 필요), `.reload`(모듈 재로드), `lm`(로드된 모듈과 심볼 상태 나열), `x ntdll!*키워드*`(와일드카드 심볼 검색)
- 환경변수: `_NT_SYMBOL_PATH=srv*C:\symbols*https://msdl.microsoft.com/download/symbols`(온라인용), `srv*C:\symbols`(오프라인 캐시 전용)
- x64dbg: Options → Preferences → Symbols

## 출력 해석
- `lm` 결과에서 `ntdll`이 `(pdb symbols)`로 나오면 PDB까지 완전히 로드된 것이고, `(export symbols)`면 Export Table 기반 대체이며(오프라인에서 흔함), `(deferred)`는 아직 로드 시도조차 안 한 상태다.
- `export symbols` 상태에서도 공개 API 이름(`CreateFileW` 등)은 정확히 보이므로 분석에 큰 지장은 없다. 다만 소스 줄 번호나 지역 변수 이름, 내부 비공개 함수 이름은 볼 수 없다.
- 분석 대상 바이너리의 함수가 계속 `sub_`로 남아있는 것은 오류가 아니라 "아직 이름을 안 붙인 상태"라는 뜻이다.

## 흔한 실수
- 오프라인 환경인 것을 모르고 심볼 다운로드가 안 된다고 x64dbg/WinDbg를 재설치하거나 재부팅을 반복하는 것. 네트워크 문제이지 도구 문제가 아니다.
- 분석 대상 바이너리에 PDB가 없는 것을 "심볼 로드 실패"로 착각해서 시간을 낭비하는 것. 애초에 CTF 바이너리는 PDB가 없는 것이 기본이다.
- `_NT_SYMBOL_PATH`를 온라인 서버 URL로만 설정해두고 오프라인 PC에 그대로 가져가서, 매번 접속 시도 → 타임아웃으로 디버거 반응이 느려지는 것. 오프라인이면 로컬 캐시 경로만 지정해야 한다.
- Export Table 이름과 PDB 심볼 이름을 같은 것으로 착각하는 것. Export 이름은 항상 볼 수 있지만, 함수 내부의 지역 변수/줄 번호 정보는 PDB가 있어야만 나온다.

## 막혔을 때 다음 체크
- 시스템 DLL 함수의 역할 자체를 추측해야 한다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- x64dbg의 기본 사용법 자체가 처음이라면 → REV-0127(x64dbg로 EXE 첫 분석 시작)을 먼저 읽는다.
- x64dbg 단축키/명령을 빠르게 찾고 싶다면 → REV-0281(x64dbg 핵심 단축키와 명령 치트시트)을 확인한다.

## 미니 예제
오프라인 대회 PC에서 WinDbg로 `target.exe`를 붙여 `kb`(콜 스택)를 실행했더니 다음처럼 나왔다.

```text
0:000> kb
 # ChildEBP RetAddr
00 0019fa10 76f1a2b0 ntdll!NtWaitForSingleObject+0x14
01 0019fa30 75c31234 KERNELBASE!WaitForSingleObjectEx+0x98
02 0019fa60 00401520 target!ReceiveLoop+0x23
```

`ntdll`과 `KERNELBASE`는 함수 이름이 정확히 보이는데(둘 다 Export 이름), `target.exe`는 애초에 자체 PDB가 없으므로 `target!ReceiveLoop`처럼 IDA에서 미리 붙여둔 이름이 아니라면 `target!sub_401520`처럼 나왔을 것이다. `lm` 명령으로 확인해보니 `ntdll`과 `KERNELBASE`는 `(export symbols)` 상태였고, 이는 인터넷 없이도 Export Table만으로 충분히 해석된 것이었다.

## 관련 글
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0281 — x64dbg 핵심 단축키와 명령 치트시트

## 출처/검증
- Microsoft 공개 심볼 서버(`https://msdl.microsoft.com/download/symbols`)와 `_NT_SYMBOL_PATH` 환경변수 문법, `.symfix`/`.reload`/`lm` 명령은 Microsoft WinDbg/디버깅 도구 공식 문서 기준이다.
- PDB 없이 Export Table만으로 공개 함수 이름을 해석하는 동작은 Microsoft DbgHelp 공식 문서 기준이다.
- 미니 예제의 구체적 주소값과 콜 스택은 설명을 위해 구성한 예시다(2026-09-08 기준 서술).
