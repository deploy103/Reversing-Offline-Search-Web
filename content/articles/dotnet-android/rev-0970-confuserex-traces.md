---
id: REV-0970
title: "ConfuserEx 흔적 알아보기"
slug: "rev-0970-confuserex-traces"
category: "dotnet-android"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [dnSpyEx]
keywords: ["ConfuserEx", "anti-tamper", "proxy call calli", "constants protection", "control flow protection", "ConfuserEx 지문"]
aliases: ["ConfuserEx 탐지", "ConfuserEx 시그니처", "ConfuserEx anti-tamper 우회", "confuserex 흔적"]
symptom_keywords: ["모듈 초기화 코드가 이상하게 크다", "calli 명령어가 자주 보인다", "실행하자마자 앱이 크래시난다", "리소스에 이상한 이름의 바이너리가 있다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ConfuserEx(및 그 포크: ConfuserEx2, MoreConfuserEx 등)는 오픈소스 .NET 난독화 도구 중 CTF/크랙미에서 가장 흔하게 보이는 도구이며, [REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 일반적인 난독화 패턴 세 가지에 더해 **anti-tamper(자기 자신 무결성 검사), proxy call(`calli` 기반 호출 위장), constants protection(상수 배열 암호화), 그리고 특유의 리소스/속성 지문**을 갖고 있어서, 이 도구 특유의 흔적만 알아두면 "이건 ConfuserEx다"라고 빠르게 확신하고 알려진 대응 전략을 바로 적용할 수 있다.

## 언제 검색해야 하나
- dnSpyEx로 열었더니 클래스 이름이 `A`, `a`, `<Module>{GUID}` 뿐 아니라 `ConfusedBy`나 낯선 커스텀 `Attribute`가 붙어 있을 때
- 앱을 dnSpyEx 디버거로 attach하거나 브레이크포인트를 걸었더니 프로그램이 곧바로 종료되거나 이상한 예외를 뱉을 때(anti-tamper/anti-debug 의심)
- IL 코드에 `calli`(Call Indirect) 명령어가 반복적으로 등장할 때
- 모듈 초기화(`<Module>.cctor`, 클래스 정적 생성자)에 비정상적으로 큰 바이트 배열과 복잡한 루프가 있을 때
- 리소스 목록에 GUID 형태의 이름을 가진 정체불명의 바이너리 리소스가 있을 때

## 핵심 개념

### 왜 ConfuserEx를 따로 알아야 하는가
ConfuserEx는 무료/오픈소스이고 설정이 비교적 쉬워서, 상용 크래커 방지 도구를 살 여력이 없는 개발자나 CTF 문제 출제자가 가장 먼저 선택하는 도구다. 그 결과 실전에서 "난독화된 .NET 바이너리"를 만나면 상당수가 ConfuserEx 계열이다. 이 도구는 프로젝트 파일(`.crproj`)에서 여러 "보호 항목(protection)"을 체크박스처럼 켜고 끌 수 있는데, 각 보호 항목마다 특유의 IL 패턴을 남기기 때문에 그 지문을 알아두면 어떤 보호가 걸려 있는지 빠르게 진단할 수 있다.

### 지문 1: 이름 맹글링과 커스텀 속성
ConfuserEx는 기본적으로 [REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 이름 맹글링을 적용하면서, 난독화되었다는 표시를 위해 어셈블리나 타입에 `[module: ConfusedBy("ConfuserEx v1.6.0")]` 같은 커스텀 어트리뷰트를 남기는 경우가 있다(버전/설정에 따라 생략되기도 한다). dnSpyEx의 어셈블리 정보(`Ctrl+Shift+F`로 `ConfusedBy` 또는 `Confuser` 검색)에서 이 문자열이 발견되면 도구가 사실상 확정된다.

### 지문 2: Anti-Tamper(변조 방지)
ConfuserEx의 anti-tamper 보호는 **메서드 본문을 암호화된 상태로 저장**해두고, 모듈이 로드되는 시점에 `<Module>` 클래스의 정적 생성자(`.cctor`)에서 자기 자신의 IL 스트림을 실행 시점에 복호화해 메모리에 다시 써넣는 방식으로 동작한다. 이 때문에:
- 파일을 디스크에서 직접 열어 IL을 보면(dnSpyEx 정적 뷰) 실제 로직이 아니라 암호화된 쓰레기 바이트처럼 보이거나 디컴파일이 실패하는 메서드가 많다.
- 파일을 1바이트라도 수정(패치)하고 저장하면, 무결성 검사에 실패해 런타임에 크래시나거나 `BadImageFormatException`류 예외가 발생한다. **anti-tamper가 걸린 파일은 IL을 정적으로 패치해서 저장하는 방식이 통하지 않는다**는 것이 핵심 특징이다.
- `.cctor` 안에 `Marshal`, `VirtualProtect` 계열 API 호출이나 대용량 바이트 배열 조작 루프가 보이면 anti-tamper 복호화 루틴일 가능성이 높다.
- **대응**: 정적 패치 대신 dnSpyEx 디버거로 attach해서 **복호화가 끝난 뒤(런타임 메모리 상)**의 실제 로직을 관찰하는 동적 접근이 표준적인 우회 전략이다. 또는 커뮤니티에 공개된 `de4dot`, `ConfuserEx-Unpacker`류 전용 언패커 도구로 anti-tamper를 먼저 제거한 사본을 만들어 그 사본에서 분석을 진행하는 방법도 널리 쓰인다.

### 지문 3: Proxy Call(간접 호출 위장)과 calli
"Proxy" 보호가 켜지면, 원래 `call SomeMethod(...)`였던 직접 호출이 델리게이트 필드나 함수 포인터를 경유하는 **간접 호출(`calli`, Call Indirect)**로 치환된다. 실제로 어떤 함수가 호출되는지가 IL의 `call`/`callvirt` 명령어로는 보이지 않고, 대신:
```
ldsfld ...              // 미리 초기화된 델리게이트/함수 포인터 필드를 로드
ldarg.0
calli ...               // 함수 포인터를 통해 간접 호출
```
같은 패턴이 반복된다. 이는 [REV-0969](./rev-0969-dotnet-reflection-obfuscation.md)에서 다룬 리플렉션 기반 은닉과 목적은 비슷하지만(호출 그래프 추적 방해), 구현 방식은 리플렉션 API가 아니라 IL 레벨의 함수 포인터라는 점이 다르다. Analyze의 Uses/Used By가 여기서도 무력화되므로, 대응 전략은 동일하게 "정적으로 안 보이면 동적으로 관찰"이다 — 브레이크포인트를 `calli` 직전 줄에 걸고 그 시점의 함수 포인터가 가리키는 실제 대상을 디버거로 확인한다.

### 지문 4: Constants Protection(상수/문자열 암호화)
[REV-0971](./rev-0971-dotnet-string-encryption-traces.md)에서 더 깊이 다루는 문자열 암호화의 ConfuserEx 구현체다. ConfuserEx는 문자열뿐 아니라 정수 상수까지도 암호화 대상으로 삼을 수 있으며, 복호화 로직이 `<Module>` 클래스 안의 이름 없는 헬퍼 메서드로 자동 삽입되고 그 메서드가 프로그램 전체에서 매우 높은 빈도로(문자열/상수가 쓰이는 곳마다) 호출된다는 것이 특징이다.

### 지문 5: Control Flow Protection
[REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 일반적인 제어 흐름 평탄화(state 변수 + switch)를 그대로 적용한다. ConfuserEx 특유의 형태로는, 평탄화에 더해 **불투명 술어(opaque predicate)** — 항상 참이거나 항상 거짓인데 겉보기엔 복잡한 계산처럼 보이는 조건문 — 을 추가로 섞어 넣어 실제로 도달 가능한 분기와 죽은 분기를 구분하기 어렵게 만드는 경우가 있다.

## 화면/코드에서 보이는 징후
- 어셈블리 속성/메타데이터에 `ConfusedBy`, `Confuser` 관련 문자열
- `<Module>` 클래스 정적 생성자(`.cctor`)가 비정상적으로 크고 바이트 배열/루프로 가득함
- IL에 `calli` 명령어가 반복 등장
- 파일을 조금이라도 수정 후 저장하면 실행이 즉시 실패(anti-tamper 의심)
- dnSpyEx 디버거로 attach 시도 시 프로세스가 곧바로 종료되거나 이상 동작(anti-debug 의심)
- 리소스 목록에 GUID 형태 이름의 바이너리 리소스(암호화된 문자열 테이블 등)가 있음

## 가장 먼저 할 것
`Ctrl+Shift+F`로 `Confuser`, `ConfusedBy` 문자열을 먼저 검색해 도구를 확정한다. 나오지 않더라도 `calli` 명령어 존재 여부, `.cctor`의 크기, anti-tamper 특유의 크래시 여부를 조합해서 ConfuserEx 계열인지 정황상 판단한다.

## 단계별 절차
1. `Ctrl+Shift+F`로 `Confuser` 계열 문자열을 검색해 도구/버전을 최대한 확정한다.
2. 원본 파일을 백업하고, 이후 실험은 항상 사본에서 진행한다(anti-tamper 때문에 원본을 실수로 깨뜨리면 복구가 번거롭다).
3. dnSpyEx로 attach를 시도해서 anti-debug/anti-tamper가 실제로 발동하는지 확인한다. 즉시 크래시하면 이 문서의 anti-tamper 대응(동적 관찰, 또는 언패커 사용)으로 넘어간다.
4. `calli` 명령어가 보이는 지점은 정적으로 대상을 특정하려 하지 말고, 그 줄 직전에 브레이크포인트를 걸어 함수 포인터가 가리키는 실제 메서드를 동적으로 확인한다.
5. 문자열/상수가 이상한 바이트 배열로 나온다면 [REV-0971](./rev-0971-dotnet-string-encryption-traces.md)의 절차로 넘어가 복호화 헬퍼 메서드를 찾는다.
6. 정적 패치가 필요한 상황(anti-tamper 때문에 막힘)이라면, `de4dot` 같은 공개 언패처 도구로 먼저 anti-tamper/이름 맹글링을 제거한 사본을 만든 뒤 그 사본에서 이후 분석을 진행하는 방법을 고려한다.

## 명령어/단축키
```text
dnSpyEx: Ctrl+Shift+F                "Confuser" / "ConfusedBy" 문자열 검색
dnSpyEx: Ctrl+Shift+K                <Module> 클래스, .cctor 빠르게 찾기
dnSpyEx: F9 (calli 직전 줄) → F5     간접 호출 직전에 멈춰서 함수 포인터 대상 확인
```
```bash
# 공개 언패처로 anti-tamper/이름 맹글링을 먼저 제거해보는 예시(도구 설치 후)
de4dot target.exe -o target_cleaned.exe
```

## 출력 해석
- `Ctrl+Shift+F` 검색에서 `Confuser`가 실제로 나오면, 특정 버전까지 특정되어 있으면 그 버전에 알려진 공개 언패처가 있는지부터 확인하는 것이 시간을 크게 아낄 수 있다.
- anti-tamper가 걸린 메서드는 dnSpyEx가 정적으로 보여주는 디컴파일 결과와 실제 실행 시점의 로직이 다를 수 있으므로, **정적 코드만 보고 결론 내리지 말고 항상 동적으로 한 번은 검증**해야 한다.
- `calli` 대상이 매 실행마다 같은 주소/메서드를 가리킨다면 사실상 고정 호출이므로, 확인 후에는 일반 `call`처럼 취급하고 넘어가도 된다.

## 흔한 실수
- anti-tamper가 걸린 파일을 dnSpyEx에서 코드 수정 후 그냥 저장했다가 파일이 깨져서 더 이상 실행되지 않는 상황을 만드는 것. 항상 원본을 백업해두고 사본에서 실험해야 한다.
- `calli` 명령어를 보고 "이 호출은 분석 불가능하다"고 포기하는 것 — 함수 포인터가 가리키는 대상은 런타임에는 결국 고정된 주소이므로 디버거로 얼마든지 확인 가능하다.
- ConfuserEx 흔적을 하나도 못 찾았다고 "이건 난독화가 아니다"라고 단정하는 것 — 설정에 따라 `ConfusedBy` 속성이 제거된 빌드도 흔하므로, 다른 지문(제어 흐름 뒤섞임, calli, 무결성 검사)을 종합적으로 봐야 한다.
- de4dot 같은 언패처를 원본 파일에 직접 덮어써서 실행하는 것 — 언패처 출력은 항상 별도 파일로 저장하고 원본은 보존해야 나중에 비교/재시도가 가능하다.
- anti-debug 크래시를 보고 바로 포기하는 것 — 대개 `Debugger.IsAttached` 검사나 타이밍 체크가 원인이므로, 그 검사가 어디서 이루어지는지 문자열/API 검색(`IsAttached`, `Environment.TickCount`)으로 찾아 우회 지점을 좁힐 수 있다.

## 막혔을 때 다음 체크
- ConfuserEx가 아닌 일반적인 난독화 패턴(이름 맹글링/제어 흐름/문자열 암호화) 자체가 헷갈리면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)
- 리플렉션으로 호출을 숨기는 별도 패턴과 구분이 안 되면 → [REV-0969 .NET 리플렉션(Reflection) 기반 난독화 알아보기](./rev-0969-dotnet-reflection-obfuscation.md)
- 문자열/상수 암호화 복호화 로직을 더 깊이 파고들고 싶으면 → [REV-0971 .NET 문자열 암호화 흔적 알아보기](./rev-0971-dotnet-string-encryption-traces.md)
- dnSpyEx 디버거 조작(브레이크포인트, attach) 단축키가 헷갈리면 → [REV-0967 dnSpyEx/ILSpy 단축키 빠른 참조](./rev-0967-dnspyex-ilspy-shortcuts.md)

## 미니 예제
`Crackme_Confused.exe`를 dnSpyEx로 열어 `Ctrl+Shift+F`로 `Confuser`를 검색하니 어셈블리 속성에서 `[assembly: ConfusedBy("ConfuserEx v1.6.0")]`가 발견되어 ConfuserEx 사용이 확정된다. `<Module>` 클래스를 열어보니 `.cctor`가 수백 줄짜리 바이트 배열 초기화와 루프로 가득 차 있어 anti-tamper로 의심된다. dnSpyEx로 attach해서 `Main` 근처에 브레이크포인트를 걸어보니 정상적으로 멈추는 것으로 보아 anti-debug는 걸려 있지 않은 것을 확인한다. `Main` 안에서 `calli` 명령어가 보이는 줄 직전에 브레이크포인트를 걸고 `F5`로 실행한 뒤, 디버거의 Watch 창에서 함수 포인터가 가리키는 메서드 이름을 확인하니 `Validator.CheckKey`로 확정된다. 이렇게 지문(속성 문자열) → 정적 관찰(anti-tamper 흔적) → 동적 검증(calli 대상 확인) 순서로 진행하면 ConfuserEx 특유의 여러 보호 기법을 하나씩 무력화하며 실제 로직에 도달할 수 있다.

## 관련 글
- REV-0247 — .NET 난독화 기초
- REV-0969 — .NET 리플렉션(Reflection) 기반 난독화 알아보기
- REV-0971 — .NET 문자열 암호화 흔적 알아보기
- REV-0967 — dnSpyEx/ILSpy 단축키 빠른 참조

## 출처/검증
- ConfuserEx의 보호 항목 분류(anti-tamper, constants protection, control flow protection, proxy call, anti-debug)는 ConfuserEx 공식 GitHub 저장소(`mkaring/ConfuserEx` 및 원조 `yck1509/ConfuserEx`) 위키/문서 기준으로 정리했다.
- IL `calli`(Call Indirect) 명령어의 의미는 ECMA-335(Common Language Infrastructure) 명세를 기준으로 확인했다.
- anti-tamper의 자기 복호화 동작 및 공개 언패처(`de4dot`)의 대응 방식은 관련 오픈소스 저장소 문서 및 .NET 리버싱 커뮤니티 자료를 기준으로 설명했다 (2026-09-09 확인).
