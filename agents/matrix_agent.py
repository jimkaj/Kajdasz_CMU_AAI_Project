"""Matrix Agent: Maintains ACH decision matrix with versioned snapshots."""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import AssessmentResult, MatrixAggregation, MatrixAgentState


logger = logging.getLogger(__name__)


class MatrixAgent:
    """Tier 3 Agent: Maintains ACH decision matrix and versioned snapshots.
    
    Responsibilities:
    - Ingest scored evidence from Assessment Agent
    - Maintain hypothesis support aggregations (cumulative evidence tallies)
    - Store versioned ACH matrix snapshots as CSV
    - Enforce 1GB storage cap on matrix directory
    """

    # Evidence-mark weights for the net-support score.
    _MARK_WEIGHTS = {"++": 2, "+": 1, "N/A": 0, "-": -1, "--": -2}

    def __init__(self, config, file_manager):
        """Initialize the Matrix Agent.

        Args:
            config: Settings object with matrix configuration
            file_manager: FileManager used for directory sizing and snapshot pruning
        """
        self.config = config
        self.file_manager = file_manager
        self.matrix_dir = config.data_dir / "matrix"
        self.matrix_dir.mkdir(parents=True, exist_ok=True)

        # Load existing matrix (accumulates across runs) or initialize new one
        self.state = self._load_matrix_state()
        logger.info(
            f"MatrixAgent initialized (v{self.state.matrix_version}, "
            f"{self.state.article_count} articles carried over)"
        )

    def _net_support(self, tally: dict[str, int]) -> float:
        """Compute net support: ++ -> +2, + -> +1, N/A -> 0, - -> -1, -- -> -2."""
        return float(sum(count * self._MARK_WEIGHTS[mark] for mark, count in tally.items()))

    def _latest_snapshot(self) -> Optional[Path]:
        """Return the most recently modified matrix snapshot, or None if none exist."""
        snapshots = sorted(
            self.matrix_dir.glob("acch_matrix_v*.csv"), key=lambda p: p.stat().st_mtime
        )
        return snapshots[-1] if snapshots else None

    def _load_matrix_state(self) -> MatrixAgentState:
        """Load the current matrix state from the latest snapshot so evidence
        tallies accumulate across runs.

        Returns:
            MatrixAgentState reconstructed from the latest snapshot, or a fresh
            state if no (compatible) snapshot exists.
        """
        fresh = MatrixAgentState(
            matrix_version=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            hypothesis_aggregates={},
            article_count=0,
        )

        latest = self._latest_snapshot()
        if latest is None:
            logger.info("No prior matrix snapshot found; starting fresh")
            return fresh

        try:
            with open(latest, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                if not header or header[0].lower() != "hypothesis_id":
                    logger.warning(
                        f"Snapshot {latest.name} lacks a hypothesis_id column "
                        "(legacy format); starting fresh"
                    )
                    return fresh

                aggregates: dict[str, MatrixAggregation] = {}
                article_count = 0
                for row in reader:
                    if len(row) < 7:
                        continue
                    hid, name = row[0], row[1]
                    tally = {
                        "++": int(row[2]), "+": int(row[3]), "N/A": int(row[4]),
                        "-": int(row[5]), "--": int(row[6]),
                    }
                    aggregates[hid] = MatrixAggregation(
                        hypothesis_id=hid,
                        hypothesis_name=name,
                        evidence_tally=tally,
                        net_support=self._net_support(tally),
                    )
                    # Each article contributes one mark per hypothesis, so the
                    # per-hypothesis tally sum equals the article count.
                    article_count = max(article_count, sum(tally.values()))
        except (OSError, ValueError, csv.Error) as e:
            logger.error(f"Failed to load matrix snapshot {latest}: {e}; starting fresh")
            return fresh

        logger.info(
            f"Loaded matrix from {latest.name}: "
            f"{len(aggregates)} hypotheses, {article_count} articles"
        )
        return MatrixAgentState(
            matrix_version=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            hypothesis_aggregates=aggregates,
            article_count=article_count,
        )

    def ingest_assessment(self, assessment: AssessmentResult) -> None:
        """Ingest a single assessment result and update hypothesis aggregates.
        
        Args:
            assessment: AssessmentResult from Assessment Agent
        """
        for score in assessment.hypothesis_scores:
            hypothesis_id = score.hypothesis_id
            evidence_mark = score.evidence_mark
            
            # Initialize hypothesis aggregate if needed
            if hypothesis_id not in self.state.hypothesis_aggregates:
                self.state.hypothesis_aggregates[hypothesis_id] = MatrixAggregation(
                    hypothesis_id=hypothesis_id,
                    hypothesis_name=score.hypothesis_name,
                )
            
            # Update evidence tally
            aggregate = self.state.hypothesis_aggregates[hypothesis_id]
            if evidence_mark in aggregate.evidence_tally:
                aggregate.evidence_tally[evidence_mark] += 1

            aggregate.net_support = self._net_support(aggregate.evidence_tally)
        
        self.state.article_count += 1
        self.state.last_update = datetime.utcnow()
        logger.debug(f"Ingested assessment for article {assessment.article_id}")

    def save_matrix_snapshot(self) -> Path:
        """Save current matrix state as versioned CSV snapshot.
        
        Returns:
            Path to the saved snapshot file
        """
        snapshot_path = self.matrix_dir / (
            f"acch_matrix_v{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.csv"
        )
        
        with open(snapshot_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header row. hypothesis_id is first so snapshots can be reloaded
            # into state keyed by id (see _load_matrix_state).
            writer.writerow(
                ["hypothesis_id", "Hypothesis", "++", "+", "N/A", "-", "--", "Net Support"]
            )

            # Data rows
            for agg in self.state.hypothesis_aggregates.values():
                writer.writerow([
                    agg.hypothesis_id,
                    agg.hypothesis_name,
                    agg.evidence_tally["++"],
                    agg.evidence_tally["+"],
                    agg.evidence_tally["N/A"],
                    agg.evidence_tally["-"],
                    agg.evidence_tally["--"],
                    agg.net_support,
                ])

        logger.info(f"Saved matrix snapshot: {snapshot_path}")
        return snapshot_path

    def cleanup_old_snapshots(self) -> None:
        """Enforce the storage cap by pruning oldest snapshots if needed.

        Delegates to the FileManager, which deletes the oldest
        ``acch_matrix_v*.csv`` files until the matrix directory is under
        ``matrix_storage_cap_gb``.
        """
        self.file_manager.cleanup_old_snapshots(self.config.matrix_storage_cap_gb)
        self.state.total_storage_used_mb = self.file_manager.get_directory_size_mb(
            self.matrix_dir
        )

    def execute(self, assessments: list[AssessmentResult]) -> MatrixAgentState:
        """Ingest assessments, update matrix, and save snapshot.
        
        Args:
            assessments: List of AssessmentResults from Assessment Agent
            
        Returns:
            Updated MatrixAgentState
        """
        logger.info(f"MatrixAgent processing {len(assessments)} assessments")
        
        for assessment in assessments:
            self.ingest_assessment(assessment)
        
        # Save snapshot
        self.save_matrix_snapshot()
        
        # Enforce storage cap
        self.cleanup_old_snapshots()
        
        logger.info(f"Matrix state updated. Total articles: {self.state.article_count}")
        return self.state
