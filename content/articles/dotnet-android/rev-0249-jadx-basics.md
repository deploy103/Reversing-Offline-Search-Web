---
id: REV-0249
title: "JADX로 APK 분석 시작"
slug: "rev-0249-jadx-basics"
category: "dotnet-android"
difficulty: "beginner"
platform: [android]
architecture: [x86, x64]
format: [APK]
tools: ["JADX"]
keywords: ["JADX 사용법", "JADX-GUI", "APK 디컴파일", "JADX Gradle export", "안드로이드 리버싱 시작", "JADX 검색"]
aliases: ["JADX란", "JADX 설치", "JADX 단축키", "APK 자바 코드 보는 법", "JADX 프로젝트 export"]
symptom_keywords: ["JADX를 처음 켰는데 뭘 봐야할지 모름", "JADX에서 MainActivity를 못 찾음", "JADX 검색 기능을 어떻게 쓰는지 모름", "APK를 Gradle 프로젝트로 export하고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**JADX**는 APK(또는 `.dex`, `.jar`) 파일을 열어 안의 `classes.dex` 바이트코드를 자바 소스에 가까운 형태로 자동 디컴파일해주고, `AndroidManifest.xml`과 리소스까지 함께 복원해서 보여주는 무료 오픈소스 도구로, 대부분의 Android 앱 리버싱은 이 도구를 여는 것에서부터 시작한다.

## 언제 검색해야 하나
- JADX 또는 JADX-GUI를 처음 실행했는데 화면 구성이 낯설어서 어디를 봐야 할지 모를 때
- APK를 열었지만 앱이 시작하는 `MainActivity`나 특정 클래스를 어떻게 찾아야 하는지 모를 때
- 특정 문자열이나 메서드 이름으로 코드를 검색하고 싶은데 방법을 모를 때
- 디컴파일된 코드를 Android Studio 같은 IDE에서 통째로 열어보고 싶어서 Gradle 프로젝트로 export하는 방법이 궁금할 때

## 핵심 개념

### JADX와 JADX-GUI
JADX는 명령줄 도구(`jadx`)와 그래픽 인터페이스(`jadx-gui`) 두 형태로 배포된다. 명령줄 버전은 스크립트로 일괄 디컴파일할 때, GUI 버전은 사람이 직접 코드를 탐색하며 읽을 때 적합하다. 이 글은 실습 편의를 위해 주로 GUI(`jadx-gui`) 사용을 기준으로 설명한다.

### 화면 구성 한눈에 보기
JADX-GUI를 실행해서 APK를 열면 기본적으로 다음과 같이 구성된다.
- **좌측 트리** — 패키지(자바 패키지 계층) → 클래스 순으로 정리된 코드 트리와, `Resources`(리소스), `APK signature` 등의 추가 노드가 함께 표시된다.
- **중앙 코드 뷰(탭 영역)** — 클릭한 클래스를 디컴파일된 자바 코드로 보여준다.
- **하단 상태/로그 영역** — 디컴파일 진행 상황이나 오류 메시지가 표시된다.

### DEX 바이트코드도 결국 메타데이터를 보존한다
[REV-0248](./rev-0248-apk-structure.md)에서 다뤘듯 `classes.dex`는 Java/Kotlin 소스가 컴파일된 DEX 바이트코드다. .NET의 CIL과 마찬가지로 클래스명, 메서드명, 필드명 같은 메타데이터가 상당 부분 보존되어 있기 때문에, 별도 난독화가 없다면 JADX만으로도 원본 소스에 매우 근접한 코드를 즉시 얻을 수 있다. 다만 난독화 도구(ProGuard/R8 등)가 적용된 앱은 이름이 `a`, `b`, `c` 처럼 짧게 축약되어 있는 경우가 많다는 점은 .NET 난독화([REV-0247](./rev-0247-dotnet-obfuscation-basics.md))와 유사한 양상이다.

## 화면/코드에서 보이는 징후
- 좌측 트리 최상단에 앱 패키지명(예: `com.example.crackme`)이 폴더처럼 표시되고, 그 아래 각 클래스가 나열된다.
- 클래스를 열었을 때 코드 중간에 회색 주석으로 `/* JADX INFO: ... */`나 `// $FF: ...` 같은 문구가 붙어 있으면 디컴파일 과정에서 자동 추론/보정이 일어난 부분이다.
- 트리에서 `AndroidManifest.xml` 노드를 클릭하면 이진 XML이 사람이 읽을 수 있는 텍스트 XML로 자동 복원되어 보인다.

## 가장 먼저 할 것
JADX-GUI에 APK 파일을 드래그 앤 드롭한 뒤, 좌측 트리에서 `AndroidManifest.xml`을 먼저 열어 앱 패키지명과 시작 Activity(`intent-filter`에 `action android:name="android.intent.action.MAIN"`과 `category android:name="android.intent.category.LAUNCHER"`가 함께 있는 Activity)를 확인한다. 이 Activity가 앱을 실행했을 때 가장 먼저 뜨는 화면이므로, 코드 분석의 자연스러운 출발점이 된다.

## 단계별 절차

**1) APK 열기**
JADX-GUI를 실행하고 `File → Open File...` (단축키 `Ctrl+O`) 또는 창에 APK 파일을 드래그 앤 드롭한다. 디컴파일은 파일을 여는 즉시 백그라운드에서 진행되며, 큰 앱은 완료까지 시간이 걸릴 수 있다.

**2) AndroidManifest.xml에서 시작점 확인**
좌측 트리 상단의 `AndroidManifest.xml`을 클릭해서 패키지명과 `LAUNCHER` Activity를 확인한다. 이 클래스명을 기억해둔다(예: `com.example.crackme.MainActivity`).

**3) 트리에서 해당 클래스로 이동**
좌측 트리에서 패키지 계층을 따라 내려가거나, 아래 검색 기능을 이용해 바로 해당 클래스로 이동한다.

**4) 이름으로 검색하기**
`Ctrl+Shift+F` (Text Search, 코드 내용 검색) 또는 `Ctrl+N`/`Ctrl+J`(클래스/메서드 이름 검색, 버전에 따라 단축키가 다를 수 있음 — 상단 메뉴 `Navigation → Search`에서도 접근 가능)로 검색창을 열고 클래스명, 메서드명, 문자열 일부를 입력하면 일치 항목이 나열된다.

**5) 문자열/상수로 검색하기**
`Text Search`에서 플래그, 비밀번호 후보 같은 키워드(`flag`, `pass`, `secret` 등)를 검색하면 그 문자열이 등장하는 모든 클래스와 줄이 결과로 나온다. 이는 [REV-0246](./rev-0246-dotnet-strings-resources.md)에서 다룬 .NET 리터럴 검색과 동일한 목적의 기능이다.

**6) 호출 관계(xref) 확인하기**
메서드나 필드 이름을 우클릭하면 **Find Usage**(또는 유사한 이름의 메뉴, 버전에 따라 다름) 옵션으로 해당 요소가 코드 어디에서 참조/호출되는지 확인할 수 있다. 이는 ILSpy의 Analyze 기능과 같은 역할을 한다.

**7) 리소스 확인하기**
좌측 트리의 `Resources` 노드를 펼쳐 `res/values/strings.xml`, `res/layout/*.xml` 등을 확인한다. JADX가 `resources.arsc`를 자동으로 해석해서 이런 형태로 복원해준다.

**8) Gradle 프로젝트로 export하기**
`File → Save As Gradle Project...`를 선택하면 디컴파일된 전체 코드를 Android Studio에서 바로 열 수 있는 Gradle 프로젝트 형태로 저장한다. 이렇게 export하면 Android Studio의 전역 검색, 참조 찾기 등 IDE 수준의 강력한 탐색 기능을 활용할 수 있어서 코드량이 많은 앱을 분석할 때 유용하다. 순수 소스만 필요하면 `File → Save As Source...`로 소스 코드만 뽑아낼 수도 있다.

## 명령어/단축키
```text
Ctrl+O                      APK/DEX/JAR 파일 열기
Ctrl+Shift+F                 Text Search(코드 전체 텍스트/문자열 검색)
Navigation → Search           클래스/메서드 이름 검색
우클릭 멤버 → Find Usage       호출/참조 위치(xref) 찾기
File → Save As Gradle Project...   Android Studio용 Gradle 프로젝트로 export
File → Save As Source...      디컴파일된 소스만 파일로 저장
```

## 출력 해석
- 클래스 코드에 `/* renamed from: ... */` 같은 주석이 보이면, 원래 DEX 상의 이름과 JADX가 표시용으로 바꾼 이름이 다르다는 뜻이다(주로 Java 예약어 충돌 등 이유로 자동 변환).
- 메서드 본문이 텅 비어 있고 `// Could not decompile` 류의 메시지만 있으면 특정 최적화나 난독화로 인해 디컴파일이 실패한 것이며, 필요하면 JADX의 **Smali** 보기(로우레벨 DEX 어셈블리 표현)로 전환해서 원문을 확인해야 한다.
- Text Search 결과에서 같은 문자열이 여러 클래스에 나타나면, 공통 상수 클래스(예: `Constants.java`)에 정의되어 여러 곳에서 참조되는 값일 가능성이 높다.

## 흔한 실수
- APK를 열자마자 트리 전체를 처음부터 끝까지 훑으려는 것. 안드로이드 표준 프레임워크 클래스(`androidx.*`, `kotlin.*` 등)까지 전부 앱 소속인 것처럼 헤매지 말고, 우선 앱 자체 패키지명 아래만 집중해서 봐야 한다.
- `AndroidManifest.xml` 확인 없이 무작정 트리에서 그럴듯한 이름의 클래스를 찾아 헤매는 것. 시작 Activity를 먼저 확인하면 진입점을 훨씬 빠르게 찾을 수 있다.
- 디컴파일 실패 메시지를 보고 바로 포기하는 것. Smali 보기로 전환하면 원문 바이트코드 수준에서는 대부분 확인이 가능하다.
- Gradle 프로젝트로 export한 뒤 그대로 빌드하면 원본과 100% 동일하게 동작할 것이라 기대하는 것. 디컴파일 결과는 원본과 근접하지만, 서명이나 일부 리소스 참조, 난독화로 손실된 정보 등으로 인해 그대로 빌드/실행이 안 될 수도 있다.

### JADX 명령줄 버전 활용
GUI 없이 여러 APK를 한꺼번에 처리해야 한다면 명령줄 버전 `jadx`를 쓸 수 있다. `jadx -d output/ target.apk` 형태로 실행하면 GUI에서 `Save As Source...`로 얻는 것과 동일한 결과물(디컴파일된 자바 소스, 리소스, 매니페스트)이 지정한 폴더에 그대로 저장된다. CTF에서 여러 APK를 순서대로 훑어봐야 하거나, 결과물을 `grep` 같은 텍스트 검색 도구와 조합해서 빠르게 문자열을 찾고 싶을 때 특히 유용하다.

## 막혔을 때 다음 체크
- APK 내부 구조 자체가 헷갈리면 → [REV-0248 APK 파일 구조 기초](./rev-0248-apk-structure.md)
- 코드 이름이 죄다 `a`, `b`, `c`로 난독화되어 있으면, 대응 원리 자체는 .NET과 유사하므로 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)의 "동작 기준으로 판단하기" 전략을 참고한다.
- 바이트코드 명령어 수준까지 내려가서 읽는 감각을 먼저 잡고 싶으면(DEX와 명령어 집합은 다르지만 스택/레지스터 기반 바이트코드를 읽는 접근 자체는 참고가 된다) → [REV-0245 CIL IL 명령어를 C#과 연결해서 읽기](./rev-0245-cil-to-csharp.md)
- 네이티브 `.so` 라이브러리까지 분석해야 하면 Ghidra/IDA 등 네이티브 디스어셈블러로 넘어가야 하며, 이는 이 카테고리가 아니라 별도 정적 분석 카테고리를 참고한다.

## 미니 예제
`crackme.apk`를 JADX-GUI에 드래그 앤 드롭한다. 트리에서 `AndroidManifest.xml`을 열어보니 `com.example.crackme.MainActivity`가 `LAUNCHER` Activity로 지정되어 있다. 트리를 따라 `com.example.crackme` 패키지 아래 `MainActivity`를 클릭하면 다음과 같은 코드가 보인다고 하자.

```java
public class MainActivity extends AppCompatActivity {
    public void onCheckClick(View view) {
        String input = ((EditText) findViewById(R.id.editText)).getText().toString();
        if (input.equals("flag{test}")) {
            Toast.makeText(this, "Correct!", 0).show();
        } else {
            Toast.makeText(this, "Wrong!", 0).show();
        }
    }
}
```

`onCheckClick` 메서드 안에서 곧바로 `input.equals("flag{test}")` 비교가 눈에 보이므로, 이 시점에서 이미 검증 로직과 정답 문자열을 정적 분석만으로 확인할 수 있다. 만약 비교 대상 문자열이 코드에 직접 보이지 않고 리소스나 다른 상수 클래스에서 온다면, `Ctrl+Shift+F`로 해당 상수가 정의된 위치를 추가로 검색하면 된다.

## 관련 글
- REV-0248 — APK 파일 구조 기초
- REV-0247 — .NET 난독화 기초
- REV-0246 — .NET 문자열과 리소스 찾기

## 출처/검증
- JADX/JADX-GUI 기능(Text Search, Find Usage, Save As Gradle Project, Smali 보기) 및 단축키: JADX 공식 GitHub 저장소(skylot/jadx) README 및 위키 기준 (2026-09-08 확인).
- Android 앱 컴포넌트(Activity, LAUNCHER intent-filter) 개념: Android 공식 개발자 문서(developer.android.com) 기준.
