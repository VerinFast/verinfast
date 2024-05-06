from verinfast.dependencies.walkers.classes import Walker, Entry


class DockerWalker(Walker):
    def parse(self, file: str, expand=False):
        with open(file, 'rb') as f:
            string = f'\nDockerfile found {file}:\n\n\n {str(f.read())} \n\n\n'
            self.log(timestamp=False, tag=None, msg=string)
        with open(file, 'rb') as f:
            lines = f.readlines()
            for line in lines:
                print(line)
                line = str(line).lower()
                if line.startswith('from'):
                    print('matches from')
                    name = line.split(' ')[1]
                    parts = name.split(':')
                    e = Entry(
                        name=parts[0],
                        specifier=parts[1],
                        source='Dockerfile',
                        required_by=file
                    )
                    print(e.to_json())
                    self.entries.append(e)

    def expand(self, file):
        raise Exception("No expansion for this Walker")
