from app.schemas.user_intent import ConversationMessage, UserIntentExtractionRequest

USER_INTENT_FIXTURES: dict[str, UserIntentExtractionRequest] = {
    "backend_expert": UserIntentExtractionRequest(
        messages=[
            ConversationMessage(
                id=1,
                message=(
                    "저는 실무에서 3년간 백엔드 개발을 해온 경력자입니다. Spring Boot와 Kafka를 "
                    "이용한 대규모 트래픽 처리 경험이 있고, 핀테크 도메인에 관심이 많습니다. "
                    "이번엔 백엔드(BE) 역할로 참여하고 싶고, 주 3~4회 오프라인으로 강도 높게 "
                    "협업하는 팀을 선호합니다. 제 경험 수준은 advanced(실무 경험자)입니다."
                ),
            ),
        ],
    ),
    "frontend_beginner": UserIntentExtractionRequest(
        messages=[
            ConversationMessage(
                id=1,
                message=(
                    "저는 이제 막 코딩을 배우기 시작한 완전 초보자입니다. HTML/CSS/JavaScript를 "
                    "독학으로 공부하고 있고, 프론트엔드(FE) 역할로 참여해보고 싶습니다. 아직 "
                    "실력이 부족해서 부담 없이 가볍게, 주 1회 정도만 참여할 수 있는 팀을 찾고 "
                    "있습니다. 제 경험 수준은 beginner(완전 초보자)입니다."
                ),
            ),
        ],
    ),
}
