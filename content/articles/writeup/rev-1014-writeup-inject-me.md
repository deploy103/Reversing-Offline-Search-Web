---
id: REV-1014
title: "[Write-up] Inject ME!!!"
slug: "rev-1014-writeup-inject-me"
category: "writeup"
difficulty: "basic"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA]
keywords: ["dreamhack Inject ME", "드림핵 Inject ME", "Inject Me 풀이", "prob_rev.dll"]
aliases: ["Inject ME 못풀겠음", "dreamhack inject me flag", "인젝트 미 드림핵"]
symptom_keywords: ["드림핵 Inject ME DllMain 분석 어떻게 해야 할지 모르겠음", "GetModuleFileNameA PathFindFileNameA dreamhack.exe 비교가 뭔지 모르겠음"]
source_ids: ["SRC-DREAMHACK-WARGAME", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Inject ME!!!는 `prob_rev.dll`이라는 64비트 Windows DLL을 분석해서 "이 DLL을 로드한 프로세스의 실행 파일명이 정확히 dreamhack.exe여야만" 플래그 생성 로직이 실행되는 조건을 찾아내고, 그 조건을 만족시키는 이름의 로더 프로그램을 직접 만들어 DLL을 로드시켜 플래그를 얻는 문제다.

## 언제 검색해야 하나
- 받은 파일이 `.exe`가 아니라 `.dll`이라서 어떻게 실행해야 할지부터 막막할 때
- IDA에서 `DllEntryPoint`(또는 `DllMain`)를 열었는데 `fdwReason` 값에 따라 분기하는 구조를 처음 봐서 어디부터 따라가야 할지 모를 때
- `GetModuleFileNameA`와 `PathFindFileNameA`를 연달아 호출하고, 그 결과를 특정 문자열과 `strncmp`로 비교하는 코드를 발견했지만 왜 이런 검사를 하는지 이해가 안 될 때

## 핵심 개념
DLL은 실행 파일(EXE)과 달리 그 자체로 더블클릭해서 실행할 수 없고, 반드시 어떤 프로세스에 로드(적재)되어야 코드가 동작한다. Windows에서 DLL이 프로세스에 로드/해제될 때마다 자동으로 호출되는 진입점이 `DllMain`이며, 이때 전달되는 `fdwReason` 인자가 `DLL_PROCESS_ATTACH`(값 1)이면 "이 DLL이 방금 어떤 프로세스에 처음 붙었다"는 뜻이다(REV-0566 참고). Inject ME!!!의 `prob_rev.dll`은 바로 이 `DLL_PROCESS_ATTACH` 분기에서 내부 검증 함수를 호출하도록 만들어져 있다.

이 검증 함수의 핵심 로직은 "이름 검사"다. `GetModuleFileNameA`로 현재 프로세스의 실행 파일 전체 경로를 얻고, `PathFindFileNameA`로 그 경로에서 파일명만 잘라낸 뒤, 이 파일명을 `strncmp`로 문자열 `"dreamhack.exe"`와 비교한다. 즉 이 DLL은 "나를 로드한 프로그램의 이름이 정확히 dreamhack.exe일 때만" 다음 단계로 넘어간다. 이름이 일치하면 그 파일명 문자열 자체를 키 재료로 사용해 XOR와 회전(ROL) 연산을 반복 수행하고, 그 결과를 하드코딩된 정수 배열과 다시 XOR해서 최종 플래그 문자열을 만든 뒤 `MessageBoxA`로 화면에 띄운다. 결국 이 문제는 코드 자체를 바꾸지 않고, "이 DLL을 로드하는 실행 파일의 이름"이라는 외부 조건 하나만 맞춰주면 풀리는 구조다.

## 화면/코드에서 보이는 징후
- 배포 파일이 `.dll` 확장자이고, 그냥 실행(더블클릭)해도 아무 반응이 없음(DLL은 단독 실행 불가)
- IDA에서 `DllEntryPoint`를 열면 `if (fdwReason == 1)` 형태의 분기와 그 안에서 이어지는 서브함수 호출들이 보임
- 함수 주소가 `0x180000000`대로 시작하는 것으로 보아 64비트 PE로 로드 베이스가 잡혀 있음(비-ASLR 고정 베이스 또는 IDA의 기본 로드 주소)
- 검증 함수 안에 `GetModuleFileNameA`, `PathFindFileNameA`, `strncmp("dreamhack.exe", ...)` 호출이 순서대로 보임
- 조건 통과 후 XOR/ROL 반복 연산과 `MessageBoxA` 호출이 뒤따름

## 가장 먼저 할 것
IDA에서 Imports 탭을 열어 `GetModuleFileNameA`, `PathFindFileNameA`, `MessageBoxA` 같은 API를 먼저 찾고, 각각의 Xref를 따라가 이 API들을 실제로 호출하는 함수 하나로 모인다는 것을 확인한다. 이 함수가 바로 이 문제의 핵심 검증 함수이며, `DllEntryPoint`에서부터 이 함수까지 이어지는 호출 체인을 먼저 그려보는 것이 첫 단계다.

## 단계별 절차
1. IDA로 `prob_rev.dll`을 열고 `DllEntryPoint`(또는 `DllMain`)를 F5로 디컴파일해 `fdwReason == 1` 분기를 확인한다.
2. 그 분기에서 호출되는 서브함수들을 하나씩 따라 들어가 최종적으로 `GetModuleFileNameA`/`PathFindFileNameA`/`strncmp`가 모두 나오는 함수를 찾는다.
3. 비교 대상 문자열이 정확히 `"dreamhack.exe"`인지 확인한다.
4. 조건을 만족한 뒤 실행되는 XOR/ROL 반복 로직과 하드코딩된 정수 배열의 위치를 확인해 둔다(직접 역산하지 않고도 조건만 맞추면 프로그램이 스스로 플래그를 만들어 보여준다는 점이 이 문제의 핵심이므로, 굳이 이 연산을 손으로 재현할 필요는 없다).
5. `LoadLibrary`만 호출하는 최소한의 C 로더 프로그램을 작성한다.
6. 이 로더를 컴파일한 결과물의 파일명을 정확히 `dreamhack.exe`로 지정한다.
7. `dreamhack.exe`를 실행해 `prob_rev.dll`을 같은 폴더에 두고 로드시키면, 이름 검사를 통과해 `MessageBoxA`로 플래그가 화면에 나타난다.

## 명령어/단축키
```c
// loader.c - 파일명을 반드시 dreamhack.exe로 저장해서 컴파일해야 한다
#include <windows.h>
int main() {
    LoadLibraryA("prob_rev.dll");
    return 0;
}
```
```text
cl loader.c /Fe:dreamhack.exe
```
IDA: Imports 탭에서 API 더블클릭 → Ctrl+X(Xref)로 호출 지점 추적, F5로 디컴파일.

## 출력 해석
`dreamhack.exe`를 실행하면 별도의 콘솔 출력 없이 Windows 메시지박스(`MessageBoxA`) 창이 뜨고, 그 안에 플래그 문자열이 표시된다. 메시지박스가 뜨지 않는다면 파일명이 정확히 일치하지 않았거나(대소문자, 확장자 포함 여부 확인), `prob_rev.dll`이 로더와 같은 디렉터리에 없어서 `LoadLibraryA`가 실패했을 가능성이 높다.

## 흔한 실수
- DLL을 직접 더블클릭해서 실행하려고 시도하는 것 — DLL은 그 자체로 실행할 수 없고 반드시 다른 프로세스가 로드해야 한다.
- 로더 프로그램의 소스 파일 이름과 최종 빌드된 실행 파일 이름을 혼동하는 것 — 검사 대상은 컴파일된 결과물(exe)의 파일명이지 소스 코드 파일명이 아니다.
- `strncmp` 비교에서 대소문자나 확장자 포함 여부를 놓쳐 이름을 살짝 다르게 짓는 것(`Dreamhack.exe`, `dreamhack` 등).
- XOR/ROL로 플래그를 만드는 연산을 굳이 손으로 역산하려고 시도하는 것 — 조건만 맞추면 프로그램이 알아서 계산해서 보여주므로 불필요한 작업이다.

## 막혔을 때 다음 체크
- `DllMain`/`DllEntryPoint`의 `fdwReason` 분기 구조 자체가 헷갈리면 → REV-0566 DllMain에서 실행되는 코드가 있을 때 주의점
- `LoadLibrary`/`GetProcAddress` 같은 동적 API 해석이 처음이라면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석
- DLL 분석을 어디서부터 시작해야 할지 전체적으로 감이 안 잡히면 → REV-0135 DLL 문제 분석 시작하기
- Reflective DLL Loading처럼 DLL을 파일 없이 메모리에서 로드하는 기법이 궁금하면 → REV-0567 Reflective DLL Loading 개념 소개

## 미니 예제
검증 함수의 핵심 흐름을 의사코드로 재구성하면 다음과 같다.
```c
void OnProcessAttach() {
    char path[272];
    GetModuleFileNameA(NULL, path, sizeof(path));
    char *name = PathFindFileNameA(path);
    if (strncmp(name, "dreamhack.exe", 13) == 0) {
        // name 문자열을 키 재료로 XOR/ROL 반복 후
        // 하드코딩된 배열과 다시 XOR하여 flag 생성
        MessageBoxA(NULL, flag, "flag", MB_OK);
    }
}
```
이 구조를 보면 알 수 있듯, 공격자가 직접 계산해야 하는 것은 "XOR/ROL 상수"가 아니라 "이 DLL을 로드하는 실행 파일의 이름"뿐이다.

## 관련 글
- REV-0566 — DllMain에서 실행되는 코드가 있을 때 주의점
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0135 — DLL 문제 분석 시작하기
- REV-0567 — Reflective DLL Loading 개념 소개

## 출처/검증
- DLL 파일명(`prob_rev.dll`), `DllEntryPoint`의 `fdwReason` 분기, `GetModuleFileNameA`/`PathFindFileNameA`/`strncmp("dreamhack.exe", ...)` 검증 구조, XOR/ROL 기반 플래그 생성 로직, `MessageBoxA` 출력, 그리고 `LoadLibrary`로 로드하는 최소 로더를 만들어 파일명을 `dreamhack.exe`로 지정해 풀었다는 최종 풀이 방법은 velog 블로그 글 "[Dreamhack] Inject Me!!!"(https://velog.io/@mm0ck3r/Dreamhack-Inject-Me)를 참고해 본 문서에서 새로운 문장과 구조로 재서술했다.
- 함수 주소가 `0x180000000`대로 나타난다는 점에서 64비트 PE(DLL)로 판단했으며, 이는 원문에 기술된 레지스터 표기(rcx, rbp 등)와도 일치한다.
- 2026-09-10 기준으로 위 velog 글이 접근 가능함을 확인했다.
