"""Offline scientific plotting desktop with self-contained portable packaging."""
from pathlib import Path
import os
import sys

from app_paths import locations
RESOURCE, BASE, RUNTIME = locations(__file__,sys.executable,getattr(sys,'frozen',False),os.environ.get('PLOTA_HOME'))
RUNTIME.mkdir(parents=True, exist_ok=True)
for _name in ('MPLCONFIGDIR', 'TEMP', 'TMP', 'XDG_CACHE_HOME'):
    _folder = RUNTIME / _name.lower()
    _folder.mkdir(exist_ok=True)
    os.environ[_name] = str(_folder)
sys.dont_write_bytecode = True

import argparse
import copy
import shutil
import json
import traceback
from types import SimpleNamespace
from datetime import datetime
if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from tkinterdnd2 import TkinterDnD, DND_FILES, COPY, REFUSE_DROP
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from dataio import load_file
from engine import new_project, new_panel, new_layer, render_project, dimensions_for_ratio, ratio_for_dimensions
from engine import STYLE_NAMES, layer_style
from exporter import export_bundle, save_project, load_project

COLORS = ['#2563eb', '#e67e22', '#0d9488', '#9333ea', '#dc2626', '#475569']
KINDS = {'折线': 'line', '散点': 'scatter', '矩阵热力图': 'matrix_heatmap', '矩阵等高线': 'matrix_contour'}
FITS = {'无拟合': 'none', '线性拟合': 'linear', '二次拟合': 'quadratic'}


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title('Plota')
        self._brand_icon=None
        icon_file=RESOURCE/'assets'/'plota.ico'
        if icon_file.exists():
            self.iconbitmap(default=str(icon_file))
            from PIL import Image, ImageTk
            with Image.open(icon_file) as icon_image:
                self._brand_icon=ImageTk.PhotoImage(icon_image.resize((40,40),Image.Resampling.LANCZOS),master=self)
        self.geometry(f'{min(1450, self.winfo_screenwidth() - 40)}x{min(940, self.winfo_screenheight() - 80)}')
        self.minsize(min(1150, self.winfo_screenwidth() - 40), min(740, self.winfo_screenheight() - 80))
        self.configure(bg='#ffffff')
        self.project = new_project()
        self.datasets = {}
        self.panel_index = 0
        self.layer_index = None
        self.dataset_ids = []
        self.last_error = None
        self._drop_active=False
        self._drop_bounds=None
        self._syncing_global=False
        self._build()
        self.sync_global()
        self.sync_panels()
        self.refresh()

    def safe(self, fn):
        def run(*args):
            try:
                return fn(*args)
            except Exception as exc:
                self.report_error(exc)
        return run

    def report_error(self, exc):
        self.last_error = str(exc)
        self.status_var.set('操作未完成：' + str(exc))
        messagebox.showerror('请检查输入', str(exc), parent=self)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 9), background='#ffffff', foreground='#252525')
        style.configure('TButton', padding=(7, 4), background='#f7f7f7', bordercolor='#d7d7d7', relief='flat')
        style.map('TButton', background=[('active', '#eeeeee'), ('pressed', '#e6e6e6')])
        style.configure('Accent.TButton', padding=(7, 4), background='#f7f7f7', foreground='#252525', bordercolor='#d7d7d7')
        style.map('Accent.TButton', background=[('active', '#eeeeee')])
        style.configure('TNotebook', borderwidth=0, tabmargins=0)
        style.configure('TNotebook.Tab', padding=(16, 7), background='#f7f7f7', borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', '#ffffff')], foreground=[('selected', '#111111')])
        style.configure('TEntry', fieldbackground='#ffffff', bordercolor='#d4d4d4', padding=3)
        style.configure('TCombobox', fieldbackground='#ffffff', background='#f5f5f5', bordercolor='#d4d4d4', padding=3, arrowsize=12)
        style.map('TCombobox', fieldbackground=[('readonly', '#ffffff')], selectbackground=[('readonly', '#ffffff')], selectforeground=[('readonly', '#252525')])
        self.editor = ttk.Frame(self)
        tools = ttk.Frame(self.editor, padding=(15, 5))
        tools.pack(fill='x')
        ttk.Label(tools, text='Plota', font=('Segoe UI', 15)).pack(side='left', padx=(0, 24))
        for label, command in [('导入', self.import_dialog), ('打开', self.open_dialog), ('保存', self.save_dialog), ('导出', self.export_dialog)]:
            ttk.Button(tools, text=label, width=5, command=self.safe(command)).pack(side='left', padx=(0, 5))
        ttk.Button(tools, text='首页', width=5, command=self.show_home).pack(side='right', padx=(7, 0))
        ttk.Button(tools, text='演示', width=5, command=self.safe(self.load_demo)).pack(side='right')
        ttk.Separator(self.editor).pack(fill='x')
        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(self.editor, textvariable=self.status_var, anchor='w', padding=(14, 5), foreground='#737373').pack(side='bottom', fill='x')
        split = ttk.Panedwindow(self.editor, orient='horizontal')
        split.pack(fill='both', expand=True)
        left = ttk.Frame(split, width=340)
        split.add(left, weight=0)
        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill='both', expand=True)
        data = self.scroll_tab('数据')
        panel = self.scroll_tab('图形')
        page = self.scroll_tab('页面')
        self.build_data(data)
        self.build_panel(panel)
        self.build_global(page)
        right = ttk.Frame(split, padding=(10, 4, 8, 0))
        split.add(right, weight=1)
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor='white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self._preview_fit_job = None
        for event_name in ('<Map>', '<Configure>'):
            self.canvas.get_tk_widget().bind(event_name, self._queue_preview_fit, add='+')
        self.toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.configure(background='#ffffff')
        for child in self.toolbar.winfo_children():
            try:
                child.configure(background='#ffffff')
            except tk.TclError:
                pass
        self.toolbar.pack(side='bottom', fill='x')
        ttk.Button(self.toolbar, text='刷新', width=5, command=self.safe(self.refresh)).pack(side='right', padx=5)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.build_home()
        self.show_home()

    def build_home(self):
        self.home = tk.Canvas(self, bg='#f0efed', highlightthickness=0, takefocus=True)
        self.home.bind('<Configure>', self._draw_home)
        self.home.bind('<Return>', self.safe(lambda event: self.import_dialog()))
        self.home.bind('<Button-1>', lambda event: self.home.focus_set())
        self.home_select = tk.Button(self.home, text='选择文件', command=self.safe(self.import_dialog), bg='#ffffff', fg='#454545', activebackground='#ffffff', activeforeground='#111111', relief='flat', borderwidth=0, cursor='hand2', font=('Microsoft YaHei UI', 10, 'underline'))
        for widget in (self.home,self.home_select):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<DropEnter>>',self.drop_position)
            widget.dnd_bind('<<DropPosition>>',self.drop_position)
            widget.dnd_bind('<<DropLeave>>',self.drop_leave)
            widget.dnd_bind('<<Drop>>',self.drop_files)

    def drop_position(self,event):
        bounds=self._drop_bounds
        x=float(event.x_root)-self.home.winfo_rootx()
        y=float(event.y_root)-self.home.winfo_rooty()
        inside=bool(bounds and bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3])
        if inside!=self._drop_active:
            self._drop_active=inside
            self._draw_home()
        return COPY if inside else REFUSE_DROP

    def drop_leave(self,event=None):
        self._drop_active=False
        self._draw_home()

    def drop_files(self,event):
        self._drop_active=False
        try:
            paths=list(self.tk.splitlist(event.data))
            if not paths or any(not Path(p).is_file() for p in paths):
                raise ValueError('请拖入数据文件，不能拖入文件夹。')
            self.import_paths(paths)
            return COPY
        except Exception as exc:
            self.report_error(exc)
            return REFUSE_DROP

    def show_home(self):
        self.editor.pack_forget()
        self.home.pack(fill='both', expand=True)
        self.home.focus_set()
        self._draw_home()

    def _show_editor(self):
        self.home.pack_forget()
        self.editor.pack(fill='both', expand=True)
        self._queue_preview_fit()

    def _draw_home(self, event=None):
        c = self.home
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        middle = w / 2
        ink, muted = '#252522', '#777772'
        brand_y = max(110, h * .23)
        mark_x = middle - 96
        if self._brand_icon is not None:
            c.create_image(mark_x+17,brand_y,image=self._brand_icon)
        else:
            c.create_line(mark_x, brand_y - 17, mark_x, brand_y + 15, mark_x + 32, brand_y + 15, fill=ink, width=2)
            c.create_line(mark_x + 5, brand_y + 6, mark_x + 14, brand_y - 6, mark_x + 23, brand_y, mark_x + 33, brand_y - 13, fill=ink, width=2)
        c.create_text(middle + 25, brand_y, text='Plota', font=('Segoe UI', 25), fill=ink)
        card_w = min(760, w - 110)
        x0, x1 = middle - card_w / 2, middle + card_w / 2
        y0 = max(210, h * .36)
        y1 = y0 + 225
        self._drop_bounds=(x0,y0,x1,y1)
        radius = 17
        points = [x0 + radius, y0, x1 - radius, y0, x1, y0, x1, y0 + radius, x1, y1 - radius, x1, y1, x1 - radius, y1, x0 + radius, y1, x0, y1, x0, y1 - radius, x0, y0 + radius, x0, y0]
        c.create_polygon(points, smooth=True, splinesteps=24, fill='#f9f9f7' if self._drop_active else '#ffffff', outline='#575750' if self._drop_active else '#d8d7d3', width=1, tags='import')
        fy = y0 + 33
        c.create_line(middle - 17, fy, middle + 7, fy, middle + 18, fy + 11, middle + 18, fy + 44, middle - 17, fy + 44, middle - 17, fy, fill='#9a9991', width=1.4, tags='import')
        c.create_line(middle + 7, fy, middle + 7, fy + 11, middle + 18, fy + 11, fill='#9a9991', width=1.4, tags='import')
        for offset, length in [(22, 22), (29, 22), (36, 13)]:
            c.create_line(middle - 10, fy + offset, middle - 10 + length, fy + offset, fill='#aaa99f', width=1, tags='import')
        c.create_text(middle, y0 + 109, text='拖入数据文件', font=('Microsoft YaHei UI', 15, 'bold'), fill=ink, tags='import')
        c.create_window(middle, y0 + 153, window=self.home_select)
        c.create_text(middle, y0 + 191, text='.out  ·  .xlsx  ·  .csv  ·  .txt', font=('Segoe UI', 9), fill=muted, tags='import')
        for tag, callback in [('import', self.import_dialog), ('example', self.load_demo), ('open', self.open_dialog)]:
            c.tag_bind(tag, '<Button-1>', self.safe(lambda event, command=callback: command()))
            c.tag_bind(tag, '<Enter>', lambda event: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda event: c.configure(cursor=''))
        c.create_text(middle, y1 + 49, text='试用示例', font=('Microsoft YaHei UI', 10), fill='#5e5e58', tags='example')
        c.create_text(middle, y1 + 91, text='打开项目', font=('Microsoft YaHei UI', 9), fill=muted, tags='open')
        if self.datasets:
            c.create_text(middle, y1 + 130, text='返回编辑', font=('Microsoft YaHei UI', 9), fill=muted, tags='resume')
            c.tag_bind('resume', '<Button-1>', lambda event: self._show_editor())
            c.tag_bind('resume', '<Enter>', lambda event: c.configure(cursor='hand2'))
            c.tag_bind('resume', '<Leave>', lambda event: c.configure(cursor=''))

    def scroll_tab(self, title):
        shell = ttk.Frame(self.notebook)
        self.notebook.add(shell, text=title)
        canvas = tk.Canvas(shell, highlightthickness=0, bg='#ffffff', width=330)
        bar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        frame = ttk.Frame(canvas, padding=(12, 10))
        window = canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        def wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), 'units')
        frame.bind('<Enter>', lambda e: canvas.bind_all('<MouseWheel>', wheel))
        frame.bind('<Leave>', lambda e: canvas.unbind_all('<MouseWheel>'))
        return frame

    def group(self, parent, text):
        shell = ttk.Frame(parent)
        shell.pack(fill='x', pady=(0, 15))
        if text:
            ttk.Label(shell, text=text, font=('Microsoft YaHei UI', 9, 'bold'), foreground='#666666').pack(anchor='w', pady=(0, 6))
        box = ttk.Frame(shell)
        box.pack(fill='x')
        box.columnconfigure(1, weight=1)
        return box

    def popup(self, title, width=370, height=700):
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry(f'{width}x{min(height, self.winfo_screenheight() - 100)}')
        window.withdraw()
        window.transient(self)
        window.protocol('WM_DELETE_WINDOW', window.withdraw)
        return window

    def show_popup(self, window):
        window.deiconify()
        window.lift()

    def field(self, parent, row, text, default='', values=None, width=15):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
        var = tk.StringVar(value=str(default))
        widget = ttk.Combobox(parent, textvariable=var, values=values, width=width, state='readonly') if values else ttk.Entry(parent, textvariable=var, width=width)
        widget.grid(row=row, column=1, sticky='ew', pady=3)
        return var, widget

    def check(self, parent, row, text, default=False):
        var = tk.BooleanVar(value=default)
        ttk.Checkbutton(parent, text=text, variable=var).grid(row=row, column=0, columnspan=2, sticky='w', pady=3)
        return var

    def build_data(self, parent):
        self.import_options = self.popup('导入设置', height=250)
        import_content = ttk.Frame(self.import_options, padding=14)
        import_content.pack(fill='both', expand=True)
        opts = self.group(import_content, '导入设置')
        self.header_var, header_entry = self.field(opts, 0, '表头', 'auto', ['auto', 'none', '0', '1', '2', '3', '4', '5'])
        header_entry.configure(state='normal')
        self.skip_var, _ = self.field(opts, 1, '跳过行数', '0')
        self.delim_var, _ = self.field(opts, 2, '分隔符', 'auto', ['auto', ',', 'tab', 'whitespace', ';', '|'])
        self.encoding_var, _ = self.field(opts, 3, '编码', 'auto', ['auto', 'utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'latin1'])
        box = self.group(parent, '')
        self.dataset_var, self.dataset_combo = self.field(box, 0, '文件', '', [''])
        self.dataset_combo.bind('<<ComboboxSelected>>', self.safe(lambda e: self.dataset_changed()))
        self.info_var = tk.StringVar(value='未导入')
        ttk.Label(box, textvariable=self.info_var, foreground='#737373').grid(row=1, column=0, columnspan=2, sticky='w', pady=(2, 7))
        self.x_var, self.x_combo = self.field(box, 2, 'X', '', [''])
        ttk.Label(box, text='Y · 多选').grid(row=3, column=0, sticky='nw', pady=4)
        self.y_list = tk.Listbox(box, selectmode='extended', height=5, exportselection=False, relief='flat', highlightthickness=1, highlightbackground='#dedede', selectbackground='#e5e5e5', selectforeground='#111111', font=('Segoe UI', 9))
        self.y_list.grid(row=3, column=1, sticky='ew', pady=3)
        self.kind_var, _ = self.field(box, 4, '类型', '折线', list(KINDS))
        ttk.Button(box, text='添加图层', command=self.safe(self.add_layers)).grid(row=5, column=0, columnspan=2, sticky='ew', pady=(7, 5))
        more = ttk.Frame(box)
        more.grid(row=6, column=0, columnspan=2, sticky='ew')
        for index, (text, callback) in enumerate([('数据表', self.show_data), ('详情', self.show_details), ('导入设置', lambda: self.show_popup(self.import_options))]):
            more.columnconfigure(index, weight=1, uniform='actions')
            ttk.Button(more, text=text, width=5, command=self.safe(callback)).grid(row=0, column=index, sticky='ew', padx=(0, 3))
        layers = self.group(parent, '图层')
        self.layer_list = tk.Listbox(layers, height=4, exportselection=False, relief='flat', highlightthickness=1, highlightbackground='#dedede', selectbackground='#e5e5e5', selectforeground='#111111', font=('Segoe UI', 9))
        self.layer_list.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.layer_list.bind('<<ListboxSelect>>', self.safe(lambda e: self.layer_changed()))
        self.style_window = self.popup('图层样式', width=390, height=840)
        self.layer_list.bind('<Double-Button-1>', lambda e: self.show_popup(self.style_window))
        ttk.Button(layers, text='样式', command=lambda: self.show_popup(self.style_window)).grid(row=1, column=0, sticky='ew', pady=7, padx=(0, 4))
        ttk.Button(layers, text='删除', command=self.safe(self.remove_layer)).grid(row=1, column=1, sticky='ew', pady=7)
        content = ttk.Frame(self.style_window, padding=14)
        content.pack(fill='both', expand=True)
        style = self.group(content, '图层样式')
        self.label_var, _ = self.field(style, 0, '图例')
        self.color_var, _ = self.field(style, 1, '颜色', '#2563eb')
        ttk.Button(style, text='选色', command=self.pick_color).grid(row=2, column=1, sticky='e')
        self.lw_var, _ = self.field(style, 3, '线宽', '1.5')
        self.ls_var, _ = self.field(style, 4, '线型', '-', ['-', '--', '-.', ':'])
        self.marker_var, _ = self.field(style, 5, '标记', '无', ['无', 'o', 's', '^', 'v', 'D', '.', 'x', '+'])
        self.ms_var, _ = self.field(style, 6, '标记大小', '4')
        self.fit_var, _ = self.field(style, 7, '拟合', '无拟合', list(FITS))
        self.cmap_var, _ = self.field(style, 8, '色图', 'viridis', ['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'coolwarm', 'RdBu_r', 'Greys'])
        self.bins_var, _ = self.field(style, 9, '等高线级数', '40')
        self.row_start_var, _ = self.field(style, 10, '起始行 / 0 基')
        self.row_end_var, _ = self.field(style, 11, '终止行 / 不含')
        self.col_start_var, _ = self.field(style, 12, '起始列 / 0 基')
        self.col_end_var, _ = self.field(style, 13, '终止列 / 不含')
        ttk.Label(style, text='矩阵范围留空 = 全部', foreground='#737373').grid(row=14, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Button(style, text='应用', command=self.safe(self.apply_layer)).grid(row=15, column=0, columnspan=2, sticky='ew', pady=7)

    def show_details(self):
        ds = self.selected_dataset()
        details = [ds.name, str(ds.source), f'{len(ds.frame):,} 行 × {len(ds.frame.columns)} 列']
        if ds.meta.get('time_formula'):
            details.append('Time_ps: ' + str(ds.meta['time_formula']))
        details.extend(str(w) for w in ds.meta.get('warnings', []))
        messagebox.showinfo('详情', '\n\n'.join(details), parent=self)

    def build_panel(self, parent):
        box = self.group(parent, '布局')
        self.rows_var, _ = self.field(box, 0, '行数', '1')
        self.cols_var, _ = self.field(box, 1, '列数', '1')
        self.panel_list = tk.Listbox(box, height=4, exportselection=False, relief='flat', highlightthickness=1, highlightbackground='#dedede', selectbackground='#e5e5e5', selectforeground='#111111', font=('Segoe UI', 9))
        self.panel_list.grid(row=2, column=0, columnspan=2, sticky='ew', pady=7)
        self.panel_list.bind('<<ListboxSelect>>', self.safe(lambda e: self.panel_changed()))
        buttons = ttk.Frame(box)
        buttons.grid(row=3, column=0, columnspan=2, sticky='ew')
        ttk.Button(buttons, text='添加子图', command=self.safe(self.add_panel)).pack(side='left', expand=True, fill='x', padx=(0, 5))
        ttk.Button(buttons, text='删除', command=self.safe(self.remove_panel)).pack(side='left', expand=True, fill='x')
        self.row_var, _ = self.field(box, 4, '起始行 / 1 基', '1')
        self.col_var, _ = self.field(box, 5, '起始列 / 1 基', '1')
        self.rowspan_var, _ = self.field(box, 6, '跨行数', '1')
        self.colspan_var, _ = self.field(box, 7, '跨列数', '1')
        box = self.group(parent, '坐标')
        self.title_var, _ = self.field(box, 0, '标题')
        self.xlabel_var, _ = self.field(box, 1, 'X 名称')
        self.ylabel_var, _ = self.field(box, 2, 'Y 名称')
        self.xlim_var, _ = self.field(box, 3, 'X 范围')
        self.ylim_var, _ = self.field(box, 4, 'Y 范围')
        self.clim_var, _ = self.field(box, 5, '色标范围')
        self.xlog_var = self.check(box, 6, 'X 对数')
        self.ylog_var = self.check(box, 7, 'Y 对数')
        self.grid_var = self.check(box, 8, '网格')
        self.legend_var = self.check(box, 9, '图例', True)
        self.letter_var = self.check(box, 10, '子图编号', True)
        self.sharex_var = self.check(box, 11, '共享 X')
        self.sharey_var = self.check(box, 12, '共享 Y')
        ttk.Button(box, text='应用', style='Accent.TButton', command=self.safe(self.apply_panel)).grid(row=13, column=0, columnspan=2, sticky='ew', pady=8)

    def build_global(self, parent):
        box = self.group(parent, '页面')
        self.ratio_var, _ = self.field(box, 0, '画布比例', '4:3', ['16:9','1:1','4:3','自定义'])
        self.width_var, _ = self.field(box, 1, '宽度 / mm', '180')
        self.height_var, self.height_entry = self.field(box, 2, '高度 / mm', '135')
        self.dpi_var, _ = self.field(box, 3, 'DPI', '300')
        self.font_var, _ = self.field(box, 4, '字体', '自动', ['自动', 'DejaVu Sans', 'Arial', 'Times New Roman', 'Microsoft YaHei', 'SimHei'])
        self.fontsize_var, _ = self.field(box, 5, '字号 / pt', '10')
        self.style_var, _ = self.field(box, 6, '风格', 'Science', list(STYLE_NAMES))
        ttk.Button(box, text='应用', style='Accent.TButton', command=self.safe(self.apply_global)).grid(row=7, column=0, columnspan=2, sticky='ew', pady=8)
        self.ratio_var.trace_add('write',self.update_ratio)
        self.width_var.trace_add('write',self.update_ratio)

    def update_ratio(self,*args):
        if self._syncing_global:
            return
        custom=self.ratio_var.get()=='自定义'
        self.height_entry.configure(state='normal' if custom else 'readonly')
        if not custom:
            try:
                _,height=dimensions_for_ratio(self.width_var.get(),self.height_var.get(),self.ratio_var.get())
                self.height_var.set(f'{height:.10g}')
            except ValueError:
                pass

    def selected_dataset(self):
        index = self.dataset_combo.current()
        if index < 0 or index >= len(self.dataset_ids):
            raise ValueError('请先导入并选择一个数据集。')
        return self.datasets[self.dataset_ids[index]]

    def import_paths(self, paths):
        header = self.header_var.get()
        if header not in ('auto', 'none'):
            header = int(header)
        delimiter = {'tab': '\t', 'whitespace': r'\s+'}.get(self.delim_var.get(), self.delim_var.get())
        loaded = []
        for path in paths:
            path = Path(path).resolve()
            if path.suffix.lower() == '.data':
                raise ValueError('不支持 LAMMPS .data，请选择热力学输出 .out 文件。')
            if not path.is_relative_to(RUNTIME.resolve()):
                imported = RUNTIME / 'imported' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                imported.mkdir(parents=True, exist_ok=True)
                local_path = imported / path.name
                shutil.copy2(path, local_path)
                path = local_path
            loaded.extend(load_file(path, header=header, skiprows=int(self.skip_var.get()), delimiter=delimiter, encoding=self.encoding_var.get()))
        for dataset in loaded:
            self.datasets[dataset.id] = dataset
        self.sync_datasets(loaded[0].id if loaded else None)
        if loaded:
            self._show_editor()
        warnings = [str(w) for ds in loaded for w in ds.meta.get('warnings', [])]
        self.status_var.set(f'{len(self.datasets)} 个数据集 · {len(self.project["panels"])} 幅图')
        return loaded

    def import_dialog(self):
        paths = filedialog.askopenfilenames(parent=self, initialdir=str(BASE), title='导入数据（可多选）', filetypes=[('科研数据', '*.xlsx *.xls *.csv *.txt *.out'), ('Excel', '*.xlsx *.xls'), ('CSV / TXT', '*.csv *.txt'), ('LAMMPS 输出', '*.out')])
        if paths:
            self.import_paths(paths)

    def sync_datasets(self, selected=None):
        self.dataset_ids = list(self.datasets)
        self.dataset_combo['values'] = [f'{i + 1}. {ds.name}' for i, ds in enumerate(self.datasets.values())]
        if self.dataset_ids:
            self.dataset_combo.current(self.dataset_ids.index(selected) if selected in self.dataset_ids else 0)
            self.dataset_changed()

    def dataset_changed(self):
        ds = self.selected_dataset()
        cols = [str(c) for c in ds.frame.columns]
        self.x_combo['values'] = cols
        self.x_var.set('Time_ps' if 'Time_ps' in cols else (cols[0] if cols else ''))
        ys = [c for c in cols if c != self.x_var.get()]
        self.y_list.delete(0, 'end')
        for col in ys:
            self.y_list.insert('end', col)
        if ys:
            index = ys.index('c_mobile_temp') if 'c_mobile_temp' in ys else 0
            self.y_list.selection_set(index)
        warning_count = len(ds.meta.get('warnings', []))
        self.info_var.set(f'{len(ds.frame):,} × {len(cols)}' + (f' · {warning_count} 条提示' if warning_count else ''))

    def show_data(self):
        ds = self.selected_dataset()
        window = tk.Toplevel(self)
        window.title(ds.name + ' · 数据预览（前 100 行）')
        window.geometry('1020x480')
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=list(ds.frame.columns), show='headings')
        for col in ds.frame.columns:
            tree.heading(col, text=col)
            tree.column(col, width=125, stretch=False)
        for row in ds.frame.head(100).itertuples(index=False, name=None):
            tree.insert('', 'end', values=[f'{v:.7g}' if isinstance(v, float) else str(v) for v in row])
        y = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        x = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        y.pack(side='right', fill='y')
        x.pack(side='bottom', fill='x')
        tree.pack(fill='both', expand=True)

    def add_layers(self):
        ds = self.selected_dataset()
        kind = KINDS[self.kind_var.get()]
        ys = [self.y_list.get(i) for i in self.y_list.curselection()]
        if kind.startswith('matrix_'):
            ys = ['']
        if not ys:
            raise ValueError('请至少选择一个 Y 列。')
        panel = self.project['panels'][self.panel_index]
        original = copy.deepcopy(panel['layers'])
        try:
            for y in ys:
                layer = new_layer(ds.id, self.x_var.get(), y)
                layer.update(kind=kind, **layer_style(self.project,len(panel['layers'])))
                panel['layers'].append(layer)
            self.refresh()
        except Exception:
            panel['layers'] = original
            raise
        self.sync_layers(len(panel['layers']) - 1)

    def sync_layers(self, index=None):
        layers = self.project['panels'][self.panel_index]['layers']
        self.layer_list.delete(0, 'end')
        for i, layer in enumerate(layers):
            self.layer_list.insert('end', f'{i + 1}. {layer["label"] or "矩阵"}')
        self.layer_index = None
        if layers:
            index = min(index if index is not None else 0, len(layers) - 1)
            self.layer_list.selection_set(index)
            self.layer_changed()

    def layer_changed(self):
        selected = self.layer_list.curselection()
        if not selected:
            return
        self.layer_index = selected[0]
        layer = self.project['panels'][self.panel_index]['layers'][self.layer_index]
        for var, key in [(self.label_var, 'label'), (self.color_var, 'color'), (self.lw_var, 'linewidth'), (self.ls_var, 'linestyle'), (self.ms_var, 'markersize'), (self.cmap_var, 'cmap'), (self.bins_var, 'bins')]:
            var.set(str(layer[key]))
        for key in ('row_start', 'row_end', 'col_start', 'col_end'):
            getattr(self, key + '_var').set('' if layer.get(key) is None else str(layer[key]))
        self.marker_var.set(layer['marker'] or '无')
        self.fit_var.set(next(k for k, v in FITS.items() if v == layer['fit']))
        self.kind_var.set(next(k for k, v in KINDS.items() if v == layer['kind']))

    def pick_color(self):
        color = colorchooser.askcolor(color=self.color_var.get(), parent=self)[1]
        if color:
            self.color_var.set(color)

    def apply_layer(self):
        if self.layer_index is None:
            raise ValueError('请先选择图层。')
        layers = self.project['panels'][self.panel_index]['layers']
        previous = copy.deepcopy(layers[self.layer_index])
        updated = dict(previous, kind=KINDS[self.kind_var.get()], label=self.label_var.get(), color=self.color_var.get(), linewidth=float(self.lw_var.get()), linestyle=self.ls_var.get(), markersize=float(self.ms_var.get()), marker='' if self.marker_var.get() == '无' else self.marker_var.get(), fit=FITS[self.fit_var.get()], cmap=self.cmap_var.get(), bins=int(self.bins_var.get()))
        for key in ('row_start', 'row_end', 'col_start', 'col_end'):
            value = getattr(self, key + '_var').get().strip()
            updated[key] = int(value) if value else None
        if updated['linewidth'] <= 0 or updated['markersize'] <= 0 or updated['bins'] < 2:
            raise ValueError('线宽、标记大小必须大于 0；等高线级数至少为 2。')
        layers[self.layer_index] = updated
        try:
            self.refresh()
        except Exception:
            layers[self.layer_index] = previous
            raise
        self.sync_layers(self.layer_index)

    def remove_layer(self):
        if self.layer_index is not None:
            self.project['panels'][self.panel_index]['layers'].pop(self.layer_index)
            self.sync_layers()
            self.refresh()

    def sync_global(self):
        self._syncing_global=True
        self.style_var.set(next((label for label,value in STYLE_NAMES.items() if value==self.project.get('style','classic')), '经典'))
        for var, key in [(self.width_var, 'width_mm'), (self.height_var, 'height_mm'), (self.dpi_var, 'dpi'), (self.font_var, 'font'), (self.fontsize_var, 'fontsize'), (self.rows_var, 'rows'), (self.cols_var, 'cols')]:
            var.set(str(self.project[key]))
        ratio=ratio_for_dimensions(self.project['width_mm'],self.project['height_mm'])
        self.ratio_var.set('自定义' if ratio=='custom' else ratio)
        self._syncing_global=False
        self.update_ratio()

    def sync_panels(self):
        self.panel_list.delete(0, 'end')
        for i, panel in enumerate(self.project['panels']):
            self.panel_list.insert('end', f'({chr(97 + i)}) {panel["title"] or "未命名子图"} · {panel["row"] + 1},{panel["col"] + 1}')
        self.panel_index = min(self.panel_index, len(self.project['panels']) - 1)
        self.panel_list.selection_set(self.panel_index)
        self.panel_changed()

    def panel_changed(self):
        selected = self.panel_list.curselection()
        if selected:
            self.panel_index = selected[0]
        panel = self.project['panels'][self.panel_index]
        for var, key in [(self.rowspan_var, 'rowspan'), (self.colspan_var, 'colspan'), (self.title_var, 'title'), (self.xlabel_var, 'xlabel'), (self.ylabel_var, 'ylabel'), (self.xlim_var, 'xlim'), (self.ylim_var, 'ylim'), (self.clim_var, 'clim'), (self.xlog_var, 'xlog'), (self.ylog_var, 'ylog'), (self.grid_var, 'grid'), (self.legend_var, 'legend'), (self.letter_var, 'letter'), (self.sharex_var, 'sharex'), (self.sharey_var, 'sharey')]:
            var.set(panel[key])
        self.row_var.set(str(panel['row'] + 1))
        self.col_var.set(str(panel['col'] + 1))
        self.sync_layers()

    def add_panel(self):
        panel = new_panel()
        cols = max(1, int(self.cols_var.get()))
        occupied = {(r, c) for p in self.project['panels'] for r in range(p['row'], p['row'] + p['rowspan']) for c in range(p['col'], p['col'] + p['colspan'])}
        position = 0
        while divmod(position, cols) in occupied:
            position += 1
        panel['row'], panel['col'] = divmod(position, cols)
        self.project['panels'].append(panel)
        self.project['rows'] = max(self.project['rows'], panel['row'] + 1)
        self.project['cols'] = cols
        self.panel_index = len(self.project['panels']) - 1
        self.sync_global()
        self.sync_panels()
        self.refresh()

    def remove_panel(self):
        if len(self.project['panels']) == 1:
            raise ValueError('至少保留一个子图。')
        self.project['panels'].pop(self.panel_index)
        self.panel_index = max(0, self.panel_index - 1)
        self.sync_panels()
        self.refresh()

    def apply_panel(self):
        previous = copy.deepcopy(self.project)
        panel = self.project['panels'][self.panel_index]
        self.project.update(rows=int(self.rows_var.get()), cols=int(self.cols_var.get()))
        panel.update(row=int(self.row_var.get()) - 1, col=int(self.col_var.get()) - 1, rowspan=int(self.rowspan_var.get()), colspan=int(self.colspan_var.get()))
        for key in ('title', 'xlabel', 'ylabel', 'xlim', 'ylim', 'clim', 'xlog', 'ylog', 'grid', 'legend', 'letter', 'sharex', 'sharey'):
            panel[key] = getattr(self, key + '_var').get()
        try:
            self.refresh()
        except Exception:
            self.project = previous
            raise
        self.sync_panels()

    def apply_global(self):
        previous = copy.deepcopy(self.project)
        ratio='custom' if self.ratio_var.get()=='自定义' else self.ratio_var.get()
        width,height=dimensions_for_ratio(self.width_var.get(),self.height_var.get(),ratio)
        self.project.update(width_mm=width,height_mm=height,aspect_ratio=ratio,dpi=int(self.dpi_var.get()), font=self.font_var.get(), fontsize=float(self.fontsize_var.get()))
        self.project['style']=STYLE_NAMES[self.style_var.get()]
        if self.project['style'] != previous.get('style','classic'):
            for panel in self.project['panels']:
                for index,layer in enumerate(panel['layers']):
                    if layer['kind'] in ('line','scatter'):
                        layer.update(layer_style(self.project,index))
        try:
            self.refresh()
        except Exception:
            self.project = previous
            raise

        self.sync_layers(self.layer_index)

    def _queue_preview_fit(self, event=None):
        # TkAgg updates its device ratio on Map, which can arrive after the
        # first demo render. A packed widget need not receive Configure when
        # only its requested size changes, so synchronize after both events.
        if self._preview_fit_job is not None:
            self.after_cancel(self._preview_fit_job)
        self._preview_fit_job = self.after_idle(self._fit_preview)

    def _fit_preview(self):
        if self._preview_fit_job is not None:
            self.after_cancel(self._preview_fit_job)
        self._preview_fit_job = None
        widget = self.canvas.get_tk_widget()
        width, height = widget.winfo_width(), widget.winfo_height()
        if width <= 10 or height <= 10:
            return
        # Screen DPI is independent of publication/export DPI. Resize the
        # Tk photo buffer as well as Figure; changing Figure alone can leave
        # a larger renderer clipped by an older, smaller Tk backing image.
        self.figure._original_dpi = 100
        self.figure._set_dpi(100, forward=False)
        self.canvas.resize(SimpleNamespace(width=width, height=height))
        self.canvas.draw()

    def destroy(self):
        job = getattr(self, '_preview_fit_job', None)
        if job is not None:
            self.after_cancel(job)
        canvas = getattr(self, 'canvas', None)
        if canvas is not None and canvas._idle_draw_id is not None:
            canvas.get_tk_widget().after_cancel(canvas._idle_draw_id)
            canvas._idle_draw_id = None
        self._preview_fit_job = None
        super().destroy()

    def refresh(self):
        render_project(self.project, self.datasets, figure=self.figure)
        self._fit_preview()
        self._queue_preview_fit()
        layers = sum(len(p['layers']) for p in self.project['panels'])
        self.status_var.set(f'{len(self.datasets)} 个数据集 · {len(self.project["panels"])} 幅图')

    @staticmethod
    def check_output_path(path):
        path = Path(path).resolve()
        return path

    def save_to(self, path):
        path = self.check_output_path(path)
        save_project(self.project, self.datasets, path)
        self.status_var.set('已保存')

    def open_from(self, path):
        project, datasets = load_project(path)
        render_project(project, datasets)  # Validate before replacing current work.
        self.project, self.datasets = project, datasets
        self._show_editor()
        self.panel_index = 0
        self.sync_global()
        self.sync_datasets()
        self.sync_panels()
        self.refresh()
        self.status_var.set(f'{len(self.datasets)} 个数据集 · {len(self.project["panels"])} 幅图')

    def save_dialog(self):
        path = filedialog.asksaveasfilename(parent=self, initialdir=str(BASE), defaultextension='.json', filetypes=[('科研绘图项目', '*.json')])
        if path:
            self.save_to(path)

    def open_dialog(self):
        path = filedialog.askopenfilename(parent=self, initialdir=str(BASE), filetypes=[('科研绘图项目', '*.json')])
        if path:
            self.open_from(path)

    def export_dialog(self):
        parent = filedialog.askdirectory(parent=self, initialdir=str(BASE), title='选择导出包的父目录')
        if parent:
            target = Path(parent) / ('plot_bundle_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            self.export_to(target)
            messagebox.showinfo('导出完成', '独立 Python、数据和图片已导出到：\n' + str(target), parent=self)

    def export_to(self, path):
        path = self.check_output_path(path)
        result = export_bundle(self.project, self.datasets, path)
        self.status_var.set('已导出复现包：' + str(result))
        return result

    def load_demo(self):
        path = RESOURCE / 'assets' / 'demo_thermo.out'
        if not path.exists():
            raise ValueError('演示 .out 文件尚未就绪：' + str(path))
        self.project = new_project()
        self.datasets = {}
        loaded = self.import_paths([str(path)])
        ds = max(loaded, key=lambda item: len(item.frame))
        cols = list(ds.frame.columns)
        x = 'Time_ps' if 'Time_ps' in cols else 'Step'
        specs = [
            ('Mobile temperature', 'Temperature / K', ['c_mobile_temp', 'Temp', 'temp']),
            ('Pressure evolution', 'Pressure / atm', ['Press', 'press', 'v_press']),
            ('Total energy', 'Energy / kcal mol$^{-1}$', ['TotEng', 'etotal', 'PotEng']),
            ('Hydrate center of mass', 'COM z / Angstrom', ['c_hydrate_com[3]', 'c_com[1]', 'c_mobile_com[1]', 'v_dx'])]
        self.project.update(rows=2, cols=2, width_mm=190, height_mm=145,aspect_ratio='custom',fontsize=9)
        self.project['panels'] = []
        numeric = [c for c in cols if c not in (x, 'Step')]
        for i, (title, ylabel, preferences) in enumerate(specs):
            y = next((c for c in preferences if c in cols), None)
            if y is None and i == 3:
                y = next((c for c in cols if 'com' in c.lower() or 'drift' in c.lower()), None)
            y = y or numeric[min(i, len(numeric) - 1)]
            panel = new_panel()
            panel.update(row=i // 2, col=i % 2, title=title, xlabel='Time / ps' if x == 'Time_ps' else 'Step', ylabel=ylabel, grid=True)
            layer = new_layer(ds.id, x, y)
            layer.update(label=y, **layer_style(self.project,i))
            panel['layers'] = [layer]
            self.project['panels'].append(panel)
        self.panel_index = 0
        self.sync_global()
        self.sync_panels()
        self.refresh()

    def smoke(self, directory):
        directory = self.check_output_path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        report = {'actions': [], 'errors': []}
        try:
            report['tkdnd_version']=str(self.tk.call('package','present','tkdnd'))
            drop_samples=[]
            for name in ('拖入 文件一.csv','拖入 文件二.txt'):
                sample=directory/name
                sample.write_text('x,y\n0,1\n1,2\n',encoding='utf-8')
                drop_samples.append(str(sample))
            assert self.drop_files(SimpleNamespace(data=tk._join(drop_samples)))==COPY
            assert len(self.datasets)==2
            report['actions'].append('drop_two_unicode_space_paths')
            self.load_demo()
            report['actions'].append('import_out_demo_2x2')
            self.color_var.set('#1d4ed8')
            self.lw_var.set('1.7')
            self.apply_layer()
            report['actions'].append('edit_layer_style')
            # Add and remove a real data layer through the same UI callbacks.
            self.kind_var.set('散点')
            self.add_layers()
            self.remove_layer()
            report['actions'].append('add_remove_layer')
            self.notebook.select(1)
            self.apply_panel()
            report['actions'].append('apply_layout')
            self.notebook.select(2)
            self.fontsize_var.set('9.5')
            self.apply_global()
            report['actions'].append('apply_page_style')
            report['styles']={}
            for label,name in STYLE_NAMES.items():
                self.style_var.set(label)
                self.apply_global()
                assert self.project['style']==name
                style_bundle=self.export_to(directory/('style_'+name))
                report['styles'][name]=str(style_bundle)
            self.style_var.set('Science')
            self.apply_global()
            report['actions'].append('export_all_five_science_styles')
            preset_before=copy.deepcopy(self.project)
            report['ratios']={}
            from PIL import Image
            import xml.etree.ElementTree as ET
            for ratio in ('16:9','1:1','4:3'):
                self.ratio_var.set(ratio)
                self.apply_global()
                ratio_bundle=self.export_to(directory/('ratio_'+ratio.replace(':','_')))
                with Image.open(ratio_bundle/'figure.png') as exported:
                    pixels=list(exported.size)
                viewbox=[float(n) for n in ET.parse(ratio_bundle/'figure.svg').getroot().attrib['viewBox'].split()]
                expected=float(ratio.split(':')[0])/float(ratio.split(':')[1])
                assert abs(viewbox[2]/viewbox[3]-expected)<1e-7
                assert abs(pixels[0]-pixels[1]*expected)<=expected+1
                report['ratios'][ratio]={'width_mm':self.project['width_mm'],'height_mm':self.project['height_mm'],'png_pixels':pixels,'svg_ratio':viewbox[2]/viewbox[3]}
            self.project=preset_before
            self.sync_global()
            self.refresh()
            report['actions'].append('export_all_three_canvas_ratios')
            bundle = self.export_to(directory / ('bundle_' + datetime.now().strftime('%H%M%S_%f')))
            report['bundle'] = str(bundle)
            report['actions'].append('export_independent_python_and_figures')
            project_path = directory / ('gui_project_' + datetime.now().strftime('%H%M%S_%f') + '.json')
            self.save_to(project_path)
            self.open_from(project_path)
            report['actions'].append('save_reload_project')
            self.notebook.select(0)
            self.update_idletasks()
            self.update()
            report['datasets'] = len(self.datasets)
            report['panels'] = len(self.project['panels'])
            report['layers'] = sum(len(p['layers']) for p in self.project['panels'])
            report['canvas_size'] = [self.canvas.get_tk_widget().winfo_width(), self.canvas.get_tk_widget().winfo_height()]
            self.lift()
            self.focus_force()
            if sys.platform == 'win32':
                ctypes.windll.user32.SetCursorPos(self.winfo_rootx() + self.winfo_width() - 60, self.winfo_rooty() + 35)
            def capture():
                try:
                    from PIL import ImageGrab
                    self.update()
                    bbox = (self.winfo_rootx(), self.winfo_rooty(), self.winfo_rootx() + self.winfo_width(), self.winfo_rooty() + self.winfo_height())
                    ImageGrab.grab(bbox=bbox, all_screens=True).save(directory / 'desktop_smoke.png')
                    report['screenshot'] = str(directory / 'desktop_smoke.png')
                except Exception as exc:
                    report['errors'].append(str(exc))
                report['passed'] = not report['errors']
                (directory / 'gui_qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                self.destroy()
            self.after(1500, capture)
        except Exception as exc:
            report['errors'].append(str(exc))
            report['traceback'] = traceback.format_exc()
            report['passed'] = False
            (directory / 'gui_qa.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            self.destroy()


def main():
    parser = argparse.ArgumentParser(description='Plota')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--smoke', type=Path)
    args = parser.parse_args()
    app = App()
    if args.smoke:
        app.after(400, lambda: app.smoke(args.smoke))
    elif args.demo:
        app.after(200, app.safe(app.load_demo))
    app.mainloop()


if __name__ == '__main__':
    main()
