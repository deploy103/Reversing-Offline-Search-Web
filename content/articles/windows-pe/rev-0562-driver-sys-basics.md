---
id: REV-0562
title: "드라이버(.sys) 파일을 만났을 때 최소 대응"
slug: "rev-0562-driver-sys-basics"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, WinDbg]
keywords: ["DriverEntry", "DRIVER_OBJECT", "IRP", "IMAGE_SUBSYSTEM_NATIVE", "커널 드라이버", "IoCreateDevice"]
aliases: ["sys 파일 분석", "커널 드라이버 리버싱 시작", "driverentry란", "irp 메이저 함수"]
symptom_keywords: [".sys 확장자 파일을 IDA로 열었더니 subsystem이 native로 나옴", "드라이버를 실행하려다 블루스크린이 걱정됨", "irp_mj_device_control이 뭔지 모름", "커널 모드 코드를 처음 봄"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.sys` 드라이버 파일을 만나면 가장 먼저 할 일은 **절대로 호스트 PC에서 직접 로드/실행하지 않는 것**이며, IDA/Ghidra로 정적 분석을 시작하되 진입점은 `DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath)`이고 실제 동작은 `DriverObject->MajorFunction[]` 배열에 등록된 IRP(I/O Request Packet) 디스패치 루틴들 안에 있다는 것만 알아도 절반은 시작한 것이다.

## 언제 검색해야 하나
- 확장자가 `.sys`인 파일을 처음 마주쳐서 어디서부터 손대야 할지 모를 때
- IDA로 열었더니 `Subsystem` 필드가 `IMAGE_SUBSYSTEM_NATIVE`(1)로 나와서 일반 EXE/DLL과 뭐가 다른지 궁금할 때
- `DriverEntry`라는 함수 이름이 보이는데 이게 일반 `main`/`WinMain`과 어떻게 다른지 궁금할 때
- `IRP_MJ_DEVICE_CONTROL`, `IoCreateDevice`, `IoCreateSymbolicLink` 같은 함수/상수가 보이는데 의미를 모를 때
- 드라이버를 실제로 로드해서 동적 분석을 해도 안전한지, 어떤 준비가 필요한지 궁금할 때

## 핵심 개념

### 가장 먼저: 안전 원칙부터
드라이버는 **커널 모드(Ring 0)**에서 실행된다. 사용자 모드 프로그램과 달리 드라이버 코드의 버그나 악의적 동작은 크래시가 나면 곧바로 BSOD(블루스크린)로 이어지고, 최악의 경우 파일시스템이나 부팅 자체가 손상될 수 있다. 그래서 `.sys` 파일은 다음 원칙을 지킨다.
- 실제 로드는 **스냅샷을 찍어둔 격리 VM**에서만 한다(호스트 PC 절대 금지).
- 정적 분석(IDA/Ghidra로 디스어셈블만 보는 것)은 위험하지 않다 — 파일을 읽기만 하는 것은 실행이 아니다.
- 동적 분석이 꼭 필요하면 커널 디버거(WinDbg)를 VM에 연결한 상태로 진행하고, 언제든 롤백할 수 있게 스냅샷을 미리 찍어둔다.

### DriverEntry: 커널 모드의 진입점
```c
NTSTATUS DriverEntry(
    _In_ PDRIVER_OBJECT  DriverObject,
    _In_ PUNICODE_STRING RegistryPath
);
```
일반 EXE의 `main`/`WinMain`(REV-0121, REV-0565)에 대응하는 커널 드라이버의 진입점이다. `DriverObject`는 이 드라이버 자신을 나타내는 구조체이고, `RegistryPath`는 이 드라이버가 등록된 레지스트리 서비스 키 경로다. `DriverEntry`가 하는 가장 중요한 일은 **`DriverObject->MajorFunction[]` 배열에 자신의 디스패치 함수들을 등록하는 것**이다.

```c
DriverObject->MajorFunction[IRP_MJ_CREATE]         = MyDispatchCreate;
DriverObject->MajorFunction[IRP_MJ_CLOSE]           = MyDispatchClose;
DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL]  = MyDispatchIoctl;
DriverObject->DriverUnload                          = MyDriverUnload;
```
`MajorFunction`은 배열이며, 인덱스가 곧 IRP 종류(`IRP_MJ_CREATE`=0, `IRP_MJ_CLOSE`=2, `IRP_MJ_READ`=3, `IRP_MJ_WRITE`=4, `IRP_MJ_DEVICE_CONTROL`=14 등)다. 사용자 모드에서 `CreateFile`, `ReadFile`, `WriteFile`, `DeviceIoControl`을 이 드라이버가 만든 디바이스에 대해 호출하면, 그 요청이 IRP(I/O Request Packet)로 포장되어 대응하는 `MajorFunction[]` 슬롯의 함수가 호출된다.

### IRP_MJ_DEVICE_CONTROL과 IOCTL 코드
가장 자주 분석하게 되는 것은 `IRP_MJ_DEVICE_CONTROL`이다. 사용자 모드에서 `DeviceIoControl(hDevice, dwIoControlCode, ...)`을 호출하면, 이 `dwIoControlCode`(IOCTL 코드)가 커널의 디스패치 함수로 전달되고, 드라이버는 보통 이 코드 값을 기준으로 거대한 `switch`문을 돌며 동작을 분기한다. 이 IOCTL 코드와 분기 로직이 드라이버의 실제 기능(파일 숨김, 안티치트 검사, 커널 메모리 읽기/쓰기 등)을 결정하는 핵심이다.

### 디바이스 객체와 심볼릭 링크
드라이버는 사용자 모드에서 접근 가능한 이름을 만들기 위해 보통 다음 두 함수를 함께 호출한다.
```c
IoCreateDevice(DriverObject, 0, &DeviceName, FILE_DEVICE_UNKNOWN, 0, FALSE, &DeviceObject);
IoCreateSymbolicLink(&SymlinkName, &DeviceName);
```
`DeviceName`은 보통 `\Device\MyDriver` 같은 커널 네임스페이스 경로이고, `SymlinkName`은 `\??\MyDriver`(사용자 모드에서는 `\\.\MyDriver`로 접근) 같은 심볼릭 링크다. 정적 분석 시 이 두 문자열을 찾으면 "사용자 모드 프로그램이 이 드라이버와 통신할 때 쓰는 핸들 이름"을 바로 알 수 있고, 이것으로 이 드라이버와 짝을 이루는 사용자 모드 EXE/DLL을 역으로 찾아낼 수 있다.

### 서브시스템과 링커 설정
드라이버는 `IMAGE_OPTIONAL_HEADER.Subsystem`이 보통 `IMAGE_SUBSYSTEM_NATIVE`(1)로 설정되며, 진입점 이름도 링커 옵션(`/ENTRY:DriverEntry`, `/SUBSYSTEM:NATIVE`)으로 명시적으로 지정된다. 일부 오래된 드라이버는 `IMAGE_SUBSYSTEM_WINDOWS_CUI`(3)로 빌드되기도 하므로 Subsystem 값만으로 100% 단정하기보다는 Import Table에 `ntoskrnl.exe`, `hal.dll` 같은 커널 전용 모듈이 있는지 함께 확인한다(REV-0564 참고).

## 화면/코드에서 보이는 징후
- IDA로 파일을 열었을 때 진입점 함수 이름이 자동으로 `DriverEntry`로 인식되거나, 시그니처가 `(PDRIVER_OBJECT, PUNICODE_STRING)` 두 개 인자로 보임
- Import Table에 `ntoskrnl.exe`(`IoCreateDevice`, `IoCreateSymbolicLink`, `ExAllocatePoolWithTag` 등)가 있음
- `.rdata`에서 `\Device\...`, `\DosDevices\...`, `\??\...` 형태의 유니코드 문자열이 보임
- 특정 함수 안에 이상하게 많은 분기를 가진 `switch`문이 있고, 각 case가 상수 IOCTL 코드(예: `0x222000` 형태의 값)와 비교되는 패턴이 보임

## 가장 먼저 할 것
IDA로 정적 분석부터 시작한다. `DriverEntry`를 찾고, 거기서 `MajorFunction[]` 배열에 어떤 함수들이 등록되는지 확인한다. `IRP_MJ_DEVICE_CONTROL`에 등록된 함수를 찾으면 IOCTL 분기 로직으로 이 드라이버의 실제 기능을 파악할 수 있다. 절대로 이 시점에 파일을 직접 로드/설치하지 않는다.

## 단계별 절차

**1) 서브시스템/헤더로 커널 드라이버인지 1차 확인**
`Subsystem` 필드와 Import Table의 `ntoskrnl.exe` 여부로 확인한다.

**2) DriverEntry 찾기**
진입점(`AddressOfEntryPoint`)이 곧 `DriverEntry`인 경우가 대부분이다. IDA가 자동 인식 못 하면 시그니처(두 개 인자, `NTSTATUS` 리턴)로 수동 식별한다.

**3) MajorFunction 배열 등록 추적**
`DriverEntry` 안에서 `DriverObject`(첫 번째 인자) 구조체 필드에 함수 포인터를 대입하는 코드를 찾는다. WDK 헤더(`ntddk.h`)의 `DRIVER_OBJECT` 구조체 정의를 IDA에 로드(Local Types 또는 구조체 임포트)하면 필드 이름이 자동으로 붙어 훨씬 읽기 쉬워진다.

**4) 관심 있는 디스패치 함수부터 분석**
보통 `IRP_MJ_DEVICE_CONTROL`(IOCTL 처리)이 가장 많은 정보를 담고 있다. `switch`문의 각 IOCTL 상수값을 기록해가며 case별로 무슨 동작을 하는지 정리한다.

**5) 디바이스/심볼릭 링크 이름으로 사용자 모드 카운터파트 찾기**
문자열에서 발견한 `\\.\장치이름`을 실제로 여는 사용자 모드 EXE/DLL이 있는지(같은 배포 패키지 안에서) 찾아, 두 파일을 함께 분석한다.

**6) 동적 분석이 꼭 필요하면 격리 VM + WinDbg**
```text
호스트가 아닌 스냅샷 VM에서:
bcdedit /set testsigning on   (테스트 서명 허용, 재부팅 필요)
WinDbg를 커널 디버깅 모드로 대상 VM에 연결
sc.exe create / start 로 드라이버 로드 후 분석
문제 발생 시 즉시 스냅샷 롤백
```

## 명령어/단축키
```text
IDA: 진입점 자동 이동(Alt+진입점 아이콘) → DriverEntry 여부 확인
IDA: Local Types 창에서 ntddk.h 기반 구조체(DRIVER_OBJECT 등) 임포트 후
     구조체 필드 자동 이름 붙이기 적용
WinDbg: 커널 디버깅 연결 후 lm 명령으로 로드된 드라이버 목록 확인
bcdedit /set testsigning on / off   테스트 서명 모드 전환(VM 안에서만!)
```

## 출력 해석
- `MajorFunction[IRP_MJ_DEVICE_CONTROL]`에 등록된 함수 안에서 IOCTL 상수가 많을수록 이 드라이버가 다양한 기능을 사용자 모드에 노출하고 있다는 뜻
- IOCTL 코드는 `CTL_CODE(DeviceType, Function, Method, Access)` 매크로로 조립되므로, 상수값을 이 매크로 규칙으로 역분해하면 `DeviceType`/`Method`(버퍼링 방식) 등을 유추할 수 있다
- `DriverObject->DriverUnload`가 `NULL`로 남아 있으면 이 드라이버는 언로드를 지원하지 않는다는 뜻 — 강제로 내리려면 재부팅이 필요할 수 있다

## 흔한 실수
- 호기심에 `.sys` 파일을 호스트 PC에서 직접 `sc.exe create`로 로드해보는 것 — 크래시 시 바로 블루스크린으로 이어질 수 있다. 반드시 스냅샷 VM에서만 시도한다.
- `DriverEntry`를 일반 `main`처럼 "여기서부터 끝까지 순차 실행된다"고 오해하는 것 — 실제 동작 로직은 대부분 나중에 IRP가 들어올 때 호출되는 `MajorFunction[]` 콜백들 안에 있고, `DriverEntry` 자체는 등록만 하고 빠르게 리턴한다.
- IOCTL 코드 상수를 그냥 매직넘버로 치부하고 넘어가는 것 — `CTL_CODE` 매크로로 분해하면 의미 있는 정보(버퍼 전달 방식 등)를 얻을 수 있다.
- 커널 구조체(`DRIVER_OBJECT`, `DEVICE_OBJECT`, `IRP` 등)를 IDA에 로드하지 않고 오프셋 숫자만 보면서 분석해 필드 의미를 계속 헷갈리는 것.

## 막혔을 때 다음 체크
- 서비스(사용자 모드) exe와 드라이버가 어떻게 다른지 헷갈리면 → [REV-0561 서비스(Windows Service) 실행 파일 분석 기초](./rev-0561-windows-service-exe.md)
- 콘솔/GUI/네이티브 서브시스템 구분이 헷갈리면 → [REV-0564 콘솔 프로그램과 GUI 프로그램 서브시스템 차이](./rev-0564-subsystem-console-gui.md)
- 체크섬이 안 맞아 드라이버 로드가 실패하는 경우 → [REV-0557 PE 체크섬(Checksum) 검증과 리버싱 의미](./rev-0557-pe-checksum.md)
- 진입점 구조 전반이 궁금하면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)

## 미니 예제
`monitor.sys`라는 알 수 없는 드라이버 파일을 받았다고 하자.

```text
1) IDA로 로드. Optional Header Subsystem = IMAGE_SUBSYSTEM_NATIVE(1) 확인.
   Imports에 ntoskrnl.exe!IoCreateDevice, IoCreateSymbolicLink 확인 → 커널 드라이버 확정.

2) 진입점(DriverEntry)에서:
   IoCreateDevice(..., &DeviceName="\Device\Monitor", ...)
   IoCreateSymbolicLink(&"\DosDevices\Monitor", &DeviceName)
   DriverObject->MajorFunction[IRP_MJ_CREATE]        = sub_14001000
   DriverObject->MajorFunction[IRP_MJ_CLOSE]          = sub_14001000
   DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = sub_14001200

3) sub_14001200 분석: switch(IoControlCode) 안에
   case 0x222004: ... (프로세스 목록 읽기로 추정되는 로직)
   case 0x222008: ... (메모리 읽기로 추정되는 로직)

4) 문자열 "\\.\Monitor"를 여는 사용자 모드 EXE가 같은 배포 패키지에 있는지 확인,
   있다면 그 EXE의 DeviceIoControl 호출부와 대조해서 IOCTL 값-기능 매핑을 완성.

5) 동적 확인이 필요하면 스냅샷을 찍어둔 VM에서만 로드/테스트.
```

## 관련 글
- REV-0561 — 서비스(Windows Service) 실행 파일 분석 기초
- REV-0564 — 콘솔 프로그램과 GUI 프로그램 서브시스템 차이
- REV-0557 — PE 체크섬(Checksum) 검증과 리버싱 의미
- REV-0121 — Entry Point와 WinMain 찾기

## 출처/검증
- `DriverEntry`, `DRIVER_OBJECT`, `MajorFunction` 배열, `IRP_MJ_*` 상수, `IoCreateDevice`/`IoCreateSymbolicLink` API: Microsoft Learn "Windows Driver Kit (WDK)" 및 "Writing a WDM Driver" 공식 문서 기준 (2026-09-08 검증).
- `CTL_CODE` 매크로와 IOCTL 코드 구성 방식: Microsoft Learn "Defining I/O Control Codes" 공식 문서 기준.
- 커널 드라이버 분석 시 격리 VM/스냅샷/테스트 서명 모드(`bcdedit /set testsigning on`) 권장 절차: Microsoft 공식 드라이버 개발/디버깅 문서 및 일반적인 안전한 리버싱 실무 관행에 기반한 설명.
