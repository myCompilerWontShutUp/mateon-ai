# mateon-ai ↔ mateon-backend API 계약 초안

`CLAUDE.md`의 "구현 로드맵" 1단계에서 공유하기로 한 초안이며, 5단계(계약 최종 확정) 기준으로
실제 구현과 맞춰 갱신했다. 실제 구현된 FastAPI 앱의 `/docs`(Swagger UI)와 `docs/openapi.json`
(내보낸 스펙 원본)이 가장 정확한 최종 소스이고, 이 문서는 그걸 사람이 읽기 편하게 예시와 함께
설명하는 보조 자료다 — 백엔드 팀은 이 문서로 먼저 감을 잡고, 정확한 타입/필수 여부는
`docs/openapi.json`으로 교차 확인하면 된다.

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
- 역할/경험 수준 코드 값: `desired_roles`/`recruiting_roles`는 `BE`/`FE`/`Design`/`PM`/`Data`,
  `experience_level`은 `beginner`/`intermediate`/`advanced`로 AI 서버가 임의로 정해서 쓰고
  있다. 백엔드의 실제 코드 체계와 다르면 역할 일치도 스코어링이 항상 0이 된다 — 반드시 맞춰야
  한다.
- 에러 응답 포맷: FastAPI 기본 `{"detail": "..."}` 형태를 가정했다.

**임베딩 벡터는 항상 정확히 1536개(float)여야 한다.** `text-embedding-3-small` 차원 기준으로
스키마 레벨에서 강제한다 — 짧거나 길면 어느 필드가 몇 개였는지 알려주는 `422`를 즉시 반환한다
(요청 전체가 500으로 죽지 않는다).

**인증**: `/internal/**` 훅뿐 아니라 **모든 엔드포인트**(`/intents/extract`,
`/recommendations/*`, `/proposals/*` 포함)에 공유 시크릿 헤더 `X-Internal-Secret`을 요구한다.
AI 서버는 mateon-backend만 호출하고 프론트엔드가 직접 부르는 경우나 AI 서버발 콜백은 없다고
확정되어, 서버 간 호출 전용으로 통일했다(CORS 해당 없음).

**LLM 프롬프트는 `prompts/`에 외부 파일로 분리돼 있다.** 각 엔드포인트가 실제로 어떤 지침으로
텍스트를 생성하는지 궁금하면 코드가 아니라 이 폴더의 `.txt` 파일을 보면 된다 — 아래 각 절에
해당 파일명을 명시한다. 생성된 텍스트(summary/message/reason)가 설계 원칙(절대평가 금지 등)을
지키는지는 `scripts/judge_outputs.py`(LLM-as-judge, 수동 실행)로 점검한다.

---

## 1. 매칭 의도 슬롯 추출 — `POST /intents/extract`

제안 기능(USER_TO_TEAM)의 재질문 흐름에 쓰인다. **stateless** — 매 호출마다 지금까지 모인 컨텍스트
전체를 다시 보낸다. AI 서버는 추출·임베딩만 하고 아무것도 저장하지 않는다 — `missing_fields`가
비어 있으면 백엔드가 이 결과로 `MatchingIntentSlot`을 만들고 자체 ID를 채번해서 저장한다.

> 추출 프롬프트: [`prompts/user_intent_extraction.txt`](../prompts/user_intent_extraction.txt)
> (역할 코드/경험 수준 정규화 규칙이 여기 있다).
> 챗봇 응답 생성 프롬프트: [`prompts/user_intent_chat_reply.txt`](../prompts/user_intent_chat_reply.txt)
> (재진술/유도 질문/방어 응답 4가지 규칙이 여기 있다).

요청:
```json
{
  "messages": [
    { "id": 1, "message": "백엔드 경험은 없지만 프론트엔드를 1년 해봤고, 이번엔 풀스택 프로젝트에서 성장하고 싶습니다. OO대학교 컴퓨터공학과이고, 포트폴리오용 프로젝트를 찾고 있습니다." }
  ]
}
```

자기소개서든 재질문 답변이든 "사용자가 한 말"이라는 점에서 같은 종류의 데이터라 `messages`
하나로 통합했다(2026-07-15 변경 — 이전엔 `self_introduction`/`profile`/`conversation_answers`
세 필드로 나눴는데, AI 서버는 이 값들을 구조적으로 읽지 않고 LLM 프롬프트에 그대로 이어붙이기만
해서 굳이 나눌 이유가 없었다). 재질문 답변을 받으면 그 답변을 새 메시지로 `messages` 배열에
append해서(`id`는 순서대로 증가) 통째로 다시 보낸다 — 순서가 배열 순서로 자연히 보존된다.

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
  "embedding_vector": null,
  "assistant_message": "포트폴리오용 프로젝트를 찾고 있구나! 혹시 어떤 역할로 참여하고 싶은지 말해줄 수 있어? (백엔드/프론트엔드/기획/디자인/데이터)"
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
  "embedding_vector": [0.0123, -0.0456, "... 1536개"],
  "assistant_message": "너의 관심사는 백엔드구나! 너의 취향을 조금 알 것 같아. 이건 내가 추천해주는 팀 후보야."
}
```

`assistant_message`는 프론트가 그대로 화면에 보여주면 되는 챗봇 문구다(2026-07-15 추가) —
재진술 + 다음 질문 하나(누락 필드가 있을 때), 또는 재진술 + 추천 시작 안내(다 채워졌을 때),
또는 응답이 맥락과 전혀 안 맞을 때는 방어 문구로 자동 대체된다. **프론트/백엔드는 더 이상
`missing_fields`를 보고 질문 문구를 직접 조립할 필요가 없다** — `missing_fields`는 "무엇이
빠졌는지"를 판단하는 용도로만 쓰면 된다(예: 다 채워졌는지 확인). 한 번에 최대 하나의 필드만
묻는다 — 여러 개가 비어 있어도 우선순위가 높은 것부터 하나씩, 답변을 받을 때마다 다음 질문으로
넘어간다.

---

## 2. 팀 임베딩 계산 — `POST /internal/teams/embedding:refresh`

팀 생성/수정 시 백엔드가 호출. AI 서버는 계산 결과만 반환하고 저장하지 않으므로 **멱등성은
자연히 보장된다** — 같은 입력이면 같은 출력이다 (LLM 비결정성은 있을 수 있으나 저장 상태 충돌은
없다). `team_id`는 요청/응답 어디에도 없다 — 백엔드가 이 결과를 자기 DB의 해당 `team_id` 행에
저장한다.

`recruiting_roles`/`required_skills`/`contest_field`는 백엔드가 이미 구조화된 값으로 가지고
있다고 가정해 그대로 받는다. 반면 `activity_goal`/`activity_style`/`activity_intensity`/
`beginner_friendly`/팀 분위기처럼 자유 서술로만 표현되는 값은 백엔드가 보내지 않고, **AI 서버가
`intro_text`에서 GPT-4.1 mini로 직접 추출**한다 — 이미 구조화된 값을 LLM이 다시 추측하게 하면
환각 위험만 커지기 때문이다.

현재 팀 구성(누가 몇 명인지)은 별도 필드가 없다 — `intro_text`에 자연어로 포함시키면 된다
(2026-07-15 변경 — 이전엔 `current_members: [{role, count}]`로 구조화했는데, 이 값은 스코어링
계산에 전혀 쓰이지 않고 임베딩 텍스트의 서술 한 줄로만 녹아들었기 때문에 별도 타입을 유지할
이유가 없었다).

> 추출 프롬프트: [`prompts/team_soft_fields_extraction.txt`](../prompts/team_soft_fields_extraction.txt)

요청:
```json
{
  "intro_text": "커머스 플랫폼을 만드는 4인 팀입니다. 현재 FE 2명, Design 1명으로 구성돼 있습니다. 매주 화, 목요일 저녁 오프라인으로 모이고, 초보자도 편하게 참여할 수 있는 분위기를 지향합니다. 이번 학기 교내 공모전 수상이 목표입니다.",
  "recruiting_roles": ["BE"],
  "required_skills": ["Spring Boot", "PostgreSQL"],
  "contest_field": "커머스"
}
```

응답:
```json
{
  "missing_fields": ["activity_intensity"],
  "embedding_text": "팀 소개: ...\n모집 역할: BE\n요구 스킬: Spring Boot, PostgreSQL\n...",
  "embedding_vector": [0.0123, -0.0456, "... 1536개"],
  "metadata": {
    "recruiting_roles": ["BE"],
    "required_skills": ["Spring Boot", "PostgreSQL"],
    "activity_goal": "교내 공모전 수상",
    "activity_style": "오프라인 모임",
    "beginner_friendly": true
  }
}
```

`missing_fields`는 `intro_text`에서 추출을 시도했지만 명시적으로 드러나지 않아 못 채운 항목이다
(예시에서는 활동 강도가 언급되지 않아 `activity_intensity`가 비었다).

---

## 3. 제안 추천 — `POST /recommendations/user-to-team`

백엔드가 후보 팀들의 임베딩 벡터를 자기 DB에서 꺼내 요청에 실어 보낸다. `query_metadata`는
유저 intent의 룰 스코어링용 원본 값(1번 응답의 `extracted`와 같은 값)이다 — 이게 없으면 임베딩
유사도만 계산할 수 있고 역할 일치도 등 룰 점수를 계산할 수 없다.

요청:
```json
{
  "query_embedding_vector": [0.01, -0.02, "... 1536개"],
  "query_metadata": {
    "desired_roles": ["BE"],
    "skills": ["Spring Boot", "Kafka"],
    "activity_style": "주 3~4회 오프라인",
    "experience_level": "advanced"
  },
  "candidates": [
    {
      "candidate_id": 17,
      "embedding_vector": [0.03, 0.04, "... 1536개"],
      "metadata": {
        "recruiting_roles": ["BE"],
        "required_skills": ["Spring Boot", "Kafka"],
        "activity_style": "주 3~4회 오프라인",
        "beginner_friendly": false
      }
    },
    {
      "candidate_id": 42,
      "embedding_vector": [0.05, -0.01, "... 1536개"],
      "metadata": {
        "recruiting_roles": ["FE"],
        "required_skills": ["React"],
        "activity_style": "온라인",
        "beginner_friendly": true
      }
    }
  ]
}
```

응답:
```json
{
  "recommendations": [
    { "candidate_id": 17, "score": 0.91, "label": "BE 역할을 모집하고 있어요" },
    { "candidate_id": 42, "score": 0.14, "label": "초보자도 편하게 참여할 수 있는 팀이에요" }
  ]
}
```

`label`은 가장 점수가 높은 구성요소를 실제 매칭된 값(역할/스킬/활동 방식 등)으로 채워 넣은
문장이다 — 동점이면 가중치가 높은 구성요소를 우선한다. 모든 구성요소가 0이면(의미 있는 룰
매칭이 하나도 없으면) "의미적으로 관심사가 잘 맞아요"처럼 유사도만 근거로 삼는 문구로
대체된다.

## 4. 역제안 추천 — `POST /recommendations/team-to-user`

요청/응답 스키마는 3번과 완전히 동일한 `RecommendationRequest`/`RecommendationResponse`를
쓴다. `query_embedding_vector`는 **팀의 기존 `embedding_vector`**(2번에서 이미 계산해 백엔드가
저장해둔 값)를 그대로 재사용한다 — 별도로 "deficit 임베딩"을 다시 계산하지 않는다. 팀
embedding_text가 이미 모집 역할/요구 스킬 중심으로 렌더링돼 있어 "이 팀이 뭘 필요로 하는가"를
충분히 대변하기 때문이다. `query_metadata`는 2번 응답의 `metadata`(recruiting_roles/
required_skills/activity_style/beginner_friendly)를, `candidates[].metadata`는 후보 유저들의
1번 응답 `extracted`(desired_roles/skills/experience_level/activity_style)를 넣는다 — 룰
스코어링 구성요소(역할 일치도/결핍 보완도/활동 방식 일치도/초보자 적합도)가 제안(3번)과 완전히
동일하기 때문에 쓰는 필드도 동일하다(`portfolio_role_fit`처럼 방향별로 따로 있던 컴포넌트는
2026-07-15에 제거했다 — 신호가 약한 `experience_level` 대리 지표라 후보군 정보 수준에 따라
결과가 흔들리는 문제가 있었다).

요청:
```json
{
  "query_embedding_vector": [0.03, 0.04, "... 1536개 (팀의 기존 embedding_vector)"],
  "query_metadata": {
    "recruiting_roles": ["BE"],
    "required_skills": ["Spring Boot", "Kafka"],
    "activity_style": "주 3~4회 오프라인",
    "beginner_friendly": false
  },
  "candidates": [
    {
      "candidate_id": 203,
      "embedding_vector": [0.01, -0.02, "... 1536개 (유저의 intent embedding)"],
      "metadata": {
        "desired_roles": ["BE"],
        "skills": ["Spring Boot", "Kafka"],
        "experience_level": "advanced",
        "activity_style": "주 3~4회 오프라인"
      }
    }
  ]
}
```

응답 형태는 3번과 동일 (`candidates[].candidate_id`는 `user_id`).

## 5. 추천 상세 이유 (lazy) — `POST /recommendations/reason`

AI 서버가 아무것도 저장하지 않으므로, 이유 생성에 필요한 컨텍스트(팀 소개/유저 프로필 요약,
매칭 점수 구성요소 등)를 백엔드가 요청에 함께 실어 보내야 한다. **방향(`direction`) 필드는
없다** — `candidate_summary`/`target_summary` 텍스트만으로 LLM이 방향과 무관하게 이유를
생성할 수 있어서 뺐다(USER_TO_TEAM이든 TEAM_TO_USER든 동일 엔드포인트·동일 스키마).

> 생성 프롬프트: [`prompts/recommendation_reason.txt`](../prompts/recommendation_reason.txt)
> ("절대평가 금지, 적합도 관점으로만" 규칙이 여기 있다). 이 규칙을 실제로 지켰는지는
> `scripts/judge_outputs.py`로 점검한다.

요청:
```json
{
  "candidate_summary": "React/TypeScript 경험, 초보자, 포트폴리오용 프로젝트 희망",
  "target_summary": "커머스 플랫폼, BE 1명 결핍, 주 2회 오프라인 활동",
  "score_context": "유사도 높음, 역할 일치, 초보자 적합도 높음"
}
```

`score_context`는 자유 서술 문자열이다(2026-07-15 변경 — 이전엔 `score_breakdown:
{구성요소: 점수}` dict였는데, AI 서버는 이 값을 필드별로 읽지 않고 LLM 프롬프트에 그대로
이어붙이기만 해서 dict 타입을 강제할 이유가 없었다). 백엔드가 원하는 형식의 짧은 서술로 보내면
된다 — 값을 아예 비워 보내도 된다(기본값 `""`).

응답:
```json
{ "reason": "React/TypeScript 경험이 있고, 이 팀이 필요로 하는 BE 결핍을 보완할 수 있는 활동 방식을 갖추고 있습니다." }
```

## 6. 최종 제안 조립 — `POST /proposals/user-to-team`

사용자가 추천 목록에서 팀을 선택한 시점에 호출. `proposal_id`는 이 응답에 없다 — 백엔드가
저장하면서 채번한다. `synergy_score`는 **추천 단계(3번)에서 이미 계산된 값을 백엔드가 그대로
넘겨준다** — AI 서버가 임베딩을 다시 받아 재계산하지 않는다(같은 후보군 스냅샷 기준 점수를
그대로 신뢰).

> 생성 프롬프트: [`prompts/user_to_team_proposal.txt`](../prompts/user_to_team_proposal.txt)

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

> 생성 프롬프트: [`prompts/team_to_user_proposal.txt`](../prompts/team_to_user_proposal.txt)

요청/응답 구조는 6번과 완전히 동일한 `ProposalAssemblyRequest`/`ProposalSchema`,
`direction: "TEAM_TO_USER"`인 점만 다르다. **주의**: `portfolio_role_fit_score`는 응답
스키마에 필드만 남아있고 항상 `null`이다 — 포트폴리오 데이터 없이 `experience_level`을
대리 지표로 쓰던 이전 방식은 후보군 정보 수준에 따라 결과가 흔들리는 문제가 있어 계산에서
뺐다(협업 온도와 같은 취급 — 필드는 예약, 실제 포트폴리오 데이터 소스가 생기면 다시 채운다).
