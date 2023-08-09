from typing import TextIO
import json
import xml.etree.ElementTree as ET

from johnnydep.walkers.classes import Walker, Entry

class NuGetWalker(Walker):
    def initialize(self, command: str):
        discoveryUrl = 'https://api.nuget.org/v3/index.json'
        uselessList = json.loads(self.getUrl(discoveryUrl).content.decode('utf-8'))
        for r in uselessList["resources"]:
            if "Catalog" in r["@type"]:
                self.catalogUrl = r["@id"]
            elif r["@type"] == "RegistrationsBaseUrl":
                self.registrationUrl = r["@id"]
        return super().initialize(command)
    
    def get_license(self, name:str, version:str)->str:
        resp = json.loads(self.getUrl(f"{self.registrationUrl}{name}/{version}.json").content.decode('utf-8'))
        catalog_entry_url = resp["catalogEntry"]
        catalog_entry = json.loads(self.getUrl(catalog_entry_url).content.decode("utf-8"))
        if "licenseExpression" in catalog_entry:
            return catalog_entry["licenseExpression"]
        elif "licenseUrl" in catalog_entry:
            return catalog_entry["licenseUrl"]
        else:
            return ""
        
    def parse(self, file):
        tree = ET.parse(file)
        x_path = "ItemGroup/PackageReference"
        dependencies = tree.findall(x_path)
        for d in dependencies:
            v = d["Version"]
            n = d["Include"]
            l = self.get_license(name=n, version=v)
            e = Entry(
                source="nuget",
                name=n,
                specifier="=="+v,
                license=l,
            )
            self.entries.append(e)

# Example: https://github.com/umbraco/Umbraco-CMS/pull/13787/files
c_sharp_matches = ["*.csproj"]

nugetWalker = NuGetWalker(manifest_type='xml', manifest_files=c_sharp_matches)
