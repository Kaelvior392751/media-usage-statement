from datetime import date
from uuid import UUID

from media_statement.usage_statement_service import MediaActivity, StatementRequest, statement_markdown


def test_statement_preserves_media_counts_and_metering_record() -> None:
    request = StatementRequest(
        statement_id=UUID("b16714b5-cdc4-4b62-aee8-3fe49a67000c"),
        creator_name="North Pier Sessions",
        recipient="ops@example.com",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        activity=MediaActivity(asset_ingestions=42, processing_jobs=118, creator_deliveries=17),
    )

    markdown = statement_markdown(request, {"units": 177, "period": "2026-08"})

    assert "Assets ingested: 42" in markdown
    assert "Processing jobs: 118" in markdown
    assert "Creator deliveries: 17" in markdown
    assert '"units": 177' in markdown
    assert "2026-08-01 through 2026-08-31" in markdown
