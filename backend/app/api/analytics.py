from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlmodel import select

from ..db.models import CountsMinutely, IncidentRow, ZoneEventRow, ZoneRow
from .deps import DB, Svc, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _range(since: datetime | None, until: datetime | None) -> tuple[datetime, datetime]:
    until = until or datetime.now(UTC)
    since = since or until - timedelta(hours=24)
    return since, until


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@router.get("/summary")
def summary(
    svc: Svc, s: DB, user: User, since: datetime | None = None, until: datetime | None = None
) -> dict:
    since, until = _range(since, until)
    runtimes = list(svc.cameras.runtimes.values()) if svc.cameras else []
    rows = s.exec(
        select(CountsMinutely).where(CountsMinutely.minute >= since, CountsMinutely.minute < until)
    ).all()
    incs = s.exec(
        select(IncidentRow).where(IncidentRow.started_at >= since, IncidentRow.started_at < until)
    ).all()
    compliant = sum(r.compliant_people for r in rows)
    noncompliant = sum(r.noncompliant_people for r in rows)
    by_rule: dict[str, int] = defaultdict(int)
    for i in incs:
        by_rule[i.rule] += 1
    open_now = s.exec(select(IncidentRow).where(IncidentRow.status == "open")).all()
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "cameras_online": sum(rt.status == "running" for rt in runtimes),
        "cameras_total": len(runtimes),
        "people_now": sum((rt.latest_result.counts.current if rt.latest_result else 0) for rt in runtimes),
        "unique_people": sum(r.new_people for r in rows) + sum(_unflushed_new(rt) for rt in runtimes),
        "incidents": len(incs),
        "incidents_by_rule": dict(by_rule),
        "open_incidents": len(open_now),
        "open_high": sum(i.severity == "high" for i in open_now),
        "compliance_rate": round(compliant / (compliant + noncompliant), 4)
        if compliant + noncompliant
        else None,
        "alert_level": svc.cameras.alert_level() if svc.cameras else "green",
    }


def _unflushed_new(rt) -> int:
    m = getattr(rt, "_minute", None)
    return m.new_people if m is not None else 0


@router.get("/timeseries")
def timeseries(s: DB, user: User, since: datetime | None = None, until: datetime | None = None,
               bucket: str = "hour", camera_id: str | None = None) -> dict:  # fmt: skip
    since, until = _range(since, until)
    q = select(CountsMinutely).where(CountsMinutely.minute >= since, CountsMinutely.minute < until)
    if camera_id:
        q = q.where(CountsMinutely.camera_id == camera_id)
    step = timedelta(hours=1) if bucket == "hour" else timedelta(minutes=1)

    def key(dt: datetime) -> datetime:
        dt = _aware(dt)
        return (
            dt.replace(minute=0, second=0, microsecond=0)
            if bucket == "hour"
            else dt.replace(second=0, microsecond=0)
        )

    buckets: dict[datetime, dict] = {}
    t = key(since)
    while t < until:
        buckets[t] = {
            "t": t.isoformat(),
            "new_people": 0,
            "peak_people": 0,
            "incidents": 0,
            "compliant": 0,
            "noncompliant": 0,
            "observed": False,  # any camera ran in this bucket; False = no data, not zero
        }
        t += step
    for r in s.exec(q).all():
        b = buckets.get(key(r.minute))
        if b is not None:
            b["observed"] = True
            b["new_people"] += r.new_people
            b["peak_people"] = max(b["peak_people"], r.peak_current)
            b["compliant"] += r.compliant_people
            b["noncompliant"] += r.noncompliant_people
    iq = select(IncidentRow).where(IncidentRow.started_at >= since, IncidentRow.started_at < until)
    if camera_id:
        iq = iq.where(IncidentRow.camera_id == camera_id)
    for i in s.exec(iq).all():
        b = buckets.get(key(i.started_at))
        if b is not None:
            b["incidents"] += 1
    return {"bucket": bucket, "points": list(buckets.values())}


@router.get("/incidents-by-hour")
def incidents_by_hour(
    s: DB, user: User, since: datetime | None = None, until: datetime | None = None
) -> dict:
    since, until = _range(since or datetime.now(UTC) - timedelta(days=7), until)
    grid: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    for i in s.exec(
        select(IncidentRow).where(IncidentRow.started_at >= since, IncidentRow.started_at < until)
    ).all():
        grid[i.rule.split(":")[0] if not i.rule.startswith("ppe_missing") else i.rule][
            _aware(i.started_at).hour
        ] += 1
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "rows": [{"rule": k, "hours": v} for k, v in sorted(grid.items())],
    }


@router.get("/zones")
def zones(s: DB, user: User, since: datetime | None = None, until: datetime | None = None) -> list[dict]:
    since, until = _range(since, until)
    out = []
    minutes = s.exec(
        select(CountsMinutely).where(CountsMinutely.minute >= since, CountsMinutely.minute < until)
    ).all()
    for z in s.exec(select(ZoneRow)).all():
        entries = s.exec(select(ZoneEventRow).where(ZoneEventRow.zone_id == z.id, ZoneEventRow.kind == "entered",
                                                    ZoneEventRow.at >= since, ZoneEventRow.at < until)).all()  # fmt: skip
        incs = s.exec(select(IncidentRow).where(IncidentRow.zone_id == z.id, IncidentRow.started_at >= since,
                                                IncidentRow.started_at < until)).all()  # fmt: skip
        out.append({
            "zone_id": z.id, "zone_name": z.name, "camera_id": z.camera_id, "kind": z.kind, "severity": z.severity,
            "entries": len(entries), "incidents": len(incs),
            "peak_occupancy": max((m.zone_peaks.get(z.id, 0) for m in minutes), default=0),
        })  # fmt: skip
    return out
