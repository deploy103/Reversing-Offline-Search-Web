---
id: REV-0596
title: "32비트 바이너리를 64비트 도구로 열어서 이상해질 때"
slug: "rev-0596-32bit-binary-64bit-tool"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords:
  - x64dbg 32비트 실행 파일 오류
  - x32dbg vs x64dbg
  - PE32 PE32+ Magic
  - IMAGE_FILE_MACHINE_I386
  - IMAGE_FILE_MACHINE_AMD64
  - 비트수 불일치
  - Not a valid PE x64 file
aliases:
  - x64dbg가 32비트 exe를 못 엶
  - 32비트 프로그램인데 레지스터가 이상함
  - PE32와 PE32+ 구분
  - 비트수 착각 분석 오류
symptom_keywords:
  - x64dbg로 열었는데 로드가 안 됨
  - 레지스터가 RAX인데 실제로는 EAX만 써야 할 것 같음
  - This is not a valid win64 application
  - 디스어셈블리가 이상하게 깨져 보임
  - x32dbg x64dbg 뭘 써야 할지 모르겠음
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
32비트(PE32) 바이너리를 64비트 전용 도구(예: `x64dbg.exe`)로 열면 로드 자체가 거부되거나 레지스터/스택 해석이 완전히 어긋나므로, 파일을 열기 전에 PE Optional Header의 Magic 값과 COFF Header의 Machine 필드로 비트수를 먼저 확인하고 그에 맞는 32비트 전용 도구(`x32dbg.exe`)를 쓰는 것이 해결책이다.

## 언제 검색해야 하나
- `x64dbg.exe`에 32비트 실행 파일을 드래그했는데 "This is not a valid win64 application" 같은 오류가 뜨며 로드가 안 될 때
- 디스어셈블리에 `RAX`/`RBX` 같은 64비트 레지스터가 보이는데 원래 32비트 프로그램이어야 할 것 같아 헷갈릴 때
- IDA에서 연 바이너리의 스택 인자 오프셋이나 호출 규약이 예상과 다르게 보일 때
- 어떤 실행 파일이 32비트인지 64비트인지부터 확실히 확인하는 방법이 필요할 때

## 가장 먼저 할 것
디버거를 열기 전에 Detect It Easy(DIE)나 PE-bear로 파일을 먼저 스캔한다. DIE 상단의 "CPU" 필드에 `80386`이면 32비트, `AMD64`면 64비트다. 이 한 단계를 건너뛰고 바로 x64dbg를 실행하는 것이 가장 흔한 실수의 원인이다.

## 핵심 개념
PE 파일이 32비트인지 64비트인지는 파일을 열어봐야 짐작할 수 있는 게 아니라 헤더에 명시적으로 기록되어 있다.

- **COFF File Header의 `Machine` 필드**: `IMAGE_FILE_MACHINE_I386` = `0x14C`(32비트), `IMAGE_FILE_MACHINE_AMD64` = `0x8664`(64비트).
- **Optional Header의 `Magic` 필드**: `0x10B`이면 `PE32`(32비트), `0x20B`이면 `PE32+`(64비트). `PE32+`에서는 `ImageBase`, `SizeOfStackReserve` 같은 필드가 8바이트로 확장되고, `BaseOfData` 필드 자체가 없어진다.

이 두 값이 같은 파일 안에서 항상 일치해야 정상이다(32비트인데 Machine은 AMD64인 식으로 섞이면 손상되었거나 위조된 파일이다 — 이 경우는 REV-0592를 참고).

x64dbg 프로젝트는 사실 하나의 실행 파일이 아니라 `x32dbg.exe`(32비트 프로세스 디버깅 전용)와 `x64dbg.exe`(64비트 프로세스 디버깅 전용) 두 개의 별도 바이너리로 배포되며, 둘을 자동으로 골라주는 런처 `x96dbg.exe`도 함께 제공된다. 32비트 디버거 프로세스는 64비트 프로세스의 메모리를 온전히 읽을 수 없고, 반대로 64비트 디버거 프로세스는 32비트 대상 프로세스를 시작하거나 그 컨텍스트(레지스터 세트, 스택 프레임)를 올바르게 해석할 수 없다. 이는 Windows 디버깅 API(`DebugActiveProcess`, `WaitForDebugEvent` 등)가 디버거와 대상 프로세스의 비트수가 같을 것을 전제로 동작하기 때문이다.

## 화면/코드에서 보이는 징후
- `x64dbg.exe`에 32비트 EXE를 직접 열려고 하면 "Failed to load module" 또는 "This is not a valid win64 application"류의 오류 메시지가 뜨고 실행이 시작되지 않는다.
- 반대로 `x32dbg.exe`에 64비트 EXE를 열면 비슷하게 거부되거나, 실행은 되어도 명령어가 깨져 보이거나 주소가 잘려 표시된다.
- IDA에서 32비트 바이너리를 열었는데 디컴파일된 함수 인자가 `a1, a2, a3, a4`처럼 레지스터 기반(x64 fastcall 패턴)으로 나온다면 아키텍처를 착각하고 있을 가능성이 있다 — 32비트는 기본적으로 스택 기반 `stdcall`/`cdecl`이다.
- Task Manager에서 실행 중인 프로세스 이름 옆에 `*32` 표시가 붙어 있다면 그 프로세스는 64비트 Windows 위에서 도는 32비트 프로세스(WOW64)라는 뜻이다.

## 단계별 절차
1. **비트수 확인**: PE-bear로 파일을 열고 좌측 "DOS/COFF/Optional Header" 트리에서 `Machine`과 `Magic` 값을 확인한다. 또는 DIE로 열어 상단 요약의 CPU 항목을 본다.
2. **정적 분석 도구 선택**: IDA는 32비트/64비트 파일을 모두 자동 인식하므로 크게 문제되지 않지만, 열린 후 상단 상태 표시줄이나 `File > Produce file > ...` 메뉴 대신 그냥 좌측 Functions 창 옆 "metapc" 표기와 함께 뜨는 아키텍처 안내를 한 번 확인한다.
3. **동적 분석 도구 선택**: 32비트면 `x32dbg.exe`, 64비트면 `x64dbg.exe`를 실행한다. 둘 중 뭘 써야 할지 모르겠으면 `x96dbg.exe`(통합 런처)로 파일을 열면 알아서 올바른 쪽으로 넘겨준다.
4. **레지스터 이름 확인**: 32비트 분석 중에는 `EAX`/`EBX`/`ESP`/`EIP`, 64비트 분석 중에는 `RAX`/`RBX`/`RSP`/`RIP`가 보여야 정상이다. 디버거 Registers 창에 예상과 다른 크기의 레지스터가 보이면 애초에 잘못된 디버거로 붙은 것이다.

## 명령어/단축키
- DIE: 파일을 드래그 앤 드롭 → 상단 "CPU" 필드 확인
- PE-bear: 좌측 트리 → `FILE_HEADER` → `Machine`, `OPTIONAL_HEADER` → `Magic`
- x64dbg/x32dbg: 실행 파일 자체를 잘못 선택했을 때는 File → Close, 올바른 비트수 실행 파일(x32dbg.exe / x64dbg.exe)을 다시 실행 후 File → Open으로 대상 로드

## 출력 해석
- `Machine = 0x14C`, `Magic = 0x10B` → 32비트(PE32), `x32dbg` 사용
- `Machine = 0x8664`, `Magic = 0x20B` → 64비트(PE32+), `x64dbg` 사용
- 두 값이 서로 모순되면(예: Machine은 AMD64인데 Magic은 PE32) 헤더가 손상/위조된 것이므로 REV-0592(PE 헤더 조작 대응)를 먼저 확인한다.

## 흔한 실수
- x64dbg가 "더 최신이고 상위 호환"일 거라고 생각해서 32비트 파일도 x64dbg로 열려고 시도하는 것 — 실제로는 완전히 별개의 프로세스 아키텍처를 다루는 별도 프로그램이다.
- IDA에서 파일을 열 때 뜨는 "Load new file" 대화상자에서 잘못된 프로세서 타입을 수동으로 선택하는 것 — 특별한 이유가 없다면 자동 감지된 기본값(대개 `metapc`)을 그대로 둔다.
- 32비트 프로그램의 함수 인자를 x64 호출 규약(`RCX`/`RDX`/`R8`/`R9`) 기준으로 찾으려 하는 것 — 32비트는 REV-0123(stdcall/cdecl/fastcall/thiscall)을 따른다.
- Wow64로 실행되는 32비트 프로세스를 다룰 때 비트수를 한 번 더 헷갈리는 것 — 이 경우는 REV-0597을 별도로 참고한다.

## 막혔을 때 다음 체크
- 32비트 프로세스인데 64비트 Windows에서 실행되어 후킹/디버깅이 이상하게 꼬인다면 → REV-0597(Wow64 환경 API 후킹/분석)을 확인한다.
- Machine/Magic 값 자체가 서로 안 맞거나 이상한 값이라면 → REV-0592(PE 헤더 조작)를 확인한다.
- 호출 규약과 스택/레지스터 인자 위치가 헷갈린다면 → REV-0122, REV-0123, REV-0124를 참고한다.

## 미니 예제
PE-bear로 어떤 `crackme.exe`를 열었더니 다음과 같이 표시되었다.

```text
FILE_HEADER.Machine        = 0x014C   (IMAGE_FILE_MACHINE_I386)
OPTIONAL_HEADER.Magic      = 0x010B   (PE32)
```

이 값을 보고 32비트로 판단했으므로 `x32dbg.exe`를 실행해 파일을 열었고, Registers 창에는 정상적으로 `EAX`, `EBX`, `ESP`, `EIP`가 표시되었다. 만약 이 파일을 `x64dbg.exe`로 열려 했다면 로드 단계에서 바로 오류가 나서 아무 분석도 시작할 수 없었을 것이다.

## 관련 글
- REV-0597 — Wow64 환경에서 API 후킹/분석이 꼬일 때
- REV-0592 — PE 헤더가 조작되어 도구가 잘못 파싱할 때
- REV-0122 — Microsoft x64 Calling Convention
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall

## 출처/검증
- PE Optional Header `Magic`(`0x10B`/`0x20B`) 및 COFF `Machine`(`0x14C`/`0x8664`) 값의 의미는 Microsoft PE/COFF 공식 스펙 기준이다.
- x64dbg가 `x32dbg.exe`/`x64dbg.exe` 두 개의 별도 바이너리로 배포되며 비트수가 맞는 대상만 디버깅할 수 있다는 사실은 x64dbg 공식 문서(help.x64dbg.com) 기준이다.
- 2026-09-08 기준 서술.
