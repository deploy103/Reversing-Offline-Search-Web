---
id: REV-0971
title: ".NET 문자열 암호화 흔적 알아보기"
slug: "rev-0971-dotnet-string-encryption-traces"
category: "dotnet-android"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [dnSpyEx]
keywords: [".NET 문자열 암호화", "ldstr 없는 문자열", "XOR 문자열 복호화", "정적 필드 캐싱 문자열", "dnSpyEx 문자열 덤프"]
aliases: ["닷넷 문자열 암호화 우회", "암호화된 문자열 복호화", "string decryption dotnet", "ldstr 대신 byte array"]
symptom_keywords: ["문자열 검색을 해도 아무것도 안 나온다", "byte 배열이 문자열 자리에 있다", "복호화 함수가 프로그램 전체에서 호출된다", "static readonly 문자열 필드가 이상하다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
.NET 문자열 암호화는 IL의 `ldstr "평문"` 명령어를 코드에서 아예 없애고, 대신 암호화된 바이트/정수 배열과 그것을 프로그램 시작 시 또는 사용 시점에 복호화하는 자동 삽입 헬퍼 메서드로 대체하는 기법이며, 복호화 알고리즘 자체를 역산하지 않고도 **실행 중 메모리에서 복호화 직후의 값을 훔쳐보는 동적 접근**이 실전에서 가장 빠르고 확실한 대응이다.

## 언제 검색해야 하나
- [REV-0246](./rev-0246-dotnet-strings-resources.md)에서 배운 대로 `Ctrl+Shift+F`로 문자열을 검색했는데 예상되는 문자열이 하나도 안 나올 때
- 코드에 `byte[]` 또는 `int[]` 리터럴 배열과 그것을 인자로 받는 낯선 static 메서드 호출이 문자열이 필요할 법한 자리마다 반복될 때
- `static readonly string` 필드가 생성자에서 이상한 계산을 거쳐 초기화되고 있을 때
- 어떤 문자열 복호화 알고리즘이 쓰였는지 직접 역산해서 파이썬으로 일괄 복호화하고 싶을 때
- [REV-0970](./rev-0970-confuserex-traces.md)에서 다룬 ConfuserEx의 Constants Protection이 걸린 파일을 만났을 때

## 핵심 개념

### 왜 문자열이 가장 먼저 암호화 대상이 되는가
[REV-0246](./rev-0246-dotnet-strings-resources.md)에서 다룬 것처럼 .NET 바이너리는 문자열 전체 검색만으로 `flag{...}`, URL, 에러 메시지 같은 결정적 힌트가 그대로 노출되는 경우가 매우 흔하다. 배포자 입장에서는 이것이 가장 손쉽게 뚫리는 지점이므로, 이름 맹글링이나 제어 흐름 난독화보다도 문자열 암호화를 우선적으로 적용하는 경우가 많다.

### 컴파일 결과의 차이 — ldstr vs 배열+호출
암호화되지 않은 일반 문자열은 IL에서 다음처럼 단순하다.
```
ldstr "Welcome to the crackme!"
call void [mscorlib]System.Console::WriteLine(string)
```
문자열이 암호화되면 이 자리가 다음과 같은 형태로 바뀐다.
```
ldsfld uint8[] Program::'encData1'      // 미리 선언된 암호화 바이트 배열
ldc.i4 0x0                              // 인덱스나 키 등 부가 인자
call string Program::Decrypt(uint8[], int32)  // 복호화 헬퍼 메서드 호출
call void [mscorlib]System.Console::WriteLine(string)
```
`ldstr`가 사라지고 `ldsfld`(정적 필드 로드)와 이름 없는 `Decrypt`류 메서드 호출로 바뀐 것이 핵심 신호다.

### 흔한 구현 패턴 3가지

**패턴 A — 사용 시점마다 즉석 복호화**: 문자열이 필요한 자리마다 바로 그 자리에서 `Decrypt(암호화배열, 인덱스)`를 호출한다. 호출 횟수가 문자열 사용 횟수만큼 그대로 반복되므로, `Ctrl+Shift+F`로 특정 메서드 이름을 검색하면 호출 지점이 프로그램 전체에 흩어져 나타난다.

**패턴 B — 모듈 초기화 시 일괄 복호화 후 캐싱**: `<Module>` 또는 특정 클래스의 정적 생성자(`.cctor`)에서 프로그램이 시작되자마자 모든 암호화 문자열을 한 번에 복호화해서 `static string[]` 배열이나 개별 `static readonly string` 필드에 저장해둔다. 이후 코드에서는 그 캐시 필드를 읽기만 한다(`ldsfld`). 이 패턴이면 **초기화 루틴이 끝난 직후 어디서든 브레이크포인트를 걸어 캐시 배열/필드를 한 번만 들여다봐도 모든 문자열을 한 번에 확인할 수 있다**는 것이 중요한 실전 팁이다.

**패턴 C — 알고리즘**: 실제 복호화 알고리즘은 도구/버전마다 다르지만 크게 세 부류로 나뉜다.
- 단순 XOR 또는 바이트 회전(비트 시프트) 기반 — 파이썬으로 몇 줄이면 재현 가능.
- Base64 인코딩 + 간단한 치환 — 디코딩 순서만 알면 재현 쉬움.
- 표준 암호(AES 등) 기반 — 키/IV가 프로그램 내부 상수로 하드코딩되어 있는 경우가 대부분이며, 알고리즘 자체는 표준이므로 키만 찾으면 파이썬 `pycryptodome` 등으로 동일하게 복호화 가능.

### 정적 역산 vs 동적 관찰 — 언제 어느 쪽을 쓸까
- 복호화 헬퍼가 한두 개뿐이고 로직이 단순(XOR 등)하면, 정적으로 알고리즘을 읽고 파이썬으로 옮겨 모든 암호화 문자열을 일괄 복호화하는 것이 효율적이다. 특히 문자열이 수십~수백 개라면 이 방법이 압도적으로 빠르다.
- 복호화 알고리즘이 복잡하거나(다단계, 커스텀 암호), 애초에 관심 있는 문자열이 한두 개뿐이라면, dnSpyEx 디버거로 복호화 호출 직후에 브레이크포인트를 걸어 그 값만 바로 읽는 동적 접근이 훨씬 빠르다.

## 화면/코드에서 보이는 징후
- `Ctrl+Shift+F` 문자열 검색 결과가 예상보다 훨씬 적거나 텍스트로 된 문자열이 거의 없다.
- 코드에 `byte[]`/`int[]` 배열 리터럴과 그것을 인자로 받는 static 메서드 호출이 반복된다.
- 어떤 static 메서드 하나가 프로그램 전체에서 비정상적으로 높은 빈도로 호출된다(문자열이 쓰이는 모든 자리에서).
- `<Module>.cctor`나 특정 클래스의 정적 생성자가 크고, 그 안에서 배열을 순회하며 `string[]` 캐시를 채우는 루프가 보인다.

## 가장 먼저 할 것
`Ctrl+Shift+F`로 아무 문자열이나(예: 프로그램 제목, 흔한 UI 문자열) 검색해서 정상적으로 나오는지부터 확인한다. 안 나오면 문자열 암호화가 걸려 있다고 확정하고, 코드에서 `byte[]`/`Decrypt`류 이름의 static 메서드부터 찾는다.

## 단계별 절차
1. `Ctrl+Shift+F`로 일반적인 UI 문자열을 검색해 암호화 여부를 확인한다.
2. 코드에서 `byte[]`/`int[]` 리터럴 배열을 인자로 받는 낯선 static 메서드(대개 이름이 `a`, `b`, `Decrypt` 등)를 찾는다.
3. 그 메서드가 어디서 호출되는지 `Analyze`(Uses/Used By, [REV-0967](./rev-0967-dnspyex-ilspy-shortcuts.md))로 확인해, 즉석 복호화(패턴 A)인지 일괄 캐싱(패턴 B)인지 판단한다.
4. 패턴 B(캐싱)라면 캐시 필드/배열이 채워지는 정적 생성자 직후에 브레이크포인트를 걸고, 캐시 전체를 한 번에 Watch 창에서 덤프한다.
5. 패턴 A(즉석 복호화)이고 관심 있는 지점이 소수라면, 각 호출 직후에 브레이크포인트를 걸어 그때그때 반환값을 확인한다.
6. 문자열이 수십 개 이상이고 알고리즘이 단순(XOR 등)해 보이면, 복호화 메서드의 IL/디컴파일 결과를 읽고 파이썬으로 동일 연산을 재현해 일괄 복호화 스크립트를 작성한다.

## 명령어/단축키
```text
dnSpyEx: Ctrl+Shift+F              일반 UI 문자열로 암호화 여부 1차 확인
dnSpyEx: Ctrl+Shift+K              복호화 의심 static 메서드 이름 검색
dnSpyEx: Alt+F12 (메서드 위)        Analyze로 Uses/Used By 확인(패턴 A/B 구분)
dnSpyEx: F9 (복호화 호출 직후) → F5  런타임 복호화 값 확인
```
```python
# 패턴 C(단순 XOR)로 밝혀졌을 때 일괄 복호화 예시
def decrypt(enc_bytes, key):
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(enc_bytes)).decode("utf-8", errors="replace")

enc = bytes([0x1a, 0x2f, 0x05, 0x33])   # 디컴파일 결과에서 그대로 옮겨온 배열
key = b"\x7e"                            # 복호화 메서드에서 확인한 고정 키
print(decrypt(enc, key))
```

## 출력 해석
- 디버거 Watch 창에서 복호화 직후 값이 `flag{...}`, URL, 파일 경로처럼 사람이 읽을 수 있는 형태로 나오면 그 지점이 목표에 해당할 확률이 높다.
- 캐시 배열(패턴 B)을 한 번에 덤프했는데 문자열이 수십 개 나온다면, 그중 실제로 유의미한 값(에러 메시지, 정답 비교 대상 등)만 골라 [REV-0246](./rev-0246-dotnet-strings-resources.md) 방식으로 다시 문맥을 확인해야 한다.
- 파이썬으로 재현한 복호화 결과가 깨진 문자(mojibake)로 나오면, 인코딩(UTF-8/UTF-16/ASCII) 가정이 틀렸을 가능성이 크므로 원본 C#의 `Encoding.` 관련 호출을 다시 확인한다.

## 흔한 실수
- 복호화 알고리즘을 처음부터 완벽하게 역산하려고 시간을 쏟는 것 — 문자열이 몇 개 안 되면 동적으로 값만 훔쳐보는 게 훨씬 빠르다.
- 정적 생성자(`.cctor`)에서 이미 캐싱된 문자열을 놓치고, 매번 사용 지점마다 개별적으로 복호화된다고 잘못 가정해 비효율적으로 하나씩 추적하는 것.
- 파이썬으로 재현한 XOR 키의 바이트 순서(리틀엔디안/빅엔디안 혼동)나 인덱스 진행 방향을 원본 C# 코드와 다르게 구현해서 결과가 깨지는 것.
- AES 같은 표준 암호가 쓰였을 때 알고리즘 자체를 의심하며 시간을 낭비하는 것 — 표준 암호라면 키/IV만 찾으면 되고, 알고리즘 구현을 손으로 다시 만들 필요가 없다(`pycryptodome` 등 기존 라이브러리를 그대로 쓰면 된다).
- 암호화된 배열 리터럴을 디컴파일 코드에서 옮겨 적을 때 값 일부를 누락하거나 순서를 잘못 옮기는 것 — 배열이 길면 IL 뷰에서 원문 그대로 복사하는 것이 안전하다.

## 막혔을 때 다음 체크
- 문자열/리소스를 체계적으로 검색하는 기본 방법이 헷갈리면 → [REV-0246 .NET 문자열과 리소스 찾기](./rev-0246-dotnet-strings-resources.md)
- 이 암호화가 ConfuserEx의 Constants Protection인지 확인하고 싶으면 → [REV-0970 ConfuserEx 흔적 알아보기](./rev-0970-confuserex-traces.md)
- 복호화 헬퍼 메서드 자체가 리플렉션으로 은닉되어 찾기 어렵다면 → [REV-0969 .NET 리플렉션(Reflection) 기반 난독화 알아보기](./rev-0969-dotnet-reflection-obfuscation.md)
- dnSpyEx 디버거 조작(브레이크포인트, Watch 창) 단축키가 헷갈리면 → [REV-0967 dnSpyEx/ILSpy 단축키 빠른 참조](./rev-0967-dnspyex-ilspy-shortcuts.md)

## 미니 예제
디컴파일된 코드가 다음과 같다고 하자.
```csharp
static readonly byte[] encData1 = new byte[] { 0x1a, 0x2f, 0x05, 0x33 };

static string a(byte[] data, byte key)
{
    var sb = new StringBuilder();
    foreach (byte b in data)
        sb.Append((char)(b ^ key));
    return sb.ToString();
}

static void Main()
{
    Console.WriteLine(a(encData1, 0x7e));
}
```
`Ctrl+Shift+F`로 문자열을 검색해도 `flag`나 `Welcome` 같은 텍스트가 전혀 안 나오는데, 코드에는 `byte[]` 배열과 `a(...)`라는 짧은 static 메서드가 보인다. `a`의 본문을 읽어보니 각 바이트를 고정 키(`0x7e`)와 XOR한 뒤 문자로 이어붙이는 단순한 로직임을 알 수 있다. 문자열이 이 배열 하나뿐이라면 dnSpyEx에서 `Console.WriteLine(a(encData1, 0x7e));` 줄에 브레이크포인트를 걸고 `F5`로 실행해 반환값을 확인하는 것으로 충분하다. 만약 이런 배열이 수십 개 있다면, 위 "명령어/단축키" 절의 파이썬 스크립트에 각 배열과 키를 그대로 대입해 한 번에 전부 복호화하는 쪽이 훨씬 빠르다.

## 관련 글
- REV-0246 — .NET 문자열과 리소스 찾기
- REV-0970 — ConfuserEx 흔적 알아보기
- REV-0969 — .NET 리플렉션(Reflection) 기반 난독화 알아보기
- REV-0967 — dnSpyEx/ILSpy 단축키 빠른 참조

## 출처/검증
- IL 명령어 `ldstr`/`ldsfld`의 의미와 문자열 리터럴이 메타데이터 문자열 힙에 저장되는 방식은 ECMA-335(Common Language Infrastructure) 명세를 기준으로 확인했다.
- .NET 난독화 도구의 문자열 암호화 일반 구현 패턴(사용 시점 즉석 복호화 vs 초기화 시 일괄 캐싱)은 ConfuserEx 등 오픈소스 난독화 도구 문서 및 관련 리버싱 커뮤니티 자료를 기준으로 정리했다.
- 위 코드/알고리즘 예제는 학습용으로 재구성한 것이며 특정 실제 문제의 정답이 아니다 (2026-09-09 확인).
