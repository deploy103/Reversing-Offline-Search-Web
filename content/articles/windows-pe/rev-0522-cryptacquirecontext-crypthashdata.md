---
id: REV-0522
title: "WinAPI 암호 관련 함수 사전: CryptAcquireContext CryptHashData"
slug: "rev-0522-cryptacquirecontext-crypthashdata"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CryptAcquireContextW", "CryptCreateHash", "CryptHashData", "CryptGetHashParam", "CAPI", "MD5", "SHA1"]
aliases: ["CAPI 해시 함수", "CryptoAPI 기초", "Crypt 계열 함수 순서"]
symptom_keywords: ["CryptAcquireContext가 뭔지 모르겠다", "CryptHashData 인자를 모르겠다", "해시 계산 API 흐름을 모르겠다", "MD5 SHA1 API가 어디서 쓰이는지 찾고 싶다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CryptAcquireContextW` → `CryptCreateHash` → `CryptHashData`(여러 번 가능) → `CryptGetHashParam`은 레거시 Windows CryptoAPI(CAPI)로 해시(MD5/SHA1 등)를 계산하는 정형화된 4단계 호출 순서이므로, 이 순서 자체를 패턴으로 외워두면 어떤 데이터가 해시되어 어떤 비교에 쓰이는지(주로 flag 검증 로직) 빠르게 짚어낼 수 있다.

## 언제 검색해야 하나
- 임포트 목록에서 `CryptAcquireContextW`, `CryptCreateHash`, `CryptHashData`, `CryptGetHashParam`을 발견했을 때
- 프로그램이 사용자 입력을 어떤 알고리즘(MD5/SHA1/SHA256)으로 해시해서 미리 저장된 값과 비교하는 flag 검증 로직을 찾을 때
- `advapi32.dll`(CryptoAPI가 속한 DLL)의 임포트가 있는데 정확히 뭘 하는지 감이 안 잡힐 때
- 더 최신 API인 BCrypt(CNG)와 이 레거시 CAPI 계열을 구분해야 할 때

## 핵심 개념
```c
BOOL CryptAcquireContextW(
    HCRYPTPROV *phProv,   // 1. 얻은 CSP(암호 서비스 제공자) 핸들이 저장될 주소
    LPCWSTR    pszContainer, // 2. 키 컨테이너 이름(NULL이면 기본)
    LPCWSTR    pszProvider,  // 3. CSP 이름(NULL이면 기본 RSA CSP)
    DWORD      dwProvType,   // 4. PROV_RSA_FULL 등 제공자 유형
    DWORD      dwFlags       // 5. CRYPT_VERIFYCONTEXT 등(단순 해시용이면 이 플래그가 흔함)
);

BOOL CryptCreateHash(
    HCRYPTPROV hProv,     // 1. CryptAcquireContext로 얻은 핸들
    ALG_ID     Algid,     // 2. CALG_MD5, CALG_SHA1, CALG_SHA_256 등
    HCRYPTKEY  hKey,      // 3. HMAC 등이 아니면 0
    DWORD      dwFlags,   // 4. 보통 0
    HCRYPTHASH *phHash    // 5. 생성된 해시 객체 핸들이 저장될 주소
);

BOOL CryptHashData(
    HCRYPTHASH hHash,     // 1. CryptCreateHash로 얻은 핸들
    const BYTE *pbData,   // 2. 해시할 데이터 버퍼
    DWORD      dwDataLen, // 3. 데이터 길이(바이트)
    DWORD      dwFlags    // 4. 보통 0
);

BOOL CryptGetHashParam(
    HCRYPTHASH hHash,    // 1. 해시 객체 핸들
    DWORD      dwParam,  // 2. HP_HASHVAL(결과 값) 또는 HP_HASHSIZE(결과 길이)
    BYTE       *pbData,  // 3. 결과가 채워질 버퍼
    DWORD      *pdwDataLen, // 4. 버퍼 크기/실제 길이
    DWORD      dwFlags   // 5. 보통 0
);
```

CryptoAPI로 해시를 계산하는 흐름은 항상 다음 4단계를 거친다.
1. `CryptAcquireContextW`로 CSP(Cryptographic Service Provider) 컨텍스트를 얻는다. 단순 해시 계산만 할 때는 키 컨테이너가 필요 없으므로 `dwFlags`에 `CRYPT_VERIFYCONTEXT`(0xF0000000)를 주는 경우가 매우 흔하다.
2. `CryptCreateHash`로 해시 객체를 만든다. `Algid`가 어떤 알고리즘인지 알려주는 핵심 인자다 — `CALG_MD5`(0x8003), `CALG_SHA1`(0x8004), `CALG_SHA_256`(0x800C) 등.
3. `CryptHashData`를 (필요하면 여러 번) 호출해서 실제 데이터를 해시 객체에 먹인다. 여러 조각의 데이터를 순차적으로 넣을 수 있다(스트리밍 해시).
4. `CryptGetHashParam`을 `HP_HASHVAL`(2)로 호출해 최종 해시 결과(바이트 배열)를 꺼낸다.

사용이 끝나면 `CryptDestroyHash`, `CryptReleaseContext`로 정리하는 것이 정석이지만, 리버싱 시 가장 중요한 것은 2단계(알고리즘 식별)와 3단계(무엇을 해시하는지)다.

## 화면/코드에서 보이는 징후
- `advapi32.dll` 임포트에 `CryptAcquireContextW`, `CryptCreateHash`, `CryptHashData`, `CryptGetHashParam`이 순서대로 나열
- `CryptCreateHash` 호출의 두 번째 인자로 `0x8003`, `0x8004`, `0x800C` 같은 16진 상수가 바로 들어가는 코드(알고리즘 식별의 지름길)
- `CryptHashData`의 두 번째 인자(버퍼)가 사용자 입력(예: `scanf`나 `GetWindowTextW`로 받은 문자열)을 가리키는 패턴
- `CryptGetHashParam`으로 얻은 바이트 배열을 이후 `memcmp`나 직접 바이트 비교로 하드코딩된 값과 비교하는 코드(flag 검증의 최종 단계)

## 가장 먼저 할 것
1. `CryptCreateHash`의 두 번째 인자(`Algid`)를 확인해 어떤 해시 알고리즘인지부터 특정한다(`0x8004`=SHA1이 CTF에서 특히 흔함).
2. `CryptHashData`에 들어가는 데이터가 사용자 입력 원문인지, 아니면 이미 한 번 가공(인코딩/치환)된 데이터인지 확인한다.
3. `CryptGetHashParam`의 결과가 어디와 비교되는지(하드코딩된 바이트 배열, 파일에서 읽은 값 등) 추적해서 정답 해시값을 확보한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `CryptCreateHash`를 찾아 `X`로 교차 참조하고, 두 번째 인자 상수로 알고리즘을 특정한다.
- `CryptGetHashParam` 호출 이후 결과 버퍼가 어디로 쓰이는지(비교 로직) `F5` 디컴파일로 추적한다.

**2) 동적 분석(x64dbg)**
- `bp CryptHashData`로 브레이크포인트를 걸고 실행한다.
- x64에서 `RDX`(pbData)를 Follow in Dump 해서 실제로 해시되는 원본 데이터(사용자 입력 등)를 확인한다. `R8`(dwDataLen)로 길이도 함께 확인한다.
- `bp CryptGetHashParam` 후, 이 함수가 리턴한 뒤(F8) `pbData`(세 번째 인자, 함수 진입 시점 기준 `R8`)가 가리키는 버퍼를 확인하면 최종 해시값(예: MD5면 16바이트, SHA1이면 20바이트)을 읽을 수 있다.

## 명령어/단축키
- x64dbg: `bp CryptAcquireContextW`, `bp CryptCreateHash`, `bp CryptHashData`, `bp CryptGetHashParam`
- x64dbg: 브레이크포인트 후 F8(스텝오버)로 결과 버퍼 채워진 뒤 상태 확인
- IDA: `X`(교차 참조), `F5`(디컴파일), 상수 자동 주석(WinAPI 상수는 IDA가 `CALG_MD5` 등으로 자동 표시해주는 경우가 많음)

## 출력 해석
- 반환값이 `FALSE`(0)이면 각 단계 실패다. `CryptAcquireContextW` 실패의 흔한 원인은 잘못된 `dwProvType`/`pszProvider` 조합.
- 해시 알고리즘 상수와 결과 길이가 일치하는지 확인한다: MD5=16바이트, SHA1=20바이트, SHA256=32바이트. `HP_HASHSIZE`(4)로 미리 크기를 조회할 수도 있다.
- 최종 해시값(바이트 배열)은 보통 16진수 문자열로 변환되어 비교되므로, 바이트 순서 그대로 16진수로 이어붙이면 비교 대상 문자열과 맞는지 확인할 수 있다.

## 흔한 실수
- `Algid` 상수(`0x8004` 등)를 못 알아보고 무시한 채 "그냥 해시 함수인가보다"로 넘어가는 것 — 알고리즘을 특정해야 정답 해시를 직접 재현하거나 크래킹할 수 있다.
- `CryptHashData`가 한 번만 호출된다고 가정하는 것 — 긴 데이터나 여러 필드를 합쳐 해시할 때는 여러 번 호출되며, 순서가 결과에 영향을 준다.
- CAPI(`Crypt*`)와 최신 CNG(`BCrypt*`)를 같은 함수로 착각하는 것. 이름이 비슷해 보여도 별개의 API 계열이며, `advapi32.dll`(CAPI) vs `bcrypt.dll`(CNG)로 구분된다.
- `CryptGetHashParam`을 `HP_HASHVAL` 대신 다른 `dwParam`(예: `HP_ALGID`)으로 호출한 경우를 결과값으로 착각하는 것.

## 막혔을 때 다음 체크
- 해시가 아니라 암호화/복호화(`CryptEncrypt`/`CryptDecrypt`)나 더 현대적인 BCrypt API가 궁금하면 → REV-0140(Crypt API BCrypt API 흔적 찾기)을 본다.
- 해시할 데이터가 사용자 입력에서 오는 경로가 궁금하면 → REV-0523(MessageBox GetWindowText)의 `GetWindowText` 부분을 본다.
- 해시된 데이터의 원본이 문자열인지 확인하려면 → REV-0128(Windows 문자열 ASCII와 UTF-16 찾기)을 본다.

## 미니 예제
x64dbg에서 `bp CryptCreateHash` 후 실행하니 다음처럼 멈췄다.

```text
RDX = 0x0000000000008004   (Algid = CALG_SHA1)
```

이어서 `bp CryptHashData`에서 `RDX`(pbData)를 Follow in Dump 하니 사용자가 입력한 문자열 `"password123"`이 그대로 보였다. 마지막으로 `CryptGetHashParam` 리턴 후 결과 버퍼(20바이트)를 16진수로 이어붙이면 `cbfdac6008f9cab4083784cbd1874f76618d2a97` 같은 SHA1 해시값이 나오며, 이 값이 바이너리 내부에 하드코딩된 정답 해시와 `memcmp`로 비교될 가능성이 높다.

## 관련 글
- REV-0140 — Crypt API BCrypt API 흔적 찾기
- REV-0523 — WinAPI 클립보드/UI 함수 사전: MessageBox GetWindowText
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `CryptAcquireContextW`/`CryptCreateHash`/`CryptHashData`/`CryptGetHashParam`의 함수 시그니처와 4단계 호출 순서, 알고리즘 상수(`CALG_MD5`=0x8003, `CALG_SHA1`=0x8004, `CALG_SHA_256`=0x800C)는 Microsoft CryptoAPI(CAPI) 공식 문서 기준이다.
- MD5(16바이트)/SHA1(20바이트)/SHA256(32바이트) 출력 길이는 각 알고리즘의 공개 표준 정의 기준이다.
- 위 미니 예제의 값과 해시 결과는 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
