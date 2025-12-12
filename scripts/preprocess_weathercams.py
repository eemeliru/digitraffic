#!/usr/bin/env python3
"""
Preprocess weathercam data to create a static mapping file.

This script fetches detailed weathercam data from Digitraffic API and creates
a static JSON file containing camera ID, presets with presentation names, and
municipality information. This avoids making many API calls during runtime.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

headers = {"Digitraffic-User": "eemeliru/digitraffic"}


def fetch_weathercam_list():
    """Fetch list of weathercam stations from Digitraffic API."""
    print("Fetching weathercam list from Digitraffic API...")
    resp = requests.get(
        "https://tie.digitraffic.fi/api/weathercam/v1/stations?lastUpdated=false",
        timeout=30,
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("features", [])


def fetch_weathercam_details(camera_id):
    """Fetch detailed information for a specific weathercam station."""
    url = f"https://tie.digitraffic.fi/api/weathercam/v1/stations/{camera_id}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def preprocess_weathercams():
    """Process weathercam data and create municipality mapping with presets."""
    cameras = fetch_weathercam_list()

    print(f"Processing {len(cameras)} weathercams...")
    print()

    mapping = {}
    raw_data = {}
    failed = []

    for i, camera in enumerate(cameras):
        camera_id = camera["id"]
        camera_name = camera["properties"]["name"]

        print(
            f"[{i + 1}/{len(cameras)}] Fetching details for {camera_id} ({camera_name})..."
        )

        try:
            details = fetch_weathercam_details(camera_id)
            props = details["properties"]

            # Store complete raw response
            raw_data[camera_id] = details

            municipality = props.get("municipality", "Unknown")
            municipality_code = props.get("municipalityCode")

            # Extract preset information (only keep id, presentationName, imageUrl)
            presets = []
            for preset in props.get("presets", []):
                if preset.get("inCollection", False):
                    presets.append(
                        {
                            "id": preset["id"],
                            "presentationName": preset.get("presentationName", ""),
                            "imageUrl": preset.get("imageUrl", ""),
                        }
                    )

            mapping[camera_id] = {
                "name": camera_name,
                "municipality": municipality,
                "presets": presets,
                "names": props.get("names", {}),
                "nearestWeatherStationId": props.get("nearestWeatherStationId"),
            }

            print(f"  ✓ {municipality} - {len(presets)} presets")

            # Be polite to the API - small delay between requests
            time.sleep(0.2)

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed.append(camera_id)

    if failed:
        print(f"\n⚠ Warning: Failed to fetch {len(failed)} cameras:")
        for cam_id in failed:
            print(f"  - {cam_id}")

    return mapping, raw_data


def preprocess_from_raw_data(raw_file):
    """Process weathercam data from existing raw data file."""
    raw_path = Path(raw_file)

    if not raw_path.exists():
        print(f"Error: Raw data file not found: {raw_file}")
        sys.exit(1)

    print(f"Loading raw data from {raw_file}...")
    with open(raw_path, encoding="utf-8") as f:
        raw_data = json.load(f)

    print(f"Processing {len(raw_data)} weathercams from raw data...")
    print()

    mapping = {}
    failed = []

    for i, (camera_id, details) in enumerate(raw_data.items(), 1):
        try:
            props = details["properties"]
            camera_name = props.get("name", camera_id)
            municipality = props.get("municipality", "Unknown")

            print(f"[{i}/{len(raw_data)}] Processing {camera_id} ({camera_name})...")

            # Extract preset information (only keep id, presentationName, imageUrl)
            presets = []
            for preset in props.get("presets", []):
                if preset.get("inCollection", False):
                    presets.append(
                        {
                            "id": preset["id"],
                            "presentationName": preset.get("presentationName", ""),
                            "imageUrl": preset.get("imageUrl", ""),
                        }
                    )

            mapping[camera_id] = {
                "name": camera_name,
                "municipality": municipality,
                "presets": presets,
                "names": props.get("names", {}),
                "nearestWeatherStationId": props.get("nearestWeatherStationId"),
            }

            print(f"  ✓ {municipality} - {len(presets)} presets")

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed.append(camera_id)

    if failed:
        print(f"\n⚠ Warning: Failed to process {len(failed)} cameras:")
        for cam_id in failed:
            print(f"  - {cam_id}")

    return mapping, raw_data


def save_mapping(mapping, output_file):
    """Save the processed mapping to a JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(mapping)} weathercam mappings to {output_path}")

    # Print summary by municipality
    municipalities = {}
    total_presets = 0
    for camera_id, data in mapping.items():
        muni = data["municipality"]
        preset_count = len(data["presets"])
        municipalities[muni] = municipalities.get(muni, 0) + 1
        total_presets += preset_count

    print("\n📊 Summary:")
    print(f"  Total cameras: {len(mapping)}")
    print(f"  Total presets: {total_presets}")
    print(f"  Municipalities: {len(municipalities)}")
    print()
    print("Cameras per municipality:")
    for muni, count in sorted(municipalities.items()):
        print(f"  {muni}: {count}")


def save_raw_data(raw_data, output_file):
    """Save the raw API responses to a JSON file for future use."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(raw_data)} raw camera data to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Preprocess Digitraffic weathercam data"
    )
    parser.add_argument(
        "--from-raw",
        action="store_true",
        help="Process from existing raw data file instead of fetching from API",
    )
    parser.add_argument(
        "--raw-file",
        default="custom_components/digitraffic/raw_data/weathercam_raw_data.json",
        help="Path to raw data file (default: custom_components/digitraffic/raw_data/weathercam_raw_data.json)",
    )
    parser.add_argument(
        "--output",
        default="custom_components/digitraffic/data/weathercam_data.json",
        help="Path to output processed file (default: custom_components/digitraffic/data/weathercam_data.json)",
    )

    args = parser.parse_args()

    processed_file = args.output
    raw_file = args.raw_file

    print("=" * 70)
    print("Digitraffic Weathercam Data Preprocessor")
    print("=" * 70)
    print()

    if args.from_raw:
        print("Mode: Processing from existing raw data")
        print()
        mapping, raw_data = preprocess_from_raw_data(raw_file)
        # Don't save raw data again when processing from raw
    else:
        print("Mode: Fetching from API")
        print()
        mapping, raw_data = preprocess_weathercams()
        save_raw_data(raw_data, raw_file)

    save_mapping(mapping, processed_file)

    print()
    print("✓ Done! Processed data file is ready.")


if __name__ == "__main__":
    main()
