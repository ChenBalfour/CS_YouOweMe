from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import import_uu_chart_batch as batch


def specimen():
    source = (ROOT / "scripts/collect_uu_charts.js").read_text(encoding="utf-8")
    source = source[source.index("(function UUChartCollector()") :]
    result = {"format": "uu-chart-batch-1.1", "collector_version": "uu-browser-charts-1.1", "collector_source": source, "run_id": "uu_charts_offline_test_44828", "created_at": "2026-10-15T00:00:00Z", "updated_at": "2026-10-15T00:01:00Z", "template_id": "44828", "item_label": "offline test specimen", "half_year_day": 181, "identity_verified": False, "status": "completed", "tasks": []}
    for window, day, order in (("7d", 7, 1), ("7d", 7, 11), ("15d", 15, 11), ("30d", 30, 1), ("30d", 30, 11), ("90d", 90, 1), ("half_year", 181, 1)):
        response = {"code": 0, "msg": "success", "timestamp": 1791953107780, "data": {"tradeDataList": [{"time": 1790622000000, "price": "1112.00" if order == 11 else "32.39", "sourceType": 0}, {"time": 1790636400000, "price": None}]}}
        result["tasks"].append({"id": f"{window}_{order}", "window": window, "request_body": {"filterTemplateTypeNames": [], "templateId": "44828", "orderType": str(order), "day": str(day), "templateTypeName": "", "customizeDay": False}, "status": "success", "attempts": 1, "origin": "explicit_user_batch", "started_at": "2026-10-15T00:00:00Z", "received_at": "2026-10-15T00:00:01Z", "http_status": 200, "response_text": json.dumps(response)})
    return result


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class BatchTests(unittest.TestCase):
    def test_metric_windows_do_not_include_unsupported_combinations(self):
        b = specimen()
        ids = {t["id"] for t in b["tasks"]}
        self.assertEqual(ids, {"7d_1", "7d_11", "15d_11", "30d_1", "30d_11", "90d_1", "half_year_1"})
        self.assertTrue(batch.inspect_batch(encode(b))["complete"])

    def test_old_eight_task_download_remains_importable_by_known_source_hash(self):
        b = specimen(); b.update(format="uu-chart-batch-1.0", collector_version="uu-browser-charts-1.0", collector_source="offline legacy source fixture")
        proto = copy.deepcopy(b["tasks"][0]); b["tasks"] = []
        for window, day in (("7d", 7), ("15d", 15), ("90d", 90), ("half_year", 181)):
            for order in (1, 11):
                t = copy.deepcopy(proto); t.update(id=f"{window}_{order}", window=window)
                t["request_body"].update(day=str(day), orderType=str(order))
                response = json.loads(t["response_text"])
                if order == 11: response["data"]["tradeDataList"][0]["price"] = "1112.00"
                t["response_text"] = json.dumps(response); b["tasks"].append(t)
        known = hashlib.sha256(b["collector_source"].encode()).hexdigest()
        with patch.object(batch, "LEGACY_SOURCES", {"uu-browser-charts-1.0": known}):
            r = batch.inspect_batch(encode(b))
        self.assertTrue(r["deprecated_request_plan"])
        self.assertEqual(r["expected_tasks"], 8)
        self.assertEqual(r["collector_version"], "uu-browser-charts-1.0")

    def test_failed_http200_has_safe_application_diagnostic(self):
        b = specimen(); b["status"] = "application_error"
        t = b["tasks"][0]; t.pop("response_text"); t.pop("received_at")
        t.update(status="failed", error="application_error", diagnostic={"stage": "application", "reason": "application_error", "application_code": 2002})
        r = batch.inspect_batch(encode(b))
        self.assertEqual(r["tasks"][0]["diagnostic"]["application_code"], 2002)
        t["diagnostic"]["authorization"] = "test-only-placeholder"
        with self.assertRaises(ValueError): batch.inspect_batch(encode(b))

    def test_all_windows_are_distinct_and_half_year_not_assumed_180(self):
        report = batch.inspect_batch(encode(specimen()))
        self.assertTrue(report["complete"])
        self.assertEqual(report["half_year_day"], 181)
        self.assertEqual(len(report["points"]), 14)
        self.assertEqual(len({p["task_id"] for p in report["points"]}), 7)
        self.assertTrue(all(p["historical_available_at"] is None for p in report["points"]))
        self.assertFalse(report["execution_eligible"])

    def test_template_and_filter_mismatch_are_rejected(self):
        for key, value in (("templateId", "980"), ("day", "30"), ("filterTemplateTypeNames", ["restricted"])):
            b = specimen(); b["tasks"][0]["request_body"][key] = value
            with self.assertRaises(ValueError): batch.inspect_batch(encode(b))

    def test_duplicate_task_and_false_completion_are_rejected(self):
        b = specimen(); b["tasks"][1] = copy.deepcopy(b["tasks"][0])
        with self.assertRaises(ValueError): batch.inspect_batch(encode(b))
        b = specimen(); b["tasks"][0] = {k: v for k, v in b["tasks"][0].items() if k in {"id", "window", "request_body"}}
        b["tasks"][0].update(status="pending", attempts=0)
        with self.assertRaises(ValueError): batch.inspect_batch(encode(b))
        b["status"] = "user_interrupted"
        self.assertFalse(batch.inspect_batch(encode(b))["complete"])

    def test_source_change_and_header_leak_are_rejected_before_output(self):
        for mutate in (lambda b: b.update(collector_source="changed"), lambda b: b["tasks"][0].update(headers={"authorization": "test-only-placeholder"})):
            b = specimen(); mutate(b)
            with tempfile.TemporaryDirectory() as temp, patch.object(batch, "DESTINATION", Path(temp)):
                with self.assertRaises(ValueError): batch.import_batch(encode(b), Path(temp) / "out")
                self.assertFalse((Path(temp) / "out").exists())

    def test_failed_or_unknown_attempts_do_not_become_data(self):
        b = specimen(); b["status"] = "http_429"
        task = b["tasks"][0]; task.pop("response_text"); task.pop("received_at")
        task.update(status="failed", http_status=429, error="http_429")
        report = batch.inspect_batch(encode(b))
        self.assertEqual(report["status_counts"], {"failed": 1, "success": 6})
        self.assertEqual(len(report["points"]), 12)

    def test_output_retains_decimal_count_null_and_each_window(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(batch, "DESTINATION", Path(temp)):
            out = Path(temp) / "run"; raw = encode(specimen())
            batch.import_batch(raw, out)
            self.assertEqual((out / "batch_input.json").read_bytes(), raw)
            with closing(sqlite3.connect((out / "chart_batch.sqlite").as_uri() + "?mode=ro", uri=True)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM tasks").fetchone()[0], 7)
                self.assertEqual(db.execute("SELECT source_trade_price_cny, source_listing_count FROM points WHERE task_id='7d_1' ORDER BY sequence").fetchall(), [("32.39", None), (None, None)])
                self.assertEqual(db.execute("SELECT source_trade_price_cny, source_listing_count FROM points WHERE task_id='7d_11' AND sequence=0").fetchone(), (None, 1112))
                self.assertEqual(db.execute("SELECT count(*) FROM points WHERE historical_available_at IS NOT NULL").fetchone()[0], 0)
            with self.assertRaises(ValueError): batch.import_batch(raw, out)

    @unittest.skipUnless(shutil.which("node"), "Node required for offline browser simulation")
    def test_browser_helpers_without_browser_or_network(self):
        code = r"""
const assert=require('node:assert/strict'), c=require(process.argv[1]);
const b={filterTemplateTypeNames:[],templateId:'44828',orderType:'1',day:'7',templateTypeName:'',customizeDay:false};
assert.equal(c.tasks(b,181).length,7); assert.equal(c.tasks(b,181)[6].request_body.day,'181');
assert.throws(()=>c.tasks(b,90)); assert.throws(()=>c.body({...b,authorization:'test-only-placeholder'}));
const p={code:0,timestamp:1791953107780,data:{tradeDataList:[{time:1790622000000,price:'1112.50'}]}};
assert.throws(()=>c.responseText(JSON.stringify(p),{...b,orderType:'11'}));
assert.equal(c.responseText(JSON.stringify(p),b).data.tradeDataList[0].price,'1112.50');
"""
        subprocess.run(["node", "-e", code, str(ROOT / "scripts/collect_uu_charts.js")], check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("node"), "Node required for offline browser simulation")
    def test_browser_fetch_xhr_stop_resume_and_credential_isolation(self):
        code = r"""
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync(process.argv[1],'utf8');
async function simulate(mode='fetch',fail=false,storage=new Map(),previous=null){
 const nodes=[],blobs=[],calls=[];
 class Element{constructor(tag){this.tag=tag;this.style={};this.disabled=false;nodes.push(this)}append(){}click(){}}
 const document={getElementById:()=>null,createElement:t=>new Element(t),body:{append(){}}};
 const requestBody={filterTemplateTypeNames:[],templateId:'44828',orderType:'1',day:String(previous?.half_year_day||181),templateTypeName:'',customizeDay:false};
 const native=async(input,init)=>{const r=new Request(input,init);const b=JSON.parse(await r.clone().text());calls.push(b);if(fail&&calls.length===2){if(fail==='application')return new Response(JSON.stringify({code:2002,msg:'not exported',timestamp:1791953107780,data:null}),{status:200});if(fail==='empty')return new Response(JSON.stringify({code:0,timestamp:1791953107780,data:{tradeDataList:[]}}),{status:200});return new Response('',{status:429});}
 return new Response(JSON.stringify({code:0,timestamp:1791953107780,data:{tradeDataList:[{time:1790622000000,price:b.orderType==='11'?'1112.00':'32.39'}]}}),{status:200});};
 class XHR{open(m,u){this.m=m;this.u=u;this.headers={}}setRequestHeader(k,v){this.headers[k]=v}addEventListener(e,fn){this.listener=fn}send(v){native(this.u,{method:this.m,headers:this.headers,body:v}).then(async r=>{this.status=r.status;this.responseText=await r.text();this.listener()})}}
 class LocalURL extends URL{static createObjectURL(blob){blobs.push(blob);return 'blob:offline'}static revokeObjectURL(){}}
 const window={fetch:native}, localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
 const ctx=vm.createContext({window,document,XMLHttpRequest:XHR,location:{origin:'https://www.youpin898.com',href:'https://www.youpin898.com/'},Request,Response,TextEncoder,TextDecoder,Blob,URL:LocalURL,AbortController,crypto:require('node:crypto').webcrypto,localStorage,console:{log(){},error(){}},setTimeout:(fn,ms)=>{if(ms===5000)Promise.resolve().then(fn);return 1},clearTimeout(){}});
 vm.runInContext(source,ctx);
 if(previous){const upload=nodes.find(n=>n.type==='file');upload.files=[{size:JSON.stringify(previous).length,text:async()=>JSON.stringify(previous)}];await upload.onchange()}
 const start=nodes.find(n=>n.textContent==='确认当前窗口为半年，开始本轮采集'),recover=nodes.find(n=>n.textContent==='已人工确认访问恢复');
 nodes.find(n=>n.placeholder).value='offline item, ordinary, Field-Tested';
 if(mode==='xhr'){const x=new XHR();x.open('POST','https://pc-api.youpin898.com/api/youpin/price/trend/data');x.setRequestHeader('authorization','test-only-session-placeholder');x.send(JSON.stringify(requestBody))}
 else await window.fetch('https://pc-api.youpin898.com/api/youpin/price/trend/data',{method:'POST',headers:{authorization:'test-only-session-placeholder'},body:JSON.stringify(requestBody)});
 for(let i=0;i<50&&start.disabled&&recover.disabled;i++)await new Promise(setImmediate);
 if(!recover.disabled){assert(start.disabled);assert.equal(calls.length,1);recover.onclick()}
 assert.equal(start.disabled,false); await start.onclick();
 assert(blobs.length); const text=await blobs.at(-1).text(), pack=JSON.parse(text);
 assert(!text.includes('test-only-session-placeholder'));
 assert.equal(pack.collector_source.replace(/\r\n/g,'\n'),source.slice(source.indexOf('(function UUChartCollector()')));
 assert.equal(pack.tasks.length,7);
 if(fail){assert.equal(calls.length,2);assert.equal(pack.status,fail==='application'?'application_error':fail==='empty'?'empty_series':'http_429');const failed=pack.tasks.find(t=>t.status==='failed');assert(failed.diagnostic);if(fail==='application'){assert.equal(failed.diagnostic.application_code,2002);assert.equal(failed.diagnostic.stage,'application')}assert.equal(pack.tasks.filter(t=>t.status==='success').length,1);assert(storage.size)}
 else if(previous?.format==='uu-chart-batch-1.0'){assert.equal(calls.length,5);assert.equal(pack.status,'completed');assert.equal(pack.tasks.filter(t=>t.status==='success').length,7)}
 else if(previous){assert.equal(calls.length,6);assert.equal(pack.status,'partial_no_automatic_retry');assert.equal(pack.tasks.filter(t=>t.status==='success').length,6)}
 else{assert.equal(calls.length,7);assert.equal(pack.status,'completed');assert.equal(pack.tasks.filter(t=>t.status==='success').length,7)}
 assert.equal(window.fetch,native);
 return {pack,storage};
}
(async()=>{await simulate('fetch');await simulate('xhr');await simulate('fetch','application');await simulate('fetch','empty');const stopped=await simulate('fetch',true);await simulate('fetch',false,stopped.storage,stopped.pack);if(process.argv[2])await simulate('fetch',false,new Map(),JSON.parse(fs.readFileSync(process.argv[2],'utf8')))})().catch(e=>{console.error(e);process.exit(1)});
"""
        result = subprocess.run(["node", "-e", code, str(ROOT / "scripts/collect_uu_charts.js")], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
