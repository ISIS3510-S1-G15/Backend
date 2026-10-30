from sqlalchemy import text

from app import models


def _report(client, user, restaurant_id="r1", level=2) -> dict:
    response = client.post(
        "/occupancy/reports", json={"restaurant_id": restaurant_id, "level": level}, headers=user["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seen(client, user, report_id, previous=None, source="detail_poll", restaurant_id="r1", gap=30000):
    body = {
        "restaurant_id": restaurant_id,
        "report_id": report_id,
        "previous_report_id": previous,
        "source": source,
        "ms_since_previous_refresh": gap,
    }
    return client.post("/analytics/occupancy-propagation", json=body, headers=user["headers"])


def _age_report(db, report_id, seconds):
    db.execute(
        text("update occupancy_reports set created_at = created_at - make_interval(secs => :s) where id = :id"),
        {"s": seconds, "id": report_id},
    )
    db.commit()


def test_status_includes_newest_report_id(client, make_user):
    a, b = make_user(), make_user()
    assert client.get("/occupancy/r1").json()["last_report_id"] is None
    first = _report(client, a)["last_report_id"]
    second = _report(client, b, level=0)["last_report_id"]
    assert second > first
    assert client.get("/occupancy/r1").json()["last_report_id"] == second
    assert client.get("/occupancy").json()[0]["last_report_id"] == second


def test_report_time_comes_from_the_database_clock(client, make_user, db):
    user = make_user()
    report_id = _report(client, user)["last_report_id"]
    gap = db.execute(
        text("select abs(extract(epoch from timezone('utc', now()) - created_at)) from occupancy_reports where id = :id"),
        {"id": report_id},
    ).scalar()
    assert gap < 5


def test_other_users_report_is_measured_once(client, make_user, db):
    author, viewer = make_user(), make_user()
    report_id = _report(client, author)["last_report_id"]
    assert _seen(client, viewer, report_id).json() == {"saved": 1}
    assert _seen(client, viewer, report_id).json() == {"saved": 0}
    row = db.query(models.OccupancyPropagationEvent).one()
    assert (row.report_id, row.user_id, row.source, row.ms_since_previous_refresh) == (
        report_id, viewer["id"], "detail_poll", 30000,
    )


def test_own_report_is_not_measured(client, make_user):
    author = make_user()
    report_id = _report(client, author)["last_report_id"]
    assert _seen(client, author, report_id, source="own_report").json() == {"saved": 0}


def test_every_report_between_two_refreshes_is_measured(client, make_user):
    a, b, c, viewer = make_user(), make_user(), make_user(), make_user()
    old = _report(client, a)["last_report_id"]
    middle = _report(client, b)["last_report_id"]
    newest = _report(client, c)["last_report_id"]
    assert _seen(client, viewer, newest, previous=old).json() == {"saved": 2}
    assert _seen(client, viewer, newest, previous=None).json() == {"saved": 1}
    assert middle < newest


def test_expired_reports_are_not_measured(client, make_user, db):
    author, viewer = make_user(), make_user()
    report_id = _report(client, author)["last_report_id"]
    _age_report(db, report_id, 2 * 3600)
    assert _seen(client, viewer, report_id).json() == {"saved": 0}


def test_invalid_ids_are_rejected(client, make_user):
    author, viewer = make_user(), make_user()
    report_id = _report(client, author, restaurant_id="r1")["last_report_id"]
    other = _report(client, author, restaurant_id="r2")["last_report_id"]
    assert _seen(client, viewer, 999999).status_code == 404
    assert _seen(client, viewer, report_id, restaurant_id="r2").status_code == 404
    assert _seen(client, viewer, report_id, previous=other).status_code == 422
    assert _seen(client, viewer, report_id, source="app_open").status_code == 422
    assert _seen(client, viewer, report_id, gap=-1).status_code == 422
    body = {"restaurant_id": "r1", "report_id": report_id, "source": "detail_poll"}
    assert client.post("/analytics/occupancy-propagation", json=body).status_code == 401


def test_summary_overall_and_by_source(client, make_user, db):
    author, first_viewer, second_viewer = make_user(), make_user(), make_user()
    quick = _report(client, author, restaurant_id="r1")["last_report_id"]
    slow = _report(client, author, restaurant_id="r2")["last_report_id"]
    _age_report(db, quick, 20)
    _age_report(db, slow, 120)
    _seen(client, first_viewer, quick, source="detail_poll")
    _seen(client, first_viewer, slow, source="tab_change", restaurant_id="r2")
    _seen(client, second_viewer, slow, source="tab_change", restaurant_id="r2")

    summary = client.get("/analytics/occupancy-propagation").json()
    overall = summary["overall"]
    assert (overall["updates"], overall["reports"]) == (3, 2)
    assert 20 <= overall["median_seconds"] < 125
    assert overall["within_30s_pct"] == 33.3
    assert overall["within_5min_pct"] == 100.0
    by_source = {s["source"]: s for s in summary["by_source"]}
    assert by_source["detail_poll"]["updates"] == 1 and 20 <= by_source["detail_poll"]["avg_seconds"] < 25
    assert by_source["tab_change"]["updates"] == 2 and 120 <= by_source["tab_change"]["p90_seconds"] < 125


def test_empty_summary(client):
    summary = client.get("/analytics/occupancy-propagation").json()
    assert summary["overall"]["updates"] == 0
    assert summary["overall"]["avg_seconds"] is None
    assert summary["by_source"] == []


def test_export_has_no_personal_data(client, make_user):
    author, viewer = make_user(), make_user()
    report_id = _report(client, author)["last_report_id"]
    _seen(client, viewer, report_id)
    response = client.get("/analytics/occupancy-propagation/export")
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert lines[0] == (
        "report_id,restaurant_id,source,reported_at_utc,seen_at_utc,seconds,ms_since_previous_refresh"
    )
    assert len(lines) == 2 and "user" not in lines[0] and "@" not in response.text


def test_delay_is_never_negative(client, make_user, db):
    author, viewer = make_user(), make_user()
    report_id = _report(client, author)["last_report_id"]
    _seen(client, viewer, report_id)
    seconds = db.execute(
        text(
            "select extract(epoch from e.seen_at - r.created_at) from occupancy_propagation_events e "
            "join occupancy_reports r on r.id = e.report_id"
        )
    ).scalar()
    assert 0 <= seconds < 5
