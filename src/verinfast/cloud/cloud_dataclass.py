from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union


@dataclass
class Utilization_Datapoint:
    Minimum: Optional[float] = None
    Average: Optional[float] = None
    Maximum: Optional[float] = None
    Timestamp: Optional[datetime] = None

    @property
    def dict(self):
        o = {}
        if self.Minimum is None and self.Average is None and self.Maximum is None:
            return None

        if self.Minimum is not None:
            o["minimum"] = self.Minimum
        if self.Average is not None:
            o["average"] = self.Average
        if self.Maximum is not None:
            o["maximum"] = self.Maximum
        return o

    @staticmethod
    def From(i: dict):
        if {"Minimum", "Average", "Maximum"} <= i.keys():
            return Utilization_Datapoint(
                Minimum=i["Minimum"], Average=i["Average"], Maximum=i["Maximum"]
            )
        else:
            raise Exception("Invalid Datapoint")


@dataclass
class Utilization_Datum:
    Timestamp: Union[datetime, float]
    cpu: Optional[Utilization_Datapoint] = None
    mem: Optional[Utilization_Datapoint] = None
    hdd: Optional[Utilization_Datapoint] = None

    @property
    def dict(self):
        if type(self.Timestamp) is datetime:
            s = int(self.Timestamp.timestamp())
        else:
            s = self.Timestamp
        o = {"timestamp": s}
        if self.cpu is not None:
            o["cpu"] = self.cpu.dict
        if self.mem is not None:
            o["mem"] = self.mem.dict
        if self.hdd is not None:
            o["hdd"] = self.hdd.dict
        return o
