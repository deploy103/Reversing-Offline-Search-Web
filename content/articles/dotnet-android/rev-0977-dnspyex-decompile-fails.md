---
id: REV-0977
title: "dnSpyEx가 어셈블리를 디컴파일하지 못할 때"
slug: "rev-0977-dnspyex-decompile-fails"
category: "dotnet-android"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [.NET]
tools: [dnSpyEx]
keywords: ["dnSpyEx 디컴파일 실패", "Could not decompile", "System.BadImageFormatException", "NGen", "ReadyToRun", ".NET Core 어셈블리 열기 실패"]
aliases: ["dnSpyEx 코드가 안 보임", "dnSpyEx 열기 오류", "dnSpyEx 디컴파일 에러", "dnSpyEx exe 실행 안됨"]
symptom_keywords: ["dnSpyEx로 exe를 열었는데 코드가 안 보임", "Could not decompile 메시지가 뜸", "BadImageFormatException 오류", "메서드 본문이 텅 빔", "dnSpyEx가 파일을 아예 못 엶"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
dnSpyEx가 어셈블리를 열지 못하거나 특정 메서드에서 `Could not decompile`만 표시된다면, 원인은 대부분 파일이 애초에 .NET 어셈블리가 아니거나(네이티브 실행 파일), ReadyToRun/NGen처럼 미리 네이티브 코드로 컴파일된 부분이라 IL 자체가 없거나, 대상이 실제로는 참조하는 다른 DLL을 못 찾아서 로드가 실패한 경우다.

## 언제 검색해야 하나
- dnSpyEx에 파일을 드래그 앤 드롭했는데 트리에 아무것도 안 뜨거나 열기 자체가 실패할 때
- 특정 메서드를 클릭했더니 코드 영역에 `Could not decompile`이나 빈 화면만 나올 때
- 파일을 열자마자 `System.BadImageFormatException` 계열 오류 팝업이 뜰 때
- 분명 `.exe`인데 클래스 트리에 익숙한 네임스페이스가 하나도 안 보일 때

## 핵심 개념
dnSpyEx는 .NET 어셈블리(PE 파일 안에 CLR 메타데이터와 IL 코드가 들어있는 구조)를 대상으로 동작하는 도구다. 파일을 열었는데 문제가 생기는 경우는 크게 세 갈래로 나뉜다.

첫째, **애초에 .NET 어셈블리가 아닌 경우**다. C/C++로 빌드된 순수 네이티브 PE는 CLR 메타데이터 자체가 없으므로 dnSpyEx가 열어도 클래스 트리가 텅 비거나 열기 자체를 거부한다. 이건 dnSpyEx 버그가 아니라 애초에 대상이 틀린 것이다.

둘째, **IL이 아니라 미리 컴파일된 네이티브 코드(ReadyToRun, 과거의 NGen)가 섞인 경우**다. .NET Core/5+ 배포 시 성능을 위해 일부 메서드를 미리 네이티브 코드로 컴파일해 넣는 ReadyToRun(R2R) 방식이 흔한데, 이런 메서드는 원본 IL이 어셈블리 안에 그대로 안 남아있을 수 있어 dnSpyEx가 C#으로 되돌릴 소스가 없다.

셋째, **참조 어셈블리를 못 찾아 로드 자체가 실패하는 경우**다. 대상 DLL이 다른 커스텀 DLL이나 특정 버전의 프레임워크를 참조하는데, 그 DLL들이 같은 폴더에 없으면 dnSpyEx가 타입 해석에 필요한 정보를 얻지 못해 트리 일부가 깨지거나 예외를 던진다.

## 화면/코드에서 보이는 징후
- 파일을 열자마자 `Could not load file or assembly...` 또는 `System.BadImageFormatException` 팝업이 뜬다.
- Assembly Explorer 트리에 어셈블리 이름만 있고 그 아래 네임스페이스/클래스가 하나도 안 펼쳐진다.
- 특정 메서드를 클릭했을 때 코드 뷰에 `// Could not decompile method` 같은 회색 주석만 보이고 본문이 비어 있다.
- IL 모드로 전환해도 명령어가 거의 없거나 `.method` 시그니처만 있고 실제 IL 바디가 극단적으로 짧다.

## 가장 먼저 할 것
가장 먼저 상단 언어 드롭다운을 **IL**로 바꿔서 원문 CIL이 실제로 존재하는지 확인한다. IL 자체가 비어 있거나 극단적으로 짧다면 C# 디컴파일 실패는 dnSpyEx 문제가 아니라 애초에 그 메서드에 복원할 IL이 없는 것이다. IL이 정상적으로 보인다면 문제는 디컴파일러 자체의 한계이므로 다음 단계로 넘어간다.

## 단계별 절차
1. 파일이 진짜 .NET 어셈블리인지 먼저 확인한다. `dnSpyEx` 밖에서 `file` 명령이나 PE 헤더 검사 도구로 CLR 헤더(`.NET` 디렉터리 엔트리) 존재 여부를 확인해도 되고, 그냥 dnSpyEx가 여는 순간 트리가 정상적으로 펼쳐지는지로 판단해도 된다.
2. 열기 자체가 실패하면(`BadImageFormatException`) 대상 DLL과 같은 폴더에 있어야 할 참조 DLL들을 전부 같은 위치에 복사해 넣고 다시 연다.
3. 특정 메서드만 안 열리면 언어 드롭다운을 IL로 바꿔서 원문 CIL 존재 여부를 확인한다.
4. IL도 비어 있다면 ReadyToRun/NGen으로 미리 컴파일된 배포본일 가능성이 높다. 같은 프로그램의 IL 전용(비-R2R) 빌드나 원본 소스가 있다면 그쪽을 우선 사용한다.
5. 그래도 IL만 봐야 하는 상황이면, R2R 바이너리는 dnSpyEx 대신 네이티브 디스어셈블러(IDA/Ghidra) 관점으로 접근을 바꿔야 할 수도 있다는 점을 인지한다.
6. 참조 어셈블리 문제라면 `File → Open` 시 관련 DLL들도 함께 열어 두면 dnSpyEx가 타입 해석에 참고할 수 있다.

## 명령어/단축키
```text
언어 드롭다운 → IL              IL 원문 확인
File → Open                      참조 DLL 함께 열기
우클릭 어셈블리 → Go to Entry Point   진입점부터 다시 확인
Ctrl+Shift+K                      전체 트리에서 이름/문자열 재검색
```

## 출력 해석
- `BadImageFormatException`은 대부분 "이 파일은 CLR이 기대하는 포맷이 아니다"라는 뜻이며, 아키텍처 불일치(32비트 dnSpyEx로 64비트 전용 어셈블리를 열려는 경우 등)나 애초에 네이티브 파일인 경우 모두 이 메시지로 뭉뚱그려질 수 있다.
- IL 모드에서 메서드 본문에 `.maxstack`과 몇 줄의 `ldarg`/`call`/`ret`만 있고 그 이상이 없다면, 그 메서드가 실제로 아주 짧은 스텁이거나 R2R로 대체된 자리 표시자일 가능성이 크다.
- 트리에서 네임스페이스가 하나도 안 보이는데 어셈블리 자체는 열렸다면, 리플렉션 전용 로드나 손상된 메타데이터 헤더를 의심해야 한다.

## 흔한 실수
- 순수 네이티브 EXE를 dnSpyEx로 열어보고 "디컴파일이 안 된다"고 착각하는 것 — 애초에 .NET 파일인지부터 확인해야 한다.
- 참조 DLL 없이 대상 파일 하나만 달랑 열어놓고 타입 해석 오류를 dnSpyEx 버그로 오해하는 것.
- ReadyToRun으로 배포된 상용 .NET 앱을 만나고도 그 개념 자체를 몰라서 "왜 이 버전만 코드가 안 보이지"라고 헤매는 것.
- IL 모드로 전환도 안 해보고 C# 창이 비어 있다는 이유만으로 파일이 손상됐다고 단정하는 것.

## 막혔을 때 다음 체크
- 그냥 코드를 읽기만 하면 되는 상황이라면 → REV-0978 ILSpy에서 참조 어셈블리를 못 찾을 때
- IL 명령어 자체를 C#과 대응시켜 읽는 방법이 궁금하면 → REV-0245 CIL IL 명령어를 C#과 연결해서 읽기
- 어셈블리가 .NET인지 애초에 헷갈린다면 → REV-0242 .NET 바이너리 식별과 첫 접근

## 미니 예제
`Launcher.exe`를 dnSpyEx에 열었더니 `MainWindow` 클래스의 `OnLoad` 메서드에서 `// Could not decompile method: OnLoad`만 보였다고 하자. 언어 드롭다운을 IL로 바꿔보니 본문이 `ldarg.0 / call instance void [System.Private.CoreLib]... / ret` 세 줄뿐이었다. 이는 실제 로직이 다른 어셈블리(R2R로 미리 컴파일된 부분 또는 다른 DLL)에 위임된 스텁이라는 뜻이며, `Analyze` 기능으로 실제 구현체가 있는 참조 DLL을 함께 열어야 전체 흐름을 확인할 수 있다.

## 관련 글
- REV-0978 — ILSpy에서 참조 어셈블리를 못 찾을 때
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기

## 출처/검증
- dnSpyEx의 IL/C# 표시 전환 및 `Could not decompile` 동작은 dnSpyEx 공식 GitHub 저장소(dnSpyEx/dnSpy) 이슈 트래커 및 문서 기준으로 정리했다(2026-09-09 확인).
- ReadyToRun/NGen이 IL 대신 미리 컴파일된 네이티브 코드를 포함할 수 있다는 사실은 .NET 공식 문서("ReadyToRun compilation")의 설명과 일치한다.
