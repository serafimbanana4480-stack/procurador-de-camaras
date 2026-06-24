"""Quick test of the camera scanning pipeline with mock data."""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONIOENCODING"] = "utf-8"

logging.basicConfig(level=logging.INFO, format="%(message)s")

from procurador.core.models import Camera, CameraStatus, SourceType, ScanConfig, ScanResult
from procurador.core.scanner import scan_camera_basic
from procurador.core.brute import brute_camera
from procurador.core.geoip import GeoIPResolver
from procurador.export.json_export import export_json
from procurador.export.csv_export import export_csv

import time

# Create mock cameras (like they came from Censys)
mock_cameras = [
    Camera(ip="192.168.1.100", port=554, source=SourceType.MANUAL, vendor="Hikvision"),
    Camera(ip="192.168.1.101", port=554, source=SourceType.MANUAL, vendor="Dahua"),
    Camera(ip="10.0.0.50", port=554, source=SourceType.MANUAL, vendor="Axis"),
]

print("[*] Testing scan pipeline on mock cameras...")
print()

config = ScanConfig(rtsp_probe_timeout=2, brute_enabled=False)

results = []
for cam in mock_cameras:
    print(f"[*] Scanning {cam.ip}:{cam.port} ({cam.vendor})...")
    result = scan_camera_basic(cam, config)
    print(f"    Status: {result.status.value}")
    if result.rtsp_path:
        print(f"    RTSP path: {result.rtsp_path}")
    if result.http_url:
        print(f"    HTTP URL: {result.http_url}")
    results.append(result)

print()
print("[*] Creating scan result...")
scan_result = ScanResult(
    scan_id="test_001",
    started_at=time.time(),
    cameras=results,
)
scan_result.finished_at = time.time()
scan_result.calculate_stats()

print(f"    Total: {scan_result.total_ips}")
print(f"    LIVE: {scan_result.accessible}")
print(f"    AUTH: {scan_result.auth_required}")
print(f"    CLOSED: {scan_result.closed}")

# Export
print()
print("[*] Exporting...")
export_json(scan_result, "data/reports")
export_csv(scan_result, "data/reports")
print(f"    [*] data/reports/*")

print()
print("[+] Pipeline test complete!")
