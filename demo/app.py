"""mateon-ai 시뮬레이션 UI.

배포된(또는 로컬) mateon-ai 서버를 실제로 호출하면서 전체 흐름(팀 임베딩 → 제안 → 역제안)을
눈으로 확인하기 위한 도구다. `docs/api-contract-draft.md`의 예시 값을 기본값으로 그대로
써서, 문서에 적힌 요청/응답이 실제로 어떻게 동작하는지 바로 볼 수 있게 했다.

AI 서버는 무상태라서 임베딩 벡터를 저장하지 않는다 — 이 화면이 "백엔드" 역할을 대신해서
계산된 벡터를 세션 동안만 잠깐 들고 있는다(새로고침하면 사라진다).

실행:
    uv run streamlit run demo/app.py
"""

import httpx
import streamlit as st

DEFAULT_BASE_URL = "https://web-production-6b62a.up.railway.app"

st.set_page_config(page_title="mateon-ai 시뮬레이션", layout="wide")

# ── 연결 설정 ────────────────────────────────────────────────────────────
st.sidebar.header("연결 설정")
base_url = st.sidebar.text_input("Base URL", value=DEFAULT_BASE_URL).rstrip("/")
secret = st.sidebar.text_input("X-Internal-Secret", type="password")
st.sidebar.caption("Railway Variables 탭에 설정한 값과 동일해야 한다.")


def call(method: str, path: str, payload: dict | None = None) -> httpx.Response:
    with httpx.Client(base_url=base_url, timeout=60) as client:
        return client.request(
            method, path, json=payload, headers={"X-Internal-Secret": secret}
        )


def show_result(resp: httpx.Response) -> dict | None:
    if resp.status_code != 200:
        st.error(f"{resp.status_code}: {resp.text}")
        return None
    data = resp.json()
    preview = {k: v for k, v in data.items() if k != "embedding_vector"}
    if "embedding_vector" in data and data["embedding_vector"] is not None:
        preview["embedding_vector"] = f"(float {len(data['embedding_vector'])}개, 미리보기 생략)"
    st.json(preview)
    return data


for key, default in [
    ("teams", {}),  # {label: {candidate_id, embedding_vector, metadata}}
    ("users", {}),  # {label: {candidate_id, embedding_vector, extracted}}
    ("conversation_answers", {}),
    ("intent_result", None),
]:
    st.session_state.setdefault(key, default)

st.title("mateon-ai 시뮬레이션")
st.caption(
    "docs/api-contract-draft.md의 예시를 기본값으로 채워뒀다 — 버튼만 눌러도 문서와 "
    "동일한 흐름이 실제로 재현된다."
)

tab_team, tab_intent, tab_u2t, tab_t2u, tab_state = st.tabs(
    ["1. 팀 임베딩", "2. 유저 의도 추출", "3. 제안 (USER→TEAM)", "4. 역제안 (TEAM→USER)", "저장된 값"]
)

# ── 1. 팀 임베딩 ─────────────────────────────────────────────────────────
with tab_team:
    st.subheader("POST /internal/teams/embedding:refresh")
    with st.form("team_form"):
        team_label = st.text_input("로컬 라벨", value="team-17")
        team_id = st.number_input("team_id (임의 지정, 백엔드 채번 흉내)", value=17, step=1)
        intro_text = st.text_area(
            "팀 소개글",
            value=(
                "커머스 플랫폼을 만드는 4인 팀입니다. 매주 화, 목요일 저녁 오프라인으로 "
                "모이고, 초보자도 편하게 참여할 수 있는 분위기를 지향합니다. 이번 학기 "
                "교내 공모전 수상이 목표입니다."
            ),
            height=100,
        )
        recruiting_roles = st.text_input("모집 역할 (쉼표 구분, BE/FE/Design/PM/Data)", value="BE")
        required_skills = st.text_input("요구 스킬 (쉼표 구분)", value="Spring Boot, PostgreSQL")
        members_raw = st.text_input("현재 구성 (role:count, 쉼표 구분)", value="FE:2, Design:1")
        contest_field = st.text_input("공모전 분야 (선택)", value="커머스")
        team_submitted = st.form_submit_button("임베딩 계산 요청")

    if team_submitted:
        members = []
        for part in members_raw.split(","):
            part = part.strip()
            if not part:
                continue
            role, _, count = part.partition(":")
            members.append({"role": role.strip(), "count": int(count.strip() or "1")})

        payload = {
            "intro_text": intro_text,
            "recruiting_roles": [r.strip() for r in recruiting_roles.split(",") if r.strip()],
            "required_skills": [s.strip() for s in required_skills.split(",") if s.strip()],
            "current_members": members,
            "contest_field": contest_field or None,
        }
        resp = call("POST", "/internal/teams/embedding:refresh", payload)
        data = show_result(resp)
        if data is not None:
            st.session_state.teams[team_label] = {"candidate_id": int(team_id), **data}
            st.success(f"'{team_label}' (team_id={team_id}) 저장 완료")

# ── 2. 유저 의도 추출 (재질문 stateless 루프) ───────────────────────────
with tab_intent:
    st.subheader("POST /intents/extract — 재질문은 필드명만 알려주고, 질문 문구는 이 화면이 만든다")
    user_label = st.text_input("로컬 라벨", value="user-203", key="user_label")
    user_id = st.number_input("user_id (임의 지정)", value=203, step=1, key="user_id")
    self_intro = st.text_area(
        "자기소개서",
        value=(
            "백엔드 경험은 없지만 프론트엔드를 1년 해봤고, 이번엔 풀스택 프로젝트에서 "
            "성장하고 싶습니다."
        ),
        height=80,
        key="self_intro",
    )

    if st.button("추출 요청 (처음 호출)"):
        st.session_state.conversation_answers = {"activity_goal": "포트폴리오용 프로젝트"}
        resp = call(
            "POST",
            "/intents/extract",
            {
                "self_introduction": self_intro,
                "profile": {"school": "OO대학교", "major": "컴퓨터공학"},
                "conversation_answers": st.session_state.conversation_answers,
            },
        )
        st.session_state.intent_result = show_result(resp) if resp.status_code == 200 else None
        if resp.status_code != 200:
            show_result(resp)

    result = st.session_state.intent_result
    if result:
        if result["missing_fields"]:
            st.warning(
                f"missing_fields = {result['missing_fields']} — AI 서버는 필드명만 알려줄 뿐, "
                "질문 문구는 만들지 않는다. 아래는 그 필드명을 실제 질문으로 바꾼 예시다."
            )
            question_map = {
                "desired_roles": "희망하시는 역할이 무엇인가요? (BE/FE/Design/PM/Data)",
                "experience_level": "지금까지의 개발 경험은 어느 정도이신가요?",
                "activity_style": "선호하는 활동 방식이 있으신가요?",
                "activity_goal": "이번 활동으로 이루고 싶은 목표가 있으신가요?",
            }
            for field in result["missing_fields"]:
                st.text_input(
                    question_map.get(field, f"'{field}'에 대한 답변"),
                    key=f"answer_{field}",
                )

            if st.button("답변 반영해서 다시 추출"):
                for field in result["missing_fields"]:
                    answer = st.session_state.get(f"answer_{field}", "")
                    if answer:
                        st.session_state.conversation_answers[field] = answer
                resp = call(
                    "POST",
                    "/intents/extract",
                    {
                        "self_introduction": self_intro,
                        "profile": {"school": "OO대학교", "major": "컴퓨터공학"},
                        "conversation_answers": st.session_state.conversation_answers,
                    },
                )
                st.session_state.intent_result = (
                    show_result(resp) if resp.status_code == 200 else None
                )
                st.rerun()
        else:
            st.success("완성됨 — embedding_vector까지 채워졌다.")
            if st.button(f"'{user_label}' (user_id={user_id})로 저장"):
                st.session_state.users[user_label] = {
                    "candidate_id": int(user_id),
                    **result,
                }
                st.success(f"'{user_label}' 저장 완료")

# ── 3. 제안: 추천 → 이유 → 최종 조립 ────────────────────────────────────
with tab_u2t:
    st.subheader("제안 흐름 (USER_TO_TEAM)")

    if not st.session_state.users or not st.session_state.teams:
        st.info("먼저 1번 탭에서 팀을, 2번 탭에서 유저를 하나 이상 저장해야 한다.")
    else:
        user_label = st.selectbox("유저 선택", list(st.session_state.users), key="u2t_user")
        team_labels = st.multiselect(
            "후보 팀 선택", list(st.session_state.teams), default=list(st.session_state.teams),
            key="u2t_teams",
        )

        if st.button("추천 요청 — POST /recommendations/user-to-team"):
            user = st.session_state.users[user_label]
            extracted = user["extracted"]
            payload = {
                "query_embedding_vector": user["embedding_vector"],
                "query_metadata": {
                    "desired_roles": extracted["desired_roles"],
                    "skills": extracted["skills"],
                    "activity_style": extracted["activity_style"],
                    "experience_level": extracted["experience_level"],
                },
                "candidates": [
                    {
                        "candidate_id": st.session_state.teams[t]["candidate_id"],
                        "embedding_vector": st.session_state.teams[t]["embedding_vector"],
                        "metadata": st.session_state.teams[t]["metadata"],
                    }
                    for t in team_labels
                ],
            }
            resp = call("POST", "/recommendations/user-to-team", payload)
            data = show_result(resp)
            if data:
                st.session_state.u2t_recommend = data

        recommend = st.session_state.get("u2t_recommend")
        if recommend and recommend["recommendations"]:
            st.divider()
            st.write("**추천 이유 생성** — POST /recommendations/reason")
            candidate_summary = st.text_input(
                "candidate_summary", value="React/TypeScript 경험, 초보자, 포트폴리오용 프로젝트 희망"
            )
            target_summary = st.text_input(
                "target_summary", value="커머스 플랫폼, BE 1명 결핍, 주 2회 오프라인 활동"
            )
            if st.button("이유 생성"):
                resp = call(
                    "POST",
                    "/recommendations/reason",
                    {
                        "candidate_summary": candidate_summary,
                        "target_summary": target_summary,
                        "score_breakdown": {"similarity": 0.8, "role_match": 1.0, "beginner_fit": 0.9},
                    },
                )
                show_result(resp)

            st.divider()
            st.write("**최종 제안 조립** — POST /proposals/user-to-team")
            top = recommend["recommendations"][0]
            col1, col2, col3 = st.columns(3)
            with col1:
                contest_id = st.number_input("contest_id", value=5, step=1)
            with col2:
                intent_id = st.number_input("intent_id", value=88, step=1)
            with col3:
                synergy_score = st.number_input("synergy_score (추천 1위 점수)", value=float(top["score"]))

            if st.button("최종 제안 조립 요청"):
                user = st.session_state.users[user_label]
                payload = {
                    "user_id": user["candidate_id"],
                    "team_id": top["candidate_id"],
                    "contest_id": int(contest_id),
                    "sender_id": user["candidate_id"],
                    "receiver_id": top["candidate_id"],
                    "intent_id": int(intent_id),
                    "synergy_score": synergy_score,
                    "candidate_summary": candidate_summary,
                    "target_summary": target_summary,
                }
                resp = call("POST", "/proposals/user-to-team", payload)
                show_result(resp)

# ── 4. 역제안: 추천 → 이유 → 최종 조립 ──────────────────────────────────
with tab_t2u:
    st.subheader("역제안 흐름 (TEAM_TO_USER)")

    if not st.session_state.users or not st.session_state.teams:
        st.info("먼저 1번 탭에서 팀을, 2번 탭에서 유저를 하나 이상 저장해야 한다.")
    else:
        team_label = st.selectbox("팀 선택", list(st.session_state.teams), key="t2u_team")
        user_labels = st.multiselect(
            "후보 유저 선택", list(st.session_state.users), default=list(st.session_state.users),
            key="t2u_users",
        )

        if st.button("추천 요청 — POST /recommendations/team-to-user"):
            team = st.session_state.teams[team_label]
            payload = {
                "query_embedding_vector": team["embedding_vector"],
                "query_metadata": {
                    "recruiting_roles": team["metadata"].get("recruiting_roles", []),
                    "required_skills": team["metadata"].get("required_skills", []),
                    "activity_goal": team["metadata"].get("activity_goal"),
                },
                "candidates": [
                    {
                        "candidate_id": st.session_state.users[u]["candidate_id"],
                        "embedding_vector": st.session_state.users[u]["embedding_vector"],
                        "metadata": {
                            "desired_roles": st.session_state.users[u]["extracted"]["desired_roles"],
                            "skills": st.session_state.users[u]["extracted"]["skills"],
                            "experience_level": st.session_state.users[u]["extracted"]["experience_level"],
                            "activity_goal": st.session_state.users[u]["extracted"]["activity_goal"],
                        },
                    }
                    for u in user_labels
                ],
            }
            resp = call("POST", "/recommendations/team-to-user", payload)
            data = show_result(resp)
            if data:
                st.session_state.t2u_recommend = data

        recommend = st.session_state.get("t2u_recommend")
        if recommend and recommend["recommendations"]:
            st.divider()
            st.write("**최종 역제안 조립** — POST /proposals/team-to-user")
            top = recommend["recommendations"][0]
            candidate_summary = st.text_input(
                "candidate_summary (스카우트 대상 요약)",
                value="React/TypeScript 경험, 초보자, 포트폴리오용 프로젝트 희망",
                key="t2u_candidate_summary",
            )
            target_summary = st.text_input(
                "target_summary (팀 요약)",
                value="커머스 플랫폼, BE 1명 결핍, 주 2회 오프라인 활동",
                key="t2u_target_summary",
            )
            portfolio_score = st.number_input("portfolio_role_fit_score (추천 응답엔 없어 수동 입력)", value=0.5)

            if st.button("최종 역제안 조립 요청"):
                team = st.session_state.teams[team_label]
                payload = {
                    "user_id": top["candidate_id"],
                    "team_id": team["candidate_id"],
                    "sender_id": team["candidate_id"],
                    "receiver_id": top["candidate_id"],
                    "synergy_score": float(top["score"]),
                    "portfolio_role_fit_score": portfolio_score,
                    "candidate_summary": candidate_summary,
                    "target_summary": target_summary,
                }
                resp = call("POST", "/proposals/team-to-user", payload)
                show_result(resp)

# ── 저장된 값 확인 ───────────────────────────────────────────────────────
with tab_state:
    st.subheader("이 화면이 '백엔드' 대신 잠깐 들고 있는 값들")
    st.write("팀:", {k: v["candidate_id"] for k, v in st.session_state.teams.items()})
    st.write("유저:", {k: v["candidate_id"] for k, v in st.session_state.users.items()})
    st.caption("AI 서버는 이 값을 전혀 저장하지 않는다 — 새로고침하면 전부 사라진다.")
