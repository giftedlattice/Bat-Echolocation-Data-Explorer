import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class BatTrajectoryViewer(tk.Tk):
    def __init__(self, db_path: str):
        super().__init__()
        self.title("Bat Trajectory Viewer (call positions) — new schema")
        self.geometry("1100x700")

        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA foreign_keys = ON;")

        # State
        self.bat_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.trials_df = pd.DataFrame()
        self.current_trial_idx = 0

        # UI
        self._build_ui()
        self._load_bats()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Bat:").pack(side=tk.LEFT)
        self.bat_cb = ttk.Combobox(top, textvariable=self.bat_var, state="readonly", width=15)
        self.bat_cb.pack(side=tk.LEFT, padx=(6, 16))
        self.bat_cb.bind("<<ComboboxSelected>>", self._on_bat_changed)

        ttk.Label(top, text="Date:").pack(side=tk.LEFT)
        self.date_cb = ttk.Combobox(top, textvariable=self.date_var, state="readonly", width=15)
        self.date_cb.pack(side=tk.LEFT, padx=(6, 16))
        self.date_cb.bind("<<ComboboxSelected>>", self._on_date_changed)

        self.info_label = ttk.Label(top, text="Select a bat and date.")
        self.info_label.pack(side=tk.LEFT, padx=(10, 0))

        # Middle: trial list + controls
        mid = ttk.Frame(self, padding=10)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Trials (select one):").pack(anchor="w")
        self.trial_list = tk.Listbox(left, height=25, width=44)
        self.trial_list.pack(side=tk.TOP, fill=tk.Y, expand=False, pady=(6, 8))
        self.trial_list.bind("<<ListboxSelect>>", self._on_trial_selected)

        btns = ttk.Frame(left)
        btns.pack(side=tk.TOP, fill=tk.X)

        self.prev_btn = ttk.Button(btns, text="Prev", command=self._prev_trial)
        self.prev_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.next_btn = ttk.Button(btns, text="Next", command=self._next_trial)
        self.next_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        self.good_only_var = tk.BooleanVar(value=False)
        self.good_only_chk = ttk.Checkbutton(
            left, text="Plot only good_call = 1", variable=self.good_only_var, command=self._refresh_plot
        )
        self.good_only_chk.pack(anchor="w", pady=(10, 0))

        # Right: plot
        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # -------------------- DATA LOADERS --------------------

    def _load_bats(self):
        bats = pd.read_sql_query("SELECT bat_code FROM bat ORDER BY bat_code;", self.con)
        if bats.empty:
            messagebox.showerror("No bats", "Table 'bat' is empty. Load data into DB first.")
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
            self._clear_plot(f"No dates found for bat {bat_code}.")
            return

        date_list = dates["session_date"].tolist()
        self.date_cb["values"] = date_list
        self.date_cb.current(0)
        self.date_var.set(date_list[0])
        self._load_trials_for_bat_date()

    def _load_trials_for_bat_date(self):
        bat_code = self.bat_var.get()
        date = self.date_var.get()

        # NOTE: cond is now in condition table, and calls are in call_event
        self.trials_df = pd.read_sql_query(
            """
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
            GROUP BY t.trial_id, t.trial_num, c.cond_code
            ORDER BY t.trial_num;
            """,
            self.con,
            params=(bat_code, date),
        )

        self.trial_list.delete(0, tk.END)

        if self.trials_df.empty:
            self.info_label.config(text=f"{bat_code} | {date} : no trials found.")
            self._clear_plot("No trials found for this bat/date.")
            return

        for _, r in self.trials_df.iterrows():
            cond = r["cond_code"] if pd.notna(r["cond_code"]) else ""
            label = (
                f"Trial {int(r['trial_num']):>3}  cond={cond:<4}  "
                f"calls={int(r['n_calls']):>5}  good={int(r['n_good']):>5}"
            )
            self.trial_list.insert(tk.END, label)

        self.current_trial_idx = 0
        self.trial_list.selection_set(0)
        self.trial_list.activate(0)

        self.info_label.config(text=f"{bat_code} | {date} : {len(self.trials_df)} trials")
        self._plot_current_trial()

    # -------------------- PLOTTING --------------------

    def _plot_current_trial(self):
        if self.trials_df.empty:
            return

        idx = max(0, min(self.current_trial_idx, len(self.trials_df) - 1))
        self.current_trial_idx = idx

        row = self.trials_df.iloc[idx]
        trial_id = int(row["trial_id"])
        trial_num = int(row["trial_num"])
        cond = row["cond_code"] if pd.notna(row["cond_code"]) else ""

        good_only = self.good_only_var.get()

        q = """
        SELECT time_s, x_call, y_call, z_call, call_num, good_call
        FROM call_event
        WHERE trial_id = ?
          AND x_call IS NOT NULL AND y_call IS NOT NULL AND z_call IS NOT NULL
        """
        params = [trial_id]
        if good_only:
            q += " AND good_call = 1"
        q += " ORDER BY time_s;"

        df = pd.read_sql_query(q, self.con, params=params)

        if df.empty:
            self._clear_plot(f"No x/y/z call points.\nTrial {trial_num} cond={cond}")
            return

        self.ax.clear()
        self.ax.plot(df["x_call"], df["y_call"], df["z_call"], marker="o", linewidth=1)
        self.ax.set_xlabel("x")
        self.ax.set_ylabel("y")
        self.ax.set_zlabel("z")

        self.ax.set_title(
            f"{self.bat_var.get()} | {self.date_var.get()} | Trial {trial_num} | cond={cond} | n={len(df)}"
            + (" | good_only" if good_only else "")
        )

        self.fig.tight_layout()
        self.canvas.draw()

    def _clear_plot(self, msg: str):
        self.ax.clear()
        self.ax.text2D(0.05, 0.95, msg, transform=self.ax.transAxes, va="top")
        self.ax.set_axis_off()
        self.canvas.draw()

    # -------------------- UI EVENTS --------------------

    def _on_bat_changed(self, _evt=None):
        self._load_dates_for_bat()

    def _on_date_changed(self, _evt=None):
        self._load_trials_for_bat_date()

    def _on_trial_selected(self, _evt=None):
        sel = self.trial_list.curselection()
        if not sel:
            return
        self.current_trial_idx = int(sel[0])
        self._plot_current_trial()

    def _prev_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx - 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._plot_current_trial()

    def _next_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx + 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._plot_current_trial()

    def _refresh_plot(self):
        self._plot_current_trial()

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

    # Create a tiny root just for the file picker (we'll hide it)
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

    app = BatTrajectoryViewer(db_path)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()