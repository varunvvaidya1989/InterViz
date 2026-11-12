"""Approval transport: real loopback HTTP with no remote mutations."""
import copy
import json
import threading
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import MagicMock, patch

from automation.approvals import intent_id
from founder_dashboard.server import ApprovalRequests, make_server

INTENT={'kind':'plan','release_id':'R-1','expected_hash':'a'*64,'revision':'b'*40}
CARD={**INTENT,'id':intent_id(INTENT)}
OPTIONS={'can_approve':True,'cards':[CARD],'confirmed_ids':[],'runs':[]}


class ApprovalTransportTests(unittest.TestCase):
    def setUp(self):
        self.client=MagicMock();self.client.repository='test/repo'
        self.cache=SimpleNamespace(snapshot=lambda:{'data':{'approvals':OPTIONS},'error':None},refresh=MagicMock())
        self.server=make_server(self.cache,lambda:self.client,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        with urlopen(self.origin+'/api/status',timeout=5) as response:self.csrf=json.load(response)['csrf_token']

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def post(self,payload=INTENT,**headers):
        headers={'Origin':self.origin,'Content-Type':'application/json','X-CSRF-Token':self.csrf,**headers}
        request=Request(self.origin+'/api/approve',data=json.dumps(payload).encode(),headers=headers)
        try:
            with urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as error:
            raw=error.read()
            error.close()
            return error.code,raw.decode()

    def test_approve_dispatches_exact_intent_without_comments_and_duplicate_clicks_once(self):
        with patch('founder_dashboard.server.approval_options',return_value=copy.deepcopy(OPTIONS)):
            code,result=self.post();self.assertEqual(code,202);self.assertEqual(result['state'],'requested')
            self.assertEqual(self.post()[0],202)
        self.client.dispatch.assert_called_once_with('founder-approval.yml',{
            'kind':'plan','release-id':'R-1','expected-hash':'a'*64,'revision':'b'*40})
        self.client.comment.assert_not_called()

    def test_origin_host_and_csrf_are_required_before_dispatch(self):
        for headers in ({'Origin':'https://evil.example'},{'Host':'evil.example'},
                        {'X-CSRF-Token':''},{'X-CSRF-Token':'wrong-token'}):
            with self.subTest(headers=headers):self.assertEqual(self.post(**headers)[0],403)
        self.client.dispatch.assert_not_called()

    def test_non_founder_and_stale_target_fail_closed(self):
        with patch('founder_dashboard.server.approval_options',return_value={**OPTIONS,'can_approve':False}):
            self.assertEqual(self.post()[0],403)
        with patch('founder_dashboard.server.approval_options',return_value={**OPTIONS,'cards':[]}):
            self.assertEqual(self.post()[0],409)
        self.assertEqual(self.post({**INTENT,'actor':'founder'})[0],409)
        self.client.dispatch.assert_not_called()

    def test_network_error_does_not_claim_approval_or_expose_upstream_detail(self):
        with patch('founder_dashboard.server.approval_options',return_value=copy.deepcopy(OPTIONS)):
            self.client.dispatch.side_effect=RuntimeError('private fixture detail')
            code,result=self.post()
            self.assertEqual(code,502);self.assertIn('dispatch_failed',result)
            self.assertNotIn('private fixture detail',result)
        with urlopen(self.origin+'/api/status',timeout=5) as response:
            self.assertEqual(json.load(response)['approval_requests'],{})

    def test_pending_is_confirmed_only_by_matching_ledger_version_and_failures_allow_retry(self):
        requests=ApprovalRequests()
        with patch('founder_dashboard.server.approval_options',return_value=copy.deepcopy(OPTIONS)):
            result=requests.submit(self.client,INTENT)
            self.assertEqual(result['state'],'requested')
            run={'display_title':'Founder approval plan R-1 '+'a'*64+' '+'b'*40,
                 'created_at':datetime.now(timezone.utc).isoformat(),'status':'completed','conclusion':'failure','html_url':'https://github.com/test/repo/actions/runs/1'}
            self.assertEqual(requests.snapshot({'approvals':{**OPTIONS,'runs':[run]}})[CARD['id']]['state'],'failed')
            requests.submit(self.client,INTENT)
            self.assertEqual(self.client.dispatch.call_count,2)
            stale=requests.snapshot({'approvals':{**OPTIONS,'cards':[]}})
            self.assertEqual(stale[CARD['id']]['state'],'stale')
            confirmed=requests.snapshot({'approvals':{**OPTIONS,'cards':[],'confirmed_ids':[CARD['id']]}})
            self.assertEqual(confirmed[CARD['id']]['state'],'confirmed')

    def test_oversized_and_non_json_requests_never_dispatch(self):
        self.assertEqual(self.post({'padding':'x'*5000})[0],409)
        self.assertEqual(self.post(**{'Content-Type':'text/plain'})[0],409)
        self.client.dispatch.assert_not_called()
