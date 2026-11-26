from check_links import legistar_meeting_link_warnings

G = "920296E4-80BE-4CA2-A78F-32C5EFCF78AF"


def test_legid_meeting_link_warns():
    url = f"https://sanjose.legistar.com/MeetingDetail.aspx?LEGID=8126&GID=317&G={G}"
    assert legistar_meeting_link_warnings(url)


def test_id_guid_meeting_link_passes():
    url = f"https://sanjose.legistar.com/MeetingDetail.aspx?ID=1427104&GUID=66FA99F3-7A7A-4CC3-AF10-7E28B31FC823&G={G}"
    assert legistar_meeting_link_warnings(url) == []


def test_other_links_ignored():
    assert legistar_meeting_link_warnings("https://sanjose.legistar.com/Calendar.aspx") == []
