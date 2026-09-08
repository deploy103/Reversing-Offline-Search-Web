---
id: REV-0507
title: "WinAPI 프로세스 정보 함수 사전: GetCurrentProcessId Module32First"
slug: "rev-0507-getcurrentprocessid-module32first"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["GetCurrentProcessId", "Module32First", "Module32Next", "CreateToolhelp32Snapshot", "MODULEENTRY32", "모듈 열거"]
aliases: ["겟커런트프로세스아이디", "모듈32퍼스트", "Toolhelp32 스냅샷", "프로세스 모듈 목록 함수"]
symptom_keywords: ["GetCurrentProcessId가 뭘 반환하는지 모르겠다", "Module32First로 뭘 찾는지 모르겠다", "로드된 DLL 목록을 도는 코드를 발견했다", "CreateToolhelp32Snapshot이 뭔지 모르겠다", "sbiedll나 분석 도구 DLL을 탐지하는 코드 같다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`GetCurrentProcessId`는 현재 프로세스의 PID를 얻는 가장 단순한 API이고, `Module32First`/`Module32Next`는 `CreateToolhelp32Snapshot`으로 찍은 스냅샷을 돌며 특정 프로세스에 로드된 모든 모듈(EXE/DLL)을 나열하는 함수로, 두 API가 함께 쓰이면 "이 프로세스가 자기 자신 혹은 다른 프로세스의 모듈 목록을 훑어보고 있다"는 뜻이며 샌드박스/분석도구 DLL 탐지나 후킹 대상 DLL 찾기 같은 목적일 가능성이 높다.

## 언제 검색해야 하나
- Import 목록에서 `Module32First`/`Module32Next`/`CreateToolhelp32Snapshot`을 발견하고 이 코드가 어떤 DLL 목록을 뒤지는지 알아내야 할 때
- `GetCurrentProcessId`의 반환값이 이후 `CreateToolhelp32Snapshot`이나 `OpenProcess`의 인자로 흘러가는 흐름을 추적해야 할 때
- 특정 모듈 이름(`sbiedll.dll`, `api_log.dll`, `dbghelp.dll` 등)과 문자열 비교를 반복하는 루프를 만나 이것이 모듈 열거 기반 탐지인지 확인하고 싶을 때
- `GetModuleHandle`/`EnumProcessModules`(REV-0520, REV-0521)와 무엇이 다른지 헷갈릴 때

## 핵심 개념

### GetCurrentProcessId
```c
DWORD GetCurrentProcessId(void);
```
인자 없이 현재 프로세스의 PID(`DWORD`)를 즉시 반환한다. 내부적으로 PEB의 `UniqueProcessId` 필드(또는 TEB의 `ClientId.UniqueProcess`)를 참조하는 매우 가벼운 호출이다. `GetCurrentProcess()`(의사 핸들 `-1`을 반환하는 별개 함수)와 이름이 비슷해 혼동하기 쉬우니 주의한다.

### CreateToolhelp32Snapshot + Module32First/Next
```c
HANDLE CreateToolhelp32Snapshot(
    DWORD dwFlags,     // TH32CS_SNAPMODULE 등, 무엇을 스냅샷할지
    DWORD th32ProcessID // 대상 프로세스 PID, 0이면 호출자 자신
);

BOOL Module32First(
    HANDLE          hSnapshot, // CreateToolhelp32Snapshot이 반환한 핸들
    LPMODULEENTRY32 lpme       // 채워질 MODULEENTRY32 구조체 주소(dwSize 필드 미리 설정 필요)
);

BOOL Module32Next(
    HANDLE          hSnapshot,
    LPMODULEENTRY32 lpme
);
```
`dwFlags`는 `TH32CS_SNAPMODULE`(0x8, 32비트 모듈), `TH32CS_SNAPMODULE32`(0x10, WOW64에서 32비트 모듈), `TH32CS_SNAPPROCESS`(0x2, 프로세스 목록) 등을 조합할 수 있다. `MODULEENTRY32` 구조체는 다음 핵심 필드를 가진다.
```c
typedef struct tagMODULEENTRY32 {
    DWORD   dwSize;         // 구조체 크기, Module32First 호출 전 반드시 설정
    DWORD   th32ModuleID;
    DWORD   th32ProcessID;
    DWORD   GlblcntUsage;
    DWORD   ProccntUsage;
    BYTE    *modBaseAddr;   // 모듈이 로드된 시작 주소(=HMODULE와 동일)
    DWORD   modBaseSize;    // 모듈 이미지 크기
    HMODULE hModule;
    char    szModule[MAX_MODULE_NAME32 + 1]; // 모듈 파일명(확장자 제외 가능)
    char    szExePath[MAX_PATH];             // 전체 경로
} MODULEENTRY32;
```
`Module32First`로 첫 항목을 얻은 뒤, `Module32Next`를 반복 호출해 더 이상 항목이 없을 때(`FALSE` 반환, `GetLastError() == ERROR_NO_MORE_FILES`)까지 순회하는 것이 표준 패턴이다.

### 왜 리버싱에서 중요한가
- 스냅샷 목록의 첫 항목(`Module32First`가 처음 채우는 항목)은 항상 EXE 자기 자신이며, `modBaseAddr`가 곧 이미지 베이스(REV-0118의 RVA 계산 기준점)다.
- 악성코드/프로텍터가 `szModule`을 `"SbieDll.dll"`(Sandboxie), `"api_log.dll"`, `"dbghelp.dll"`, `"x64dbg.dll"`류 이름과 비교하는 루프를 만들면, 이는 분석 환경/디버거 플러그인을 모듈 이름으로 탐지하는 기법이다.
- `GetModuleHandle`(REV-0520)이 이름을 알고 있을 때 즉시 핸들을 얻는 데 반해, `Module32First`/`Next`는 "이름을 모르는 상태에서 전체 목록을 나열"할 때 쓰인다는 점이 근본적인 차이다.

## 화면/코드에서 보이는 징후
```asm
call GetCurrentProcessId
push eax                      ; th32ProcessID
push 8                        ; TH32CS_SNAPMODULE
call CreateToolhelp32Snapshot
...
call Module32First
loop_top:
lea  eax, [ebp+me32.szModule]
push offset aSbiedllDll        ; "sbiedll.dll"
push eax
call _stricmp
test eax, eax
jz   detected
call Module32Next
test eax, eax
jnz  loop_top
```
- 반복문 안에 `Module32Next` 호출과 문자열 비교(`_stricmp`, `strcmp`, `lstrcmpi`)가 함께 있으면 전형적인 모듈 열거 탐지 패턴이다.
- `lpme.dwSize`에 `sizeof(MODULEENTRY32)`(0x224 부근)를 미리 세팅하는 코드가 `Module32First` 호출 직전에 보인다(이 값을 세팅하지 않으면 API가 실패한다).

## 가장 먼저 할 것
`Module32First`/`Module32Next`가 발견되면 먼저 루프 안에서 비교되는 문자열 상수(`szModule`과 비교되는 대상)부터 확인한다. 비교 대상 문자열이 곧 "이 프로그램이 찾고 있는 대상"이므로 분석 목적을 가장 빨리 파악할 수 있다.

## 단계별 절차
**1) IDA에서 문자열 비교 대상 확인**
`Module32Next` 루프 안의 `call`(strcmp류) 직전 인자로 들어가는 문자열 리터럴을 확인한다. Strings 창(`Shift+F12`)에서 관련 DLL 이름이 있는지 미리 훑어보면 빠르다.

**2) x64dbg로 동적 확인**
```text
bp Module32First
run
; RDX(x64)/[esp+8](x86)가 가리키는 MODULEENTRY32 버퍼를 Follow in Dump
; szModule 오프셋(약 +0x2C)에서 현재 순회 중인 모듈 이름을 눈으로 확인
```
`Ctrl+F9`로 한 번씩 빠져나오며 어떤 모듈 이름이 나열되는지 순서대로 관찰한다.

**3) 탐지 성공 분기 추적**
`stricmp`/`strcmp` 결과가 0(일치)일 때 어디로 점프하는지 따라가서, 탐지됐을 때 프로그램이 무엇을 하는지(종료, 다른 코드 경로, 잘못된 결과 계산) 확인한다.

## 명령어/단축키
- x64dbg: `bp CreateToolhelp32Snapshot`, `bp Module32First`, `bp Module32Next`, `Ctrl+F9`
- x64dbg: 버퍼 주소 우클릭 → `Follow in Dump`로 `MODULEENTRY32` 필드 직접 확인
- IDA: `Shift+F12`(Strings), `X`(xref)

## 출력 해석
- `Module32First`/`Module32Next`가 `FALSE`(0)를 반환하면 더 이상 순회할 모듈이 없다는 뜻이며, `GetLastError()`가 `ERROR_NO_MORE_FILES`(18)이면 정상 종료다.
- `modBaseAddr` 값이 IDA/PE-bear에서 본 Image Base와 일치하면 그 항목이 EXE 자기 자신이다.
- 문자열 비교가 대소문자를 구분하지 않는 `stricmp`/`lstrcmpiA`를 쓰는지, 구분하는 `strcmp`를 쓰는지에 따라 우회 난이도가 달라진다(대소문자 구분 비교라면 파일명 대소문자만 바꿔도 우회될 수 있다).

## 흔한 실수
- `dwSize` 필드를 세팅하지 않아서 `Module32First`가 실패하는 실제 버그 코드를 보고, 리버서 본인이 "이건 왜 실패하지?"라며 헷갈리는 것 — 원본 코드 자체의 버그일 수도 있으므로 반환값과 `GetLastError`를 항상 함께 확인한다.
- `GetCurrentProcessId`와 `GetCurrentProcess`(핸들이 아니라 PID를 반환하는 함수와, 의사 핸들 -1을 반환하는 함수)를 같은 것으로 착각하는 것.
- 자기 프로세스가 아니라 다른 프로세스(`th32ProcessID`가 0이 아닌 값)를 스냅샷하는 경우를 놓치는 것 — 이 경우 인젝션 대상 탐색이나 프로세스 후킹 목적일 수 있다.
- `TH32CS_SNAPMODULE`만 확인하고 `TH32CS_SNAPMODULE32`(WOW64 프로세스의 32비트 모듈 목록)를 함께 요청하지 않은 코드가 64비트 프로세스에서 32비트 대상 모듈을 놓친다는 점을 간과하는 것 — 대상 프로세스가 WOW64로 실행 중이면 두 플래그를 OR해서 요청해야 완전한 목록을 얻는다.
- `szModule`(파일명만)과 `szExePath`(전체 경로) 필드를 혼동해서, 짧은 이름만 비교하는 코드를 전체 경로까지 비교한다고 잘못 해석하는 것 — 두 필드는 서로 다른 오프셋에 저장되며 길이 제한도 다르다(`szModule`은 `MAX_MODULE_NAME32+1`, `szExePath`는 `MAX_PATH`).

## 막혔을 때 다음 체크
- 이름을 이미 알고 있는 모듈의 핸들만 빠르게 얻는 방식이 궁금하면 → REV-0520 WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle
- 더 현대적인 모듈 열거 API(`EnumProcessModules`)와 비교하고 싶다면 → REV-0521 WinAPI 모듈 함수 사전: EnumProcessModules GetModuleFileName
- 다른 프로세스를 열어 접근하려는 흐름이라면 → REV-0504 WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess

## 미니 예제
```c
DWORD pid = GetCurrentProcessId();
HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);
MODULEENTRY32 me32 = { .dwSize = sizeof(MODULEENTRY32) };
if (Module32First(hSnap, &me32)) {
    do {
        if (_stricmp(me32.szModule, "SbieDll.dll") == 0) {
            ExitProcess(1); // 샌드박스 DLL 탐지 시 종료
        }
    } while (Module32Next(hSnap, &me32));
}
```

## 관련 글
- REV-0520 — WinAPI 모듈 함수 사전: LoadLibraryEx FreeLibrary GetModuleHandle
- REV-0521 — WinAPI 모듈 함수 사전: EnumProcessModules GetModuleFileName
- REV-0504 — WinAPI 프로세스 함수 사전: OpenProcess TerminateProcess

## 출처/검증
- `GetCurrentProcessId`, `CreateToolhelp32Snapshot`, `Module32First`/`Module32Next`, `MODULEENTRY32` 구조체 필드는 Microsoft 공식 문서(learn.microsoft.com, "Toolhelp32Snapshot Functions") 기준이다(2026-09-08 확인).
- 모듈 이름 기반 샌드박스/분석 DLL 탐지 패턴은 일반적인 안티분석 관례 레퍼런스 기준이다.
