from types import SimpleNamespace
from app.models.server_selection import SelectionRequest,RejectionReason
from app.services.server_selection_service import ServerSelectionEngine
def s(id='SG-01',**x):
 b=dict(public_server_id=id,archived_at=None,enabled=True,is_active=True,maintenance_mode=False,status='online',health_status='ok',api_compatible=True,stale_data=False,country_code='SG',priority=100,weight=1,max_users=100,current_users=20,max_keys=100,existing_key_count=20,traffic_limit_bytes=1000,used_traffic_bytes=100,free_trial_enabled=True,paid_enabled=True,vip_enabled=True); b.update(x); return SimpleNamespace(**b)
def e(rows,**x): return ServerSelectionEngine().select(rows,SelectionRequest(**x))
def test_filters():
 r=e([s('disabled',enabled=False),s('maint',maintenance_mode=True),s('down',status='offline',health_status='offline'),s('full',current_users=100),s('good')],plan='paid',country_code='SG'); assert r.selected.server_id=='good' and r.eligible==1; assert {x.reason for x in r.rejected}>={RejectionReason.DISABLED,RejectionReason.MAINTENANCE,RejectionReason.OFFLINE,RejectionReason.CAPACITY_USERS}
def test_country_plan():
 r=e([s('JP',country_code='JP'),s('NOFREE',free_trial_enabled=False),s('SG')],plan='free',country_code='SG'); assert r.selected.server_id=='SG'; assert any(x.reason==RejectionReason.COUNTRY_MISMATCH for x in r.rejected); assert any(x.reason==RejectionReason.PLAN_UNSUPPORTED for x in r.rejected)
def test_health_load():
 r=e([s('degraded',health_status='degraded',current_users=5),s('healthy',current_users=60)],plan='paid',country_code='SG'); assert r.selected.server_id=='healthy'
def test_tie_break():
 r=e([s('SG-02',priority=50,weight=5),s('SG-01',priority=50,weight=5)],plan='paid',country_code='SG'); assert r.selected.server_id=='SG-01'
def test_no_server_no_key():
 rows=[s('offline',status='offline',health_status='offline'),s('disabled',enabled=False)]; r=e(rows,plan='vip',country_code='SG'); assert r.selected is None and r.no_server_reason=='no_eligible_server'; assert all(not hasattr(x,'vpn_key_id') for x in rows)
