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
    load_device_master,
    load_included_model_keys,
    quote_output_root,
    resume_batch,
    run_batch,
    run_individual,
    save_included_model_keys,
)
from quote_system.config import (
    APP_DISPLAY_NAME,
    APP_VERSION,
    DATA_DIR,
    IS_TM_SPECIAL,
    QUOTE_OUTPUT_DIRNAME,
    QUOTE_OUTPUT_DIRNAME_24,
    QUOTE_OUTPUT_DIRNAME_36,
    app_window_title,
    ensure_directories,
    load_json,
    save_json,
)
from quote_system.installment_36 import (
    TARGETS_PATH,
    UPDATE_36_DIR,
    filter_36_target_devices,
    import_installment_36_master,
    load_installment_36_targets,
)
from quote_system.price_pdf_parser import SALES_COLUMNS, find_device, parse_price_pdf
from quote_system.quote_service import (
    is_device_data_plan_allowed,
    is_device_plan_allowed,
    is_device_sales_type_allowed,
    is_plan_data_plan_allowed,
    is_sales_plan_allowed,
)
from quote_system.update_check import (
    RemoteLatest,
    check_for_update,
    mark_dismissed,
    open_update_location,
)


# 情報ボタン（右上「i」）で開く紹介ページ
INFO_HOME_URL = "https://alphascript-kyoto.github.io/as-homepage/"

class QuoteApp(tk.Tk):
    def __init__(self) -> None:
        ensure_directories()
        super().__init__()
        # ウィンドウタイトルバー（マウスでつかんで移動する場所）にバージョンを表示
        self.title(app_window_title())
        self.pdf_var = tk.StringVar()
        self.status_var = tk.StringVar(value="「機種代金一覧表」フォルダの価格表PDFを確認してください。")
        self.force_all_var = tk.BooleanVar(value=True)
        self.upfront_var = tk.BooleanVar(value=False)
        self.upfront_mode_var = tk.StringVar(value="lump")
        self.mnp_shinki_irs_var = tk.BooleanVar(value=False)
        self.no_ips_var = tk.BooleanVar(value=False)
        self.light_plan_var = tk.BooleanVar(value=False)
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
        if IS_TM_SPECIAL:
            self.after(300, self._warn_tm_special_edition)
        else:
            # 通常版のみ：共有フォルダの latest.json を短時間チェック（失敗時は黙って起動）
            self.after(500, self._start_update_check)

    def _warn_tm_special_edition(self) -> None:
        messagebox.showwarning(
            "TM兼任事業部用パッケージ",
            "このアプリはTM兼任事業部向けの特例版です。\n\n"
            "・一括作成 … 通常版と同じ制限\n"
            "・個別作成 … ライト系の販売区分・容量・IRSの制限を解除\n\n"
            "標準ルール外の見積になるため、取扱いには注意してください。",
        )

    def _start_update_check(self) -> None:
        """Background fetch so a stuck N: drive cannot freeze the main window."""

        def worker() -> None:
            remote = check_for_update()
            if remote is not None:
                self.after(0, self._show_update_notice, remote)

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_notice(self, remote: RemoteLatest) -> None:
        if not self.winfo_exists():
            return
        message = (
            f"新しいバージョン {remote.version} があります。\n"
            f"（いまのアプリは {APP_VERSION} です）\n\n"
            "更新する場合は、共有フォルダの最新ZIPを手元にコピーして\n"
            "展開し直してください。\n\n"
            "［はい］でZIPの場所を開きます。［いいえ］であとで確認します。"
        )
        if messagebox.askyesno("更新があります", message, parent=self):
            open_update_location(remote)
            self._write_log(
                f"更新案内：共有の {remote.version}（{remote.zip_name}）を開きました。"
            )
        else:
            mark_dismissed(remote.version)
            self._write_log(
                f"更新案内：{remote.version} をあとで（本日中は再表示しません）。"
            )

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
        ver_label = f"ver.{APP_VERSION}"
        if IS_TM_SPECIAL:
            ver_label = f"TM兼任事業部用  {ver_label}"
        ttk.Label(
            header,
            text=ver_label,
            font=("Yu Gothic UI", 12),
        ).pack(side="left", anchor="s", padx=(10, 0), pady=(0, 4))
        self._build_info_button(header).pack(side="right", anchor="ne")
        ttk.Label(
            root,
            text="価格表PDFを読み取り、見積もりを作成します。"
            "作成タイプ（通常48回／36回割賦）で入口・出力先が切り替わります。"
            "24回割賦は下のボタンから個別作成ウィンドウを開きます。",
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
        ttk.Button(
            mode_frame,
            text="24回割賦（個別作成ウィンドウを開く）",
            command=lambda: self._open_individual_window(24),
        ).pack(anchor="w", pady=(8, 0), ipadx=8, ipady=2)
        ttk.Label(
            mode_frame,
            text=(
                f"出力：通常 → output\\{QUOTE_OUTPUT_DIRNAME}"
                f"　／　36回 → output\\{QUOTE_OUTPUT_DIRNAME_36}"
                f"　／　24回 → output\\{QUOTE_OUTPUT_DIRNAME_24}"
            ),
            foreground="#555555",
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            mode_frame,
            text="※24回は価格表の「24回」列がある機種のみ。一括ラジオは切り替えず、個別ウィンドウで作成します。",
            foreground="#555555",
            wraplength=700,
        ).pack(anchor="w", pady=(2, 0))
        if IS_TM_SPECIAL:
            ttk.Label(
                mode_frame,
                text="※このパッケージはTM兼任事業部用です。一括は通常ルール／個別のみ制限解除。",
                foreground="#C00000",
                wraplength=700,
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
            text="データ容量：ケータイは1GBのみ／iPad・AndroidTabは1・5・50GB／他は5GB以上。"
            "おうち割あり×5GBは通常作成しません（iPad・AndroidTabは例外で作成）。",
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
            "　オンのとき：作成対象の販売中機種をすべて作り直します。"
            "　いちばん最初の作成だけは、オン／オフどちらでも全部作ります。",
            wraplength=700,
            foreground="#555555",
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            option_frame,
            text="※［作成する機種］でチェックした機種だけを作ります。",
            foreground="#C00000",
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            option_frame,
            text="事務手数料あり（税抜4,500円）版も作成",
            variable=self.standard_fee_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            option_frame,
            text="通常IPSプランも作成",
            variable=self.upfront_var,
        ).pack(anchor="w")
        upfront_mode_row = ttk.Frame(option_frame)
        upfront_mode_row.pack(anchor="w", padx=(20, 0))
        ttk.Radiobutton(
            upfront_mode_row,
            text="一括表記",
            variable=self.upfront_mode_var,
            value="lump",
        ).pack(side="left")
        ttk.Radiobutton(
            upfront_mode_row,
            text="ランニングコスト表記",
            variable=self.upfront_mode_var,
            value="monthly_as_running",
        ).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(
            option_frame,
            text="新規／MNPでもスーパー／ハイパー（IRSあり・割引セット）を作成",
            variable=self.mnp_shinki_irs_var,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Checkbutton(
            option_frame,
            text="ライトプランも作成（IRSなし）",
            variable=self.light_plan_var,
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
        self.exclude_button = ttk.Button(
            exclude_row,
            text="作成する機種",
            command=self._open_exclude_window,
        )
        self.exclude_button.pack(side="left", ipadx=12, ipady=4)
        ttk.Label(
            exclude_row,
            textvariable=self.exclude_status_var,
            foreground="#C00000",
        ).pack(side="left", padx=(12, 0))
        # 36回モードのときだけ表示する（対象JSONを直接開いて編集）
        self.edit_targets_button = ttk.Button(
            exclude_row,
            text="対象機種JSONを編集",
            command=self._open_targets_json,
        )

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
        self.individual_button = ttk.Button(
            action,
            text="個別見積作成",
            command=lambda: self._open_individual_window(48),
        )
        self.individual_button.pack(side="left")
        self.individual36_button = ttk.Button(
            action,
            text="個別見積（36回割賦）",
            command=lambda: self._open_individual_window(36),
        )
        self.individual36_button.pack(side="left", padx=(8, 0))

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

    def _open_targets_json(self) -> None:
        """36回割賦の対象機種JSONを既定のエディタで開く。"""
        if not TARGETS_PATH.exists():
            # 初回はシード内容を書き出してから開く
            save_json(TARGETS_PATH, load_installment_36_targets())
        try:
            os.startfile(TARGETS_PATH)  # type: ignore[attr-defined]
        except OSError:
            import subprocess

            subprocess.Popen(["notepad.exe", str(TARGETS_PATH)])
        self._write_log(f"対象機種JSONを開きました：{TARGETS_PATH}")
        self._write_log("編集して保存すると、次の作成（個別・一括）から反映されます。")

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
            # 36回割賦では［作成する機種］は使わない（対象は installment_36_targets.json）
            self.exclude_button.configure(state="disabled")
            self.exclude_status_var.set(
                "※36回割賦では使いません（対象は installment_36_targets.json で管理）"
            )
            self.edit_targets_button.pack(side="left", padx=(12, 0), ipadx=8, ipady=2)
            # モードに合わない個別見積ボタンは押せないようにする
            self.individual_button.configure(state="disabled")
            self.individual36_button.configure(state="normal")
        else:
            self.edit_targets_button.pack_forget()
            self.exclude_button.configure(state="normal")
            self.individual_button.configure(state="normal")
            self.individual36_button.configure(state="disabled")
            self._refresh_exclude_status()
            self._select_latest()

    def _select_latest(self) -> None:
        latest = latest_price_pdf()
        if latest:
            self.pdf_var.set(str(latest))
            self._write_log(f"価格表を検出しました：{latest.name}")
        else:
            self._write_log("「機種代金一覧表」にPDFがありません。PDFを入れるか［PDFを選ぶ］を押してください。")
        included = load_included_model_keys()
        self._refresh_exclude_status(included)
        if included:
            self._write_log(f"作成する機種：{len(included)}件（［作成する機種］で変更できます）")
        else:
            self._write_log("作成する機種が0件です（［作成する機種］で対象を選んでください）。")

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

    def _refresh_exclude_status(self, included: set[str] | None = None) -> None:
        keys = included if included is not None else load_included_model_keys()
        if keys:
            self.exclude_status_var.set(f"※いま {len(keys)} 機種を作成対象にしています")
        else:
            self.exclude_status_var.set("※作成対象が0件です（［作成する機種］で選んでください）")

    def _choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(title="機種代金表PDFを選択", filetypes=[("PDF", "*.pdf")])
        if selected:
            self.pdf_var.set(selected)

    def _refresh_device_master_for_picker(self) -> dict | None:
        """作成する機種一覧用に、選択中／最新の価格表から機種マスターを更新する。"""
        pdf_text = (self.pdf_var.get() or "").strip()
        pdf = Path(pdf_text) if pdf_text else latest_price_pdf()
        if pdf is None or not pdf.exists():
            if (DATA_DIR / "device_master.json").exists():
                return load_device_master()
            messagebox.showerror(
                "価格表がありません",
                "「機種代金一覧表」に価格表PDFを入れてから［作成する機種］を開いてください。",
            )
            return None
        try:
            device_master = parse_price_pdf(pdf)
        except Exception as exc:
            messagebox.showerror(
                "価格表の読取に失敗しました",
                f"{exc}\n価格表PDFを確認してください。",
            )
            return None
        save_json(DATA_DIR / "device_master.json", device_master)
        device_master = load_device_master(device_master)
        self.pdf_var.set(str(pdf))
        self._write_log(
            f"作成する機種一覧のため価格表を取り込みました：{pdf.name}"
            f"（販売中 {sum(1 for d in device_master['devices'] if d['status']=='販売中')} 機種）"
        )
        return device_master

    def _open_exclude_window(self) -> None:
        device_master = self._refresh_device_master_for_picker()
        if device_master is None:
            return
        devices = [d for d in device_master["devices"] if d["status"] == "販売中"]
        if not devices:
            messagebox.showerror("販売中機種がありません", "機種マスターを確認してください。")
            return

        win = tk.Toplevel(self)
        win.title("作成する機種")
        win.geometry("560x620")
        win.minsize(500, 480)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="作成する機種", font=("Yu Gothic UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="チェックした機種だけを一括作成・個別見積の一覧に出します。"
            "新しく価格表に載った機種は、ここでチェックするまで作りません。"
            "カテゴリ見出しをクリックすると開閉できます。"
            "「すべて選択」「すべて解除」も使えます。",
            wraplength=500,
        ).pack(anchor="w", pady=(2, 8))

        included = load_included_model_keys(device_master)
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
        sections = self._device_picker_sections(devices)

        def _section_title(label: str, count: int, expanded: bool) -> str:
            mark = "▼" if expanded else "▶"
            return f"{mark} {label}（{count}）"

        for section_label, section_devices, start_expanded in sections:
            section_wrap = ttk.Frame(list_frame)
            section_wrap.pack(fill="x", anchor="w", pady=(6, 0))
            body = ttk.Frame(section_wrap)
            expanded_var = tk.BooleanVar(value=start_expanded)
            header = ttk.Button(section_wrap, style="Toolbutton")

            def _refresh_header(
                btn: ttk.Button = header,
                label: str = section_label,
                count: int = len(section_devices),
                state: tk.BooleanVar = expanded_var,
            ) -> None:
                btn.configure(text=_section_title(label, count, state.get()))

            def _toggle(
                btn: ttk.Button = header,
                body_frame: ttk.Frame = body,
                state: tk.BooleanVar = expanded_var,
                label: str = section_label,
                count: int = len(section_devices),
            ) -> None:
                state.set(not state.get())
                if state.get():
                    body_frame.pack(fill="x", anchor="w", padx=(12, 0), pady=(2, 0))
                else:
                    body_frame.pack_forget()
                btn.configure(text=_section_title(label, count, state.get()))
                canvas.configure(scrollregion=canvas.bbox("all"))

            header.configure(command=_toggle)
            _refresh_header()
            header.pack(fill="x", anchor="w")
            header.bind("<MouseWheel>", _on_mousewheel)

            cat_keys: list[str] = []
            for device in section_devices:
                key = str(device["model_key"])
                var = tk.BooleanVar(value=key in included)
                vars_by_key[key] = var
                cat_keys.append(key)
                check = ttk.Checkbutton(
                    body,
                    text=str(device.get("model") or key),
                    variable=var,
                )
                check.pack(anchor="w", pady=1)
                check.bind("<MouseWheel>", _on_mousewheel)

            cat_toolbar = ttk.Frame(body)
            cat_toolbar.pack(anchor="w", pady=(2, 4))

            def _select_category(keys: list[str] = cat_keys, value: bool = True) -> None:
                for key in keys:
                    vars_by_key[key].set(value)

            ttk.Button(
                cat_toolbar,
                text="このカテゴリを選択",
                command=lambda keys=cat_keys: _select_category(keys, True),
            ).pack(side="left")
            ttk.Button(
                cat_toolbar,
                text="このカテゴリを解除",
                command=lambda keys=cat_keys: _select_category(keys, False),
            ).pack(side="left", padx=(6, 0))

            if start_expanded:
                body.pack(fill="x", anchor="w", padx=(12, 0), pady=(2, 0))

        def select_all() -> None:
            for var in vars_by_key.values():
                var.set(True)

        def clear_all() -> None:
            for var in vars_by_key.values():
                var.set(False)

        ttk.Button(toolbar, text="すべて選択", command=select_all).pack(side="left")
        ttk.Button(toolbar, text="すべて解除", command=clear_all).pack(side="left", padx=(8, 0))
        ttk.Button(
            toolbar,
            text="すべて開く",
            command=lambda: self._set_picker_sections_expanded(list_frame, True, canvas),
        ).pack(side="left", padx=(16, 0))
        ttk.Button(
            toolbar,
            text="すべて閉じる",
            command=lambda: self._set_picker_sections_expanded(list_frame, False, canvas),
        ).pack(side="left", padx=(8, 0))

        def save() -> None:
            selected = [key for key, var in vars_by_key.items() if var.get()]
            if not selected:
                if not messagebox.askyesno(
                    "作成対象が0件になります",
                    "1機種もチェックされていません。このまま保存すると一括作成は実行できません。保存しますか？",
                    parent=win,
                ):
                    return
            save_included_model_keys(selected)
            self._refresh_exclude_status(set(selected))
            self._write_log(f"作成する機種を更新しました：{len(selected)}件")
            messagebox.showinfo("保存しました", f"{len(selected)}機種を作成対象にしました。", parent=win)
            _unbind_wheel()
            win.destroy()

        ttk.Button(frame, text="保存", command=save).pack(anchor="w", pady=(12, 0), ipadx=20, ipady=4)

    @staticmethod
    def _device_display_sort_key(device: dict) -> tuple:
        """Sort by model family, then Pro before Pro Max, then capacity 256→512→1TB→2TB."""
        import re

        model = str(device.get("model") or "")
        match = re.search(r"\(([^)]+)\)\s*$", model)
        capacity = (match.group(1) if match else "").strip().lower().replace(" ", "")
        base = model[: match.start()] if match else model
        is_pro_max = "Pro Max" in base or "ProMax" in base.replace(" ", "")
        family = (
            base.replace(" Pro Max", " Pro")
            .replace("Pro Max", "Pro")
            .replace("ProMax", "Pro")
        )
        capacity_rank = {
            "1gb": 1,
            "5gb": 2,
            "20gb": 3,
            "50gb": 4,
            "64gb": 5,
            "128gb": 6,
            "256gb": 7,
            "512gb": 8,
            "1tb": 9,
            "2tb": 10,
        }.get(capacity, 500)
        return (family.lower(), 1 if is_pro_max else 0, capacity_rank, model.lower())

    @staticmethod
    def _device_picker_sections(
        devices: list[dict],
    ) -> list[tuple[str, list[dict], bool]]:
        """Return (section_label, devices, start_expanded) for the include picker.

        Temporary overlay models come first. Other models are grouped by category.
        """
        from quote_system.temporary_devices import temporary_model_keys

        temp_keys = temporary_model_keys()
        temp_devices = [d for d in devices if str(d.get("model_key") or "") in temp_keys]
        other_devices = [
            d for d in devices if str(d.get("model_key") or "") not in temp_keys
        ]
        temp_devices.sort(key=QuoteApp._device_display_sort_key)

        preferred = [
            "iPhone",
            "Android",
            "iPad",
            "AndroidTab",
            "ケータイ",
            "データ通信",
            "キッズフォン",
        ]
        by_category: dict[str, list[dict]] = {}
        for device in other_devices:
            category = str(device.get("category") or "").strip() or "その他"
            by_category.setdefault(category, []).append(device)
        for group in by_category.values():
            group.sort(key=QuoteApp._device_display_sort_key)

        ordered_categories = [c for c in preferred if c in by_category]
        ordered_categories.extend(
            sorted(c for c in by_category if c not in preferred)
        )

        sections: list[tuple[str, list[dict], bool]] = []
        if temp_devices:
            sections.append(("臨時追加（価格表PDF未反映）", temp_devices, True))
        for index, category in enumerate(ordered_categories):
            # Open the first normal category when there is no temporary block.
            start_open = (not temp_devices) and index == 0
            sections.append((category, by_category[category], start_open))
        return sections

    @staticmethod
    def _sort_devices_temp_first(devices: list[dict]) -> list[dict]:
        """Put temporary overlay models first (then keep remaining order)."""
        from quote_system.temporary_devices import temporary_model_keys

        temp_keys = temporary_model_keys()
        if not temp_keys:
            return list(devices)
        first = [d for d in devices if str(d.get("model_key") or "") in temp_keys]
        rest = [d for d in devices if str(d.get("model_key") or "") not in temp_keys]
        first.sort(key=QuoteApp._device_display_sort_key)
        return first + rest

    @staticmethod
    def _set_picker_sections_expanded(
        list_frame: ttk.Frame,
        expanded: bool,
        canvas: tk.Canvas,
    ) -> None:
        """Expand or collapse every category body under the picker list."""
        for section_wrap in list_frame.winfo_children():
            children = section_wrap.winfo_children()
            if len(children) < 2:
                continue
            header, body = children[0], children[1]
            text = str(header.cget("text") or "")
            # Keep the count suffix; swap only the marker.
            if text.startswith("▼ ") or text.startswith("▶ "):
                rest = text[2:]
            else:
                rest = text
            marker = "▼" if expanded else "▶"
            try:
                header.configure(text=f"{marker} {rest}")
            except tk.TclError:
                pass
            if expanded:
                body.pack(fill="x", anchor="w", padx=(12, 0), pady=(2, 0))
            else:
                body.pack_forget()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _open_individual_window(self, months: int | None = None) -> None:
        if months is None:
            months = self._installment_months()
        plan_master = load_json(DATA_DIR / "plans.json")
        included = load_included_model_keys()
        if months == 36:
            try:
                pdf36 = latest_installment_36_pdf()
                if pdf36 is None:
                    raise FileNotFoundError("36回PDFなし")
                master_36 = import_installment_36_master(pdf36)
                # 36回割賦は除外機能の対象外。installment_36_targets.json のみで絞る。
                devices = list(filter_36_target_devices(master_36))
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
            if IS_TM_SPECIAL:
                mode_label = "特例個別見積（36回・TM兼任事業部用）"
        elif months == 24:
            if not (DATA_DIR / "device_master.json").exists():
                messagebox.showerror(
                    "機種マスターがありません",
                    "先に通常（48回）で価格表PDFから一括作成（または機種取込）を実行してください。",
                )
                return
            device_master = load_device_master()
            with_24 = [
                d
                for d in device_master["devices"]
                if d.get("payment_24") is not None
            ]
            if included:
                devices = [d for d in with_24 if d.get("model_key") in included]
                if not devices:
                    # 作成する機種に24回対象が無い場合は、一覧にある24回機種をすべて出す
                    devices = with_24
            else:
                devices = with_24
            mode_label = "個別見積作成（24回割賦）"
            if IS_TM_SPECIAL:
                mode_label = "特例個別見積（24回・TM兼任事業部用）"
        else:
            if not (DATA_DIR / "device_master.json").exists():
                # Temporary overlays alone are enough for 48-mode individual.
                from quote_system.temporary_devices import temporary_devices_enabled

                if not temporary_devices_enabled():
                    messagebox.showerror(
                        "機種マスターがありません",
                        "先に価格表PDFから一括作成を実行してください。",
                    )
                    return
            device_master = load_device_master()
            devices = [
                d for d in device_master["devices"]
                if d["status"] == "販売中" and d.get("model_key") in included
            ]
            mode_label = "個別見積作成（通常48回）"
            if IS_TM_SPECIAL:
                mode_label = "特例個別見積（通常48回・TM兼任事業部用）"
        devices = self._sort_devices_temp_first(devices)
        models = [d["model"] for d in devices]
        if not models:
            if months == 24:
                messagebox.showerror(
                    "選択できる機種がありません",
                    "24回列がある機種が0件です。価格表PDFを取り込み直してください。",
                )
            else:
                messagebox.showerror(
                    "選択できる機種がありません",
                    "対象機種が0件です。作成する機種・対象JSON・価格表を確認してください。",
                )
            return

        win = tk.Toplevel(self)
        win.title(mode_label)
        if months == 36:
            if IS_TM_SPECIAL:
                win.geometry("720x980")
                win.minsize(660, 880)
            else:
                win.geometry("720x900")
                win.minsize(660, 800)
        elif IS_TM_SPECIAL:
            # 特例は注意文・IRSラジオ・初期費用注記が増えるため高めにする
            win.geometry("700x920")
            win.minsize(640, 860)
        else:
            win.geometry("680x780")
            win.minsize(620, 720)
        frame = ttk.Frame(win, padding=18)
        frame.pack(fill="both", expand=True)
        status_var = tk.StringVar(value="条件を選択して［PDF作成］を押してください。")
        # 作成ボタンは右上に固定表示（ウィンドウが縦に長くても隠れない）
        header = ttk.Frame(frame)
        header.pack(fill="x")
        ttk.Label(header, text=mode_label, font=("Yu Gothic UI", 17, "bold")).pack(side="left")
        create_button = ttk.Button(
            header,
            text="PDF作成",
            command=lambda: start(),
            style="Accent.TButton",
        )
        create_button.pack(side="right", ipadx=24, ipady=6)
        ttk.Label(
            frame,
            text="選択した条件だけを作成します。",
        ).pack(anchor="w", pady=(2, 2))
        if IS_TM_SPECIAL:
            ttk.Label(
                frame,
                text="※特例：標準の販売区分×プラン×容量×IRSセット制限を外しています（一括作成は通常ルールのまま）。",
                wraplength=620,
                foreground="#C00000",
            ).pack(anchor="w", pady=(0, 4))
        if months == 36:
            note_text = "※対象機種は installment_36_targets.json で管理します（作成する機種の指定は使いません）。"
        elif months == 24:
            note_text = (
                f"※価格表の24回列がある機種のみ。出力は output\\{QUOTE_OUTPUT_DIRNAME_24} です。"
            )
        else:
            note_text = "※［作成する機種］でチェックした機種が一覧に出ます。"
        ttk.Label(
            frame,
            text=note_text,
            wraplength=620,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            frame,
            textvariable=status_var,
            wraplength=620,
            foreground="#2B6CB0",
        ).pack(anchor="w", pady=(0, 12))

        # 36回割賦：機種はプルダウンではなくチェックボックスで複数選択する
        model_check_vars: dict[str, tk.BooleanVar] = {}
        if months == 36:
            model_box = ttk.LabelFrame(frame, text="作成する機種（複数選択可）", padding=10)
            model_box.pack(fill="x", pady=(0, 8))
            model_toolbar = ttk.Frame(model_box)
            model_toolbar.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

            def _set_all_models(value: bool) -> None:
                for var in model_check_vars.values():
                    var.set(value)
                on_device_selection_changed()

            ttk.Button(
                model_toolbar, text="すべて選択",
                command=lambda: _set_all_models(True),
            ).pack(side="left")
            ttk.Button(
                model_toolbar, text="すべて解除",
                command=lambda: _set_all_models(False),
            ).pack(side="left", padx=(8, 0))
            for index, name in enumerate(models):
                var = tk.BooleanVar(value=True)
                model_check_vars[name] = var
                row, column = divmod(index, 2)
                ttk.Checkbutton(
                    model_box, text=name, variable=var,
                    command=lambda: on_device_selection_changed(),
                ).grid(row=row + 1, column=column, sticky="w", padx=4, pady=1)
            model_box.columnconfigure(0, weight=1)
            model_box.columnconfigure(1, weight=1)

        fields = ttk.Frame(frame)
        fields.pack(fill="x")
        model_var = tk.StringVar(value=models[0])
        # SALES_COLUMNS は {販売区分名: PDF列Index} の辞書。選択肢はキー一覧を使う。
        sales_types = list(SALES_COLUMNS.keys())
        sales_var = tk.StringVar(value=sales_types[0])
        # TM特例個別: Biz → ライト → スーパー → ハイパー の順で見せる
        _tm_plan_order = ("biz_plus", "light", "super_light", "hyper_light")
        if IS_TM_SPECIAL:
            all_plan_name_to_id: dict[str, str] = {}
            for plan_id in _tm_plan_order:
                plan = plan_master["plans"].get(plan_id)
                if plan and plan.get("enabled"):
                    all_plan_name_to_id[str(plan["name"])] = plan_id
            for plan_id, plan in plan_master["plans"].items():
                if plan.get("enabled") and str(plan["name"]) not in all_plan_name_to_id:
                    all_plan_name_to_id[str(plan["name"])] = plan_id
        else:
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

        model_combo = None
        if months != 36:
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
        if IS_TM_SPECIAL:
            ttk.Label(
                ouchi_box,
                text="※特例：5GBでもSB光あり（おうち割）を作成できます",
                foreground="#555555",
            ).pack(side="left", padx=(12, 0))

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
        if IS_TM_SPECIAL:
            # 特例: プラン自動割当なし。なし／XS／S の排他ラジオ
            support_radio_var = tk.StringVar(value="none")
            support_box = ttk.LabelFrame(service_box, text="安心サポート（どれか1つ）", padding=8)
            support_box.pack(fill="x", pady=(0, 4))
            ttk.Radiobutton(
                support_box, text="安心サポートなし", variable=support_radio_var, value="none"
            ).pack(anchor="w")
            ttk.Radiobutton(
                support_box,
                text="安心サポートXS（税抜980円）",
                variable=support_radio_var,
                value="support_xs",
            ).pack(anchor="w")
            ttk.Radiobutton(
                support_box,
                text="安心サポートS（税抜1,480円）",
                variable=support_radio_var,
                value="support_s",
            ).pack(anchor="w")

            def current_support_plan_id() -> str | None:
                raw = support_radio_var.get()
                return None if raw == "none" else raw
        else:
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
            support_combo = ttk.Combobox(
                support_row,
                textvariable=support_var,
                values=list(support_display),
                state="readonly",
                width=30,
            )
            support_combo.pack(side="left")
            ttk.Label(
                service_box,
                text="※個別のみ：スーパー／ハイパーで「安心サポートなし」可"
                "（割引は維持・一括作成では不可）",
                wraplength=580,
                foreground="#555555",
            ).pack(anchor="w", pady=(4, 0))

            def current_support_plan_id() -> str | None:
                return support_display[support_var.get()]

        fee_box = ttk.LabelFrame(frame, text="初期費用（複数選択可）", padding=10)
        fee_box.pack(fill="x", pady=6)
        fee_special_var = tk.BooleanVar(value=True)
        fee_standard_var = tk.BooleanVar(value=False)
        fee_special_label = (
            "事務手数料免除＋初期費用4,500円（標準）"
            if IS_TM_SPECIAL
            else "事務手数料免除＋初期費用3,000円（標準）"
        )
        ttk.Checkbutton(
            fee_box, text=fee_special_label, variable=fee_special_var
        ).pack(anchor="w")
        ttk.Checkbutton(
            fee_box, text="事務手数料あり（税抜4,500円）", variable=fee_standard_var
        ).pack(anchor="w")
        if IS_TM_SPECIAL:
            ttk.Label(
                fee_box,
                text="※特例の標準は免除＋初期費用4,500円（税込4,950円）。通常版の3,000円とは異なります。",
                wraplength=580,
                foreground="#555555",
            ).pack(anchor="w", pady=(4, 0))

        def refresh_plans(*_args) -> None:
            nonlocal plan_name_to_id
            sales = sales_var.get()
            selected = _selected_devices()
            plan_name_to_id = {
                name: plan_id
                for name, plan_id in all_plan_name_to_id.items()
                if is_sales_plan_allowed(sales, plan_id, unrestricted=IS_TM_SPECIAL)
                and (
                    not selected
                    or all(
                        is_device_plan_allowed(device, plan_id)
                        for device in selected
                    )
                )
            }
            names = list(plan_name_to_id)
            plan_combo.configure(values=names)
            if not names:
                plan_var.set("")
                return
            if plan_var.get() not in plan_name_to_id:
                plan_var.set(names[0])
            refresh_capacities()

        def _selected_devices() -> list[dict]:
            if months == 36:
                names = {name for name, var in model_check_vars.items() if var.get()}
                return [d for d in devices if d["model"] in names]
            try:
                return [find_device(device_master, model_var.get())]
            except (KeyError, ValueError):
                return []

        def refresh_sales_types(*_args) -> None:
            """iPad／データ通信／AndroidTab では MNP・番号移行を選べない。"""
            selected = _selected_devices()
            all_types = list(SALES_COLUMNS.keys())
            if not selected:
                allowed = all_types
            else:
                allowed = [
                    sales
                    for sales in all_types
                    if all(
                        is_device_sales_type_allowed(device, sales)
                        for device in selected
                    )
                ]
            if not allowed:
                allowed = [
                    sales for sales in all_types
                    if sales not in {"MNP", "番号移行"}
                ]
            sales_combo.configure(values=allowed)
            if sales_var.get() not in allowed:
                sales_var.set(allowed[0] if allowed else "")
            refresh_plans()

        def on_device_selection_changed(*_args) -> None:
            refresh_sales_types()

        def refresh_capacities(*_args) -> None:
            selected_devices = _selected_devices()
            try:
                plan_id = plan_name_to_id[plan_var.get()]
                plan = plan_master["plans"][plan_id]
            except KeyError:
                return
            selected_any = False
            for name, check in capacity_checks.items():
                # 複数機種選択時は「どれか1機種でも使える容量」を選択可能にする
                allowed = (
                    name in plan["data_plans"]
                    and is_plan_data_plan_allowed(
                        plan_id, name, unrestricted=IS_TM_SPECIAL
                    )
                    and any(
                        is_device_data_plan_allowed(device, name, sales_var.get())
                        for device in selected_devices
                    )
                )
                check.configure(state="normal" if allowed else "disabled")
                if not allowed:
                    capacity_vars[name].set(False)
                elif not selected_any:
                    capacity_vars[name].set(True)
                    selected_any = True

        def completed(generated_files: int, output_dir) -> None:
            create_button.configure(state="normal")
            status_var.set(f"{generated_files}件のPDFを作成しました。")
            messagebox.showinfo("個別見積作成完了", status_var.get(), parent=win)
            if output_dir:
                _open_path(output_dir)

        def failed(detail: str) -> None:
            create_button.configure(state="normal")
            status_var.set("作成を停止しました。条件を確認してください。")
            messagebox.showerror("個別見積作成エラー", detail, parent=win)

        def worker(target_models: list[str]) -> None:
            try:
                fee_modes = [
                    mode for mode, enabled in (
                        ("special_3000", fee_special_var.get()),
                        ("standard", fee_standard_var.get()),
                    ) if enabled
                ]
                selected_capacities = [
                    name for name, var in capacity_vars.items() if var.get()
                ]
                total_files = 0
                output_dir = None
                for target in target_models:
                    device = find_device(device_master, target)
                    # 機種ごとに使える容量だけ渡す（複数機種の混在選択に対応）
                    data_plans = [
                        name for name in selected_capacities
                        if is_device_data_plan_allowed(device, name, sales_var.get())
                    ]
                    if not data_plans:
                        continue
                    result = run_individual(
                        model=target,
                        sales_type=sales_var.get(),
                        plan_id=plan_name_to_id[plan_var.get()],
                        data_plans=data_plans,
                        ouchi_options=[
                            option for option, enabled in (
                                (False, ouchi_none_var.get()), (True, ouchi_yes_var.get())
                            ) if enabled
                        ],
                        include_ips_subscription=ips_subscription_var.get(),
                        include_upfront_lump=ips_upfront_lump_var.get(),
                        include_upfront_running=ips_upfront_running_var.get(),
                        include_no_ips=ips_none_var.get(),
                        support_plan_id=current_support_plan_id(),
                        department=self.department_var.get(),
                        initial_fee_modes=fee_modes,
                        installment_months=months,
                        unrestricted_individual=IS_TM_SPECIAL,
                    )
                    total_files += result.generated_files
                    output_dir = result.output_dir
                if total_files == 0:
                    raise ValueError(
                        "作成できたPDFが0件です。機種・データ容量の選択を確認してください。"
                    )
            except Exception as exc:
                self.after(0, failed, str(exc))
                return
            self.after(0, completed, total_files, output_dir)

        def start() -> None:
            if months == 36:
                target_models = [
                    name for name, var in model_check_vars.items() if var.get()
                ]
                if not target_models:
                    messagebox.showerror(
                        "機種が未選択です",
                        "作成する機種にチェックを入れてください。",
                        parent=win,
                    )
                    return
            else:
                target_models = [model_var.get()]
            create_button.configure(state="disabled")
            status_var.set(f"PDFを作成しています…（{len(target_models)}機種）")
            threading.Thread(target=worker, args=(target_models,), daemon=True).start()

        if model_combo is not None:
            model_combo.bind("<<ComboboxSelected>>", on_device_selection_changed)
            model_combo.bind("<FocusOut>", on_device_selection_changed)
        sales_combo.bind("<<ComboboxSelected>>", refresh_plans)
        plan_combo.bind("<<ComboboxSelected>>", refresh_capacities)
        refresh_sales_types()

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
                master = load_device_master()
                on_sale = [
                    d for d in master.get("devices", []) if d.get("status") == "販売中"
                ]
                included = load_included_model_keys(master)
                if on_sale and not included:
                    messagebox.showerror(
                        "作成対象がありません",
                        "作成する機種が1件も選ばれていません。"
                        "［作成する機種］で対象を選んでください。",
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
                include_upfront_lump=self.upfront_mode_var.get() == "lump",
                include_upfront_running=self.upfront_mode_var.get() == "monthly_as_running",
                include_no_ips=self.no_ips_var.get(),
                include_mnp_shinki_irs=self.mnp_shinki_irs_var.get(),
                include_standard_initial_fee=self.standard_fee_var.get(),
                include_light_plan=self.light_plan_var.get(),
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
