from types import SimpleNamespace
from app.models.server_selection import ServerSelectionPolicy, ServerSelectionRequest, RejectionReason
from app.services.server_selection_service import ServerSelectionService

def row(i='SG-01',**kw):
 b=dict(public_server_id=i,archived_at=None,enabled=True,is_active=True,maintenance_mode=False,status='online',provider_type='outline',health_status='ok',stale_data=False,country_code='SG',priority=10,weight=70,max_users=100,current_users=20,max_keys=100,existing_key_count=20,traffic_limit_bytes=1000,used_traffic_bytes=100,paid_enabled=True,free_trial_enabled=True,vip_enabled=True);b.update(kw);return SimpleNamespace(**b)
def choose(rows,**kw): return ServerSelectionService(None).select_from_rows(rows,ServerSelectionRequest(**kw))
def test_hard_filters_and_reasons():
 r=choose([row('good'),row('disabled',enabled=False),row('maintenance',maintenance_mode=True),row('offline',health_status='offline'),row('wrong',country_code='JP'),row('other',provider_type='wireguard')],workload_type='paid',required_country='SG')
 assert r.selected and r.selected.server_id=='good'; reasons={reason for x in r.rejected for reason in x.reasons}; assert {RejectionReason.DISABLED,RejectionReason.MAINTENANCE,RejectionReason.OFFLINE,RejectionReason.COUNTRY_MISMATCH,RejectionReason.PROVIDER_MISMATCH}<=reasons
def test_degraded_setting_and_unknown_stale():
 assert choose([row(health_status='degraded')],workload_type='paid').selected is None
 p=ServerSelectionPolicy(allow_degraded=True,allow_stale_fallback=True)
 assert ServerSelectionService(None,policy=p).select_from_rows([row(health_status='degraded',stale_data=True)],ServerSelectionRequest(workload_type='paid',require_fresh=True)).selected is not None
def test_headroom_and_traffic():
 r=choose([row('near',current_users=91),row('fulltraffic',used_traffic_bytes=950),row('good')],workload_type='paid'); assert r.selected.server_id=='good'
def test_preferred_country_fallback_and_required_country():
 r=choose([row('JP',country_code='JP')],workload_type='paid',preferred_country='SG',allow_fallback=True); assert r.selected and r.selected.fallback_used
 r=choose([row('JP',country_code='JP')],workload_type='paid',required_country='SG',allow_fallback=True); assert r.selected is None
def test_exclusion_and_required_server():
 r=choose([row('A'),row('B')],workload_type='paid',exclude_server_ids=frozenset({'A'})); assert r.selected.server_id=='B'
 r=choose([row('A'),row('B')],workload_type='paid',required_server_id='B'); assert r.selected.server_id=='B'
def test_scoring_is_explainable_and_no_secrets():
 r=choose([row('A',current_users=80),row('B',current_users=10)],workload_type='paid'); assert r.selected.server_id=='B'; assert r.selected.score.capacity_score>0; assert 'api_url' not in str(r)
def test_free_vip_capabilities_and_dry_run():
 assert choose([row(free_trial_enabled=False)],workload_type='free_trial').selected is None
 assert choose([row(vip_enabled=False)],workload_type='vip').selected is None
 r=choose([row()],workload_type='paid'); assert r.selected.handoff['phase4_key_creation_allowed'] is False
