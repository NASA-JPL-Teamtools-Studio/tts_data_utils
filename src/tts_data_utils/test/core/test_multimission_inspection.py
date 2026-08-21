"""Human-inspectable PowerTable tests for multimission AMPCS frame types.

Each test class generates a full HtmlCompiler document that a developer must
open in a browser and verify before the suite will pass (via the .sha256
certification mechanism in inspection_utils.py).

To certify after visual inspection:
    python src/tts_data_utils/test/certify.py
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tts_data_utils.multimission.ampcs.eha import AmpcsEhaFrame
from tts_data_utils.multimission.ampcs.evr import AmpcsEvrFrame
from tts_data_utils.test.core.inspection_utils import check_inspection_hash


_EHA_PATH = Path(__file__).parent / "test_files" / "ampcs_eha_inspection.html"
_EVR_PATH = Path(__file__).parent / "test_files" / "ampcs_evr_inspection.html"

_T0 = datetime(2026, 3, 15, 10, 0, 0)


_EHA_DATA = [
    {"scet": _T0 + timedelta(seconds=0),  "ert": _T0 + timedelta(seconds=2),
     "channelId": "FSW-0001", "name": "battery_voltage",
     "module": "EPS", "type": "FSW",
     "dn": 4095, "eu": 28.4, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "GREEN"},
    {"scet": _T0 + timedelta(seconds=5),  "ert": _T0 + timedelta(seconds=7),
     "channelId": "FSW-0002", "name": "solar_array_current",
     "module": "EPS", "type": "FSW",
     "dn": 3820, "eu": 3.21, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "GREEN"},
    {"scet": _T0 + timedelta(seconds=10), "ert": _T0 + timedelta(seconds=12),
     "channelId": "FSW-0003", "name": "bus_voltage",
     "module": "EPS", "type": "FSW",
     "dn": 3210, "eu": 22.1, "status": "TIMEOUT",
     "dnAlarmState": "YELLOW", "euAlarmState": "YELLOW"},
    {"scet": _T0 + timedelta(seconds=15), "ert": _T0 + timedelta(seconds=17),
     "channelId": "FSW-0004", "name": "cpu_temperature",
     "module": "CDH", "type": "FSW",
     "dn": 2730, "eu": 71.3, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "GREEN"},
    {"scet": _T0 + timedelta(seconds=20), "ert": _T0 + timedelta(seconds=22),
     "channelId": "FSW-0005", "name": "heater_power",
     "module": "THERMAL", "type": "FSW",
     "dn": 500, "eu": 0.49, "status": "OK",
     "dnAlarmState": "RED", "euAlarmState": "RED"},
    {"scet": _T0 + timedelta(seconds=25), "ert": _T0 + timedelta(seconds=27),
     "channelId": "FSW-0006", "name": "gyro_rate_x",
     "module": "ADCS", "type": "FSW",
     "dn": 32767, "eu": 0.003, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "GREEN"},
    {"scet": _T0 + timedelta(seconds=30), "ert": _T0 + timedelta(seconds=32),
     "channelId": "FSW-0007", "name": "downlink_rate",
     "module": "RF", "type": "FSW",
     "dn": 1024, "eu": 100.0, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "YELLOW"},
    {"scet": _T0 + timedelta(seconds=35), "ert": _T0 + timedelta(seconds=37),
     "channelId": "FSW-0008", "name": "reaction_wheel_speed",
     "module": "ADCS", "type": "FSW",
     "dn": 100, "eu": 980.0, "status": "OK",
     "dnAlarmState": "GREEN", "euAlarmState": "GREEN"},
]

_EVR_DATA = [
    {"scet": _T0 + timedelta(seconds=0),  "ert": _T0 + timedelta(seconds=2),
     "level": "DIAGNOSTIC", "eventId": 1001, "name": "EPS_INIT",
     "module": "EPS", "vcid": 0, "dssId": 14,
     "message": "EPS subsystem initialized successfully.",
     "sclk": 712345600.0},
    {"scet": _T0 + timedelta(seconds=5),  "ert": _T0 + timedelta(seconds=7),
     "level": "COMMAND", "eventId": 2001, "name": "CMD_RECV",
     "module": "CDH", "vcid": 0, "dssId": 14,
     "message": "Command 0xA3 received and accepted: HEATER_ON.",
     "sclk": 712345605.0},
    {"scet": _T0 + timedelta(seconds=10), "ert": _T0 + timedelta(seconds=12),
     "level": "ACTIVITY_LO", "eventId": 3001, "name": "DOWNLINK_START",
     "module": "RF", "vcid": 1, "dssId": 14,
     "message": "Downlink session started at 100 kbps.",
     "sclk": 712345610.0},
    {"scet": _T0 + timedelta(seconds=15), "ert": _T0 + timedelta(seconds=17),
     "level": "ACTIVITY_HI", "eventId": 3002, "name": "PLAYBACK_START",
     "module": "CDH", "vcid": 2, "dssId": 14,
     "message": "Recorder playback started: partition A, 2.1 GB queued.",
     "sclk": 712345615.0},
    {"scet": _T0 + timedelta(seconds=20), "ert": _T0 + timedelta(seconds=22),
     "level": "WARNING_LO", "eventId": 4001, "name": "BUS_VOLT_LOW",
     "module": "EPS", "vcid": 0, "dssId": 14,
     "message": "Bus voltage 22.1V below caution limit of 24.0V.",
     "sclk": 712345620.0},
    {"scet": _T0 + timedelta(seconds=25), "ert": _T0 + timedelta(seconds=27),
     "level": "WARNING_HI", "eventId": 4002, "name": "HEATER_OVERCURRENT",
     "module": "THERMAL", "vcid": 0, "dssId": 14,
     "message": "Heater power 0.49W exceeds design limit of 0.45W. Monitor closely.",
     "sclk": 712345625.0},
    {"scet": _T0 + timedelta(seconds=30), "ert": _T0 + timedelta(seconds=32),
     "level": "FATAL", "eventId": 5001, "name": "CDH_REBOOT",
     "module": "CDH", "vcid": 0, "dssId": 14,
     "message": "CDH watchdog timeout. Autonomous reboot initiated.",
     "sclk": 712345630.0},
    {"scet": _T0 + timedelta(seconds=42), "ert": _T0 + timedelta(seconds=44),
     "level": "ACTIVITY_LO", "eventId": 3003, "name": "CDH_RECOVERED",
     "module": "CDH", "vcid": 0, "dssId": 14,
     "message": "CDH reboot complete. All subsystems nominal.",
     "sclk": 712345642.0},
]


@pytest.mark.human_review
@pytest.mark.unreviewed_ai_generated_test
class TestAmpcsEhaInspection:
    """Writes a full HtmlCompiler artifact for AmpcsEhaFrame inspection.

    Open the file printed to stdout after running this test to verify:
    - RED rows for channels in RED alarm state (FSW-0005 heater_power)
    - YELLOW rows for channels in YELLOW alarm state (FSW-0003 bus_voltage,
      FSW-0007 downlink_rate)
    - WHITE/alternating rows for nominal channels
    - Bold EU values on alarmed rows
    - Sortable column headers (click to sort by channelId, eu, alarm state, etc.)
    - Filterable columns (type in the filter boxes below headers)
    - Superheader showing the time range
    """

    def test_write_eha_inspection_html(self):
        from tts_html_utils.core.compiler import HtmlCompiler

        _EHA_PATH.parent.mkdir(parents=True, exist_ok=True)

        frame = AmpcsEhaFrame(_EHA_DATA, coerce=False, validate=False)

        table = frame.power_table(
            superheader="EHA Latest — DemoSat  2026-075T10:00:00 SCET",
            columns=["scet", "channelId", "name", "module", "dn", "eu",
                     "status", "dnAlarmState", "euAlarmState"],
            add_sorting="local",
            add_filters="local",
        )

        compiler = HtmlCompiler(
            "AmpcsEhaFrame PowerTable Inspection (ticket #12 / multimission)"
        )
        compiler.add_body_component(table)
        compiler.render_to_file(_EHA_PATH)

        print(
            f"\n\n  Human-inspectable output → open in browser:\n"
            f"  {_EHA_PATH.resolve()}\n"
        )

        assert _EHA_PATH.exists()
        assert _EHA_PATH.stat().st_size > 0
        content = _EHA_PATH.read_text()
        assert "FSW-0005" in content
        assert "FFCCCC" in content
        assert "FFF3CC" in content

        check_inspection_hash(_EHA_PATH)


@pytest.mark.human_review
@pytest.mark.unreviewed_ai_generated_test
class TestAmpcsEvrInspection:
    """Writes a full HtmlCompiler artifact for AmpcsEvrFrame inspection.

    Open the file printed to stdout after running this test to verify:
    - Deep red row for FATAL CDH_REBOOT event
    - Red/orange rows for WARNING_HI and WARNING_LO events
    - Yellow rows for ACTIVITY events
    - Blue row for COMMAND event
    - Unstyled DIAGNOSTIC row
    - Bold level cell on WARNING and FATAL rows
    - Sortable and filterable columns
    """

    def test_write_evr_inspection_html(self):
        from tts_html_utils.core.compiler import HtmlCompiler

        _EVR_PATH.parent.mkdir(parents=True, exist_ok=True)

        frame = AmpcsEvrFrame(_EVR_DATA, coerce=False, validate=False)

        table = frame.power_table(
            superheader="EVR Log — DemoSat  2026-075T10:00:00 to 10:00:42 SCET",
            columns=["scet", "level", "name", "module", "message"],
            add_sorting="local",
            add_filters="local",
        )

        compiler = HtmlCompiler(
            "AmpcsEvrFrame PowerTable Inspection (ticket #12 / multimission)"
        )
        compiler.add_body_component(table)
        compiler.render_to_file(_EVR_PATH)

        print(
            f"\n\n  Human-inspectable output → open in browser:\n"
            f"  {_EVR_PATH.resolve()}\n"
        )

        assert _EVR_PATH.exists()
        assert _EVR_PATH.stat().st_size > 0
        content = _EVR_PATH.read_text()
        assert "CDH_REBOOT" in content
        assert "FF5E66" in content
        assert "WARNING_HI" in content

        check_inspection_hash(_EVR_PATH)
