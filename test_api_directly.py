#!/usr/bin/env python3
"""Test the API endpoint directly to verify the fix is loaded."""

import sys
import requests
import json
from pathlib import Path

# Test image path
image_path = Path("storage/captures/INJECTED/STATION_1_main_1793112337.jpg")

if not image_path.exists():
    print(f"ERROR: Image not found at {image_path}")
    sys.exit(1)

print(f"Testing API with image: {image_path}")
print("="*80)

# Read the image
with open(image_path, "rb") as f:
    image_data = f.read()

# Try to call the API
api_url = "http://127.0.0.1:8000/api/v1/inspect/STATION_1"

print(f"\nCalling: {api_url}")

try:
    response = requests.post(
        api_url,
        files={"image": ("test.jpg", image_data, "image/jpeg")},
        data={
            "camera_name": "main",
            "seat_id": "TEST_SCRATCH_1793112337"
        },
        timeout=30
    )

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"\nResult:")
        print(json.dumps(result, indent=2))

        # Check defects
        if "defects" in result and result["defects"]:
            for defect in result["defects"]:
                print(f"\n{'='*80}")
                print(f"Defect Type: {defect.get('defect_type', 'UNKNOWN')}")
                print(f"Confidence: {defect.get('confidence', 0):.2f}")
                print(f"{'='*80}")

                defect_type = defect.get('defect_type', '').lower()
                if 'scratch' in defect_type:
                    print("\n✓ SUCCESS: Correctly classified as SCRATCH!")
                    sys.exit(0)
                elif 'anomaly' in defect_type:
                    print("\n✗ FAILED: Still showing as LEATHER_ANOMALY")
                    sys.exit(1)
        else:
            print("\nNo defects returned")
    else:
        print(f"Error: {response.text}")

except requests.exceptions.ConnectionError:
    print("\nERROR: Could not connect to API at http://127.0.0.1:8000")
    print("Make sure the server is running with:")
    print("  python -m camerainspection.main --host 127.0.0.1 --port 8000 --reload")
    sys.exit(1)
except Exception as e:
    print(f"\nERROR: {e}")
    sys.exit(1)
