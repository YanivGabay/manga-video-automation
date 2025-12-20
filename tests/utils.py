"""
Shared test utilities
"""
from pathlib import Path
from datetime import datetime

# Base test output directory
TESTS_OUTPUT_DIR = Path(__file__).parent / "output"
TESTS_OUTPUT_DIR.mkdir(exist_ok=True)


def create_test_run_dir(prefix: str = "test") -> Path:
    """Create a unique timestamped output directory for a test run.

    Args:
        prefix: Name prefix for the folder (e.g., "narration", "pipeline")

    Returns:
        Path to the created directory

    Example:
        output_dir = create_test_run_dir("narration")
        # Creates: tests/output/narration_20241219_143052/
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = TESTS_OUTPUT_DIR / f"{prefix}_{timestamp}"
    output_dir.mkdir(exist_ok=True)
    return output_dir
