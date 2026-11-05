"""Offline gallery palette browser; does not execute upstream plotting code."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class PalettePicker(tk.Toplevel):
    def __init__(self,parent,catalog,callback):
        super().__init__(parent)
        self.title('配色库');self.transient(parent)
        self.geometry(f'{min(1000,self.winfo_screenwidth()-80)}x{min(720,self.winfo_screenheight()-120)}')
        self.records=json.loads(Path(catalog).read_text(encoding='utf-8'))['records']
        self.callback=callback;self.filtered=[];self.current=None
        self.configure(bg='white')
        self.columnconfigure(0,weight=1);self.rowconfigure(1,weight=1)
        tools=ttk.Frame(self,padding=12);tools.grid(row=0,column=0,sticky='ew')
        self.query=tk.StringVar();self.source=tk.StringVar(value='全部')
        ttk.Entry(tools,textvariable=self.query).pack(side='left',fill='x',expand=True,padx=(0,8))
        ttk.Combobox(tools,textvariable=self.source,values=['全部','SCI Gallery','Seaborn','Scientific Colours'],state='readonly',width=20).pack(side='left')
        self.count=ttk.Label(tools);self.count.pack(side='right',padx=(8,0))
        body=ttk.Panedwindow(self,orient='horizontal');body.grid(row=1,column=0,sticky='nsew',padx=12)
        self._sash_set=False
        def set_sash(event):
            if event.width>100 and not self._sash_set:
                self._sash_set=True;body.sashpos(0,int(event.width*.35))
        body.bind('<Configure>',set_sash)
        left=ttk.Frame(body);right=ttk.Frame(body,padding=(12,0))
        body.add(left,weight=2);body.add(right,weight=3)
        self.list=tk.Listbox(left,exportselection=False,relief='flat',font=('Segoe UI',9))
        self.list.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(left,orient='vertical',command=self.list.yview);bar.pack(side='right',fill='y')
        self.list.configure(yscrollcommand=bar.set)
        self.canvas=tk.Canvas(right,height=110,highlightthickness=0,bg='white');self.canvas.pack(fill='x')
        self.details=tk.Text(right,wrap='word',font=('Microsoft YaHei UI',10),relief='flat',padx=4,pady=6)
        self.details.pack(fill='both',expand=True)
        buttons=ttk.Frame(self,padding=12);buttons.grid(row=2,column=0,sticky='ew')
        ttk.Button(buttons,text='随风格',command=lambda:self.callback(None,False)).pack(side='left')
        self.apply_button=ttk.Button(buttons,text='用于线条与分类',command=lambda:self.apply(False));self.apply_button.pack(side='right')
        self.cmap_button=ttk.Button(buttons,text='用于连续色图',command=lambda:self.apply(True));self.cmap_button.pack(side='right',padx=8)
        self.list.bind('<<ListboxSelect>>',lambda e:self.select())
        self.canvas.bind('<Configure>',lambda e:self.select())
        self.query.trace_add('write',lambda *args:self.filter())
        self.source.trace_add('write',lambda *args:self.filter())
        self.filter()

    def filter(self):
        query=self.query.get().casefold().split();source=self.source.get()
        self.filtered=[r for r in self.records if (source=='全部' or r['group']==source) and all(
            word in ' '.join(str(r.get(key,'')) for key in ('name','keywords','title','design','id')).casefold() for word in query)]
        self.list.delete(0,'end')
        for item in self.filtered:self.list.insert('end',item['name'])
        self.count.configure(text=str(len(self.filtered)))
        if self.filtered:self.list.selection_set(0)
        self.select()

    def select(self):
        selected=self.list.curselection()
        self.canvas.delete('all')
        self.current=self.filtered[selected[0]] if selected else None
        self.details.configure(state='normal');self.details.delete('1.0','end')
        self.apply_button.configure(state='normal' if self.current else 'disabled')
        self.cmap_button.configure(state='normal' if self.current and len(self.current['colors'])>=2 else 'disabled')
        if self.current:
            entry=self.current;colors=entry['colors'];w=max(200,self.canvas.winfo_width()-10)
            for i,color in enumerate(colors):self.canvas.create_rectangle(5+i*w/len(colors),10,5+(i+1)*w/len(colors),55,fill=color,outline='')
            samples=colors if len(colors)<=8 else [colors[round(i*(len(colors)-1)/5)] for i in range(6)]
            self.canvas.create_text(5,77,text='  '.join(samples),anchor='w',font=('Consolas',9),fill='#444444')
            methods={'thumbnail-sampled':'图像取样（近似值）','metadata-hex':'图库记录的 HEX','library-palette':'库原生分类配色','library-colormap':'库原生连续色图'}
            text=entry['name']+'\n\n'+methods.get(entry['method'],entry['method'])+'\n\n'+entry.get('design','')
            if entry.get('color_notes'):text+='\n\n'+entry['color_notes']
            text+='\n\n'+entry.get('source','')+'\n\n'+entry.get('attribution','')
            if entry.get('figure_license'):text+='\n原图许可：'+entry['figure_license']
            self.details.insert('1.0',text)
        self.details.configure(state='disabled')

    def apply(self,gradient):
        if self.current:self.callback(self.current,gradient)
