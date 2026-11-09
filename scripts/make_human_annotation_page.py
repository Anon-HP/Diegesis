"""Generate a local HTML page that lets a person label (or verify) pairs with the six McCloud labels.

usage: python scripts/make_human_annotation_page.py [--sample annotations/sample_r1.csv] [--show-llm]
Open the resulting HTML file in a browser (it loads the composites from local disk), label the pairs, and
click "Download CSV". Save the file into annotations/human/ and re-run scripts/build_manifest.py.
Human labels take precedence over llm labels and are marked label_source=human.
By default the llm label is hidden, which avoids anchoring bias. --show-llm turns this into verification mode.
"""
import argparse
import csv
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transition.labels import LABELS  # noqa: E402
from transition.paths import ANN_DIR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=str(ANN_DIR / "sample_r1.csv"))
    ap.add_argument("--show-llm", action="store_true")
    ap.add_argument("--out", default=str(ANN_DIR / "human_annotation_tool.html"))
    args = ap.parse_args()
    llm = {}
    for p in glob.glob(str(ANN_DIR / "batches" / "*_labels.csv")):
        for r in csv.DictReader(open(p)):
            llm[r["pair_id"]] = r.get("label", "")
    items = [{"id": r["pair_id"], "img": "file://" + r["composite"],
              "llm": llm.get(r["pair_id"], "") if args.show_llm else ""}
             for r in csv.DictReader(open(args.sample))]
    page = f"""<!doctype html><meta charset=utf-8><title>McCloud transition annotation</title>
<style>body{{font-family:sans-serif;max-width:1450px;margin:auto;padding:16px}} .it{{border-bottom:2px solid #ccc;padding:12px 0}}
img{{max-width:100%}} label{{margin-right:14px}} .llm{{color:#a50}}</style>
<h1>McCloud transition annotation</h1>
<p>Follow docs/annotation_guidelines.md. Panel A is on the left, panel B on the right. Mark "invalid" for non-story or broken pairs.
Progress is kept in this browser (localStorage). <button onclick=dl()>Download CSV</button> <input id=who placeholder="annotator name"></p>
<div id=list></div>
<script>
const LABELS={json.dumps(list(LABELS))}, ITEMS={json.dumps(items)};
const st=JSON.parse(localStorage.getItem('cpt_ann')||'{{}}');
function save(){{localStorage.setItem('cpt_ann',JSON.stringify(st))}}
const L=document.getElementById('list');
ITEMS.forEach((it,i)=>{{const d=document.createElement('div');d.className='it';
 let h=`<b>${{i+1}}/${{ITEMS.length}}</b> ${{it.id}} ${{it.llm?'<span class=llm>(llm: '+it.llm+')</span>':''}}<br><img loading=lazy src="${{it.img}}"><br>`;
 for(const l of [...LABELS,'invalid']) h+=`<label><input type=radio name="r${{i}}" value="${{l}}" ${{st[it.id]&&st[it.id].label==l?'checked':''}}> ${{l}}</label>`;
 h+=`<select name=c${{i}}><option>high<option>medium<option>low</select>`;
 d.innerHTML=h;d.addEventListener('change',()=>{{const v=d.querySelector('input:checked');
  st[it.id]={{label:v?v.value:'',conf:d.querySelector('select').value}};save()}});L.appendChild(d)}});
function dl(){{const who=document.getElementById('who').value||'human';
 let s='pair_id,valid,label,confidence,second_choice,rationale,annotator\\n';
 for(const it of ITEMS){{const a=st[it.id];if(!a||!a.label)continue;
  const inv=a.label=='invalid';s+=`${{it.id}},${{inv?0:1}},${{inv?'':a.label}},${{a.conf}},,,${{who}}\\n`}}
 const b=new Blob([s],{{type:'text/csv'}});const u=URL.createObjectURL(b);const e=document.createElement('a');
 e.href=u;e.download='human_labels.csv';e.click()}}
</script>"""
    Path(args.out).write_text(page)
    print("wrote", args.out, len(items), "items")


if __name__ == "__main__":
    main()
