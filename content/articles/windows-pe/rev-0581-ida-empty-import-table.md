---
id: REV-0581
title: "IDA에서 PE를 열었는데 Import Table이 비어있을 때"
slug: "rev-0581-ida-empty-import-table"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, DIE, PE-bear, x64dbg]
keywords: ["Import Table 비어있음", "IMAGE_IMPORT_DESCRIPTOR", "IAT 재구성", "Scylla", "패킹된 PE", "API Hashing"]
aliases: ["IDA Imports 탭이 비어있다", "Import table empty IDA", "임포트 테이블이 안 보임"]
symptom_keywords: ["IDA Imports 탭에 아무것도 없다", "임포트가 kernel32 몇 개뿐이다", "패킹된 것 같은데 API가 안 보인다", "덤프한 파일에 임포트가 없다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA Imports 탭이 비어 있거나 몇 개뿐이면 대부분 IDA 버그가 아니라 패킹/API Hashing/IAT 미복구/헤더 손상 중 하나이며, DIE로 먼저 패커 여부를 확인하는 것이 가장 빠른 진단 경로다.

## 진단 먼저: 왜 비어 보이는가
IDA Imports 탭이 완전히 비어 있거나 `kernel32.dll`의 `LoadLibraryA`/`GetProcAddress` 몇 개만 보인다면, 십중팔구 다음 네 가지 중 하나다. 순서대로 확인하면 원인을 빠르게 좁힐 수 있다.

1. **패킹된 실행 파일** — 원본 PE가 UPX 등으로 패킹되어 있고, 지금 IDA에 보이는 것은 언패킹 스텁의 임포트뿐이다. 실제 프로그램이 쓰는 API들은 압축 해제 후 런타임에 스스로 IAT를 채운다.
2. **API Hashing / 동적 해석** — 프로그램이 애초에 Import Table을 거의 쓰지 않고, 함수 이름을 해시값으로 만들어 실행 중에 `GetProcAddress`로 직접 찾는다(REV-0569 참고). 이 경우 "비어있음"은 버그가 아니라 의도된 설계다.
3. **메모리 덤프 후 IAT 미복구** — 언패킹 후 메모리에서 덤프한 파일이라면, 원래 Import Table이 있던 자리가 실제 함수 주소(VA)로 이미 치환되어 있어서 표준 Import Directory 구조가 깨져 있는 상태다.
4. **손상되거나 비표준적인 PE 헤더** — Optional Header의 Data Directory 1번(Import Table) 항목의 RVA/Size가 잘못되었거나, `NumberOfRvaAndSizes`가 비정상적으로 작아 IDA가 Import Directory 자체를 못 찾는 경우다.

## 언제 검색해야 하나
- IDA로 PE를 열었는데 Imports 탭에 함수가 몇 개 없거나 아예 없을 때
- Strings에는 정상적인 API 이름이나 문자열이 보이는데 Imports 탭과 안 맞을 때
- 덤프한(unpacked memory dump) 파일을 IDA로 열었더니 임포트가 다 사라졌을 때
- DIE(Detect It Easy)로 열었을 때 패커 시그니처가 뜨는데 IDA 분석은 그대로 진행했을 때

## 핵심 개념
Import Table은 `IMAGE_OPTIONAL_HEADER`의 `DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT]`(인덱스 1)이 가리키는 위치에 `IMAGE_IMPORT_DESCRIPTOR` 배열로 존재하며, 각 항목은 DLL 이름과 그 DLL에서 가져올 함수 목록(Import Name Table/Import Address Table)을 가리킨다. IDA는 로드 시 이 구조를 파싱해 Imports 탭을 채우는데, 이 구조 자체가 실질적으로 텅 비어 있거나(패킹/해싱) 파싱이 실패하면(헤더 손상) 탭이 비게 된다. 즉 "Imports 탭이 비었다"는 것은 IDA의 버그가 아니라, 대부분 원본 PE의 실제 상태를 그대로 반영한 것이다.

## 화면/코드에서 보이는 징후
- Imports 탭에 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress`, `VirtualAlloc`, `VirtualProtect` 등 소수의 "로더용" 함수만 보임 — 전형적인 패커 스텁 패턴
- 엔트리 포인트 근처에 `pushad`/`popad`(x86) 또는 다수의 레지스터를 보존하는 프롤로그와 함께 큰 루프(압축 해제 루틴)가 있음
- DIE로 열면 "UPX", "Themida", "VMProtect" 등 패커/프로텍터 시그니처가 표시됨
- 함수 내부에 해시 상수(`0x6A4ABC5B` 같은 특이한 32/64비트 상수)와 문자열 순회 루프가 있고, 그 결과를 `GetProcAddress`에 넘기는 패턴이 있음(API Hashing)

## 가장 먼저 할 것
파일을 IDA에 로드하기 전에(또는 로드한 채로) **Detect It Easy(DIE)**로 먼저 열어 패커/컴파일러 시그니처를 확인한다. "Nothing found" + 컴파일러만 표시되면 4번(헤더 손상) 가능성이 높고, 패커 이름이 뜨면 1번이 거의 확실하다.

## 단계별 절차
**1) 패킹이 의심될 때**
- DIE 결과에서 패커 이름을 확인하고, UPX처럼 알려진 패커라면 `upx -d` 명령으로 먼저 언패킹을 시도한다(공식 UPX 도구 기준).
- 알려지지 않은 커스텀 패커라면 x64dbg로 실행 후 OEP(Original Entry Point, 압축 해제가 끝나고 원본 코드로 넘어가는 지점)를 수동으로 찾아야 한다. `ESP`가 스택 프레임에서 크게 바뀌는 지점, 또는 큰 루프가 끝나고 멀리 점프(`jmp far`)하는 지점을 단서로 삼는다.
- OEP를 찾았다면 그 지점에서 메모리를 덤프하고, x64dbg의 **Scylla** 플러그인(메뉴 → Plugins → Scylla)으로 IAT를 재구성한다. Scylla는 프로세스 메모리를 스캔해 각 IAT 슬롯의 함수 주소를 실제 DLL 이름/함수 이름으로 되돌려 새 Import Table을 만들어준다.

**2) API Hashing이 의심될 때**
- 해시 상수와 순회 루프가 보이면 이는 정상 설계이므로 "복구"할 게 아니라 "해석"해야 한다. REV-0569(API Hashing 개념)와 REV-0570(해시 상수를 IDA/Ghidra에서 찾는 법)을 참고해 각 해시가 어떤 API에 대응하는지 하나씩 계산한다.

**3) 덤프 파일의 IAT가 깨진 것으로 보일 때**
- 원본 프로세스가 아직 살아있다면 x64dbg로 다시 붙여서(Scylla의 "Attach to process" 기능) IAT를 재구성한다.
- 이미 파일만 남아있다면, Import Directory RVA/Size를 PE-bear로 직접 열어 값이 0인지, 아니면 잘못된 위치를 가리키는지 확인한다.

**4) 헤더 자체가 손상된 것으로 보일 때**
- PE-bear나 HxD로 Optional Header의 `DataDirectory[1]`(Import Table, 오프셋은 32/64비트에 따라 다름)의 RVA/Size 필드를 직접 확인한다. 값이 `0x00000000`이면 원본부터 Import Table이 없는 것(정상일 수도 있음, 예: 순수 셸코드를 억지로 PE로 감싼 경우), 값이 있는데 섹션 범위를 벗어난다면 헤더가 수동으로 손상/난독화된 것이다.
- IDA에서 File → Load file → Reload the input file with different settings로 다시 파싱을 시도하거나, 필요하면 PE 헤더를 수동으로 고쳐 다시 로드한다.

## 명령어/단축키
- DIE: 파일 드래그 후 좌측 상단 결과 확인, "Deep scan" 버튼으로 정밀 탐지
- x64dbg: Plugins → Scylla(IAT 재구성), OEP 탐색 시 `Ctrl+F9`(함수 끝까지 실행), 하드웨어 브레이크포인트로 `VirtualProtect`/`VirtualAlloc`에 걸어 압축 해제 완료 시점 포착
- IDA: `Ctrl+F`(Imports 검색), `Shift+F12`(Strings로 해시 상수/DLL 이름 흔적 탐색)
- 명령줄: `upx -d packed.exe -o unpacked.exe`(UPX로 패킹된 경우만 해당)

## 출력 해석
- Scylla로 IAT를 재구성한 뒤 "Get Imports" 결과에 함수 이름이 정상적으로 나오면(예: `kernel32.dll!CreateFileW`) 성공한 것이며, `???`나 `Invalid`로 표시되는 항목이 있으면 그 슬롯의 주소가 실제 API 진입점이 아니거나(스텁을 거쳐가는 경우) OEP 시점이 아직 이르다는 뜻이다.
- Import Directory RVA/Size가 둘 다 0이면 원본 PE 자체가 정적 링크 위주로 빌드되어 임포트가 거의 없는 경우일 수도 있으니 패닉하지 말고 Export Table이나 다른 섹션도 함께 확인한다.

## 흔한 실수
- 패킹된 스텁의 임포트(`LoadLibraryA`, `GetProcAddress`)만 보고 "이 프로그램은 파일도 안 열고 레지스트리도 안 건드린다"고 성급히 결론 내리는 것 — 언패킹 전 상태를 원본으로 착각하는 실수다.
- Scylla로 IAT를 재구성할 때 OEP를 잘못 지정해서(압축 해제가 덜 끝난 시점) 일부 API 주소가 여전히 스텁 코드를 가리키는 채로 저장하는 것.
- API Hashing 패턴을 "Import Table이 깨졌다"고 오인해서 억지로 복구를 시도하는 것 — 애초에 복구할 표준 Import Table이 없는 정상 설계다.
- IDA가 자동으로 인식 못한 것을 "파일이 손상됐다"고 바로 단정하는 것 — DIE로 먼저 패커 여부를 확인하는 습관이 시간을 크게 아껴준다.

## 막혔을 때 다음 체크
- 패커 종류 자체를 못 찾겠다면 → REV-0126(Detect It Easy로 컴파일러 패커 확인)을 다시 확인한다.
- OEP를 어떻게 찾는지 막막하다면 → REV-0127(x64dbg로 EXE 첫 분석 시작)의 기본 흐름부터 다시 훑는다.
- API Hashing 상수 계산이 막힌다면 → REV-0570(API Hashing 상수를 IDA/Ghidra에서 찾는 법) 참고

## 미니 예제
```
DIE 결과: "UPX(3.96)[NRV,brute]"
→ upx -d packed.exe -o unpacked.exe
→ unpacked.exe를 IDA로 다시 열면 Imports 탭에 kernel32/user32/advapi32 등
  정상적인 함수 목록이 채워진다.
```
반대로 DIE에서 "Nothing found *"만 나오고 컴파일러 정보도 애매하다면 헤더 손상(4번) 쪽을 먼저 의심한다.

## 관련 글
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0569 — Import 함수를 런타임에 해시로 찾는 API Hashing 개념
- REV-0570 — API Hashing 상수를 IDA/Ghidra에서 찾는 법
- REV-0119 — Import Table에서 중요한 API 찾기

## 출처/검증
- `IMAGE_IMPORT_DESCRIPTOR`와 Import Directory(`DataDirectory[1]`) 구조는 Microsoft PE Format 공식 문서 기준이다.
- UPX 언패킹 명령(`upx -d`)은 UPX 공식 프로젝트 사용법 기준이다.
- Scylla를 이용한 IAT 재구성 절차는 x64dbg에 번들된 Scylla 플러그인의 일반적인 사용법을 기준으로 서술했다(2026-09-08 기준).
