from verinfast.dependencies.walkers.classes import Walker, Entry
import xml.etree.ElementTree as ET


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

    def parse(self, file: str, expand=False):
        tree = ET.parse(file)
        # root = tree.getroot()
        dependencies = tree.findall('dependencies/dependency')
        for d in dependencies:
            groupId = d.find("groupId")
            artifcact = d.find("artifactId")
            version = d.find("version")
            g = groupId.text
            a = artifcact.text
            v = version.text
            n = g + "/" + a
            e = Entry(
                name=n,
                source='maven',
                specifier="=="+v
            )
            self.entries.append(e)

    def expand(self, file):
        raise Exception("No expansion for this Walker")
