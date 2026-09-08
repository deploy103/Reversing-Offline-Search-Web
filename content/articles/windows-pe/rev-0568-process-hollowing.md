---
id: REV-0568
title: "프로세스 할로잉(Process Hollowing) 개념 소개"
slug: "rev-0568-process-hollowing"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Process Hollowing", "RunPC", "NtUnmapViewOfSection", "CREATE_SUSPENDED", "SetThreadContext", "ZwUnmapViewOfSection", "프로세스 인젝션"]
aliases: ["프로세스 할로잉", "프로세스 비우기 기법", "정상 프로세스 안에 악성코드 심기", "RunPE"]
symptom_keywords: ["정상 파일명인데 코드가 다른 이미지로 바뀌어 있다", "svchost.exe인데 이상한 코드가 실행된다", "CREATE_SUSPENDED로 프로세스를 만든다", "메모리의 PE 헤더와 디스크 파일이 다르다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
프로세스 할로잉(Process Hollowing, 흔히 RunPE라고도 불림)은 정상적이고 서명까지 된 실행 파일(예: `svchost.exe`, `explorer.exe`)을 일시 정지 상태로 실행시킨 뒤, 그 프로세스의 메모리에서 원래 이미지를 언매핑하고 그 자리에 완전히 다른(악성) PE 이미지를 다시 매핑해 실행 흐름을 바꿔치기하는 기법으로, 작업 관리자나 보안 도구에는 정상 프로세스 이름/서명으로 보이지만 실제 메모리 내용은 전혀 다른 프로그램이 돌아가는 상황을 만든다.

## 언제 검색해야 하나
- 프로세스 이름은 `svchost.exe`처럼 정상인데, 메모리 덤프를 떠보니 디스크의 원본 파일과 `.text` 섹션 내용이 완전히 다를 때
- 코드에서 `CreateProcess`를 `CREATE_SUSPENDED` 플래그로 호출한 뒤 `NtUnmapViewOfSection`, `SetThreadContext`, `ResumeThread`가 순서대로 나오는 패턴을 봤을 때
- CTF 라이트업이나 악성코드 분석 리포트에서 "Process Hollowing" 또는 "RunPE"라는 용어를 보고 원리가 궁금할 때
- 정상 프로세스의 `ImageBase` 메모리 영역인데 그 안의 PE 헤더 값(`AddressOfEntryPoint` 등)이 파일과 다른 경우

## 핵심 개념
프로세스 할로잉의 표준적인 절차는 다음과 같다.

1. **일시 정지 상태로 정상 프로세스 생성**: 공격자가 `CreateProcess`를 `dwCreationFlags`에 `CREATE_SUSPENDED`(0x4)를 포함해 호출한다. 이렇게 하면 프로세스와 기본 스레드는 만들어지지만, 메인 스레드는 아직 코드를 실행하지 않고 멈춰 있다. 대상으로는 서명된 정상 시스템 바이너리(`svchost.exe`, `RegAsm.exe`, `MSBuild.exe` 등)를 흔히 쓴다.
2. **원본 이미지 언매핑("비우기")**: `NtUnmapViewOfSection`(또는 `ZwUnmapViewOfSection`) 함수로 대상 프로세스의 메모리에서 원래 로드되어 있던 정상 이미지를 통째로 언매핑한다. 이 시점에서 프로세스는 이름과 핸들은 정상이지만 실행할 코드가 없는 "빈 껍데기(hollow)" 상태가 된다. — 기법 이름의 유래다.
3. **악성 이미지 매핑**: `VirtualAllocEx`로 대상 프로세스 안에 새 메모리를 할당하고(대개 원본 이미지의 `ImageBase`와 같은 주소를 지정), 공격자가 준비한 악성 PE의 각 섹션을 `WriteProcessMemory`로 써넣는다. 필요하면 재배치도 함께 처리한다.
4. **컨텍스트 조작**: `GetThreadContext`로 정지된 메인 스레드의 CPU 컨텍스트(레지스터 상태)를 읽고, x86에서는 `EAX`(또는 x64에서는 `RCX`/`RDX` 등 관례에 따라 다름, 흔히 문서화된 것은 x86 기준 `CONTEXT.Eax`가 새 프로세스 최초 진입점 주변 정보를 가리키는 패턴) 값을 조작하거나, 더 흔하게는 `CONTEXT.Eip`(또는 `Rip`) 값을 새 이미지의 `AddressOfEntryPoint`로 직접 바꾼다. `SetThreadContext`로 이 조작된 컨텍스트를 다시 써넣는다.
5. **실행 재개**: `ResumeThread`를 호출하면 스레드가 깨어나 조작된 `EIP`/`RIP`, 즉 악성 이미지의 진입점부터 실행을 시작한다.

이 기법이 위험한 이유는, 프로세스를 만든 부모 정보(부모 프로세스 이름), 실행 파일 경로, 심지어 일부 EDR/AV가 확인하는 디스크 서명(원본 EXE 자체는 정상이므로 초기 실행 시 서명 검증을 통과)까지 모두 정상처럼 보이지만, 실제 메모리에서 실행되는 코드는 완전히 다르기 때문이다. 리버싱 관점에서는 "프로세스 이름을 믿지 말고 메모리 내용을 확인하라"는 원칙이 바로 이 기법 때문에 생겼다고 봐도 된다.

## 화면/코드에서 보이는 징후
- 코드에서 `CreateProcessA`/`CreateProcessW` 호출 시 다섯 번째 인자(`dwCreationFlags`)에 `CREATE_SUSPENDED`(0x00000004) 비트가 설정됨
- 바로 뒤이어 `NtUnmapViewOfSection` 또는 `ZwUnmapViewOfSection`(직접 임포트되지 않고 `GetProcAddress(GetModuleHandle("ntdll.dll"), "NtUnmapViewOfSection")`로 동적 해결하는 경우가 많음, REV-0129 참고) 호출
- `VirtualAllocEx` + `WriteProcessMemory` 조합으로 다른 프로세스 핸들에 데이터를 써넣는 코드
- `GetThreadContext`/`SetThreadContext` + `ResumeThread` 순서
- Process Hacker/Process Explorer 등으로 실행 중인 정상 프로세스를 보면, 메모리의 이미지 베이스 영역에서 PE 헤더를 읽었을 때 `SizeOfImage`, `AddressOfEntryPoint` 등이 디스크 파일과 다름

## 가장 먼저 할 것
1. 인젝터로 의심되는 바이너리의 Import Table 또는 문자열에서 `CreateProcess`, `NtUnmapViewOfSection`, `WriteProcessMemory`, `SetThreadContext`, `ResumeThread`가 함께 있는지 먼저 확인한다. 이 조합이 다 모여 있으면 프로세스 할로잉일 가능성이 매우 높다.
2. x64dbg에서 `CreateProcess` 호출 직후 대상 프로세스가 `CREATE_SUSPENDED`로 생성되는지 인자를 확인한다.

## 단계별 절차
**1) 인젝터 흐름 정적 분석**
- IDA에서 위 API들이 호출되는 함수를 찾아 순서대로 xref(`X`)를 따라간다. 특히 `WriteProcessMemory`에 넘기는 버퍼가 어디서 오는지(리소스 섹션에 박혀 있는 경우가 매우 흔하다, REV-0141 참고) 확인한다.
- `WriteProcessMemory`로 써넣는 데이터의 시작 바이트가 `MZ`(4D 5A)인지 확인하면 그것이 통째로 새 PE 이미지라는 강한 증거가 된다.

**2) 동적으로 할로잉 순간 관찰**
- x64dbg의 `Options → Preferences → Events`에서 "System Breakpoint" 및 자식 프로세스도 함께 디버깅할 수 있는 옵션(또는 `DebugActiveProcess`로 자식에 직접 붙기)을 준비한다.
- 인젝터 프로세스를 실행하고, `CreateProcess`가 리턴한 직후 대상 프로세스(피해자, victim)의 PID를 확인한 뒤 별도 x64dbg 인스턴스로 그 프로세스에 `Attach`한다(단, `CREATE_SUSPENDED`라 아직 실행되지 않은 상태이므로 붙어도 안전하다).
- 인젝터의 `NtUnmapViewOfSection`, `WriteProcessMemory`, `SetThreadContext` 호출에 브레이크포인트를 걸어 각 단계 전후로 대상 프로세스의 메모리 맵(`Alt+M`)이 어떻게 바뀌는지 비교한다.

**3) 최종 페이로드 덤프**
- `ResumeThread` 호출 직전, 대상 프로세스의 새로 매핑된 이미지 영역(원본 언매핑 후 다시 할당된 주소)을 메모리 맵에서 찾는다.
- 해당 영역을 덤프해 파일로 저장한다. 이때 메모리 상의 섹션 정렬(Virtual 정렬)과 디스크 파일의 정렬(Raw 정렬)이 다르므로, PE-bear 등으로 열었을 때 섹션 헤더의 `PointerToRawData`를 `VirtualAddress`와 맞춰 재정렬해야 정상적으로 디스어셈블되는 파일이 된다(이 재정렬 작업을 흔히 "unpacking/rebuilding"이라 부른다).
- 재구성한 파일을 IDA로 새로 열어 진짜 악성 페이로드를 분석한다.

## 명령어/단축키
- x64dbg: `Attach`(대상 프로세스에 붙기), `Alt+M`(메모리 맵), 우클릭 `Follow in Dump`, 우클릭 `Binary → Save To a File`(덤프)
- IDA: 임포트 검색(`Ctrl+Alt+F` 또는 `Alt+T`로 텍스트 검색), `X`(교차 참조로 호출 지점 확인)
- 브레이크포인트 대상 함수: `kernel32!CreateProcessW`, `ntdll!NtUnmapViewOfSection`, `kernel32!WriteProcessMemory`, `kernel32!SetThreadContext`, `kernel32!ResumeThread`

## 출력 해석
- `NtUnmapViewOfSection` 호출이 성공(리턴값 `STATUS_SUCCESS`, 0)하면 그 시점 이후 대상 프로세스의 원래 이미지 메모리는 더 이상 유효하지 않다. 이후 그 주소를 읽으면 접근 위반이 나거나 새로 매핑된 다른 내용이 보인다.
- 컨텍스트 조작 후 `SetThreadContext`가 성공했다면, 그 스레드가 재개될 때 `EIP`/`RIP`는 조작된 값에서 시작한다. 즉 원본 EXE의 진짜 진입점이 아니라 공격자가 지정한 주소에서 실행이 시작된다는 뜻이다.

## 흔한 실수
- 프로세스 이름과 아이콘, 파일 경로만 보고 "이건 정상 시스템 프로세스니까 안전하다"고 판단하는 것. 할로잉의 핵심이 바로 이 신뢰를 악용하는 것이다.
- `WriteProcessMemory`로 써넣는 데이터를 확인하지 않고 그냥 "메모리 조작 API를 쓰는구나" 정도로만 넘어가는 것. 실제 페이로드가 그 안에 있으므로 반드시 덤프해서 봐야 한다.
- 덤프한 메모리 이미지를 정렬 보정 없이 그대로 IDA에 로드해서 "디스어셈블이 이상하다"고 헷갈리는 것. 메모리 정렬(Virtual)과 파일 정렬(Raw)의 차이를 이해하고 섹션 헤더를 보정해야 한다.
- Reflective DLL Loading(REV-0567)과 혼동하는 것. 할로잉은 완전히 새로운 프로세스(EXE)를 만들어 그 안의 코드를 통째로 바꿔치기하는 기법이고, 리플렉티브 로딩은 DLL이 자기 자신을 메모리에 직접 매핑하는 기법으로 목적과 대상이 다르다.

## 막혔을 때 다음 체크
- 언매핑/재매핑 대신 DLL 자체가 스스로를 로드하는 방식이라면 → REV-0567(Reflective DLL Loading 개념 소개)을 확인한다.
- 대상 API 이름이 문자열로 안 보이고 해시나 오프셋 계산으로 찾는 것 같다면 → REV-0569(API Hashing 개념)를 본다.
- 덤프한 페이로드 안에서 실제 API 이름을 찾기 어려우면 → REV-0570(API Hashing 상수를 IDA/Ghidra에서 찾는 법)과 REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.

## 미니 예제
```c
STARTUPINFOA si = { sizeof(si) };
PROCESS_INFORMATION pi;
CreateProcessA("C:\\Windows\\System32\\svchost.exe", NULL, NULL, NULL,
    FALSE, CREATE_SUSPENDED, NULL, NULL, &si, &pi);

NtUnmapViewOfSection(pi.hProcess, imageBase); // 원본 이미지 비우기

LPVOID remoteImage = VirtualAllocEx(pi.hProcess, imageBase, payloadSize,
    MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
WriteProcessMemory(pi.hProcess, remoteImage, payloadBytes, payloadSize, NULL);

CONTEXT ctx = { CONTEXT_FULL };
GetThreadContext(pi.hThread, &ctx);
ctx.Eip = (DWORD)remoteImage + payloadEntryPointRVA; // 진입점 재지정
SetThreadContext(pi.hThread, &ctx);

ResumeThread(pi.hThread); // 악성 코드 실행 시작
```
이 코드는 정상 `svchost.exe`를 정지 상태로 띄운 뒤, 원본 이미지를 지우고 `payloadBytes`(악성 PE)를 그 자리에 써넣은 다음, 스레드의 `EIP`를 새 이미지의 진입점으로 바꿔서 실행을 재개한다. 작업 관리자에서는 여전히 `svchost.exe`로 보이지만 실제로는 `payloadBytes`가 실행되고 있다.

## 관련 글
- REV-0567 — Reflective DLL Loading 개념 소개
- REV-0569 — Import 함수를 런타임에 해시로 찾는 API Hashing 개념
- REV-0141 — Resource Section과 숨겨진 데이터 확인
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `CREATE_SUSPENDED`, `GetThreadContext`/`SetThreadContext`, `ResumeThread`의 시그니처와 동작은 Microsoft Learn Win32 API 공식 문서 기준이다.
- `NtUnmapViewOfSection`은 공식 문서화가 제한적인 ntdll 네이티브 API로, 다수의 공개 악성코드 분석 자료와 Windows 내부 구조 레퍼런스에서 프로세스 할로잉의 핵심 단계로 공통적으로 설명된다.
- 절차 세부 순서(언매핑 → 재매핑 → 컨텍스트 조작 → 재개)는 여러 공개 보안 리서치 자료에서 일관되게 확인되는 표준적 패턴이다(2026-09-08 기준 서술).
