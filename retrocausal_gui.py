#!/usr/bin/env python3
"""
P-CTC consistency terminal.

Each transmitted bit is the fixed point of a noisy loop whose boundary
condition is the bit you sent. Redundancy is a majority vote over readouts of
that fixed point. Text in the received panes is that vote, decoded as bytes.

    python retrocausal_gui.py
    python retrocausal_gui.py --self-test

Requires numpy, matplotlib, and tkinter
(Debian/Ubuntu: sudo apt install python3-tk && pip install matplotlib).
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from datetime import datetime

import numpy as np

from retrocausal_channel import (
    PHRASES,
    RECOMMENDED_INTERVAL,
    RECOMMENDED_MODULATION,
    RECOMMENDED_NOISE,
    RECOMMENDED_REPS,
    VARIATION_NAMES,
    PCTCChannel,
    apply_gentle_variation,
    bin_to_hex,
    bin_to_text,
    channel_warning,
    communication_quality,
    consistency_landscape,
    is_consistent_reception,
    run_transmission,
    solve_fixed_point,
    text_to_binary,
)

AMBER = "#FFAA00"
DARK_AMBER = "#CC8800"
BG = "#0F0C00"
PANEL_BG = "#1A1600"
TEXT_BG = "#120E00"
HIGHLIGHT = "#FFCC33"
GREEN_OK = "#00FF66"
CYAN = "#00DDFF"
ALARM = "#FF5555"
MAX_MESSAGE_CHARS = 240


def launch():
    app = build_app()
    app.mainloop()


def build_app():
    import tkinter as tk
    from tkinter import filedialog, font as tkfont, scrolledtext

    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    class RetrocausalAmberTerminal(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("RETROCAUSAL COMM v1.0")
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            self.geometry(f"{min(1500, max(1100, screen_w - 80))}x{min(980, max(760, screen_h - 120))}")
            self.minsize(1100, 720)
            self.configure(bg=BG)
            self._alive = True
            self.channel = PCTCChannel(noise=RECOMMENDED_NOISE)
            self.result_queue = queue.Queue()
            self.continuous_running = False
            self._busy = False
            self.tick = 0
            self.var_stats = {i: {"count": 0, "fidelity_sum": 0.0} for i in range(5)}
            self.fidelity_history = []
            self.post_hist = []
            self.acc_hist = []
            self.mi_hist = []
            self.retro_hist = []
            self.received_messages = []
            self.retrocausal_receptions = []
            self.session_history = []
            self.retrocausal_count = 0
            self.retrocausal_fidelity_sum = 0.0
            self._params = {
                "noise": RECOMMENDED_NOISE,
                "modulation": RECOMMENDED_MODULATION,
                "reps": RECOMMENDED_REPS,
                "vary": True,
                "interval": RECOMMENDED_INTERVAL,
            }

            self.noise_var = tk.DoubleVar(value=RECOMMENDED_NOISE)
            self.mod_var = tk.DoubleVar(value=RECOMMENDED_MODULATION)
            self.rep_var = tk.IntVar(value=RECOMMENDED_REPS)
            self.font_var = tk.IntVar(value=10)
            self.cont_var = tk.BooleanVar(value=False)
            self.var_var = tk.BooleanVar(value=True)
            self.interval_var = tk.DoubleVar(value=RECOMMENDED_INTERVAL)

            self._TclError = tk.TclError
            self.update_idletasks()
            self.font_family = _pick_font(tkfont)
            self._build_ui(tk, scrolledtext, Figure, FigureCanvasTkAgg)
            self._wire_traces()
            self._publish_params()
            self._draw_idle_plots()
            self._start_queue_processor()
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self.bind("<Escape>", lambda _event: self._stop_continuous())
            soft = solve_fixed_point(0, RECOMMENDED_NOISE, RECOMMENDED_MODULATION)
            self._log(
                "v1.0 ready — output is the fixed point of the noisy loop, "
                f"then a {RECOMMENDED_REPS}-read majority vote."
            )
            self._log(
                f"At the recommended point a future 0 fixes P(past=0) at {soft['past_p0']:.3f}."
            )
            self.after(200, self.custom_msg_entry.focus_set)

        def _build_ui(self, tk, scrolledtext, Figure, FigureCanvasTkAgg):
            header = tk.Frame(self, bg="#2A2200", height=32)
            header.pack(fill="x", padx=6, pady=(4, 2))
            tk.Label(
                header,
                text="▶ P-CTC RETROCAUSAL v1.0   |   FIXED-POINT CHANNEL  ·  READOUT IS THE RECEIVED TEXT",
                font=(self.font_family, 10, "bold"),
                fg=AMBER,
                bg="#2A2200",
            ).pack(pady=5)

            main = tk.Frame(self, bg=BG)
            main.pack(fill="both", expand=True, padx=6, pady=2)

            left = tk.Frame(main, bg=PANEL_BG, relief="ridge", bd=3)
            left.pack(side="left", fill="y", padx=(0, 5))
            tk.Label(
                left, text="◉ CONTROLS", font=(self.font_family, 10, "bold"), fg=HIGHLIGHT, bg=PANEL_BG
            ).pack(pady=(8, 4))

            self._add_scale(tk, left, "NOISE", self.noise_var, 0.0, 0.45, 0.01)
            self._add_scale(tk, left, "MODULATION", self.mod_var, 0.0, 1.0, 0.01)
            self._add_scale(tk, left, "REDUNDANCY (MAJORITY VOTE)", self.rep_var, 1, 12, 1)
            self._add_scale(tk, left, "FONT SIZE", self.font_var, 8, 18, 1)
            self._add_scale(tk, left, "INTERVAL (s)", self.interval_var, 0.25, 3.5, 0.05)

            tk.Checkbutton(
                left,
                text="CONTINUOUS TX",
                variable=self.cont_var,
                font=(self.font_family, 9, "bold"),
                bg=PANEL_BG,
                fg=AMBER,
                activebackground=PANEL_BG,
                activeforeground=AMBER,
                selectcolor="#3A3000",
                command=self._toggle_continuous,
            ).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Checkbutton(
                left,
                text="GENTLE VARIATIONS",
                variable=self.var_var,
                font=(self.font_family, 9, "bold"),
                bg=PANEL_BG,
                fg=HIGHLIGHT,
                activebackground=PANEL_BG,
                activeforeground=HIGHLIGHT,
                selectcolor="#3A3000",
            ).pack(anchor="w", padx=8)

            self.transmit_btn = tk.Button(
                left,
                text='TRANSMIT "Hello this"',
                command=self._threaded_transmit,
                font=(self.font_family, 9, "bold"),
                bg="#3A2A00",
                fg=AMBER,
                activebackground="#5A4200",
                activeforeground=AMBER,
            )
            self.transmit_btn.pack(fill="x", padx=8, pady=(8, 3), ipady=4)
            tk.Button(
                left,
                text="RECOMMENDED SETTINGS",
                command=self._apply_recommended_settings,
                font=(self.font_family, 9, "bold"),
                bg="#2A4A00",
                fg=HIGHLIGHT,
                activebackground="#3A6A00",
                activeforeground=HIGHLIGHT,
            ).pack(fill="x", padx=8, pady=3, ipady=4)
            tk.Button(
                left,
                text="STOP CONTINUOUS",
                command=self._stop_continuous,
                font=(self.font_family, 9, "bold"),
                bg="#3A2200",
                fg=DARK_AMBER,
                activebackground="#5A3300",
                activeforeground=DARK_AMBER,
            ).pack(fill="x", padx=8, pady=3, ipady=3)
            tk.Button(
                left,
                text="EXPORT SESSION (JSON)",
                command=self._export_session,
                font=(self.font_family, 9, "bold"),
                bg="#2A3A00",
                fg=AMBER,
                activebackground="#4A5A00",
                activeforeground=AMBER,
            ).pack(fill="x", padx=8, pady=3, ipady=3)
            tk.Button(
                left,
                text="CLEAR ALL",
                command=self._clear_all_logs,
                font=(self.font_family, 9, "bold"),
                bg="#2A2200",
                fg=DARK_AMBER,
                activebackground="#4A3300",
                activeforeground=DARK_AMBER,
            ).pack(fill="x", padx=8, pady=(3, 8), ipady=3)

            center = tk.Frame(main, bg=BG)
            center.pack(side="left", fill="both", expand=True)

            mon = tk.Frame(center, bg="#3A3000", relief="sunken", bd=3)
            mon.pack(fill="both", expand=True, padx=2, pady=2)
            tk.Label(
                mon,
                text="LIVE FIXED-POINT MONITOR",
                font=(self.font_family, 9, "bold"),
                fg=HIGHLIGHT,
                bg="#3A3000",
            ).pack(pady=(3, 1))

            status = tk.Frame(mon, bg=TEXT_BG)
            status.pack(fill="x", padx=6, pady=2)
            self.status_label = tk.Label(
                status, text="STATUS: IDLE", font=(self.font_family, 9, "bold"), fg=GREEN_OK, bg=TEXT_BG
            )
            self.status_label.pack(side="left", padx=4)
            self.variation_label = tk.Label(
                status, text="VAR: —", font=(self.font_family, 9, "bold"), fg=CYAN, bg=TEXT_BG
            )
            self.variation_label.pack(side="left", padx=6)
            self.live_fid = tk.Label(
                status, text="FID: —", font=(self.font_family, 9, "bold"), fg=AMBER, bg=TEXT_BG
            )
            self.live_fid.pack(side="left", padx=4)
            self.live_post = tk.Label(
                status, text="POST: —", font=(self.font_family, 9, "bold"), fg=HIGHLIGHT, bg=TEXT_BG
            )
            self.live_post.pack(side="left", padx=4)
            self.live_acc = tk.Label(
                status, text="ACC: —", font=(self.font_family, 9, "bold"), fg=AMBER, bg=TEXT_BG
            )
            self.live_acc.pack(side="left", padx=4)

            self.quality_label = tk.Label(
                mon,
                text="COMMUNICATION QUALITY: —",
                font=(self.font_family, 11, "bold"),
                fg=AMBER,
                bg=TEXT_BG,
                anchor="w",
            )
            self.quality_label.pack(fill="x", padx=6, pady=(2, 0))
            self.residual_label = tk.Label(
                mon,
                text="Fixed-point defect: —",
                font=(self.font_family, 9, "bold"),
                fg=CYAN,
                bg=TEXT_BG,
                anchor="w",
            )
            self.residual_label.pack(fill="x", padx=6)
            self.warning_label = tk.Label(
                mon,
                text=" ",
                font=(self.font_family, 9, "bold"),
                fg=ALARM,
                bg=TEXT_BG,
                anchor="w",
                height=1,
            )
            self.warning_label.pack(fill="x", padx=6)

            tk.Label(
                mon,
                text="FUTURE INFLUENCE  |p − 1/2|",
                font=(self.font_family, 8, "bold"),
                fg=CYAN,
                bg=TEXT_BG,
                anchor="w",
            ).pack(fill="x", padx=6)
            self.signal_canvas = tk.Canvas(mon, height=22, bg="#0A0800", highlightthickness=0)
            self.signal_canvas.pack(fill="x", padx=6, pady=(0, 2))
            self.bar_canvas = tk.Canvas(mon, height=58, bg="#0A0800", highlightthickness=0)
            self.bar_canvas.pack(fill="x", padx=6, pady=(0, 2))

            banner = tk.Frame(mon, bg=TEXT_BG)
            banner.pack(fill="x", padx=6, pady=(2, 2))
            self.tx_banner = tk.Label(
                banner,
                text="SENT: —",
                font=(self.font_family, 9),
                fg=DARK_AMBER,
                bg=TEXT_BG,
                anchor="w",
            )
            self.tx_banner.pack(fill="x")
            self.rx_banner = tk.Label(
                banner,
                text="—",
                font=(self.font_family, 18, "bold"),
                fg=AMBER,
                bg=TEXT_BG,
                anchor="w",
                wraplength=640,
                justify="left",
            )
            self.rx_banner.pack(fill="x")
            banner.bind("<Configure>", lambda event: self.rx_banner.configure(wraplength=max(180, event.width - 8)))

            tk.Label(
                mon,
                text="EVENT LOG",
                font=(self.font_family, 8, "bold"),
                fg=DARK_AMBER,
                bg="#3A3000",
                anchor="w",
            ).pack(fill="x", padx=6)
            self.log_text = scrolledtext.ScrolledText(
                mon,
                height=4,
                width=48,
                font=(self.font_family, 10),
                bg=TEXT_BG,
                fg=AMBER,
                insertbackground=AMBER,
                relief="flat",
                wrap="word",
            )
            self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 4))

            recv = tk.Frame(center, bg="#3A3000", relief="sunken", bd=3)
            recv.pack(fill="both", expand=True, padx=2, pady=2)
            tk.Label(
                recv,
                text="READOUTS   source → majority vote → text",
                font=(self.font_family, 9, "bold"),
                fg=HIGHLIGHT,
                bg="#3A3000",
            ).pack(pady=(2, 0))
            self.recv_text = scrolledtext.ScrolledText(
                recv,
                height=4,
                width=48,
                font=(self.font_family, 10),
                bg=TEXT_BG,
                fg=AMBER,
                insertbackground=AMBER,
                relief="flat",
                wrap="word",
            )
            self.recv_text.pack(fill="both", expand=True, padx=5, pady=3)
            self.recv_text.tag_config("good", foreground=GREEN_OK)
            self.recv_text.tag_config("bad", foreground=ALARM)

            twoway = tk.Frame(center, bg=BG)
            twoway.pack(fill="both", expand=True, padx=2, pady=2)
            twoway.columnconfigure(0, weight=1, uniform="pair")
            twoway.columnconfigure(1, weight=1, uniform="pair")
            twoway.rowconfigure(0, weight=1)
            custom = tk.Frame(twoway, bg=PANEL_BG, relief="ridge", bd=3)
            custom.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
            tk.Label(
                custom,
                text="▶ YOU SEND",
                font=(self.font_family, 9, "bold"),
                fg=CYAN,
                bg=PANEL_BG,
            ).pack(pady=(4, 0))
            self.custom_msg_entry = tk.Entry(
                custom,
                font=(self.font_family, 12),
                bg=TEXT_BG,
                fg=AMBER,
                insertbackground=AMBER,
                relief="flat",
            )
            self.custom_msg_entry.pack(fill="x", padx=8, pady=4, ipady=4)
            self.custom_msg_entry.bind("<Return>", self._on_entry_return)
            tk.Button(
                custom,
                text="SEND THROUGH CHANNEL",
                command=self._send_custom_message_threaded,
                font=(self.font_family, 9, "bold"),
                bg="#2A3A00",
                fg=AMBER,
                activebackground="#4A5A00",
                activeforeground=AMBER,
            ).pack(fill="x", padx=8, pady=(0, 6), ipady=3)

            retro = tk.Frame(twoway, bg=PANEL_BG, relief="ridge", bd=3)
            retro.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
            tk.Label(
                retro,
                text="◀ HIGH-CONFIDENCE FIXED POINTS",
                font=(self.font_family, 9, "bold"),
                fg=CYAN,
                bg=PANEL_BG,
            ).pack(pady=(4, 0))
            self.retrocausal_text = scrolledtext.ScrolledText(
                retro,
                height=4,
                width=36,
                font=(self.font_family, 10),
                bg=TEXT_BG,
                fg=AMBER,
                insertbackground=AMBER,
                relief="flat",
                wrap="word",
            )
            self.retrocausal_text.pack(fill="both", expand=True, padx=5, pady=4)

            right = tk.Frame(main, bg=PANEL_BG, relief="ridge", bd=3)
            right.pack(side="right", fill="y", padx=(5, 0))
            tk.Label(
                right,
                text="◉ CONSISTENCY",
                font=(self.font_family, 10, "bold"),
                fg=HIGHLIGHT,
                bg=PANEL_BG,
            ).pack(pady=(4, 0))
            self.fig = Figure(figsize=(4.5, 6.3), facecolor="#0A0800", dpi=100)
            self.fig.subplots_adjust(hspace=0.55, left=0.16, right=0.97, top=0.96, bottom=0.05)
            self.axes = [self.fig.add_subplot(5, 1, index + 1) for index in range(5)]
            self.canvas = FigureCanvasTkAgg(self.fig, master=right)
            widget = self.canvas.get_tk_widget()
            widget.configure(bg="#0A0800", highlightthickness=0)
            widget.pack(fill="both", expand=True, padx=4, pady=(0, 4))

            bot = tk.Frame(self, bg=PANEL_BG, relief="ridge", bd=3)
            bot.pack(fill="x", padx=6, pady=(2, 5))
            tk.Label(
                bot,
                text="LIVE METRICS",
                font=(self.font_family, 8, "bold"),
                fg=HIGHLIGHT,
                bg=PANEL_BG,
            ).pack(pady=(2, 0))
            grid = tk.Frame(bot, bg=TEXT_BG)
            grid.pack(fill="x", padx=6, pady=3)
            self.live_numbers = {}
            metrics = [
                ("Fidelity", "fid"),
                ("Postselect %", "post"),
                ("Accuracy %", "acc"),
                ("Mutual info", "mi"),
                ("Consistent rx", "retro_count"),
                ("Avg consistent fid", "retro_fid"),
                ("Future influence", "future_influence"),
                ("Active var fid", "var_fid"),
                ("Tick", "tick"),
            ]
            columns = 5
            for index, (label, key) in enumerate(metrics):
                cell = tk.Frame(grid, bg=TEXT_BG)
                cell.grid(row=index // columns, column=index % columns, sticky="ew", padx=8, pady=1)
                tk.Label(cell, text=label, font=(self.font_family, 7), fg=DARK_AMBER, bg=TEXT_BG).pack(anchor="w")
                self.live_numbers[key] = tk.Label(
                    cell, text="—", font=(self.font_family, 12, "bold"), fg=AMBER, bg=TEXT_BG
                )
                self.live_numbers[key].pack(anchor="w")
            for column in range(5):
                grid.columnconfigure(column, weight=1)

        def _add_scale(self, tk, parent, label, variable, start, end, resolution):
            tk.Label(
                parent, text=label, font=(self.font_family, 8, "bold"), fg=AMBER, bg=PANEL_BG, anchor="w"
            ).pack(fill="x", padx=8, pady=(4, 0))
            tk.Scale(
                parent,
                from_=start,
                to=end,
                resolution=resolution,
                variable=variable,
                orient="horizontal",
                length=250,
                bg=PANEL_BG,
                fg=AMBER,
                troughcolor="#6A5420",
                activebackground=AMBER,
                highlightthickness=0,
                bd=0,
                sliderlength=18,
                width=14,
                showvalue=True,
            ).pack(fill="x", padx=8)

        def _wire_traces(self):
            for variable in (
                self.noise_var,
                self.mod_var,
                self.rep_var,
                self.var_var,
                self.interval_var,
            ):
                variable.trace_add("write", self._publish_params)
            self.font_var.trace_add("write", self._update_fonts)

        def _publish_params(self, *_args):
            try:
                reps = int(float(self.rep_var.get()))
            except (self._TclError, ValueError, TypeError):
                reps = RECOMMENDED_REPS
            self._params = {
                "noise": float(self.noise_var.get()),
                "modulation": float(self.mod_var.get()),
                "reps": max(1, reps),
                "vary": bool(self.var_var.get()),
                "interval": max(0.05, float(self.interval_var.get())),
            }

        def _update_fonts(self, *_args):
            size = int(self.font_var.get())
            family = self.font_family
            for widget in (self.log_text, self.recv_text, self.retrocausal_text):
                widget.configure(font=(family, size))
            self.custom_msg_entry.configure(font=(family, size + 1))
            self.rx_banner.configure(font=(family, max(14, size + 6), "bold"))

        def report_callback_exception(self, exc, val, tb):
            self._log(f"UI error: {val}")

        def _on_close(self):
            self._alive = False
            self.continuous_running = False
            self.destroy()

        def _apply_recommended_settings(self):
            self.noise_var.set(RECOMMENDED_NOISE)
            self.mod_var.set(RECOMMENDED_MODULATION)
            self.rep_var.set(RECOMMENDED_REPS)
            self.interval_var.set(RECOMMENDED_INTERVAL)
            self.var_var.set(True)
            soft = solve_fixed_point(0, RECOMMENDED_NOISE, RECOMMENDED_MODULATION)
            self._log(
                "Recommended settings restored. "
                f"Soft fidelity {soft['fidelity']:.3f}, postselect {soft['postselect_prob'] * 100:.1f}%."
            )

        def _toggle_continuous(self):
            if self.cont_var.get():
                self._start_continuous()
            else:
                self._stop_continuous()

        def _start_continuous(self):
            if self.continuous_running:
                return
            self.continuous_running = True
            self.tick = 0
            self.cont_var.set(True)
            self._set_status("CONTINUOUS")
            threading.Thread(target=self._continuous_loop, daemon=True).start()
            self._log("Continuous TX started. Esc or STOP ends it. Phrases rotate every four ticks.")

        def _stop_continuous(self):
            was_running = self.continuous_running
            self.continuous_running = False
            self.cont_var.set(False)
            if not self._busy:
                self._set_status("IDLE")
            self.variation_label.config(text="VAR: —")
            if was_running:
                self._log("Continuous TX stopped.")

        def _continuous_loop(self):
            while self.continuous_running:
                started = time.monotonic()
                try:
                    self._queue_transmission(kind="continuous")
                except Exception as exc:
                    self.result_queue.put({"type": "log", "msg": f"Continuous step failed: {exc}"})
                interval = float(self._params.get("interval", RECOMMENDED_INTERVAL))
                while self.continuous_running and time.monotonic() - started < interval:
                    time.sleep(0.05)

        def _threaded_transmit(self):
            if self._busy:
                self._log("A one-shot transmit is already running.")
                return
            self._busy = True
            self._set_status("TRANSMITTING")
            self.transmit_btn.config(state="disabled", text="TRANSMITTING…")
            threading.Thread(
                target=self._worker,
                args=("single", PHRASES[0], False, 0, None),
                daemon=True,
            ).start()

        def _on_entry_return(self, _event):
            self._send_custom_message_threaded()
            return "break"

        def _send_custom_message_threaded(self):
            text = self.custom_msg_entry.get().strip()
            if not text:
                self._log("Type a message, then Send or press Enter.")
                return
            if len(text) > MAX_MESSAGE_CHARS:
                text = text[:MAX_MESSAGE_CHARS]
                self._log(f"Message truncated to {MAX_MESSAGE_CHARS} characters.")
            self.custom_msg_entry.delete(0, "end")
            self._set_status("TRANSMITTING")
            threading.Thread(
                target=self._worker,
                args=("custom", text, False, 0, None),
                daemon=True,
            ).start()

        def _queue_transmission(self, kind):
            params = dict(self._params)
            tick = self.tick
            phrase = PHRASES[(tick // 4) % len(PHRASES)]
            vary = bool(params["vary"])
            var_id = (tick % 5) if vary else 0
            mod_offset = 0.0
            if vary and var_id == 2:
                mod_offset = 0.06 * np.sin(tick * 0.9)
            self.tick = tick + 1
            record = self._transmit_text(
                phrase,
                noise=params["noise"],
                modulation=params["modulation"] + mod_offset,
                reps=params["reps"],
                vary=vary,
                var_id=var_id,
                tick=tick,
            )
            record["kind"] = kind
            self.result_queue.put({"type": "result", "data": record})

        def _worker(self, kind, text, vary, var_id, tick):
            try:
                params = dict(self._params)
                record = self._transmit_text(
                    text,
                    noise=params["noise"],
                    modulation=params["modulation"],
                    reps=params["reps"],
                    vary=vary,
                    var_id=var_id,
                    tick=tick,
                )
                record["kind"] = kind
                self.result_queue.put({"type": "result", "data": record})
            except Exception as exc:
                self.result_queue.put({"type": "log", "msg": f"Transmit failed: {exc}"})
            finally:
                if kind == "single":
                    self.result_queue.put({"type": "busy", "busy": False})

        def _transmit_text(self, text, noise, modulation, reps, vary, var_id, tick):
            bits = text_to_binary(text)
            if vary:
                bits = apply_gentle_variation(bits, var_id, 0 if tick is None else tick)
            else:
                var_id = 0
            summary = run_transmission(self.channel, bits, modulation, reps=reps, noise=noise)
            sent_text = bin_to_text(bits)
            summary.update(
                {
                    "time": time.strftime("%H:%M:%S"),
                    "source_text": text,
                    "sent_text": sent_text,
                    "var_id": int(var_id),
                    "var_name": VARIATION_NAMES.get(int(var_id), "identity"),
                    "vary": bool(vary),
                    "tick": tick,
                }
            )
            summary["warning"] = channel_warning(
                summary["fidelity"], summary["accuracy"], summary["english"]
            )
            summary["quality"] = communication_quality(
                summary["fidelity"], summary["postselect"], summary["influence"]
            )
            summary["triggered"] = is_consistent_reception(
                summary["fidelity"], summary["postselect"], summary["accuracy"], summary["english"]
            )
            return summary

        def _start_queue_processor(self):
            self.after(28, self._process_queue)

        def _process_queue(self):
            try:
                if not self._alive or not self.winfo_exists():
                    return
                self._drain_queue()
            except self._TclError:
                return
            except Exception as exc:
                try:
                    self._log(f"Queue error: {exc}")
                except self._TclError:
                    return
            try:
                if self._alive:
                    self.after(28, self._process_queue)
            except self._TclError:
                return

        def _drain_queue(self):
            processed = 0
            while processed < 40:
                try:
                    item = self.result_queue.get_nowait()
                except queue.Empty:
                    break
                processed += 1
                kind = item.get("type")
                if kind == "log":
                    self._log(item.get("msg", ""))
                elif kind == "result":
                    self._apply_result(item.get("data") or {})
                elif kind == "busy":
                    self._busy = bool(item.get("busy"))
                    self.transmit_btn.config(state="normal", text='TRANSMIT "Hello this"')
                    if not self._busy and not self.continuous_running:
                        self._set_status("IDLE")

        def _apply_result(self, data):
            if not data:
                return
            fidelity = data["fidelity"]
            post = data["postselect"]
            accuracy = data["accuracy"]
            influence = data["influence"]
            self.live_fid.config(text=f"FID: {fidelity:.3f}")
            self.live_post.config(text=f"POST: {post * 100:.1f}%")
            self.live_acc.config(text=f"ACC: {accuracy * 100:.1f}%")
            self.live_numbers["fid"].config(text=f"{fidelity:.3f}")
            self.live_numbers["post"].config(text=f"{post * 100:.1f}%")
            self.live_numbers["acc"].config(text=f"{accuracy * 100:.1f}%")
            self.live_numbers["mi"].config(text=f"{data['mi']:.2f}")
            self.live_numbers["future_influence"].config(text=f"{influence:.2f}")
            if data.get("tick") is not None:
                self.live_numbers["tick"].config(text=str(data["tick"]))
            self._draw_signal_bar(influence)
            self._draw_bars(data.get("p0_given_0"), data.get("p0_given_1"))
            score = data["quality"]
            score_color = GREEN_OK if score >= 70 else (AMBER if score >= 45 else ALARM)
            self.quality_label.config(text=f"COMMUNICATION QUALITY: {score:.0f}/100", fg=score_color)
            self.residual_label.config(
                text=(
                    f"Fixed-point defect {data['residual']:.1e}"
                    f"    idle gap {data['idle_gap']:.3f}"
                    f"    {data['bits']} bits × {data['reps']} reads"
                )
            )
            warning = data.get("warning") or ""
            self.warning_label.config(text=warning if warning else " ")
            var_name = data.get("var_name", "identity")
            if data.get("vary"):
                self.variation_label.config(text=f"VAR: #{data.get('var_id', 0)} {var_name}")
                stats = self.var_stats[int(data.get("var_id", 0))]
                stats["count"] += 1
                stats["fidelity_sum"] += fidelity
                self.live_numbers["var_fid"].config(
                    text=f"#{data.get('var_id', 0)} {stats['fidelity_sum'] / stats['count']:.2f}"
                )
            else:
                self.variation_label.config(text="VAR: off")

            sent = data.get("sent_text") or "(non-printable)"
            got = data.get("english") or "(non-printable)"
            self.tx_banner.config(text=f"SENT: {sent}   ({var_name})")
            self.rx_banner.config(text=got, fg=GREEN_OK if data.get("correct") else ALARM)

            if data.get("triggered"):
                self.retrocausal_count += 1
                self.retrocausal_fidelity_sum += fidelity
                self.retro_hist.append(1)
                self._append_retro(data)
            else:
                self.retro_hist.append(0)
            if len(self.retro_hist) > 40:
                del self.retro_hist[:-40]
            self.live_numbers["retro_count"].config(text=str(self.retrocausal_count))
            avg_retro = (
                self.retrocausal_fidelity_sum / self.retrocausal_count if self.retrocausal_count else 0.0
            )
            self.live_numbers["retro_fid"].config(text=f"{avg_retro:.2f}" if self.retrocausal_count else "—")

            self.fidelity_history.append(fidelity)
            self.post_hist.append(post)
            self.acc_hist.append(accuracy)
            self.mi_hist.append(data["mi"])
            for series, limit in (
                (self.fidelity_history, 40),
                (self.post_hist, 15),
                (self.acc_hist, 40),
                (self.mi_hist, 40),
            ):
                if len(series) > limit:
                    del series[:-limit]
            self._redraw_plots(data["noise"], data["modulation"])
            self._append_received(data)
            if data.get("kind") != "continuous":
                mark = "exact" if data.get("correct") else "with errors"
                self._log(f"Received \"{got}\" {mark} from \"{data.get('source_text', '')}\".")
            if self.continuous_running:
                self._set_status("CONTINUOUS")
            elif not self._busy:
                self._set_status("IDLE")

            self.session_history.append(
                {
                    "time": data.get("time"),
                    "kind": data.get("kind"),
                    "source_text": data.get("source_text"),
                    "sent_text": data.get("sent_text"),
                    "english": data.get("english"),
                    "correct": bool(data.get("correct")),
                    "fidelity": fidelity,
                    "postselect": post,
                    "accuracy": accuracy,
                    "mi": data["mi"],
                    "residual": data["residual"],
                    "idle_gap": data["idle_gap"],
                    "influence": influence,
                    "quality": score,
                    "triggered": bool(data.get("triggered")),
                    "noise": data["noise"],
                    "modulation": data["modulation"],
                    "reps": data["reps"],
                    "bits": data["bits"],
                    "variation": var_name,
                    "tick": data.get("tick"),
                }
            )
            if len(self.session_history) > 400:
                del self.session_history[:-400]

        def _append_received(self, data):
            line, tag = _format_received(data)
            self.received_messages.append((line, tag))
            if len(self.received_messages) > 24:
                del self.received_messages[:-24]
            self._render_tagged(self.recv_text, self.received_messages)

        def _append_retro(self, data):
            english = data.get("english") or "(non-printable)"
            line = (
                f"[{data.get('time', '')}] ← \"{english}\"   "
                f"fid={data['fidelity']:.2f}  post={data['postselect'] * 100:.0f}%  "
                f"defect={data['residual']:.1e}"
            )
            self.retrocausal_receptions.append(line)
            if len(self.retrocausal_receptions) > 24:
                del self.retrocausal_receptions[:-24]
            self.retrocausal_text.delete("1.0", "end")
            self.retrocausal_text.insert("end", "\n".join(self.retrocausal_receptions))
            self.retrocausal_text.see("end")

        def _render_tagged(self, widget, rows):
            widget.delete("1.0", "end")
            for index, (line, tag) in enumerate(rows):
                widget.insert("end", line + ("\n" if index < len(rows) - 1 else ""), tag)
            widget.see("end")

        def _draw_signal_bar(self, strength):
            self.signal_canvas.delete("all")
            width = max(self.signal_canvas.winfo_width(), 280)
            strength = max(0.0, min(1.0, float(strength)))
            color = AMBER if strength >= 0.5 else DARK_AMBER
            self.signal_canvas.create_rectangle(8, 3, 8 + int(strength * (width - 70)), 19, fill=color, outline="")
            self.signal_canvas.create_text(
                width - 8,
                11,
                text=f"{strength * 100:.0f}%",
                fill=AMBER,
                font=(self.font_family, 9, "bold"),
                anchor="e",
            )

        def _draw_bars(self, p_given_0, p_given_1):
            self.bar_canvas.delete("all")
            width = max(self.bar_canvas.winfo_width(), 280)
            rows = (
                (8, "p(0|sent 0)", p_given_0, AMBER),
                (32, "p(0|sent 1)", p_given_1, DARK_AMBER),
            )
            for y, label, value, color in rows:
                self.bar_canvas.create_text(
                    8, y + 8, text=label, fill=HIGHLIGHT, font=(self.font_family, 8, "bold"), anchor="w"
                )
                if value is None:
                    self.bar_canvas.create_text(
                        width - 8, y + 8, text="—", fill=DARK_AMBER, font=(self.font_family, 8), anchor="e"
                    )
                    continue
                value = max(0.0, min(1.0, float(value)))
                left = 110
                right = width - 58
                self.bar_canvas.create_rectangle(left, y, left + int(value * (right - left)), y + 16, fill=color, outline="")
                self.bar_canvas.create_text(
                    width - 8,
                    y + 8,
                    text=f"{value:.3f}",
                    fill=color,
                    font=(self.font_family, 9, "bold"),
                    anchor="e",
                )

        def _style_ax(self, ax, title, color=HIGHLIGHT):
            ax.set_facecolor("#0A0800")
            ax.set_title(title, color=color, fontsize=8, pad=2)
            ax.tick_params(colors=AMBER, labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#553300")

        def _draw_idle_plots(self):
            self._redraw_plots(RECOMMENDED_NOISE, RECOMMENDED_MODULATION)
            self._draw_bars(None, None)
            self._draw_signal_bar(0.0)

        def _redraw_plots(self, noise, modulation):
            xs, y0, y1, p0, p1 = consistency_landscape(noise, modulation)
            titles = (
                "Consistency landscape  (p − f(p))²",
                "Postselection  (last 15)",
                "Accuracy and mutual information",
                "Soft fidelity",
                "High-confidence receptions",
            )
            for ax in self.axes:
                ax.clear()
            self._style_ax(self.axes[0], titles[0])
            self.axes[0].plot(xs, y0, color=AMBER, lw=1.2, label="future 0")
            self.axes[0].plot(xs, y1, color=CYAN, lw=1.1, label="future 1")
            self.axes[0].axvline(p0, color=AMBER, ls="--", lw=0.7)
            self.axes[0].axvline(p1, color=CYAN, ls="--", lw=0.7)
            self.axes[0].legend(
                loc="upper right", fontsize=6, facecolor="#1A1600", edgecolor="#553300", labelcolor=AMBER
            )
            self._style_ax(self.axes[1], titles[1])
            if self.post_hist:
                self.axes[1].bar(range(len(self.post_hist)), self.post_hist, color=AMBER, width=0.7)
                self.axes[1].set_xlim(-0.6, max(14.6, len(self.post_hist) - 0.4))
                self.axes[1].set_ylim(0, 1)
            self._style_ax(self.axes[2], titles[2])
            if self.acc_hist:
                self.axes[2].plot(self.acc_hist, color=AMBER, lw=1.2, marker="o", ms=3, label="accuracy")
                self.axes[2].plot(self.mi_hist, color=CYAN, lw=1.1, marker="o", ms=3, label="MI")
                self.axes[2].set_xlim(-0.5, max(10, len(self.acc_hist) - 1) + 0.5)
                self.axes[2].set_ylim(-0.05, 1.05)
                self.axes[2].legend(
                    loc="lower left", fontsize=6, facecolor="#1A1600", edgecolor="#553300", labelcolor=AMBER
                )
            self._style_ax(self.axes[3], titles[3])
            if self.fidelity_history:
                self.axes[3].plot(self.fidelity_history, color=AMBER, lw=1.2, marker="o", ms=3)
                self.axes[3].set_xlim(-0.5, max(10, len(self.fidelity_history) - 1) + 0.5)
                self.axes[3].set_ylim(0, 1)
            self._style_ax(self.axes[4], titles[4], CYAN)
            if self.retro_hist:
                self.axes[4].plot(self.retro_hist, color=CYAN, lw=1.2, marker="o", ms=3)
                self.axes[4].set_xlim(-0.5, max(10, len(self.retro_hist) - 1) + 0.5)
                self.axes[4].set_ylim(-0.05, 1.05)
            self.canvas.draw_idle()

        def _set_status(self, text):
            color = GREEN_OK if text == "IDLE" else HIGHLIGHT
            self.status_label.config(text=f"STATUS: {text}", fg=color)

        def _log(self, msg):
            stamp = time.strftime("%H:%M:%S")
            self.log_text.insert("end", f"[{stamp}] {msg}\n")
            # Keep the widget from growing without bound.
            end_index = int(float(self.log_text.index("end-1c")))
            if end_index > 80:
                self.log_text.delete("1.0", f"{end_index - 60}.0")
            self.log_text.see("end")

        def _clear_all_logs(self):
            self.log_text.delete("1.0", "end")
            self.received_messages.clear()
            self.recv_text.delete("1.0", "end")
            self.retrocausal_receptions.clear()
            self.retrocausal_text.delete("1.0", "end")
            self.session_history.clear()
            self.fidelity_history.clear()
            self.post_hist.clear()
            self.acc_hist.clear()
            self.mi_hist.clear()
            self.retro_hist.clear()
            self.retrocausal_count = 0
            self.retrocausal_fidelity_sum = 0.0
            self.var_stats = {i: {"count": 0, "fidelity_sum": 0.0} for i in range(5)}
            for label in self.live_numbers.values():
                label.config(text="—")
            self.live_fid.config(text="FID: —")
            self.live_post.config(text="POST: —")
            self.live_acc.config(text="ACC: —")
            self.quality_label.config(text="COMMUNICATION QUALITY: —", fg=AMBER)
            self.residual_label.config(text="Fixed-point defect: —")
            self.warning_label.config(text=" ")
            self.tx_banner.config(text="SENT: —")
            self.rx_banner.config(text="—", fg=AMBER)
            self.variation_label.config(text="VAR: —")
            self._draw_idle_plots()
            self._log("Logs, metrics, and plots cleared.")

        def _export_session(self, path=None):
            if not self.session_history:
                self._log("No session data to export.")
                return None
            if path is None:
                path = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json")],
                    initialfile="retrocausal_session.json",
                )
            if not path:
                return None
            payload = {
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "model": "affine noisy-loop fixed point with majority readout",
                "parameters": dict(self._params),
                "history": self.session_history,
            }
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            self._log(f"Session exported to {path}")
            return path

    return RetrocausalAmberTerminal()


def _pick_font(tkfont):
    families = set(tkfont.families())
    for name in ("DejaVu Sans Mono", "Liberation Mono", "Consolas", "Courier New", "Courier"):
        if name in families:
            return name
    return "TkFixedFont"


def _format_received(data):
    english = data.get("english") or "(non-printable)"
    sent = data.get("sent_text") or "(non-printable)"
    origin = data.get("source_text") or ""
    var_name = data.get("var_name") or "identity"
    mark = "✓" if data.get("correct") else "✗"
    if data.get("vary") and sent != origin:
        body = f"\"{origin}\" → sent \"{sent}\" ({var_name}) → \"{english}\""
    else:
        body = f"\"{origin}\" → \"{english}\"  ({var_name})"
    line = (
        f"[{data.get('time', '')}] {body}  {mark}  "
        f"acc={data['accuracy'] * 100:.0f}%  fid={data['fidelity']:.2f}  "
        f"post={data['postselect'] * 100:.0f}%  "
        f"hex={_short_hex(data.get('decoded_bits', ''))}"
    )
    return line, ("good" if data.get("correct") else "bad")


def _short_hex(bits):
    rendered = bin_to_hex(bits)
    if len(rendered) > 24:
        return rendered[:24] + "…"
    return rendered


def self_test():
    """Drive the window without a human: round trip, custom text, noise, export."""
    app = build_app()
    try:
        app.update()
        log = app.log_text.get("1.0", "end")
        if "0.951" not in log:
            raise AssertionError(f"startup log did not show the fixed point: {log!r}")

        app.noise_var.set(0.0)
        app.mod_var.set(1.0)
        app.rep_var.set(1)
        app.update()
        record = app._transmit_text("Hello this", noise=0.0, modulation=1.0, reps=1, vary=False, var_id=0, tick=None)
        record["kind"] = "single"
        app._apply_result(record)
        app.update()
        if app.rx_banner.cget("text") != "Hello this":
            raise AssertionError(app.rx_banner.cget("text"))
        if "Hello this" not in app.recv_text.get("1.0", "end"):
            raise AssertionError(app.recv_text.get("1.0", "end"))
        if "Hello this" not in app.retrocausal_text.get("1.0", "end"):
            raise AssertionError("perfect packet was not filed as a consistent reception")
        if app.live_acc.cget("text") != "ACC: 100.0%":
            raise AssertionError(app.live_acc.cget("text"))

        app.custom_msg_entry.insert(0, "Hi")
        app._send_custom_message_threaded()
        _pump_until(app, lambda: "Hi" in app.recv_text.get("1.0", "end"), 3.0)
        if app.rx_banner.cget("text") != "Hi":
            raise AssertionError(app.rx_banner.cget("text"))

        app._threaded_transmit()
        _pump_until(app, lambda: not app._busy, 3.0)
        if app.transmit_btn.cget("state") != "normal":
            raise AssertionError("transmit button stayed disabled")

        noisy = app._transmit_text("Hello this" * 4, noise=0.40, modulation=0.15, reps=1, vary=False, var_id=0, tick=None)
        if noisy["accuracy"] >= 0.85 or noisy["fidelity"] >= 0.70:
            raise AssertionError(f"high noise still looked clean: {noisy['accuracy']} {noisy['fidelity']}")
        if noisy["triggered"]:
            raise AssertionError("a weak fixed point was treated as high confidence")
        noisy["kind"] = "custom"
        app._apply_result(noisy)
        app.update()
        if not app.warning_label.cget("text").strip():
            raise AssertionError("expected a warning on a damaged readout")

        app._apply_recommended_settings()
        app.interval_var.set(0.25)
        app.update()
        before = len(app.received_messages)
        app._start_continuous()
        _pump_until(app, lambda: len(app.received_messages) >= before + 2, 4.0)
        app._stop_continuous()
        _pump_until(app, lambda: not app.continuous_running, 1.0)
        app._drain_queue()
        if app.live_numbers["tick"].cget("text") in ("—", ""):
            raise AssertionError("continuous TX did not advance the tick")

        path = "/tmp/retrocausal_self_test.json"
        exported = app._export_session(path)
        if exported != path:
            raise AssertionError("export did not write")
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not payload["history"]:
            raise AssertionError("export history empty")

        app._clear_all_logs()
        app.update()
        if app.recv_text.get("1.0", "end").strip():
            raise AssertionError("clear left received text behind")
        if app.rx_banner.cget("text") != "—":
            raise AssertionError(app.rx_banner.cget("text"))
        print("SELF-TEST OK")
        return 0
    finally:
        try:
            app._alive = False
            app.continuous_running = False
            app.destroy()
        except Exception:
            pass


def _pump_until(app, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.update()
        if predicate():
            return
        time.sleep(0.02)
    app.update()
    if not predicate():
        raise AssertionError("timed out waiting for the UI")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        try:
            raise SystemExit(self_test())
        except Exception as exc:
            print(f"SELF-TEST FAILED: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    try:
        launch()
    except ImportError as exc:
        raise SystemExit(
            "This UI needs tkinter and matplotlib. "
            "On Debian/Ubuntu: sudo apt install python3-tk && pip install matplotlib. "
            f"Import failed: {exc}"
        ) from exc
