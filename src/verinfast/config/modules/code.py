from dataclasses import dataclass
from ..utils.printable import Printable
from ..constants import DEFAULT_START


@dataclass
class GitModule(Printable):
    start: str = DEFAULT_START


@dataclass
class CodeModule(Printable):
    git: GitModule
    dry: bool = False
    dependencies: bool = True
