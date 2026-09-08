---
id: REV-0602
title: "CreateRemoteThread로 생성된 코드가 안 보일 때"
slug: "rev-0602-createremotethread-code-not-visible"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords:
  - CreateRemoteThread
  - VirtualAllocEx
  - WriteProcessMemory
  - DLL 인젝션 정적분석 한계
  - 원격 스레드 코드 덤프
  - 프로세스 간 코드 인젝션
aliases:
  - CreateRemoteThread로 만든 코드를 IDA에서 못 찾음
  - 인젝션된 셸코드 위치 찾기
  - WriteProcessMemory 버퍼 덤프
  - 다른 프로세스에 심어진 코드 분석
symptom_keywords:
  - CreateRemoteThread는 있는데 실제 코드가 안 보임
  - VirtualAllocEx WriteProcessMemory만 보임
  - 인젝션된 셸코드를 찾을 수 없음
  - 정적분석에서 페이로드가 안 보임
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA에서 `CreateRemoteThread`, `VirtualAllocEx`, `WriteProcessMemory` 임포트는 보이는데 실제로 실행될 코드(셸코드나 DLL 경로)가 파일 어디에도 안 보인다면, 그 코드는 애초에 이 파일 안이 아니라 대상 프로세스의 메모리 안에서만 존재하는 것이므로 정적 분석을 포기하고 `WriteProcessMemory` 호출 시점에 버퍼를 가로채거나 대상 프로세스에 직접 붙어 동적으로 확인해야 한다.

## 언제 검색해야 하나
- IDA Imports 탭에 `CreateRemoteThread`, `VirtualAllocEx`, `WriteProcessMemory`, `OpenProcess`가 함께 보여서 이 프로그램이 다른 프로세스에 코드를 주입한다는 것은 알겠는데, 정작 주입되는 코드 내용을 파일 안에서 찾을 수 없을 때
- 인젝션 대상 프로세스가 무엇인지, 실제로 무슨 코드가 실행되는지 확인해야 할 때
- `CreateRemoteThread`의 시작 주소(`lpStartAddress`) 인자가 상수가 아니라 런타임에 계산된 값이라 정적으로 추적이 안 될 때

## 가장 먼저 할 것
`WriteProcessMemory` 임포트에 크로스 레퍼런스(`X` 키)를 걸어 호출 지점을 모두 나열한다. 이 함수가 "무엇을, 어디에, 얼마나" 쓰는지가 인젝션되는 코드의 정체를 밝히는 가장 직접적인 단서다.

## 핵심 개념
`CreateRemoteThread`를 이용한 코드 인젝션은 다음과 같은 전형적인 3단계 패턴을 따른다.

```c
HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, dwTargetPid);
LPVOID pRemoteMem = VirtualAllocEx(
    hProcess, NULL, dwSize,
    MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);   // 대상 프로세스에 실행 가능한 메모리 확보
WriteProcessMemory(hProcess, pRemoteMem, pPayload, dwSize, NULL); // 페이로드(셸코드/DLL 경로)를 그 메모리에 복사
HANDLE hThread = CreateRemoteThread(
    hProcess, NULL, 0,
    (LPTHREAD_START_ROUTINE)pRemoteMem,  // lpStartAddress: 방금 써넣은 메모리의 시작 주소
    NULL, 0, NULL);
```

여기서 핵심은, 실제로 실행되는 코드(`pPayload`가 가리키는 바이트들)는 인젝터 프로세스의 실행 파일(PE) 자체 안에 반드시 있는 것이 아니라는 점이다. 다음과 같은 경우 정적 분석으로는 절대 찾을 수 없다.

- 페이로드가 네트워크에서 다운로드되거나, 인젝터 자신의 리소스 섹션에 암호화된 채로 있다가 런타임에 복호화되어 힙 버퍼에 조립되는 경우
- `CreateRemoteThread`의 목적이 셸코드 실행이 아니라 단순 DLL 인젝션(`LoadLibraryA`를 원격 스레드의 시작 주소로 쓰고, `WriteProcessMemory`로는 DLL 경로 문자열만 써넣는 방식)인 경우 — 이 경우 진짜 "코드"는 그 DLL 파일 자체에 있으므로 DLL 파일을 별도로 찾아 분석해야 한다.

즉 인젝터 파일 하나만 정적으로 아무리 들여다봐도, "무엇이 실행되는가"의 답이 그 파일 밖(대상 프로세스의 런타임 메모리, 또는 별도의 DLL 파일)에 있는 경우가 흔하다는 것이 이 문제의 본질이다.

## 화면/코드에서 보이는 징후
- IDA에서 `CreateRemoteThread`의 4번째 인자(`lpStartAddress`)가 상수 주소가 아니라 레지스터/지역 변수(`VirtualAllocEx`의 반환값을 그대로 넣는 패턴)로 되어 있다.
- `WriteProcessMemory`의 3번째 인자(`lpBuffer`, 즉 복사할 원본 데이터의 주소)를 따라가 봐도 코드처럼 안 보이고 그냥 랜덤한 바이트나 암호화된 블록으로 보인다.
- Process Hacker/Process Explorer로 실행 중인 대상 프로세스를 보면 원래 없던 새 스레드가 생성되어 있고, 그 스레드의 시작 주소가 대상 프로세스의 정상 모듈 범위 밖(익명의 `PAGE_EXECUTE_READWRITE` 영역)을 가리킨다.

## 단계별 절차
1. **인젝터 쪽 정적 분석**: `OpenProcess` 호출로 대상 프로세스를 어떻게 특정하는지(PID 인자, 또는 프로세스 이름으로 검색하는 로직) 확인해 어떤 프로세스가 피해자인지 파악한다.
2. **동적 분석 - 페이로드 가로채기**: x64dbg로 인젝터를 실행하고 `bp WriteProcessMemory`를 건다. 걸리면 x64(`RCX`=hProcess, `RDX`=lpBaseAddress, `R8`=lpBuffer, `R9`=nSize) 또는 x86(스택 인자)에서 `lpBuffer`가 가리키는 메모리를 Dump 창에서 "Follow in Dump"로 확인하고, 그 영역을 우클릭 → "Binary → Save To a File"로 통째로 저장한다. 저장된 바이너리는 셸코드 자체이거나 완전한 PE 파일일 수 있다.
3. **동적 분석 - 원격 스레드 시작 주소 확인**: `bp CreateRemoteThread` 브레이크포인트에서 4번째 인자(x64는 스택의 첫 번째 스택 인자, x86은 `[esp+0x10]`)를 확인하면, 이것이 대상 프로세스 안에서 실제로 코드 실행이 시작되는 주소다.
4. **대상 프로세스에 직접 붙기**: `x64dbg`(또는 `x32dbg`) 새 인스턴스로 대상 프로세스에 attach하고, 3번에서 확인한 주소에 브레이크포인트를 건다. 인젝터가 `CreateRemoteThread`를 실행하면 대상 프로세스 쪽 디버거에서 그 주소에 멈춘다.
5. 멈춘 시점부터는 대상 프로세스 컨텍스트에서 정상적으로 코드를 한 줄씩 분석할 수 있다. 필요하면 이 시점의 메모리를 덤프해 IDA로 다시 정적 분석한다.

## 명령어/단축키
- IDA: `X`(크로스 레퍼런스로 `WriteProcessMemory`/`CreateRemoteThread` 호출 지점 나열)
- x64dbg: `bp WriteProcessMemory`, `bp CreateRemoteThread`, 메모리 영역 우클릭 → "Follow in Dump", "Binary → Save To a File"
- x64dbg 두 번째 인스턴스: File → Attach로 대상 PID에 붙기
- Process Hacker/Process Explorer: 대상 프로세스의 스레드 목록에서 새로 생긴 스레드의 시작 주소 확인

## 출력 해석
- `WriteProcessMemory`로 가로챈 버퍼의 첫 2바이트가 `MZ`(`0x5A4D`)라면 통째로 하나의 PE 파일(셸코드가 아니라 리플렉티브 DLL 로딩 등)을 심는 방식이다.
- `lpStartAddress`가 `kernel32.dll!LoadLibraryA`(또는 `LoadLibraryW`)의 실제 주소와 일치한다면, 이는 셸코드 실행이 아니라 클래식 DLL 인젝션 패턴이며, `WriteProcessMemory`로 써넣은 데이터는 코드가 아니라 로드할 DLL의 경로 문자열이다.
- 가로챈 버퍼가 사람이 읽을 수 있는 코드처럼 안 보이고 엔트로피가 높다면 암호화/난독화된 상태이며, 대상 프로세스 안에서 스스로를 복호화하는 스텁이 앞부분에 있을 가능성이 높다.

## 흔한 실수
- 인젝터 파일 하나만 계속 IDA로 열어보며 "코드가 없다"고 결론짓는 것 — 애초에 그 파일 안에 코드가 없을 수 있다는 것을 전제로 접근해야 한다.
- `WriteProcessMemory` 브레이크포인트 없이 `CreateRemoteThread`만 보고 넘어가서, 실제 페이로드 내용을 확보할 기회를 놓치는 것.
- 대상 프로세스에 미리 디버거를 붙여두지 않고 인젝터를 실행해서, 새 스레드가 이미 실행을 마친 뒤에야 뒤늦게 attach하는 것 — 인젝션은 순식간에 끝나므로 인젝터를 실행하기 전에 대상 프로세스(또는 인젝터 자체)를 먼저 디버거에 붙여 놓아야 한다.
- `LoadLibraryA`를 시작 주소로 쓰는 DLL 인젝션 패턴을 셸코드 인젝션으로 착각해서, 존재하지도 않는 셸코드를 찾아 헤매는 것.

## 막혔을 때 다음 체크
- 대상 프로세스가 실행 도중 여러 자식 프로세스를 만들어 어디에 인젝션되는지 헷갈린다면 → REV-0603을 확인한다.
- 인젝션된 DLL의 함수를 분석해야 한다면 → REV-0129(GetProcAddress LoadLibrary 동적 API 해석)를 참고한다.
- 페이로드가 리소스에 암호화되어 있었다면 → REV-0605(문자열이 암호화된 블록에 있을 때)와 REV-0140(Crypt/BCrypt API 흔적)을 확인한다.

## 미니 예제
인젝터를 x64dbg로 실행하고 `bp WriteProcessMemory`를 걸었더니 다음과 같이 멈췄다.

```text
RCX = 0x00000000000000E8   (hProcess)
RDX = 0x0000021A5B7B0000   (원격 메모리 주소, lpBaseAddress)
R8  = 0x0000000000AC0F30   (lpBuffer, 로컬 프로세스의 페이로드 주소)
R9  = 0x0000000000000C00   (nSize = 3072 바이트)
```

`R8`을 "Follow in Dump"로 확인하니 앞부분이 `4D 5A 90 00`(`MZ`)로 시작하는 완전한 PE 파일이었다. 이를 통해 이 인젝터가 셸코드가 아니라 통째의 DLL/EXE 이미지를 대상 프로세스에 심는 방식임을 확인했고, 이 3072바이트를 "Save To a File"로 저장해 별도의 PE 파일로 재구성한 뒤 IDA로 독립적으로 분석할 수 있었다.

## 관련 글
- REV-0603 — 프로세스가 여러 개 자식 프로세스를 만들어 분석이 꼬일 때
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0605 — 문자열이 리소스가 아니라 암호화된 블록에 있을 때

## 출처/검증
- `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread`의 함수 시그니처와 인자 순서, 그리고 전형적인 원격 코드 인젝션 3단계 패턴은 Microsoft Win32 API 공식 문서 및 일반적인 Windows 코드 인젝션 기법 레퍼런스 기준이다.
- `LoadLibraryA`를 `lpStartAddress`로 사용하는 클래식 DLL 인젝션 기법은 널리 알려진 Windows 인젝션 기법(고전적인 "CreateRemoteThread + LoadLibrary" 기법) 기준이다.
- 2026-09-08 기준 서술.
