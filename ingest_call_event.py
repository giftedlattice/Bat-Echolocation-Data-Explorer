import sqlite3
import pandas as pd

COND_MAP = {"L1": "L", "R": "R1", "R2D1": "R2"}

CSV_TO_CALL_EVENT = {
    "pairID": "pair_id",
    "pairID_binned": "pair_id_binned",
    "pairID_binned_all": "pair_id_binned_all",

    "time": "time_s",
    "good_call": "good_call",
    "behind": "behind",

    "x_call": "x_call",
    "y_call": "y_call",
    "z_call": "z_call",

    "x": "x",
    "y": "y",
    "z": "z",
    "s": "s",
    "first_trip_s": "first_trip_s",
    "trip": "trip",
    "lon": "lon",
    "long_angle_to_target": "long_angle_to_target",
    "lon_angle_to_target": "lon_angle_to_target",
    "lon_angle_to_target_medfiltered": "lon_angle_to_target_medfiltered",

    "norm_hd_x": "norm_hd_x",
    "norm_hd_y": "norm_hd_y",
    "norm_hd_z": "norm_hd_z",
    "norm_hd_2d_x": "norm_hd_2d_x",
    "norm_hd_2d_y": "norm_hd_2d_y",

    "norm_beam_aim_vec_x": "norm_beam_aim_vec_x",
    "norm_beam_aim_vec_y": "norm_beam_aim_vec_y",
    "norm_beam_aim_vec_z": "norm_beam_aim_vec_z",
    "norm_beam_aim_vec_2d_x": "norm_beam_aim_vec_2d_x",
    "norm_beam_aim_vec_2d_y": "norm_beam_aim_vec_2d_y",

    "lon_beam": "lon_beam",
    "lat_beam": "lat_beam",
    "lon_head": "lon_head",
    "lat_head": "lat_head",
    "lon_aim_to_head": "lon_aim_to_head",
    "lat_aim_to_head": "lat_aim_to_head",

    "inter_click_interval": "inter_click_interval",
    "inter_click_distance_3D": "inter_click_distance_3D",
    "inter_click_distance_2D": "inter_click_distance_2D",

    "pair_click_angle_lon": "pair_click_angle_lon",
    "pair_click_angle_lat": "pair_click_angle_lat",

    "inter_click_distance_3D_bcfiltered": "inter_click_distance_3D_bcfiltered",
    "inter_click_distance_2D_bcfiltered": "inter_click_distance_2D_bcfiltered",
    "pair_click_angle_lon_bcfiltered": "pair_click_angle_lon_bcfiltered",
    "pair_click_angle_lat_bcfiltered": "pair_click_angle_lat_bcfiltered",
    "lon_aim_to_head_bcfiltered": "lon_aim_to_head_bcfiltered",
    "lat_aim_to_head_bcfiltered": "lat_aim_to_head_bcfiltered",
    "inter_click_interval_bcfiltered": "inter_click_interval_bcfiltered",
    "lon_beam_bcfiltered": "lon_beam_bcfiltered",
    "lat_beam_bcfiltered": "lat_beam_bcfiltered",
    "lon_head_bcfiltered": "lon_head_bcfiltered",
    "lat_head_bcfiltered": "lat_head_bcfiltered",

    "HD-SD_rad": "hd_sd_rad",
    "HD-SD": "hd_sd_deg",
    "HD-SD_medianfiltered_rad": "hd_sd_medianfiltered_rad",
    "HD-SD_medianfiltered": "hd_sd_medianfiltered_deg",
    "HD-SD_bcfiltered": "hd_sd_bcfiltered",

    "binned_s": "binned_s",
    "binned_s_all": "binned_s_all",
}

def yyyymmdd_to_iso(d) -> str:
    d = str(int(float(d)))
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"

def get_or_create_id(cur, table, key_col, key_val, extra_cols=None):
    extra_cols = extra_cols or {}
    cur.execute(f"SELECT {table}_id FROM {table} WHERE {key_col} = ?", (key_val,))
    row = cur.fetchone()
    if row:
        return row[0]
    cols = [key_col] + list(extra_cols.keys())
    vals = [key_val] + list(extra_cols.values())
    placeholders = ",".join(["?"] * len(vals))
    cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
    return cur.lastrowid

def ingest_csv(db_path: str, csv_path: str, processing_run_id=None, train_or_test=None):
    df = pd.read_csv(csv_path)

    required = {"bat", "date", "cond", "trial", "time"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["cond"] = df["cond"].astype(str).replace(COND_MAP)
    df["session_date"] = df["date"].apply(yyyymmdd_to_iso)
    df["trial"] = pd.to_numeric(df["trial"], errors="coerce").astype("Int64")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    total = 0

    for (bat_code, session_date, cond_code, trial_num), g in df.groupby(["bat", "session_date", "cond", "trial"], dropna=False):
        if pd.isna(trial_num):
            continue

        bat_id = get_or_create_id(cur, "bat", "bat_code", str(bat_code))
        session_id = get_or_create_id(cur, "session", "session_date", str(session_date))
        condition_id = get_or_create_id(cur, "condition", "cond_code", str(cond_code))

        cur.execute(
            "SELECT trial_id FROM trial WHERE session_id=? AND bat_id=? AND trial_num=? AND condition_id=?",
            (session_id, bat_id, int(trial_num), condition_id),
        )
        row = cur.fetchone()
        if row:
            trial_id = row[0]
        else:
            cur.execute(
                "INSERT INTO trial (session_id, bat_id, condition_id, trial_num, train_or_test, processing_run_id) VALUES (?,?,?,?,?,?)",
                (session_id, bat_id, condition_id, int(trial_num), train_or_test, processing_run_id),
            )
            trial_id = cur.lastrowid

        gg = g.sort_values("time").reset_index(drop=True).copy()
        gg["call_num"] = (gg.index + 1).astype(int)

        out = pd.DataFrame({"trial_id": trial_id, "call_num": gg["call_num"]})
        for src, dst in CSV_TO_CALL_EVENT.items():
            if src in gg.columns:
                out[dst] = gg[src]

        cols_sql = ",".join(out.columns)
        placeholders = ",".join(["?"] * len(out.columns))
        sql = f"INSERT OR IGNORE INTO call_event ({cols_sql}) VALUES ({placeholders})"

        cur.executemany(sql, out.itertuples(index=False, name=None))
        total += cur.rowcount

    conn.commit()
    conn.close()
    print(f"Inserted ~{total} rows into call_event from {csv_path}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--csv", required=True)
    p.add_argument("--processing_run_id", type=int, default=None)
    p.add_argument("--train_or_test", default=None)
    args = p.parse_args()
    ingest_csv(args.db, args.csv, args.processing_run_id, args.train_or_test)