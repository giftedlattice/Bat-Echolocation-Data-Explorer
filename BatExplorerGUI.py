import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class BatExplorer(tk.Tk):
    """
    DB-driven explorer for call_event data:
    - filters by bat/date/cond/trip/good/behind
    - 3D + 2D + time-series plots
    - table view of filtered calls
    - click row to highlight call
    - export filtered data
    """
    def __init__(self, db_path: str):
        super().__init__()
        self.title("Bat DB Explorer")
        self.geometry("1250x780")

        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA foreign_keys = ON;")

        # State
        self.bat_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.cond_var = tk.StringVar(value="(All)")
        self.trip_var = tk.StringVar(value="(All)")
        self.good_only_var = tk.BooleanVar(value=False)
        self.front_only_var = tk.BooleanVar(value=False)
        self.pair_only_var = tk.BooleanVar(value=False)

        self.trials_df = pd.DataFrame()
        self.calls_df = pd.DataFrame()
        self.current_trial_idx = 0
        self.highlight_call_num = None

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
        self.trip_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_everything())

        self.good_chk = ttk.Checkbutton(top, text="good_call only", variable=self.good_only_var, command=self._refresh_everything)
        self.good_chk.pack(side=tk.LEFT, padx=(10, 4))

        self.front_chk = ttk.Checkbutton(top, text="front only (behind=0)", variable=self.front_only_var, command=self._refresh_everything)
        self.front_chk.pack(side=tk.LEFT, padx=(10, 4))

        self.pair_chk = ttk.Checkbutton(top, text="pair only (pair_id!=-1)", variable=self.pair_only_var, command=self._refresh_everything)
        self.pair_chk.pack(side=tk.LEFT, padx=(10, 4))

        self.info_label = ttk.Label(top, text="")
        self.info_label.pack(side=tk.LEFT, padx=(14, 0))

        # Middle layout
        mid = ttk.Frame(self, padding=10)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Left: trial list + controls
        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Trials").pack(anchor="w")
        self.trial_list = tk.Listbox(left, height=26, width=44)
        self.trial_list.pack(side=tk.TOP, fill=tk.Y, pady=(6, 8))
        self.trial_list.bind("<<ListboxSelect>>", self._on_trial_selected)

        btns = ttk.Frame(left)
        btns.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(btns, text="Prev", command=self._prev_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(btns, text="Next", command=self._next_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        preset = ttk.Frame(left)
        preset.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))
        ttk.Button(preset, text="Preset: Trip0+Good+Front", command=self._preset_trip0_good_front).pack(fill=tk.X)
        ttk.Button(preset, text="Reset filters", command=self._reset_filters).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(preset, text="Export filtered CSV", command=self._export_filtered).pack(fill=tk.X, pady=(6, 0))

        # Right: tabs
        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        # Tab 1: plots (3D + 2D + time-series)
        self.plot_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.plot_tab, text="Plots")

        self.fig = plt.figure(figsize=(9, 6))
        self.ax3d = self.fig.add_subplot(221, projection="3d")
        self.ax2d = self.fig.add_subplot(222)
        self.ax_ts1 = self.fig.add_subplot(223)
        self.ax_ts2 = self.fig.add_subplot(224)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_tab)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Tab 2: table
        self.table_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.table_tab, text="Table")

        self._build_table(self.table_tab)

    def _build_table(self, parent):
        cols = [
            "call_num", "time_s", "good_call", "behind", "pair_id",
            "x_call", "y_call", "z_call",
            "inter_click_interval_bcfiltered", "hd_sd_deg"
        ]
        self.table_cols = cols

        self.tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, anchor="center")
        self.tree.column("call_num", width=80)
        self.tree.column("time_s", width=90)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_table_select)

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

    # ---------------- Data loading ----------------

    def _load_bats(self):
        bats = pd.read_sql_query("SELECT bat_code FROM bat ORDER BY bat_code;", self.con)
        if bats.empty:
            messagebox.showerror("No bats", "Table 'bat' is empty.")
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
            self._clear_plots("No dates found for this bat.")
            return

        date_list = dates["session_date"].tolist()
        self.date_cb["values"] = date_list
        self.date_cb.current(0)
        self.date_var.set(date_list[0])

        # Cond dropdown depends on bat/date
        self._load_cond_options()
        self._load_trials_for_bat_date()

    def _load_cond_options(self):
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
            self.con,
            params=(bat_code, date),
        )
        cond_list = ["(All)"] + conds["cond_code"].tolist()
        self.cond_cb["values"] = cond_list
        self.cond_var.set(cond_list[0])

        # Trip options come from call_event values
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
            self.con,
            params=(bat_code, date),
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
            self.con,
            params=params,
        )

        self.trial_list.delete(0, tk.END)
        if self.trials_df.empty:
            self.info_label.config(text=f"{bat_code} | {date} : no trials")
            self._clear_plots("No trials for current filters.")
            return

        for _, r in self.trials_df.iterrows():
            label = (
                f"Trial {int(r['trial_num']):>3}  cond={r['cond_code']:<4}  "
                f"calls={int(r['n_calls']):>5}  good={int(r['n_good']):>5}"
            )
            self.trial_list.insert(tk.END, label)

        self.current_trial_idx = 0
        self.trial_list.selection_set(0)
        self.trial_list.activate(0)

        self.info_label.config(text=f"{bat_code} | {date} : {len(self.trials_df)} trials")
        self._refresh_everything()

    # ---------------- Query + refresh ----------------

    def _query_calls_for_trial(self, trial_id: int) -> pd.DataFrame:
        good_only = self.good_only_var.get()
        front_only = self.front_only_var.get()
        pair_only = self.pair_only_var.get()
        trip = self.trip_var.get()

        where = ["trial_id = ?"]
        params = [trial_id]

        if good_only:
            where.append("good_call = 1")
        if front_only:
            where.append("(behind = 0 OR behind IS NULL)")
        if pair_only:
            where.append("(pair_id != -1 AND pair_id IS NOT NULL)")
        if trip != "(All)":
            where.append("trip = ?")
            params.append(int(trip))

        where_sql = " AND ".join(where)

        q = f"""
        SELECT
          call_id, call_num, time_s, good_call, behind, pair_id,
          x_call, y_call, z_call,
          inter_click_interval_bcfiltered,
          inter_click_interval,
          binned_s_all,
          hd_sd_deg,
          lon_aim_to_head, lat_aim_to_head,
          lon_beam, lat_beam,
          lon_head, lat_head
        FROM call_event
        WHERE {where_sql}
        ORDER BY time_s;
        """
        return pd.read_sql_query(q, self.con, params=params)

    def _refresh_everything(self):
        self._plot_current_trial()
        self._refresh_table()

    def _refresh_table(self):
        # clear
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.calls_df.empty:
            return

        # add rows
        for _, r in self.calls_df.iterrows():
            vals = []
            for c in self.table_cols:
                v = r.get(c, None)
                if pd.isna(v):
                    vals.append("")
                elif isinstance(v, float):
                    vals.append(f"{v:.4g}")
                else:
                    vals.append(v)
            self.tree.insert("", "end", values=vals)

    # ---------------- Plotting ----------------

    def _plot_current_trial(self):
        if self.trials_df.empty:
            return

        idx = max(0, min(self.current_trial_idx, len(self.trials_df) - 1))
        self.current_trial_idx = idx
        row = self.trials_df.iloc[idx]

        trial_id = int(row["trial_id"])
        trial_num = int(row["trial_num"])
        cond = row["cond_code"]

        self.calls_df = self._query_calls_for_trial(trial_id)

        self.ax3d.clear()
        self.ax2d.clear()
        self.ax_ts1.clear()
        self.ax_ts2.clear()

        if self.calls_df.empty or self.calls_df[["x_call", "y_call", "z_call"]].dropna(how="any").empty:
            self._clear_plots(f"No call points for Trial {trial_num} cond={cond} with current filters.")
            return

        df = self.calls_df.dropna(subset=["x_call", "y_call", "z_call"]).copy()

        # --- 3D path
        self.ax3d.plot(df["x_call"], df["y_call"], df["z_call"], marker="o", linewidth=1)
        self.ax3d.set_xlabel("x")
        self.ax3d.set_ylabel("y")
        self.ax3d.set_zlabel("z")
        self.ax3d.set_title("3D call positions")

        # highlight if selected
        if self.highlight_call_num is not None and "call_num" in df.columns:
            h = df[df["call_num"] == self.highlight_call_num]
            if not h.empty:
                self.ax3d.scatter(h["x_call"], h["y_call"], h["z_call"], s=80)

        # --- 2D top view
        self.ax2d.plot(df["x_call"], df["y_call"], marker="o", linewidth=1)
        self.ax2d.set_aspect("equal", adjustable="datalim")
        self.ax2d.set_xlabel("x")
        self.ax2d.set_ylabel("y")
        self.ax2d.set_title("2D top view (x,y)")

        if self.highlight_call_num is not None:
            h = df[df["call_num"] == self.highlight_call_num]
            if not h.empty:
                self.ax2d.scatter(h["x_call"], h["y_call"], s=80)

        # --- Time series 1: inter-click interval (bcfiltered) vs binned_s_all
        ts = df.dropna(subset=["binned_s_all", "inter_click_interval_bcfiltered"])
        if not ts.empty:
            self.ax_ts1.plot(ts["binned_s_all"], ts["inter_click_interval_bcfiltered"], marker="o", linewidth=1)
        self.ax_ts1.set_title("ICI (bcfiltered) vs binned_s_all")
        self.ax_ts1.set_xlabel("binned_s_all")
        self.ax_ts1.set_ylabel("inter_click_interval_bcfiltered")

        # --- Time series 2: HD-SD vs time
        ts2 = df.dropna(subset=["time_s", "hd_sd_deg"])
        if not ts2.empty:
            self.ax_ts2.plot(ts2["time_s"], ts2["hd_sd_deg"], marker="o", linewidth=1)
        self.ax_ts2.set_title("HD-SD (deg) vs time")
        self.ax_ts2.set_xlabel("time_s")
        self.ax_ts2.set_ylabel("hd_sd_deg")

        # top label
        self.fig.suptitle(
            f"{self.bat_var.get()} | {self.date_var.get()} | Trial {trial_num} | cond={cond} | n={len(df)}"
            + (" | good_only" if self.good_only_var.get() else "")
            + (" | front_only" if self.front_only_var.get() else "")
            + (" | pair_only" if self.pair_only_var.get() else "")
            + (f" | trip={self.trip_var.get()}" if self.trip_var.get() != "(All)" else ""),
            fontsize=11
        )
        self.fig.tight_layout()
        self.canvas.draw()

    def _clear_plots(self, msg):
        for ax in [self.ax3d, self.ax2d, self.ax_ts1, self.ax_ts2]:
            ax.clear()
        self.ax2d.text(0.05, 0.95, msg, transform=self.ax2d.transAxes, va="top")
        self.canvas.draw()

    # ---------------- Events ----------------

    def _on_bat_changed(self, _evt=None):
        self._load_dates_for_bat()

    def _on_date_changed(self, _evt=None):
        self._load_cond_options()
        self._load_trials_for_bat_date()

    def _on_trial_selected(self, _evt=None):
        sel = self.trial_list.curselection()
        if not sel:
            return
        self.current_trial_idx = int(sel[0])
        self.highlight_call_num = None
        self._refresh_everything()

    def _prev_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx - 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self.highlight_call_num = None
        self._refresh_everything()

    def _next_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx + 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self.highlight_call_num = None
        self._refresh_everything()

    def _on_table_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        try:
            call_num = int(float(vals[0]))
            self.highlight_call_num = call_num
            self._plot_current_trial()
        except Exception:
            pass

    # ---------------- Presets / utilities ----------------

    def _preset_trip0_good_front(self):
        self.trip_var.set("0")
        self.good_only_var.set(True)
        self.front_only_var.set(True)
        self.pair_only_var.set(True)
        self._refresh_everything()

    def _reset_filters(self):
        self.cond_var.set("(All)")
        self.trip_var.set("(All)")
        self.good_only_var.set(False)
        self.front_only_var.set(False)
        self.pair_only_var.set(False)
        self.highlight_call_num = None
        self._load_trials_for_bat_date()

    def _export_filtered(self):
        if self.calls_df.empty:
            messagebox.showinfo("Export", "Nothing to export for current filters.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Save filtered calls to CSV"
        )
        if not path:
            return
        self.calls_df.to_csv(path, index=False)
        messagebox.showinfo("Export", f"Saved:\n{path}")

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

    # Small hidden root for the file picker
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

    app = BatExplorer(db_path)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()