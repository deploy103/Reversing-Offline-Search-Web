---
id: REV-0594
title: "리소스가 암호화되어 있어 아이콘/문자열이 안 보일 때"
slug: "rev-0594-encrypted-resources"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["Resource Hacker", "PE-bear", x64dbg]
keywords: ["RT_RCDATA", "FindResource", "LoadResource", "LockResource", ".rsrc 섹션", "리소스 암호화", "커스텀 리소스"]
aliases: ["resource hacker에서 아이콘이 안보임", "rsrc가 깨져있음", "리소스 문자열이 안열림"]
symptom_keywords: ["Resource Hacker로 열었는데 아이콘이 깨져 보인다", "버전 정보 문자열이 안 보인다", "rsrc 섹션에 알 수 없는 바이너리 데이터만 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Resource Hacker나 PE-bear의 리소스 뷰어로 아이콘/문자열을 열었는데 깨져 보이거나 "알 수 없는 데이터"로만 뜬다면, 그 리소스가 표준 `RT_ICON`/`RT_STRING` 형식이 아니라 개발자가 **직접 암호화하거나 커스텀 포맷으로 저장한 `RT_RCDATA`(원시 데이터) 리소스**일 가능성이 크며, 이런 경우 정적 리소스 뷰어로는 원본을 볼 수 없고 `LoadResource`/`LockResource` 호출 지점에 브레이크포인트를 걸어 **런타임에 복호화된 후의 메모리를 덤프**해야 한다.

## 언제 검색해야 하나
- Resource Hacker로 파일을 열었는데 아이콘 미리보기가 깨진 이미지로 나오거나 "이 리소스를 편집기로 열 수 없습니다" 류의 메시지가 뜰 때
- PE-bear의 Resources 탭에서 버전 정보(`VERSIONINFO`)나 문자열 테이블을 열었는데 사람이 읽을 수 없는 바이트만 보일 때
- 실행 파일을 실제로 실행하면 정상적인 아이콘/메시지가 화면에 나타나는데, 정적으로 리소스를 열면 이상하게 보일 때(런타임 복호화가 있다는 강한 신호)

## 핵심 개념
PE의 `.rsrc` 섹션은 트리 구조(타입 → 이름/ID → 언어)로 리소스를 저장하며, 각 리소스는 `RT_ICON`, `RT_BITMAP`, `RT_STRING`, `RT_VERSION`, `RT_MANIFEST`처럼 표준 타입으로 등록되면 Resource Hacker 같은 도구가 각 타입에 맞는 포맷(BMP/ICO 헤더, UTF-16 문자열 테이블 등)으로 해석해서 보여준다.

그런데 개발자가 리소스를 표준 API(`LoadIcon`, `LoadString` 등)로 그대로 쓰지 않고, `RT_RCDATA`(정해진 포맷이 없는 원시 바이너리 데이터, ID나 이름으로만 구분)로 등록한 뒤 자기만의 방식으로 암호화/인코딩해서 저장해두고, 실행 시점에 다음과 같은 순서로 직접 복호화해서 쓰는 경우가 있다.

1. `FindResource(hModule, lpName, lpType)`로 리소스 정보 핸들을 찾는다.
2. `LoadResource(hModule, hResInfo)`로 리소스 데이터를 담은 전역 메모리 핸들을 얻는다.
3. `LockResource(hGlobal)`로 실제 데이터에 대한 포인터를 얻는다.
4. `SizeofResource(hModule, hResInfo)`로 크기를 얻는다.
5. 이렇게 얻은 원시 바이트를 **자체 복호화 루틴**(XOR, RC4, 커스텀 알고리즘 등)에 통과시켜 실제 아이콘 이미지나 문자열, 설정 데이터로 변환한다.

이 경우 디스크에 저장된 `.rsrc` 섹션의 원본 바이트는 애초에 암호화된 상태이므로, Resource Hacker나 PE-bear가 아무리 잘 파싱해도 "깨진 데이터"로 보이는 것이 오히려 정상이다. 진짜 내용을 보려면 정적 리소스 뷰어가 아니라 **동적으로 복호화가 끝난 시점의 메모리**를 확인해야 한다.

## 화면/코드에서 보이는 징후
- Resource Hacker에서 아이콘 트리는 보이는데 미리보기 이미지가 깨져 있거나 "지원하지 않는 형식"이라고 뜸
- PE-bear Resources 탭에서 `RT_RCDATA` 타입 아래 이름 모를 리소스가 여러 개 있고, 헥스 덤프로 보면 규칙성 없는 바이트로 가득함
- IDA Imports 목록에 `FindResourceA/W`, `LoadResource`, `LockResource`, `SizeofResource`가 있고, 이를 호출한 직후 별도의 루프(XOR 등)를 도는 함수가 존재
- 프로그램을 실제로 실행하면 아이콘/메시지가 정상적으로 보임(즉 데이터 자체는 살아있고 손상된 게 아니라 암호화된 것)

## 가장 먼저 할 것
IDA Imports 창(REV-0119)에서 `FindResource`, `LoadResource`, `LockResource` 계열 API가 임포트되어 있는지 확인한다. 있다면 정적 리소스 뷰어를 더 붙잡고 있지 말고, x64dbg로 넘어가 이 API들에 브레이크포인트를 걸 준비를 한다.

## 단계별 절차
**1) 리소스 로딩 API에 브레이크포인트**
- x64dbg에서 대상 파일을 연다.
- `Symbols` 탭에서 `LockResource`(또는 `LoadResource`)를 찾아 우클릭 → `Toggle Breakpoint`로 브레이크포인트를 건다.
- `F9`로 실행해 해당 API 호출 지점까지 진행한다.

**2) LockResource 반환값(포인터) 확인**
- `LockResource`는 리소스 데이터를 가리키는 포인터를 반환한다(x64에서는 `RAX`, x86 stdcall에서는 `EAX`). 함수가 반환하는 시점까지 `F8`(Step Over) 또는 `Ctrl+F9`(Run to Return)로 진행해 이 값을 확인한다.
- 이 포인터를 Dump 창(`Ctrl+G`로 주소 이동)에서 열어 아직 암호화된 원시 바이트 상태를 확인해둔다.

**3) 복호화 루틴을 지나 실제 데이터 확인**
- `LockResource` 이후 그 포인터를 인자로 받아 순회하며 바이트를 변형하는 루프(복호화 루틴)를 찾아 `F8`로 지나간다.
- 복호화가 끝난 뒤 같은 메모리 영역(또는 새로 할당된 버퍼)을 다시 Dump 창에서 확인하면, 이제는 유효한 BMP/ICO 헤더(`42 4D`나 아이콘 디렉터리 구조)나 사람이 읽을 수 있는 문자열이 보여야 한다.

**4) 복호화된 데이터 메모리 덤프로 저장**
- Dump 창에서 해당 범위를 드래그로 선택한 뒤 우클릭 → `Binary → Save to a File`로 저장하면, 복호화된 순수 데이터만 별도 파일로 뽑아낼 수 있다.
- 이미지 데이터라면 적절한 헤더를 앞에 붙여(BMP/ICO 포맷 규격에 맞게) 이미지 뷰어로 열어 확인한다.

## 명령어/단축키
```text
x64dbg: Symbols 탭에서 LockResource 찾기 → 우클릭 Toggle Breakpoint
x64dbg: F9(실행), F8(Step Over), Ctrl+F9(Run to Return)
x64dbg: Dump 창에서 우클릭 → Binary → Save to a File
```

## 출력 해석
- `LockResource` 직후 덤프에서 규칙성 없는 바이트가 보이면 아직 복호화 전 상태이므로 정상이다(원본 `.rsrc` 데이터와 동일할 것이다).
- 복호화 루틴을 지난 뒤 덤프에서 `42 4D`(BMP), 아이콘 디렉터리 구조, 또는 읽을 수 있는 UTF-16 문자열이 보이면 성공적으로 원본 데이터에 도달한 것이다.
- 복호화 루틴을 지나도 여전히 무작위 바이트라면, 아직 완전한 복호화가 안 끝났거나(다단계 암호화) 다른 버퍼에 결과를 쓰는 함수를 놓쳤을 수 있으므로 호출 스택을 한 단계 더 따라간다.

## 흔한 실수
- `.rsrc` 섹션이 깨져 있다고 파일이 손상됐다고 오해하고 분석을 포기하는 것 — 실제로 실행하면 정상 작동한다면 손상이 아니라 의도된 암호화다.
- Resource Hacker로 계속 다른 뷰 모드를 시도하며 시간을 쓰는 것 — 표준 리소스 타입이 아니라 `RT_RCDATA`로 저장된 커스텀 데이터는 애초에 정적 리소스 뷰어가 해석할 방법이 없다.
- `LoadResource`/`LockResource`에 브레이크포인트를 걸었는데 여러 번 호출되는 경우, 원하는 리소스(아이콘 등)를 로드하는 호출이 아닌 다른 호출에서 멈춰 헷갈리는 것 — 이때는 `FindResource` 호출 시점의 인자(리소스 ID/이름)를 먼저 확인해서 원하는 리소스를 로드하는 호출만 골라 스텝한다.

## 막혔을 때 다음 체크
- 리소스 섹션 구조 자체가 헷갈리면 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 먼저 읽는다.
- 어떤 API가 호출되는지는 알겠는데 그 인자/반환값 규칙이 헷갈리면 → REV-0122/REV-0123(호출 규약)을 참고한다.
- 복호화 루틴 자체가 암호 알고리즘처럼 보이면 → REV-0140(Crypt API BCrypt API 흔적 찾기)을 참고해 표준 암호 API를 쓰는지부터 확인한다.

## 미니 예제
IDA에서 다음과 같은 함수를 봤다고 하자.

```c
HRSRC hRes = FindResourceW(hModule, MAKEINTRESOURCE(101), RT_RCDATA);
HGLOBAL hGlobal = LoadResource(hModule, hRes);
BYTE* pData = (BYTE*)LockResource(hGlobal);
DWORD size = SizeofResource(hModule, hRes);
for (DWORD i = 0; i < size; i++)
    pData[i] ^= 0x5A;  // 단순 XOR 복호화
```

x64dbg에서 `LockResource` 반환 직후 `pData`가 가리키는 메모리를 보면 XOR로 뒤섞인 바이트가 보인다. 이 `for` 루프를 `F8`로 다 지나간 뒤 같은 주소를 다시 보면, 매 바이트가 `0x5A`와 XOR되어 원래의 BMP 아이콘 데이터로 복원된 것을 확인할 수 있다. 이 시점의 메모리를 파일로 덤프하면 정상적인 이미지 뷰어로 열어볼 수 있는 아이콘 파일이 된다.

## 관련 글
- REV-0141 — Resource Section과 숨겨진 데이터 확인
- REV-0140 — Crypt API BCrypt API 흔적 찾기
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0138 — Windows API 이름으로 기능 추측하는 법

## 출처/검증
- `.rsrc` 섹션의 타입/이름/언어 3단 트리 구조와 `RT_ICON`/`RT_RCDATA` 등 표준 리소스 타입 정의는 Microsoft PE/COFF 형식 및 Win32 리소스 공식 문서 기준.
- `FindResource`/`LoadResource`/`LockResource`/`SizeofResource` API 시그니처와 동작 순서는 Microsoft Learn Win32 API 공식 문서 기준.
