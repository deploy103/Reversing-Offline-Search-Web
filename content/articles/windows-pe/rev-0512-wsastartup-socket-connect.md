---
id: REV-0512
title: "WinAPI 네트워킹 함수 사전: WSAStartup socket connect"
slug: "rev-0512-wsastartup-socket-connect"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["WSAStartup", "socket", "connect", "sockaddr_in", "WinSock", "ws2_32.dll", "C2 IP 포트 추출"]
aliases: ["윈속 초기화 함수", "소켓 생성 함수", "커넥트 함수", "WSA스타트업"]
symptom_keywords: ["ws2_32.dll을 임포트하는데 뭘 하는지 모르겠다", "WSAStartup이 뭔지 모르겠다", "connect 인자에서 IP와 포트를 뽑아내고 싶다", "sockaddr_in 구조체가 뭔지 모르겠다", "C2 서버 주소를 찾고 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`WSAStartup`은 WinSock 라이브러리를 초기화하는 필수 첫 호출이고, `socket`은 통신용 소켓 핸들을 만들며, `connect`는 그 소켓을 특정 IP:포트에 연결하는 함수로, 세 API가 `ws2_32.dll` Import 목록에 함께 있으면 이 프로그램이 네트워크(대개 C2 서버)와 통신한다는 확실한 신호이며 `connect`에 넘어가는 `sockaddr_in` 구조체를 덤프해서 실제 IP/포트(IOC)를 추출하는 것이 분석의 첫걸음이다.

## 언제 검색해야 하나
- Import 목록에 `ws2_32.dll`이 있고 `WSAStartup`/`socket`/`connect`가 보여서 이 프로그램의 통신 목적지를 알아내야 할 때
- CTF나 악성코드 분석에서 "이 프로그램이 접속하는 서버 IP와 포트가 무엇인가"를 답해야 할 때
- `connect` 호출 직전 스택/레지스터에 있는 `sockaddr` 구조체를 어떻게 해석해야 IP/포트가 나오는지 모를 때
- `WSAStartup` 실패 시 나머지 네트워크 코드가 어떻게 되는지 확인해야 할 때

## 핵심 개념

### WSAStartup — 반드시 가장 먼저 호출됨
```c
int WSAStartup(
    WORD      wVersionRequested, // 1. 요청 WinSock 버전, MAKEWORD(2,2) = 0x0202가 사실상 표준
    LPWSADATA lpWSAData          // 2. 버전 정보 등이 채워질 WSADATA 구조체 주소
);
```
성공 시 `0`을 반환한다(다른 Win32 함수와 달리 `GetLastError`가 아니라 반환값 자체가 오류 코드다). 이 호출 없이 `socket`/`connect`를 쓰면 실패하므로, WinSock 관련 코드를 찾을 때 이 함수를 기준점으로 삼으면 빠르다.

### socket — 통신 핸들 생성
```c
SOCKET socket(
    int af,       // 1. 주소 체계, AF_INET(2)=IPv4, AF_INET6(23)=IPv6
    int type,     // 2. SOCK_STREAM(1)=TCP, SOCK_DGRAM(2)=UDP
    int protocol  // 3. IPPROTO_TCP(6), IPPROTO_UDP(17), 0이면 type에 맞는 기본값
);
```
실패 시 `INVALID_SOCKET`(`-1`, 즉 `0xFFFFFFFF`)를 반환한다. 대부분의 C2 통신은 `AF_INET, SOCK_STREAM, IPPROTO_TCP` 조합이다.

### connect — 목적지에 연결
```c
int connect(
    SOCKET         s,     // 1. socket()이 반환한 소켓
    const sockaddr *name, // 2. 목적지 주소가 담긴 구조체(대개 sockaddr_in으로 캐스팅해서 채움)
    int            namelen // 3. name 구조체의 크기(sizeof(sockaddr_in) = 16)
);
```
성공 시 `0`, 실패 시 `SOCKET_ERROR`(`-1`)를 반환하며 실패 원인은 `WSAGetLastError()`로 확인한다.

### sockaddr_in — IP와 포트가 담기는 실체
```c
struct sockaddr_in {
    short          sin_family; // AF_INET = 2
    u_short        sin_port;   // 포트, htons()로 네트워크 바이트오더(빅엔디안) 변환된 값
    struct in_addr sin_addr;   // 4바이트 IPv4 주소(빅엔디안 순서 그대로, 즉 문자열과 같은 순서)
    char           sin_zero[8];// 사용 안 함, 0으로 채움
};
```
`connect`의 두 번째 인자가 가리키는 메모리를 16바이트만 그대로 읽으면 이 구조체이며, IP/포트를 사람이 읽는 형태로 바꾸려면 다음을 알아야 한다.
- `sin_port`는 네트워크 바이트오더(빅엔디안)이므로 리틀엔디안 CPU에서 그대로 읽으면 바이트가 뒤집혀 보인다. 예를 들어 실제 포트가 `443`(0x01BB)이면 메모리에는 `BB 01`로 저장되어 있다.
- `sin_addr`(4바이트)은 애초에 사람이 읽는 "192.168.0.1" 표기와 같은 순서(빅엔디안, 네트워크 순서)로 저장되므로 그냥 4바이트를 순서대로 각각 십진수로 읽으면 된다.

## 화면/코드에서 보이는 징후
```asm
sub  esp, 190h            ; WSADATA용 스택 공간
push offset wsaData
push 202h                 ; MAKEWORD(2,2)
call WSAStartup
...
push 6                    ; IPPROTO_TCP
push 1                    ; SOCK_STREAM
push 2                    ; AF_INET
call socket
mov  [s], eax
...
mov  word ptr [sockaddr.sin_family], 2
mov  word ptr [sockaddr.sin_port], 5C11h   ; htons(0x115C) = 4444
mov  dword ptr [sockaddr.sin_addr], 0100A8C0h ; 192.168.0.1
push 10h
push offset sockaddr
push [s]
call connect
```
- `WSAStartup`, `socket`, `connect`가 순서대로 등장하며, `sockaddr` 구조체가 로컬 스택에 직접 채워지는 코드가 매우 흔하다(문자열이 아니라 4바이트/2바이트 상수 대입 형태라서 Strings 검색으로는 안 잡힌다).

## 가장 먼저 할 것
`connect` 호출을 발견하면 즉시 두 번째 인자(`sockaddr` 구조체 주소)로 브레이크포인트를 걸어 그 시점의 메모리 16바이트를 확인한다. IP/포트는 정적 문자열이 아니라 숫자 대입으로 만들어지는 경우가 많아 정적 분석만으로는 놓치기 쉽다.

## 단계별 절차
**1) Import에서 확인**
`ws2_32.dll`에 `WSAStartup`/`socket`/`connect`가 있는지 IDA Imports 창에서 확인한다.

**2) x64dbg로 connect에 브레이크포인트**
```text
bp connect
run
; x86: [esp+8] = name(sockaddr 주소), x64: R8 = name
; 그 주소를 Follow in Dump
```
**3) 16바이트 해석**
Dump 창에서 앞 2바이트는 `sin_family`(무시), 다음 2바이트는 `sin_port`(바이트 순서를 뒤집어서 십진수로), 다음 4바이트는 `sin_addr`(그대로 4개 옥텟으로) 읽는다.

**4) 정적 상수로도 대조**
IDA에서 `connect` 호출 직전 `sockaddr` 필드에 대입되는 `mov` 명령의 즉시값을 직접 계산해도 같은 결과를 얻을 수 있다(동적 실행 없이도 가능).

## 명령어/단축키
- x64dbg: `bp connect`, `bp socket`, `bp WSAStartup`, `Ctrl+F9`
- x64dbg: sockaddr 주소 우클릭 → `Follow in Dump`, Dump 창에서 `Hex` 뷰로 바이트 직접 확인
- IDA: 구조체 타입 적용(`Structures`에 `sockaddr_in` 추가), `X`(xref)

## 출력 해석
- `WSAStartup`이 `0`이 아닌 값을 반환하면 초기화 자체가 실패한 것이며, 이 경우 뒤따르는 `socket`/`connect` 호출은 대개 실패하거나 애초에 실행되지 않는다.
- `connect`가 `0`이면 연결 성공, `SOCKET_ERROR`(-1)이면 실패이며 `WSAGetLastError()`로 `WSAECONNREFUSED`(10061, 연결 거부) 등 원인을 확인한다.
- `sin_port` 예시: 메모리에서 `39 05`로 보이면 `0x0539` = 십진수 `1337`이 실제 포트다(바이트 순서를 뒤집어 읽어야 함).

## 흔한 실수
- `sin_port`를 리틀엔디안으로 그대로(뒤집지 않고) 읽어서 포트 번호를 잘못 계산하는 것 — 네트워크 바이트오더는 항상 빅엔디안이므로 x86/x64(리틀엔디안 CPU)에서는 바이트를 뒤집어야 한다.
- `sin_addr`는 반대로 이미 사람이 읽는 순서와 같으므로 뒤집으면 오히려 틀린 IP가 나온다 — 포트와 IP의 바이트오더 처리 방향이 다르다는 점을 헷갈리지 않는다.
- 도메인 이름으로 연결하는 코드(`gethostbyname`/`getaddrinfo` 이후 `connect`)에서는 `sockaddr`에 IP 상수가 바로 안 보이므로, 이 경우 DNS 조회 API 쪽 인자(도메인 문자열)를 먼저 확인해야 한다.

## 막혔을 때 다음 체크
- 연결 이후 실제로 주고받는 데이터를 보고 싶다면 → REV-0513 WinAPI 네트워킹 함수 사전: send recv closesocket
- 저수준 소켓이 아니라 HTTP 기반 통신이라면 → REV-0514 WinAPI 네트워킹 함수 사전: InternetOpen 계열(WinINet 기초)
- 파일 입출력과 조합된 통신(다운로드 후 파일 저장 등)이라면 → REV-0139 CreateFile ReadFile WriteFile 입력 데이터 추적

## 미니 예제
```c
WSADATA wsa;
WSAStartup(MAKEWORD(2, 2), &wsa);
SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
struct sockaddr_in addr;
addr.sin_family = AF_INET;
addr.sin_port = htons(4444);
addr.sin_addr.s_addr = inet_addr("192.168.0.1");
connect(s, (struct sockaddr *)&addr, sizeof(addr));
```
x64dbg에서 `bp connect` 후 `R8`(x64)이 가리키는 16바이트를 확인하면 `02 00 11 5C C0 A8 00 01 ...`처럼 보이며, `11 5C`를 뒤집어 `0x115C`=`4444`, `C0 A8 00 01`을 그대로 읽어 `192.168.0.1`을 얻는다.

## 관련 글
- REV-0513 — WinAPI 네트워킹 함수 사전: send recv closesocket
- REV-0514 — WinAPI 네트워킹 함수 사전: InternetOpen 계열(WinINet 기초)
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적

## 출처/검증
- `WSAStartup`/`socket`/`connect`의 시그니처와 `sockaddr_in` 구조체, 네트워크 바이트오더(`htons`) 규칙은 Microsoft 공식 문서(learn.microsoft.com, "Winsock functions" / "sockaddr_in structure") 및 관련 POSIX 소켓 표준 기준이다(2026-09-08 확인).
- `connect` 인자에서 C2 IP/포트를 추출하는 기법은 일반적인 악성코드 분석/CTF 리버싱 관례 레퍼런스 기준이다.
