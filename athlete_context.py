from snapshot import build_morning_snapshot
from database import get_latest_xert_status


def build_athlete_context():
    snapshot = build_morning_snapshot()
    xert = get_latest_xert_status()

    today_checkin = snapshot.get("today_checkin")
    latest_checkin = snapshot.get("latest_checkin")
    checkin = today_checkin or latest_checkin

    context = {
        "snapshot": snapshot,
        "snapshot_percent": snapshot.get("snapshot_percent"),
        "snapshot_complete": snapshot.get("snapshot_percent") == 100,

        "weight": snapshot.get("weight"),
        "body_fat": snapshot.get("body_fat"),
        "muscle": snapshot.get("muscle"),
        "pwv": snapshot.get("pwv"),
        "systolic": snapshot.get("systolic"),
        "diastolic": snapshot.get("diastolic"),

        "checkin": checkin,
        "today_checkin": today_checkin,
        "latest_checkin": latest_checkin,

        "energy": None,
        "mood": None,
        "soreness": None,
        "lumen_score": None,
        "fat_burn_percent": None,
        "carb_burn_percent": None,

        "xert": xert,
        "xert_status": None,
        "xert_ftp": None,
        "xert_ltp": None,
        "xert_hie": None,
        "xert_pp": None,
        "xert_training_load": None,
        "xert_target_xss": None,
        "xert_wotd_type": None,
    }

    if checkin:
        context["energy"] = checkin.get("energy")
        context["mood"] = checkin.get("mood")
        context["soreness"] = checkin.get("soreness")
        context["lumen_score"] = checkin.get("lumen_score")
        context["fat_burn_percent"] = checkin.get("fat_burn_percent")
        context["carb_burn_percent"] = checkin.get("carb_burn_percent")

    if xert:
        context["xert_status"] = xert.get("status")
        context["xert_ftp"] = xert.get("ftp")
        context["xert_ltp"] = xert.get("ltp")
        context["xert_hie"] = xert.get("hie")
        context["xert_pp"] = xert.get("pp")
        context["xert_training_load"] = xert.get("tl_total")
        context["xert_target_xss"] = xert.get("target_xss_total")
        context["xert_wotd_type"] = xert.get("wotd_type")

    return context