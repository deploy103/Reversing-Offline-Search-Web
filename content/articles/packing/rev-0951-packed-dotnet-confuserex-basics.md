---
id: REV-0951
title: "패킹된 .NET 바이너리(ConfuserEx 등) 기초 알아보기"
slug: "rev-0951-packed-dotnet-confuserex-basics"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [dnSpyEx]
keywords: ["ConfuserEx", ".NET 패킹", "IL 난독화", "dnSpyEx로 언패킹", "ConfuserEx 언패킹", ".NET 문자열 암호화", "de4dot"]
aliases: ["confuserex가 뭐임", "닷넷 패킹된 exe 열기", "닷넷 난독화 풀기", "IL 코드 난독화 우회"]
symptom_keywords: ["dnspy에서 exception이 계속 뜸", "메서드 본문이 비어있음", "문자열이 다 깨져서 나옴", "ilspy에서 decompile 실패"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ConfuserEx 같은 .NET 전용 보호 도구는 native PE 패커(UPX, ASPack 등)와 근본적으로 다르게 동작한다 — 압축 대상이 x86/x64 기계어가 아니라 CLR이 실행하는 IL(Intermediate Language) 코드이므로, OEP를 찾고 메모리를 덤프하는 native 언패킹 절차(REV-0227, REV-0944~0946) 대신 dnSpyEx로 CLR 어셈블리 자체를 직접 열어 IL 난독화를 다루는 별도의 접근이 필요하다.

## 언제 검색해야 하나
- REV-0136/REV-0242로 이 바이너리가 .NET 실행 파일임을 확인했는데, DIE 또는 실행 결과에서 `ConfuserEx`, `Confuser`, 비슷한 이름의 .NET 보호 도구 흔적이 보일 때
- dnSpyEx로 파일을 열었는데 메서드 본문이 비어있거나 디컴파일 시 예외가 발생할 때
- 문자열이 정상적인 C# 문자열 리터럴이 아니라 암호화된 바이트 배열과 복호화 호출로 바뀌어 있을 때
- native PE 언패킹 절차(REV-0944)를 시도했는데 전혀 맞지 않는 것 같아서 .NET 전용 접근이 필요한지 확인하고 싶을 때

## 핵심 개념

### native 패킹과 .NET 보호가 다른 이유
UPX/ASPack 같은 native 패커는 CPU가 직접 실행하는 x86/x64 기계어를 압축하고, 실행 중 압축을 풀어 원래의 기계어로 복원한 뒤 그 코드로 점프한다(REV-0227). 하지만 .NET 실행 파일은 CPU가 직접 실행하는 코드가 아니라 **CLR(Common Language Runtime)이 해석/JIT 컴파일하는 IL 바이트코드**로 구성되어 있다(REV-0242, REV-0245). 즉:

- .NET EXE를 실행하면 실제로는 `mscoree.dll`(또는 최신 .NET의 호스트 실행 파일)이 CLR을 초기화하고, CLR이 어셈블리 안의 IL 메서드를 읽어 JIT 컴파일한 뒤 실행한다.
- 따라서 ".NET을 보호한다"는 것은 "IL 코드와 메타데이터를 읽기 어렵게 만든다"는 의미이지, native 패커처럼 "기계어 코드를 압축해서 숨긴다"는 의미가 아니다.
- **OEP(Original Entry Point)라는 개념 자체가 native PE와 다르게 적용된다.** .NET EXE의 엔트리 포인트는 애초에 CLR 로더를 호출하는 작은 native 스텁이거나(구버전) 메타데이터의 엔트리 포인트 토큰을 가리키는 값이며, "압축 해제 후 점프할 원본 코드 주소"라는 개념 자체가 성립하지 않는다.

### ConfuserEx가 적용하는 보호 기법들
ConfuserEx는 오픈소스 .NET 난독화/보호 도구로, 다음과 같은 여러 보호를 조합해서 적용한다.

- **이름 난독화(Name Mangling)**: 클래스/메서드/필드 이름을 `a`, `b`, `c` 같은 의미 없는 이름으로 바꾼다.
- **제어 흐름 난독화(Control Flow Obfuscation)**: IL 수준에서 REV-0231(Control Flow Flattening)과 비슷한 원리로 분기 구조를 뒤섞는다.
- **문자열 암호화**: 문자열 리터럴을 암호화해서 저장하고, 실행 시 복호화 헬퍼 메서드를 호출해 복원한다 — native의 REV-0233/REV-0948과 개념은 같지만 IL 메서드 수준에서 이루어진다.
- **Anti-Tamper(변조 방지)**: 어셈블리의 IL 코드를 암호화해서 저장해두고, 모듈 초기화 시점에 CLR 내부 구조를 직접 건드려(리플렉션/네이티브 상호운용을 통해) 복호화한다. 이는 native 패커의 "전체 압축 해제"와 개념적으로 가장 유사한 부분이다.
- **리소스 암호화**: 임베디드 리소스도 암호화해서 저장한다.

### 왜 dnSpyEx를 쓰는가
IL 코드는 native 디스어셈블러(IDA/Ghidra의 x86 모드)로는 의미 있게 해석되지 않는다(REV-0136, REV-0611에서 다룬 "native 도구로 분석이 안 되는" 상황). dnSpyEx는 .NET 어셈블리를 열어 IL을 다시 C# 유사 코드로 디컴파일해주는 도구이며, Anti-Tamper가 걸려 있지 않은 일반 어셈블리라면 대부분의 로직을 곧바로 읽을 수 있다. Anti-Tamper가 걸린 경우에는 dnSpyEx만으로 바로 디컴파일이 안 되고, 별도의 언패킹 단계(공개된 ConfuserEx 언패커, 또는 de4dot 같은 범용 .NET 디난독화 도구)가 필요할 수 있다.

## 화면/코드에서 보이는 징후
- dnSpyEx로 열었을 때 클래스/메서드 이름이 전부 `#A0.#Bx.#Cy` 같은 형태
- 메서드를 더블클릭했을 때 "디컴파일 실패" 또는 예외 메시지가 뜸(Anti-Tamper 적용 시)
- 문자열 리터럴 자리에 `Class1.Method2(0x1A2B3C4D)` 같은 함수 호출이 대신 들어있음(문자열 복호화 헬퍼 호출)
- 모듈 초기화 메서드(`<Module>.cctor` 등)에 유난히 복잡한 코드가 들어있고 리플렉션/포인터 조작 관련 호출이 많이 보임

## 가장 먼저 할 것
native PE 언패킹 절차(OEP 찾기, 메모리 덤프)를 시도하기 전에, 먼저 이 파일이 정말 .NET 어셈블리인지부터 REV-0136/REV-0242 방식으로 재확인한다. 확인되었다면 dnSpyEx로 직접 열어보고, 메서드가 정상적으로 디컴파일되는지부터 확인한다. 정상적으로 보인다면 Anti-Tamper 없이 이름/문자열 난독화만 적용된 상태이므로 바로 코드 분석으로 들어갈 수 있다.

## 단계별 절차
1. REV-0136/REV-0242 절차로 .NET EXE임을 재확인
2. dnSpyEx로 파일 열기, 메서드 디컴파일 정상 여부 확인
3. 정상 디컴파일된다면: 이름 난독화만 있는 상태 — dnSpyEx의 리네임 기능으로 주요 클래스/메서드에 알아보기 쉬운 이름을 직접 붙여가며 분석
4. 문자열이 암호화되어 있다면: 복호화 헬퍼 메서드를 dnSpyEx에서 찾아 로직 확인(REV-0948과 유사한 접근을 IL 수준에서 적용)
5. 디컴파일 자체가 실패한다면: Anti-Tamper 적용 가능성 — 공개된 de4dot 같은 .NET 전용 디난독화 도구나 ConfuserEx 버전별 공개 언패커 존재 여부를 먼저 검색
6. 언패커가 없다면 dnSpyEx의 디버깅 기능(닷넷 어셈블리를 직접 실행하며 중단점 설정)으로 동적 분석을 병행

## 명령어/단축키
- dnSpyEx: 파일 열기(`Ctrl+O`), 어셈블리 트리에서 메서드 더블클릭으로 디컴파일 확인
- dnSpyEx 리네임: 항목 우클릭 → `Rename Class...`/`Rename Method...` (REV-0243 참고)
- dnSpyEx 디버깅: `Debug → Start Debugging` (어셈블리를 직접 실행하며 중단점 설정 가능)

## 출력 해석
- dnSpyEx가 메서드 본문을 정상적으로 C# 유사 코드로 보여주면 Anti-Tamper는 없는 상태다.
- "Decompile 실패" 또는 IL 명령어 나열만 나오고 C#으로 재구성이 안 된다면 Anti-Tamper 또는 복잡한 제어 흐름 난독화가 적용된 것이다.
- 문자열 복호화 헬퍼 메서드가 항상 정수 하나(토큰/인덱스)를 인자로 받는다면, 이는 암호화된 문자열 풀에서 인덱스로 값을 찾아 복호화하는 전형적인 ConfuserEx 문자열 보호 패턴이다.

## 흔한 실수
- .NET 바이너리인데 native PE 언패킹 절차(OEP 찾기, Scylla 덤프)를 그대로 적용하려는 것 — IL 코드에는 이 개념이 적용되지 않는다.
- 이름이 `#A0` 같은 형태로 바뀐 것만 보고 "코드가 암호화되었다"고 오해하는 것 — 이는 단순 이름 난독화이며 로직 자체는 그대로 dnSpyEx에서 읽을 수 있다.
- Anti-Tamper 적용 여부를 확인하지 않고 무작정 de4dot 같은 도구를 실행해서 오히려 어셈블리를 더 망가뜨리는 것 — 먼저 dnSpyEx로 직접 열어 실제 상태를 확인하는 것이 순서다.
- IL 명령어를 x86 어셈블리처럼 해석하려고 시도하는 것 — IL은 스택 기반의 별도 명령어 집합이며 REV-0245의 CIL-C# 대응표를 먼저 참고해야 한다.

## 막혔을 때 다음 체크
- .NET인지 native인지부터 다시 헷갈린다면 → REV-0136 .NET EXE인지 Native EXE인지 구분, REV-0242 .NET 바이너리 식별과 첫 접근
- IL 코드를 C# 관점에서 읽는 법이 필요하다면 → REV-0245 CIL IL 명령어를 C#과 연결해서 읽기
- 일반적인 .NET 난독화 기초 개념이 더 필요하다면 → REV-0247 .NET 난독화 기초
- dnSpyEx 자체 사용법이 헷갈린다면 → REV-0243 dnSpyEx로 .NET EXE 열기

## 미니 예제
```csharp
// dnSpyEx로 본 디컴파일 결과 (이름 난독화 + 문자열 암호화 적용 상태)
public class #A0
{
    public static void #B1()
    {
        Console.WriteLine(#C2.#D3(0x1A2B3C4D));   // 문자열 복호화 헬퍼 호출
    }
}
```
`#C2.#D3(0x1A2B3C4D)`가 문자열 복호화 헬퍼라면, dnSpyEx로 그 메서드 내부를 열어 알고리즘을 확인하고, 필요하다면 같은 로직을 별도 .NET 콘솔 프로젝트나 Python으로 재구현해 모든 암호화된 문자열을 일괄 복호화할 수 있다. 이는 native PE의 REV-0948과 목적은 같지만 대상이 IL 메서드라는 점이 다르다.

## 관련 글
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0247 — .NET 난독화 기초
- REV-0227 — 수동 언패킹 개념 OEP와 Dump

## 출처/검증
- ConfuserEx의 보호 기법 구성(이름 난독화, 제어 흐름 난독화, 문자열 암호화, Anti-Tamper, 리소스 암호화)은 ConfuserEx 공식 GitHub 저장소(mkaring/ConfuserEx) 문서를 기준으로 정리했다.
- .NET EXE의 실행 모델(CLR이 IL을 JIT 컴파일해서 실행)은 Microsoft 공식 .NET 문서(Common Language Runtime 개요)를 기준으로 확인했다.
- de4dot 같은 범용 .NET 디난독화 도구의 존재와 역할은 공개 저장소(de4dot) 설명을 참고했다(2026-09-09 검증).
