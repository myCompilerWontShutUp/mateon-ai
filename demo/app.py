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
    # [{id, role, message}, ...] — /intents/extract에 누적해서 통째로 다시 보낸다.
    # AI의 질문(role=assistant)도 반드시 같이 재전송해야 한다 — 사용자의 짧은 답변("없어" 등)을
    # 추출 LLM이 해석하려면 직전 질문이 필요하기 때문이다. 화면 표시도 이 리스트를 그대로 쓴다.
    ("messages", []),
    ("intent_result", None),
    ("chat_started", False),
    ("chat_user_label", "user-203"),
    ("chat_user_id", 203),
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
            "팀 소개글 (현재 팀 구성도 문장으로 포함시키면 된다 — 별도 필드 없음)",
            value=(
                "커머스 플랫폼을 만드는 4인 팀입니다. 현재 FE 2명, Design 1명으로 구성돼 "
                "있습니다. 매주 화, 목요일 저녁 오프라인으로 모이고, 초보자도 편하게 참여할 수 "
                "있는 분위기를 지향합니다. 이번 학기 교내 공모전 수상이 목표입니다."
            ),
            height=100,
        )
        recruiting_roles = st.text_input("모집 역할 (쉼표 구분, BE/FE/Design/PM/Data)", value="BE")
        required_skills = st.text_input("요구 스킬 (쉼표 구분)", value="Spring Boot, PostgreSQL")
        contest_field = st.text_input("공모전 분야 (선택)", value="커머스")
        team_submitted = st.form_submit_button("임베딩 계산 요청")

    if team_submitted:
        payload = {
            "intro_text": intro_text,
            "recruiting_roles": [r.strip() for r in recruiting_roles.split(",") if r.strip()],
            "required_skills": [s.strip() for s in required_skills.split(",") if s.strip()],
            "contest_field": contest_field or None,
        }
        resp = call("POST", "/internal/teams/embedding:refresh", payload)
        data = show_result(resp)
        if data is not None:
            st.session_state.teams[team_label] = {"candidate_id": int(team_id), **data}
            st.success(f"'{team_label}' (team_id={team_id}) 저장 완료")

# ── 2. 유저 의도 추출 챗봇 시뮬레이터 (프롬프트 엔지니어링 파트 전용) ──
# AI_PERSONA_NAME/OPENING_GREETING은 app/features/user_to_team/chat_reply.py와 내용을
# 맞춰야 한다 — 이 인사말은 API 호출 없이 클라이언트가 먼저 보여주는 고정 문구다(아직 추출할
# 사용자 발화가 없다). missing_fields가 있든 없든(바로 추천 가능하든 아니든) 항상 이 인사말이
# 먼저 나오고, 그다음 사용자의 첫 답변부터 실제 재질문 흐름(rule 1~4)이 시작된다.
AI_PERSONA_NAME = "드림이"
OPENING_GREETING = (
    f"안녕! 나는 {AI_PERSONA_NAME}야, 너한테 딱 맞는 팀을 찾아주는 도우미야. "
    "먼저 너에 대해 간단히 소개해줄래? 어떤 역할을 하고 싶은지, 관심 분야나 경험이 있다면 "
    "편하게 말해줘!"
)

with tab_intent:
    st.subheader("채팅 시뮬레이터 — POST /intents/extract")
    st.caption(
        f"{AI_PERSONA_NAME}가 먼저 인사하고 자기소개를 부탁한 뒤, 그 답변부터 재진술 + 유도 "
        "질문(1개씩) / 추천 시작 안내 / 맥락 이탈 방어 문구까지 전부 `assistant_message`로 "
        "AI가 생성한다(`prompts/user_intent_chat_reply.txt`)."
    )

    if not st.session_state.chat_started:
        # ── 입력 폼: 사용자 정보 + (선택) 미리 등록된 자기소개서/포트폴리오 ──
        user_label = st.text_input("로컬 라벨", value="user-203", key="user_label")
        user_id = st.number_input("user_id (임의 지정)", value=203, step=1, key="user_id")
        self_intro = st.text_area(
            "자기소개서 (선택 — 채팅 시작 전 미리 등록된 값이라고 가정, 채팅 첫 답변보다 먼저 반영)",
            value="",
            height=80,
            key="profile_self_intro",
        )
        portfolio = st.text_area(
            "포트폴리오 (선택 — 초보자는 없어도 된다)",
            value="",
            height=80,
            key="profile_portfolio",
        )
        st.caption(
            "채팅 첫 답변 예시: \"백엔드 경험은 없지만 프론트엔드를 1년 해봤고, 이번엔 풀스택 "
            "프로젝트에서 성장하고 싶습니다.\" — 자기소개서/포트폴리오와 채팅 답변 내용이 서로 "
            "다르면 채팅에 쓴 내용이 우선 반영된다(`prompts/user_intent_extraction.txt`)."
        )

        if st.button("채팅 시작", type="primary"):
            st.session_state.chat_user_label = user_label
            st.session_state.chat_user_id = int(user_id)

            profile_messages = []
            if self_intro.strip():
                profile_messages.append({"role": "user", "message": f"[자기소개서]\n{self_intro.strip()}"})
            if portfolio.strip():
                profile_messages.append({"role": "user", "message": f"[포트폴리오]\n{portfolio.strip()}"})

            st.session_state.messages = [
                {"id": i + 1, **m} for i, m in enumerate(profile_messages)
            ] + [
                {"id": len(profile_messages) + 1, "role": "assistant", "message": OPENING_GREETING}
            ]
            st.session_state.intent_result = None
            st.session_state.chat_started = True
            st.rerun()
    else:
        # ── 채팅 화면: messages를 그대로 렌더링하고(표시=전송 상태가 항상 일치), 하단
        # 입력창으로 계속 이어간다. AI turn도 messages에 쌓여서 다음 호출 때 같이 재전송된다.
        for turn in st.session_state.messages:
            st.chat_message(turn["role"]).write(turn["message"])

        result = st.session_state.intent_result
        if result:
            with st.expander("가장 최근 응답 원본 JSON"):
                preview = {k: v for k, v in result.items() if k != "embedding_vector"}
                if result.get("embedding_vector") is not None:
                    preview["embedding_vector"] = f"(float {len(result['embedding_vector'])}개, 생략)"
                st.json(preview)

        still_needs_reply = result is None or result["missing_fields"]
        if still_needs_reply:
            reply = st.chat_input("답장하기")
            if reply:
                next_id = len(st.session_state.messages) + 1
                st.session_state.messages.append({"id": next_id, "role": "user", "message": reply})

                resp = call("POST", "/intents/extract", {"messages": st.session_state.messages})
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.intent_result = data
                    next_id = len(st.session_state.messages) + 1
                    st.session_state.messages.append(
                        {"id": next_id, "role": "assistant", "message": data["assistant_message"]}
                    )
                else:
                    show_result(resp)
                st.rerun()
        else:
            st.success("필수 정보가 모두 채워졌다 — embedding_vector까지 포함된 상태.")
            label = st.session_state.chat_user_label
            uid = st.session_state.chat_user_id
            if st.button(f"'{label}' (user_id={uid})로 저장"):
                st.session_state.users[label] = {"candidate_id": uid, **result}
                st.success(f"'{label}' 저장 완료")

        if st.button("새 대화 시작"):
            st.session_state.chat_started = False
            st.session_state.messages = []
            st.session_state.intent_result = None
            st.rerun()

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
                        "score_context": "유사도 높음, 역할 일치, 초보자 적합도 높음",
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
                    "activity_style": team["metadata"].get("activity_style"),
                    "beginner_friendly": team["metadata"].get("beginner_friendly"),
                },
                "candidates": [
                    {
                        "candidate_id": st.session_state.users[u]["candidate_id"],
                        "embedding_vector": st.session_state.users[u]["embedding_vector"],
                        "metadata": {
                            "desired_roles": st.session_state.users[u]["extracted"]["desired_roles"],
                            "skills": st.session_state.users[u]["extracted"]["skills"],
                            "experience_level": st.session_state.users[u]["extracted"]["experience_level"],
                            "activity_style": st.session_state.users[u]["extracted"]["activity_style"],
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

            if st.button("최종 역제안 조립 요청"):
                team = st.session_state.teams[team_label]
                payload = {
                    "user_id": top["candidate_id"],
                    "team_id": team["candidate_id"],
                    "sender_id": team["candidate_id"],
                    "receiver_id": top["candidate_id"],
                    "synergy_score": float(top["score"]),
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
