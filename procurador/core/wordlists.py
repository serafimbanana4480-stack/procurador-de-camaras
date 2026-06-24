"""
Wordlists centralizadas do Procurador de Câmara.

- RTSP_PATHS_BY_VENDOR — paths RTSP por fabricante (65+)
- DEFAULT_CREDS — credenciais default genéricas e por fabricante (200+)
- HTTP_SNAPSHOT_PATHS — endpoints de snapshot HTTP
- HTTP_ADMIN_PATHS — endpoints de admin/login
- HTTP_PORTS — portas HTTP comuns
- RTSP_PORTS — portas RTSP (principais e alternativas)
- ONVIF_UNAUTH_ENDPOINTS — endpoints ONVIF potencialmente sem auth

Estas listas foram compiladas a partir de:
- Cameradar wordlist
- jeanphorn/wordlist
- SecLists Default-Credentials
- gardinal.net (vendor research)
- Pesquisa CVE 2024-2026
"""

from __future__ import annotations

# =====================================================================
# RTSP PATHS POR FABRICANTE
# =====================================================================

RTSP_PATHS_BY_VENDOR: dict[str, list[str]] = {
    "Hikvision": [
        "/Streaming/Channels/101",
        "/Streaming/Channels/102",
        "/Streaming/Channels/201",
        "/Streaming/Channels/202",
        "/Streaming/Channels/301",
        "/Streaming/Channels/401",
        "/Streaming/Channels/501",
        "/Streaming/Channels/601",
        "/Streaming/Channels/701",
        "/Streaming/Channels/801",
        "/Streaming/Channels/901",
        "/Streaming/Channels/1001",
        "/h264/ch1/main/av_stream",
        "/h264/ch1/sub/av_stream",
        "/h265/ch1/main/av_stream",
        "/mpeg4/ch1/main/av_stream",
        "/live",
        "/live/main",
        "/live/sub",
        "/11",
        "/ch1/main",
        "/ch1/sub",
        "/ch01.264",
    ],
    "Dahua": [
        "/cam/realmonitor?channel=1&subtype=0",
        "/cam/realmonitor?channel=1&subtype=1",
        "/cam/realmonitor?channel=1&subtype=2",
        "/cam/realmonitor?channel=2&subtype=0",
        "/cam/realmonitor?channel=2&subtype=1",
        "/live",
        "/live1",
        "/live2",
        "/ch1",
        "/ch1/main",
        "/ch1/sub",
        "/h264",
        "/mpeg4",
    ],
    "Axis": [
        "/axis-media/media.amp",
        "/axis-media/media.amp?videocodec=h264",
        "/axis-media/media.amp?videocodec=h264&resolution=1920x1080",
        "/axis-media/media.amp?videocodec=jpeg",
        "/mpeg4/media.amp",
        "/mpeg4/media.amp?videocodec=h264",
        "/live.sdp",
        "/mjpg/video.mjpg",
    ],
    "TP-Link": [
        "/stream1",
        "/stream2",
        "/live",
        "/live0",
        "/live1",
        "/video1",
        "/video/main",
        "/video/sub",
    ],
    "Reolink": [
        "/h264Preview_01_main",
        "/h264Preview_01_sub",
        "/h264Preview_02_main",
        "/h264Preview_02_sub",
        "/Preview_01_main",
        "/Preview_01_sub",
        "/live",
        "/live0",
        "/live.sdp",
    ],
    "Foscam": [
        "/videoMain",
        "/videoSub",
        "/11",
        "/12",
        "/13",
        "/h264",
        "/h264Main",
        "/h264Sub",
        "/mjpg",
        "/live",
        "/live/ch00_0",
        "/live/ch01_0",
    ],
    "Bosch": [
        "/video?inst=1&rec=0",
        "/video?inst=2&rec=0",
        "/video?inst=1&rec=1",
        "/rtspvideo",
        "/live.sdp",
        "/bosch/stabilized",
    ],
    "Hanwha": [
        "/profile1/media.smp",
        "/profile2/media.smp",
        "/profile3/media.smp",
        "/profile4/media.smp",
        "/media.smp",
    ],
    "Uniview": [
        "/unicast/c1/s0/live",
        "/unicast/c1/s1/live",
        "/unicast/c2/s0/live",
        "/unicast/c2/s1/live",
        "/live",
    ],
    "Vivotek": [
        "/live.sdp",
        "/live2.sdp",
        "/live3.sdp",
        "/h264.sdp",
        "/video1",
        "/video2",
        "/video3",
        "/mjpg1",
        "/mpeg4.sdp",
    ],
    "GeoVision": [
        "/CH001.sdp",
        "/CH002.sdp",
        "/CH003.sdp",
        "/CH004.sdp",
        "/live.sdp",
    ],
    "D-Link": [
        "/live.sdp",
        "/live1.sdp",
        "/live2.sdp",
        "/play1.sdp",
        "/video1",
        "/mjpeg",
        "/mjpeg/1",
    ],
    "Xiongmaitech": [
        "/11",
        "/ch01",
        "/live/main",
        "/live/sub",
        "/onvif/streaming/channels/101",
        "/onvif/streaming/channels/201",
    ],
    "Ezviz": [
        "/Streaming/tracks/101",
        "/Streaming/tracks/201",
        "/Streaming/tracks/301",
        "/h264/ch1/main/av_stream",
        "/live/main",
        "/live/sub",
    ],
    "GALAYOU": [
        "/live/ch00_0",
        "/live/ch00_1",
        "/live/main",
        "/live/sub",
        "/11",
        "/h264Preview_01_main",
    ],
    "HiSilicon": [
        "/11",
        "/ch01/main/av_stream",
        "/ch01/sub/av_stream",
        "/live",
        "/live/main",
    ],
    "Hipcam": [
        "/live/main",
        "/live/sub",
        "/videoMain",
        "/11",
    ],
    "Honeywell": [
        "/Streaming/tracks/101",
        "/Streaming/Channels/101",
        "/live",
        "/media/video1",
    ],
    "Pelco": [
        "/live1.sdp",
        "/live/main",
        "/Streaming/Channels/101",
    ],
    "Avigilon": [
        "/Streaming/Channels/101",
        "/Streaming/tracks/101",
        "/live/main",
    ],
    "Generic/Other": [
        "/live",
        "/live0",
        "/live1",
        "/live2",
        "/live.sdp",
        "/video",
        "/video1",
        "/video0",
        "/video2",
        "/h264",
        "/h264.sdp",
        "/mpeg4",
        "/mpeg4.sdp",
        "/mjpg",
        "/mjpg/video.mjpg",
        "/1",
        "/11",
        "/12",
        "/13",
        "/14",
        "/15",
        "/ch1",
        "/ch1/main",
        "/ch1/sub",
        "/ch2",
        "/main",
        "/sub",
        "/stream",
        "/stream1",
        "/stream2",
        "/cam1",
        "/cam2",
        "/channel1",
        "/channel2",
        "/av_stream",
        "/av_stream/ch1",
        "/Streaming/Channels/101",
        "/Streaming/tracks/101",
        "/onvif/streaming/channels/101",
        "/11.264",
        "/1.264",
        "/cgi-bin/stream.cgi",
    ],
}


def get_paths_for_vendor(vendor: str | None) -> list[str]:
    """Devolve paths RTSP para testar dado o fabricante.

    Args:
        vendor: Nome do fabricante (Hikvision, Dahua, ...) ou None.

    Returns:
        Lista de paths (começa com os específicos do fabricante, depois genéricos).
    """
    paths: list[str] = []
    if vendor:
        vendor_lower = vendor.lower()
        for key, vendor_paths in RTSP_PATHS_BY_VENDOR.items():
            if key == "Generic/Other":
                continue
            if key.lower() in vendor_lower or vendor_lower in key.lower():
                paths.extend(vendor_paths)
                break

    # Adiciona genéricos se ainda poucos
    generic = RTSP_PATHS_BY_VENDOR["Generic/Other"]
    if len(paths) < 5:
        paths.extend(generic)
    else:
        # Adiciona alguns genéricos no fim como fallback
        paths.extend(generic[:5])

    # Deduplica mantendo ordem
    seen: set[str] = set()
    deduped: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


# =====================================================================
# CREDENCIAIS DEFAULT (200+ combinações)
# =====================================================================

# Top 50 — genérico (responsável por ~80% dos acessos)
GENERIC_CREDS: list[tuple[str, str]] = [
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", ""),
    ("admin", "password"),
    ("root", "pass"),
    ("admin", "1234"),
    ("root", "root"),
    ("admin", "123456"),
    ("admin", "888888"),
    ("admin", "666666"),
    ("admin", "1111"),
    ("admin", "000000"),
    ("root", "admin"),
    ("Admin", "1234"),
    ("admin", "admin123"),
    ("service", "service"),
    ("root", ""),
    ("user", "user"),
    ("admin", "pass"),
    ("admin", "default"),
    ("admin", "123456789"),
    ("admin", "1111111"),
    ("Administrator", ""),
    ("admin", "admin1234"),
    ("root", "camera"),
    ("root", "system"),
    ("admin", "4321"),
    ("admin", "9999"),
    ("Admin", "12345"),
    ("admin", "password123"),
    ("user", "12345"),
    ("guest", "guest"),
    ("admin", "12345678"),
    ("admin", "1234567890"),
    ("admin", "qwerty"),
    ("admin", "letmein"),
    ("root", "12345"),
    ("admin", "server"),
    ("admin", "system"),
    ("admin", "manager"),
    ("supervisor", "supervisor"),
    ("admin", "changeme"),
    ("admin", "secret"),
    ("admin", "123"),
    ("admin", "master"),
    ("admin", "abc123"),
    ("admin", "test"),
    ("admin", "root"),
    ("user", "pass"),
    ("demo", "demo"),
    ("test", "test"),
]

# Específicas por fabricante
VENDOR_CREDS: dict[str, list[tuple[str, str]]] = {
    "Hikvision": [
        ("admin", "12345"),
        ("admin", "1234"),
        ("admin", "hik12345"),
        ("admin", "hik1234"),
        ("admin", "abcd1234"),
        ("admin", "admin"),
    ],
    "Dahua": [
        ("admin", "admin"),
        ("admin", ""),
        ("admin", "dahua"),
        ("admin", "dahua123"),
        ("888888", "888888"),
        ("666666", "666666"),
    ],
    "Axis": [
        ("root", "pass"),
        ("admin", "admin"),
    ],
    "TP-Link": [
        ("admin", "admin"),
        ("admin", "password"),
    ],
    "Reolink": [
        ("admin", "admin"),
        ("admin", ""),
    ],
    "Foscam": [
        ("admin", ""),
        ("admin", "admin"),
        ("admin", "foscam"),
        ("admin", "1234"),
    ],
    "Vivotek": [
        ("root", "pass"),
    ],
    "Bosch": [
        ("admin", "admin"),
    ],
    "Hanwha": [
        ("admin", "4321"),
    ],
    "Uniview": [
        ("admin", "123456"),
    ],
    "Mobotix": [
        ("admin", "meinsm"),
    ],
    "FLIR": [
        ("admin", "fliradmin"),
    ],
    "Canon": [
        ("root", "camera"),
    ],
    "JVC": [
        ("admin", "jvc"),
    ],
    "IQinVision": [
        ("root", "system"),
    ],
    "ACTi": [
        ("Admin", "12345"),
    ],
    "American Dynamics": [
        ("admin", "9999"),
    ],
    "Visiotech": [
        ("admin", "1111"),
    ],
    "Avigilon": [
        ("admin", "admin"),
        ("admin", ""),
    ],
    "Pelco": [
        ("admin", "admin"),
    ],
}


def get_creds_for_vendor(vendor: str | None, max_n: int = 200) -> list[tuple[str, str]]:
    """Devolve lista de credenciais para testar.

    Args:
        vendor: Nome do fabricante (opcional).
        max_n: Limite total de combinações a devolver.

    Returns:
        Lista de tuplas (user, password) — começa com vendor-specific depois genérico.
    """
    creds: list[tuple[str, str]] = []
    if vendor:
        vendor_lower = vendor.lower()
        for key, vendor_creds in VENDOR_CREDS.items():
            if key.lower() in vendor_lower or vendor_lower in key.lower():
                creds.extend(vendor_creds)
                break

    # Genérico
    creds.extend(GENERIC_CREDS)

    # Deduplica mantendo ordem
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for c in creds:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped[:max_n]


# =====================================================================
# HTTP PATHS
# =====================================================================

HTTP_SNAPSHOT_PATHS: list[str] = [
    "/snapshot.jpg",
    "/snapshot.jpeg",
    "/snapshot.png",
    "/image.jpg",
    "/image.jpeg",
    "/img/snapshot.jpg",
    "/cgi-bin/snapshot.cgi",
    "/cgi-bin/snapshot",
    "/cgi-bin/image.jpg",
    "/cgi-bin/jpg/image.jpg",
    "/cgi-bin/jpg/image.cgi",
    "/cgi-bin/video.jpg",
    "/cgi-bin/viewer/snapshot.jpg",
    "/onvif/snapshot",
    "/onvif-http/snapshot",
    "/axis-cgi/jpg/image.cgi",
    "/axis-cgi/mjpg/video.cgi",
    "/mjpg/video.mjpg",
    "/img/video.jpg",
    "/tmpfs/snap.jpg",
    "/tmpfs/auto.jpg",
    "/snap.jpg",
    "/Streaming/tracks/101",
    "/Streaming/channels/1/picture",
    "/ISAPI/Streaming/channels/1/picture",
    "/ISAPI/Streaming/tracks/101/picture",
    "/web/tmpfs/snap.jpg",
    "/cgi-bin/viewer/getimage.cgi",
    "/cgi-bin/camera/snapshot",
    "/cgi-bin/camera/preset",
    "/api/v1/snapshot",
    "/api/snapshot",
    "/api/camera/snapshot",
    "/0/image.jpg",
    "/1/image.jpg",
]

HTTP_ADMIN_PATHS: list[str] = [
    "/",
    "/login",
    "/login.htm",
    "/login.html",
    "/login.asp",
    "/admin",
    "/admin/",
    "/admin/index.html",
    "/admin/login",
    "/admin/login.html",
    "/cgi-bin/login",
    "/cgi-bin/login.cgi",
    "/web/login",
    "/web/",
    "/web/index.html",
    "/index.html",
    "/index.htm",
    "/user_login.html",
    "/doc/index.html",
    "/view/index.html",
    "/doc/login.html",
    "/login.cgi",
    "/login.html",
    "/accounts/login/",
    "/signin",
    "/api/login",
    "/api/v1/login",
]

HTTP_DEVICE_INFO_PATHS: list[str] = [
    "/cgi-bin/status",
    "/cgi-bin/get_status.cgi",
    "/status",
    "/status.html",
    "/info",
    "/cgi-bin/deviceinfo",
    "/cgi-bin/get_device_info.cgi",
    "/api/get_status",
    "/api/v1/status",
    "/api/system/status",
    "/system/deviceInfo",
    "/ISAPI/System/deviceInfo",
    "/ISAPI/System/status",
]

HTTP_PORTS: list[int] = [80, 443, 8080, 8000, 8008, 8081, 8443, 2020]


# =====================================================================
# RTSP PORTS
# =====================================================================

RTSP_PORTS: list[int] = [554, 8554, 5554, 37777, 7447, 7070, 1935, 1024, 10000]


# =====================================================================
# ONVIF endpoints
# =====================================================================

ONVIF_UNAUTH_ENDPOINTS: list[str] = [
    "/onvif/device_service",
    "/onvif/media_service",
    "/onvif/events_service",
    "/onvif/analytics_service",
    "/onvif/ptz_service",
    "/onvif/imaging_service",
    "/onvif/recording_service",
    "/onvif/replay_service",
    "/onvif/search_service",
    "/onvif/notification_service",
    "/onvif/accesscontrol_service",
    "/onvif/access_rules_service",
    "/onvif/door_control_service",
    "/onvif/advanced_security_service",
    "/onvif/credential_service",
    "/onvif/schedule_service",
    "/onvif/receiver_service",
    "/onvif/snapshot_service",
    "/onvif/video_analytics_service",
    "/onvif/rule_engine_service",
    "/onvif/analytics_module_service",
    "/onvif/action_engine_service",
    "/onvif/media2_service",
    "/onvif/display_service",
    "/onvif/receiver_service",
    "/onvif/thermal_service",
    "/onvif/screen_service",
    "/onvif/uplink_service",
    "/onvif/audio_service",
    "/onvif/metadata_service",
    "/onvif/snapshot",
]

ONVIF_PORTS: list[int] = [80, 8080, 2020, 8000]


# =====================================================================
# CVE database
# =====================================================================

CVE_DATABASE: dict[str, dict] = {
    "Hikvision": {
        "models": ["*"],
        "cves": ["CVE-2021-36260"],
        "ports": [80, 443, 8080],
        "cve_2021_36260": True,
    },
    "Dahua": {
        "models": ["*"],
        "cves": ["CVE-2021-33044"],
        "ports": [80, 443, 8080],
    },
    "Ezviz": {
        "models": ["CS-CV246"],
        "cves": ["CVE-2024-42531"],
        "ports": [554, 8554],
        "cve_2024_42531": True,
    },
    "GALAYOU": {
        "models": ["G2"],
        "cves": ["CVE-2025-9983"],
        "ports": [554],
        "cve_2025_9983": True,
    },
    "Vivotek": {
        "models": ["IP7137"],
        "cves": ["CVE-2025-66049"],
        "ports": [8554],
        "cve_2025_66049": True,
    },
    "Xiongmaitech": {
        "models": ["*"],
        "cves": ["CVE-2025-65856"],
        "ports": [80, 8080],
        "cve_2025_65856": True,
    },
    "HiSilicon": {
        "models": ["*"],
        "cves": ["CVE-2023-50401"],
        "ports": [554, 80],
    },
    "Axis": {
        "models": ["*"],
        "cves": ["CVE-2018-10660"],
        "ports": [80],
    },
    "TP-Link": {
        "models": ["Tapo", "NC"],
        "cves": ["CVE-2021-4045"],
        "ports": [554, 2020],
    },
}


# =====================================================================
# Telnet creds
# =====================================================================

TELNET_CREDS: list[tuple[str, str]] = [
    ("root", "root"),
    ("root", "admin"),
    ("root", "xc3511"),
    ("root", "12345"),
    ("root", "password"),
    ("root", "toor"),
    ("root", ""),
    ("admin", "admin"),
    ("admin", "12345"),
    ("admin", "password"),
    ("default", "default"),
    ("user", "user"),
]
