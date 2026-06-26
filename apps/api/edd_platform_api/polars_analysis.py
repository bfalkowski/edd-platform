from __future__ import annotations

from typing import Dict, List

import polars as pl

from edd_platform_api.schemas import (
    FailureMode,
    ReviewCorpusAnalysis,
    ReviewCoverageSummary,
    ReviewFailureModeCount,
    ReviewFailureRate,
    ReviewItem,
    ReviewAnnotation,
)


def review_corpus_analysis(
    *,
    project_id: str,
    corpus_id: str,
    agent_design_id: str,
    items: List[ReviewItem],
    annotations: List[ReviewAnnotation],
    failure_modes: List[FailureMode],
    pending_suggestions: int,
) -> ReviewCorpusAnalysis:
    items_df = pl.DataFrame(
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
    annotations_df = pl.DataFrame(
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
    failure_modes_df = pl.DataFrame(
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
        rationale=(
            "Polars computes read-side corpus analytics from platform-owned "
            "review records; Postgres remains the source of truth for metadata, "
            "workflow state, and evidence artifacts."
        ),
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
