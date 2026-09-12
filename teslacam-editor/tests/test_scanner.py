from teslacam_editor import scanner


def test_scan_finds_all_kinds(teslacam_root):
    events = scanner.scan(str(teslacam_root))
    kinds = sorted(e.kind for e in events)
    assert kinds == ["RecentClips", "RecentClips", "SavedClips", "SentryClips"]
    # newest first
    assert [e.kind for e in events][0] == "RecentClips"


def test_saved_event_metadata(teslacam_root):
    events = {e.kind: e for e in scanner.scan(str(teslacam_root)) if e.kind != "RecentClips"}
    saved = events["SavedClips"]
    assert saved.segment_count == 3
    assert saved.cameras == ["front", "back", "left_repeater", "right_repeater", "left_pillar", "right_pillar"]
    assert saved.reason_label == "Honk"
    assert saved.city == "Testville"
    assert abs(saved.lat - 37.3861) < 1e-6
    assert saved.trigger_camera == "left_repeater"
    sentry = events["SentryClips"]
    assert sentry.reason_label == "Sentry: object detected"
    assert sentry.cameras == ["front", "back", "left_repeater", "right_repeater"]
    # the second segment is missing its rear camera file
    assert "back" not in sentry.segments[1].files


def test_recent_clips_grouped_by_gap(teslacam_root):
    recent = [e for e in scanner.scan(str(teslacam_root)) if e.kind == "RecentClips"]
    counts = sorted(e.segment_count for e in recent)
    assert counts == [1, 2]
    assert all(e.title.startswith("Drive") for e in recent)


def test_resolve_durations_and_timeline(teslacam_root):
    saved = [e for e in scanner.scan(str(teslacam_root)) if e.kind == "SavedClips"][0]
    assert saved.duration == 180.0  # placeholder before probing
    scanner.resolve_durations(saved)
    assert 8.5 < saved.duration < 9.5
    seg, off = scanner.event_time_to_segment(saved, 4.0)
    assert seg is saved.segments[1]
    assert abs(off - 1.0) < 0.1
    # trigger (12:00:00) is 120 s of wall clock after the first segment, clamped to the timeline
    assert saved.trigger_offset == saved.duration


def test_root_normalisation_and_single_folder(teslacam_root):
    usb = teslacam_root.parent
    assert len(scanner.scan(str(usb))) == 4
    only_saved = scanner.scan(str(teslacam_root / "SavedClips"))
    assert len(only_saved) == 1 and only_saved[0].kind == "SavedClips"
    single = scanner.scan(str(teslacam_root / "SavedClips" / "2024-05-01_12-00-00"))
    assert len(single) == 1 and single[0].segment_count == 3


def test_directory_browser(teslacam_root):
    listing = scanner.list_directory(str(teslacam_root))
    names = {d["name"] for d in listing["dirs"]}
    assert {"SavedClips", "SentryClips", "RecentClips"} <= names
    assert listing["is_teslacam"] is True
    roots = scanner.list_directory(None)
    assert roots["dirs"]
