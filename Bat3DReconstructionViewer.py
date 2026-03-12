# Bat3DReconstructionViewer.py
# 3-column 3D viewer: Audio | Video | Combined
# Robust to missing *_z vector columns and NULL/None values in DB.

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class Bat3DReconstructionViewer(tk.Tk):
    """
    3-column 3D viewer:
      [Audio]    [Video]    [Combined]
    Uses call_event for call points and beam/head vectors.
    If a trajectory_frame table exists, uses it for full trajectory in Video + Combined.
    Otherwise falls back to call_event x/y/z as trajectory-at-call-times.

    Robust fixes:
      - Handles missing norm_beam_aim_vec_z / norm_hd_z columns
      - Coerces vector columns to numeric
      - Drops rows with NaN/None before quiver
    """

    def __init__(self, db_path: str):
        super().__init__()
        self.title("Bat 3D Reconstruction Viewer — Audio | Video | Combined")
        self.geometry("1450x820")

        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA foreign_keys = ON;")

        # Cache schema info
        self.call_event_cols = self._get_table_columns("call_event")
        self.has_traj_frames = self._table_exists("trajectory_frame")

        # State
        self.bat_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.cond_var = tk.StringVar(value="(All)")
        self.trip_var = tk.StringVar(value="(All)")
        self.good_only_var = tk.BooleanVar(value=False)
        self.front_only_var = tk.BooleanVar(value=False)

        self.show_beam_var = tk.BooleanVar(value=True)
        self.show_head_var = tk.BooleanVar(value=False)

        self.trials_df = pd.DataFrame()
        self.current_trial_idx = 0

        self.calls_df = pd.DataFrame()
        self.traj_df = pd.DataFrame()
        self.current_call_idx = 0

        # UI
        self._build_ui()
        self._load_bats()

    # ---------------- UI ----------------

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Bat:").pack(side=tk.LEFT)
        self.bat_cb = ttk.Combobox(top, textvariable=self.bat_var, state="readonly", width=12)
        self.bat_cb.pack(side=tk.LEFT, padx=(6, 14))
        self.bat_cb.bind("<<ComboboxSelected>>", self._on_bat_changed)

        ttk.Label(top, text="Date:").pack(side=tk.LEFT)
        self.date_cb = ttk.Combobox(top, textvariable=self.date_var, state="readonly", width=12)
        self.date_cb.pack(side=tk.LEFT, padx=(6, 14))
        self.date_cb.bind("<<ComboboxSelected>>", self._on_date_changed)

        ttk.Label(top, text="Cond:").pack(side=tk.LEFT)
        self.cond_cb = ttk.Combobox(top, textvariable=self.cond_var, state="readonly", width=10)
        self.cond_cb.pack(side=tk.LEFT, padx=(6, 14))
        self.cond_cb.bind("<<ComboboxSelected>>", lambda e: self._load_trials_for_bat_date())

        ttk.Label(top, text="Trip:").pack(side=tk.LEFT)
        self.trip_cb = ttk.Combobox(top, textvariable=self.trip_var, state="readonly", width=8)
        self.trip_cb.pack(side=tk.LEFT, padx=(6, 14))
        self.trip_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_trial())

        ttk.Checkbutton(top, text="good only", variable=self.good_only_var, command=self._refresh_trial).pack(
            side=tk.LEFT, padx=(10, 4)
        )
        ttk.Checkbutton(top, text="front only (behind=0)", variable=self.front_only_var, command=self._refresh_trial).pack(
            side=tk.LEFT, padx=(10, 4)
        )

        ttk.Separator(top, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Checkbutton(top, text="show beam vectors", variable=self.show_beam_var, command=self._plot_all).pack(
            side=tk.LEFT, padx=(6, 4)
        )
        ttk.Checkbutton(top, text="show head vectors", variable=self.show_head_var, command=self._plot_all).pack(
            side=tk.LEFT, padx=(6, 4)
        )

        self.info_label = ttk.Label(top, text="")
        self.info_label.pack(side=tk.LEFT, padx=(12, 0))

        mid = ttk.Frame(self, padding=10)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Left: trials list + call navigation
        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Trials").pack(anchor="w")
        self.trial_list = tk.Listbox(left, height=26, width=42)
        self.trial_list.pack(side=tk.TOP, fill=tk.Y, pady=(6, 8))
        self.trial_list.bind("<<ListboxSelect>>", self._on_trial_selected)

        btns = ttk.Frame(left)
        btns.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(btns, text="Prev trial", command=self._prev_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(btns, text="Next trial", command=self._next_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        ttk.Separator(left, orient="horizontal").pack(fill=tk.X, pady=10)

        ttk.Label(left, text="Call index").pack(anchor="w")
        self.call_scale = ttk.Scale(left, from_=0, to=0, orient="horizontal", command=self._on_call_scale)
        self.call_scale.pack(fill=tk.X)
        self.call_label = ttk.Label(left, text="Call: - / -")
        self.call_label.pack(anchor="w", pady=(6, 0))

        callbtns = ttk.Frame(left)
        callbtns.pack(side=tk.TOP, fill=tk.X, pady=(8, 0))
        ttk.Button(callbtns, text="Prev call", command=self._prev_call).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(callbtns, text="Next call", command=self._next_call).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        # Right: 3-column plots
        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.fig = plt.figure(figsize=(12, 6))
        self.ax_audio = self.fig.add_subplot(131, projection="3d")
        self.ax_video = self.fig.add_subplot(132, projection="3d")
        self.ax_comb = self.fig.add_subplot(133, projection="3d")

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------------- DB helpers ----------------

    def _table_exists(self, table_name: str) -> bool:
        q = "SELECT name FROM sqlite_master WHERE type='table' AND name=?;"
        return pd.read_sql_query(q, self.con, params=(table_name,)).shape[0] > 0

    def _get_table_columns(self, table_name: str) -> set:
        if not self._table_exists(table_name):
            return set()
        cols = pd.read_sql_query(f"PRAGMA table_info({table_name});", self.con)["name"].tolist()
        return set(cols)

    # ---------------- Loaders ----------------

    def _load_bats(self):
        bats = pd.read_sql_query("SELECT bat_code FROM bat ORDER BY bat_code;", self.con)
        if bats.empty:
            messagebox.showerror("No bats", "Table 'bat' is empty. (Load data into DB first.)")
            return
        bat_list = bats["bat_code"].tolist()
        self.bat_cb["values"] = bat_list
        self.bat_cb.current(0)
        self.bat_var.set(bat_list[0])
        self._load_dates_for_bat()

    def _load_dates_for_bat(self):
        bat_code = self.bat_var.get()
        dates = pd.read_sql_query(
            """
            SELECT DISTINCT s.session_date
            FROM session s
            JOIN trial t ON t.session_id = s.session_id
            JOIN bat b   ON b.bat_id = t.bat_id
            WHERE b.bat_code = ?
            ORDER BY s.session_date;
            """,
            self.con,
            params=(bat_code,),
        )
        if dates.empty:
            self.date_cb["values"] = []
            self.date_var.set("")
            self.trial_list.delete(0, tk.END)
            self._clear_axes("No dates for this bat.")
            return

        date_list = dates["session_date"].tolist()
        self.date_cb["values"] = date_list
        self.date_cb.current(0)
        self.date_var.set(date_list[0])
        self._load_cond_trip_options()
        self._load_trials_for_bat_date()

    def _load_cond_trip_options(self):
        bat_code = self.bat_var.get()
        date = self.date_var.get()

        conds = pd.read_sql_query(
            """
            SELECT DISTINCT c.cond_code
            FROM trial t
            JOIN bat b ON b.bat_id=t.bat_id
            JOIN session s ON s.session_id=t.session_id
            JOIN condition c ON c.condition_id=t.condition_id
            WHERE b.bat_code=? AND s.session_date=?
            ORDER BY c.cond_code;
            """,
            self.con, params=(bat_code, date)
        )
        cond_list = ["(All)"] + conds["cond_code"].tolist()
        self.cond_cb["values"] = cond_list
        self.cond_var.set(cond_list[0])

        trips = pd.read_sql_query(
            """
            SELECT DISTINCT ce.trip
            FROM call_event ce
            JOIN trial t ON t.trial_id=ce.trial_id
            JOIN bat b ON b.bat_id=t.bat_id
            JOIN session s ON s.session_id=t.session_id
            WHERE b.bat_code=? AND s.session_date=? AND ce.trip IS NOT NULL
            ORDER BY ce.trip;
            """,
            self.con, params=(bat_code, date)
        )
        trip_list = ["(All)"] + [str(int(x)) for x in trips["trip"].dropna().tolist()]
        self.trip_cb["values"] = trip_list
        self.trip_var.set(trip_list[0])

    def _load_trials_for_bat_date(self):
        bat_code = self.bat_var.get()
        date = self.date_var.get()
        cond = self.cond_var.get()

        cond_filter = ""
        params = [bat_code, date]
        if cond != "(All)":
            cond_filter = " AND c.cond_code = ? "
            params.append(cond)

        self.trials_df = pd.read_sql_query(
            f"""
            SELECT
              t.trial_id,
              t.trial_num,
              c.cond_code AS cond_code,
              COUNT(ce.call_id) AS n_calls,
              SUM(CASE WHEN ce.good_call = 1 THEN 1 ELSE 0 END) AS n_good
            FROM trial t
            JOIN bat b       ON b.bat_id = t.bat_id
            JOIN session s   ON s.session_id = t.session_id
            JOIN condition c ON c.condition_id = t.condition_id
            LEFT JOIN call_event ce ON ce.trial_id = t.trial_id
            WHERE b.bat_code = ?
              AND s.session_date = ?
              {cond_filter}
            GROUP BY t.trial_id, t.trial_num, c.cond_code
            ORDER BY t.trial_num;
            """,
            self.con, params=params
        )

        self.trial_list.delete(0, tk.END)
        if self.trials_df.empty:
            self.info_label.config(text=f"{bat_code} | {date} : no trials")
            self._clear_axes("No trials for current filters.")
            return

        for _, r in self.trials_df.iterrows():
            label = f"Trial {int(r['trial_num']):>3}  cond={r['cond_code']:<4}  calls={int(r['n_calls']):>5}  good={int(r['n_good']):>5}"
            self.trial_list.insert(tk.END, label)

        self.current_trial_idx = 0
        self.trial_list.selection_set(0)
        self.trial_list.activate(0)
        self._refresh_trial()

    # ---------------- Queries ----------------

    def _query_calls_for_trial(self, trial_id: int) -> pd.DataFrame:
        good_only = self.good_only_var.get()
        front_only = self.front_only_var.get()
        trip = self.trip_var.get()

        where = ["trial_id=?"]
        params = [trial_id]

        if good_only:
            where.append("good_call=1")
        if front_only:
            where.append("(behind=0 OR behind IS NULL)")
        if trip != "(All)":
            where.append("trip=?")
            params.append(int(trip))

        # Build SELECT dynamically based on available columns
        select_cols = [
            "call_num", "time_s",
            "good_call", "behind", "pair_id",
            "x_call", "y_call", "z_call",
            "x", "y", "z",
            "norm_beam_aim_vec_x", "norm_beam_aim_vec_y",
            "norm_hd_x", "norm_hd_y",
        ]
        if "norm_beam_aim_vec_z" in self.call_event_cols:
            select_cols.append("norm_beam_aim_vec_z")
        if "norm_hd_z" in self.call_event_cols:
            select_cols.append("norm_hd_z")

        q = f"""
        SELECT {", ".join(select_cols)}
        FROM call_event
        WHERE {" AND ".join(where)}
          AND x_call IS NOT NULL AND y_call IS NOT NULL AND z_call IS NOT NULL
        ORDER BY time_s;
        """
        df = pd.read_sql_query(q, self.con, params=params)

        # Coerce vectors to numeric (None -> NaN)
        for c in ["norm_beam_aim_vec_x", "norm_beam_aim_vec_y", "norm_beam_aim_vec_z",
                  "norm_hd_x", "norm_hd_y", "norm_hd_z"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        return df

    def _query_trajectory_for_trial(self, trial_id: int) -> pd.DataFrame:
        if self.has_traj_frames:
            # Expected schema: trajectory_frame(trial_id, time_s, x, y, z, ...)
            q = """
            SELECT time_s, x, y, z
            FROM trajectory_frame
            WHERE trial_id=?
              AND x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL
            ORDER BY time_s;
            """
            return pd.read_sql_query(q, self.con, params=(trial_id,))
        else:
            # Fallback: trajectory at call times
            q = """
            SELECT time_s, x, y, z
            FROM call_event
            WHERE trial_id=?
              AND x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL
            ORDER BY time_s;
            """
            return pd.read_sql_query(q, self.con, params=(trial_id,))

    # ---------------- Plotting ----------------

    def _plot_all(self):
        self.ax_audio.clear()
        self.ax_video.clear()
        self.ax_comb.clear()

        if self.calls_df.empty:
            self._clear_axes("No calls for current filters.")
            return

        df = self.calls_df.copy()
        # Positions at call times (for plotting call points)
        xC = pd.to_numeric(df["x_call"], errors="coerce").to_numpy()
        yC = pd.to_numeric(df["y_call"], errors="coerce").to_numpy()
        zC = pd.to_numeric(df["z_call"], errors="coerce").to_numpy()

        # Ensure finite call points
        finite_calls = np.isfinite(xC) & np.isfinite(yC) & np.isfinite(zC)
        if finite_calls.sum() < 2:
            self._clear_axes("Not enough finite call points to plot.")
            return

        # Current call index (relative to df)
        self.current_call_idx = max(0, min(self.current_call_idx, len(df) - 1))

        # Trajectory for video panel
        if not self.traj_df.empty:
            tx = pd.to_numeric(self.traj_df["x"], errors="coerce").to_numpy()
            ty = pd.to_numeric(self.traj_df["y"], errors="coerce").to_numpy()
            tz = pd.to_numeric(self.traj_df["z"], errors="coerce").to_numpy()
            finite_traj = np.isfinite(tx) & np.isfinite(ty) & np.isfinite(tz)
        else:
            tx = ty = tz = None
            finite_traj = None

        # --- AUDIO panel: call points + vectors
        self.ax_audio.plot(xC[finite_calls], yC[finite_calls], zC[finite_calls], marker="o", linewidth=1)
        self.ax_audio.set_title("Audio (Beam/Head)")
        self.ax_audio.set_xlabel("x"); self.ax_audio.set_ylabel("y"); self.ax_audio.set_zlabel("z")

        if self.show_beam_var.get():
            self._quiver_vectors(
                self.ax_audio, df, xC, yC, zC,
                "norm_beam_aim_vec_x", "norm_beam_aim_vec_y",
                "norm_beam_aim_vec_z" if "norm_beam_aim_vec_z" in df.columns else None,
                scale=0.25
            )

        if self.show_head_var.get():
            self._quiver_vectors(
                self.ax_audio, df, xC, yC, zC,
                "norm_hd_x", "norm_hd_y",
                "norm_hd_z" if "norm_hd_z" in df.columns else None,
                scale=0.25
            )

        # Highlight current call
        if np.isfinite(xC[self.current_call_idx]) and np.isfinite(yC[self.current_call_idx]) and np.isfinite(zC[self.current_call_idx]):
            self._highlight_point(self.ax_audio, xC[self.current_call_idx], yC[self.current_call_idx], zC[self.current_call_idx])

        # --- VIDEO panel: full trajectory if available, else call-sampled trajectory
        if tx is not None and finite_traj is not None and finite_traj.sum() >= 2:
            self.ax_video.plot(tx[finite_traj], ty[finite_traj], tz[finite_traj], linewidth=1)
        else:
            self.ax_video.plot(xC[finite_calls], yC[finite_calls], zC[finite_calls], linewidth=1)
        self.ax_video.set_title("Video (Trajectory)")
        self.ax_video.set_xlabel("x"); self.ax_video.set_ylabel("y"); self.ax_video.set_zlabel("z")
        if np.isfinite(xC[self.current_call_idx]) and np.isfinite(yC[self.current_call_idx]) and np.isfinite(zC[self.current_call_idx]):
            self._highlight_point(self.ax_video, xC[self.current_call_idx], yC[self.current_call_idx], zC[self.current_call_idx])

        # --- COMBINED panel: trajectory + call points + vectors
        if tx is not None and finite_traj is not None and finite_traj.sum() >= 2:
            self.ax_comb.plot(tx[finite_traj], ty[finite_traj], tz[finite_traj], linewidth=1, alpha=0.8)
        self.ax_comb.plot(xC[finite_calls], yC[finite_calls], zC[finite_calls], marker="o", linewidth=1, alpha=0.9)
        self.ax_comb.set_title("Combined (3D recreation)")
        self.ax_comb.set_xlabel("x"); self.ax_comb.set_ylabel("y"); self.ax_comb.set_zlabel("z")

        if self.show_beam_var.get():
            self._quiver_vectors(
                self.ax_comb, df, xC, yC, zC,
                "norm_beam_aim_vec_x", "norm_beam_aim_vec_y",
                "norm_beam_aim_vec_z" if "norm_beam_aim_vec_z" in df.columns else None,
                scale=0.25
            )
        if self.show_head_var.get():
            self._quiver_vectors(
                self.ax_comb, df, xC, yC, zC,
                "norm_hd_x", "norm_hd_y",
                "norm_hd_z" if "norm_hd_z" in df.columns else None,
                scale=0.25
            )

        if np.isfinite(xC[self.current_call_idx]) and np.isfinite(yC[self.current_call_idx]) and np.isfinite(zC[self.current_call_idx]):
            self._highlight_point(self.ax_comb, xC[self.current_call_idx], yC[self.current_call_idx], zC[self.current_call_idx])

        self.fig.tight_layout()
        self.canvas.draw()

    def _quiver_vectors(self, ax, df, x, y, z, vx, vy, vz=None, scale=0.2):
        # Require x/y vector columns
        if vx not in df.columns or vy not in df.columns:
            return

        vdf = df.copy()
        vdf[vx] = pd.to_numeric(vdf[vx], errors="coerce")
        vdf[vy] = pd.to_numeric(vdf[vy], errors="coerce")

        if vz and vz in vdf.columns:
            vdf[vz] = pd.to_numeric(vdf[vz], errors="coerce")
        else:
            vz = None

        # Mask for finite positions + vectors
        mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & np.isfinite(vdf[vx].to_numpy()) & np.isfinite(vdf[vy].to_numpy())
        if vz:
            mask = mask & np.isfinite(vdf[vz].to_numpy())

        if mask.sum() < 2:
            return

        idx = np.where(mask)[0]
        step = max(1, len(idx) // 40)
        idx = idx[::step]

        U = vdf[vx].to_numpy()[idx] * scale
        V = vdf[vy].to_numpy()[idx] * scale
        if vz:
            W = vdf[vz].to_numpy()[idx] * scale
        else:
            W = np.zeros_like(U)

        ax.quiver(x[idx], y[idx], z[idx], U, V, W, length=1.0, normalize=False)

    def _highlight_point(self, ax, x, y, z):
        ax.scatter([x], [y], [z], s=80)

    def _clear_axes(self, msg):
        for ax in [self.ax_audio, self.ax_video, self.ax_comb]:
            ax.clear()
        self.ax_video.text2D(0.05, 0.95, msg, transform=self.ax_video.transAxes, va="top")
        self.canvas.draw()

    # ---------------- Refresh logic ----------------

    def _refresh_trial(self):
        if self.trials_df.empty:
            return
        idx = max(0, min(self.current_trial_idx, len(self.trials_df) - 1))
        self.current_trial_idx = idx

        trial_id = int(self.trials_df.iloc[idx]["trial_id"])
        trial_num = int(self.trials_df.iloc[idx]["trial_num"])
        cond = self.trials_df.iloc[idx]["cond_code"]

        self.calls_df = self._query_calls_for_trial(trial_id)
        self.traj_df = self._query_trajectory_for_trial(trial_id)

        if self.calls_df.empty:
            self.info_label.config(text=f"Trial {trial_num} cond={cond}: no calls for filters")
            self.call_scale.configure(from_=0, to=0)
            self.call_label.config(text="Call: - / -")
            self._clear_axes("No calls.")
            return

        self.current_call_idx = 0
        self.call_scale.configure(from_=0, to=len(self.calls_df) - 1)
        self.call_scale.set(0)
        self.call_label.config(text=f"Call: 1 / {len(self.calls_df)}")

        self.info_label.config(
            text=f"{self.bat_var.get()} | {self.date_var.get()} | Trial {trial_num} cond={cond} "
                 f"| calls={len(self.calls_df)} | traj={'frames' if self.has_traj_frames else 'call-sampled'}"
        )
        self._plot_all()

    # ---------------- Events ----------------

    def _on_bat_changed(self, _evt=None):
        self._load_dates_for_bat()

    def _on_date_changed(self, _evt=None):
        self._load_cond_trip_options()
        self._load_trials_for_bat_date()

    def _on_trial_selected(self, _evt=None):
        sel = self.trial_list.curselection()
        if not sel:
            return
        self.current_trial_idx = int(sel[0])
        self._refresh_trial()

    def _prev_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx - 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._refresh_trial()

    def _next_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx + 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._refresh_trial()

    def _on_call_scale(self, val):
        if self.calls_df.empty:
            return
        idx = int(float(val))
        idx = max(0, min(idx, len(self.calls_df) - 1))
        self.current_call_idx = idx
        self.call_label.config(text=f"Call: {idx+1} / {len(self.calls_df)}")
        self._plot_all()

    def _prev_call(self):
        if self.calls_df.empty:
            return
        self.current_call_idx = (self.current_call_idx - 1) % len(self.calls_df)
        self.call_scale.set(self.current_call_idx)

    def _next_call(self):
        if self.calls_df.empty:
            return
        self.current_call_idx = (self.current_call_idx + 1) % len(self.calls_df)
        self.call_scale.set(self.current_call_idx)

    def on_close(self):
        try:
            self.con.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    import os
    import tkinter as tk
    from tkinter import filedialog, messagebox

    # Hidden root just for the file picker
    picker_root = tk.Tk()
    picker_root.withdraw()
    picker_root.update()

    db_path = filedialog.askopenfilename(
        title="Select your SQLite database",
        filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")],
    )

    picker_root.destroy()

    if not db_path:
        messagebox.showinfo("No database selected", "Exiting (no DB selected).")
        raise SystemExit(0)

    if not os.path.exists(db_path):
        messagebox.showerror("DB not found", f"File does not exist:\n{db_path}")
        raise SystemExit(1)

    app = Bat3DReconstructionViewer(db_path)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()