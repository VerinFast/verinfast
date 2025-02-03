from dataclasses import is_dataclass, asdict
from datetime import date
import json


class Printable:
    """Base class providing string representation for config classes"""

    def __str__(self):
        d = {}
        for key in dir(self):
            x = self.__getattribute__(key)
            if not key.startswith("_") and not callable(x):
                if is_dataclass(x):
                    d[key] = asdict(x)
                elif isinstance(x, date):
                    d[key] = x.strftime("%Y-%mm-%dd")
                elif x is None:
                    d[key] = None
                else:
                    d[key] = x.__str__()

        return json.dumps(d, indent=4, default=str)
