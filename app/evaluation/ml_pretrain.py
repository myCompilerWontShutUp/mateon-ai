"""ML 사전 구축 실험(2026-08-21)의 학습 로직을 공유 모듈로 뺐다 — 세 스크립트
(train_cluster_weight_ml_pretrain.py, _gpt56terra.py, eval_ml_pretrain_weights.py)가 같은
학습 코드를 중복해서 들고 있던 걸 정리.

**2026-08-21 개선**: 사용자가 지적한 두 가지 methodological gap을 고쳤다.
1. **클래스 불균형 미처리** — 양성(선택됨) 비율이 ~2%로 심하게 불균형했는데
   `class_weight='balanced'` 없이 학습했다. 이제 명시적으로 적용한다.
2. **학습/검증 분리·정규화 강도 튜닝 없음** — 전체 데이터로 한 번만 fit했다. 이제
   `LogisticRegressionCV`로 정규화 강도(C)를 교차검증으로 튜닝한다. 단, 같은 선택 세션(event)의
   후보들이 train/validation 폴드에 걸쳐 섞이면 정보 누수가 생기므로(같은 세션 내 후보들은
   서로 강하게 상관됨), 일반 KFold가 아니라 **GroupKFold**(이벤트 단위로 통째로 나눔)를 쓴다.
"""

import numpy as np
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import GroupKFold

COMPONENTS = ["similarity", "role_match", "deficit_fit", "beginner_fit", "activity_style_match"]


def events_to_training_rows(events: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """이벤트 목록을 (피처, 라벨, 그룹) 배열로 펼친다. 그룹 = 이벤트 인덱스 — 같은 이벤트의
    후보들이 GroupKFold에서 항상 같은 폴드에 묶이게 하기 위함(정보 누수 방지)."""
    X, y, groups = [], [], []
    for event_idx, event in enumerate(events):
        selected_id = event["selected_candidate_id"]
        for candidate in event["shown_candidates"]:
            row = [candidate["component_scores"].get(c, 0.0) or 0.0 for c in COMPONENTS]
            X.append(row)
            y.append(1 if candidate["candidate_id"] == selected_id else 0)
            groups.append(event_idx)
    return np.array(X), np.array(y), np.array(groups)


def learn_ml_weights(events: list[dict], n_splits: int = 5) -> dict:
    """로지스틱 회귀(class_weight=balanced, GroupKFold 교차검증으로 정규화 강도 C 튜닝)를 학습해
    가중치(양수 클립 후 정규화, 합=1.0)와 진단 정보를 함께 반환한다."""
    X, y, groups = events_to_training_rows(events)

    n_groups = len(set(groups.tolist()))
    n_splits = max(2, min(n_splits, n_groups))  # 이벤트 수가 적으면 폴드 수 자동 축소
    cv_splits = list(GroupKFold(n_splits=n_splits).split(X, y, groups))

    model = LogisticRegressionCV(
        Cs=10,
        cv=cv_splits,
        class_weight="balanced",
        max_iter=5000,
        scoring="average_precision",  # 불균형 이진 분류에서 accuracy보다 의미 있는 지표
    )
    model.fit(X, y)

    raw_coef = model.coef_[0]
    clipped = np.clip(raw_coef, 0, None)
    weights = clipped / clipped.sum() if clipped.sum() > 0 else np.ones(len(COMPONENTS)) / len(COMPONENTS)

    return {
        "weights": dict(zip(COMPONENTS, weights.tolist())),
        "raw_coef": dict(zip(COMPONENTS, raw_coef.tolist())),
        "best_C": float(model.C_[0]),
        "n_splits": n_splits,
        "n_rows": int(X.shape[0]),
        "positive_rate": float(y.mean()),
    }
