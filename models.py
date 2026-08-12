from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Employee(db.Model):
    """소속 직원"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    emp_no = db.Column(db.String(20), unique=True)
    department = db.Column(db.String(50))
    position = db.Column(db.String(50))       # 직급 (예: 선임연구원)
    role_title = db.Column(db.String(50))     # 보직 (예: 팀장, 파트장)
    email = db.Column(db.String(100))
    hire_date = db.Column(db.String(20))
    memo = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    scores = db.relationship(
        "KPIScore", backref="employee", cascade="all, delete-orphan"
    )


class KPIItem(db.Model):
    """평가 항목(가중치를 갖는 KPI 지표)"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    weight = db.Column(db.Float, default=10.0)  # 가중치(%)
    unit = db.Column(db.String(20))             # 단위 (건, %, 점 등)
    direction = db.Column(db.String(10), default="higher")  # higher(높을수록 좋음) / lower(낮을수록 좋음)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    scores = db.relationship(
        "KPIScore", backref="kpi_item", cascade="all, delete-orphan"
    )


class KPIScore(db.Model):
    """특정 기간(분기/반기 등)에 대한 직원별 KPI 실적/점수"""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    kpi_item_id = db.Column(db.Integer, db.ForeignKey("kpi_item.id"), nullable=False)
    period = db.Column(db.String(20), nullable=False)  # 예: 2026-Q3
    target_value = db.Column(db.Float)
    actual_value = db.Column(db.Float)
    score = db.Column(db.Float)  # 0~100 자동 계산
    note = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("employee_id", "kpi_item_id", "period", name="uq_emp_kpi_period"),
    )


def calc_score(target_value, actual_value, direction):
    """target/actual로부터 0~100점 환산 점수를 계산한다."""
    if target_value is None or actual_value is None or target_value == 0:
        return None
    if direction == "lower":
        raw = (target_value / actual_value) * 100 if actual_value else 0
    else:
        raw = (actual_value / target_value) * 100
    return round(min(max(raw, 0), 100), 1)


def employee_overall_score(employee_id, period):
    """해당 직원의 특정 기간 가중 평균 종합 점수를 계산한다."""
    rows = KPIScore.query.filter_by(employee_id=employee_id, period=period).all()
    rows = [r for r in rows if r.score is not None and r.kpi_item and r.kpi_item.weight]
    total_weight = sum(r.kpi_item.weight for r in rows)
    if not total_weight:
        return None
    weighted = sum(r.score * r.kpi_item.weight for r in rows)
    return round(weighted / total_weight, 1)
