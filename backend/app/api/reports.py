from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from sqlmodel import col, select

from ..db.models import IncidentRow
from ..services.reports import incidents_csv, shift_pdf
from .analytics import summary
from .deps import DB, Svc, User, audit
from .incidents import camera_names

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/shift", response_class=Response, responses={200: {"content": {"application/pdf": {}, "text/csv": {}}}}
)
def shift_report(svc: Svc, s: DB, user: User, since: datetime | None = None, until: datetime | None = None,
                 format: str = "pdf") -> Response:  # fmt: skip
    until = until or datetime.now(UTC)
    since = since or until - timedelta(hours=12)
    rows = list(s.exec(select(IncidentRow).where(IncidentRow.started_at >= since, IncidentRow.started_at < until)
                       .order_by(col(IncidentRow.started_at))).all())  # fmt: skip
    names = camera_names(s)
    stamp = f"{since:%Y%m%d-%H%M}_{until:%Y%m%d-%H%M}"
    audit(s, user, "report.export", format, {"since": since.isoformat(), "until": until.isoformat()})
    s.commit()
    if format == "csv":
        return Response(incidents_csv(rows, names), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=incidents_{stamp}.csv"})  # fmt: skip
    summ = summary(svc, s, user, since, until)
    pdf = shift_pdf(rows, summ, since, until, names)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=shift_{stamp}.pdf"},
    )
