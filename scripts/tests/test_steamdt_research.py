from contextlib import closing, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import steamdt_research as engine
from cs_youoweme.collectors.website import SYSTEM, ITEM, MARKET_COMPARISON, KLINE, WebsiteClient
from cs_youoweme.errors import CollectionError, AccessStopped
from cs_youoweme.history.store import Store


class Response(io.BytesIO):
    url = "https://www.steamdt.com/api"
    status = 200


class FakeOpener:
    def __init__(self, item, cutoff, revision=0, blocked=False):
        self.item, self.cutoff, self.revision, self.blocked = item, cutoff, revision, blocked
        self.calls = []

    def open(self, request, timeout):
        import urllib.parse
        path = urllib.parse.urlsplit(request.full_url).path.removeprefix('/api')
        params = json.loads(request.data) if request.data else {k:v[0] for k,v in urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query).items()}
        self.calls.append((path, params))
        if self.blocked:
            raise engine.urllib.error.HTTPError(request.full_url, 429, "test", {"Retry-After":"120"}, None)
        if path == SYSTEM:
            data = {"systemTime": int(time.time()*1000)}
        elif path == ITEM:
            data = {"marketHashName": self.item['market_hash_name'], "itemId": self.item['steamdt_item_id']}
        elif path == MARKET_COMPARISON:
            data = {"platformMarket":[{"platform":"youpin","platformName":"悠悠","link":"https://www.youpin898.com/market/goods-list?gameId=730&templateId=113014", "sellPrice":200,"biddingPrice":190,"sellCount":50,"biddingCount":20,"updateTime":int(time.time())}]}
        elif path == KLINE:
            data = [[self.cutoff-10800,100+self.revision,101+self.revision,102+self.revision,99+self.revision, None, None], [self.cutoff-7200,101+self.revision,102+self.revision,103+self.revision,100+self.revision,2,"204.20"]] if int(params['maxTime']) >= self.cutoff-10800 else []
        else:
            raise AssertionError(path)
        return Response(json.dumps({"success":True,"errorCode":0,"data":data}).encode())


class ResearchTests(unittest.TestCase):
    def setUp(self):
        # Use a named writable workspace temp directory; cleanup is scoped here.
        temp_parent = ROOT/'data/local/staging/steamdt'
        temp_parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='_offline_research_',dir=temp_parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        assert self.root.is_relative_to((ROOT/'data/local/staging/steamdt').resolve())
        self.items = json.loads(engine.SEEDS.read_text(encoding='utf-8'))
        self.items['items'] = self.items['items'][:1]
        self.seed = self.root/'seeds.json'; self.seed.write_text(json.dumps(self.items),encoding='utf-8')
        for target,value in [('BASE',self.root/'warehouses'),('CONTROL',self.root/'control'),('SEEDS',self.seed)]:
            p=patch.object(engine,target,value); p.start(); self.addCleanup(p.stop)
        p=patch('cs_youoweme.history.store.LOCAL_DATA',self.root);p.start();self.addCleanup(p.stop)
        for target in ('cs_youoweme.collectors.website.time.sleep','scripts.steamdt_research.time.sleep'):
            p=patch(target);p.start();self.addCleanup(p.stop)
        self.path=engine.init_workspace('research_test')
        self.cutoff=int(time.time())//3600*3600

    def invoke(self,maximum=30,revision=0,blocked=False):
        opener=FakeOpener(self.items['items'][0],self.cutoff,revision,blocked)
        def factory(archive,guard,store):
            return WebsiteClient(archive,3,opener=opener,max_response_bytes=2*1024*1024,before_request=lambda p,q:guard.before(p,q,store))
        with redirect_stdout(io.StringIO()):
            result=engine.sync('research_test',maximum=maximum,delay=3,client_factory=factory)
        return result,opener

    def test_initial_backfill_cursor_and_resume_do_not_duplicate_values(self):
        first,opener=self.invoke(maximum=4)
        self.assertEqual(first['run']['status'],'paused_budget')
        self.assertEqual(first['items'][0]['hour_rows'],2)
        cursor=first['items'][0]['jobs'][0]['cursor'];self.assertTrue(cursor)
        second,opener=self.invoke()
        self.assertEqual(second['run']['status'],'completed')
        self.assertEqual(second['items'][0]['hour_rows'],2)
        history=[q for p,q in opener.calls if p==KLINE]
        self.assertTrue(any(q['maxTime']==cursor for q in history))
        with closing(sqlite3.connect((self.path/'research.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM bars').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM research_bar_versions').fetchone()[0],2)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_source_revisions_are_retained_without_duplicate_current_rows(self):
        self.invoke(); self.invoke(); result,_=self.invoke(revision=10)
        self.assertEqual(result['items'][0]['hour_rows'],2)
        self.assertEqual(result['changed_bar_versions'],2)
        with closing(sqlite3.connect((self.path/'research.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM research_bar_versions').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT min(open_cny) FROM research_hourly_latest').fetchone()[0],'110')

    def test_registry_rejects_duplicates_special_versions_and_bad_ids(self):
        for mutate in (lambda v:v['items'].append(copy.deepcopy(v['items'][0])), lambda v:v['items'][0].update(market_hash_name='StatTrak™ AK-47 | The Oligarch (Field-Tested)'),lambda v:v['items'][0].update(steamdt_item_id='not-an-id')):
            value=copy.deepcopy(self.items);mutate(value);self.seed.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(CollectionError):engine.registry(self.seed)

    def test_budget_is_persisted_before_send_and_stop_survives_new_calls(self):
        guard=engine.Guard(1,3)
        with Store(self.path/'research.sqlite') as store:
            guard.before(ITEM,{},store)
            self.assertEqual(len(json.loads((engine.CONTROL/'state.json').read_text())['requests']),1)
            with self.assertRaises(CollectionError):guard.before(ITEM,{},store)
        guard.stop(time.time()+100)
        with self.assertRaises(AccessStopped):engine.Guard(10,3,confirmed=True)

    def test_429_is_not_retried_and_persistently_stops(self):
        result,opener=self.invoke(blocked=True)
        self.assertEqual(result['run']['status'],'stopped')
        self.assertEqual(len(opener.calls),1)
        self.assertTrue(json.loads((engine.CONTROL/'state.json').read_text())['blocked'])
        with self.assertRaises(AccessStopped):self.invoke()

    def test_read_only_status_sends_no_requests(self):
        self.assertEqual(engine.status('research_test')['status'],'initialized')
        self.invoke()
        before=(self.path/'research.sqlite').read_bytes()
        with patch.object(engine,'sync',side_effect=AssertionError):
            value=engine.status('research_test')
        self.assertEqual(value['integrity'],'ok')
        self.assertEqual((self.path/'research.sqlite').read_bytes(),before)

    def test_aggregates_preserve_missing_flows_and_partial_coverage(self):
        start=int(engine.datetime(2026,10,12,tzinfo=engine.CHINA).timestamp())
        rows=[{'bucket_time':start+i*3600,'open_cny':'10','close_cny':'11','high_cny':'12','low_cny':'9','source_volume':None if i==0 else 2,'source_turnover_cny':'22.20'} for i in range(4)]
        row=engine.aggregate(rows,'4h')[0]
        self.assertTrue(row['complete_hours']);self.assertIsNone(row['source_volume']);self.assertEqual(row['source_turnover_cny'],'88.80')
        self.assertFalse(engine.aggregate(rows,'1d')[0]['complete_hours'])
        self.assertIsNone(engine.aggregate(rows,'1w')[0]['source_turnover_cny'])

    def test_init_never_overwrites_existing_workspace(self):
        with self.assertRaises(CollectionError):engine.init_workspace('research_test')

    def test_interrupt_before_page_commit_replays_only_uncommitted_page(self):
        with patch('cs_youoweme.history.jobs.commit_page', side_effect=KeyboardInterrupt):
            interrupted, _ = self.invoke()
        self.assertEqual(interrupted['run']['status'], 'interrupted')
        self.assertEqual(interrupted['items'][0]['hour_rows'], 0)
        self.assertEqual(interrupted['items'][0]['jobs'][0]['cursor'], '')
        resumed, _ = self.invoke()
        self.assertEqual(resumed['run']['status'], 'completed')
        self.assertEqual(resumed['items'][0]['hour_rows'], 2)

    def test_new_item_and_all_available_history_create_separate_tasks(self):
        # A later registry addition gets its own full task, independent of the old item.
        with Store(self.path/'research.sqlite') as store:
            for index, item in enumerate(json.loads(engine.SEEDS.read_text())['items']):
                engine.upsert_item(store.db, {'marketHashName':item['market_hash_name'], 'name':item['name_zh']}, None)
                item['history_start'] = None if index else '2025-06-01'
                engine.ensure_tasks(store, item, self.cutoff, 7)
            rows=store.db.execute('SELECT market_hash_name,start_time,state FROM jobs ORDER BY job_id').fetchall()
            self.assertEqual(len(rows), 1)  # Test seed has one item.
            extra=json.loads((ROOT/'scripts/config/steamdt_research_items.json').read_text(encoding='utf-8'))['items'][1]
            engine.upsert_item(store.db, {'marketHashName':extra['market_hash_name'],'name':extra['name_zh']}, None)
            extra['history_start']=None
            engine.ensure_tasks(store, extra, self.cutoff, 7)
            extra_job=store.db.execute('SELECT start_time,state FROM jobs WHERE market_hash_name=?',(extra['market_hash_name'],)).fetchone()
            self.assertEqual(tuple(extra_job),(1,'pending'))
            self.assertEqual(store.db.execute('SELECT count(*) FROM jobs').fetchone()[0],2)


if __name__=='__main__':unittest.main()
