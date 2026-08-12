import csv
import io
import os
from datetime import datetime

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    Response,
    url_for,
)

from models import KPIItem, KPIScore, Employee, calc_score, db, employee_overall_score

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "krri-kpi-dashboard-dev-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "kpi.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def grade_of(score):
    if score is None:
        return "-"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "D"


app.jinja_env.filters["grade"] = grade_of


def all_periods():
    rows = db.session.query(KPIScore.period).distinct().order_by(KPIScore.period.desc()).all()
    return [r[0] for r in rows]


def latest_period():
    periods = all_periods()
    return periods[0] if periods else None


# ---------------------------------------------------------------- 대시보드
@app.route("/")
def dashboard():
    period = request.args.get("period") or latest_period()
    periods = all_periods()
    employees = Employee.query.order_by(Employee.department, Employee.name).all()

    rows = []
    for emp in employees:
        overall = employee_overall_score(emp.id, period) if period else None
        rows.append({"employee": emp, "score": overall, "grade": grade_of(overall)})

    scored_rows = [r for r in rows if r["score"] is not None]
    scored_rows.sort(key=lambda r: r["score"], reverse=True)
    unscored_rows = [r for r in rows if r["score"] is None]

    avg_score = (
        round(sum(r["score"] for r in scored_rows) / len(scored_rows), 1)
        if scored_rows
        else None
    )
    top_row = scored_rows[0] if scored_rows else None
    bottom_row = scored_rows[-1] if scored_rows else None

    dept_map = {}
    for r in scored_rows:
        d = r["employee"].department or "미지정"
        dept_map.setdefault(d, []).append(r["score"])
    dept_avg = {
        d: round(sum(v) / len(v), 1) for d, v in dept_map.items()
    }

    kpi_items = KPIItem.query.filter_by(active=True).all()
    item_avg = {}
    for item in kpi_items:
        vals = [
            s.score
            for s in item.scores
            if s.period == period and s.score is not None
        ]
        if vals:
            item_avg[item.name] = round(sum(vals) / len(vals), 1)

    return render_template(
        "dashboard.html",
        period=period,
        periods=periods,
        rows=scored_rows,
        unscored_rows=unscored_rows,
        avg_score=avg_score,
        top_row=top_row,
        bottom_row=bottom_row,
        dept_avg=dept_avg,
        item_avg=item_avg,
        total_employees=len(employees),
    )


# ---------------------------------------------------------------- 직원 관리
@app.route("/employees")
def employee_list():
    q = request.args.get("q", "").strip()
    query = Employee.query
    if q:
        query = query.filter(
            (Employee.name.contains(q))
            | (Employee.department.contains(q))
            | (Employee.emp_no.contains(q))
        )
    employees = query.order_by(Employee.department, Employee.name).all()
    return render_template("employee_list.html", employees=employees, q=q)


@app.route("/employees/new", methods=["GET", "POST"])
def employee_new():
    if request.method == "POST":
        emp = Employee(
            name=request.form["name"].strip(),
            emp_no=request.form.get("emp_no", "").strip() or None,
            department=request.form.get("department", "").strip(),
            position=request.form.get("position", "").strip(),
            role_title=request.form.get("role_title", "").strip(),
            email=request.form.get("email", "").strip(),
            hire_date=request.form.get("hire_date", "").strip(),
            memo=request.form.get("memo", "").strip(),
        )
        db.session.add(emp)
        db.session.commit()
        flash(f"'{emp.name}' 직원이 등록되었습니다.", "success")
        return redirect(url_for("employee_list"))
    return render_template("employee_form.html", employee=None)


@app.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
def employee_edit(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    if request.method == "POST":
        emp.name = request.form["name"].strip()
        emp.emp_no = request.form.get("emp_no", "").strip() or None
        emp.department = request.form.get("department", "").strip()
        emp.position = request.form.get("position", "").strip()
        emp.role_title = request.form.get("role_title", "").strip()
        emp.email = request.form.get("email", "").strip()
        emp.hire_date = request.form.get("hire_date", "").strip()
        emp.memo = request.form.get("memo", "").strip()
        db.session.commit()
        flash(f"'{emp.name}' 직원 정보가 수정되었습니다.", "success")
        return redirect(url_for("employee_list"))
    return render_template("employee_form.html", employee=emp)


@app.route("/employees/<int:emp_id>/delete", methods=["POST"])
def employee_delete(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    db.session.delete(emp)
    db.session.commit()
    flash(f"'{emp.name}' 직원이 삭제되었습니다.", "info")
    return redirect(url_for("employee_list"))


@app.route("/employees/<int:emp_id>")
def employee_detail(emp_id):
    emp = Employee.query.get_or_404(emp_id)
    periods = all_periods()
    period = request.args.get("period") or (periods[0] if periods else None)

    item_scores = (
        KPIScore.query.filter_by(employee_id=emp.id, period=period).all()
        if period
        else []
    )
    overall = employee_overall_score(emp.id, period) if period else None

    history = []
    for p in periods:
        s = employee_overall_score(emp.id, p)
        if s is not None:
            history.append({"period": p, "score": s})
    history.sort(key=lambda h: h["period"])

    return render_template(
        "employee_detail.html",
        employee=emp,
        period=period,
        periods=periods,
        item_scores=item_scores,
        overall=overall,
        grade=grade_of(overall),
        history=history,
    )


# ---------------------------------------------------------------- KPI 항목 관리
@app.route("/kpis")
def kpi_list():
    items = KPIItem.query.order_by(KPIItem.active.desc(), KPIItem.name).all()
    total_weight = sum(i.weight or 0 for i in items if i.active)
    return render_template("kpi_list.html", items=items, total_weight=total_weight)


@app.route("/kpis/new", methods=["GET", "POST"])
def kpi_new():
    if request.method == "POST":
        item = KPIItem(
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip(),
            weight=float(request.form.get("weight") or 0),
            unit=request.form.get("unit", "").strip(),
            direction=request.form.get("direction", "higher"),
            active=True,
        )
        db.session.add(item)
        db.session.commit()
        flash(f"'{item.name}' KPI 항목이 등록되었습니다.", "success")
        return redirect(url_for("kpi_list"))
    return render_template("kpi_form.html", item=None)


@app.route("/kpis/<int:item_id>/edit", methods=["GET", "POST"])
def kpi_edit(item_id):
    item = KPIItem.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form["name"].strip()
        item.description = request.form.get("description", "").strip()
        item.weight = float(request.form.get("weight") or 0)
        item.unit = request.form.get("unit", "").strip()
        item.direction = request.form.get("direction", "higher")
        item.active = bool(request.form.get("active"))
        db.session.commit()

        # 가중치/방향이 바뀌었으므로 관련 점수 재계산
        for s in item.scores:
            s.score = calc_score(s.target_value, s.actual_value, item.direction)
        db.session.commit()

        flash(f"'{item.name}' KPI 항목이 수정되었습니다.", "success")
        return redirect(url_for("kpi_list"))
    return render_template("kpi_form.html", item=item)


@app.route("/kpis/<int:item_id>/delete", methods=["POST"])
def kpi_delete(item_id):
    item = KPIItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash(f"'{item.name}' KPI 항목이 삭제되었습니다.", "info")
    return redirect(url_for("kpi_list"))


# ---------------------------------------------------------------- 평가 입력
@app.route("/scores", methods=["GET", "POST"])
def score_entry():
    employees = Employee.query.order_by(Employee.department, Employee.name).all()
    items = KPIItem.query.filter_by(active=True).order_by(KPIItem.name).all()
    periods = all_periods()

    if not employees:
        flash("먼저 직원을 등록해주세요.", "warning")
        return redirect(url_for("employee_new"))
    if not items:
        flash("먼저 KPI 항목을 등록해주세요.", "warning")
        return redirect(url_for("kpi_new"))

    if request.method == "POST":
        emp_id = int(request.form["employee_id"])
        period = request.form["period"].strip()
        for item in items:
            target_raw = request.form.get(f"target_{item.id}", "").strip()
            actual_raw = request.form.get(f"actual_{item.id}", "").strip()
            note = request.form.get(f"note_{item.id}", "").strip()

            target_value = float(target_raw) if target_raw else None
            actual_value = float(actual_raw) if actual_raw else None

            record = KPIScore.query.filter_by(
                employee_id=emp_id, kpi_item_id=item.id, period=period
            ).first()
            if not record:
                if target_value is None and actual_value is None:
                    continue
                record = KPIScore(employee_id=emp_id, kpi_item_id=item.id, period=period)
                db.session.add(record)

            record.target_value = target_value
            record.actual_value = actual_value
            record.note = note
            record.score = calc_score(target_value, actual_value, item.direction)
            record.updated_at = datetime.utcnow()

        db.session.commit()
        flash("평가 결과가 저장되었습니다.", "success")
        return redirect(url_for("employee_detail", emp_id=emp_id, period=period))

    sel_emp_id = request.args.get("employee_id", type=int) or employees[0].id
    sel_period = request.args.get("period") or (periods[0] if periods else "")

    existing = {}
    if sel_period:
        for s in KPIScore.query.filter_by(employee_id=sel_emp_id, period=sel_period):
            existing[s.kpi_item_id] = s

    return render_template(
        "score_entry.html",
        employees=employees,
        items=items,
        periods=periods,
        sel_emp_id=sel_emp_id,
        sel_period=sel_period,
        existing=existing,
    )


# ---------------------------------------------------------------- 내보내기(CSV)
@app.route("/export.csv")
def export_csv():
    period = request.args.get("period") or latest_period()
    employees = Employee.query.order_by(Employee.department, Employee.name).all()

    buf = io.StringIO()
    buf.write("﻿")  # 엑셀 한글 깨짐 방지 BOM
    writer = csv.writer(buf)
    writer.writerow(["기간", "부서", "이름", "사번", "직급", "보직", "종합점수", "등급"])
    for emp in employees:
        score = employee_overall_score(emp.id, period) if period else None
        writer.writerow(
            [
                period or "",
                emp.department or "",
                emp.name,
                emp.emp_no or "",
                emp.position or "",
                emp.role_title or "",
                score if score is not None else "",
                grade_of(score),
            ]
        )

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=kpi_{period or 'all'}.csv"
        },
    )


def seed_sample_data():
    """최초 실행 시 화면 확인용 예시 데이터를 채워준다."""
    if Employee.query.first():
        return

    employees = [
        Employee(name="홍길동", emp_no="R001", department="철도안전연구팀", position="책임연구원", role_title="팀장"),
        Employee(name="김영희", emp_no="R002", department="철도안전연구팀", position="선임연구원"),
        Employee(name="이철수", emp_no="R003", department="철도안전연구팀", position="연구원"),
        Employee(name="박민수", emp_no="R004", department="스마트인프라연구팀", position="선임연구원", role_title="파트장"),
        Employee(name="정수진", emp_no="R005", department="스마트인프라연구팀", position="연구원"),
    ]
    db.session.add_all(employees)

    items = [
        KPIItem(name="연구과제 수행실적", description="정부/수탁 과제 수행 실적 점수", weight=30, unit="점", direction="higher"),
        KPIItem(name="논문/특허 실적", description="SCI 논문, 특허 출원·등록 건수", weight=20, unit="건", direction="higher"),
        KPIItem(name="예산 집행률", description="배정 예산 대비 집행 비율", weight=15, unit="%", direction="higher"),
        KPIItem(name="대내외 기술지원", description="기술자문, 기술이전 등 지원 실적", weight=15, unit="건", direction="higher"),
        KPIItem(name="안전/품질 사고", description="안전사고 및 품질 결함 발생 건수(적을수록 우수)", weight=20, unit="건", direction="lower"),
    ]
    db.session.add_all(items)
    db.session.commit()

    import random

    random.seed(42)
    for period in ["2026-Q1", "2026-Q2"]:
        for emp in employees:
            for item in items:
                if item.direction == "lower":
                    target = 2
                    actual = random.choice([0, 0, 1, 2, 3])
                else:
                    target = 100
                    actual = round(random.uniform(70, 115), 1)
                score = calc_score(target, actual, item.direction)
                db.session.add(
                    KPIScore(
                        employee_id=emp.id,
                        kpi_item_id=item.id,
                        period=period,
                        target_value=target,
                        actual_value=actual,
                        score=score,
                    )
                )
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_sample_data()


if __name__ == "__main__":
    app.run(debug=True)
