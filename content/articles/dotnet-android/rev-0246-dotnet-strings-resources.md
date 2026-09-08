---
id: REV-0246
title: ".NET 문자열과 리소스 찾기"
slug: "rev-0246-dotnet-strings-resources"
category: "dotnet-android"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: ["dnSpyEx", "ILSpy"]
keywords: [".NET 문자열 검색", ".resources 리소스", ".NET 리소스 뷰어", "임베디드 리소스", "US-String Heap", ".NET 메타데이터 힙"]
aliases: [".NET 문자열은 어디에 있나", ".resources 파일이란", ".NET 리소스와 PE 리소스 차이", "닷넷 임베디드 리소스 추출"]
symptom_keywords: ["strings.exe로 .NET 파일을 뒤졌는데 원하는 문자열이 안 보임", ".NET 프로그램의 리소스를 어떻게 여는지 모름", ".resources 확장자가 뭔지 모름", "플래그가 코드가 아니라 리소스 안에 있는 것 같음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
.NET 바이너리의 문자열은 IL 코드 안의 `ldstr` 리터럴뿐 아니라 **User String Heap이라는 메타데이터 영역**과, PE의 `.rsrc` 섹션과는 별개로 존재하는 **`.resources` 임베디드 리소스**(문자열 테이블, 이미지, 설정값 등)에도 나뉘어 저장될 수 있으므로, dnSpyEx/ILSpy의 검색 기능과 리소스 트리를 모두 확인해야 문자열/플래그를 놓치지 않는다.

## 언제 검색해야 하나
- `strings.exe`나 일반 헥스에디터로 .NET 실행 파일을 뒤졌는데 예상한 문자열이 안 보이거나 이상한 형태로만 보일 때
- ILSpy/dnSpyEx 트리에서 `Resources` 노드를 봤는데 이게 뭔지, 어떻게 열어야 하는지 모를 때
- 프로그램이 `Properties.Resources.SomeString`처럼 리소스를 참조하는 코드를 봤는데 실제 값이 어디 있는지 못 찾을 때
- CTF 문제에서 플래그가 코드에 직접 안 보여서 리소스 안에 숨겨져 있을 것 같다고 의심될 때

## 핵심 개념

### .NET 문자열이 저장되는 세 곳
1. **User String Heap (`#US` 스트림)** — IL 코드에서 `ldstr "..."`로 쓰이는 모든 문자열 리터럴이 모이는 메타데이터 힙이다. UTF-16으로 인코딩되어 있으며, 어떤 IL 도구로 봐도(원문 헥스 덤프 포함) UTF-16 문자 배열 형태로 나타난다. dnSpyEx/ILSpy 검색창의 `Literal`/`String` 필터가 바로 이 힙을 뒤진다.
2. **Metadata 문자열 힙 (`#Strings` 스트림)** — 클래스명, 메서드명, 네임스페이스, 필드명 등 식별자 이름들이 저장되는 별도의 힙이다. 값(데이터)이 아니라 이름(식별자)이 담기는 곳이라는 점에서 User String Heap과 역할이 다르다.
3. **임베디드 리소스(`.resources`)** — 어셈블리 안에 통째로 포함된 별도의 이진 데이터 블록으로, 이미지, 아이콘, 설정 파일, 그리고 무엇보다 **다국어 문자열 테이블**이 자주 여기 저장된다. Visual Studio에서 `Resources.resx` 파일을 프로젝트에 추가하면 빌드 시 이 리소스로 컴파일되어 들어간다.

### .NET 리소스가 네이티브 PE `.rsrc`와 다른 점
네이티브 PE 파일의 `.rsrc` 섹션은 아이콘, 버전 정보, 대화상자 템플릿, 커서 등을 담는 Windows 고유의 리소스 디렉터리 구조(`IMAGE_RESOURCE_DIRECTORY`)를 따른다. 반면 .NET의 임베디드 리소스는 완전히 다른 메커니즘이다. .NET 어셈블리도 물론 PE 포맷 위에 얹혀 있으므로 `.rsrc` 섹션이 존재할 수는 있지만(아이콘, 매니페스트 등 Win32 수준 리소스), **프로그램이 실제로 코드에서 접근하는 `.resources`는 `.rsrc` 섹션이 아니라 CLR 메타데이터 안에 별도로 포함된 매니지드 리소스**다. 즉 "이 .NET 파일에 리소스가 있다"고 할 때는 십중팔구 `.rsrc` 섹션 얘기가 아니라 이 매니지드 `.resources` 얘기이며, 이걸 열려면 PE-bear 같은 네이티브 PE 도구가 아니라 dnSpyEx/ILSpy의 리소스 뷰어를 써야 한다. `.resources`는 내부적으로 키-값 쌍(문자열 리소스의 경우 리소스 이름 → 문자열 값)으로 구성된 바이너리 포맷이며, 대표적으로 `{네임스페이스}.Properties.Resources.resources`처럼 클래스 이름과 짝지어 저장된다.

### strings.exe로 .NET 파일을 뒤지면 왜 잘 안 나오나
`ldstr`로 들어가는 문자열은 UTF-16으로 저장되어 있어서 `strings`(기본이 ASCII 기준)로는 `-e l`(little-endian UTF-16) 옵션을 켜야 겨우 보인다. 게다가 임베디드 `.resources` 안의 문자열은 자체 이진 포맷(리소스 이름, 타입 태그, 길이 프리픽스 등)으로 인코딩되어 있어서 원문 그대로 순수 텍스트로 나타나지 않는 경우가 많다. 그래서 .NET 바이너리에서는 일반 `strings` 도구보다 **dnSpyEx/ILSpy의 문자열 검색과 리소스 뷰어를 우선 사용**하는 것이 훨씬 정확하고 빠르다.

## 화면/코드에서 보이는 징후
- ILSpy/dnSpyEx 트리에서 어셈블리 노드 아래 `Resources`(또는 `{ProjectName}.g.resources`, `{Namespace}.Properties.Resources.resources` 같은 항목)가 보인다.
- 코드 안에서 `Properties.Resources.SomeKey`나 `ResourceManager.GetString("SomeKey")` 같은 호출이 보이면, 그 값이 리소스에 있다는 강한 신호다.
- `Resources` 노드를 더블클릭했을 때 hex 덤프나 표(Resource Name / Type / Value) 형태로 내용이 열린다.

## 가장 먼저 할 것
ILSpy나 dnSpyEx로 파일을 연 상태에서 좌측 트리의 `Resources` 노드를 펼쳐 어떤 리소스가 포함되어 있는지 목록부터 확인한다. 이름만 봐도 `Properties.Resources.resources` 같은 표준 리소스인지, 이미지/아이콘류인지, 아니면 프로그램이 직접 정의한 커스텀 데이터인지 감이 잡힌다.

## 단계별 절차

**1) Resources 트리 펼치기**
좌측 Assembly Explorer/트리에서 어셈블리 노드 아래 `Resources`를 펼친다. 항목이 여러 개면 이름으로 용도를 짐작한다(`.g.resources`는 대개 WPF/XAML 관련 리소스).

**2) .resources 항목 열어보기**
`.resources` 확장자를 가진 항목을 더블클릭한다. dnSpyEx는 이런 리소스를 표(그리드) 형태로 펼쳐서 리소스 이름과 타입, 값(문자열이면 값 자체, 이미지면 미리보기)을 보여준다. ILSpy도 유사하게 트리 형태로 개별 리소스 엔트리를 펼쳐볼 수 있다.

**3) 코드에서 리소스 접근 지점 찾기**
`ResourceManager.GetString(...)`이나 자동 생성된 `Properties.Resources` 클래스의 프로퍼티(예: `Resources.WelcomeMessage`)를 검색해서, 코드가 어떤 키로 리소스를 읽는지 확인한다. 키 이름을 알면 리소스 표에서 정확히 어느 항목을 봐야 하는지 바로 알 수 있다.

**4) 코드 내 리터럴 문자열도 함께 검색**
리소스뿐 아니라 IL의 `ldstr` 리터럴도 놓치지 않도록 [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)에서 다룬 `Literal` 필터 검색을 병행한다. 실제로 많은 초심자용 CTF 문제는 리소스가 아니라 코드 안에 문자열을 직접 박아두는 경우가 더 흔하다.

**5) 필요 시 리소스 원본을 파일로 추출**
dnSpyEx에서 리소스 항목을 우클릭 → **Save**를 선택하면 해당 리소스를 원본 이진 파일로 저장할 수 있다. 이미지나 별도 분석 도구가 필요한 데이터라면 이렇게 추출해서 다른 도구로 열어본다.

**6) 값이 암호화되어 있다면 코드에서 복호화 루틴 추적**
리소스나 문자열이 그대로 읽히지 않고 Base64나 바이트 배열처럼 보인다면, 그 값을 사용하는 코드를 따라가 복호화 함수(XOR, AES 등)를 찾아야 한다. 이는 [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)에서 다루는 문자열 암호화와 같은 맥락이다.

## 명령어/단축키
```text
dnSpyEx/ILSpy: 트리에서 Resources 노드 펼치기
dnSpyEx: 리소스 항목 우클릭 → Save   원본 리소스를 파일로 추출
ILSpy/dnSpyEx: Ctrl+T(또는 Ctrl+Shift+K) 검색창 → 필터 Literal/String   ldstr 문자열 검색
strings -e l file.exe   (보조 수단) UTF-16 문자열만 걸러서 보기
```

## 출력 해석
- 리소스 표에서 타입이 `System.String`이면 바로 읽을 수 있는 텍스트다. 타입이 `System.Byte[]`나 `System.Drawing.Bitmap`이면 별도 처리(추출 후 다른 도구로 확인)가 필요하다.
- `ResourceManager.GetString("Key")` 호출에서 `Key` 값이 리소스 표의 이름과 정확히 일치해야 실제 값을 찾을 수 있다. 대소문자까지 정확히 일치하는지 확인한다.
- 리소스 값이 사람이 읽을 수 없는 바이트 나열이라면 암호화/압축되어 있을 가능성이 높으므로, 그 값을 넘겨받는 함수(예: `Decrypt(bytes)`)를 코드에서 추적해야 한다.

## 흔한 실수
- `.rsrc` PE 섹션만 확인하고 "이 파일엔 리소스가 없다"고 결론짓는 것. .NET 매니지드 리소스는 `.rsrc` 섹션이 아니라 CLR 메타데이터 안에 별도로 있으므로 PE 도구가 아니라 dnSpyEx/ILSpy로 확인해야 한다.
- 일반 `strings` 도구로만 문자열을 찾고 안 나온다고 포기하는 것. UTF-16 인코딩과 리소스 이진 포맷 때문에 일반 텍스트 검색으로는 놓치는 문자열이 많다.
- 리소스 이름과 코드에서 참조하는 키 이름이 다를 수 있다는 것을 모르고 무작정 리소스 목록만 눈으로 훑는 것. 반드시 코드에서 실제로 어떤 키로 접근하는지 확인해야 정확한 항목을 찾을 수 있다.
- Base64로 인코딩된 리소스 값을 보고 "이게 플래그다"라고 바로 제출하는 것. Base64/암호화 여부를 먼저 확인하고 필요하면 디코딩/복호화까지 마쳐야 한다.

## 막혔을 때 다음 체크
- IL의 `ldstr` 문자열 자체를 더 잘 읽는 법이 궁금하면 → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 이름과 문자열이 전부 난독화/암호화되어 있으면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 도구 조작 자체가 헷갈리면 → [REV-0243 dnSpyEx로 .NET EXE 열기](./rev-0243-dnspyex-basics.md), [REV-0244 ILSpy 기본 사용법](./rev-0244-ilspy-basics.md)
- 네이티브 PE의 `.rsrc` 구조 자체가 궁금하면 → windows-pe 카테고리의 PE 리소스 관련 글을 참고한다.

## 미니 예제
`Crackme.exe`를 dnSpyEx로 열어 `Resources` 트리를 펼쳐보니 `Crackme.Properties.Resources.resources`라는 항목이 하나 있다. 더블클릭하면 표가 뜨고, `Name` 열에 `SecretKey`, `Type` 열에 `System.String`, `Value` 열에 `RmxnZ3s0ZXN0fQ==`처럼 Base64로 보이는 값이 있다. 코드에서 `Properties.Resources.SecretKey`를 검색해보니 `Convert.FromBase64String(...)`으로 디코딩한 뒤 XOR 연산을 거쳐 비교하는 함수가 나온다. 이 경우 리소스 값 자체는 플래그가 아니라 인코딩+암호화된 원본이며, 실제 값을 얻으려면 해당 디코딩/XOR 로직을 코드에서 그대로 따라가거나 같은 연산을 파이썬 등으로 재현해야 한다.

## 관련 글
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0244 — ILSpy 기본 사용법
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0247 — .NET 난독화 기초

## 출처/검증
- .NET 메타데이터 힙 구조(`#US`, `#Strings` 스트림)와 CLR 메타데이터 포맷: ECMA-335 Common Language Infrastructure(CLI) 표준 문서, Partition II(Metadata) 기준 (2026-09-08 확인).
- .NET 임베디드 리소스(`.resources`) 및 `ResourceManager` 동작: Microsoft Learn ".NET 리소스 만들기 및 사용" 공식 문서 기준.
