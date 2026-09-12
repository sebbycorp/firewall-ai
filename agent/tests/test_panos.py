import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from panos import api_url, parse_system_info

SUCCESS_XML = """
<response status="success">
  <result>
    <system>
      <hostname>PA-VM-STUDENT</hostname>
      <ip-address>172.16.10.222</ip-address>
      <sw-version>11.1.4-h7</sw-version>
      <model>PA-VM</model>
      <serial>015351000000000</serial>
    </system>
  </result>
</response>
"""

ERROR_XML = """
<response status="error">
  <msg>
    <line>Invalid credential</line>
  </msg>
</response>
"""


def test_parses_show_system_info() -> None:
    info = parse_system_info(SUCCESS_XML)
    assert info.ok is True
    assert info.hostname == "PA-VM-STUDENT"
    assert info.sw_version == "11.1.4-h7"
    assert info.mgmt_ip == "172.16.10.222"
    assert info.serial == "015351000000000"
    assert info.model == "PA-VM"
    payload = info.as_heartbeat("jane@sheridancollege.ca")
    assert payload["student_id"] == "jane@sheridancollege.ca"
    assert payload["ok"] is True


def test_parses_api_error() -> None:
    info = parse_system_info(ERROR_XML)
    assert info.ok is False
    assert "Invalid credential" in (info.error or "")


def test_invalid_xml() -> None:
    info = parse_system_info("<not-closed")
    assert info.ok is False
    assert info.error


def test_api_url_includes_op_cmd_and_key() -> None:
    url = api_url("https://172.16.10.222", "example-key")
    assert url.startswith("https://172.16.10.222/api/?")
    assert "type=op" in url
    assert "key=example-key" in url
    assert "show" in url
