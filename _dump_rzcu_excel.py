"""读取 RZCU Excel，输出每个 sheet 的列名和所有行数据"""
import zipfile, xml.etree.ElementTree as ET, json, sys, re, os

EXCEL = r"D:\wy_wangbo\WorkSpace\Work\ZCU\python\RZCU\RZCU\RzcuTestCase_SKU4.xlsx"
OUT   = r"D:\Siada\general_test_manager\_excel_dump.json"

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def col_idx(ref):
    ref = re.sub(r'\d', '', ref)
    n = 0
    for c in ref:
        n = n * 26 + (ord(c) - ord('A') + 1)
    return n - 1

with zipfile.ZipFile(EXCEL) as zf:
    # shared strings
    try:
        ss_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
            for si in ss_xml.iter(f"{{{NS}}}si")
        ]
    except Exception:
        shared = []

    # workbook → sheet names + rIds
    wb_xml = ET.fromstring(zf.read("xl/workbook.xml"))
    wb_rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        r.get(f"{{{NS_R}}}id", r.get("Id")): r.get("Target")
        for r in wb_rels_xml
    }
    sheets = []
    for s in wb_xml.iter(f"{{{NS}}}sheet"):
        name = s.get("name")
        rid  = s.get(f"{{{NS_R}}}id", s.get("r:id"))
        target = rid_to_target.get(rid, "")
        sheets.append((name, target))

    result = {}
    for sname, target in sheets:
        path = f"xl/{target}" if not target.startswith("xl/") else target
        if path not in zf.namelist():
            continue
        ws_xml = ET.fromstring(zf.read(path))
        all_rows = []
        for row_el in ws_xml.iter(f"{{{NS}}}row"):
            cells = {}
            for c in row_el:
                ref = c.get("r", "")
                cidx = col_idx(ref)
                t    = c.get("t", "")
                v_el = c.find(f"{{{NS}}}v")
                if v_el is None:
                    val = None
                elif t == "s":
                    val = shared[int(v_el.text)] if v_el.text is not None else ""
                elif t == "b":
                    val = bool(int(v_el.text))
                else:
                    try:
                        val = float(v_el.text)
                        if val == int(val):
                            val = int(val)
                    except Exception:
                        val = v_el.text
                cells[cidx] = val
            if cells:
                max_col = max(cells.keys()) + 1
                all_rows.append([cells.get(i) for i in range(max_col)])

        if not all_rows:
            continue
        headers = [str(c) if c is not None else "" for c in all_rows[0]]
        data_rows = []
        for row in all_rows[1:]:
            d = {}
            for i, h in enumerate(headers):
                d[h] = row[i] if i < len(row) else None
            data_rows.append(d)
        result[sname] = {"headers": headers, "rows": data_rows}
        sys.stderr.write(f"  {sname}: {headers} — {len(data_rows)} rows\n")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
sys.stderr.write(f"\nSaved → {OUT}\n")
