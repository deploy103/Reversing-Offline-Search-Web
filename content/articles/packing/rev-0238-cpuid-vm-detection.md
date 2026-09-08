---
id: REV-0238
title: "CPUID 기반 VM 탐지 기초"
slug: "rev-0238-cpuid-vm-detection"
category: "packing"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [x64dbg, GDB, IDA]
keywords:
  - CPUID VM detection
  - 안티VM 기초
  - hypervisor bit check
  - vendor string check
  - VMware detection
  - VirtualBox detection
  - sandbox evasion
  - anti-sandbox
  - 가상머신 탐지 패턴
aliases:
  - VM 탐지가 뭐임
  - 안티VM이 뭐임
  - VMware 탐지 우회
  - 샌드박스 우회 개념
symptom_keywords:
  - VMware에서 실행하면 프로그램이 다르게 동작함
  - VirtualBox에서 실행이 안됨
  - 하이퍼바이저 비트를 검사하는 코드가 있음
  - 벤더 문자열을 비교하는 코드가 있음
  - 레지스트리나 MAC주소를 검사하는 코드가 있음
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CPUID` 명령어 자체의 leaf/레지스터 동작은 `../assembly/rev-0086-cpuid.md`에서 다뤘고, 이 글은 그 위에서 실제 바이너리에서 **"VM 위에서 실행 중인지"를 판단하는 더 큰 그림의 패턴들**(하이퍼바이저 비트, 벤더 문자열, 그리고 CPUID 외의 다른 VM 흔적들과의 조합)을 다룬다 — 악성코드/프로텍터가 샌드박스 분석을 회피하기 위해 흔히 쓰는 1차 방어선이다.

## 언제 검색해야 하나
- 분석 대상 프로그램을 VMware/VirtualBox 안에서 실행했더니 실제 PC와 다르게 동작하거나 조용히 종료될 때
- `cpuid` 명령 뒤에 하이퍼바이저 비트나 벤더 문자열을 비교하는 코드를 발견했을 때, 그게 프로그램 전체 방어 전략에서 어떤 역할인지 궁금할 때
- 레지스트리 키, 서비스 이름, MAC 주소, 드라이버 파일명처럼 CPUID와 무관한 "VM 흔적"을 검사하는 코드를 함께 발견했을 때
- 샌드박스(자동 분석 시스템)에서 제출한 파일이 "무해함"으로 나왔는데 실제 PC에서는 다르게 동작한다는 보고를 접했을 때

## 핵심 개념

### CPUID는 VM 탐지의 여러 수단 중 하나
`CPUID`의 하이퍼바이저 비트(leaf 1, ECX bit 31)와 벤더 문자열(leaf 0x40000000) 검사는 가장 저비용이고 흔한 VM 탐지 방법이지만, 실제 악성코드/프로텍터는 이것 **하나만으로 끝내지 않고 여러 신호를 조합**해서 판단 정확도를 높이는 경우가 많다. `CPUID` 자체의 세부 동작은 REV-0086에서 이미 다뤘으므로, 여기서는 "그 결과가 더 큰 탐지 전략 안에서 어떻게 쓰이는지"에 집중한다.

### CPUID와 함께 흔히 결합되는 다른 VM 탐지 신호
| 신호 | 설명 |
|---|---|
| 레지스트리 키 (Windows) | `HKLM\HARDWARE\Description\System\SystemBiosVersion`, `HKLM\SYSTEM\...\Services\Disk\Enum` 등에서 `"VMWARE"`, `"VBOX"`, `"QEMU"` 문자열 검색 |
| MAC 주소 OUI | VMware(`00:05:69`, `00:0C:29`, `00:50:56`), VirtualBox(`08:00:27`) 등 가상화 제품이 사용하는 고정된 MAC 주소 접두사 |
| 프로세스/서비스 목록 | `vboxservice.exe`, `vmtoolsd.exe`, `VGAuthService.exe` 같은 게스트 확장 프로세스 존재 여부 |
| 드라이버/장치 파일 | `\\.\VBoxMiniRdrDN`, `vmci.sys` 등 가상화 전용 드라이버 파일 존재 여부 |
| 화면 해상도/메모리 크기 | 샌드박스는 흔히 기본값(예: 1024x768, 메모리 2~4GB)을 그대로 사용하는 경우가 많아 이를 의심 신호로 삼기도 함 |
| RDTSC + CPUID 타이밍 결합 | `CPUID`는 하이퍼바이저가 트랩해서 처리해야 하므로 실행 시간이 비정상적으로 느림 — 이를 `RDTSC`(REV-0237)로 측정해 이중으로 확인 |

**분석가 입장에서 중요한 점**: `CPUID` 체크 하나만 패치했다고 안심하면 안 되고, 근처(같은 함수 또는 인접한 초기화 루틴)에 레지스트리/MAC/프로세스 목록 검사가 더 있는지 함께 살펴야 한다.

### 어디서 흔히 발견되는가
- **프로그램 시작 직후(초기화 루틴)**: 실제 로직 실행 전 "환경 검증" 단계로 한 곳에 몰아서 여러 VM 탐지 로직을 순서대로 실행하는 경우가 많다.
- **패커/프로텍터 스텁**: 압축 해제나 복호화 루틴이 시작되기 전에, 분석 환경이면 아예 압축을 풀지 않거나 잘못된 키로 풀어 의도적으로 깨진 코드를 실행시키는 경우도 있다.
- **네트워크/C2 통신 직전**: 악성코드의 경우, 실제로 외부와 통신하기 직전에 마지막으로 한 번 더 환경을 검증하는 패턴도 흔하다.

## 화면/코드에서 보이는 징후
- `cpuid` 호출 뒤 하이퍼바이저 비트/벤더 문자열 비교(REV-0086 패턴)와 더불어, 근처에 레지스트리 API(`RegOpenKeyExA`, `RegQueryValueExA`) 호출이나 `GetAdaptersInfo`(MAC 주소 조회) 같은 API 호출이 섞여 있다.
- IDA Strings 창에 `"VMware"`, `"VBox"`, `"QEMU"`, `"Virtual"` 같은 문자열이 여러 곳에서 발견된다.
- 여러 개의 독립적인 체크 함수가 각각 `BOOL`을 반환하고, 이를 `||`(OR)로 묶어 "하나라도 참이면 VM"으로 판단하는 상위 함수가 있다.
- VMware/VirtualBox 안에서 실행할 때만 특정 메시지가 뜨거나 조용히 종료된다.

## 가장 먼저 할 것
1. `cpuid` 사용처를 REV-0086/REV-0238 방식으로 찾아 하이퍼바이저 비트/벤더 문자열 체크 여부를 확인한다.
2. 같은 함수 또는 그 호출자 근처에서 레지스트리/MAC/프로세스 목록을 검사하는 API 호출이 있는지 xref로 훑어본다.
3. 이 체크들을 모아서 최종 판단하는 "VM 여부 반환 함수"를 찾고, 그 반환값이 어디서 쓰이는지(어떤 분기로 이어지는지) 확인한다.

## 단계별 절차
1. Strings 창에서 `"VMware"`, `"VBox"`, `"QEMU"`, `"Xen"`, `"Virtual"`, `"Sandbox"` 같은 키워드를 검색해 관련 코드를 모두 찾는다.
2. 각 문자열의 xref를 따라가 어떤 함수에서 어떻게 비교하는지 확인한다.
3. `cpuid` 사용처도 함께 찾아 같은 파일/모듈 안에 있는지 확인한다.
4. 이 개별 체크 함수들을 호출하는 "종합 판단" 함수를 역추적한다(각 체크 함수를 호출하는 xref를 따라가면 보통 하나의 상위 함수로 모인다).
5. 종합 판단 함수의 반환값을 사용하는 분기를 찾아, "탐지됨" 처리(종료, 다른 로직 실행, 조용히 아무것도 안 함 등)를 확인한다.
6. 우회 실습(자신의 크랙미/CTF 문제에 한함)은 개별 체크를 하나씩 패치하기보다, 종합 판단 함수의 반환값 자체를 항상 "VM 아님"으로 고정하는 편이 효율적이다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창), `X`(Xrefs to), `F5`(디컴파일), `Ctrl+F`(Imports 탭에서 Reg*/GetAdaptersInfo 등 검색)
- x64dbg: 종합 판단 함수의 리턴 지점에 `F2` 브레이크포인트, `F9` 실행 후 `EAX` 확인
- GDB/Pwndbg: `break *0x함수_리턴주소`, `p $eax`

## 출력 해석
- VM 안에서 실행했을 때 종합 판단 함수의 반환값이 `1`(또는 `TRUE`)로 나오면 VM 탐지 로직이 정상적으로 작동 중인 것이다.
- 물리 PC(베어메탈)에서 실행했을 때 반환값이 `0`으로 나오면 비교 기준으로 삼을 수 있다 — 두 값을 비교해 어떤 개별 체크가 결과를 좌우하는지 특정할 수 있다.

## 흔한 실수
- `CPUID` 하나만 우회하고 레지스트리/MAC/프로세스 기반 체크를 놓치는 것 — VM 탐지는 여러 신호의 조합인 경우가 많다.
- 분석 환경을 VM에서 물리 PC로 옮기는 것만이 유일한 해법이라고 생각하는 것 — 실제로는 VM 설정(MAC 주소 변경, 레지스트리 값 정리, 프로세스 이름 변경)이나 코드 패치로도 대응 가능하다.
- Strings 창에서 `"VMware"` 같은 문자열을 발견했다고 무조건 안티VM이라고 단정하는 것 — 정상적인 하드웨어 호환성 코드(예: 드라이버가 실행 환경을 인식해 최적화)에서도 등장할 수 있으므로 주변 로직을 함께 확인해야 한다.

## 막혔을 때 다음 체크
- VM 안에서만 이상하게 동작하는데 원인을 못 찾겠다면 → 물리 PC 또는 VM 흔적을 최대한 지운 환경에서 다시 실행해 비교한다.
- `cpuid` 검색으로 아무것도 안 나온다면 → 레지스트리/MAC/프로세스 이름 기반 체크만 쓰는 경우일 수 있으니 Strings 창부터 다시 확인한다.
- 여러 체크가 뒤섞여 헷갈리면 → 타이밍 체크(REV-0237), 예외 기반 체크(REV-0239)도 같은 초기화 루틴 안에 있는지 확인한다.
- 정적으로 다 이해하기 번거로우면 → 동적 분석으로 전환해 실제 반환값을 직접 관찰한다(REV-0241).

## CTF 환경에서의 실전 팁
CTF 대회에서는 문제 출제자가 굳이 정교한 VM 탐지를 넣는 경우가 드물지만(대회 서버/채점 환경 자체가 가상화되어 있는 경우가 많아 너무 엄격한 체크는 문제 자체를 못 풀게 만들 수 있다), 리버싱 연습용으로 스스로 만든 크랙미나 상용 프로텍터 학습용 샘플에서는 이런 체크를 자주 접하게 된다. 분석 환경을 준비할 때부터 VMware/VirtualBox의 게스트 확장 도구(VMware Tools, Guest Additions)를 설치하지 않거나, MAC 주소와 레지스트리의 대표적인 VM 흔적을 미리 정리해두는 "VM 은폐(VM cloaking)" 준비를 해두면, 이런 종류의 1차 방어선에 걸리는 빈도를 크게 줄일 수 있다.

## 미니 예제
**예제 — CPUID + 레지스트리 조합 판단**
```c
BOOL check_cpuid_hypervisor(void) {
    int regs[4];
    __cpuid(regs, 1);
    return (regs[2] >> 31) & 1; // ECX bit 31
}

BOOL check_registry_vmware(void) {
    HKEY hKey;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE,
        "HARDWARE\\Description\\System", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        // SystemBiosVersion 값에 "VMWARE" 포함 여부 검사
    }
    return FALSE; // 예시 단순화
}

BOOL is_virtual_machine(void) {
    return check_cpuid_hypervisor() || check_registry_vmware();
}

int main() {
    if (is_virtual_machine()) {
        exit(1);
    }
    // 실제 로직
}
```

## 관련 글
- ../assembly/rev-0086-cpuid.md
- REV-0237 — RDTSC Time Check 안티디버깅
- REV-0241 — 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환

## 출처/검증
- `CPUID` 하이퍼바이저 비트/벤더 문자열: `../assembly/rev-0086-cpuid.md`(Intel SDM, Microsoft Hypervisor Top Level Functional Specification 기준) 참고.
- 레지스트리/MAC/프로세스 기반 VM 탐지 신호: 공개된 악성코드 분석 및 안티샌드박스 기법 교육 자료에서 공통적으로 다루는 표준 기법을 정리함(2026-09-08 검증).
