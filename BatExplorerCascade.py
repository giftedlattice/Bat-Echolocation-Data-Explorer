# BatExplorerCascade.py
# Reorderable cascading filters with a placeholder in the order selectors
# and "soft" validation (no popup errors while user is choosing order).

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class BatExplorerCascade(tk.Tk):
    """
    Reorderable cascading filters:
      - user chooses the facet order (bat/date/cond/trial)
      - then selects values in that order
      - the next dropdown only shows values that exist given prior selections

    Data comes from:
      trial + bat + session + condition + call_event
    """

    FACETS = ["bat", "date", "cond", "trial"]

    ORDER_PLACEHOLDER = "(Select)"
    ORDER_CHOICES = [ORDER_PLACEHOLDER, "bat", "date", "cond", "trial"]

    FACET_SQL = {
        "bat": ("b.bat_code", "bat"),
        "date": ("s.session_date", "date"),
        "cond": ("c.cond_code", "cond"),
        "trial": ("t.trial_num", "trial"),
    }

    BASE_FROM = """
    FROM trial t
    JOIN bat b ON b.bat_id = t.bat_id
    JOIN session s ON s.session_id = t.session_id
    JOIN condition c ON c.condition_id = t.condition_id
    """

    def __init__(self, db_path: str):
        super().__init__()
        self.title("Bat DB Explorer — Reorderable Cascading Filters (test)")
        self.geometry("1250x780")

        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA foreign_keys = ON;")

        # Order selection (default order so it works immediately)
        self.order_vars = [tk.StringVar(value=v) for v in ["bat", "date", "cond", "trial"]]

        # Current selections for each facet (always exist)
        self.sel_vars = {f: tk.StringVar(value="(All)") for f in self.FACETS}
        self.sel_cbs = {}  # facet -> combobox widget

        # Toggles (analysis filters on call_event)
        self.good_only_var = tk.BooleanVar(value=False)
        self.front_only_var = tk.BooleanVar(value=False)  # behind=0
        self.pair_only_var = tk.BooleanVar(value=False)   # pair_id != -1

        # Trial list + selection state
        self.trials_df = pd.DataFrame()
        self.current_trial_idx = 0

        # Current call data for plotting
        self.calls_df = pd.DataFrame()

        self._build_ui()

        # Initialize cascade with default order
        self._reset_all_filters()

    # ---------------------- UI ----------------------

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        # Order panel
        order_frame = ttk.LabelFrame(top, text="Cascade order", padding=8)
        order_frame.pack(side=tk.LEFT, padx=(0, 12))

        self.order_cbs = []
        for i in range(4):
            cb = ttk.Combobox(
                order_frame,
                textvariable=self.order_vars[i],
                values=self.ORDER_CHOICES,
                state="readonly",
                width=9
            )
            cb.grid(row=0, column=i, padx=4)
            cb.bind("<<ComboboxSelected>>", self._on_order_changed)
            self.order_cbs.append(cb)

        # Filters panel
        filt_frame = ttk.LabelFrame(top, text="Selections", padding=8)
        filt_frame.pack(side=tk.LEFT, padx=(0, 12), fill=tk.X, expand=True)

        # Dynamic selection row (in chosen order)
        self.sel_container = ttk.Frame(filt_frame)
        self.sel_container.pack(side=tk.TOP, fill=tk.X)

        # Toggle panel
        toggle_frame = ttk.LabelFrame(top, text="Call filters", padding=8)
        toggle_frame.pack(side=tk.LEFT)

        ttk.Checkbutton(toggle_frame, text="good_call only", variable=self.good_only_var,
                        command=self._refresh_trial_view).pack(anchor="w")
        ttk.Checkbutton(toggle_frame, text="front only (behind=0)", variable=self.front_only_var,
                        command=self._refresh_trial_view).pack(anchor="w")
        ttk.Checkbutton(toggle_frame, text="pair only (pair_id!=-1)", variable=self.pair_only_var,
                        command=self._refresh_trial_view).pack(anchor="w")

        self.info_label = ttk.Label(top, text="", padding=(12, 0))
        self.info_label.pack(side=tk.LEFT)

        # Middle layout
        mid = ttk.Frame(self, padding=10)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Left: trials
        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Trials").pack(anchor="w")
        self.trial_list = tk.Listbox(left, height=28, width=46)
        self.trial_list.pack(side=tk.TOP, fill=tk.Y, pady=(6, 8))
        self.trial_list.bind("<<ListboxSelect>>", self._on_trial_selected)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Prev", command=self._prev_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(btns, text="Next", command=self._next_trial).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        ttk.Button(left, text="Reset filters", command=self._reset_all_filters).pack(fill=tk.X, pady=(10, 0))

        # Right: plots
        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.fig = plt.figure(figsize=(9, 6))
        self.ax_xy = self.fig.add_subplot(211)
        self.ax_ts = self.fig.add_subplot(212)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------------------- Cascade mechanics ----------------------

    def _get_order(self):
        return [v.get() for v in self.order_vars]

    def _validate_order_soft(self):
        """
        Soft validation: no popup errors.
        Returns True if order is usable, else False and updates info label.
        """
        order = self._get_order()

        # Placeholder(s) present -> not ready
        if any(o == self.ORDER_PLACEHOLDER for o in order):
            self.info_label.config(text="Pick 4 unique facets for cascade order.")
            return False

        # Duplicates present -> not ready
        if len(set(order)) != len(order):
            self.info_label.config(text="Cascade order has duplicates — choose unique facets.")
            return False

        return True

    def _on_order_changed(self, _evt=None):
        """
        When the order changes:
          - if order invalid (placeholder/duplicate), do nothing (no popup)
          - if order valid, rebuild selection widgets and repopulate cascade
        """
        if not self._validate_order_soft():
            return

        self._rebuild_selection_row()
        self._reset_selections_only()
        self._apply_cascade_from_start()

    def _rebuild_selection_row(self):
        # clear existing selection widgets
        for child in self.sel_container.winfo_children():
            child.destroy()

        self.sel_cbs.clear()

        order = self._get_order()
        for i, facet in enumerate(order):
            ttk.Label(self.sel_container, text=f"{facet}:").grid(row=0, column=2 * i, padx=(0, 4), sticky="w")
            cb = ttk.Combobox(self.sel_container, textvariable=self.sel_vars[facet], state="readonly", width=14)
            cb.grid(row=0, column=2 * i + 1, padx=(0, 12))
            cb.bind("<<ComboboxSelected>>", lambda e, idx=i: self._on_facet_selected(idx))
            self.sel_cbs[facet] = cb

    def _reset_selections_only(self):
        for f in self.FACETS:
            self.sel_vars[f].set("(All)")

    def _on_facet_selected(self, changed_index: int):
        # cascade downstream
        self._apply_cascade(changed_index)
        # update trials list + plots
        self._refresh_trials_list()

    def _apply_cascade_from_start(self):
        """
        Populate first facet options with no constraints.
        Downstream facets start with (All) only until user selects upstream.
        """
        order = self._get_order()
        if not order:
            return

        # Fill first facet with all possible values
        first = order[0]
        opts = ["(All)"] + self._fetch_distinct(first, {})
        self.sel_cbs[first]["values"] = opts
        self.sel_vars[first].set("(All)")

        # Downstream facets start empty
        for facet in order[1:]:
            self.sel_cbs[facet]["values"] = ["(All)"]
            self.sel_vars[facet].set("(All)")

        self.info_label.config(text="")  # clear message
        self._refresh_trials_list()

    def _apply_cascade(self, changed_index: int):
        order = self._get_order()

        # constraints from upstream selections
        constraints = {}
        for i in range(changed_index + 1):
            facet = order[i]
            constraints[facet] = self.sel_vars[facet].get()

        # repopulate downstream facets based on current constraints
        for j in range(changed_index + 1, len(order)):
            facet = order[j]
            opts = ["(All)"] + self._fetch_distinct(facet, constraints)
            self.sel_cbs[facet]["values"] = opts
            self.sel_vars[facet].set("(All)")
            constraints[facet] = "(All)"

    # ---------------------- SQL helpers ----------------------

    def _fetch_distinct(self, facet: str, constraints: dict) -> list:
        col, alias = self.FACET_SQL[facet]

        where = []
        params = []

        for f, v in constraints.items():
            if v in (None, "", "(All)"):
                continue
            ccol, _ = self.FACET_SQL[f]
            where.append(f"{ccol} = ?")
            params.append(v)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        q = f"SELECT DISTINCT {col} AS {alias} {self.BASE_FROM} {where_sql} ORDER BY {alias};"

        df = pd.read_sql_query(q, self.con, params=params)
        vals = df[alias].dropna().tolist()
        if facet == "trial":
            vals = [int(x) for x in vals]
        return vals

    def _current_constraints(self) -> dict:
        return {f: self.sel_vars[f].get() for f in self.FACETS}

    # ---------------------- Trials + plotting ----------------------

    def _refresh_trials_list(self):
        cons = self._current_constraints()
        where = []
        params = []

        for f, v in cons.items():
            if v in (None, "", "(All)"):
                continue
            col, _ = self.FACET_SQL[f]
            where.append(f"{col} = ?")
            params.append(v)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        q = f"""
        SELECT
          t.trial_id,
          t.trial_num,
          b.bat_code AS bat,
          s.session_date AS date,
          c.cond_code AS cond,
          COUNT(ce.call_id) AS n_calls,
          SUM(CASE WHEN ce.good_call=1 THEN 1 ELSE 0 END) AS n_good
        {self.BASE_FROM}
        LEFT JOIN call_event ce ON ce.trial_id = t.trial_id
        {where_sql}
        GROUP BY t.trial_id, t.trial_num, bat, date, cond
        ORDER BY date, bat, t.trial_num;
        """
        self.trials_df = pd.read_sql_query(q, self.con, params=params)

        self.trial_list.delete(0, tk.END)

        if self.trials_df.empty:
            self.info_label.config(text="No trials match current selections.")
            self._clear_plots("No trials for these filters.")
            return

        for _, r in self.trials_df.iterrows():
            label = f"{r['bat']} | {r['date']} | Trial {int(r['trial_num'])} cond={r['cond']}  calls={int(r['n_calls'])} good={int(r['n_good'])}"
            self.trial_list.insert(tk.END, label)

        self.current_trial_idx = 0
        self.trial_list.selection_set(0)
        self.trial_list.activate(0)
        self._refresh_trial_view()

    def _refresh_trial_view(self):
        if self.trials_df.empty:
            return

        idx = max(0, min(self.current_trial_idx, len(self.trials_df) - 1))
        self.current_trial_idx = idx

        trial_id = int(self.trials_df.iloc[idx]["trial_id"])
        bat = self.trials_df.iloc[idx]["bat"]
        date = self.trials_df.iloc[idx]["date"]
        trial_num = int(self.trials_df.iloc[idx]["trial_num"])
        cond = self.trials_df.iloc[idx]["cond"]

        where = ["trial_id=?"]
        params = [trial_id]

        if self.good_only_var.get():
            where.append("good_call=1")
        if self.front_only_var.get():
            where.append("(behind=0 OR behind IS NULL)")
        if self.pair_only_var.get():
            where.append("(pair_id != -1 AND pair_id IS NOT NULL)")

        q = f"""
        SELECT
          time_s, call_num, good_call, behind, pair_id,
          x_call, y_call, z_call,
          binned_s_all, inter_click_interval_bcfiltered
        FROM call_event
        WHERE {" AND ".join(where)}
          AND x_call IS NOT NULL AND y_call IS NOT NULL
        ORDER BY time_s;
        """
        self.calls_df = pd.read_sql_query(q, self.con, params=params)

        self.info_label.config(text=f"{bat} | {date} | Trial {trial_num} | cond={cond} | calls={len(self.calls_df)}")
        self._plot_trial()

    def _plot_trial(self):
        self.ax_xy.clear()
        self.ax_ts.clear()

        if self.calls_df.empty:
            self._clear_plots("No call rows after call filters.")
            return

        df = self.calls_df.copy()
        df["x_call"] = pd.to_numeric(df["x_call"], errors="coerce")
        df["y_call"] = pd.to_numeric(df["y_call"], errors="coerce")

        self.ax_xy.plot(df["x_call"], df["y_call"], marker="o", linewidth=1)
        self.ax_xy.set_aspect("equal", adjustable="datalim")
        self.ax_xy.set_xlabel("x_call")
        self.ax_xy.set_ylabel("y_call")
        self.ax_xy.set_title("Call positions (x_call vs y_call)")

        ts = df.dropna(subset=["binned_s_all", "inter_click_interval_bcfiltered"]).copy()
        if not ts.empty:
            self.ax_ts.plot(ts["binned_s_all"], ts["inter_click_interval_bcfiltered"], marker="o", linewidth=1)
            self.ax_ts.set_xlabel("binned_s_all")
            self.ax_ts.set_ylabel("inter_click_interval_bcfiltered")
            self.ax_ts.set_title("ICI (bcfiltered) vs binned_s_all")
        else:
            self.ax_ts.text(0.05, 0.9, "No binned_s_all / inter_click_interval_bcfiltered to plot.",
                            transform=self.ax_ts.transAxes)

        self.fig.tight_layout()
        self.canvas.draw()

    def _clear_plots(self, msg: str):
        self.ax_xy.clear()
        self.ax_ts.clear()
        self.ax_xy.text(0.05, 0.95, msg, transform=self.ax_xy.transAxes, va="top")
        self.canvas.draw()

    # ---------------------- Listbox navigation ----------------------

    def _on_trial_selected(self, _evt=None):
        sel = self.trial_list.curselection()
        if not sel:
            return
        self.current_trial_idx = int(sel[0])
        self._refresh_trial_view()

    def _prev_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx - 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._refresh_trial_view()

    def _next_trial(self):
        if self.trials_df.empty:
            return
        self.current_trial_idx = (self.current_trial_idx + 1) % len(self.trials_df)
        self.trial_list.selection_clear(0, tk.END)
        self.trial_list.selection_set(self.current_trial_idx)
        self.trial_list.activate(self.current_trial_idx)
        self._refresh_trial_view()

    # ---------------------- Reset ----------------------

    def _reset_all_filters(self):
        # Keep a working default order (no placeholders required to use it)
        defaults = ["bat", "date", "cond", "trial"]
        for i, v in enumerate(defaults):
            self.order_vars[i].set(v)

        self._rebuild_selection_row()
        self._reset_selections_only()
        self.good_only_var.set(False)
        self.front_only_var.set(False)
        self.pair_only_var.set(False)
        self._apply_cascade_from_start()

    # ---------------------- Close ----------------------

    def on_close(self):
        try:
            self.con.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    # GUI file picker for DB
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

    app = BatExplorerCascade(db_path)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()