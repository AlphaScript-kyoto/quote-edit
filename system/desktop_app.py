from __future__ import annotations

import os
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from quote_system.batch_service import (
    QUOTE_OUTPUT_ROOT,
    QUOTE_OUTPUT_ROOT_36,
    UPDATE_DIR,
    BatchControl,
    checkpoint_exists,
    clear_checkpoint,
    latest_installment_36_pdf,
    latest_price_pdf,
    load_excluded_model_keys,
    quote_output_root,
    resume_batch,
    run_batch,
    run_individual,
    save_excluded_model_keys,
)
from quote_system.config import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    DATA_DIR,
    ensure_directories,
    load_json,
)
from quote_system.installment_36 import (
    UPDATE_36_DIR,
    filter_36_target_devices,
    import_installment_36_master,
    load_installment_36_targets,
)
from quote_system.price_pdf_parser import SALES_COLUMNS, find_device
from quote_system.quote_service import (
    is_device_data_plan_allowed,
    is_plan_data_plan_allowed,
    is_sales_plan_allowed,
)


# 情報ボタン（右上「i」）で開く紹介ページ
INFO_HOME_URL = "https://alphascript-kyoto.github.io/as-homepage/"

class QuoteApp(tk.Tk):
    def __init__(self) -> None:
        ensure_directories()
        super().__init__()
        # ウィンドウタイトルバー（マウスでつかんで移動する場所）にバージョンを表示
        self.title(f"{APP_DISPLAY_NAME}  ver.{APP_VERSION}")
        self.pdf_var = tk.StringVar()
        self.status_var = tk.StringVar(value="「機種代金一覧表」フォルダの価格表PDFを確認してください。")
        self.force_all_var = tk.BooleanVar(value=True)
        self.upfront_var = tk.BooleanVar(value=False)
        self.no_ips_var = tk.BooleanVar(value=False)
        self.standard_fee_var = tk.BooleanVar(value=False)
        self.installment_mode_var = tk.StringVar(value="48")
        self.exclude_status_var = tk.StringVar(value="")
        self._batch_control: BatchControl | None = None
        self._is_running = False
        company = load_json(DATA_DIR / "company.json")
        self.departments = company.get("departments", [company.get("department", "TM事業本部")])
        self.department_var = tk.StringVar(value=company.get("department", self.departments[0]))
        self._build_ui()
        self._fit_window_to_content()
        self._on_installment_mode_changed()
        self._refresh_resume_button(log_if_available=True)

    def _fit_window_to_content(self) -> None:
        """見積もり作成ボタンより下（進捗・状態・ログ）まで、起動時点で見える高さにする。"""
        self.update_idletasks()
        needed_w = max(820, self.winfo_reqwidth() + 24)
        needed_h = max(900, self.winfo_reqheight() + 48)
        screen_w = max(self.winfo_screenwidth(), needed_w)
        screen_h = max(self.winfo_screenheight(), needed_h)
        win_w = min(needed_w, int(screen_w * 0.96))
        win_h = min(needed_h, int(screen_h * 0.92))
        self.minsize(760, min(800, win_h))
        self.geometry(f"{win_w}x{win_h}")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text=APP_DISPLAY_NAME, font=("Yu Gothic UI", 20, "bold")).pack(
            side="left", anchor="w"
        )
        ttk.Label(
            header,
            text=f"ver.{APP_VERSION}",
            font=("Yu Gothic UI", 12),
        ).pack(side="left", anchor="s", padx=(10, 0), pady=(0, 4))
        self._build_info_button(header).pack(side="right", anchor="ne")
        ttk.Label(
            root,
            text="価格表PDFを読み取り、見積もりを作成します。"
            "作成タイプ（通常48回／36回割賦）で入口・出力先が切り替わります。",
            wraplength=720,
        ).pack(anchor="w", pady=(4, 12))

        mode_frame = ttk.LabelFrame(root, text="0. 作成タイプ", padding=12)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(
            mode_frame,
            text="通常（48回分割）… 機種代金一覧表 の本体PDF",
            variable=self.installment_mode_var,
            value="48",
            command=self._on_installment_mode_changed,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame,
            text="36回割賦 … 機種代金一覧表\\36回割賦 のPDF（対象は installment_36_targets.json）",
            variable=self.installment_mode_var,
            value="36",
            command=self._on_installment_mode_changed,
        ).pack(anchor="w")
        ttk.Label(
            mode_frame,
            text="出力：通常 → output\\見積PDF　／　36回 → output\\見積PDF_36回",
            foreground="#555555",
        ).pack(anchor="w", pady=(4, 0))

        file_frame = ttk.LabelFrame(root, text="1. 機種代金表PDF", padding=12)
        file_frame.pack(fill="x")
        ttk.Entry(file_frame, textvariable=self.pdf_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(file_frame, text="PDFを選ぶ", command=self._choose_pdf).pack(side="left", padx=(8, 0))
        ttk.Button(
            file_frame,
            text="価格表フォルダを開く",
            command=self._open_price_folder,
        ).pack(side="left", padx=(8, 0))

        option_frame = ttk.LabelFrame(root, text="2. 作成条件", padding=12)
        option_frame.pack(fill="x", pady=12)
        ttk.Label(
            option_frame,
            text="標準：販売区分4種 × 対象料金プラン・データ容量 × SB光なし／あり × IPSサブスク × 安心サポート自動選択"
            " × 事務手数料免除＋初期費用3,000円",
        ).pack(anchor="w")
        ttk.Label(
            option_frame,
            text="データ容量：ケータイ分類は1GBのみ／それ以外は5GB以上。おうち割ありは5GBを作成しません。",
        ).pack(anchor="w", pady=(3, 0))
        department_row = ttk.Frame(option_frame)
        department_row.pack(fill="x", pady=(8, 3))
        ttk.Label(department_row, text="見積書に表示する部署：").pack(side="left")
        ttk.Combobox(
            department_row,
            textvariable=self.department_var,
            values=self.departments,
            state="normal",
            width=28,
        ).pack(side="left")
        ttk.Label(
            option_frame,
            text="※選んだ部署が、見積もりの右上に表示されます（電話・住所も部署ごと同じになります）。",
            wraplength=700,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            option_frame,
            text="値段が変わっていない機種も、もう一度すべて作り直す",
            variable=self.force_all_var,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            option_frame,
            text="※オフのとき（ふつう）：値段が変わった機種だけ作り直します。"
            "　オンのとき：除外していない販売中の機種をすべて作り直します。"
            "　いちばん最初の作成だけは、オン／オフどちらでも全部作ります。",
            wraplength=700,
            foreground="#555555",
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            option_frame,
            text="※［除外する機種］でチェックした機種は、どの場合も作りません。",
            foreground="#C00000",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            option_frame,
            text="事務手数料あり（税抜4,500円）版も作成",
            variable=self.standard_fee_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            option_frame,
            text="IPS通常プランも作成（一括請求表示＋ランニングコスト表示の2パターン）",
            variable=self.upfront_var,
        ).pack(anchor="w")
        ttk.Label(
            option_frame,
            text="※PDF数と処理時間が大幅に増える可能性があります",
            foreground="#C00000",
        ).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(
            option_frame,
            text="IPSなしの特別対応版も作成",
            variable=self.no_ips_var,
        ).pack(anchor="w")
        exclude_row = ttk.Frame(option_frame)
        exclude_row.pack(fill="x", pady=(12, 0))
        ttk.Button(
            exclude_row,
            text="除外する機種",
            command=self._open_exclude_window,
        ).pack(side="left", ipadx=12, ipady=4)
        ttk.Label(
            exclude_row,
            textvariable=self.exclude_status_var,
            foreground="#C00000",
        ).pack(side="left", padx=(12, 0))

        action = ttk.Frame(root)
        action.pack(fill="x", pady=(2, 12))
        self.run_button = ttk.Button(action, text="3. 見積もり作成", command=self._start, style="Accent.TButton")
        self.run_button.pack(side="left", ipadx=28, ipady=8)
        self.cancel_button = ttk.Button(
            action, text="中断", command=self._cancel_batch, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(8, 0), ipadx=12, ipady=8)
        self.resume_button = ttk.Button(
            action, text="再開", command=self._resume_batch, state="disabled"
        )
        self.resume_button.pack(side="left", padx=(8, 0), ipadx=12, ipady=8)
        ttk.Button(action, text="出力フォルダを開く", command=self._open_output_folder).pack(side="left", padx=10)
        ttk.Button(action, text="個別見積作成", command=self._open_individual_window).pack(side="left")

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(
            root,
            text="作成に時間がかかるときは［中断］で止め、［再開］で続きから作成できます。",
            wraplength=720,
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(root, textvariable=self.status_var, wraplength=720).pack(anchor="w", pady=(8, 4))
        self.log = tk.Text(root, height=9, state="disabled", font=("Yu Gothic UI", 9))
        self.log.pack(fill="both", expand=True)

    def _installment_months(self) -> int:
        return 36 if self.installment_mode_var.get() == "36" else 48

    def _open_price_folder(self) -> None:
        if self._installment_months() == 36:
            UPDATE_36_DIR.mkdir(parents=True, exist_ok=True)
            _open_path(UPDATE_36_DIR)
        else:
            _open_path(UPDATE_DIR)

    def _open_output_folder(self) -> None:
        root = quote_output_root(self._installment_months())
        root.mkdir(parents=True, exist_ok=True)
        _open_path(root)

    def _on_installment_mode_changed(self) -> None:
        if self._installment_months() == 36:
            latest = latest_installment_36_pdf()
            if latest:
                self.pdf_var.set(str(latest))
                self._write_log(f"36回割賦の価格表を検出しました：{latest.name}")
            else:
                self.pdf_var.set("")
                self._write_log(
                    "「機種代金一覧表\\36回割賦」にPDFがありません。"
                    "PDFを入れてから作成してください。"
                )
            try:
                rules = load_installment_36_targets()
                self._write_log(
                    "36回対象JSON："
                    f"categories={rules.get('match_categories')} "
                    f"contains={rules.get('match_model_key_contains')}"
                )
            except Exception as exc:
                self._write_log(f"対象JSONの読込に失敗：{exc}")
            self.force_all_var.set(True)
        else:
            self._select_latest()

    def _select_latest(self) -> None:
        latest = latest_price_pdf()
        if latest:
            self.pdf_var.set(str(latest))
            self._write_log(f"価格表を検出しました：{latest.name}")
        else:
            self._write_log("「機種代金一覧表」にPDFがありません。PDFを入れるか［PDFを選ぶ］を押してください。")
        excluded = load_excluded_model_keys()
        self._refresh_exclude_status(excluded)
        if excluded:
            self._write_log(f"除外する機種：{len(excluded)}件（［除外する機種］で変更できます）")
        else:
            self._write_log("除外する機種は未設定です（販売中の全機種が対象）。")

    def _build_info_button(self, parent: ttk.Frame) -> tk.Canvas:
        """右上の情報ボタン（青い〇の中に i）。"""
        size = 30
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            highlightthickness=0,
            cursor="hand2",
            background=self.cget("background"),
            borderwidth=0,
        )
        pad = 2
        canvas.create_oval(
            pad, pad, size - pad, size - pad,
            fill="#2B6CB0", outline="#1A4A8A", width=1,
        )
        canvas.create_text(
            size // 2, size // 2,
            text="i", fill="white", font=("Segoe UI", 12, "bold"),
        )
        canvas.bind("<Button-1>", lambda _e: self._open_info_page())
        return canvas

    def _open_info_page(self) -> None:
        webbrowser.open(INFO_HOME_URL)

    def _refresh_exclude_status(self, excluded: set[str] | None = None) -> None:
        keys = excluded if excluded is not None else load_excluded_model_keys()
        if keys:
            self.exclude_status_var.set(f"※いま {len(keys)} 機種を除外しています")
        else:
            self.exclude_status_var.set("※除外なし（販売中の全機種が作成対象）")

    def _choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(title="機種代金表PDFを選択", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.pdf_var.set(selected)

    def _open_exclude_window(self) -> None:
        if not (DATA_DIR / "device_master.json").exists():
            messagebox.showerror(
                "機種マスターがありません",
                "先に価格表PDFから一括作成を1回実行するか、機種マスターを用意してください。",
            )
            return
        device_master = load_json(DATA_DIR / "device_master.json")
        devices = [d for d in device_master["devices"] if d["status"] == "販売中"]
        if not devices:
            messagebox.showerror("販売中機種がありません", "機種マスターを確認してください。")
            return

        win = tk.Toplevel(self)
        win.title("除外する機種")
        win.geometry("520x560")
        win.minsize(480, 460)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="除外する機種", font=("Yu Gothic UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="チェックした機種は一括作成・個別見積の一覧から外れます。"
            "必要な機種だけ作りたい場合に除外してください。"
            "「すべて選択」「すべて解除」も使えます。",
            wraplength=460,
        ).pack(anchor="w", pady=(2, 8))

        excluded = load_excluded_model_keys()
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 6))

        list_wrap = ttk.Frame(frame)
        list_wrap.pack(fill="both", expand=True)

        canvas = tk.Canvas(list_wrap, highlightthickness=0)
        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=canvas.yview)
        list_frame = ttk.Frame(canvas)
        list_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _sync_width(event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        canvas.bind("<Configure>", _sync_width)

        def _on_mousewheel(event: tk.Event) -> str:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def _bind_wheel(_event: tk.Event | None = None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_wheel(_event: tk.Event | None = None) -> None:
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        list_frame.bind("<Enter>", _bind_wheel)
        win.bind("<Destroy>", lambda _e: _unbind_wheel())

        vars_by_key: dict[str, tk.BooleanVar] = {}
        for device in devices:
            key = device["model_key"]
            var = tk.BooleanVar(value=key in excluded)
            vars_by_key[key] = var
            check = ttk.Checkbutton(
                list_frame,
                text=f'{device.get("category", "")} / {device["model"]}',
                variable=var,
            )
            check.pack(anchor="w", pady=1)
            check.bind("<MouseWheel>", _on_mousewheel)

        def select_all() -> None:
            for var in vars_by_key.values():
                var.set(True)

        def clear_all() -> None:
            for var in vars_by_key.values():
                var.set(False)

        ttk.Button(toolbar, text="すべて選択（除外）", command=select_all).pack(side="left")
        ttk.Button(toolbar, text="すべて解除（除外なし）", command=clear_all).pack(side="left", padx=(8, 0))

        def save() -> None:
            selected = [key for key, var in vars_by_key.items() if var.get()]
            if len(selected) >= len(vars_by_key):
                if not messagebox.askyesno(
                    "全機種が除外されます",
                    "すべての機種にチェックが付いています。このまま保存すると一括作成は実行できません。保存しますか？",
                    parent=win,
                ):
                    return
            save_excluded_model_keys(selected)
            self._refresh_exclude_status(set(selected))
            self._write_log(f"除外機種を更新しました：{len(selected)}件")
            messagebox.showinfo("保存しました", f"{len(selected)}機種を除外にしました。", parent=win)
            _unbind_wheel()
            win.destroy()

        ttk.Button(frame, text="保存", command=save).pack(anchor="w", pady=(12, 0), ipadx=20, ipady=4)

    def _open_individual_window(self) -> None:
        months = self._installment_months()
        plan_master = load_json(DATA_DIR / "plans.json")
        excluded = load_excluded_model_keys()
        if months == 36:
            try:
                pdf36 = latest_installment_36_pdf()
                if pdf36 is None:
                    raise FileNotFoundError("36回PDFなし")
                master_36 = import_installment_36_master(pdf36)
                devices = [
                    d
                    for d in filter_36_target_devices(master_36)
                    if d.get("model_key") not in excluded
                ]
            except Exception as exc:
                messagebox.showerror(
                    "36回割賦を開けません",
                    f"{exc}\n「機種代金一覧表\\36回割賦」と installment_36_targets.json を確認してください。",
                )
                return
            device_master = {
                "schema_version": 1,
                "installment_months": 36,
                "devices": devices,
            }
            mode_label = "個別見積作成（36回割賦）"
        else:
            if not (DATA_DIR / "device_master.json").exists():
                messagebox.showerror(
                    "機種マスターがありません",
                    "先に価格表PDFから一括作成を実行してください。",
                )
                return
            device_master = load_json(DATA_DIR / "device_master.json")
            devices = [
                d for d in device_master["devices"]
                if d["status"] == "販売中" and d.get("model_key") not in excluded
            ]
            mode_label = "個別見積作成（通常48回）"
        models = [d["model"] for d in devices]
        if not models:
            messagebox.showerror(
                "選択できる機種がありません",
                "対象機種が0件です。除外設定・対象JSON・価格表を確認してください。",
            )
            return

        win = tk.Toplevel(self)
        win.title(mode_label)
        win.geometry("680x780")
        win.minsize(620, 720)
        frame = ttk.Frame(win, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=mode_label, font=("Yu Gothic UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="メイン画面の作成タイプに連動します。選択した条件だけを作成します。",
        ).pack(anchor="w", pady=(2, 2))
        ttk.Label(
            frame,
            text="※［除外する機種］で除外していない機種が一覧に出ます。",
            wraplength=620,
        ).pack(anchor="w", pady=(0, 12))

        fields = ttk.Frame(frame)
        fields.pack(fill="x")
        model_var = tk.StringVar(value=models[0])
        # SALES_COLUMNS は {販売区分名: PDF列Index} の辞書。選択肢はキー一覧を使う。
        sales_types = list(SALES_COLUMNS.keys())
        sales_var = tk.StringVar(value=sales_types[0])
        all_plan_name_to_id = {
            plan["name"]: plan_id
            for plan_id, plan in plan_master["plans"].items() if plan.get("enabled")
        }
        if not all_plan_name_to_id:
            messagebox.showerror("料金プランがありません", "plans.json の有効プランを確認してください。", parent=win)
            win.destroy()
            return
        plan_name_to_id = dict(all_plan_name_to_id)
        plan_var = tk.StringVar(value=next(iter(plan_name_to_id)))

        def add_row(row: int, label: str, widget) -> None:
            ttk.Label(fields, text=label, width=16).grid(row=row, column=0, sticky="w", pady=4)
            widget.grid(row=row, column=1, sticky="ew", pady=4)

        model_combo = ttk.Combobox(fields, textvariable=model_var, values=models, state="normal")
        add_row(0, "機種", model_combo)
        sales_combo = ttk.Combobox(
            fields, textvariable=sales_var, values=sales_types, state="readonly"
        )
        add_row(1, "販売区分", sales_combo)
        plan_combo = ttk.Combobox(
            fields, textvariable=plan_var, values=list(plan_name_to_id), state="readonly"
        )
        add_row(2, "料金プラン", plan_combo)
        fields.columnconfigure(1, weight=1)

        capacity_box = ttk.LabelFrame(frame, text="データ容量（複数選択可）", padding=10)
        capacity_box.pack(fill="x", pady=(12, 6))
        capacity_vars = {name: tk.BooleanVar() for name in ["1GB", "5GB", "20GB", "50GB", "無制限"]}
        capacity_checks = {}
        for index, (name, var) in enumerate(capacity_vars.items()):
            check = ttk.Checkbutton(capacity_box, text=name, variable=var)
            check.grid(row=0, column=index, padx=8, sticky="w")
            capacity_checks[name] = check

        ouchi_box = ttk.LabelFrame(frame, text="SB光・おうち割（複数選択可）", padding=10)
        ouchi_box.pack(fill="x", pady=6)
        ouchi_none_var = tk.BooleanVar(value=True)
        ouchi_yes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ouchi_box, text="SB光なし", variable=ouchi_none_var).pack(side="left", padx=8)
        ttk.Checkbutton(ouchi_box, text="SB光あり", variable=ouchi_yes_var).pack(side="left", padx=8)

        service_box = ttk.LabelFrame(frame, text="付帯サービス", padding=10)
        service_box.pack(fill="x", pady=6)
        ips_box = ttk.LabelFrame(service_box, text="修理保証（複数選択可）", padding=8)
        ips_box.pack(fill="x", pady=(0, 8))
        ips_subscription_var = tk.BooleanVar(value=True)
        ips_upfront_lump_var = tk.BooleanVar(value=False)
        ips_upfront_running_var = tk.BooleanVar(value=False)
        ips_none_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ips_box, text="IPSサブスク（月額）", variable=ips_subscription_var
        ).pack(anchor="w")
        ttk.Checkbutton(
            ips_box, text="通常IPS（一括表記）", variable=ips_upfront_lump_var
        ).pack(anchor="w")
        ttk.Checkbutton(
            ips_box, text="通常IPS（ランニングコスト表記）", variable=ips_upfront_running_var
        ).pack(anchor="w")
        ttk.Checkbutton(
            ips_box, text="修理保証なし（特別対応）", variable=ips_none_var
        ).pack(anchor="w")
        ttk.Label(
            ips_box,
            text="※通常IPSは機種に合うゴールド／プラチナ等をすべて作成します。",
            wraplength=580,
        ).pack(anchor="w", pady=(4, 0))
        support_display = {
            "料金プランに合わせて自動": "auto",
            "安心サポートなし": None,
            "安心サポートXS": "support_xs",
            "安心サポートS": "support_s",
        }
        support_var = tk.StringVar(value="料金プランに合わせて自動")
        support_row = ttk.Frame(service_box)
        support_row.pack(fill="x")
        ttk.Label(support_row, text="安心サポート：").pack(side="left")
        ttk.Combobox(
            support_row, textvariable=support_var, values=list(support_display), state="readonly", width=30
        ).pack(side="left")

        fee_box = ttk.LabelFrame(frame, text="初期費用（複数選択可）", padding=10)
        fee_box.pack(fill="x", pady=6)
        fee_special_var = tk.BooleanVar(value=True)
        fee_standard_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            fee_box, text="事務手数料免除＋初期費用3,000円（標準）", variable=fee_special_var
        ).pack(anchor="w")
        ttk.Checkbutton(
            fee_box, text="事務手数料あり（税抜4,500円）", variable=fee_standard_var
        ).pack(anchor="w")

        status_var = tk.StringVar(value="条件を選択して［PDF作成］を押してください。")

        def refresh_plans(*_args) -> None:
            nonlocal plan_name_to_id
            sales = sales_var.get()
            plan_name_to_id = {
                name: plan_id
                for name, plan_id in all_plan_name_to_id.items()
                if is_sales_plan_allowed(sales, plan_id)
            }
            names = list(plan_name_to_id)
            plan_combo.configure(values=names)
            if not names:
                plan_var.set("")
                return
            if plan_var.get() not in plan_name_to_id:
                plan_var.set(names[0])
            refresh_capacities()

        def refresh_capacities(*_args) -> None:
            try:
                device = find_device(device_master, model_var.get())
                plan_id = plan_name_to_id[plan_var.get()]
                plan = plan_master["plans"][plan_id]
            except (KeyError, ValueError):
                return
            selected_any = False
            for name, check in capacity_checks.items():
                allowed = (
                    name in plan["data_plans"]
                    and is_plan_data_plan_allowed(plan_id, name)
                    and is_device_data_plan_allowed(device, name, sales_var.get())
                )
                check.configure(state="normal" if allowed else "disabled")
                if not allowed:
                    capacity_vars[name].set(False)
                elif not selected_any:
                    capacity_vars[name].set(True)
                    selected_any = True

        def completed(result) -> None:
            create_button.configure(state="normal")
            status_var.set(f"{result.generated_files}件のPDFを作成しました。")
            messagebox.showinfo("個別見積作成完了", status_var.get(), parent=win)
            _open_path(result.output_dir)

        def failed(detail: str) -> None:
            create_button.configure(state="normal")
            status_var.set("作成を停止しました。条件を確認してください。")
            messagebox.showerror("個別見積作成エラー", detail, parent=win)

        def worker() -> None:
            try:
                fee_modes = [
                    mode for mode, enabled in (
                        ("special_3000", fee_special_var.get()),
                        ("standard", fee_standard_var.get()),
                    ) if enabled
                ]
                result = run_individual(
                    model=model_var.get(),
                    sales_type=sales_var.get(),
                    plan_id=plan_name_to_id[plan_var.get()],
                    data_plans=[name for name, var in capacity_vars.items() if var.get()],
                    ouchi_options=[
                        option for option, enabled in (
                            (False, ouchi_none_var.get()), (True, ouchi_yes_var.get())
                        ) if enabled
                    ],
                    include_ips_subscription=ips_subscription_var.get(),
                    include_upfront_lump=ips_upfront_lump_var.get(),
                    include_upfront_running=ips_upfront_running_var.get(),
                    include_no_ips=ips_none_var.get(),
                    support_plan_id=support_display[support_var.get()],
                    department=self.department_var.get(),
                    initial_fee_modes=fee_modes,
                    installment_months=months,
                )
            except Exception as exc:
                self.after(0, failed, str(exc))
                return
            self.after(0, completed, result)

        def start() -> None:
            create_button.configure(state="disabled")
            status_var.set("PDFを作成しています…")
            threading.Thread(target=worker, daemon=True).start()

        model_combo.bind("<<ComboboxSelected>>", refresh_capacities)
        sales_combo.bind("<<ComboboxSelected>>", refresh_plans)
        plan_combo.bind("<<ComboboxSelected>>", refresh_capacities)
        model_combo.bind("<FocusOut>", refresh_capacities)
        refresh_plans()
        ttk.Label(frame, textvariable=status_var, wraplength=620).pack(anchor="w", pady=(12, 6))
        create_button = ttk.Button(frame, text="PDF作成", command=start)
        create_button.pack(anchor="w", ipadx=28, ipady=7)

    def _set_running_ui(self, running: bool) -> None:
        self._is_running = running
        self.run_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        if running:
            self.resume_button.configure(state="disabled")
        else:
            self._refresh_resume_button()

    def _refresh_resume_button(self, *, log_if_available: bool = False) -> None:
        can_resume = (not self._is_running) and checkpoint_exists()
        self.resume_button.configure(state="normal" if can_resume else "disabled")
        if can_resume and log_if_available:
            self._write_log("中断した作成があります。［再開］で続きから作成できます。")

    def _cancel_batch(self) -> None:
        if self._batch_control is None:
            return
        self._batch_control.request_cancel()
        self.status_var.set("中断を受け付けました。現在の1件が終わると停止します…")
        self._write_log("中断を要求しました。")

    def _start(self) -> None:
        if self._is_running:
            return
        months = self._installment_months()
        if months == 36:
            pdf36 = latest_installment_36_pdf()
            if pdf36 is None:
                messagebox.showerror(
                    "価格表がありません",
                    "「機種代金一覧表\\36回割賦」フォルダに36回用PDFを入れてください。",
                )
                return
            self.pdf_var.set(str(pdf36))
        else:
            if (DATA_DIR / "device_master.json").exists():
                master = load_json(DATA_DIR / "device_master.json")
                on_sale = [
                    d for d in master.get("devices", []) if d.get("status") == "販売中"
                ]
                excluded = load_excluded_model_keys()
                if on_sale and all(d["model_key"] in excluded for d in on_sale):
                    messagebox.showerror(
                        "作成対象がありません",
                        "すべての機種が除外されています。"
                        "［除外する機種］で除外を減らしてください。",
                    )
                    return
            pdf = Path(self.pdf_var.get())
            if not pdf.exists():
                messagebox.showerror(
                    "価格表がありません",
                    "「機種代金一覧表」フォルダに価格表PDFを入れてください。",
                )
                return
        if checkpoint_exists():
            if not messagebox.askyesno(
                "中断データがあります",
                "前回中断した作成データがあります。\n"
                "新規に作成を始めると、中断データは破棄されます。\n"
                "続行しますか？（続きから再開する場合は［再開］を使ってください）",
            ):
                return
            clear_checkpoint()
        self._batch_control = BatchControl()
        self._set_running_ui(True)
        self.progress.configure(value=0, maximum=1)
        self.status_var.set("開始しています…")
        if months == 36:
            self._write_log("36回割賦モードで価格表の取込と作成を開始します。")
        else:
            self._write_log("価格表の取込と検算を開始します。")
        pdf = Path(self.pdf_var.get()) if self.pdf_var.get() else Path(".")
        threading.Thread(target=self._worker, args=(pdf, months), daemon=True).start()

    def _worker(self, pdf: Path, installment_months: int) -> None:
        try:
            result = run_batch(
                pdf,
                force_all=self.force_all_var.get(),
                include_upfront_ips=self.upfront_var.get(),
                include_no_ips=self.no_ips_var.get(),
                include_standard_initial_fee=self.standard_fee_var.get(),
                department=self.department_var.get(),
                control=self._batch_control,
                installment_months=installment_months,
                progress=lambda done, total, message: self.after(0, self._progress, done, total, message),
            )
        except Exception as exc:
            self.after(0, self._failed, str(exc))
            return
        self.after(0, self._completed, result)

    def _resume_batch(self) -> None:
        if self._is_running:
            return
        if not checkpoint_exists():
            messagebox.showinfo("再開できません", "中断した作成データがありません。")
            self._refresh_resume_button()
            return
        self._batch_control = BatchControl()
        self._set_running_ui(True)
        self.status_var.set("中断した場所から再開しています…")
        self._write_log("中断チェックポイントから再開します。")
        threading.Thread(target=self._worker_resume, daemon=True).start()

    def _worker_resume(self) -> None:
        try:
            result = resume_batch(
                control=self._batch_control,
                progress=lambda done, total, message: self.after(0, self._progress, done, total, message),
            )
        except Exception as exc:
            self.after(0, self._failed, str(exc))
            return
        self.after(0, self._completed, result)

    def _progress(self, done: int, total: int, message: str) -> None:
        self.progress.configure(maximum=max(total, 1), value=done)
        self.status_var.set(f"{done:,} / {total:,}　{message}")

    def _completed(self, result) -> None:
        self._batch_control = None
        self._set_running_ui(False)
        out_root = result.output_dir or quote_output_root(self._installment_months())
        if result.paused:
            text = (
                f"作成を中断しました。{result.generated_files:,} / "
                f"{result.total_planned:,} 件まで完了しています。\n"
                f"［再開］で続きから作成できます。\n出力先：{out_root}"
            )
            self.status_var.set(text)
            self._write_log(text)
            messagebox.showinfo("中断しました", text)
            self._refresh_resume_button()
            return
        if result.unchanged:
            text = "価格変更のある販売中機種はありませんでした。PDFは作成していません。"
        else:
            text = f"{result.mode}：{result.target_models}機種、{result.generated_files:,}件の見積PDFを作成しました。"
            text += f"\n出力先：{out_root}"
        if result.discontinued_models:
            text += f"\n取扱終了：{len(result.discontinued_models)}機種（見積作成対象外）"
        self.status_var.set(text)
        self._write_log(text)
        messagebox.showinfo("処理完了", text)
        if result.output_dir:
            _open_path(result.output_dir)

    def _failed(self, detail: str) -> None:
        self._batch_control = None
        self._set_running_ui(False)
        self.status_var.set("処理を停止しました。価格表とエラー内容を確認してください。")
        self._write_log(f"エラー：{detail}")
        messagebox.showerror("処理エラー", detail)
        self._refresh_resume_button()

    def _write_log(self, message: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def _open_path(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.startfile(path)  # type: ignore[attr-defined]


if __name__ == "__main__":
    QuoteApp().mainloop()
