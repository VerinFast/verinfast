from verinfast.dependencies.walkers.classes import Walker, Entry


class DockerWalker(Walker):
    def clean_str(self, s: str | bytes):
        bad_chars = ["\n", "\r", "\t"]
        s = str(s).lower().strip()
        for char in bad_chars:
            s = s.replace(char, "")
        return s

    def parse_address(
            self,
            address: str,
            file: str,
            source: str = "Dockerfile"
            ) -> Entry:
        name = address
        specifier = "*"

        if "/" in name:
            last_slash = name.rfind("/")
            sub_str = name[last_slash+1:]
            if "@" in name:
                [name, specifier] = name.split("@")
            elif ":" in sub_str:
                specifier = sub_str.split(":")[1]
                name = name[0:last_slash]

        elif "@" in name:
            [name, specifier] = name.split("@")

        elif ":" in name:
            [name, specifier] = name.split(":")

        e = Entry(
            name=name,
            specifier=specifier,
            source=source,
            required_by=file
        )
        return e

    def parse(self, file: str, expand=False):
        with open(file, 'r') as f:
            string = f'\nDockerfile found {file}:\n\n\n {str(f.read())} \n\n\n'
            self.log(timestamp=False, tag=None, msg=string)
        with open(file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                line = self.clean_str(line)
                if line.startswith('from '):
                    name = line.split(' ')[1]
                    e = self.parse_address(name, file)
                    self.entries.append(e)
                elif line.startswith("image:"):
                    name = line[6:]
                    e = self.parse_address(name, file, source="docker-compose")
                    self.entries.append(e)

    def expand(self, file):
        raise Exception("No expansion for this Walker")
