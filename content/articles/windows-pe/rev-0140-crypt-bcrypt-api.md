---
id: REV-0140
title: "Crypt API BCrypt API 흔적 찾기"
slug: "rev-0140-crypt-bcrypt-api"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CryptoAPI", "CNG", "BCrypt", "CryptAcquireContext", "CryptHashData", "BCryptOpenAlgorithmProvider", "advapi32.dll", "bcrypt.dll"]
aliases: ["암호화 API 흔적", "표준 암호화 사용 여부 확인", "CryptAPI BCryptAPI 구분", "AES SHA 임포트로 확인"]
symptom_keywords: ["암호화 로직인데 표준 알고리즘인지 커스텀인지 모르겠다", "advapi32.dll이나 bcrypt.dll이 임포트되어 있다", "AES SHA256 같은 문자열이 코드에 있다", "직접 암호화 알고리즘을 구현한 코드로 보이지 않는다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이너리의 임포트 테이블에 `CryptAcquireContext`, `CryptHashData`, `BCryptOpenAlgorithmProvider` 같은 이름이 보이면 이는 개발자가 암호화 로직을 직접 구현하지 않고 Windows가 제공하는 표준 암호화 API(레거시 CryptoAPI 또는 최신 CNG/BCrypt)를 그대로 사용했다는 강력한 신호이므로, 알고리즘을 밑바닥부터 리버싱할 필요 없이 호출 인자(알고리즘 이름, 키, IV, 데이터)만 추적해서 파이썬 암호화 라이브러리로 그대로 재현하면 훨씬 빠르게 분석을 끝낼 수 있다.

## 언제 검색해야 하나
- 임포트 테이블에 `advapi32.dll`(레거시 CryptoAPI 계열 함수 포함)이나 `bcrypt.dll`(CNG/BCrypt 계열)이 보일 때
- 문자열 창에 `"AES"`, `"RSA"`, `"SHA256"`, `"3DES"` 같은 알고리즘 이름이 그대로 보일 때
- 어떤 함수가 데이터를 뒤섞는데, 단순 XOR/회전 반복이 아니라 복잡한 S-box나 라운드 구조처럼 보여서 "이거 표준 암호 알고리즘 아닌가?" 싶을 때
- 커스텀 암호화 알고리즘을 리버싱하려다가 시간이 너무 오래 걸릴 것 같아서, 혹시 표준 API를 쓴 건 아닌지 먼저 확인하고 싶을 때

## 핵심 개념
Windows는 암호화 기능을 직접 구현하지 않고도 쓸 수 있도록 두 세대의 공식 암호화 API를 제공한다.

**1) 레거시 CryptoAPI(CAPI, `advapi32.dll`)**
오래된 방식으로, 다음과 같은 함수들이 세트로 쓰인다.
- `CryptAcquireContext` — 암호화 서비스 제공자(CSP, Cryptographic Service Provider)에 대한 핸들을 얻는다. 거의 모든 CryptoAPI 사용의 시작점이다.
- `CryptCreateHash` / `CryptHashData` — 해시 객체를 만들고 데이터를 해시에 먹인다(SHA1, MD5 등).
- `CryptDeriveKey` — 해시 결과로부터 암호화 키를 유도한다(비밀번호 기반 키 생성에 자주 쓰임).
- `CryptEncrypt` / `CryptDecrypt` — 실제 암/복호화 수행.
- `CryptGenRandom` — 암호학적으로 안전한 난수 생성.

**2) CNG(Cryptography API: Next Generation, `bcrypt.dll`)**
Windows Vista 이후 권장되는 최신 방식으로, `BCrypt` 접두사가 붙는다.
- `BCryptOpenAlgorithmProvider` — 사용할 알고리즘 제공자를 연다. 이때 두 번째 인자(`pszAlgId`)로 알고리즘 이름을 문자열로 직접 넘긴다는 점이 리버싱에서 매우 중요하다.
- `BCryptCreateHash` / `BCryptHashData` / `BCryptFinishHash` — 해시 계산.
- `BCryptGenerateSymmetricKey` — 대칭키(AES 등) 객체 생성.
- `BCryptEncrypt` / `BCryptDecrypt` — 실제 암/복호화 수행.
- `BCryptGenRandom` — 난수 생성.

여기서 리버싱에 가장 유용한 부분은 `BCryptOpenAlgorithmProvider`의 `pszAlgId` 인자다. Microsoft는 알고리즘 식별을 위해 표준화된 문자열 상수를 정의해두었는데, 대표적으로 다음과 같다.

```text
BCRYPT_AES_ALGORITHM    = L"AES"
BCRYPT_RSA_ALGORITHM    = L"RSA"
BCRYPT_SHA1_ALGORITHM   = L"SHA1"
BCRYPT_SHA256_ALGORITHM = L"SHA256"
BCRYPT_MD5_ALGORITHM    = L"MD5"
BCRYPT_DES_ALGORITHM    = L"DES"
```

즉 `BCryptOpenAlgorithmProvider` 호출 직전에 `lea rdx, [algo_name_string]`처럼 문자열 주소가 세팅되는 코드를 찾아 그 문자열 값만 읽으면, "이 프로그램이 무슨 암호화 알고리즘을 쓰는지"를 코드 분석 없이 바로 알아낼 수 있다. 그 다음부터는 키, IV, 체이닝 모드(`BCryptSetProperty`로 `BCRYPT_CHAINING_MODE` 설정, 예: `BCRYPT_CHAIN_MODE_CBC`) 등의 인자만 추적해서 Python의 `pycryptodome` 같은 라이브러리로 동일한 알고리즘을 그대로 재현하면 된다. 알고리즘 자체를 어셈블리 레벨에서 역산할 필요가 전혀 없다는 뜻이다.

이 점이 바로 "Crypt/BCrypt API 흔적 찾기"가 리버싱 초반 트리아지에서 중요한 이유다. 반대로 이런 임포트가 전혀 없이 데이터를 뒤섞는 코드가 있다면, 이는 십중팔구 개발자가 직접 만든 **커스텀 암호화(XOR 반복, 비트 회전, 자체 치환 테이블 등)**이며, 이 경우엔 알고리즘 자체를 코드에서 읽어내 재구현해야 한다(관련 패턴은 알고리즘 카테고리의 XOR/회전/치환 관련 글에서 다룬다).

## 화면/코드에서 보이는 징후
- 임포트 테이블에 `advapi32.dll`의 `CryptAcquireContextW`, `CryptHashData` 등이 보임
- 임포트 테이블에 `bcrypt.dll`의 `BCryptOpenAlgorithmProvider`, `BCryptEncrypt` 등이 보임
- 문자열 창(`Shift+F12`)에서 `AES`, `SHA256`, `RSA1` 같은 짧고 대문자 위주인 문자열이 보임(알고리즘 ID 상수)
- `CryptStringToBinaryA`/`CryptBinaryToStringA` 임포트가 있으면 Base64 인코딩/디코딩을 자체 구현 대신 API로 처리하고 있다는 뜻
- 데이터 변환 로직이 복잡한데도 정작 눈에 보이는 반복 연산(XOR 루프 등)이 코드에 없다면, 표준 API 호출로 처리되고 있을 가능성을 의심해야 함

## 가장 먼저 할 것
1. 임포트 테이블에서 `advapi32.dll`과 `bcrypt.dll`을 확인해서, 이 프로그램이 표준 암호화 API를 쓰는지부터 확인한다.
2. `BCryptOpenAlgorithmProvider`(또는 `CryptAcquireContext`)를 쓴다면, 그 호출 직전에 세팅되는 알고리즘 이름 문자열을 읽는다.
3. 표준 API 흔적이 전혀 없다면 커스텀 암호화이므로, 데이터를 직접 조작하는 루프를 REV-0139 방식으로 추적해서 알고리즘을 코드로 재구성해야 한다.

## 단계별 절차
**1) 정적으로 알고리즘 식별**
- IDA 임포트 목록에서 `BCryptOpenAlgorithmProvider`를 찾아 `X`로 호출 지점을 확인한다.
- 호출 직전 두 번째 인자(`pszAlgId`)로 넘어가는 문자열 주소를 확인한다. 유니코드 문자열이므로 IDA에서 자동으로 `L"AES"` 형태로 표시되는 경우가 많다.
- `CryptAcquireContext` 계열이라면 알고리즘 이름 대신 CSP 이름과 이후의 `CryptCreateHash`/`CryptDeriveKey` 호출에서 쓰이는 `ALG_ID` 상수(예: `CALG_AES_256`, `CALG_SHA1`)를 확인해야 한다. 이 상수는 정수값이므로, MSDN에 정의된 `ALG_ID` 값 표와 대조해서 알고리즘을 특정한다.

**2) 동적으로 키/IV/데이터 추적**
- x64dbg에서 `bp BCryptEncrypt`(또는 `CryptEncrypt`)로 브레이크포인트를 건다.
- REV-0139에서 익힌 방법과 동일하게, x64면 `RCX`/`RDX`/`R8`/`R9`(및 스택의 추가 인자)를, x86이면 스택을 확인해서 키 핸들, 평문 버퍼, 버퍼 길이 등을 하나씩 확인한다.
- `BCryptGenerateSymmetricKey` 호출 시점으로 거슬러 올라가면 실제 키 바이트 값을 담은 버퍼 주소를 얻을 수 있다. 이 버퍼를 덤프해서 실제 키 값을 확보한다.

**3) Python으로 재현**
- 알고리즘 이름, 키, IV, 체이닝 모드를 모두 확보했다면, `pycryptodome` 같은 라이브러리로 동일한 연산을 Python에서 그대로 재현해서 복호화/암호화 결과를 확인한다. 어셈블리 레벨에서 라운드 함수를 하나하나 따라갈 필요가 없다.

## 명령어/단축키
- IDA: `X`(교차 참조로 알고리즘 문자열 사용처 확인), `Shift+F12`(문자열 창에서 알고리즘 이름 직접 검색)
- x64dbg: `bp BCryptOpenAlgorithmProvider`, `bp BCryptEncrypt`, `bp CryptEncrypt` 등으로 원하는 단계에서 바로 멈추기
- 참고: `CyberChef`(오프라인 버전이 있다면) 같은 도구로 확보한 키/데이터를 빠르게 검증

## 출력 해석
- `BCryptOpenAlgorithmProvider`의 `pszAlgId` 문자열이 `"AES"`이면 대칭키 블록 암호인 AES가 쓰인 것이며, 이후 `BCryptSetProperty`로 설정되는 체이닝 모드(`ECB`/`CBC`/`GCM` 등)와 키 길이(128/192/256비트)를 추가로 확인해야 완전한 재현이 가능하다.
- `CryptAcquireContext`의 `dwProvType` 인자가 `PROV_RSA_AES`(24) 같은 값이면 AES를 지원하는 CSP를 요청한 것이고, `PROV_RSA_FULL`(1)이면 RSA 계열 CSP를 요청한 것이다.
- 표준 API 함수의 반환값이 `NTSTATUS`(BCrypt 계열, 0이면 `STATUS_SUCCESS`) 또는 `BOOL`(CryptoAPI 계열, 0이 아니면 성공)인지 헷갈리지 않도록 두 세대 API의 반환값 규칙이 다르다는 점을 기억한다.

## 흔한 실수
- `CryptAcquireContext`/`BCryptOpenAlgorithmProvider`가 보인다고 무조건 "안전하게 암호화되어 있어서 못 뚫는다"고 지레 포기하는 것. 표준 알고리즘이라도 키가 하드코딩되어 있거나 고정된 IV를 쓰는 등 구현 실수가 있는 경우가 CTF에서는 흔하다.
- BCrypt 계열과 레거시 CryptoAPI 계열 함수를 섞어서 인자 순서를 착각하는 것. 두 세대는 이름은 비슷해도 구조체와 인자 순서가 다르므로 반드시 각각의 공식 시그니처를 확인해야 한다.
- 알고리즘 이름 문자열만 확인하고 체이닝 모드나 패딩 방식(PKCS7 등)을 확인하지 않아, Python으로 재현했을 때 결과가 원본과 다르게 나오는 것.
- 이런 API 흔적이 전혀 없는데도 "혹시 어딘가에 숨어있지 않을까" 하고 무한정 임포트 테이블만 뒤지는 것. 흔적이 없으면 커스텀 구현일 가능성이 높으므로 빠르게 REV-0139 방식의 데이터 흐름 추적으로 전환하는 것이 효율적이다.

## 막혔을 때 다음 체크
- 암호화된 데이터가 파일로 읽고 쓰인다면 → REV-0139(CreateFile ReadFile WriteFile 입력 데이터 추적)로 데이터 흐름을 함께 확인한다.
- 함수 이름이 낯설어 인자 개수/순서 짐작이 어렵다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 참고한다.
- 암호화 키나 알고리즘 관련 문자열이 리소스에 숨겨져 있을 수도 있으니 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 확인한다.

## 미니 예제
IDA로 어떤 바이너리의 임포트 목록을 봤더니 `bcrypt.dll`에서 `BCryptOpenAlgorithmProvider`, `BCryptSetProperty`, `BCryptGenerateSymmetricKey`, `BCryptEncrypt`가 임포트되어 있었다. `BCryptOpenAlgorithmProvider` 호출 지점을 `X`로 따라가 보니 다음과 같은 코드가 있었다.

```c
BCryptOpenAlgorithmProvider(&hAlg, L"AES", NULL, 0);
BCryptSetProperty(hAlg, L"ChainingMode", (PUCHAR)L"ChainingModeCBC", ..., 0);
BCryptGenerateSymmetricKey(hAlg, &hKey, NULL, 0, key_bytes, 16, 0);
BCryptEncrypt(hKey, plaintext, plaintext_len, NULL, iv_bytes, 16, output, ..., &result_len, 0);
```

이 코드만으로 "AES-128-CBC를 쓰고, 키는 `key_bytes`(16바이트), IV는 `iv_bytes`(16바이트)"라는 것을 바로 알 수 있다. x64dbg로 `BCryptGenerateSymmetricKey` 호출 지점에 브레이크포인트를 걸어 `key_bytes`가 가리키는 실제 16바이트 값을 덤프하고, `BCryptEncrypt` 호출 지점에서 `iv_bytes`도 함께 확보하면, 이제 어셈블리를 더 볼 필요 없이 Python `pycryptodome`으로 동일하게 `AES.new(key, AES.MODE_CBC, iv)`를 구성해서 복호화를 재현할 수 있다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- 레거시 CryptoAPI(`CryptAcquireContext`, `CryptHashData` 등)와 CNG/BCrypt(`BCryptOpenAlgorithmProvider`, `BCryptEncrypt` 등)의 함수 시그니처와 표준 알고리즘 식별 문자열(`BCRYPT_AES_ALGORITHM` 등)은 Microsoft 공식 Cryptography API 문서 기준이다.
- `ALG_ID`, `dwProvType`(`PROV_RSA_FULL`, `PROV_RSA_AES` 등) 상수값은 Microsoft CryptoAPI 공식 헤더/문서 기준이다.
- 위 미니 예제 코드는 전형적인 CNG 사용 패턴을 보여주기 위해 구성한 예시이며 실제 특정 문제의 코드가 아니다(2026-09-08 기준 서술).
