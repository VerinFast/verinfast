from dataclasses import dataclass
import datetime


@dataclass
class Utilization_Datapoint:
    Timestamp: datetime
    Minimum: float
    Average: float
    Maximum: float

    @staticmethod
    def From(i: dict):
        if {"Timestamp", "Minimum", "Average", "Maximum"} <= i.keys():
            return Utilization_Datapoint(
                Timestamp=i["Timestamp"],
                Minimum=i["Minimum"],
                Average=i["Average"],
                Maximum=i["Maximum"])
        else:
            raise Exception("Invalid Datapoint")


@dataclass
class Utilization_Datum:
    cpu: Utilization_Datapoint
    mem: Utilization_Datapoint
    hdd: Utilization_Datapoint
