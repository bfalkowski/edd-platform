from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import polars as pl

from edd_platform_api.schemas import (
    AnalysisSnapshotMetadata,
    FailureMode,
    ReviewCorpusAnalysis,
    ReviewCoverageSummary,
    ReviewFailureModeCount,
    ReviewFailureRate,
    ReviewItem,
    ReviewAnnotation,
)


SNAPSHOT_METADATA_FILE = "metadata.json"
SNAPSHOT_ITEMS_FILE = "review_items.parquet"
SNAPSHOT_ANNOTATIONS_FILE = "annotations.parquet"
SNAPSHOT_FAILURE_MODES_FILE = "failure_modes.parquet"


def review_corpus_analysis(
    *,
    project_id: str,
    corpus_id: str,
    agent_design_id: str,
    items: List[ReviewItem],
    annotations: List[ReviewAnnotation],
    failure_modes: List[FailureMode],
    pending_suggestions: int,
    snapshot: Optional[AnalysisSnapshotMetadata] = None,
) -> ReviewCorpusAnalysis:
    return review_corpus_analysis_from_frames(
        project_id=project_id,
        corpus_id=corpus_id,
        agent_design_id=agent_design_id,
        items_df=review_items_frame(items),
        annotations_df=review_annotations_frame(annotations),
        failure_modes_df=failure_modes_frame(failure_modes),
        pending_suggestions=pending_suggestions,
        snapshot=snapshot,
    )


def review_corpus_analysis_from_snapshot(
    *,
    project_id: str,
    corpus_id: str,
    agent_design_id: str,
    pending_suggestions: int,
    snapshot_dir: Path,
) -> Optional[ReviewCorpusAnalysis]:
    items_path = snapshot_dir / SNAPSHOT_ITEMS_FILE
    annotations_path = snapshot_dir / SNAPSHOT_ANNOTATIONS_FILE
    failure_modes_path = snapshot_dir / SNAPSHOT_FAILURE_MODES_FILE
    if not items_path.exists() or not annotations_path.exists() or not failure_modes_path.exists():
        return None
    items_df = pl.read_parquet(items_path)
    annotations_df = pl.read_parquet(annotations_path)
    failure_modes_df = pl.read_parquet(failure_modes_path)
    snapshot = load_snapshot_metadata(
        snapshot_dir=snapshot_dir,
        status="loaded",
        item_count=items_df.height,
        annotation_count=annotations_df.height,
        failure_mode_count=failure_modes_df.height,
    )
    return review_corpus_analysis_from_frames(
        project_id=project_id,
        corpus_id=corpus_id,
        agent_design_id=agent_design_id,
        items_df=items_df,
        annotations_df=annotations_df,
        failure_modes_df=failure_modes_df,
        pending_suggestions=pending_suggestions,
        snapshot=snapshot,
    )


def materialize_review_corpus_snapshot(
    *,
    snapshot_dir: Path,
    items: List[ReviewItem],
    annotations: List[ReviewAnnotation],
    failure_modes: List[FailureMode],
) -> AnalysisSnapshotMetadata:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    items_df = review_items_frame(items)
    annotations_df = review_annotations_frame(annotations)
    failure_modes_df = failure_modes_frame(failure_modes)
    items_df.write_parquet(snapshot_dir / SNAPSHOT_ITEMS_FILE)
    annotations_df.write_parquet(snapshot_dir / SNAPSHOT_ANNOTATIONS_FILE)
    failure_modes_df.write_parquet(snapshot_dir / SNAPSHOT_FAILURE_MODES_FILE)
    snapshot = AnalysisSnapshotMetadata(
        status="materialized",
        directory=str(snapshot_dir),
        generated_at=datetime.now(timezone.utc),
        item_count=items_df.height,
        annotation_count=annotations_df.height,
        failure_mode_count=failure_modes_df.height,
    )
    (snapshot_dir / SNAPSHOT_METADATA_FILE).write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return snapshot


def review_corpus_analysis_from_frames(
    *,
    project_id: str,
    corpus_id: str,
    agent_design_id: str,
    items_df: pl.DataFrame,
    annotations_df: pl.DataFrame,
    failure_modes_df: pl.DataFrame,
    pending_suggestions: int,
    snapshot: Optional[AnalysisSnapshotMetadata] = None,
) -> ReviewCorpusAnalysis:

    accepted_annotations = annotations_df.filter(pl.col("status") == "accepted")
    coverage = ReviewCoverageSummary(
        total_items=items_df.height,
        reviewed_items=items_df.filter(pl.col("status") == "reviewed").height,
        unreviewed_items=items_df.filter(pl.col("status") != "reviewed").height,
        accepted_annotations=accepted_annotations.height,
        failure_modes=failure_modes_df.height,
        pending_suggestions=pending_suggestions,
    )

    return ReviewCorpusAnalysis(
        corpus_id=corpus_id,
        project_id=project_id,
        agent_design_id=agent_design_id,
        backend="polars",
        coverage=coverage,
        source_kind_counts=count_by(items_df, "source_kind"),
        annotation_status_counts=count_by(annotations_df, "status"),
        pass_fail_counts=count_by(annotations_df, "pass_fail"),
        failure_mode_counts=failure_mode_counts(accepted_annotations, failure_modes_df),
        failure_rates=failure_rates(items_df, accepted_annotations),
        snapshot=snapshot,
        rationale=(
            "Polars computes read-side corpus analytics from platform-owned "
            "review records; Postgres remains the source of truth for metadata, "
            "workflow state, and evidence artifacts."
        ),
    )


def review_items_frame(items: List[ReviewItem]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "id": item.id,
                "source_kind": item.source_kind,
                "status": item.status,
                "has_langfuse_ref": item.langfuse_ref is not None,
                "langfuse_object_type": (
                    item.langfuse_ref.object_type if item.langfuse_ref else None
                ),
            }
            for item in items
        ],
        schema={
            "id": pl.String,
            "source_kind": pl.String,
            "status": pl.String,
            "has_langfuse_ref": pl.Boolean,
            "langfuse_object_type": pl.String,
        },
    )


def review_annotations_frame(annotations: List[ReviewAnnotation]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "id": annotation.id,
                "review_item_id": annotation.review_item_id,
                "status": annotation.status,
                "failure_mode_id": annotation.failure_mode_id,
                "pass_fail": annotation.metadata.get("pass_fail"),
            }
            for annotation in annotations
        ],
        schema={
            "id": pl.String,
            "review_item_id": pl.String,
            "status": pl.String,
            "failure_mode_id": pl.String,
            "pass_fail": pl.String,
        },
    )


def failure_modes_frame(failure_modes: List[FailureMode]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "id": failure_mode.id,
                "name": failure_mode.name,
                "severity": failure_mode.severity,
            }
            for failure_mode in failure_modes
        ],
        schema={"id": pl.String, "name": pl.String, "severity": pl.String},
    )


def load_snapshot_metadata(
    *,
    snapshot_dir: Path,
    status: str,
    item_count: int,
    annotation_count: int,
    failure_mode_count: int,
) -> AnalysisSnapshotMetadata:
    metadata_path = snapshot_dir / SNAPSHOT_METADATA_FILE
    generated_at = None
    if metadata_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        generated_at_value = payload.get("generated_at")
        if generated_at_value:
            generated_at = datetime.fromisoformat(generated_at_value)
    return AnalysisSnapshotMetadata(
        status=status,
        directory=str(snapshot_dir),
        generated_at=generated_at,
        item_count=item_count,
        annotation_count=annotation_count,
        failure_mode_count=failure_mode_count,
    )


def count_by(dataframe: pl.DataFrame, column: str) -> Dict[str, int]:
    if dataframe.height == 0:
        return {}
    counts = (
        dataframe.with_columns(pl.col(column).fill_null("unknown"))
        .group_by(column)
        .len(name="count")
        .sort(column)
    )
    return {str(row[column]): int(row["count"]) for row in counts.to_dicts()}


def failure_mode_counts(
    annotations_df: pl.DataFrame,
    failure_modes_df: pl.DataFrame,
) -> List[ReviewFailureModeCount]:
    if annotations_df.height == 0 or failure_modes_df.height == 0:
        return []
    joined = (
        annotations_df.filter(pl.col("failure_mode_id").is_not_null())
        .join(failure_modes_df, left_on="failure_mode_id", right_on="id", how="left")
        .with_columns(
            pl.col("name").fill_null("Unmapped failure mode"),
            pl.col("severity").fill_null("unknown"),
        )
    )
    if joined.height == 0:
        return []
    rows = (
        joined.group_by("failure_mode_id", "name", "severity")
        .len(name="accepted_annotations")
        .sort(["accepted_annotations", "name"], descending=[True, False])
        .to_dicts()
    )
    return [
        ReviewFailureModeCount(
            failure_mode_id=row["failure_mode_id"],
            name=row["name"],
            severity=row["severity"],
            accepted_annotations=int(row["accepted_annotations"]),
        )
        for row in rows
    ]


def failure_rates(
    items_df: pl.DataFrame,
    annotations_df: pl.DataFrame,
) -> List[ReviewFailureRate]:
    if items_df.height == 0:
        return []
    failed_items = (
        annotations_df.filter(
            (pl.col("status") == "accepted")
            & (
                (pl.col("pass_fail") == "fail")
                | pl.col("failure_mode_id").is_not_null()
            )
        )
        .select(pl.col("review_item_id").alias("id"))
        .unique()
        .with_columns(pl.lit(True).alias("has_failure"))
    )
    rated_items = items_df.join(failed_items, on="id", how="left").with_columns(
        pl.col("has_failure").fill_null(False)
    )
    rows = (
        rated_items.group_by("source_kind")
        .agg(
            pl.len().alias("total_items"),
            (pl.col("status") == "reviewed").sum().alias("reviewed_items"),
            pl.col("has_failure").sum().alias("failed_items"),
        )
        .with_columns(
            (pl.col("failed_items") / pl.col("total_items")).alias("failure_rate")
        )
        .sort("source_kind")
        .to_dicts()
    )
    return [
        ReviewFailureRate(
            source_kind=row["source_kind"],
            total_items=int(row["total_items"]),
            reviewed_items=int(row["reviewed_items"]),
            failed_items=int(row["failed_items"]),
            failure_rate=round(float(row["failure_rate"]), 4),
        )
        for row in rows
    ]
