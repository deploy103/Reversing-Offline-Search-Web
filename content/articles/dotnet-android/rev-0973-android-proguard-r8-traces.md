---
id: REV-0973
title: "Android 난독화(ProGuard/R8) 흔적 알아보기"
slug: "rev-0973-android-proguard-r8-traces"
category: "dotnet-android"
difficulty: "intermediate"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [JADX]
keywords: ["ProGuard", "R8", "mapping.txt", "코드 슈링킹 인라이닝", "짧은 클래스 이름 a b c", "안드로이드 난독화 매핑"]
aliases: ["proguard 흔적 확인", "r8 난독화 우회", "mapping.txt 복원", "안드로이드 클래스 이름이 a b c인 이유"]
symptom_keywords: ["클래스 이름이 a b c로만 되어 있다", "메서드가 통째로 사라진 것 같다", "코드가 원래 구조와 다르게 합쳐져 있다", "mapping.txt가 뭔지 모르겠다"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ProGuard와 그 후속인 R8은 안드로이드 앱 빌드 시 자동으로 적용되는 코드 슈링킹(shrinking, 안 쓰는 코드 제거)·최적화(inlining 등)·난독화(이름 압축) 도구여서, 릴리스 APK에서 클래스/메서드 이름이 `a`, `b`, `c`로 짧아지고 일부 메서드가 사라지거나 합쳐진 것처럼 보이는 것은 대부분 악의적 난독화가 아니라 **표준 빌드 과정에서 자동으로 벌어지는 일**이라는 점을 이해하면, 서드파티 난독화 도구가 아니라 그냥 기본 빌드 설정만 걸린 앱과 진짜 강한 난독화가 걸린 앱을 구분해서 분석 전략을 다르게 세울 수 있다.

## 언제 검색해야 하나
- JADX로 열었더니 클래스/메서드/필드 이름이 짧은 알파벳(`a.b.c`, `zza`, `zzb`)으로 대량으로 바뀌어 있는데 이게 특수 난독화 도구인지 기본 빌드 설정인지 헷갈릴 때
- 원래 있어야 할 것 같은 메서드가 안 보이거나, 여러 메서드가 하나로 합쳐진 것처럼 코드가 짧아져 있을 때
- `mapping.txt`(또는 `mapping-*.txt`)라는 파일 이름을 들어봤는데 이게 무엇이고 왜 있으면 분석이 쉬워지는지 모를 때
- 최적화(inlining, 클래스 병합)로 인해 실제 실행 순서와 디컴파일된 코드 구조가 미묘하게 달라 보일 때
- 앱이 ProGuard/R8만 쓰는지, 아니면 그 위에 [REV-0247](./rev-0247-dotnet-obfuscation-basics.md) 계열의 상용 난독화까지 추가로 걸려 있는지 판단하고 싶을 때

## 핵심 개념

### ProGuard/R8이 하는 세 가지 일
안드로이드 앱을 릴리스(release) 빌드로 만들 때, Android Gradle Plugin은 기본적으로(또는 `minifyEnabled true` 설정 시) ProGuard 규칙 문법을 그대로 계승한 **R8**(ProGuard의 후속 대체 도구, 현재 안드로이드 공식 기본값)을 적용한다. R8은 세 가지 작업을 한 번에 수행한다.
1. **Shrinking(슈링킹)**: 앱 진입점(액티비티, 매니페스트에 선언된 컴포넌트 등)에서 도달 불가능한 것으로 판단된 클래스/메서드/필드를 제거한다. 즉 소스에는 있었지만 실행 경로상 절대 호출되지 않는 코드는 최종 APK에서 아예 사라질 수 있다.
2. **Optimization(최적화)**: 짧은 메서드 인라이닝, 사용하지 않는 인자 제거, 클래스 병합(비슷한 역할의 여러 클래스를 하나로 합침) 등 성능/크기를 위한 코드 변형을 수행한다. 이 때문에 디컴파일된 코드가 원본 소스와 구조적으로 달라 보일 수 있다(로직 자체는 동일).
3. **Obfuscation(난독화/이름 압축)**: 앱 외부에 노출될 필요가 없는 클래스/메서드/필드 이름을 `a`, `b`, `c`, `a.a`, `a.b` 같은 극도로 짧은 이름으로 바꾼다. 이름을 최대한 짧게 만들어서 `classes.dex`의 문자열 풀 크기(따라서 앱 용량)를 줄이는 것이 원래 목적이며, 부수적으로 분석을 어렵게 만드는 효과도 있다.

### 왜 이것이 "악성 난독화"와는 다른가
ProGuard/R8은 [REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 .NET용 상용 난독화 도구(ConfuserEx 등)처럼 제어 흐름을 의도적으로 뒤섞거나(control flow flattening) 문자열을 암호화하는 기능은 기본적으로 갖고 있지 않다(단, R8 8.x 이후 옵션으로 일부 문자열/리소스 난독화 기능이 추가되는 추세이므로 버전에 따라 다를 수 있다). 즉 R8만 걸린 앱은 **이름만 짧아졌을 뿐 제어 흐름과 데이터 흐름 자체는 원본 로직과 동일**하다는 점이 중요한 차이다. 이는 실전에서 "이름이 다 깨졌다고 겁먹지 않아도 되는" 경우가 대부분이라는 뜻이다.

### mapping.txt — 개발자에게는 있지만 공격자에게는 없는 열쇠
R8이 난독화를 적용하면, 원본 이름과 난독화된 이름의 대응표인 **`mapping.txt`**가 빌드 산출물로 함께 생성된다(`app/build/outputs/mapping/release/mapping.txt` 등). 개발자는 이 파일을 보관해두었다가 나중에 크래시 리포트에 찍힌 난독화된 이름(`a.b.c`)을 원래 이름으로 역매핑해서 디버깅하는 데 쓴다. **CTF/분석 대상 APK를 받을 때 이 `mapping.txt`가 함께 제공되는 경우는 거의 없으므로**, 분석자는 이름 복원 없이 동작 기반으로 분석해야 하는 것이 기본 전제다. 다만 문제 출제자가 실수로 또는 의도적으로 `mapping.txt`를 함께 배포했다면, JADX/Android Studio에서 이 파일을 불러와 원래 이름으로 되돌려볼 수 있다.

### 클래스/메서드가 통째로 사라졌을 때
Shrinking 때문에 소스코드에는 있었지만 최종 APK에는 없는 클래스/메서드가 있을 수 있다. 이것이 "숨겨진 로직"이 아니라 진짜로 안 쓰여서 제거된 코드인지 확인하려면, 매니페스트에 선언된 컴포넌트([REV-0250](./rev-0250-androidmanifest-clues.md))부터 시작해 실제로 호출되는 코드 경로만 남아 있다는 전제를 갖고 분석 범위를 좁히면 된다. 반대로, 리플렉션으로만 호출되는 클래스는 R8이 정적으로 도달 불가능하다고 오판해 실수로 제거하지 않도록, 개발자가 `proguard-rules.pro`에 `-keep` 규칙을 넣어 보존을 명시하는 경우가 많다 — 즉 **살아남은 리플렉션 호출 대상 클래스는 오히려 keep 규칙이 걸린 "중요한" 클래스일 가능성**이 있다는 역발상도 가능하다.

## 화면/코드에서 보이는 징후
- 클래스/메서드/필드 이름이 `a`, `b`, `aa`, `ab`처럼 극도로 짧고, 패키지 계층 구조까지 `a.a.a.a` 식으로 납작해져 있다.
- Google Play 서비스 등 서드파티 라이브러리 코드에서 `zza`, `zzb`(구글 라이브러리 특유의 R8 접두사 패턴)로 시작하는 이름이 대량으로 보인다 — 이는 해당 라이브러리가 이미 난독화된 상태로 배포됐다는 뜻이며 앱 자체의 난독화와는 별개다.
- 원래 있어야 할 것 같은 메서드가 검색해도 안 나오거나(shrinking), 여러 단계였을 로직이 한 메서드 안에 그대로 풀려서 들어가 있다(inlining).
- `assets/`나 별도 배포 자료에 `mapping.txt`가 포함되어 있는(드문) 경우.

## 가장 먼저 할 것
클래스 트리 전체가 짧은 이름으로 뒤덮여 있다면, 먼저 매니페스트([REV-0250](./rev-0250-androidmanifest-clues.md))에 선언된 액티비티/서비스 이름부터 확인한다. 이 이름들은 R8이 외부(안드로이드 시스템)에서 참조해야 하므로 원본 이름이 그대로 유지되는 경우가 많아, 여기서부터 호출 그래프를 따라 들어가면 실제 분석 시작점을 잡기 쉽다.

## 단계별 절차
1. `AndroidManifest.xml`([REV-0250](./rev-0250-androidmanifest-clues.md))에서 진입점이 되는 컴포넌트(주 액티비티 등)의 전체 클래스 이름을 확인한다. 이 이름은 대개 난독화되지 않는다.
2. JADX에서 그 클래스로 이동해 `onCreate` 등 생명주기 메서드부터 코드를 읽기 시작한다.
3. `mapping.txt`가 배포에 포함되어 있는지 확인한다. 있다면 JADX/Android Studio에서 로드해 이름을 복원한다.
4. 이름이 짧아진 클래스라도 로직(조건문, 반복문 구조)은 원본과 동일하므로, 이름 대신 동작(무슨 값을 비교하고 무엇을 반환하는지)으로 분석을 진행한다.
5. 제어 흐름이 심하게 뒤섞이거나 문자열이 암호화되어 있다면, R8 기본 동작 범위를 넘어선 추가 난독화(상용 도구, 커스텀 난독화)가 있다고 의심하고 별도 대응을 검토한다.

## 명령어/단축키
```text
JADX-GUI: Ctrl+Alt+H            클래스 계층(Hierarchy) 보기 — 상속 관계로 실제 역할 추정
JADX-GUI: File → Load mapping   mapping.txt가 있을 때 원본 이름 복원(버전에 따라 메뉴 위치 다름)
```
```bash
# 매니페스트에서 진입점 컴포넌트 이름 확인 (apktool 디코딩 후)
grep -A2 "android:name" out/AndroidManifest.xml | grep -i activity

# mapping.txt가 배포물에 포함되어 있는지 확인
find . -iname "mapping*.txt"
```

## 출력 해석
- `mapping.txt`의 각 줄은 `원본이름 -> 난독화이름:` 형태다(클래스 라인). 메서드/필드 라인은 들여쓰기되어 `원본시그니처 -> 난독화이름` 형태로 이어진다. 이 파일을 JADX에 로드하면 트리 전체가 원본 이름으로 복원된다.
- 매니페스트에 나온 진입점 클래스 이름이 트리에서 이미 짧은 이름(`a.b.MainActivity`가 아니라 `a.b.c`)으로도 보인다면, R8의 `-keep` 규칙이 그 클래스의 이름까지는 보존하지 않았다는 뜻이다(패키지/클래스 구분 없이 코드 검색으로 접근해야 한다).
- `zza`, `zzb` 패턴이 보이는 클래스는 대개 Google Play Services/Firebase 같은 서드파티 SDK이므로, 이 부분은 앱 고유 로직이 아닐 가능성이 높아 분석 우선순위에서 낮춰도 된다.

## 흔한 실수
- ProGuard/R8이 걸린 것을 보고 [REV-0247](./rev-0247-dotnet-obfuscation-basics.md)에서 다룬 상용 난독화 도구 수준의 강한 방어(제어 흐름 평탄화, 문자열 암호화)까지 걸려 있다고 지레짐작하고 과도하게 대비하는 것 — 기본 R8은 이름 압축과 최적화가 전부인 경우가 대부분이다.
- shrinking으로 제거된 코드를 "숨겨진 비밀 로직"이라고 착각하고 존재하지도 않는 코드를 찾으려 헤매는 것 — 매니페스트 기준으로 실제 도달 가능한 코드만 최종 APK에 남는다는 전제를 기억해야 한다.
- 서드파티 라이브러리의 `zza`/`zzb` 이름까지 앱 고유 로직으로 착각해서 분석 시간을 낭비하는 것.
- `mapping.txt`가 없다고 분석이 불가능하다고 포기하는 것 — 이름이 없어도 로직 자체는 그대로 보존되어 있으므로 동작 기반 분석이 항상 가능하다.
- `-keep` 규칙으로 이름이 보존된 클래스가 왜 유독 원래 이름 그대로인지 이유를 궁금해하지 않고 지나치는 것 — 개발자가 리플렉션 등으로 참조하기 때문에 일부러 보존한 경우가 많아, 오히려 그 클래스가 분석 우선순위가 높은 핵심 로직일 단서가 된다.

## 막혔을 때 다음 체크
- 매니페스트에서 진입점을 찾는 구체적 방법이 헷갈리면 → [REV-0250 AndroidManifest.xml에서 단서 찾기](./rev-0250-androidmanifest-clues.md)
- 이름이 다 깨진 상태에서 실제로 코드를 읽어나가는 요령이 더 필요하면 → [REV-0247 .NET 난독화 기초](./rev-0247-dotnet-obfuscation-basics.md)(이름 대신 동작으로 판단하는 전략은 플랫폼과 무관하게 동일하게 적용된다)
- JADX 옵션(`--deobf` 등)으로 이름을 어느 정도 자동 복원하고 싶으면 → [REV-0968 JADX/apktool 옵션 빠른 참조](./rev-0968-jadx-apktool-options-quickref.md)
- 코드가 아니라 리소스 쪽에 힌트가 있는지 확인하고 싶으면 → [REV-0972 Android 리소스(resources.arsc)에서 단서 찾기](./rev-0972-android-resources-arsc-clues.md)

## 미니 예제
JADX로 열어보니 진입점 액티비티만 매니페스트 그대로 `com.example.ctf.MainActivity`이고, 나머지 클래스는 전부 `com.example.ctf.a`, `com.example.ctf.b`처럼 짧아져 있다.
```java
public class MainActivity extends Activity {
    public void onCheckClick(View v) {
        String input = ((EditText) findViewById(R.id.editInput)).getText().toString();
        boolean ok = a.a(input);   // 짧은 이름의 클래스 a, 메서드 a
        Toast.makeText(this, ok ? "OK" : "FAIL", Toast.LENGTH_SHORT).show();
    }
}
```
`a.a(input)`으로 이동해보면 원본 소스에서는 `Validator.checkPassword(String)`였을 법한 로직이 그대로(이름만 바뀐 채) 들어 있다.
```java
public class a {
    public static boolean a(String s) {
        return s.equals("s3cr3t");
    }
}
```
이름이 `a.a`로 극도로 짧아졌지만 로직 자체(`equals` 비교)는 원본과 동일하게 보존되어 있다는 것을 알 수 있다. 이런 식으로 R8 난독화는 "이름을 못 알아보는 것"이 문제일 뿐, 코드를 한 줄씩 읽는 능력만 있으면 분석 자체는 일반 코드와 다르지 않다.

## 관련 글
- REV-0247 — .NET 난독화 기초
- REV-0250 — AndroidManifest.xml에서 단서 찾기
- REV-0968 — JADX/apktool 옵션 빠른 참조
- REV-0972 — Android 리소스(resources.arsc)에서 단서 찾기
- REV-0249 — JADX로 APK 분석 시작

## 출처/검증
- ProGuard/R8의 shrinking/optimization/obfuscation 세 단계 구분 및 `mapping.txt` 생성 방식은 Android 공식 개발자 문서(developer.android.com, "Shrink, obfuscate, and optimize your app")를 기준으로 정리했다.
- R8이 ProGuard의 후속으로 Android Gradle Plugin의 기본 코드 축소/난독화 도구가 되었다는 사실은 Android 공식 릴리스 노트 및 개발자 문서를 기준으로 확인했다.
- Google Play Services/Firebase 라이브러리의 `zza`/`zzb` 형태 이름 패턴은 공개된 해당 라이브러리 AAR 배포본에서 실제로 반복 관찰되는 명명 규칙이다 (2026-09-09 확인).
