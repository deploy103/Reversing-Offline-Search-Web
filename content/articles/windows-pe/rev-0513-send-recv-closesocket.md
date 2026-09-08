---
id: REV-0513
title: "WinAPI 네트워킹 함수 사전: send recv closesocket"
slug: "rev-0513-send-recv-closesocket"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["send", "recv", "closesocket", "WinSock", "네트워크 데이터 가로채기", "C2 명령 수신"]
aliases: ["센드 리시브 함수", "소켓 닫기 함수", "send recv 인자", "네트워크 송수신 API"]
symptom_keywords: ["send로 뭘 보내는지 확인하고 싶다", "recv로 받은 데이터를 가로채고 싶다", "closesocket이 언제 호출되는지 궁금하다", "네트워크로 주고받는 평문 데이터를 보고 싶다", "C2 명령을 확인하고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`send`는 이미 연결된 소켓으로 데이터를 내보내고 `recv`는 들어오는 데이터를 버퍼에 채우며 `closesocket`은 소켓을 닫는 함수로, `send` 호출 직전과 `recv` 호출 직후 각각 브레이크포인트를 걸어 버퍼 내용을 덤프하면 암호화 이전의 평문 송신 데이터나 C2로부터 받은 명령/응답을 실행 흐름 그대로 가로챌 수 있다.

## 언제 검색해야 하나
- `connect`(REV-0512) 이후 코드에서 `send`/`recv`가 반복 호출되는 것을 보고 실제로 어떤 데이터가 오가는지 확인해야 할 때
- 암호화된 통신에서 "암호화 직전 평문" 또는 "복호화 이후 평문"을 정확히 어느 시점에 가로채야 하는지 판단해야 할 때
- `closesocket` 호출 위치를 보고 통신이 언제 끝나는지, 연결을 재사용하는 루프 구조인지 확인하고 싶을 때
- CTF에서 "서버가 보내는 응답에 flag가 있다"는 힌트를 보고 `recv` 버퍼를 직접 확인하고 싶을 때

## 핵심 개념

### 함수 시그니처
```c
int send(
    SOCKET     s,     // 1. 연결된 소켓
    const char *buf,  // 2. 보낼 데이터가 있는 버퍼 주소
    int        len,   // 3. 보낼 바이트 수
    int        flags  // 4. 대개 0, MSG_OOB/MSG_DONTROUTE 등 특수 옵션
);

int recv(
    SOCKET s,     // 1. 연결된 소켓
    char   *buf,  // 2. 받은 데이터를 채울 버퍼 주소
    int    len,   // 3. 버퍼 최대 크기
    int    flags  // 4. 대개 0, MSG_PEEK(데이터를 큐에서 제거하지 않고 미리보기) 등
);

int closesocket(SOCKET s); // 소켓을 닫고 관련 자원을 해제
```
`send`/`recv` 모두 성공 시 실제로 처리된 바이트 수를 반환하고, 실패 시 `SOCKET_ERROR`(`-1`)를 반환한다. `recv`가 `0`을 반환하는 특수한 경우는 오류가 아니라 "상대방이 정상적으로 연결을 종료했다"는 뜻이므로 `-1`과 구분해서 처리해야 한다.

### send와 recv의 인자 구조는 완전히 대칭
`ReadFile`/`WriteFile`(REV-0139)과 마찬가지로, 두 번째 인자(버퍼)의 방향만 반대(송신은 "읽어가는 곳", 수신은 "채워지는 곳")라는 점만 기억하면 헷갈리지 않는다.

### 왜 리버싱에서 핵심 지점인가
- **`send` 직전 = 암호화 이후, 평문 확인 불가**: 로그인 정보나 flag를 암호화해서 보내는 프로그램이라면, `send`에 넘어가는 `buf`는 이미 암호화된 바이트열이다. 평문을 보려면 `send` 호출을 역추적해서 그 버퍼를 채운 암호화 함수 호출 이전 지점(암호화 함수의 입력 인자)에 브레이크포인트를 걸어야 한다.
- **`recv` 직후 = 아직 복호화 전일 수 있음**: 반대로 `recv`가 채운 데이터가 암호문이라면, 그 데이터가 어떤 복호화 함수를 거치는지 이후 흐름을 추적해야 진짜 명령/응답 내용을 알 수 있다.
- **반복 호출 패턴**: `recv`를 루프 안에서 반복 호출해 지정된 총 길이만큼 채우는 코드(TCP는 스트림이라 한 번의 `recv`로 전체 메시지가 안 올 수 있기 때문)는 정상적인 견고한 구현이며, 이런 루프를 보고 당황하지 않아야 한다.

## 화면/코드에서 보이는 징후
```asm
push 0
push [len]
push offset sendBuf
push [s]
call send
...
push 0
push 400h
push offset recvBuf
push [s]
call recv
mov  [recvLen], eax
```
- `send`/`recv` 호출 앞뒤로 `Sleep`(REV-0538과 연관되는 폴링 간격) 또는 반복문(`while(1)` 형태의 C2 폴링 루프)이 감싸고 있는 경우가 흔하다.
- `recv` 반환값(`eax`, 실제로 받은 바이트 수)을 확인해서 그 길이만큼만 이후 처리 루틴에 넘기는 코드.

## 가장 먼저 할 것
가로채려는 데이터가 "나가는 데이터"인지 "들어오는 데이터"인지부터 정한다. 나가는 데이터는 `send` 호출 진입 시점(아직 실제 전송 전, 버퍼 내용은 그대로 메모리에 있음)에, 들어오는 데이터는 `recv`가 리턴한 직후(버퍼가 막 채워진 시점)에 확인하는 것이 원칙이다.

## 단계별 절차
**1) send 데이터 가로채기(x64dbg)**
```text
bp send
run
; x64: RDX = buf, R8 = len
; RDX를 Follow in Dump하여 len 바이트만큼 확인
```
**2) recv 데이터 가로채기**
```text
bp recv
run
Ctrl+F9              ; 실행 till return — recv가 실제로 버퍼를 채운 뒤 시점
; RAX = 실제로 받은 바이트 수
; 진입 시 기록해둔 RDX(buf) 주소를 다시 Dump에서 확인
```
`recv`는 함수에 "진입할 때" 버퍼가 아직 안 채워져 있으므로, 반드시 `Ctrl+F9`로 리턴 지점까지 실행한 뒤에 버퍼를 확인해야 한다는 점이 `send`와 다르다.

**3) 반복 여부 확인**
같은 브레이크포인트가 여러 번 걸린다면 폴링/스트림 분할 수신 구조이므로, 몇 번째 호출에서 의미 있는 데이터가 오는지 각 회차를 기록한다.

**4) closesocket 위치로 통신 범위 파악**
`closesocket` 호출 지점을 찾아 그 앞뒤로 연결이 몇 번 반복되는지(한 번 쓰고 닫는지, 루프 안에서 계속 재연결하는지) 확인한다.

## 명령어/단축키
- x64dbg: `bp send`, `bp recv`, `bp closesocket`, `Ctrl+F9`(Execute till return)
- x64dbg: 버퍼 주소 우클릭 → `Follow in Dump`, Dump 창 우클릭 → `Save to a file`로 큰 데이터 저장 가능
- IDA: `X`(xref)로 반복 호출 패턴 파악

## 출력 해석
- `send`/`recv` 반환값이 요청한 `len`보다 작다면 부분 전송/수신이며, TCP 스트림 특성상 정상적인 상황이다. 코드가 이를 루프로 재시도하는지 확인한다.
- `recv`가 `0`을 반환하면 상대방이 정상 종료(graceful shutdown)한 것이고, `-1`이면 오류이므로 `WSAGetLastError()`를 함께 봐야 한다.
- 가로챈 바이트열이 사람이 읽을 수 있는 ASCII/UTF-8 텍스트가 아니라 무작위처럼 보이면 암호화/압축된 데이터라는 뜻이므로 REV-0140(Crypt/BCrypt API 흔적)을 함께 확인한다.

## 흔한 실수
- `recv` 호출에 진입하자마자(리턴 전) 버퍼를 확인해서 아직 채워지지 않은 이전 값을 보고 "데이터가 이상하다"고 오해하는 것 — 반드시 리턴 이후에 확인해야 한다.
- `send`로 나가는 데이터가 암호문인데 "평문을 못 찾았다"며 여기서 분석을 멈추는 것 — 암호화 함수 호출부(REV-0140)까지 거슬러 올라가야 평문이 나온다.
- 소켓 하나로 여러 번 주고받는 프로토콜에서 첫 번째 `recv` 결과만 보고 전체 프로토콜을 다 파악했다고 단정하는 것.

## 막혔을 때 다음 체크
- 애초에 이 소켓이 어디로 연결됐는지(IP/포트) 확인하고 싶다면 → REV-0512 WinAPI 네트워킹 함수 사전: WSAStartup socket connect
- 가로챈 데이터가 암호화된 것 같다면 → REV-0140 Crypt API BCrypt API 흔적 찾기
- HTTP 기반 통신이라 `send`/`recv`가 안 보인다면 → REV-0514 WinAPI 네트워킹 함수 사전: InternetOpen 계열(WinINet 기초)

## 미니 예제
```c
send(s, "AUTH 1234\r\n", 11, 0);
char buf[512];
int n = recv(s, buf, sizeof(buf), 0);
buf[n] = 0;
printf("%s", buf); // 서버 응답 출력
closesocket(s);
```
x64dbg에서 `bp recv` → `Ctrl+F9` → `RAX`(받은 바이트 수) 확인 → 저장해둔 buf 주소를 Dump에서 ASCII로 보면 `220 Welcome CTF{...}` 같은 서버 배너/flag를 그대로 확인할 수 있는 경우가 많다.

## 관련 글
- REV-0512 — WinAPI 네트워킹 함수 사전: WSAStartup socket connect
- REV-0140 — Crypt API BCrypt API 흔적 찾기
- REV-0514 — WinAPI 네트워킹 함수 사전: InternetOpen 계열(WinINet 기초)

## 출처/검증
- `send`/`recv`/`closesocket`의 시그니처와 반환값 의미(`0`=정상 종료, `-1`=오류)는 Microsoft 공식 문서(learn.microsoft.com, "send function" / "recv function" / "closesocket function") 기준이다(2026-09-08 확인).
- 암호화 전/후 지점을 구분해 가로채는 기법은 일반적인 네트워크 트래픽 리버싱 관례 레퍼런스 기준이다.
