import os
from pathlib import Path
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
    """
    Determines the appropriate opengrep binary based on the
    current system and architecture.
    Assumes the binaries are located in /verinfast/bin relative
    to the package's root directory.

    :return: Absolute path to the opengrep executable.
    :raises OSError: If the platform or architecture is unsupported.
    :raises FileNotFoundError: If the opengrep binary is not found
    in the expected location.
    """
    # Detect the operating system and machine architecture
    system = platform.system().lower()         # e.g., "linux", "darwin"
    machine = platform.machine().lower()       # e.g., "x86_64", "arm64"

    current_file = Path(__file__).resolve()
    # Navigate up three levels to reach /verinfast/
    # /verinfast/src/verinfast/sast/opengrid.py
    # -> parents[0] = /verinfast/src/verinfast/sast
    # parents[1] = /verinfast/src/verinfast
    # parents[2] = /verinfast/src
    # parents[3] = /verinfast
    verinfast_dir = current_file.parents[3]
    bin_dir = verinfast_dir / 'bin'

    # Define the mapping of (system, machine) to the
    # corresponding binary filenames
    binary_map = {
        ("linux", "x86_64"): "opengrep_manylinux_x86",
        ("darwin", "arm64"): "opengrep_osx_arm64"
    }

    # Retrieve the binary name based on the current system and machine
    binary_name = binary_map.get((system, machine))

    if not binary_name:
        raise OSError(
            f"Unsupported platform or architecture: {system}/{machine}"
        )

    # Construct the full path to the opengrep binary
    opengrep_path = bin_dir / binary_name

    # Check if the binary exists
    if not opengrep_path.exists():
        raise FileNotFoundError(
            f"opengrep binary not found at {opengrep_path}. "
            "Please ensure the binary is downloaded and placed in the "
            "'bin' directory."
        )

    # Ensure the binary has execute permissions
    if not os.access(opengrep_path, os.X_OK):
        try:
            os.chmod(opengrep_path, 0o755)
        except PermissionError as e:
            raise PermissionError(
                f"Cannot make opengrep executable at {opengrep_path}. "
                f"Please check your permissions."
            ) from e

    return str(opengrep_path)
