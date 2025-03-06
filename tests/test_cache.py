from pathlib import Path
import time
from verinfast.agent import Agent
from verinfast.config import Config


def setup_test_file():
    # Create a simple test file
    test_content = """
def test_function():
    password = "hardcoded_password"  # This should trigger a semgrep finding
    return password
"""
    test_file = Path("test_sample.py")
    with open(test_file, "w") as f:
        f.write(test_content)
    return test_file


def test_semgrep_cache():
    # Create test file
    test_file = setup_test_file()

    # Minimal configuration
    config = Config()
    config.runGit = False
    config.runSizes = False
    config.runStats = False
    config.runDependencies = False
    config.config["local_repos"] = [str(test_file.parent.absolute())]

    try:
        # First run
        print("\nRunning first scan...")
        start_time = time.time()
        agent = Agent()
        agent.config = config
        agent.scan()
        first_duration = time.time() - start_time
        print(f"First scan took: {first_duration:.2f} seconds")

        # Second run should use cache
        print("\nRunning second scan...")
        start_time = time.time()
        agent2 = Agent()
        agent2.config = config
        agent2.scan()
        second_duration = time.time() - start_time
        print(f"Second scan took: {second_duration:.2f} seconds")

        assert second_duration < first_duration - 0.5  # Second run should be faster
        assert Path(Path.home(), '.verinfast_cache/semgrep.db').exists()

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


def test_cache_persistence():
    cache_path = Path(Path.home(), '.verinfast_cache/semgrep.db')

    # First run creates cache
    agent = Agent()
    agent.config.runGit = False
    agent.config.runSizes = False
    agent.config.runStats = False
    agent.config.runDependencies = False
    agent.scan()

    # Verify cache exists and has content
    assert cache_path.exists()
    assert cache_path.stat().st_size > 0
