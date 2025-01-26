import os
import subprocess
import shutil
import platform


def install_opengrep(install_dir, version="main"):
    """
    Clones the opengrep repo (which uses a Makefile), then runs make and
         make install.

    :param install_dir: Directory in which opengrep will be cloned.
    :param version:     Branch/tag/commit to check out.
    """
    os.makedirs(install_dir, exist_ok=True)

    opengrep_src = os.path.join(install_dir, "opengrep")

    # If the directory exists (e.g., from a prior attempt), remove it
    if os.path.isdir(opengrep_src):
        shutil.rmtree(opengrep_src)

    # Shallow clone at the specified version/branch/commit
    subprocess.run([
        "git", "clone",
        "--depth", "1",
        "--branch", version,
        "https://github.com/opengrep/opengrep.git",
        opengrep_src
    ], check=True)

    # Build with make
    # subprocess.run(["make", "install-deps"], check=True, cwd=opengrep_src)

    # Install (not using sudo, because installing in user temporary directory)
    # subprocess.run(["sudo", "make", "install"], check=True, cwd=opengrep_src)
    subprocess.run(["make"], check=True, cwd=opengrep_src)


def check_opengrep(install_dir="/tmp/opengrep_install"):
    """
    Checks if 'opengrep' is already installed on the system (on PATH).
        If not, installs it
    by calling install_opengrep, then returns the path to the
        'opengrep' executable.

    :param install_dir: Directory to clone and build opengrep in, if needed.
    :param version:     Git tag, branch, or commit to install if not present.
    :return:            The absolute path to the opengrep executable.
    """
    try:
        # Attempt to locate 'opengrep' in the PATH
        result = subprocess.run(
            ["which", "opengrep"], capture_output=True, text=True, check=True
        )
        opengrep_path = result.stdout.strip()
        print(f"opengrep is already installed at: {opengrep_path}")
        return opengrep_path
    except subprocess.CalledProcessError:
        # 'which opengrep' failed, so we install it
        print("opengrep not found on PATH. Installing now...")
        install_opengrep(install_dir)
        print("opengrep installation complete.")

        # Now try again to get the path
        try:
            result = subprocess.run(
                ["which", "opengrep"],
                capture_output=True,
                text=True,
                check=True
            )
            opengrep_path = result.stdout.strip()
            print(f"opengrep is now installed at: {opengrep_path}")
            return opengrep_path
        except subprocess.CalledProcessError:
            raise OSError(
                "opengrep was installed but could not be located on PATH."
            )


def get_opengrep_path():
    system = platform.system().lower()    # "linux", "darwin", ...
    machine = platform.machine().lower()  # "x86_64", "arm64", "aarch64", ...

    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"base_dir: {base_dir}")

    if system == "linux" and machine == "x86_64":
        return os.path.join(base_dir, "bin", "opengrep_linux_x86_64")
    elif system == "darwin" and machine == "x86_64":
        return os.path.join(base_dir, "bin", "opengrep_macos_x86_64")
    elif system == "darwin" and (machine == "arm64" or machine == "aarch64"):
        return os.path.join(base_dir, "bin", "opengrep_macos_arm64")
    else:
        raise OSError(f"Unsupported platform: {system}/{machine}")
