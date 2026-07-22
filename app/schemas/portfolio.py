from pydantic import BaseModel


class PortfolioSummaryResult(BaseModel):
    # PDF 바이트의 SHA-256 해시 — AI 서버는 상태가 없어 채번할 ID가 없으므로, 같은 파일이면
    # 항상 같은 값이 나오는 결정론적 식별자로 대신한다. 백엔드가 중복 판정에 쓸 수 있다.
    pdf_id: str
    # 경력사항 불릿 목록 + 요약 문단을 하나의 마크다운 문자열로 반환한다.
    response: str
