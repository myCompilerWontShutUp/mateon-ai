# mateon-ai ↔ mateon-backend API 계약 초안

`CLAUDE.md`의 "구현 로드맵" 1단계에서 공유하기로 한 초안. 실제 구현된 FastAPI 앱의 `/docs`
(OpenAPI)가 최종 스펙이며, 이 문서는 그 전에 백엔드 팀과 필드명·형태를 맞추기 위한 시작점이다.

## 핵심 원칙: AI 서버는 무상태(stateless)다

AI 서버는 데이터베이스를 갖지 않는다. 임베딩 벡터를 포함한 모든 영속 데이터는 백엔드가 저장·소유
하고, AI 서버는 **매 요청에 필요한 데이터를 전부 받아서 계산만 하고 반환**한다. 즉:

- 팀/유저 임베딩 벡터는 백엔드가 저장한다 (예: 백엔드 Postgres에 pgvector 확장 추가).
- 추천 계산 시 백엔드가 후보들의 임베딩 벡터를 요청 본문에 실어 보낸다 — AI 서버가 자체 DB에서
  조회하는 단계는 없다.
- 임베딩 갱신 훅은 AI 서버가 계산 결과(`embedding_text`, `embedding_vector`, `metadata`,
  `missing_fields`)를 반환만 하고, 저장은 백엔드가 한다. `last_embedded_at` 같은 신선도 정보도
  전적으로 백엔드가 관리한다 — AI 서버는 이 값 자체를 모른다.

**미확정으로 표시된 부분은 백엔드 팀 확인이 필요하다.**

- ID 타입: 아래 예시는 `user_id`/`team_id`/`contest_id`/`sender_id`/`receiver_id`/`intent_id`를
  정수(Long)로 가정했다 (Spring Data JPA 기본 전략). UUID를 쓴다면 타입을 맞춰야 한다.
- 내부 훅 엔드포인트(`/internal/**`) 인증 방식: 공유 시크릿 헤더(예: `X-Internal-Secret`)를
  가정했다.
- 에러 응답 포맷: FastAPI 기본 `{"detail": "..."}` 형태를 가정했다.

---

## 1. 매칭 의도 슬롯 추출 — `POST /intents/extract`

제안 기능(USER_TO_TEAM)의 재질문 흐름에 쓰인다. **stateless** — 매 호출마다 지금까지 모인 컨텍스트
전체를 다시 보낸다. AI 서버는 추출·임베딩만 하고 아무것도 저장하지 않는다 — `missing_fields`가
비어 있으면 백엔드가 이 결과로 `MatchingIntentSlot`을 만들고 자체 ID를 채번해서 저장한다.

요청:
```json
{
  "self_introduction": "백엔드 경험은 없지만 프론트엔드를 1년 해봤고, 이번엔 풀스택 프로젝트에서 성장하고 싶습니다.",
  "profile": { "school": "OO대학교", "major": "컴퓨터공학" },
  "conversation_answers": { "activity_goal": "포트폴리오용 프로젝트" }
}
```

응답 (필수 항목 미완성 — 재질문 필요):
```json
{
  "missing_fields": ["desired_roles", "experience_level"],
  "extracted": {
    "desired_roles": [],
    "skills": ["React", "TypeScript"],
    "interests": [],
    "activity_goal": "포트폴리오용 프로젝트",
    "activity_style": null,
    "experience_level": null
  },
  "embedding_text": null,
  "embedding_vector": null
}
```

응답 (완성됨 — 임베딩까지 포함):
```json
{
  "missing_fields": [],
  "extracted": {
    "desired_roles": ["BE"],
    "skills": ["React", "TypeScript"],
    "interests": ["커머스"],
    "activity_goal": "포트폴리오용 프로젝트",
    "activity_style": "주 2회 오프라인",
    "experience_level": "beginner"
  },
  "embedding_text": "...",
  "embedding_vector": [0.0123, -0.0456, "... 1536개"]
}
```

---

## 2. 팀 임베딩 계산 — `POST /internal/teams/embedding:compute`

팀 생성/수정 시 백엔드가 호출. AI 서버는 계산 결과만 반환하고 저장하지 않으므로 **멱등성은
자연히 보장된다** — 같은 입력이면 같은 출력이다 (LLM 비결정성은 있을 수 있으나 저장 상태 충돌은
없다). `team_id`는 응답에 필요 없다 — 백엔드가 이 결과를 자기 DB의 해당 `team_id` 행에 저장한다.

요청:
```json
{
  "intro_text": "커머스 플랫폼을 만드는 4인 팀입니다. BE 1명이 부족합니다.",
  "recruiting_roles": ["BE"],
  "required_skills": ["Spring Boot", "PostgreSQL"],
  "current_members": [
    { "role": "FE", "count": 2 },
    { "role": "Design", "count": 1 }
  ],
  "activity_goal": "공모전 수상",
  "activity_style": "주 2회 오프라인",
  "activity_intensity": "high",
  "contest_field": "커머스",
  "beginner_friendly": true
}
```

응답:
```json
{
  "missing_fields": [],
  "embedding_text": "...",
  "embedding_vector": [0.0123, -0.0456, "... 1536개"],
  "metadata": {
    "recruiting_roles": ["BE"],
    "required_skills": ["Spring Boot", "PostgreSQL"],
    "activity_style": "주 2회 오프라인"
  }
}
```

---

## 3. 제안 추천 — `POST /recommendations/user-to-team`

백엔드가 후보 팀들의 임베딩 벡터를 자기 DB에서 꺼내 요청에 실어 보낸다.

요청:
```json
{
  "query_embedding_vector": [0.01, -0.02, "... 1536개"],
  "candidates": [
    {
      "candidate_id": 17,
      "embedding_vector": [0.03, 0.04, "... 1536개"],
      "metadata": { "recruiting_roles": ["BE"], "beginner_friendly": true }
    },
    {
      "candidate_id": 42,
      "embedding_vector": [0.05, -0.01, "... 1536개"],
      "metadata": { "recruiting_roles": ["FE"], "beginner_friendly": false }
    }
  ]
}
```

응답:
```json
{
  "recommendations": [
    { "candidate_id": 17, "score": 0.91, "label": "BE 결핍 보완에 적합" },
    { "candidate_id": 42, "score": 0.77, "label": "활동 방식 일치" }
  ]
}
```

## 4. 역제안 추천 — `POST /recommendations/team-to-user`

요청/응답 형태는 3번과 동일하다 (`query_embedding_vector`는 팀의 deficit 임베딩,
`candidates[].candidate_id`는 `user_id`).

## 5. 추천 상세 이유 (lazy) — `POST /recommendations/reason`

AI 서버가 아무것도 저장하지 않으므로, 이유 생성에 필요한 컨텍스트(팀 소개/유저 프로필 요약,
매칭 점수 구성요소 등)를 백엔드가 요청에 함께 실어 보내야 한다. 정확한 필드는 3~4단계에서
reason 생성 프롬프트를 설계하며 확정 — 아래는 형태 예시.

요청:
```json
{
  "direction": "USER_TO_TEAM",
  "candidate_summary": "React/TypeScript 경험, 초보자, 포트폴리오용 프로젝트 희망",
  "target_summary": "커머스 플랫폼, BE 1명 결핍, 주 2회 오프라인 활동",
  "score_breakdown": { "similarity": 0.8, "role_match": 1.0, "beginner_fit": 0.9 }
}
```

응답:
```json
{ "reason": "React/TypeScript 경험이 있고, 이 팀이 필요로 하는 BE 결핍을 보완할 수 있는 활동 방식을 갖추고 있습니다." }
```

## 6. 최종 제안 조립 — `POST /proposals/user-to-team`

사용자가 추천 목록에서 팀을 선택한 시점에 호출. `proposal_id`는 이 응답에 없다 — 백엔드가
저장하면서 채번한다. `synergy_score`는 추천 단계에서 이미 계산된 값을 백엔드가 그대로 넘겨줄지,
AI 서버가 임베딩을 다시 받아 재계산할지는 3단계에서 정한다 — 아래는 전자(재사용) 기준 예시.

요청:
```json
{
  "user_id": 203,
  "team_id": 17,
  "contest_id": 5,
  "sender_id": 203,
  "receiver_id": 17,
  "intent_id": 88,
  "synergy_score": 0.91,
  "candidate_summary": "React/TypeScript 경험, 초보자",
  "target_summary": "커머스 플랫폼, BE 1명 결핍"
}
```

응답 (`ProposalSchema`):
```json
{
  "direction": "USER_TO_TEAM",
  "user_id": 203,
  "team_id": 17,
  "contest_id": 5,
  "sender_id": 203,
  "receiver_id": 17,
  "intent_id": 88,
  "synergy_score": 0.91,
  "portfolio_role_fit_score": null,
  "summary": "React/TypeScript 경험을 바탕으로 이 팀의 BE 결핍을 보완하고 싶습니다.",
  "message": "안녕하세요, 팀의 커머스 프로젝트에 관심이 있어 지원합니다..."
}
```

## 7. 최종 역제안 조립 — `POST /proposals/team-to-user`

요청/응답 구조는 6번과 동일, `direction: "TEAM_TO_USER"`, `portfolio_role_fit_score` 채워짐.
