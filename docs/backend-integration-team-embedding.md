# mateon-backend 연동 가이드 — 팀 임베딩

`docs/api-contract-draft.md`가 "요청/응답 JSON이 어떤 모양인가"를 다룬다면, 이 문서는
**"백엔드 코드에서 언제, 어떻게 호출해야 하는가"**를 다룬다. mateon-backend가 Java 21 /
Spring Boot 기반이므로 예시 코드도 그 기준으로 작성한다(`RestClient`, Java record, Spring Data
JPA). 실제 패키지 구조·빈 이름은 백엔드 컨벤션에 맞게 바꿔 써도 된다.

**공통 전제 — AI 서버는 무상태다.** 이전 호출을 기억하지 않으므로, 뭔가 바뀔 때마다 "바뀐
부분만" 보내는 게 아니라 **그 시점의 전체 상태를 통째로 다시 보낸다.**

`intro_text`에서 활동 목표/방식/강도/초보자 여부를 추출할 때 AI 서버가 실제로 쓰는 지침은
[`prompts/team_soft_fields_extraction.txt`](../prompts/team_soft_fields_extraction.txt)에 있다.

## 사전 설정 — AI 서버 클라이언트

모든 엔드포인트가 `X-Internal-Secret` 헤더를 요구하므로, 공유 시크릿을 기본 헤더로 박아둔
`RestClient` 빈 하나를 만들어 재사용한다.

```java
@Configuration
public class MateonAiClientConfig {

    @Bean
    public RestClient mateonAiRestClient(
            @Value("${mateon-ai.base-url}") String baseUrl,
            @Value("${mateon-ai.internal-secret}") String internalSecret) {
        return RestClient.builder()
                .baseUrl(baseUrl)
                .defaultHeader("X-Internal-Secret", internalSecret)
                .build();
    }
}
```

`mateon-ai.internal-secret`은 AI 서버의 `.env`에 있는 `INTERNAL_SHARED_SECRET`과 같은 값이어야
한다(비밀 값이므로 두 서버 운영자끼리 별도 채널로 공유 — 저장소에 커밋하지 않는다).

---

## 언제 호출하는가

아래 중 하나라도 바뀌면 호출한다. 각각 다른 엔드포인트가 있는 게 아니라 **전부 같은
엔드포인트를 같은 방식으로** 호출한다 — 차이는 "이번엔 무엇이 바뀌었는지"뿐이고, 요청
바디에는 항상 팀의 **현재 전체 상태**를 담는다.

- 팀 생성
- 팀 소개글 수정
- 모집 역할(`recruiting_roles`) 변경
- 요구 스킬(`required_skills`) 변경
- **팀원 추가/삭제/역할 변경** — `current_members` 배열이 바뀌었을 때. AI 서버는 현재 구성을
  보고 "결핍 역할" 뉘앙스를 임베딩에 녹이기 때문에, 팀원이 바뀌면 재호출해야 그 뉘앙스가
  최신 상태를 반영한다.
- 공모전 분야(`contest_field`) 변경

## 호출 방식

```java
public record TeamMemberPayload(String role, int count) {}

public record TeamEmbeddingRefreshRequest(
        String introText,
        List<String> recruitingRoles,
        List<String> requiredSkills,
        List<TeamMemberPayload> currentMembers,
        String contestField
) {}

public record TeamEmbeddingRefreshResponse(
        List<String> missingFields,
        String embeddingText,
        List<Double> embeddingVector,
        Map<String, Object> metadata
) {}
```

```java
@Service
@RequiredArgsConstructor
public class TeamEmbeddingService {

    private final RestClient mateonAiRestClient;
    private final TeamRepository teamRepository;

    public void refreshEmbedding(Team team) {
        var request = new TeamEmbeddingRefreshRequest(
                team.getIntroText(),
                team.getRecruitingRoles(),
                team.getRequiredSkills(),
                team.getMembers().stream()
                        .map(m -> new TeamMemberPayload(m.getRole(), m.getCount()))
                        .toList(),
                team.getContestField()
        );

        var response = mateonAiRestClient.post()
                .uri("/internal/teams/embedding:refresh")
                .body(request)
                .retrieve()
                .body(TeamEmbeddingRefreshResponse.class);

        // AI 서버는 아무것도 저장하지 않는다 — 응답을 백엔드가 직접 저장해야 한다.
        team.setEmbeddingVector(response.embeddingVector()); // pgvector 컬럼
        team.setEmbeddingMetadata(response.metadata());       // jsonb 컬럼
        team.setMissingFields(response.missingFields());
        team.setLastEmbeddedAt(Instant.now());                // 신선도는 백엔드가 관리
        teamRepository.save(team);
    }
}
```

## 어디서 호출하는가

- `TeamService.createTeam(...)` 트랜잭션 커밋 후
- `TeamService.updateTeamProfile(...)` (소개글/모집 역할/요구 스킬/공모전 분야 수정 API) 끝에서
- `TeamMemberService.addMember(...)` / `removeMember(...)` / `changeMemberRole(...)` 끝에서

매번 같은 `refreshEmbedding(team)` 메서드를 재사용하면 된다 — 트리거별로 다른 로직을 만들
필요가 없다. DB 트랜잭션 커밋 이후(비동기 이벤트 리스너 등)에 호출하는 걸 권장한다 — AI 서버
호출이 실패해도 팀 생성/수정 자체가 롤백되지 않도록 하기 위해서다. 실패 시 재시도는 백엔드
쪽에서 결정할 일이며(이 훅은 멱등하므로 몇 번을 재시도해도 안전하다), AI 서버는 자체 재시도
큐를 갖지 않는다.

## 에러 처리

- `401`: `X-Internal-Secret` 누락/오류. 재시도해도 소용없다 — 설정값을 확인해야 한다.
- `422`: 요청 바디 검증 실패(필드 누락/타입 불일치). 백엔드 쪽 DTO와 AI 서버 스키마가
  어긋났다는 뜻이므로 `docs/api-contract-draft.md`와 대조해야 한다.
- `5xx` / 타임아웃: AI 서버 내부 OpenAI 호출 실패 등. 이 훅은 멱등하므로(같은 입력 → 같은
  결과) 안전하게 재시도할 수 있다.
