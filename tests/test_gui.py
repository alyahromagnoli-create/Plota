import unittest
from pathlib import Path
import tempfile
import os
import subprocess
import sys
from functools import wraps
from app import App


def isolated_tk(method):
    """Each real app owns one Tcl interpreter for its process lifetime."""
    @wraps(method)
    def run(self):
        if os.environ.get('PLOTA_GUI_CASE') == method.__name__:
            return method(self)
        env=os.environ.copy()
        env['PLOTA_GUI_CASE']=method.__name__
        env['PYTHONIOENCODING']='utf-8'
        env['PYTHONDONTWRITEBYTECODE']='1'
        root=Path(__file__).resolve().parents[1]
        child=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'tests'),
                              '-p','test_gui.py','-k',method.__name__],cwd=root,env=env,
                             capture_output=True,text=True,encoding='utf-8',timeout=45)
        self.assertEqual(child.returncode,0,child.stdout+'\n'+child.stderr)
    return run


class GuiWorkflowTest(unittest.TestCase):
    @isolated_tk
    def test_science_style_selection_and_manual_edits(self):
        app=App()
        app.withdraw()
        try:
            app.load_demo()
            dimensions=(app.project['width_mm'],app.project['height_mm'])
            app.style_var.set('IEEE')
            app.apply_global()
            self.assertEqual(app.project['style'],'ieee')
            self.assertEqual((app.project['width_mm'],app.project['height_mm']),dimensions)
            self.assertEqual(app.project['panels'][0]['layers'][0]['color'],'k')
            app.color_var.set('#ab1234')
            app.apply_layer()
            app.apply_global()
            self.assertEqual(app.project['panels'][0]['layers'][0]['color'],'#ab1234')
            app.style_var.set('Nature')
            app.apply_global()
            self.assertEqual(app.project['style'],'nature')
            self.assertEqual(app.project['panels'][0]['layers'][0]['color'],'#0C5DA5')
            app.project.pop('style')
            app.sync_global()
            self.assertEqual(app.style_var.get(),'经典')
        finally:
            app.destroy()

    @isolated_tk
    def test_ratio_selection_and_multi_file_drop(self):
        from types import SimpleNamespace
        import tkinter as tk
        app=App()
        app.withdraw()
        try:
            app.width_var.set('160')
            for ratio,height in [('16:9',90),('1:1',160),('4:3',120)]:
                app.ratio_var.set(ratio)
                app.apply_global()
                self.assertAlmostEqual(app.project['height_mm'],height)
            self.assertTrue(app.tk.call('package','present','tkdnd'))
            self.assertTrue(app.home.dnd_bind('<<Drop>>'))
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work') as tmp:
                files=[Path(tmp)/'中文 文件一.csv',Path(tmp)/'second file.txt']
                for file in files:
                    file.write_text('x,y\n0,1\n1,2\n',encoding='utf-8')
                result=app.drop_files(SimpleNamespace(data=tk._join([str(f) for f in files])))
                self.assertEqual(result,'copy')
                self.assertEqual(len(app.datasets),2)
                app.update_idletasks()
                self.assertTrue(app.editor.winfo_manager())
                errors=[]
                app.report_error=lambda error:errors.append(str(error))
                self.assertEqual(app.drop_files(SimpleNamespace(data=tk._join([tmp]))),'refuse_drop')
                self.assertTrue(errors)
                self.assertEqual(len(app.datasets),2)
        finally:
            app.destroy()

    @isolated_tk
    def test_import_layers_layout_and_project_roundtrip(self):
        app = App()
        app.withdraw()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'work') as tmp:
                source = Path(tmp) / 'sample.csv'
                source.write_text('time,A,B\n0,1,2\n1,3,4\n2,5,6\n', encoding='utf-8')
                app.import_paths([str(source)])
                self.assertEqual(len(app.datasets), 1)
                app.x_var.set('time')
                app.y_list.selection_clear(0, 'end')
                app.y_list.selection_set(0, 1)
                app.add_layers()
                self.assertEqual(len(app.project['panels'][0]['layers']), 2)
                app.add_panel()
                app.rows_var.set('1')
                app.cols_var.set('2')
                app.row_var.set('1')
                app.col_var.set('2')
                app.apply_panel()
                self.assertEqual(app.project['panels'][1]['col'], 1)
                existing_project = app.project
                app.show_home()
                self.assertIs(app.project, existing_project)
                self.assertEqual(len(app.datasets), 1)
                app._show_editor()
                target = Path(tmp) / 'project.json'
                app.save_to(target)
                app.open_from(target)
                self.assertEqual(len(app.project['panels']), 2)
                self.assertEqual(len(app.datasets), 1)
        finally:
            app.destroy()

    @isolated_tk
    def test_matrix_selection_and_forbidden_input(self):
        app = App()
        app.withdraw()
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'work') as tmp:
                source = Path(tmp) / 'matrix.csv'
                source.write_text('1,2,3\n4,5,6\n7,8,9\n', encoding='utf-8')
                app.header_var.set('none')
                app.import_paths([str(source)])
                app.kind_var.set('矩阵热力图')
                app.add_layers()
                app.row_start_var.set('1')
                app.row_end_var.set('3')
                app.col_start_var.set('0')
                app.col_end_var.set('2')
                app.apply_layer()
                layer = app.project['panels'][0]['layers'][0]
                self.assertEqual((layer['row_start'], layer['row_end'], layer['col_start'], layer['col_end']), (1, 3, 0, 2))
                self.assertEqual(tuple(app.figure.axes[0].images[0].get_array().shape), (2, 2))
                with self.assertRaisesRegex(ValueError, '.data'):
                    app.import_paths([str(Path(tmp) / 'do_not_read.data')])
                # Portable application accepts user-selected drives; this check does not write.
                self.assertEqual(app.check_output_path(Path('E:/Research/output.json')),Path('E:/Research/output.json').resolve())
        finally:
            app.destroy()

    @isolated_tk
    def test_normal_delayed_demo_and_resize_match_backing_store(self):
        app = App()
        app.attributes('-topmost', True)
        records = []
        failures = []
        def record():
            try:
                widget = app.canvas.get_tk_widget()
                size = (widget.winfo_width(), widget.winfo_height())
                bbox = tuple(round(v) for v in app.figure.bbox.size)
                photo = (app.canvas._tkphoto.width(), app.canvas._tkphoto.height())
                records.append((size, bbox, photo))
                self.assertEqual(bbox, size)
                self.assertEqual(photo, size)
                if len(records) == 1:
                    from PIL import ImageGrab
                    x, y = app.winfo_rootx(), app.winfo_rooty()
                    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True).save(Path(__file__).resolve().parents[1] / 'work' / 'normal_demo_startup.png')
            except Exception as exc:
                failures.append(exc)
        def capture_home():
            try:
                self.assertTrue(app.home.winfo_ismapped())
                self.assertFalse(app.editor.winfo_ismapped())
                from PIL import ImageGrab
                x, y = app.winfo_rootx(), app.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height()), all_screens=True).save(Path(__file__).resolve().parents[1] / 'work' / 'home_startup.png')
            except Exception as exc:
                failures.append(exc)
        app.after(300, capture_home)
        app.after(500, lambda: app.home.event_generate('<Button-1>', x=int(app.winfo_width() / 2), y=int(max(210, app.winfo_height() * .36) + 225 + 49)))
        app.after(1800, record)
        def late_map():
            app.canvas._device_pixel_ratio = 1.0
            app.canvas.get_tk_widget().event_generate('<Map>')
        app.after(2100, late_map)
        app.after(2600, record)
        app.after(2800, lambda: app.geometry('1250x800'))
        app.after(3600, record)
        app.after(3800, app.destroy)
        app.mainloop()
        import json
        (Path(__file__).resolve().parents[1] / 'work' / 'normal_demo_startup_qa.json').write_text(json.dumps({'observations': records, 'description': 'widget, figure_bbox, Tk_photo: normal demo; late DPI Map; window resize'}, indent=2), encoding='utf-8')
        self.assertEqual(len(records), 3)
        self.assertNotEqual(records[0][0], records[2][0])
        if failures:
            raise failures[0]

if __name__ == '__main__':
    unittest.main()
