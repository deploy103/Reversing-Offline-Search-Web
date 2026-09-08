---
id: REV-0576
title: "가상머신 아티팩트(레지스트리/파일)로 VM 탐지하는 기법"
slug: "rev-0576-vm-artifact-detection"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, DIE]
keywords: ["VM 탐지", "VirtualBox 탐지", "VMware 탐지", "RegQueryValueExW", "SystemBiosVersion", "VBoxGuest", "안티VM", "레지스트리 아티팩트"]
aliases: ["가상머신 탐지 기법", "VM 아티팩트 탐지", "샌드박스 VM 판별", "VirtualBox VMware 흔적 탐지"]
symptom_keywords: ["프로그램이 VM에서만 다르게 동작한다", "VBOX 문자열이 보인다", "레지스트리에서 VirtualBox를 찾는 코드가 있다", "가상머신에서 실행하면 종료된다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
많은 크랙미/악성코드는 레지스트리 키 값이나 드라이버 파일 존재 여부처럼 가상머신(VirtualBox, VMware, QEMU, Hyper-V)이 남기는 고유한 "아티팩트(artifact)"를 조회해서 분석 환경인지 판단하며, `RegQueryValueExW`나 `GetFileAttributesW` 같은 API 호출과 그 인자로 쓰인 하드코딩 문자열을 찾으면 탐지 로직 전체를 빠르게 특정할 수 있다.

## 언제 검색해야 하나
- 프로그램을 물리 PC에서 실행하면 정상 동작하는데 VirtualBox/VMware 안에서 실행하면 종료되거나 다르게 동작할 때
- 문자열 목록(Strings)에서 `VBOX`, `VMWARE`, `VirtualBox`, `Oracle`, `innotek`, `qemu` 같은 키워드가 보일 때
- IDA에서 `RegOpenKeyExW`/`RegQueryValueExW` 임포트가 있고, 인자로 `SOFTWARE\\Oracle\\VirtualBox Guest Additions` 같은 레지스트리 경로 문자열이 들어갈 때
- `GetFileAttributesW`나 `CreateFileW`로 `C:\windows\system32\drivers\VBoxMouse.sys` 같은 특정 파일 경로를 확인하는 코드를 발견했을 때

## 핵심 개념
가상화 소프트웨어는 게스트 OS에 하드웨어를 가상으로 제공하기 위해 전용 드라이버(Guest Additions/VMware Tools)를 설치하고, 이 과정에서 레지스트리와 파일 시스템에 흔적을 남긴다. 이 흔적은 물리 PC에는 절대 존재하지 않으므로, 존재 여부만 확인해도 "지금 VM 안에서 실행 중인가"를 매우 높은 신뢰도로 판단할 수 있다. VM 탐지는 안티디버깅과 목적이 비슷하지만(분석 환경 회피), 확인하는 대상이 "디버거"가 아니라 "가상화 계층"이라는 점이 다르다.

**대표적인 레지스트리 아티팩트**
- `HKLM\HARDWARE\Description\System` 아래 `SystemBiosVersion`, `VideoBiosVersion`, `SystemManufacturer` 값에 `"VBOX"`, `"VMWARE"`, `"innotek"`, `"QEMU"` 문자열이 포함되어 있는지 확인
- `HKLM\SOFTWARE\Oracle\VirtualBox Guest Additions` 키 존재 여부(VirtualBox Guest Additions가 설치되어 있으면 존재)
- `HKLM\SOFTWARE\VMware, Inc.\VMware Tools` 키 존재 여부
- `HKLM\SYSTEM\ControlSet001\Services\VBoxGuest`, `VBoxMouse`, `VBoxSF`, `VBoxVideo`(VirtualBox 드라이버 서비스 등록 여부)
- `HKLM\SYSTEM\ControlSet001\Services\vmci`, `vmhgfs`, `vmmouse`, `vm3dmp`(VMware 드라이버 서비스 등록 여부)

**대표적인 파일 시스템 아티팩트**
- `C:\windows\system32\drivers\VBoxMouse.sys`, `VBoxGuest.sys`, `VBoxSF.sys`, `VBoxVideo.sys`(VirtualBox)
- `C:\windows\system32\drivers\vmmouse.sys`, `vmhgfs.sys`, `vm3dmp.sys`(VMware)
- `C:\windows\system32\vboxdisp.dll`, `vboxhook.dll`(VirtualBox 관련 DLL)

**기타 자주 쓰이는 신호**
- MAC 주소 OUI(제조사 식별) 접두사: VirtualBox는 `08:00:27`, VMware는 `00:0C:29` / `00:1C:14` / `00:50:56` / `00:05:69`로 시작하는 경우가 많다. `GetAdaptersInfo`나 `GetAdaptersAddresses`로 조회한 뒤 앞 3바이트를 비교한다.
- WMI 쿼리(`SELECT * FROM Win32_ComputerSystem`)의 `Manufacturer`/`Model` 필드가 `"VMware, Inc."`, `"innotek GmbH"`, `"Microsoft Corporation"`(Hyper-V) 등으로 나오는지 확인
- 실행 중인 프로세스 이름에 `vboxservice.exe`, `vboxtray.exe`, `vmtoolsd.exe`, `vmwaretray.exe`가 있는지 `CreateToolhelp32Snapshot` + `Process32First`/`Process32Next`로 순회하며 확인

**하이퍼바이저 비트(CPUID)와의 관계**: 레지스트리/파일 아티팩트 탐지는 CPUID 명령의 ECX 비트 31(하이퍼바이저 존재 여부, Hyper-V/VMware/VirtualBox 공통으로 1로 설정됨)을 확인하는 방식과 함께 쓰이는 경우가 많다. CPUID는 "가상화 계층이 있는가"만 알려주고 어떤 제품인지는 알려주지 않으므로, 어떤 벤더의 VM인지 특정하려면 결국 레지스트리/파일 아티팩트나 벤더 문자열(CPUID leaf `0x40000000`의 벤더 ID)까지 함께 확인해야 한다. 레지스트리/파일 아티팩트 쪽이 더 널리 쓰이는 이유는 커널 권한 없이 유저 모드 API만으로 조회 가능하고, 특정 제품(VirtualBox vs VMware)까지 구분해주기 때문이다.

**Hyper-V/컨테이너 환경 특유의 흔적**: Hyper-V 게스트는 `HKLM\SOFTWARE\Microsoft\Virtual Machine\Guest\Parameters` 키나 `vmicheartbeat`, `vmicvss` 같은 통합 서비스(Integration Services) 이름으로 식별되며, WSL2/Docker 컨테이너 환경은 별도로 `HKLM\SYSTEM\CurrentControlSet\Services\LxssManager` 같은 키나 환경변수 `WSL_DISTRO_NAME`으로 판별하는 경우도 있다. CTF에서는 VirtualBox/VMware가 압도적으로 많지만, 실무 악성코드 분석에서는 Hyper-V/클라우드 환경(Azure, AWS) 탐지 로직도 자주 등장하므로 레지스트리 경로 목록에 익숙해질수록 유리하다.

## 화면/코드에서 보이는 징후
- `RegOpenKeyExW` 호출 직후 `RegQueryValueExW`가 이어지고, 두 번째 인자(`lpValueName`)나 첫 번째 `RegOpenKeyExW` 인자(`lpSubKey`)로 레지스트리 경로 문자열이 들어감
- 조회한 문자열 버퍼에 대해 `wcsstr`/`StrStrIW` 같은 부분 문자열 검색 함수로 `"VBOX"`, `"VMWARE"`를 비교
- `GetFileAttributesW` 반환값을 `INVALID_FILE_ATTRIBUTES`(`0xFFFFFFFF`)와 비교해서 "파일이 존재하지 않으면 정상, 존재하면 VM"으로 분기
- 여러 개의 탐지 함수를 순서대로 호출한 뒤 결과를 OR로 합쳐 하나의 불리언 플래그로 만드는 패턴(레지스트리 체크 + 파일 체크 + MAC 체크를 한 번에 몰아서 수행)

## 가장 먼저 할 것
Strings(x64dbg의 Symbols 창이나 별도 strings 도구, IDA의 `Shift+F12`)로 바이너리 전체에서 `VBOX`, `VMWARE`, `VirtualBox`, `QEMU`, `innotek` 키워드를 먼저 검색한다. 문자열이 하나라도 나오면 그 문자열의 교차 참조(`X` 단축키)를 따라가서 어느 함수가 이 문자열을 쓰는지부터 확인한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- Strings 창에서 위 키워드로 검색하고, 발견된 각 문자열에 `X`(교차 참조)를 눌러 사용 위치를 찾는다.
- 해당 함수를 열어 `RegOpenKeyExW`/`RegQueryValueExW`/`GetFileAttributesW`/`CreateFileW` 중 어떤 API로 아티팩트를 조회하는지 확인한다.
- `F5`로 디컴파일하면 대개 `if (RegQueryValueExW(...) == ERROR_SUCCESS && wcsstr(buf, L"VBOX")) { is_vm = 1; }` 형태로 바로 읽힌다.

**2) 동적 분석(x64dbg)**
- `bp RegQueryValueExW`로 브레이크포인트를 걸고 실행한다.
- 브레이크포인트가 걸리면 2번째 인자(`lpValueName`, x64는 `RDX`)를 "Follow in Dump"해서 어떤 값 이름을 조회하는지 확인한다.
- 반환된 데이터 버퍼(3번째 인자가 가리키는 곳, x64는 `R8`)의 내용을 확인해 실제 조회 결과(예: BIOS 버전 문자열)를 본다.
- `GetFileAttributesW`도 같은 방식으로 `bp GetFileAttributesW` 후 첫 인자 문자열을 확인한다.

**3) 우회가 필요할 때**
- 분석 목적(CTF)이라면 탐지 로직이 세팅하는 플래그 변수(예: `is_vm`)를 찾아 조건 분기의 `jz`/`jnz`를 패치하거나, 애초에 물리 PC 또는 아티팩트를 제거/위장한 VM에서 분석하는 방법도 있다.
- VirtualBox라면 Guest Additions를 설치하지 않은 상태로 분석하거나, 레지스트리 키를 임시로 이름 변경해 아티팩트를 숨기는 방식도 실무에서 쓰인다(단, 이는 시스템 설정 변경이 필요하므로 스냅샷을 미리 떠 두는 것을 권장한다).

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창), `X`(교차 참조), `F5`(디컴파일), `Ctrl+F`(Imports 검색)
- x64dbg: `bp RegQueryValueExW`, `bp RegOpenKeyExW`, `bp GetFileAttributesW`, 인자 레지스터 우클릭 → "Follow in Dump"
- 레지스트리 직접 확인(분석 VM에서): `regedit`로 `HKLM\HARDWARE\Description\System` 값 확인

## 출력 해석
- `RegOpenKeyExW`가 `ERROR_SUCCESS`(0)를 반환하면 해당 키가 존재한다는 뜻이며, VM 전용 키(예: VirtualBox Guest Additions 키)라면 이 자체가 강한 VM 신호다.
- `GetFileAttributesW`가 `INVALID_FILE_ATTRIBUTES`가 아닌 값을 반환하면 해당 경로의 파일/폴더가 존재한다는 뜻이다.
- BIOS 버전 문자열에 `"VBOX"`가 포함되어 있으면 VirtualBox, `"VMware"`가 포함되어 있으면 VMware, `"American Megatrends"` 등 일반 제조사명만 있으면 물리 PC일 가능성이 높다.

## 흔한 실수
- 문자열 하나만 발견하고 바로 "VM 탐지 확정"이라고 단정하는 것 — 같은 문자열이 다른 목적(예: 설치 프로그램의 하드웨어 호환성 안내)으로 쓰였을 수도 있으므로 반드시 교차 참조로 실제 사용 문맥을 확인해야 한다.
- 레지스트리 경로 문자열이 여러 조각(예: `L"SOFTWARE\\"`와 `L"Oracle\\VirtualBox Guest Additions"`)으로 나뉘어 `wcscat`으로 합쳐지는 경우를 놓치는 것 — Strings 창에서 한 번에 안 보일 수 있으므로 조합 함수도 함께 확인한다.
- VM 탐지 로직을 안티디버깅과 혼동해서 `IsDebuggerPresent`만 우회하고 VM 체크는 그대로 두는 것 — 두 체크는 별개이므로 각각 확인해야 한다.
- 분석용 VM에 Guest Additions/VMware Tools를 설치한 채로 "이 프로그램은 VM 탐지가 없다"고 결론 내리는 것 — 애초에 아티팩트가 다 걸리는 상태이므로 오탐(정상 동작처럼 보임)이 발생할 수 있다.

## 막혔을 때 다음 체크
- VM 탐지 뒤에 이어지는 안티디버깅도 함께 있는지 → REV-0572(GetTickCount/QueryPerformanceCounter 시간측정), REV-0573(Sleep 남용) 참고
- Mutex 이름으로도 환경을 판별하는지 함께 확인 → REV-0574(Mutex 이름으로 중복 실행/샌드박스 회피 판단)
- 환경변수나 사용자명도 확인하는 복합 탐지인지 → REV-0575(환경변수/사용자명으로 분석 환경 탐지)
- 여러 안티분석 기법이 뒤섞여 있어 원인을 못 찾겠다면 → REV-0240(디버거에서 갑자기 종료될 때 체크리스트)의 체크리스트 순서를 참고한다.

## 미니 예제
IDA에서 다음과 같은 디컴파일 결과를 만났다고 하자.

```c
HKEY hKey;
if (RegOpenKeyExW(HKEY_LOCAL_MACHINE,
                   L"SOFTWARE\\Oracle\\VirtualBox Guest Additions",
                   0, KEY_READ, &hKey) == ERROR_SUCCESS)
{
    RegCloseKey(hKey);
    is_vm_detected = 1;
}
```

이 코드는 VirtualBox Guest Additions 설치 키가 존재하는지만 확인하며, 값(value)까지 읽지 않고 키가 열리는지(`ERROR_SUCCESS`)만 검사한다. `is_vm_detected` 변수의 교차 참조를 따라가면 이 값이 뒤에서 어떤 분기(예: 조기 종료, 가짜 성공 메시지 출력)에 쓰이는지 알 수 있고, 분석 목적이라면 이 변수가 항상 0이 되도록 x64dbg에서 값을 강제로 덮어쓰거나 조건 분기를 패치해 우회할 수 있다.

## 관련 글
- REV-0572 — GetTickCount와 QueryPerformanceCounter 시간측정 안티디버깅
- REV-0573 — Sleep 남용과 안티디버깅/안티샌드박스 기법
- REV-0574 — Mutex 이름으로 중복 실행 방지/샌드박스 회피 판단하기
- REV-0575 — 환경변수/사용자명으로 분석 환경을 탐지하는 기법
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0132 — PEB BeingDebugged 검사 이해

## 출처/검증
- `RegOpenKeyExW`/`RegQueryValueExW`/`GetFileAttributesW`의 함수 시그니처와 반환값 의미는 Microsoft Win32 API 공식 문서 기준이다.
- VirtualBox/VMware가 남기는 레지스트리 키·드라이버 파일·MAC 주소 OUI 목록은 공개된 안티VM/VM 탐지 관련 리버싱 레퍼런스와 각 가상화 제품의 Guest Additions/Tools 설치 문서에서 공통적으로 확인되는 항목을 정리한 것이다(2026-09-08 기준).
- 위 미니 예제 코드는 설명을 위해 구성한 예시이며 실제 특정 문제의 코드가 아니다.
