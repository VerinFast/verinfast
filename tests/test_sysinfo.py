from verinfast.system.sysinfo import get_system_info
import json


def test_system_info_comprehensive():
    """Comprehensive test of system information collection"""
    print("\nTesting system information collection:")

    # Get system information
    info = get_system_info()

    # Print formatted output for visual inspection
    print("\nCollected System Information:")
    print(json.dumps(info, indent=4))

    # Validate the information
    assert isinstance(info, dict), "System info should be a dictionary"
    assert len(info) > 0, "System info should not be empty"

    # Check for essential keys
    essential_keys = [
        "OS",
        "OS Version",
        "OS Release",
        "Machine",
        "Processor",
        "CPU Cores",
        "Total RAM",
        "Python Version",
    ]

    print("\nValidating essential system information:")
    for key in essential_keys:
        assert key in info, f"Missing essential key: {key}"
        print(f"✓ {key}: {info[key]}")

    # Print summary
    print(f"\nTotal fields collected: {len(info)}")
    print("All validations passed!")


if __name__ == "__main__":
    test_system_info_comprehensive()
