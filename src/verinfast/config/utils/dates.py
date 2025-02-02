from datetime import datetime, date
from typing import Tuple, Optional

from ..constants import DEFAULT_START, DEFAULT_END


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format

    Args:
        date_str: Date string to parse

    Returns:
        date: Parsed date object

    Raises:
        ValueError: If date string is invalid
    """
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got {date_str}") from e


def format_date(d: date) -> str:
    """Format date as YYYY-MM-DD string

    Args:
        d: Date to format

    Returns:
        str: Formatted date string
    """
    return d.strftime('%Y-%m-%d')


def validate_date_range(
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Tuple[str, str]:
    """Validate and normalize date range

    Args:
        start: Start date string (YYYY-MM-DD)
        end: End date string (YYYY-MM-DD)

    Returns:
        Tuple[str, str]: Normalized start and end dates

    Raises:
        ValueError: If dates are invalid or end is before start
    """
    # Use defaults if not provided
    start = start or DEFAULT_START
    end = end or DEFAULT_END

    # Parse dates
    start_date = parse_date(start)
    end_date = parse_date(end)

    # Validate range
    if end_date < start_date:
        raise ValueError(
            f"End date ({end}) cannot be before start date ({start})"
        )

    return format_date(start_date), format_date(end_date)
