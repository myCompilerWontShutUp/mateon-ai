from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamMember

TEAM_FIXTURES: dict[int, TeamEmbeddingRefreshRequest] = {
    1: TeamEmbeddingRefreshRequest(
        intro_text=(
            "커머스 플랫폼을 만드는 대학생 4인 팀입니다. 매주 화, 목요일 저녁 학교 스터디룸에서 "
            "오프라인으로 모이고, 초보자도 편하게 참여할 수 있는 분위기를 지향합니다. 이번 학기 "
            "교내 공모전 수상이 목표입니다."
        ),
        recruiting_roles=["BE"],
        required_skills=["Spring Boot", "PostgreSQL"],
        current_members=[TeamMember(role="FE", count=2), TeamMember(role="Design", count=1)],
        contest_field="커머스",
    ),
    2: TeamEmbeddingRefreshRequest(
        intro_text=(
            "헬스케어 예약 서비스를 만드는 팀입니다. 실무 경험이 있는 시니어 위주로 빠르게 "
            "MVP를 만들어 외부 공모전에 출품하려 합니다. 주 3회 이상 온라인으로 강도 높게 "
            "모입니다. 초보자보다는 즉시 실무에 투입 가능한 인력을 찾습니다."
        ),
        recruiting_roles=["FE", "PM"],
        required_skills=["React", "TypeScript", "Figma"],
        current_members=[TeamMember(role="BE", count=2)],
        contest_field="헬스케어",
    ),
    3: TeamEmbeddingRefreshRequest(
        intro_text=(
            "교육용 AI 튜터 서비스를 준비하는 3인 팀입니다. 아직 아무도 실무 경험이 없는 "
            "완전 초보자들로 구성되어 있고, 서로 배워가며 천천히 만드는 걸 목표로 합니다. "
            "격주 주말에 오프라인으로 만납니다."
        ),
        recruiting_roles=["BE", "Data"],
        required_skills=["Python", "FastAPI"],
        current_members=[TeamMember(role="FE", count=1), TeamMember(role="PM", count=2)],
        contest_field="에듀테크",
    ),
    4: TeamEmbeddingRefreshRequest(
        intro_text=(
            "중고거래 매칭 플랫폼을 개발하는 팀입니다. 포트폴리오 제작이 주 목적이라 완성도보다 "
            "빠른 결과물에 집중합니다. 주 1회 짧게 온라인으로만 모이는 가벼운 강도의 팀입니다."
        ),
        recruiting_roles=["BE"],
        required_skills=["Node.js", "MongoDB"],
        current_members=[TeamMember(role="FE", count=1)],
    ),
    5: TeamEmbeddingRefreshRequest(
        intro_text=(
            "여행 일정 추천 서비스를 만드는 5인 팀입니다. 전국 대학생 공모전 수상을 목표로 "
            "체계적으로 움직이며, 매주 3회 오프라인 스프린트를 진행합니다. 초보자도 멘토링을 "
            "통해 성장할 수 있도록 돕습니다."
        ),
        recruiting_roles=["Data", "BE"],
        required_skills=["Python", "Django", "AWS"],
        current_members=[
            TeamMember(role="FE", count=2),
            TeamMember(role="Design", count=1),
            TeamMember(role="PM", count=1),
        ],
        contest_field="여행",
    ),
    6: TeamEmbeddingRefreshRequest(
        intro_text=(
            "반려동물 커뮤니티 앱을 만드는 팀입니다. 취미로 가볍게 시작했고 정해진 목표 없이 "
            "각자 페이스대로 기여합니다. 비정기적으로 온라인에서 소통합니다."
        ),
        recruiting_roles=["Design"],
        required_skills=["Figma"],
        current_members=[TeamMember(role="FE", count=1), TeamMember(role="BE", count=1)],
    ),
    7: TeamEmbeddingRefreshRequest(
        intro_text=(
            "핀테크 가계부 서비스를 만드는 팀입니다. 실무 수준의 백엔드 아키텍처 설계 경험이 "
            "있는 사람을 찾고 있으며, 주 4회 오프라인으로 강도 높게 협업합니다. 산업 공모전 "
            "본선 진출이 목표입니다."
        ),
        recruiting_roles=["BE"],
        required_skills=["Spring Boot", "Kafka", "Redis"],
        current_members=[
            TeamMember(role="FE", count=2),
            TeamMember(role="Data", count=1),
            TeamMember(role="PM", count=1),
        ],
        contest_field="핀테크",
    ),
    8: TeamEmbeddingRefreshRequest(
        intro_text=(
            "대학 동아리 관리 서비스를 만드는 2인 팀입니다. 이제 막 코딩을 배우기 시작한 "
            "완전 초보자들이라 서로 알려주며 천천히 진행합니다. 주 1회 온라인으로 짧게 모입니다."
        ),
        recruiting_roles=["FE"],
        required_skills=["HTML", "CSS", "JavaScript"],
        current_members=[TeamMember(role="BE", count=1)],
    ),
    9: TeamEmbeddingRefreshRequest(
        intro_text=(
            "채용 매칭 플랫폼을 만드는 팀입니다. 데이터 기반 추천 로직 설계 경험이 있는 사람을 "
            "찾고, 전국 규모 공모전 수상을 목표로 주 3회 오프라인 스프린트를 진행합니다."
        ),
        recruiting_roles=["Data"],
        required_skills=["Python", "Pandas", "scikit-learn"],
        current_members=[
            TeamMember(role="BE", count=1),
            TeamMember(role="FE", count=1),
            TeamMember(role="Design", count=1),
        ],
        contest_field="HR",
    ),
    10: TeamEmbeddingRefreshRequest(
        intro_text=(
            "환경 캠페인 홍보 웹사이트를 만드는 팀입니다. 비영리 성격이라 부담 없이, 관심 있는 "
            "만큼만 참여하면 됩니다. 초보자를 적극 환영하며 격주 온라인 모임으로 진행합니다."
        ),
        recruiting_roles=["FE", "Design"],
        required_skills=["React", "Figma"],
        current_members=[TeamMember(role="PM", count=1)],
        contest_field="환경",
    ),
}
