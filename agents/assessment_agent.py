"""Assessment Agent: Evaluates article diagnostic value against hypotheses using self-consistency."""

import logging
from collections import Counter

from tools.audit_logger import AuditLogger

from .base import ArticleData, AssessmentResult, HypothesisScore


logger = logging.getLogger(__name__)


class AssessmentAgent:
    """Tier 2 Agent: Evaluates articles against competing hypotheses.
    
    Responsibilities:
    - Evaluate each article's diagnostic value against 3 human-selected hypotheses
    - Use temperature-sampled multi-pass evaluation to measure confidence via self-consistency
    - Flag for human review if confidence < threshold
    - Use evidence marks: ++, +, N/A, -, --
    """

    def __init__(self, config, hypotheses: list[dict], llm_interface):
        """Initialize the Assessment Agent.

        Args:
            config: Settings object with assessment configuration
            hypotheses: List of hypothesis definitions from hypothesis_config.yaml
            llm_interface: LLMInterface used to score article-hypothesis pairs
        """
        self.config = config
        self.hypotheses = hypotheses
        self.llm_interface = llm_interface
        logger.info(f"AssessmentAgent initialized with {len(hypotheses)} hypotheses")

    def evaluate_single_pass(self, article: ArticleData) -> dict[str, str]:
        """One comparative LLM pass scoring the article against all hypotheses.

        Args:
            article: Article to evaluate

        Returns:
            Dict mapping each hypothesis id -> evidence mark.

        Note:
            All competing hypotheses are scored together in a single call so the
            model can discriminate between them (ACH diagnosticity). Uses the
            configured sampling temperature (default 0.7) so repeated passes vary,
            enabling self-consistency measurement. Evidence marks: ++, +, N/A, -, --
        """
        return self.llm_interface.evaluate_hypotheses(
            article_content=article.content,
            hypotheses=self.hypotheses,
            evidence_marks=self.config.evidence_marks,
        )

    def measure_self_consistency(self, scores: list[str]) -> float:
        """Compute confidence as fraction of agreement across multi-pass evaluations.
        
        Args:
            scores: List of evidence marks from multiple LLM passes (e.g., ['+', '+', 'N/A', '+', ...])
            
        Returns:
            Confidence score (0.0-1.0) representing agreement rate
        """
        if not scores:
            return 0.0

        # Confidence = fraction of passes that agree with the most common mark
        _, most_common_count = Counter(scores).most_common(1)[0]
        return most_common_count / len(scores)

    def assess_article(self, article: ArticleData) -> AssessmentResult:
        """Main assessment: Evaluate article against all hypotheses using multi-pass sampling.
        
        Args:
            article: Article to assess
            
        Returns:
            AssessmentResult with hypothesis scores and confidence
            
        Process:
            1. Run N comparative passes (default=10) at temperature=0.7; each
               pass scores all hypotheses together.
            2. Per hypothesis, measure self-consistency across passes for confidence.
            3. Flag for human review if any confidence < threshold.
        """
        logger.debug(f"Assessing article: {article.title[:60]}")

        # Run multi-pass comparative evaluation; each pass returns {hyp_id: mark}.
        # Collect the per-pass marks for each hypothesis to measure consistency.
        marks_by_hypothesis: dict[str, list[str]] = {h["id"]: [] for h in self.hypotheses}
        for _ in range(self.config.llm_num_passes):
            pass_marks = self.evaluate_single_pass(article)
            for h in self.hypotheses:
                marks_by_hypothesis[h["id"]].append(pass_marks.get(h["id"], "N/A"))

        hypothesis_scores = []
        for hypothesis in self.hypotheses:
            scores = marks_by_hypothesis[hypothesis["id"]]

            # Self-consistency: confidence is the majority-agreement fraction
            confidence = self.measure_self_consistency(scores)
            most_common = Counter(scores).most_common(1)[0][0]

            hypothesis_scores.append(
                HypothesisScore(
                    hypothesis_id=hypothesis["id"],
                    hypothesis_name=hypothesis["name"],
                    evidence_mark=most_common,
                    confidence=confidence,
                    reasoning=(
                        f"{self.config.llm_num_passes}-pass comparative ACH "
                        f"{dict(Counter(scores))} -> {most_common} "
                        f"(confidence {confidence:.2f})"
                    ),
                )
            )

        # Compute overall confidence and determine if human review is needed
        overall_confidence = sum(hs.confidence for hs in hypothesis_scores) / len(hypothesis_scores)
        flagged_for_review = (
            overall_confidence < self.config.confidence_threshold
            or any(hs.confidence < self.config.confidence_threshold for hs in hypothesis_scores)
        )

        result = AssessmentResult(
            article_id=article.article_id,
            hypothesis_scores=hypothesis_scores,
            overall_confidence=overall_confidence,
            flagged_for_human_review=flagged_for_review,
        )

        AuditLogger.log_assessment(
            article.article_id,
            {hs.hypothesis_id: hs.evidence_mark for hs in hypothesis_scores},
            overall_confidence,
        )
        logger.info(
            f"Assessment complete. Overall confidence: {overall_confidence:.2f}. "
            f"Flagged: {flagged_for_review}"
        )

        return result

    def execute(self, articles: list[ArticleData]) -> list[AssessmentResult]:
        """Batch process articles and return assessments.
        
        Args:
            articles: List of articles from Scraper Agent
            
        Returns:
            List of AssessmentResults (forwarded to Matrix Agent)
        """
        results = []
        total = len(articles)
        for i, article in enumerate(articles, start=1):
            logger.info(
                f"[{i}/{total}] assessing ({self.config.llm_num_passes} passes): "
                f"{article.title[:60]}"
            )
            result = self.assess_article(article)
            results.append(result)

        logger.info(f"Assessed {len(results)} articles")
        return results
