from datetime import date

# Default time periods
DEFAULT_MONTH_DELTA = 6

DEFAULT_END_DATE = date.today()
DEFAULT_START_YEAR = DEFAULT_END_DATE.year
DEFAULT_START_MONTH = DEFAULT_END_DATE.month - DEFAULT_MONTH_DELTA

# Adjust start date if needed
while DEFAULT_START_MONTH <= 0:
    DEFAULT_START_YEAR -= 1
    DEFAULT_START_MONTH += 12

DEFAULT_START_DATE = date(
    year=DEFAULT_START_YEAR,
    month=DEFAULT_START_MONTH,
    day=1
)

# Format dates as strings
DEFAULT_START = f"{DEFAULT_START_DATE.year}-{DEFAULT_START_DATE.month}-{DEFAULT_START_DATE.day}"
DEFAULT_END = f"{DEFAULT_END_DATE.year}-{DEFAULT_END_DATE.month}-{DEFAULT_END_DATE.day}"

# Default paths and settings
DEFAULT_CONFIG_PATH = ".verinfast.yaml"
DEFAULT_SCAN_PATH = "./"
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_TRUNCATE_LENGTH = 30
DEFAULT_LOG_FORMAT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_LOG_FILENAME = "_log.txt"

# Supported protocols for remote configs
SUPPORTED_PROTOCOLS = ["http", "https"]
PROTOCOL_SEPARATOR = "://"
