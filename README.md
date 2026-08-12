# KRRI 직원관리용 KPI 대시보드

KRRI 보직자가 팀원들의 KPI를 등록하고 관리할 수 있는 Flask 기반 웹 대시보드입니다.

## 주요 기능

- **대시보드**: 팀 평균 점수, 최고/최저 점수자, 직원별 순위, 부서별 평균, KPI 항목별 팀 평균을 한눈에 확인
- **직원 관리**: 이름/사번/부서/직급/보직 등록·수정·삭제, 검색
- **KPI 항목 관리**: 항목명, 가중치(%), 단위, 평가 방향(높을수록/낮을수록 좋음) 관리
- **평가 입력**: 직원·기간별 목표/실적 입력 시 0~100점으로 자동 환산, 등급(A/B/C/D) 산출
- **직원 상세**: 항목별 레이더 차트, 기간별 점수 추이 라인 차트
- **CSV 내보내기**: 기간별 평가 결과를 CSV로 다운로드

## 실행 방법

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속하면 됩니다. 최초 실행 시 SQLite DB(`kpi.db`)가 자동 생성되고 예시 데이터가 채워집니다.

## 기술 스택

- Flask 3 / Flask-SQLAlchemy
- SQLite
- Bootstrap 5, Chart.js (CDN)
