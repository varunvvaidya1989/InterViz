"""Founder identity, exact-version and replay checks for dashboard approvals."""
import argparse
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation import cli
from automation.approvals import approval_cards, intent_id, validate_intent
from automation.control import Control, ControlError
from automation.runtime import digest

PLAN='a'*64
HEAD='b'*40
MERGE='c'*40
EVIDENCE={'artifact':'fixture://checks'}


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.control=Control(Path(self.temp.name)/'state.db',{'founder'})
        self.control.create_release('R-1','Example release','lead')
        self.control.upsert_story('R-1','S1','Example outcome',{'allowed_paths':['automation/example.py'],'acceptance':['Works']},[],'lead')
        self.control.submit_plan('R-1',PLAN,'lead')
        self.p=copy.deepcopy(cli.policy());self.p['founders']['usernames']=['founder']
        self.manifest={'hash':PLAN,'revision':HEAD,'pr_url':'https://github.com/test/repo/pull/1',
                       'document':{'user_stories':[{'title':'Example outcome','acceptance':['Works']}]}}
        self.values={'plan:R-1':self.manifest}
        self.client=MagicMock();self.client.repository='test/repo'
        self.client.pr.return_value={'head':{'sha':HEAD,'repo':{'full_name':'test/repo'}},'state':'open'}
        def kv(key,value=None,write=False):
            if write:self.values[key]=value
            return self.values.get(key)
        for target,kwargs in [('ledger',{'return_value':self.control}),('github',{'return_value':self.client}),
                              ('principal',{'return_value':'founder'}),('kv',{'side_effect':kv}),
                              ('current_plan',{'return_value':(self.manifest,PLAN)}),
                              ('output',{'side_effect':lambda name,value:value})]:
            patcher=patch.object(cli,target,**kwargs)
            setattr(self,'mock_'+target,patcher.start());self.addCleanup(patcher.stop)

    def args(self,kind='plan',expected_hash=PLAN,revision=HEAD):
        return argparse.Namespace(kind=kind,release_id='R-1',expected_hash=expected_hash,revision=revision)

    def frozen(self):
        self.control.approve_plan('R-1',PLAN,'founder')
        lease=self.control.claim('R-1','S1','coder')
        self.control.associate_pr('R-1','S1',HEAD,'https://github.com/test/repo/pull/2','coder','controller',lease_id=lease['lease_id'])
        self.control.record_review('R-1','S1',HEAD,'reviewer','APPROVE',EVIDENCE,'reviewer')
        self.control.record_ci('R-1','S1',HEAD,True,EVIDENCE,'ci')
        self.control.integrate('R-1','S1',HEAD,MERGE,'controller')
        self.control.start_qa('R-1',MERGE,'qa')
        self.control.complete_qa('R-1',MERGE,EVIDENCE,'qa')
        return cli.prepare_candidate(self.p,self.control,'R-1',MERGE,'controller')[1]

    def test_plan_click_records_founder_and_is_idempotent(self):
        cli.approve(self.p,self.args());cli.approve(self.p,self.args())
        release=self.control.snapshot('R-1')['releases'][0]
        self.assertEqual(release['plan_approved_hash'],PLAN)
        self.assertEqual(release['plan_approved_by'],'founder')
        self.assertEqual(len([e for e in self.control.events() if e['type']=='plan_approved']),1)
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_payload_cannot_supply_founder_authority(self):
        self.mock_principal.return_value='other-user'
        with self.assertRaisesRegex(ValueError,'configured founder'):cli.approve(self.p,self.args())
        self.assertIsNone(self.control.snapshot('R-1')['releases'][0]['plan_approved_hash'])

    def test_stale_plan_hash_revision_pr_head_and_withdrawn_pr_fail_closed(self):
        for mode in ('hash','revision','pr-head','withdrawn','source'):
            with self.subTest(mode=mode):
                self.client.pr.return_value={'head':{'sha':HEAD,'repo':{'full_name':'test/repo'}},'state':'open'}
                self.mock_current_plan.return_value=(self.manifest,PLAN)
                args=self.args()
                if mode=='hash':args.expected_hash='d'*64
                if mode=='revision':args.revision='d'*40
                if mode=='pr-head':self.client.pr.return_value['head']['sha']='d'*40
                if mode=='withdrawn':self.client.pr.return_value['state']='closed'
                if mode=='source':self.mock_current_plan.return_value=(self.manifest,'d'*64)
                with self.assertRaises(ValueError):cli.approve(self.p,args)
                self.assertIsNone(self.control.snapshot('R-1')['releases'][0]['plan_approved_hash'])

    def test_release_card_requires_frozen_exact_qa_and_current_policy(self):
        candidate=self.frozen()
        ledger={**self.control.snapshot(),'kv':self.values}
        cards=approval_cards(ledger,self.p)
        self.assertEqual([c['kind'] for c in cards],['release'])
        self.assertEqual(cards[0]['expected_hash'],digest(candidate))
        broken=copy.deepcopy(ledger);broken['releases'][0]['qa_passed']=0
        self.assertEqual(approval_cards(broken,self.p),[])
        changed=copy.deepcopy(self.p);changed['limits']['max_cost']+=1
        self.assertEqual(approval_cards(ledger,changed),[])

    def test_release_click_records_exact_candidate_then_disappears(self):
        candidate=self.frozen();args=self.args('release',digest(candidate),MERGE)
        cli.approve(self.p,args);cli.approve(self.p,args)
        self.assertEqual(self.values['release-manifest-approval:R-1']['actor'],'founder')
        self.assertEqual(approval_cards({**self.control.snapshot(),'kv':self.values},self.p),[])
        self.assertEqual(len([e for e in self.control.events() if e['type']=='release_approved']),1)

    def test_approval_cannot_override_missing_qa_or_changed_manifest(self):
        candidate=self.frozen();args=self.args('release',digest(candidate),MERGE)
        candidate['changelog']='Changed after display'
        with self.assertRaises(ValueError):cli.approve(self.p,args)
        args.expected_hash=digest(candidate)
        self.control.record_ci('R-1','S1',HEAD,False,EVIDENCE,'ci')
        with self.assertRaises(ControlError):cli.approve(self.p,args)

    def test_candidate_preparation_is_stable_on_repeated_controller_pulses(self):
        candidate=self.frozen();count=len(self.control.events())
        result,again=cli.prepare_candidate(self.p,self.control,'R-1',MERGE,'controller')
        self.assertEqual(candidate,again);self.assertEqual(len(self.control.events()),count)

    def test_changed_candidate_evidence_cannot_reuse_a_displayed_manifest(self):
        before=self.frozen()
        self.control.record_review('R-1','S1',HEAD,'another-reviewer','APPROVE',{'artifact':'fixture://new-review'},'another-reviewer')
        _,after=cli.prepare_candidate(self.p,self.control,'R-1',MERGE,'controller')
        self.assertNotEqual(digest(before),digest(after))
        with self.assertRaises(ValueError):cli.approve(self.p,self.args('release',digest(before),MERGE))

    def test_intent_rejects_extra_authority_fields_and_invalid_references(self):
        valid=vars(self.args());self.assertEqual(validate_intent(valid),valid)
        for change in ({'founder':'founder'},{'kind':'override'},{'release_id':'../R'},{'expected_hash':HEAD},{'revision':'main'}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_intent({**valid,**change})
        self.assertNotEqual(intent_id(valid),intent_id({**valid,'revision':'e'*40}))

    def test_bot_publication_requires_existing_founder_approval_and_fresh_checks(self):
        self.p['authority']['production_release_enabled']=True
        candidate=self.frozen()
        args=argparse.Namespace(phase='publish',candidate_id='R-1',revision=MERGE)
        self.mock_principal.return_value='github-actions[bot]'
        with self.assertRaises(ValueError):cli.release(self.p,args)
        self.client.request.assert_not_called()
        self.mock_principal.return_value='founder'
        cli.approve(self.p,self.args('release',digest(candidate),MERGE))
        self.mock_principal.return_value='github-actions[bot]'
        self.control.record_ci('R-1','S1',HEAD,False,EVIDENCE,'ci')
        with self.assertRaises(ValueError):cli.release(self.p,args)
        self.client.request.assert_not_called()

    def test_configured_publication_uses_saved_approval_without_another_founder_command(self):
        self.p['authority']['production_release_enabled']=True
        candidate=self.frozen()
        cli.approve(self.p,self.args('release',digest(candidate),MERGE))
        self.mock_principal.return_value='github-actions[bot]'
        self.client.root='/repos/test/repo';self.client.request.return_value={'html_url':'https://github.com/test/repo/releases/tag/release-R-1'}
        result=cli.release(self.p,argparse.Namespace(phase='publish',candidate_id='R-1',revision=MERGE))
        self.assertEqual(result['released_sha'],MERGE)
        self.assertEqual(self.control.snapshot('R-1')['releases'][0]['state'],'RELEASED')

    def test_disabled_production_cannot_be_enabled_by_a_release_approval(self):
        candidate=self.frozen();cli.approve(self.p,self.args('release',digest(candidate),MERGE))
        self.mock_principal.return_value='github-actions[bot]'
        with self.assertRaisesRegex(ValueError,'disabled'):
            cli.release(self.p,argparse.Namespace(phase='publish',candidate_id='R-1',revision=MERGE))
        self.client.request.assert_not_called()
