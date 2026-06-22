"""Comprehensive audit logging for agent interactions."""

import logging
from pathlib import Path

# Third-party loggers that are noisy at INFO/DEBUG; kept quiet on the console.
_NOISY_LOGGERS = ("urllib3", "requests", "httpx", "httpcore", "filelock", "asyncio")


def setup_console_logging(debug: bool = False) -> None:
    """Stream agent logs to the terminal so a run shows live progress.

    The agents/tools log via module loggers (``agents.*``, ``tools.*``) which
    propagate to the root logger, so a single console handler on root surfaces
    all of them. File-based audit logging (see ``setup_audit_logging``) is
    unaffected. Uses ``rich`` for readable output when available.

    Args:
        debug: If True, show DEBUG-level messages; otherwise INFO and above.
    """
    root = logging.getLogger()
    level = logging.DEBUG if debug else logging.INFO
    root.setLevel(level)

    # Idempotent: don't stack duplicate console handlers across calls.
    if any(getattr(h, "_ach_console", False) for h in root.handlers):
        return

    try:
        from rich.logging import RichHandler

        handler = RichHandler(show_path=False, rich_tracebacks=True, markup=False)
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    except ImportError:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
        )

    handler.setLevel(level)
    handler._ach_console = True  # marker for idempotency
    root.addHandler(handler)

    # Keep chatty third-party libraries off the console.
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_audit_logging(logs_dir: Path) -> None:
    """Configure audit logging for all agent interactions.
    
    Args:
        logs_dir: Directory for log files
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure main interaction logger
    interaction_logger = logging.getLogger("ach_agent.interactions")
    interaction_handler = logging.FileHandler(
        logs_dir / "agent_interactions.log", encoding="utf-8"
    )
    interaction_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    interaction_logger.addHandler(interaction_handler)
    interaction_logger.setLevel(logging.INFO)
    
    # Configure assessment logger
    assessment_logger = logging.getLogger("ach_agent.assessments")
    assessment_handler = logging.FileHandler(
        logs_dir / "assessments.log", encoding="utf-8"
    )
    assessment_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    assessment_logger.addHandler(assessment_handler)
    assessment_logger.setLevel(logging.INFO)
    
    # Configure error logger
    error_logger = logging.getLogger("ach_agent.errors")
    error_handler = logging.FileHandler(logs_dir / "errors.log", encoding="utf-8")
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    error_logger.addHandler(error_handler)
    error_logger.setLevel(logging.WARNING)


class AuditLogger:
    """Centralized audit logging for agent interactions."""
    
    @staticmethod
    def log_scrape(url: str, status: str, message: str = "") -> None:
        """Log a web scrape attempt.
        
        Args:
            url: URL that was scraped
            status: Success/failure status
            message: Additional context
        """
        logger = logging.getLogger("ach_agent.interactions")
        logger.info(f"SCRAPE [{status}] {url} - {message}")
    
    @staticmethod
    def log_assessment(article_id: str, hypothesis_scores: dict, confidence: float) -> None:
        """Log an assessment result.
        
        Args:
            article_id: Article being assessed
            hypothesis_scores: Scores for each hypothesis
            confidence: Overall confidence metric
        """
        logger = logging.getLogger("ach_agent.assessments")
        logger.info(f"ASSESS [{article_id}] confidence={confidence:.2f} - {hypothesis_scores}")
    
    @staticmethod
    def log_error(agent: str, error: Exception) -> None:
        """Log an error from an agent.
        
        Args:
            agent: Agent that encountered error
            error: The exception
        """
        logger = logging.getLogger("ach_agent.errors")
        logger.error(f"[{agent}] {type(error).__name__}: {str(error)}")
