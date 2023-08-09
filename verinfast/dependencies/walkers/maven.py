from johnnydep.walkers.classes import Walker, Entry
from typing import TextIO
import xml.etree.ElementTree as ET

# TODO implement defusedxml

class MavenWalker(Walker):
    # pkg:maven/springframework/spring@1.2.6
    # mvn license:aggregate-add-third-party
    # mvn dependency:analyze
    # mvn dependency-check:check
    # mvn org.sonatype.ossindex.maven:ossindex-maven-plugin:audit -f pom.xml
    # <project>
    # ...
    # <properties>
    # <mavenVersion>3.0</mavenVersion>
    # </properties>

    # <dependencies>
    # <dependency>
    #     <groupId>org.apache.maven</groupId>
    #     <artifactId>maven-artifact</artifactId>
    #     <version>${mavenVersion}</version>
    # </dependency>
    # <dependency>
    #     <groupId>org.apache.maven</groupId>
    #     <artifactId>maven-core</artifactId>
    #     <version>${mavenVersion}</version>
    # </dependency>
    # </dependencies>
    # ...
    # </project>

    def parse(self, file:TextIO, expand=False):
        tree = ET.parse(file)
        # root = tree.getroot()
        dependencies = tree.findall('dependencies/dependency')
        for d in dependencies:
            n=d["groupId"]+ "/" + d["artifactId"]
            e = Entry(
                name=n, 
                source='maven', 
                specifier="=="+d["version"]
            )
            self.entries.append(e)

    def expand(self, file):
        raise Exception("No expansion for this Walker")

mavenWalker = Walker(manifest_type="xml", manifest_files=["pom.xml"])
