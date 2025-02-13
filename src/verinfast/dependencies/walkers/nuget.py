import json
import xml.etree.ElementTree as ET

from verinfast.dependencies.walkers.classes import Walker, Entry


class NuGetWalker(Walker):
    def initialize(self, command: str = None):
        discoveryUrl = 'https://api.nuget.org/v3/index.json'
        try:
            resp = self.getUrl(discoveryUrl)
            uselessList = json.loads(resp)
            for r in uselessList["resources"]:
                if "Catalog" in r["@type"]:
                    self.catalogUrl = r["@id"]
                elif r["@type"] == "RegistrationsBaseUrl":
                    self.registrationUrl = r["@id"]
            if command:
                return super().initialize(command)
        except Exception as e:
            self.log(
                f"NuGet API not found for: {discoveryUrl}",
                display=False
            )
            self.log(e, display=False)
            return None

    def get_license(self, name: str, version: str) -> str:
        resp = None
        name2 = name.lower()
        try:
            license_resp = self.getUrl(f"{self.registrationUrl}{name}/{version}.json")  # NOQA:E501
            resp = json.loads(license_resp)
        except Exception as e:
            self.log(e, display=False)
            try:
                license_resp = (
                    self
                    .getUrl(f"{self.registrationUrl}{name2}/{version}.json")
                )
                resp = json.loads(license_resp)
            except Exception as e2:
                self.log(
                    f"License not found for: {name}@{version}",
                    display=True
                )
                self.log(e2, display=False)
        if resp is not None:
            catalog_entry_url = resp["catalogEntry"]
            catalog_entry = json.loads(self.getUrl(catalog_entry_url))
            if "licenseExpression" in catalog_entry:
                return catalog_entry["licenseExpression"]
            elif "licenseUrl" in catalog_entry:
                return catalog_entry["licenseUrl"]
            else:
                return ""
        else:
            return ""

    def parse(self, file: str, expand=False):
        # Reference: <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" /> # noqa: E501
        tree = ET.parse(file)
        x_path = "ItemGroup/PackageReference"
        dependencies = tree.findall(x_path)
        for d in dependencies:
            v = d.attrib["Version"]
            n = d.attrib["Include"]
            lic = self.get_license(name=n, version=v)
            e = Entry(
                source="nuget",
                name=n,
                specifier="=="+v,
                license=lic,
            )
            self.entries.append(e)


# Example: https://github.com/umbraco/Umbraco-CMS/pull/13787/files
c_sharp_matches = ["*.csproj"]
