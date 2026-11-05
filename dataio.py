"""Read numeric tables and LAMMPS tabular thermo output without executing input."""
from __future__ import annotations
import csv
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

SUPPORTED_EXTENSIONS={'.xlsx','.xlsm','.xls','.ods','.csv','.txt','.tsv','.dat','.asc','.xy','.xvg',
                      '.out','.log','.json','.jsonl','.ndjson','.npy','.npz','.parquet','.feather','.h5','.hdf5'}


@dataclass
class Dataset:
    id: str
    name: str
    frame: pd.DataFrame
    source: str = ''
    meta: dict = field(default_factory=dict)


def _dataset(path, frame, name=None, **meta):
    frame.columns = [str(c) for c in frame.columns]
    if frame.columns.duplicated().any():
        raise ValueError('列名重复，请在源表中修改列名。')
    if frame.empty:
        raise ValueError('没有可绘制的数据行。')
    return Dataset(uuid.uuid4().hex, name or path.name, frame, str(path), meta)


def _read_text(path, encoding):
    if encoding != 'auto':
        return path.read_text(encoding=encoding), encoding
    for enc in ('utf-8-sig', 'gb18030'):
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            pass
    raise ValueError('文件编码无法识别，请指定编码。')


def _thermo(path, text):
    result, headers, rows = [], None, []
    units, dt, info, warnings = None, None, {}, []

    def flush():
        nonlocal headers, rows, info, warnings
        if headers is not None and rows:
            f = pd.DataFrame(rows, columns=headers)
            if not np.isfinite(f.to_numpy()).all():
                warnings.append('数据含 NaN/Inf，绘图时不会自动插值。')
            if 'Step' in f and (f.Step.diff().dropna() < 0).any():
                warnings.append('本段 Step 存在回退；未自动重排或拼接。')
            if info.get('units') == 'real':
                if 'Time' in f and 'Time_ps' not in f:
                    f['Time_ps'] = f['Time'] / 1000
                    info['time_formula'] = 'Time / 1000 (real: fs -> ps)'
                elif info.get('timestep_fs') is not None and 'Time_ps' not in f:
                    f['Time_ps'] = f['Step'] * info['timestep_fs'] / 1000
                    info['time_formula'] = 'Step * timestep_fs / 1000; Step origin, not stitched across runs'
                    warnings.append('Time_ps 按 Step×步长/1000 换算；重置 Step 或变步长时不代表连续累计时间。')
            result.append(_dataset(path, f, f'{path.name} · 段{len(result)+1}', kind='lammps', warnings=list(warnings), **info))
        headers, rows, info, warnings = None, [], {}, []

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        match = re.match(r'(?:Unit style\s*:\s*|units\s+)(\w+)', line)
        if match:
            flush()
            units = match.group(1)
            continue
        match = re.match(r'(?:Time step\s*:\s*|timestep\s+)(\S+)', line)
        if match:
            flush()
            try:
                candidate = float(match.group(1))
                dt = candidate if np.isfinite(candidate) and candidate > 0 else None
            except ValueError:
                dt = None
            continue
        parts = line.split()
        if parts[0] == 'Step' and len(parts) > 1:
            flush()
            if len(set(parts)) != len(parts):
                raise ValueError(f'第{lineno}行热力学表头含重复列名。')
            headers = parts
            info = {'units': units, 'header_line': lineno}
            if units == 'real' and dt is not None:
                info['timestep_fs'] = dt
            continue
        if headers is None:
            continue
        if line.startswith(('WARNING:', 'WARNING ')):
            warnings.append(f'第{lineno}行：{line}')
            continue
        if line.startswith(('Loop time', 'ERROR:', 'MPI task', 'Per MPI', 'Total wall')):
            if line.startswith('ERROR:'):
                warnings.append(f'运行以错误结束：{line}')
            flush()
            continue
        # Only numerical Step-prefixed rows are records. Other text closes the block.
        if re.match(r'^[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?$', parts[0]):
            if len(parts) != len(headers):
                raise ValueError(f'第{lineno}行有{len(parts)}列，表头有{len(headers)}列；拒绝静默截断。')
            try:
                rows.append([float(s.replace('D','e').replace('d','e')) for s in parts])
            except ValueError as exc:
                raise ValueError(f'第{lineno}行含非数值热力学字段。') from exc
        else:
            raise ValueError(f'第{lineno}行不是合法的热力学数值行或已识别的结束标记：{line[:100]}')
    flush()
    if not result:
        raise ValueError('未找到以 Step 开头的 LAMMPS 数值表。本版支持 thermo one/custom 表格输出。')
    return result


def _is_number(value):
    try:
        float(str(value))
        return True
    except (ValueError, TypeError):
        return False


def _numeric_frame(raw):
    raw=raw.copy();raw.columns=[str(c).strip() for c in raw.columns]
    if raw.columns.duplicated().any():raise ValueError('列名重复，请修改源表。')
    result={};warnings=[];numeric_count=0
    for col in raw.columns:
        values=raw[col]
        text=values.map(lambda v: '' if pd.isna(v) else (v.decode('utf-8') if isinstance(v,bytes) else str(v)))
        numeric=pd.to_numeric(values,errors='coerce')
        missing=text.str.strip().str.lower().isin(['','nan','na','null','none','n/a'])
        nonnumeric=(~missing)&numeric.isna()
        if nonnumeric.any() or text.str.match(r'^0\d+$').any():
            result[col]=text
            warnings.append('已保留分类/文本列：'+col+'；数值图请选择数值列。')
        elif numeric.notna().any():
            result[col]=numeric;numeric_count+=1
    if not numeric_count:raise ValueError('所选范围没有数值列，请检查数据与表头。')
    numeric=pd.DataFrame(result,index=raw.index).reset_index(drop=True)
    if numeric.isna().any().any():
        warnings.append('缺失或非数值单元格保留为 NaN；不自动插值。')
    return numeric, warnings


def _from_array(path,value,name):
    array=np.asarray(value)
    if np.iscomplexobj(array):raise ValueError('暂不读取复数数组，请先明确实部/虚部。')
    if array.dtype.names:
        frame=pd.DataFrame.from_records(array)
    elif array.ndim==1:
        frame=pd.DataFrame({'Index':np.arange(len(array)),name:array})
    elif array.ndim==2:
        frame=pd.DataFrame(array,columns=[f'Column_{i+1}' for i in range(array.shape[1])])
    else:raise ValueError(f'{name} 是{array.ndim}维数组；当前仅支持一维/二维表格，不自动切片。')
    frame,warnings=_numeric_frame(frame)
    return _dataset(path,frame,f'{path.name} · {name}',kind='array',warnings=warnings)


def _structured(path,ext):
    if ext in {'.npy','.npz'}:
        loaded=np.load(path,allow_pickle=False)
        if ext=='.npy':return [_from_array(path,loaded,'Value')]
        with loaded as archive:
            result=[];vectors={}
            for key in archive.files:
                a=archive[key]  # allow_pickle=False rejects object payloads.
                if a.ndim==1 and not a.dtype.names:vectors[key]=a
                else:result.append(_from_array(path,a,key))
            if vectors:
                if len({len(a) for a in vectors.values()})==1 and len(vectors)>1:
                    frame,warnings=_numeric_frame(pd.DataFrame(vectors))
                    result.append(_dataset(path,frame,path.name+' · vectors',warnings=warnings))
                else:result.extend(_from_array(path,a,key) for key,a in vectors.items())
            if not result:raise ValueError('NPZ中没有可读数组。')
            return result
    if ext in {'.h5','.hdf5'}:
        import h5py
        result=[];skipped=[]
        with h5py.File(path,'r') as handle:
            def visit(name,obj):
                if isinstance(obj,h5py.Dataset):
                    if obj.ndim in (1,2) and obj.dtype.kind in 'biufSU':result.append(_from_array(path,obj[()],name))
                    else:skipped.append(name)
            # visititems does not dereference external links or execute stored code.
            handle.visititems(visit)
        if not result:raise ValueError('HDF5中没有受支持的一维/二维数值数据集；不自动解释Pandas专用存储布局。')
        if skipped:
            for item in result:item.meta.setdefault('warnings',[]).append('未导入的数据集：'+', '.join(skipped))
        return result
    if ext in {'.json','.jsonl','.ndjson'}:
        text=path.read_text(encoding='utf-8-sig')
        if ext in {'.jsonl','.ndjson'}:
            value=[json.loads(line) for line in text.splitlines() if line.strip()]
        else:value=json.loads(text)
        if isinstance(value,dict) and value.get('format')=='ScientificPlotStudio':
            raise ValueError('这是Plota项目，请使用“打开项目”，不要作为数据导入。')
        if isinstance(value,dict) and set(value)>={'columns','data'}:
            frame=pd.DataFrame(value['data'],columns=value['columns'])
        elif isinstance(value,list):frame=pd.DataFrame(value)
        elif isinstance(value,dict):frame=pd.DataFrame(value)
        else:raise ValueError('JSON须为记录数组、等长列数组或columns/data表格。')
    elif ext=='.parquet':frame=pd.read_parquet(path,engine='pyarrow')
    elif ext=='.feather':frame=pd.read_feather(path)
    else:raise ValueError('不支持的结构化格式。')
    frame,warnings=_numeric_frame(frame)
    return [_dataset(path,frame,kind='table',warnings=warnings)]


def load_file(path, *, sheet=None, header='auto', delimiter='auto', encoding='auto', skiprows=0):
    path = Path(path)
    if not path.is_file():
        raise ValueError('数据文件不存在：' + str(path))
    ext = path.suffix.lower()
    if ext == '.data':
        raise ValueError('按当前需求，本软件不支持 LAMMPS .data，请导入 .out。')
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError('不支持该格式。请使用Excel、文本表、JSON、NumPy、Parquet、Feather或HDF5。')
    if ext in {'.json','.jsonl','.ndjson','.npy','.npz','.parquet','.feather','.h5','.hdf5'}:
        return _structured(path,ext)
    skiprows = int(skiprows)
    if skiprows < 0:
        raise ValueError('跳过行数不能小于0。')
    hdr = None if header in ('none', None, -1) else ('auto' if header == 'auto' else int(header))
    if ext in {'.xlsx','.xlsm','.xls','.ods'}:
        result = []
        engine={'.xls':'xlrd','.ods':'odf'}.get(ext,'openpyxl')
        with pd.ExcelFile(path, engine=engine) as book:
            names = book.sheet_names if sheet is None else [sheet]
            for name in names:
                raw = pd.read_excel(book, sheet_name=name, header=None, skiprows=skiprows,dtype=object,keep_default_na=False)
                if raw.empty:
                    continue
                selected = hdr
                if hdr == 'auto':
                    selected = None if all(_is_number(v) for v in raw.iloc[0].dropna() if str(v).strip()) else 0
                if selected is not None:
                    if selected >= len(raw):
                        raise ValueError('表头行超出数据范围。')
                    columns = raw.iloc[selected].tolist()
                    raw = raw.iloc[selected+1:].copy()
                    raw.columns = columns
                else:
                    raw.columns = [f'Column_{i+1}' for i in range(raw.shape[1])]
                f, warnings = _numeric_frame(raw)
                result.append(_dataset(path,f,f'{path.name} · {name}',kind='table',warnings=warnings,sheet=name))
        if not result:
            raise ValueError('工作簿没有非空工作表。')
        return result
    text, enc = _read_text(path,encoding)
    if ext in {'.out','.log'}:
        return _thermo(path,text)
    lines = [s for s in text.splitlines()[skiprows:] if s.strip() and not s.lstrip().startswith('#') and not (ext=='.xvg' and s.lstrip().startswith('@'))]
    if not lines:
        raise ValueError('文件没有数据行。')
    sep = delimiter
    if sep == 'auto':
        try:
            sep = csv.Sniffer().sniff('\n'.join(lines[:20]), delimiters=',;\t').delimiter
        except csv.Error:
            sep = r'\s+'
    sep = {'whitespace':r'\s+', '空白':r'\s+', 'tab':'\t', '\\t':'\t'}.get(sep,sep)
    tokens = re.split(r'\s+',lines[0].strip()) if sep == r'\s+' else next(csv.reader([lines[0]],delimiter=sep))
    if hdr == 'auto':
        hdr = None if all(_is_number(t) for t in tokens if str(t).strip()) else 0
    # pandas may infer an implicit index when rows exceed header width.
    # Check widths first so no numeric field can be silently shifted or discarded.
    records = ([re.split(r'\s+',s.strip()) for s in lines] if sep == r'\s+'
               else list(csv.reader(lines,delimiter=sep)))
    start = 0 if hdr is None else hdr
    if start >= len(records):
        raise ValueError('表头行超出数据范围。')
    width=len(records[start])
    for n,record in enumerate(records[start:],start+1):
        if len(record)!=width:
            raise ValueError(f'第{n}条记录列数为{len(record)}，预期{width}列，请检查分隔符和表头。')
    try:
        raw = pd.read_csv(io.StringIO('\n'.join(lines)),sep=sep,engine='python',header=hdr,on_bad_lines='error',dtype=str,keep_default_na=False)
    except Exception as exc:
        raise ValueError('表格解析失败，请检查分隔符与表头：'+str(exc)) from exc
    if hdr is None:
        raw.columns = [f'Column_{i+1}' for i in range(raw.shape[1])]
    f, warnings = _numeric_frame(raw)
    return [_dataset(path,f,kind='table',warnings=warnings,encoding=enc)]
