import pytest
from types import SimpleNamespace
from app.services.paid_vpn_automation_service import PaidVPNAutomationService
class R:
 def __init__(self,v=None,e=None):self.value=v;self.error=e;self.is_failure=e is not None
class P:
 def __init__(self):self.requests=[]
 async def provision(self,r,actor_user_id):self.requests.append(r);return R(SimpleNamespace(vpn_key_id=9))
class L:
 def __init__(self):self.calls=[]
 async def apply_for_key(self,**kw):self.calls.append(kw);return R({})
class C:
 def __init__(self):self.calls=[]
 async def activate_key(self,**kw):self.calls.append(kw);return R({})
@pytest.mark.asyncio
async def test_paid_order_automation(monkeypatch):
 p,l,c=P(),L(),C();s=PaidVPNAutomationService(db=None,provisioning_service=p,data_limit_service=l,lifecycle_service=c);monkeypatch.setattr('app.services.paid_vpn_automation_service.bus.emit',lambda *a,**k:None)
 r=await s.provision_paid_order(order_id=5,user_id=2,payment_reference='p5');assert r.status=='ready' and p.requests[0].idempotency_key=='paid-order:5' and l.calls[0]['key_id']==9 and c.calls[0]['key_id']==9
@pytest.mark.asyncio
async def test_unpaid_event_is_ignored():
 s=PaidVPNAutomationService(db=None,provisioning_service=P(),data_limit_service=L(),lifecycle_service=C());assert await s.handle_terminal_paid_event(order_id=1,user_id=2,payment_status='pending') is None
