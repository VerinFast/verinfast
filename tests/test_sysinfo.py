from verinfast.system.sysinfo import get_system_info
import subprocess
import json


def test_hyfetch_installation():
    """Test if hyfetch is installed and can run directly"""
    print("\nTesting hyfetch installation:")
    try:
        # Try to run hyfetch directly with timeout
        result = subprocess.run(
            ["hyfetch", "--version"],
            capture_output=True,
            text=True,
            timeout=15
        )
        print(f"Hyfetch is installed. Version output: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("Hyfetch is not installed")
        return False
    except subprocess.TimeoutExpired:
        print("Hyfetch command timed out")
        return False
    except Exception as e:
        print(f"Unexpected error running hyfetch: {str(e)}")
        return False


def test_system_info_comprehensive():
    """Comprehensive test of system information collection"""
    print("\nTesting system information collection:")

    # First check if hyfetch is installed
    hyfetch_available = test_hyfetch_installation()

    # Get system information
    info = get_system_info()

    # Print formatted output for visual inspection
    print("\nCollected System Information:")
    print(json.dumps(info, indent=4))

    # Analyze the response
    if "error" in info:
        print(f"\nFallback mechanism was triggered: {info['error']}")
        if hyfetch_available:
            print("WARNING: Hyfetch is installed but failed to run properly")
        info = info["system_info"]  # Use fallback info for validation
    else:
        print("\nHyfetch ran successfully")

    # Validate the information
    assert isinstance(info, dict), "System info should be a dictionary"
    assert len(info) > 0, "System info should not be empty"

    # Check for essential keys
    essential_keys = [
        "os",
        "os_release",
        "architecture",
        "python_version",
        "cpu_count",
        "platform",
        "processor"
    ]

    print("\nValidating essential system information:")
    for key in essential_keys:
        if key in info:
            print(f"✓ {key}: {info[key]}")
        else:
            print(f"✗ Missing: {key}")
            assert False, f"Missing essential key: {key}"

    # Print summary
    print(f"\nTotal fields collected: {len(info)}")
    print("All validations passed!")


if __name__ == "__main__":
    test_system_info_comprehensive()
