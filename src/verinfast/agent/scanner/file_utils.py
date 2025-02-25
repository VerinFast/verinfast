import os


class FileUtils:
    def _get_file_list(self, path):
        """Get list of files for modernmetric analysis"""
        filelist = []
        for filepath, subdirs, files in os.walk("."):
            for name in files:
                fp = os.path.join(filepath, name)
                if self._is_allowed_file(fp):
                    filelist.append({"name": name, "path": fp})
        return filelist

    def _is_allowed_file(self, path, allow_dir=False):
        """Check if file should be included in analysis"""
        normpath = os.path.normpath(path)
        dirlist = normpath.split(os.sep)
        return (
            "node_modules" not in dirlist
            and ".git" not in dirlist
            and not os.path.islink(path)
            and (os.path.isfile(path) or allow_dir)
        )

    def get_raw_size(self, start_path="."):
        """Get recursive size of a directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp) and not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    def getloc(self, file):
        """Simple algorithm for lines of code in a file"""
        try:
            count = 0
            with open(file) as fp:
                for line in fp:
                    if line.strip():
                        count += 1
            return count
        except Exception as e:
            self.log(tag="ERROR", msg=f"Error getting lines of code: {str(e)}")
            return 0
