"""
deps/ReadCaseExcel.py — 数据驱动 Excel 读取器

相比原版改动：
  - read_test_cases_excel() 新增 excel_file 参数，默认从 test_config.yaml 读取路径
  - 去掉所有 print()，改为返回状态；错误时抛出 ValueError 供调用方捕获
"""

import os
import yaml
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_RZCU = os.path.dirname(_HERE)   # rzcu/ 目录


def _default_excel_path() -> str:
    cfg_path = os.path.join(_RZCU, "test_data", "test_config.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    p = cfg["file_paths"]["test_case_excel"]
    if not os.path.isabs(p):
        p = os.path.join(_RZCU, p)
    return p


def read_test_cases_excel(sheet_name=0, excel_file: str = None):
    """
    从 Excel 文件指定 sheet 读取测试用例。

    Parameters
    ----------
    sheet_name : str or int
        工作表名称或索引。
    excel_file : str, optional
        Excel 文件路径。为 None 时从 test_config.yaml 读取。

    Returns
    -------
    (test_cases: dict, test_pin: list)
        test_cases  — {pin_key: {列名: 值, ...}}
        test_pin    — 按顺序排列的 pin key 列表
    Raises
    ------
    ValueError / FileNotFoundError / 其他 Exception
    """
    if excel_file is None:
        excel_file = _default_excel_path()

    df = pd.read_excel(
        excel_file,
        sheet_name=sheet_name,
        header=0,
        usecols="A:Q",
        engine="openpyxl",
    )
    df = df.fillna(value=float("nan")).replace({float("nan"): None})

    if df.empty:
        return {}, []
    if len(df.columns) < 4:
        raise ValueError(f"Sheet '{sheet_name}' 列数不足 4 列")

    key_col = df.columns[3]   # D 列为 key
    test_pin = [str(v) for v in df[key_col].dropna()]

    test_cases = {}
    for _, row in df.iterrows():
        key = row[key_col]
        if key is None:
            continue
        test_cases[str(key)] = row.to_dict()

    return test_cases, test_pin
